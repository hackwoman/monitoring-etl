import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Card, Tag, Drawer, Descriptions, Spin, Empty, Space, Row, Col, Divider,
  Progress, Tabs, Table, Timeline, Badge, Button, Tooltip, Select, message,
  Input, Slider, Dropdown,
} from 'antd';
import {
  ApartmentOutlined, ApiOutlined, DatabaseOutlined, DesktopOutlined,
  CloudServerOutlined, GlobalOutlined, BranchesOutlined, AlertOutlined,
  ClockCircleOutlined, FileTextOutlined, ThunderboltOutlined,
  ArrowRightOutlined, FieldTimeOutlined, SearchOutlined, FilterOutlined,
  CloseOutlined, NodeExpandOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import { TimeRangeBar } from '../components/TimeRangeContext';

const API = '/api/v1/cmdb';

// ============================================================
// 共享类型
// ============================================================
interface Entity {
  guid: string; name: string; type_name: string;
  health_score: number; health_level: string; risk_score: number;
  biz_service: string; attributes: Record<string, any>;
}
interface Relation {
  guid: string; type_name: string;
  from_guid: string; to_guid: string;
  dimension: string; source: string; confidence: number;
  attributes: Record<string, any>;
}
interface TraceRelation {
  caller: string; callee: string;
  call_count: number; avg_latency_ms: number;
  p99_latency_ms: number; error_rate: number;
}

// ============================================================
// 业务拓扑类型
// ============================================================
interface LogicalNode {
  guid: string; name: string; type_name: string;
  display_name: string; category: string;
  health_score: number | null; health_level: string | null;
  biz_service: string | null;
  attributes: Record<string, any>;
  alert_count: number;
  key_metrics: Record<string, any>;
}
interface LogicalEdge {
  from_guid: string; to_guid: string;
  relation_type: string;
  call_type: 'sync' | 'async';
  confidence: number;
  call_count?: number | null;
  avg_latency_ms?: number | null;
  error_rate?: number | null;
}
interface DrilldownNode {
  guid: string; name: string; type_name: string;
  display_name: string; category: string;
  health_score: number | null; health_level: string | null;
  risk_score: number | null;
  attributes: Record<string, any>;
  key_metrics: Record<string, any>;
  alert_count: number;
  relation_type: string | null;
  children: DrilldownNode[];
}

// ============================================================
// 样式常量
// ============================================================
const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};
const healthBg: Record<string, string> = {
  healthy: '#f6ffed', warning: '#fffbe6', critical: '#fff2f0', down: '#fff1f0',
};
const typeIcons: Record<string, React.ReactNode> = {
  Business: <ApartmentOutlined />, Application: <ApiOutlined />,
  Service: <ApiOutlined />, Middleware: <CloudServerOutlined />,
  Data: <DatabaseOutlined />, Infrastructure: <DesktopOutlined />,
  Host: <DesktopOutlined />, MySQL: <DatabaseOutlined />,
  Redis: <DatabaseOutlined />, Database: <DatabaseOutlined />,
  NetworkDevice: <CloudServerOutlined />, Page: <FileTextOutlined />,
  HttpRequest: <FieldTimeOutlined />, Endpoint: <ThunderboltOutlined />,
};
const layerColors: Record<string, string> = {
  business: '#e8f4ff', application: '#f0f5ff', service: '#fff7e6',
  middleware: '#fff0f0', data: '#f6ffed', infrastructure: '#f5f5f5',
  frontend: '#e8f4ff', runtime: '#fff7e6', custom: '#fafafa',
};

// 错误率 → 颜色（绿→黄→红）
function errorRateColor(rate: number | null | undefined): string {
  if (rate == null) return '#d9d9d9';
  if (rate <= 0.001) return '#52c41a';
  if (rate <= 0.01) return '#faad14';
  if (rate <= 0.05) return '#fa8c16';
  return '#ff4d4f';
}

// call_count → strokeWidth（1~8px，log 缩放）
function callCountWidth(count: number | null | undefined): number {
  if (count == null || count <= 0) return 1;
  return Math.max(1, Math.min(8, Math.log10(count + 1) * 2.5));
}

const NODE_R = 28;

// ============================================================
// 布局
// ============================================================
interface LayoutNode extends LogicalNode {
  x: number; y: number;
}

function layoutLogicalGraph(nodes: LogicalNode[], edges: LogicalEdge[]) {
  if (nodes.length === 0) return { positions: {} as Record<string, { x: number; y: number }>, layers: [] as string[] };

  const layerOrder = ['business', 'application', 'service', 'middleware', 'data', 'infrastructure', 'frontend', 'runtime', 'custom'];
  const layers: LogicalNode[][] = [];

  for (const n of nodes) {
    const idx = layerOrder.indexOf(n.category);
    (layers[idx >= 0 ? idx : layerOrder.length - 1] ||= []).push(n);
  }

  const nodeGapX = 160, layerGapX = 100, layerGapY = 130, startX = 80, startY = 60;
  const positions: Record<string, { x: number; y: number }> = {};

  for (let li = 0; li < layers.length; li++) {
    const layerNodes = layers[li] || [];
    layerNodes.forEach((n, ni) => {
      positions[n.guid] = {
        x: startX + li * (nodeGapX + layerGapX),
        y: startY + ni * layerGapY,
      };
    });
  }

  return { positions, layers };
}

// ============================================================
// 健康环组件
// ============================================================
function HealthRing({ health_score, health_level, size = NODE_R * 2 }: {
  health_score: number | null; health_level: string | null; size?: number;
}) {
  const r = size / 2;
  const ratio = (health_score ?? 100) / 100;
  const color = healthColors[health_level || 'healthy'] || '#d9d9d9';
  const errorAngle = (1 - ratio) * 360;
  const startAngle = 90, toRad = (d: number) => (d * Math.PI) / 180;

  let arc = '';
  if (errorAngle > 0) {
    const x1 = r + r * Math.cos(toRad(startAngle));
    const y1 = r - r * Math.sin(toRad(startAngle));
    const x2 = r + r * Math.cos(toRad(startAngle - errorAngle));
    const y2 = r - r * Math.sin(toRad(startAngle - errorAngle));
    arc = `M ${x1} ${y1} A ${r} ${r} 0 ${errorAngle > 180 ? 1 : 0} 1 ${x2} ${y2} Z`;
  }

  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <circle cx={r} cy={r} r={r - 2} fill="white" stroke="#f0f0f0" strokeWidth={3} />
      {arc && <path d={arc} fill={color} opacity={0.85} />}
      <text x={r} y={r + 1} textAnchor="middle" dominantBaseline="middle"
        fontSize={10} fontWeight={700} fill={color}>{health_score ?? '?'}</text>
    </svg>
  );
}

// ============================================================
// 悬停边指标卡
// ============================================================
function EdgeTooltipCard({ edge }: { edge: LogicalEdge }) {
  return (
    <div style={{
      background: 'white', border: '1px solid #e8e8e8', borderRadius: 8,
      padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
      minWidth: 160, fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 8, color: '#262626' }}>
        {edge.relation_type}
        <Tag style={{ marginLeft: 6, fontSize: 10 }}>{edge.call_type}</Tag>
      </div>
      <Row gutter={[4, 4]}>
        {edge.call_count != null && (
          <Col span={12}>
            <div style={{ color: '#8c8c8c', fontSize: 10 }}>QPS</div>
            <div style={{ fontWeight: 600, color: '#1890ff' }}>{edge.call_count.toLocaleString()}</div>
          </Col>
        )}
        {edge.avg_latency_ms != null && (
          <Col span={12}>
            <div style={{ color: '#8c8c8c', fontSize: 10 }}>延迟</div>
            <div style={{ fontWeight: 600, color: '#52c41a' }}>{edge.avg_latency_ms.toFixed(1)}ms</div>
          </Col>
        )}
        {edge.error_rate != null && (
          <Col span={12}>
            <div style={{ color: '#8c8c8c', fontSize: 10 }}>错误率</div>
            <div style={{ fontWeight: 600, color: errorRateColor(edge.error_rate) }}>
              {(edge.error_rate * 100).toFixed(2)}%
            </div>
          </Col>
        )}
        {edge.confidence != null && (
          <Col span={12}>
            <div style={{ color: '#8c8c8c', fontSize: 10 }}>置信度</div>
            <div style={{ fontWeight: 600 }}>{(edge.confidence * 100).toFixed(0)}%</div>
          </Col>
        )}
      </Row>
    </div>
  );
}

// ============================================================
// 主拓扑图组件
// ============================================================
interface LogicalGraphProps {
  nodes: LogicalNode[];
  edges: LogicalEdge[];
  positions: Record<string, { x: number; y: number }>;
  onNodeClick: (node: LogicalNode) => void;
  selectedGuid: string | null;
  searchText: string;
  highlightedGuids: Set<string>;
  fadedGuids: Set<string>;
}

function LogicalGraph({
  nodes, edges, positions, onNodeClick, selectedGuid,
  searchText, highlightedGuids, fadedGuids,
}: LogicalGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredEdge, setHoveredEdge] = useState<LogicalEdge | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const bounds = useMemo(() => {
    const xs = Object.values(positions).map(p => p.x);
    const ys = Object.values(positions).map(p => p.y);
    return {
      minX: Math.min(...xs, 0) - 80,
      maxX: Math.max(...xs, 0) + 220,
      minY: Math.min(...ys, 0) - 60,
      maxY: Math.max(...ys, 0) + 120,
    };
  }, [positions]);

  const isSearchActive = searchText.length > 0;

  return (
    <div style={{ position: 'relative', overflowX: 'auto', overflowY: 'auto', background: '#fafbfc', borderRadius: 8 }}>
      {/* 悬停边指标卡（绝对定位） */}
      {hoveredEdge && (
        <div style={{
          position: 'absolute', zIndex: 100,
          left: tooltipPos.x + 12, top: tooltipPos.y - 10,
          pointerEvents: 'none',
        }}>
          <EdgeTooltipCard edge={hoveredEdge} />
        </div>
      )}

      <svg
        ref={svgRef}
        width={Math.max(bounds.maxX - bounds.minX, 800)}
        height={Math.max(bounds.maxY - bounds.minY, 400)}
        style={{ display: 'block', minWidth: 800 }}
      >
        <defs>
          <marker id="arrow-sync" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#1890ff" />
          </marker>
          <marker id="arrow-async" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#722ed1" />
          </marker>
        </defs>

        {/* ── 边 ── */}
        {edges.map((edge, i) => {
          const from = positions[edge.from_guid];
          const to = positions[edge.to_guid];
          if (!from || !to) return null;

          const isFaded = fadedGuids.has(edge.from_guid) || fadedGuids.has(edge.to_guid);
          const isHighlighted = highlightedGuids.has(edge.from_guid) && highlightedGuids.has(edge.to_guid);

          // 流量可视化：strokeWidth = call_count，颜色 = error_rate
          const sw = callCountWidth(edge.call_count);
          const edgeColor = isFaded ? '#e0e0e0' : errorRateColor(edge.error_rate);
          const lineDash = edge.call_type === 'async' ? '8,4' : 'none';
          const alpha = isFaded ? 0.2 : 1;

          const mx = (from.x + to.x) / 2;
          const my = (from.y + to.y) / 2;

          return (
            <g key={i} opacity={alpha}
              onMouseEnter={(e) => {
                setHoveredEdge(edge);
                setTooltipPos({ x: e.clientX, y: e.clientY });
              }}
              onMouseLeave={() => setHoveredEdge(null)}
              style={{ cursor: 'pointer' }}
            >
              <line
                x1={from.x + NODE_R} y1={from.y}
                x2={to.x - NODE_R - 10} y2={to.y}
                stroke={edgeColor} strokeWidth={sw}
                strokeDasharray={lineDash}
                markerEnd={`url(#arrow-${edge.call_type})`}
              />
              {/* QPS 标签（只在大流量边上显示） */}
              {edge.call_count != null && edge.call_count > 100 && !isFaded && (
                <>
                  <rect x={mx - 18} y={my - 9} width={36} height={14} rx={3}
                    fill="white" stroke="#e8e8e8" strokeWidth={1} />
                  <text x={mx} y={my + 3} textAnchor="middle" fontSize={9}
                    fill="#595959" fontWeight={600}>
                    {edge.call_count >= 1000 ? `${(edge.call_count / 1000).toFixed(1)}k` : edge.call_count}
                  </text>
                </>
              )}
            </g>
          );
        })}

        {/* ── 节点 ── */}
        {nodes.map(node => {
          const pos = positions[node.guid];
          if (!pos) return null;
          const isSelected = node.guid === selectedGuid;
          const isFaded = isSearchActive && fadedGuids.has(node.guid);
          const isHighlighted = isSearchActive && highlightedGuids.has(node.guid);

          return (
            <g
              key={node.guid}
              transform={`translate(${pos.x}, ${pos.y})`}
              style={{ cursor: 'pointer', opacity: isFaded ? 0.15 : 1 }}
              onClick={() => onNodeClick(node)}
            >
              {/* 搜索高亮 */}
              {isHighlighted && (
                <circle cx={0} cy={0} r={NODE_R + 8} fill="none"
                  stroke="#1890ff" strokeWidth={2.5} strokeDasharray="5,2" />
              )}
              {/* 选中 */}
              {isSelected && (
                <circle cx={0} cy={0} r={NODE_R + 5} fill="none"
                  stroke="#1890ff" strokeWidth={2} />
              )}
              <HealthRing health_score={node.health_score} health_level={node.health_level} />
              <foreignObject x={-NODE_R} y={-NODE_R} width={NODE_R * 2} height={NODE_R * 2}
                style={{ pointerEvents: 'none' }}>
                <div style={{
                  width: '100%', height: '100%', display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                  fontSize: 16, color: '#595959',
                }}>
                  {typeIcons[node.type_name] || <ApiOutlined />}
                </div>
              </foreignObject>
              {node.alert_count > 0 && (
                <>
                  <circle cx={NODE_R - 4} cy={-NODE_R + 4} r={7} fill="#ff4d4f" />
                  <text x={NODE_R - 4} y={-NODE_R + 7} textAnchor="middle" fontSize={8}
                    fill="white" fontWeight={700}>{node.alert_count}</text>
                </>
              )}
              <text x={0} y={NODE_R + 14} textAnchor="middle" fontSize={11} fontWeight={600}
                fill={isSearchActive && !isHighlighted ? '#bfbfbf' : '#262626'}>
                {node.display_name}
              </text>
              <text x={0} y={NODE_R + 26} textAnchor="middle" fontSize={9} fill="#8c8c8c">
                {node.type_name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ============================================================
// 横向指标面板
// ============================================================
function HorizontalMetricsPanel({ node }: { node: LogicalNode }) {
  const metrics = node.key_metrics || {};
  const latency = metrics.avg_latency_ms ?? metrics.latency;
  const errorRate = metrics.error_rate ?? metrics.errors;

  return (
    <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
      <Row gutter={[8, 8]}>
        {latency != null && (
          <Col span={8}>
            <div style={{ textAlign: 'center', padding: '8px 4px', background: '#f6ffed', borderRadius: 6 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#52c41a' }}>
                {typeof latency === 'number' ? latency.toFixed(1) : latency}
                <span style={{ fontSize: 10, fontWeight: 400, marginLeft: 2 }}>ms</span>
              </div>
              <div style={{ fontSize: 10, color: '#8c8c8c' }}>平均延迟</div>
            </div>
          </Col>
        )}
        {errorRate != null && (
          <Col span={8}>
            <div style={{ textAlign: 'center', padding: '8px 4px', background: Number(errorRate) > 0.01 ? '#fff2f0' : '#f6ffed', borderRadius: 6 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: Number(errorRate) > 0.01 ? '#ff4d4f' : '#52c41a' }}>
                {(Number(errorRate) * 100).toFixed(2)}
                <span style={{ fontSize: 10, fontWeight: 400, marginLeft: 2 }}>%</span>
              </div>
              <div style={{ fontSize: 10, color: '#8c8c8c' }}>错误率</div>
            </div>
          </Col>
        )}
        {node.health_score != null && (
          <Col span={8}>
            <div style={{ textAlign: 'center', padding: '8px 4px', background: healthBg[node.health_level || 'healthy'] || '#f6ffed', borderRadius: 6 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: healthColors[node.health_level || 'healthy'] }}>
                {node.health_score}
              </div>
              <div style={{ fontSize: 10, color: '#8c8c8c' }}>健康度</div>
            </div>
          </Col>
        )}
      </Row>
      {node.attributes && Object.keys(node.attributes).length > 0 && (
        <Descriptions size="small" column={2} style={{ marginTop: 8 }}>
          {Object.entries(node.attributes).slice(0, 6).map(([k, v]) => (
            <Descriptions.Item key={k} label={<span style={{ fontSize: 10 }}>{k}</span>}>
              <span style={{ fontSize: 11 }}>{String(v)}</span>
            </Descriptions.Item>
          ))}
        </Descriptions>
      )}
    </div>
  );
}

// ============================================================
// 纵向钻取树
// ============================================================
function DrilldownTree({ rootGuid }: { rootGuid: string }) {
  const [tree, setTree] = useState<DrilldownNode | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDrilldown = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/topology/drilldown/${rootGuid}`, { params: { max_depth: 4 } });
      setTree(res.data.root);
    } catch (e) {
      setTree(null);
    }
    setLoading(false);
  }, [rootGuid]);

  useEffect(() => { fetchDrilldown(); }, [fetchDrilldown]);

  const renderNode = (node: DrilldownNode, depth = 0): React.ReactNode => {
    const hColor = healthColors[node.health_level || 'healthy'] || '#d9d9d9';
    return (
      <div key={node.guid}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '4px 8px', borderRadius: 4,
          background: depth === 0 ? `${hColor}10` : '#fafafa',
          border: `1px solid ${depth === 0 ? hColor : '#f0f0f0'}`,
          marginBottom: 2,
        }}>
          {depth > 0 && node.relation_type && (
            <Tag style={{ fontSize: 9 }}>{node.relation_type}</Tag>
          )}
          <span style={{ fontWeight: depth === 0 ? 700 : 400, fontSize: 12 }}>{node.display_name}</span>
          <Tag style={{ fontSize: 9 }}>{node.type_name}</Tag>
          <span style={{ fontSize: 11, color: hColor, fontWeight: 600 }}>{node.health_score ?? '?'}</span>
          {node.alert_count > 0 && <Badge count={node.alert_count} style={{ backgroundColor: '#ff4d4f' }} />}
        </div>
        {node.children.length > 0 && (
          <div style={{ marginLeft: 16 }}>
            {node.children.map(child => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  if (loading) return <Spin style={{ display: 'block', margin: '20px auto' }} />;
  if (!tree) return <Empty description="无纵向承载关系" imageStyle={{ height: 50 }} />;

  return (
    <div style={{ maxHeight: 380, overflow: 'auto', padding: '8px 0' }}>
      {renderNode(tree)}
    </div>
  );
}

// ============================================================
// 业务拓扑主页面
// ============================================================
export default function LogicalTopologyPage() {
  const [nodes, setNodes] = useState<LogicalNode[]>([]);
  const [edges, setEdges] = useState<LogicalEdge[]>([]);
  const [layers, setLayers] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<LogicalNode | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [bizServiceFilter, setBizServiceFilter] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState('');
  const [healthFilter, setHealthFilter] = useState<string | undefined>(undefined);
  // 邻居高亮（点击传播）
  const [neighborGuids, setNeighborGuids] = useState<Set<string>>(new Set());

  const fetchLogical = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (bizServiceFilter) params.biz_service = bizServiceFilter;
      const res = await axios.get(`${API}/topology/logical`, { params });
      setNodes(res.data.nodes || []);
      setEdges(res.data.edges || []);
      setLayers(res.data.layers || []);
    } catch (e) {
      message.error('加载业务拓扑失败');
    }
    setLoading(false);
  }, [bizServiceFilter]);

  useEffect(() => { fetchLogical(); }, [fetchLogical]);

  // ── 节点过滤 + 高亮计算 ──
  const { filteredNodes, filteredEdges, highlightedGuids, fadedGuids } = useMemo(() => {
    // 1. 健康状态过滤
    let visibleNodes = nodes;
    if (healthFilter) {
      visibleNodes = nodes.filter(n => n.health_level === healthFilter);
    }

    // 2. 搜索过滤
    let hGuids = new Set<string>();
    let fGuids = new Set<string>();

    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      const matched = visibleNodes.filter(n =>
        n.name.toLowerCase().includes(q) ||
        n.display_name.toLowerCase().includes(q) ||
        n.type_name.toLowerCase().includes(q)
      );
      const matchedSet = new Set(matched.map(n => n.guid));

      // 匹配节点的直接邻居
      const neighborSet = new Set<string>();
      for (const e of edges) {
        if (matchedSet.has(e.from_guid)) neighborSet.add(e.to_guid);
        if (matchedSet.has(e.to_guid)) neighborSet.add(e.from_guid);
      }

      // 高亮 = 匹配节点 + 邻居
      hGuids = new Set([...matchedSet, ...neighborSet]);
      // 暗淡 = 不在以上集合里的节点
      const allGuids = new Set(visibleNodes.map(n => n.guid));
      for (const g of allGuids) {
        if (!hGuids.has(g)) fGuids.add(g);
      }
    }

    // 3. 只保留可见节点相关的边
    const visibleSet = new Set(visibleNodes.map(n => n.guid));
    const visEdges = edges.filter(e =>
      visibleSet.has(e.from_guid) && visibleSet.has(e.to_guid)
    );

    return { filteredNodes: visibleNodes, filteredEdges: visEdges, highlightedGuids: hGuids, fadedGuids: fGuids };
  }, [nodes, edges, searchText, healthFilter]);

  // 布局（只用过滤后数据）
  const { positions } = useMemo(() => layoutLogicalGraph(filteredNodes, filteredEdges), [filteredNodes, filteredEdges]);

  const bizServices = useMemo(() => {
    return Array.from(new Set(nodes.map(n => n.biz_service).filter(Boolean))) as string[];
  }, [nodes]);

  const handleNodeClick = (node: LogicalNode) => {
    setSelectedNode(node);
    setDrawerOpen(true);
    // 传播高亮：只显示该节点的 1 度邻居
    const nSet = new Set<string>([node.guid]);
    for (const e of edges) {
      if (e.from_guid === node.guid) nSet.add(e.to_guid);
      if (e.to_guid === node.guid) nSet.add(e.from_guid);
    }
    setNeighborGuids(nSet);
  };

  const clearFilters = () => {
    setSearchText('');
    setHealthFilter(undefined);
    setBizServiceFilter(undefined);
    setNeighborGuids(new Set());
  };

  const hasActiveFilter = searchText || healthFilter || bizServiceFilter;

  return (
    <div style={{ padding: '0 16px 16px' }}>
      {/* ── 标题栏 + 筛选器 ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <ApartmentOutlined style={{ fontSize: 18, color: '#1890ff' }} />
        <span style={{ fontSize: 16, fontWeight: 600 }}>业务应用拓扑</span>

        {/* 搜索框 */}
        <Input
          prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
          placeholder="搜索节点名称或类型…"
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          allowClear
          style={{ width: 200 }}
          size="small"
        />

        {/* 健康状态筛选 */}
        <Select
          allowClear placeholder="健康状态"
          style={{ width: 130 }}
          onChange={v => setHealthFilter(v || undefined)}
          value={healthFilter}
          options={[
            { label: '🟢 正常', value: 'healthy' },
            { label: '🟡 警告', value: 'warning' },
            { label: '🔴 严重', value: 'critical' },
          ]}
          size="small"
        />

        {/* 业务线筛选 */}
        <Select
          allowClear placeholder="业务线"
          style={{ width: 160 }}
          onChange={v => setBizServiceFilter(v || undefined)}
          value={bizServiceFilter}
          options={bizServices.map(b => ({ label: b, value: b }))}
          size="small"
        />

        {hasActiveFilter && (
          <Button size="small" icon={<CloseOutlined />} onClick={clearFilters}>
            清除筛选
          </Button>
        )}

        <span style={{ marginLeft: 'auto', color: '#8c8c8c', fontSize: 12 }}>
          {filteredNodes.length}/{nodes.length} 实体 · {filteredEdges.length} 关系
          {hasActiveFilter && ` · 已筛选`}
        </span>
      </div>

      {/* ── 图例 ── */}
      <div style={{ display: 'flex', gap: 20, fontSize: 11, color: '#8c8c8c', marginBottom: 8, flexWrap: 'wrap' }}>
        <span>
          <span style={{ display: 'inline-block', width: 24, height: 2, background: '#1890ff', verticalAlign: 'middle', marginRight: 4 }} />
          同步调用
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 24, height: 1.5, borderTop: '2px dashed #722ed1', verticalAlign: 'middle', marginRight: 4 }} />
          异步调用
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 28, height: 3, background: '#52c41a', verticalAlign: 'middle', marginRight: 4 }} />
          <span style={{ display: 'inline-block', width: 20, height: 1.5, background: '#faad14', verticalAlign: 'middle', marginRight: 4 }} />
          <span style={{ display: 'inline-block', width: 14, height: 1, background: '#ff4d4f', verticalAlign: 'middle', marginRight: 4 }} />
          边宽=流量，颜色=错误率（绿→黄→红）
        </span>
        <span>圆环=健康度 · 🔴角标=未确认告警</span>
        {layers.map(l => (
          <span key={l} style={{
            padding: '1px 6px', borderRadius: 4, fontSize: 10,
            background: layerColors[l] || '#f5f5f5',
          }}>
            {l}
          </span>
        ))}
      </div>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
      ) : filteredNodes.length === 0 ? (
        <Empty description="无匹配数据，试试调整筛选条件" />
      ) : (
        <Card bodyStyle={{ padding: 0 }} style={{ borderRadius: 8 }}>
          <LogicalGraph
            nodes={filteredNodes}
            edges={filteredEdges}
            positions={positions}
            onNodeClick={handleNodeClick}
            selectedGuid={selectedNode?.guid || null}
            searchText={searchText}
            highlightedGuids={highlightedGuids}
            fadedGuids={fadedGuids}
          />
        </Card>
      )}

      {/* ── 节点详情抽屉 ── */}
      <Drawer
        title={
          <Space>
            {selectedNode && (typeIcons[selectedNode.type_name] || <ApiOutlined />)}
            <span>{selectedNode?.display_name}</span>
            <Tag>{selectedNode?.type_name}</Tag>
            {selectedNode?.health_level && (
              <Tag color={selectedNode.health_level === 'healthy' ? 'green' : selectedNode.health_level === 'warning' ? 'orange' : 'red'}>
                {selectedNode.health_level}
              </Tag>
            )}
          </Space>
        }
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setSelectedNode(null); setNeighborGuids(new Set()); }}
        width={520}
        destroyOnClose
      >
        {selectedNode && (
          <>
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 6, fontWeight: 600 }}>
                <ArrowRightOutlined style={{ marginRight: 4 }} />
                横向调用指标
              </div>
              <HorizontalMetricsPanel node={selectedNode} />
            </div>

            <Divider style={{ margin: '12px 0' }} />

            <div>
              <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 6, fontWeight: 600 }}>
                <ArrowRightOutlined style={{ marginRight: 4 }} />
                纵向承载链（容器 → 进程 → 服务器）
              </div>
              <DrilldownTree rootGuid={selectedNode.guid} />
            </div>
          </>
        )}
      </Drawer>
    </div>
  );
}
