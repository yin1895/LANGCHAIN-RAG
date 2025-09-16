import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))
import tempfile  # noqa: E402

from django.test.client import RequestFactory  # noqa: E402

from backend.rag_api import views  # noqa: E402

# Ensure docs root is an empty temp dir to make ingest quick
tmpd = tempfile.mkdtemp()
os.environ["DOCS_ROOT"] = tmpd

rf = RequestFactory()
req = rf.post("/api/ingest")
resp = views.ingest(req)
print("ingest resp:", resp.content)
import json  # noqa: E402

job = json.loads(resp.content)
job_id = job.get("job_id")
print("job_id", job_id)

# poll status
for i in range(20):
    st = views.ingest_status(req, job_id)
    info = json.loads(st.content)
    print(i, info)
    if info.get("status") in ("finished", "error"):
        break
    time.sleep(1)
