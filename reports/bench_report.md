# Benchmark Report

Date: 2025-09-16

Summary of latest retrieval benchmarks (after caching and prometheus instrumentation changes):

- vector-only no-cache mean(ms): 0.4478750008274801
- vector-only with-cache mean(ms): 0.4546675001620315
- hybrid no-cache mean(ms): 1.9265066664956976
- hybrid with-cache mean(ms): 0.18513666655053385

Notes:
- Hybrid retrieval benefits significantly from local caching in this single-process setup.
- For multi-process deployments, consider a shared cache (Redis) or a remote vector database to avoid cache duplication.

Next steps:
- Prometheus metrics centralization and Grafana dashboard.
- Persist ingest job metadata in Redis and wire Celery reliably for background ingestion.
- Migrate vectors to Milvus/Weaviate and validate end-to-end latencies.
