import os
import shutil
import time
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_DB = ROOT / 'users.db'
NEW_DB = Path(os.environ.get('AUTH_DB_PATH') or (ROOT / 'users.db'))

SCHEMA = {
    'users': '''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at INTEGER
    )''',
    'revoked_tokens': '''CREATE TABLE IF NOT EXISTS revoked_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jti TEXT UNIQUE NOT NULL,
        revoked_at INTEGER NOT NULL,
        revoked_by TEXT
    )''',
    'admin_audit': '''CREATE TABLE IF NOT EXISTS admin_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        created_at INTEGER NOT NULL
    )'''
}


def ensure_schema(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    try:
        for ddl in SCHEMA.values():
            conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()


def copy_rows(src: Path, dst: Path):
    s = sqlite3.connect(str(src))
    s.row_factory = sqlite3.Row
    d = sqlite3.connect(str(dst))
    try:
        # users
        rows = s.execute('SELECT id, username, password_hash, is_admin, is_active, created_at FROM users').fetchall()
        for r in rows:
            d.execute('INSERT OR IGNORE INTO users (id, username, password_hash, is_admin, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                      (r['id'], r['username'], r['password_hash'], r['is_admin'], r['is_active'], r['created_at']))
        # revoked_tokens
        rows = s.execute('SELECT id, jti, revoked_at, revoked_by FROM revoked_tokens').fetchall()
        for r in rows:
            d.execute('INSERT OR IGNORE INTO revoked_tokens (id, jti, revoked_at, revoked_by) VALUES (?, ?, ?, ?)',
                      (r['id'], r['jti'], r['revoked_at'], r['revoked_by']))
        # admin_audit
        rows = s.execute('SELECT id, actor, action, target, created_at FROM admin_audit').fetchall()
        for r in rows:
            d.execute('INSERT OR IGNORE INTO admin_audit (id, actor, action, target, created_at) VALUES (?, ?, ?, ?, ?)',
                      (r['id'], r['actor'], r['action'], r['target'], r['created_at']))
        d.commit()
    finally:
        s.close()
        d.close()


def backup_file(path: Path):
    if not path.exists():
        return None
    ts = time.strftime('%Y%m%d-%H%M%S')
    bak = path.with_suffix(path.suffix + f'.bak.{ts}')
    shutil.copy2(path, bak)
    return bak


def main():
    if not OLD_DB.exists():
        print(f"old users.db not found at {OLD_DB}")
        return 1
    NEW_DB.parent.mkdir(parents=True, exist_ok=True)
    # 保守：先备份目标库
    bak = backup_file(NEW_DB)
    ensure_schema(NEW_DB)
    copy_rows(OLD_DB, NEW_DB)
    # 打印统计
    conn = sqlite3.connect(str(NEW_DB))
    conn.row_factory = sqlite3.Row
    u = conn.execute('SELECT COUNT(1) c FROM users').fetchone()['c']
    r = conn.execute('SELECT COUNT(1) c FROM revoked_tokens').fetchone()['c']
    a = conn.execute('SELECT COUNT(1) c FROM admin_audit').fetchone()['c']
    conn.close()
    print({"users": u, "revoked_tokens": r, "admin_audit": a, "backup": str(bak) if bak else None, "target": str(NEW_DB)})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
