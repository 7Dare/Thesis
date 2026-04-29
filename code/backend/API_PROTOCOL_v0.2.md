# 接口协议文档 v0.2（多用户状态版）

目标：支持房间化学习场景，包含认证、邀请码入房、YOLO 检测、WebRTC 音视频信令。

## 1. 基础约定
- Base URL：`http://<WSL_HOST>:8000`
- 时间字段：`ISO 8601` 字符串（UTC，如 `2026-02-15T12:00:00+00:00`）
- JSON 成功响应：`{ "code": 0, "message": "ok", "data": {...} }`
- JSON 失败响应：`{ "code": "<error_code>", "message": "<中文错误信息>", "data": null }`
- HTTP 状态码保留语义（400/401/403/404/409/500）
- 特例：`GET /snapshot` 成功返回 `image/jpeg`，失败返回上述 JSON 错误体

## 2. 健康检查

### `GET /health`
返回服务状态和 WebRTC ICE 配置。

## 3. 认证接口

### `POST /auth/register`
`Content-Type: application/x-www-form-urlencoded`

字段：
1. `login_user_id`（必填）
2. `password`（必填）
3. `display_name`（必填）
4. `email`（可空）

### `POST /auth/login`
`Content-Type: application/x-www-form-urlencoded`

字段：
1. `login_user_id`（必填）
2. `password`（必填）

## 4. 邀请码房间管理

### `POST /rooms` 创建房间并生成邀请码
请求（JSON）：

```json
{
  "host_user_id": "uuid",
  "room_name": "高数自习室",
  "duration_minutes": 120
}
```

成功 `data`：

```json
{
  "room_id": "uuid",
  "room_name": "高数自习室",
  "host_user_id": "uuid",
  "status": "active",
  "created_at": "2026-02-15T12:00:00+00:00",
  "ends_at": "2026-02-15T14:00:00+00:00",
  "invite_code": "123456789012"
}
```

说明：
1. 邀请码为 12 位数字，可重复使用（房间 `active` 时有效）。
2. 同一用户同一时间只能拥有一个进行中的房间。

### `POST /rooms/join-by-invite` 通过邀请码加入
请求（JSON）：

```json
{
  "user_id": "uuid",
  "invite_code": "123456789012",
  "display_name": "同学B"
}
```

成功 `data`：

```json
{
  "room_id": "uuid",
  "user_id": "uuid",
  "role": "member",
  "joined_at": "2026-02-15T12:01:00+00:00"
}
```

### `POST /rooms/{room_id}/leave` 成员离开
请求（JSON）：

```json
{
  "user_id": "uuid"
}
```

说明：最后一人离开时房间自动关闭。

成功 `data`（普通离开）：

```json
{
  "room_id": "uuid",
  "status": "active",
  "member_count": 2
}
```

成功 `data`（最后一人离开）：

```json
{
  "room_id": "uuid",
  "status": "closed",
  "reason": "last_member_left"
}
```

### `POST /rooms/{room_id}/close` 房主手动关闭
请求（JSON）：

```json
{
  "host_user_id": "uuid"
}
```

说明：关闭后房间不可再加入，相关活跃邀请码失效。

成功 `data`：

```json
{
  "room_id": "uuid",
  "status": "closed",
  "closed_at": "2026-02-15T12:05:00+00:00"
}
```

### `GET /rooms/{room_id}` 查询房间信息
返回房间状态、成员数、成员列表。

成功 `data`：

```json
{
  "room_id": "uuid",
  "room_name": "高数自习室",
  "host_user_id": "uuid",
  "status": "active",
  "created_at": "2026-02-15T12:00:00+00:00",
  "started_at": "2026-02-15T12:00:00+00:00",
  "ends_at": "2026-02-15T14:00:00+00:00",
  "invite_code": "123456789012",
  "member_count": 3,
  "members": [
    {
      "user_id": "uuid",
      "role": "host",
      "joined_at": "2026-02-15T12:00:00+00:00"
    }
  ]
}
```

### `GET /rooms/{room_id}/study-time` 查询房间学习时长统计
Query：
1. `user_id`：必填（用于成员权限校验）

成功 `data`：

```json
{
  "room_id": "uuid",
  "room_status": "active",
  "room_total_seconds": 3600,
  "room_elapsed_seconds": 1800,
  "my_total_seconds": 1200,
  "members": [
    {
      "user_id": "uuid",
      "display_name": "同学A",
      "total_seconds": 2400,
      "current_session_seconds": 1200
    }
  ]
}
```

说明：
1. `room_total_seconds`：房间内所有成员累计学习时长总和（秒）。
2. `room_elapsed_seconds`：房间从 `started_at` 到当前（或关闭时刻）的经过时长（秒）。
3. `my_total_seconds`：当前查询用户在该房间累计学习时长（秒）。
4. `members`：按累计时长降序返回成员统计。

### `GET /rooms/recommendations` 推荐自习室

Query：
1. `user_id`：必填
2. `limit`：可选，默认 `6`，范围 `1-20`

说明：
1. 根据用户历史学习时长、偏好房间时长、近 30 天学习稳定性，为用户推荐可加入的活跃自习室。
2. 已加入的房间不会出现在推荐列表中。
3. 一期采用可解释规则推荐，推荐结果包含标签与推荐理由。

成功 `data`：

```json
{
  "user_profile": {
    "avg_session_minutes": 85.5,
    "preferred_duration_minutes": 100.0,
    "preferred_period": "evening",
    "preferred_period_name": "晚上",
    "study_days_30d": 12,
    "total_minutes_30d": 1260,
    "intensity_level": "high"
  },
  "rooms": [
    {
      "room_id": "uuid",
      "room_name": "考研晚间自习室",
      "host_user_id": "uuid",
      "duration_minutes": 120,
      "started_at": "2026-02-15T12:00:00+00:00",
      "ends_at": "2026-02-15T14:00:00+00:00",
      "invite_code": "123456789012",
      "member_count": 3,
      "max_members": 6,
      "member_avg_session_minutes": 92.4,
      "match_score": 0.86,
      "tags": [
        {
          "code": "high_intensity",
          "name": "高强度",
          "score": 0.95
        }
      ],
      "reasons": [
        "你的历史学习时长较长，这个房间节奏更匹配",
        "房间计划学习 120 分钟",
        "当前人数适合小组自习"
      ]
    }
  ]
}
```

## 5. WebRTC 音视频连麦信令

### `WS /rooms/{room_id}/signal?user_id=<uid>&display_name=<name>`

客户端 -> 服务端消息：

```json
{
  "type": "offer|answer|ice|peer_ping",
  "target_user_id": "u002",
  "payload": {}
}
```

服务端 -> 客户端消息：

```json
{
  "type": "offer|answer|ice|peer_join|peer_leave|peer_ping|signal_error|room_closed",
  "room_id": "r001",
  "from_user_id": "u001",
  "payload": {},
  "ts": 1739512345.12
}
```

权限规则：
1. `room_id` 不存在或已关闭：WS 关闭 `4404`，reason=`room_not_found_or_closed`
2. `user_id` 非该房间成员：WS 关闭 `4403`，reason=`not_room_member`

## 6. 聊天接口（一期）

### `GET /rooms/{room_id}/chat/conversation`
查询（或初始化）房间聊天会话。

Query：
1. `user_id`：必填

成功 `data`：

```json
{
  "conversation_id": "uuid",
  "type": "room",
  "room_id": "uuid",
  "is_active": true,
  "created_at": "2026-02-15T12:00:00+00:00",
  "updated_at": "2026-02-15T12:00:00+00:00"
}
```

### `POST /rooms/{room_id}/chat/messages`
发送文本消息。

请求（JSON）：

```json
{
  "user_id": "uuid",
  "content": "大家好，开始学习吧"
}
```

成功 `data`：

```json
{
  "message_id": 101,
  "conversation_id": "uuid",
  "sender_user_id": "uuid",
  "content_type": "text",
  "content": "大家好，开始学习吧",
  "is_deleted": false,
  "edited_at": null,
  "created_at": "2026-02-15T12:10:00+00:00"
}
```

### `GET /rooms/{room_id}/chat/messages`
分页拉取消息（默认 20 条，最大 100 条）。

Query：
1. `user_id`：必填
2. `limit`：可选，默认 `20`
3. `before_message_id`：可选（用于向前翻页）

成功 `data`：

```json
{
  "conversation_id": "uuid",
  "messages": [
    {
      "message_id": 100,
      "conversation_id": "uuid",
      "sender_user_id": "uuid",
      "content_type": "text",
      "content": "上一条消息",
      "is_deleted": false,
      "edited_at": null,
      "created_at": "2026-02-15T12:09:00+00:00"
    }
  ],
  "next_before_message_id": 100
}
```

### `POST /rooms/{room_id}/chat/read-cursor`
更新会话级已读游标。

请求（JSON）：

```json
{
  "user_id": "uuid",
  "last_read_message_id": 101
}
```

成功 `data`：

```json
{
  "conversation_id": "uuid",
  "user_id": "uuid",
  "last_read_message_id": 101,
  "last_read_at": "2026-02-15T12:11:00+00:00",
  "updated_at": "2026-02-15T12:11:00+00:00"
}
```

权限规则：
1. 仅当前房间成员可访问聊天接口（`room_memberships.left_at IS NULL`）。
2. 房间非 `active` 状态或已到期时，聊天写入会被拒绝。

## 7. 推理上传与专注度平滑

### `POST /ingest/frame`
`Content-Type: multipart/form-data`

字段：
1. `frame`：必填，图片二进制（jpg/png）
2. `room_id`：必填
3. `user_id`：必填

### `GET /status`
返回最新检测状态（JSON 包裹结构）。

### `GET /snapshot`
- 成功：`image/jpeg`
- 失败：JSON 错误体（如 `snapshot_not_found`）

推理策略：
1. 后端先使用检测模型识别画面中的人像区域，再将最大人像框裁剪后送入专注度模型。
2. 专注度模型输出单帧走神判断，但业务层不直接根据单帧触发干预。
3. 系统维护 `T=3秒` 的时间窗口；只有窗口内走神判定率超过 `70%` 时，才返回 `intervention_required=true`。
4. 该策略用于降低低头笔记、短暂闭眼等正常学习动作造成的误判。

推理响应新增字段：

```json
{
  "focus_label": "focused|suspected_distracted|distracted|no_person|unavailable",
  "focus_score": 0.82,
  "focus_enabled": true,
  "distracted": false,
  "distraction_rate": 0.33,
  "intervention_required": false,
  "focus_window_seconds": 3.0,
  "focus_window_frames": 4,
  "focus_detail": {
    "boredom_prob": 0.12,
    "engagement_prob": 0.88,
    "confusion_prob": 0.08,
    "frustration_prob": 0.05,
    "distraction_score": 0.12
  }
}
```

## 8. 个人学习统计

### `GET /users/{user_id}/study-calendar`
Query：
1. `days`：可选，默认 `365`，范围 `30~730`

成功 `data`：

```json
{
  "user_id": "uuid",
  "range": {
    "start_date": "2025-03-09",
    "end_date": "2026-03-08",
    "days": 365
  },
  "summary": {
    "total_seconds_all_time": 123456,
    "total_seconds_365d": 67890,
    "total_seconds_30d": 5432,
    "streak_max_all_time_days": 12,
    "streak_max_365d_days": 7,
    "streak_max_30d_days": 4
  },
  "heatmap": [
    { "date": "2026-03-08", "seconds": 3600, "minutes": 60, "level": 3 }
  ],
  "levels": {
    "0": "0分钟",
    "1": "1-29分钟",
    "2": "30-59分钟",
    "3": "60-119分钟",
    "4": "120分钟以上"
  }
}
```

## 9. 房间与聊天接口常见错误码
1. `invalid_invite_code_format`
2. `invite_not_found`
3. `invite_not_active`
4. `room_not_found`
5. `room_not_active`
6. `room_closed`
7. `not_room_member`
8. `not_room_host`
9. `room_member_conflict`
10. `room_member_limit_reached`
11. `user_not_found`
12. `host_active_room_exists`
13. `message_content_empty`
14. `message_too_long`
15. `invalid_message_query`
16. `invalid_read_cursor_payload`
17. `chat_message_not_found`
18. `invalid_days_range`
19. `user_stats_failed`
18. `room_resume_check_failed`
19. `room_study_time_failed`
