import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Card, Drawer, Descriptions, Spin, Empty, Space, Tag, Tabs, Badge, Table, Row, Col, Progress, Divider } from 'antd';
import {
  ApartmentOutlined, ApiOutlined, DatabaseOutlined,
  DesktopOutlined, CloudServerOutlined, ArrowLeftOutlined,
  BranchesOutlined, AlertOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import { TimeRangeBar } from '../components/TimeRangeContext';

const API = '/api/v1/cmdb';

// ---- 类型定义 ----
interface Entity {
  guid: string; name: string; type_name: string;
  health_score: number; health_level: string; risk_score: number;
  biz_service: string; biz_system: string; system_name: string;
  attributes: Record<string, any>;
  labels: Record<string, string>;
  health_detail: any;
}
interface Relation {
  guid: string; type_name: string;
  from_guid: string; to_guid: string;
  dimension: string; source: string;
}
interface TraceRelation {
  caller: string; callee: string;
  call_count: number; avg_latency_ms: number;
  p99_latency_ms: number; error_rate: number;
}
interface DrillNode {
  entity: Entity;
  relation_type: string;
  children: DrillNode[];
}

// ---- 颜色常量 ----
const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};
const relLineStyle: Record<string, { dash: string; width: number }> = {
  calls:          { dash: 'none',    width: 2 },
  depends_on:     { dash: '6,3',     width: 1.5 },
  runs_on:        { dash: '4,3',     width: 1.5 },
  hosts:          { dash: '4,3',     width: 1.5 },
  includes:       { dash: '8,4',     width: 2 },
  connected_to:   { dash: '2,2',     width: 1 },
  async_calls:    { dash: '10,3,2,3', width: 1.5 },
};
const typeColors: Record<string, string> = {
  Service: '#1890ff', Host: '#13c2c2', MySQL: '#fa8c16', Redis: '#eb2f96',
  Database: '#fa8c16', NetworkDevice: '#2f54eb', Middleware: '#13c2c2',
  Business: '#722ed1',
};

// ---- 节点尺寸 ----
const NODE_R = 32;          // 服务节点半径
const SYSTEM_R = 56;        // 系统节点半径

// ---- 错误率颜色（圆周描边） ----
function errorRateColor(rate: number): string {
  if (rate <= 0) return '#52c41a';
  if (rate <= 5) return '#faad14';
  return '#ff4d4f';
}

// ---- 健康度颜色（圆内图标） ----
// 优先用 apdex，否则用 health_score
function healthColor(entity: Entity): string {
  const ad = entity.health_detail?.apdex;
  if (ad !== undefined) {
    if (ad >= 0.94) return '#52c41a';
    if (ad >= 0.7) return '#faad14';
    return '#ff4d4f';
  }
  // fallback 到 health_level
  return healthColors[entity.health_level] || '#d9d9d9';
}

// ---- 错误率弧形 ----
function errorArc(r: number, ratio: number): string {
  if (ratio <= 0) return '';
  if (ratio >= 1) return `M 0 ${-r} A ${r} ${r} 0 1 1 -0.01 ${-r} Z`;
  const startAngle = Math.PI / 2;
  const endAngle = startAngle - ratio * 2 * Math.PI;
  const x1 = r * Math.cos(startAngle), y1 = r * Math.sin(startAngle);
  const x2 = r * Math.cos(endAngle), y2 = r * Math.sin(endAngle);
  const large = ratio > 0.5 ? 1 : 0;
  return `M 0 0 L ${x1} ${y1} A ${r} ${r} 0 ${large} 0 ${x2} ${y2} Z`;
}

// ---- 类型 SVG 图标 ----
type IconFn = (color: string) => React.ReactNode;
const _typeIcons: Record<string, IconFn> = {
  Service: (c) => <g><path d="M-2,-8 L4,-1 L0,-1 L2,8 L-4,1 L0,1 Z" fill={c} opacity={0.85} /></g>,
  Host: (c) => <g>
    <rect x={-7} y={-7} width={14} height={4} rx={1} fill="none" stroke={c} strokeWidth={1.5} />
    <rect x={-7} y={-2} width={14} height={4} rx={1} fill="none" stroke={c} strokeWidth={1.5} />
    <rect x={-7} y={3} width={14} height={4} rx={1} fill="none" stroke={c} strokeWidth={1.5} />
    <circle cx={-4} cy={-5} r={1} fill={c} /><circle cx={-4} cy={0} r={1} fill={c} /><circle cx={-4} cy={5} r={1} fill={c} />
  </g>,
  MySQL: (c) => <g>
    <path d="M0,-7 C4,-7 7,-4 7,-1 C7,3 4,7 0,7 C-2,7 -3,5 -3,3 L-5,5 L-5,3 C-6,1 -6,-2 -4,-4 C-3,-6 -1,-7 0,-7Z" fill={c} opacity={0.25} stroke={c} strokeWidth={1} />
    <path d="M3,-4 L6,-6 M6,-6 L5,-3" stroke={c} strokeWidth={1} fill="none" />
  </g>,
  Redis: (c) => <g>
    <rect x={-6} y={-6} width={12} height={3} rx={1} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
    <rect x={-6} y={-2} width={12} height={3} rx={1} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
    <rect x={-6} y={2} width={12} height={3} rx={1} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
  </g>,
  Database: (c) => <g>
    <ellipse cx={0} cy={-4} rx={7} ry={3} fill="none" stroke={c} strokeWidth={1.5} />
    <path d="M-7,-4 L-7,4 A7,3 0 0,0 7,4 L7,-4" fill={c} opacity={0.15} stroke={c} strokeWidth={1.5} />
    <ellipse cx={0} cy={0} rx={7} ry={3} fill="none" stroke={c} strokeWidth={0.8} opacity={0.4} />
  </g>,
  Business: (c) => <g>
    <rect x={-7} y={-7} width={5} height={5} rx={1} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
    <rect x={2} y={-7} width={5} height={5} rx={1} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
    <rect x={-7} y={2} width={5} height={5} rx={1} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
    <rect x={2} y={2} width={5} height={5} rx={1} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
  </g>,
  NetworkDevice: (c) => <g>
    <rect x={-7} y={-4} width={14} height={8} rx={2} fill="none" stroke={c} strokeWidth={1.5} />
    <circle cx={-3} cy={-1} r={1.2} fill={c} /><circle cx={0} cy={-1} r={1.2} fill={c} /><circle cx={3} cy={-1} r={1.2} fill={c} />
    <line x1={-5} y1={3} x2={-1} y2={3} stroke={c} strokeWidth={1} /><line x1={1} y1={3} x2={5} y2={3} stroke={c} strokeWidth={1} />
  </g>,
  Middleware: (c) => <g>
    <path d="M0,-7 L7,-3 L7,3 L0,7 L-7,3 L-7,-3 Z" fill="none" stroke={c} strokeWidth={1.5} />
    <line x1={-7} y1={-3} x2={7} y2={-3} stroke={c} strokeWidth={0.8} opacity={0.5} />
    <line x1={-7} y1={3} x2={7} y2={3} stroke={c} strokeWidth={0.8} opacity={0.5} />
  </g>,
  K8sCluster: (c) => <g>
    <path d="M0,-7 L6,-3.5 L6,3.5 L0,7 L-6,3.5 L-6,-3.5 Z" fill="none" stroke={c} strokeWidth={1.5} />
    <circle cx={0} cy={0} r={2} fill={c} opacity={0.3} stroke={c} strokeWidth={1} />
  </g>,
  K8sPod: (c) => <g>
    <circle cx={0} cy={0} r={5} fill="none" stroke={c} strokeWidth={1.5} />
    <path d="M0,-5 L0,-2 M5,0 L2,0 M0,5 L0,2 M-5,0 L-2,0" stroke={c} strokeWidth={1.5} />
    <circle cx={0} cy={0} r={1.5} fill={c} />
  </g>,
  default: (c) => <g>
    <rect x={-6} y={-6} width={12} height={12} rx={3} fill="none" stroke={c} strokeWidth={1.5} />
    <text x={0} y={4} fontSize={10} textAnchor="middle" fill={c}>?</text>
  </g>,
};
function getTypeIcon(typeName: string): React.ReactNode {
  const fn = _typeIcons[typeName] || _typeIcons['default'];
  return fn('#595959');
}

// ============================================================
// 纵向钻取树组件
// ============================================================
const DrillDownTree: React.FC<{ entity: Entity }> = ({ entity }) => {
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
        if (child) { child.relation_type = r.type_name; children.push(child); }
      }
      return { entity: ent, relation_type: '', children };
    } catch { return null; }
  };

  const renderNode = (node: DrillNode, depth = 0): React.ReactNode => {
    const e = node.entity;
    const hColor = healthColors[e.health_level] || '#d9d9d9';
    return (
      <div key={e.guid} style={{ marginLeft: depth * 24, marginBottom: 6 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '5px 8px', borderRadius: 6,
          background: depth === 0 ? `${hColor}10` : '#fafafa',
          border: `1px solid ${depth === 0 ? hColor : '#f0f0f0'}`,
        }}>
          {node.relation_type && <Tag style={{ fontSize: 9, border: `1px dashed ${hColor}`, background: 'transparent' }}>{node.relation_type}</Tag>}
          <span style={{ fontWeight: depth === 0 ? 700 : 400, fontSize: 12 }}>{e.name}</span>
          <Tag color={typeColors[e.type_name]}>{e.type_name}</Tag>
          <span style={{ fontSize: 11, color: hColor, fontWeight: 600 }}>{e.health_score ?? '?'}</span>
        </div>
        {node.children.map(c => renderNode(c, depth + 1))}
      </div>
    );
  };

  if (loading) return <Spin style={{ display: 'block', margin: '30px auto' }} />;
  if (!tree) return <Empty description="无纵向关系数据" imageStyle={{ height: 60 }} />;
  return <div style={{ maxHeight: 450, overflow: 'auto', padding: '8px 0' }}>{renderNode(tree)}</div>;
};

// ============================================================
// 主组件
// ============================================================
const TopologyPage: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [traceRels, setTraceRels] = useState<TraceRelation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState('drill');
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [entityAlerts, setEntityAlerts] = useState<any[]>([]);
  const [entitySpans, setEntitySpans] = useState<any[]>([]);
  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [systemFilter, setSystemFilter] = useState('all');

  // ---- 系统视图状态 ----
  const [inSystemView, setInSystemView] = useState(false);
  const [currentSystem, setCurrentSystem] = useState<string>('');

  // ---- 数据加载 ----
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [entRes, traceRes] = await Promise.all([
        axios.get(`${API}/entities`, { params: { limit: 500 } }),
        axios.get(`${API}/discover/trace/topology`, { params: { window_minutes: 1440 } }),
      ]);
      const entList: Entity[] = entRes.data.items || [];
      setEntities(entList);
      setTraceRels(traceRes.data.relations || []);

      const relResults = await Promise.all(
        entList.slice(0, 80).map(e =>
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

  const entityMap = useMemo(() => {
    const m: Record<string, Entity> = {};
    entities.forEach(e => m[e.guid] = e);
    return m;
  }, [entities]);

  const entityByName = useMemo(() => {
    const m: Record<string, Entity> = {};
    entities.forEach(e => m[e.name] = e);
    return m;
  }, [entities]);

  // ---- 错误率计算（来自 traceRels） ----
  const errorRateByName = useMemo(() => {
    const m: Record<string, number> = {};
    traceRels.forEach(r => {
      const prev = m[r.callee];
      if (prev === undefined || r.error_rate > prev) m[r.callee] = r.error_rate;
    });
    return m;
  }, [traceRels]);

  // ---- 系统分组 ----
  const systems = useMemo(() => {
    const s: Record<string, Entity[]> = {};
    entities.forEach(e => {
      const sys = e.biz_system || e.system_name || '__no_system__';
      (s[sys] ||= []).push(e);
    });
    return s;
  }, [entities]);

  const systemList = useMemo(() => Object.keys(systems).filter(k => k !== '__no_system__'), [systems]);
  const noSystemEntities = systems['__no_system__'] || [];

  // ---- 高亮状态 ----
  const hlGuid = selected?.guid || null;
  const relatedRels = useMemo(() => {
    if (!hlGuid) return new Set<string>();
    const s = new Set<string>();
    relations.forEach(r => { if (r.from_guid === hlGuid || r.to_guid === hlGuid) s.add(r.guid); });
    return s;
  }, [hlGuid, relations]);

  // ---- 进入系统视图 ----
  const enterSystem = (sysName: string) => {
    setCurrentSystem(sysName);
    setInSystemView(true);
  };

  // ---- 节点点击 ----
  const handleNodeClick = async (e: Entity) => {
    setSelected(e); setDrawerOpen(true); setDrawerTab('drill');
    setEntityAlerts([]); setEntitySpans([]);
    setDrawerLoading(true);
    try {
      const [alertRes] = await Promise.all([
        axios.get(`${API}/entities/${e.guid}/alerts`, { params: { limit: 20 } }).catch(() => ({ data: { items: [] } })),
      ]);
      setEntityAlerts(alertRes.data.items || []);
      const spans = (traceRels || []).filter((r: TraceRelation) => r.caller === e.name || r.callee === e.name);
      setEntitySpans(spans);
    } catch (err) { console.error(err); }
    setDrawerLoading(false);
  };

  const handleDrawerClose = () => { setDrawerOpen(false); setSelected(null); };

  // ============================================================
  // 全局拓扑布局（平铺服务，无L1-L4分层）
  // ============================================================
  const globalLayout = useMemo(() => {
    const W = 1200;
    const nodeGap = NODE_R * 2 + 16;
    const sysGap = NODE_R * 2 + 30;
    const pos: Record<string, { x: number; y: number }> = {};
    const systemBounds: Record<string, { x0: number; y0: number; x1: number; y1: number }> = {};

    let totalH = 60;

    // 有系统的服务：按系统分组
    if (systemList.length > 0) {
      systemList.forEach((sys, si) => {
        const members = systems[sys];
        const cols = Math.ceil(Math.sqrt(members.length));
        const rows = Math.ceil(members.length / cols);
        const spanW = cols * nodeGap;
        const spanH = rows * nodeGap;
        const sx0 = 60 + si * (spanW + sysGap * 2);
        const sy0 = totalH;

        members.forEach((e, i) => {
          const col = i % cols; const row = Math.floor(i / cols);
          pos[e.guid] = { x: sx0 + col * nodeGap, y: sy0 + row * nodeGap };
        });

        systemBounds[sys] = {
          x0: sx0 - SYSTEM_R, y0: sy0 - SYSTEM_R,
          x1: sx0 + spanW + SYSTEM_R, y1: sy0 + spanH + SYSTEM_R,
        };
        totalH = Math.max(totalH, sy0 + spanH + SYSTEM_R * 2 + 20);
      });
    }

    // 无系统的服务：平铺在底部
    if (noSystemEntities.length > 0) {
      const startY = totalH + 20;
      const perRow = Math.floor((W - 120) / nodeGap);
      noSystemEntities.forEach((e, i) => {
        const col = i % perRow; const row = Math.floor(i / perRow);
        pos[e.guid] = { x: 60 + col * nodeGap, y: startY + row * nodeGap };
      });
      const rows = Math.ceil(noSystemEntities.length / perRow);
      totalH = startY + rows * nodeGap + 60;
    }

    return { pos, height: Math.max(500, totalH), systemBounds };
  }, [systems, systemList, noSystemEntities]);

  // ============================================================
  // 系统内服务拓扑布局
  // ============================================================
  const systemLayout = useMemo(() => {
    if (!currentSystem) return { pos: {}, height: 400, edges: [] };
    const members = systems[currentSystem] || [];
    const W = 900;
    const nodeGap = NODE_R * 2 + 16;

    const pos: Record<string, { x: number; y: number }> = {};
    const cols = Math.ceil(Math.sqrt(members.length));
    members.forEach((e, i) => {
      const col = i % cols; const row = Math.floor(i / cols);
      pos[e.guid] = { x: 60 + col * nodeGap, y: 60 + row * nodeGap };
    });

    // 系统内的调用关系（两个端点都在该系统内）
    const guids = new Set(members.map(e => e.guid));
    const edges: { from: string; to: string; type: string }[] = [];
    traceRels.forEach(tr => {
      const callerEnt = entityByName[tr.caller];
      const calleeEnt = entityByName[tr.callee];
      if (callerEnt && calleeEnt && guids.has(callerEnt.guid) && guids.has(calleeEnt.guid)) {
        edges.push({ from: callerEnt.guid, to: calleeEnt.guid, type: 'calls' });
      }
    });
    relations.forEach(r => {
      if (r.type_name === 'calls' || r.type_name === 'depends_on') {
        if (guids.has(r.from_guid) && guids.has(r.to_guid)) {
          edges.push({ from: r.from_guid, to: r.to_guid, type: r.type_name });
        }
      }
    });

    const rows = Math.ceil(members.length / cols);
    const height = 60 + rows * nodeGap + 80;
    return { pos, height, edges };
  }, [currentSystem, systems, traceRels, relations, entityByName]);

  // ============================================================
  // 全局视图渲染
  // ============================================================
  const renderGlobalTopology = () => {
    if (entities.length === 0) return <Empty description="暂无实体数据" />;
    const { pos, height, systemBounds } = globalLayout;
    const svgW = 1200;

    // 过滤
    let visibleEntities = entities;
    if (typeFilter !== 'all') visibleEntities = visibleEntities.filter(e => e.type_name === typeFilter);
    if (searchText.trim()) {
      const kw = searchText.toLowerCase();
      visibleEntities = visibleEntities.filter(e => e.name.toLowerCase().includes(kw));
    }

    // 高亮相关
    const relatedGuids = new Set<string>();
    if (hlGuid) {
      relations.forEach(r => {
        if (r.from_guid === hlGuid) relatedGuids.add(r.to_guid);
        if (r.to_guid === hlGuid) relatedGuids.add(r.from_guid);
      });
      relatedGuids.add(hlGuid);
    }

    const visibleGuids = new Set(visibleEntities.map(e => e.guid));

    return (
      <Card size="small" style={{ overflow: 'auto', background: '#fafbfc' }}>
        <svg width="100%" height={height} viewBox={`0 0 ${svgW} ${height}`} style={{ minWidth: 800 }}>
          <defs>
            <marker id="arrow-g" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#bfbfbf" />
            </marker>
          </defs>

          {/* 系统虚线框 */}
          {Object.entries(systemBounds).map(([sys, bounds]) => {
            const isHl = searchText.trim() && visibleGuids.size > 0 &&
              systems[sys]?.some(e => visibleGuids.has(e.guid));
            return (
              <g key={sys}>
                <rect
                  x={bounds.x0} y={bounds.y0}
                  width={bounds.x1 - bounds.x0} height={bounds.y1 - bounds.y0}
                  rx={16} fill="none"
                  stroke={isHl ? '#1890ff' : '#d9d9d9'}
                  strokeWidth={isHl ? 2 : 1}
                  strokeDasharray="6,3"
                />
                <text x={bounds.x0 + 8} y={bounds.y0 - 6}
                  fontSize={11} fill={isHl ? '#1890ff' : '#595959'} fontWeight={700}
                  style={{ cursor: 'pointer' }}
                  onClick={() => enterSystem(sys)}>
                  🏢 {sys}
                </text>
              </g>
            );
          })}

          {/* 调用关系线 */}
          {relations.map(rel => {
            const f = pos[rel.from_guid], t = pos[rel.to_guid];
            if (!f || !t) return null;
            if (!visibleGuids.has(rel.from_guid) && !visibleGuids.has(rel.to_guid)) return null;
            const isHl = relatedRels.has(rel.guid);
            const ls = relLineStyle[rel.type_name] || { dash: 'none', width: 1.2 };
            const dx = t.x - f.x, dy = t.y - f.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const ux = dx / dist, uy = dy / dist;
            const x1 = f.x + ux * (NODE_R + 2), y1 = f.y + uy * (NODE_R + 2);
            const x2 = t.x - ux * (NODE_R + 2), y2 = t.y - uy * (NODE_R + 2);
            const dimmed = hlGuid && !isHl;
            return (
              <line key={rel.guid}
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={isHl ? '#1890ff' : '#bfbfbf'}
                strokeWidth={isHl ? ls.width + 0.5 : ls.width * 0.7}
                strokeDasharray={ls.dash}
                strokeOpacity={dimmed ? 0.1 : 1}
                markerEnd="url(#arrow-g)"
              />
            );
          })}

          {/* 服务节点 */}
          {entities.filter(e => pos[e.guid] && visibleGuids.has(e.guid)).map(e => {
            const p = pos[e.guid];
            const isHl = relatedGuids.has(e.guid);
            const dimmed = hlGuid && !isHl;
            const er = errorRateByName[e.name] ?? 0;
            const hc = healthColor(e);
            const isBad = e.health_level === 'critical' || e.health_level === 'down';
            const erRatio = Math.min(1, er / 100);

            return (
              <g key={e.guid}
                style={{ cursor: 'pointer' }}
                opacity={dimmed ? 0.15 : 1}
                onClick={() => handleNodeClick(e)}
                transform={`translate(${p.x}, ${p.y})`}
              >
                {/* 选中光环 */}
                {isHl && <circle cx={0} cy={0} r={NODE_R + 7} fill="none" stroke="#1890ff" strokeWidth={2} strokeDasharray="4,2" />}

                {/* 背景 */}
                <circle cx={0} cy={0} r={NODE_R} fill="white" />

                {/* 错误率弧形（圆周颜色） */}
                {erRatio > 0 && (
                  <path d={errorArc(NODE_R, erRatio)} fill={errorRateColor(er)} opacity={0.3} />
                )}

                {/* 圆边框（错误率颜色） */}
                <circle cx={0} cy={0} r={NODE_R} fill="none"
                  stroke={errorRateColor(er)} strokeWidth={isBad ? 3 : 1.5} />

                {/* 严重时背景 */}
                {isBad && !isHl && <circle cx={0} cy={0} r={NODE_R + 4} fill={hc} opacity={0.08} />}

                {/* 类型图标（健康度颜色） */}
                <g transform="translate(0, -6)">
                  <g transform={`scale(0.65)`} style={{ overflow: 'visible' }}>
                    {React.cloneElement(getTypeIcon(e.type_name) as React.ReactElement, { color: hc })}
                  </g>
                </g>

                {/* 名称 */}
                <text x={0} y={13} fontSize={7} fontWeight={700} fill="#262626" textAnchor="middle">
                  {e.name.length > 9 ? e.name.slice(0, 8) + '…' : e.name}
                </text>

                {/* 健康度分 */}
                <text x={0} y={21} fontSize={7} fill={hc} textAnchor="middle" fontWeight={600}>
                  {e.health_score ?? '?'}
                </text>
              </g>
            );
          })}
        </svg>

        {/* 底部统计 */}
        <div style={{ display: 'flex', gap: 24, marginTop: 8, fontSize: 11, color: '#8c8c8c', flexWrap: 'wrap' }}>
          <span>📊 {visibleEntities.length} 服务</span>
          <span>🔗 {relations.length} 调用关系</span>
          {systemList.length > 0 && <span>🏢 {systemList.length} 系统</span>}
          <span style={{ color: '#52c41a' }}>外环 = 错误率</span>
          <span style={{ color: '#1890ff' }}>图标 = 健康度</span>
          <span style={{ color: '#8c8c8c' }}>点击服务 → 纵向钻取</span>
        </div>
      </Card>
    );
  };

  // ============================================================
  // 系统内视图渲染
  // ============================================================
  const renderSystemTopology = () => {
    if (!currentSystem) return null;
    const members = systems[currentSystem] || [];
    const { pos, height, edges } = systemLayout;

    // 高亮
    const relatedGuids = new Set<string>();
    if (hlGuid) {
      relations.forEach(r => {
        if (r.from_guid === hlGuid) relatedGuids.add(r.to_guid);
        if (r.to_guid === hlGuid) relatedGuids.add(r.from_guid);
      });
      relatedGuids.add(hlGuid);
    }

    return (
      <Card size="small" style={{ overflow: 'auto', background: '#fafbfc' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <span style={{ fontSize: 13, fontWeight: 700 }}>🏢 系统: {currentSystem}</span>
          <span style={{ fontSize: 11, color: '#8c8c8c' }}>{members.length} 个服务</span>
        </div>

        <svg width="100%" height={height} viewBox={`0 0 900 ${height}`} style={{ minWidth: 600 }}>
          <defs>
            <marker id="arrow-sys" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#52c41a" />
            </marker>
          </defs>

          {/* 系统内调用关系 */}
          {edges.map((e, i) => {
            const f = pos[e.from], t = pos[e.to];
            if (!f || !t) return null;
            const ls = relLineStyle[e.type] || { dash: 'none', width: 1.5 };
            const midX = (f.x + t.x) / 2;
            const path = `M ${f.x + NODE_R} ${f.y} Q ${midX} ${f.y} ${midX} ${(f.y + t.y) / 2} T ${t.x - NODE_R} ${t.y}`;
            return <path key={i} d={path} fill="none" stroke="#52c41a" strokeWidth={ls.width} strokeOpacity={0.7}
              strokeDasharray={ls.dash} markerEnd="url(#arrow-sys)" />;
          })}

          {/* 服务节点 */}
          {members.map(e => {
            const p = pos[e.guid];
            if (!p) return null;
            const isHl = relatedGuids.has(e.guid);
            const dimmed = hlGuid && !isHl;
            const er = errorRateByName[e.name] ?? 0;
            const hc = healthColor(e);
            const isBad = e.health_level === 'critical' || e.health_level === 'down';
            const erRatio = Math.min(1, er / 100);

            return (
              <g key={e.guid}
                style={{ cursor: 'pointer' }}
                opacity={dimmed ? 0.15 : 1}
                onClick={() => handleNodeClick(e)}
                transform={`translate(${p.x}, ${p.y})`}
              >
                {isHl && <circle cx={0} cy={0} r={NODE_R + 7} fill="none" stroke="#1890ff" strokeWidth={2} strokeDasharray="4,2" />}
                <circle cx={0} cy={0} r={NODE_R} fill="white" />
                {erRatio > 0 && <path d={errorArc(NODE_R, erRatio)} fill={errorRateColor(er)} opacity={0.3} />}
                <circle cx={0} cy={0} r={NODE_R} fill="none" stroke={errorRateColor(er)} strokeWidth={isBad ? 3 : 1.5} />
                {isBad && !isHl && <circle cx={0} cy={0} r={NODE_R + 4} fill={hc} opacity={0.08} />}
                <g transform="translate(0, -6)">
                  <g transform="scale(0.65)">
                    {React.cloneElement(getTypeIcon(e.type_name) as React.ReactElement, { color: hc })}
                  </g>
                </g>
                <text x={0} y={13} fontSize={7} fontWeight={700} fill="#262626" textAnchor="middle">
                  {e.name.length > 9 ? e.name.slice(0, 8) + '…' : e.name}
                </text>
                <text x={0} y={21} fontSize={7} fill={hc} textAnchor="middle" fontWeight={600}>
                  {e.health_score ?? '?'}
                </text>
              </g>
            );
          })}
        </svg>

        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: '#8c8c8c' }}>
          <span>📊 {members.length} 服务</span>
          <span>🔗 {edges.length} 系统内调用</span>
          <span style={{ color: '#52c41a' }}>外环 = 错误率 · 图标 = 健康度</span>
        </div>
      </Card>
    );
  };

  // ============================================================
  // 可用类型列表
  // ============================================================
  const typeOptions = useMemo(() => {
    const types = new Set(entities.map(e => e.type_name));
    return ['all', ...Array.from(types)];
  }, [entities]);

  // ============================================================
  // 主渲染
  // ============================================================
  return (
    <div>
      <TimeRangeBar onQuery={() => {}} />
      <h2 style={{ marginBottom: 16 }}>
        <ApartmentOutlined style={{ marginRight: 8 }} />
        {inSystemView ? `🏢 ${currentSystem}` : '🔗 全局拓扑'}
      </h2>

      {/* 顶部工具栏 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        {inSystemView ? (
          <button
            onClick={() => { setInSystemView(false); setCurrentSystem(''); }}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: '#fff', border: '1px solid #d9d9d9', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}
          >
            <ArrowLeftOutlined /> 返回全局拓扑
          </button>
        ) : (
          <>
            <input
              type="text"
              placeholder="搜索服务..."
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: 6, fontSize: 13, width: 160 }}
            />
            <select
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: 6, fontSize: 13 }}
            >
              {typeOptions.map(t => <option key={t} value={t}>{t === 'all' ? '所有类型' : t}</option>)}
            </select>
            <button
              onClick={fetchData}
              style={{ padding: '6px 12px', background: '#1890ff', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}
            >
              🔄 刷新
            </button>
            <span style={{ fontSize: 11, color: '#8c8c8c', marginLeft: 8 }}>
              {entities.length} 实体 · {traceRels.length} Trace调用
            </span>
          </>
        )}
      </div>

      {/* 主拓扑画布 */}
      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : inSystemView ? (
        renderSystemTopology()
      ) : (
        renderGlobalTopology()
      )}

      {/* 图例 */}
      {!inSystemView && (
        <div style={{ marginTop: 12, padding: '8px 16px', background: '#fafbfc', borderRadius: 6, display: 'flex', gap: 24, fontSize: 11, color: '#8c8c8c', flexWrap: 'wrap' }}>
          <span>
            <strong>外环颜色</strong> = 错误率：
            <span style={{ marginLeft: 6 }}>🟢 ≤0%</span>
            <span style={{ marginLeft: 4 }}>🟡 1-5%</span>
            <span style={{ marginLeft: 4 }}>🔴 &gt;5%</span>
          </span>
          <span>
            <strong>图标颜色</strong> = 健康度（Apdex）：
            <span style={{ marginLeft: 6 }}>🟢 ≥0.94</span>
            <span style={{ marginLeft: 4 }}>🟡 0.7-0.93</span>
            <span style={{ marginLeft: 4 }}>🔴 &lt;0.7</span>
          </span>
          <span>
            <strong>线条</strong> = 调用关系
          </span>
          <span>
            <strong>系统</strong> = 点击名称进入系统内视图
          </span>
        </div>
      )}

      {/* 详情抽屉（点击服务弹出） */}
      <Drawer
        title={
          <Space>
            {selected && (
              <svg width={18} height={18} viewBox="-10 -10 20 20">
                <g transform="scale(0.6)">{getTypeIcon(selected.type_name)}</g>
              </svg>
            )}
            <span>{selected?.name}</span>
            {selected && <Tag color={healthColors[selected.health_level]}>{selected.health_level}</Tag>}
          </Space>
        }
        open={drawerOpen}
        onClose={handleDrawerClose}
        width={520}
      >
        {selected && (
          <>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="类型"><Tag color={typeColors[selected.type_name]}>{selected.type_name}</Tag></Descriptions.Item>
              <Descriptions.Item label="健康度">
                <Space>
                  <Progress percent={selected.health_score || 0} size="small"
                    strokeColor={healthColors[selected.health_level]} style={{ width: 120 }} />
                  <Tag color={healthColors[selected.health_level]}>{selected.health_level}</Tag>
                </Space>
              </Descriptions.Item>
              {selected.biz_service && <Descriptions.Item label="业务服务">{selected.biz_service}</Descriptions.Item>}
              {(selected.biz_system || selected.system_name) && (
                <Descriptions.Item label="系统">
                  <Tag>🏢 {selected.biz_system || selected.system_name}</Tag>
                </Descriptions.Item>
              )}
              <Descriptions.Item label="风险度">
                <span style={{ color: (selected.risk_score || 0) >= 50 ? '#ff4d4f' : '#52c41a', fontWeight: 'bold', fontSize: 18 }}>
                  {selected.risk_score ?? 0}
                </span>
              </Descriptions.Item>
            </Descriptions>

            <Divider style={{ margin: '12px 0' }} />

            {drawerLoading ? <Spin style={{ display: 'block', margin: '20px auto' }} /> :
              <Tabs activeKey={drawerTab} onChange={setDrawerTab} size="small"
                items={[
                  { key: 'drill', label: '🌲 纵向钻取', children: <DrillDownTree entity={selected} /> },
                  {
                    key: 'alerts', label: (
                      <span>
                        <AlertOutlined /> 告警{entityAlerts.length > 0 && <Badge count={entityAlerts.length} size="small" style={{ marginLeft: 4 }} />}
                      </span>
                    ), children: (
                      entityAlerts.length === 0 ? <Empty description="暂无告警" imageStyle={{ height: 40 }} /> :
                        <Table size="small" pagination={false} rowKey="alert_id"
                          dataSource={entityAlerts}
                          columns={[
                            { title: '状态', dataIndex: 'status', width: 50, render: (s: string) => s === 'firing' ? <Tag color="red">🔥</Tag> : <Tag color="green">✅</Tag> },
                            { title: '严重度', dataIndex: 'severity', width: 70, render: (s: string) => <Tag color={s === 'critical' ? 'red' : s === 'error' ? 'orange' : 'gold'}>{s}</Tag> },
                            { title: '标题', dataIndex: 'title', ellipsis: true },
                            { title: '时间', dataIndex: 'starts_at', width: 130, render: (t: string) => t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-' },
                          ]}
                        />
                    ),
                  },
                  {
                    key: 'spans', label: <span><ThunderboltOutlined /> 调用</span>, children: (
                      entitySpans.length === 0 ? <Empty description="暂无调用数据" imageStyle={{ height: 40 }} /> :
                        <div style={{ maxHeight: 400, overflow: 'auto' }}>
                          {entitySpans.map((s: TraceRelation, i: number) => (
                            <div key={i} style={{ padding: '6px 8px', marginBottom: 4, background: '#fafafa', borderRadius: 4, fontSize: 11 }}>
                              <Space>
                                <span style={{ fontWeight: 600 }}>{s.caller}</span>
                                <span style={{ color: '#8c8c8c' }}>→</span>
                                <span style={{ fontWeight: 600 }}>{s.callee}</span>
                              </Space>
                              <div style={{ color: '#8c8c8c', marginTop: 2 }}>
                                {s.call_count}次 · P99: {s.p99_latency_ms}ms · 错误率: {s.error_rate}%
                              </div>
                            </div>
                          ))}
                        </div>
                    ),
                  },
                ]}
              />
            }
          </>
        )}
      </Drawer>
    </div>
  );
};

export default TopologyPage;
