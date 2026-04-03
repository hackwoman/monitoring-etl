import React, { useState, useEffect } from 'react';
import { Table, Tag, Button, Modal, Form, Input, Select, Space, Card, Row, Col, Statistic, Empty, Tabs, Descriptions, Divider, Spin } from 'antd';
import { PlusOutlined, DatabaseOutlined, ApiOutlined, DesktopOutlined, CloudServerOutlined, ApartmentOutlined, WarningOutlined } from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

// 实体类型定义
const ENTITY_TYPES = [
  { type: 'Service', display: '微服务', category: 'application', icon: <ApiOutlined />, color: '#1890ff' },
  { type: 'Host', display: '主机', category: 'infrastructure', icon: <DesktopOutlined />, color: '#13c2c2' },
  { type: 'MySQL', display: 'MySQL', category: 'middleware', icon: <DatabaseOutlined />, color: '#fa8c16' },
  { type: 'Redis', display: 'Redis', category: 'middleware', icon: <DatabaseOutlined />, color: '#eb2f96' },
  { type: 'NetworkDevice', display: '网络设备', category: 'infrastructure', icon: <CloudServerOutlined />, color: '#2f54eb' },
  { type: 'Business', display: '业务服务', category: 'business', icon: <ApartmentOutlined />, color: '#722ed1' },
  { type: 'Database', display: '数据库', category: 'middleware', icon: <DatabaseOutlined />, color: '#fa8c16' },
  { type: 'K8sCluster', display: 'K8s集群', category: 'runtime', icon: <CloudServerOutlined />, color: '#1890ff' },
  { type: 'K8sPod', display: 'K8s Pod', category: 'runtime', icon: <CloudServerOutlined />, color: '#13c2c2' },
  { type: 'Endpoint', display: 'API端点', category: 'application', icon: <ApiOutlined />, color: '#1890ff' },
  { type: 'IP', display: 'IP地址', category: 'infrastructure', icon: <CloudServerOutlined />, color: '#2f54eb' },
  { type: 'Middleware', display: '中间件', category: 'middleware', icon: <DatabaseOutlined />, color: '#13c2c2' },
];

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};

const CmdbPage: React.FC = () => {
  // 两级导航：分类 → 实体类型 → 实体列表
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [entities, setEntities] = useState<any[]>([]);
  const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [typeDef, setTypeDef] = useState<any>(null);

  // 加载所有类型的数量
  useEffect(() => {
    const fetchCounts = async () => {
      try {
        const res = await axios.get(`${API_BASE}/entities`, { params: { limit: 500 } });
        const items = res.data.items || [];
        const counts: Record<string, number> = {};
        items.forEach((e: any) => {
          counts[e.type_name] = (counts[e.type_name] || 0) + 1;
        });
        setTypeCounts(counts);
      } catch (e) { console.error(e); }
    };
    fetchCounts();
  }, []);

  // 加载选中类型的实体 + 类型定义
  useEffect(() => {
    if (!selectedType) return;
    setTypeDef(null);
    const fetch = async () => {
      setLoading(true);
      try {
        const [entRes, defRes] = await Promise.all([
          axios.get(`${API_BASE}/entities`, { params: { type_name: selectedType, limit: 200 } }),
          axios.get(`${API_BASE}/type-schema/${selectedType}`).catch(() => ({ data: null }))
        ]);
        setEntities(entRes.data.items || []);
        setTypeDef(defRes.data);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    fetch();
  }, [selectedType]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await axios.post(`${API_BASE}/entities`, values);
      setModalOpen(false);
      form.resetFields();
    } catch (err: any) {
      console.error(err);
    }
  };

  // 按 category 分组
  const categories = [
    { key: 'application', label: '应用层', types: ENTITY_TYPES.filter(t => t.category === 'application') },
    { key: 'middleware', label: '中间件层', types: ENTITY_TYPES.filter(t => t.category === 'middleware') },
    { key: 'infrastructure', label: '基础设施层', types: ENTITY_TYPES.filter(t => t.category === 'infrastructure') },
    { key: 'runtime', label: '运行时层', types: ENTITY_TYPES.filter(t => t.category === 'runtime') },
    { key: 'business', label: '业务层', types: ENTITY_TYPES.filter(t => t.category === 'business') },
  ].filter(c => c.types.length > 0);

  // 实体列表列
  const columns = [
    { title: '名称', dataIndex: 'name', width: 200, render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { title: '健康度', dataIndex: 'health_score', width: 120, sorter: (a: any, b: any) => (a.health_score || 0) - (b.health_score || 0),
      render: (_: any, r: any) => (
        <Space>
          <span style={{ color: healthColors[r.health_level] || '#999', fontWeight: 600 }}>{r.health_score ?? '?'}</span>
          <Tag color={healthColors[r.health_level]}>{r.health_level}</Tag>
        </Space>
      )
    },
    { title: '标签', dataIndex: 'labels', width: 250,
      render: (labels: Record<string, string>) => (
        <Space wrap>{Object.entries(labels || {}).map(([k, v]) => <Tag key={k}>{k}:{v}</Tag>)}</Space>
      )
    },
    { title: '来源', dataIndex: 'source', width: 100 },
    { title: '更新时间', dataIndex: 'updated_at', width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}><DatabaseOutlined style={{ marginRight: 8 }} />CMDB 实体管理</h2>

      {!selectedType ? (
        // 第一级：分类导航
        <div>
          {categories.map(cat => (
            <div key={cat.key} style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#595959', marginBottom: 12, paddingBottom: 4, borderBottom: '1px solid #f0f0f0' }}>
                {cat.label}
              </div>
              <Row gutter={[12, 12]}>
                {cat.types.map(t => (
                  <Col key={t.type} span={4}>
                    <Card
                      hoverable
                      size="small"
                      style={{ textAlign: 'center', cursor: 'pointer', borderTop: `2px solid ${t.color}` }}
                      onClick={() => setSelectedType(t.type)}
                    >
                      <div style={{ fontSize: 24, color: t.color, marginBottom: 4 }}>{t.icon}</div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{t.display}</div>
                      <div style={{ color: '#8c8c8c', fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                        {typeCounts[t.type] || 0}
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          ))}
        </div>
      ) : (
        // 第二级：类型定义 + 实体列表
        <div>
          <Space style={{ marginBottom: 12 }}>
            <a onClick={() => setSelectedType(null)} style={{ fontSize: 12 }}>← 返回分类</a>
            <span style={{ color: '#8c8c8c' }}>|</span>
            <Tag color={ENTITY_TYPES.find(t => t.type === selectedType)?.color}>
              {ENTITY_TYPES.find(t => t.type === selectedType)?.display || selectedType}
            </Tag>
            <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => {
              form.setFieldsValue({ type_name: selectedType });
              setModalOpen(true);
            }}>新建实体</Button>
          </Space>

          <Tabs items={[
            {
              key: 'definition',
              label: '📐 指标体系',
              children: typeDef ? <TypeDefView def={typeDef} /> : <Spin style={{ display: 'block', margin: '40px auto' }} />
            },
            {
              key: 'entities',
              label: `📋 实体列表 (${entities.length})`,
              children: (
                <Table columns={columns} dataSource={entities} rowKey="guid" loading={loading} size="small" pagination={{ pageSize: 50 }} />
              )
            }
          ]} />
        </div>
      )}

      <Modal title="新建实体" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="type_name" label="类型" rules={[{ required: true }]}>
            <Select options={ENTITY_TYPES.map(t => ({ label: t.display, value: t.type }))} />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如: payment-service" />
          </Form.Item>
          <Form.Item name="qualified_name" label="唯一标识 (可选)">
            <Input placeholder="留空自动生成" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// 指标体系展示组件
const TypeDefView: React.FC<{ def: any }> = ({ def }) => {
  const attrs = def.attributes || [];
  const metrics = def.metrics || [];
  const relations = def.relations || [];
  const health = def.health_model || {};

  // 按 category 分组指标
  const metricsByCategory: Record<string, any[]> = {};
  metrics.forEach((m: any) => {
    const cat = m.category || 'other';
    (metricsByCategory[cat] ||= []).push(m);
  });

  return (
    <div>
      {/* 基本信息 */}
      <Descriptions size="small" column={3} bordered style={{ marginBottom: 16 }}>
        <Descriptions.Item label="类型名">{def.type_name}</Descriptions.Item>
        <Descriptions.Item label="显示名">{def.display_name}</Descriptions.Item>
        <Descriptions.Item label="分类">{def.category}</Descriptions.Item>
      </Descriptions>

      {/* 指标体系 */}
      {Object.entries(metricsByCategory).map(([cat, items]) => (
        <div key={cat} style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#262626', marginBottom: 8 }}>
            {catLabels[cat] || cat} ({items.length})
          </div>
          <Table size="small" pagination={false} rowKey="name"
            dataSource={items}
            columns={[
              { title: '指标名', dataIndex: 'name', width: 280, render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
              { title: '显示名', dataIndex: 'display', width: 120 },
              { title: '类型', dataIndex: 'type', width: 60 },
              { title: '单位', dataIndex: 'unit', width: 70 },
              {
                title: '阈值', width: 140,
                render: (_: any, m: any) => {
                  const t = m.thresholds || {};
                  if (!t.warn && !t.crit) return '-';
                  return (
                    <Space size={4}>
                      {t.warn && <Tag color="gold">warn: {t.warn}</Tag>}
                      {t.crit && <Tag color="red">crit: {t.crit}</Tag>}
                    </Space>
                  );
                }
              }
            ]}
          />
        </div>
      ))}

      {metrics.length === 0 && <Empty description="暂无指标定义" imageStyle={{ height: 40 }} />}

      {/* 属性定义 */}
      {attrs.length > 0 && (
        <>
          <Divider orientation="left" plain>属性定义</Divider>
          <Table size="small" pagination={false} rowKey="key"
            dataSource={attrs}
            columns={[
              { title: 'Key', dataIndex: 'key', width: 160, render: (v: string) => <code>{v}</code> },
              { title: '名称', dataIndex: 'name', width: 120 },
              { title: '类型', dataIndex: 'type', width: 60 },
              { title: '必填', dataIndex: 'required', width: 50, render: (v: boolean) => v ? <Tag color="red">必填</Tag> : <Tag>可选</Tag> },
              { title: '默认值', dataIndex: 'default', width: 80, render: (v: any) => v !== undefined ? String(v) : '-' },
              { title: '说明', dataIndex: 'description' },
            ]}
          />
        </>
      )}

      {/* 关系 */}
      {relations.length > 0 && (
        <>
          <Divider orientation="left" plain>关系定义</Divider>
          <Space wrap>
            {relations.map((r: any, i: number) => (
              <Tag key={i} color={r.direction === 'out' ? 'blue' : 'green'}>
                {r.direction === 'out' ? '→' : '←'} {r.type} ({r.target})
              </Tag>
            ))}
          </Space>
        </>
      )}

      {/* 健康模型 */}
      {health.method && (
        <>
          <Divider orientation="left" plain>健康度模型</Divider>
          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="计算方法">{health.method}</Descriptions.Item>
            <Descriptions.Item label="维度数">{health.dimensions?.length || 0}</Descriptions.Item>
          </Descriptions>
          {health.dimensions && (
            <Table size="small" pagination={false} rowKey="name" style={{ marginTop: 8 }}
              dataSource={health.dimensions}
              columns={[
                { title: '维度', dataIndex: 'name', width: 100 },
                { title: '指标', dataIndex: 'metric', width: 280, render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
                { title: '权重', dataIndex: 'weight', width: 60, render: (v: number) => `${(v * 100).toFixed(0)}%` },
                { title: '分类', dataIndex: 'category', width: 80 },
              ]}
            />
          )}
        </>
      )}
    </div>
  );
};

const catLabels: Record<string, string> = {
  latency: '⏱ 延迟', traffic: '📈 流量', error: '❌ 错误', saturation: '🔥 饱和度',
  performance: '⚡ 性能', compute: '🖥 计算', memory: '💾 内存', disk: '💿 磁盘',
  network: '🌐 网络', resource: '📦 资源', connections: '🔗 连接', replication: '🔄 复制',
  locks: '🔒 锁', quality: '✅ 质量', capacity: '📊 容量', dynamic: '🔄 动态',
  status: '🚦 状态', business: '💰 业务', stability: '⚖️ 稳定性', interactivity: '👆 交互性',
  payload: '📦 数据量', other: '📦 其他',
};

export default CmdbPage;
