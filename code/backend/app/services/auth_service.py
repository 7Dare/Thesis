import hashlib
import hmac
import os
import secrets
from typing import Optional, Tuple

from fastapi import HTTPException

DATABASE_URL = os.getenv("DATABASE_URL", "")


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
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="database_url_missing")
    driver_name, driver = _load_db_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="db_driver_missing_install_psycopg")
    return driver_name, driver.connect(DATABASE_URL)


def _hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def _verify_password(password: str, salt_hex: str, digest_hex: str) -> bool:
    _, calc_hex = _hash_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(calc_hex, digest_hex)


def register_user(login_user_id: str, password: str, display_name: str, email: Optional[str]):
    login_user_id = login_user_id.strip()
    display_name = display_name.strip()
    if not login_user_id or not password or not display_name:
        raise HTTPException(status_code=400, detail="invalid_register_payload")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="password_too_short")

    salt_hex, digest_hex = _hash_password(password)
    password_hash = f"pbkdf2_sha256${salt_hex}${digest_hex}"
    driver_name, conn = _get_conn()

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (login_user_id, display_name, email, password_hash)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id, login_user_id, display_name, email, created_at
            """,
            (login_user_id, display_name, email, password_hash),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "user_id": str(row[0]),
            "login_user_id": row[1],
            "display_name": row[2],
            "email": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
        }
    except Exception as exc:
        conn.rollback()
        msg = str(exc).lower()
        if "users_login_user_id_key" in msg or ("login_user_id" in msg and "duplicate" in msg):
            raise HTTPException(status_code=409, detail="login_user_id_exists")
        if "users_email_key" in msg or ("email" in msg and "duplicate" in msg):
            raise HTTPException(status_code=409, detail="email_exists")
        raise HTTPException(status_code=500, detail=f"register_failed_{driver_name}")
    finally:
        conn.close()


def login_user(login_user_id: str, password: str):
    login_user_id = login_user_id.strip()
    if not login_user_id or not password:
        raise HTTPException(status_code=400, detail="invalid_login_payload")

    driver_name, conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, login_user_id, display_name, email, password_hash
            FROM users
            WHERE login_user_id = %s
            """,
            (login_user_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="invalid_credentials")

        stored = row[4] or ""
        parts = stored.split("$")
        if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
            raise HTTPException(status_code=500, detail="password_hash_format_invalid")

        if not _verify_password(password, parts[1], parts[2]):
            raise HTTPException(status_code=401, detail="invalid_credentials")

        return {
            "user_id": str(row[0]),
            "login_user_id": row[1],
            "display_name": row[2],
            "email": row[3],
            "message": "login_success",
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail=f"login_failed_{driver_name}")
    finally:
        conn.close()
