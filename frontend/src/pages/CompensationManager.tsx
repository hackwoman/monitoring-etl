import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Space, Tag, Tabs, Modal, Form, Input, Select, Popconfirm,
  message, Badge, Descriptions, Divider, Empty, Spin, Tooltip, Row, Col, Statistic,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, CheckOutlined, CloseOutlined,
  SwapOutlined, LinkOutlined, ReloadOutlined, WarningOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ClockCircleOutlined, ToolOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

// ========== 指标映射管理 ==========
const MetricMappingManager: React.FC = () => {
  const [mappings, setMappings] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<any>(null);
  const [form] = Form.useForm();

  const fetchMappings = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/mappings/metrics`);
      setMappings(Array.isArray(res.data) ? res.data : (res.data.items || []));
    } catch (e) {
      console.error('Failed to fetch mappings:', e);
      setMappings([]);
    }
    setLoading(false);
  };

  useEffect(() => { fetchMappings(); }, []);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editingMapping) {
        await axios.put(`${API_BASE}/mappings/metrics/${editingMapping.id}`, values);
        message.success('映射已更新');
      } else {
        await axios.post(`${API_BASE}/mappings/metrics`, values);
        message.success('映射已创建');
      }
      setModalOpen(false);
      setEditingMapping(null);
      form.resetFields();
      fetchMappings();
    } catch (e: any) {
      if (e.errorFields) return; // form validation
      message.error('操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(`${API_BASE}/mappings/metrics/${id}`);
      message.success('映射已删除');
      fetchMappings();
    } catch {
      message.error('删除失败');
    }
  };

  const handleEdit = (record: any) => {
    setEditingMapping(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const columns = [
    {
      title: '源指标', dataIndex: 'source_metric', width: 250,
      render: (v: string) => <code style={{ fontSize: 11, background: '#f5f5f5', padding: '2px 6px', borderRadius: 3 }}>{v}</code>,
    },
    {
      title: '目标指标', dataIndex: 'target_metric', width: 250,
      render: (v: string) => <code style={{ fontSize: 11, background: '#f0f5ff', padding: '2px 6px', borderRadius: 3 }}>{v}</code>,
    },
    {
      title: '转换方式', dataIndex: 'transform', width: 120,
      render: (v: string) => <Tag color="blue">{v || '直接映射'}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => {
        const colors: Record<string, string> = { active: 'green', inactive: 'default', pending: 'orange' };
        const labels: Record<string, string> = { active: '启用', inactive: '停用', pending: '待确认' };
        return <Tag color={colors[v] || 'default'}>{labels[v] || v}</Tag>;
      },
    },
    {
      title: '操作', width: 120,
      render: (_: any, record: any) => (
        <Space size={4}>
          <Tooltip title="编辑"><Button size="small" type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} /></Tooltip>
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除"><Button size="small" type="text" danger icon={<DeleteOutlined />} /></Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: '#8c8c8c' }}>共 {mappings.length} 条映射规则</span>
        <Space>
          <Button size="small" icon={<ReloadOutlined />} onClick={fetchMappings}>刷新</Button>
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => { setEditingMapping(null); form.resetFields(); setModalOpen(true); }}>
            新建映射
          </Button>
        </Space>
      </div>

      <Table
        dataSource={mappings}
        rowKey="id"
        columns={columns}
        loading={loading}
        size="small"
        pagination={{ pageSize: 15 }}
      />

      <Modal
        title={editingMapping ? '编辑映射' : '新建映射'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); setEditingMapping(null); form.resetFields(); }}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="source_metric" label="源指标" rules={[{ required: true, message: '请输入源指标名' }]}>
            <Input placeholder="如: system.cpu.utilization" />
          </Form.Item>
          <Form.Item name="target_metric" label="目标指标" rules={[{ required: true, message: '请输入目标指标名' }]}>
            <Input placeholder="如: cpu_usage_percent" />
          </Form.Item>
          <Form.Item name="transform" label="转换方式">
            <Select
              placeholder="选择转换方式"
              allowClear
              options={[
                { label: '直接映射', value: 'direct' },
                { label: '比率转换', value: 'ratio' },
                { label: '偏移转换', value: 'offset' },
                { label: '自定义表达式', value: 'expression' },
              ]}
            />
          </Form.Item>
          <Form.Item name="expression" label="转换表达式">
            <Input.TextArea placeholder="如: value / 100 或 value * 1024" rows={2} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select
              options={[
                { label: '启用', value: 'active' },
                { label: '停用', value: 'inactive' },
                { label: '待确认', value: 'pending' },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="映射说明" rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// ========== 动态扩展指标确认 ==========
const DynamicMetricsConfirm: React.FC = () => {
  const [metrics, setMetrics] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('pending');

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/dynamic/metrics`);
      setMetrics(Array.isArray(res.data) ? res.data : (res.data.items || []));
    } catch (e) {
      console.error('Failed to fetch dynamic metrics:', e);
      setMetrics([]);
    }
    setLoading(false);
  };

  useEffect(() => { fetchMetrics(); }, []);

  const handleConfirm = async (id: string, action: 'confirm' | 'reject') => {
    try {
      await axios.post(`${API_BASE}/dynamic/metrics/${id}/${action}`);
      message.success(action === 'confirm' ? '已确认' : '已拒绝');
      fetchMetrics();
    } catch {
      message.error('操作失败');
    }
  };

  const filteredMetrics = metrics.filter(m => {
    if (filterStatus === 'all') return true;
    return m.status === filterStatus;
  });

  const statusCounts = {
    pending: metrics.filter(m => m.status === 'pending').length,
    confirmed: metrics.filter(m => m.status === 'confirmed').length,
    rejected: metrics.filter(m => m.status === 'rejected').length,
  };

  const columns = [
    {
      title: '指标名', dataIndex: 'metric_name', width: 280,
      render: (v: string) => <code style={{ fontSize: 11, background: '#f5f5f5', padding: '2px 6px', borderRadius: 3 }}>{v}</code>,
    },
    { title: '实体类型', dataIndex: 'entity_type', width: 120, render: (v: string) => <Tag>{v}</Tag> },
    { title: '来源', dataIndex: 'source', width: 100 },
    { title: '发现时间', dataIndex: 'discovered_at', width: 160, render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => {
        const config: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
          pending: { color: 'orange', icon: <ClockCircleOutlined />, label: '待确认' },
          confirmed: { color: 'green', icon: <CheckCircleOutlined />, label: '已确认' },
          rejected: { color: 'red', icon: <CloseCircleOutlined />, label: '已拒绝' },
        };
        const c = config[v] || config.pending;
        return <Tag color={c.color} icon={c.icon}>{c.label}</Tag>;
      },
    },
    {
      title: '操作', width: 140,
      render: (_: any, record: any) => record.status === 'pending' ? (
        <Space size={4}>
          <Popconfirm title="确认接受此指标?" onConfirm={() => handleConfirm(record.id, 'confirm')}>
            <Button size="small" type="primary" icon={<CheckOutlined />}>确认</Button>
          </Popconfirm>
          <Popconfirm title="确认拒绝此指标?" onConfirm={() => handleConfirm(record.id, 'reject')}>
            <Button size="small" danger icon={<CloseOutlined />}>拒绝</Button>
          </Popconfirm>
        </Space>
      ) : (
        <span style={{ color: '#8c8c8c', fontSize: 12 }}>已处理</span>
      ),
    },
  ];

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small" hoverable onClick={() => setFilterStatus('pending')} style={{ borderColor: filterStatus === 'pending' ? '#faad14' : undefined }}>
            <Statistic title="待确认" value={statusCounts.pending} valueStyle={{ color: '#faad14' }} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" hoverable onClick={() => setFilterStatus('confirmed')} style={{ borderColor: filterStatus === 'confirmed' ? '#52c41a' : undefined }}>
            <Statistic title="已确认" value={statusCounts.confirmed} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" hoverable onClick={() => setFilterStatus('rejected')} style={{ borderColor: filterStatus === 'rejected' ? '#ff4d4f' : undefined }}>
            <Statistic title="已拒绝" value={statusCounts.rejected} valueStyle={{ color: '#ff4d4f' }} prefix={<CloseCircleOutlined />} />
          </Card>
        </Col>
      </Row>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Space>
          <span style={{ fontSize: 13, color: '#8c8c8c' }}>筛选:</span>
          {['pending', 'confirmed', 'rejected', 'all'].map(s => (
            <Tag
              key={s}
              color={filterStatus === s ? 'blue' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => setFilterStatus(s)}
            >
              {{ pending: '待确认', confirmed: '已确认', rejected: '已拒绝', all: '全部' }[s]}
            </Tag>
          ))}
        </Space>
        <Button size="small" icon={<ReloadOutlined />} onClick={fetchMetrics}>刷新</Button>
      </div>

      <Table
        dataSource={filteredMetrics}
        rowKey="id"
        columns={columns}
        loading={loading}
        size="small"
        pagination={{ pageSize: 15 }}
      />
    </div>
  );
};

// ========== 维度映射管理 ==========
const DimensionMappingManager: React.FC = () => {
  const [dimensions, setDimensions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingDim, setEditingDim] = useState<any>(null);
  const [form] = Form.useForm();

  const fetchDimensions = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/dimensions`).catch(() => ({ data: [] }));
      setDimensions(Array.isArray(res.data) ? res.data : (res.data.items || []));
    } catch {
      setDimensions([]);
    }
    setLoading(false);
  };

  useEffect(() => { fetchDimensions(); }, []);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editingDim) {
        await axios.put(`${API_BASE}/dimensions/${editingDim.id}`, values);
        message.success('维度映射已更新');
      } else {
        await axios.post(`${API_BASE}/dimensions`, values);
        message.success('维度映射已创建');
      }
      setModalOpen(false);
      setEditingDim(null);
      form.resetFields();
      fetchDimensions();
    } catch (e: any) {
      if (e.errorFields) return;
      message.error('操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(`${API_BASE}/dimensions/${id}`);
      message.success('维度映射已删除');
      fetchDimensions();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '维度名', dataIndex: 'name', width: 160, render: (v: string) => <strong>{v}</strong> },
    { title: '源维度', dataIndex: 'source_dimension', width: 180, render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
    { title: '目标维度', dataIndex: 'target_dimension', width: 180, render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
    { title: '类型', dataIndex: 'type', width: 100, render: (v: string) => <Tag color="blue">{v || 'string'}</Tag> },
    { title: '描述', dataIndex: 'description', ellipsis: true },
    {
      title: '操作', width: 120,
      render: (_: any, record: any) => (
        <Space size={4}>
          <Tooltip title="编辑">
            <Button size="small" type="text" icon={<EditOutlined />} onClick={() => {
              setEditingDim(record);
              form.setFieldsValue(record);
              setModalOpen(true);
            }} />
          </Tooltip>
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除"><Button size="small" type="text" danger icon={<DeleteOutlined />} /></Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: '#8c8c8c' }}>共 {dimensions.length} 条维度映射</span>
        <Space>
          <Button size="small" icon={<ReloadOutlined />} onClick={fetchDimensions}>刷新</Button>
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => { setEditingDim(null); form.resetFields(); setModalOpen(true); }}>
            新建维度映射
          </Button>
        </Space>
      </div>

      <Table
        dataSource={dimensions}
        rowKey="id"
        columns={columns}
        loading={loading}
        size="small"
        pagination={{ pageSize: 15 }}
      />

      <Modal
        title={editingDim ? '编辑维度映射' : '新建维度映射'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); setEditingDim(null); form.resetFields(); }}
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="维度名" rules={[{ required: true }]}>
            <Input placeholder="如: region" />
          </Form.Item>
          <Form.Item name="source_dimension" label="源维度" rules={[{ required: true }]}>
            <Input placeholder="如: datacenter" />
          </Form.Item>
          <Form.Item name="target_dimension" label="目标维度" rules={[{ required: true }]}>
            <Input placeholder="如: region" />
          </Form.Item>
          <Form.Item name="type" label="类型">
            <Select
              options={[
                { label: 'string', value: 'string' },
                { label: 'number', value: 'number' },
                { label: 'boolean', value: 'boolean' },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="维度映射说明" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// ========== 主页面 ==========
const CompensationManager: React.FC = () => {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <ToolOutlined style={{ fontSize: 20, color: '#1890ff' }} />
        <span style={{ fontWeight: 700, fontSize: 16 }}>补偿机制管理</span>
      </div>

      <Tabs
        defaultActiveKey="mapping"
        items={[
          {
            key: 'mapping',
            label: <span><LinkOutlined /> 指标映射管理</span>,
            children: <Card size="small"><MetricMappingManager /></Card>,
          },
          {
            key: 'dynamic',
            label: <span><WarningOutlined /> 动态扩展指标确认</span>,
            children: <Card size="small"><DynamicMetricsConfirm /></Card>,
          },
          {
            key: 'dimension',
            label: <span><SwapOutlined /> 维度映射管理</span>,
            children: <Card size="small"><DimensionMappingManager /></Card>,
          },
        ]}
      />
    </div>
  );
};

export default CompensationManager;
