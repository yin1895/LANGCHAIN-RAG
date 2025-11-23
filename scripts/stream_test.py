import requests

url = "http://127.0.0.1:9000/api/ask/stream"
headers = {"Content-Type": "application/json"}
body = {"question": "测试问题：请简单回答 '你好'", "top_k": 3}

print("POST", url)
with requests.post(url, json=body, headers=headers, stream=True, timeout=120) as r:
    print("status", r.status_code)
    try:
        for line in r.iter_lines(decode_unicode=True):
            if line:
                print("LINE:", line)
    except Exception as e:
        print("stream error", e)
    print("done")
