# 前端架构设计文档 v0.1（Vue3 + TS + Vite）

## 0. 当前实现状态（已同步）

已落地模块：
1. `frontend/app` 已初始化并可运行。
2. 路由与页面：`AuthPage`、`LobbyPage`、`RoomPage` 已创建并接入。
3. API 调用层已建立：认证、房间、聊天相关服务与类型。
4. `RoomPage` 已完成聊天一期 UI 与接口联调（发送、拉取、已读游标、轮询刷新）。
5. 房间信息与成员列表位于右侧区域，成员展示优先 `display_name`。
6. 房间学习时长统计已接入（房间累计/个人累计/成员排行）。
7. 个人页学习热力图已接入（最近365天 + 6项统计）。

待落地模块：
1. `src/webrtc/peerManager.ts`、`VideoWall`、`mediaStore` 的完整连麦链路。
2. YOLO 前端链路（定时截图上传、状态轮询、快照展示）。

## 1. 项目目标与范围

### 1.1 一期目标
1. 登录/注册（对接后端 `/auth/register`、`/auth/login`）。
2. 创建自习室、邀请码入房、离房、关房（对接后端 `/rooms` 系列接口）。
3. 房间内聊天（会话查询、发送消息、拉取消息、更新已读游标）。
4. 房间内音视频连麦（WebRTC，后端仅信令）。
5. YOLO 学习状态展示（定时上传帧 + 状态展示 + 快照展示）。

### 1.2 非目标（一期不做）
1. 好友系统。
2. 私聊和群聊扩展（当前仅房间群聊）。
3. 文件/图片消息上传。
4. 管理后台与运营系统。

## 2. 技术栈与工程约定

| 项目 | 选型 | 说明 |
|---|---|---|
| 前端框架 | Vue 3 | 使用 Composition API |
| 语言 | TypeScript | 强类型约束接口与状态 |
| 构建工具 | Vite | 本地开发与构建 |
| 路由 | Vue Router | 页面级路由管理 |
| 状态管理 | Pinia | 全局业务状态 |
| 网络请求 | Axios | 统一封装 `{code,message,data}` 响应 |
| 实时通信 | WebSocket + WebRTC | 信令与音视频 |
| UI 组件 | 可后续引入（Element Plus） | 一期可先原生组件 |

环境变量约定：
1. `VITE_API_BASE`：HTTP 接口基础地址（如 `http://localhost:8000`）。
2. `VITE_WS_BASE`：WebSocket 基础地址（如 `ws://localhost:8000`，可选，不设时由 `API_BASE` 转换）。

## 3. 目录设计

```text
frontend/
  app/                      # 正式 Vue 项目（已创建）
    src/
      pages/
        AuthPage.vue
        LobbyPage.vue
        RoomPage.vue
      components/
        auth/
        room/
        chat/
        media/
        inference/
      stores/
        auth.ts
        room.ts
        chat.ts
        media.ts
        inference.ts
      services/
        http.ts
        auth.ts
        room.ts
        chat.ts
        inference.ts
        signaling.ts
      webrtc/
        peerManager.ts
      types/
        api.ts
        auth.ts
        room.ts
        chat.ts
        inference.ts
      utils/
        env.ts
        error.ts
        time.ts
      router/
        index.ts
      App.vue
      main.ts
  camera_dashboard/         # 现有临时 demo，继续保留
  FRONTEND_ARCHITECTURE_v0.1.md
  README.md
```

依赖方向约束：
1. `pages -> stores/services/components`。
2. `stores -> services/types`。
3. `services -> http/types`。
4. `services` 不依赖 `pages`。

## 4. 页面与路由设计

| 路由 | 页面 | 输入 | 关键操作 | 输出/展示 | 异常提示 |
|---|---|---|---|---|---|
| `/auth` | 登录注册页 | login_user_id/password/display_name/email | 注册、登录 | 登录成功后写入 `authStore` 并跳转 `/lobby` | 表单缺失、账号冲突、密码错误 |
| `/lobby` | 大厅页 | 房间名、时长、邀请码 | 创建房间、邀请码入房 | 进入 `/room/:roomId` | 邀请码失效、房间已关闭、用户非成员 |
| `/room/:roomId` | 自习页 | 用户上下文、房间 ID | 建立信令、连麦、发消息、拉消息、更新已读、上传帧、离房/关房、拉取学习时长 | 视频墙、聊天区、YOLO 状态区、学习时长统计区 | WS 断开、房间关闭、接口超时、权限失败 |
| `/profile` | 个人页 | 用户上下文 | 拉取最近365天学习数据 | 学习热力图 + 6项统计 | 数据加载失败、网络异常 |

页面最小交互要求：
1. `RoomPage` 首次进入必须完成房间信息加载与成员权限校验。
2. 连麦失败不应阻塞聊天与 YOLO 展示。
3. 聊天失败不应影响连麦与推理上传。

## 5. 状态模型（Pinia）

### 5.1 `authStore`
- `userId`
- `loginUserId`
- `displayName`
- `isAuthed`

来源与刷新：
1. 登录成功写入。
2. 页面刷新从 `localStorage` 恢复（一期可选）。

### 5.2 `roomStore`
- `roomId`
- `hostUserId`
- `inviteCode`
- `status`
- `members`

来源与刷新：
1. 创建/入房接口返回。
2. 进入房间页时调用 `GET /rooms/{room_id}` 刷新。

### 5.3 `chatStore`
- `conversationId`
- `messages`
- `nextBeforeMessageId`
- `readCursor`（`lastReadMessageId`、`updatedAt`）

来源与刷新：
1. `GET /chat/conversation` 初始化。
2. `GET /chat/messages` 分页追加。
3. `POST /chat/read-cursor` 更新已读游标。

### 5.4 `mediaStore`
- `localStream`
- `peers`
- `remoteStreams`
- `micEnabled`
- `camEnabled`
- `wsConnected`

来源与刷新：
1. 加入房间后创建本地流和 WS 连接。
2. `peer_join/peer_leave` 动态更新。

### 5.5 `inferenceStore`
- `status`
- `personCount`
- `phoneCount`
- `ts`
- `snapshotUrl`

来源与刷新：
1. 周期性上传帧后更新状态。
2. 周期性拉取 `/snapshot` 更新快照。

## 6. 接口映射与前端类型草案

### 6.1 统一响应类型

```ts
export interface ApiSuccess<T> {
  code: 0;
  message: string;
  data: T;
}

export interface ApiError {
  code: string;
  message: string;
  data: null;
}
```

### 6.2 认证接口
1. `POST /auth/register`（`application/x-www-form-urlencoded`）
2. `POST /auth/login`（`application/x-www-form-urlencoded`）

前端调用时机：
1. `AuthPage` 提交表单。
2. 成功后写 `authStore`。

### 6.3 房间接口
1. `POST /rooms`
2. `POST /rooms/join-by-invite`
3. `POST /rooms/{id}/leave`
4. `POST /rooms/{id}/close`
5. `GET /rooms/{id}`
6. `GET /rooms/{id}/study-time`
7. `GET /users/{user_id}/study-calendar`

前端调用时机：
1. `LobbyPage` 创建或加入房间。
2. `RoomPage` 进入时拉取房间详情。
3. `RoomPage` 离房或关房按钮触发。

### 6.4 聊天接口
1. `GET /rooms/{id}/chat/conversation?user_id=...`
2. `POST /rooms/{id}/chat/messages`
3. `GET /rooms/{id}/chat/messages?user_id=...&limit=...&before_message_id=...`
4. `POST /rooms/{id}/chat/read-cursor`

前端调用时机：
1. 进入 `RoomPage` 初始化会话。
2. 发送按钮提交消息。
3. 打开聊天区与滚动翻页加载历史。
4. 读到最新消息后更新游标。

### 6.5 推理接口
1. `POST /ingest/frame`
2. `GET /status`
3. `GET /snapshot`

前端调用时机：
1. 入房后启动定时上传帧（500~800ms/帧）。
2. 定时拉状态和快照展示。

### 6.6 信令接口
1. `WS /rooms/{room_id}/signal?user_id=<uid>&display_name=<name>`

前端调用时机：
1. 进入 `RoomPage` 连接 WS。
2. 处理 `offer/answer/ice/peer_join/peer_leave/room_closed`。

## 7. 关键交互流程（时序）

1. 登录成功后进入大厅。
2. 创建房间或邀请码入房。
3. 进入房间页，拉取房间详情并初始化聊天会话。
4. 建立 WS 与 WebRTC，渲染本地/远端视频。
5. 启动 YOLO 帧上传与状态轮询。
6. 聊天发送与消息分页拉取并维护已读游标。
7. 离房或房主关房，清理定时器/连接并回大厅。

断线与刷新最小策略：
1. WS 断线：指数退避重连（1s/2s/4s，最多 5 次）。
2. 页面刷新：通过 `roomId + userId` 恢复最小状态并重新入会话。

## 8. 错误处理与用户提示规范

统一处理：
1. `code === 0`：按 `data` 更新 UI。
2. `code !== 0`：toast `message`，并按错误码做页面级行为。

常见错误码与前端动作：
1. `not_room_member`：提示后回大厅。
2. `room_not_active` / `room_closed`：提示“房间不可用”，回大厅。
3. `host_active_room_exists`：停留大厅并展示“请先结束当前房间”。
4. `invalid_credentials`：停留登录页高亮错误。
5. 网络超时：展示“网络异常，请重试”并提供重试按钮。

## 9. 联调验收清单

### 9.1 单用户流程
1. 登录 -> 创建房间 -> 发送消息 -> 更新已读 -> 关闭房间。

### 9.2 双用户流程
1. A 创建房间并分享邀请码。
2. B 输入邀请码入房。
3. A/B 连麦成功并可互发聊天消息。
4. 任一方离房后 UI 状态正确更新。

### 9.3 异常流程
1. 缺失参数返回错误并展示提示。
2. 房间关闭时页面自动回退或提示。
3. 非成员访问聊天接口时被拒绝并回大厅。
4. WS 中断后自动重连并提示状态。

### 9.4 回归流程
1. `camera_dashboard` 临时 demo 保持可运行，不因架构文档变更而失效。

## 10. 假设与默认值

1. 使用现有目录 `~/Thesis/code/frontend`，不创建 `fronted`。
2. 一期前端按 `Vue3 + TS + Vite` 实施。
3. 本文档覆盖架构、页面、状态、接口映射，不含详细排期。
4. `frontend/app` 项目骨架与首批页面已完成，后续按实现计划继续补齐音视频与 YOLO。
