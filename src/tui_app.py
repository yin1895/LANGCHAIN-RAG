"""Textual TUI for the Math Modeling RAG system.

Features:
 - Sidebar actions: Ingest (incremental), Rebuild (delete & ingest), Ask
 - Question input box with live retrieval preview (top-k scores)
 - Answer panel streaming (chunked via async) – fallback to full once ready
 - Logs tail panel (reads metrics/log lines best-effort)

Note: Streaming of OpenRouter responses simulated by splitting paragraphs because
current OpenRouter wrapper here returns full text. Can enhance later.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Log, Static

# 兼容不同 Textual 版本: 若有 TextLog 用之，否则用 Log 作为替代
try:  # pragma: no cover
    from textual.widgets import TextLog  # type: ignore
except Exception:  # pragma: no cover
    TextLog = Log  # type: ignore

from .config import get_settings
from .ingestion.chunking import adaptive_chunk
from .ingestion.docx_parser import ingest_to_raw
from .rag.embeddings import OllamaEmbeddings
from .rag.llm import OpenRouterLLM
from .rag.retriever import Retriever
from .rag.vector_store import FaissStore, build_or_update


class StatusBar(Static):
    status = reactive("Ready")

    def watch_status(self, value: str):
        self.update(f"[b]{value}[/b]")


class RAGTUI(App):
    CSS_PATH = None
    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
        ("f5", "action_ingest", "Ingest"),
        ("f6", "action_rebuild", "Rebuild"),
    ]

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.embed = OllamaEmbeddings(self.settings.embed_model)
        self.store = FaissStore(
            self.settings.vector_store_path, self.settings.metadata_store_path, dim=None
        )
        self.retriever: Retriever | None = None
        if self.store._index is not None:
            self.retriever = Retriever(self.store, self.embed, k=6, bm25_weight=0.35)
        self.llm = OpenRouterLLM(self.settings.openrouter_api_key)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Horizontal(
                Container(
                    Static("操作", id="ops_title"),
                    Button("增量摄取(F5)", id="btn_ingest"),
                    Button("重建索引(F6)", id="btn_rebuild"),
                    Static("输入问题后回车检索+回答", id="hint"),
                    id="sidebar",
                ),
                Container(
                    Input(placeholder="请输入问题并回车", id="question"),
                    Label("Top-K 预览"),
                    DataTable(id="preview"),
                    id="main",
                ),
                Container(
                    Static("回答", id="answer_title"),
                    TextLog(id="answer_log"),
                    Static("日志", id="logs_title"),
                    TextLog(id="sys_log"),
                    id="right",
                ),
            ),
            id="root",
        )
        yield StatusBar(id="status")
        yield Footer()

    async def on_mount(self):
        table = self.query_one("#preview", DataTable)
        table.add_columns("Rank", "Score", "Source")
        self.set_status("就绪")
        # start log tail task
        self.call_later(self.tail_logs)

    def set_status(self, txt: str):
        self.query_one(StatusBar).status = txt

    async def tail_logs(self):
        """Tail metrics.jsonl or meta logs if exist (best-effort)."""
        log_widget = self.query_one("#sys_log", TextLog)
        metrics_file = Path("metrics.jsonl")
        pos = 0
        while True:
            try:
                if metrics_file.exists():
                    with metrics_file.open("r", encoding="utf-8") as f:
                        f.seek(pos)
                        for line in f:
                            log_widget.write(line.strip())
                        pos = f.tell()
            except Exception as e:
                log_widget.write(f"[ERR]{e}")
            await asyncio.sleep(2)

    async def action_ingest(self):
        await self.run_ingest(rebuild=False)

    async def action_rebuild(self):
        await self.run_ingest(rebuild=True)

    async def run_ingest(self, rebuild: bool):
        self.set_status("摄取中…")
        ans_log = self.query_one("#answer_log", TextLog)
        if rebuild:
            # delete existing index/meta
            try:
                if os.path.exists(self.settings.vector_store_path):
                    os.remove(self.settings.vector_store_path)
                if os.path.exists(self.settings.metadata_store_path):
                    os.remove(self.settings.metadata_store_path)
                self.store = FaissStore(
                    self.settings.vector_store_path, self.settings.metadata_store_path, dim=None
                )
            except Exception as e:
                ans_log.write(f"重建清理失败: {e}")
        start = time.time()
        raw = ingest_to_raw(self.settings.docs_root)
        chunks = adaptive_chunk(raw, self.settings.chunk_size, self.settings.chunk_overlap)
        added = build_or_update(chunks, self.store, self.embed)
        self.retriever = Retriever(self.store, self.embed, k=6, bm25_weight=0.35)
        self.set_status(f"摄取完成 added={added} 用时 {time.time()-start:.1f}s")
        ans_log.write(f"摄取完成 新增 {added} 向量")

    async def handle_question(self, q: str):
        if not q.strip():
            return
        if self.retriever is None:
            self.set_status("尚无索引, 请先摄取")
            return
        table = self.query_one("#preview", DataTable)
        table.clear()
        docs = self.retriever.get_relevant(q)
        for i, d in enumerate(docs):
            table.add_row(str(i + 1), f"{d['score']:.3f}", d["source"])
        self.set_status("调用 LLM 中…")
        ans_log = self.query_one("#answer_log", TextLog)
        ans_log.clear()
        try:
            full = await self.llm.acomplete(q, docs)
        except Exception as e:
            ans_log.write(f"LLM错误: {e}")
            self.set_status("LLM 调用失败")
            return
        # naive streaming simulation
        for part in full.split("\n\n"):
            ans_log.write(part)
            await asyncio.sleep(0.05)
        self.set_status("完成")

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "question":
            await self.handle_question(event.value)

    async def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn_ingest":
            await self.action_ingest()
        elif bid == "btn_rebuild":
            await self.action_rebuild()


def run():  # entrypoint
    RAGTUI().run()


if __name__ == "__main__":  # manual run
    run()
