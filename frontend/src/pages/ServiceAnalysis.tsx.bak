import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Space, Spin, Empty } from 'antd';
import {
  ApiOutlined, WarningOutlined, CheckCircleOutlined,
  ClockCircleOutlined, FireOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import EntityDetailDrawer, { DrawerEntity as Entity } from '../components/EntityDetailDrawer';
import { TimeRangeBar, useTimeRange } from '../components/TimeRangeContext';

const CMDB = '/api/v1/cmdb';
const API = '/api/v1';


interface Stats {
  total: number; avg_health_score: number;
  health_distribution: Record<string, number>;
  firing_alerts: number; alerts_by_severity: Record<string, number>;
}

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};

const ServiceAnalysis: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [traceStats, setTraceStats] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [entRes, statsRes, traceRes] = await Promise.all([
        axios.get(`${CMDB}/entities`, { params: { type_name: 'Service', limit: 100 } }),
        axios.get(`${CMDB}/stats`, { params: { type_name: 'Service' } }),
        axios.get(`${CMDB}/discover/trace/topology`, { params: { window_minutes: 60 } }).catch(() => ({ data: { relations: [] } })),
      ]);
      setEntities(entRes.data.items || []);
      setStats(statsRes.data);

      // 构建 trace 统计映射
      const tMap: Record<string, any> = {};
      for (const r of (traceRes.data.relations || [])) {
        if (!tMap[r.caller]) tMap[r.caller] = { p99: 0, error_rate: 0, calls: 0 };
        tMap[r.caller].p99 = Math.max(tMap[r.caller].p99, r.p99_latency_ms || 0);
        tMap[r.caller].error_rate = Math.max(tMap[r.caller].error_rate, r.error_rate || 0);
        tMap[r.caller].calls += r.call_count || 0;
      }
      setTraceStats(tMap);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // URL 参数自动打开实体
  useEffect(() => {
    const name = searchParams.get('name');
    if (name && entities.length > 0) {
      const found = entities.find(e => e.name === name);
      if (found) { setSelected(found); setDrawerOpen(true); }
    }
  }, [searchParams, entities]);

  const handleRowClick = (e: Entity) => { setSelected(e); setDrawerOpen(true); };
  const handleEntityClick = (info: { guid: string; type_name: string; name: string }) => {
    setDrawerOpen(false);
    const path = { Service: '/service-analysis', Host: '/host-analysis', NetworkDevice: '/network-analysis' }[info.type_name];
    if (path) navigate(`${path}?name=${info.name}`);
  };

  const columns = [
    { title: '服务名', dataIndex: 'name', sorter: (a: Entity, b: Entity) => a.name.localeCompare(b.name), render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { title: '健康度', dataIndex: 'health_score', sorter: (a: Entity, b: Entity) => (a.health_score || 0) - (b.health_score || 0),
      render: (_: any, r: Entity) => (
        <Space>
          <span style={{ color: healthColors[r.health_level], fontWeight: 600 }}>{r.health_score ?? '?'}</span>
          <Tag color={healthColors[r.health_level]}>{r.health_level}</Tag>
        </Space>
      )
    },
    { title: 'P99延迟', key: 'p99', sorter: (a: Entity, b: Entity) => (traceStats[a.name]?.p99 || 0) - (traceStats[b.name]?.p99 || 0),
      render: (_: any, r: Entity) => {
        const p99 = traceStats[r.name]?.p99 || 0;
        return <span style={{ color: p99 > 2000 ? '#ff4d4f' : p99 > 500 ? '#faad14' : '#52c41a' }}>{p99 > 0 ? `${p99.toFixed(0)}ms` : '-'}</span>;
      }
    },
    { title: '错误率', key: 'err', sorter: (a: Entity, b: Entity) => (traceStats[a.name]?.error_rate || 0) - (traceStats[b.name]?.error_rate || 0),
      render: (_: any, r: Entity) => {
        const err = traceStats[r.name]?.error_rate || 0;
        return <span style={{ color: err > 5 ? '#ff4d4f' : err > 1 ? '#faad14' : '#52c41a' }}>{err > 0 ? `${err}%` : '0%'}</span>;
      }
    },
    { title: '业务', dataIndex: 'biz_service', render: (v: string) => v || '-' },
    { title: '风险度', dataIndex: 'risk_score', sorter: (a: Entity, b: Entity) => (a.risk_score || 0) - (b.risk_score || 0),
      render: (v: number) => v && v > 50 ? <Tag color="red">{v}</Tag> : <span style={{ color: '#8c8c8c' }}>{v || 0}</span>
    },
  ];

  return (
    <div>
      <TimeRangeBar onQuery={() => fetchData()} />
      <h2 style={{ marginBottom: 16 }}><ApiOutlined style={{ marginRight: 8 }} />服务分析</h2>

      {/* 汇总卡片 */}
      {stats && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={4}><Card size="small"><Statistic title="总服务数" value={stats.total} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="健康" value={stats.health_distribution?.healthy || 0} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="告警" value={stats.health_distribution?.warning || 0} valueStyle={{ color: '#faad14' }} prefix={<WarningOutlined />} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="严重" value={stats.health_distribution?.critical || 0} valueStyle={{ color: '#ff4d4f' }} prefix={<FireOutlined />} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="活跃告警" value={stats.firing_alerts} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="平均健康分" value={stats.avg_health_score || '-'} suffix={stats.avg_health_score ? '/100' : ''} /></Card></Col>
        </Row>
      )}

      {/* 实体列表 */}
      {loading ? <Spin size="large" style={{ display: 'block', margin: '60px auto' }} /> :
        entities.length === 0 ? <Empty /> :
        <Table rowKey="guid" dataSource={entities} columns={columns} size="small" pagination={{ pageSize: 20 }}
          onRow={(record) => ({ onClick: () => handleRowClick(record), style: { cursor: 'pointer' } })}
        />
      }

      <EntityDetailDrawer entity={selected} open={drawerOpen} onClose={() => setDrawerOpen(false)} onEntityClick={handleEntityClick} />
    </div>
  );
};

export default ServiceAnalysis;
