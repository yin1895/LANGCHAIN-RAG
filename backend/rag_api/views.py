import asyncio
import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from jose import JWTError, jwt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

# Global singletons & concurrency guard
_GLOBAL = {
    "embed": None,
    "store": None,
    "llm": None,
}
_ASK_SEMAPHORE = asyncio.Semaphore(
    int((settings and getattr(settings, "ASK_MAX_CONCURRENCY", None)) or 32)
)

# Ingest job tracking for async mode
_INGEST_JOBS = {}

# Repo root used for locating resources
ROOT = Path(__file__).resolve().parents[2]


def _ensure_components():
    # Lazy import of project-local modules to avoid import-time side-effects
    import sys

    from dotenv import load_dotenv

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    load_dotenv()
    from src.config import get_settings as get_src_settings
    from src.rag.embeddings import OllamaEmbeddings
    from src.rag.llm import get_default_llm
    from src.rag.vector_store import FaissStore

    # read project settings locally for initialization
    s = get_src_settings()
    if _GLOBAL["embed"] is None:
        _GLOBAL["embed"] = OllamaEmbeddings(s.embed_model)
    if _GLOBAL["store"] is None:
        _GLOBAL["store"] = FaissStore(s.vector_store_path, s.metadata_store_path, dim=None)
    if _GLOBAL["llm"] is None:
        _GLOBAL["llm"] = get_default_llm()


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: HttpRequest):
    return Response({"status": "ok", "backend": "django"})


@method_decorator(csrf_exempt, name="dispatch")
class AskView(APIView):
    permission_classes = [AllowAny]

    async def post(self, request: HttpRequest):
        if request.method != "POST":
            return Response({"error": "method not allowed"}, status=405)
        try:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
        except Exception:
            body = {}
        question = body.get("question") or body.get("query") or ""
        top_k = int(body.get("top_k") or 6)
        bm25_weight = float(body.get("bm25_weight") or 0.35)
        include_content = bool(body.get("include_content") or False)
        if not question:
            return Response({"error": "empty question"}, status=400)

        await _ASK_SEMAPHORE.acquire()
        try:
            _ensure_components()
            # import Retriever lazily after components ensured
            from src.rag.retriever import Retriever

            retriever = Retriever(
                _GLOBAL["store"], _GLOBAL["embed"], k=top_k, bm25_weight=bm25_weight
            )
            docs = retriever.get_relevant(question)
            timeout_sec = int(os.environ.get("ASK_TIMEOUT", "60"))
            try:
                answer = await asyncio.wait_for(
                    _GLOBAL["llm"].acomplete(question, docs), timeout=timeout_sec
                )
            except Exception as e:
                return Response({"error": "llm_error", "detail": str(e)}, status=502)
            contexts = []
            for d in docs:
                item = {"score": d.get("score"), "source": d.get("source"), "hash": d.get("hash")}
                if include_content and "content" in d:
                    c = d["content"]
                    if isinstance(c, str) and len(c) > 2000:
                        c = c[:2000] + "..."
                    item["content"] = c
                contexts.append(item)
            return Response({"answer": answer, "contexts": contexts})
        finally:
            _ASK_SEMAPHORE.release()


@method_decorator(csrf_exempt, name="dispatch")
class AskStreamView(APIView):
    permission_classes = [AllowAny]

    async def post(self, request: HttpRequest):
        if request.method != "POST":
            return Response({"error": "method not allowed"}, status=405)
        try:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
        except Exception:
            body = {}
        question = body.get("question") or body.get("query") or ""
        top_k = int(body.get("top_k") or 6)
        bm25_weight = float(body.get("bm25_weight") or 0.35)
        include_content = bool(body.get("include_content") or False)
        if not question:
            return Response({"error": "empty question"}, status=400)

        await _ASK_SEMAPHORE.acquire()
        try:
            _ensure_components()
            # import Retriever lazily after components ensured
            from src.rag.retriever import Retriever

            retriever = Retriever(
                _GLOBAL["store"], _GLOBAL["embed"], k=top_k, bm25_weight=bm25_weight
            )
            docs = retriever.get_relevant(question)
            base_contexts = []
            for d in docs:
                item = {"score": d.get("score"), "source": d.get("source"), "hash": d.get("hash")}
                if include_content and "content" in d:
                    c = d["content"]
                    if isinstance(c, str) and len(c) > 2000:
                        c = c[:2000] + "..."
                    item["content"] = c
                base_contexts.append(item)

            async def event_gen():
                yield f"data: {json.dumps({'type':'contexts','data': base_contexts}, ensure_ascii=False)}\n\n"
                try:
                    async for chunk in _GLOBAL["llm"].astream(question, docs):
                        yield f"data: {json.dumps({'type':'chunk','data': chunk}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    err = {"type": "error", "detail": str(e)}
                    yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
                yield 'data: {"type":"end"}\n\n'

            return StreamingHttpResponse(event_gen(), content_type="text/event-stream")
        finally:
            _ASK_SEMAPHORE.release()


@csrf_exempt
def ingest(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    # Ensure components and project path are set up, then import ingestion helpers
    _ensure_components()

    # EDGE_MODE=sync will run a synchronous, tightly-coupled ingest fast-path
    # which is simpler for edge deployments and reduces orchestration overhead.
    edge_mode = os.environ.get("EDGE_MODE", "sync").lower()
    if edge_mode == "sync":
        # run locally and return the result immediately
        try:
            from backend.tasks import run_ingest_sync

            res = run_ingest_sync()
            return JsonResponse(res)
        except Exception as e:
            return JsonResponse({"error": "ingest_failed", "detail": str(e)}, status=500)
    else:
        # async mode: try enqueue to Celery if available; otherwise start a
        # background thread and return a job_id the client can poll.
        job_id = str(uuid.uuid4())
        _INGEST_JOBS[job_id] = {
            "status": "queued",
            "started_at": None,
            "finished_at": None,
            "error": None,
            "added": 0,
        }
        # prefer Celery if configured
        try:
            from backend.tasks import run_ingest

            # schedule Celery task
            run_ingest.delay(job_id)
        except Exception:
            # fallback to background thread to avoid requiring Celery in edge
            import threading

            def _bg():
                try:
                    from backend.tasks import run_ingest_task

                    _INGEST_JOBS[job_id]["status"] = "running"
                    _INGEST_JOBS[job_id]["started_at"] = int(time.time())
                    res = run_ingest_task(job_id)
                    _INGEST_JOBS[job_id]["added"] = int(res.get("added", 0))
                    _INGEST_JOBS[job_id]["status"] = "finished"
                    _INGEST_JOBS[job_id]["finished_at"] = int(time.time())
                except Exception as e:
                    _INGEST_JOBS[job_id]["status"] = "error"
                    _INGEST_JOBS[job_id]["error"] = str(e)
                    _INGEST_JOBS[job_id]["finished_at"] = int(time.time())

            t = threading.Thread(target=_bg, daemon=True)
            t.start()
        return JsonResponse({"job_id": job_id})


@csrf_exempt
def ingest_status(request: HttpRequest, job_id: str):
    info = _INGEST_JOBS.get(job_id)
    if not info:
        return JsonResponse({"error": "job_not_found"}, status=404)
    return JsonResponse(info)


def _db_path() -> str:
    # Same path scheme as src/api/auth.py
    env_path = os.environ.get("AUTH_DB_PATH")
    if env_path:
        return str(Path(env_path).resolve())
    return str((ROOT / "users.db").resolve())


def _get_db():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _create_tables():
    conn = _get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at INTEGER
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS revoked_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jti TEXT UNIQUE NOT NULL,
        revoked_at INTEGER NOT NULL,
        revoked_by TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        created_at INTEGER NOT NULL
    )"""
    )
    conn.commit()
    conn.close()


_create_tables()


SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"


def _jwt_decode(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def _get_current_user_from_request(request: HttpRequest) -> dict:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        raise PermissionError("未登录")
    token = auth.split(" ", 1)[1]
    try:
        payload = _jwt_decode(token)
    except JWTError:
        raise PermissionError("Token无效或过期")
    jti = payload.get("jti")
    username = payload.get("sub")
    # revoked check
    if jti:
        conn = _get_db()
        r = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti=?", (jti,)).fetchone()
        conn.close()
        if r:
            raise PermissionError("Token 已被撤销")
    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not user:
        raise PermissionError("用户不存在")
    if not user["is_active"]:
        raise PermissionError("账号已冻结")
    payload["is_admin"] = bool(user["is_admin"])
    return payload


def _require_admin(payload: dict):
    if not payload.get("is_admin"):
        raise PermissionError("需要管理员权限")


@csrf_exempt
def register(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    data = json.loads(request.body or b"{}")
    username = data.get("username", "")
    password = data.get("password", "")
    if not username or not password:
        return JsonResponse({"error": "用户名或密码缺失"}, status=400)
    conn = _get_db()
    cur = conn.cursor()
    if cur.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        conn.close()
        return JsonResponse({"error": "用户名已存在"}, status=400)
    pw_hash = _hash_password(password)
    cur.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, pw_hash, int(time.time())),
    )
    conn.commit()
    conn.close()
    return JsonResponse({"success": True})


@csrf_exempt
def login(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    data = json.loads(request.body or b"{}")
    username = data.get("username", "")
    password = data.get("password", "")
    conn = _get_db()
    cur = conn.cursor()
    user = cur.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if (not user) or (user["password_hash"] != _hash_password(password)):
        conn.close()
        return JsonResponse({"error": "用户名或密码错误"}, status=401)
    if not user["is_active"]:
        conn.close()
        return JsonResponse({"error": "账号已冻结"}, status=403)
    jti = str(uuid.uuid4())
    now = int(time.time())
    payload = {
        "sub": user["username"],
        "is_admin": bool(user["is_admin"]),
        "iat": now,
        "jti": jti,
        "exp": now + 86400,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    conn.close()
    return JsonResponse({"token": token, "is_admin": bool(user["is_admin"]), "jti": jti})


@csrf_exempt
def admin_list_users(request: HttpRequest):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, username, is_admin, is_active, created_at FROM users"
    ).fetchall()
    conn.close()
    return JsonResponse({"users": [dict(r) for r in rows]})


def _count_admins(cur) -> int:
    r = cur.execute("SELECT COUNT(1) as c FROM users WHERE is_admin=1").fetchone()
    return int(r["c"]) if r else 0


def _log_admin_action(actor: str, action: str, target: Optional[str] = None):
    conn = _get_db()
    conn.execute(
        "INSERT INTO admin_audit (actor, action, target, created_at) VALUES (?, ?, ?, ?)",
        (actor, action, target, int(time.time())),
    )
    conn.commit()
    conn.close()


@csrf_exempt
def admin_promote(request: HttpRequest, username: str):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    _log_admin_action(user.get("sub"), "promote", username)
    return JsonResponse({"success": True})


@csrf_exempt
def admin_demote(request: HttpRequest, username: str):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    conn = _get_db()
    cur = conn.cursor()
    target = cur.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not target:
        conn.close()
        return JsonResponse({"error": "目标用户不存在"}, status=404)
    admins = _count_admins(cur)
    if target["is_admin"] and admins <= 1:
        conn.close()
        return JsonResponse({"error": "不能降级最后一个管理员"}, status=400)
    cur.execute("UPDATE users SET is_admin=0 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    _log_admin_action(user.get("sub"), "demote", username)
    return JsonResponse({"success": True})


@csrf_exempt
def admin_freeze(request: HttpRequest, username: str):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_active=0 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    _log_admin_action(user.get("sub"), "freeze", username)
    return JsonResponse({"success": True})


@csrf_exempt
def admin_unfreeze(request: HttpRequest, username: str):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_active=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    _log_admin_action(user.get("sub"), "unfreeze", username)
    return JsonResponse({"success": True})


@csrf_exempt
def admin_delete_user(request: HttpRequest, username: str):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    conn = _get_db()
    cur = conn.cursor()
    target = cur.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not target:
        conn.close()
        return JsonResponse({"error": "目标用户不存在"}, status=404)
    if target["is_admin"] and _count_admins(cur) <= 1:
        conn.close()
        return JsonResponse({"error": "不能删除最后一个管理员"}, status=400)
    cur.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    _log_admin_action(user.get("sub"), "delete_user", username)
    return JsonResponse({"success": True})


@csrf_exempt
def admin_revoke_token(request: HttpRequest):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    data = json.loads(request.body or b"{}")
    jti = data.get("jti")
    token = data.get("token")
    if not jti and token:
        try:
            payload = _jwt_decode(token)
            jti = payload.get("jti")
        except JWTError:
            return JsonResponse({"error": "提供的 token 无效"}, status=400)
    if not jti:
        return JsonResponse({"error": "需要提供 token 或 jti"}, status=400)
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO revoked_tokens (jti, revoked_at, revoked_by) VALUES (?, ?, ?)",
        (jti, int(time.time()), user.get("sub")),
    )
    conn.commit()
    conn.close()
    _log_admin_action(user.get("sub"), "revoke_token", jti)
    return JsonResponse({"success": True, "jti": jti})


@csrf_exempt
def admin_list_revoked(request: HttpRequest):
    try:
        user = _get_current_user_from_request(request)
        _require_admin(user)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, jti, revoked_at, revoked_by FROM revoked_tokens ORDER BY revoked_at DESC"
    ).fetchall()
    conn.close()
    return JsonResponse({"revoked": [dict(r) for r in rows]})


@csrf_exempt
def upload_file(request: HttpRequest):
    try:
        user = _get_current_user_from_request(request)
        if not user.get("is_admin"):
            return JsonResponse({"error": "无权限"}, status=403)
    except PermissionError as e:
        return JsonResponse({"error": str(e)}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    if "file" not in request.FILES:
        return JsonResponse({"error": "缺少文件"}, status=400)
    f = request.FILES["file"]
    # ensure project imports are configured
    _ensure_components()
    from src.config import get_settings as get_src_settings

    docs_root = get_src_settings().docs_root
    os.makedirs(docs_root, exist_ok=True)
    out_path = os.path.join(docs_root, f.name)
    with open(out_path, "wb") as dst:
        for chunk in f.chunks():
            dst.write(chunk)
    return JsonResponse({"success": True, "filename": f.name})


def root_page(request: HttpRequest):
    # Serve static/index.html if present (for parity with FastAPI root)
    idx = ROOT / "static" / "index.html"
    if idx.exists():
        return HttpResponse(idx.read_text(encoding="utf-8"))
    return HttpResponse("<html><body><h3>前端页面缺失: 请创建 static/index.html</h3></body></html>")
