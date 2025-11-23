import sys

import requests

url = "http://127.0.0.1:9000/api/health"
try:
    r = requests.get(url, timeout=5)
    print("STATUS", r.status_code)
    print("CONTENT-TYPE", r.headers.get("content-type"))
    print("BODY_SNIPPET")
    print(r.text[:1000])
except Exception as e:
    print("ERROR", type(e).__name__, e)
    sys.exit(2)
