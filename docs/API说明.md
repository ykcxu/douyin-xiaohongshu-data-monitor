# API 说明

本文档描述当前已经落地的主要接口，便于联调、手工录入监测对象和后续接采集器。

## 1. 基础接口

### 健康检查

- `GET /health`
- 作用：检查服务是否启动

### 根接口

- `GET /`
- 作用：返回当前应用名和运行环境

### 系统状态

- `GET /system/status`
- 作用：查看当前调度器开关、provider 配置、关键目录状态

## 2. 监测对象管理

### 账号管理

- `GET /accounts`
- `POST /accounts`
- `GET /accounts/{account_pk}`
- `PATCH /accounts/{account_pk}`

主要用途：

- 新增监测账号
- 更新所属部门、是否竞品、负责人、标签、主页链接
- 作为抖音和小红书对象的统一业务主档

### 抖音直播间管理

- `GET /douyin/live-rooms`
- `POST /douyin/live-rooms`
- `GET /douyin/live-rooms/{room_pk}`
- `PATCH /douyin/live-rooms/{room_pk}`

主要用途：

- 新增直播间监测对象
- 启停直播间监测
- 设置直播间优先级
- 绑定账号主档

## 3. 抖音直播接口

### 手动触发扫描

- `POST /monitor/douyin/live/scan`

作用：

- 手动执行一轮直播间状态扫描
- 用于调试调度器或手动验证 provider 行为

### 直播场次查询

- `GET /douyin/live/sessions`
- `GET /douyin/live/sessions/{session_id}`

支持：

- 按 `room_id` 过滤
- 按 `status` 过滤

### 直播快照查询

- `GET /douyin/live/sessions/{session_id}/snapshots`

### 直播弹幕查询

- `GET /douyin/live/sessions/{session_id}/comments`

支持：

- 按 `message_type` 过滤

## 4. 登录态接口

### 登录态查询

- `GET /login-states?platform=douyin&account_id=xxx`

作用：

- 查看某个账号当前记录的登录态
- 确认 `storage_state_path`
- 观察当前 `status`、`last_error_code`、`last_error_message`

## 5. 小红书接口

### 小红书数据查询

- `GET /xiaohongshu/accounts/snapshots`
- `GET /xiaohongshu/notes`
- `GET /xiaohongshu/notes/{note_pk}`
- `GET /xiaohongshu/notes/{note_pk}/snapshots`
- `GET /xiaohongshu/notes/{note_pk}/comments`

### 小红书写入接口

- `POST /xiaohongshu/ingest/account-snapshot`
- `POST /xiaohongshu/ingest/note`
- `POST /xiaohongshu/ingest/note-snapshot`
- `POST /xiaohongshu/ingest/note-comment`

作用：

- 为后续真实采集器预留标准化写入口
- 当前也可用于手工联调、回放样本入库

## 6. 样本与种子接口

### Demo 种子数据

- `POST /seed/demo`

作用：

- 初始化一批演示账号与演示抖音直播间
- 方便新环境快速联调

### 抖音样本回放

- `POST /douyin/ingest/status-sample`
- `POST /douyin/ingest/comment-sample`

作用：

- 不依赖真实抖音接口，直接拿样本 JSON 跑通直播状态和弹幕链路
- 适合验证建场次、写快照、写弹幕和 JSONL 归档

## 7. 当前状态说明

当前接口层已经具备：

- 账号和直播间配置管理
- 抖音直播场次/快照/弹幕查询
- 小红书账号/笔记/评论查询
- 小红书数据写入入口
- 登录态查询

当前尚未完成：

- 真实抖音接口抓取逻辑
- 真实小红书接口抓取逻辑
- 管理后台页面
- 告警与报表接口
