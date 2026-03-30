import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Progress, Table, Tag, Space, Spin, Empty, Tooltip, Segmented } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  FireOutlined,
  BranchesOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API = '/api/v1';
const CMDB = '/api/v1/cmdb';

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a', unknown: '#d9d9d9',
};

const levelEmoji: Record<string, string> = {
  healthy: '🟢', warning: '🟡', critical: '🔴', down: '⛔',
};

const OverviewPage: React.FC = () => {
  const [overview, setOverview] = useState<any>(null);
  const [traceStats, setTraceStats] = useState<any>(null);
  const [topRisks, setTopRisks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ovRes, entRes] = await Promise.all([
        axios.get(`${API}/overview`),
        axios.get(`${CMDB}/entities`, { params: { limit: 100, sort: 'risk_score', order: 'desc' } }),
      ]);
      setOverview(ovRes.data);
      setTopRisks(entRes.data.items || []);

      // trace 统计（通过后端代理或直接查 — 这里用简化的 overview 数据）
      setTraceStats({ spans: 'N/A', traces: 'N/A' });
    } catch (err) {
      console.error('Fetch failed:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); const t = setInterval(fetchData, 30000); return () => clearInterval(t); }, []);

  if (loading && !overview) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!overview) return <Empty description="暂无数据" />;

  const { total_entities = 0, resource_size = {}, health_distribution = {}, anomaly_entities = [], business_health = [] } = overview;
  const hd = { healthy: 0, warning: 0, critical: 0, down: 0, ...health_distribution };
  const totalH = hd.healthy + hd.warning + hd.critical + hd.down;
  const globalScore = totalH > 0 ? Math.round((hd.healthy * 100 + hd.warning * 70 + hd.critical * 30 + hd.down * 0) / totalH) : 100;
  const globalColor = globalScore >= 80 ? '#52c41a' : globalScore >= 60 ? '#faad14' : globalScore >= 30 ? '#ff4d4f' : '#a8071a';

  const riskColumns = [
    {
      title: '实体', dataIndex: 'name', width: 180, ellipsis: true,
      render: (n: string, r: any) => (
        <Space>
          <span>{levelEmoji[r.health_level] || '⚪'}</span>
          <span style={{ fontWeight: 500 }}>{n}</span>
        </Space>
      ),
    },
    { title: '类型', dataIndex: 'type_name', width: 100, render: (t: string) => <Tag color="blue">{t}</Tag> },
    {
      title: '健康度', dataIndex: 'health_score', width: 120, sorter: (a: any, b: any) => (a.health_score || 0) - (b.health_score || 0),
      render: (s: number) => {
        const color = s >= 80 ? '#52c41a' : s >= 60 ? '#faad14' : '#ff4d4f';
        return (
          <Space>
            <Progress percent={s || 0} size="small" strokeColor={color} style={{ width: 60 }} />
            <span style={{ color, fontWeight: 'bold' }}>{s ?? '-'}</span>
          </Space>
        );
      },
    },
    {
      title: '风险度', dataIndex: 'risk_score', width: 120, defaultSortOrder: 'descend' as const,
      sorter: (a: any, b: any) => (a.risk_score || 0) - (b.risk_score || 0),
      render: (s: number) => {
        const v = s || 0;
        const color = v >= 60 ? '#ff4d4f' : v >= 30 ? '#faad14' : '#52c41a';
        const icon = v >= 60 ? <FireOutlined /> : null;
        return <span style={{ color, fontWeight: 'bold', fontSize: 16 }}>{icon} {v}</span>;
      },
    },
    {
      title: '影响范围', width: 120,
      render: (_: any, r: any) => (
        <Tooltip title={`blast_radius: ${r.blast_radius || 0}, propagation_hops: ${r.propagation_hops || 0}`}>
          <Space>
            <BranchesOutlined />
            <span>{r.blast_radius || 0} 实体</span>
            <span style={{ color: '#8c8c8c' }}>{r.propagation_hops || 0} 跳</span>
          </Space>
        </Tooltip>
      ),
    },
    { title: '业务', dataIndex: 'biz_service', width: 120, ellipsis: true },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>📊 全局概览</h2>

      {/* 顶部大数字 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card style={{ borderTop: `3px solid ${globalColor}` }}>
            <Statistic title="全局健康度" value={globalScore} suffix="/ 100"
              valueStyle={{ color: globalColor, fontSize: 36 }} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="实体总数" value={total_entities} prefix={<DatabaseOutlined />} />
            <div style={{ marginTop: 8, color: '#8c8c8c', fontSize: 12 }}>
              {Object.entries(resource_size).map(([k, v]) => `${k}:${v}`).join(' · ')}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card style={{ borderTop: `3px solid ${hd.critical + hd.down > 0 ? '#ff4d4f' : '#52c41a'}` }}>
            <Statistic title="异常实体" value={hd.warning + hd.critical + hd.down}
              valueStyle={{ color: hd.critical + hd.down > 0 ? '#ff4d4f' : '#faad14' }}
              prefix={<WarningOutlined />} />
            <div style={{ marginTop: 4, color: '#8c8c8c', fontSize: 12 }}>
              ⚠️ {hd.warning} 告警 · 🔴 {hd.critical} 严重 · ⛔ {hd.down} 宕机
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="健康分布" value={totalH > 0 ? Math.round(hd.healthy / totalH * 100) : 100} suffix="% 正常"
              valueStyle={{ color: '#52c41a' }} />
            <Progress percent={totalH > 0 ? Math.round(hd.healthy / totalH * 100) : 100}
              strokeColor="#52c41a" size="small" showInfo={false} style={{ marginTop: 4 }} />
          </Card>
        </Col>
      </Row>

      {/* 业务健康度 + 健康分布柱状 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="🏢 业务健康度" size="small">
            {business_health.length === 0 ? <Empty description="无业务数据" /> : (
              <Row gutter={[12, 12]}>
                {business_health.map((biz: any) => {
                  const score = biz.health_score || 0;
                  const color = score >= 80 ? '#52c41a' : score >= 60 ? '#faad14' : '#ff4d4f';
                  return (
                    <Col key={biz.name} span={12}>
                      <Card size="small" style={{ borderLeft: `3px solid ${color}` }}>
                        <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{biz.name}</div>
                        <Progress percent={score} strokeColor={color} format={() => `${score} 分`} />
                        <div style={{ color: '#8c8c8c', fontSize: 12 }}>{biz.resource_count} 个资源</div>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            )}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="📊 健康分布" size="small">
            <Row gutter={[8, 8]} style={{ textAlign: 'center' }}>
              {[
                { label: '健康', key: 'healthy', color: '#52c41a', icon: '🟢' },
                { label: '告警', key: 'warning', color: '#faad14', icon: '🟡' },
                { label: '严重', key: 'critical', color: '#ff4d4f', icon: '🔴' },
                { label: '宕机', key: 'down', color: '#a8071a', icon: '⛔' },
              ].map(item => {
                const count = hd[item.key as keyof typeof hd] || 0;
                const pct = totalH > 0 ? Math.round(count / totalH * 100) : 0;
                return (
                  <Col key={item.key} span={6}>
                    <div style={{ fontSize: 28, fontWeight: 'bold', color: item.color }}>{count}</div>
                    <div style={{ fontSize: 12, color: '#8c8c8c' }}>{item.icon} {item.label}</div>
                    <Progress percent={pct} strokeColor={item.color} size="small" showInfo={false} />
                  </Col>
                );
              })}
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 风险度排行榜 */}
      <Card title={<><FireOutlined style={{ color: '#ff4d4f' }} /> 风险度排行榜</>} size="small" style={{ marginTop: 16 }}
        extra={<span style={{ color: '#8c8c8c', fontSize: 12 }}>按风险度降序 · 风险 = 健康度 × 影响范围</span>}>
        <Table columns={riskColumns} dataSource={topRisks} rowKey="guid" size="small"
          pagination={false} scroll={{ x: 700 }}
          locale={{ emptyText: <Empty description="🎉 无风险实体" /> }} />
      </Card>

      {/* 调用链概览 */}
      <Card title={<><BranchesOutlined /> 调用链场景</>} size="small" style={{ marginTop: 16 }}>
        <Row gutter={[16, 16]}>
          {[
            { name: 'create_order', desc: '用户下单', path: 'gateway → order → payment → db', color: '#ff4d4f' },
            { name: 'user_login', desc: '用户登录', path: 'gateway → user → session-cache', color: '#52c41a' },
            { name: 'query_inventory', desc: '查询库存', path: 'gateway → inventory → order-db', color: '#52c41a' },
            { name: 'check_payment', desc: '查询支付', path: 'gateway → payment → payment-db', color: '#faad14' },
          ].map(chain => (
            <Col key={chain.name} xs={24} sm={12} md={6}>
              <Card size="small" style={{ borderLeft: `3px solid ${chain.color}` }}>
                <div style={{ fontWeight: 'bold' }}>{chain.desc}</div>
                <div style={{ color: '#8c8c8c', fontSize: 12, marginTop: 4, fontFamily: 'monospace' }}>
                  {chain.path}
                </div>
                <Tag color={chain.color} style={{ marginTop: 8 }}>
                  {chain.color === '#ff4d4f' ? '🔴 含故障' : chain.color === '#faad14' ? '🟡 轻微异常' : '🟢 正常'}
                </Tag>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
};

export default OverviewPage;
