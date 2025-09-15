import pytest
from src.ingestion.chunking import adaptive_chunk

def test_chunking_basic():
    elements = [
        {'type':'paragraph','text':'线性规划是一种优化方法','source':'x','order':0},
        {'type':'paragraph','text':'约束条件包含不等式','source':'x','order':1},
    ]
    chunks = adaptive_chunk(elements, chunk_size=30, overlap=5)
    assert chunks, 'chunks should not be empty'
    assert len(chunks[0]['content'])>0

if __name__ == '__main__':
    pytest.main([__file__])
