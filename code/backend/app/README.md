# app 目录说明

本目录是后端主应用代码区（FastAPI + YOLOv8 + WebRTC signaling + invite rooms）。

## 当前结构

- `main.py`
- `api/`
  - `routes/`
- `core/`
- `services/`
- `state/`
- `utils/`

## 各目录职责

### `main.py`
应用入口文件。
1. 创建 FastAPI 实例。
2. 挂载中间件（CORS）。
3. 注册 HTTP 路由和 WebSocket 路由。
4. 注册全局异常处理（统一 JSON 响应结构）。
5. 启动时加载 YOLO 模型。

### `api/routes/`
按协议暴露接口。
1. `auth.py`：注册/登录。
2. `health.py`：健康检查和 WebRTC 配置回显。
3. `rooms.py`：房间创建、邀请码入房、离房、关房、查房。
4. `chat.py`：房间聊天会话、消息发送/查询、已读游标更新。
5. `inference.py`：图片上传检测、状态、快照。
6. `signaling.py`：WebRTC 信令（offer/answer/ice、peer_join/peer_leave）。

### `services/`
业务逻辑层。
1. `auth_service.py`：数据库用户认证逻辑。
2. `room_service.py`：房间与邀请码管理（数据库态，落库到 `study_rooms` / `room_memberships`）。
3. `chat_service.py`：房间聊天会话、消息与已读游标管理（数据库态）。
4. `inference_service.py`：YOLO 推理与状态维护。
5. `signaling_service.py`：WebSocket 连接管理、定向转发、广播、房间连接关闭。

### `state/`
内存运行态。
1. `runtime.py`：YOLO 检测共享状态。
2. `signaling_state.py`：信令连接表（`room_id -> user_id -> websocket`）。

### `core/`
全局配置与错误定义。
1. `error_codes.py`：错误码文案映射。
2. `webrtc_config.py`：STUN/TURN 环境变量加载。

### `utils/`
通用工具。
1. `response.py`：统一 `success/error` JSON 包装。

## 统一响应约定

除二进制接口（如 `/snapshot`）外，JSON 接口统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

错误时：

```json
{
  "code": "invalid_credentials",
  "message": "登录失败：账号或密码错误",
  "data": null
}
```

## 邀请码房间规则（当前版本）

1. 创建房间自动生成 12 位数字邀请码。
2. 邀请码可重复使用（房间关闭或邀请码失效前）。
3. 通过邀请码入房必须是已登录用户（`users` 表存在该 `user_id`）。
4. 最后一位成员离开时房间自动关闭。
5. 房主可手动关闭房间，关闭后新加入和新信令连接会被拒绝。
6. 房间和成员关系持久化在 PostgreSQL，服务重启不影响已创建房间数据。

## WebRTC 说明

1. 后端仅处理信令，不转发媒体流。
2. 媒体（音频+视频）由浏览器间 P2P 传输。
3. 默认建议小房间 Mesh（2-6 人）。
4. 入房默认麦克风静音由前端控制。
