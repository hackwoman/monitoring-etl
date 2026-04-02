import React, { useEffect, useState } from 'react';
import {
  Table, Card, Tag, Space, Button, Statistic, Row, Col,
  Modal, message, Tooltip, Typography, Select,
} from 'antd';
import {
  AlertOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  ClockCircleOutlined, StopOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const API = '/api/v1';

interface AlertItem {
  alert_id: string;
  rule_id: string;
  entity_name: string;
  entity_type: string;
  status: string;
  severity: string;
  title: string;
  summary: string;
  fingerprint: string;
  blast_radius: number;
  group_id: string | null;
  starts_at: string;
  ends_at: string | null;
  ack_at: string | null;
  ack_by: string | null;
  created_at: string;
  updated_at: string;
}

interface AlertStats {
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  total_firing: number;
  total_resolved: number;
}

interface AlertRule {
  rule_id: string;
  rule_name: string;
  description: string;
  target_type: string | null;
  condition_type: string;
  severity: string;
  is_enabled: boolean;
}

const severityColor: Record<string, string> = {
  critical: 'red',
  error: 'orange',
  warning: 'gold',
  info: 'blue',
};

const statusIcon: Record<string, React.ReactNode> = {
  firing: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
  resolved: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  acknowledged: <ClockCircleOutlined style={{ color: '#1890ff' }} />,
  silenced: <StopOutlined style={{ color: '#8c8c8c' }} />,
};

const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [activeTab, setActiveTab] = useState<'alerts' | 'rules'>('alerts');

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      params.set('limit', '100');
      const res = await fetch(`${API}/alerts?${params}`);
      const data = await res.json();
      setAlerts(data.items || []);
    } catch (e) {
      console.error('Failed to fetch alerts:', e);
    }
    setLoading(false);
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API}/alerts/stats`);
      const data = await res.json();
      setStats(data);
    } catch (e) {
      console.error('Failed to fetch stats:', e);
    }
  };

  const fetchRules = async () => {
    try {
      const res = await fetch(`${API}/alerts/rules`);
      const data = await res.json();
      setRules(data.items || []);
    } catch (e) {
      console.error('Failed to fetch rules:', e);
    }
  };

  useEffect(() => {
    fetchAlerts();
    fetchStats();
    fetchRules();
    const interval = setInterval(() => {
      fetchAlerts();
      fetchStats();
    }, 30000);
    return () => clearInterval(interval);
  }, [statusFilter]);

  const handleAck = async (alertId: string) => {
    try {
      await fetch(`${API}/alerts/${alertId}/ack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ack_by: 'user' }),
      });
      message.success('告警已确认');
      fetchAlerts();
    } catch {
      message.error('确认失败');
    }
  };

  const handleSilence = async (alertId: string, minutes: number) => {
    try {
      await fetch(`${API}/alerts/${alertId}/silence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_minutes: minutes }),
      });
      message.success(`告警已静默 ${minutes} 分钟`);
      fetchAlerts();
    } catch {
      message.error('静默失败');
    }
  };

  const alertColumns = [
    {
      title: '状态',
      dataIndex: 'status',
      width: 60,
      render: (status: string) => (
        <Tooltip title={status}>
          {statusIcon[status] || status}
        </Tooltip>
      ),
    },
    {
      title: '严重度',
      dataIndex: 'severity',
      width: 80,
      render: (sev: string) => (
        <Tag color={severityColor[sev] || 'default'}>{sev}</Tag>
      ),
    },
    {
      title: '告警标题',
      dataIndex: 'title',
      ellipsis: true,
    },
    {
      title: '实体',
      dataIndex: 'entity_name',
      width: 140,
      render: (name: string, record: AlertItem) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{record.entity_type}</Text>
        </Space>
      ),
    },
    {
      title: '影响范围',
      dataIndex: 'blast_radius',
      width: 80,
      render: (br: number) => br > 0 ? <Tag color="red">{br} 实体</Tag> : '-',
    },
    {
      title: '触发时间',
      dataIndex: 'starts_at',
      width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      width: 180,
      render: (_: any, record: AlertItem) => (
        <Space>
          {record.status === 'firing' && (
            <>
              <Button size="small" onClick={() => handleAck(record.alert_id)}>确认</Button>
              <Button size="small" onClick={() => handleSilence(record.alert_id, 60)}>静默1h</Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  const ruleColumns = [
    { title: '规则名', dataIndex: 'rule_name' },
    { title: '类型', dataIndex: 'condition_type', width: 100 },
    { title: '目标', dataIndex: 'target_type', width: 100, render: (v: string) => v || '全部' },
    {
      title: '严重度',
      dataIndex: 'severity',
      width: 80,
      render: (sev: string) => <Tag color={severityColor[sev]}>{sev}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      width: 80,
      render: (enabled: boolean) => (
        <Tag color={enabled ? 'green' : 'default'}>{enabled ? '启用' : '禁用'}</Tag>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}><AlertOutlined /> 统一告警中心</Title>

      {/* 统计卡片 */}
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="活跃告警"
                value={stats.total_firing}
                valueStyle={{ color: '#ff4d4f' }}
                prefix={<ExclamationCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="已恢复"
                value={stats.total_resolved}
                valueStyle={{ color: '#52c41a' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Critical"
                value={stats.by_severity?.critical || 0}
                valueStyle={{ color: '#ff4d4f' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Error"
                value={stats.by_severity?.error || 0}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Tab 切换 */}
      <Space style={{ marginBottom: 16 }}>
        <Button
          type={activeTab === 'alerts' ? 'primary' : 'default'}
          onClick={() => setActiveTab('alerts')}
        >
          告警列表
        </Button>
        <Button
          type={activeTab === 'rules' ? 'primary' : 'default'}
          onClick={() => setActiveTab('rules')}
        >
          告警规则
        </Button>
        {activeTab === 'alerts' && (
          <Select
            placeholder="筛选状态"
            allowClear
            style={{ width: 120 }}
            onChange={(v) => setStatusFilter(v)}
            options={[
              { label: '🔥 Firing', value: 'firing' },
              { label: '✅ Resolved', value: 'resolved' },
              { label: '🔇 Silenced', value: 'silenced' },
              { label: '👀 Acknowledged', value: 'acknowledged' },
            ]}
          />
        )}
        <Button onClick={() => { fetchAlerts(); fetchStats(); }}>刷新</Button>
      </Space>

      {activeTab === 'alerts' ? (
        <Table
          rowKey="alert_id"
          columns={alertColumns}
          dataSource={alerts}
          loading={loading}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      ) : (
        <Table
          rowKey="rule_id"
          columns={ruleColumns}
          dataSource={rules}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      )}
    </div>
  );
};

export default AlertsPage;
