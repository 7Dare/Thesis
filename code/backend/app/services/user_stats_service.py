from datetime import date, datetime, time, timedelta, timezone
import os
from typing import Dict, List, Tuple

from fastapi import HTTPException


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


def _user_exists(cur, user_id: str) -> bool:
    cur.execute("SELECT 1 FROM users WHERE user_id::text = %s LIMIT 1", (user_id,))
    return cur.fetchone() is not None


def _seconds_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if end <= start:
        return 0
    return int((end - start).total_seconds())


def _level(seconds: int) -> int:
    minutes = seconds // 60
    if minutes <= 0:
        return 0
    if minutes < 30:
        return 1
    if minutes < 60:
        return 2
    if minutes < 120:
        return 3
    return 4


def _max_streak(days_with_study: List[date]) -> int:
    if not days_with_study:
        return 0
    sorted_days = sorted(set(days_with_study))
    best = 1
    cur = 1
    for i in range(1, len(sorted_days)):
        if sorted_days[i] == sorted_days[i - 1] + timedelta(days=1):
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 1
    return best


def get_user_study_calendar(user_id: str, days: int = 365) -> Dict:
    user_id = user_id.strip()
    if days < 30 or days > 730:
        raise HTTPException(status_code=400, detail="invalid_days_range")

    now = _now()
    today = now.date()
    start_day = today - timedelta(days=days - 1)
    day_start_dt = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
    day_after_end_dt = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)

    conn = _get_conn()
    try:
        cur = conn.cursor()
        if not _user_exists(cur, user_id):
            raise HTTPException(status_code=404, detail="user_not_found")

        cur.execute(
            """
            SELECT joined_at, left_at
            FROM room_memberships
            WHERE user_id::text = %s
            ORDER BY joined_at ASC
            """,
            (user_id,),
        )
        rows: List[Tuple[datetime, datetime]] = [
            (r[0], r[1] if r[1] is not None else now)
            for r in cur.fetchall()
            if r[0] is not None
        ]

        daily_seconds: Dict[date, int] = {}
        for i in range(days):
            d = start_day + timedelta(days=i)
            daily_seconds[d] = 0

        all_days_with_study: List[date] = []
        total_seconds_all_time = 0
        for joined_at, left_at in rows:
            if left_at < joined_at:
                continue
            total_seconds_all_time += int((left_at - joined_at).total_seconds())

            cur_day = joined_at.date()
            end_day = left_at.date()
            while cur_day <= end_day:
                seg_start = datetime.combine(cur_day, time.min, tzinfo=timezone.utc)
                seg_end = seg_start + timedelta(days=1)
                overlap = _seconds_overlap(joined_at, left_at, seg_start, seg_end)
                if overlap > 0:
                    all_days_with_study.append(cur_day)
                if cur_day in daily_seconds:
                    daily_seconds[cur_day] += overlap
                cur_day += timedelta(days=1)

        heatmap = []
        for i in range(days):
            d = start_day + timedelta(days=i)
            sec = int(daily_seconds.get(d, 0))
            heatmap.append(
                {
                    "date": d.isoformat(),
                    "seconds": sec,
                    "minutes": sec // 60,
                    "level": _level(sec),
                }
            )

        total_seconds_365d = sum(item["seconds"] for item in heatmap)
        last_30 = heatmap[-30:]
        total_seconds_30d = sum(item["seconds"] for item in last_30)

        days_with_study_365 = [date.fromisoformat(item["date"]) for item in heatmap if item["seconds"] > 0]
        days_with_study_30 = [date.fromisoformat(item["date"]) for item in last_30 if item["seconds"] > 0]

        conn.commit()
        return {
            "user_id": user_id,
            "range": {
                "start_date": start_day.isoformat(),
                "end_date": today.isoformat(),
                "days": days,
            },
            "summary": {
                "total_seconds_all_time": int(max(total_seconds_all_time, 0)),
                "total_seconds_365d": int(total_seconds_365d),
                "total_seconds_30d": int(total_seconds_30d),
                "streak_max_all_time_days": _max_streak(all_days_with_study),
                "streak_max_365d_days": _max_streak(days_with_study_365),
                "streak_max_30d_days": _max_streak(days_with_study_30),
            },
            "heatmap": heatmap,
            "levels": {
                "0": "0分钟",
                "1": "1-29分钟",
                "2": "30-59分钟",
                "3": "60-119分钟",
                "4": "120分钟以上",
            },
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="user_stats_failed")
    finally:
        conn.close()

