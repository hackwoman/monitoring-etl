import React, { useState, useEffect } from 'react';
import { Table, Tag, Button, Modal, Form, Input, Select, Space, Card, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

const CmdbPage: React.FC = () => {
  const [entities, setEntities] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [typeFilter, setTypeFilter] = useState<string>();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const fetchEntities = async (type?: string) => {
    setLoading(true);
    try {
      const params: any = { limit: 100 };
      if (type) params.type_name = type;
      const res = await axios.get(`${API_BASE}/entities`, { params });
      setEntities(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error('Fetch failed:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchEntities(); }, []);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await axios.post(`${API_BASE}/entities`, values);
      message.success('实体创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchEntities(typeFilter);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', width: 200 },
    {
      title: '类型', dataIndex: 'type_name', width: 120,
      render: (t: string) => <Tag color="blue">{t}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (s: string) => (
        <Tag color={s === 'active' ? 'green' : 'default'}>{s}</Tag>
      ),
    },
    {
      title: '标签', dataIndex: 'labels', width: 250,
      render: (labels: Record<string, string>) => (
        <>
          {Object.entries(labels || {}).map(([k, v]) => (
            <Tag key={k}>{k}:{v}</Tag>
          ))}
        </>
      ),
    },
    { title: '来源', dataIndex: 'source', width: 100 },
    {
      title: '更新时间', dataIndex: 'updated_at', width: 180,
      render: (t: string) => t ? new Date(t).toLocaleString() : '-',
    },
  ];

  return (
    <Card
      title={`CMDB 实体管理 (共 ${total} 个)`}
      extra={
        <Space>
          <Select
            placeholder="筛选类型"
            allowClear
            style={{ width: 150 }}
            onChange={(v) => { setTypeFilter(v); fetchEntities(v); }}
            options={[
              { label: 'Service', value: 'Service' },
              { label: 'Host', value: 'Host' },
              { label: 'Database', value: 'Database' },
              { label: 'Application', value: 'Application' },
              { label: 'Middleware', value: 'Middleware' },
            ]}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建实体
          </Button>
        </Space>
      }
    >
      <Table
        columns={columns}
        dataSource={entities}
        rowKey="guid"
        loading={loading}
        size="small"
        pagination={{ pageSize: 50 }}
      />

      <Modal title="新建实体" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="type_name" label="类型" rules={[{ required: true }]}>
            <Select options={[
              { label: 'Service', value: 'Service' },
              { label: 'Host', value: 'Host' },
              { label: 'Database', value: 'Database' },
              { label: 'Application', value: 'Application' },
              { label: 'Middleware', value: 'Middleware' },
            ]} />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如: payment-service" />
          </Form.Item>
          <Form.Item name="qualified_name" label="唯一标识 (可选)">
            <Input placeholder="留空自动生成" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default CmdbPage;
