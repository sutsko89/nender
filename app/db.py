"""Модуль работы с локальной базой данных SQLite."""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = Path(os.environ.get("NENDER_DB_PATH", "nender.db"))
SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Инициализация базы данных по схеме."""
    with get_connection() as conn:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
    log("db", "База данных инициализирована")


# --- Настройки ------------------------------------------------------------------

def get_settings() -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM app_settings WHERE id=1").fetchone()
        return dict(row) if row else None


def save_settings(data: Dict):
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM app_settings WHERE id=1").fetchone()
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if existing:
            fields = ", ".join(f"{k}=?" for k in data)
            conn.execute(f"UPDATE app_settings SET {fields} WHERE id=1", list(data.values()))
        else:
            data["id"] = 1
            keys = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            conn.execute(f"INSERT INTO app_settings ({keys}) VALUES ({placeholders})", list(data.values()))


# --- Поисковые профили ----------------------------------------------------------

def get_all_profiles() -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM search_profiles ORDER BY created_at DESC").fetchall()
        profiles = []
        for row in rows:
            p = dict(row)
            p["keywords"] = json.loads(p["keywords"]) if p["keywords"] else []
            p["inn_list"] = [
                r["inn"] for r in conn.execute(
                    "SELECT inn FROM search_profile_inn WHERE search_profile_id=?", (p["id"],)
                ).fetchall()
            ]
            profiles.append(p)
        return profiles


def get_profile(profile_id: int) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM search_profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            return None
        p = dict(row)
        p["keywords"] = json.loads(p["keywords"]) if p["keywords"] else []
        p["inn_list"] = [
            r["inn"] for r in conn.execute(
                "SELECT inn FROM search_profile_inn WHERE search_profile_id=?", (p["id"],)
            ).fetchall()
        ]
        return p


def save_profile(data: Dict) -> int:
    """Создать или обновить профиль. Возвращает id."""
    inn_list = data.pop("inn_list", [])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["keywords"] = json.dumps(data.get("keywords", []), ensure_ascii=False)
    data["updated_at"] = now
    with get_connection() as conn:
        if data.get("id"):
            profile_id = data.pop("id")
            fields = ", ".join(f"{k}=?" for k in data)
            conn.execute(f"UPDATE search_profiles SET {fields} WHERE id=?", list(data.values()) + [profile_id])
            conn.execute("DELETE FROM search_profile_inn WHERE search_profile_id=?", (profile_id,))
        else:
            data.pop("id", None)
            data["created_at"] = now
            keys = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cur = conn.execute(f"INSERT INTO search_profiles ({keys}) VALUES ({placeholders})", list(data.values()))
            profile_id = cur.lastrowid
        for inn in inn_list:
            if inn.strip():
                conn.execute(
                    "INSERT INTO search_profile_inn (search_profile_id, inn) VALUES (?, ?)",
                    (profile_id, inn.strip())
                )
    return profile_id


def delete_profile(profile_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM search_profiles WHERE id=?", (profile_id,))


def update_profile_last_run(profile_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE search_profiles SET last_run_at=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), profile_id)
        )


def update_profile_last_email(profile_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE search_profiles SET last_email_sent_at=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), profile_id)
        )


# --- Закупки и результаты -------------------------------------------------------

def upsert_tender(tender: Dict) -> int:
    """Сохранить закупку. Если уже есть — вернуть id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM tenders WHERE external_id=?", (tender["external_id"],)
        ).fetchone()
        if row:
            return row["id"]
        tender["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tender["raw_payload"] = json.dumps(tender.get("raw_payload", {}), ensure_ascii=False)
        keys = ", ".join(tender.keys())
        placeholders = ", ".join(["?"] * len(tender))
        cur = conn.execute(
            f"INSERT INTO tenders ({keys}) VALUES ({placeholders})", list(tender.values())
        )
        return cur.lastrowid


def add_search_result(profile_id: int, tender_id: int) -> bool:
    """Добавить связь профиль—закупка. Возвращает True если закупка новая."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email_sent FROM search_results WHERE search_profile_id=? AND tender_id=?",
            (profile_id, tender_id)
        ).fetchone()
        if row:
            return not bool(row["email_sent"])
        conn.execute(
            "INSERT INTO search_results (search_profile_id, tender_id, is_new, email_sent) VALUES (?, ?, 1, 0)",
            (profile_id, tender_id)
        )
        return True


def get_unsent_results(profile_id: int) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT t.* FROM tenders t
            JOIN search_results sr ON sr.tender_id = t.id
            WHERE sr.search_profile_id=? AND sr.email_sent=0
            ORDER BY t.publish_date DESC
            """,
            (profile_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_results_sent(profile_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE search_results SET email_sent=1, email_sent_at=? WHERE search_profile_id=? AND email_sent=0",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), profile_id)
        )


def get_recent_results(profile_id: int, limit: int = 50) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT t.*, sr.is_new, sr.email_sent, sr.matched_at, sr.email_sent_at
            FROM tenders t
            JOIN search_results sr ON sr.tender_id = t.id
            WHERE sr.search_profile_id=?
            ORDER BY sr.matched_at DESC
            LIMIT ?
            """,
            (profile_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# --- Журнал ---------------------------------------------------------------------

def log(module: str, message: str, level: str = "INFO", details: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO app_log (level, module, message, details) VALUES (?, ?, ?, ?)",
            (level, module, message, details)
        )


def get_logs(limit: int = 200) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM app_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
