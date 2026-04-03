import React, { createContext, useContext, useState, useCallback } from 'react';
import { DatePicker, Space } from 'antd';
import dayjs, { Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;

export interface TimeRange {
  start: string; // ISO string
  end: string;
  label: string; // '1h' | '6h' | '24h' | '7d' | 'custom'
}

interface TimeContextValue {
  range: TimeRange;
  setRange: (r: TimeRange) => void;
  /** 转换为 API 参数 */
  apiParams: { time_range: string; start?: string; end?: string };
}

const TimeContext = createContext<TimeContextValue>({
  range: { start: '', end: '', label: '1h' },
  setRange: () => {},
  apiParams: { time_range: '1h' },
});

export const useTimeRange = () => useContext(TimeContext);

const presetRanges: { label: string; value: string }[] = [
  { label: '1小时', value: '1h' },
  { label: '6小时', value: '6h' },
  { label: '24小时', value: '24h' },
  { label: '7天', value: '7d' },
];

function labelToRange(label: string): TimeRange {
  const now = dayjs();
  const map: Record<string, number> = { '1h': 1, '6h': 6, '24h': 24, '7d': 168 };
  const hours = map[label] || 1;
  return {
    start: now.subtract(hours, 'hour').toISOString(),
    end: now.toISOString(),
    label,
  };
}

export const TimeRangeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [range, setRange] = useState<TimeRange>(labelToRange('1h'));

  const apiParams = range.label === 'custom'
    ? { time_range: 'custom', start: range.start, end: range.end }
    : { time_range: range.label };

  return (
    <TimeContext.Provider value={{ range, setRange, apiParams }}>
      {children}
    </TimeContext.Provider>
  );
};

/** 通用时间选择器组件，可放在任何页面顶部 */
export const TimeRangeBar: React.FC<{ style?: React.CSSProperties }> = ({ style }) => {
  const { range, setRange } = useTimeRange();

  return (
    <Space style={{ marginBottom: 12, ...style }}>
      <span style={{ color: '#8c8c8c', fontSize: 12 }}>时间范围：</span>
      {presetRanges.map(p => (
        <a key={p.value}
          onClick={() => setRange(labelToRange(p.value))}
          style={{
            padding: '2px 10px', borderRadius: 4, fontSize: 12,
            background: range.label === p.value ? '#1890ff' : '#f5f5f5',
            color: range.label === p.value ? '#fff' : '#595959',
            cursor: 'pointer',
          }}
        >{p.label}</a>
      ))}
      <RangePicker
        size="small"
        showTime
        value={range.label === 'custom' ? [dayjs(range.start), dayjs(range.end)] : undefined}
        onChange={(dates) => {
          if (dates && dates[0] && dates[1]) {
            setRange({
              start: dates[0].toISOString(),
              end: dates[1].toISOString(),
              label: 'custom',
            });
          }
        }}
        style={{ width: 280 }}
      />
    </Space>
  );
};
