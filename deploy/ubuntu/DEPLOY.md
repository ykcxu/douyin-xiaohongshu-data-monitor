# Ubuntu 部署准备

适用于未安装 Python、Redis、Docker 的 Ubuntu 22.04 机器。

## 1. 安装系统依赖

```bash
sudo bash deploy/ubuntu/install_dependencies.sh
```

脚本会安装：

- Python 3.11
- pip
- Redis
- PostgreSQL
- Chromium 及 Playwright 运行依赖
- Docker Engine
- Docker Compose Plugin

## 2. 初始化部署目录

```bash
sudo bash deploy/ubuntu/bootstrap_server.sh
```

默认初始化目录：

- `/opt/monitoring/app`
- `/opt/monitoring/config`
- `/opt/monitoring/data`
- `/opt/monitoring/logs`
- `/opt/monitoring/browser`

## 3. 可选环境变量

可在执行脚本前覆盖：

```bash
export PROJECT_ROOT=/opt/monitoring
export PYTHON_VERSION=3.11
export REDIS_PORT=6379
export TIMEZONE=Asia/Shanghai
```

`bootstrap_server.sh` 可覆盖：

```bash
export APP_ROOT=/opt/monitoring
export APP_USER=monitoring
export APP_GROUP=monitoring
```
