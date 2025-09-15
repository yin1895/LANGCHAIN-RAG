import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import get_settings
from ..ingestion.chunking import adaptive_chunk
from ..ingestion.docx_parser import ingest_to_raw
from ..logging_utils import emit_metric, get_logger, span
from ..rag.embeddings import OllamaEmbeddings
from ..rag.llm import get_default_llm
from ..rag.retriever import Retriever
from ..rag.vector_store import FaissStore, build_or_update
from .auth import get_current_user
from .auth import router as auth_router

logger = get_logger("api")

app = FastAPI(title="Math Modeling RAG")
api_router = APIRouter()

# --- 全局单例缓存 ---
GLOBAL: dict[str, object] = {}


@app.on_event("startup")
async def _startup_init():  # pragma: no cover
    # Load environment variables here (avoid side-effects at import time)
    load_dotenv()
    settings = get_settings()
    logger.info("startup: initializing global embeddings/store/llm")
    embed = OllamaEmbeddings(settings.embed_model)
    store = FaissStore(settings.vector_store_path, settings.metadata_store_path, dim=None)
    llm = get_default_llm()
    GLOBAL["embed"] = embed
    GLOBAL["store"] = store
    GLOBAL["llm"] = llm
    # 预热 embedding 与轻量检索
    try:
        _ = embed.embed_documents(["warmup"])[0]
    except Exception as e:
        logger.warning(f"warmup embedding failed: {e}")
    # 如果已有索引, 做一次空检索以加载内存结构
    if getattr(store, "_index", None) is not None:
        try:
            # 构造一个假向量快速遍历内部代码路径（若需要）
            pass
        except Exception:  # pragma: no cover
            pass
    logger.info("startup: warmup complete")


# 挂载静态资源目录 (简单前端页面)
static_dir = Path(__file__).resolve().parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root_page():
    """简单交互页面: 若 static/index.html 存在则返回文件内容, 否则给出占位提示。"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return HTMLResponse("<html><body><h3>前端页面缺失: 请创建 static/index.html</h3></body></html>")


class AskRequest(BaseModel):
    question: str
    top_k: int | None = 6
    bm25_weight: float | None = 0.35
    include_content: bool | None = False


@api_router.get("/health")
async def health():
    return {"status": "ok"}


@api_router.post("/ingest")
async def ingest(settings=Depends(get_settings)):
    with span("api_ingest", logger):
        raw = ingest_to_raw(settings.docs_root)
        chunks = adaptive_chunk(raw, settings.chunk_size, settings.chunk_overlap)
        embed: OllamaEmbeddings = GLOBAL.get("embed") or OllamaEmbeddings(settings.embed_model)
        store: FaissStore = GLOBAL.get("store") or FaissStore(
            settings.vector_store_path, settings.metadata_store_path, dim=None
        )
        added = build_or_update(chunks, store, embed)
        GLOBAL["embed"] = embed
        GLOBAL["store"] = store
        logger.info(f"ingest raw={len(raw)} chunks={len(chunks)} added={added}")
        emit_metric("api_ingest", raw=len(raw), chunks=len(chunks), added=added)
        return {"raw_items": len(raw), "chunks": len(chunks), "added": added}


@api_router.post("/ask")
async def ask(req: AskRequest, settings=Depends(get_settings)):
    with span("api_ask", logger, top_k=req.top_k):
        embed: OllamaEmbeddings = GLOBAL.get("embed")  # type: ignore
        store: FaissStore = GLOBAL.get("store")  # type: ignore
        if embed is None:
            embed = OllamaEmbeddings(settings.embed_model)
            GLOBAL["embed"] = embed
        if store is None:
            store = FaissStore(settings.vector_store_path, settings.metadata_store_path, dim=None)
            GLOBAL["store"] = store
        retriever = Retriever(store, embed, k=req.top_k or 6, bm25_weight=req.bm25_weight or 0.35)
        llm = GLOBAL.get("llm")  # type: ignore
        if llm is None:
            llm = get_default_llm()
            GLOBAL["llm"] = llm
        docs = retriever.get_relevant(req.question)
        answer = await llm.acomplete(req.question, docs)
        logger.info(
            f"ask q_len={len(req.question)} hits={len(docs)} top_score={(docs[0]['score'] if docs else None)}"
        )
        emit_metric("api_ask", q_len=len(req.question), hits=len(docs))
        contexts = []
        for d in docs:
            item = {"score": d["score"], "source": d["source"], "hash": d["hash"]}
            if req.include_content and "content" in d:
                c = d["content"]
                if len(c) > 2000:
                    c = c[:2000] + "..."
                item["content"] = c
            contexts.append(item)
        return {"answer": answer, "contexts": contexts}


@api_router.post("/ask/stream")
async def ask_stream(req: AskRequest, settings=Depends(get_settings)):
    """SSE-like streaming of answer tokens (markdown chunks)."""
    embed: OllamaEmbeddings = GLOBAL.get("embed")  # type: ignore
    store: FaissStore = GLOBAL.get("store")  # type: ignore
    if embed is None:
        embed = OllamaEmbeddings(settings.embed_model)
        GLOBAL["embed"] = embed
    if store is None:
        store = FaissStore(settings.vector_store_path, settings.metadata_store_path, dim=None)
        GLOBAL["store"] = store
    retriever = Retriever(store, embed, k=req.top_k or 6, bm25_weight=req.bm25_weight or 0.35)
    llm = GLOBAL.get("llm")  # type: ignore
    if llm is None:
        llm = get_default_llm()
        GLOBAL["llm"] = llm
    docs = retriever.get_relevant(req.question)

    async def event_gen():
        base_contexts = []
        for d in docs:
            item = {"score": d["score"], "source": d["source"], "hash": d["hash"]}
            if req.include_content and "content" in d:
                c = d["content"]
                if len(c) > 2000:
                    c = c[:2000] + "..."
                item["content"] = c
            base_contexts.append(item)
        yield f"data: {json.dumps({'type':'contexts','data': base_contexts}, ensure_ascii=False)}\n\n"
        async for chunk in llm.astream(req.question, docs):
            yield f"data: {json.dumps({'type':'chunk','data': chunk}, ensure_ascii=False)}\n\n"
        yield 'data: {"type":"end"}\n\n'

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@api_router.post("/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(403, "无权限")
    docs_root = get_settings().docs_root
    os.makedirs(docs_root, exist_ok=True)
    file_path = os.path.join(docs_root, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"success": True, "filename": file.filename}


app.include_router(auth_router, prefix="/api")
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
