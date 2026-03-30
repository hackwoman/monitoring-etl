import React, { useState, useEffect, useMemo } from 'react';
import { Card, Select, Tag, Drawer, Descriptions, Spin, Empty, Space, Row, Col, Divider, Progress, Tooltip } from 'antd';
import { CheckCircleOutlined, WarningOutlined, CloseCircleOutlined, FireOutlined, BranchesOutlined } from '@ant-design/icons';
import axios from 'axios';

const API = '/api/v1/cmdb';

interface Entity {
  guid: string; name: string; type_name: string;
  health_score: number; health_level: string; risk_score: number;
  biz_service: string; attributes: Record<string, any>;
  blast_radius: number; propagation_hops: number;
  health_detail: any;
}
interface Relation { guid: string; type_name: string; from_guid: string; to_guid: string; }

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};
const typeColors: Record<string, string> = {
  Business: '#722ed1', Service: '#1890ff', Host: '#13c2c2',
  MySQL: '#fa8c16', Redis: '#eb2f96', NetworkDevice: '#2f54eb', Database: '#fa8c16',
};
const relColors: Record<string, string> = {
  calls: '#1890ff', depends_on: '#fa8c16', runs_on: '#13c2c2',
  includes: '#722ed1', hosts: '#13c2c2', connected_to: '#2f54eb',
};

// ---- 分层布局 ----
function layoutNodes(entities: Entity[], filter?: string) {
  const typeOrder = ['Business', 'Service', 'MySQL', 'Redis', 'Database', 'Host', 'NetworkDevice'];
  const filtered = filter ? entities.filter(e => e.type_name === filter) : entities;
  const grouped: Record<string, Entity[]> = {};
  for (const e of filtered) { (grouped[e.type_name] ||= []).push(e); }

  const pos: Record<string, { x: number; y: number }> = {};
  const W = 960, rowH = 130, startY = 50;
  let row = 0;
  const usedTypes = typeOrder.filter(t => grouped[t]?.length);
  // 未分类追加
  for (const t of Object.keys(grouped)) if (!typeOrder.includes(t)) usedTypes.push(t);

  for (const type of usedTypes) {
    const items = grouped[type] || [];
    if (!items.length) continue;
    const sp = Math.min(150, (W - 80) / items.length);
    const sx = (W - sp * (items.length - 1)) / 2;
    items.forEach((e, i) => { pos[e.guid] = { x: sx + i * sp, y: startY + row * rowH }; });
    row++;
  }
  return { pos, rows: row, height: Math.max(400, startY + row * rowH + 60) };
}

const TopologyPage: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>();
  const [selected, setSelected] = useState<Entity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetchData = async (typeName?: string) => {
    setLoading(true);
    try {
      const params: any = { limit: 500 };
      if (typeName) params.type_name = typeName;
      const entRes = await axios.get(`${API}/entities`, { params });
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
          const key = [r.from_guid, r.to_guid].sort().join('-');
          if (!seen.has(key)) { seen.add(key); allRels.push(r); }
        }
      }
      setRelations(allRels);
    } catch (err) { console.error(err); }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const { pos, height } = useMemo(() => layoutNodes(entities, typeFilter), [entities, typeFilter]);
  const entityMap = useMemo(() => {
    const m: Record<string, Entity> = {};
    entities.forEach(e => m[e.guid] = e);
    return m;
  }, [entities]);

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>🗺️ 资源拓扑</h2>
      <Space style={{ marginBottom: 16 }}>
        <Select placeholder="按类型筛选" allowClear style={{ width: 180 }} value={typeFilter}
          onChange={v => { setTypeFilter(v); fetchData(v); }}
          options={['Business', 'Service', 'Host', 'MySQL', 'Redis', 'NetworkDevice'].map(t => ({ label: t, value: t }))} />
        <span style={{ color: '#8c8c8c' }}>{entities.length} 实体 · {relations.length} 关系</span>
      </Space>

      {loading ? <Spin size="large" style={{ display: 'block', margin: '100px auto' }} /> :
        entities.length === 0 ? <Empty /> : (
        <Card size="small" style={{ overflow: 'auto' }}>
          <svg width="100%" height={height} viewBox={`0 0 960 ${height}`} style={{ minWidth: 700 }}>
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#bfbfbf" />
              </marker>
              {/* 发光滤镜 */}
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* 关系连线 */}
            {relations.map(rel => {
              const from = pos[rel.from_guid], to = pos[rel.to_guid];
              if (!from || !to) return null;
              const srcEntity = entityMap[rel.from_guid];
              const isBad = srcEntity && (srcEntity.health_level === 'critical' || srcEntity.health_level === 'down');
              const lineColor = isBad ? '#ff4d4f40' : (relColors[rel.type_name] || '#d9d9d9') + '60';
              return (
                <g key={rel.guid}>
                  <line x1={from.x} y1={from.y + 22} x2={to.x} y2={to.y - 22}
                    stroke={lineColor} strokeWidth={isBad ? 2 : 1.2}
                    strokeDasharray={rel.type_name === 'runs_on' ? '4,3' : 'none'}
                    markerEnd="url(#arrow)" />
                  <text x={(from.x + to.x) / 2 + 12} y={(from.y + to.y) / 2}
                    fontSize={9} fill="#8c8c8c">{rel.type_name}</text>
                </g>
              );
            })}

            {/* 节点 */}
            {entities.map(e => {
              const p = pos[e.guid];
              if (!p) return null;
              const hColor = healthColors[e.health_level] || '#d9d9d9';
              const tColor = typeColors[e.type_name] || '#8c8c8c';
              const isBad = e.health_level === 'critical' || e.health_level === 'down';
              const radius = isBad ? 22 : 18;
              return (
                <g key={e.guid} style={{ cursor: 'pointer' }} onClick={() => { setSelected(e); setDrawerOpen(true); }}>
                  {/* 异常脉冲光环 */}
                  {isBad && <>
                    <circle cx={p.x} cy={p.y} r={radius + 12} fill={hColor} opacity={0.08} />
                    <circle cx={p.x} cy={p.y} r={radius + 6} fill={hColor} opacity={0.12} />
                  </>}
                  {/* 健康度底色 */}
                  <circle cx={p.x} cy={p.y} r={radius + 2} fill={hColor} opacity={0.15} />
                  {/* 主圆形 */}
                  <circle cx={p.x} cy={p.y} r={radius} fill="white" stroke={hColor}
                    strokeWidth={isBad ? 3 : 2} filter={isBad ? 'url(#glow)' : undefined} />
                  {/* 类型色点 */}
                  <circle cx={p.x} cy={p.y} r={7} fill={tColor} opacity={0.8} />
                  {/* 健康评分文字 */}
                  <text x={p.x} y={p.y + 4} fontSize={10} textAnchor="middle" fill={hColor} fontWeight="bold">
                    {e.health_score ?? '?'}
                  </text>
                  {/* 名称 */}
                  <text x={p.x} y={p.y + radius + 16} fontSize={11} textAnchor="middle" fill="#262626" fontWeight="bold">
                    {e.name.length > 16 ? e.name.slice(0, 14) + '…' : e.name}
                  </text>
                  {/* 类型 + 风险度 */}
                  <text x={p.x} y={p.y + radius + 30} fontSize={9} textAnchor="middle" fill="#8c8c8c">
                    {e.type_name}
                    {e.risk_score ? ` · 风险${e.risk_score}` : ''}
                  </text>
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

      {/* 详情抽屉 */}
      <Drawer title={selected?.name || '详情'} open={drawerOpen} onClose={() => setDrawerOpen(false)} width={420}>
        {selected && (
          <>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="GUID"><code>{selected.guid}</code></Descriptions.Item>
              <Descriptions.Item label="类型"><Tag color={typeColors[selected.type_name]}>{selected.type_name}</Tag></Descriptions.Item>
              <Descriptions.Item label="健康度">
                <Space>
                  <Progress percent={selected.health_score || 0} size="small"
                    strokeColor={healthColors[selected.health_level]} style={{ width: 100 }} />
                  <Tag color={healthColors[selected.health_level]}>{selected.health_level}</Tag>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="风险度">
                <span style={{ color: (selected.risk_score || 0) >= 50 ? '#ff4d4f' : '#52c41a', fontWeight: 'bold', fontSize: 18 }}>
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

            {/* 健康度详情维度 */}
            {selected.health_detail && typeof selected.health_detail === 'object' && (
              <>
                <Divider orientation="left" plain>健康度维度</Divider>
                {Object.entries(selected.health_detail).filter(([k]) => !['method', 'reason', 'children_count', 'children_avg', 'min_score', 'max_score'].includes(k)).map(([dim, info]: [string, any]) => (
                  <Row key={dim} style={{ marginBottom: 8 }}>
                    <Col span={8}><strong>{dim}</strong></Col>
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

            <Divider orientation="left" plain>属性</Divider>
            <Space wrap>
              {Object.entries(selected.attributes || {}).map(([k, v]) => <Tag key={k}>{k}: {String(v)}</Tag>)}
            </Space>
          </>
        )}
      </Drawer>
    </div>
  );
};

export default TopologyPage;
