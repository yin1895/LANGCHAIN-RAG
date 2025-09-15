import React, { useEffect, useState } from 'react';
import { Table, Button, Space, message, Popconfirm } from 'antd';

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchUsers = async () => {
  setLoading(true);
    try {
      const res = await fetch('/api/admin/users', { headers: { Authorization: 'Bearer ' + (localStorage.getItem('token')||'') } });
      const data = await res.json();
      setUsers(data.users || []);
    } catch (e) {
      message.error('获取用户失败');
    }
    setLoading(false);
  };

  useEffect(()=>{ fetchUsers(); }, []);

  const doAction = async (username, path, method='POST') => {
    setActionLoading(username + '|' + path);
    try {
      const res = await fetch(path.replace('{username}', encodeURIComponent(username)), { method, headers: { Authorization: 'Bearer ' + (localStorage.getItem('token')||'') } });
      const j = await res.json();
      if (res.ok) {
        message.success('操作成功');
        fetchUsers();
      } else {
        message.error(j.detail || '操作失败');
      }
    } catch (e) { message.error('请求失败'); }
    setActionLoading(null);
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '管理员', dataIndex: 'is_admin', key: 'is_admin', render: v => v ? '是' : '否' },
    { title: '激活', dataIndex: 'is_active', key: 'is_active', render: v => v ? '是' : '否' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v*1000).toLocaleString() : '' },
    { title: '操作', key: 'actions', render: (_, record) => (
      <Space>
        {record.is_admin ? (
          <Button danger size="small" loading={actionLoading===record.username+'|'+'/api/admin/users/{username}/demote'} onClick={()=>doAction(record.username, '/api/admin/users/{username}/demote')}>降级</Button>
        ) : (
          <Button size="small" loading={actionLoading===record.username+'|'+'/api/admin/users/{username}/promote'} onClick={()=>doAction(record.username, '/api/admin/users/{username}/promote')}>提升为管理员</Button>
        )}
        {record.is_active ? (
          <Button size="small" loading={actionLoading===record.username+'|'+'/api/admin/users/{username}/freeze'} onClick={()=>doAction(record.username, '/api/admin/users/{username}/freeze')}>冻结</Button>
        ) : (
          <Button size="small" loading={actionLoading===record.username+'|'+'/api/admin/users/{username}/unfreeze'} onClick={()=>doAction(record.username, '/api/admin/users/{username}/unfreeze')}>解冻</Button>
        )}
        <Popconfirm title="确认删除用户吗?" onConfirm={()=>doAction(record.username, '/api/admin/users/{username}', 'DELETE')}>
          <Button danger size="small" loading={actionLoading===record.username+'|'+'/api/admin/users/{username}'}>删除</Button>
        </Popconfirm>
      </Space>
    ) }
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2>管理员：用户管理</h2>
      <Table rowKey="username" loading={loading} columns={columns} dataSource={users} />
    </div>
  );
}
