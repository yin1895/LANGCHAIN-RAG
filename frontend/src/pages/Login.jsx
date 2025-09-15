import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Input, Button, Typography, message } from 'antd';

const { Title } = Typography;

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [regMode, setRegMode] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async () => {
    if (!username || !password) return message.error('请输入用户名和密码');
    setLoading(true);
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (data.token) {
        localStorage.setItem('token', data.token);
        message.success('登录成功');
        onLogin && onLogin(data);
        navigate('/');
      } else {
        message.error(data.msg || '登录失败');
      }
    } catch (e) {
      message.error('登录请求失败');
    }
    setLoading(false);
  };

  const handleRegister = async () => {
    if (!username || !password) return message.error('请输入用户名和密码');
    setLoading(true);
    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (data.success) {
        message.success('注册成功，请登录');
        setRegMode(false);
      } else {
        message.error(data.msg || '注册失败');
      }
    } catch (e) {
      message.error('注册请求失败');
    }
    setLoading(false);
  };

  return (
    <Card style={{ maxWidth: 400, margin: '80px auto', borderRadius: 16, background: '#F5F7FA' }}>
      <Title level={3} style={{ textAlign: 'center', marginBottom: 32 }}>{regMode ? '用户注册' : '系统登录'}</Title>
      <Input
        placeholder="用户名"
        value={username}
        onChange={e => setUsername(e.target.value)}
        style={{ marginBottom: 16 }}
      />
      <Input.Password
        placeholder="密码"
        value={password}
        onChange={e => setPassword(e.target.value)}
        style={{ marginBottom: 24 }}
      />
      {regMode ? (
        <Button type="primary" block loading={loading} onClick={handleRegister}>注册</Button>
      ) : (
        <Button type="primary" block loading={loading} onClick={handleLogin}>登录</Button>
      )}
      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <Button type="link" onClick={()=>setRegMode(!regMode)}>
          {regMode ? '已有账号？去登录' : '没有账号？去注册'}
        </Button>
      </div>
    </Card>
  );
}
