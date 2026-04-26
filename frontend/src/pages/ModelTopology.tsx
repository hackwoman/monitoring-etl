import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, Spin, Tag, Tooltip, Space, Typography, Empty, Badge } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
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
} from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1/cmdb';

const { Text } = Typography;

/* ─── Types ─── */
interface EntityType {
  type_name: string;
  display_name: string;
  layer: string;
  category?: string;
  icon?: string;
  description?: string;
  integrated?: boolean; // whether the platform has integrated this type
}

interface Relation {
  source_type: string;
  target_type: string;
  relation_type: string;
}

/* ─── Layer definitions ─── */
const LAYERS = [
  { key: 'L1_business', label: 'L1 业务层', color: '#722ed1', bg: '#f9f0ff' },
  { key: 'L2_application', label: 'L2 应用层', color: '#1677ff', bg: '#e6f4ff' },
  { key: 'L3_service', label: 'L3 服务层', color: '#13c2c2', bg: '#e6fffb' },
  { key: 'L4_infrastructure', label: 'L4 基础设施层', color: '#595959', bg: '#f5f5f5' },
];

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
const ModelTopology: React.FC = () => {
  const navigate = useNavigate();
  const [types, setTypes] = useState<EntityType[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredType, setHoveredType] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  /* Fetch entity types */
  const fetchTypes = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/types`);
      const items: EntityType[] = res.data.items || res.data || [];
      setTypes(items);
    } catch (err) {
      console.error('Failed to fetch types:', err);
    }
  }, []);

  /* Fetch relations for all types */
  const fetchRelations = useCallback(async () => {
    try {
      const allRelations: Relation[] = [];
      // Fetch relations for each type
      const typeNames = types.map((t) => t.type_name);
      await Promise.all(
        typeNames.map(async (typeName) => {
          try {
            const res = await axios.get(`${API_BASE}/types/${typeName}/relations`);
            const items = res.data.relations || res.data.items || (Array.isArray(res.data) ? res.data : []);
            items.forEach((r: any) => {
              // Avoid duplicates
              const exists = allRelations.some(
                (er) =>
                  er.source_type === r.source_type &&
                  er.target_type === r.target_type &&
                  er.relation_type === r.relation_type
              );
              if (!exists) {
                allRelations.push({
                  source_type: r.source_type,
                  target_type: r.target_type,
                  relation_type: r.relation_type,
                });
              }
            });
          } catch {
            // Some types may not have relations endpoint
          }
        })
      );
      setRelations(allRelations);
    } catch (err) {
      console.error('Failed to fetch relations:', err);
    }
  }, [types]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchTypes();
      setLoading(false);
    };
    load();
  }, [fetchTypes]);

  useEffect(() => {
    if (types.length > 0) {
      fetchRelations();
    }
  }, [types, fetchRelations]);

  /* Group types by layer */
  const typesByLayer = LAYERS.map((layer) => ({
    ...layer,
    types: types.filter((t) => t.layer === layer.key),
  }));

  /* Get unique categories */
  const categories = [...new Set(types.map((t) => t.category).filter(Boolean))];

  /* Navigate to detail */
  const handleTypeClick = (typeName: string) => {
    navigate(`/model-topology/${typeName}`);
  };

  /* Check if a relation involves hovered type */
  const isRelatedToHovered = (rel: Relation) => {
    if (!hoveredType) return false;
    return rel.source_type === hoveredType || rel.target_type === hoveredType;
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="加载模型拓扑..." />
      </div>
    );
  }

  return (
    <div style={{ padding: 0 }}>
      {/* Header */}
      <Card
        style={{ marginBottom: 16 }}
        bodyStyle={{ padding: '16px 24px' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <BranchesOutlined style={{ fontSize: 20, color: '#1677ff' }} />
            <Text strong style={{ fontSize: 18 }}>
              模型拓扑图
            </Text>
            <Text style={{ color: "#475569" }}>
              展示实体类型间的层级关系与接入状态
            </Text>
          </Space>
          <Space>
            <Badge status="success" text="已接入" />
            <Badge status="default" text="未接入" />
          </Space>
        </div>
      </Card>

      {/* Legend */}
      <Card style={{ marginBottom: 16 }} bodyStyle={{ padding: '12px 24px' }}>
        <Space size="large" wrap>
          <Text style={{ color: "#475569" }}>图例：</Text>
          {LAYERS.map((layer) => (
            <Space key={layer.key} size={4}>
              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  backgroundColor: layer.color,
                }}
              />
              <Text>{layer.label}</Text>
            </Space>
          ))}
          <Space size={4}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: '#52c41a',
                border: '2px solid #52c41a',
              }}
            />
            <Text>已接入</Text>
          </Space>
          <Space size={4}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: '#d9d9d9',
                border: '2px solid #d9d9d9',
              }}
            />
            <Text>未接入</Text>
          </Space>
        </Space>
      </Card>

      {/* Topology */}
      <Card bodyStyle={{ padding: 0, overflow: 'auto' }}>
        <div
          ref={containerRef}
          style={{
            position: 'relative',
            minHeight: 600,
            padding: '24px',
          }}
        >
          {/* SVG for relation lines */}
          <svg
            ref={svgRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: 'none',
              zIndex: 1,
            }}
          >
            {relations.map((rel, idx) => {
              const sourceEl = document.getElementById(`type-node-${rel.source_type}`);
              const targetEl = document.getElementById(`type-node-${rel.target_type}`);
              if (!sourceEl || !targetEl) return null;

              const containerRect = containerRef.current?.getBoundingClientRect();
              if (!containerRect) return null;

              const sourceRect = sourceEl.getBoundingClientRect();
              const targetRect = targetEl.getBoundingClientRect();

              const x1 = sourceRect.left + sourceRect.width / 2 - containerRect.left;
              const y1 = sourceRect.top + sourceRect.height / 2 - containerRect.top;
              const x2 = targetRect.left + targetRect.width / 2 - containerRect.left;
              const y2 = targetRect.top + targetRect.height / 2 - containerRect.top;

              const isHighlighted = isRelatedToHovered(rel);
              const isDimmed = hoveredType && !isHighlighted;

              return (
                <g key={idx}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={isHighlighted ? '#1677ff' : '#d9d9d9'}
                    strokeWidth={isHighlighted ? 2.5 : 1.5}
                    strokeDasharray={isHighlighted ? 'none' : '6,3'}
                    opacity={isDimmed ? 0.15 : 0.6}
                    style={{ transition: 'all 0.3s' }}
                  />
                  {isHighlighted && (
                    <text
                      x={(x1 + x2) / 2}
                      y={(y1 + y2) / 2 - 6}
                      textAnchor="middle"
                      fill="#1677ff"
                      fontSize={11}
                      fontWeight={500}
                    >
                      {rel.relation_type}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Layer rows */}
          {typesByLayer.map((layer) => (
            <div
              key={layer.key}
              style={{
                marginBottom: 24,
                position: 'relative',
                zIndex: 2,
              }}
            >
              {/* Layer label */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 12,
                }}
              >
                <div
                  style={{
                    width: 4,
                    height: 20,
                    backgroundColor: layer.color,
                    borderRadius: 2,
                    marginRight: 8,
                  }}
                />
                <Text strong style={{ color: "#1e293b", fontSize: 14 }}>
                  {layer.label}
                </Text>
                <Text style={{ color: "#475569", marginLeft: 8, fontSize: 12  }}>
                  ({layer.types.length} 个类型)
                </Text>
              </div>

              {/* Type nodes */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 12,
                  padding: '16px',
                  backgroundColor: layer.bg,
                  borderRadius: 8,
                  border: `1px solid ${layer.color}20`,
                  minHeight: 80,
                }}
              >
                {layer.types.length === 0 ? (
                  <Text style={{ color: "#475569", padding: '8px 0'  }}>
                    暂无实体类型
                  </Text>
                ) : (
                  layer.types.map((type) => {
                    const isHovered = hoveredType === type.type_name;
                    const isRelated = hoveredType
                      ? relations.some(
                          (r) =>
                            (r.source_type === hoveredType && r.target_type === type.type_name) ||
                            (r.target_type === hoveredType && r.source_type === type.type_name)
                        )
                      : false;
                    const isDimmed = hoveredType && !isHovered && !isRelated;

                    return (
                      <Tooltip
                        key={type.type_name}
                        title={
                          <div>
                            <div><strong>{type.display_name}</strong></div>
                            <div>{type.description || '暂无描述'}</div>
                            {type.category && (
                              <div>分类: {categoryLabels[type.category] || type.category}</div>
                            )}
                            <div style={{ marginTop: 4, fontSize: 12, color: '#aaa' }}>
                              点击查看详情 →
                            </div>
                          </div>
                        }
                      >
                        <div
                          id={`type-node-${type.type_name}`}
                          onClick={() => handleTypeClick(type.type_name)}
                          onMouseEnter={() => setHoveredType(type.type_name)}
                          onMouseLeave={() => setHoveredType(null)}
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            padding: '12px 16px',
                            backgroundColor: '#ffffff',
                            borderRadius: 8,
                            border: `2px solid ${isHovered ? layer.color : '#e8e8e8'}`,
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            minWidth: 100,
                            opacity: isDimmed ? 0.3 : 1,
                            transform: isHovered ? 'scale(1.05)' : 'scale(1)',
                            boxShadow: isHovered
                              ? `0 4px 12px ${layer.color}30`
                              : '0 1px 4px rgba(0,0,0,0.08)',
                          }}
                        >
                          {/* Integration status dot */}
                          <div
                            style={{
                              position: 'absolute',
                              top: -4,
                              right: -4,
                              width: 10,
                              height: 10,
                              borderRadius: '50%',
                              backgroundColor: type.integrated !== false ? '#52c41a' : '#d9d9d9',
                              border: '2px solid #fff',
                            }}
                          />
                          {/* Icon */}
                          <div
                            style={{
                              fontSize: 24,
                              color: layer.color,
                              marginBottom: 6,
                            }}
                          >
                            {getIcon(type.icon)}
                          </div>
                          {/* Display name */}
                          <Text
                            strong
                            style={{
                              fontSize: 13,
                              textAlign: 'center',
                              lineHeight: 1.3,
                            }}
                          >
                            {type.display_name}
                          </Text>
                          {/* Type name */}
                          <Text
                            style={{ color: "#475569",
                              fontSize: 11,
                              marginTop: 2,
                             }}
                          >
                            {type.type_name}
                          </Text>
                          {/* Category tag */}
                          {type.category && (
                            <Tag
                              style={{
                                marginTop: 4,
                                fontSize: 10,
                                lineHeight: '16px',
                                padding: '0 4px',
                              }}
                            >
                              {categoryLabels[type.category] || type.category}
                            </Tag>
                          )}
                        </div>
                      </Tooltip>
                    );
                  })
                )}
              </div>
            </div>
          ))}

          {/* Empty state */}
          {types.length === 0 && !loading && (
            <Empty
              description="暂无实体类型数据"
              style={{ marginTop: 60 }}
            />
          )}
        </div>
      </Card>

      {/* Relations summary */}
      {relations.length > 0 && (
        <Card
          title={
            <Space>
              <NodeIndexOutlined />
              <Text>关系总览</Text>
            </Space>
          }
          style={{ marginTop: 16 }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {relations.map((rel, idx) => (
              <Tag
                key={idx}
                color="blue"
                style={{ cursor: 'pointer' }}
                onClick={() => handleTypeClick(rel.source_type)}
              >
                {rel.source_type} → {rel.target_type}
                <Text style={{ color: "#475569", marginLeft: 4, fontSize: 11  }}>
                  ({rel.relation_type})
                </Text>
              </Tag>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

export default ModelTopology;
