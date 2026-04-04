import React, { useEffect, useState } from 'react';
import {
  Table, Card, Tag, Space, Button, Statistic, Row, Col,
  Modal, message, Tooltip, Typography, Select, Form, Input,
  InputNumber, Switch
} from 'antd';
import {
  AlertOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  ClockCircleOutlined, StopOutlined, PlusOutlined, EditOutlined,
  DeleteOutlined, ExperimentOutlined
} from '@ant-design/icons';
import { TimeRangeBar } from '../components/TimeRangeContext';

const { Title, Text } = Typography;
const { TextArea } = Input;
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
  
  // 规则管理状态
  const [ruleModalVisible, setRuleModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [testingRule, setTestingRule] = useState<AlertRule | null>(null);
  const [form] = Form.useForm();
  const [testForm] = Form.useForm();

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

  // 规则管理函数
  const openCreateRule = () => {
    setEditingRule(null);
    form.resetFields();
    form.setFieldsValue({
      condition_type: 'threshold',
      severity: 'warning',
      eval_interval: 60,
      eval_window: 300,
      for_duration: 0,
    });
    setRuleModalVisible(true);
  };

  const openEditRule = (rule: AlertRule) => {
    setEditingRule(rule);
    form.setFieldsValue({
      rule_name: rule.rule_name,
      description: rule.description,
      target_type: rule.target_type,
      condition_type: rule.condition_type,
      severity: rule.severity,
      is_enabled: rule.is_enabled,
    });
    setRuleModalVisible(true);
  };

  const handleSaveRule = async () => {
    try {
      const values = await form.validateFields();
      const url = editingRule 
        ? `${API}/alerts/rules/${editingRule.rule_id}`
        : `${API}/alerts/rules`;
      const method = editingRule ? 'PUT' : 'POST';

      const body = {
        ...values,
        condition_expr: values.condition_expr || { metric: 'cpu', op: '>', threshold: 80 }
      };

      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      message.success(editingRule ? '规则已更新' : '规则已创建');
      setRuleModalVisible(false);
      fetchRules();
    } catch (e) {
      message.error('保存失败');
    }
  };

  const handleDeleteRule = (rule: AlertRule) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除规则 "${rule.rule_name}" 吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await fetch(`${API}/alerts/rules/${rule.rule_id}`, { method: 'DELETE' });
          message.success('规则已删除');
          fetchRules();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const handleToggleRule = async (rule: AlertRule, enabled: boolean) => {
    try {
      await fetch(`${API}/alerts/rules/${rule.rule_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_enabled: enabled }),
      });
      message.success(enabled ? '规则已启用' : '规则已禁用');
      fetchRules();
    } catch {
      message.error('操作失败');
    }
  };

  const openTestRule = (rule: AlertRule) => {
    setTestingRule(rule);
    testForm.resetFields();
    setTestModalVisible(true);
  };

  const handleTestRule = async () => {
    try {
      const values = await testForm.validateFields();
      const testData = {
        rule_id: testingRule?.rule_id,
        test_data: {
          metric: values.metric || 'cpu',
          value: values.value || 90,
          labels: { instance: 'test-host-01', job: 'node-exporter' }
        }
      };

      const res = await fetch(`${API}/alerts/rules/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testData),
      });
      const result = await res.json();
      
      Modal.success({
        title: '测试结果',
        content: (
          <div>
            <p><strong>规则:</strong> {testingRule?.rule_name}</p>
            <p><strong>测试指标:</strong> {values.metric} = {values.value}</p>
            <p><strong>触发结果:</strong> {result.triggered ? '✅ 触发' : '❌ 未触发'}</p>
            {result.message && <p><strong>说明:</strong> {result.message}</p>}
          </div>
        ),
      });
    } catch {
      message.error('测试失败');
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
      width: 100,
      render: (enabled: boolean, record: AlertRule) => (
        <Switch
          checked={enabled}
          onChange={(checked) => handleToggleRule(record, checked)}
          checkedChildren="启用"
          unCheckedChildren="禁用"
        />
      ),
    },
    {
      title: '操作',
      width: 200,
      render: (_: any, record: AlertRule) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditRule(record)}>编辑</Button>
          <Button size="small" icon={<ExperimentOutlined />} onClick={() => openTestRule(record)}>测试</Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteRule(record)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}><AlertOutlined /> 统一告警中心</Title>
      <TimeRangeBar onQuery={() => { fetchAlerts(); fetchStats(); }} />

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
        <>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateRule}>
              新建规则
            </Button>
          </div>
          <Table
            rowKey="rule_id"
            columns={ruleColumns}
            dataSource={rules}
            pagination={{ pageSize: 20 }}
            size="small"
          />
        </>
      )}

      {/* 规则编辑/创建弹窗 */}
      <Modal
        title={editingRule ? '编辑告警规则' : '新建告警规则'}
        open={ruleModalVisible}
        onOk={handleSaveRule}
        onCancel={() => setRuleModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="rule_name" label="规则名称" rules={[{ required: true, message: '请输入规则名称' }]}>
            <Input placeholder="例如: CPU 使用率过高" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="规则描述（可选）" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="condition_type" label="条件类型" rules={[{ required: true }]}>
                <Select options={[
                  { label: '阈值 (threshold)', value: 'threshold' },
                  { label: '变化率 (rate)', value: 'rate' },
                  { label: '异常检测 (anomaly)', value: 'anomaly' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="target_type" label="目标实体类型">
                <Select allowClear placeholder="全部" options={[
                  { label: 'Host', value: 'Host' },
                  { label: 'Service', value: 'Service' },
                  { label: 'Database', value: 'Database' },
                  { label: 'Redis', value: 'Redis' },
                ]} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="severity" label="严重度" rules={[{ required: true }]}>
                <Select options={[
                  { label: 'Critical', value: 'critical' },
                  { label: 'Error', value: 'error' },
                  { label: 'Warning', value: 'warning' },
                  { label: 'Info', value: 'info' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="eval_interval" label="评估间隔（秒）">
                <InputNumber min={10} max={3600} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="is_enabled" label="启用" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 规则测试弹窗 */}
      <Modal
        title={`测试规则: ${testingRule?.rule_name}`}
        open={testModalVisible}
        onOk={handleTestRule}
        onCancel={() => setTestModalVisible(false)}
        okText="执行测试"
      >
        <Form form={testForm} layout="vertical">
          <Form.Item name="metric" label="测试指标" initialValue="cpu">
            <Select options={[
              { label: 'CPU 使用率', value: 'cpu' },
              { label: '内存使用率', value: 'memory' },
              { label: '磁盘使用率', value: 'disk' },
              { label: 'HTTP 延迟 P99', value: 'http.latency.p99' },
              { label: '错误率', value: 'error_rate' },
            ]} />
          </Form.Item>
          <Form.Item name="value" label="测试值" initialValue={90}>
            <InputNumber min={0} max={10000} style={{ width: '100%' }} />
          </Form.Item>
          <Text type="secondary">输入测试数据，预览规则是否触发</Text>
        </Form>
      </Modal>
    </div>
  );
};

export default AlertsPage;
