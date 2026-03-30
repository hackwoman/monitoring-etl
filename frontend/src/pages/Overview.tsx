import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Progress, Table, Tag, Space, Spin, Empty } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1';

const healthColors: Record<string, string> = {
  healthy: '#52c41a',
  warning: '#faad14',
  critical: '#ff4d4f',
  down: '#a8071a',
  unknown: '#d9d9d9',
};

const healthIcons: Record<string, React.ReactNode> = {
  healthy: <CheckCircleOutlined style={{ color: healthColors.healthy }} />,
  warning: <WarningOutlined style={{ color: healthColors.warning }} />,
  critical: <CloseCircleOutlined style={{ color: healthColors.critical }} />,
  down: <CloseCircleOutlined style={{ color: healthColors.down }} />,
};

const OverviewPage: React.FC = () => {
  const [overview, setOverview] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchOverview = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/overview`);
      setOverview(res.data);
    } catch (err) {
      console.error('Fetch overview failed:', err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchOverview();
    const timer = setInterval(fetchOverview, 30000); // 30s 刷新
    return () => clearInterval(timer);
  }, []);

  if (loading && !overview) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (!overview) {
    return <Empty description="暂无数据" />;
  }

  const {
    total_entities = 0,
    resource_size = {},
    health_distribution = {},
    anomaly_entities = [],
    business_health = [],
  } = overview;

  // 计算全局健康度
  const healthyCount = health_distribution.healthy || 0;
  const warningCount = health_distribution.warning || 0;
  const criticalCount = health_distribution.critical || 0;
  const downCount = health_distribution.down || 0;
  const totalHealth = healthyCount + warningCount + criticalCount + downCount;
  const globalScore = totalHealth > 0
    ? Math.round((healthyCount * 100 + warningCount * 70 + criticalCount * 30 + downCount * 0) / totalHealth)
    : 100;

  // 健康分布百分比
  const healthPercent = totalHealth > 0 ? {
    healthy: Math.round(healthyCount / totalHealth * 100),
    warning: Math.round(warningCount / totalHealth * 100),
    critical: Math.round(criticalCount / totalHealth * 100),
    down: Math.round(downCount / totalHealth * 100),
  } : { healthy: 100, warning: 0, critical: 0, down: 0 };

  const globalColor = globalScore >= 80 ? healthColors.healthy
    : globalScore >= 60 ? healthColors.warning
    : globalScore >= 30 ? healthColors.critical
    : healthColors.down;

  const anomalyColumns = [
    { title: '名称', dataIndex: 'name', width: 200, ellipsis: true },
    {
      title: '类型', dataIndex: 'type_name', width: 120,
      render: (t: string) => <Tag color="blue">{t}</Tag>,
    },
    {
      title: '健康度', dataIndex: 'health_score', width: 100,
      render: (s: number) => (
        <span style={{ color: s < 60 ? '#ff4d4f' : s < 80 ? '#faad14' : '#52c41a', fontWeight: 'bold' }}>
          {s ?? '-'}
        </span>
      ),
    },
    {
      title: '状态', dataIndex: 'health_level', width: 100,
      render: (l: string) => (
        <Tag color={l === 'critical' || l === 'down' ? 'red' : l === 'warning' ? 'orange' : 'green'}>
          {healthIcons[l]} {l}
        </Tag>
      ),
    },
    {
      title: '风险度', dataIndex: 'risk_score', width: 100,
      render: (s: number) => s != null ? (
        <span style={{ color: s > 70 ? '#ff4d4f' : s > 40 ? '#faad14' : '#52c41a' }}>{s}</span>
      ) : '-',
    },
    { title: '业务', dataIndex: 'biz_service', width: 150, ellipsis: true },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>📊 全局概览</h2>

      {/* 顶部指标卡 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="全局健康度"
              value={globalScore}
              suffix="/ 100"
              valueStyle={{ color: globalColor, fontSize: 36 }}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="实体总数"
              value={total_entities}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="异常实体"
              value={warningCount + criticalCount + downCount}
              valueStyle={{ color: (warningCount + criticalCount + downCount) > 0 ? '#ff4d4f' : '#52c41a' }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="资源类型"
              value={Object.keys(resource_size).length}
              prefix={<CloudServerOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 健康分布 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="💚 健康分布" size="small">
            <Row gutter={[8, 8]}>
              <Col span={6} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: healthColors.healthy }}>{healthyCount}</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>健康</div>
                <Progress percent={healthPercent.healthy} strokeColor={healthColors.healthy} size="small" showInfo={false} />
              </Col>
              <Col span={6} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: healthColors.warning }}>{warningCount}</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>告警</div>
                <Progress percent={healthPercent.warning} strokeColor={healthColors.warning} size="small" showInfo={false} />
              </Col>
              <Col span={6} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: healthColors.critical }}>{criticalCount}</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>严重</div>
                <Progress percent={healthPercent.critical} strokeColor={healthColors.critical} size="small" showInfo={false} />
              </Col>
              <Col span={6} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: healthColors.down }}>{downCount}</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>宕机</div>
                <Progress percent={healthPercent.down} strokeColor={healthColors.down} size="small" showInfo={false} />
              </Col>
            </Row>
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card title="📦 资源规模" size="small">
            <Row gutter={[8, 8]}>
              {Object.entries(resource_size).map(([type, count]) => (
                <Col key={type} span={8}>
                  <Card size="small" style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold' }}>{count as number}</div>
                    <Tag color="blue">{type}</Tag>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 业务健康度 */}
      {business_health.length > 0 && (
        <Card title="🏢 业务健康度" size="small" style={{ marginTop: 16 }}>
          <Row gutter={[16, 16]}>
            {business_health.map((biz: any) => {
              const score = biz.health_score || 0;
              const color = score >= 80 ? healthColors.healthy : score >= 60 ? healthColors.warning : healthColors.critical;
              return (
                <Col key={biz.name} xs={24} sm={12} md={8}>
                  <Card size="small">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <div style={{ fontWeight: 'bold' }}>{biz.name}</div>
                      <Progress
                        percent={score}
                        strokeColor={color}
                        format={() => `${score} 分`}
                      />
                      <div style={{ color: '#8c8c8c', fontSize: 12 }}>
                        {biz.resource_count} 个资源
                      </div>
                    </Space>
                  </Card>
                </Col>
              );
            })}
          </Row>
        </Card>
      )}

      {/* 异常实体 */}
      <Card title="🚨 异常实体 Top 10" size="small" style={{ marginTop: 16 }}>
        <Table
          columns={anomalyColumns}
          dataSource={anomaly_entities}
          rowKey="guid"
          size="small"
          pagination={false}
          locale={{ emptyText: <Empty description="🎉 无异常实体" /> }}
        />
      </Card>
    </div>
  );
};

export default OverviewPage;
