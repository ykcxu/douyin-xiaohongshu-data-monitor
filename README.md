# 抖音小红书数据监测

一个面向抖音与小红书的数据监测项目，用于持续采集直播、账号、视频、笔记、评论、点赞、粉丝等核心指标。

## 当前阶段

当前仓库已完成项目初始化，需求与开发设计文档见：

- `docs/开发文档.md`
- `deploy/ubuntu/install_dependencies.sh`
- `deploy/ubuntu/bootstrap_server.sh`
- `deploy/ubuntu/DEPLOY.md`

## 目录结构

```text
src/    业务代码
data/   原始数据与中间产物
logs/   运行日志
docs/   项目文档
deploy/ Ubuntu 部署脚本
runtime/ 本地运行时数据
```

## 本地开发

```bash
copy .env.example .env
py -3 -m pip install -e .
py -3 src/main.py
```

## Docker 启动

```bash
cp .env.example .env
docker compose up --build
```
