import sys, os, time
sys.path.insert(0, os.path.abspath('.'))
from backend.rag_api import views
from django.test.client import RequestFactory
import tempfile

# Ensure docs root is an empty temp dir to make ingest quick
tmpd = tempfile.mkdtemp()
os.environ['DOCS_ROOT'] = tmpd

rf = RequestFactory()
req = rf.post('/api/ingest')
resp = views.ingest(req)
print('ingest resp:', resp.content)
import json
job = json.loads(resp.content)
job_id = job.get('job_id')
print('job_id', job_id)

# poll status
for i in range(20):
    st = views.ingest_status(req, job_id)
    info = json.loads(st.content)
    print(i, info)
    if info.get('status') in ('finished','error'):
        break
    time.sleep(1)
