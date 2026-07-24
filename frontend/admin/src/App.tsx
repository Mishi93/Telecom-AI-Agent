import { Layout, Menu } from "antd";
import {
  TeamOutlined,
  DashboardOutlined,
  BarChartOutlined,
} from "@ant-design/icons";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import AdminPortal from "./pages/AdminPortal";
import CustomerDashboard from "./pages/CustomerDashboard";
import Analytics from "./pages/Analytics";

const { Header, Content, Sider } = Layout;

function App() {
  const location = useLocation();

  const menuItems = [
    { key: "/", icon: <TeamOutlined />, label: <Link to="/">Manage Customers</Link> },
    { key: "/dashboard", icon: <DashboardOutlined />, label: <Link to="/dashboard">Customer Dashboard</Link> },
    { key: "/analytics", icon: <BarChartOutlined />, label: <Link to="/analytics">Analytics</Link> },
  ];

  return (
    <Layout className="min-h-screen">
      <Header className="flex items-center">
        <span className="text-white text-lg font-semibold">
          ⚙️ Telecom Admin Portal
        </span>
      </Header>
      <Layout>
        <Sider width={220} theme="light" className="border-r border-gray-200">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            className="h-full pt-2"
          />
        </Sider>
        <Layout className="p-6">
          <Content className="bg-white rounded-lg p-6 shadow-sm">
            <Routes>
              <Route path="/" element={<AdminPortal />} />
              <Route path="/dashboard" element={<CustomerDashboard />} />
              <Route path="/analytics" element={<Analytics />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}

export default App;
