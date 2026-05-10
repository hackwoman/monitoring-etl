import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Statistic, Button, List, Tag, Space, Spin, Empty,
  Progress, Typography, Avatar, Divider, Steps, Tooltip, Badge,
} from 'antd';
import {
  CheckCircleOutlined, WarningOutlined, CloseCircleOutlined,
  ThunderboltOutlined, DatabaseOutlined, CloudServerOutlined,
  AlertOutlined, ClusterOutlined,
  ToolOutlined, BarChartOutlined, RocketOutlined, ArrowUpOutlined,
  RightOutlined, BulbOutlined,
  SafetyCertificateOutlined,
  ClockCircleOutlined, SyncOutlined, EyeOutlined, FundOutlined,
} from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';

const { Title, Text, Paragraph } = Typography;

const API = '/api/v1';
const CMDB = '/api/v1/cmdb';

const healthColors: Record<string, string> = {
  healthy: '#52c41a', warning: '#faad14', critical: '#ff4d4f', down: '#a8071a', unknown: '#d9d9d9',
};

const levelEmoji: Record<string, string> = {
  healthy: '🟢', warning: '🟡', critical: '🔴', down: '⛔',
};

const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<any>(null);
  const [entities, setEntities] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ovRes, entRes] = await Promise.allSettled([
        axios.get(`${API}/overview`),
        axios.get(`${CMDB}/entities`, { params: { limit: 5, sort: 'updated_at', order: 'desc' } }),
      ]);

      if (ovRes.status === 'fulfilled') setOverview(ovRes.value?.data || {});
      if (entRes.status === 'fulfilled') setEntities(entRes.value?.data?.items || []);
    } catch (err) {
      console.error('Fetch failed:', err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    const t = setInterval(fetchData, 30000);
    return () => clearInterval(t);
  }, []);

  // 计算统计数据
  const totalEntities = overview?.total_entities || 0;
  const healthDist = overview?.health_distribution || {};
  const activeAlerts = (healthDist.warning || 0) + (healthDist.critical || 0) + (healthDist.down || 0);
  const dataSources = overview?.resource_size ? Object.keys(overview.resource_size).length : 0;
  const totalH = (healthDist.healthy || 0) + (healthDist.warning || 0) + (healthDist.critical || 0) + (healthDist.down || 0);
  const healthScore = totalH > 0 ? Math.round(((healthDist.healthy || 0) * 100 + (healthDist.warning || 0) * 70 + (healthDist.critical || 0) * 30) / totalH) : 100;
  const healthColor = healthScore >= 80 ? '#52c41a' : healthScore >= 60 ? '#faad14' : healthScore >= 30 ? '#ff4d4f' : '#a8071a';

  // 快速操作配置
  const quickActions = [
    { title: '查看拓扑', desc: '查看服务依赖关系', icon: <ClusterOutlined />, path: '/topology', color: '#1890ff' },
    { title: '查看告警', desc: '管理活跃告警', icon: <AlertOutlined />, path: '/alerts', color: '#ff4d4f' },
    { title: '接入数据源', desc: '配置ETL数据采集', icon: <ToolOutlined />, path: '/etl', color: '#52c41a' },
    { title: '管理CMDB', desc: '查看配置数据库', icon: <DatabaseOutlined />, path: '/cmdb', color: '#722ed1' },
  ];

  // 新手引导步骤
  const guideSteps = [
    { title: '接入数据源', description: '配置ETL任务，从各数据源采集监控数据', path: '/etl', icon: <ToolOutlined /> },
    { title: '查看拓扑', description: '了解服务间的依赖关系和调用链路', path: '/topology', icon: <ClusterOutlined /> },
    { title: '配置告警', description: '设置告警规则，及时发现异常', path: '/alerts', icon: <AlertOutlined /> },
    { title: '查看指标', description: '浏览各项监控指标和趋势', path: '/metric-browser', icon: <BarChartOutlined /> },
  ];

  if (loading && !overview) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666666' }}>加载中...</div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0, color: '#333333' }}>
          <FundOutlined style={{ marginRight: 8 }} />
          系统总览
        </Title>
        <Text style={{ color: '#666666' }}>
          实时监控系统健康状态，快速访问常用功能
        </Text>
      </div>

      {/* 新手引导卡片 */}
      {showGuide && (
        <Card
          style={{
            marginBottom: 24,
            background: '#ffffff',
            border: '1px solid #e8e8e8',
          }}
          extra={
            <Button type="text" size="small" onClick={() => setShowGuide(false)} style={{ color: '#666666' }}>
              关闭引导
            </Button>
          }
        >
          <Space align="center" style={{ marginBottom: 16 }}>
            <BulbOutlined style={{ color: '#faad14', fontSize: 20 }} />
            <Text strong style={{ color: '#333333', fontSize: 16 }}>快速开始</Text>
          </Space>
          <Paragraph style={{ color: '#666666', marginBottom: 16 }}>
            按照以下步骤快速上手监控平台：
          </Paragraph>
          <Steps
            current={-1}
            direction="horizontal"
            size="small"
            items={guideSteps.map((step, index) => ({
              title: (
                <Link to={step.path} style={{ color: '#1890ff' }}>
                  {step.title}
                </Link>
              ),
              description: step.description,
              icon: React.cloneElement(step.icon as React.ReactElement, {
                style: { color: '#1890ff' }
              }),
            }))}
          />
        </Card>
      )}

      {/* 顶部：系统健康状态卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            style={{
              background: '#ffffff',
              border: '1px solid #e8e8e8',
            }}
          >
            <Statistic
              title={<span style={{ color: '#666666' }}>实体总数</span>}
              value={totalEntities}
              prefix={<DatabaseOutlined style={{ color: '#1890ff' }} />}
              valueStyle={{ color: '#333333', fontSize: 32 }}
            />
            <div style={{ marginTop: 8, color: '#52c41a', fontSize: 12 }}>
              <ArrowUpOutlined /> 系统运行中
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            style={{
              background: '#ffffff',
              border: `1px solid ${activeAlerts > 0 ? '#ff4d4f' : '#304156'}`,
            }}
          >
            <Statistic
              title={<span style={{ color: '#666666' }}>活跃告警</span>}
              value={activeAlerts}
              prefix={<AlertOutlined style={{ color: activeAlerts > 0 ? '#ff4d4f' : '#52c41a' }} />}
              valueStyle={{ color: activeAlerts > 0 ? '#ff4d4f' : '#52c41a', fontSize: 32 }}
            />
            <div style={{ marginTop: 8, color: '#666666', fontSize: 12 }}>
              {activeAlerts > 0 ? (
                <><WarningOutlined style={{ color: '#faad14' }} /> 需要关注</>
              ) : (
                <><CheckCircleOutlined style={{ color: '#52c41a' }} /> 一切正常</>
              )}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            style={{
              background: '#ffffff',
              border: '1px solid #e8e8e8',
            }}
          >
            <Statistic
              title={<span style={{ color: '#666666' }}>数据源数</span>}
              value={dataSources}
              prefix={<CloudServerOutlined style={{ color: '#722ed1' }} />}
              valueStyle={{ color: '#333333', fontSize: 32 }}
            />
            <div style={{ marginTop: 8, color: '#666666', fontSize: 12 }}>
              <SyncOutlined spin={loading} /> 实时同步中
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            style={{
              background: '#ffffff',
              border: `1px solid ${healthColor}`,
            }}
          >
            <Statistic
              title={<span style={{ color: '#666666' }}>系统健康度</span>}
              value={healthScore}
              suffix="/ 100"
              prefix={<ThunderboltOutlined style={{ color: healthColor }} />}
              valueStyle={{ color: healthColor, fontSize: 32 }}
            />
            <Progress
              percent={healthScore}
              strokeColor={healthColor}
              size="small"
              showInfo={false}
              style={{ marginTop: 8 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 中部：快速操作区 */}
      <Card
        title={
          <Space>
            <RocketOutlined style={{ color: '#1890ff' }} />
            <span style={{ color: '#333333' }}>快速操作</span>
          </Space>
        }
        style={{
          marginBottom: 24,
          background: '#ffffff',
          border: '1px solid #e8e8e8',
        }}
      >
        <Row gutter={[16, 16]}>
          {quickActions.map((action) => (
            <Col xs={24} sm={12} md={6} key={action.path}>
              <Button
                block
                size="large"
                onClick={() => navigate(action.path)}
                style={{
                  height: 80,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(255,255,255,0.05)',
                  border: `1px solid ${action.color}33`,
                  borderRadius: 8,
                }}
              >
                <div style={{ fontSize: 24, color: action.color, marginBottom: 4 }}>
                  {action.icon}
                </div>
                <div style={{ color: '#333333', fontWeight: 500 }}>{action.title}</div>
                <div style={{ color: '#666666', fontSize: 12 }}>{action.desc}</div>
              </Button>
            </Col>
          ))}
        </Row>
      </Card>

      {/* 下部：最近活动 */}
      <Row gutter={[16, 16]}>
        {/* 最近发现的实体 */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <EyeOutlined style={{ color: '#1890ff' }} />
                <span style={{ color: '#333333' }}>最近发现的实体</span>
              </Space>
            }
            style={{
              background: '#ffffff',
              border: '1px solid #e8e8e8',
              height: '100%',
            }}
            extra={
              <Link to="/cmdb" style={{ color: '#1890ff', fontSize: 12 }}>
                查看全部 <RightOutlined />
              </Link>
            }
          >
            {entities.length === 0 ? (
              <Empty
                description={
                  <span style={{ color: '#666666' }}>
                    暂无实体数据，请先接入数据源
                  </span>
                }
              >
                <Link to="/etl">
                  <Button type="primary" size="small">
                    <ToolOutlined /> 接入数据源
                  </Button>
                </Link>
              </Empty>
            ) : (
              <List
                dataSource={entities}
                renderItem={(item: any) => (
                  <List.Item
                    style={{ borderBottom: '1px solid #304156', padding: '8px 0' }}
                  >
                    <List.Item.Meta
                      avatar={
                        <Avatar
                          size="small"
                          style={{
                            backgroundColor: healthColors[item.health_level] || '#d9d9d9',
                          }}
                          icon={
                            item.health_level === 'healthy' ? <CheckCircleOutlined /> :
                            item.health_level === 'warning' ? <WarningOutlined /> :
                            item.health_level === 'critical' ? <CloseCircleOutlined /> :
                            <CloudServerOutlined />
                          }
                        />
                      }
                      title={
                        <Text style={{ color: '#333333' }} ellipsis>
                          {levelEmoji[item.health_level] || '⚪'} {item.name}
                        </Text>
                      }
                      description={
                        <Space size={4}>
                          <Tag color="blue" style={{ fontSize: 11 }}>{item.type_name}</Tag>
                          <Text style={{ color: '#666666', fontSize: 11 }}>
                            健康度: {item.health_score ?? '-'}
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* 最近的告警 */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <AlertOutlined style={{ color: '#ff4d4f' }} />
                <span style={{ color: '#333333' }}>最近的告警</span>
                {activeAlerts > 0 && (
                  <Badge count={activeAlerts} style={{ backgroundColor: '#ff4d4f' }} />
                )}
              </Space>
            }
            style={{
              background: '#ffffff',
              border: '1px solid #e8e8e8',
              height: '100%',
            }}
            extra={
              <Link to="/alerts" style={{ color: '#1890ff', fontSize: 12 }}>
                查看全部 <RightOutlined />
              </Link>
            }
          >
            {alerts.length === 0 ? (
              <Empty
                description={
                  <span style={{ color: '#666666' }}>
                    暂无告警，系统运行正常
                  </span>
                }
              >
                <CheckCircleOutlined style={{ fontSize: 32, color: '#52c41a' }} />
              </Empty>
            ) : (
              <List
                dataSource={alerts}
                renderItem={(item: any) => (
                  <List.Item
                    style={{ borderBottom: '1px solid #304156', padding: '8px 0' }}
                  >
                    <List.Item.Meta
                      avatar={
                        <Avatar
                          size="small"
                          style={{
                            backgroundColor: item.level === 'critical' ? '#ff4d4f' :
                              item.level === 'warning' ? '#faad14' : '#1890ff',
                          }}
                          icon={
                            item.level === 'critical' ? <CloseCircleOutlined /> :
                            item.level === 'warning' ? <WarningOutlined /> :
                            <AlertOutlined />
                          }
                        />
                      }
                      title={
                        <Text style={{ color: '#333333' }} ellipsis>
                          {item.title || item.name || '告警'}
                        </Text>
                      }
                      description={
                        <Space size={4}>
                          <Tag
                            color={item.level === 'critical' ? 'red' :
                              item.level === 'warning' ? 'orange' : 'blue'}
                            style={{ fontSize: 11 }}
                          >
                            {item.level || 'info'}
                          </Tag>
                          <Text style={{ color: '#666666', fontSize: 11 }}>
                            <ClockCircleOutlined /> {item.created_at ? new Date(item.created_at).toLocaleString() : '-'}
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 系统状态摘要 */}
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined style={{ color: '#52c41a' }} />
            <span style={{ color: '#333333' }}>系统状态摘要</span>
          </Space>
        }
        style={{
          marginTop: 16,
          background: '#ffffff',
          border: '1px solid #e8e8e8',
        }}
      >
        <Row gutter={[24, 16]}>
          <Col xs={24} sm={8}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: '#52c41a' }}>
                {healthDist.healthy || 0}
              </div>
              <div style={{ color: '#666666', fontSize: 12 }}>🟢 健康实体</div>
            </div>
          </Col>
          <Col xs={24} sm={8}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: '#faad14' }}>
                {healthDist.warning || 0}
              </div>
              <div style={{ color: '#666666', fontSize: 12 }}>🟡 告警实体</div>
            </div>
          </Col>
          <Col xs={24} sm={8}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: '#ff4d4f' }}>
                {(healthDist.critical || 0) + (healthDist.down || 0)}
              </div>
              <div style={{ color: '#666666', fontSize: 12 }}>🔴 异常/宕机</div>
            </div>
          </Col>
        </Row>
        <Divider style={{ borderColor: '#304156', margin: '16px 0' }} />
        <div style={{ textAlign: 'center', color: '#666666', fontSize: 12 }}>
          数据每30秒自动刷新 · 上次更新: {new Date().toLocaleTimeString()}
        </div>
      </Card>
    </div>
  );
};

export default OverviewPage;
