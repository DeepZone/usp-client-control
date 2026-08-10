import asyncio
import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from google.protobuf.json_format import MessageToDict
from itsdangerous import BadSignature, URLSafeTimedSerializer
from passlib.context import CryptContext
from pydantic import BaseModel, Field

import usp_msg_pb2 as usp
import usp_record_pb2 as record_pb


VERSION = Path("VERSION").read_text().strip() if Path("VERSION").exists() else "0.1.0"
DB_PATH = os.getenv("DATABASE_PATH", "/data/controller.db")
ENDPOINT_ID = os.getenv("CONTROLLER_ENDPOINT_ID", "usp:noisens:controller")
CONTROLLER_TOPIC = os.getenv("MQTT_CONTROLLER_TOPIC", "usp/controller")
AGENT_TOPIC_TEMPLATE = os.getenv("MQTT_AGENT_TOPIC_TEMPLATE", "usp/agent/[[EID]]")
WEBSOCKET_PATH = os.getenv("USP_WEBSOCKET_PATH", "/usp")
WEBSOCKET_PUBLIC_URL = os.getenv("USP_WEBSOCKET_PUBLIC_URL", "")
WEBSOCKET_TOKEN = os.getenv("USP_WEBSOCKET_TOKEN", "")
WEBSOCKET_USERNAME = os.getenv("USP_WEBSOCKET_USERNAME", "box")
# AVM FRITZ!OS WebSocket agents currently do not send HTTP Basic credentials
# (nor the optional v1.usp subprotocol) during their initial connection. The
# per-controller path is therefore a deterministic, non-reversible secret
# derived from the server-side token. It is only shown to administrators.
WEBSOCKET_PATH_KEY = os.getenv(
    "USP_WEBSOCKET_PATH_KEY",
    hashlib.sha256(WEBSOCKET_TOKEN.encode()).hexdigest()[:32] if WEBSOCKET_TOKEN else "",
)
# Query notation deliberately keeps the reverse-proxy location stable at /usp.
# FRITZ!OS appends its endpoint ID to an existing query string correctly.
WEBSOCKET_AGENT_PATH = f"{WEBSOCKET_PATH}?access={WEBSOCKET_PATH_KEY}" if WEBSOCKET_PATH_KEY else WEBSOCKET_PATH
serializer = URLSafeTimedSerializer(os.environ["APP_SECRET"], salt="usp-session")
passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")
db_lock = threading.RLock()
mqtt_client = None
mqtt_connected = False
websocket_agents = {}
websocket_agents_lock = threading.RLock()
main_loop = None
live_clients = set()
poller_task = None
logger = logging.getLogger("usp.websocket")
observed_agents = {}
observed_agents_lock = threading.RLock()
traffic_sample_messages = {}
traffic_sample_messages_lock = threading.RLock()
ripe_cache = {}
ripe_cache_lock = threading.RLock()
GENIEACS_DEFAULT = "http://genieacs:7557"
ROLES = {"admin", "operator", "viewer"}
CUSTOM_LOGO_PATH = "/data/custom-company-logo"

DEFAULT_LIVE_PATHS = [
    # Request the complete object. Besides live resource values this includes
    # identity, firmware-image data and the ProcessStatus.Process instances.
    "Device.DeviceInfo.",
    "Device.IP.Interface.",
    "Device.Ethernet.Interface.",
    "Device.WiFi.Radio.",
    "Device.WiFi.SSID.",
    "Device.WiFi.AccessPoint.",
    "Device.Hosts.Host.",
    "Device.DOCSIS.",
    "Device.DSL.",
    "Device.Optical.",
    "Device.Cellular.",
]
DEFAULT_POLL_INTERVAL = 60
MAX_AUTOMATIC_REFERENCES_PER_TYPE = 1500
MIN_FULL_SCHEMA_ENTRIES = 100


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    with db_lock:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


def initialize_database():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin', active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agents(endpoint_id TEXT PRIMARY KEY, protocol_version TEXT, reply_topic TEXT, oui TEXT, product_class TEXT, serial_number TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, online INTEGER NOT NULL DEFAULT 1, mqtt_topic TEXT, remote_meta TEXT DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS parameters(endpoint_id TEXT NOT NULL, path TEXT NOT NULL, value TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(endpoint_id,path), FOREIGN KEY(endpoint_id) REFERENCES agents(endpoint_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id TEXT UNIQUE NOT NULL, endpoint_id TEXT NOT NULL, action TEXT NOT NULL, request_json TEXT NOT NULL, response_json TEXT, state TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL, completed_at TEXT, FOREIGN KEY(endpoint_id) REFERENCES agents(endpoint_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, action TEXT NOT NULL, target TEXT, detail TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS parameter_history(id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint_id TEXT NOT NULL, path TEXT NOT NULL, value TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS parameter_history_lookup ON parameter_history(endpoint_id,path,created_at);
        CREATE TABLE IF NOT EXISTS traffic_counters(endpoint_id TEXT PRIMARY KEY, bytes_received INTEGER NOT NULL, bytes_sent INTEGER NOT NULL, sampled_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS traffic_samples(endpoint_id TEXT NOT NULL, bucket_start TEXT NOT NULL, down_bps REAL NOT NULL, up_bps REAL NOT NULL, PRIMARY KEY(endpoint_id,bucket_start));
        CREATE INDEX IF NOT EXISTS traffic_samples_time ON traffic_samples(bucket_start,endpoint_id);
        CREATE TABLE IF NOT EXISTS model_schema(endpoint_id TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', access TEXT NOT NULL DEFAULT '', value_type TEXT NOT NULL DEFAULT '', value_change TEXT NOT NULL DEFAULT '', metadata TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL, PRIMARY KEY(endpoint_id,path,kind,name));
        CREATE INDEX IF NOT EXISTS model_schema_lookup ON model_schema(endpoint_id,kind,path);
        CREATE TABLE IF NOT EXISTS speed_tests(id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id TEXT UNIQUE NOT NULL, endpoint_id TEXT NOT NULL, direction TEXT NOT NULL, state TEXT NOT NULL, duration INTEGER NOT NULL, result_json TEXT, error TEXT, created_at TEXT NOT NULL, completed_at TEXT, FOREIGN KEY(endpoint_id) REFERENCES agents(endpoint_id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS speed_tests_lookup ON speed_tests(endpoint_id,created_at);
        """)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "display_name" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
        if "updated_at" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        username = os.getenv("ADMIN_USERNAME", "admin")
        existing = connection.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not existing:
            connection.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)", (username, passwords.hash(os.environ["ADMIN_PASSWORD"]), "admin", now()))


def migrate_legacy_traffic():
    with db() as connection:
        if connection.execute("SELECT 1 FROM traffic_counters LIMIT 1").fetchone():
            return
        paths = ("Device.IP.Interface.1.Stats.BytesReceived", "Device.IP.Interface.1.Stats.BytesSent")
        rows = connection.execute("SELECT endpoint_id,path,value,created_at FROM parameter_history WHERE path IN (?,?) ORDER BY endpoint_id,path,created_at", paths).fetchall()
        previous, latest, buckets = {}, {}, {}
        for row in rows:
            key = (row["endpoint_id"], row["path"])
            try:
                timestamp = datetime.fromisoformat(row["created_at"]).timestamp()
                counter = int(row["value"])
            except (TypeError, ValueError):
                continue
            earlier = previous.get(key)
            previous[key] = (timestamp, counter)
            latest.setdefault(row["endpoint_id"], {})[row["path"]] = (timestamp, counter)
            if not earlier or timestamp <= earlier[0] or counter < earlier[1]:
                continue
            bucket = datetime.fromtimestamp(int(timestamp // 60 * 60), timezone.utc).isoformat()
            direction = "down_bps" if row["path"] == paths[0] else "up_bps"
            buckets.setdefault((row["endpoint_id"], bucket), {})[direction] = (counter - earlier[1]) * 8 / (timestamp - earlier[0])
        for (endpoint, bucket), rates in buckets.items():
            connection.execute("INSERT OR IGNORE INTO traffic_samples(endpoint_id,bucket_start,down_bps,up_bps) VALUES(?,?,?,?)", (endpoint, bucket, rates.get("down_bps", 0), rates.get("up_bps", 0)))
        for endpoint, counters in latest.items():
            if paths[0] not in counters or paths[1] not in counters:
                continue
            sampled_at = datetime.fromtimestamp(max(counters[paths[0]][0], counters[paths[1]][0]), timezone.utc).isoformat()
            connection.execute("INSERT OR IGNORE INTO traffic_counters(endpoint_id,bytes_received,bytes_sent,sampled_at) VALUES(?,?,?,?)", (endpoint, counters[paths[0]][1], counters[paths[1]][1], sampled_at))


def setting(key, default=""):
    with db() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def save_setting(key, value):
    with db() as connection:
        connection.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (key, str(value), now()))


def wan_ip_from_parameters(parameters):
    preferred = ["Device.IP.Interface.1.IPv4Address.1.IPAddress", "Device.IP.Interface.1.IPv6Address.1.IPAddress"]
    values = {row["path"]: row["value"] for row in parameters}
    candidates = [values.get(path) for path in preferred]
    candidates.extend(row["value"] for row in parameters if re.match(r"^Device\.IP\.Interface\.(?!1000\.)\d+\.IPv[46]Address\.\d+\.IPAddress$", row["path"]))
    for candidate in candidates:
        try:
            address = ipaddress.ip_address(str(candidate or "").split("%", 1)[0])
        except ValueError:
            continue
        if not address.is_unspecified and not address.is_loopback and not address.is_link_local:
            return str(address)
    return ""


def ripe_network_info(address):
    """Resolve a public WAN address to its originating ASN and RIPE holder."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return {"ip": address, "public": False, "provider": "", "asn": "", "prefix": ""}
    if not ip.is_global:
        return {"ip": str(ip), "public": False, "provider": "", "asn": "", "prefix": ""}
    with ripe_cache_lock:
        cached = ripe_cache.get(str(ip))
        if cached and time.time() - cached[0] < 86400:
            return cached[1]
    result = {"ip": str(ip), "public": True, "provider": "", "asn": "", "prefix": ""}
    try:
        query = urllib.parse.urlencode({"resource": str(ip)})
        with urllib.request.urlopen(f"https://stat.ripe.net/data/network-info/data.json?{query}", timeout=5) as response:
            network = json.load(response).get("data", {})
        asns = network.get("asns") or []
        result["prefix"] = str(network.get("prefix") or "")
        if asns:
            result["asn"] = f"AS{asns[0]}"
            as_query = urllib.parse.urlencode({"resource": result["asn"]})
            with urllib.request.urlopen(f"https://stat.ripe.net/data/as-overview/data.json?{as_query}", timeout=5) as response:
                overview = json.load(response).get("data", {})
            result["provider"] = str(overview.get("holder") or "").strip()
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        pass
    with ripe_cache_lock:
        ripe_cache[str(ip)] = (time.time(), result)
    return result


def live_paths():
    try:
        paths = json.loads(setting("live_paths", json.dumps(DEFAULT_LIVE_PATHS)))
        return [str(path).strip() for path in paths if str(path).strip()]
    except (TypeError, json.JSONDecodeError):
        return list(DEFAULT_LIVE_PATHS)


def live_paths_for_agent(endpoint):
    paths = live_paths()
    with db() as connection:
        fiber = connection.execute(
            "SELECT 1 FROM parameters WHERE endpoint_id=? AND path LIKE 'Device.Optical.%' AND value<>'' LIMIT 1",
            (endpoint,),
        ).fetchone()
    if fiber and "Device.XPON." not in paths:
        paths.append("Device.XPON.")
    return paths


def supported_live_paths(endpoint):
    """Return configured live roots that the agent's current model supports."""
    configured = live_paths()
    with db() as connection:
        schema_paths = [row["path"] for row in connection.execute(
            "SELECT path FROM model_schema WHERE endpoint_id=?", (endpoint,)
        ).fetchall()]
    if not schema_paths:
        return configured
    paths = [root for root in configured if any(path.startswith(root) or root.startswith(path) for path in schema_paths)]
    if any(path.startswith("Device.XPON.") for path in schema_paths) and "Device.XPON." not in paths:
        paths.append("Device.XPON.")
    return paths


def poll_interval():
    try:
        return min(max(int(setting("live_poll_interval", DEFAULT_POLL_INTERVAL)), 15), 3600)
    except (TypeError, ValueError):
        return DEFAULT_POLL_INTERVAL


def path_in_live_profile(path, configured=None):
    configured = configured or live_paths()
    return any(path == root or path.startswith(root) for root in configured)


def schema_template_regex(path):
    parts = re.split(r"(\{i\})", path)
    return re.compile("^" + "".join(r"\d+" if part == "{i}" else re.escape(part) for part in parts) + "$")


def resolve_template_instances(template, resolved_paths):
    if "{i}" not in template:
        return [template]
    pieces = re.split(r"(\{i\})", template)
    pattern = re.compile("^" + "".join(r"(\d+)" if piece == "{i}" else re.escape(piece) for piece in pieces) + ".*")
    results = []
    for candidate in resolved_paths:
        match = pattern.match(candidate)
        if not match:
            continue
        values = iter(match.groups())
        results.append("".join(next(values) if piece == "{i}" else piece for piece in pieces))
    return sorted(dict.fromkeys(results))


def subscription_reference(path):
    return path.replace(".{i}.", ".").replace("{i}.", "")


def pack_subscription_references(paths, maximum_length=240):
    groups = []
    current = []
    length = 0
    for path in paths:
        added = len(path) + (1 if current else 0)
        if current and length + added > maximum_length:
            groups.append(",".join(current))
            current, length = [], 0
        current.append(path)
        length += len(path) + (1 if len(current) > 1 else 0)
    if current:
        groups.append(",".join(current))
    return groups


def automatic_live_profile(endpoint):
    """Derive subscriptions and a bounded polling fallback from this agent's schema."""
    configured = live_paths_for_agent(endpoint)
    profile = {"ValueChange": [], "Event": [], "ObjectCreation": [], "ObjectDeletion": [], "OperationComplete": []}
    with db() as connection:
        schema = connection.execute(
            "SELECT path,kind,value_change,value_type,metadata FROM model_schema WHERE endpoint_id=? ORDER BY path,kind",
            (endpoint,),
        ).fetchall()
        resolved = [row["path"] for row in connection.execute(
            "SELECT path FROM parameters WHERE endpoint_id=? ORDER BY path", (endpoint,)
        ).fetchall()]
    polling = []
    allowed_resolved = set()
    allowed_templates = []
    event_templates = []
    operation_templates = []
    poll_name = re.compile(
        r"(Status|Enable|Active|UpTime|Bytes|Packets|Rate|Speed|Power|SNR|MSE|RSRP|RSRQ|RSSI|SINR|"
        r"Signal|Noise|Quality|Utilization|Usage|Load|Errors?|Temperature|Voltage|Current|Latency|Count)$",
        re.I,
    )
    for row in schema:
        path = row["path"]
        if not path_in_live_profile(path, configured):
            continue
        if row["kind"] == "parameter" and row["value_change"] == "VALUE_CHANGE_ALLOWED":
            allowed_templates.append(path)
            if "{i}" in path:
                matcher = schema_template_regex(path)
                allowed_resolved.update(item for item in resolved if matcher.match(item))
            elif path in resolved:
                allowed_resolved.add(path)
        elif row["kind"] == "parameter" and poll_name.search(path):
            if "{i}" in path:
                matcher = schema_template_regex(path)
                polling.extend(item for item in resolved if matcher.match(item))
            elif path in resolved:
                polling.append(path)
        elif row["kind"] == "event":
            event_templates.append(path)
        elif row["kind"] == "command" and row["value_type"] == "CMD_ASYNC":
            operation_templates.append(path)
        elif row["kind"] == "object":
            metadata = json.loads(row["metadata"] or "{}")
            if metadata.get("multi_instance"):
                creation = (path[:-4] if path.endswith("{i}.") else subscription_reference(path)).replace("{i}", "*")
                deletion = path.replace("{i}", "*")
                profile["ObjectCreation"].append(creation)
                profile["ObjectDeletion"].append(deletion)

    # USP allows an Object Path for these notification types. One configured
    # root therefore covers every supported current and future instance below it.
    profile["ValueChange"] = [root for root in configured if any(path.startswith(root) for path in allowed_templates)]
    profile["Event"] = [root for root in configured if any(path.startswith(root) for path in event_templates)]
    profile["OperationComplete"] = [root for root in configured if any(path.startswith(root) for path in operation_templates)]
    for kind in profile:
        profile[kind] = sorted(dict.fromkeys(path for path in profile[kind] if len(path) <= 256))
    order = ("ValueChange", "Event", "ObjectCreation", "ObjectDeletion", "OperationComplete")
    for kind in order:
        profile[kind] = profile[kind][:MAX_AUTOMATIC_REFERENCES_PER_TYPE]
    profile["poll_paths"] = [path for path in sorted(dict.fromkeys(polling)) if path not in allowed_resolved][:160]
    if not schema:
        profile["poll_paths"] = configured
    profile["poll_interval"] = poll_interval()
    profile["subscription_count"] = sum(len(profile[kind]) for kind in order)
    profile["capability_counts"] = {
        "ValueChange": len(allowed_templates),
        "Event": len(event_templates),
        "OperationComplete": len(operation_templates),
        "ObjectCreation": len(profile["ObjectCreation"]),
        "ObjectDeletion": len(profile["ObjectDeletion"]),
    }
    return profile


def emit_live(event_type, endpoint=None, payload=None):
    if not main_loop or not main_loop.is_running():
        return
    event = {"type": event_type, "endpoint_id": endpoint, "timestamp": now(), "payload": payload or {}}
    def distribute():
        for queue in tuple(live_clients):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)
    main_loop.call_soon_threadsafe(distribute)


def record_event(endpoint, kind, detail):
    with db() as connection:
        connection.execute("INSERT INTO events(endpoint_id,kind,detail,created_at) VALUES(?,?,?,?)", (endpoint, kind, json.dumps(detail, ensure_ascii=False), now()))
    emit_live("event", endpoint, {"kind": kind, "detail": detail})


def audit(user, action, target="", detail=""):
    with db() as connection:
        connection.execute("INSERT INTO audit(username,action,target,detail,created_at) VALUES(?,?,?,?,?)", (user, action, target, detail, now()))


def current_user(request: Request, admin=False):
    token = request.cookies.get("usp_session")
    if not token:
        raise HTTPException(401, "Anmeldung erforderlich")
    try:
        session = serializer.loads(token, max_age=12 * 3600)
    except BadSignature:
        raise HTTPException(401, "Sitzung ungültig")
    with db() as connection:
        user = connection.execute("SELECT id,username,display_name,role,active,created_at,updated_at FROM users WHERE id=?", (session.get("id"),)).fetchone()
    if not user or not user["active"]:
        raise HTTPException(401, "Benutzerkonto nicht aktiv")
    if admin and user["role"] != "admin":
        raise HTTPException(403, "Administratorrechte erforderlich")
    return dict(user)


def upsert_agent(endpoint, version="", reply_topic="", mqtt_topic="", transport="mqtt", **identity):
    timestamp = now()
    with db() as connection:
        existing = connection.execute("SELECT endpoint_id,remote_meta FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone()
        if existing:
            try:
                remote_meta = json.loads(existing["remote_meta"] or "{}")
            except json.JSONDecodeError:
                remote_meta = {}
            transports = set(remote_meta.get("transports") or [])
            transports.add(transport)
            remote_meta["transports"] = sorted(transports)
            remote_meta[f"{transport}_last_seen"] = timestamp
            connection.execute("UPDATE agents SET protocol_version=COALESCE(NULLIF(?,''),protocol_version),reply_topic=COALESCE(NULLIF(?,''),reply_topic),mqtt_topic=COALESCE(NULLIF(?,''),mqtt_topic),last_seen=?,online=1,oui=COALESCE(NULLIF(?,''),oui),product_class=COALESCE(NULLIF(?,''),product_class),serial_number=COALESCE(NULLIF(?,''),serial_number),remote_meta=? WHERE endpoint_id=?", (version, reply_topic, mqtt_topic, timestamp, identity.get("oui", ""), identity.get("product_class", ""), identity.get("serial_number", ""), json.dumps(remote_meta, ensure_ascii=False), endpoint))
        else:
            remote_meta = {"transports": [transport], f"{transport}_last_seen": timestamp}
            connection.execute("INSERT INTO agents(endpoint_id,protocol_version,reply_topic,oui,product_class,serial_number,first_seen,last_seen,online,mqtt_topic,remote_meta) VALUES(?,?,?,?,?,?,?,?,1,?,?)", (endpoint, version, reply_topic, identity.get("oui", ""), identity.get("product_class", ""), identity.get("serial_number", ""), timestamp, timestamp, mqtt_topic, json.dumps(remote_meta, ensure_ascii=False)))
    emit_live("agent", endpoint, {"last_seen": timestamp, "online": True, "protocol_version": version, "transport": transport})


def extract_payload(record):
    kind = record.WhichOneof("record_type")
    if kind == "no_session_context":
        return record.no_session_context.payload
    if kind == "session_context":
        return b"".join(record.session_context.payload)
    return None


def json_message(message):
    return MessageToDict(message, preserving_proto_field_name=True, always_print_fields_with_no_presence=True)


def store_get_parameters(endpoint, response):
    rows = []
    timestamp = now()
    for requested in response.req_path_results:
        for resolved in requested.resolved_path_results:
            for name, value in resolved.result_params.items():
                path = name if name.startswith("Device.") else resolved.resolved_path + name
                rows.append((endpoint, path, value, timestamp))
    if rows:
        with db() as connection:
            current = {row["path"]: row["value"] for row in connection.execute("SELECT path,value FROM parameters WHERE endpoint_id=?", (endpoint,)).fetchall()}
            history_rows = []
            metric_pattern = re.compile(r"(Usage|Utilization|Bytes(?:Received|Sent)?|Packets|Power|SNR|RSRP|RSRQ|RSSI|Rate|Latency|Errors|Timeouts?|UpTime|Free|Total|Current|Temperature|Signal|Noise|Quality|Speed|Load|Count)$", re.I)
            for _, path, value, updated in rows:
                traffic_counter = path in {"Device.IP.Interface.1.Stats.BytesReceived", "Device.IP.Interface.1.Stats.BytesSent"}
                radio_sample = re.search(r"(RSRP|RSRQ|RSSI)$", path, re.I)
                if traffic_counter or (current.get(path) == value and not radio_sample) or not metric_pattern.search(path):
                    continue
                try:
                    float(value)
                except (TypeError, ValueError):
                    continue
                history_rows.append((endpoint, path, value, updated))
            connection.executemany("INSERT INTO parameters(endpoint_id,path,value,updated_at) VALUES(?,?,?,?) ON CONFLICT(endpoint_id,path) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", rows)
            if history_rows:
                connection.executemany("INSERT INTO parameter_history(endpoint_id,path,value,created_at) VALUES(?,?,?,?)", history_rows)
                connection.execute("DELETE FROM parameter_history WHERE created_at < datetime('now','-7 days')")
            traffic = {path: value for _, path, value, _ in rows if path in {"Device.IP.Interface.1.Stats.BytesReceived", "Device.IP.Interface.1.Stats.BytesSent"}}
            if len(traffic) == 2:
                try:
                    received = int(traffic["Device.IP.Interface.1.Stats.BytesReceived"])
                    sent = int(traffic["Device.IP.Interface.1.Stats.BytesSent"])
                except (TypeError, ValueError):
                    received = sent = None
            else:
                received = sent = None
            if received is not None and sent is not None:
                previous = connection.execute("SELECT bytes_received,bytes_sent,sampled_at FROM traffic_counters WHERE endpoint_id=?", (endpoint,)).fetchone()
                if previous:
                    seconds = datetime.fromisoformat(timestamp).timestamp() - datetime.fromisoformat(previous["sampled_at"]).timestamp()
                    if seconds > 0 and received >= previous["bytes_received"] and sent >= previous["bytes_sent"]:
                        down_bps = (received - previous["bytes_received"]) * 8 / seconds
                        up_bps = (sent - previous["bytes_sent"]) * 8 / seconds
                        bucket = datetime.fromtimestamp(int(datetime.fromisoformat(timestamp).timestamp() // 60 * 60), timezone.utc).isoformat()
                        connection.execute("INSERT INTO traffic_samples(endpoint_id,bucket_start,down_bps,up_bps) VALUES(?,?,?,?) ON CONFLICT(endpoint_id,bucket_start) DO UPDATE SET down_bps=excluded.down_bps,up_bps=excluded.up_bps", (endpoint, bucket, down_bps, up_bps))
                connection.execute("INSERT INTO traffic_counters(endpoint_id,bytes_received,bytes_sent,sampled_at) VALUES(?,?,?,?) ON CONFLICT(endpoint_id) DO UPDATE SET bytes_received=excluded.bytes_received,bytes_sent=excluded.bytes_sent,sampled_at=excluded.sampled_at", (endpoint, received, sent, timestamp))
                connection.execute("DELETE FROM traffic_samples WHERE bucket_start < datetime('now','-8 days')")
        emit_live("parameters", endpoint, {"values": [{"path": path, "value": value, "updated_at": updated} for _, path, value, updated in rows]})


def agent_is_observed(endpoint):
    with observed_agents_lock:
        expires = observed_agents.get(endpoint, 0)
        if expires <= time.time():
            observed_agents.pop(endpoint, None)
            return False
        return True


def observe_agent(endpoint, seconds=900):
    with observed_agents_lock:
        observed_agents[endpoint] = time.time() + seconds


async def traffic_sampler(interval, observed):
    """Spread lightweight WAN samples evenly across a fixed fleet interval."""
    await asyncio.sleep(20 if observed else 30)
    paths = ["Device.IP.Interface.1.Stats.BytesReceived", "Device.IP.Interface.1.Stats.BytesSent"]
    while True:
        cycle_started = time.monotonic()
        with traffic_sample_messages_lock:
            expired = time.time() - 3600
            for msg_id, created_at in list(traffic_sample_messages.items()):
                if created_at < expired:
                    traffic_sample_messages.pop(msg_id, None)
        # A quiet MQTT agent may not send unsolicited messages for hours. Keep
        # agents seen during the last day in the base rotation; a successful
        # sample refreshes last_seen automatically.
        cutoff = datetime.fromtimestamp(time.time() - 86400, timezone.utc).isoformat()
        try:
            with db() as connection:
                agents = connection.execute("SELECT endpoint_id,protocol_version,reply_topic FROM agents WHERE last_seen>=? ORDER BY endpoint_id", (cutoff,)).fetchall()
            agents = [agent for agent in agents if agent_is_observed(agent["endpoint_id"]) is observed]
            spacing = interval / max(1, len(agents))
            for agent in agents:
                message = None
                try:
                    message = build_message("get", {"paths": paths, "max_depth": 0})
                    with traffic_sample_messages_lock:
                        traffic_sample_messages[message.header.msg_id] = time.time()
                    send_usp_message(agent["endpoint_id"], message, agent["protocol_version"] or "1.3")
                except Exception:
                    if message is not None:
                        with traffic_sample_messages_lock:
                            traffic_sample_messages.pop(message.header.msg_id, None)
                    pass
                await asyncio.sleep(spacing)
        except Exception:
            pass
        remaining = interval - (time.monotonic() - cycle_started)
        if remaining > 0:
            await asyncio.sleep(remaining)


def store_supported_model(endpoint, response):
    rows = []
    timestamp = now()
    for requested in response.req_obj_results:
        for obj in requested.supported_objs:
            obj_path = obj.supported_obj_path
            rows.append((endpoint, obj_path, "object", "", usp.GetSupportedDMResp.ObjAccessType.Name(obj.access), "", "", json.dumps({
                "multi_instance": obj.is_multi_instance,
                "divergent_paths": list(obj.divergent_paths),
                "unique_key_sets": [list(item.key_names) for item in obj.unique_key_sets],
            }, ensure_ascii=False), timestamp))
            for param in obj.supported_params:
                rows.append((endpoint, obj_path + param.param_name, "parameter", param.param_name,
                    usp.GetSupportedDMResp.ParamAccessType.Name(param.access),
                    usp.GetSupportedDMResp.ParamValueType.Name(param.value_type),
                    usp.GetSupportedDMResp.ValueChangeType.Name(param.value_change), "{}", timestamp))
            for command in obj.supported_commands:
                rows.append((endpoint, obj_path + command.command_name, "command", command.command_name, "",
                    usp.GetSupportedDMResp.CmdType.Name(command.command_type), "", json.dumps({
                        "input_args": list(command.input_arg_names), "output_args": list(command.output_arg_names)
                    }, ensure_ascii=False), timestamp))
            for event in obj.supported_events:
                rows.append((endpoint, obj_path + event.event_name, "event", event.event_name, "", "", "",
                    json.dumps({"args": list(event.arg_names)}, ensure_ascii=False), timestamp))
    if not rows:
        return
    with db() as connection:
        connection.execute("DELETE FROM model_schema WHERE endpoint_id=?", (endpoint,))
        connection.executemany("INSERT INTO model_schema(endpoint_id,path,kind,name,access,value_type,value_change,metadata,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", rows)
    emit_live("schema", endpoint, {"count": len(rows), "updated_at": timestamp})
    # A model refresh may follow a changed access medium. Read only roots the
    # freshly synchronized model actually exposes, avoiding invalid paths.
    paths = supported_live_paths(endpoint)
    if paths:
        try:
            dispatch_job(endpoint, "get", {"paths": paths, "max_depth": 0}, "system")
        except Exception as exc:
            record_event(endpoint, "MODEL_REFRESH_ERROR", {"error": str(exc)})


def websocket_agent_connected(endpoint):
    with websocket_agents_lock:
        return endpoint in websocket_agents


async def send_websocket_record(endpoint, wire_record):
    with websocket_agents_lock:
        websocket = websocket_agents.get(endpoint)
    if not websocket:
        raise RuntimeError("WebSocket-Agent nicht verbunden")
    await websocket.send_bytes(wire_record)


def publish_websocket_message(endpoint, message, version="1.3"):
    if not main_loop or not main_loop.is_running():
        raise RuntimeError("WebSocket-Endpunkt nicht bereit")
    wire_record = record_pb.Record(version=version or "1.3", to_id=endpoint, from_id=ENDPOINT_ID,
                                   payload_security=record_pb.Record.PLAINTEXT)
    wire_record.no_session_context.payload = message.SerializeToString()
    future = asyncio.run_coroutine_threadsafe(send_websocket_record(endpoint, wire_record.SerializeToString()), main_loop)
    future.result(timeout=10)


def send_notify_response(endpoint, topic, msg_id, subscription_id, version, transport="mqtt"):
    message = usp.Msg()
    message.header.msg_id = msg_id
    message.header.msg_type = usp.Header.NOTIFY_RESP
    message.body.response.notify_resp.subscription_id = subscription_id
    send_usp_message(endpoint, message, version, transport, topic)


def handle_usp_message(endpoint, topic, reply_topic, version, payload, transport="mqtt"):
    message = usp.Msg()
    message.ParseFromString(payload)
    body_type = message.body.WhichOneof("msg_body")
    msg_type = usp.Header.MsgType.Name(message.header.msg_type)
    data = json_message(message)
    with traffic_sample_messages_lock:
        internal_traffic_sample = traffic_sample_messages.pop(message.header.msg_id, None) is not None
    tracked_response = True
    if body_type in {"response", "error"}:
        with db() as connection:
            tracked_response = connection.execute("SELECT 1 FROM jobs WHERE msg_id=?", (message.header.msg_id,)).fetchone() is not None
    if not internal_traffic_sample and (body_type not in {"response", "error"} or tracked_response):
        record_event(endpoint, msg_type, data)
    if body_type == "response" or body_type == "error":
        state = "failed" if body_type == "error" else "complete"
        error = message.body.error.err_msg if body_type == "error" else None
        if body_type == "response" and message.body.response.WhichOneof("resp_type") == "operate_resp":
            # An asynchronous operation is only accepted by OPERATE_RESP. Its
            # actual result follows later in an OperationComplete notification.
            if any(item.WhichOneof("operation_resp") == "req_obj_path" for item in message.body.response.operate_resp.operation_results):
                state = "running"
        with db() as connection:
            connection.execute("UPDATE jobs SET state=?,response_json=?,error=?,completed_at=? WHERE msg_id=?", (state, json.dumps(data, ensure_ascii=False), error, None if state == "running" else now(), message.header.msg_id))
            connection.execute("UPDATE speed_tests SET state=?,error=?,completed_at=? WHERE msg_id=?", (state, error, None if state == "running" else now(), message.header.msg_id))
        if body_type == "response" and message.body.response.WhichOneof("resp_type") == "get_resp":
            store_get_parameters(endpoint, message.body.response.get_resp)
        elif body_type == "response" and message.body.response.WhichOneof("resp_type") == "get_supported_dm_resp":
            store_supported_model(endpoint, message.body.response.get_supported_dm_resp)
    elif body_type == "request" and message.body.request.WhichOneof("req_type") == "notify":
        notification = message.body.request.notify
        notification_type = notification.WhichOneof("notification")
        if notification_type == "on_board_req":
            onboard = notification.on_board_req
            upsert_agent(endpoint, version, reply_topic, topic, oui=onboard.oui, product_class=onboard.product_class, serial_number=onboard.serial_number)
        elif notification_type == "value_change":
            value = notification.value_change
            timestamp = now()
            with db() as connection:
                connection.execute("INSERT INTO parameters(endpoint_id,path,value,updated_at) VALUES(?,?,?,?) ON CONFLICT(endpoint_id,path) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (endpoint, value.param_path, value.param_value, timestamp))
                connection.execute("INSERT INTO parameter_history(endpoint_id,path,value,created_at) VALUES(?,?,?,?)", (endpoint, value.param_path, value.param_value, timestamp))
                connection.execute("DELETE FROM parameter_history WHERE created_at < datetime('now','-7 days')")
            emit_live("parameter", endpoint, {"path": value.param_path, "value": value.param_value, "updated_at": timestamp})
        elif notification_type == "event":
            event = notification.event
            emit_live("usp_event", endpoint, {"path": event.obj_path, "name": event.event_name, "parameters": dict(event.params)})
        elif notification_type == "obj_creation":
            created = notification.obj_creation
            emit_live("object_created", endpoint, {"path": created.obj_path, "unique_keys": dict(created.unique_keys)})
            try:
                dispatch_job(endpoint, "get", {"paths": [created.obj_path], "max_depth": 0}, "system")
            except Exception as exc:
                record_event(endpoint, "LIVE_REFRESH_ERROR", {"path": created.obj_path, "error": str(exc)})
        elif notification_type == "obj_deletion":
            deleted = notification.obj_deletion
            with db() as connection:
                connection.execute("DELETE FROM parameters WHERE endpoint_id=? AND path LIKE ?", (endpoint, deleted.obj_path + "%"))
            emit_live("object_deleted", endpoint, {"path": deleted.obj_path})
        elif notification_type == "oper_complete":
            operation = notification.oper_complete
            operation_kind = operation.WhichOneof("operation_resp")
            operation_data = dict(operation.req_output_args.output_args) if operation_kind == "req_output_args" else {}
            operation_error = operation.cmd_failure.err_msg if operation_kind == "cmd_failure" else None
            operation_state = "failed" if operation_error else "complete"
            completed = now()
            with db() as connection:
                connection.execute(
                    "UPDATE jobs SET state=?,response_json=?,error=?,completed_at=? WHERE msg_id=?",
                    (operation_state, json.dumps(data, ensure_ascii=False), operation_error, completed, operation.command_key),
                )
                connection.execute(
                    "UPDATE speed_tests SET state=?,result_json=?,error=?,completed_at=? WHERE msg_id=?",
                    (operation_state, json.dumps(operation_data, ensure_ascii=False), operation_error, completed, operation.command_key),
                )
            emit_live("speedtest", endpoint, {"msg_id": operation.command_key, "state": operation_state})
            emit_live("operation_complete", endpoint, {
                "path": operation.obj_path,
                "command": operation.command_name,
                "command_key": operation.command_key,
                "result": data,
            })
        if notification.send_resp:
            send_notify_response(endpoint, reply_topic, message.header.msg_id, notification.subscription_id, version, transport)


def on_connect(client, userdata, flags, reason_code, properties):
    global mqtt_connected
    mqtt_connected = reason_code == 0
    if mqtt_connected:
        client.subscribe(CONTROLLER_TOPIC + "/#", qos=1)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    global mqtt_connected
    mqtt_connected = False


def on_message(client, userdata, mqtt_message):
    try:
        record = record_pb.Record()
        record.ParseFromString(mqtt_message.payload)
        endpoint = record.from_id
        reply_topic = getattr(mqtt_message.properties, "ResponseTopic", None) or ""
        kind = record.WhichOneof("record_type")
        if kind == "mqtt_connect":
            reply_topic = record.mqtt_connect.subscribed_topic or reply_topic
            upsert_agent(endpoint, record.version, reply_topic, mqtt_message.topic, "mqtt")
            record_event(endpoint, "MQTT_CONNECT", {"version": record.version, "reply_topic": reply_topic})
            return
        upsert_agent(endpoint, record.version, reply_topic, mqtt_message.topic, "mqtt")
        payload = extract_payload(record)
        if payload:
            handle_usp_message(endpoint, mqtt_message.topic, reply_topic or agent_topic(endpoint), record.version, payload, "mqtt")
    except Exception as exc:
        record_event(None, "DECODE_ERROR", {"topic": mqtt_message.topic, "error": str(exc)})


def agent_topic(endpoint):
    with db() as connection:
        row = connection.execute("SELECT reply_topic FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone()
    if row and row["reply_topic"]:
        return row["reply_topic"]
    return AGENT_TOPIC_TEMPLATE.replace("[[EID]]", endpoint)


def publish_message(endpoint, topic, message, version="1.3"):
    if not mqtt_client or not mqtt_connected:
        raise RuntimeError("MQTT-Broker nicht verbunden")
    record = record_pb.Record(version=version or "1.3", to_id=endpoint, from_id=ENDPOINT_ID, payload_security=record_pb.Record.PLAINTEXT)
    record.no_session_context.payload = message.SerializeToString()
    properties = Properties(PacketTypes.PUBLISH)
    properties.ResponseTopic = CONTROLLER_TOPIC
    properties.ContentType = "application/vnd.bbf.usp.msg"
    result = mqtt_client.publish(topic, record.SerializeToString(), qos=1, properties=properties)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT Publish fehlgeschlagen: {result.rc}")


def send_usp_message(endpoint, message, version="1.3", transport="auto", topic=""):
    """Send one USP record without changing the established MQTT path."""
    with db() as connection:
        row = connection.execute("SELECT mqtt_topic,reply_topic FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone()
    mqtt_available = bool(mqtt_connected and row and row["mqtt_topic"])
    mqtt_topic = topic or (row["reply_topic"] if row else "") or agent_topic(endpoint)
    websocket_available = websocket_agent_connected(endpoint)
    if transport == "mqtt":
        return publish_message(endpoint, mqtt_topic, message, version)
    if transport == "websocket":
        return publish_websocket_message(endpoint, message, version)
    # Existing MQTT agents continue to use their current broker route. A
    # WebSocket-only agent is selected only when no MQTT transport is known.
    if mqtt_available:
        try:
            return publish_message(endpoint, mqtt_topic, message, version)
        except Exception:
            if not websocket_available:
                raise
    if websocket_available:
        return publish_websocket_message(endpoint, message, version)
    raise RuntimeError("Kein erreichbarer USP-Transport (MQTT oder WebSocket)")


def build_message(action, payload):
    message = usp.Msg()
    message.header.msg_id = secrets.token_hex(12)
    request = message.body.request
    if action == "get":
        message.header.msg_type = usp.Header.GET
        request.get.param_paths.extend(payload.get("paths") or ["Device."])
        request.get.max_depth = int(payload.get("max_depth", 0))
    elif action == "get_instances":
        message.header.msg_type = usp.Header.GET_INSTANCES
        request.get_instances.obj_paths.extend(payload.get("paths") or ["Device."])
        request.get_instances.first_level_only = bool(payload.get("first_level_only", False))
    elif action == "get_supported_dm":
        message.header.msg_type = usp.Header.GET_SUPPORTED_DM
        request.get_supported_dm.obj_paths.extend(payload.get("paths") or ["Device."])
        request.get_supported_dm.first_level_only = bool(payload.get("first_level_only", False))
        request.get_supported_dm.return_commands = True
        request.get_supported_dm.return_events = True
        request.get_supported_dm.return_params = True
        request.get_supported_dm.return_unique_key_sets = True
    elif action == "set":
        message.header.msg_type = usp.Header.SET
        request.set.allow_partial = bool(payload.get("allow_partial", False))
        update = request.set.update_objs.add(obj_path=payload["object_path"])
        for item in payload["parameters"]:
            update.param_settings.add(param=item["name"], value=str(item["value"]), required=bool(item.get("required", True)))
    elif action == "add":
        message.header.msg_type = usp.Header.ADD
        request.add.allow_partial = bool(payload.get("allow_partial", False))
        create = request.add.create_objs.add(obj_path=payload["object_path"])
        for item in payload.get("parameters", []):
            create.param_settings.add(param=item["name"], value=str(item["value"]), required=bool(item.get("required", True)))
    elif action == "delete":
        message.header.msg_type = usp.Header.DELETE
        request.delete.allow_partial = bool(payload.get("allow_partial", False))
        request.delete.obj_paths.extend(payload["paths"])
    elif action == "operate":
        message.header.msg_type = usp.Header.OPERATE
        request.operate.command = payload["command"]
        request.operate.command_key = payload.get("command_key") or message.header.msg_id
        request.operate.send_resp = True
        request.operate.input_args.update({str(k): str(v) for k, v in payload.get("input_args", {}).items()})
    else:
        raise ValueError("Nicht unterstützte USP-Aktion")
    return message


def start_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=ENDPOINT_ID, protocol=mqtt.MQTTv5)
    mqtt_client.username_pw_set(os.getenv("MQTT_CONTROLLER_USERNAME", "controller"), os.environ["MQTT_CONTROLLER_PASSWORD"])
    if os.getenv("MQTT_TLS", "false").lower() == "true":
        mqtt_client.tls_set()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    mqtt_client.connect_async(os.getenv("MQTT_HOST", "mqtt"), int(os.getenv("MQTT_PORT", "1883")), keepalive=60)
    mqtt_client.loop_start()


async def live_poll_loop():
    """Refresh only relevant non-notifiable values without blocking MQTT or UI."""
    await asyncio.sleep(10)
    while True:
        interval = poll_interval()
        try:
            if mqtt_connected or websocket_agents:
                online_cutoff = datetime.fromtimestamp(time.time() - 15 * 60, timezone.utc).isoformat()
                pending_cutoff = datetime.fromtimestamp(time.time() - max(interval, 30), timezone.utc).isoformat()
                with db() as connection:
                    endpoints = [row["endpoint_id"] for row in connection.execute(
                        "SELECT endpoint_id FROM agents WHERE last_seen>=?", (online_cutoff,)
                    ).fetchall()]
                spacing = min(2.0, interval / max(1, len(endpoints)))
                for endpoint in endpoints:
                    with db() as connection:
                        schema_count = connection.execute(
                            "SELECT COUNT(*) FROM model_schema WHERE endpoint_id=?", (endpoint,)
                        ).fetchone()[0]
                        pending = connection.execute(
                            "SELECT 1 FROM jobs WHERE endpoint_id=? AND action='get' AND state IN ('queued','sent') AND created_at>=? LIMIT 1",
                            (endpoint, pending_cutoff),
                        ).fetchone()
                    if pending:
                        continue
                    if schema_count < MIN_FULL_SCHEMA_ENTRIES:
                        sync_cutoff = datetime.fromtimestamp(time.time() - 3600, timezone.utc).isoformat()
                        with db() as connection:
                            recent_sync = connection.execute(
                                "SELECT 1 FROM jobs WHERE endpoint_id=? AND action='get_supported_dm' AND created_at>=? LIMIT 1",
                                (endpoint, sync_cutoff),
                            ).fetchone()
                        if not recent_sync:
                            try:
                                await asyncio.to_thread(
                                    dispatch_job, endpoint, "get_supported_dm",
                                    {"paths": ["Device."], "first_level_only": False}, "system"
                                )
                            except Exception as exc:
                                record_event(endpoint, "MODEL_SYNC_ERROR", {"error": str(exc)})
                        continue
                    try:
                        paths = automatic_live_profile(endpoint)["poll_paths"]
                        if paths:
                            await asyncio.to_thread(dispatch_job, endpoint, "get", {"paths": paths, "max_depth": 0}, "system")
                    except Exception as exc:
                        record_event(endpoint, "LIVE_POLL_ERROR", {"error": str(exc)})
                    await asyncio.sleep(spacing)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            record_event(None, "LIVE_POLLER_ERROR", {"error": str(exc)})
        await asyncio.sleep(interval)


class Login(BaseModel):
    username: str
    password: str


class JobRequest(BaseModel):
    action: str
    payload: dict = Field(default_factory=dict)


class ControllerSettings(BaseModel):
    live_paths: list[str] = Field(default_factory=list)
    genieacs_url: str = ""
    live_poll_interval: int = DEFAULT_POLL_INTERVAL
    udpst_host: str = ""
    udpst_port: int = 25000
    udpst_duration: int = 10
    udpst_auth_key: str = ""


class SpeedTestRequest(BaseModel):
    direction: str = "download"
    duration: int = 10


def genieacs_devices():
    url = setting("genieacs_url", GENIEACS_DEFAULT).rstrip("/")
    query = urllib.parse.urlencode({"projection": "_id,VirtualParameters.CustomerNumber"})
    try:
        with urllib.request.urlopen(f"{url}/devices/?{query}", timeout=6) as response:
            rows = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(str(exc)) from exc
    return rows


def genieacs_customer_map():
    result = {}
    for device in genieacs_devices():
        device_id = urllib.parse.unquote(str(device.get("_id", "")))
        number = (((device.get("VirtualParameters") or {}).get("CustomerNumber") or {}).get("_value") or "")
        if not number:
            continue
        for token in re.findall(r"[0-9A-F]{12,16}", device_id.upper()):
            result[token] = str(number)
    return result


def summarized_agents():
    cutoff = datetime.fromtimestamp(time.time() - 600, timezone.utc).isoformat()
    try:
        customers = genieacs_customer_map()
    except RuntimeError:
        customers = {}
    with db() as connection:
        agent_rows = connection.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
        parameter_rows = connection.execute("SELECT endpoint_id,path,value FROM parameters").fetchall()
    by_agent = {}
    for row in parameter_rows:
        by_agent.setdefault(row["endpoint_id"], {})[row["path"]] = row["value"]
    result = []
    for raw in agent_rows:
        row, params = dict(raw), by_agent.get(raw["endpoint_id"], {})
        serial = str(row.get("serial_number") or "").upper()
        customer = next((number for token, number in customers.items() if serial and (serial in token or token in serial)), "")
        if str(params.get("Device.DOCSIS.InterfaceNumberOfEntries", "0")) != "0":
            access = "Cable"
            healthy = params.get("Device.DOCSIS.Interface.1.ConnectivityStatus.Value") == "Operational"
        elif str(params.get("Device.DSL.LineNumberOfEntries", "0")) != "0":
            access = "DSL"
            healthy = str(params.get("Device.DSL.Line.1.Status", "")).lower() == "up"
        elif str(params.get("Device.Cellular.InterfaceNumberOfEntries", "0")) != "0":
            access = "Mobile"
            rsrp = float(params.get("Device.Cellular.Interface.1.RSRP", -200) or -200)
            healthy = rsrp >= -110
        elif str(params.get("Device.Optical.InterfaceNumberOfEntries", "0")) != "0":
            access = "Fiber"
            healthy = str(params.get("Device.Optical.Interface.1.Status", "")).lower() == "up"
        else:
            access, healthy = "WAN", None
        online = row["last_seen"] >= cutoff
        health = "Kritisch" if not online else "Gesund" if healthy is True else "Warnung" if healthy is False else "Unbekannt"
        row.update({
            "model": params.get("Device.DeviceInfo.ModelName") or row.get("product_class") or "USP-Agent",
            "firmware": params.get("Device.DeviceInfo.SoftwareVersion") or params.get("Device.DeviceInfo.FirmwareImage.1.Version") or "–",
            "access": access, "health": health, "online": online, "customer_number": customer,
        })
        result.append(row)
    return result


app = FastAPI(title="USP Control", version=VERSION, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def startup():
    global main_loop, poller_task
    main_loop = asyncio.get_running_loop()
    initialize_database()
    migrate_legacy_traffic()
    start_mqtt()
    asyncio.create_task(traffic_sampler(900, False))
    asyncio.create_task(traffic_sampler(300, True))
    poller_task = asyncio.create_task(live_poll_loop())


@app.on_event("shutdown")
async def shutdown():
    global poller_task
    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
        poller_task = None
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/health")
def health():
    with websocket_agents_lock:
        websocket_count = len(websocket_agents)
    return {"ok": True, "version": VERSION, "mqtt": mqtt_connected, "websocket_agents": websocket_count,
            "websocket_enabled": bool(WEBSOCKET_TOKEN), "endpoint_id": ENDPOINT_ID}


def valid_websocket_endpoint(endpoint):
    return bool(re.fullmatch(r"[A-Za-z0-9:._!@+%-]{3,200}", endpoint or ""))


def valid_websocket_credentials(authorization, query_token):
    """Accept the legacy URL token and FRITZ!OS Basic authentication."""
    if not WEBSOCKET_TOKEN:
        return False
    if query_token and secrets.compare_digest(query_token, WEBSOCKET_TOKEN):
        return True
    if not authorization or not authorization.startswith("Basic "):
        return False
    try:
        username, password = base64.b64decode(authorization[6:], validate=True).decode("utf-8").split(":", 1)
    except (ValueError, UnicodeDecodeError):
        return False
    return secrets.compare_digest(username, WEBSOCKET_USERNAME) and secrets.compare_digest(password, WEBSOCKET_TOKEN)


@app.websocket(f"{WEBSOCKET_PATH}/{{access_key}}")
@app.websocket(WEBSOCKET_PATH)
async def usp_websocket(websocket: WebSocket, access_key: str = ""):
    """TR-369 WebSocket MTP: binary USP Records using subprotocol v1.usp."""
    endpoint = websocket.query_params.get("eid", "")
    token = websocket.query_params.get("token", "")
    authorization = websocket.headers.get("authorization")
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    credentials_valid = valid_websocket_credentials(authorization, token)
    query_access_key = websocket.query_params.get("access", "")
    path_valid = bool(
        WEBSOCKET_PATH_KEY
        and ((access_key and secrets.compare_digest(access_key, WEBSOCKET_PATH_KEY))
             or (query_access_key and secrets.compare_digest(query_access_key, WEBSOCKET_PATH_KEY)))
    )
    credentials_valid = credentials_valid or path_valid
    if not valid_websocket_endpoint(endpoint) or not credentials_valid:
        logger.warning(
            "USP WebSocket rejected: endpoint_valid=%s path_valid=%s token_present=%s authorization_present=%s protocols=%s",
            valid_websocket_endpoint(endpoint), path_valid, bool(token), bool(authorization), protocols,
        )
        if valid_websocket_endpoint(endpoint) and not access_key and not token and not authorization:
            # FRITZ!OS sends Basic credentials after receiving this standard challenge.
            await websocket.send_denial_response(
                Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="USP Control"'})
            )
        else:
            await websocket.close(code=1008)
        return
    # FRITZ!OS omits Sec-WebSocket-Protocol even though it transports valid
    # binary USP Records. Preserve standard v1.usp negotiation where offered.
    if "v1.usp" in {item.strip() for item in protocols.split(",")}:
        await websocket.accept(subprotocol="v1.usp")
    else:
        await websocket.accept()
    with websocket_agents_lock:
        websocket_agents[endpoint] = websocket
    await asyncio.to_thread(upsert_agent, endpoint, "1.3", "", "", "websocket")
    await asyncio.to_thread(record_event, endpoint, "WEBSOCKET_CONNECT", {"path": websocket.url.path})
    try:
        while True:
            frame = await websocket.receive()
            if frame["type"] == "websocket.disconnect":
                logger.info("USP WebSocket disconnected: endpoint=%s code=%s", endpoint, frame.get("code"))
                break
            payload = frame.get("bytes")
            if payload is None:
                logger.warning("USP WebSocket received non-binary frame: endpoint=%s", endpoint)
                await websocket.close(code=1003)
                return
            wire_record = record_pb.Record()
            try:
                wire_record.ParseFromString(payload)
            except Exception as exc:
                logger.warning("USP WebSocket received invalid record: endpoint=%s bytes=%s error=%s", endpoint, len(payload), exc)
                await websocket.close(code=1003)
                return
            kind = wire_record.WhichOneof("record_type")
            logger.info("USP WebSocket record: endpoint=%s kind=%s bytes=%s", endpoint, kind, len(payload))
            if wire_record.from_id and wire_record.from_id != endpoint:
                logger.warning("USP WebSocket endpoint mismatch: requested=%s record=%s", endpoint, wire_record.from_id)
                await websocket.close(code=1008)
                return
            if wire_record.to_id and wire_record.to_id != ENDPOINT_ID:
                logger.warning("USP WebSocket controller mismatch: received=%s expected=%s", wire_record.to_id, ENDPOINT_ID)
                await websocket.close(code=1008)
                return
            if kind == "websocket_connect":
                await asyncio.to_thread(upsert_agent, endpoint, wire_record.version or "1.3", "", "", "websocket")
                await asyncio.to_thread(record_event, endpoint, "WEBSOCKET_CONNECT_RECORD", {"version": wire_record.version})
                try:
                    # A WebSocket MTP has no broker-side connect callback that
                    # would otherwise initiate discovery. Start the same model
                    # synchronization used for a newly connected MQTT agent.
                    await asyncio.to_thread(
                        dispatch_job, endpoint, "get_supported_dm",
                        {"paths": ["Device."], "first_level_only": False}, "system",
                    )
                except Exception as exc:
                    logger.warning("USP WebSocket model sync could not start: endpoint=%s error=%s", endpoint, exc)
                continue
            message_payload = extract_payload(wire_record)
            if message_payload:
                await asyncio.to_thread(
                    handle_usp_message, endpoint, "websocket", "", wire_record.version or "1.3", message_payload, "websocket"
                )
    except WebSocketDisconnect as exc:
        logger.info("USP WebSocket disconnected before/after record: endpoint=%s code=%s", endpoint, exc.code)
    except RuntimeError:
        pass
    except Exception:
        logger.exception("USP WebSocket processing failed: endpoint=%s", endpoint)
    finally:
        with websocket_agents_lock:
            if websocket_agents.get(endpoint) is websocket:
                websocket_agents.pop(endpoint, None)
        await asyncio.to_thread(record_event, endpoint, "WEBSOCKET_DISCONNECT", {"path": WEBSOCKET_PATH})


@app.websocket("/api/live")
async def live(websocket: WebSocket):
    try:
        current_user(websocket)
    except HTTPException:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    queue = asyncio.Queue(maxsize=250)
    live_clients.add(queue)
    await websocket.send_json({"type": "hello", "timestamp": now(), "payload": {"mqtt": mqtt_connected, "endpoint_id": ENDPOINT_ID}})
    try:
        while True:
            await websocket.send_json(await queue.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        live_clients.discard(queue)


@app.post("/api/login")
def login(data: Login, request: Request):
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE username=? AND active=1", (data.username,)).fetchone()
    if not user or not passwords.verify(data.password, user["password_hash"]):
        raise HTTPException(401, "Benutzername oder Kennwort falsch")
    response = {"ok": True, "username": user["username"], "display_name": user["display_name"], "role": user["role"]}
    from fastapi.responses import JSONResponse
    result = JSONResponse(response)
    result.set_cookie("usp_session", serializer.dumps({"id": user["id"]}), httponly=True, samesite="strict", max_age=43200)
    audit(user["username"], "Anmeldung")
    return result


@app.post("/api/logout")
def logout(request: Request):
    user = current_user(request)
    from fastapi.responses import JSONResponse
    result = JSONResponse({"ok": True})
    result.delete_cookie("usp_session")
    audit(user["username"], "Abmeldung")
    return result


@app.get("/api/session")
def session(request: Request):
    user = current_user(request)
    return {"authenticated": True, **user, "version": VERSION}


def user_json(user):
    return {"id": user["id"], "username": user["username"], "display_name": user["display_name"],
            "role": user["role"], "active": bool(user["active"]), "created_at": user["created_at"],
            "updated_at": user["updated_at"]}


@app.get("/api/users")
def users_list(request: Request):
    current_user(request, admin=True)
    with db() as connection:
        rows = connection.execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return [user_json(row) for row in rows]


@app.post("/api/users")
async def user_create(request: Request):
    actor = current_user(request, admin=True)
    data = await request.json()
    username, password, role = str(data.get("username", "")).strip(), str(data.get("password", "")), str(data.get("role", "viewer"))
    if len(username) < 3 or len(password) < 10 or role not in ROLES:
        raise HTTPException(400, "Benutzername, Kennwort oder Rolle ungültig")
    try:
        with db() as connection:
            cursor = connection.execute("INSERT INTO users(username,display_name,password_hash,role,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (username, str(data.get("display_name", "")).strip(), passwords.hash(password), role, int(bool(data.get("active", True))), now(), now()))
            row = connection.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Benutzername ist bereits vergeben") from exc
    audit(actor["username"], "Benutzer angelegt", username, role)
    return user_json(row)


@app.put("/api/users/{user_id}")
async def user_update(user_id: int, request: Request):
    actor = current_user(request, admin=True)
    data = await request.json()
    with db() as connection:
        row = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Benutzer nicht gefunden")
        username = str(data.get("username", row["username"])).strip()
        role = str(data.get("role", row["role"]))
        active = int(bool(data.get("active", bool(row["active"]))))
        if len(username) < 3 or role not in ROLES:
            raise HTTPException(400, "Benutzername oder Rolle ungültig")
        if user_id == actor["id"] and (role != "admin" or not active):
            raise HTTPException(400, "Der eigene Administratorzugang darf nicht deaktiviert oder herabgestuft werden")
        if row["role"] == "admin" and (role != "admin" or not active):
            if connection.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
                raise HTTPException(400, "Der letzte aktive Administrator muss erhalten bleiben")
        values = [username, str(data.get("display_name", row["display_name"])).strip(), role, active]
        password = str(data.get("password", ""))
        try:
            if password:
                if len(password) < 10:
                    raise HTTPException(400, "Das Kennwort muss mindestens 10 Zeichen lang sein")
                connection.execute("UPDATE users SET username=?,display_name=?,role=?,active=?,password_hash=?,updated_at=? WHERE id=?", (*values, passwords.hash(password), now(), user_id))
            else:
                connection.execute("UPDATE users SET username=?,display_name=?,role=?,active=?,updated_at=? WHERE id=?", (*values, now(), user_id))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Benutzername ist bereits vergeben") from exc
        updated = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    audit(actor["username"], "Benutzer geändert", username, role)
    return user_json(updated)


@app.delete("/api/users/{user_id}")
def user_delete(user_id: int, request: Request):
    actor = current_user(request, admin=True)
    if user_id == actor["id"]:
        raise HTTPException(400, "Der eigene Benutzer kann nicht gelöscht werden")
    with db() as connection:
        row = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Benutzer nicht gefunden")
        if row["role"] == "admin" and connection.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
            raise HTTPException(400, "Der letzte aktive Administrator kann nicht gelöscht werden")
        connection.execute("DELETE FROM users WHERE id=?", (user_id,))
    audit(actor["username"], "Benutzer gelöscht", row["username"])
    return {"ok": True}


@app.get("/api/profile")
def profile_get(request: Request):
    user = current_user(request)
    return user_json(user)


@app.put("/api/profile")
async def profile_update(request: Request):
    user = current_user(request)
    data = await request.json()
    with db() as connection:
        row = connection.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not passwords.verify(str(data.get("current_password", "")), row["password_hash"]):
            raise HTTPException(400, "Aktuelles Kennwort ist falsch")
        username, display_name = str(data.get("username", row["username"])).strip(), str(data.get("display_name", row["display_name"])).strip()
        if len(username) < 3:
            raise HTTPException(400, "Benutzername muss mindestens 3 Zeichen lang sein")
        try:
            connection.execute("UPDATE users SET username=?,display_name=?,updated_at=? WHERE id=?", (username, display_name, now(), user["id"]))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Benutzername ist bereits vergeben") from exc
        updated = connection.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    audit(username, "Eigenes Profil geändert")
    return user_json(updated)


@app.put("/api/profile/password")
async def profile_password(request: Request):
    user = current_user(request)
    data = await request.json()
    new_password = str(data.get("new_password", ""))
    if len(new_password) < 10:
        raise HTTPException(400, "Das neue Kennwort muss mindestens 10 Zeichen lang sein")
    with db() as connection:
        row = connection.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not passwords.verify(str(data.get("current_password", "")), row["password_hash"]):
            raise HTTPException(400, "Aktuelles Kennwort ist falsch")
        connection.execute("UPDATE users SET password_hash=?,updated_at=? WHERE id=?", (passwords.hash(new_password), now(), user["id"]))
    audit(user["username"], "Eigenes Kennwort geändert")
    return {"ok": True}


@app.get("/api/branding")
def branding_get():
    custom = Path(CUSTOM_LOGO_PATH).is_file() and bool(setting("brand_logo_content_type"))
    return {"custom_logo": custom, "logo_url": "/api/branding/logo" if custom else "/static/branding/noisens-logo.png"}


@app.get("/api/branding/logo")
def branding_logo():
    content_type = setting("brand_logo_content_type")
    path = CUSTOM_LOGO_PATH if content_type and Path(CUSTOM_LOGO_PATH).is_file() else "static/branding/noisens-logo.png"
    return FileResponse(path, media_type=content_type or "image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/branding/logo")
async def branding_upload(request: Request, logo: UploadFile = File(...)):
    actor = current_user(request, admin=True)
    data = await logo.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(400, "Das Logo darf maximal 2 MB groß sein")
    signatures = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"RIFF", "image/webp"))
    content_type = next((kind for signature, kind in signatures if data.startswith(signature)), None)
    if content_type == "image/webp" and data[8:12] != b"WEBP":
        content_type = None
    if not content_type:
        raise HTTPException(400, "Erlaubt sind PNG, JPEG oder WebP")
    temporary = CUSTOM_LOGO_PATH + ".new"
    Path(temporary).write_bytes(data)
    os.replace(temporary, CUSTOM_LOGO_PATH)
    save_setting("brand_logo_content_type", content_type)
    audit(actor["username"], "Unternehmenslogo geändert", logo.filename or "Logo")
    return {"ok": True, "logo_url": "/api/branding/logo"}


@app.delete("/api/branding/logo")
def branding_reset(request: Request):
    actor = current_user(request, admin=True)
    Path(CUSTOM_LOGO_PATH).unlink(missing_ok=True)
    save_setting("brand_logo_content_type", "")
    audit(actor["username"], "Unternehmenslogo zurückgesetzt", "NoiSens Services")
    return {"ok": True, "logo_url": "/static/branding/noisens-logo.png"}


@app.get("/api/settings")
def controller_settings(request: Request):
    current_user(request, admin=True)
    return {
        "endpoint_id": ENDPOINT_ID,
        "controller_topic": CONTROLLER_TOPIC,
        "agent_topic_template": AGENT_TOPIC_TEMPLATE,
        "mqtt_host": os.getenv("MQTT_HOST", "mqtt"),
        "mqtt_port": int(os.getenv("MQTT_PORT", "1883")),
        "mqtt_tls": os.getenv("MQTT_TLS", "false").lower() == "true",
        "mqtt_username": os.getenv("MQTT_CONTROLLER_USERNAME", "controller"),
        "mqtt_password_configured": bool(os.getenv("MQTT_CONTROLLER_PASSWORD")),
        "mqtt_connected": mqtt_connected,
        "websocket_enabled": bool(WEBSOCKET_TOKEN),
        "websocket_path": WEBSOCKET_AGENT_PATH,
        "websocket_url": f"{WEBSOCKET_PUBLIC_URL}?access={WEBSOCKET_PATH_KEY}" if WEBSOCKET_PUBLIC_URL and WEBSOCKET_PATH_KEY else WEBSOCKET_PUBLIC_URL,
        "live_paths": live_paths(),
        "live_poll_interval": poll_interval(),
        "genieacs_url": setting("genieacs_url", GENIEACS_DEFAULT),
        "udpst_host": setting("udpst_host"),
        "udpst_port": int(setting("udpst_port", "25000")),
        "udpst_duration": int(setting("udpst_duration", "10")),
        "udpst_auth_configured": bool(setting("udpst_auth_key")),
    }


@app.put("/api/settings")
def controller_settings_update(data: ControllerSettings, request: Request):
    user = current_user(request, admin=True)
    paths = []
    for raw in data.live_paths:
        path = raw.strip()
        if not path.startswith("Device.") or len(path) > 512:
            raise HTTPException(400, f"Ungültiger USP-Pfad: {path or 'leer'}")
        if path not in paths:
            paths.append(path)
    if not paths or len(paths) > 100:
        raise HTTPException(400, "Bitte 1 bis 100 Live-Pfade angeben")
    save_setting("live_paths", json.dumps(paths, ensure_ascii=False))
    interval = min(max(int(data.live_poll_interval), 15), 3600)
    save_setting("live_poll_interval", interval)
    genieacs_url = data.genieacs_url.strip().rstrip("/") or setting("genieacs_url", GENIEACS_DEFAULT)
    parsed = urllib.parse.urlparse(genieacs_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(400, "Ungültige GenieACS-API-URL")
    try:
        query = urllib.parse.urlencode({"projection": "_id", "limit": "1"})
        with urllib.request.urlopen(f"{genieacs_url}/devices/?{query}", timeout=6) as response:
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        raise HTTPException(400, f"GenieACS nicht erreichbar: {exc}") from exc
    save_setting("genieacs_url", genieacs_url)
    udpst_host = data.udpst_host.strip()
    if not udpst_host or len(udpst_host) > 253 or any(character.isspace() for character in udpst_host):
        raise HTTPException(400, "Ungültiger UDPST-Server")
    if not 1 <= data.udpst_port <= 65535:
        raise HTTPException(400, "Ungültiger UDPST-Port")
    if not 5 <= data.udpst_duration <= 30:
        raise HTTPException(400, "Die UDPST-Testdauer muss zwischen 5 und 30 Sekunden liegen")
    save_setting("udpst_host", udpst_host)
    save_setting("udpst_port", data.udpst_port)
    save_setting("udpst_duration", data.udpst_duration)
    # An empty field means "retain" so the browser never needs to receive the
    # existing authentication secret. A single dash explicitly removes it.
    if data.udpst_auth_key == "-":
        save_setting("udpst_auth_key", "")
    elif data.udpst_auth_key:
        if len(data.udpst_auth_key) > 32 or not re.fullmatch(r"[A-Za-z0-9.:()]+", data.udpst_auth_key):
            raise HTTPException(400, "Der UDPST-Auth-Key enthält unzulässige Zeichen")
        save_setting("udpst_auth_key", data.udpst_auth_key)
    audit(user["username"], "Live-Profil geändert", detail=f"{len(paths)} Pfade · Polling {interval}s")
    return {"ok": True, "live_paths": paths, "live_poll_interval": interval, "genieacs_url": genieacs_url}


@app.get("/api/genieacs/status")
def genieacs_status(request: Request):
    current_user(request)
    started = time.perf_counter()
    try:
        devices = genieacs_devices()
        return {"ok": True, "status": "Verbunden", "latency_ms": round((time.perf_counter() - started) * 1000), "devices": len(devices)}
    except RuntimeError as exc:
        return {"ok": False, "status": "Getrennt", "error": str(exc), "latency_ms": round((time.perf_counter() - started) * 1000)}


@app.get("/api/dashboard")
def dashboard(request: Request):
    current_user(request)
    rows = summarized_agents()
    with db() as connection:
        jobs = connection.execute("SELECT state,COUNT(*) count FROM jobs GROUP BY state").fetchall()
    job_counts = {row["state"]: row["count"] for row in jobs}
    return {"agents": {"total": len(rows), "online": sum(1 for row in rows if row["online"])}, "jobs": job_counts, "active_errors": job_counts.get("failed", 0), "attention": sum(1 for row in rows if row["health"] in {"Warnung", "Kritisch"}), "access": {name: sum(1 for row in rows if row["access"] == name) for name in ["Cable", "DSL", "Mobile", "Fiber", "WAN"]}, "health": {name: sum(1 for row in rows if row["health"] == name) for name in ["Gesund", "Warnung", "Kritisch", "Unbekannt"]}, "mqtt": mqtt_connected, "endpoint_id": ENDPOINT_ID}


@app.get("/api/traffic")
def traffic_history(request: Request, hours: int = 24, endpoint: str = ""):
    current_user(request)
    hours = min(max(hours, 1), 168)
    cutoff_timestamp = time.time() - hours * 3600
    cutoff = datetime.fromtimestamp(cutoff_timestamp, timezone.utc).isoformat()
    query = "SELECT endpoint_id,bucket_start,down_bps,up_bps FROM traffic_samples WHERE bucket_start>=?"
    values = [cutoff]
    if endpoint:
        query += " AND endpoint_id=?"
        values.append(endpoint)
    query += " ORDER BY endpoint_id,bucket_start"
    with db() as connection:
        rows = connection.execute(query, values).fetchall()
    series = {}
    for row in rows:
        series.setdefault(row["endpoint_id"], []).append((datetime.fromisoformat(row["bucket_start"]).timestamp(), row["down_bps"], row["up_bps"]))
    step = 60 if hours <= 1 else 300 if hours <= 24 else 900
    start = int(cutoff_timestamp // step * step)
    end = int(time.time() // step * step)
    cursors = {agent: -1 for agent in series}
    points = []
    for timestamp in range(start, end + 1, step):
        down = up = 0
        coverage = 0
        for agent, samples in series.items():
            cursor = cursors[agent]
            while cursor + 1 < len(samples) and samples[cursor + 1][0] <= timestamp:
                cursor += 1
            cursors[agent] = cursor
            if cursor >= 0 and timestamp - samples[cursor][0] <= 1800:
                down += samples[cursor][1]
                up += samples[cursor][2]
                coverage += 1
        if coverage:
            points.append({"time": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(), "down_bps": round(down), "up_bps": round(up), "coverage": coverage})
    return {"hours": hours, "scope": endpoint or "all", "points": points, "agents": len(series)}


@app.get("/api/agents")
def agents(request: Request):
    current_user(request)
    rows = summarized_agents()
    with db() as connection:
        counts = {row["endpoint_id"]: row["count"] for row in connection.execute("SELECT endpoint_id,COUNT(*) count FROM parameters GROUP BY endpoint_id").fetchall()}
    for row in rows:
        row["parameter_count"] = counts.get(row["endpoint_id"], 0)
    return rows


@app.get("/api/agents/{endpoint}")
def agent(endpoint: str, request: Request):
    current_user(request)
    observe_agent(endpoint)
    with db() as connection:
        row = connection.execute("SELECT * FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone()
        if not row:
            raise HTTPException(404, "USP-Agent nicht gefunden")
        params = connection.execute("SELECT path,value,updated_at FROM parameters WHERE endpoint_id=? ORDER BY path LIMIT 10000", (endpoint,)).fetchall()
        jobs = connection.execute("SELECT * FROM jobs WHERE endpoint_id=? ORDER BY id DESC LIMIT 100", (endpoint,)).fetchall()
        events = connection.execute("SELECT * FROM events WHERE endpoint_id=? ORDER BY id DESC LIMIT 100", (endpoint,)).fetchall()
    parameter_values = [dict(x) for x in params]
    network = ripe_network_info(wan_ip_from_parameters(parameter_values))
    return {"agent": dict(row), "parameters": parameter_values, "jobs": [dict(x) for x in jobs], "events": [dict(x) for x in events], "network": network}


@app.get("/api/agents/{endpoint}/history")
def agent_history(endpoint: str, request: Request, path: str = "", hours: int = 24):
    current_user(request)
    hours = min(max(hours, 1), 168)
    cutoff = datetime.fromtimestamp(time.time() - hours * 3600, timezone.utc).isoformat()
    query = "SELECT path,value,created_at FROM parameter_history WHERE endpoint_id=? AND created_at>=?"
    values = [endpoint, cutoff]
    if path:
        query += " AND path LIKE ?"
        values.append(path.rstrip("%") + "%")
    query += " ORDER BY created_at LIMIT 20000"
    with db() as connection:
        rows = connection.execute(query, values).fetchall()
    return {"hours": hours, "values": [dict(row) for row in rows]}


@app.get("/api/agents/{endpoint}/schema")
def agent_schema(endpoint: str, request: Request):
    current_user(request)
    with db() as connection:
        exists = connection.execute("SELECT 1 FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone()
        if not exists:
            raise HTTPException(404, "USP-Agent nicht gefunden")
        rows = connection.execute("SELECT path,kind,name,access,value_type,value_change,metadata,updated_at FROM model_schema WHERE endpoint_id=? ORDER BY path,kind", (endpoint,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item["metadata"] or "{}")
        result.append(item)
    return {"items": result, "count": len(result)}


@app.post("/api/agents/{endpoint}/refresh-live")
def refresh_live(endpoint: str, request: Request):
    return create_job(endpoint, JobRequest(action="get", payload={"paths": live_paths_for_agent(endpoint), "max_depth": 0}), request)


def clear_agent_state(endpoint, remove_agent=False):
    """Clear controller-side state while optionally retaining agent identity."""
    with db() as connection:
        exists = connection.execute("SELECT 1 FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone()
        if not exists:
            raise ValueError("USP-Agent nicht gefunden")
        for table in ("parameter_history", "traffic_counters", "traffic_samples", "model_schema", "events"):
            connection.execute(f"DELETE FROM {table} WHERE endpoint_id=?", (endpoint,))
        # These tables cascade when the agent itself is removed. Explicitly
        # clearing them also gives a retained agent a genuinely clean state.
        connection.execute("DELETE FROM speed_tests WHERE endpoint_id=?", (endpoint,))
        connection.execute("DELETE FROM jobs WHERE endpoint_id=?", (endpoint,))
        connection.execute("DELETE FROM parameters WHERE endpoint_id=?", (endpoint,))
        if remove_agent:
            connection.execute("DELETE FROM agents WHERE endpoint_id=?", (endpoint,))
    with observed_agents_lock:
        observed_agents.pop(endpoint, None)


@app.post("/api/agents/{endpoint}/reset")
def reset_agent(endpoint: str, request: Request):
    user = current_user(request)
    if user["role"] == "viewer":
        raise HTTPException(403, "Diese Rolle besitzt ausschließlich Leserechte")
    try:
        clear_agent_state(endpoint)
        synchronization = dispatch_job(
            endpoint, "get_supported_dm", {"paths": ["Device."], "first_level_only": False}, "system"
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(409, f"Neusynchronisation konnte nicht gestartet werden: {exc}") from exc
    audit(user["username"], "USP-Agent zurückgesetzt", endpoint, "Controllerdaten gelöscht; Datenmodell-Neusynchronisation gestartet")
    emit_live("agent_reset", endpoint, {"msg_id": synchronization["msg_id"]})
    return {"ok": True, "status": "synchronizing", "msg_id": synchronization["msg_id"]}


@app.delete("/api/agents/{endpoint}")
def delete_agent(endpoint: str, request: Request):
    user = current_user(request, admin=True)
    try:
        clear_agent_state(endpoint, remove_agent=True)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    audit(user["username"], "USP-Agent gelöscht", endpoint, "Agent und sämtliche zugehörigen Controllerdaten dauerhaft gelöscht")
    emit_live("agent_deleted", endpoint)
    return {"ok": True}


@app.get("/api/agents/{endpoint}/live-profile")
def live_profile(endpoint: str, request: Request):
    current_user(request)
    with db() as connection:
        if not connection.execute("SELECT 1 FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone():
            raise HTTPException(404, "USP-Agent nicht gefunden")
        schema_count = connection.execute("SELECT COUNT(*) FROM model_schema WHERE endpoint_id=?", (endpoint,)).fetchone()[0]
    profile = automatic_live_profile(endpoint)
    profile["schema_synchronized"] = schema_count >= MIN_FULL_SCHEMA_ENTRIES
    profile["schema_count"] = schema_count
    return profile


@app.post("/api/agents/{endpoint}/subscribe-live")
def subscribe_live(endpoint: str, request: Request):
    user = current_user(request)
    if user["role"] == "viewer":
        raise HTTPException(403, "Diese Rolle besitzt ausschließlich Leserechte")
    profile = automatic_live_profile(endpoint)
    subscription_specs = [
        (kind, reference_list)
        for kind in ("ValueChange", "Event", "ObjectCreation", "ObjectDeletion", "OperationComplete")
        for reference_list in pack_subscription_references(profile[kind])
    ]
    if not subscription_specs:
        raise HTTPException(400, "Das synchronisierte Datenmodell weist keine abonnierbaren Live-Werte aus")
    existing = set()
    with db() as connection:
        rows = connection.execute(
            "SELECT state,request_json,response_json FROM jobs "
            "WHERE endpoint_id=? AND action='add' ORDER BY id DESC",
            (endpoint,),
        ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["request_json"] or "{}")
            if payload.get("object_path") != "Device.LocalAgent.Subscription.":
                continue
            parameters = {
                item.get("name"): str(item.get("value", ""))
                for item in payload.get("parameters", [])
                if isinstance(item, dict)
            }
            path = parameters.get("ReferenceList")
            notif_type = parameters.get("NotifType")
            if not path or not notif_type:
                continue
            if row["state"] == "complete":
                existing.add((notif_type, path))
                continue
            response = json.loads(row["response_json"] or "{}")
            errors = response.get("body", {}).get("error", {}).get("param_errs", [])
            if any(error.get("err_code") == 7025 and error.get("param_path") == "ID" for error in errors):
                existing.add((notif_type, path))
        except (TypeError, ValueError, AttributeError):
            continue

    missing = [spec for spec in subscription_specs if spec not in existing]
    jobs = []
    for notif_type, path in missing:
        stable_id = hashlib.sha1(f"{notif_type}:{path}".encode()).hexdigest()[:16]
        payload = {
            "object_path": "Device.LocalAgent.Subscription.",
            "parameters": [
                {"name": "Enable", "value": "true", "required": True},
                {"name": "ID", "value": f"noisens-{stable_id}", "required": True},
                {"name": "NotifType", "value": notif_type, "required": True},
                {"name": "ReferenceList", "value": path, "required": True},
                {"name": "Persistent", "value": "true", "required": True},
                {"name": "TimeToLive", "value": "0", "required": False},
            ],
        }
        jobs.append(create_job(endpoint, JobRequest(action="add", payload=payload), request))
    audit(user["username"], "Automatisches Live-Profil aktiviert", endpoint,
          f"{len(jobs)} neu · {len(existing.intersection(subscription_specs))} vorhanden")
    return {
        "ok": True,
        "status": "created" if jobs else "already_active",
        "subscriptions": jobs,
        "profile": profile,
        "created": len(jobs),
        "existing": len(existing.intersection(subscription_specs)),
    }


def dispatch_job(endpoint, action, payload, actor="system"):
    with db() as connection:
        agent_row = connection.execute("SELECT protocol_version,reply_topic FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone()
    if not agent_row:
        raise ValueError("USP-Agent nicht gefunden")
    message = build_message(action, payload)
    topic = agent_row["reply_topic"] or agent_topic(endpoint)
    stored_payload = json.loads(json.dumps(payload))
    if action == "operate" and isinstance(stored_payload.get("input_args"), dict) and "X_AuthKey" in stored_payload["input_args"]:
        stored_payload["input_args"]["X_AuthKey"] = "[geschützt]"
    with db() as connection:
        connection.execute("INSERT INTO jobs(msg_id,endpoint_id,action,request_json,state,created_at) VALUES(?,?,?,?,?,?)", (message.header.msg_id, endpoint, action, json.dumps(stored_payload, ensure_ascii=False), "queued", now()))
    try:
        send_usp_message(endpoint, message, agent_row["protocol_version"] or "1.3", "auto", topic)
        with db() as connection:
            connection.execute("UPDATE jobs SET state='sent' WHERE msg_id=?", (message.header.msg_id,))
    except Exception as exc:
        with db() as connection:
            connection.execute("UPDATE jobs SET state='failed',error=?,completed_at=? WHERE msg_id=?", (str(exc), now(), message.header.msg_id))
        raise
    if actor != "system":
        audit(actor, f"USP {action}", endpoint, json.dumps(stored_payload, ensure_ascii=False))
    return {"ok": True, "msg_id": message.header.msg_id, "topic": topic,
            "transport": "mqtt" if mqtt_connected else "websocket"}


@app.post("/api/agents/{endpoint}/jobs")
def create_job(endpoint: str, data: JobRequest, request: Request):
    user = current_user(request)
    if data.action in {"set", "add", "delete", "operate"} and user["role"] == "viewer":
        raise HTTPException(403, "Diese Rolle besitzt ausschließlich Leserechte")
    try:
        return dispatch_job(endpoint, data.action, data.payload, user["username"])
    except ValueError as exc:
        if str(exc) == "USP-Agent nicht gefunden":
            raise HTTPException(404, str(exc)) from exc
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/agents/{endpoint}/speedtests")
def speed_tests(endpoint: str, request: Request):
    current_user(request)
    with db() as connection:
        if not connection.execute("SELECT 1 FROM agents WHERE endpoint_id=?", (endpoint,)).fetchone():
            raise HTTPException(404, "USP-Agent nicht gefunden")
        supported = connection.execute(
            "SELECT value FROM parameters WHERE endpoint_id=? AND path='Device.IP.Diagnostics.IPLayerCapacitySupported'",
            (endpoint,),
        ).fetchone()
        command = connection.execute(
            "SELECT 1 FROM model_schema WHERE endpoint_id=? AND path='Device.IP.Diagnostics.IPLayerCapacity()' AND kind='command'",
            (endpoint,),
        ).fetchone()
        # An Agent can lose its MQTT session while an asynchronous diagnostic
        # is running (for example during a PPPoE reconnect). In that case no
        # OperationComplete can arrive. Expire the orphan instead of blocking
        # all future tests forever.
        stale_before = datetime.fromtimestamp(time.time() - 90, timezone.utc).isoformat()
        stale = connection.execute(
            "SELECT msg_id FROM speed_tests WHERE endpoint_id=? AND state IN ('queued','sent','running') AND created_at<?",
            (endpoint, stale_before),
        ).fetchall()
        if stale:
            timeout_error = "Keine Abschlussmeldung vom USP-Agenten – Verbindung während des Tests möglicherweise unterbrochen"
            completed = now()
            for item in stale:
                connection.execute("UPDATE speed_tests SET state='failed',error=?,completed_at=? WHERE msg_id=?", (timeout_error, completed, item["msg_id"]))
                connection.execute("UPDATE jobs SET state='failed',error=?,completed_at=? WHERE msg_id=?", (timeout_error, completed, item["msg_id"]))
        rows = connection.execute("SELECT * FROM speed_tests WHERE endpoint_id=? ORDER BY id DESC LIMIT 25", (endpoint,)).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        try:
            item["result"] = json.loads(item.pop("result_json") or "{}")
        except json.JSONDecodeError:
            item["result"] = {}
        items.append(item)
    return {
        "supported": (str(supported["value"]).lower() in {"1", "true", "yes", "on"}) if supported else bool(command),
        "support_known": bool(supported or command),
        "host": setting("udpst_host"),
        "port": int(setting("udpst_port", "25000")),
        "default_duration": int(setting("udpst_duration", "10")),
        "items": items,
    }


@app.post("/api/agents/{endpoint}/speedtests")
def start_speed_test(endpoint: str, data: SpeedTestRequest, request: Request):
    user = current_user(request)
    if user["role"] == "viewer":
        raise HTTPException(403, "Diese Rolle besitzt ausschließlich Leserechte")
    if data.direction not in {"download", "upload"}:
        raise HTTPException(400, "Richtung muss Download oder Upload sein")
    if not 5 <= data.duration <= 30:
        raise HTTPException(400, "Die Testdauer muss zwischen 5 und 30 Sekunden liegen")
    with db() as connection:
        active = connection.execute("SELECT 1 FROM speed_tests WHERE endpoint_id=? AND state IN ('queued','sent','running') LIMIT 1", (endpoint,)).fetchone()
    if active:
        raise HTTPException(409, "Auf diesem Gerät läuft bereits ein Speedtest")
    host = setting("udpst_host").strip()
    if not host:
        raise HTTPException(409, "Kein UDPST-Server konfiguriert")
    arguments = {
        "Role": "Receiver" if data.direction == "download" else "Sender",
        "Host": host,
        "Port": str(int(setting("udpst_port", "25000"))),
        "ProtocolVersion": "Any",
        "TestType": "Search",
        "IPDVEnable": "true",
        "X_TestIntervalSecs": str(data.duration),
        "X_TestSubIntervalSecs": "1",
    }
    auth_key = setting("udpst_auth_key")
    if auth_key:
        arguments["X_AuthKey"] = auth_key
    result = create_job(endpoint, JobRequest(action="operate", payload={
        "command": "Device.IP.Diagnostics.IPLayerCapacity()",
        "input_args": arguments,
    }), request)
    with db() as connection:
        connection.execute(
            "INSERT INTO speed_tests(msg_id,endpoint_id,direction,state,duration,created_at) VALUES(?,?,?,?,?,?)",
            (result["msg_id"], endpoint, data.direction, "sent", data.duration, now()),
        )
    audit(user["username"], "UDPST-Speedtest gestartet", endpoint, f"{data.direction}, {data.duration} Sekunden")
    return {"ok": True, "msg_id": result["msg_id"], "state": "sent"}


@app.get("/api/audit")
def audit_log(request: Request):
    current_user(request, admin=True)
    with db() as connection:
        rows = connection.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 500").fetchall()
    return [dict(row) for row in rows]
