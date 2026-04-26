import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Tabs, Input, Button, Space, Tag, Drawer, Descriptions, Table, Spin, Empty,
  Tooltip, Select, Badge, Collapse, Typography, Divider, Row, Col, Card, Statistic,
  Checkbox, Radio,
} from 'antd';
import {
  DatabaseOutlined, SearchOutlined, FilterOutlined, ZoomInOutlined, ZoomOutOutlined,
  CompressOutlined, ApartmentOutlined, ApiOutlined, DesktopOutlined, CloudServerOutlined,
  NodeIndexOutlined, ExpandOutlined, InfoCircleOutlined, ReloadOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

// ========== 4层逻辑分区定义 ==========
const LAYERS = [
  { key: 'L1', label: 'L1 业务层', color: '#e8f5e9', borderColor: '#a5d6a7', types: ['BusinessModule', 'BusinessEvent', 'E2ECallChain'] },
  { key: 'L2', label: 'L2 应用层', color: '#e3f2fd', borderColor: '#90caf9', types: ['TerminalApp', 'Page', 'NetworkRequest', 'UserAction', 'Service', 'ServiceInstance', 'Interface', 'KeyMethod'] },
  { key: 'L3', label: 'L3 服务层', color: '#fff3e0', borderColor: '#ffcc80', types: ['Database', 'MySQL', 'Redis', 'Cache', 'MessageQueue', 'ObjectStorage', 'SearchEngine', 'Middleware'] },
  { key: 'L4', label: 'L4 基础设施层', color: '#f3e5f5', borderColor: '#ce93d8', types: ['Host', 'Container', 'Process', 'ProcessGroup', 'NetworkDevice', 'StorageDevice', 'CloudResource', 'K8sCluster', 'K8sNode', 'K8sPod', 'K8sService', 'K8sWorkload', 'IP'] },
];

// ========== 节点颜色映射 ==========
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

// ========== 获取节点所在层级 ==========
function getLayerForType(typeName: string) {
  for (const layer of LAYERS) {
    if (layer.types.includes(typeName)) return layer;
  }
  return LAYERS[3]; // default to L4
}

// ========== 拓扑节点组件 ==========
const TopoNode: React.FC<{
  entity: any;
  x: number;
  y: number;
  selected: boolean;
  onClick: () => void;
  scale: number;
}> = ({ entity, x, y, selected, onClick, scale }) => {
  const color = NODE_COLORS[entity.type_name] || '#8c8c8c';
  const display = TYPE_DISPLAY[entity.type_name] || entity.type_name;
  const nodeSize = 36;

  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{ cursor: 'pointer' }}
    >
      {/* 选中高亮 */}
      {selected && (
        <circle r={nodeSize / 2 + 6} fill="none" stroke={color} strokeWidth={3} strokeDasharray="4 2" opacity={0.7} />
      )}
      {/* 节点圆形 */}
      <circle
        r={nodeSize / 2}
        fill={color}
        stroke={selected ? '#ff4d4f' : '#fff'}
        strokeWidth={selected ? 2.5 : 1.5}
        style={{ filter: 'drop-shadow(0 1px 3px rgba(0,0,0,0.15))' }}
      />
      {/* 类型首字母 */}
      <text
        textAnchor="middle"
        dominantBaseline="central"
        fill="#fff"
        fontSize={12}
        fontWeight={700}
        style={{ pointerEvents: 'none' }}
      >
        {display.charAt(0)}
      </text>
      {/* 名称标签 */}
      <text
        textAnchor="middle"
        y={nodeSize / 2 + 14}
        fill="#333"
        fontSize={10}
        fontWeight={500}
        style={{ pointerEvents: 'none' }}
      >
        {entity.name?.length > 12 ? entity.name.slice(0, 12) + '…' : entity.name}
      </text>
    </g>
  );
};

// ========== 拓扑连线组件 ==========
const TopoEdge: React.FC<{
  x1: number; y1: number;
  x2: number; y2: number;
}> = ({ x1, y1, x2, y2 }) => {
  const midY = (y1 + y2) / 2;
  const d = `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;
  return (
    <path
      d={d}
      fill="none"
      stroke="#c0c0c0"
      strokeWidth={1.5}
      strokeDasharray="6 3"
      markerEnd="url(#arrowhead)"
      opacity={0.5}
    />
  );
};

// ========== CMDB 主页面 ==========
const CmdbPage: React.FC = () => {
  // 数据状态
  const [entities, setEntities] = useState<any[]>([]);
  const [entityTypes, setEntityTypes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('topology');

  // 拓扑图状态
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const [filterTypes, setFilterTypes] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  // 拖拽状态
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // 实体详情
  const [entityDetail, setEntityDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // ========== 数据加载 ==========
  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [entRes, typeRes] = await Promise.all([
        axios.get(`${API_BASE}/entities`, { params: { limit: 500 } }),
        axios.get(`${API_BASE}/types`).catch(() => ({ data: [] })),
      ]);
      setEntities(entRes.data.items || []);
      setEntityTypes(Array.isArray(typeRes.data) ? typeRes.data : (typeRes.data.items || []));
    } catch (e) {
      console.error('Failed to fetch CMDB data:', e);
    }
    setLoading(false);
  };

  // ========== 加载实体详情 ==========
  const loadEntityDetail = async (entity: any) => {
    setSelectedEntity(entity);
    setDrawerOpen(true);
    setDetailLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/entities/${entity.guid}`).catch(() => ({ data: entity }));
      setEntityDetail(res.data);
    } catch {
      setEntityDetail(entity);
    }
    setDetailLoading(false);
  };

  // ========== 过滤后的实体 ==========
  const filteredEntities = entities.filter(e => {
    if (filterTypes.length > 0 && !filterTypes.includes(e.type_name)) return false;
    if (searchValue && !e.name?.toLowerCase().includes(searchValue.toLowerCase())) return false;
    return true;
  });

  // ========== 计算节点位置 ==========
  const computeLayout = useCallback(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    const layerHeight = 160;
    const startY = 40;

    LAYERS.forEach((layer, layerIdx) => {
      const layerEntities = filteredEntities.filter(e => layer.types.includes(e.type_name));
      const rowY = startY + layerIdx * layerHeight;
      const nodeSpacing = 120;
      const totalWidth = layerEntities.length * nodeSpacing;
      const startX = Math.max(60, 600 - totalWidth / 2);

      layerEntities.forEach((entity, i) => {
        positions[entity.guid] = {
          x: startX + i * nodeSpacing,
          y: rowY + 40 + (i % 2) * 30,
        };
      });
    });

    return positions;
  }, [filteredEntities]);

  const positions = computeLayout();

  // ========== 计算关系连线 ==========
  const computeEdges = useCallback(() => {
    const edges: { from: string; to: string }[] = [];
    filteredEntities.forEach(e => {
      if (e.relations) {
        e.relations.forEach((r: any) => {
          if (positions[r.target_guid]) {
            edges.push({ from: e.guid, to: r.target_guid });
          }
        });
      }
    });
    return edges;
  }, [filteredEntities, positions]);

  const edges = computeEdges();

  // ========== SVG 尺寸 ==========
  const svgWidth = 1200;
  const svgHeight = 700;

  // ========== 拖拽处理 ==========
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setScale(s => Math.min(3, Math.max(0.3, s + delta)));
  };

  // ========== 缩放控制 ==========
  const zoomIn = () => setScale(s => Math.min(3, s + 0.2));
  const zoomOut = () => setScale(s => Math.max(0.3, s - 0.2));
  const zoomFit = () => { setScale(1); setOffset({ x: 0, y: 0 }); };

  // ========== 搜索定位 ==========
  const handleSearch = (value: string) => {
    setSearchValue(value);
    if (value) {
      const found = filteredEntities.find(e =>
        e.name?.toLowerCase().includes(value.toLowerCase())
      );
      if (found && positions[found.guid]) {
        const pos = positions[found.guid];
        setOffset({
          x: svgWidth / 2 - pos.x * scale,
          y: svgHeight / 2 - pos.y * scale,
        });
      }
    }
  };

  // ========== 所有可用类型（用于筛选） ==========
  const allTypes = [...new Set(entities.map(e => e.type_name))].sort();

  // ========== 顶部标签页内容 ==========
  const tabItems = [
    {
      key: 'topology',
      label: <span><ApartmentOutlined /> 拓扑视图</span>,
      children: null, // 渲染在下方
    },
    {
      key: 'entities',
      label: <span><DatabaseOutlined /> 实体列表</span>,
      children: null,
    },
    {
      key: 'metrics',
      label: <span><NodeIndexOutlined /> 指标</span>,
      children: null,
    },
    {
      key: 'meta',
      label: <span><InfoCircleOutlined /> 元属性</span>,
      children: null,
    },
    {
      key: 'dict',
      label: <span><FilterOutlined /> 字典</span>,
      children: null,
    },
  ];

  // ========== 实体列表视图 ==========
  const renderEntityList = () => (
    <Table
      dataSource={filteredEntities}
      rowKey="guid"
      size="small"
      loading={loading}
      pagination={{ pageSize: 20, showSizeChanger: true }}
      onRow={(record) => ({
        onClick: () => loadEntityDetail(record),
        style: { cursor: 'pointer' },
      })}
      columns={[
        {
          title: '类型', dataIndex: 'type_name', width: 120,
          render: (v: string) => (
            <Tag color={NODE_COLORS[v] || '#8c8c8c'} style={{ color: '#fff' }}>
              {TYPE_DISPLAY[v] || v}
            </Tag>
          ),
        },
        { title: '名称', dataIndex: 'name', width: 200, render: (v: string) => <strong>{v}</strong> },
        {
          title: '健康度', dataIndex: 'health_score', width: 100,
          render: (v: number, r: any) => (
            <span style={{ color: v >= 80 ? '#52c41a' : v >= 60 ? '#faad14' : '#ff4d4f', fontWeight: 600 }}>
              {v ?? '-'}
            </span>
          ),
        },
        {
          title: '标签', dataIndex: 'labels', width: 250,
          render: (labels: Record<string, string>) => (
            <Space wrap size={2}>
              {Object.entries(labels || {}).slice(0, 3).map(([k, v]) => (
                <Tag key={k} style={{ fontSize: 11 }}>{k}: {v}</Tag>
              ))}
            </Space>
          ),
        },
        { title: '来源', dataIndex: 'source', width: 80 },
        {
          title: '更新时间', dataIndex: 'updated_at', width: 140,
          render: (t: string) => t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-',
        },
      ]}
    />
  );

  // ========== 指标视图 ==========
  const renderMetrics = () => (
    <Empty description="指标浏览器请前往「指标浏览器」页面" image={Empty.PRESENTED_IMAGE_SIMPLE}>
      <Button type="primary" onClick={() => window.location.hash = '#/metric-browser'}>
        前往指标浏览器
      </Button>
    </Empty>
  );

  // ========== 元属性视图 ==========
  const renderMeta = () => (
    <Table
      dataSource={entityTypes}
      rowKey="type_name"
      size="small"
      pagination={{ pageSize: 20 }}
      columns={[
        { title: '类型名', dataIndex: 'type_name', width: 160, render: (v: string) => <code>{v}</code> },
        { title: '显示名', dataIndex: 'display_name', width: 120 },
        { title: '分类', dataIndex: 'category', width: 100 },
        { title: '属性数', dataIndex: 'attr_count', width: 80 },
        { title: '指标数', dataIndex: 'metric_count', width: 80 },
        { title: '关系数', dataIndex: 'relation_count', width: 80 },
      ]}
    />
  );

  // ========== 字典视图 ==========
  const renderDict = () => (
    <div>
      <Typography.Title level={5}>实体类型字典</Typography.Title>
      {LAYERS.map(layer => (
        <div key={layer.key} style={{ marginBottom: 16 }}>
          <div style={{
            padding: '6px 12px', background: layer.color, borderLeft: `3px solid ${layer.borderColor}`,
            fontWeight: 600, fontSize: 13, marginBottom: 8, borderRadius: '0 4px 4px 0',
          }}>
            {layer.label}
          </div>
          <Space wrap>
            {layer.types.map(t => (
              <Tag key={t} color={NODE_COLORS[t]} style={{ color: '#fff', fontSize: 12 }}>
                {TYPE_DISPLAY[t] || t}
              </Tag>
            ))}
          </Space>
        </div>
      ))}
    </div>
  );

  // ========== 拓扑图渲染 ==========
  const renderTopology = () => (
    <div style={{ position: 'relative', width: '100%', height: 'calc(100vh - 260px)', minHeight: 500, overflow: 'hidden', background: '#fafafa', borderRadius: 8, border: '1px solid #e8e8e8' }}>
      {/* 缩放控制 */}
      <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <Tooltip title="放大"><Button size="small" icon={<ZoomInOutlined />} onClick={zoomIn} /></Tooltip>
        <Tooltip title="缩小"><Button size="small" icon={<ZoomOutOutlined />} onClick={zoomOut} /></Tooltip>
        <Tooltip title="适应画布"><Button size="small" icon={<CompressOutlined />} onClick={zoomFit} /></Tooltip>
        <Tooltip title="刷新"><Button size="small" icon={<ReloadOutlined />} onClick={fetchData} /></Tooltip>
      </div>

      {/* 比例显示 */}
      <div style={{ position: 'absolute', bottom: 12, left: 12, zIndex: 10, fontSize: 11, color: '#8c8c8c' }}>
        {Math.round(scale * 100)}% | {filteredEntities.length} 实体 | {edges.length} 关系
      </div>

      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#c0c0c0" />
          </marker>
        </defs>

        <g transform={`translate(${offset.x}, ${offset.y}) scale(${scale})`}>
          {/* 4层逻辑分区背景 */}
          {LAYERS.map((layer, idx) => {
            const layerEntities = filteredEntities.filter(e => layer.types.includes(e.type_name));
            if (layerEntities.length === 0) return null;
            const y = 20 + idx * 160;
            return (
              <g key={layer.key}>
                <rect
                  x={10} y={y} width={svgWidth - 20} height={150}
                  rx={8} ry={8}
                  fill={layer.color}
                  stroke={layer.borderColor}
                  strokeWidth={1}
                  opacity={0.6}
                />
                <text x={24} y={y + 20} fill="#666" fontSize={12} fontWeight={600}>
                  {layer.label}
                </text>
              </g>
            );
          })}

          {/* 关系连线 */}
          {edges.map((edge, i) => {
            const p1 = positions[edge.from];
            const p2 = positions[edge.to];
            if (!p1 || !p2) return null;
            return <TopoEdge key={i} x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} />;
          })}

          {/* 实体节点 */}
          {filteredEntities.map(entity => {
            const pos = positions[entity.guid];
            if (!pos) return null;
            return (
              <TopoNode
                key={entity.guid}
                entity={entity}
                x={pos.x}
                y={pos.y}
                selected={selectedEntity?.guid === entity.guid}
                onClick={() => loadEntityDetail(entity)}
                scale={scale}
              />
            );
          })}

          {filteredEntities.length === 0 && !loading && (
            <text x={svgWidth / 2} y={svgHeight / 2} textAnchor="middle" fill="#999" fontSize={14}>
              暂无实体数据
            </text>
          )}
        </g>
      </svg>
    </div>
  );

  // ========== 详情面板内容 ==========
  const renderDetailContent = () => {
    if (!entityDetail) return <Empty description="选择节点查看详情" />;
    const layer = getLayerForType(entityDetail.type_name);
    const color = NODE_COLORS[entityDetail.type_name] || '#8c8c8c';

    return (
      <div style={{ padding: '0 4px' }}>
        {/* 实体头部 */}
        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%', background: color,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 22, fontWeight: 700, marginBottom: 8,
          }}>
            {(TYPE_DISPLAY[entityDetail.type_name] || entityDetail.type_name).charAt(0)}
          </div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{entityDetail.name}</div>
          <Tag color={color} style={{ marginTop: 4 }}>
            {TYPE_DISPLAY[entityDetail.type_name] || entityDetail.type_name}
          </Tag>
          <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 4 }}>
            {layer.label}
          </div>
        </div>

        <Divider style={{ margin: '12px 0' }} />

        {/* 基本信息 */}
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="GUID">{entityDetail.guid}</Descriptions.Item>
          <Descriptions.Item label="类型">{entityDetail.type_name}</Descriptions.Item>
          <Descriptions.Item label="健康度">
            <span style={{
              color: (entityDetail.health_score || 0) >= 80 ? '#52c41a' :
                     (entityDetail.health_score || 0) >= 60 ? '#faad14' : '#ff4d4f',
              fontWeight: 700,
            }}>
              {entityDetail.health_score ?? '-'}
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="来源">{entityDetail.source || '-'}</Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {entityDetail.updated_at ? new Date(entityDetail.updated_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
        </Descriptions>

        {/* 标签 */}
        {entityDetail.labels && Object.keys(entityDetail.labels).length > 0 && (
          <>
            <Divider orientation="left" plain style={{ fontSize: 12 }}>标签</Divider>
            <Space wrap size={4}>
              {Object.entries(entityDetail.labels).map(([k, v]) => (
                <Tag key={k} style={{ fontSize: 11 }}>{k}: {String(v)}</Tag>
              ))}
            </Space>
          </>
        )}

        {/* 关系 */}
        {entityDetail.relations && entityDetail.relations.length > 0 && (
          <>
            <Divider orientation="left" plain style={{ fontSize: 12 }}>关系 ({entityDetail.relations.length})</Divider>
            {entityDetail.relations.map((r: any, i: number) => (
              <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid #f0f0f0', fontSize: 12 }}>
                <Tag color={r.direction === 'out' ? 'blue' : 'green'} style={{ fontSize: 10 }}>
                  {r.direction === 'out' ? '→' : '←'}
                </Tag>
                <span style={{ fontWeight: 500 }}>{r.type}</span>
                <span style={{ color: '#8c8c8c', marginLeft: 4 }}>{r.target_name || r.target_guid}</span>
              </div>
            ))}
          </>
        )}

        {/* 指标概要 */}
        {entityDetail.metrics && Object.keys(entityDetail.metrics).length > 0 && (
          <>
            <Divider orientation="left" plain style={{ fontSize: 12 }}>关键指标</Divider>
            <Descriptions column={1} size="small">
              {Object.entries(entityDetail.metrics).slice(0, 8).map(([k, v]) => (
                <Descriptions.Item key={k} label={k}>
                  {typeof v === 'number' ? v.toFixed(2) : String(v)}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </>
        )}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      {/* 顶部工具栏 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <DatabaseOutlined style={{ fontSize: 20, color: '#1890ff' }} />
        <span style={{ fontWeight: 700, fontSize: 16 }}>CMDB 实体模型</span>

        <div style={{ flex: 1 }} />

        <Button
          icon={<FilterOutlined />}
          onClick={() => setShowFilters(!showFilters)}
          type={showFilters ? 'primary' : 'default'}
          size="small"
        >
          筛选
        </Button>

        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索实体名称..."
          value={searchValue}
          onChange={e => setSearchValue(e.target.value)}
          onPressEnter={e => handleSearch((e.target as HTMLInputElement).value)}
          style={{ width: 220 }}
          size="small"
          allowClear
        />

        <Badge count={filteredEntities.length} style={{ backgroundColor: '#1890ff' }}>
          <Tag>实体</Tag>
        </Badge>
      </div>

      {/* 筛选面板 */}
      {showFilters && (
        <Card size="small" style={{ marginBottom: 8 }} bodyStyle={{ padding: '8px 16px' }}>
          <Space wrap>
            <span style={{ fontSize: 12, fontWeight: 600 }}>类型筛选:</span>
            <Checkbox.Group
              value={filterTypes}
              onChange={(vals) => setFilterTypes(vals as string[])}
              style={{ fontSize: 11 }}
            >
              {allTypes.map(t => (
                <Checkbox key={t} value={t} style={{ fontSize: 11 }}>
                  <Tag color={NODE_COLORS[t]} style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: 0 }}>
                    {TYPE_DISPLAY[t] || t}
                  </Tag>
                </Checkbox>
              ))}
            </Checkbox.Group>
            {filterTypes.length > 0 && (
              <Button size="small" type="link" onClick={() => setFilterTypes([])}>清除</Button>
            )}
          </Space>
        </Card>
      )}

      {/* 标签页 + 主内容 */}
      <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
        {/* 左侧主区域 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={tabItems}
            size="small"
            style={{ marginBottom: 0 }}
          />

          {/* 根据 tab 渲染内容 */}
          <div style={{ marginTop: activeTab === 'topology' ? -48 : 0 }}>
            {activeTab === 'topology' && renderTopology()}
            {activeTab === 'entities' && renderEntityList()}
            {activeTab === 'metrics' && renderMetrics()}
            {activeTab === 'meta' && renderMeta()}
            {activeTab === 'dict' && renderDict()}
          </div>
        </div>

        {/* 右侧详情面板 */}
        <div style={{
          width: drawerOpen ? 360 : 0,
          minWidth: drawerOpen ? 360 : 0,
          transition: 'all 0.3s',
          overflow: 'hidden',
          background: '#fff',
          borderLeft: drawerOpen ? '1px solid #e8e8e8' : 'none',
          borderRadius: 8,
        }}>
          {drawerOpen && (
            <div style={{ padding: 16, height: '100%', overflowY: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>实体详情</span>
                <Button size="small" type="text" onClick={() => { setDrawerOpen(false); setSelectedEntity(null); setEntityDetail(null); }}>
                  ✕
                </Button>
              </div>
              {detailLoading ? <Spin style={{ display: 'block', margin: '40px auto' }} /> : renderDetailContent()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CmdbPage;
