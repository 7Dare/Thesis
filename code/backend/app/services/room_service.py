import os
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import HTTPException


MAX_ROOM_MEMBERS = int(os.getenv("MESH_ROOM_LIMIT", "6"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _load_db_driver():
    try:
        import psycopg  # type: ignore

        return ("psycopg", psycopg)
    except Exception:
        pass
    try:
        import psycopg2  # type: ignore

        return ("psycopg2", psycopg2)
    except Exception:
        return (None, None)


def _get_conn():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise HTTPException(status_code=500, detail="database_url_missing")
    _, driver = _load_db_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="db_driver_missing_install_psycopg")
    return driver.connect(database_url)


def _user_exists(cur, user_id: str) -> bool:
    cur.execute("SELECT 1 FROM users WHERE user_id::text = %s LIMIT 1", (user_id,))
    return cur.fetchone() is not None


def _new_invite_code(cur) -> str:
    for _ in range(20):
        code = "".join(str(random.randint(0, 9)) for _ in range(12))
        cur.execute("SELECT 1 FROM study_rooms WHERE invite_code = %s LIMIT 1", (code,))
        if cur.fetchone() is None:
            return code
    raise HTTPException(status_code=500, detail="invite_code_generation_failed")


def _close_room(cur, room_id: str, now: datetime) -> None:
    cur.execute(
        """
        UPDATE study_rooms
        SET status = 'closed', closed_at = %s
        WHERE room_id::text = %s AND status = 'active'
        """,
        (now, room_id),
    )


def _close_if_expired(cur, room_id: str, ends_at: datetime, now: datetime) -> bool:
    if now < ends_at:
        return False
    _close_room(cur, room_id, now)
    return True


def create_room(host_user_id: str, room_name: str, duration_minutes: int) -> Dict:
    host_user_id = host_user_id.strip()
    room_name = room_name.strip() or "自习室"
    if duration_minutes <= 0:
        raise HTTPException(status_code=400, detail="invalid_duration_minutes")

    now = _now()
    ends_at = now + timedelta(minutes=duration_minutes)

    conn = _get_conn()
    try:
        cur = conn.cursor()
        if not _user_exists(cur, host_user_id):
            raise HTTPException(status_code=404, detail="user_not_found")

        # One user can only own one active (non-expired) room at the same time.
        cur.execute(
            """
            SELECT room_id::text, ends_at
            FROM study_rooms
            WHERE host_user_id::text = %s AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            FOR UPDATE
            """,
            (host_user_id,),
        )
        active_room = cur.fetchone()
        if active_room:
            active_room_id, active_room_ends_at = active_room
            if _now() < active_room_ends_at:
                raise HTTPException(status_code=409, detail="host_active_room_exists")
            _close_room(cur, active_room_id, now)

        invite_code = _new_invite_code(cur)

        cur.execute(
            """
            INSERT INTO study_rooms (
                room_name,
                host_user_id,
                duration_minutes,
                started_at,
                ends_at,
                status,
                invite_code,
                max_members
            )
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s)
            RETURNING room_id::text, room_name, host_user_id::text, status, created_at, ends_at, invite_code
            """,
            (
                room_name,
                host_user_id,
                duration_minutes,
                now,
                ends_at,
                invite_code,
                MAX_ROOM_MEMBERS,
            ),
        )
        row = cur.fetchone()

        cur.execute(
            """
            INSERT INTO room_memberships (room_id, user_id, role, joined_at)
            VALUES (%s, %s, 'host', %s)
            """,
            (row[0], host_user_id, now),
        )

        conn.commit()
        return {
            "room_id": row[0],
            "room_name": row[1],
            "host_user_id": row[2],
            "status": row[3],
            "created_at": _to_iso(row[4]),
            "ends_at": _to_iso(row[5]),
            "invite_code": row[6],
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_create_failed")
    finally:
        conn.close()


def join_by_invite(user_id: str, invite_code: str, display_name: str) -> Dict:
    user_id = user_id.strip()
    invite_code = invite_code.strip()
    _ = display_name.strip() or "member"

    if not invite_code.isdigit() or len(invite_code) != 12:
        raise HTTPException(status_code=400, detail="invalid_invite_code_format")

    now = _now()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        if not _user_exists(cur, user_id):
            raise HTTPException(status_code=404, detail="user_not_found")

        cur.execute(
            """
            SELECT room_id::text, status, ends_at, max_members
            FROM study_rooms
            WHERE invite_code = %s
            FOR UPDATE
            """,
            (invite_code,),
        )
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="invite_not_found")

        room_id, room_status, ends_at, max_members = room
        if room_status != "active":
            raise HTTPException(status_code=409, detail="invite_not_active")

        if _close_if_expired(cur, room_id, ends_at, now):
            raise HTTPException(status_code=409, detail="room_not_active")

        cur.execute(
            """
            SELECT 1
            FROM room_memberships
            WHERE room_id::text = %s AND user_id::text = %s AND left_at IS NULL
            LIMIT 1
            """,
            (room_id, user_id),
        )
        if cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail="room_member_conflict")

        cur.execute(
            """
            SELECT COUNT(*)
            FROM room_memberships
            WHERE room_id::text = %s AND left_at IS NULL
            """,
            (room_id,),
        )
        active_count = int(cur.fetchone()[0])
        if active_count >= int(max_members):
            raise HTTPException(status_code=409, detail="room_member_limit_reached")

        cur.execute(
            """
            INSERT INTO room_memberships (room_id, user_id, role, joined_at)
            VALUES (%s, %s, 'member', %s)
            """,
            (room_id, user_id, now),
        )

        conn.commit()
        return {
            "room_id": room_id,
            "user_id": user_id,
            "role": "member",
            "joined_at": _to_iso(now),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_join_failed")
    finally:
        conn.close()


def leave_room(room_id: str, user_id: str) -> Dict:
    user_id = user_id.strip()
    now = _now()

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id::text, host_user_id::text, status, ends_at
            FROM study_rooms
            WHERE room_id::text = %s
            FOR UPDATE
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")

        room_id_val, host_user_id, room_status, ends_at = room
        if room_status != "active":
            raise HTTPException(status_code=409, detail="room_not_active")

        if _close_if_expired(cur, room_id_val, ends_at, now):
            raise HTTPException(status_code=409, detail="room_not_active")

        cur.execute(
            """
            SELECT membership_id::text
            FROM room_memberships
            WHERE room_id::text = %s AND user_id::text = %s AND left_at IS NULL
            ORDER BY joined_at DESC
            LIMIT 1
            FOR UPDATE
            """,
            (room_id_val, user_id),
        )
        active_membership = cur.fetchone()
        if not active_membership:
            raise HTTPException(status_code=403, detail="not_room_member")

        cur.execute(
            """
            UPDATE room_memberships
            SET left_at = %s, leave_reason = 'left'
            WHERE membership_id::text = %s
            """,
            (now, active_membership[0]),
        )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM room_memberships
            WHERE room_id::text = %s AND left_at IS NULL
            """,
            (room_id_val,),
        )
        active_count = int(cur.fetchone()[0])

        if active_count == 0:
            _close_room(cur, room_id_val, now)
            conn.commit()
            return {
                "room_id": room_id_val,
                "status": "closed",
                "reason": "last_member_left",
            }

        if user_id == host_user_id:
            cur.execute(
                """
                SELECT membership_id::text, user_id::text
                FROM room_memberships
                WHERE room_id::text = %s AND left_at IS NULL
                ORDER BY joined_at ASC
                LIMIT 1
                """,
                (room_id_val,),
            )
            new_host = cur.fetchone()
            if new_host:
                cur.execute(
                    """
                    UPDATE room_memberships
                    SET role = 'host'
                    WHERE membership_id::text = %s
                    """,
                    (new_host[0],),
                )
                cur.execute(
                    """
                    UPDATE study_rooms
                    SET host_user_id = %s
                    WHERE room_id::text = %s
                    """,
                    (new_host[1], room_id_val),
                )

        conn.commit()
        return {
            "room_id": room_id_val,
            "status": "active",
            "member_count": active_count,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_leave_failed")
    finally:
        conn.close()


def close_room(room_id: str, host_user_id: str) -> Dict:
    host_user_id = host_user_id.strip()
    now = _now()

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id::text, host_user_id::text, status
            FROM study_rooms
            WHERE room_id::text = %s
            FOR UPDATE
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")

        room_id_val, room_host_user_id, room_status = room
        if room_host_user_id != host_user_id:
            raise HTTPException(status_code=403, detail="not_room_host")
        if room_status != "active":
            raise HTTPException(status_code=409, detail="room_closed")

        _close_room(cur, room_id_val, now)
        cur.execute(
            """
            UPDATE room_memberships
            SET left_at = %s, leave_reason = 'room_closed'
            WHERE room_id::text = %s AND left_at IS NULL
            """,
            (now, room_id_val),
        )

        conn.commit()
        return {
            "room_id": room_id_val,
            "status": "closed",
            "closed_at": _to_iso(now),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_close_failed")
    finally:
        conn.close()


def get_room(room_id: str) -> Dict:
    now = _now()

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id::text, room_name, host_user_id::text, status, created_at, started_at, ends_at, invite_code
            FROM study_rooms
            WHERE room_id::text = %s
            FOR UPDATE
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")

        room_id_val, room_name, host_user_id, status, created_at, started_at, ends_at, invite_code = room
        if status == "active" and _close_if_expired(cur, room_id_val, ends_at, now):
            status = "closed"

        cur.execute(
            """
            SELECT rm.user_id::text, u.display_name, rm.role, rm.joined_at
            FROM room_memberships rm
            JOIN users u ON u.user_id = rm.user_id
            WHERE rm.room_id::text = %s AND rm.left_at IS NULL
            ORDER BY rm.joined_at ASC
            """,
            (room_id_val,),
        )
        members = [
            {
                "user_id": row[0],
                "display_name": row[1],
                "role": row[2],
                "joined_at": _to_iso(row[3]),
            }
            for row in cur.fetchall()
        ]

        conn.commit()
        return {
            "room_id": room_id_val,
            "room_name": room_name,
            "host_user_id": host_user_id,
            "status": status,
            "created_at": _to_iso(created_at),
            "started_at": _to_iso(started_at),
            "ends_at": _to_iso(ends_at),
            "invite_code": invite_code,
            "member_count": len(members),
            "members": members,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_get_failed")
    finally:
        conn.close()


def ensure_room_member_for_signal(room_id: str, user_id: str) -> str:
    now = _now()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id::text, status, ends_at
            FROM study_rooms
            WHERE room_id::text = %s
            FOR UPDATE
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            conn.rollback()
            return "room_not_found_or_closed"

        room_id_val, status, ends_at = room
        if status != "active":
            conn.rollback()
            return "room_not_found_or_closed"

        if _close_if_expired(cur, room_id_val, ends_at, now):
            conn.commit()
            return "room_not_found_or_closed"

        cur.execute(
            """
            SELECT 1
            FROM room_memberships
            WHERE room_id::text = %s AND user_id::text = %s AND left_at IS NULL
            LIMIT 1
            """,
            (room_id_val, user_id),
        )
        is_member = cur.fetchone() is not None
        conn.commit()
        if not is_member:
            return "not_room_member"
        return "ok"
    except Exception:
        conn.rollback()
        return "room_not_found_or_closed"
    finally:
        conn.close()


def leave_room_by_disconnect(room_id: str, user_id: str) -> Dict:
    user_id = user_id.strip()
    now = _now()

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id::text, host_user_id::text, status, ends_at
            FROM study_rooms
            WHERE room_id::text = %s
            FOR UPDATE
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            conn.rollback()
            return {"room_id": room_id, "status": "noop", "reason": "room_not_found"}

        room_id_val, host_user_id, room_status, ends_at = room
        if room_status != "active":
            conn.rollback()
            return {"room_id": room_id_val, "status": "noop", "reason": "room_not_active"}

        if _close_if_expired(cur, room_id_val, ends_at, now):
            conn.commit()
            return {"room_id": room_id_val, "status": "closed", "reason": "expired"}

        cur.execute(
            """
            SELECT membership_id::text
            FROM room_memberships
            WHERE room_id::text = %s AND user_id::text = %s AND left_at IS NULL
            ORDER BY joined_at DESC
            LIMIT 1
            FOR UPDATE
            """,
            (room_id_val, user_id),
        )
        active_membership = cur.fetchone()
        if not active_membership:
            conn.rollback()
            return {"room_id": room_id_val, "status": "noop", "reason": "already_left"}

        cur.execute(
            """
            UPDATE room_memberships
            SET left_at = %s, leave_reason = 'disconnect_timeout'
            WHERE membership_id::text = %s
            """,
            (now, active_membership[0]),
        )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM room_memberships
            WHERE room_id::text = %s AND left_at IS NULL
            """,
            (room_id_val,),
        )
        active_count = int(cur.fetchone()[0])

        if active_count == 0:
            _close_room(cur, room_id_val, now)
            conn.commit()
            return {
                "room_id": room_id_val,
                "status": "closed",
                "reason": "last_member_left",
            }

        if user_id == host_user_id:
            cur.execute(
                """
                SELECT membership_id::text, user_id::text
                FROM room_memberships
                WHERE room_id::text = %s AND left_at IS NULL
                ORDER BY joined_at ASC
                LIMIT 1
                """,
                (room_id_val,),
            )
            new_host = cur.fetchone()
            if new_host:
                cur.execute(
                    """
                    UPDATE room_memberships
                    SET role = 'host'
                    WHERE membership_id::text = %s
                    """,
                    (new_host[0],),
                )
                cur.execute(
                    """
                    UPDATE study_rooms
                    SET host_user_id = %s
                    WHERE room_id::text = %s
                    """,
                    (new_host[1], room_id_val),
                )

        conn.commit()
        return {
            "room_id": room_id_val,
            "status": "active",
            "member_count": active_count,
            "reason": "disconnect_timeout",
        }
    except Exception:
        conn.rollback()
        return {"room_id": room_id, "status": "noop", "reason": "disconnect_leave_failed"}
    finally:
        conn.close()


def check_room_resumable(room_id: str, user_id: str) -> Dict:
    user_id = user_id.strip()
    now = _now()

    conn = _get_conn()
    try:
        cur = conn.cursor()

        if not _user_exists(cur, user_id):
            raise HTTPException(status_code=404, detail="user_not_found")

        cur.execute(
            """
            SELECT room_id::text, status, ends_at
            FROM study_rooms
            WHERE room_id::text = %s
            FOR UPDATE
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")

        room_id_val, status, ends_at = room
        if status != "active":
            raise HTTPException(status_code=409, detail="room_not_active")

        if _close_if_expired(cur, room_id_val, ends_at, now):
            conn.commit()
            raise HTTPException(status_code=409, detail="room_not_active")

        cur.execute(
            """
            SELECT 1
            FROM room_memberships
            WHERE room_id::text = %s AND user_id::text = %s AND left_at IS NULL
            LIMIT 1
            """,
            (room_id_val, user_id),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=403, detail="not_room_member")

        conn.commit()
        return {
            "room_id": room_id_val,
            "resumable": True,
            "room_status": "active",
            "is_member": True,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_resume_check_failed")
    finally:
        conn.close()


def get_room_study_time(room_id: str, user_id: str) -> Dict:
    user_id = user_id.strip()
    now = _now()

    conn = _get_conn()
    try:
        cur = conn.cursor()

        if not _user_exists(cur, user_id):
            raise HTTPException(status_code=404, detail="user_not_found")

        cur.execute(
            """
            SELECT room_id::text, status, started_at, ends_at, closed_at
            FROM study_rooms
            WHERE room_id::text = %s
            FOR UPDATE
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")

        room_id_val, status, started_at, ends_at, closed_at = room
        if status == "active" and _close_if_expired(cur, room_id_val, ends_at, now):
            status = "closed"
            closed_at = now

        cur.execute(
            """
            SELECT 1
            FROM room_memberships
            WHERE room_id::text = %s AND user_id::text = %s
            LIMIT 1
            """,
            (room_id_val, user_id),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=403, detail="not_room_member")

        cur.execute(
            """
            SELECT
                rm.user_id::text AS user_id,
                u.display_name AS display_name,
                COALESCE(
                    SUM(
                        GREATEST(
                            EXTRACT(EPOCH FROM (COALESCE(rm.left_at, %s) - rm.joined_at)),
                            0
                        )
                    ),
                    0
                )::BIGINT AS total_seconds,
                COALESCE(
                    MAX(
                        CASE
                            WHEN rm.left_at IS NULL THEN GREATEST(EXTRACT(EPOCH FROM (%s - rm.joined_at)), 0)
                            ELSE 0
                        END
                    ),
                    0
                )::BIGINT AS current_session_seconds
            FROM room_memberships rm
            JOIN users u ON u.user_id = rm.user_id
            WHERE rm.room_id::text = %s
            GROUP BY rm.user_id, u.display_name
            ORDER BY total_seconds DESC, rm.user_id::text ASC
            """,
            (now, now, room_id_val),
        )
        rows = cur.fetchall()

        members = [
            {
                "user_id": row[0],
                "display_name": row[1],
                "total_seconds": int(row[2]),
                "current_session_seconds": int(row[3]),
            }
            for row in rows
        ]
        room_total_seconds = sum(item["total_seconds"] for item in members)
        my_total_seconds = 0
        for item in members:
            if item["user_id"] == user_id:
                my_total_seconds = item["total_seconds"]
                break

        room_end = now
        if status == "closed" and closed_at is not None:
            room_end = closed_at
        elif status == "active" and ends_at is not None and ends_at < now:
            room_end = ends_at

        room_elapsed_seconds = int(max((room_end - started_at).total_seconds(), 0))

        conn.commit()
        return {
            "room_id": room_id_val,
            "room_status": status,
            "room_total_seconds": int(room_total_seconds),
            "room_elapsed_seconds": room_elapsed_seconds,
            "my_total_seconds": int(my_total_seconds),
            "members": members,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="room_study_time_failed")
    finally:
        conn.close()
