import React, { useEffect, useState, useCallback } from 'react';
import { Card, Select, Spin, Space, Button, Tooltip, Progress, Row, Col, Statistic } from 'antd';
import { ReloadOutlined, LineChartOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

interface TimeSeriesPoint {
  time: string;
  min: number;
  max: number;
  avg: number;
  count: number;
  p50: number;
  p75: number;
  p90: number;
  p99: number;
}

interface MetricsTrendProps {
  /** 实体 GUID */
  entityGuid?: string;
  /** 实体类型 */
  entityType?: string;
  /** 指标名称 */
  metricName?: string;
  /** 图表标题 */
  title?: string;
  /** 单位 */
  unit?: string;
  /** 时间范围 */
  timeRange?: { start: string; end: string };
  /** 粒度 */
  granularity?: string;
  /** 阈值线 */
  thresholds?: { warn?: number; crit?: number };
  /** 图表高度 */
  height?: number;
  /** 数据加载完成回调 */
  onDataLoaded?: (data: TimeSeriesPoint[]) => void;
}

const API_BASE = '/api/v1';

const MetricsTrend: React.FC<MetricsTrendProps> = ({
  entityGuid,
  entityType,
  metricName,
  title,
  unit = '',
  timeRange,
  granularity = '5m',
  thresholds,
  height = 200,
  onDataLoaded,
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TimeSeriesPoint[]>([]);
  const [selectedGranularity, setSelectedGranularity] = useState(granularity);
  const [summary, setSummary] = useState<{
    current: number;
    min: number;
    max: number;
    avg: number;
    p90: number;
    p99: number;
  } | null>(null);

  // 加载数据
  const loadData = useCallback(async () => {
    if (!metricName) return;

    setLoading(true);
    try {
      const params = new URLSearchParams({
        metric_name: metricName,
        start: timeRange?.start || dayjs().subtract(24, 'hour').format('YYYY-MM-DDTHH:mm:ss'),
        end: timeRange?.end || dayjs().format('YYYY-MM-DDTHH:mm:ss'),
        granularity: selectedGranularity,
      });

      if (entityGuid) params.append('entity_guid', entityGuid);
      if (entityType) params.append('entity_type', entityType);

      const response = await fetch(`${API_BASE}/metrics/query?${params}`);
      const result = await response.json();
      
      const series = result.series || [];
      setData(series);
      
      // 计算汇总
      if (series.length > 0) {
        const last = series[series.length - 1];
        setSummary({
          current: last.avg,
          min: Math.min(...series.map((s: TimeSeriesPoint) => s.min)),
          max: Math.max(...series.map((s: TimeSeriesPoint) => s.max)),
          avg: series.reduce((a: number, s: TimeSeriesPoint) => a + s.avg, 0) / series.length,
          p90: series.reduce((a: number, s: TimeSeriesPoint) => a + s.p90, 0) / series.length,
          p99: series.reduce((a: number, s: TimeSeriesPoint) => a + s.p99, 0) / series.length,
        });
      }
      
      onDataLoaded?.(series);
    } catch (error) {
      console.error('Failed to load metrics:', error);
    } finally {
      setLoading(false);
    }
  }, [entityGuid, entityType, metricName, timeRange, selectedGranularity, onDataLoaded]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 生成 SVG 趋势图
  const renderTrendChart = () => {
    if (data.length === 0) return null;

    const width = 100;
    const height = 100;
    const padding = 5;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const values = data.map(d => d.avg);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    // 生成路径点
    const points = values.map((v, i) => {
      const x = padding + (i / (values.length - 1)) * chartWidth;
      const y = padding + chartHeight - ((v - min) / range) * chartHeight;
      return `${x},${y}`;
    });

    // 生成填充区域
    const areaPoints = [
      `${padding},${padding + chartHeight}`,
      ...points,
      `${padding + chartWidth},${padding + chartHeight}`,
    ].join(' ');

    // 阈值线
    const warnY = thresholds?.warn ? padding + chartHeight - ((thresholds.warn - min) / range) * chartHeight : null;
    const critY = thresholds?.crit ? padding + chartHeight - ((thresholds.crit - min) / range) * chartHeight : null;

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '60px' }}>
        {/* 背景网格 */}
        <defs>
          <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#1890ff" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#1890ff" stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {/* 阈值线 */}
        {warnY && (
          <line
            x1={padding}
            y1={warnY}
            x2={padding + chartWidth}
            y2={warnY}
            stroke="#faad14"
            strokeWidth="0.5"
            strokeDasharray="2,2"
          />
        )}
        {critY && (
          <line
            x1={padding}
            y1={critY}
            x2={padding + chartWidth}
            y2={critY}
            stroke="#ff4d4f"
            strokeWidth="0.5"
            strokeDasharray="2,2"
          />
        )}

        {/* 填充区域 */}
        <polygon points={areaPoints} fill="url(#areaGradient)" />

        {/* 趋势线 */}
        <polyline
          points={points.join(' ')}
          fill="none"
          stroke="#1890ff"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* 当前点 */}
        <circle
          cx={padding + chartWidth}
          cy={padding + chartHeight - ((values[values.length - 1] - min) / range) * chartHeight}
          r="2"
          fill="#1890ff"
        />
      </svg>
    );
  };

  // 判断当前值状态
  const getStatus = (value: number) => {
    if (thresholds?.crit && value >= thresholds.crit) return 'exception';
    if (thresholds?.warn && value >= thresholds.warn) return 'normal';
    return 'normal';
  };

  // 计算进度条百分比（用于显示当前值在范围内的位置）
  const getProgressPercent = (value: number) => {
    if (!thresholds) return 50;
    const max = thresholds.crit || thresholds.warn || 100;
    return Math.min((value / max) * 100, 100);
  };

  return (
    <Card
      size="small"
      title={
        <Space>
          <LineChartOutlined />
          <span>{title || metricName}</span>
        </Space>
      }
      extra={
        <Space>
          <Select
            size="small"
            value={selectedGranularity}
            onChange={setSelectedGranularity}
            style={{ width: 70 }}
            options={[
              { label: '1m', value: '1m' },
              { label: '5m', value: '5m' },
              { label: '1h', value: '1h' },
              { label: '1d', value: '1d' },
            ]}
          />
          <Tooltip title="刷新">
            <Button size="small" icon={<ReloadOutlined />} onClick={loadData} loading={loading} />
          </Tooltip>
        </Space>
      }
      bodyStyle={{ padding: '12px' }}
    >
      <Spin spinning={loading}>
        {summary ? (
          <div>
            {/* 趋势图 */}
            <div style={{ marginBottom: 12 }}>
              {renderTrendChart()}
            </div>

            {/* 统计信息 */}
            <Row gutter={[8, 8]}>
              <Col span={8}>
                <Statistic
                  title="当前"
                  value={summary.current}
                  precision={2}
                  suffix={unit}
                  valueStyle={{ fontSize: 14 }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="P90"
                  value={summary.p90}
                  precision={2}
                  suffix={unit}
                  valueStyle={{ fontSize: 14, color: '#faad14' }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="P99"
                  value={summary.p99}
                  precision={2}
                  suffix={unit}
                  valueStyle={{ fontSize: 14, color: '#ff4d4f' }}
                />
              </Col>
            </Row>

            {/* 阈值进度条 */}
            {thresholds && (
              <div style={{ marginTop: 8 }}>
                <Progress
                  percent={getProgressPercent(summary.current)}
                  status={getStatus(summary.current)}
                  showInfo={false}
                  strokeColor={{
                    '0%': '#52c41a',
                    '70%': '#faad14',
                    '90%': '#ff4d4f',
                  }}
                  size="small"
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#999' }}>
                  <span>0</span>
                  {thresholds.warn && <span>Warn: {thresholds.warn}{unit}</span>}
                  {thresholds.crit && <span>Crit: {thresholds.crit}{unit}</span>}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ height: `${height}px`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
            暂无数据
          </div>
        )}
      </Spin>
    </Card>
  );
};

export default MetricsTrend;
