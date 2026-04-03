import React, { useState, useEffect } from 'react';
import { Table, Tag, Button, Modal, Form, Input, Select, Space, Switch, Card, Row, Col, message } from 'antd';
import { PlusOutlined, ExperimentOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import axios from 'axios';

const API = '/api/v1/cmdb/business-mappings';

const BizMappingPage: React.FC = () => {
  const [mappings, setMappings] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [testOpen, setTestOpen] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [form] = Form.useForm();
  const [testForm] = Form.useForm();

  const fetchMappings = async () => {
    setLoading(true);
    try {
      const res = await axios.get(API);
      setMappings(res.data.items || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { fetchMappings(); }, []);

  const handleSave = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await axios.put(`${API}/${editing.mapping_id}`, values);
        message.success('更新成功');
      } else {
        await axios.post(API, values);
        message.success('创建成功');
      }
      setModalOpen(false);
      setEditing(null);
      form.resetFields();
      fetchMappings();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    Modal.confirm({
      title: '确认删除？',
      onOk: async () => {
        await axios.delete(`${API}/${id}`);
        message.success('已删除');
        fetchMappings();
      }
    });
  };

  const handleTest = async () => {
    const values = await testForm.validateFields();
    try {
      const res = await axios.post(`${API}/test`, values);
      setTestResult(res.data);
    } catch (e) { message.error('测试失败'); }
  };

  const columns = [
    { title: 'URL 模式', dataIndex: 'url_pattern', width: 180,
      render: (v: string) => <code style={{ fontSize: 12 }}>{v}</code> },
    { title: '方法', dataIndex: 'http_method', width: 70,
      render: (v: string) => v ? <Tag>{v}</Tag> : <Tag color="default">ALL</Tag> },
    { title: '业务域', dataIndex: 'business_domain', width: 90,
      render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: '业务动作', dataIndex: 'business_action', width: 90 },
    { title: '业务服务', dataIndex: 'biz_service', width: 100 },
    { title: '优先级', dataIndex: 'priority', width: 70, sorter: (a: any, b: any) => a.priority - b.priority },
    { title: '启用', dataIndex: 'enabled', width: 60,
      render: (v: boolean) => v ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag> },
    { title: '说明', dataIndex: 'description', ellipsis: true },
    { title: '操作', width: 120,
      render: (_: any, r: any) => (
        <Space size={4}>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => {
            setEditing(r);
            form.setFieldsValue(r);
            setModalOpen(true);
          }}>编辑</Button>
          <Button size="small" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.mapping_id)}>删除</Button>
        </Space>
      )
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>🏷️ 业务映射管理</h2>
      <div style={{ marginBottom: 12, padding: '8px 12px', background: '#f6f8fa', borderRadius: 6, fontSize: 12, color: '#595959' }}>
        URL 模式自动映射到业务标签。支持 <code>*</code> 通配符，按优先级匹配。
        HttpRequest 实体创建时自动根据 URL 匹配业务域/业务动作/业务服务。
      </div>

      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null);
          form.resetFields();
          setModalOpen(true);
        }}>新建规则</Button>
        <Button icon={<ExperimentOutlined />} onClick={() => setTestOpen(true)}>测试匹配</Button>
      </Space>

      <Table columns={columns} dataSource={mappings} rowKey="mapping_id" loading={loading} size="small" pagination={{ pageSize: 20 }} />

      {/* 编辑/新建 */}
      <Modal title={editing ? '编辑规则' : '新建规则'} open={modalOpen} onOk={handleSave} onCancel={() => { setModalOpen(false); setEditing(null); }} width={520}>
        <Form form={form} layout="vertical">
          <Row gutter={12}>
            <Col span={16}>
              <Form.Item name="url_pattern" label="URL 模式" rules={[{ required: true }]} tooltip="支持 * 通配符，如 /api/pay/*">
                <Input placeholder="/api/pay/*" style={{ fontFamily: 'monospace' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="http_method" label="HTTP 方法">
                <Select placeholder="所有" allowClear options={[
                  { label: 'GET', value: 'GET' }, { label: 'POST', value: 'POST' },
                  { label: 'PUT', value: 'PUT' }, { label: 'DELETE', value: 'DELETE' },
                ]} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="business_domain" label="业务域" rules={[{ required: true }]}>
                <Input placeholder="交易/用户/库存" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="business_action" label="业务动作" rules={[{ required: true }]}>
                <Input placeholder="下单/支付/查询" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="biz_service" label="业务服务">
                <Input placeholder="在线支付" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="priority" label="优先级" tooltip="数字越大优先匹配">
                <Input type="number" placeholder="0" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="enabled" label="启用" valuePropName="checked" initialValue={true}>
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} placeholder="描述这条规则的用途" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 测试 */}
      <Modal title="测试 URL 匹配" open={testOpen} onOk={handleTest} onCancel={() => { setTestOpen(false); setTestResult(null); }} width={420}>
        <Form form={testForm} layout="vertical">
          <Form.Item name="url" label="URL" rules={[{ required: true }]}>
            <Input placeholder="/api/pay/create" style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="method" label="HTTP 方法">
            <Input placeholder="POST" />
          </Form.Item>
        </Form>
        {testResult && (
          <div style={{ padding: 12, background: testResult.matched ? '#f6ffed' : '#fff2e8', borderRadius: 6, marginTop: 8 }}>
            {testResult.matched ? (
              <>
                <div style={{ color: '#52c41a', fontWeight: 600, marginBottom: 8 }}>✅ 匹配成功</div>
                <div>业务域: <Tag color="purple">{testResult.mapping?.business_domain}</Tag></div>
                <div>业务动作: {testResult.mapping?.business_action}</div>
                <div>业务服务: {testResult.mapping?.biz_service}</div>
              </>
            ) : (
              <div style={{ color: '#faad14', fontWeight: 600 }}>⚠️ 无匹配规则</div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default BizMappingPage;
