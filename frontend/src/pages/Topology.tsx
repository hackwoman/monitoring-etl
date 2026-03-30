import React, { useState, useEffect, useCallback } from 'react';
import { Card, Select, Tag, Drawer, Descriptions, Spin, Empty, Space, Row, Col } from 'antd';
import { CheckCircleOutlined, WarningOutlined, CloseCircleOutlined } from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

const healthColors: Record<string, string> = {
  healthy: '#52c41a',
  warning: '#faad14',
  critical: '#ff4d4f',
  down: '#a8071a',
};

const typeColors: Record<string, string> = {
  Business: '#722ed1',
  Service: '#1890ff',
  Host: '#13c2c2',
  MySQL: '#fa8c16',
  Redis: '#eb2f96',
  NetworkDevice: '#2f54eb',
  Database: '#fa8c16',
};

// ---- 简易 SVG 拓扑图 ----

interface Entity {
  guid: string;
  name: string;
  type_name: string;
  health_score: number;
  health_level: string;
  risk_score: number;
  biz_service: string;
  attributes: Record<string, any>;
}

interface Relation {
  guid: string;
  type_name: string;
  from_guid: string;
  to_guid: string;
}

interface NodePos {
  x: number;
  y: number;
}

const TopologyPage: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>();
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetchData = async (typeName?: string) => {
    setLoading(true);
    try {
      const params: any = { limit: 500 };
      if (typeName) params.type_name = typeName;

      const [entRes, relPromises] = await Promise.all([
        axios.get(`${API_BASE}/entities`, { params }),
      ]);

      const entList: Entity[] = entRes.data.items || [];
      setEntities(entList);

      // 批量获取关系
      const relResults = await Promise.all(
        entList.slice(0, 100).map((e) =>
          axios.get(`${API_BASE}/entities/${e.guid}/relations`).catch(() => ({ data: { items: [] } }))
        )
      );

      const allRels: Relation[] = [];
      const seen = new Set<string>();
      for (const res of relResults) {
        for (const r of (res.data.items || [])) {
          const key = [r.from_guid, r.to_guid].sort().join('-');
          if (!seen.has(key)) {
            seen.add(key);
            allRels.push(r);
          }
        }
      }
      setRelations(allRels);
    } catch (err) {
      console.error('Fetch topology failed:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handleFilterChange = (v?: string) => {
    setTypeFilter(v);
    fetchData(v);
  };

  // ---- 布局算法：按类型分层排列 ----
  const layoutNodes = useCallback(() => {
    const typeOrder = ['Business', 'Service', 'MySQL', 'Redis', 'Database', 'Host', 'NetworkDevice'];
    const grouped: Record<string, Entity[]> = {};
    for (const e of entities) {
      const cat = e.type_name;
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(e);
    }

    const nodePositions: Record<string, NodePos> = {};
    const svgWidth = 900;
    const rowHeight = 120;
    const startY = 60;

    let row = 0;
    for (const type of typeOrder) {
      const items = grouped[type] || [];
      if (items.length === 0) continue;

      const spacing = Math.min(160, svgWidth / (items.length + 1));
      const startX = (svgWidth - spacing * (items.length - 1)) / 2;

      items.forEach((e, i) => {
        nodePositions[e.guid] = {
          x: startX + i * spacing,
          y: startY + row * rowHeight,
        };
      });
      row++;
    }

    // 未分类的放最后
    for (const [type, items] of Object.entries(grouped)) {
      if (typeOrder.includes(type)) continue;
      const spacing = Math.min(160, svgWidth / (items.length + 1));
      const startX = (svgWidth - spacing * (items.length - 1)) / 2;
      items.forEach((e, i) => {
        nodePositions[e.guid] = {
          x: startX + i * spacing,
          y: startY + row * rowHeight,
        };
      });
      row++;
    }

    return nodePositions;
  }, [entities]);

  const nodePositions = layoutNodes();
  const svgHeight = Math.max(500, Object.keys(nodePositions).length > 0
    ? Math.max(...Object.values(nodePositions).map(p => p.y)) + 100
    : 500);

  const entityMap: Record<string, Entity> = {};
  for (const e of entities) entityMap[e.guid] = e;

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>🗺️ 资源拓扑</h2>

      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="按类型筛选"
          allowClear
          style={{ width: 180 }}
          value={typeFilter}
          onChange={handleFilterChange}
          options={[
            { label: 'Business', value: 'Business' },
            { label: 'Service', value: 'Service' },
            { label: 'Host', value: 'Host' },
            { label: 'MySQL', value: 'MySQL' },
            { label: 'Redis', value: 'Redis' },
            { label: 'NetworkDevice', value: 'NetworkDevice' },
          ]}
        />
        <span style={{ color: '#8c8c8c' }}>
          共 {entities.length} 个实体, {relations.length} 条关系
        </span>
      </Space>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : entities.length === 0 ? (
        <Empty description="暂无实体数据" />
      ) : (
        <Card size="small" style={{ overflow: 'auto' }}>
          <svg width="100%" height={svgHeight} viewBox={`0 0 900 ${svgHeight}`} style={{ minWidth: 600 }}>
            {/* 关系连线 */}
            {relations.map((rel) => {
              const from = nodePositions[rel.from_guid];
              const to = nodePositions[rel.to_guid];
              if (!from || !to) return null;
              return (
                <g key={rel.guid}>
                  <line
                    x1={from.x} y1={from.y + 20}
                    x2={to.x} y2={to.y - 20}
                    stroke="#d9d9d9"
                    strokeWidth={1.5}
                    markerEnd="url(#arrow)"
                  />
                  <text
                    x={(from.x + to.x) / 2}
                    y={(from.y + to.y) / 2}
                    fontSize={10}
                    fill="#8c8c8c"
                    textAnchor="middle"
                  >
                    {rel.type_name}
                  </text>
                </g>
              );
            })}

            {/* 箭头定义 */}
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#d9d9d9" />
              </marker>
            </defs>

            {/* 实体节点 */}
            {entities.map((e) => {
              const pos = nodePositions[e.guid];
              if (!pos) return null;
              const color = healthColors[e.health_level] || '#d9d9d9';
              const typeColor = typeColors[e.type_name] || '#8c8c8c';
              return (
                <g
                  key={e.guid}
                  style={{ cursor: 'pointer' }}
                  onClick={() => { setSelectedEntity(e); setDrawerOpen(true); }}
                >
                  {/* 健康度光晕 */}
                  <circle cx={pos.x} cy={pos.y} r={22} fill={color} opacity={0.15} />
                  {/* 节点圆形 */}
                  <circle
                    cx={pos.x} cy={pos.y} r={18}
                    fill="white"
                    stroke={color}
                    strokeWidth={3}
                  />
                  {/* 类型标识 */}
                  <circle cx={pos.x} cy={pos.y} r={6} fill={typeColor} />
                  {/* 名称 */}
                  <text x={pos.x} y={pos.y + 32} fontSize={11} textAnchor="middle" fill="#262626" fontWeight="bold">
                    {e.name.length > 14 ? e.name.slice(0, 12) + '…' : e.name}
                  </text>
                  {/* 类型标签 */}
                  <text x={pos.x} y={pos.y + 46} fontSize={9} textAnchor="middle" fill="#8c8c8c">
                    {e.type_name}
                  </text>
                </g>
              );
            })}
          </svg>
        </Card>
      )}

      {/* 图例 */}
      <Card title="图例" size="small" style={{ marginTop: 16 }}>
        <Row gutter={[16, 8]}>
          <Col>
            <span style={{ fontWeight: 'bold', marginRight: 8 }}>健康度：</span>
            {Object.entries(healthColors).map(([level, color]) => (
              <Tag key={level} color={color}>{level}</Tag>
            ))}
          </Col>
          <Col>
            <span style={{ fontWeight: 'bold', marginRight: 8 }}>类型：</span>
            {Object.entries(typeColors).map(([type, color]) => (
              <Tag key={type} color={color}>{type}</Tag>
            ))}
          </Col>
        </Row>
      </Card>

      {/* 实体详情抽屉 */}
      <Drawer
        title={selectedEntity?.name || '实体详情'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={400}
      >
        {selectedEntity && (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="GUID">{selectedEntity.guid}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={typeColors[selectedEntity.type_name]}>{selectedEntity.type_name}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="健康度">
              <span style={{ color: healthColors[selectedEntity.health_level], fontWeight: 'bold', fontSize: 18 }}>
                {selectedEntity.health_score ?? '-'} / 100
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedEntity.health_level === 'healthy' ? 'green' : selectedEntity.health_level === 'warning' ? 'orange' : 'red'}>
                {selectedEntity.health_level}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="风险度">{selectedEntity.risk_score ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="业务">{selectedEntity.biz_service || '-'}</Descriptions.Item>
            <Descriptions.Item label="属性">
              {Object.entries(selectedEntity.attributes || {}).map(([k, v]) => (
                <Tag key={k}>{k}: {String(v)}</Tag>
              ))}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
};

export default TopologyPage;
