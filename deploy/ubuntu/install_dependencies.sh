#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT_DEFAULT="/opt/monitoring"
PYTHON_VERSION_DEFAULT="3.11"
REDIS_PORT_DEFAULT="6379"
TIMEZONE_DEFAULT="Asia/Shanghai"

PROJECT_ROOT="${PROJECT_ROOT:-$PROJECT_ROOT_DEFAULT}"
PYTHON_VERSION="${PYTHON_VERSION:-$PYTHON_VERSION_DEFAULT}"
REDIS_PORT="${REDIS_PORT:-$REDIS_PORT_DEFAULT}"
TIMEZONE="${TIMEZONE:-$TIMEZONE_DEFAULT}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root: sudo bash $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "[1/8] Updating apt indexes..."
apt-get update -y

echo "[2/8] Installing base packages..."
apt-get install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  lsb-release \
  software-properties-common \
  unzip \
  wget \
  build-essential \
  pkg-config \
  tzdata

echo "[3/8] Setting timezone to ${TIMEZONE}..."
timedatectl set-timezone "${TIMEZONE}" || true

echo "[4/8] Installing Python ${PYTHON_VERSION} and common tooling..."
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -y
apt-get install -y \
  "python${PYTHON_VERSION}" \
  "python${PYTHON_VERSION}-dev" \
  "python${PYTHON_VERSION}-venv" \
  python3-pip

if ! command -v python3 >/dev/null 2>&1; then
  ln -sf "/usr/bin/python${PYTHON_VERSION}" /usr/local/bin/python3
fi

python3 -m pip install --upgrade pip setuptools wheel

echo "[5/8] Installing Redis..."
apt-get install -y redis-server
sed -i "s/^port .*/port ${REDIS_PORT}/" /etc/redis/redis.conf
systemctl enable redis-server
systemctl restart redis-server

echo "[6/8] Installing PostgreSQL..."
apt-get install -y postgresql postgresql-contrib
systemctl enable postgresql
systemctl restart postgresql

echo "[7/8] Installing Chromium runtime dependencies..."
CHROMIUM_PACKAGE=""
if apt-cache show chromium >/dev/null 2>&1; then
  CHROMIUM_PACKAGE="chromium"
elif apt-cache show chromium-browser >/dev/null 2>&1; then
  CHROMIUM_PACKAGE="chromium-browser"
fi

if [[ -z "${CHROMIUM_PACKAGE}" ]]; then
  echo "Unable to find chromium package in apt repositories."
  echo "Please install Chromium manually before setting up Playwright-based login flows."
  exit 1
fi

apt-get install -y \
  "${CHROMIUM_PACKAGE}" \
  fonts-liberation \
  libasound2 \
  libatk-bridge2.0-0 \
  libatk1.0-0 \
  libcups2 \
  libdbus-1-3 \
  libdrm2 \
  libgbm1 \
  libglib2.0-0 \
  libgtk-3-0 \
  libnss3 \
  libnspr4 \
  libu2f-udev \
  libvulkan1 \
  libx11-6 \
  libx11-xcb1 \
  libxcb1 \
  libxcomposite1 \
  libxdamage1 \
  libxext6 \
  libxfixes3 \
  libxkbcommon0 \
  libxrandr2 \
  xdg-utils

echo "[8/8] Installing Docker Engine and Compose plugin..."
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable
EOF

apt-get update -y
apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

systemctl enable docker
systemctl restart docker

install -d -m 0755 "${PROJECT_ROOT}"

echo
echo "Dependencies installed successfully."
echo "Python: $(python3 --version)"
echo "Redis: $(redis-server --version | head -n 1)"
echo "Docker: $(docker --version)"
echo "Compose: $(docker compose version)"
echo "Project root prepared at: ${PROJECT_ROOT}"
