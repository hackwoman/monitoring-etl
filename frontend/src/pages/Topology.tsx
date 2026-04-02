import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Card, Tag, Drawer, Descriptions, Spin, Empty, Space, Row, Col, Divider, Progress, Tabs, Table, Timeline, Badge } from 'antd';
import {
  ApartmentOutlined, ApiOutlined, DatabaseOutlined,
  DesktopOutlined, CloudServerOutlined, GlobalOutlined,
  BranchesOutlined, AlertOutlined, ClockCircleOutlined,
  FileTextOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API = '/api/v1/cmdb';

// ---- 类型定义 ----
interface Entity {
  guid: string; name: string; type_name: string;
  health_score: number; health_level: string; risk_score: number;
  biz_service: string; attributes: Record<string, any>;
  blast_radius: number; propagation_hops: number;
  health_detail: any; labels: Record<string, string>;
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
interface DrillNode {
  entity: Entity;
  relation_type: string;
  children: DrillNode[];
}

// ---- 颜色/图标 ----
const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};
// 类型→图形形状（不靠颜色区分）
const typeShapes: Record<string, 'rect' | 'circle' | 'diamond' | 'hexagon'> = {
  Business: 'diamond', Service: 'rect', Host: 'hexagon',
  MySQL: 'circle', Redis: 'circle', Database: 'circle',
  NetworkDevice: 'diamond', Middleware: 'rect',
};
const typeIcons: Record<string, React.ReactNode> = {
  Business: <ApartmentOutlined />, Service: <ApiOutlined />,
  Host: <DesktopOutlined />, MySQL: <DatabaseOutlined />,
  Redis: <DatabaseOutlined />, Database: <DatabaseOutlined />,
  NetworkDevice: <CloudServerOutlined />,
};
// 关系→线条样式（不靠颜色区分）
const relLineStyle: Record<string, { dash: string; width: number }> = {
  calls:          { dash: 'none',    width: 2 },
  depends_on:     { dash: '6,3',     width: 1.5 },
  runs_on:        { dash: '4,3',     width: 1.5 },
  hosts:          { dash: '4,3',     width: 1.5 },
  includes:       { dash: '8,4',     width: 2 },
  connected_to:   { dash: '2,2',     width: 1 },
  has_endpoint:   { dash: '1,2',     width: 1 },
  async_calls:    { dash: '10,3,2,3', width: 1.5 },
};
// 保留类型颜色（仅用于抽屉详情等辅助场景，不在拓扑主视觉中使用）
const typeColors: Record<string, string> = {
  Business: '#722ed1', Service: '#1890ff', Host: '#13c2c2',
  MySQL: '#fa8c16', Redis: '#eb2f96', Database: '#fa8c16',
  NetworkDevice: '#2f54eb', Middleware: '#13c2c2',
};

// ---- 圆形节点相关 ----
const NODE_R = 32;

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

const typeIconChars: Record<string, string> = {
  Service: '⚙', Host: '🖥', MySQL: '🐬',
  Redis: '💎', Database: '🗄', Business: '🏢',
  NetworkDevice: '🌐', Middleware: '⚙', Endpoint: '🔗',
  K8sCluster: '☸', K8sPod: '📦', IP: '🌐',
};

// ============================================================
// 纵向下钻拓扑组件
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
          {node.relation_type && <Tag style={{ fontSize: 9, border: `1px dashed ${healthColors[e.health_level] || '#d9d9d9'}`, background: 'transparent' }}>{node.relation_type}</Tag>}
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
  const [activeTab, setActiveTab] = useState('global');
  const [drawerTab, setDrawerTab] = useState('metrics');
  const [hlGuid, setHlGuid] = useState<string | null>(null);
  const [entityAlerts, setEntityAlerts] = useState<any[]>([]);
  const [entityRecords, setEntityRecords] = useState<any[]>([]);
  const [entitySpans, setEntitySpans] = useState<any[]>([]);
  const [drawerLoading, setDrawerLoading] = useState(false);

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

      // 批量取关系
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

  // ---- 全局拓扑布局（从下到上） ----
  const globalLayout = useMemo(() => {
    const layerOrder = ['NetworkDevice', 'Host', 'Redis', 'MySQL', 'Database', 'Middleware', 'Service', 'Business'];
    const bizGroups: Record<string, Entity[]> = {};
    entities.forEach(e => { (bizGroups[e.biz_service || '未分组'] ||= []).push(e); });

    const W = 1100, nodeGap = NODE_R * 2 + 12, layerGap = NODE_R * 2 + 30, bizGap = 20;
    const pos: Record<string, { x: number; y: number }> = {};
    let totalH = 40;

    for (const [biz, ents] of Object.entries(bizGroups)) {
      const layers: Record<number, Entity[]> = {};
      for (const e of ents) {
        const idx = Math.max(0, layerOrder.indexOf(e.type_name));
        (layers[idx] ||= []).push(e);
      }
      const sorted = Object.keys(layers).map(Number).sort((a, b) => a - b);
      const groupH = sorted.length * layerGap + 30;
      const baseY = totalH;

      for (let i = 0; i < sorted.length; i++) {
        const items = layers[sorted[i]];
        const sp = Math.min(nodeGap + 10, (W - 80) / items.length);
        const sx = (W - sp * (items.length - 1)) / 2;
        const y = baseY + NODE_R + 10 + (sorted.length - 1 - i) * layerGap;
        items.forEach((e, j) => { pos[e.guid] = { x: sx + j * sp, y }; });
      }
      pos[`__biz_${biz}`] = { x: 20, y: baseY };
      totalH = baseY + groupH + bizGap;
      pos[`__biz_${biz}`] = { x: 20, y: baseY };
      totalH = baseY + groupH + bizGap;
    }
    return { pos, height: Math.max(500, totalH) };
  }, [entities]);

  // ---- 调用拓扑布局（有向图） ----
  const callLayout = useMemo(() => {
    // 从 traceRels 构建有向图节点
    const nodeSet = new Set<string>();
    traceRels.forEach(r => { nodeSet.add(r.caller); nodeSet.add(r.callee); });
    const nodeList = Array.from(nodeSet);

    // BFS 分层：找 root 节点（没有被调用的）
    const callees = new Set(traceRels.map(r => r.callee));
    const roots = nodeList.filter(n => !callees.has(n));
    if (roots.length === 0 && nodeList.length > 0) roots.push(nodeList[0]);

    const layers: Record<number, string[]> = {};
    const visited = new Set<string>();
    let queue = roots.map(r => ({ name: r, layer: 0 }));
    roots.forEach(r => visited.add(r));

    while (queue.length > 0) {
      const next: { name: string; layer: number }[] = [];
      for (const { name, layer } of queue) {
        (layers[layer] ||= []).push(name);
        for (const r of traceRels) {
          if (r.caller === name && !visited.has(r.callee)) {
            visited.add(r.callee);
            next.push({ name: r.callee, layer: layer + 1 });
          }
        }
      }
      queue = next;
    }
    // 未访问的节点放到最后层
    const maxLayer = Math.max(0, ...Object.keys(layers).map(Number));
    nodeList.filter(n => !visited.has(n)).forEach(n => {
      (layers[maxLayer + 1] ||= []).push(n);
    });

    const W = 1100, sp = NODE_R * 2 + 30, layerH = NODE_R * 2 + 40;
    const pos: Record<string, { x: number; y: number }> = {};
    const sortedLayers = Object.keys(layers).map(Number).sort((a, b) => a - b);
    let maxItems = 0;
    sortedLayers.forEach(l => { maxItems = Math.max(maxItems, (layers[l] || []).length); });

    for (const l of sortedLayers) {
      const items = layers[l] || [];
      const sx = (W - sp * (items.length - 1)) / 2;
      items.forEach((n, i) => { pos[n] = { x: sx + i * sp, y: 60 + l * layerH }; });
    }

    return { pos, height: Math.max(400, 60 + sortedLayers.length * layerH + 60), nodeNames: nodeList };
  }, [traceRels]);

  // ---- 基础设施拓扑布局 ----
  const infraLayout = useMemo(() => {
    // 只显示 Host、NetworkDevice、以及其上运行的 Service/DB
    const hosts = entities.filter(e => e.type_name === 'Host');
    const nets = entities.filter(e => e.type_name === 'NetworkDevice');
    const hostRels = relations.filter(r => r.type_name === 'runs_on' || r.type_name === 'hosts' || r.type_name === 'connected_to');

    // 找每个 host 上运行的实体
    const hostChildren: Record<string, Entity[]> = {};
    for (const r of hostRels) {
      if (r.type_name === 'runs_on') {
        const child = entityMap[r.from_guid];
        const host = entityMap[r.to_guid];
        if (child && host) (hostChildren[host.name] ||= []).push(child);
      }
    }

    const W = 1100, sp = NODE_R * 2 + 20;
    const pos: Record<string, { x: number; y: number }> = {};

    // 网络设备在顶部
    nets.forEach((n, i) => { pos[n.guid] = { x: W / 2 - (nets.length - 1) * sp / 2 + i * sp, y: 45 }; });

    // 主机在中间
    hosts.forEach((h, i) => { pos[h.guid] = { x: NODE_R + 20 + i * sp, y: 180 }; });

    // 主机上的服务在底部
    let childY = 320;
    for (const [hostName, children] of Object.entries(hostChildren)) {
      const host = entityByName[hostName];
      if (!host || !pos[host.guid]) continue;
      const hx = pos[host.guid].x;
      const csp = Math.min(NODE_R * 2 + 10, 160 / Math.max(children.length, 1));
      children.forEach((c, i) => {
        pos[c.guid] = { x: hx - (children.length - 1) * csp / 2 + i * csp, y: childY };
      });
    }

    return { pos, height: Math.max(500, childY + 100) };
  }, [entities, relations, entityMap, entityByName]);

  // ---- 选中相关关系 ----
  const relatedRels = useMemo(() => {
    if (!hlGuid) return new Set<string>();
    const s = new Set<string>();
    relations.forEach(r => { if (r.from_guid === hlGuid || r.to_guid === hlGuid) s.add(r.guid); });
    return s;
  }, [hlGuid, relations]);

  // ---- 节点点击 ----
  const handleNodeClick = async (e: Entity) => {
    setSelected(e); setHlGuid(e.guid); setDrawerOpen(true); setDrawerTab('metrics');
    setEntityAlerts([]); setEntityRecords([]); setEntitySpans([]);
    setDrawerLoading(true);
    try {
      const [alertRes, recordRes] = await Promise.all([
        axios.get(`${API}/entities/${e.guid}/alerts`, { params: { limit: 20 } }).catch(() => ({ data: { items: [] } })),
        axios.get(`/api/v1/records`, { params: { entity_name: e.name, time_range: '24h', limit: 20 } }).catch(() => ({ data: { items: [] } })),
      ]);
      setEntityAlerts(alertRes.data.items || []);
      setEntityRecords(recordRes.data.items || []);
      // Trace spans (从 ClickHouse 查)
      try {
        const spanRes = await axios.get(`/api/v1/cmdb/discover/trace/topology`, { params: { window_minutes: 60 } });
        const spans = (spanRes.data.relations || [])
          .filter((r: any) => r.caller === e.name || r.callee === e.name);
        setEntitySpans(spans);
      } catch { setEntitySpans([]); }
    } catch (err) { console.error(err); }
    setDrawerLoading(false);
  };
  const handleDrawerClose = () => { setDrawerOpen(false); setHlGuid(null); };

  // ---- 圆形节点渲染 ----
  const renderNode = (e: Entity, x: number, y: number, errorRate?: number) => {
    const hc = healthColors[e.health_level] || '#d9d9d9';
    const isBad = e.health_level === 'critical' || e.health_level === 'down';
    const isSel = hlGuid === e.guid;
    const r = NODE_R;
    const er = Math.min(100, Math.max(0, errorRate ?? 0));
    const erRatio = er / 100;
    const erColor = er > 10 ? '#ff4d4f' : er > 2 ? '#faad14' : 'rgba(255,77,79,0.15)';
    return (
      <g key={e.guid} style={{ cursor: 'pointer' }} onClick={() => handleNodeClick(e)}
         transform={`translate(${x}, ${y})`}>
        {isSel && <circle cx={0} cy={0} r={r + 6} fill="none" stroke="#1890ff" strokeWidth={2} strokeDasharray="4,2" />}
        {isBad && !isSel && <circle cx={0} cy={0} r={r + 4} fill={hc} opacity={0.08} />}
        <circle cx={0} cy={0} r={r} fill="white" />
        {erRatio > 0 && <path d={errorArc(r, erRatio)} fill={erColor} opacity={0.35} />}
        <circle cx={0} cy={0} r={r} fill="none" stroke={hc} strokeWidth={isBad ? 3 : 2} />
        <text x={0} y={-6} fontSize={16} textAnchor="middle" dominantBaseline="middle">{typeIconChars[e.type_name] || '📄'}</text>
        <text x={0} y={10} fontSize={8} fontWeight={700} fill="#262626" textAnchor="middle">{e.name.length > 8 ? e.name.slice(0, 7) + '…' : e.name}</text>
        <text x={0} y={20} fontSize={7} fill={hc} textAnchor="middle" fontWeight={600}>{e.health_score ?? '?'}</text>
      </g>
    );
  };

  const renderNameNode = (name: string, x: number, y: number, errorRate?: number) => {
    const e = entityByName[name];
    const hc = e ? (healthColors[e.health_level] || '#d9d9d9') : '#52c41a';
    const isBad = e && (e.health_level === 'critical' || e.health_level === 'down');
    const r = NODE_R;
    const er = Math.min(100, Math.max(0, errorRate ?? 0));
    const erRatio = er / 100;
    const erColor = er > 10 ? '#ff4d4f' : er > 2 ? '#faad14' : 'rgba(255,77,79,0.15)';
    return (
      <g key={name} style={{ cursor: 'pointer' }} onClick={() => e && handleNodeClick(e)}
         transform={`translate(${x}, ${y})`}>
        <circle cx={0} cy={0} r={r} fill="white" />
        {erRatio > 0 && <path d={errorArc(r, erRatio)} fill={erColor} opacity={0.35} />}
        <circle cx={0} cy={0} r={r} fill="none" stroke={isBad ? hc : '#d9d9d9'} strokeWidth={isBad ? 3 : 1.5} />
        <text x={0} y={-6} fontSize={16} textAnchor="middle" dominantBaseline="middle">{e ? (typeIconChars[e.type_name] || '📄') : '🔍'}</text>
        <text x={0} y={10} fontSize={8} fontWeight={700} fill="#262626" textAnchor="middle">{name.length > 8 ? name.slice(0, 7) + '…' : name}</text>
        {e && <text x={0} y={20} fontSize={7} fill={hc} textAnchor="middle" fontWeight={600}>{e.health_score ?? '?'}</text>}
      </g>
    );
  };

  // ============================================================
  // 三个视图
  // ============================================================

  // ---- 全局拓扑 ----
  const renderGlobal = () => {
    const bizGroups: Record<string, Entity[]> = {};
    entities.forEach(e => { (bizGroups[e.biz_service || '未分组'] ||= []).push(e); });
    return (
      <Card size="small" style={{ overflow: 'auto', background: '#fafbfc' }}>
        <svg width="100%" height={globalLayout.height} viewBox={`0 0 1100 ${globalLayout.height}`} style={{ minWidth: 800 }}>
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#bfbfbf" />
            </marker>
          </defs>
          {/* 虚线框 */}
          {Object.entries(bizGroups).map(([biz, ents]) => {
            const ps = ents.map(e => globalLayout.pos[e.guid]).filter(Boolean);
            if (!ps.length) return null;
            const pad = NODE_R + 10;
            const x0 = Math.min(...ps.map(p => p.x)) - pad, x1 = Math.max(...ps.map(p => p.x)) + pad;
            const y0 = Math.min(...ps.map(p => p.y)) - pad, y1 = Math.max(...ps.map(p => p.y)) + pad;
            return (
              <g key={biz}>
                <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} rx={12} fill="none" stroke="#d9d9d9" strokeWidth={1} strokeDasharray="6,3" />
                <text x={x0 + 6} y={y0 - 4} fontSize={10} fill="#8c8c8c" fontWeight="bold">{biz}</text>
              </g>
            );
          })}
          {/* 连线（从圆心到圆心，到圆边界截断） */}
          {relations.map(rel => {
            const f = globalLayout.pos[rel.from_guid], t = globalLayout.pos[rel.to_guid];
            if (!f || !t) return null;
            const isHl = relatedRels.has(rel.guid);
            const dimmed = hlGuid && !isHl;
            const ls = relLineStyle[rel.type_name] || { dash: 'none', width: 1.2 };
            // 计算从 f 圆心到 t 圆心的线段，截断到圆边界
            const dx = t.x - f.x, dy = t.y - f.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const ux = dx / dist, uy = dy / dist;
            const x1 = f.x + ux * (NODE_R + 2), y1 = f.y + uy * (NODE_R + 2);
            const x2 = t.x - ux * (NODE_R + 2), y2 = t.y - uy * (NODE_R + 2);
            return (
              <g key={rel.guid} opacity={dimmed ? 0.1 : 1}>
                <line x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={isHl ? '#1890ff' : '#bfbfbf'} strokeWidth={isHl ? ls.width + 0.5 : ls.width * 0.8}
                  strokeDasharray={ls.dash}
                  markerEnd="url(#arrow)" />
              </g>
            );
          })}
          {/* 节点 */}
          {entities.map(e => {
            const p = globalLayout.pos[e.guid];
            if (!p) return null;
            const dimmed = hlGuid && e.guid !== hlGuid && !relatedRels.has(
              relations.find(r => r.from_guid === e.guid || r.to_guid === e.guid)?.guid || ''
            );
            return <g key={e.guid} opacity={dimmed ? 0.15 : 1}>{renderNode(e, p.x, p.y)}</g>;
          })}
        </svg>
      </Card>
    );
  };

  // ---- 调用拓扑（Trace 驱动） ----
  const renderCall = () => {
    if (traceRels.length === 0) return <Empty description="暂无 Trace 调用数据，请先生成 Trace" />;
    return (
      <Card size="small" style={{ overflow: 'auto', background: '#fafbfc' }}>
        <div style={{ marginBottom: 8, color: '#8c8c8c', fontSize: 11 }}>
          基于 Trace 数据自动发现 · 边粗细=调用量 · 颜色=错误率
        </div>
        <svg width="100%" height={callLayout.height} viewBox={`0 0 1100 ${callLayout.height}`} style={{ minWidth: 800 }}>
          <defs>
            <marker id="arrow-c" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#bfbfbf" />
            </marker>
          </defs>
          {/* 连线 */}
          {traceRels.map((r, i) => {
            const f = callLayout.pos[r.caller], t = callLayout.pos[r.callee];
            if (!f || !t) return null;
            const sw = r.call_count > 10000 ? 3 : r.call_count > 1000 ? 2 : 1.2;
            const col = r.error_rate > 20 ? '#ff4d4f' : r.error_rate > 5 ? '#faad14' : '#bfbfbf';
            const dx = t.x - f.x, dy = t.y - f.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const ux = dx / dist, uy = dy / dist;
            const x1 = f.x + ux * (NODE_R + 2), y1 = f.y + uy * (NODE_R + 2);
            const x2 = t.x - ux * (NODE_R + 2), y2 = t.y - uy * (NODE_R + 2);
            return (
              <g key={i}>
                <line x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={col} strokeWidth={sw} strokeOpacity={0.6} markerEnd="url(#arrow-c)" />
                <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6}
                  fontSize={8} fill="#8c8c8c" textAnchor="middle">
                  {r.p99_latency_ms}ms · {r.error_rate}%
                </text>
              </g>
            );
          })}
          {/* 节点 */}
          {callLayout.nodeNames.map(name => {
            const p = callLayout.pos[name];
            if (!p) return null;
            // 传递错误率
            const tr = traceRels.find(r => r.caller === name || r.callee === name);
            return renderNameNode(name, p.x, p.y, tr?.error_rate);
          })}
        </svg>
      </Card>
    );
  };

  // ---- 基础设施拓扑 ----
  const renderInfra = () => {
    const hosts = entities.filter(e => e.type_name === 'Host');
    const nets = entities.filter(e => e.type_name === 'NetworkDevice');
    if (hosts.length === 0 && nets.length === 0) return <Empty description="暂无基础设施数据" />;

    return (
      <Card size="small" style={{ overflow: 'auto', background: '#fafbfc' }}>
        <svg width="100%" height={infraLayout.height} viewBox={`0 0 1100 ${infraLayout.height}`} style={{ minWidth: 800 }}>
          <defs>
            <marker id="arrow-i" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#bfbfbf" />
            </marker>
          </defs>
          {/* 连线（圆心到圆心） */}
          {relations.filter(r => r.type_name === 'connected_to' || r.type_name === 'runs_on').map(r => {
            const f = infraLayout.pos[r.from_guid], t = infraLayout.pos[r.to_guid];
            if (!f || !t) return null;
            const ls = relLineStyle[r.type_name] || { dash: '4,3', width: 1 };
            const dx = t.x - f.x, dy = t.y - f.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const ux = dx / dist, uy = dy / dist;
            const x1 = f.x + ux * (NODE_R + 2), y1 = f.y + uy * (NODE_R + 2);
            const x2 = t.x - ux * (NODE_R + 2), y2 = t.y - uy * (NODE_R + 2);
            return <line key={r.guid} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="#bfbfbf" strokeWidth={ls.width * 0.8} strokeDasharray={ls.dash} markerEnd="url(#arrow-i)" />;
          })}
          {/* 节点 */}
          {entities.filter(e => infraLayout.pos[e.guid]).map(e => {
            const p = infraLayout.pos[e.guid];
            const dimmed = hlGuid && e.guid !== hlGuid;
            return <g key={e.guid} opacity={dimmed ? 0.15 : 1}>{renderNode(e, p.x, p.y)}</g>;
          })}
          {/* 层标签 */}
          <text x={10} y={45 + NODE_R} fontSize={10} fill="#8c8c8c" fontWeight="bold">网络层</text>
          <text x={10} y={180 + NODE_R} fontSize={10} fill="#8c8c8c" fontWeight="bold">主机层</text>
          <text x={10} y={320 + NODE_R} fontSize={10} fill="#8c8c8c" fontWeight="bold">服务/DB</text>
        </svg>
      </Card>
    );
  };

  // ============================================================
  // 主渲染
  // ============================================================
  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>
        <ApartmentOutlined style={{ marginRight: 8 }} />
        资源拓扑
      </h2>

      <Tabs activeKey={activeTab} onChange={setActiveTab}
        items={[
          { key: 'global', label: <span><GlobalOutlined /> 全局拓扑</span> },
          { key: 'call', label: <span><ApiOutlined /> 调用拓扑</span> },
          { key: 'infra', label: <span><DesktopOutlined /> 基础设施拓扑</span> },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Space style={{ marginBottom: 12 }}>
        <span style={{ color: '#8c8c8c' }}>{entities.length} 实体 · {relations.length} 关系
          {traceRels.length > 0 && ` · ${traceRels.length} 调用链`}
        </span>
      </Space>

      {loading ? <Spin size="large" style={{ display: 'block', margin: '100px auto' }} /> :
        entities.length === 0 ? <Empty /> :
        activeTab === 'global' ? renderGlobal() :
        activeTab === 'call' ? renderCall() :
        renderInfra()
      }

      {/* 图例（紧凑一行） */}
      <div style={{ marginTop: 12, padding: '6px 12px', background: '#fafbfc', borderRadius: 6, display: 'flex', gap: 24, fontSize: 11, color: '#8c8c8c', flexWrap: 'wrap' }}>
        <span>
          <strong>外环</strong> = 健康度：
          {Object.entries(healthColors).map(([l, c]) => (
            <span key={l} style={{ display: 'inline-flex', alignItems: 'center', gap: 2, marginLeft: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${c}`, display: 'inline-block' }} />
              {l}
            </span>
          ))}
        </span>
        <span>
          <strong>扇形</strong> = 错误率：
          <span style={{ marginLeft: 4 }}>🟢低</span>
          <span style={{ marginLeft: 4 }}>🟡中</span>
          <span style={{ marginLeft: 4 }}>🔴高</span>
        </span>
        <span>
          <strong>图标</strong> = 类型：
          {Object.entries(typeIconChars).filter(([k]) => ['Service','Host','MySQL','Redis','Business','NetworkDevice'].includes(k)).map(([k, v]) => (
            <span key={k} style={{ marginLeft: 6 }}>{v}{k}</span>
          ))}
        </span>
        <span>
          <strong>线条</strong> = 关系：—调用 ┄依赖 ┈运行于 ·连接
        </span>
      </div>

      {/* 详情抽屉 */}
      <Drawer
        title={<Space>{selected && typeIcons[selected.type_name]}<span>{selected?.name}</span>
          {selected && <Tag color={healthColors[selected.health_level]}>{selected.health_level}</Tag>}</Space>}
        open={drawerOpen} onClose={handleDrawerClose} width={480}
      >
        {selected && (
          <>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="类型"><Tag color={typeColors[selected.type_name]}>{selected.type_name}</Tag></Descriptions.Item>
              <Descriptions.Item label="健康度">
                <Space>
                  <Progress percent={selected.health_score || 0} size="small" strokeColor={healthColors[selected.health_level]} style={{ width: 100 }} />
                  <Tag color={healthColors[selected.health_level]}>{selected.health_level}</Tag>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="风险度">
                <span style={{ color: (selected.risk_score || 0) >= 50 ? '#ff4d4f' : '#52c41a', fontWeight: 'bold', fontSize: 18 }}>{selected.risk_score ?? 0}</span>
              </Descriptions.Item>
              <Descriptions.Item label="影响范围">
                <Space><BranchesOutlined /><span>{selected.blast_radius || 0} 个实体受影响</span></Space>
              </Descriptions.Item>
              <Descriptions.Item label="业务">{selected.biz_service || '-'}</Descriptions.Item>
            </Descriptions>

            <Divider style={{ margin: '12px 0' }} />
            {drawerLoading ? <Spin style={{ display: 'block', margin: '20px auto' }} /> :
            <Tabs activeKey={drawerTab} onChange={setDrawerTab} size="small"
              items={[
                { key: 'metrics', label: '📊 指标', children: (
                  <>
                    {selected.health_detail && typeof selected.health_detail === 'object' && (
                      <>
                        <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 6 }}>健康度维度</div>
                        {Object.entries(selected.health_detail)
                          .filter(([k]) => !['method', 'reason', 'children_count', 'children_avg', 'min_score', 'max_score'].includes(k))
                          .map(([dim, info]: [string, any]) => (
                            <Row key={dim} style={{ marginBottom: 6 }}>
                              <Col span={7}><span style={{ fontSize: 11 }}>{dim}</span></Col>
                              <Col span={8}><Progress percent={info.score || 0} size="small"
                                strokeColor={(info.score || 0) >= 80 ? '#52c41a' : (info.score || 0) >= 60 ? '#faad14' : '#ff4d4f'} style={{ width: 80 }} /></Col>
                              <Col span={9} style={{ color: '#8c8c8c', fontSize: 10 }}>值: {info.value ?? 'N/A'}</Col>
                            </Row>
                          ))}
                      </>
                    )}
                    <Divider orientation="left" plain style={{ fontSize: 10 }}>属性</Divider>
                    <Space wrap>{Object.entries(selected.attributes || {}).map(([k, v]) => <Tag key={k}>{k}: {String(v)}</Tag>)}</Space>
                  </>
                )},
                { key: 'alerts', label: <span><AlertOutlined /> 告警{entityAlerts.length > 0 && <Badge count={entityAlerts.length} size="small" style={{ marginLeft: 4 }} />}</span>, children: (
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
                )},
                { key: 'events', label: <span><FileTextOutlined /> 记录</span>, children: (
                  entityRecords.length === 0 ? <Empty description="暂无记录" imageStyle={{ height: 40 }} /> :
                  <div style={{ maxHeight: 400, overflow: 'auto', padding: '0 8px' }}>
                    <Timeline>
                      {entityRecords.map((r, i) => (
                        <Timeline.Item key={i}
                          color={r.severity === 'critical' ? 'red' : r.severity === 'error' ? 'orange' : r.severity === 'warning' ? 'gold' : 'green'}>
                          <div style={{ fontSize: 11, fontWeight: 600 }}>{r.title || r.record_type}</div>
                          <div style={{ fontSize: 10, color: '#8c8c8c' }}>
                            {r.timestamp ? new Date(r.timestamp).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                            {' · '}{r.record_type}{' · '}{r.severity}
                          </div>
                        </Timeline.Item>
                      ))}
                    </Timeline>
                  </div>
                )},
                { key: 'spans', label: <span><ThunderboltOutlined /> 调用链</span>, children: (
                  entitySpans.length === 0 ? <Empty description="暂无调用链数据" imageStyle={{ height: 40 }} /> :
                  <div style={{ maxHeight: 400, overflow: 'auto' }}>
                    {entitySpans.map((s, i) => (
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
                )},
                { key: 'drill', label: '🌲 下钻', children: <DrillDownTree entity={selected} /> },
                { key: 'relations', label: '🔗 关系', children: (
                  <div style={{ maxHeight: 400, overflow: 'auto' }}>
                    {relations.filter(r => r.from_guid === selected.guid || r.to_guid === selected.guid).map(r => {
                      const otherGuid = r.from_guid === selected.guid ? r.to_guid : r.from_guid;
                      const other = entityMap[otherGuid];
                      const dir = r.from_guid === selected.guid ? '→' : '←';
                      return (
                        <div key={r.guid} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 6px', marginBottom: 3, background: '#fafafa', borderRadius: 4 }}>
                          <Tag style={{ fontSize: 9 }}>{r.type_name}</Tag>
                          <span>{dir}</span>
                          <span style={{ fontWeight: 600, fontSize: 12 }}>{other?.name || '未知'}</span>
                          {other && <Tag color={typeColors[other.type_name]}>{other.type_name}</Tag>}
                          <Tag color={r.dimension === 'horizontal' ? 'blue' : 'green'} style={{ fontSize: 8 }}>{r.dimension || 'v'}</Tag>
                        </div>
                      );
                    })}
                  </div>
                )},
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
