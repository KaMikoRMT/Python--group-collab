"""平台層房間管理。

建立平台房間時，會同步在共識模組（consensus.db）與任務分工模組（division.db）
建立對應的房間，使用者在大廳輸入一次 nickname + 建立／加入房間後，
即可無痛使用四個功能模組，不必再重複建立／加入房間。
"""

import sqlite3
import random
import string
from datetime import datetime

PLATFORM_DB = "collab_platform.db"
CONSENSUS_DB = "consensus.db"
DIVISION_DB = "division.db"


# ==========================================
# 平台房間資料庫（主控）
# ==========================================
def init_platform_db():
    with sqlite3.connect(PLATFORM_DB) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS platform_rooms (
                room_code TEXT PRIMARY KEY,
                host_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS platform_members (
                room_code TEXT,
                user_name TEXT,
                is_host INTEGER DEFAULT 0,
                PRIMARY KEY(room_code, user_name)
            )"""
        )
        conn.commit()


def _generate_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def get_platform_host(room_code):
    with sqlite3.connect(PLATFORM_DB) as conn:
        row = conn.execute(
            "SELECT host_name FROM platform_rooms WHERE room_code = ?",
            (room_code.upper(),),
        ).fetchone()
    return row[0] if row else None


def verify_platform_room(code):
    with sqlite3.connect(PLATFORM_DB) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM platform_rooms WHERE room_code = ?", (code.upper(),)
        )
        return cursor.fetchone() is not None


def is_user_host(room_code, user_name):
    host = get_platform_host(room_code)
    if host is None:
        return False
    return host.strip().lower() == user_name.strip().lower()


# ==========================================
# 共識模組（consensus.db）同步操作
# ==========================================
def _ensure_consensus_tables():
    with sqlite3.connect(CONSENSUS_DB) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rooms (
                room_code TEXT PRIMARY KEY,
                host_nickname TEXT NOT NULL,
                phase INTEGER NOT NULL DEFAULT 1
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS room_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT NOT NULL,
                nickname TEXT NOT NULL,
                UNIQUE(room_code, nickname)
            )"""
        )
        # consensus 的 project_ideas 與 evaluations 表會由其 init_db() 處理，這裡只需建立房間相關表
        conn.commit()


def _create_consensus_room(room_code, host_name):
    _ensure_consensus_tables()
    with sqlite3.connect(CONSENSUS_DB) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO rooms (room_code, host_nickname, phase) VALUES (?, ?, 1)",
            (room_code, host_name.strip()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO room_members (room_code, nickname) VALUES (?, ?)",
            (room_code, host_name.strip()),
        )
        conn.commit()


def _add_consensus_member(room_code, user_name):
    _ensure_consensus_tables()
    with sqlite3.connect(CONSENSUS_DB) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO room_members (room_code, nickname) VALUES (?, ?)",
            (room_code.upper(), user_name.strip()),
        )
        conn.commit()


# ==========================================
# 任務分工模組（division.db）同步操作
# ==========================================
def _ensure_division_tables():
    with sqlite3.connect(DIVISION_DB) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rooms (
                room_code TEXT PRIMARY KEY,
                project_name TEXT,
                host_name TEXT NOT NULL,
                member_count INTEGER DEFAULT 1,
                phase INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT NOT NULL,
                nickname TEXT NOT NULL,
                is_host INTEGER DEFAULT 0,
                joined_at TEXT NOT NULL,
                UNIQUE(room_code, nickname)
            )"""
        )
        conn.commit()


def _create_division_room(room_code, host_name):
    _ensure_division_tables()
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(DIVISION_DB) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO rooms
               (room_code, project_name, host_name, member_count, phase, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (room_code, "未命名專案", host_name.strip(), 1, 0, now),
        )
        conn.execute(
            """INSERT OR IGNORE INTO members
               (room_code, nickname, is_host, joined_at) VALUES (?, ?, ?, ?)""",
            (room_code, host_name.strip(), 1, now),
        )
        conn.commit()


def _add_division_member(room_code, user_name):
    _ensure_division_tables()
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(DIVISION_DB) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO members
               (room_code, nickname, is_host, joined_at) VALUES (?, ?, ?, ?)""",
            (room_code.upper(), user_name.strip(), 0, now),
        )
        # 房間人數 +1（取目前實際成員數）
        cur = conn.execute(
            "SELECT COUNT(*) FROM members WHERE room_code = ?", (room_code.upper(),)
        )
        count = cur.fetchone()[0]
        conn.execute(
            "UPDATE rooms SET member_count = ? WHERE room_code = ?",
            (count, room_code.upper()),
        )
        conn.commit()


# ==========================================
# 跨資料庫統一操作介面
# ==========================================
def create_platform_room(host_name):
    """建立平台房間，並在共識、任務分工模組同步建立相同 code 的房間。"""
    init_platform_db()
    host_name = host_name.strip()

    # 確保 code 在三個資料庫都唯一
    while True:
        code = _generate_code()
        with sqlite3.connect(PLATFORM_DB) as conn:
            exists = conn.execute(
                "SELECT 1 FROM platform_rooms WHERE room_code = ?", (code,)
            ).fetchone()
        if not exists:
            break

    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(PLATFORM_DB) as conn:
        conn.execute(
            "INSERT INTO platform_rooms (room_code, host_name, created_at) VALUES (?, ?, ?)",
            (code, host_name, now),
        )
        conn.execute(
            "INSERT INTO platform_members (room_code, user_name, is_host) VALUES (?, ?, 1)",
            (code, host_name),
        )
        conn.commit()

    # 同步到子模組
    _create_consensus_room(code, host_name)
    _create_division_room(code, host_name)
    return code


def join_platform_room(room_code, user_name):
    """加入平台房間，並在共識、任務分工模組同步加入。"""
    init_platform_db()
    room_code = room_code.strip().upper()
    user_name = user_name.strip()

    if not verify_platform_room(room_code):
        return False

    with sqlite3.connect(PLATFORM_DB) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO platform_members (room_code, user_name, is_host) VALUES (?, ?, 0)",
            (room_code, user_name),
        )
        conn.commit()

    _add_consensus_member(room_code, user_name)
    _add_division_member(room_code, user_name)
    return True
