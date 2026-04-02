# 抖音小红书数据监测

一个面向抖音与小红书的数据监测项目，用于持续采集直播、账号、视频、笔记、评论、点赞、粉丝等核心指标。

## 当前阶段

当前仓库已完成项目初始化，需求与开发设计文档见：

- `docs/开发文档.md`
- `docs/API说明.md`
- `docs/运行说明.md`
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
py -3 -m alembic upgrade head
py -3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir src
```

## Docker 启动

```bash
cp .env.example .env
docker compose up --build
```

## 数据库迁移

```bash
py -3 -m alembic upgrade head
py -3 -m alembic revision -m "describe change"
```

## 当前能力

当前已经完成：

- 监测账号与抖音直播间管理接口
- 抖音直播扫描、场次、快照、弹幕查询骨架
- 弹幕 JSONL 归档入口
- 小红书账号、笔记、评论的查询与写入骨架
- Playwright 登录态记录与请求上下文骨架
