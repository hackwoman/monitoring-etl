import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  FileTextOutlined,
  DatabaseOutlined,
  DashboardOutlined,
  ClusterOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import LogsPage from './pages/Logs';
import CmdbPage from './pages/Cmdb';
import OverviewPage from './pages/Overview';
import TopologyPage from './pages/Topology';
import ChatPage from './pages/Chat';

const { Header, Content, Sider } = Layout;

const App: React.FC = () => (
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
              { key: 'topology', icon: <ClusterOutlined />, label: <Link to="/topology">拓扑</Link> },
              { key: 'cmdb', icon: <DatabaseOutlined />, label: <Link to="/cmdb">CMDB</Link> },
              { key: 'logs', icon: <FileTextOutlined />, label: <Link to="/logs">日志</Link> },
              { key: 'chat', icon: <MessageOutlined />, label: <Link to="/chat">问答</Link> },
            ]}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/topology" element={<TopologyPage />} />
            <Route path="/cmdb" element={<CmdbPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  </BrowserRouter>
);

export default App;
