import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  FileTextOutlined, DatabaseOutlined, DashboardOutlined,
  ClusterOutlined, MessageOutlined, AlertOutlined,
  ApiOutlined, DesktopOutlined, CloudServerOutlined,
  EyeOutlined, ThunderboltOutlined, MonitorOutlined,
  TagOutlined, ToolOutlined, SearchOutlined, ApartmentOutlined,
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
import LogicalTopologyPage from './pages/LogicalTopology';
import { TimeRangeProvider } from './components/TimeRangeContext';

const { Header, Content, Sider } = Layout;

const App: React.FC = () => (
  <TimeRangeProvider>
  <BrowserRouter>
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ color: '#fff', fontSize: 20, fontWeight: 'bold' }}>
        🔍 Monitoring ETL Platform
      </Header>
      <Layout>
        <Sider width={200}>
          <Menu
            mode="inline"
            defaultSelectedKeys={['overview']}
            defaultOpenKeys={['entity-monitor']}
            style={{ height: '100%' }}
            items={[
              { key: 'overview', icon: <DashboardOutlined />, label: <Link to="/">总览</Link> },
              {
                key: 'entity-monitor', icon: <MonitorOutlined />, label: '实体监控',
                children: [
                  { key: 'page', icon: <EyeOutlined />, label: <Link to="/page-analysis">页面分析</Link> },
                  { key: 'http', icon: <ThunderboltOutlined />, label: <Link to="/http-request-analysis">网络请求</Link> },
                  { key: 'service', icon: <ApiOutlined />, label: <Link to="/service-analysis">服务分析</Link> },
                  { key: 'host', icon: <DesktopOutlined />, label: <Link to="/host-analysis">主机分析</Link> },
                  { key: 'network', icon: <CloudServerOutlined />, label: <Link to="/network-analysis">网络分析</Link> },
                ],
              },
              { key: 'topology', icon: <ClusterOutlined />, label: <Link to="/topology">拓扑</Link> },
              { key: 'logical-topology', icon: <ApartmentOutlined />, label: <Link to="/logical-topology">业务拓扑</Link> },
              { key: 'biz-discovery', icon: <SearchOutlined />, label: <Link to="/business-discovery">业务发现</Link> },
              { key: 'alerts', icon: <AlertOutlined />, label: <Link to="/alerts">告警</Link> },
              { key: 'cmdb', icon: <DatabaseOutlined />, label: <Link to="/cmdb">CMDB</Link> },
              { key: 'biz-mapping', icon: <TagOutlined />, label: <Link to="/biz-mapping">业务映射</Link> },
              { key: 'etl', icon: <ToolOutlined />, label: <Link to="/etl">智能ETL</Link> },
              { key: 'logs', icon: <FileTextOutlined />, label: <Link to="/logs">日志</Link> },
              { key: 'chat', icon: <MessageOutlined />, label: <Link to="/chat">问答</Link> },
            ]}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/page-analysis" element={<PageAnalysis />} />
            <Route path="/http-request-analysis" element={<HttpRequestAnalysis />} />
            <Route path="/service-analysis" element={<ServiceAnalysis />} />
            <Route path="/host-analysis" element={<HostAnalysis />} />
            <Route path="/network-analysis" element={<NetworkAnalysis />} />
            <Route path="/topology" element={<TopologyPage />} />
            <Route path="/logical-topology" element={<LogicalTopologyPage />} />
            <Route path="/business-discovery" element={<BusinessDiscovery />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/cmdb" element={<CmdbPage />} />
            <Route path="/biz-mapping" element={<BizMappingPage />} />
            <Route path="/etl" element={<EtlPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  </BrowserRouter>
  </TimeRangeProvider>
);

export default App;
