# 抖音小红书数据监测

一个面向抖音与小红书的数据监测项目，用于持续采集直播、账号、视频、笔记、评论、点赞、粉丝等核心指标。

## 当前能力

- 监测账号与抖音直播间管理 API
- 抖音直播扫描、场次、快照、弹幕查询骨架
- 弹幕 JSONL 归档入口
- 小红书账号、笔记、评论的查询与写入骨架
- Playwright 登录态记录、请求上下文、Provider 工厂
- Ubuntu 部署脚本、Docker、Alembic 迁移
- Windows 本地 SQLite 联调支持

## 文档入口

- [开发文档](docs/开发文档.md)
- [API说明](docs/API说明.md)
- [运行说明](docs/运行说明.md)
- [抖音直播联调笔记](docs/抖音直播联调笔记.md)
- [Ubuntu 部署说明](deploy/ubuntu/DEPLOY.md)

## Windows 本地联调

```bash
copy .env.example .env
py -3 -m pip install -e .
py -3 -m playwright install chromium
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir src
```

建议在 `.env` 中设置：

```env
AUTO_CREATE_SCHEMA=true
DATABASE_URL=sqlite:///./runtime/app.db
SCHEDULER_ENABLED=false
DOUYIN_LIVE_PROVIDER=stub
```

### 导出抖音登录态

```bash
py -3 -m app.cli.export_douyin_storage_state --account-id douyin_demo --operator admin
```

系统会打开浏览器。扫码登录完成后，回到终端按 Enter，即可把 `storage_state` 保存到 `runtime/browser` 并写入 `browser_login_state`。

### 检查登录态

```bash
py -3 -m app.cli.inspect_login_state --account-id douyin_demo
```

### 追踪真实直播间请求

```bash
py -3 -m app.cli.trace_douyin_live_requests --account-id douyin_demo --room-url https://live.douyin.com/7044145585217083655
```

这会打开带登录态的浏览器，并把 `fetch/xhr/websocket` 请求写进 `data/raw/douyin/request-trace/`，方便继续定位在线人数、弹幕和评论接口。

分析抓到的样本：

```bash
py -3 -m app.cli.analyze_douyin_trace --input data/raw/douyin/request-trace/douyin_demo-20260402T051008Z.jsonl
```

探测单个直播间的已知候选接口：

```bash
py -3 -m app.cli.probe_douyin_live_room --room-id 7044145585217083655 --account-id douyin_demo
```

如果要在浏览器页面上下文里复用 `frontierSign` 做带签名请求探测，可以直接跑：

```bash
py -3 -m app.cli.probe_douyin_signed_api --account-id douyin_demo --room-id 7044145585217083655 --preset room-web-enter
```

如果要进一步观察页面运行时自己触发了哪些 `fetch/xhr/websocket`，以及加载阶段有没有真的调用 `frontierSign`，可以直接跑：

```bash
py -3 -m app.cli.trace_douyin_page_runtime --account-id douyin_demo --room-id 7044145585217083655 --wait-seconds 15
```

如果要把 trace 里的 `frontier-pc/frontier-im` WebSocket 握手参数单独拆出来，可以直接跑：

```bash
py -3 -m app.cli.extract_douyin_frontier_ws --input data/raw/douyin/request-trace/douyin_demo-20260402T053837Z.jsonl
```

## 数据库迁移

```bash
py -3 -m alembic upgrade head
py -3 -m alembic revision -m "describe change"
```

## 目录结构

```text
src/      业务代码
data/     原始数据与样本
docs/     项目文档
deploy/   部署脚本
runtime/  本地运行时数据
scripts/  本地调试辅助脚本
```
