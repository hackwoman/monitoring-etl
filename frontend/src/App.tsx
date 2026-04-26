import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Space, Avatar } from 'antd';
import {
  FileTextOutlined, DatabaseOutlined, DashboardOutlined,
  ClusterOutlined, MessageOutlined, AlertOutlined,
  ApiOutlined, DesktopOutlined, CloudServerOutlined,
  EyeOutlined, ThunderboltOutlined, MonitorOutlined,
  TagOutlined, ToolOutlined, SearchOutlined,
  BarChartOutlined, LinkOutlined, SettingOutlined,
  SafetyCertificateOutlined,  FundOutlined,
  BlockOutlined,
} from '@ant-design/icons';
import LogsPage from './pages/Logs';
import CmdbPage from './pages/Cmdb';
import OverviewPage from './pages/Overview';
import TopologyPage from './pages/Topology';
import ChatPage from './pages/Chat';
import AlertsPage from './pages/Alerts';
import ServiceAnalysis from './pages/ServiceAnalysis';
import HostAnalysis from './pages/HostAnalysis';
import NetworkAnalysis from './pages/NetworkAnalysis';
import PageAnalysis from './pages/PageAnalysis';
import HttpRequestAnalysis from './pages/HttpRequestAnalysis';
import BizMappingPage from './pages/BizMapping';
import EtlPage from './pages/Etl';
import BusinessDiscovery from './pages/BusinessDiscovery';
import MetricBrowserPage from './pages/MetricBrowser';
import CompensationManagerPage from './pages/CompensationManager';
import ModelTopology from './pages/ModelTopology';
import EntityTypeDetail from './pages/EntityTypeDetail';
import { TimeRangeProvider } from './components/TimeRangeContext';

const { Header, Content, Sider } = Layout;
const { Text } = Typography;

// 根据当前路径确定选中的菜单项和展开的子菜单
const getSelectedKeys = (pathname: string): string[] => {
  if (pathname === '/') return ['overview'];
  const routeMap: Record<string, string> = {
    '/topology': 'topology',
    '/business-discovery': 'biz-discovery',
    '/service-analysis': 'service-analysis',
    '/host-analysis': 'host-analysis',
    '/network-analysis': 'network-analysis',
    '/page-analysis': 'page-analysis',
    '/http-request-analysis': 'http-request',
    '/cmdb': 'cmdb',
    '/metric-browser': 'metric-browser',
    '/compensation': 'compensation',
    '/biz-mapping': 'biz-mapping',
    '/etl': 'etl',
    '/model-topology': 'model-topology',
    '/alerts': 'alerts',
    '/logs': 'logs',
    '/chat': 'chat',
  };
  return [routeMap[pathname] || ''];
};

const getOpenKeys = (pathname: string): string[] => {
  if (pathname === '/') return ['workspace'];
  const groupMap: Record<string, string> = {
    '/topology': 'monitor-analysis',
    '/business-discovery': 'monitor-analysis',
    '/service-analysis': 'monitor-analysis',
    '/host-analysis': 'monitor-analysis',
    '/network-analysis': 'monitor-analysis',
    '/page-analysis': 'monitor-analysis',
    '/http-request-analysis': 'monitor-analysis',
    '/cmdb': 'config-management',
    '/metric-browser': 'config-management',
    '/compensation': 'config-management',
    '/biz-mapping': 'config-management',
    '/etl': 'config-management',
    '/model-topology': 'model-topology',
    '/alerts': 'alert-management',
    '/logs': 'data-query',
    '/chat': 'data-query',
  };
  return [groupMap[pathname] || 'workspace'];
};

const AppContent: React.FC = () => {
  const location = useLocation();
  const selectedKeys = getSelectedKeys(location.pathname);
  const openKeys = getOpenKeys(location.pathname);

  const menuItems = [
    {
      key: 'workspace',
      icon: <DashboardOutlined />,
      label: '工作台',
      children: [
        { key: 'overview', icon: <FundOutlined />, label: <Link to="/">总览</Link> },
      ],
    },
    {
      key: 'monitor-analysis',
      icon: <SearchOutlined />,
      label: '监控分析',
      children: [
        { key: 'topology', icon: <ClusterOutlined />, label: <Link to="/topology">拓扑</Link> },
        { key: 'biz-discovery', icon: <EyeOutlined />, label: <Link to="/business-discovery">业务发现</Link> },
        { key: 'service-analysis', icon: <ApiOutlined />, label: <Link to="/service-analysis">服务分析</Link> },
        { key: 'host-analysis', icon: <DesktopOutlined />, label: <Link to="/host-analysis">主机分析</Link> },
        { key: 'network-analysis', icon: <CloudServerOutlined />, label: <Link to="/network-analysis">网络分析</Link> },
        { key: 'page-analysis', icon: <MonitorOutlined />, label: <Link to="/page-analysis">页面分析</Link> },
        { key: 'http-request', icon: <ThunderboltOutlined />, label: <Link to="/http-request-analysis">网络请求</Link> },
      ],
    },
    {
      key: 'config-management',
      icon: <SettingOutlined />,
      label: '配置管理',
      children: [
        { key: 'cmdb', icon: <DatabaseOutlined />, label: <Link to="/cmdb">CMDB</Link> },
        { key: 'metric-browser', icon: <BarChartOutlined />, label: <Link to="/metric-browser">指标浏览器</Link> },
        { key: 'compensation', icon: <LinkOutlined />, label: <Link to="/compensation">补偿机制</Link> },
        { key: 'biz-mapping', icon: <TagOutlined />, label: <Link to="/biz-mapping">业务映射</Link> },
        { key: 'etl', icon: <ToolOutlined />, label: <Link to="/etl">智能ETL</Link> },
      ],
    },
    {
      key: 'model-topology',
      icon: <BlockOutlined />,
      label: '模型视图',
      children: [
        { key: 'model-topology', icon: <BlockOutlined />, label: <Link to="/model-topology">模型拓扑</Link> },
      ],
    },
    {
      key: 'alert-management',
      icon: <AlertOutlined />,
      label: '告警管理',
      children: [
        { key: 'alerts', icon: <SafetyCertificateOutlined />, label: <Link to="/alerts">告警</Link> },
      ],
    },
    {
      key: 'data-query',
      icon: <FileTextOutlined />,
      label: '数据查询',
      children: [
        { key: 'logs', icon: <FileTextOutlined />, label: <Link to="/logs">日志</Link> },
        { key: 'chat', icon: <MessageOutlined />, label: <Link to="/chat">问答</Link> },
      ],
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        background: 'linear-gradient(90deg, #001529 0%, #002140 100%)',
        boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
      }}>
        <Space size={12}>
          <Avatar
            size={32}
            style={{ backgroundColor: '#1890ff', fontSize: 18 }}
            icon={<MonitorOutlined />}
          />
          <Text strong style={{ color: '#fff', fontSize: 18, letterSpacing: 1 }}>
            Monitoring ETL Platform
          </Text>
        </Space>
        <Space size={16}>
          <Text style={{ color: 'rgba(255,255,255,0.65)', fontSize: 12 }}>
            v1.0 · 智能监控运维平台
          </Text>
        </Space>
      </Header>
      <Layout>
        <Sider
          width={220}
          style={{
            background: '#001529',
            borderRight: '1px solid #304156',
            overflow: 'auto',
            height: 'calc(100vh - 64px)',
            position: 'sticky',
            top: 64,
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={selectedKeys}
            defaultOpenKeys={openKeys}
            style={{
              height: '100%',
              borderRight: 0,
              background: 'transparent',
            }}
            items={menuItems}
          />
        </Sider>
        <Content style={{
          padding: 24,
          minHeight: 'calc(100vh - 64px)',
          background: '#f0f2f5',
        }}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/page-analysis" element={<PageAnalysis />} />
            <Route path="/http-request-analysis" element={<HttpRequestAnalysis />} />
            <Route path="/service-analysis" element={<ServiceAnalysis />} />
            <Route path="/host-analysis" element={<HostAnalysis />} />
            <Route path="/network-analysis" element={<NetworkAnalysis />} />
            <Route path="/topology" element={<TopologyPage />} />
            <Route path="/business-discovery" element={<BusinessDiscovery />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/cmdb" element={<CmdbPage />} />
            <Route path="/metric-browser" element={<MetricBrowserPage />} />
            <Route path="/compensation" element={<CompensationManagerPage />} />
            <Route path="/biz-mapping" element={<BizMappingPage />} />
            <Route path="/etl" element={<EtlPage />} />
            <Route path="/model-topology" element={<ModelTopology />} />
            <Route path="/model-topology/:typeName" element={<EntityTypeDetail />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

const App: React.FC = () => (
  <TimeRangeProvider>
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  </TimeRangeProvider>
);

export default App;
