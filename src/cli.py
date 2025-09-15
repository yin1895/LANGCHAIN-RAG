import argparse
import asyncio
import json
import os
import sys
from typing import List, Dict
from dotenv import load_dotenv

from .config import get_settings
from .ingestion.docx_parser import ingest_to_raw, list_docx_paths, ingest_files, PARSER_VERSION
from .ingestion.chunking import adaptive_chunk
from .rag.embeddings import OllamaEmbeddings
from .rag.vector_store import FaissStore, build_or_update
from .rag.retriever import Retriever
from .rag.llm import get_default_llm, BaseLLM
from tenacity import retry, stop_after_attempt, wait_exponential
from importlib import import_module


def cmd_ingest(args) -> int:
    settings = get_settings()
    if args.root:
        settings.docs_root = args.root  # type: ignore
    print(f"[INGEST] 指定目录: {settings.docs_root}")
    # rebuild: 删除旧索引文件
    if getattr(args, 'rebuild', False):
        vs = [settings.vector_store_path, settings.metadata_store_path]
        removed = []
        for p in vs:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    removed.append(p)
                except Exception as e:
                    print(f"[INGEST] 重建清理失败 {p}: {e}", file=sys.stderr)
        if removed:
            print(f"[INGEST] 已删除旧索引文件: {removed}")
    # Show resolved path & docx count
    from pathlib import Path
    root_path = Path(settings.docs_root)
    if not root_path.is_absolute():
        proj_root = Path(__file__).resolve().parents[2]
        candidate = proj_root / settings.docs_root
        if candidate.exists():
            root_path = candidate
    print(f"[INGEST] 解析后绝对路径: {root_path}")
    files = list_docx_paths(root_path)
    if args.limit_files and args.limit_files > 0:
        files = files[: args.limit_files]
        print(f"[INGEST] 仅处理前 {len(files)} 个文件 (受 --limit-files 限制)")
    print(f"[INGEST] 发现 docx 文件数量: {len(files)}")
    if files[:5]:
        for i, p in enumerate(files[:5]):
            print(f"  - 文件[{i}]: {p.relative_to(root_path)}")
    if not files:
        print('[INGEST] 未发现任何 docx 文件，请检查目录名称/编码。')
    if args.limit_files:
        raw = ingest_files(files, max_pdf_mb=settings.max_pdf_mb, low_pdf_text_ratio=settings.low_pdf_text_ratio)
    else:
        raw = ingest_to_raw(str(root_path), max_pdf_mb=settings.max_pdf_mb, low_pdf_text_ratio=settings.low_pdf_text_ratio)
    print(f"[INGEST] 原始元素数量: {len(raw)}")
    print(f"[INGEST] 解析版本: {PARSER_VERSION}")
    # --- 解析统计增强 ---
    try:
        from collections import Counter
        type_counter = Counter(r.get('type','?') for r in raw)
        para_total = type_counter.get('paragraph', 0)
        table_total = type_counter.get('table', 0)
        error_total = type_counter.get('error', 0)
        math_paras = 0
        placeholder_paras = 0
        pdf_paras = 0
        for r in raw:
            if r.get('type') == 'paragraph':
                txt = r.get('text','')
                if '$ ' in txt or '\\frac' in txt or '\\sqrt' in txt:
                    math_paras += 1
                if '/*math*/' in txt:
                    placeholder_paras += 1
                if r.get('origin') == 'pdf':
                    pdf_paras += 1
        docx_paras = para_total - pdf_paras
        if para_total:
            print(f"[INGEST][STAT] 段落: total={para_total} docx={docx_paras} pdf={pdf_paras} math={math_paras} placeholder={placeholder_paras}")
        if table_total:
            print(f"[INGEST][STAT] 表格: total={table_total}")
        if error_total:
            print(f"[INGEST][STAT] 解析错误: total={error_total}")
            # 列出前 3 个错误样例
            shown = 0
            for r in raw:
                if r.get('type') == 'error':
                    print(f"[INGEST][STAT][ERROR] source={r.get('source')} error={r.get('error')}")
                    shown += 1
                    if shown >= 3:
                        break
        # 估计解析覆盖率： (para_total - placeholder_paras) / para_total
        if para_total:
            covered = para_total - placeholder_paras
            coverage = covered / para_total
            print(f"[INGEST][STAT] 公式解析覆盖率≈{coverage:.2%} (占位段落 {placeholder_paras})")
            if coverage < 0.7:
                print("[INGEST][WARN] 覆盖率低 (<70%)，建议扩展 OMML 解析。")
    except Exception as e:  # pragma: no cover
        print(f"[INGEST][STAT] 统计过程异常: {e}")
    if getattr(args, 'sample', 0):
        print(f"[INGEST] 展示前 {args.sample} 个元素简要：")
        for i, r in enumerate(raw[: args.sample]):
            preview = ''
            if r.get('type') == 'paragraph':
                preview = r.get('text','')[:80]
            elif r.get('type') == 'table':
                rows = r.get('rows', [])
                preview = f"table rows={len(rows)} cols={len(rows[0]) if rows else 0}"
            elif r.get('type') == 'error':
                preview = f"ERROR: {r.get('error')}"
            print(f"  #{i} type={r.get('type')} len={len(r.get('text','')) if 'text' in r else 0} {preview}")
        # Count error types
        err_count = sum(1 for r in raw if r.get('type')=='error')
        if err_count:
            print(f"[INGEST] 共有 {err_count} 个解析错误元素。")
    chunks = adaptive_chunk(raw, settings.chunk_size, settings.chunk_overlap)
    print(f"[INGEST] 分块数量: {len(chunks)} (chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap})")
    embed = OllamaEmbeddings(settings.embed_model)
    store = FaissStore(settings.vector_store_path, settings.metadata_store_path, dim=None)
    added = build_or_update(chunks, store, embed)
    print(f"[INGEST] 新增写入向量: {added} (可能已跳过部分失败项)")
    return 0


def format_contexts(ctxs: List[Dict], limit: int = 220) -> str:
    lines = []
    for i, c in enumerate(ctxs, 1):
        snippet = c.get('content', '')
        if len(snippet) > limit:
            snippet = snippet[:limit] + '…'
        lines.append(f"[ref {i} | score={c.get('score'):.3f}] {c.get('source')}\n  {snippet.replace('\n',' ')}")
    return '\n'.join(lines)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _call_llm(llm: BaseLLM, question: str, docs: List[Dict]):
    return await llm.acomplete(question, docs)


async def async_answer(question: str, top_k: int, show_ctx: bool, json_out: bool, bm25_weight: float):
    settings = get_settings()
    embed = OllamaEmbeddings(settings.embed_model)
    store = FaissStore(settings.vector_store_path, settings.metadata_store_path, dim=None)
    if store._index is None:
        print('[ASK] 未找到向量索引，请先运行 ingest 命令。', file=sys.stderr)
        return 2
    retriever = Retriever(store, embed, k=top_k, bm25_weight=bm25_weight)
    docs = retriever.get_relevant(question)
    llm = get_default_llm()
    answer = await _call_llm(llm, question, docs)
    if json_out:
        payload = {
            'question': question,
            'answer': answer,
            'contexts': [
                {
                    'ref': i + 1,
                    'score': d['score'],
                    'source': d['source'],
                    'hash': d['hash']
                } for i, d in enumerate(docs)
            ]
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print('================= ANSWER =================')
        print(answer)
        if show_ctx:
            print('\n================= CONTEXTS =================')
            print(format_contexts(docs))
    return 0


def cmd_ask(args) -> int:
    questions: List[str] = []
    if args.file:
        if not os.path.exists(args.file):
            print(f"问题文件不存在: {args.file}", file=sys.stderr)
            return 1
        with open(args.file, 'r', encoding='utf-8') as f:
            for line in f:
                q = line.strip()
                if q:
                    questions.append(q)
    if args.question:
        questions.append(args.question)
    if not questions:
        print('需要 --question 或 --file', file=sys.stderr)
        return 1
    exit_code = 0
    for idx, q in enumerate(questions, 1):
        if len(questions) > 1:
            print(f"\n### 问题 {idx}/{len(questions)}: {q}")
        exit_code = asyncio.run(async_answer(q, args.top_k, args.show_context, args.json, args.bm25_weight))
        if exit_code != 0:
            break
    return exit_code


def cmd_repl(args) -> int:
    print('进入交互模式，输入 /exit 退出，/help 查看命令。')
    settings = get_settings()
    embed = OllamaEmbeddings(settings.embed_model)
    store = FaissStore(settings.vector_store_path, settings.metadata_store_path, dim=None)
    if store._index is None:
        print('未找到向量索引，请先运行: python -m src.cli ingest')
        return 1
    retriever = Retriever(store, embed, k=args.top_k, bm25_weight=args.bm25_weight)
    llm = get_default_llm()
    history: List[Dict] = []  # optional future use
    while True:
        try:
            q = input('\n问> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n退出。')
            break
        if not q:
            continue
        if q in ('/exit', '/quit'):
            break
        if q == '/help':
            print('命令: /exit 退出 /ctx 显示上次检索片段 /help 帮助')
            continue
        if q == '/ctx':
            if history:
                print(history[-1]['contexts'])
            else:
                print('无历史。')
            continue
        # normal question
        docs = retriever.get_relevant(q)
        answer = asyncio.run(_call_llm(llm, q, docs))
        print('\n答>')
        print(answer)
        if args.show_context:
            from pprint import pprint
            print('\n片段:')
            pprint([{'score': d['score'], 'source': d['source'][:80], 'hash': d['hash']} for d in docs])
        history.append({'q': q, 'answer': answer, 'contexts': docs})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='数学建模 RAG CLI')
    sub = p.add_subparsers(dest='command')

    pin = sub.add_parser('ingest', help='摄取(或增量更新)全部文档')
    pin.add_argument('--root', help='覆盖文档根目录')
    pin.add_argument('--sample', type=int, default=0, help='打印前N个原始解析元素以调试')
    pin.add_argument('--limit-files', type=int, default=0, help='仅处理前N个docx文件用于调试或快速构建索引')
    pin.add_argument('--rebuild', action='store_true', help='先删除旧索引文件再全量重建')
    pin.set_defaults(func=cmd_ingest)

    pask = sub.add_parser('ask', help='提问')
    pask.add_argument('-q', '--question', help='单个问题')
    pask.add_argument('-f', '--file', help='批量问题文件, 每行一个')
    pask.add_argument('-k', '--top-k', type=int, default=6, help='检索条数')
    pask.add_argument('--show-context', action='store_true', help='显示引用上下文')
    pask.add_argument('--bm25-weight', type=float, default=0.35, help='BM25混合权重[0-1]')
    pask.add_argument('--json', action='store_true', help='JSON 输出')
    pask.set_defaults(func=cmd_ask)

    prepl = sub.add_parser('repl', help='交互式多轮问答')
    prepl.add_argument('-k', '--top-k', type=int, default=6)
    prepl.add_argument('--bm25-weight', type=float, default=0.35)
    prepl.add_argument('--show-context', action='store_true')
    prepl.set_defaults(func=cmd_repl)

    ptui = sub.add_parser('tui', help='终端图形界面 (Textual)')
    def _cmd_tui(_):
        try:
            app_mod = import_module('src.tui_app')
        except ModuleNotFoundError:
            print('需要先安装 textual: pip install textual rich', file=sys.stderr)
            return 1
        return app_mod.run()
    ptui.set_defaults(func=_cmd_tui)

    return p


def main(argv=None):
    # Load environment variables at runtime (avoid import-time side-effects)
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, 'command', None):
        parser.print_help()
        return 0
    return args.func(args)  # type: ignore


if __name__ == '__main__':
    raise SystemExit(main())
