import React, { useState, useRef, useEffect } from 'react';
import { Card, Input, Button, List, Tag, Space, Spin, Empty, Tooltip } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import axios from 'axios';

const API_BASE = '/api/v1';
const CMDB_API = '/api/v1/cmdb';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  data?: any;
  source?: 'backend' | 'frontend';
}

const SUGGESTIONS = [
  'payment-service 的健康度',
  '异常的实体',
  '最慢的服务',
  '错误率',
  '有多少个服务',
  '帮助',
];

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '你好！我是监控助手。你可以问我：\n• "有哪些异常实体"\n• "payment-service 的健康度"\n• "有多少个 Service"\n• "业务在线支付的情况"',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (text?: string) => {
    const question = (text || input).trim();
    if (!question) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      // 优先调用后端 Chat API
      const res = await axios.post(`${API_BASE}/chat`, { message: question });
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: res.data.reply || '没有收到回复',
        data: res.data.data,
        source: 'backend',
      }]);
    } catch (err: any) {
      // 后端不可用时，降级到前端解析
      try {
        const answer = await fallbackProcess(question);
        setMessages((prev) => [...prev, answer]);
      } catch (fallbackErr: any) {
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: `抱歉，查询出错了：${err.message || '未知错误'}`,
        }]);
      }
    }
    setLoading(false);
  };

  // 前端降级解析（后端不可用时）
  const fallbackProcess = async (q: string): Promise<Message> => {
    const lower = q.toLowerCase();

    // 异常实体查询
    if (lower.includes('异常') || lower.includes('告警') || lower.includes('问题') || lower.includes('anomal')) {
      const resAll = await axios.get(`${CMDB_API}/entities`, { params: { limit: 100 } });
      const anomalies = (resAll.data.items || []).filter(
        (e: any) => e.health_level && e.health_level !== 'healthy'
      );

      if (anomalies.length === 0) {
        return { role: 'assistant', content: '🎉 当前没有异常实体，所有实体状态正常！' };
      }

      const lines = anomalies.map((e: any) =>
        `• ${e.name} (${e.type_name}) — 健康度 ${e.health_score}, 状态 ${e.health_level}, 风险度 ${e.risk_score}`
      );
      return {
        role: 'assistant',
        content: `🚨 发现 ${anomalies.length} 个异常实体：\n${lines.join('\n')}`,
        data: anomalies,
      };
    }

    // 实体健康度查询 — 尝试匹配实体名
    const healthMatch = q.match(/(.+?)(?:的|健康度|健康|状态|health)/);
    if (healthMatch) {
      const entityName = healthMatch[1].trim();
      const res = await axios.get(`${CMDB_API}/entities`, {
        params: { search: entityName, limit: 5 },
      });
      const items = res.data.items || [];
      if (items.length === 0) {
        return { role: 'assistant', content: `没有找到名为 "${entityName}" 的实体。` };
      }

      const lines = items.map((e: any) => {
        const levelEmoji = e.health_level === 'healthy' ? '💚' : e.health_level === 'warning' ? '⚠️' : '🔴';
        return `${levelEmoji} ${e.name} (${e.type_name})\n  健康度: ${e.health_score}/100 (${e.health_level})\n  风险度: ${e.risk_score ?? '-'}\n  业务: ${e.biz_service || '-'}`;
      });
      return {
        role: 'assistant',
        content: lines.join('\n\n'),
        data: items,
      };
    }

    // 数量查询
    if (lower.includes('多少') || lower.includes('几个') || lower.includes('数量') || lower.includes('count')) {
      // 提取类型名
      const typeNames = ['Service', 'Host', 'MySQL', 'Redis', 'Database', 'Business', 'NetworkDevice'];
      const matchedType = typeNames.find(t => lower.includes(t.toLowerCase()));

      if (matchedType) {
        const res = await axios.get(`${CMDB_API}/entities`, {
          params: { type_name: matchedType, limit: 1 },
        });
        return {
          role: 'assistant',
          content: `📦 共有 ${res.data.total || 0} 个 ${matchedType} 实体。`,
        };
      }

      // 总数
      const res = await axios.get(`${CMDB_API}/entities`, { params: { limit: 1 } });
      return {
        role: 'assistant',
        content: `📦 平台共有 ${res.data.total || 0} 个实体。`,
      };
    }

    // 业务查询
    if (lower.includes('业务') || lower.includes('business')) {
      const res = await axios.get(`${CMDB_API}/entities`, {
        params: { type_name: 'Business', limit: 20 },
      });
      const businesses = res.data.items || [];
      if (businesses.length === 0) {
        return { role: 'assistant', content: '暂无业务实体数据。' };
      }

      const lines = businesses.map((e: any) => {
        const emoji = e.health_level === 'healthy' ? '💚' : e.health_level === 'warning' ? '⚠️' : '🔴';
        return `${emoji} ${e.name} — 健康度 ${e.health_score ?? '-'}`;
      });
      return {
        role: 'assistant',
        content: `🏢 业务列表：\n${lines.join('\n')}`,
        data: businesses,
      };
    }

    // 默认：搜索实体
    const res = await axios.get(`${CMDB_API}/entities`, {
      params: { search: q, limit: 10 },
    });
    const items = res.data.items || [];
    if (items.length > 0) {
      const lines = items.map((e: any) =>
        `• ${e.name} (${e.type_name}) — 健康度 ${e.health_score ?? '-'}, 状态 ${e.health_level || '-'}`
      );
      return {
        role: 'assistant',
        content: `🔍 找到 ${items.length} 个相关实体：\n${lines.join('\n')}`,
        data: items,
      };
    }

    return {
      role: 'assistant',
      content: `抱歉，我不太理解 "${q}"。试试这些：\n• "有哪些异常实体"\n• "payment-service 的健康度"\n• "有多少个 Service"\n• "业务列表"`,
    };
  };

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>💬 智能问答</h2>

      <Card
        style={{ height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}
      >
        {/* 消息列表 */}
        <div ref={listRef} style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          <List
            dataSource={messages}
            renderItem={(msg) => (
              <div style={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: 12,
              }}>
                <div style={{
                  maxWidth: '80%',
                  padding: '10px 14px',
                  borderRadius: 12,
                  background: msg.role === 'user' ? '#1890ff' : '#f5f5f5',
                  color: msg.role === 'user' ? '#fff' : '#262626',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}>
                  <Space align="start">
                    {msg.role === 'assistant' ? <RobotOutlined style={{ marginTop: 4 }} /> : null}
                    <div>{msg.content}</div>
                    {msg.role === 'user' ? <UserOutlined style={{ marginTop: 4 }} /> : null}
                  </Space>
                </div>
              </div>
            )}
          />
          {loading && (
            <div style={{ textAlign: 'center', padding: 8 }}>
              <Spin size="small" /> 思考中...
            </div>
          )}
        </div>

        {/* 快捷建议 */}
        <div style={{ padding: '8px 12px', borderTop: '1px solid #f0f0f0', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {SUGGESTIONS.map((s) => (
            <Button key={s} size="small" type="dashed" onClick={() => handleSend(s)}>
              {s}
            </Button>
          ))}
        </div>

        {/* 输入框 */}
        <div style={{ padding: 12, borderTop: '1px solid #f0f0f0', display: 'flex', gap: 8 }}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => handleSend()}
            placeholder="输入问题，如：有哪些异常实体"
            disabled={loading}
            style={{ flex: 1 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={() => handleSend()}
            loading={loading}
          >
            发送
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default ChatPage;
