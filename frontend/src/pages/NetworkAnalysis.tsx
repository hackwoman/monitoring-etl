import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Space, Spin, Empty } from 'antd';
import { CloudServerOutlined, CheckCircleOutlined, WarningOutlined, FireOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import EntityDetailDrawer, { DrawerEntity as Entity } from '../components/EntityDetailDrawer';

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

  const columns = [
    { title: '设备名', dataIndex: 'name', sorter: (a: Entity, b: Entity) => a.name.localeCompare(b.name), render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { title: '厂商', key: 'vendor', render: (_: any, r: Entity) => r.attributes?.vendor || '-' },
    { title: '型号', key: 'model', render: (_: any, r: Entity) => r.attributes?.model || '-' },
    { title: '管理IP', key: 'mgmt_ip', render: (_: any, r: Entity) => r.attributes?.mgmt_ip || '-' },
    { title: '健康度', dataIndex: 'health_score', sorter: (a: Entity, b: Entity) => (a.health_score || 0) - (b.health_score || 0),
      render: (_: any, r: Entity) => (
        <Space>
          <span style={{ color: healthColors[r.health_level], fontWeight: 600 }}>{r.health_score ?? '?'}</span>
          <Tag color={healthColors[r.health_level]}>{r.health_level}</Tag>
        </Space>
      )
    },
    { title: '标签', dataIndex: 'labels', render: (labels: Record<string, string>) => (
      <Space wrap>{Object.entries(labels || {}).map(([k, v]) => <Tag key={k}>{k}:{v}</Tag>)}</Space>
    )},
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}><CloudServerOutlined style={{ marginRight: 8 }} />网络分析</h2>

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
        />
      }

      <EntityDetailDrawer entity={selected} open={drawerOpen} onClose={() => setDrawerOpen(false)} onEntityClick={handleEntityClick} />
    </div>
  );
};

export default NetworkAnalysis;
