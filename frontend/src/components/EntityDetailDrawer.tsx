import React, { useState, useEffect } from 'react';
import { Drawer, Descriptions, Tag, Space, Progress, Divider, Tabs, Table, Timeline, Empty, Spin, Badge } from 'antd';
import {
  BranchesOutlined, AlertOutlined, FileTextOutlined,
  ThunderboltOutlined, ApartmentOutlined, ApiOutlined,
  DatabaseOutlined, DesktopOutlined, CloudServerOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const CMDB = '/api/v1/cmdb';
const API = '/api/v1';

export interface DrawerEntity {
  guid: string; name: string; type_name: string;
  health_score: number; health_level: string; risk_score: number;
  biz_service: string; attributes: Record<string, any>;
  blast_radius: number; propagation_hops?: number;
  health_detail: any; labels: Record<string, string>;
}

interface Relation {
  guid: string; type_name: string;
  from_guid: string; to_guid: string;
  dimension: string; source: string;
}

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a', unknown: '#d9d9d9',
};
const typeColors: Record<string, string> = {
  Business: '#722ed1', Service: '#1890ff', Host: '#13c2c2',
  MySQL: '#fa8c16', Redis: '#eb2f96', Database: '#fa8c16',
  NetworkDevice: '#2f54eb', Middleware: '#13c2c2',
};
const typeIcons: Record<string, React.ReactNode> = {
  Business: <ApartmentOutlined />, Service: <ApiOutlined />,
  Host: <DesktopOutlined />, MySQL: <DatabaseOutlined />,
  Redis: <DatabaseOutlined />, Database: <DatabaseOutlined />,
  NetworkDevice: <CloudServerOutlined />,
};

// 实体类型 → 分析页路径
const typeAnalysisPath: Record<string, string> = {
  Service: '/service-analysis',
  Host: '/host-analysis',
  NetworkDevice: '/network-analysis',
};

interface Props {
  entity: DrawerEntity | null;
  open: boolean;
  onClose: () => void;
  /** 关系 Tab 中点击关联实体时的回调（用于路由跳转） */
  onEntityClick?: (entity: { guid: string; type_name: string; name: string }) => void;
}

const EntityDetailDrawer: React.FC<Props> = ({ entity, open, onClose, onEntityClick }) => {
  const [activeTab, setActiveTab] = useState('metrics');
  const [loading, setLoading] = useState(false);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [records, setEntityRecords] = useState<any[]>([]);
  const [spans, setSpans] = useState<any[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [entityMap, setEntityMap] = useState<Record<string, any>>({});

  useEffect(() => {
    if (!entity || !open) return;
    setActiveTab('metrics');
    setAlerts([]); setEntityRecords([]); setSpans([]); setRelations([]);
    setLoading(true);

    const fetchData = async () => {
      try {
        const [alertRes, recordRes, relRes] = await Promise.all([
          axios.get(`${CMDB}/entities/${entity.guid}/alerts`, { params: { limit: 20 } }).catch(() => ({ data: { items: [] } })),
          axios.get(`${API}/records`, { params: { entity_name: entity.name, time_range: '24h', limit: 20 } }).catch(() => ({ data: { items: [] } })),
          axios.get(`${CMDB}/entities/${entity.guid}/relations`).catch(() => ({ data: { items: [] } })),
        ]);
        setAlerts(alertRes.data.items || []);
        setEntityRecords(recordRes.data.items || []);
        const rels: Relation[] = relRes.data.items || [];
        setRelations(rels);

        // 加载关联实体信息
        const guids = new Set<string>();
        rels.forEach(r => { guids.add(r.from_guid); guids.add(r.to_guid); });
        const map: Record<string, any> = {};
        await Promise.all(Array.from(guids).slice(0, 20).map(async g => {
          try {
            const res = await axios.get(`${CMDB}/entities/${g}`);
            map[g] = res.data;
          } catch {}
        }));
        setEntityMap(map);

        // Trace spans
        try {
          const spanRes = await axios.get(`${CMDB}/discover/trace/topology`, { params: { window_minutes: 60 } });
          setSpans((spanRes.data.relations || [])
            .filter((r: any) => r.caller === entity.name || r.callee === entity.name));
        } catch { setSpans([]); }
      } catch (err) { console.error(err); }
      setLoading(false);
    };
    fetchData();
  }, [entity?.guid, open]);

  if (!entity) return null;

  const hc = healthColors[entity.health_level] || '#d9d9d9';

  const handleRelationClick = (rel: Relation) => {
    const otherGuid = rel.from_guid === entity.guid ? rel.to_guid : rel.from_guid;
    const other = entityMap[otherGuid];
    if (other && onEntityClick) {
      onEntityClick({ guid: other.guid, type_name: other.type_name, name: other.name });
    }
  };

  return (
    <Drawer
      title={
        <Space>
          {typeIcons[entity.type_name]}
          <span>{entity.name}</span>
          <Tag color={hc}>{entity.health_level}</Tag>
        </Space>
      }
      open={open} onClose={onClose} width={480}
    >
      <Descriptions column={1} size="small">
        <Descriptions.Item label="类型"><Tag color={typeColors[entity.type_name]}>{entity.type_name}</Tag></Descriptions.Item>
        <Descriptions.Item label="健康度">
          <Space>
            <Progress percent={entity.health_score || 0} size="small" strokeColor={hc} style={{ width: 100 }} />
            <Tag color={hc}>{entity.health_level}</Tag>
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="风险度">
          <span style={{ color: (entity.risk_score || 0) >= 50 ? '#ff4d4f' : '#52c41a', fontWeight: 'bold', fontSize: 18 }}>
            {entity.risk_score ?? 0}
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="影响范围">
          <Space><BranchesOutlined /><span>{entity.blast_radius || 0} 个实体受影响</span></Space>
        </Descriptions.Item>
        <Descriptions.Item label="业务">{entity.biz_service || '-'}</Descriptions.Item>
      </Descriptions>

      <Divider style={{ margin: '12px 0' }} />
      {loading ? <Spin style={{ display: 'block', margin: '20px auto' }} /> :
        <Tabs activeKey={activeTab} onChange={setActiveTab} size="small" items={[
          {
            key: 'metrics', label: '📊 指标',
            children: (
              <>
                {entity.health_detail && typeof entity.health_detail === 'object' && (
                  <>
                    <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 6 }}>健康度维度</div>
                    {Object.entries(entity.health_detail)
                      .filter(([k]) => !['method', 'reason', 'children_count', 'children_avg', 'min_score', 'max_score'].includes(k))
                      .map(([dim, info]: [string, any]) => (
                        <div key={dim} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                          <span style={{ fontSize: 11, width: 60 }}>{dim}</span>
                          <Progress percent={info.score || 0} size="small"
                            strokeColor={(info.score || 0) >= 80 ? '#52c41a' : (info.score || 0) >= 60 ? '#faad14' : '#ff4d4f'}
                            style={{ flex: 1 }} />
                          <span style={{ color: '#8c8c8c', fontSize: 10, width: 60 }}>{info.value ?? 'N/A'}</span>
                        </div>
                      ))}
                  </>
                )}
                <Divider orientation="left" plain style={{ fontSize: 10 }}>属性</Divider>
                <Space wrap>{Object.entries(entity.attributes || {}).map(([k, v]) => <Tag key={k}>{k}: {String(v)}</Tag>)}</Space>
              </>
            )
          },
          {
            key: 'alerts', label: <span><AlertOutlined /> 告警{alerts.length > 0 && <Badge count={alerts.length} size="small" style={{ marginLeft: 4 }} />}</span>,
            children: alerts.length === 0 ? <Empty description="暂无告警" imageStyle={{ height: 40 }} /> : (
              <Table size="small" pagination={false} rowKey="alert_id" dataSource={alerts}
                columns={[
                  { title: '状态', dataIndex: 'status', width: 50, render: (s: string) => s === 'firing' ? <Tag color="red">🔥</Tag> : <Tag color="green">✅</Tag> },
                  { title: '严重度', dataIndex: 'severity', width: 70, render: (s: string) => <Tag color={s === 'critical' ? 'red' : s === 'error' ? 'orange' : 'gold'}>{s}</Tag> },
                  { title: '标题', dataIndex: 'title', ellipsis: true },
                  { title: '时间', dataIndex: 'starts_at', width: 130, render: (t: string) => t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-' },
                ]}
              />
            )
          },
          {
            key: 'records', label: <span><FileTextOutlined /> 记录</span>,
            children: records.length === 0 ? <Empty description="暂无记录" imageStyle={{ height: 40 }} /> : (
              <div style={{ maxHeight: 400, overflow: 'auto', padding: '0 8px' }}>
                <Timeline>
                  {records.map((r, i) => (
                    <Timeline.Item key={i} color={r.severity === 'critical' ? 'red' : r.severity === 'error' ? 'orange' : r.severity === 'warning' ? 'gold' : 'green'}>
                      <div style={{ fontSize: 11, fontWeight: 600 }}>{r.title || r.record_type}</div>
                      <div style={{ fontSize: 10, color: '#8c8c8c' }}>
                        {r.timestamp ? new Date(r.timestamp).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                        {' · '}{r.record_type}{' · '}{r.severity}
                      </div>
                    </Timeline.Item>
                  ))}
                </Timeline>
              </div>
            )
          },
          {
            key: 'spans', label: <span><ThunderboltOutlined /> 调用链</span>,
            children: spans.length === 0 ? <Empty description="暂无调用链数据" imageStyle={{ height: 40 }} /> : (
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                {spans.map((s, i) => (
                  <div key={i} style={{ padding: '6px 8px', marginBottom: 4, background: '#fafafa', borderRadius: 4, fontSize: 11 }}>
                    <Space><span style={{ fontWeight: 600 }}>{s.caller}</span><span style={{ color: '#8c8c8c' }}>→</span><span style={{ fontWeight: 600 }}>{s.callee}</span></Space>
                    <div style={{ color: '#8c8c8c', marginTop: 2 }}>{s.call_count}次 · P99: {s.p99_latency_ms}ms · 错误率: {s.error_rate}%</div>
                  </div>
                ))}
              </div>
            )
          },
          {
            key: 'relations', label: '🔗 关系',
            children: (
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                {relations.map(r => {
                  const otherGuid = r.from_guid === entity.guid ? r.to_guid : r.from_guid;
                  const other = entityMap[otherGuid];
                  const dir = r.from_guid === entity.guid ? '→' : '←';
                  return (
                    <div key={r.guid}
                      style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 6px', marginBottom: 3, background: '#fafafa', borderRadius: 4, cursor: 'pointer' }}
                      onClick={() => handleRelationClick(r)}
                    >
                      <Tag style={{ fontSize: 9 }}>{r.type_name}</Tag>
                      <span>{dir}</span>
                      <span style={{ fontWeight: 600, fontSize: 12, color: '#1890ff' }}>{other?.name || '未知'}</span>
                      {other && <Tag color={typeColors[other.type_name]}>{other.type_name}</Tag>}
                      <Tag color={r.dimension === 'horizontal' ? 'blue' : 'green'} style={{ fontSize: 8 }}>{r.dimension || 'v'}</Tag>
                    </div>
                  );
                })}
              </div>
            )
          },
          {
            key: 'stacks', label: '💥 堆栈',
            children: (() => {
              const stackRecords = records.filter(r => r.record_type === 'stack_snapshot');
              if (stackRecords.length === 0) return <Empty description="暂无堆栈快照" imageStyle={{ height: 40 }} />;
              return (
                <div style={{ maxHeight: 400, overflow: 'auto' }}>
                  {stackRecords.map((r, i) => (
                    <div key={i} style={{ marginBottom: 12, padding: 8, background: '#1e1e1e', borderRadius: 4, fontFamily: 'monospace', fontSize: 10, color: '#d4d4d4', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      <div style={{ color: '#ce9178', marginBottom: 4, fontWeight: 600 }}>{r.title}</div>
                      {r.content}
                    </div>
                  ))}
                </div>
              );
            })()
          },
        ]}
        />
      }
    </Drawer>
  );
};

export default EntityDetailDrawer;
