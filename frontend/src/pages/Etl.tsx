import React, { useState } from 'react';
import { Card, Button, Input, Table, Tag, Space, Spin, Steps, message, Descriptions, Divider, Row, Col, Select } from 'antd';
import { ExperimentOutlined, PlayCircleOutlined, CopyOutlined, CheckOutlined } from '@ant-design/icons';
import axios from 'axios';

const { TextArea } = Input;

interface FieldInfo {
  name: string; type: string; example: string; confidence: number; description: string;
}

const typeColors: Record<string, string> = {
  string: 'blue', int: 'green', float: 'cyan', bool: 'orange',
  timestamp: 'purple', ip: 'geekblue', url: 'magenta',
};

const EtlPage: React.FC = () => {
  const [sample, setSample] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [configCopied, setConfigCopied] = useState(false);

  const handleParse = async () => {
    if (!sample.trim()) {
      message.warning('请粘贴日志样例');
      return;
    }
    setLoading(true);
    setCurrentStep(1);
    try {
      const res = await axios.post('/api/v1/etl/parse', { sample: sample.trim() });
      setResult(res.data);
      setCurrentStep(2);
    } catch (e: any) {
      message.error(e.response?.data?.detail || '解析失败');
      setCurrentStep(0);
    }
    setLoading(false);
  };

  const handleCopyConfig = () => {
    if (result?.suggested_vector_config) {
      navigator.clipboard.writeText(JSON.stringify(result.suggested_vector_config, null, 2));
      setConfigCopied(true);
      setTimeout(() => setConfigCopied(false), 2000);
    }
  };

  const columns = [
    { title: '字段名', dataIndex: 'name', width: 160,
      render: (v: string) => <code style={{ fontSize: 12 }}>{v}</code> },
    { title: '类型', dataIndex: 'type', width: 80,
      render: (v: string) => <Tag color={typeColors[v] || 'default'}>{v}</Tag> },
    { title: '示例值', dataIndex: 'example', width: 200,
      render: (v: string) => <span style={{ fontSize: 12, color: '#595959', fontFamily: 'monospace' }}>{v}</span> },
    { title: '置信度', dataIndex: 'confidence', width: 80,
      render: (v: number) => <span style={{ color: v >= 0.9 ? '#52c41a' : v >= 0.7 ? '#faad14' : '#ff4d4f' }}>{(v * 100).toFixed(0)}%</span> },
    { title: '说明', dataIndex: 'description', render: (v: string) => v || '-' },
  ];

  const formatLabels: Record<string, string> = {
    json: 'JSON', kv: 'Key=Value', apache: 'Apache Log', nginx: 'Nginx Log',
    syslog: 'Syslog', custom: '自定义格式',
  };

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>🔧 智能 ETL 识别</h2>
      <div style={{ marginBottom: 16, padding: '8px 12px', background: '#f6f8fa', borderRadius: 6, fontSize: 12, color: '#595959' }}>
        粘贴样例日志 → 自动识别格式 → 提取字段 → 生成 Vector pipeline 配置。支持 JSON / Key=Value / Syslog / Apache / Nginx 等常见格式。
      </div>

      <Steps
        current={currentStep}
        size="small"
        items={[
          { title: '粘贴日志' },
          { title: 'AI 解析', icon: loading ? <Spin size="small" /> : <ExperimentOutlined /> },
          { title: '确认结果' },
        ]}
        style={{ marginBottom: 24 }}
      />

      {/* Step 1: 输入 */}
      <Card title="📋 样例日志" size="small" style={{ marginBottom: 16 }}
        extra={
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleParse} loading={loading}>
            开始解析
          </Button>
        }>
        <TextArea
          rows={8}
          value={sample}
          onChange={e => setSample(e.target.value)}
          placeholder={"粘贴你的日志样例，每行一条。例如：\n\n{\"timestamp\":\"2026-04-03T10:00:00Z\",\"level\":\"info\",\"service\":\"order-service\",\"message\":\"Order created\",\"trace_id\":\"abc123\",\"duration_ms\":45}\n{\"timestamp\":\"2026-04-03T10:00:01Z\",\"level\":\"error\",\"service\":\"order-service\",\"message\":\"Payment failed\",\"trace_id\":\"def456\",\"error\":\"timeout\"}"}
          style={{ fontFamily: 'monospace', fontSize: 12 }}
        />
      </Card>

      {/* Step 2-3: 结果 */}
      {result && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Card size="small">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="识别格式">
                    <Tag color="blue" style={{ fontSize: 14 }}>{formatLabels[result.format] || result.format}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="分析行数">{result.sample_lines}</Descriptions.Item>
                  <Descriptions.Item label="解析方法"><code>{result.parse_method}</code></Descriptions.Item>
                  <Descriptions.Item label="识别字段">{result.fields.length} 个</Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
            <Col span={16}>
              <Card size="small" title="字段结构"
                extra={<Space>
                  <Tag color="green">string: {result.fields.filter((f: FieldInfo) => f.type === 'string').length}</Tag>
                  <Tag color="cyan">int/float: {result.fields.filter((f: FieldInfo) => f.type === 'int' || f.type === 'float').length}</Tag>
                  <Tag color="purple">timestamp: {result.fields.filter((f: FieldInfo) => f.type === 'timestamp').length}</Tag>
                </Space>}>
                <Table columns={columns} dataSource={result.fields} rowKey="name" size="small" pagination={false} scroll={{ y: 300 }} />
              </Card>
            </Col>
          </Row>

          {/* Vector 配置预览 */}
          <Card
            title="⚙️ Vector Pipeline 配置"
            size="small"
            extra={
              <Button size="small" icon={configCopied ? <CheckOutlined /> : <CopyOutlined />} onClick={handleCopyConfig}>
                {configCopied ? '已复制' : '复制配置'}
              </Button>
            }
          >
            <pre style={{ background: '#1e1e1e', color: '#d4d4d4', padding: 16, borderRadius: 6, fontSize: 12, overflow: 'auto', maxHeight: 400 }}>
              {JSON.stringify(result.suggested_vector_config, null, 2)}
            </pre>
          </Card>
        </>
      )}
    </div>
  );
};

export default EtlPage;
