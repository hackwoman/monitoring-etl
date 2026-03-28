import React, { useState } from 'react';
import { Table, Input, Select, Button, DatePicker, Tag, Space, Card } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import axios from 'axios';
import dayjs from 'dayjs';

const API_BASE = '/api/v1/logs';

const levelColors: Record<string, string> = {
  error: 'red', fatal: 'red',
  warn: 'orange', warning: 'orange',
  info: 'blue',
  debug: 'default',
};

const LogsPage: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [service, setService] = useState<string>();
  const [level, setLevel] = useState<string>();
  const [timeRange, setTimeRange] = useState<any>();

  const handleSearch = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 200 };
      if (searchText) params.q = searchText;
      if (service) params.service = service;
      if (level) params.level = level;
      if (timeRange?.[0]) params.start = timeRange[0].toISOString();
      if (timeRange?.[1]) params.end = timeRange[1].toISOString();

      const res = await axios.get(`${API_BASE}/search`, { params });
      setLogs(res.data.items || []);
    } catch (err) {
      console.error('Search failed:', err);
    }
    setLoading(false);
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      width: 200,
      render: (t: string) => dayjs(t).format('YYYY-MM-DD HH:mm:ss.SSS'),
    },
    {
      title: '服务',
      dataIndex: 'service_name',
      width: 150,
      render: (s: string) => <Tag color="geekblue">{s}</Tag>,
    },
    {
      title: '主机',
      dataIndex: 'host_name',
      width: 150,
    },
    {
      title: '级别',
      dataIndex: 'level',
      width: 80,
      render: (l: string) => <Tag color={levelColors[l] || 'default'}>{l?.toUpperCase()}</Tag>,
    },
    {
      title: '日志内容',
      dataIndex: 'message',
      ellipsis: true,
    },
  ];

  return (
    <Card title="日志查询">
      <Space style={{ marginBottom: 16, width: '100%', flexWrap: 'wrap' }}>
        <Input
          placeholder="搜索日志内容..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 300 }}
          prefix={<SearchOutlined />}
        />
        <Select
          placeholder="服务"
          allowClear
          style={{ width: 150 }}
          onChange={setService}
          options={[
            { label: '全部', value: undefined },
            { label: 'payment', value: 'payment' },
            { label: 'order', value: 'order' },
          ]}
        />
        <Select
          placeholder="级别"
          allowClear
          style={{ width: 100 }}
          onChange={setLevel}
          options={[
            { label: 'ERROR', value: 'error' },
            { label: 'WARN', value: 'warn' },
            { label: 'INFO', value: 'info' },
            { label: 'DEBUG', value: 'debug' },
          ]}
        />
        <DatePicker.RangePicker
          showTime
          onChange={setTimeRange}
          defaultValue={[dayjs().subtract(1, 'hour'), dayjs()]}
        />
        <Button type="primary" onClick={handleSearch} loading={loading}>
          搜索
        </Button>
      </Space>
      <Table
        columns={columns}
        dataSource={logs}
        rowKey={(r, i) => `${r.timestamp}-${i}`}
        size="small"
        scroll={{ y: 600 }}
        pagination={{ pageSize: 50 }}
      />
    </Card>
  );
};

export default LogsPage;
