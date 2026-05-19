import { Card, Steps, Table, Tag } from 'antd';
import type { RunRequest, WizardState, WorkbenchTask } from '../types/workflow';
import { catalogCount } from '../store/workbench';
import { statusLabel } from '../utils/format';
import { buildRunPayload, runPayloadSummary, seedUrlRows } from '../utils/runPayload';
import type { SettingsState } from '../types/workflow';

interface Props {
  wizard: WizardState;
  settings: SettingsState;
  activeTask?: WorkbenchTask;
  payload?: RunRequest;
  compact?: boolean;
}

function stepStatus(done: boolean, active: boolean): 'wait' | 'process' | 'finish' {
  if (done) return 'finish';
  if (active) return 'process';
  return 'wait';
}

export function WorkflowOverview({ wizard, settings, activeTask, payload, compact = false }: Props) {
  const currentPayload = payload || buildRunPayload(wizard, settings);
  const hasTarget = Boolean(wizard.targetUrl);
  const hasAnalysis = wizard.analysisStatus === 'completed' && Boolean(wizard.analysis);
  const hasFields = wizard.selectedFields.length > 0;
  const hasRun = Boolean(activeTask || wizard.lastRunPayload);
  const isRunning = ['running', 'queued'].includes(String(activeTask?.status || '').toLowerCase());
  const isFinished = ['completed', 'failed', 'cancelled'].includes(String(activeTask?.status || '').toLowerCase());

  const items = [
    { title: '目标', status: stepStatus(hasTarget, !hasTarget) },
    { title: '站点分析', status: stepStatus(hasAnalysis, hasTarget && !hasAnalysis) },
    { title: '目录字段', status: stepStatus(hasFields, hasAnalysis && !hasFields) },
    { title: '启动任务', status: stepStatus(hasRun, hasFields && !hasRun) },
    { title: '运行监控', status: stepStatus(isFinished, isRunning) },
    { title: '导出结果', status: stepStatus(Boolean(activeTask?.export), isFinished && !activeTask?.export) }
  ] as const;

  return (
    <Card title="工作流总览" className="workflow-card">
      <Steps size="small" items={items.map((item) => ({ title: item.title, status: item.status }))} />
      <div className="workflow-meta">
        <Tag color={hasAnalysis ? 'success' : 'blue'}>分析状态：{statusLabel(wizard.analysisStatus || 'idle')}</Tag>
        <Tag color={catalogCount(wizard.catalogTree) ? 'success' : 'default'}>目录节点：{catalogCount(wizard.catalogTree)}</Tag>
        <Tag color={wizard.selectedFields.length ? 'success' : 'default'}>字段：{wizard.selectedFields.length}</Tag>
        <Tag color={activeTask ? 'processing' : 'default'}>任务：{activeTask ? statusLabel(activeTask.status) : '未提交'}</Tag>
      </div>
      {!compact ? (
        <div className="two-column-grid section-gap">
          <Table
            size="small"
            pagination={false}
            rowKey="key"
            columns={[
              { title: '启动参数', dataIndex: 'key', width: 150 },
              { title: '值', dataIndex: 'value' }
            ]}
            dataSource={runPayloadSummary(currentPayload)}
          />
          <Table
            size="small"
            pagination={{ pageSize: 6, hideOnSinglePage: true }}
            rowKey="index"
            columns={[
              { title: '#', dataIndex: 'index', width: 64 },
              { title: '实际会采集的 seed URL', dataIndex: 'url', ellipsis: true }
            ]}
            dataSource={seedUrlRows(currentPayload)}
          />
        </div>
      ) : null}
    </Card>
  );
}
