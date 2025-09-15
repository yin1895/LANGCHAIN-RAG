import requests

#requests.post('http://127.0.0.1:8000/ingest')  添加了新文档再去用，一般是不需要动的

question = input("输入你的问题,/quit退出：")
while question!="/quit" :
    payload = {"question":question,"top_k":6,"bm25_weight":0.35}#权重越大越遵循文档注入的知识，这个也不用动
    r = requests.post('http://127.0.0.1:8000/ask', json=payload, timeout=600)
    data = r.json()
    print(data['answer'])
    for ctx in data['contexts']:
            print(ctx['score'], ctx['source'])