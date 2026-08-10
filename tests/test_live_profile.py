import base64
import json
import os
import tempfile
import unittest

os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "TestPassword123!")
os.environ.setdefault("MQTT_CONTROLLER_PASSWORD", "test")

import app


class LiveProfileTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        app.DB_PATH = os.path.join(self.tempdir.name, "controller.db")
        app.initialize_database()
        timestamp = app.now()
        with app.db() as connection:
            connection.execute("INSERT INTO agents(endpoint_id,first_seen,last_seen) VALUES(?,?,?)", ("agent", timestamp, timestamp))
            connection.executemany(
                "INSERT INTO parameters(endpoint_id,path,value,updated_at) VALUES(?,?,?,?)",
                [
                    ("agent", "Device.DeviceInfo.ProcessStatus.CPUUsage", "12", timestamp),
                    ("agent", "Device.WiFi.Radio.1.ChannelUtilization", "25", timestamp),
                    ("agent", "Device.WiFi.AccessPoint.1.AssociatedDevice.1.SignalStrength", "-52", timestamp),
                ],
            )
            rows = [
                ("Device.DeviceInfo.ProcessStatus.CPUUsage", "parameter", "CPUUsage", "PARAM_READ_ONLY", "PARAM_UNSIGNED_INT", "VALUE_CHANGE_ALLOWED", {}),
                ("Device.WiFi.Radio.{i}.ChannelUtilization", "parameter", "ChannelUtilization", "PARAM_READ_ONLY", "PARAM_UNSIGNED_INT", "VALUE_CHANGE_WILL_IGNORE", {}),
                ("Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.SignalStrength", "parameter", "SignalStrength", "PARAM_READ_ONLY", "PARAM_INT", "VALUE_CHANGE_ALLOWED", {}),
                ("Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.", "object", "", "OBJ_READ_ONLY", "", "", {"multi_instance": True}),
                ("Device.DeviceInfo.Boot!", "event", "Boot!", "", "", "", {"args": []}),
            ]
            connection.executemany(
                "INSERT INTO model_schema(endpoint_id,path,kind,name,access,value_type,value_change,metadata,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                [("agent", *row[:6], json.dumps(row[6]), timestamp) for row in rows],
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_profile_resolves_instances_and_separates_polling(self):
        profile = app.automatic_live_profile("agent")
        self.assertIn("Device.DeviceInfo.", profile["ValueChange"])
        self.assertIn("Device.WiFi.AccessPoint.", profile["ValueChange"])
        self.assertEqual(profile["capability_counts"]["ValueChange"], 2)
        self.assertIn("Device.WiFi.Radio.1.ChannelUtilization", profile["poll_paths"])
        self.assertNotIn("Device.DeviceInfo.ProcessStatus.CPUUsage", profile["poll_paths"])
        self.assertIn("Device.WiFi.AccessPoint.*.AssociatedDevice.", profile["ObjectCreation"])
        self.assertIn("Device.WiFi.AccessPoint.*.AssociatedDevice.*.", profile["ObjectDeletion"])
        self.assertIn("Device.DeviceInfo.", profile["Event"])

    def test_reference_lists_stay_below_agent_limit(self):
        paths = [f"Device.WiFi.Radio.{index}.ChannelUtilization" for index in range(1, 30)]
        groups = app.pack_subscription_references(paths)
        self.assertEqual(paths, [path for group in groups for path in group.split(",")])
        self.assertTrue(all(len(group) <= 240 for group in groups))

    def test_reset_clears_state_but_retains_agent_identity(self):
        timestamp = app.now()
        with app.db() as connection:
            connection.execute("INSERT INTO parameter_history(endpoint_id,path,value,created_at) VALUES(?,?,?,?)", ("agent", "Device.Test", "1", timestamp))
            connection.execute("INSERT INTO traffic_counters(endpoint_id,bytes_received,bytes_sent,sampled_at) VALUES(?,?,?,?)", ("agent", 1, 2, timestamp))
            connection.execute("INSERT INTO traffic_samples(endpoint_id,bucket_start,down_bps,up_bps) VALUES(?,?,?,?)", ("agent", timestamp, 3, 4))
            connection.execute("INSERT INTO events(endpoint_id,kind,detail,created_at) VALUES(?,?,?,?)", ("agent", "TEST", "{}", timestamp))
        app.observe_agent("agent")
        app.clear_agent_state("agent")
        with app.db() as connection:
            self.assertIsNotNone(connection.execute("SELECT 1 FROM agents WHERE endpoint_id='agent'").fetchone())
            for table in ("parameters", "parameter_history", "traffic_counters", "traffic_samples", "model_schema", "events"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE endpoint_id='agent'").fetchone()[0], 0)
        self.assertNotIn("agent", app.observed_agents)

    def test_delete_removes_agent_and_all_state(self):
        app.clear_agent_state("agent", remove_agent=True)
        with app.db() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM agents WHERE endpoint_id='agent'").fetchone())
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM parameters WHERE endpoint_id='agent'").fetchone()[0], 0)

    def test_websocket_presence_does_not_overwrite_mqtt_route(self):
        timestamp = app.now()
        with app.db() as connection:
            connection.execute("UPDATE agents SET mqtt_topic=?,reply_topic=? WHERE endpoint_id=?", ("usp/agent/agent", "usp/reply/agent", "agent"))
        app.upsert_agent("agent", "1.3", transport="websocket")
        with app.db() as connection:
            row = connection.execute("SELECT mqtt_topic,reply_topic,remote_meta FROM agents WHERE endpoint_id='agent'").fetchone()
        self.assertEqual(row["mqtt_topic"], "usp/agent/agent")
        self.assertEqual(row["reply_topic"], "usp/reply/agent")
        self.assertIn("websocket", json.loads(row["remote_meta"])["transports"])

    def test_websocket_endpoint_validation(self):
        self.assertTrue(app.valid_websocket_endpoint("os::00040E-123456789ABC"))
        self.assertFalse(app.valid_websocket_endpoint(""))
        self.assertFalse(app.valid_websocket_endpoint("invalid endpoint"))

    def test_websocket_basic_authentication(self):
        old_token, old_username = app.WEBSOCKET_TOKEN, app.WEBSOCKET_USERNAME
        try:
            app.WEBSOCKET_TOKEN, app.WEBSOCKET_USERNAME = "test-secret", "box"
            authorization = "Basic " + base64.b64encode(b"box:test-secret").decode()
            self.assertTrue(app.valid_websocket_credentials(authorization, ""))
            invalid_authorization = "Basic " + base64.b64encode(b"box:wrong").decode()
            self.assertFalse(app.valid_websocket_credentials(invalid_authorization, ""))
        finally:
            app.WEBSOCKET_TOKEN, app.WEBSOCKET_USERNAME = old_token, old_username


if __name__ == "__main__":
    unittest.main()
