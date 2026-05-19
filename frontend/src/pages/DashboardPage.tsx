import { Alert, Button, Card, Space, Table, Tag } from 'antd';
import {
  DownloadOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  SettingOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { MetricStrip } from '../components/MetricStrip';
import { StatusPill } from '../components/StatusPill';
import { WorkflowOverview } from '../components/WorkflowOverview';
import { useWorkbench } from '../store/workbench';
import type { WorkbenchTask } from '../types/workflow';
import { apiModeLabel, formatTime, runModeLabel } from '../utils/format';

export function DashboardPage() {
  const { settings, tasks, setPage, setActiveTaskId, wizard } = useWorkbench();
  const running = tasks.filter((task) => String(task.status).toLowerCase() === 'running');
  const completed = tasks.filter((task) => String(task.status).toLowerCase() === 'completed');
  const failed = tasks.filter((task) => String(task.status).toLowerCase() === 'failed');
  const modelReady = Boolean(settings.llm.base_url && settings.llm.model);

  const columns: ColumnsType<WorkbenchTask> = [
    { title: '任务', dataIndex: 'task_id', width: 130 },
    { title: '目标站点', dataIndex: 'target_url', ellipsis: true },
    { title: '模式', dataIndex: 'mode', width: 100, render: (value) => <Tag>{runModeLabel(value)}</Tag> },
    { title: '状态', dataIndex: 'status', width: 120, render: (value) => <StatusPill status={value} /> },
    { title: '记录数', dataIndex: 'record_count', width: 100 },
    { title: '更新时间', dataIndex: 'updated_at', width: 170, render: (value, task) => formatTime(value || task.created_at) },
    {
      title: '',
      width: 100,
      render: (_, task) => (
        <Button
          size="small"
          onClick={() => {
            setActiveTaskId(task.task_id);
            setPage('detail');
          }}
        >
          查看
        </Button>
      )
    }
  ];

  return (
    <Space direction="vertical" size={16} className="page-stack">
      <WorkflowOverview wizard={wizard} settings={settings} activeTask={tasks.find((task) => task.task_id === tasks[0]?.task_id)} />

      <div className="dashboard-grid">
        <div>
          <Card title="运行总览" extra={<Tag color={settings.apiMode === 'live' ? 'green' : 'blue'}>{apiModeLabel(settings.apiMode)}</Tag>}>
            <MetricStrip
              metrics={[
                { label: '任务总数', value: tasks.length },
                { label: '运行中', value: running.length },
                { label: '已完成', value: completed.length },
                { label: '失败', value: failed.length }
              ]}
            />
            <div className="section-gap">
              <Alert
                type={modelReady ? 'success' : 'warning'}
                showIcon
                message={modelReady ? `LLM 已配置：${settings.llm.model}` : '尚未选择 LLM 模型，可以先用演示数据跑通工作流。'}
              />
            </div>
            <div className="quick-actions">
              <Button type="primary" icon={<ExperimentOutlined />} onClick={() => setPage('wizard')}>
                新建采集任务
              </Button>
              <Button icon={<HistoryOutlined />} onClick={() => setPage('history')}>
                历史任务
              </Button>
              <Button icon={<DownloadOutlined />} onClick={() => setPage('detail')}>
                导出结果
              </Button>
              <Button icon={<SettingOutlined />} onClick={() => setPage('settings')}>
                设置
              </Button>
            </div>
          </Card>
        </div>
        <div>
          <Card title="当前配置" className="dense-card">
            <dl className="config-list">
              <dt>后端 API</dt>
              <dd>{settings.apiBaseUrl}</dd>
              <dt>模型</dt>
              <dd>{settings.llm.model || '未配置'}</dd>
              <dt>运行目录</dt>
              <dd>{settings.runtime.default_runtime_dir}</dd>
              <dt>导出目录</dt>
              <dd>{settings.runtime.default_export_dir}</dd>
              <dt>浏览器模式</dt>
              <dd>{settings.runtime.browser_enabled ? '开启' : '关闭'}</dd>
              <dt>并发 worker</dt>
              <dd>{settings.runtime.item_workers}</dd>
            </dl>
          </Card>
        </div>
      </div>

      <div className="dashboard-grid secondary">
        <Card title="首次使用检查">
          <div className="check-list">
            <div><Tag color={settings.apiBaseUrl ? 'success' : 'warning'}>1</Tag> 后端地址：{settings.apiBaseUrl || '未填写'}</div>
            <div><Tag color={settings.llm.model ? 'success' : 'warning'}>2</Tag> LLM 模型：{settings.llm.model || '可先点击“获取模型列表”'}</div>
            <div><Tag color={settings.runtime.default_export_dir ? 'success' : 'warning'}>3</Tag> 导出目录：{settings.runtime.default_export_dir}</div>
            <div><Tag color="processing">4</Tag> 建议先跑 100 条试跑，再切全量运行。</div>
          </div>
        </Card>
        <Card title="当前能力">
          <div className="check-list">
            <div><Tag color="blue">可用</Tag> 站点分析、字段选择、任务提交、状态查询、结果导出</div>
            <div><Tag color="gold">注意</Tag> 动态目录、强反爬站点仍建议先走分析页确认目录与 seed URL</div>
            <div><Tag color="red">限制</Tag> 终止、清除、导出路径检查依赖后端可访问路径</div>
          </div>
        </Card>
      </div>

      <Card title="最近任务" extra={<Button icon={<PlayCircleOutlined />} onClick={() => setPage('wizard')}>开始试跑</Button>}>
        <Table
          size="small"
          rowKey="task_id"
          columns={columns}
          dataSource={tasks.slice(0, 8)}
          pagination={false}
          locale={{ emptyText: '还没有任务。请先从“新建采集任务”开始。' }}
        />
      </Card>
    </Space>
  );
}
