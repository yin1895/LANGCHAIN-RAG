import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Button, Input, Card, Upload, message, Typography } from 'antd';
import { CloudUploadOutlined, SendOutlined, RobotOutlined, SettingOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';

const { Header, Content } = Layout;
const { Title, Text } = Typography;

// 系统信息
const APP_NAME = '数学建模 RAG 智能问答系统';
const APP_DESC = '基于已收集资料的数学建模专业问答助手';

export default function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [contexts, setContexts] = useState([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    // 检查 token 并解码 is_admin
    const token = localStorage.getItem('token');
    if (!token) return setIsAdmin(false);
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setIsAdmin(!!payload.is_admin);
    } catch {
      setIsAdmin(false);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAdmin(false);
    navigate('/login', { replace: true });
  };

  const goToLogin = () => {
    localStorage.removeItem('token');
    navigate('/login', { replace: true });
  };

  const goToRegister = () => {
    localStorage.removeItem('token');
    navigate('/register', { replace: true });
  };

  // Enhanced ask function with streaming support
  const handleAsk = async () => {
    if (!question.trim()) return;
    
    setLoading(true);
    setAnswer('');
    setStreamingAnswer('');
    setContexts([]);
    setIsStreaming(true);
    
    try {
      // Try streaming first
      const streamRes = await fetch('/api/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question, 
          include_content: true,
          top_k: 6,
          bm25_weight: 0.35
        })
      });
      
      if (streamRes.ok) {
        const reader = streamRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'contexts') {
                  setContexts(data.data || []);
                } else if (data.type === 'chunk') {
                  setStreamingAnswer(prev => prev + data.data);
                } else if (data.type === 'end') {
                  setIsStreaming(false);
                } else if (data.type === 'error') {
                  throw new Error(data.detail);
                }
              } catch (e) {
                console.warn('Failed to parse SSE data:', e);
              }
            }
          }
        }
        setAnswer(streamingAnswer);
      } else {
        // Fallback to regular ask
        throw new Error('Streaming not available');
      }
    } catch (e) {
      console.log('Streaming failed, using regular ask:', e);
      setIsStreaming(false);
      
      try {
        const res = await fetch('/api/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            question,
            include_content: true,
            top_k: 6,
            bm25_weight: 0.35
          })
        });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const data = await res.json();
        setAnswer(data.answer || '抱歉，暂时无法回答您的问题');
        setContexts(data.contexts || []);
      } catch (err) {
        setAnswer('请求失败，请检查网络连接后重试');
        message.error('网络请求失败');
      }
    }
    
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && e.ctrlKey && !loading) {
      handleAsk();
    }
  };

  const handleUpload = async (info) => {
    if (info.file.status === 'uploading') return;
    if (info.file.status === 'done') {
      message.success(`${info.file.name} 上传成功`);
    } else if (info.file.status === 'error') {
      message.error(`${info.file.name} 上传失败`);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <Header style={{ 
        background: 'rgba(255,255,255,0.95)', 
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px'
      }}>
        <Title level={3} style={{ margin: 0, color: '#1890ff' }}>
          <RobotOutlined style={{ marginRight: 8 }} />
          {APP_NAME}
        </Title>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {isAdmin && (
            <Button 
              icon={<SettingOutlined />} 
              onClick={() => navigate('/admin/users')}
              size="small"
            >
              管理
            </Button>
          )}
          {localStorage.getItem('token') ? (
            <Button size="small" onClick={handleLogout}>登出</Button>
          ) : (
            <div style={{ display: 'flex', gap: 8 }}>
              <Button size="small" onClick={goToLogin}>登录</Button>
              <Button size="small" type="primary" onClick={goToRegister}>注册</Button>
            </div>
          )}
        </div>
      </Header>
      
      <Content style={{ 
        padding: '32px 24px', 
        display: 'flex', 
        flexDirection: 'column',
        alignItems: 'center',
        gap: 24
      }}>
        <div style={{ textAlign: 'center', color: 'white', marginBottom: 16 }}>
          <Title level={2} style={{ color: 'white', marginBottom: 8 }}>
            数学建模智能问答助手
          </Title>
          <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 16 }}>
            {APP_DESC}
          </Text>
        </div>

        <div style={{ width: '100%', maxWidth: 1200, display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {/* 主问答区域 */}
          <Card style={{ 
            flex: 2, 
            minWidth: 600,
            borderRadius: 16,
            boxShadow: '0 8px 32px rgba(0,0,0,0.1)'
          }}>
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ fontSize: 16, color: '#1890ff' }}>
                <RobotOutlined style={{ marginRight: 8 }} />
                智能问答
              </Text>
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <Input.TextArea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="请输入您的数学建模问题...&#10;&#10;例如：如何选择合适的优化算法？&#10;线性规划模型的约束条件如何设置？&#10;&#10;按 Ctrl+Enter 快速提问"
                autoSize={{ minRows: 4, maxRows: 8 }}
                style={{ 
                  borderRadius: 8, 
                  fontSize: 14,
                  border: '2px solid #f0f0f0'
                }}
                disabled={loading}
              />
            </div>
            
            <div style={{ marginBottom: 24, textAlign: 'center' }}>
              <Button
                type="primary"
                size="large"
                icon={<SendOutlined />}
                onClick={handleAsk}
                loading={loading}
                disabled={!question.trim()}
                style={{ 
                  borderRadius: 8,
                  height: 48,
                  paddingLeft: 32,
                  paddingRight: 32,
                  fontSize: 16
                }}
              >
                {loading ? (isStreaming ? '智能分析中...' : '思考中...') : '提问'}
              </Button>
            </div>

            {/* 回答显示区域 */}
            {(answer || streamingAnswer || loading) && (
              <div style={{ 
                background: '#f8f9fa', 
                padding: 20,
                borderRadius: 12,
                border: '1px solid #e9ecef',
                minHeight: 120
              }}>
                <Text strong style={{ color: '#1890ff', marginBottom: 12, display: 'block' }}>
                  AI 回答：
                </Text>
                {loading && !streamingAnswer ? (
                  <div style={{ textAlign: 'center', color: '#999' }}>
                    正在分析您的问题...
                  </div>
                ) : (
                  <ReactMarkdown style={{ 
                    lineHeight: 1.6,
                    color: '#333'
                  }}>
                    {streamingAnswer || answer}
                  </ReactMarkdown>
                )}
                {isStreaming && (
                  <div style={{ 
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    background: '#1890ff',
                    borderRadius: '50%',
                    animation: 'pulse 1s infinite',
                    marginLeft: 4
                  }} />
                )}
              </div>
            )}
          </Card>

          {/* 侧边栏：文档上传和引用 */}
          <div style={{ flex: 1, minWidth: 320, display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* 文档上传区域（仅管理员可见） */}
            {isAdmin && (
              <Card style={{ borderRadius: 16, boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
                <Title level={5} style={{ marginBottom: 16, color: '#1890ff' }}>
                  <CloudUploadOutlined style={{ marginRight: 8 }} />
                  文档上传
                </Title>
                <Upload.Dragger
                  name="file"
                  action="/api/upload"
                  headers={{ Authorization: 'Bearer ' + (localStorage.getItem('token') || '') }}
                  onChange={handleUpload}
                  multiple
                  style={{ borderRadius: 8 }}
                >
                  <p className="ant-upload-drag-icon">
                    <CloudUploadOutlined style={{ fontSize: 32, color: '#1890ff' }} />
                  </p>
                  <p className="ant-upload-text">点击或拖拽上传文档</p>
                  <p className="ant-upload-hint" style={{ color: '#999' }}>
                    支持 PDF、Word、TXT 格式
                  </p>
                </Upload.Dragger>
              </Card>
            )}

            {/* 参考资料显示 */}
            {contexts.length > 0 && (
              <Card style={{ borderRadius: 16, boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
                <Title level={5} style={{ marginBottom: 16, color: '#1890ff' }}>
                  参考资料
                </Title>
                <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                  {contexts.map((ctx, i) => (
                    <div key={i} style={{ 
                      marginBottom: 12,
                      padding: 12,
                      background: '#f8f9fa',
                      borderRadius: 8,
                      border: '1px solid #e9ecef'
                    }}>
                      <Text strong style={{ color: '#666', fontSize: 12 }}>
                        来源: {ctx.source || '未知'}
                      </Text>
                      {ctx.content && (
                        <div style={{ 
                          marginTop: 8,
                          fontSize: 13,
                          lineHeight: 1.5,
                          color: '#555'
                        }}>
                          {ctx.content.length > 200 
                            ? ctx.content.substring(0, 200) + '...'
                            : ctx.content
                          }
                        </div>
                      )}
                      <Text style={{ color: '#999', fontSize: 11 }}>
                        相关度: {(ctx.score * 100).toFixed(1)}%
                      </Text>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        </div>
      </Content>
    </Layout>
  );
}