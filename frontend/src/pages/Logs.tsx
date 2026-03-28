import React, { useState, useEffect } from 'react';
import { Table, Input, Select, Button, DatePicker, Tag, Space, Card } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import axios from 'axios';
import dayjs from 'dayjs';

const API_BASE = '/api/v1/logs';
const CMDB_BASE = '/api/v1/cmdb';

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
  const [timeRange, setTimeRange] = useState<any>([dayjs().subtract(1, 'hour'), dayjs()]);
  const [services, setServices] = useState<{label: string, value: string}[]>([]);

  // 动态获取服务列表
  useEffect(() => {
    const fetchServices = async () => {
      try {
        const res = await axios.get(`${CMDB_BASE}/entities`, { params: { type_name: 'Service', limit: 100 } });
        const opts = (res.data.items || []).map((e: any) => ({ label: e.name, value: e.name }));
        setServices([{ label: '全部', value: '' }, ...opts]);
      } catch {
        // CMDB 没有实体时，用默认列表
        setServices([
          { label: '全部', value: '' },
          { label: 'gateway', value: 'gateway' },
          { label: 'order-service', value: 'order-service' },
          { label: 'payment-service', value: 'payment-service' },
          { label: 'inventory-service', value: 'inventory-service' },
        ]);
      }
    };
    fetchServices();
  }, []);

  // 页面加载自动搜索
  useEffect(() => { handleSearch(); }, []);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 200 };
      if (searchText) params.q = searchText;
      if (service) params.service = service;
      if (level) params.level = level;
      if (timeRange?.[0]) params.start = timeRange[0].format('YYYY-MM-DD HH:mm:ss');
      if (timeRange?.[1]) params.end = timeRange[1].format('YYYY-MM-DD HH:mm:ss');

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
      render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-',
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
      width: 120,
    },
    {
      title: '级别',
      dataIndex: 'level',
      width: 80,
      render: (l: string) => <Tag color={levelColors[l] || 'default'}>{(l || '').toUpperCase()}</Tag>,
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
          allowClear
        />
        <Select
          placeholder="选择服务"
          allowClear
          style={{ width: 180 }}
          value={service}
          onChange={(v) => setService(v || undefined)}
          options={services}
          showSearch
          filterOption={(input, option) =>
            (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <Select
          placeholder="日志级别"
          allowClear
          style={{ width: 100 }}
          value={level}
          onChange={(v) => setLevel(v || undefined)}
          options={[
            { label: 'ERROR', value: 'error' },
            { label: 'WARN', value: 'warn' },
            { label: 'INFO', value: 'info' },
            { label: 'DEBUG', value: 'debug' },
          ]}
        />
        <DatePicker.RangePicker
          showTime
          value={timeRange}
          onChange={setTimeRange}
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
        pagination={{ pageSize: 50, showTotal: (total) => `共 ${total} 条` }}
      />
    </Card>
  );
};

export default LogsPage;
