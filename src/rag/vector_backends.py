"""Pluggable adapters for different vector backends.

This file provides a small adapter interface and a Milvus placeholder implementation.
Use these adapters to migrate from local FAISS to a remote vector DB.
"""

from typing import Dict, List


class VectorBackend:
    def add(self, ids: List[str], vectors: List[List[float]], metas: List[Dict]):
        raise NotImplementedError()

    def search(self, vector: List[float], k: int) -> List[Dict]:
        raise NotImplementedError()


class MilvusBackend(VectorBackend):
    def __init__(self, uri: str, collection: str = "default"):
        # Placeholder: real implementation requires pymilvus and server
        self.uri = uri
        self.collection = collection

    def add(self, ids: List[str], vectors: List[List[float]], metas: List[Dict]):
        # Implement actual Milvus insert logic here
        raise NotImplementedError("Milvus adapter not implemented in this placeholder")

    def search(self, vector: List[float], k: int) -> List[Dict]:
        raise NotImplementedError("Milvus adapter not implemented in this placeholder")
