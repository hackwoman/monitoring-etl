import React, { useEffect, useState, useCallback } from 'react';
import { Card, Table, Tag, Spin, Space, Select, Button, Tooltip, Statistic, Row, Col } from 'antd';
import { ReloadOutlined, LineChartOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

interface MetricSummary {
  metric_name: string;
  metric_unit: string;
  current_value: number;
  avg_value: number;
  min_value: number;
  max_value: number;
  p50: number;
  p90: number;
  data_points: number;
}

interface EntityMetricsSummaryProps {
  /** 实体 GUID */
  entityGuid: string;
  /** 时间范围 */
  timeRange?: string;
  /** 是否显示为表格模式 */
  tableMode?: boolean;
}

const API_BASE = '/api/v1';

const EntityMetricsSummary: React.FC<EntityMetricsSummaryProps> = ({
  entityGuid,
  timeRange = '1h',
  tableMode = false,
}) => {
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState<MetricSummary[]>([]);
  const [selectedTimeRange, setSelectedTimeRange] = useState(timeRange);

  const loadData = useCallback(async () => {
    if (!entityGuid) return;

    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE}/metrics/entity/${entityGuid}/summary?time_range=${selectedTimeRange}`
      );
      const result = await response.json();
      setMetrics(result.metrics || []);
    } catch (error) {
      console.error('Failed to load entity metrics:', error);
    } finally {
      setLoading(false);
    }
  }, [entityGuid, selectedTimeRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getMetricStatus = (current: number, unit: string) => {
    // 基于常见阈值判断状态
    const thresholds: Record<string, { warn: number; crit: number }> = {
      percent: { warn: 80, crit: 90 },
      ratio: { warn: 0.7, crit: 1.0 },
      ms: { warn: 200, crit: 800 },
    };

    const threshold = thresholds[unit];
    if (!threshold) return 'default';

    if (current >= threshold.crit) return 'error';
    if (current >= threshold.warn) return 'warning';
    return 'success';
  };

  const formatValue = (value: number, unit: string) => {
    if (unit === 'percent') return `${value.toFixed(1)}%`;
    if (unit === 'ms') return `${value.toFixed(0)}ms`;
    if (unit === 'count' || unit === 'count/s' || unit === 'count/min') {
      if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
      if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
      return value.toFixed(0);
    }
    if (unit === 'bytes' || unit === 'MB/s' || unit === 'GB') {
      return `${value.toFixed(1)} ${unit}`;
    }
    return value.toFixed(2);
  };

  // 表格列定义
  const columns = [
    {
      title: '指标',
      dataIndex: 'metric_name',
      key: 'metric_name',
      render: (text: string) => {
        // 简化指标名称显示
        const parts = text.split('.');
        const shortName = parts[parts.length - 1] || text;
        return (
          <Tooltip title={text}>
            <Tag>{shortName}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '当前值',
      dataIndex: 'current_value',
      key: 'current_value',
      align: 'right' as const,
      render: (val: number, record: MetricSummary) => (
        <Statistic
          value={formatValue(val, record.metric_unit)}
          valueStyle={{ 
            fontSize: 14,
            color: getMetricStatus(val, record.metric_unit) === 'error' ? '#ff4d4f' :
                   getMetricStatus(val, record.metric_unit) === 'warning' ? '#faad14' : '#52c41a'
          }}
        />
      ),
    },
    {
      title: 'P50',
      dataIndex: 'p50',
      key: 'p50',
      align: 'right' as const,
      render: (val: number, record: MetricSummary) => formatValue(val, record.metric_unit),
    },
    {
      title: 'P90',
      dataIndex: 'p90',
      key: 'p90',
      align: 'right' as const,
      render: (val: number, record: MetricSummary) => (
        <span style={{ color: '#faad14' }}>{formatValue(val, record.metric_unit)}</span>
      ),
    },
    {
      title: '范围',
      key: 'range',
      align: 'right' as const,
      render: (_: any, record: MetricSummary) => (
        <span style={{ color: '#999', fontSize: 12 }}>
          {formatValue(record.min_value, record.metric_unit)} - {formatValue(record.max_value, record.metric_unit)}
        </span>
      ),
    },
  ];

  if (tableMode) {
    return (
      <Card
        size="small"
        title={
          <Space>
            <LineChartOutlined />
            <span>指标摘要</span>
          </Space>
        }
        extra={
          <Space>
            <Select
              size="small"
              value={selectedTimeRange}
              onChange={setSelectedTimeRange}
              style={{ width: 80 }}
              options={[
                { label: '1小时', value: '1h' },
                { label: '6小时', value: '6h' },
                { label: '24小时', value: '24h' },
                { label: '7天', value: '7d' },
              ]}
            />
            <Tooltip title="刷新">
              <Button size="small" icon={<ReloadOutlined />} onClick={loadData} loading={loading} />
            </Tooltip>
          </Space>
        }
      >
        <Spin spinning={loading}>
          <Table
            dataSource={metrics}
            columns={columns}
            size="small"
            pagination={false}
            rowKey="metric_name"
            scroll={{ y: 300 }}
          />
        </Spin>
      </Card>
    );
  }

  // 卡片模式
  return (
    <Spin spinning={loading}>
      <Row gutter={[8, 8]}>
        {metrics.slice(0, 6).map((metric) => (
          <Col span={8} key={metric.metric_name}>
            <Card size="small" bodyStyle={{ padding: '8px' }}>
              <Statistic
                title={
                  <Tooltip title={metric.metric_name}>
                    <span style={{ fontSize: 11 }}>
                      {metric.metric_name.split('.').pop()}
                    </span>
                  </Tooltip>
                }
                value={formatValue(metric.current_value, metric.metric_unit)}
                valueStyle={{ fontSize: 14 }}
              />
              <div style={{ fontSize: 10, color: '#999', marginTop: 4 }}>
                P90: {formatValue(metric.p90, metric.metric_unit)}
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </Spin>
  );
};

export default EntityMetricsSummary;
