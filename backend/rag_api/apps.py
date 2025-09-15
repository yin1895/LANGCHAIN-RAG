from django.apps import AppConfig
import os
from dotenv import load_dotenv
load_dotenv()


class RagApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rag_api"

    def ready(self):  # pragma: no cover
        # Optional warmup to improve first-request latency
        if os.environ.get("RAG_WARMUP", "1") != "1":
            return
        try:
            # Lazy import to avoid issues during migrations
            from pathlib import Path
            import sys
            ROOT = Path(__file__).resolve().parents[2]
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from src.config import get_settings as _get
            from src.rag.embeddings import OllamaEmbeddings
            from src.rag.vector_store import FaissStore
            from src.rag.llm import get_default_llm

            s = _get()
            embed = OllamaEmbeddings(s.embed_model)
            _ = embed.embed_documents(["warmup"])  # touch model
            _ = FaissStore(s.vector_store_path, s.metadata_store_path, dim=None)
            _ = get_default_llm()
        except Exception:
            # Warmup should never break startup
            pass
