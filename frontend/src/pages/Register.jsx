import React, { useState } from 'react';
import { Card, Input, Button, Typography, message } from 'antd';

const { Title } = Typography;

export default function Register({ onRegister }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

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
        onRegister && onRegister(data);
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
      <Title level={3} style={{ textAlign: 'center', marginBottom: 32 }}>用户注册</Title>
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
      <Button type="primary" block loading={loading} onClick={handleRegister}>注册</Button>
    </Card>
  );
}
