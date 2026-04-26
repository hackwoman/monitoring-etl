import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  message,
  Card,
  Descriptions,
  Table,
  Tag,
  Space,
  Typography,
  Spin,
  Tabs,
  Breadcrumb,
  Empty,
  Badge,
  Tooltip,
  Button,
  Divider,
} from 'antd';
import {  ArrowLeftOutlined,
  ApiOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  AppstoreOutlined,
  ClusterOutlined,
  GlobalOutlined,
  HddOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  CodeOutlined,
  DeploymentUnitOutlined,
  NodeIndexOutlined,
  CloudOutlined,
  DesktopOutlined,
  LockOutlined,
  AlertOutlined,
  DashboardOutlined,
  BarChartOutlined,
  SettingOutlined,
  BranchesOutlined,
  InfoCircleOutlined,
  LinkOutlined,
  FieldNumberOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

const { Title, Text, Paragraph } = Typography;

/* ─── Types ─── */
interface EntityTypeDetail {
  type_name: string;
  display_name: string;
  layer: string;
  category?: string;
  icon?: string;
  description?: string;
}

interface AttributeSchema {
  name: string;
  display_name?: string;
  type: string;
  required?: boolean;
  description?: string;
  default_value?: any;
  enum_values?: string[];
}

interface RelationDef {
  source_type: string;
  target_type: string;
  relation_type: string;
  description?: string;
  cardinality?: string;
}

interface MetricDef {
  name: string;
  display_name?: string;
  unit?: string;
  description?: string;
  metric_type?: string;
  aggregation?: string;
}

/* ─── Layer info ─── */
const LAYER_MAP: Record<string, { label: string; color: string; bg: string }> = {
  L1_business: { label: 'L1 业务层', color: '#722ed1', bg: '#f9f0ff' },
  L2_application: { label: 'L2 应用层', color: '#1677ff', bg: '#e6f4ff' },
  L3_service: { label: 'L3 服务层', color: '#13c2c2', bg: '#e6fffb' },
  L4_infrastructure: { label: 'L4 基础设施层', color: '#595959', bg: '#f5f5f5' },
};

/* ─── Icon mapping ─── */
const iconMap: Record<string, React.ReactNode> = {
  api: <ApiOutlined />,
  server: <CloudServerOutlined />,
  database: <DatabaseOutlined />,
  app: <AppstoreOutlined />,
  cluster: <ClusterOutlined />,
  global: <GlobalOutlined />,
  disk: <HddOutlined />,
  shield: <SafetyOutlined />,
  bolt: <ThunderboltOutlined />,
  code: <CodeOutlined />,
  deploy: <DeploymentUnitOutlined />,
  node: <NodeIndexOutlined />,
  cloud: <CloudOutlined />,
  desktop: <DesktopOutlined />,
  lock: <LockOutlined />,
  alert: <AlertOutlined />,
  dashboard: <DashboardOutlined />,
  chart: <BarChartOutlined />,
  setting: <SettingOutlined />,
  branch: <BranchesOutlined />,
};

const getIcon = (icon?: string) => {
  if (!icon) return <AppstoreOutlined />;
  return iconMap[icon] || <AppstoreOutlined />;
};

/* ─── Category labels ─── */
const categoryLabels: Record<string, string> = {
  frontend: '前端',
  backend: '后端',
  middleware: '中间件',
  storage: '存储',
  network: '网络',
  compute: '计算',
  security: '安全',
  monitoring: '监控',
  platform: '平台',
  business: '业务',
  data: '数据',
  external: '外部',
};

/* ─── Main Component ─── */
const EntityTypeDetail: React.FC = () => {
  const { typeName } = useParams<{ typeName: string }>();
  const navigate = useNavigate();

  const [typeInfo, setTypeInfo] = useState<EntityTypeDetail | null>(null);
  const [attributes, setAttributes] = useState<AttributeSchema[]>([]);
  const [relations, setRelations] = useState<RelationDef[]>([]);
  const [metrics, setMetrics] = useState<MetricDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('attributes');

  /* Fetch type detail */
  const fetchTypeDetail = useCallback(async () => {
    if (!typeName) return;
    try {
      const res = await axios.get(`${API_BASE}/types/${typeName}`);
      setTypeInfo(res.data);
    } catch (err) {
      console.error('Failed to fetch type detail:', err);
    }
  }, [typeName]);

  /* Fetch attributes */
  const fetchAttributes = useCallback(async () => {
    if (!typeName) return;
    try {
      const res = await axios.get(`${API_BASE}/attribute-schemas/${typeName}`);
      const data = res.data;
      setAttributes(data.attributes || data.items || data || []);
    } catch (err) {
      message.error('加载属性数据失败');
    }
  }, [typeName]);

  /* Fetch relations */
  const fetchRelations = useCallback(async () => {
    if (!typeName) return;
    try {
      const res = await axios.get(`${API_BASE}/types/${typeName}/relations`);
      const data = res.data;
      const raw = data.relations || data.items || data || [];
      setRelations(raw.map((r: any) => ({
        source_type: r.source_type || r.from_type || 'Service',
        target_type: r.target_type || r.to_type || r.target || '',
        relation_type: r.relation_type || r.type || '',
        description: r.description || '',
      })));
    } catch (err) {
      message.error('加载关系数据失败');
    }
  }, [typeName]);

  /* Fetch metrics */
  const fetchMetrics = useCallback(async () => {
    if (!typeName) return;
    try {
      const res = await axios.get(`${API_BASE}/types/${typeName}/metrics`);
      const data = res.data;
      const raw = data.metrics || data.items || data || [];
      setMetrics(raw.map((m: any) => ({
        metric_name: m.name || m.metric_name,
        display_name: m.display || m.display_name || m.name,
        metric_type: m.type || m.metric_type,
        aggregation: m.aggregations?.join(', ') || m.aggregation,
        unit: m.unit,
        description: m.description,
      })));
    } catch (err) {
      message.error('加载指标数据失败');
    }
  }, [typeName]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([
        fetchTypeDetail(),
        fetchAttributes(),
        fetchRelations(),
        fetchMetrics(),
      ]);
      setLoading(false);
    };
    load();
  }, [fetchTypeDetail, fetchAttributes, fetchRelations, fetchMetrics]);

  /* Navigate to related type */
  const handleRelatedTypeClick = (typeName: string) => {
    navigate(`/model-topology/${typeName}`);
  };

  /* Attribute columns */
  const attributeColumns = [
    {
      title: '属性名',
      dataIndex: 'key',
      key: 'name',
      width: 180,
      render: (name: string) => <Text code>{name}</Text>,
    },
    {
      title: '显示名',
      dataIndex: 'name',
      key: 'display_name',
      width: 150,
      render: (name: string) => name || '-',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => <Tag color="blue">{type}</Tag>,
    },
    {
      title: '必填',
      dataIndex: 'required',
      key: 'required',
      width: 80,
      render: (required: boolean) =>
        required ? (
          <Tag color="red">必填</Tag>
        ) : (
          <Tag color="default">可选</Tag>
        ),
    },
    {
      title: '默认值',
      dataIndex: 'default_value',
      key: 'default_value',
      width: 120,
      render: (val: any) => (val !== undefined && val !== null ? <Text code>{String(val)}</Text> : '-'),
    },
    {
      title: '枚举值',
      dataIndex: 'enum_values',
      key: 'enum_values',
      width: 200,
      render: (values: string[]) =>
        values && values.length > 0 ? (
          <Space size={4} wrap>
            {values.map((v) => (
              <Tag key={v}>{v}</Tag>
            ))}
          </Space>
        ) : (
          '-'
        ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ];

  /* Relation columns */
  const relationColumns = [
    {
      title: '源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 160,
      render: (type: string) => (
        <Button
          type="link"
          size="small"
          onClick={() => handleRelatedTypeClick(type)}
          style={{ padding: 0 }}
        >
          {type}
        </Button>
      ),
    },
    {
      title: '关系类型',
      dataIndex: 'relation_type',
      key: 'relation_type',
      width: 160,
      render: (type: string) => <Tag color="orange">{type}</Tag>,
    },
    {
      title: '目标类型',
      dataIndex: 'target_type',
      key: 'target_type',
      width: 160,
      render: (type: string) => (
        <Button
          type="link"
          size="small"
          onClick={() => handleRelatedTypeClick(type)}
          style={{ padding: 0 }}
        >
          {type}
        </Button>
      ),
    },
    {
      title: '基数',
      dataIndex: 'cardinality',
      key: 'cardinality',
      width: 120,
      render: (card: string) => (card ? <Tag>{card}</Tag> : '-'),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ];

  /* Metric columns */
  const metricColumns = [
    {
      title: '指标名',
      dataIndex: 'metric_name',
      key: 'name',
      width: 200,
      render: (name: string) => <Text code>{name}</Text>,
    },
    {
      title: '显示名',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 160,
      render: (name: string) => name || '-',
    },
    {
      title: '类型',
      dataIndex: 'metric_type',
      key: 'metric_type',
      width: 120,
      render: (type: string) =>
        type ? <Tag color={type === 'gauge' ? 'green' : type === 'counter' ? 'blue' : 'orange'}>{type}</Tag> : '-',
    },
    {
      title: '聚合方式',
      dataIndex: 'aggregation',
      key: 'aggregation',
      width: 120,
      render: (agg: string) => (agg ? <Tag>{agg}</Tag> : '-'),
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 100,
      render: (unit: string) => unit || '-',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="加载实体类型详情..." />
      </div>
    );
  }

  if (!typeInfo) {
    return (
      <Card>
        <Empty description="未找到该实体类型" />
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/model-topology')}
          style={{ marginTop: 16 }}
        >
          返回拓扑图
        </Button>
      </Card>
    );
  }

  const layerInfo = LAYER_MAP[typeInfo.layer] || {
    label: typeInfo.layer,
    color: '#595959',
    bg: '#f5f5f5',
  };

  return (
    <div style={{ padding: 0 }}>
      {/* Breadcrumb */}
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <a onClick={() => navigate('/model-topology')}>模型拓扑</a>
            ),
          },
          {
            title: typeInfo.display_name || typeInfo.type_name,
          },
        ]}
      />

      {/* Type header card */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
          {/* Icon */}
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 12,
              backgroundColor: layerInfo.bg,
              border: `2px solid ${layerInfo.color}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 28,
              color: layerInfo.color,
              flexShrink: 0,
            }}
          >
            {getIcon(typeInfo.icon)}
          </div>

          {/* Info */}
          <div style={{ flex: 1 }}>
            <Space align="center" style={{ marginBottom: 4 }}>
              <Title level={4} style={{ margin: 0 }}>
                {typeInfo.display_name}
              </Title>
              <Tag color={layerInfo.color}>{layerInfo.label}</Tag>
              {typeInfo.category && (
                <Tag>{categoryLabels[typeInfo.category] || typeInfo.category}</Tag>
              )}
            </Space>
            <Text style={{ color: "#475569", display: 'block', marginTop: 4  }}>
              {typeInfo.description || '暂无描述'}
            </Text>
            <Space style={{ marginTop: 8 }}>
              <Text style={{ color: "#475569" }}>
                <InfoCircleOutlined style={{ marginRight: 4 }} />
                类型标识: <Text code>{typeInfo.type_name}</Text>
              </Text>
            </Space>
          </div>

          {/* Back button */}
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/model-topology')}
          >
            返回拓扑图
          </Button>
        </div>
      </Card>

      {/* Stats cards */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
        <Card
          style={{ flex: 1 }}
          bodyStyle={{ padding: '16px 20px' }}
        >
          <Space>
            <FieldNumberOutlined style={{ fontSize: 20, color: '#1677ff' }} />
            <div>
              <Text style={{ color: "#475569", fontSize: 12  }}>属性定义</Text>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{attributes.length}</div>
            </div>
          </Space>
        </Card>
        <Card
          style={{ flex: 1 }}
          bodyStyle={{ padding: '16px 20px' }}
        >
          <Space>
            <LinkOutlined style={{ fontSize: 20, color: '#fa8c16' }} />
            <div>
              <Text style={{ color: "#475569", fontSize: 12  }}>关系定义</Text>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{relations.length}</div>
            </div>
          </Space>
        </Card>
        <Card
          style={{ flex: 1 }}
          bodyStyle={{ padding: '16px 20px' }}
        >
          <Space>
            <BarChartOutlined style={{ fontSize: 20, color: '#52c41a' }} />
            <div>
              <Text style={{ color: "#475569", fontSize: 12  }}>监控指标</Text>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{metrics.length}</div>
            </div>
          </Space>
        </Card>
      </div>

      {/* Tabs: Attributes / Relations / Metrics */}
      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'attributes',
              label: (
                <Space>
                  <FieldNumberOutlined />
                  属性定义
                  <Badge count={attributes.length} style={{ backgroundColor: '#1677ff' }} />
                </Space>
              ),
              children: (
                <Table
                  columns={attributeColumns}
                  dataSource={attributes}
                  rowKey="metric_name"
                  size="small"
                  pagination={attributes.length > 10 ? { pageSize: 10 } : false}
                  locale={{ emptyText: '暂无属性定义' }}
                />
              ),
            },
            {
              key: 'relations',
              label: (
                <Space>
                  <LinkOutlined />
                  关系定义
                  <Badge count={relations.length} style={{ backgroundColor: '#fa8c16' }} />
                </Space>
              ),
              children: (
                <Table
                  columns={relationColumns}
                  dataSource={relations}
                  rowKey={(r) => `${r.source_type}-${r.relation_type}-${r.target_type}`}
                  size="small"
                  pagination={relations.length > 10 ? { pageSize: 10 } : false}
                  locale={{ emptyText: '暂无关系定义' }}
                />
              ),
            },
            {
              key: 'metrics',
              label: (
                <Space>
                  <BarChartOutlined />
                  监控指标
                  <Badge count={metrics.length} style={{ backgroundColor: '#52c41a' }} />
                </Space>
              ),
              children: (
                <Table
                  columns={metricColumns}
                  dataSource={metrics}
                  rowKey="metric_name"
                  size="small"
                  pagination={metrics.length > 10 ? { pageSize: 10 } : false}
                  locale={{ emptyText: '暂无监控指标' }}
                />
              ),
            },
          ]}
        />
      </Card>

      {/* Related types quick links */}
      {relations.length > 0 && (
        <Card
          title={
            <Space>
              <BranchesOutlined />
              <Text>关联类型</Text>
            </Space>
          }
          style={{ marginTop: 16 }}
        >
          <Space wrap>
            {[...new Set(
              relations
                .map((r) => [r.source_type, r.target_type])
                .flat()
                .filter((t) => t !== typeName)
            )].map((relatedType) => (
              <Tooltip key={relatedType} title={`查看 ${relatedType} 类型详情`}>
                <Tag
                  color="blue"
                  style={{ cursor: 'pointer', padding: '4px 12px' }}
                  onClick={() => handleRelatedTypeClick(relatedType)}
                >
                  {relatedType}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        </Card>
      )}
    </div>
  );
};

export default EntityTypeDetail;
