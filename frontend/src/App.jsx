import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Menu, Button, Input, Card, Upload, message, Typography, Switch } from 'antd';
import { CloudUploadOutlined, SendOutlined, RobotOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';

const { Header, Content, Footer } = Layout;
const { Title } = Typography;

// 系统静态信息
const APP_NAME = '数学建模RAG chat system By Yin';
const APP_DESC = '针对已收集的资料强化在数模领域的能力';
const COPYRIGHT = '©2025 Powered by LangChain';
const CONTACT = 'For Yin and Gc team';

export default function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [theme, setTheme] = useState('light');
  const [contexts, setContexts] = useState([]);
  const [debugLog, setDebugLog] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);

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
  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setAnswer('');
    setContexts([]);
    setDebugLog('');
    try {
      const res = await fetch(`/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });
      const data = await res.json();
      setAnswer(data.answer || '无回复');
      setContexts(data.contexts || []);
      setDebugLog(logLine('ASK ok'));
    } catch (e) {
      setAnswer('请求失败，请稍后重试');
      setDebugLog(logLine('ASK error ' + e));
    }
    setLoading(false);
  };

  function logLine(line) {
    const ts = new Date().toISOString().split('T')[1].replace('Z','');
    return `[${ts}] ${line}\n`;
  }

  const handleUpload = async (info) => {
    if (info.file.status === 'uploading') return;
    if (info.file.status === 'done') {
      message.success(`${info.file.name} 上传成功`);
    } else if (info.file.status === 'error') {
      message.error(`${info.file.name} 上传失败`);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh', background: theme==='dark' ? 'linear-gradient(135deg,#232946 0%,#7C4DFF 100%)' : 'linear-gradient(135deg,#1A237E 0%,#7C4DFF 100%)' }}>
      <Header style={{ background: 'rgba(255,255,255,0.95)', boxShadow: '0 2px 8px #f0f1f2' }}>
          <Menu mode="horizontal" theme="light" defaultSelectedKeys={['home']} style={{ fontWeight: 500 }}>
          <Menu.Item key="home">{APP_NAME}</Menu.Item>
          <Menu.Item key="upload" icon={<CloudUploadOutlined />}>文档上传</Menu.Item>
          <Menu.Item key="settings">设置</Menu.Item>
          {isAdmin && <Menu.Item key="admin"><a href="/admin/users">用户管理</a></Menu.Item>}
          <div style={{ float: 'right', marginLeft: 24, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Switch checkedChildren="暗" unCheckedChildren="亮" checked={theme==='dark'} onChange={v=>setTheme(v?'dark':'light')} />
            {/* 如果已登录，显示登出；否则显示登录/注册快捷入口（点击会先清除本地 token） */}
            {localStorage.getItem('token') ? (
              <Button size="small" onClick={handleLogout}>登出</Button>
            ) : (
              <div>
                <Button size="small" onClick={goToLogin} style={{ marginRight: 6 }}>登录</Button>
                <Button size="small" onClick={goToRegister}>注册</Button>
              </div>
            )}
          </div>
        </Menu>
      </Header>
      <Content style={{ padding: '48px 16px', display: 'flex', gap: 32 }}>
        {isAdmin ? (
          <Card style={{ flex: 1, minWidth: 320, maxWidth: 400, background: '#F5F7FA', borderRadius: 16 }}>
            <Title level={4} style={{ marginBottom: 16 }}>文档上传（仅管理员）</Title>
            <Upload.Dragger
              name="file"
              action="/api/upload"
              headers={{ Authorization: 'Bearer ' + (localStorage.getItem('token') || '') }}
              onChange={handleUpload}
              multiple
            >
              <p className="ant-upload-drag-icon">
                <CloudUploadOutlined style={{ fontSize: 32, color: '#7C4DFF' }} />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此上传</p>
              <p className="ant-upload-hint">支持 PDF、Word、TXT 等格式</p>
            </Upload.Dragger>
          </Card>
        ) : (
          <Card style={{ flex: 1, minWidth: 320, maxWidth: 400, background: '#F5F7FA', borderRadius: 16, color: '#888', textAlign: 'center', paddingTop: 48 }}>
            <Title level={4} style={{ marginBottom: 16 }}>文档上传</Title>
            <div>仅管理员可上传文件，请联系系统管理员。</div>
          </Card>
        )}
        <Card style={{ flex: 2, minWidth: 400, background: '#ECEFF1', borderRadius: 16 }}>
          <Title level={4} style={{ marginBottom: 8 }}><RobotOutlined /> 智能问答</Title>
          <div style={{ marginBottom: 8, color: '#7C4DFF', fontWeight: 500 }}>{APP_DESC}</div>
          <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
            <Input.TextArea
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="请输入你的问题..."
              autoSize={{ minRows: 2, maxRows: 6 }}
              style={{ borderRadius: 8, fontSize: 16 }}
              disabled={loading}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={loading}
              onClick={handleAsk}
              style={{ borderRadius: 8 }}
            >发送</Button>
          </div>
          <Card style={{ minHeight: 180, background: '#fff', borderRadius: 12, boxShadow: '0 2px 8px #f0f1f2', marginBottom: 16 }}>
            <ReactMarkdown>{answer}</ReactMarkdown>
          </Card>
          <Card style={{ background: '#F5F7FA', borderRadius: 12, marginBottom: 8 }}>
            <div style={{ fontWeight: 500, marginBottom: 4 }}>检索上下文：</div>
            {contexts.length === 0 ? <div style={{ color: '#888' }}>暂无相关片段</div> : contexts.map((c,i)=>(
              <details key={i} className="ctx-item" open={i<2} style={{ marginBottom: 8 }}>
                <summary><b>#{i+1}</b> score={c.score?.toFixed(3)} <span style={{ fontSize: 12, color: '#7C4DFF' }}>{c.source}</span></summary>
                {c.content && <pre style={{ background: '#fff', borderRadius: 8, padding: 8 }}>{c.content}</pre>}
              </details>
            ))}
          </Card>
          <Card style={{ background: '#ECEFF1', borderRadius: 12 }}>
            <div style={{ fontWeight: 500, marginBottom: 4 }}>调试日志：</div>
            <pre style={{ fontSize: 12, color: '#263238', maxHeight: 80, overflow: 'auto' }}>{debugLog}</pre>
          </Card>
        </Card>
      </Content>
      <Footer style={{ textAlign: 'center', background: 'rgba(255,255,255,0.95)', color: '#1A237E', fontWeight: 500 }}>
        {COPYRIGHT} | {CONTACT}
      </Footer>
    </Layout>
  );
}
