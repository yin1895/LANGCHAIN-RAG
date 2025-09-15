import sqlite3
import hashlib
import time
import uuid
from pathlib import Path
import os
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from jose import jwt, JWTError
from typing import Optional

SECRET_KEY = os.environ.get('AUTH_SECRET_KEY', 'your-secret-key')
ALGORITHM = 'HS256'
# Use a deterministic absolute path for users.db placed at repo root
ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = str(Path(os.environ.get('AUTH_DB_PATH') or (ROOT / 'users.db')).resolve())

router = APIRouter()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def create_tables():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at INTEGER
    )''')
    # 撤销的 token 列表（存储 jti）
    conn.execute('''CREATE TABLE IF NOT EXISTS revoked_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jti TEXT UNIQUE NOT NULL,
        revoked_at INTEGER NOT NULL,
        revoked_by TEXT
    )''')
    # 管理操作审计表
    conn.execute('''CREATE TABLE IF NOT EXISTS admin_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        created_at INTEGER NOT NULL
    )''')
    conn.commit()
    conn.close()


create_tables()


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RevokeTokenRequest(BaseModel):
    token: Optional[str] = None
    jti: Optional[str] = None


@router.post('/register')
def register(req: RegisterRequest):
    conn = get_db()
    cur = conn.cursor()
    if cur.execute('SELECT * FROM users WHERE username=?', (req.username,)).fetchone():
        raise HTTPException(400, '用户名已存在')
    pw_hash = hash_password(req.password)
    cur.execute('INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)',
                (req.username, pw_hash, int(time.time())))
    conn.commit()
    conn.close()
    return {'success': True}


@router.post('/login')
def login(req: LoginRequest):
    conn = get_db()
    cur = conn.cursor()
    user = cur.execute('SELECT * FROM users WHERE username=?', (req.username,)).fetchone()
    if not user or user['password_hash'] != hash_password(req.password):
        raise HTTPException(401, '用户名或密码错误')
    if not user['is_active']:
        raise HTTPException(403, '账号已冻结')
    jti = str(uuid.uuid4())
    now = int(time.time())
    payload = {
        'sub': user['username'],
        'is_admin': bool(user['is_admin']),
        'iat': now,
        'jti': jti,
        'exp': now + 86400
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    conn.close()
    return {'token': token, 'is_admin': bool(user['is_admin']), 'jti': jti}


# JWT校验工具：检查 token 是否被撤销，并确认用户仍处于活跃状态
def get_current_user(request: Request):
    auth = request.headers.get('authorization')
    if not auth or not auth.startswith('Bearer '):
        raise HTTPException(401, '未登录')
    token = auth.split(' ', 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(401, 'Token无效或过期')

    jti = payload.get('jti')
    username = payload.get('sub')
    # 检查是否已被撤销
    if jti:
        conn = get_db()
        cur = conn.cursor()
        revoked = cur.execute('SELECT * FROM revoked_tokens WHERE jti=?', (jti,)).fetchone()
        conn.close()
        if revoked:
            raise HTTPException(401, 'Token 已被撤销')

    # 检查用户是否存在并且处于激活状态
    conn = get_db()
    cur = conn.cursor()
    user = cur.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(401, '用户不存在')
    if not user['is_active']:
        raise HTTPException(403, '账号已冻结')

    # 将数据库中最新的 is_admin 信息合并到返回 payload 中
    payload['is_admin'] = bool(user['is_admin'])
    return payload


### 管理端点：需要管理员权限 ###


def require_admin(payload: dict):
    if not payload.get('is_admin'):
        raise HTTPException(403, '需要管理员权限')


@router.get('/admin/users')
def admin_list_users(user=Depends(get_current_user)):
    require_admin(user)
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute('SELECT id, username, is_admin, is_active, created_at FROM users').fetchall()
    conn.close()
    users = [dict(r) for r in rows]
    return {'users': users}


def _count_admins(cur):
    r = cur.execute('SELECT COUNT(1) as c FROM users WHERE is_admin=1').fetchone()
    return int(r['c']) if r else 0


def _log_admin_action(actor: str, action: str, target: Optional[str] = None):
    conn = get_db()
    conn.execute('INSERT INTO admin_audit (actor, action, target, created_at) VALUES (?, ?, ?, ?)',
                 (actor, action, target, int(time.time())))
    conn.commit()
    conn.close()


@router.post('/admin/users/{username}/promote')
def admin_promote(username: str, user=Depends(get_current_user)):
    require_admin(user)
    actor = user.get('sub')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_admin=1 WHERE username=?', (username,))
    conn.commit()
    conn.close()
    _log_admin_action(actor, 'promote', username)
    return {'success': True}


@router.post('/admin/users/{username}/demote')
def admin_demote(username: str, user=Depends(get_current_user)):
    require_admin(user)
    actor = user.get('sub')
    conn = get_db()
    cur = conn.cursor()
    admins = _count_admins(cur)
    # 防止降级或删除最后一个管理员
    target = cur.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, '目标用户不存在')
    if target['is_admin'] and admins <= 1:
        conn.close()
        raise HTTPException(400, '不能降级最后一个管理员')
    cur.execute('UPDATE users SET is_admin=0 WHERE username=?', (username,))
    conn.commit()
    conn.close()
    _log_admin_action(actor, 'demote', username)
    return {'success': True}


@router.post('/admin/users/{username}/freeze')
def admin_freeze(username: str, user=Depends(get_current_user)):
    require_admin(user)
    actor = user.get('sub')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_active=0 WHERE username=?', (username,))
    conn.commit()
    conn.close()
    _log_admin_action(actor, 'freeze', username)
    return {'success': True}


@router.post('/admin/users/{username}/unfreeze')
def admin_unfreeze(username: str, user=Depends(get_current_user)):
    require_admin(user)
    actor = user.get('sub')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_active=1 WHERE username=?', (username,))
    conn.commit()
    conn.close()
    _log_admin_action(actor, 'unfreeze', username)
    return {'success': True}


@router.delete('/admin/users/{username}')
def admin_delete_user(username: str, user=Depends(get_current_user)):
    require_admin(user)
    actor = user.get('sub')
    conn = get_db()
    cur = conn.cursor()
    target = cur.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, '目标用户不存在')
    if target['is_admin']:
        admins = _count_admins(cur)
        if admins <= 1:
            conn.close()
            raise HTTPException(400, '不能删除最后一个管理员')
    cur.execute('DELETE FROM users WHERE username=?', (username,))
    conn.commit()
    conn.close()
    _log_admin_action(actor, 'delete_user', username)
    return {'success': True}


@router.post('/admin/tokens/revoke')
def admin_revoke_token(req: RevokeTokenRequest, user=Depends(get_current_user)):
    require_admin(user)
    actor = user.get('sub')
    jti = None
    if req.jti:
        jti = req.jti
    elif req.token:
        try:
            payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get('jti')
        except JWTError:
            raise HTTPException(400, '提供的 token 无效')
    if not jti:
        raise HTTPException(400, '需要提供 token 或 jti')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO revoked_tokens (jti, revoked_at, revoked_by) VALUES (?, ?, ?)',
                (jti, int(time.time()), actor))
    conn.commit()
    conn.close()
    _log_admin_action(actor, 'revoke_token', jti)
    return {'success': True, 'jti': jti}


@router.get('/admin/tokens')
def admin_list_revoked(user=Depends(get_current_user)):
    require_admin(user)
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute('SELECT id, jti, revoked_at, revoked_by FROM revoked_tokens ORDER BY revoked_at DESC').fetchall()
    conn.close()
    items = [dict(r) for r in rows]
    return {'revoked': items}

