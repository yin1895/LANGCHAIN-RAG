import React, { useState, useEffect } from 'react';
import { Card, Input, List, Typography, Spin, message } from 'antd';

const { Title, Text } = Typography;

export default function DocumentSearch() {
  const [docs, setDocs] = useState([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    fetch('/api/docs')
      .then(res => res.json())
      .then(data => { if (mounted) setDocs(data.docs || []) })
      .catch(() => { if (mounted) setDocs([]) });
    return ()=>{ mounted = false }
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
  setResults(data.results || []);
    } catch (e) {
  message.error('检索失败，请稍后重试');
    }
    setLoading(false);
  };

  return (
    <Card style={{ maxWidth: 800, margin: '32px auto', borderRadius: 16, background: '#F5F7FA' }}>
      <Title level={4}>文档检索</Title>
      <List
        header={<Text strong>已上传文档</Text>}
        dataSource={docs}
        locale={{ emptyText: '暂无上传文档' }}
        renderItem={item => <List.Item>{item.name}</List.Item>}
        style={{ marginBottom: 24 }}
      />
      <Input.Search
        value={query}
        onChange={e => setQuery(e.target.value)}
        onSearch={handleSearch}
        placeholder="请输入检索内容..."
        enterButton="检索"
        size="large"
        style={{ marginBottom: 24 }}
        loading={loading}
      />
    {loading ? <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div> : (
        <List
          header={<Text strong>检索结果</Text>}
          dataSource={results}
      locale={{ emptyText: query ? '未找到匹配结果' : '请输入检索内容后点击检索' }}
      renderItem={item => (
            <List.Item>
              <Card style={{ width: '100%', background: '#fff', borderRadius: 12 }}>
                <Text mark>{item.highlight || item.content}</Text>
                <div style={{ marginTop: 8, color: '#7C4DFF' }}>文档：{item.doc_name}</div>
              </Card>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
