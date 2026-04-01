import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Card, Select, Tag, Drawer, Descriptions, Spin, Empty, Space, Row, Col, Divider, Progress, Tooltip, Tabs, Badge, Button } from 'antd';
import {
  CheckCircleOutlined, WarningOutlined, CloseCircleOutlined,
  FireOutlined, BranchesOutlined, ApartmentOutlined,
  ClusterOutlined, ApiOutlined, DatabaseOutlined,
  DesktopOutlined, CloudServerOutlined, GlobalOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API = '/api/v1/cmdb';

// ---- 类型定义 ----
interface Entity {
  guid: string; name: string; type_name: string;
  health_score: number; health_level: string; risk_score: number;
  biz_service: string; attributes: Record<string, any>;
  blast_radius: number; propagation_hops: number;
  health_detail: any; source: string; labels: Record<string, string>;
}
interface Relation {
  guid: string; type_name: string;
  from_guid: string; to_guid: string;
  dimension: string; source: string; confidence: number;
  attributes: Record<string, any>;
}
interface DrillNode {
  entity: Entity;
  relation_type: string;
  children: DrillNode[];
}

// ---- 颜色配置 ----
const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};
const typeColors: Record<string, string> = {
  Business: '#722ed1', Service: '#1890ff', Host: '#13c2c2',
  MySQL: '#fa8c16', Redis: '#eb2f96', Database: '#fa8c16',
  NetworkDevice: '#2f54eb', Middleware: '#13c2c2',
};
const relColors: Record<string, string> = {
  calls: '#1890ff', depends_on: '#fa8c16', runs_on: '#13c2c2',
  includes: '#722ed1', hosts: '#13c2c2', connected_to: '#2f54eb',
};
const typeIcons: Record<string, React.ReactNode> = {
  Business: <ClusterOutlined />, Service: <ApiOutlined />,
  Host: <DesktopOutlined />, MySQL: <DatabaseOutlined />,
  Redis: <DatabaseOutlined />, Database: <DatabaseOutlined />,
  NetworkDevice: <CloudServerOutlined />, Middleware: <ApartmentOutlined />,
};

// ---- 分层布局（从下到上：DB→服务→业务） ----
function layoutNodes(entities: Entity[], relations: Relation[], selectedGuid?: string) {
  // 按 biz_service 分组
  const bizGroups: Record<string, Entity[]> = {};
  for (const e of entities) {
    const biz = e.biz_service || '未分组';
    (bizGroups[biz] ||= []).push(e);
  }

  // 层级顺序（从下到上）
  const layerOrder = ['NetworkDevice', 'Host', 'Redis', 'MySQL', 'Database', 'Middleware', 'Service', 'Business'];
  const W = 1100, cardW = 160, cardH = 70, layerGap = 140, bizGap = 60;

  const pos: Record<string, { x: number; y: number; layer: number; biz: string }> = {};
  let totalHeight = 60;

  for (const [biz, ents] of Object.entries(bizGroups)) {
    // 每个业务组内按类型分层
    const layers: Record<string, Entity[]> = {};
    for (const e of ents) {
      const idx = layerOrder.indexOf(e.type_name);
      const layer = idx >= 0 ? idx : 4;
      (layers[layer] ||= []).push(e);
    }

    const sortedLayers = Object.keys(layers).map(Number).sort((a, b) => a - b);
    const groupHeight = sortedLayers.length * layerGap + 40;
    const startY = totalHeight;

    // 画虚线框标题
    pos[`__biz_${biz}`] = { x: 20, y: startY, layer: -1, biz };

    for (let i = 0; i < sortedLayers.length; i++) {
      const layerIdx = sortedLayers[i];
      const items = layers[layerIdx];
      const spacing = Math.min(cardW + 30, (W - 100) / items.length);
      const sx = (W - spacing * (items.length - 1)) / 2;
      const y = startY + 30 + (sortedLayers.length - 1 - i) * layerGap; // 从下到上

      for (let j = 0; j < items.length; j++) {
        pos[items[j].guid] = { x: sx + j * spacing, y, layer: layerIdx, biz };
      }
    }

    totalHeight = startY + groupHeight + bizGap;
  }

  return { pos, height: Math.max(500, totalHeight) };
}

// ---- 纵向下钻拓扑组件 ----
const DrillDownTree: React.FC<{ entity: Entity; onClose: () => void }> = ({ entity }) => {
  const [tree, setTree] = useState<DrillNode | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTree = async () => {
      setLoading(true);
      try {
        const node = await buildDrillTree(entity.guid, 3, new Set());
        setTree(node);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    fetchTree();
  }, [entity.guid]);

  const buildDrillTree = async (guid: string, depth: number, visited: Set<string>): Promise<DrillNode | null> => {
    if (depth <= 0 || visited.has(guid)) return null;
    visited.add(guid);

    try {
      const entRes = await axios.get(`${API}/entities/${guid}`);
      const ent = entRes.data;

      const relRes = await axios.get(`${API}/entities/${guid}/relations?dimension=vertical`);
      const rels: Relation[] = relRes.data.items || [];

      const children: DrillNode[] = [];
      for (const r of rels) {
        const childGuid = r.from_guid === guid ? r.to_guid : r.from_guid;
        const child = await buildDrillTree(childGuid, depth - 1, visited);
        if (child) {
          child.relation_type = r.type_name;
          children.push(child);
        }
      }

      return { entity: ent, relation_type: '', children };
    } catch { return null; }
  };

  const renderNode = (node: DrillNode, depth: number = 0): React.ReactNode => {
    const e = node.entity;
    const hColor = healthColors[e.health_level] || '#d9d9d9';
    const indent = depth * 24;

    return (
      <div key={e.guid} style={{ marginLeft: indent, marginBottom: 8 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 10px', borderRadius: 6,
          background: depth === 0 ? `${hColor}15` : '#fafafa',
          border: `1px solid ${depth === 0 ? hColor : '#f0f0f0'}`,
        }}>
          {node.relation_type && (
            <Tag color={relColors[node.relation_type] || '#999'} style={{ fontSize: 10, marginRight: 4 }}>
              {node.relation_type}
            </Tag>
          )}
          {typeIcons[e.type_name] || <ApartmentOutlined />}
          <span style={{ fontWeight: depth === 0 ? 'bold' : 'normal' }}>{e.name}</span>
          <Tag color={typeColors[e.type_name]}>{e.type_name}</Tag>
          <Progress
            percent={e.health_score || 0}
            size="small"
            strokeColor={hColor}
            style={{ width: 60 }}
            format={(p) => <span style={{ fontSize: 10, color: hColor }}>{p}</span>}
          />
          {e.risk_score > 50 && <Tag color="red">风险{e.risk_score}</Tag>}
        </div>
        {node.children.map(c => renderNode(c, depth + 1))}
      </div>
    );
  };

  if (loading) return <Spin style={{ display: 'block', margin: '40px auto' }} />;
  if (!tree) return <Empty description="无纵向关系数据" />;

  return (
    <div style={{ maxHeight: 500, overflow: 'auto', padding: '8px 0' }}>
      {renderNode(tree)}
    </div>
  );
};

// ---- 主拓扑页面 ----
const TopologyPage: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('global');
  const [drawerTab, setDrawerTab] = useState<string>('metrics');
  const [highlightedGuid, setHighlightedGuid] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const entRes = await axios.get(`${API}/entities`, { params: { limit: 500 } });
      const entList: Entity[] = entRes.data.items || [];
      setEntities(entList);

      // 批量取关系
      const relResults = await Promise.all(
        entList.slice(0, 100).map(e =>
          axios.get(`${API}/entities/${e.guid}/relations`).catch(() => ({ data: { items: [] } }))
        )
      );
      const allRels: Relation[] = [];
      const seen = new Set<string>();
      for (const res of relResults) {
        for (const r of (res.data.items || [])) {
          const key = [r.from_guid, r.to_guid, r.type_name].sort().join('-');
          if (!seen.has(key)) { seen.add(key); allRels.push(r); }
        }
      }
      setRelations(allRels);
    } catch (err) { console.error(err); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const { pos, height } = useMemo(
    () => layoutNodes(entities, relations, highlightedGuid || undefined),
    [entities, relations, highlightedGuid]
  );
  const entityMap = useMemo(() => {
    const m: Record<string, Entity> = {};
    entities.forEach(e => m[e.guid] = e);
    return m;
  }, [entities]);

  // 业务分组
  const bizGroups = useMemo(() => {
    const g: Record<string, Entity[]> = {};
    entities.forEach(e => { (g[e.biz_service || '未分组'] ||= []).push(e); });
    return g;
  }, [entities]);

  // 选中节点的相关关系
  const relatedRels = useMemo(() => {
    if (!highlightedGuid) return new Set<string>();
    const s = new Set<string>();
    relations.forEach(r => {
      if (r.from_guid === highlightedGuid || r.to_guid === highlightedGuid) {
        s.add(r.guid);
      }
    });
    return s;
  }, [highlightedGuid, relations]);

  const handleNodeClick = (e: Entity) => {
    setSelected(e);
    setHighlightedGuid(e.guid);
    setDrawerOpen(true);
    setDrawerTab('metrics');
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setHighlightedGuid(null);
  };

  // ---- 渲染 ----
  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>
        <ApartmentOutlined style={{ marginRight: 8 }} />
        资源拓扑
      </h2>

      {/* 视图切换 Tab */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'global', label: <span><GlobalOutlined /> 全局拓扑</span> },
          { key: 'call', label: <span><ApiOutlined /> 调用拓扑</span> },
          { key: 'infra', label: <span><DesktopOutlined /> 基础设施拓扑</span> },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Space style={{ marginBottom: 12 }}>
        <span style={{ color: '#8c8c8c' }}>{entities.length} 实体 · {relations.length} 关系</span>
      </Space>

      {loading ? <Spin size="large" style={{ display: 'block', margin: '100px auto' }} /> :
        entities.length === 0 ? <Empty /> : (
        <Card size="small" style={{ overflow: 'auto', background: '#fafbfc' }}>
          <svg width="100%" height={height} viewBox={`0 0 1100 ${height}`} style={{ minWidth: 800 }}>
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#bfbfbf" />
              </marker>
              <marker id="arrow-hl" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#1890ff" />
              </marker>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              <filter id="shadow">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.1" />
              </filter>
            </defs>

            {/* 业务分组虚线框 */}
            {Object.entries(bizGroups).map(([biz, ents]) => {
              const positions = ents.map(e => pos[e.guid]).filter(Boolean);
              if (positions.length === 0) return null;
              const minX = Math.min(...positions.map(p => p.x)) - 20;
              const maxX = Math.max(...positions.map(p => p.x)) + 180;
              const minY = Math.min(...positions.map(p => p.y)) - 10;
              const maxY = Math.max(...positions.map(p => p.y)) + 80;
              return (
                <g key={`biz-${biz}`}>
                  <rect x={minX} y={minY} width={maxX - minX} height={maxY - minY}
                    rx={12} fill="none" stroke="#d9d9d9" strokeWidth={1.5}
                    strokeDasharray="8,4" />
                  <text x={minX + 8} y={minY - 4} fontSize={11} fill="#8c8c8c" fontWeight="bold">
                    📦 {biz}
                  </text>
                </g>
              );
            })}

            {/* 关系连线 */}
            {relations.map(rel => {
              const from = pos[rel.from_guid], to = pos[rel.to_guid];
              if (!from || !to) return null;
              const isHighlighted = relatedRels.has(rel.guid);
              const isDimmed = highlightedGuid && !isHighlighted;
              const srcEntity = entityMap[rel.from_guid];
              const isBad = srcEntity && (srcEntity.health_level === 'critical' || srcEntity.health_level === 'down');
              const lineColor = isHighlighted ? '#1890ff' : isBad ? '#ff4d4f60' : (relColors[rel.type_name] || '#d9d9d9') + '40';

              return (
                <g key={rel.guid} opacity={isDimmed ? 0.15 : 1}>
                  <line x1={from.x + 80} y1={from.y + 35} x2={to.x + 80} y2={to.y + 35}
                    stroke={lineColor} strokeWidth={isHighlighted ? 2.5 : 1.2}
                    strokeDasharray={rel.type_name === 'runs_on' || rel.type_name === 'hosts' ? '4,3' : 'none'}
                    markerEnd={isHighlighted ? 'url(#arrow-hl)' : 'url(#arrow)'} />
                  {isHighlighted && (
                    <text x={(from.x + to.x) / 2 + 80} y={(from.y + to.y) / 2 + 30}
                      fontSize={9} fill="#1890ff" fontWeight="bold">{rel.type_name}</text>
                  )}
                </g>
              );
            })}

            {/* 节点卡片 */}
            {entities.map(e => {
              const p = pos[e.guid];
              if (!p) return null;
              const hColor = healthColors[e.health_level] || '#d9d9d9';
              const isBad = e.health_level === 'critical' || e.health_level === 'down';
              const isSelected = highlightedGuid === e.guid;
              const isDimmed = highlightedGuid && !isSelected && !relatedRels.has(
                relations.find(r => r.from_guid === e.guid || r.to_guid === e.guid)?.guid || ''
              );
              const icon = typeIcons[e.type_name] || <ApartmentOutlined />;

              return (
                <g key={e.guid}
                  style={{ cursor: 'pointer' }}
                  opacity={isDimmed ? 0.2 : 1}
                  onClick={() => handleNodeClick(e)}
                >
                  {/* 异常脉冲 */}
                  {isBad && <>
                    <rect x={p.x - 4} y={p.y - 4} width={168} height={78} rx={12}
                      fill={hColor} opacity={0.06} />
                  </>}
                  {/* 卡片背景 */}
                  <rect x={p.x} y={p.y} width={160} height={70} rx={8}
                    fill="white" stroke={isSelected ? '#1890ff' : isBad ? hColor : '#e8e8e8'}
                    strokeWidth={isSelected ? 2.5 : isBad ? 2 : 1}
                    filter={isBad ? 'url(#glow)' : 'url(#shadow)'} />
                  {/* 左侧类型色条 */}
                  <rect x={p.x} y={p.y} width={4} height={70} rx={2}
                    fill={typeColors[e.type_name] || '#999'} />
                  {/* 健康度指示条 */}
                  <rect x={p.x + 4} y={p.y} width={156} height={3} rx={1}
                    fill={hColor} opacity={0.3} />
                  {/* 服务名 */}
                  <text x={p.x + 16} y={p.y + 26} fontSize={12} fontWeight="bold" fill="#262626">
                    {e.name.length > 16 ? e.name.slice(0, 14) + '…' : e.name}
                  </text>
                  {/* 类型 + 健康度 */}
                  <text x={p.x + 16} y={p.y + 44} fontSize={10} fill="#8c8c8c">
                    {e.type_name}
                  </text>
                  <text x={p.x + 80} y={p.y + 44} fontSize={10} fontWeight="bold" fill={hColor}>
                    {e.health_score ?? '?'}分
                  </text>
                  {/* 风险度标签 */}
                  {(e.risk_score ?? 0) > 50 && (
                    <text x={p.x + 120} y={p.y + 44} fontSize={9} fill="#ff4d4f">
                      🔥{e.risk_score}
                    </text>
                  )}
                  {/* 底部标签 */}
                  {e.biz_service && (
                    <text x={p.x + 16} y={p.y + 60} fontSize={9} fill="#bfbfbf">
                      {e.biz_service}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </Card>
      )}

      {/* 图例 */}
      <Card title="图例" size="small" style={{ marginTop: 16 }}>
        <Row gutter={[24, 8]}>
          <Col>
            <strong>健康度：</strong>
            {Object.entries(healthColors).map(([l, c]) => <Tag key={l} color={c}>{l}</Tag>)}
          </Col>
          <Col>
            <strong>类型：</strong>
            {Object.entries(typeColors).map(([t, c]) => <Tag key={t} color={c}>{t}</Tag>)}
          </Col>
          <Col>
            <strong>关系：</strong>
            {Object.entries(relColors).map(([r, c]) => <Tag key={r} color={c}>{r}</Tag>)}
          </Col>
        </Row>
      </Card>

      {/* 详情抽屉（博睿风格三 Tab） */}
      <Drawer
        title={
          <Space>
            {selected && typeIcons[selected.type_name]}
            <span>{selected?.name || '详情'}</span>
            {selected && <Tag color={healthColors[selected.health_level]}>{selected.health_level}</Tag>}
          </Space>
        }
        open={drawerOpen}
        onClose={handleDrawerClose}
        width={480}
      >
        {selected && (
          <>
            {/* 基础信息 */}
            <Descriptions column={1} size="small">
              <Descriptions.Item label="类型">
                <Tag color={typeColors[selected.type_name]}>{selected.type_name}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="健康度">
                <Space>
                  <Progress percent={selected.health_score || 0} size="small"
                    strokeColor={healthColors[selected.health_level]} style={{ width: 100 }} />
                  <Tag color={healthColors[selected.health_level]}>{selected.health_level}</Tag>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="风险度">
                <span style={{
                  color: (selected.risk_score || 0) >= 50 ? '#ff4d4f' : '#52c41a',
                  fontWeight: 'bold', fontSize: 18,
                }}>
                  {selected.risk_score ?? 0}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="影响范围">
                <Space>
                  <BranchesOutlined />
                  <span>{selected.blast_radius || 0} 个实体受影响</span>
                  <span style={{ color: '#8c8c8c' }}>{selected.propagation_hops || 0} 跳传播</span>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="业务">{selected.biz_service || '-'}</Descriptions.Item>
            </Descriptions>

            <Divider style={{ margin: '12px 0' }} />

            {/* 一级 Tab：指标 / 下钻拓扑 */}
            <Tabs
              activeKey={drawerTab}
              onChange={setDrawerTab}
              size="small"
              items={[
                {
                  key: 'metrics',
                  label: '📊 指标',
                  children: (
                    <>
                      {/* 健康度维度 */}
                      {selected.health_detail && typeof selected.health_detail === 'object' && (
                        <>
                          <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 8 }}>健康度维度</div>
                          {Object.entries(selected.health_detail)
                            .filter(([k]) => !['method', 'reason', 'children_count', 'children_avg', 'min_score', 'max_score'].includes(k))
                            .map(([dim, info]: [string, any]) => (
                              <Row key={dim} style={{ marginBottom: 8 }}>
                                <Col span={8}><strong style={{ fontSize: 12 }}>{dim}</strong></Col>
                                <Col span={8}>
                                  <Progress percent={info.score || 0} size="small"
                                    strokeColor={(info.score || 0) >= 80 ? '#52c41a' : (info.score || 0) >= 60 ? '#faad14' : '#ff4d4f'}
                                    style={{ width: 80 }} />
                                </Col>
                                <Col span={8} style={{ color: '#8c8c8c', fontSize: 12 }}>
                                  值: {info.value ?? 'N/A'}
                                </Col>
                              </Row>
                            ))}
                        </>
                      )}
                      {/* 属性 */}
                      <Divider orientation="left" plain style={{ fontSize: 11 }}>属性</Divider>
                      <Space wrap>
                        {Object.entries(selected.attributes || {}).map(([k, v]) => (
                          <Tag key={k}>{k}: {String(v)}</Tag>
                        ))}
                      </Space>
                    </>
                  ),
                },
                {
                  key: 'drill',
                  label: '🌲 纵向下钻',
                  children: <DrillDownTree entity={selected} onClose={() => {}} />,
                },
                {
                  key: 'relations',
                  label: '🔗 关系',
                  children: (
                    <div style={{ maxHeight: 400, overflow: 'auto' }}>
                      {relations
                        .filter(r => r.from_guid === selected.guid || r.to_guid === selected.guid)
                        .map(r => {
                          const otherGuid = r.from_guid === selected.guid ? r.to_guid : r.from_guid;
                          const other = entityMap[otherGuid];
                          const direction = r.from_guid === selected.guid ? '→' : '←';
                          return (
                            <div key={r.guid} style={{
                              display: 'flex', alignItems: 'center', gap: 8,
                              padding: '6px 8px', marginBottom: 4,
                              background: '#fafafa', borderRadius: 4,
                            }}>
                              <Tag color={relColors[r.type_name] || '#999'} style={{ fontSize: 10 }}>
                                {r.type_name}
                              </Tag>
                              <span>{direction}</span>
                              <span style={{ fontWeight: 'bold' }}>{other?.name || otherGuid.slice(0, 8)}</span>
                              {other && <Tag color={typeColors[other.type_name]}>{other.type_name}</Tag>}
                              <Tag color={r.dimension === 'horizontal' ? 'blue' : 'green'} style={{ fontSize: 9 }}>
                                {r.dimension || 'vertical'}
                              </Tag>
                            </div>
                          );
                        })}
                    </div>
                  ),
                },
              ]}
            />
          </>
        )}
      </Drawer>
    </div>
  );
};

export default TopologyPage;
