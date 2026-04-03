import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Space, Spin, Empty } from 'antd';
import { CloudServerOutlined, CheckCircleOutlined, WarningOutlined, FireOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import EntityDetailDrawer, { DrawerEntity as Entity } from '../components/EntityDetailDrawer';
import { TimeRangeBar, useTimeRange } from '../components/TimeRangeContext';

const CMDB = '/api/v1/cmdb';


interface Stats {
  total: number; avg_health_score: number;
  health_distribution: Record<string, number>;
  firing_alerts: number;
}

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a',
};

const NetworkAnalysis: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [entRes, statsRes] = await Promise.all([
        axios.get(`${CMDB}/entities`, { params: { type_name: 'NetworkDevice', limit: 100 } }),
        axios.get(`${CMDB}/stats`, { params: { type_name: 'NetworkDevice' } }),
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
    const path = { Service: '/service-analysis', Host: '/host-analysis', NetworkDevice: '/network-analysis' }[info.type_name];
    if (path) navigate(`${path}?name=${info.name}`);
  };

  // 着色辅助
  const colorVal = (v: any, w: number, c: number) => Number(v) >= c ? '#ff4d4f' : Number(v) >= w ? '#faad14' : '#52c41a';
  const attr = (e: Entity, k: string, d: any = '-') => e.attributes?.[k] !== undefined ? e.attributes[k] : d;

  const columns = [
    { title: '设备名', dataIndex: 'name', width: 160, sorter: (a: Entity, b: Entity) => a.name.localeCompare(b.name), render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { title: '厂商', key: 'vendor', width: 70, render: (_: any, r: Entity) => attr(r, 'vendor') },
    { title: '型号', key: 'model', width: 60, render: (_: any, r: Entity) => attr(r, 'model') },
    { title: '管理IP', key: 'mgmt_ip', width: 120, render: (_: any, r: Entity) => <code>{attr(r, 'mgmt_ip')}</code> },
    { title: '健康度', dataIndex: 'health_score', width: 110, sorter: (a: Entity, b: Entity) => (a.health_score || 0) - (b.health_score || 0),
      render: (_: any, r: Entity) => (
        <Space>
          <span style={{ color: healthColors[r.health_level], fontWeight: 600 }}>{r.health_score ?? '?'}</span>
          <Tag color={healthColors[r.health_level]}>{r.health_level}</Tag>
        </Space>
      )
    },
    { title: '丢包率', key: 'pkt_loss', width: 80,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'packet_loss', 0);
        return <span style={{ color: colorVal(v, 0.1, 1), fontWeight: 600 }}>{v}%</span>;
      }
    },
    { title: '延迟', key: 'latency', width: 70,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'latency_ms', 0);
        return <span style={{ color: colorVal(v, 10, 50) }}>{v}ms</span>;
      }
    },
    { title: '新建连接/s', key: 'tcp_new', width: 90,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'tcp_new_connections_rate', 0);
        return <span style={{ color: colorVal(v, 1000, 5000), fontWeight: 600 }}>{v}</span>;
      }
    },
    { title: '活跃连接', key: 'tcp_est', width: 80,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'tcp_established_count', 0);
        return <span style={{ color: colorVal(v, 10000, 50000) }}>{v}</span>;
      }
    },
    { title: 'TIME_WAIT', key: 'tcp_tw', width: 90,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'tcp_time_wait_count', 0);
        return <span style={{ color: colorVal(v, 5000, 20000) }}>{v}</span>;
      }
    },
    { title: '重传率', key: 'retransmit', width: 80,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'tcp_retransmit_rate', 0);
        return <span style={{ color: colorVal(v, 1, 5), fontWeight: 600 }}>{v}%</span>;
      }
    },
    { title: '带宽利用率', key: 'bw', width: 90,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'bandwidth_utilization', 0);
        return <span style={{ color: colorVal(v, 70, 90) }}>{v}%</span>;
      }
    },
    { title: '设备CPU', key: 'cpu', width: 80,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'device_cpu', 0);
        return <span style={{ color: colorVal(v, 70, 90) }}>{v}%</span>;
      }
    },
    { title: '设备内存', key: 'mem', width: 80,
      render: (_: any, r: Entity) => {
        const v = attr(r, 'device_memory', 0);
        return <span style={{ color: colorVal(v, 80, 95) }}>{v}%</span>;
      }
    },
    { title: '端口', key: 'ports', width: 70,
      render: (_: any, r: Entity) => {
        const up = attr(r, 'port_status_up', 0);
        const down = attr(r, 'port_status_down', 0);
        return <span>{up}<span style={{ color: '#52c41a' }}>↑</span> {down}<span style={{ color: '#ff4d4f' }}>↓</span></span>;
      }
    },
  ];

  return (
    <div>
      <TimeRangeBar onQuery={() => fetchData()} />
      <h2 style={{ marginBottom: 16 }}><CloudServerOutlined style={{ marginRight: 8 }} />网络分析</h2>

      {/* TCP 动态感知说明 */}
      <div style={{ marginBottom: 12, padding: '8px 12px', background: '#f6f8fa', borderRadius: 6, fontSize: 12, color: '#595959' }}>
        <strong>TCP 动态感知：</strong>新建连接/s 反映业务流量变化，TIME_WAIT 过高表示短连接风暴，重传率异常指向网络质量问题。
        设备 CPU/内存直接影响转发性能。端口状态变化可快速定位物理层故障。
      </div>

      {stats && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={4}><Card size="small"><Statistic title="网络设备" value={stats.total} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="健康" value={stats.health_distribution?.healthy || 0} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="告警" value={stats.health_distribution?.warning || 0} valueStyle={{ color: '#faad14' }} prefix={<WarningOutlined />} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="严重" value={stats.health_distribution?.critical || 0} valueStyle={{ color: '#ff4d4f' }} prefix={<FireOutlined />} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="活跃告警" value={stats.firing_alerts} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
          <Col span={4}><Card size="small"><Statistic title="平均健康分" value={stats.avg_health_score || '-'} suffix={stats.avg_health_score ? '/100' : ''} /></Card></Col>
        </Row>
      )}

      {loading ? <Spin size="large" style={{ display: 'block', margin: '60px auto' }} /> :
        entities.length === 0 ? <Empty /> :
        <Table rowKey="guid" dataSource={entities} columns={columns} size="small" pagination={{ pageSize: 20 }}
          onRow={(record) => ({ onClick: () => handleRowClick(record), style: { cursor: 'pointer' } })}
          scroll={{ x: 1400 }}
        />
      }

      <EntityDetailDrawer entity={selected} open={drawerOpen} onClose={() => setDrawerOpen(false)} onEntityClick={handleEntityClick} />
    </div>
  );
};

export default NetworkAnalysis;
