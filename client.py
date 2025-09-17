import requests

# Simple CLI client for testing the RAG API
# Usage: python client.py

def main():
    base_url = "http://127.0.0.1:9000/api"
    
    print("RAG问答系统测试客户端")
    print("输入 '/ingest' 重新索引文档")
    print("输入 '/quit' 退出")
    print("-" * 40)
    
    while True:
        question = input("\n请输入问题: ")
        
        if question == "/quit":
            break
        elif question == "/ingest":
            try:
                r = requests.post(f"{base_url}/ingest", timeout=300)
                if r.status_code == 200:
                    print("✅ 文档索引更新成功")
                else:
                    print(f"❌ 索引失败: {r.status_code}")
            except requests.RequestException as e:
                print(f"❌ 请求失败: {e}")
            continue
        
        if not question.strip():
            continue
            
        try:
            payload = {
                "question": question,
                "top_k": 6,
                "bm25_weight": 0.35,
                "include_content": True
            }
            
            r = requests.post(f"{base_url}/ask", json=payload, timeout=600)
            if r.status_code == 200:
                data = r.json()
                print(f"\n🤖 回答:\n{data['answer']}")
                
                if data.get('contexts'):
                    print(f"\n📚 参考资料 ({len(data['contexts'])}条):")
                    for i, ctx in enumerate(data['contexts'][:3], 1):
                        print(f"{i}. {ctx['source']} (相关度: {ctx['score']:.3f})")
            else:
                print(f"❌ 请求失败: {r.status_code}")
                
        except requests.RequestException as e:
            print(f"❌ 连接失败: {e}")
            print("请确保后端服务正在运行 (python -m uvicorn rag_backend.asgi:application --port 9000)")

if __name__ == "__main__":
    main()
