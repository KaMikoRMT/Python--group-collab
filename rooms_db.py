import sqlite3
import random
import string

DB_FILE = "collab_platform.db"


def init_platform_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS platform_rooms (room_code TEXT PRIMARY KEY)"
        )
        conn.commit()


def create_platform_room():
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO platform_rooms (room_code) VALUES (?)", (code,))
        conn.commit()
    return code


def verify_platform_room(code):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM platform_rooms WHERE room_code = ?", (code.upper(),)
        )
        return cursor.fetchone() is not None
