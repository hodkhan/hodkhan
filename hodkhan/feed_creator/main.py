import sqlite3
from pathlib import Path
import datetime


DB_PATH = Path(__file__).resolve().parent.parent.parent / 'db.sqlite3'


def record(username, news_id, n):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Resolve user id from username if possible
    try:
        cursor.execute("SELECT id FROM auth_user WHERE username = ?", (username,))
        uid = cursor.fetchone()
        user_id = uid[0] if uid else None
    except Exception:
        user_id = None

    created_at = datetime.datetime.utcnow().isoformat()
    sql = (
        "INSERT INTO app_interaction (user_id, article_id, type, star, is_trained, created_at, value)"
        "\nVALUES (?, ?, 'view', ?, 0, ?, ?)"
    )
    cursor.execute(sql, (user_id, news_id, n, created_at, None))
    conn.commit()
    conn.close()
