import React, { useMemo } from 'react';
import { Select, Tag, Space, Tooltip } from 'antd';
import { InfoCircleOutlined, ExpandOutlined } from '@ant-design/icons';

// ---- 类型定义 ----
interface Entity {
  guid: string;
  name: string;
  type_name: string;
  health_score: number;
  health_level: string;
  risk_score: number;
  biz_service: string;
}

interface TopoFilterPanelProps {
  entities: Entity[];
  // 筛选器值
  entityType: 'system' | 'app';
  selectedSystems: string[];
  selectedServices: string[];
  // 回调
  onEntityTypeChange: (v: 'system' | 'app') => void;
  onSystemsChange: (v: string[]) => void;
  onServicesChange: (v: string[]) => void;
  // 观测对象
  observeTarget: string | null;
  onSetObserve: (guid: string) => void;
  // 健康统计
  stats: { critical: number; warning: number; healthy: number };
  statsApp: { critical: number; warning: number; healthy: number };
}

const healthColors = {
  critical: '#ff4d4f',
  warning: '#faad14',
  healthy: '#52c41a',
};

const TopoFilterPanel: React.FC<TopoFilterPanelProps> = ({
  entities,
  entityType,
  selectedSystems,
  selectedServices,
  onEntityTypeChange,
  onSystemsChange,
  onServicesChange,
  observeTarget,
  onSetObserve,
  stats,
  statsApp,
}) => {
  // 从 entities 提取系统和应用选项
  const systemOptions = useMemo(() => {
    const systems = new Set<string>();
    const apps = new Set<string>();
    entities.forEach(e => {
      // 假设 biz_service 字段区分业务系统
      if (e.biz_service) {
        if (e.type_name === 'Business' || e.type_name === 'Service') {
          apps.add(e.biz_service);
        }
      }
      // 假设 name 中包含系统标识的作为系统
      if (e.type_name === 'Host' || e.type_name === 'NetworkDevice') {
        systems.add(e.name.split('-')[0] || e.name);
      }
    });
    return {
      systems: Array.from(systems).map(s => ({ label: s, value: s })),
      apps: Array.from(apps).map(a => ({ label: a, value: a })),
      all: [...Array.from(systems), ...Array.from(apps)].map(s => ({ label: s, value: s })),
    };
  }, [entities]);

  // 服务列表（去重）
  const serviceOptions = useMemo(() => {
    const svcs = new Set<string>();
    entities.forEach(e => {
      if (e.type_name === 'Service') svcs.add(e.name);
    });
    return Array.from(svcs).map(s => ({ label: s, value: s }));
  }, [entities]);

  // 显示已选数量
  const selectedCount = selectedSystems.length;

  return (
    <div style={{
      width: 260,
      background: '#fff',
      borderRadius: 8,
      boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* 头部: 系统/应用切换 */}
      <div style={{
        padding: '10px 12px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
      }}>
        <span style={{ fontSize: 12, color: '#8c8c8c', whiteSpace: 'nowrap' }}>类型</span>
        <Select
          value={entityType}
          onChange={v => onEntityTypeChange(v)}
          style={{ width: 100 }}
          size="small"
          options={[
            { label: '系统', value: 'system' },
            { label: '应用', value: 'app' },
          ]}
        />
      </div>

      {/* 系统选择 (Cascader 样式两列) */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 6 }}>
          全部系统
          {selectedCount > 0 && (
            <Tag color="blue" style={{ marginLeft: 6, fontSize: 10 }}>
              +{selectedCount}
            </Tag>
          )}
        </div>
        <Select
          mode="multiple"
          value={selectedSystems}
          onChange={onSystemsChange}
          placeholder="选择系统..."
          style={{ width: '100%' }}
          size="small"
          maxTagCount={2}
          options={systemOptions.all}
          allowClear
        />
      </div>

      {/* 服务选择 */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 6 }}>服务</div>
        <Select
          mode="multiple"
          value={selectedServices}
          onChange={onServicesChange}
          placeholder="选择服务..."
          style={{ width: '100%' }}
          size="small"
          maxTagCount={2}
          options={serviceOptions}
          allowClear
          showSearch
          filterOption={(input, option) =>
            (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
          }
        />
      </div>

      {/* 调用深度 (disabled) */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #f0f0f0', opacity: 0.5 }}>
        <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 6 }}>调用深度</div>
        <Select
          placeholder="全部调用深度"
          style={{ width: '100%' }}
          size="small"
          disabled
          defaultValue="all"
          options={[{ label: '全部调用深度', value: 'all' }]}
        />
      </div>

      {/* 健康状态统计 */}
      <div style={{
        padding: '12px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fafbfc',
      }}>
        <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 8 }}>
          <InfoCircleOutlined style={{ marginRight: 4 }} />
          健康状态
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
          <span style={{ color: healthColors.critical }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>{stats.critical}</span>
            <span style={{ marginLeft: 2 }}>严重</span>
          </span>
          <span style={{ color: healthColors.warning }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>{stats.warning}</span>
            <span style={{ marginLeft: 2 }}>轻微</span>
          </span>
          <span style={{ color: healthColors.healthy }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>{stats.healthy}</span>
            <span style={{ marginLeft: 2 }}>健康</span>
          </span>
        </div>
        {/* 第二组 (应用层) */}
        <div style={{ display: 'flex', gap: 12, fontSize: 12, marginTop: 6 }}>
          <span style={{ color: healthColors.critical }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>{statsApp.critical}</span>
          </span>
          <span style={{ color: healthColors.warning }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>{statsApp.warning}</span>
          </span>
          <span style={{ color: healthColors.healthy }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>{statsApp.healthy}</span>
          </span>
        </div>
      </div>

      {/* 操作按钮 */}
      <div style={{ padding: '10px 12px' }}>
        <Tooltip title="点击图谱中的节点可设置为观测对象">
          <button
            style={{
              width: '100%',
              padding: '6px 12px',
              border: '1px solid #1890ff',
              borderRadius: 4,
              background: '#e6f7ff',
              color: '#1890ff',
              fontSize: 12,
              cursor: 'pointer',
              marginBottom: 6,
            }}
            onClick={() => observeTarget && onSetObserve('')}
          >
            {observeTarget ? '删除观测对象' : '设置为观测对象'}
          </button>
        </Tooltip>
        <button
          style={{
            width: '100%',
            padding: '6px 12px',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            background: '#fff',
            color: '#595959',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          <ExpandOutlined style={{ marginRight: 4 }} />
          展开系统
        </button>
      </div>
    </div>
  );
};

export default TopoFilterPanel;

// ---- 健康统计计算 Hook ----
export function useHealthStats(entities: Entity[]) {
  return useMemo(() => {
    const stats = { critical: 0, warning: 0, healthy: 0 };
    entities.forEach(e => {
      if (e.health_level === 'critical' || e.health_level === 'down') {
        stats.critical++;
      } else if (e.health_level === 'warning') {
        stats.warning++;
      } else {
        stats.healthy++;
      }
    });
    return stats;
  }, [entities]);
}
