import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { FileTextOutlined, DatabaseOutlined } from '@ant-design/icons';
import LogsPage from './pages/Logs';
import CmdbPage from './pages/Cmdb';

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
            defaultSelectedKeys={['logs']}
            style={{ height: '100%' }}
            items={[
              { key: 'logs', icon: <FileTextOutlined />, label: <Link to="/">日志查询</Link> },
              { key: 'cmdb', icon: <DatabaseOutlined />, label: <Link to="/cmdb">CMDB</Link> },
            ]}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<LogsPage />} />
            <Route path="/cmdb" element={<CmdbPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  </BrowserRouter>
);

export default App;
