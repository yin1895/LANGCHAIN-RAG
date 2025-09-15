import os
import sqlite3

p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "users.db"))
print("DB PATH:", p)
if not os.path.exists(p):
    print("users.db not found")
else:
    conn = sqlite3.connect(p)
    cur = conn.cursor()
    try:
        rows = cur.execute(
            "SELECT id, username, is_admin, is_active, created_at FROM users"
        ).fetchall()
        print("rows count:", len(rows))
        for r in rows:
            print(r)
    except Exception as e:
        print("error reading users table:", e)
    finally:
        conn.close()
