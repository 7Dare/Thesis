# 前端设计计划文档 v0.1

## 0. 最新进展（已同步）

已完成：
1. 前端工程已初始化并可运行：`frontend/app`（Vue3 + TS + Vite）。
2. 路由与页面骨架已落地：`/auth`、`/lobby`、`/room/:roomId`。
3. 认证与房间主流程已接通：登录/注册、创建房间、邀请码入房、离房、关房、房间详情。
4. 聊天一期已接通：会话初始化、消息发送、历史分页拉取、已读游标更新、轮询刷新。
5. 房间页布局已更新：右侧显示房间信息与成员列表；聊天区显示规则为“自己右侧、他人左侧”。
6. 成员显示已按 `display_name` 展示（不再直接展示 `user_id`）。
7. 学习时长统计已接入：房间进行时长、房间累计、个人累计、成员累计排行。
8. 个人页已接入：最近365天学习热力图 + 6项统计。

当前未完成：
1. `RoomPage` 的 WebRTC 连麦仍为占位区，尚未接入 `VideoWall` 与 `peerManager`。
2. YOLO 区域仍未接入定时上传帧、状态轮询与快照展示。

## 1. 背景与目标

当前已完成基础条件：
1. 已有架构文档：`FRONTEND_ARCHITECTURE_v0.1.md`。
2. 已初始化前端工程：`frontend/app`（Vue3 + TS + Vite）。
3. 已完成基础 API 调用层（services/types/http 封装）。

本文目标：
1. 将页面开发与联调任务拆成明确里程碑。
2. 定义页面、状态、接口、异常处理和验收标准。
3. 作为后续实现和联调的执行依据。

## 2. 范围定义

### 2.1 In Scope
1. `Auth / Lobby / Room` 三页面落地。
2. 房间创建、邀请码入房、离房、关房。
3. 房间聊天（会话初始化、发消息、分页拉取、更新已读游标）。
4. YOLO 状态展示（上传帧、状态展示、快照展示）。
5. WebRTC 连麦（WS 信令 + P2P 音视频）。
6. 个人学习统计页（365天热力图 + 6项汇总）。

### 2.2 Out of Scope
1. 私聊、好友、群组管理。
2. 文件/图片消息。
3. UI 深度视觉打磨与设计系统建设。
4. 后台管理与运营模块。

## 3. 阶段拆分（里程碑）

### M1：路由与页面骨架
状态：已完成

1. 建立 `Vue Router` 基础路由：
   - `/auth`
   - `/lobby`
   - `/room/:roomId`
2. 页面骨架及基础布局落地。
3. 全局导航守卫（未登录跳转 `/auth`）。

### M2：认证与房间流程接通
状态：已完成

1. `/auth` 接通注册/登录接口。
2. `/lobby` 接通创建房间与邀请码入房。
3. `/room/:roomId` 初始化房间详情加载与离房/关房操作。

### M3：聊天与已读游标接通
状态：已完成（一期轮询版）

1. 进入房间初始化会话。
2. 发送消息与消息列表分页拉取。
3. 已读游标更新逻辑。
4. 聊天区错误提示和空状态处理。

### M4：连麦 + YOLO 并行联调
状态：进行中

1. 建立 WS 信令连接。
2. WebRTC peer 连接与远端流渲染。
3. 定时上传帧 + 状态展示 + 快照展示。
4. 保证聊天、连麦、YOLO 三链路互不阻塞。

### M5：异常流程与回归验证
状态：待开始

1. 断线重连策略验证。
2. 房间关闭/成员权限失败回退验证。
3. 回归 `camera_dashboard` 仍可运行。

## 4. 页面任务清单

## 4.1 `/auth`
输入：
1. `login_user_id`
2. `password`
3. `display_name`（注册）
4. `email`（注册可选）

操作：
1. 注册请求
2. 登录请求

输出：
1. 登录成功后写入认证状态并跳转 `/lobby`。

异常提示：
1. 参数缺失
2. 账号已存在
3. 密码错误
4. 网络错误

## 4.2 `/lobby`
输入：
1. 创建房间：房间名、时长
2. 加入房间：邀请码

操作：
1. 创建房间
2. 邀请码入房

输出：
1. 成功后进入 `/room/:roomId`。

异常提示：
1. 邀请码格式错误/失效
2. 房间不可用
3. 用户已有进行中房间

## 4.3 `/room/:roomId`
模块：
1. 聊天区（消息列表 + 输入框，自己消息右侧、他人消息左侧）
2. 右侧房间信息区（名称、状态、房主、邀请码、成员数、结束时间）
3. 右侧成员列表（显示 `display_name` 与角色）
4. 右侧学习时长统计区（累计时长与成员排行）
5. 视频区（本地 + 远端，待接入）
6. YOLO 状态区（status/person_count/phone_count + 快照，待接入）

操作：
1. 初始化房间与会话
2. 发消息、拉消息、更新已读
3. 开关麦克风/摄像头
4. 离房或关房

异常提示：
1. 非成员访问
2. 房间关闭
3. WS 断开
4. 推理上传失败

## 5. 状态与数据流计划

## 5.1 `authStore`
字段：
1. `userId`
2. `loginUserId`
3. `displayName`
4. `isAuthed`

更新来源：
1. 登录成功写入。
2. 刷新时从本地存储恢复（一期最小实现）。

清理时机：
1. 主动退出登录。
2. 凭证失效。

## 5.2 `roomStore`
字段：
1. `roomId`
2. `hostUserId`
3. `inviteCode`
4. `status`
5. `members`

更新来源：
1. 创建/加入房间返回。
2. 进入房间页后 `GET /rooms/{id}` 刷新。

清理时机：
1. 离房后清理。
2. 房间关闭后清理。

## 5.3 `chatStore`
字段：
1. `conversationId`
2. `messages`
3. `nextBeforeMessageId`
4. `readCursor`

更新来源：
1. 会话初始化接口。
2. 消息分页拉取接口。
3. 已读游标更新接口。

清理时机：
1. 退出房间时清理。

## 5.4 `mediaStore`
字段：
1. `localStream`
2. `peers`
3. `remoteStreams`
4. `micEnabled`
5. `camEnabled`
6. `wsConnected`

更新来源：
1. 进入房间后建立媒体与 WS。
2. 信令消息更新 peer 状态。

清理时机：
1. 离房/关房/页面卸载时关闭连接。

## 5.5 `inferenceStore`
字段：
1. `status`
2. `personCount`
3. `phoneCount`
4. `ts`
5. `snapshotUrl`

更新来源：
1. `POST /ingest/frame`
2. `GET /status`
3. `GET /snapshot`

清理时机：
1. 离房时停止轮询并清空。

## 6. 接口对接计划（引用后端协议）

## 6.1 认证接口
1. `POST /auth/register`
2. `POST /auth/login`

调用时机：
1. `/auth` 表单提交。

成功处理：
1. 写入 `authStore`。
2. 跳转 `/lobby`。

失败处理：
1. 根据 `code/message` 提示并保留输入状态。

## 6.2 房间接口
1. `POST /rooms`
2. `POST /rooms/join-by-invite`
3. `POST /rooms/{id}/leave`
4. `POST /rooms/{id}/close`
5. `GET /rooms/{id}`
6. `GET /rooms/{id}/study-time`

调用时机：
1. 大厅创建/入房。
2. 房间页初始化。
3. 离房/关房操作。

## 6.3 聊天接口
1. `GET /rooms/{id}/chat/conversation`
2. `POST /rooms/{id}/chat/messages`
3. `GET /rooms/{id}/chat/messages`
4. `POST /rooms/{id}/chat/read-cursor`

调用时机：
1. 进房初始化会话。
2. 点击发送消息。
3. 初次加载与历史翻页。
4. 用户读到最新消息后更新游标。

## 6.4 推理接口
1. `POST /ingest/frame`
2. `GET /status`
3. `GET /snapshot`

调用时机：
1. 进房后定时上传与展示。

## 6.5 信令接口
1. `WS /rooms/{room_id}/signal?...`

调用时机：
1. 进入房间建立连接。
2. 处理 `offer/answer/ice/peer_join/peer_leave/room_closed`。

## 7. 关键交互时序

1. 用户登录成功进入大厅。
2. 创建房间或邀请码入房。
3. 进入房间后加载房间详情与聊天会话。
4. 建立信令连接并启动 WebRTC。
5. 开始上传帧并更新 YOLO 状态。
6. 聊天发收与已读游标同步。
7. 用户离房/房主关房，清理连接与定时器并回大厅。

异常回退：
1. 断网：提示并触发重连。
2. 房间关闭：提示后回大厅。
3. 权限失败：提示后回大厅。

## 8. 错误处理规范

统一规则：
1. `code === 0`：按 `data` 更新状态。
2. `code !== 0`：toast `message`，按错误码执行页面动作。

常见错误码行为：
1. `room_not_active`：提示并退出房间页。
2. `not_room_member`：提示并回大厅。
3. `host_active_room_exists`：停留大厅并提示“请先结束当前房间”。
4. `invalid_credentials`：停留登录页并提示。
5. `network_error/http_5xx`：提示“网络异常，请重试”。

## 9. 测试与验收标准

每条用例记录：
1. 前置条件
2. 操作步骤
3. 预期结果

### 9.1 单用户流程
1. 登录 -> 创建房间 -> 发消息 -> 更新已读 -> 关闭房间。

### 9.2 双用户流程
1. 邀请码入房 -> 连麦 -> 双向聊天 -> 一方离开。

### 9.3 异常流程
1. 缺参请求。
2. 非成员访问。
3. 房间关闭后继续操作。
4. WS 断开重连。

### 9.4 回归流程
1. `camera_dashboard` 现有 demo 可继续运行。

## 10. 风险与后续扩展

风险：
1. Mesh 连麦在多成员场景下带宽与 CPU 压力增大。
2. YOLO 帧上传频率过高会影响前端渲染性能。
3. 聊天轮询/分页策略不当会导致重复请求与卡顿。

应对：
1. 限制房间人数（建议 2-6）。
2. 帧上传频率控制在 500ms~800ms。
3. 聊天分页按 `before_message_id` 控制增量加载。

二期扩展点：
1. 私聊与好友关系。
2. 文件/图片消息。
3. 聊天实时推送（独立 WS）。
4. 更完善的 UI 与可观测性（埋点/日志）。

## 11. 下一步执行项（当前建议）

1. 完成 `M4`：先接入 `peerManager + mediaStore + VideoWall`，跑通 2 人连麦。
2. 接入 YOLO 前端链路：本地视频截图上传 `/ingest/frame`，并行轮询 `/status` 与 `/snapshot`。
3. 增加房间关闭与 WS 断线的页面级回退提示，进入 `M5` 异常回归。

## Public API / Interface Changes
1. 本文档阶段不新增后端 API。
2. 前端仅按现有 `API_PROTOCOL_v0.2.md` 执行调用规范。

## Assumptions and Defaults
1. 文档路径固定：`thesis/code/frontend/FRONTEND_IMPLEMENTATION_PLAN_v0.1.md`。
2. 技术栈固定：`Vue3 + TS + Vite + Pinia + Axios`。
3. 一期优先完成功能闭环，再进行视觉优化。
4. 后续页面实现严格遵循本计划与后端协议。
