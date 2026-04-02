#!/usr/bin/env bash

set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-/opt/monitoring}"
APP_USER="${APP_USER:-monitoring}"
APP_GROUP="${APP_GROUP:-monitoring}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root: sudo bash $0"
  exit 1
fi

if ! getent group "${APP_GROUP}" >/dev/null 2>&1; then
  groupadd --system "${APP_GROUP}"
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --gid "${APP_GROUP}" --shell /bin/bash "${APP_USER}"
fi

install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/app"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/config"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/deploy"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/logs"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/data"
install -d -m 0750 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/browser"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/data/raw"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/data/archive"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/data/postgres"
install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/data/redis"

cat >"${APP_ROOT}/config/.env.example" <<EOF
TZ=Asia/Shanghai
APP_ENV=production
APP_ROOT=${APP_ROOT}
POSTGRES_DB=monitoring
POSTGRES_USER=monitoring
POSTGRES_PASSWORD=change_me
POSTGRES_PORT=5432
REDIS_PORT=6379
EOF

chown "${APP_USER}:${APP_GROUP}" "${APP_ROOT}/config/.env.example"
chmod 0640 "${APP_ROOT}/config/.env.example"

echo "Bootstrap complete."
echo "App root: ${APP_ROOT}"
echo "App user: ${APP_USER}"
echo "Example env file: ${APP_ROOT}/config/.env.example"
