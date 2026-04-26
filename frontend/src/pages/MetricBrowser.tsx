import React, { useState, useEffect } from 'react';
import {
  Card, Tree, Table, Input, Space, Tag, Spin, Empty, Tabs, Descriptions,
  Button, Tooltip, Row, Col, Statistic, Badge, Typography, Divider, Select,
} from 'antd';
import {
  SearchOutlined, DatabaseOutlined, ApiOutlined, DesktopOutlined,
  CloudServerOutlined, NodeIndexOutlined, ReloadOutlined, BarChartOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

// 层级定义
const LAYERS = [
  { key: 'L1', label: 'L1 业务层', color: '#e8f5e9', types: ['BusinessModule', 'BusinessEvent', 'E2ECallChain'] },
  { key: 'L2', label: 'L2 应用层', color: '#e3f2fd', types: ['TerminalApp', 'Page', 'NetworkRequest', 'UserAction', 'Service', 'ServiceInstance', 'Interface', 'KeyMethod'] },
  { key: 'L3', label: 'L3 服务层', color: '#fff3e0', types: ['Database', 'MySQL', 'Redis', 'Cache', 'MessageQueue', 'ObjectStorage', 'SearchEngine', 'Middleware'] },
  { key: 'L4', label: 'L4 基础设施层', color: '#f3e5f5', types: ['Host', 'Container', 'Process', 'ProcessGroup', 'NetworkDevice', 'StorageDevice', 'CloudResource', 'K8sCluster', 'K8sNode', 'K8sPod', 'K8sService', 'K8sWorkload', 'IP'] },
];

const TYPE_DISPLAY: Record<string, string> = {
  BusinessModule: '业务模块', BusinessEvent: '业务事件', E2ECallChain: '端到端调用链',
  TerminalApp: '终端应用', Page: '页面', NetworkRequest: '网络请求', UserAction: '用户操作',
  Service: '微服务', ServiceInstance: '服务实例', Interface: '接口', KeyMethod: '关键方法',
  Database: '数据库', MySQL: 'MySQL', Redis: 'Redis', Cache: '缓存',
  MessageQueue: '消息队列', ObjectStorage: '对象存储', SearchEngine: '搜索引擎', Middleware: '中间件',
  Host: '主机', Container: '容器', Process: '进程', ProcessGroup: '进程组',
  NetworkDevice: '网络设备', StorageDevice: '存储设备', CloudResource: '云资源',
  K8sCluster: 'K8s集群', K8sNode: 'K8s节点', K8sPod: 'K8s Pod',
  K8sService: 'K8s Service', K8sWorkload: 'K8s工作负载', IP: 'IP地址',
};

const NODE_COLORS: Record<string, string> = {
  BusinessModule: '#4caf50', BusinessEvent: '#66bb6a', E2ECallChain: '#81c784',
  TerminalApp: '#2196f3', Page: '#42a5f5', NetworkRequest: '#64b5f6', UserAction: '#90caf9',
  Service: '#1e88e5', ServiceInstance: '#1976d2', Interface: '#1565c0', KeyMethod: '#0d47a1',
  Database: '#ff9800', MySQL: '#fb8c00', Redis: '#f57c00', Cache: '#ef6c00',
  MessageQueue: '#e65100', ObjectStorage: '#ff6d00', SearchEngine: '#ff9100', Middleware: '#ffa726',
  Host: '#9c27b0', Container: '#ab47bc', Process: '#ba68c8', ProcessGroup: '#ce93d8',
  NetworkDevice: '#7b1fa2', StorageDevice: '#6a1b9a', CloudResource: '#4a148c',
  K8sCluster: '#8e24aa', K8sNode: '#9c27b0', K8sPod: '#ab47bc',
  K8sService: '#7b1fa2', K8sWorkload: '#6a1b9a', IP: '#512da8',
};

const catLabels: Record<string, string> = {
  latency: '⏱ 延迟', traffic: '📈 流量', error: '❌ 错误', saturation: '🔥 饱和度',
  performance: '⚡ 性能', compute: '🖥 计算', memory: '💾 内存', disk: '💿 磁盘',
  network: '🌐 网络', resource: '📦 资源', connections: '🔗 连接', replication: '🔄 复制',
  locks: '🔒 锁', quality: '✅ 质量', capacity: '📊 容量', dynamic: '🔄 动态',
  status: '🚦 状态', business: '💰 业务', stability: '⚖️ 稳定性', interactivity: '👆 交互性',
  payload: '📦 数据量', other: '📦 其他',
};

const MetricBrowser: React.FC = () => {
  const [entityTypes, setEntityTypes] = useState<any[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const [filterCategory, setFilterCategory] = useState<string | null>(null);

  // 加载实体类型
  useEffect(() => {
    const fetchTypes = async () => {
      try {
        const res = await axios.get(`${API_BASE}/types`);
        setEntityTypes(Array.isArray(res.data) ? res.data : (res.data.items || []));
      } catch (e) {
        console.error('Failed to fetch types:', e);
      }
    };
    fetchTypes();
  }, []);

  // 加载选中类型的指标
  useEffect(() => {
    if (!selectedType) { setMetrics([]); return; }
    const fetchMetrics = async () => {
      setMetricsLoading(true);
      try {
        const res = await axios.get(`${API_BASE}/types/${selectedType}/metrics`);
        setMetrics(Array.isArray(res.data) ? res.data : (res.data.items || res.data.metrics || []));
      } catch (e) {
        console.error('Failed to fetch metrics:', e);
        setMetrics([]);
      }
      setMetricsLoading(false);
    };
    fetchMetrics();
  }, [selectedType]);

  // 构建树形数据
  const treeData = LAYERS.map(layer => ({
    title: layer.label,
    key: layer.key,
    children: layer.types
      .filter(t => entityTypes.some((et: any) => (et.type_name || et.type) === t))
      .map(t => ({
        title: (
          <Space size={4}>
            <span style={{ color: NODE_COLORS[t], fontWeight: 500 }}>{TYPE_DISPLAY[t] || t}</span>
          </Space>
        ),
        key: t,
        icon: <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: NODE_COLORS[t] }} />,
      })),
  })).filter(layer => (layer.children as any[]).length > 0);

  // 按 category 分组指标
  const filteredMetrics = metrics.filter(m => {
    if (searchValue && !m.name?.toLowerCase().includes(searchValue.toLowerCase()) && !m.display?.toLowerCase().includes(searchValue.toLowerCase())) return false;
    if (filterCategory && m.category !== filterCategory) return false;
    return true;
  });

  const metricsByCategory: Record<string, any[]> = {};
  filteredMetrics.forEach(m => {
    const cat = m.category || 'other';
    (metricsByCategory[cat] ||= []).push(m);
  });

  const categories = [...new Set(metrics.map(m => m.category || 'other'))].sort();

  // 指标表格列
  const metricColumns = [
    {
      title: '指标名', dataIndex: 'name', width: 320,
      render: (v: string) => <code style={{ fontSize: 11, background: '#f5f5f5', padding: '2px 6px', borderRadius: 3 }}>{v}</code>,
    },
    { title: '显示名', dataIndex: 'display', width: 140 },
    { title: '类型', dataIndex: 'type', width: 70, render: (v: string) => <Tag>{v}</Tag> },
    { title: '单位', dataIndex: 'unit', width: 80, render: (v: string) => v || '-' },
    {
      title: '阈值', width: 160,
      render: (_: any, m: any) => {
        const t = m.thresholds || {};
        if (!t.warn && !t.crit) return '-';
        return (
          <Space size={4}>
            {t.warn && <Tag color="gold">warn: {t.warn}</Tag>}
            {t.crit && <Tag color="red">crit: {t.crit}</Tag>}
          </Space>
        );
      },
    },
    { title: '描述', dataIndex: 'description', ellipsis: true },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      {/* 顶部标题 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <BarChartOutlined style={{ fontSize: 20, color: '#1890ff' }} />
        <span style={{ fontWeight: 700, fontSize: 16 }}>指标浏览器</span>
        <div style={{ flex: 1 }} />
        <Badge count={metrics.length} style={{ backgroundColor: '#1890ff' }}>
          <Tag>指标</Tag>
        </Badge>
      </div>

      {/* 主内容：左侧树 + 右侧列表 */}
      <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
        {/* 左侧：实体类型树形导航 */}
        <Card
          size="small"
          title="实体类型"
          style={{ width: 280, flexShrink: 0 }}
          bodyStyle={{ padding: '8px', overflowY: 'auto', maxHeight: 'calc(100vh - 180px)' }}
          extra={<Button size="small" type="text" icon={<ReloadOutlined />} onClick={() => {
            axios.get(`${API_BASE}/types`).then(res => {
              setEntityTypes(Array.isArray(res.data) ? res.data : (res.data.items || []));
            });
          }} />}
        >
          <Tree
            treeData={treeData}
            defaultExpandAll
            selectedKeys={selectedType ? [selectedType] : []}
            onSelect={(keys) => {
              if (keys.length > 0) {
                setSelectedType(keys[0] as string);
              }
            }}
            showIcon
            style={{ fontSize: 12 }}
          />
        </Card>

        {/* 右侧：指标列表 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {/* 工具栏 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Input
              prefix={<SearchOutlined />}
              placeholder="搜索指标名称..."
              value={searchValue}
              onChange={e => setSearchValue(e.target.value)}
              style={{ width: 240 }}
              size="small"
              allowClear
            />
            <Select
              placeholder="按分类筛选"
              value={filterCategory}
              onChange={setFilterCategory}
              allowClear
              size="small"
              style={{ width: 160 }}
              options={categories.map(c => ({ label: catLabels[c] || c, value: c }))}
            />
            {selectedType && (
              <Tag color={NODE_COLORS[selectedType]} style={{ color: '#fff' }}>
                {TYPE_DISPLAY[selectedType] || selectedType}
              </Tag>
            )}
          </div>

          {/* 指标列表 */}
          <Card size="small" style={{ flex: 1 }} bodyStyle={{ padding: 8, overflowY: 'auto', maxHeight: 'calc(100vh - 240px)' }}>
            {metricsLoading ? (
              <Spin style={{ display: 'block', margin: '60px auto' }} />
            ) : !selectedType ? (
              <Empty description="请在左侧选择实体类型" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : filteredMetrics.length === 0 ? (
              <Empty description="暂无指标数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              Object.entries(metricsByCategory).map(([cat, items]) => (
                <div key={cat} style={{ marginBottom: 16 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 600, color: '#262626', marginBottom: 8,
                    padding: '4px 8px', background: '#fafafa', borderRadius: 4,
                  }}>
                    {catLabels[cat] || cat} ({items.length})
                  </div>
                  <Table
                    size="small"
                    pagination={false}
                    rowKey="name"
                    dataSource={items}
                    columns={metricColumns}
                    scroll={{ x: 800 }}
                  />
                </div>
              ))
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default MetricBrowser;
