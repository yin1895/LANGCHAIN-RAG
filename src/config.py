import os
import os.path
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 自动加载根目录下 .env
load_dotenv()


class Settings(BaseModel):
    openrouter_api_key: str = Field(
        default_factory=lambda: (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENROUTER_KEY")
            or os.getenv("OPENROUTER_TOKEN")
            or ""
        )
    )
    docs_root: str = Field(
        default_factory=lambda: os.path.abspath(os.getenv("DOCS_ROOT", "./docs"))
    )
    vector_store_path: str = Field(
        default_factory=lambda: os.getenv("VECTOR_STORE_PATH", "vector_store/index.faiss")
    )
    metadata_store_path: str = Field(
        default_factory=lambda: os.getenv("METADATA_STORE_PATH", "vector_store/meta.jsonl")
    )
    embed_model: str = Field(
        default_factory=lambda: os.getenv("EMBED_MODEL", "nomic-embed-text:v1.5")
    )
    chunk_size: int = Field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1200")))
    chunk_overlap: int = Field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "120")))
    max_pdf_mb: int = Field(
        default_factory=lambda: int(os.getenv("MAX_PDF_MB", "25"))
    )  # 超过则跳过解析
    low_pdf_text_ratio: float = Field(
        default_factory=lambda: float(os.getenv("LOW_PDF_TEXT_RATIO", "0.02"))
    )  # 文本字节/文件字节 低于判定为扫描版


@lru_cache
def get_settings() -> Settings:
    return Settings()
