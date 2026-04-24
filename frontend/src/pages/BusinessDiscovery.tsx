import React, { useState, useEffect } from 'react';
import { Card, Table, Tag, Space, Button, Modal, Form, Input, Select, message, Descriptions, List, Badge, Divider, Tooltip, Drawer, Tabs } from 'antd';
import { 
  ApiOutlined, SearchOutlined, PlusOutlined, EditOutlined, 
  ThunderboltOutlined, CheckCircleOutlined, WarningOutlined,
  LinkOutlined, CodeOutlined, GlobalOutlined, CloudServerOutlined
} from '@ant-design/icons';
import axios from 'axios';

const API = '/api/v1';

interface Pattern {
  fingerprint: string;
  root_service: string;
  root_url: string;
  root_method: string;
  trace_count: number;
  avg_duration_ms: number;
  error_rate: number;
  services: string[];
  endpoints: string[];
  db_systems: string[];
  suggested_name: string;
  pattern_type: string;  // "api" 或 "page"
}

interface Business {
  guid: string;
  name: string;
  health_score: number;
  health_level: string;
  auto_discovered: boolean;
  fingerprint: string;
  url_patterns: {
    frontend: string[];
    api: string[];
    auto_discovered: string[];
  };
  frontend_urls: string[];
  api_urls: string[];
  created_at: string;
}

const BusinessDiscovery: React.FC = () => {
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editDrawerVisible, setEditDrawerVisible] = useState(false);
  const [selectedPattern, setSelectedPattern] = useState<Pattern | null>(null);
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  // 加载数据
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [patternsRes, businessesRes] = await Promise.all([
        axios.get(`${API}/business-discovery/patterns?hours=24&min_traces=10`).catch(() => ({ data: { patterns: [] } })),
        axios.get(`${API}/business-discovery/list`).catch(() => ({ data: { items: [] } })),
      ]);
      setPatterns(patternsRes.data.patterns || []);
      setBusinesses(businessesRes.data.items || []);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  // 从模式创建 Business
  const handleCreate = async (values: any) => {
    if (!selectedPattern) return;
    try {
      await axios.post(`${API}/business-discovery/create`, {
        fingerprint: selectedPattern.fingerprint,
        name: values.name,
        display_name: values.display_name,
        frontend_urls: values.frontend_urls || [],
        api_urls: values.api_urls || [],
        include_services: values.include_services,
      });
      message.success('业务创建成功');
      setCreateModalVisible(false);
      form.resetFields();
      loadData();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败');
    }
  };

  // 编辑 Business
  const handleEdit = async (values: any) => {
    if (!selectedBusiness) return;
    try {
      await axios.put(`${API}/business-discovery/${selectedBusiness.guid}`, {
        frontend_urls: values.frontend_urls || [],
        api_urls: values.api_urls || [],
        include_services: values.include_services,
        exclude_services: values.exclude_services,
      });
      message.success('更新成功');
      setEditDrawerVisible(false);
      editForm.resetFields();
      loadData();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败');
    }
  };

  // 自动发现的模式表格列
  const patternColumns = [
    {
      title: '业务名称',
      dataIndex: 'suggested_name',
      key: 'name',
      render: (name: string, record: Pattern) => (
        <Space>
          {record.pattern_type === 'page' 
            ? <GlobalOutlined style={{ color: '#52c41a' }} /> 
            : <CloudServerOutlined style={{ color: '#1890ff' }} />
          }
          <span style={{ fontWeight: 600 }}>{name}</span>
          <Tag color={record.pattern_type === 'page' ? 'green' : 'blue'}>
            {record.pattern_type === 'page' ? '页面' : 'API'}
          </Tag>
        </Space>
      ),
    },
    {
      title: '入口',
      key: 'entry',
      render: (_: unknown, record: Pattern) => (
        <Space direction="vertical" size={0}>
          {record.pattern_type === 'api' && <Tag color="blue">{record.root_method}</Tag>}
          <code style={{ fontSize: 11 }}>{record.root_url}</code>
        </Space>
      ),
    },
    {
      title: '调用次数',
      dataIndex: 'trace_count',
      key: 'trace_count',
      sorter: (a: Pattern, b: Pattern) => a.trace_count - b.trace_count,
      render: (count: number) => <Badge count={count} showZero color={count > 1000 ? 'red' : count > 100 ? 'orange' : 'green'} />,
    },
    {
      title: '错误率',
      dataIndex: 'error_rate',
      key: 'error_rate',
      render: (rate: number) => (
        <Tag color={rate > 10 ? 'red' : rate > 1 ? 'orange' : 'green'}>
          {rate.toFixed(1)}%
        </Tag>
      ),
    },
    {
      title: '关联服务',
      dataIndex: 'services',
      key: 'services',
      render: (services: string[]) => (
        <Space wrap>
          {services.slice(0, 3).map(s => <Tag key={s}>{s}</Tag>)}
          {services.length > 3 && <Tag>+{services.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: '数据存储',
      dataIndex: 'db_systems',
      key: 'db_systems',
      render: (dbs: string[]) => (
        <Space>
          {dbs.map(db => <Tag key={db} color={db === 'mysql' ? 'orange' : db === 'redis' ? 'red' : db === 'elasticsearch' ? 'blue' : 'default'}>{db}</Tag>)}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Pattern) => (
        <Space>
          <Button 
            type="primary" 
            size="small" 
            icon={<PlusOutlined />}
            onClick={() => {
              setSelectedPattern(record);
              form.setFieldsValue({ name: record.suggested_name, url_patterns: [record.root_url] });
              setCreateModalVisible(true);
            }}
          >
            创建业务
          </Button>
        </Space>
      ),
    },
  ];

  // 已有 Business 表格列
  const businessColumns = [
    {
      title: '业务名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Business) => (
        <Space>
          {record.auto_discovered ? <ThunderboltOutlined style={{ color: '#faad14' }} /> : <EditOutlined style={{ color: '#1890ff' }} />}
          <span style={{ fontWeight: 600 }}>{name}</span>
          {record.auto_discovered && <Tag color="gold">自动发现</Tag>}
        </Space>
      ),
    },
    {
      title: '健康度',
      key: 'health',
      render: (_: unknown, record: Business) => (
        <Space>
          <span style={{ 
            color: record.health_level === 'healthy' ? '#52c41a' : record.health_level === 'warning' ? '#faad14' : '#ff4d4f',
            fontWeight: 600 
          }}>
            {record.health_score || '-'}
          </span>
          <Tag color={record.health_level === 'healthy' ? 'green' : record.health_level === 'warning' ? 'orange' : 'red'}>
            {record.health_level || 'unknown'}
          </Tag>
        </Space>
      ),
    },
    {
      title: 'URL 模式',
      key: 'url_patterns',
      render: (_: unknown, record: Business) => {
        const frontend = record.frontend_urls || record.url_patterns?.frontend || [];
        const api = record.api_urls || record.url_patterns?.api || [];
        return (
          <Space direction="vertical" size={2}>
            {frontend.length > 0 && (
              <div>
                <GlobalOutlined style={{ color: '#52c41a', marginRight: 4 }} />
                {frontend.slice(0, 2).map(u => <Tag key={u} color="green">{u}</Tag>)}
                {frontend.length > 2 && <Tag color="green">+{frontend.length - 2}</Tag>}
              </div>
            )}
            {api.length > 0 && (
              <div>
                <CloudServerOutlined style={{ color: '#1890ff', marginRight: 4 }} />
                {api.slice(0, 2).map(u => <Tag key={u} color="blue">{u}</Tag>)}
                {api.length > 2 && <Tag color="blue">+{api.length - 2}</Tag>}
              </div>
            )}
            {frontend.length === 0 && api.length === 0 && (
              <span style={{ color: '#888' }}>未配置</span>
            )}
          </Space>
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Business) => (
        <Button 
          size="small" 
          icon={<EditOutlined />}
          onClick={() => {
            setSelectedBusiness(record);
            editForm.setFieldsValue({ url_patterns: record.url_patterns || [] });
            setEditDrawerVisible(true);
          }}
        >
          编辑
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>🔍 业务自动发现</h2>
          <p style={{ color: '#888', margin: '4px 0 0 0' }}>从 Trace 拓扑自动识别业务模式 (L2)，支持手动编辑 (L1)</p>
        </div>
        <Button icon={<SearchOutlined />} onClick={loadData}>刷新</Button>
      </div>

      {/* 自动发现的模式 */}
      <Card 
        title={<><ThunderboltOutlined /> 自动发现的业务模式 ({patterns.length})</>}
        style={{ marginBottom: 16 }}
      >
        <Table 
          columns={patternColumns} 
          dataSource={patterns} 
          rowKey="fingerprint"
          loading={loading}
          size="small"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 已创建的 Business */}
      <Card 
        title={<><ApiOutlined /> 已创建的业务 ({businesses.length})</>}
      >
        <Table 
          columns={businessColumns} 
          dataSource={businesses} 
          rowKey="guid"
          loading={loading}
          size="small"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 创建 Business 弹窗 */}
      <Modal
        title={<><PlusOutlined /> 创建业务</>}
        open={createModalVisible}
        onCancel={() => { setCreateModalVisible(false); form.resetFields(); }}
        onOk={() => form.submit()}
        width={600}
      >
        {selectedPattern && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
            <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>基于模式</div>
            <div><strong>{selectedPattern.root_method} {selectedPattern.root_url}</strong></div>
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                {selectedPattern.services.map(s => <Tag key={s}>{s}</Tag>)}
              </Space>
            </div>
          </div>
        )}
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="业务名称" rules={[{ required: true }]}>
            <Input placeholder="如: 订单业务" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="可选" />
          </Form.Item>
          <Divider orientation="left" plain>URL 模式 (L1 手动)</Divider>
          <Form.Item name="frontend_urls" label={<><GlobalOutlined /> 前端页面 URL</>}>
            <Select mode="tags" placeholder="如: /checkout, /cart" />
          </Form.Item>
          <Form.Item name="api_urls" label={<><CloudServerOutlined /> API URL</>}>
            <Select mode="tags" placeholder="如: /api/order, /api/pay" />
          </Form.Item>
          <Divider orientation="left" plain>关联服务</Divider>
          <Form.Item name="include_services" label="关联服务">
            <Select mode="tags" placeholder="选择要关联的服务">
              {selectedPattern?.services.map(s => (
                <Select.Option key={s} value={s}>{s}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑 Business 抽屉 */}
      <Drawer
        title={<><EditOutlined /> 编辑业务</>}
        open={editDrawerVisible}
        onClose={() => { setEditDrawerVisible(false); editForm.resetFields(); }}
        width={480}
      >
        {selectedBusiness && (
          <>
            <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="业务名称">{selectedBusiness.name}</Descriptions.Item>
              <Descriptions.Item label="来源">{selectedBusiness.auto_discovered ? '自动发现' : '手动创建'}</Descriptions.Item>
              <Descriptions.Item label="健康度">{selectedBusiness.health_score || '-'}</Descriptions.Item>
            </Descriptions>
            <Divider />
            <Form form={editForm} layout="vertical" onFinish={handleEdit}>
              <Divider orientation="left" plain>URL 模式 (L1 手动)</Divider>
              <Form.Item name="frontend_urls" label={<><GlobalOutlined /> 前端页面 URL</>}>
                <Select mode="tags" placeholder="如: /checkout, /cart" />
              </Form.Item>
              <Form.Item name="api_urls" label={<><CloudServerOutlined /> API URL</>}>
                <Select mode="tags" placeholder="如: /api/order, /api/pay" />
              </Form.Item>
              <Divider orientation="left" plain>关联服务</Divider>
              <Form.Item name="include_services" label="添加关联服务">
                <Select mode="tags" placeholder="输入服务名" />
              </Form.Item>
              <Form.Item name="exclude_services" label="移除关联服务">
                <Select mode="tags" placeholder="输入要移除的服务名" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" block>保存</Button>
              </Form.Item>
            </Form>
          </>
        )}
      </Drawer>
    </div>
  );
};

export default BusinessDiscovery;
