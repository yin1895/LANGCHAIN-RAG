import requests

url = "http://127.0.0.1:9000/api/ask/stream"
print("POST", url)
# increase timeout to allow long LLM/embedding calls
r = requests.post(url, json={"question": "测试"}, stream=True, timeout=120)
print("status", r.status_code, "encoding", r.encoding)
count = 0
try:
    for chunk in r.iter_content(chunk_size=4096):
        if not chunk:
            continue
        # print raw bytes repr for debugging encoding/SSE framing
        print("RAW:", repr(chunk))
        count += 1
        if count > 10:
            break
finally:
    try:
        r.close()
    except Exception:
        pass
