import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException


MAX_MESSAGE_LEN = int(os.getenv("CHAT_MAX_MESSAGE_LEN", "2000"))


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


def _require_active_member(cur, room_id: str, user_id: str, now: datetime) -> None:
    cur.execute(
        """
        SELECT status, ends_at
        FROM study_rooms
        WHERE room_id::text = %s
        FOR UPDATE
        """,
        (room_id,),
    )
    room = cur.fetchone()
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")

    status, ends_at = room
    if status != "active" or now > ends_at:
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
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="not_room_member")


def _get_or_create_conversation(cur, room_id: str, user_id: str):
    cur.execute(
        """
        INSERT INTO conversations (type, room_id, created_by, is_active)
        VALUES ('room', %s, %s, true)
        ON CONFLICT (room_id)
        DO UPDATE SET room_id = EXCLUDED.room_id
        RETURNING conversation_id::text, type, room_id::text, is_active, created_at, updated_at
        """,
        (room_id, user_id),
    )
    return cur.fetchone()


def get_room_conversation(room_id: str, user_id: str) -> Dict:
    user_id = user_id.strip()
    now = _now()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        _require_active_member(cur, room_id, user_id, now)
        row = _get_or_create_conversation(cur, room_id, user_id)
        conn.commit()
        return {
            "conversation_id": row[0],
            "type": row[1],
            "room_id": row[2],
            "is_active": row[3],
            "created_at": _to_iso(row[4]),
            "updated_at": _to_iso(row[5]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="chat_conversation_failed")
    finally:
        conn.close()


def send_room_message(room_id: str, user_id: str, content: str) -> Dict:
    user_id = user_id.strip()
    content = content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="message_content_empty")
    if len(content) > MAX_MESSAGE_LEN:
        raise HTTPException(status_code=400, detail="message_too_long")

    now = _now()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        _require_active_member(cur, room_id, user_id, now)
        conversation = _get_or_create_conversation(cur, room_id, user_id)

        cur.execute(
            """
            INSERT INTO messages (
                conversation_id, sender_user_id, content_type, content, metadata_json, created_at
            )
            VALUES (%s, %s, 'text', %s, '{}'::jsonb, %s)
            RETURNING message_id, conversation_id::text, sender_user_id::text, content_type, content,
                      is_deleted, edited_at, created_at
            """,
            (conversation[0], user_id, content, now),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "message_id": row[0],
            "conversation_id": row[1],
            "sender_user_id": row[2],
            "content_type": row[3],
            "content": row[4],
            "is_deleted": row[5],
            "edited_at": _to_iso(row[6]),
            "created_at": _to_iso(row[7]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="chat_send_failed")
    finally:
        conn.close()


def list_room_messages(room_id: str, user_id: str, limit: int = 20, before_message_id: Optional[int] = None) -> Dict:
    user_id = user_id.strip()
    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=400, detail="invalid_message_query")

    now = _now()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        _require_active_member(cur, room_id, user_id, now)
        conversation = _get_or_create_conversation(cur, room_id, user_id)

        if before_message_id is None:
            cur.execute(
                """
                SELECT message_id, conversation_id::text, sender_user_id::text, content_type, content,
                       is_deleted, edited_at, created_at
                FROM messages
                WHERE conversation_id::text = %s
                ORDER BY message_id DESC
                LIMIT %s
                """,
                (conversation[0], limit),
            )
        else:
            cur.execute(
                """
                SELECT message_id, conversation_id::text, sender_user_id::text, content_type, content,
                       is_deleted, edited_at, created_at
                FROM messages
                WHERE conversation_id::text = %s AND message_id < %s
                ORDER BY message_id DESC
                LIMIT %s
                """,
                (conversation[0], before_message_id, limit),
            )

        rows = cur.fetchall()
        rows.reverse()
        messages: List[Dict] = []
        for row in rows:
            messages.append(
                {
                    "message_id": row[0],
                    "conversation_id": row[1],
                    "sender_user_id": row[2],
                    "content_type": row[3],
                    "content": row[4],
                    "is_deleted": row[5],
                    "edited_at": _to_iso(row[6]),
                    "created_at": _to_iso(row[7]),
                }
            )

        next_before_message_id = rows[0][0] if rows else None
        conn.commit()
        return {
            "conversation_id": conversation[0],
            "messages": messages,
            "next_before_message_id": next_before_message_id,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="chat_list_failed")
    finally:
        conn.close()


def update_read_cursor(room_id: str, user_id: str, last_read_message_id: int) -> Dict:
    user_id = user_id.strip()
    if last_read_message_id <= 0:
        raise HTTPException(status_code=400, detail="invalid_read_cursor_payload")

    now = _now()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        _require_active_member(cur, room_id, user_id, now)
        conversation = _get_or_create_conversation(cur, room_id, user_id)

        cur.execute(
            """
            SELECT 1
            FROM messages
            WHERE conversation_id::text = %s AND message_id = %s
            LIMIT 1
            """,
            (conversation[0], last_read_message_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="chat_message_not_found")

        cur.execute(
            """
            INSERT INTO conversation_read_cursors (
                conversation_id, user_id, last_read_message_id, last_read_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (conversation_id, user_id)
            DO UPDATE SET
                last_read_message_id = EXCLUDED.last_read_message_id,
                last_read_at = EXCLUDED.last_read_at,
                updated_at = EXCLUDED.updated_at
            RETURNING conversation_id::text, user_id::text, last_read_message_id, last_read_at, updated_at
            """,
            (conversation[0], user_id, last_read_message_id, now, now),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "conversation_id": row[0],
            "user_id": row[1],
            "last_read_message_id": row[2],
            "last_read_at": _to_iso(row[3]),
            "updated_at": _to_iso(row[4]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="chat_read_cursor_failed")
    finally:
        conn.close()
