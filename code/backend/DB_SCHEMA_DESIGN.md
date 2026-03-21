# 数据库表设计（v0.5 表格版）

适用场景：自习室管理 + WebRTC 信令 + YOLO 学习状态检测 + 聊天功能。

当前策略：`12位数字邀请码`、`可重复使用`、`房间关闭或到期后失效`、成员可中途离开后重入并保留历史记录、聊天一期仅支持房间群聊（`text/system`）+ 会话级已读游标。

## 1. 选型与主键策略

| 项目 | 设计 |
|---|---|
| 数据库 | PostgreSQL |
| 主键策略 | 业务实体表使用 `UUID`，事件流水表使用 `BIGSERIAL` |
| 时间字段 | 统一 `TIMESTAMPTZ` |

## 2. 表结构设计

## 2.1 `users`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | UUID | PK, NOT NULL | 用户主键 |
| login_user_id | VARCHAR(64) | NOT NULL, UNIQUE | 登录用户 ID（用于登录） |
| display_name | VARCHAR(64) | NOT NULL | 显示名 |
| email | VARCHAR(128) | UNIQUE | 邮箱（可空） |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| avatar_url | VARCHAR(255) | NULL | 头像地址 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 更新时间 |

## 2.2 `study_rooms`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| room_id | UUID | PK, NOT NULL | 房间主键 |
| room_name | VARCHAR(120) | NOT NULL | 房间名称 |
| host_user_id | UUID | NOT NULL, FK -> users.user_id | 房主 |
| duration_minutes | INT | NOT NULL, CHECK > 0 | 计划时长（分钟） |
| started_at | TIMESTAMPTZ | NOT NULL | 开始时间 |
| ends_at | TIMESTAMPTZ | NOT NULL | 结束时间（到时自动失效） |
| status | VARCHAR(20) | NOT NULL | `active`/`closed`/`ended` |
| closed_at | TIMESTAMPTZ | NULL | 关闭时间 |
| invite_code | VARCHAR(12) | NOT NULL, UNIQUE | 12 位数字邀请码（与房间一一绑定） |
| max_members | INT | NOT NULL, DEFAULT 6 | 最大成员数（Mesh 建议小房间） |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 更新时间 |

## 2.3 `room_memberships`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| membership_id | UUID | PK, NOT NULL | 成员关系主键 |
| room_id | UUID | NOT NULL, FK -> study_rooms.room_id | 房间 ID |
| user_id | UUID | NOT NULL, FK -> users.user_id | 用户 ID |
| role | VARCHAR(20) | NOT NULL | `host`/`member` |
| joined_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 本次加入时间 |
| left_at | TIMESTAMPTZ | NULL | 本次离开时间 |
| leave_reason | VARCHAR(40) | NULL | `manual_leave`/`room_closed`/`disconnect_timeout` |
| is_muted | BOOLEAN | NOT NULL, DEFAULT false | 连麦静音状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 创建时间 |

> 历史模式：每次进入新增记录，离开时写入 `left_at`，支持中途退出后再次加入。
>
> 关键唯一约束：`UNIQUE(room_id, user_id, joined_at)`

> 邀请码有效性由房间状态控制：房间 `active` 时可用，`closed/ended` 时不可用。

## 2.4 `webrtc_peers`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| peer_session_id | UUID | PK, NOT NULL | 连麦会话主键 |
| room_id | UUID | NOT NULL, FK -> study_rooms.room_id | 房间 ID |
| user_id | UUID | NOT NULL, FK -> users.user_id | 用户 ID |
| connection_state | VARCHAR(20) | NOT NULL | `connecting`/`connected`/`disconnected` |
| ws_session_id | VARCHAR(128) | NULL | WebSocket 会话标识 |
| joined_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 进入连麦时间 |
| last_heartbeat_at | TIMESTAMPTZ | NULL | 最近心跳时间 |
| left_at | TIMESTAMPTZ | NULL | 离开时间 |
| disconnect_reason | VARCHAR(40) | NULL | `normal`/`network_error`/`room_closed` |

## 2.5 `user_inference_state`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| state_id | UUID | PK, NOT NULL | 状态主键 |
| room_id | UUID | NOT NULL, FK -> study_rooms.room_id | 房间 ID |
| user_id | UUID | NOT NULL, FK -> users.user_id | 用户 ID |
| status | VARCHAR(40) | NOT NULL | `no_person`/`person_no_phone`/`person_with_phone` |
| has_person | BOOLEAN | NOT NULL | 是否有人 |
| using_phone | BOOLEAN | NOT NULL | 是否使用手机 |
| person_count | INT | NOT NULL, DEFAULT 0 | 人数 |
| phone_count | INT | NOT NULL, DEFAULT 0 | 手机数量 |
| focus_score | NUMERIC(4,2) | NOT NULL, DEFAULT 0 | 专注评分 |
| focused | BOOLEAN | NOT NULL, DEFAULT false | 是否专注 |
| last_reminder_level | VARCHAR(20) | NULL | 提醒等级 |
| last_reminder_text | TEXT | NULL | 最近提醒内容 |
| detections_json | JSONB | NOT NULL, DEFAULT '[]'::jsonb | 最近检测框 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 更新时间 |

> 关键唯一约束：`UNIQUE(room_id, user_id)`

## 2.6 `inference_events`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| event_id | BIGSERIAL | PK | 事件主键 |
| room_id | UUID | NOT NULL, FK -> study_rooms.room_id | 房间 ID |
| user_id | UUID | NOT NULL, FK -> users.user_id | 用户 ID |
| client_ts | TIMESTAMPTZ | NULL | 前端采集时间 |
| server_ts | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 服务端入库时间 |
| status | VARCHAR(40) | NOT NULL | 当前状态 |
| has_person | BOOLEAN | NOT NULL | 是否有人 |
| using_phone | BOOLEAN | NOT NULL | 是否用手机 |
| person_count | INT | NOT NULL, DEFAULT 0 | 人数 |
| phone_count | INT | NOT NULL, DEFAULT 0 | 手机数量 |
| focus_score | NUMERIC(4,2) | NOT NULL, DEFAULT 0 | 专注评分 |
| focused | BOOLEAN | NOT NULL, DEFAULT false | 是否专注 |
| detections_json | JSONB | NOT NULL | 检测详情 |
| reminder_json | JSONB | NULL | 提醒详情 |

## 2.7 `conversations`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| conversation_id | UUID | PK, NOT NULL | 会话主键 |
| type | VARCHAR(20) | NOT NULL, CHECK(type='room') | 会话类型（一期固定 `room`） |
| room_id | UUID | NOT NULL, FK -> study_rooms.room_id | 绑定房间（一房间一会话） |
| created_by | UUID | NOT NULL, FK -> users.user_id | 创建人 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 更新时间 |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 会话是否可用 |

> 关键唯一约束：`UNIQUE(room_id)`（一个房间只绑定一个会话）。

## 2.8 `messages`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| message_id | BIGSERIAL | PK | 消息主键 |
| conversation_id | UUID | NOT NULL, FK -> conversations.conversation_id | 会话 ID |
| sender_user_id | UUID | NULL, FK -> users.user_id | 发送者（系统消息可为空） |
| content_type | VARCHAR(20) | NOT NULL, DEFAULT 'text' | `text`/`system` |
| content | TEXT | NULL | 文本内容 |
| metadata_json | JSONB | NOT NULL, DEFAULT '{}'::jsonb | 扩展元数据（一期不存文件附件） |
| reply_to_message_id | BIGINT | NULL, FK -> messages.message_id | 回复消息 ID |
| is_deleted | BOOLEAN | NOT NULL, DEFAULT false | 软删除标记 |
| edited_at | TIMESTAMPTZ | NULL | 编辑时间 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 发送时间 |

> 关键 CHECK 约束建议：
>
> `CHECK(content_type IN ('text','system'))`
>
> `CHECK((content_type='text' AND sender_user_id IS NOT NULL) OR content_type='system')`

## 2.9 `conversation_read_cursors`

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| cursor_id | BIGSERIAL | PK | 游标主键 |
| conversation_id | UUID | NOT NULL, FK -> conversations.conversation_id | 会话 ID |
| user_id | UUID | NOT NULL, FK -> users.user_id | 用户 ID |
| last_read_message_id | BIGINT | NULL, FK -> messages.message_id | 最后一条已读消息 ID |
| last_read_at | TIMESTAMPTZ | NULL | 最后已读时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 最近更新时间 |

> 关键唯一约束：`UNIQUE(conversation_id, user_id)`（每用户每会话一条已读游标）。

## 3. 索引设计

| 表名 | 索引名 | 索引字段 | 用途 |
|---|---|---|---|
| study_rooms | idx_study_rooms_status_ends_at | (status, ends_at) | 房间状态筛选与到期扫描 |
| study_rooms | idx_study_rooms_invite_code | (invite_code) | 邀请码快速查询（唯一约束已覆盖） |
| room_memberships | idx_room_memberships_room_left_at | (room_id, left_at) | 查询当前在线成员（`left_at IS NULL`） |
| room_memberships | idx_room_memberships_room_user_joined_desc | (room_id, user_id, joined_at DESC) | 查询成员进出历史 |
| webrtc_peers | idx_webrtc_peers_room_state | (room_id, connection_state) | 查询房间连麦状态 |
| user_inference_state | idx_user_inference_state_room_focused | (room_id, focused) | 房间专注统计 |
| inference_events | idx_inference_events_room_user_ts | (room_id, user_id, server_ts DESC) | 用户历史检测回放 |
| conversations | idx_conversations_type_room | (type, room_id) | 房间会话查询（一期 type 固定 room） |
| messages | idx_messages_conv_created_desc | (conversation_id, created_at DESC) | 会话消息分页（倒序） |
| messages | idx_messages_conv_msgid_desc | (conversation_id, message_id DESC) | 会话消息按游标分页 |
| messages | idx_messages_sender_created_desc | (sender_user_id, created_at DESC) | 用户发送历史 |
| conversation_read_cursors | uq_crc_conversation_user | (conversation_id, user_id) UNIQUE | 会话已读游标唯一定位 |
| conversation_read_cursors | idx_crc_user_updated_desc | (user_id, updated_at DESC) | 查询用户会话已读进度 |

## 4. 设计原则

| 原则 | 说明 |
|---|---|
| 最新态与历史分离 | 最新状态查 `user_inference_state`，历史查 `inference_events` |
| 统一主键策略 | 业务实体 UUID，事件表 BIGSERIAL |
| 可扩展 | `detections_json`、`reminder_json` 预留算法升级空间 |
| 高查询字段建索引 | 避免房间和检测查询互相拖慢 |
| 邀请码绑定房间 | 每个房间一个邀请码，邀请码字段直接存于 `study_rooms`，简化关系与查询 |
| 邀请码复用 + 历史留痕 | 邀请码负责入房控制，成员轨迹由 `room_memberships` 历史承载 |
| 聊天一期最小闭环优先 | 一期先落地 `conversations/messages/conversation_read_cursors`，后续再扩展私聊与群聊 |
| 聊天与房间解耦 | 聊天统一走 `conversations/messages`，房间仅通过 `room_id` 关联，不把消息直接塞进房间表；发言权限仍绑定 `room_memberships` 当前成员 |

## 5. 二期扩展预留

## 5.1 `conversation_members`（预留）

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| member_id | UUID | PK, NOT NULL | 会话成员主键 |
| conversation_id | UUID | NOT NULL, FK -> conversations.conversation_id | 会话 ID |
| user_id | UUID | NOT NULL, FK -> users.user_id | 用户 ID |
| role | VARCHAR(20) | NOT NULL, DEFAULT 'member' | `owner`/`admin`/`member` |
| joined_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 本次加入时间 |
| left_at | TIMESTAMPTZ | NULL | 本次离开时间 |
| mute_until | TIMESTAMPTZ | NULL | 禁言到期时间（可选） |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 创建时间 |

> 启用条件：需要私聊/群聊权限模型时启用。
>
> 关键唯一约束：`UNIQUE(conversation_id, user_id, joined_at)`

## 5.2 `message_receipts`（预留）

| 字段名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| receipt_id | BIGSERIAL | PK | 回执主键 |
| message_id | BIGINT | NOT NULL, FK -> messages.message_id | 消息 ID |
| user_id | UUID | NOT NULL, FK -> users.user_id | 用户 ID |
| delivered_at | TIMESTAMPTZ | NULL | 送达时间 |
| read_at | TIMESTAMPTZ | NULL | 已读时间 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 创建时间 |

> 启用条件：需要逐消息已读统计时启用。
>
> 关键唯一约束：`UNIQUE(message_id, user_id)`（每用户每消息一条回执）。
