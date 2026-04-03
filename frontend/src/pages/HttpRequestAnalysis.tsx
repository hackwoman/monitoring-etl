import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Space, Spin, Empty } from 'antd';
import {
  ApiOutlined, WarningOutlined, CheckCircleOutlined,
  FireOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import EntityDetailDrawer, { DrawerEntity as Entity } from '../components/EntityDetailDrawer';
import { TimeRangeBar, useTimeRange } from '../components/TimeRangeContext';

const CMDB = '/api/v1/cmdb';

interface Stats {
  total: number; avg_health_score: number;
  health_distribution: Record<string, number>;
  firing_alerts: number; alerts_by_severity: Record<string, number>;
}

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};

const HttpRequestAnalysis: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { range } = useTimeRange();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [entRes, statsRes] = await Promise.all([
        axios.get(`${CMDB}/entities`, { params: { type_name: 'HttpRequest', limit: 200 } }),
        axios.get(`${CMDB}/stats`, { params: { type_name: 'HttpRequest' } }),
      ]);
      setEntities(entRes.data.items || []);
      setStats(statsRes.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

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
    const path = { HttpRequest: '/http-request-analysis', Service: '/service-analysis', Host: '/host-analysis', NetworkDevice: '/network-analysis', Page: '/page-analysis' }[info.type_name];
    if (path) navigate(`${path}?name=${info.name}`);
  };

  // 从 attributes 读取 URL 模式和 HTTP 方法
  const getAttr = (e: Entity, key: string) => e.attributes?.[key] || '-';

  const columns = [
    { title: 'URL 模式', dataIndex: 'name', width: 220, sorter: (a: Entity, b: Entity) => a.name.localeCompare(b.name),
      render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
    { title: '方法', key: 'method', width: 70,
      render: (_: any, r: Entity) => {
        const m = getAttr(r, 'http_method');
        const colors: Record<string, string> = { GET: '#52c41a', POST: '#1890ff', PUT: '#faad14', DELETE: '#ff4d4f' };
        return <Tag color={colors[m] || 'default'}>{m}</Tag>;
      }
    },
    { title: '健康度', dataIndex: 'health_score', width: 110, sorter: (a: Entity, b: Entity) => (a.health_score || 0) - (b.health_score || 0),
      render: (_: any, r: Entity) => (
        <Space>
          <span style={{ color: healthColors[r.health_level] || '#999', fontWeight: 600 }}>{r.health_score ?? '?'}</span>
          <Tag color={healthColors[r.health_level]}>{r.health_level}</Tag>
        </Space>
      )
    },
    { title: 'DNS', key: 'dns', width: 70,
      render: (_: any, r: Entity) => {
        const v = r.attributes?.xhr_timing_dns;
        return v ? <span style={{ color: v > 500 ? '#ff4d4f' : v > 100 ? '#faad14' : '#52c41a' }}>{v}ms</span> : '-';
      }
    },
    { title: 'TCP', key: 'tcp', width: 70,
      render: (_: any, r: Entity) => {
        const v = r.attributes?.xhr_timing_tcp;
        return v ? <span style={{ color: v > 300 ? '#ff4d4f' : v > 100 ? '#faad14' : '#52c41a' }}>{v}ms</span> : '-';
      }
    },
    { title: 'SSL', key: 'ssl', width: 70,
      render: (_: any, r: Entity) => {
        const v = r.attributes?.xhr_timing_ssl;
        return v ? <span style={{ color: v > 500 ? '#ff4d4f' : v > 200 ? '#faad14' : '#52c41a' }}>{v}ms</span> : '-';
      }
    },
    { title: 'TTFB', key: 'ttfb', width: 80,
      render: (_: any, r: Entity) => {
        const v = r.attributes?.xhr_timing_ttfb;
        return v ? <span style={{ color: v > 2000 ? '#ff4d4f' : v > 800 ? '#faad14' : '#52c41a' }}>{v}ms</span> : '-';
      }
    },
    { title: '总耗时', key: 'total', width: 80, sorter: (a: Entity, b: Entity) => (a.attributes?.xhr_timing_total || 0) - (b.attributes?.xhr_timing_total || 0),
      render: (_: any, r: Entity) => {
        const v = r.attributes?.xhr_timing_total;
        return v ? <span style={{ color: v > 5000 ? '#ff4d4f' : v > 2000 ? '#faad14' : '#52c41a', fontWeight: 600 }}>{v}ms</span> : '-';
      }
    },
    { title: '业务域', key: 'biz', width: 90,
      render: (_: any, r: Entity) => {
        const d = getAttr(r, 'business_domain');
        return d !== '-' ? <Tag color="purple">{d}</Tag> : '-';
      }
    },
    { title: '地域', key: 'geo', width: 90,
      render: (_: any, r: Entity) => getAttr(r, 'geo_region')
    },
    { title: '运营商', key: 'isp', width: 80,
      render: (_: any, r: Entity) => {
        const v = getAttr(r, 'isp');
        return v !== '-' ? <Tag>{v}</Tag> : '-';
      }
    },
  ];

  return (
    <div>
      <TimeRangeBar onQuery={() => fetchData()} />
      <h2 style={{ marginBottom: 16 }}><ThunderboltOutlined style={{ marginRight: 8 }} />网络请求分析</h2>

      {stats && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={3}><Card size="small"><Statistic title="总请求数" value={stats.total} /></Card></Col>
          <Col span={3}><Card size="small"><Statistic title="健康" value={stats.health_distribution?.healthy || 0} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} /></Card></Col>
          <Col span={3}><Card size="small"><Statistic title="告警" value={stats.health_distribution?.warning || 0} valueStyle={{ color: '#faad14' }} prefix={<WarningOutlined />} /></Card></Col>
          <Col span={3}><Card size="small"><Statistic title="严重" value={stats.health_distribution?.critical || 0} valueStyle={{ color: '#ff4d4f' }} prefix={<FireOutlined />} /></Card></Col>
          <Col span={3}><Card size="small"><Statistic title="活跃告警" value={stats.firing_alerts} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
          <Col span={3}><Card size="small"><Statistic title="平均健康分" value={stats.avg_health_score || '-'} suffix={stats.avg_health_score ? '/100' : ''} /></Card></Col>
        </Row>
      )}

      {/* 网络耗时说明 */}
      <div style={{ marginBottom: 12, padding: '8px 12px', background: '#f6f8fa', borderRadius: 6, fontSize: 12, color: '#595959' }}>
        <strong>网络耗时拆解：</strong>DNS 解析 → TCP 握手 → SSL 握手 → 服务响应(TTFB) → 下载完成。
        网络问题定位：<code>DNS/TCP/SSL 高 + TTFB 正常</code> = 网络层问题，查 NetworkDevice；
        <code>TTFB 高 + 网络阶段正常</code> = 服务端问题，查 Service。
      </div>

      {loading ? <Spin size="large" style={{ display: 'block', margin: '60px auto' }} /> :
        entities.length === 0 ? <Empty description="暂无 HttpRequest 实体" /> :
        <Table rowKey="guid" dataSource={entities} columns={columns} size="small" pagination={{ pageSize: 20 }}
          onRow={(record) => ({ onClick: () => handleRowClick(record), style: { cursor: 'pointer' } })}
          scroll={{ x: 1200 }}
        />
      }

      <EntityDetailDrawer entity={selected} open={drawerOpen} onClose={() => setDrawerOpen(false)} onEntityClick={handleEntityClick} />
    </div>
  );
};

export default HttpRequestAnalysis;
