import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  FileTextOutlined, DatabaseOutlined, DashboardOutlined,
  ClusterOutlined, MessageOutlined, AlertOutlined,
  ApiOutlined, DesktopOutlined, CloudServerOutlined,
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
            style={{ height: '100%' }}
            items={[
              { key: 'overview', icon: <DashboardOutlined />, label: <Link to="/">总览</Link> },
              { key: 'service', icon: <ApiOutlined />, label: <Link to="/service-analysis">服务分析</Link> },
              { key: 'host', icon: <DesktopOutlined />, label: <Link to="/host-analysis">主机分析</Link> },
              { key: 'network', icon: <CloudServerOutlined />, label: <Link to="/network-analysis">网络分析</Link> },
              { key: 'topology', icon: <ClusterOutlined />, label: <Link to="/topology">拓扑</Link> },
              { key: 'alerts', icon: <AlertOutlined />, label: <Link to="/alerts">告警</Link> },
              { key: 'cmdb', icon: <DatabaseOutlined />, label: <Link to="/cmdb">CMDB</Link> },
              { key: 'logs', icon: <FileTextOutlined />, label: <Link to="/logs">日志</Link> },
              { key: 'chat', icon: <MessageOutlined />, label: <Link to="/chat">问答</Link> },
            ]}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/service-analysis" element={<ServiceAnalysis />} />
            <Route path="/host-analysis" element={<HostAnalysis />} />
            <Route path="/network-analysis" element={<NetworkAnalysis />} />
            <Route path="/topology" element={<TopologyPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/cmdb" element={<CmdbPage />} />
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
