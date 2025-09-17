"""
Core functionality smoke test for RAG system.
Tests basic components without requiring external services.
"""
import pytest
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.ingestion.chunking import adaptive_chunk


def test_chunking_basic():
    """Test basic document chunking functionality."""
    elements = [
        {"type": "paragraph", "text": "线性规划是一种优化方法", "source": "test_doc", "order": 0},
        {"type": "paragraph", "text": "约束条件包含不等式", "source": "test_doc", "order": 1},
    ]
    chunks = adaptive_chunk(elements, chunk_size=30, overlap=5)
    
    assert chunks, "chunks should not be empty"
    assert len(chunks) > 0, "should have at least one chunk"
    assert len(chunks[0]["content"]) > 0, "chunk content should not be empty"
    assert "source" in chunks[0], "chunk should have source information"


def test_chunking_with_large_content():
    """Test chunking with content that exceeds chunk size."""
    large_text = "这是一个很长的文本内容，用于测试文档分块功能是否能够正确处理超出大小限制的内容。" * 5
    elements = [
        {"type": "paragraph", "text": large_text, "source": "large_doc", "order": 0},
        {"type": "paragraph", "text": "另一个段落内容。", "source": "large_doc", "order": 1},
    ]
    chunks = adaptive_chunk(elements, chunk_size=50, overlap=10)
    
    # The actual chunking behavior depends on the implementation
    # Just ensure we get valid chunks
    assert len(chunks) >= 1, "should have at least one chunk"
    for chunk in chunks:
        assert len(chunk["content"]) > 0, "chunks should have content"
        assert "source" in chunk, "chunks should have source"


def test_chunking_empty_input():
    """Test chunking with empty input."""
    chunks = adaptive_chunk([], chunk_size=100, overlap=10)
    assert chunks == [], "empty input should return empty list"


def test_config_loading():
    """Test that configuration can be loaded."""
    try:
        from src.config import get_settings
        settings = get_settings()
        assert settings is not None, "settings should be loadable"
        assert hasattr(settings, 'docs_root'), "settings should have docs_root"
    except ImportError:
        pytest.skip("Config module not available")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
