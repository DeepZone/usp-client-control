#!/bin/sh
set -eu

umask 077
mkdir -p data mosquitto/data mosquitto/log mosquitto/certs

if [ ! -f .env ]; then
  app_secret="$(openssl rand -hex 32)"
  controller_password="$(openssl rand -base64 24 | tr -d '\n')"
  agent_password="$(openssl rand -base64 24 | tr -d '\n')"
  admin_password="$(openssl rand -base64 18 | tr -d '\n')"
  sed -e "s|__APP_SECRET__|$app_secret|" \
      -e "s|__CONTROLLER_PASSWORD__|$controller_password|" \
      -e "s|__AGENT_PASSWORD__|$agent_password|" \
      -e "s|__ADMIN_PASSWORD__|$admin_password|" .env.example > .env
fi

if [ ! -f mosquitto/certs/server.key ]; then
  common_name="$(sed -n 's/^MQTT_TLS_COMMON_NAME=//p' .env | head -n 1)"
  common_name="${common_name:-localhost}"
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
    -subj "/CN=$common_name/O=USP Client Control" \
    -keyout mosquitto/certs/server.key -out mosquitto/certs/server.crt
  cp mosquitto/certs/server.crt mosquitto/certs/ca.crt
fi

. ./.env
docker run --rm -v "$PWD/mosquitto/config:/work" eclipse-mosquitto:2.0 \
  sh -c "touch /work/passwords && mosquitto_passwd -b /work/passwords controller '$MQTT_CONTROLLER_PASSWORD' && mosquitto_passwd -b /work/passwords box '$MQTT_AGENT_PASSWORD'"
chmod 600 .env mosquitto/config/passwords mosquitto/certs/server.key
chown 1883:1883 mosquitto/config/acl mosquitto/config/passwords mosquitto/certs/ca.crt mosquitto/certs/server.crt mosquitto/certs/server.key
chmod 755 data mosquitto mosquitto/config mosquitto/certs mosquitto/data mosquitto/log
chmod 600 mosquitto/config/acl mosquitto/config/passwords mosquitto/certs/server.key
chmod 644 mosquitto/certs/ca.crt mosquitto/certs/server.crt
chown 10001:10001 data

docker compose build --pull
docker compose up -d
printf 'ADMIN_USERNAME=%s\nADMIN_PASSWORD=%s\nMQTT_AGENT_USERNAME=%s\nMQTT_AGENT_PASSWORD=%s\n' "$ADMIN_USERNAME" "$ADMIN_PASSWORD" "$MQTT_AGENT_USERNAME" "$MQTT_AGENT_PASSWORD"
