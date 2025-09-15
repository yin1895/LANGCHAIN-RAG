import os
import sqlite3
from typing import Optional, Tuple
from jose import jwt, JWTError
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from dataclasses import dataclass
from rest_framework.permissions import BasePermission
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ.get('AUTH_SECRET_KEY', 'your-secret-key')
ALGORITHM = 'HS256'


def _db_path() -> str:
    # Allow override via env var; fallback to repo root users.db
    env_path = os.environ.get('AUTH_DB_PATH')
    if env_path:
        return str(Path(env_path).resolve())
    return str((ROOT / 'users.db').resolve())


def _get_db():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


@dataclass
class SimpleUser:
    username: str
    is_admin: bool = False

    # DRF expects attributes similar to Django User
    @property
    def is_authenticated(self) -> bool:
        return True


def _decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


class JwtSqliteAuthentication(BaseAuthentication):
    def authenticate(self, request) -> Optional[Tuple[SimpleUser, str]]:
        auth = request.headers.get('Authorization') or request.headers.get('authorization')
        if not auth or not auth.startswith('Bearer '):
            return None
        token = auth.split(' ', 1)[1]
        try:
            payload = _decode_token(token)
        except JWTError:
            raise exceptions.AuthenticationFailed('Token无效或过期')

        jti = payload.get('jti')
        username = payload.get('sub')
        conn = _get_db()
        cur = conn.cursor()
        try:
            if jti:
                if cur.execute('SELECT 1 FROM revoked_tokens WHERE jti=?', (jti,)).fetchone():
                    raise exceptions.AuthenticationFailed('Token 已被撤销')
            user = cur.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            if not user:
                raise exceptions.AuthenticationFailed('用户不存在')
            if not user['is_active']:
                raise exceptions.AuthenticationFailed('账号已冻结')
            simple = SimpleUser(username=user['username'], is_admin=bool(user['is_admin']))
            return (simple, token)
        finally:
            conn.close()


 

class IsAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        u = getattr(request, 'user', None)
        return bool(u and getattr(u, 'is_admin', False))
