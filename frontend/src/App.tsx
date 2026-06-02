import { ConfigProvider, Layout, Menu, Space, Tag, Typography, theme } from 'antd';
import type { MenuProps } from 'antd';
import {
  DashboardOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  LineChartOutlined,
  ProfileOutlined,
  SettingOutlined
} from '@ant-design/icons';
import RocketOutlined from '@ant-design/icons/lib/icons/RocketOutlined';
import { AnalysisPage } from './pages/AnalysisPage';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { NewTaskWizardPage } from './pages/NewTaskWizardPage';
import { OneClickCrawlPage } from './pages/OneClickCrawlPage';
import { SettingsPage } from './pages/SettingsPage';
import { TaskDetailPage } from './pages/TaskDetailPage';
import { WorkbenchProvider, useWorkbench } from './store/workbench';
import { apiModeLabel } from './utils/format';
import './styles.css';

const { Header, Sider, Content } = Layout;

function Shell() {
  const { page, setPage, settings, tasks } = useWorkbench();
  const runningCount = tasks.filter((task) => String(task.status).toLowerCase() === 'running').length;

  const items: MenuProps['items'] = [
    { key: 'dashboard', icon: <DashboardOutlined />, label: '工作台' },
    { key: 'oneClickCrawl', icon: <RocketOutlined />, label: '一键采集' },
    { key: 'wizard', icon: <ExperimentOutlined />, label: '新建任务' },
    { key: 'analysis', icon: <ProfileOutlined />, label: '站点分析' },
    { key: 'detail', icon: <LineChartOutlined />, label: '任务详情' },
    { key: 'history', icon: <HistoryOutlined />, label: '历史任务' },
    { key: 'settings', icon: <SettingOutlined />, label: '系统设置' }
  ];

  return (
    <Layout className="app-shell">
      <Sider width={236} breakpoint="lg" collapsedWidth="0" className="app-sider">
        <div className="brand">
          <div className="brand-mark">CLM</div>
          <div>
            <Typography.Text strong>Crawler-Mind</Typography.Text>
            <div className="brand-sub">采集控制台</div>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[page]}
          items={items}
          onClick={({ key }) => setPage(key as typeof page)}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space split={<span className="header-divider" />}>
            <Typography.Text strong>CLM 商品采集工作台</Typography.Text>
            <Tag color={settings.apiMode === 'mock' ? 'purple' : 'blue'}>{apiModeLabel(settings.apiMode)}</Tag>
            <span className="muted">{settings.apiBaseUrl}</span>
            <Tag color={runningCount ? 'processing' : 'default'}>{runningCount} 个运行中</Tag>
          </Space>
        </Header>
        <Content className="app-content">{renderPage(page)}</Content>
      </Layout>
    </Layout>
  );
}

function renderPage(page: string) {
  if (page === 'oneClickCrawl') return <OneClickCrawlPage />;
  if (page === 'wizard') return <NewTaskWizardPage />;
  if (page === 'analysis') return <AnalysisPage />;
  if (page === 'detail') return <TaskDetailPage />;
  if (page === 'history') return <HistoryPage />;
  if (page === 'settings') return <SettingsPage />;
  return <DashboardPage />;
}

export default function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#2563eb'
        },
        components: {
          Card: { headerBg: '#ffffff' },
          Layout: { bodyBg: '#f4f6f8', siderBg: '#ffffff', headerBg: '#ffffff' }
        }
      }}
    >
      <WorkbenchProvider>
        <Shell />
      </WorkbenchProvider>
    </ConfigProvider>
  );
}
