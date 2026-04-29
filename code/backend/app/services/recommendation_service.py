import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException


DEFAULT_RECOMMEND_LIMIT = int(os.getenv("ROOM_RECOMMEND_LIMIT", "6"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_db_driver():
    try:
        import psycopg  # type: ignore

        return psycopg
    except Exception:
        pass
    try:
        import psycopg2  # type: ignore

        return psycopg2
    except Exception:
        return None


def _get_conn():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise HTTPException(status_code=500, detail="database_url_missing")
    driver = _load_db_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="db_driver_missing_install_psycopg")
    return driver.connect(database_url)


def _period_from_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 24:
        return "evening"
    return "late_night"


def _period_name(period: Optional[str]) -> str:
    return {
        "morning": "上午",
        "afternoon": "下午",
        "evening": "晚上",
        "late_night": "深夜",
    }.get(period or "", "暂无偏好")


def _intensity_level(avg_session_minutes: float, total_minutes_30d: int, study_days_30d: int) -> str:
    if avg_session_minutes >= 90 or total_minutes_30d >= 1800 or study_days_30d >= 18:
        return "high"
    if avg_session_minutes > 0 and avg_session_minutes <= 45:
        return "relaxed"
    if total_minutes_30d == 0:
        return "new"
    return "normal"


def _build_user_profile(rows: List) -> Dict:
    now = _now()
    if not rows:
        return {
            "avg_session_minutes": 0.0,
            "preferred_duration_minutes": 60.0,
            "preferred_period": None,
            "preferred_period_name": "暂无偏好",
            "study_days_30d": 0,
            "total_minutes_30d": 0,
            "intensity_level": "new",
        }

    session_minutes: List[float] = []
    room_durations: List[int] = []
    period_counts: Dict[str, int] = {}
    daily_minutes: Dict[str, float] = {}
    cutoff = now.timestamp() - 30 * 24 * 3600

    for joined_at, left_at, duration_minutes in rows:
        if joined_at is None:
            continue
        end_at = left_at or now
        minutes = max((end_at - joined_at).total_seconds() / 60.0, 0.0)
        if minutes <= 0:
            continue
        session_minutes.append(minutes)
        if duration_minutes:
            room_durations.append(int(duration_minutes))

        period = _period_from_hour(joined_at.hour)
        period_counts[period] = period_counts.get(period, 0) + 1

        if joined_at.timestamp() >= cutoff:
            day_key = joined_at.date().isoformat()
            daily_minutes[day_key] = daily_minutes.get(day_key, 0.0) + minutes

    avg_session = sum(session_minutes) / len(session_minutes) if session_minutes else 0.0
    preferred_duration = sum(room_durations) / len(room_durations) if room_durations else max(avg_session, 60.0)
    preferred_period = max(period_counts.items(), key=lambda item: item[1])[0] if period_counts else None
    total_30d = int(sum(daily_minutes.values()))
    study_days_30d = len([minutes for minutes in daily_minutes.values() if minutes > 0])

    return {
        "avg_session_minutes": round(avg_session, 2),
        "preferred_duration_minutes": round(preferred_duration, 2),
        "preferred_period": preferred_period,
        "preferred_period_name": _period_name(preferred_period),
        "study_days_30d": study_days_30d,
        "total_minutes_30d": total_30d,
        "intensity_level": _intensity_level(avg_session, total_30d, study_days_30d),
    }


def _room_tags(duration_minutes: int, member_count: int, member_avg_session_minutes: float) -> List[Dict]:
    tags: List[Dict] = []

    def add(code: str, name: str, score: float) -> None:
        tags.append({"code": code, "name": name, "score": round(score, 2)})

    if duration_minutes >= 120:
        add("long_session", "长时段", 1.0)
    if duration_minutes >= 90 or member_avg_session_minutes >= 90:
        add("high_intensity", "高强度", 0.95)
    if duration_minutes <= 45:
        add("short_sprint", "短时冲刺", 1.0)
    if duration_minutes <= 60 and member_avg_session_minutes < 75:
        add("relaxed", "轻松型", 0.9)
    if 2 <= member_count <= 4:
        add("small_group", "小组自习", 0.82)
    if member_avg_session_minutes >= 75:
        add("stable_focus", "稳定专注", 0.78)
    if not tags:
        add("balanced", "均衡型", 0.7)

    return tags


def _duration_match(preferred: float, duration: int) -> float:
    if preferred <= 0:
        return 0.65
    gap = abs(preferred - duration)
    return max(0.0, 1.0 - min(gap / max(preferred, duration, 1), 1.0))


def _intensity_match(level: str, tag_codes: set[str]) -> float:
    if level == "high":
        return 1.0 if {"high_intensity", "long_session"} & tag_codes else 0.45
    if level == "relaxed":
        return 1.0 if {"relaxed", "short_sprint"} & tag_codes else 0.5
    if level == "new":
        return 0.9 if {"relaxed", "balanced", "small_group"} & tag_codes else 0.65
    if {"balanced", "small_group", "stable_focus"} & tag_codes:
        return 0.85
    return 0.65


def _member_fit(member_count: int, max_members: int) -> float:
    if member_count <= 0:
        return 0.55
    if 2 <= member_count <= 4:
        return 1.0
    if member_count < max_members:
        return 0.72
    return 0.2


def _remaining_fit(now: datetime, ends_at: datetime, duration_minutes: int) -> float:
    remaining = max((ends_at - now).total_seconds() / 60.0, 0.0)
    if remaining <= 0:
        return 0.0
    if duration_minutes <= 0:
        return 0.6
    ratio = min(remaining / duration_minutes, 1.0)
    return max(0.35, ratio)


def _recommendation_reasons(profile: Dict, room: Dict, tag_names: List[str]) -> List[str]:
    reasons: List[str] = []
    level = profile["intensity_level"]
    duration = room["duration_minutes"]

    if level == "high" and ("高强度" in tag_names or "长时段" in tag_names):
        reasons.append("你的历史学习时长较长，这个房间节奏更匹配")
    elif level == "relaxed" and ("轻松型" in tag_names or "短时冲刺" in tag_names):
        reasons.append("你的单次学习时长偏短，这个房间更适合轻量开始")
    elif level == "new":
        reasons.append("你还没有足够历史记录，优先推荐容易加入的活跃房间")

    preferred = float(profile["preferred_duration_minutes"])
    if preferred > 0 and abs(preferred - duration) <= 30:
        reasons.append(f"房间时长 {duration} 分钟与你常见学习时长接近")
    else:
        reasons.append(f"房间计划学习 {duration} 分钟")

    member_count = int(room["member_count"])
    if 2 <= member_count <= 4:
        reasons.append("当前人数适合小组自习")
    elif member_count == 1:
        reasons.append("当前房间较安静，适合先进入状态")

    return reasons[:3]


def _score_room(profile: Dict, room: Dict, tag_codes: set[str], now: datetime) -> float:
    duration_score = _duration_match(float(profile["preferred_duration_minutes"]), int(room["duration_minutes"]))
    intensity_score = _intensity_match(str(profile["intensity_level"]), tag_codes)
    member_score = _member_fit(int(room["member_count"]), int(room["max_members"]))
    remaining_score = _remaining_fit(now, room["ends_at"], int(room["duration_minutes"]))

    score = (
        0.4 * duration_score
        + 0.3 * intensity_score
        + 0.18 * member_score
        + 0.12 * remaining_score
    )
    return round(min(max(score, 0.0), 1.0), 4)


def get_room_recommendations(user_id: str, limit: int = DEFAULT_RECOMMEND_LIMIT) -> Dict:
    user_id = user_id.strip()
    limit = min(max(int(limit or DEFAULT_RECOMMEND_LIMIT), 1), 20)
    now = _now()

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE user_id::text = %s LIMIT 1", (user_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="user_not_found")

        cur.execute(
            """
            SELECT rm.joined_at, rm.left_at, sr.duration_minutes
            FROM room_memberships rm
            JOIN study_rooms sr ON sr.room_id = rm.room_id
            WHERE rm.user_id::text = %s
            ORDER BY rm.joined_at DESC
            LIMIT 100
            """,
            (user_id,),
        )
        profile = _build_user_profile(cur.fetchall())

        cur.execute(
            """
            WITH active_members AS (
                SELECT room_id, user_id
                FROM room_memberships
                WHERE left_at IS NULL
            ),
            user_history AS (
                SELECT
                    user_id,
                    AVG(GREATEST(EXTRACT(EPOCH FROM (COALESCE(left_at, %s) - joined_at)), 0) / 60.0)
                        AS avg_session_minutes
                FROM room_memberships
                GROUP BY user_id
            )
            SELECT
                sr.room_id::text,
                sr.room_name,
                sr.host_user_id::text,
                sr.duration_minutes,
                sr.started_at,
                sr.ends_at,
                sr.invite_code,
                sr.max_members,
                COUNT(am.user_id)::int AS member_count,
                COALESCE(AVG(uh.avg_session_minutes), 0)::float AS member_avg_session_minutes
            FROM study_rooms sr
            LEFT JOIN active_members am ON am.room_id = sr.room_id
            LEFT JOIN user_history uh ON uh.user_id = am.user_id
            WHERE sr.status = 'active'
              AND sr.ends_at > %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM room_memberships mine
                  WHERE mine.room_id = sr.room_id
                    AND mine.user_id::text = %s
                    AND mine.left_at IS NULL
              )
            GROUP BY sr.room_id
            HAVING COUNT(am.user_id) < sr.max_members
            ORDER BY sr.created_at DESC
            LIMIT 50
            """,
            (now, now, user_id),
        )

        rooms = []
        for row in cur.fetchall():
            room = {
                "room_id": row[0],
                "room_name": row[1],
                "host_user_id": row[2],
                "duration_minutes": int(row[3]),
                "started_at": row[4],
                "ends_at": row[5],
                "invite_code": row[6],
                "max_members": int(row[7]),
                "member_count": int(row[8]),
                "member_avg_session_minutes": round(float(row[9] or 0), 2),
            }
            tags = _room_tags(
                duration_minutes=room["duration_minutes"],
                member_count=room["member_count"],
                member_avg_session_minutes=room["member_avg_session_minutes"],
            )
            tag_codes = {item["code"] for item in tags}
            tag_names = [item["name"] for item in tags]
            score = _score_room(profile, room, tag_codes, now)
            rooms.append(
                {
                    "room_id": room["room_id"],
                    "room_name": room["room_name"],
                    "host_user_id": room["host_user_id"],
                    "duration_minutes": room["duration_minutes"],
                    "started_at": room["started_at"].isoformat() if room["started_at"] else None,
                    "ends_at": room["ends_at"].isoformat() if room["ends_at"] else None,
                    "invite_code": room["invite_code"],
                    "member_count": room["member_count"],
                    "max_members": room["max_members"],
                    "member_avg_session_minutes": room["member_avg_session_minutes"],
                    "match_score": score,
                    "tags": tags,
                    "reasons": _recommendation_reasons(profile, room, tag_names),
                }
            )

        rooms.sort(key=lambda item: item["match_score"], reverse=True)
        conn.commit()
        return {
            "user_profile": profile,
            "rooms": rooms[:limit],
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_recommendation_failed")
    finally:
        conn.close()
