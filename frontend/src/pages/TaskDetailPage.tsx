import { Alert, Button, Card, Descriptions, Empty, Input, Popconfirm, Progress, Select, Space, Table, message } from 'antd';
import { useEffect, useMemo, useState, type ChangeEvent } from 'react';
import { cancelRun, deleteRun, exportRun, fetchRunEvents, fetchRunStatus } from '../api/client';
import { AiManagedPanel } from '../components/AiManagedPanel';
import { EventTimeline } from '../components/EventTimeline';
import { MetricStrip } from '../components/MetricStrip';
import { StatusPill } from '../components/StatusPill';
import { WorkflowOverview } from '../components/WorkflowOverview';
import { useWorkbench } from '../store/workbench';
import { exportFilename, joinExportPath } from '../utils/format';
import { formatTime, managedAiModeLabel, percent, qualitySeverityLabel, replaceExportPathSuffix, statusLabel, userFacingError } from '../utils/format';
import type { ExportFormat } from '../types/workflow';
import { seedUrlRows } from '../utils/runPayload';

function isMissingRunError(error: unknown): boolean {
  const messageText = error instanceof Error ? error.message : String(error || '');
  return messageText.includes('404') || messageText.includes('Not Found') || messageText.includes('run not found');
}

export function TaskDetailPage() {
  const {
    settings,
    tasks,
    activeTaskId,
    statuses,
    events,
    updateTaskStatus,
    updateTaskEvents,
    removeTask,
    wizard,
    upsertTask
  } = useWorkbench();
  const task = tasks.find((item) => item.task_id === activeTaskId) || tasks[0];
  const [format, setFormat] = useState(wizard.export.format);
  const [outputPath, setOutputPath] = useState(wizard.export.output_path);
  const [busy, setBusy] = useState(false);
  const [polling, setPolling] = useState(true);
  const [lastRefreshAt, setLastRefreshAt] = useState('');
  const [browserDirectoryName, setBrowserDirectoryName] = useState('');

  const status = task ? statuses[task.task_id] : undefined;
  const eventList = task ? events[task.task_id]?.events || [] : [];
  const progress = status?.progress;
  const completion = progress?.completion || 0;
  const isRunning = ['running', 'queued'].includes(String(status?.status || task?.status || '').toLowerCase());
  const currentStage = statusLabel(progress?.status || status?.status || task?.status || 'unknown');
  const payload = task?.run_payload;
  const managedAi = status?.managed_ai || task?.managed_ai || payload?.managed_ai || settings.managed_ai;
  const managedMode = status?.managed_mode || task?.managed_mode || payload?.managed_ai?.mode || (settings.managed_ai.enabled ? settings.managed_ai.mode : 'deterministic');
  const aiDecisions = status?.ai_decisions || task?.ai_decisions || [];
  const aiDiagnostics = status?.ai_diagnostics || task?.ai_diagnostics || [];
  const aiRepairSuggestions = status?.ai_repair_suggestions || task?.ai_repair_suggestions || [];
  const selectedFields = payload?.selected_fields || wizard.selectedFields;
  const seedCount = payload ? seedUrlRows(payload).length : 0;
  const modelName = payload?.llm?.model || settings.llm.model || '未选择模型';

  const qualityRows = useMemo(() => {
    const quality = progress?.quality || {};
    const gate = (quality.quality_gate || {}) as Record<string, unknown>;
    return [
      { key: '质量门禁', value: qualitySeverityLabel(gate.severity) },
      { key: '重复率', value: String(quality.duplicate_rate ?? '-') },
      { key: '失败 URL 数', value: String(quality.failed_url_count ?? '-') },
      { key: '分页停止原因', value: String(quality.pagination_stop_reason ?? '-') }
    ];
  }, [progress]);

  const refresh = async (silent = false) => {
    if (!task) return;
    setBusy(true);
    try {
      const [nextStatus, nextEvents] = await Promise.all([
        fetchRunStatus(settings, task.task_id, task.run_id),
        fetchRunEvents(settings, task.task_id)
      ]);
      updateTaskStatus(nextStatus);
      updateTaskEvents(task.task_id, nextEvents);
      setLastRefreshAt(new Date().toISOString());
      if (!silent) message.success('任务状态已刷新');
    } catch (error) {
      if (isMissingRunError(error)) {
        const staleMessage = '后端没有找到这个任务。它可能来自演示模式或浏览器缓存，请重新提交一次测试任务。';
        setPolling(false);
        updateTaskStatus({
          task_id: task.task_id,
          kind: 'missing_backend_run',
          run_id: task.run_id,
          status: 'failed',
          record_count: task.record_count || 0,
                accepted: false,
                managed_mode: task.managed_mode,
                managed_ai: task.managed_ai,
                ai_decisions: task.ai_decisions,
                ai_diagnostics: task.ai_diagnostics,
                ai_repair_suggestions: task.ai_repair_suggestions,
                error: staleMessage,
          progress: {
            status: 'failed',
            records_saved: task.record_count || 0,
            failed: 0,
            queued: 0,
            done: 0,
            completion: 0
          }
        });
        if (!silent) message.warning(staleMessage);
        return;
      }
      if (!silent) message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!task || !polling || !isRunning) return undefined;
    const timer = window.setInterval(() => {
      void refresh(true);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [isRunning, polling, task?.task_id]);

  useEffect(() => {
    if (!task) return;
    const taskExport = task.export_config || wizard.export;
    setFormat(taskExport.format);
    setOutputPath(replaceExportPathSuffix(taskExport.output_path || wizard.export.output_path, taskExport.format));
    setBrowserDirectoryName(wizard.browserDirectoryName || '');
  }, [task?.task_id, task?.export_config?.format, task?.export_config?.output_path, wizard.export.format, wizard.export.output_path]);

  const syncFormat = (nextFormat: ExportFormat) => {
    setFormat(nextFormat);
    setOutputPath((current) => replaceExportPathSuffix(current, nextFormat));
  };

  const chooseExportDirectory = async () => {
    const picker = window as Window & { showDirectoryPicker?: () => Promise<{ name: string }> };
    if (!picker.showDirectoryPicker) {
      message.warning('当前浏览器不支持目录选择器。');
      return;
    }
    try {
      const handle = await picker.showDirectoryPicker();
      setBrowserDirectoryName(handle.name);
      message.success(`已选择浏览器目录：${handle.name}`);
    } catch {
      message.info('已取消目录选择');
    }
  };

  useEffect(() => {
    if (!task) return;
    void refresh(true);
  }, [task?.task_id]);

  if (!task) {
    return (
      <Card title="任务详情">
        <Empty description="还没有选中任务。请先从向导提交一次试跑。" />
      </Card>
    );
  }

  const triggerExport = async () => {
    setBusy(true);
    try {
      const finalOutputPath = replaceExportPathSuffix(outputPath, format);
      const result = await exportRun(settings, task.run_id, task.runtime_dir || settings.runtime.default_runtime_dir, {
        ...(task.export_config || wizard.export),
        format,
        output_path: finalOutputPath
      });
      setOutputPath(result.output_path || finalOutputPath);
      upsertTask({
        ...task,
        export: result,
        export_config: { ...(task.export_config || wizard.export), format, output_path: result.output_path || finalOutputPath },
        updated_at: new Date().toISOString()
      });
      message.success(`导出完成：${result.output_path}`);
    } catch (error) {
      message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const triggerCancel = async () => {
    if (!task) return;
    setBusy(true);
    try {
      const result = await cancelRun(settings, task.task_id);
      setPolling(false);
      updateTaskStatus({
        task_id: task.task_id,
        kind: status?.kind || 'product_run',
        run_id: task.run_id,
        status: result.status || 'cancelled',
        record_count: status?.record_count ?? task.record_count,
        accepted: false,
        error: '用户已终止任务',
        progress: {
          ...(status?.progress || {}),
          status: result.status || 'cancelled'
        }
      });
      message.success('已向后端发送终止请求');
    } catch (error) {
      message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const triggerRemoveLocal = async () => {
    if (!task) return;
    setBusy(true);
    try {
      await deleteRun(settings, task.task_id);
      message.success('已清除后端任务记录');
    } catch {
      message.info('后端记录未删除，仅清除了工作台本地记录');
    } finally {
      removeTask(task.task_id);
      setBusy(false);
    }
  };

  return (
    <Space direction="vertical" size={16} className="page-stack">
      <WorkflowOverview wizard={wizard} settings={settings} activeTask={task} compact />
      <Card
        title="任务详情"
        extra={
          <Space>
            <Button onClick={() => setPolling((value) => !value)}>{polling ? '暂停轮询' : '恢复轮询'}</Button>
            <Button loading={busy} onClick={() => refresh(false)}>立即刷新</Button>
            <Button danger loading={busy} disabled={!isRunning} onClick={triggerCancel}>终止任务</Button>
            <Popconfirm title="只清除工作台记录，不删除已导出的文件。确认清除？" onConfirm={triggerRemoveLocal}>
              <Button>清除记录</Button>
            </Popconfirm>
            <Button type="primary" loading={busy} onClick={triggerExport}>导出</Button>
          </Space>
        }
      >
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="任务 ID">{task.task_id}</Descriptions.Item>
          <Descriptions.Item label="运行 ID">{task.run_id}</Descriptions.Item>
          <Descriptions.Item label="目标站点">{task.target_url}</Descriptions.Item>
          <Descriptions.Item label="状态"><StatusPill status={status?.status || task.status} /></Descriptions.Item>
          <Descriptions.Item label="当前阶段">{currentStage}</Descriptions.Item>
          <Descriptions.Item label="最后刷新">{formatTime(lastRefreshAt || task.updated_at)}</Descriptions.Item>
          <Descriptions.Item label="AI 托管">{managedAiModeLabel(String(managedMode))}</Descriptions.Item>
          <Descriptions.Item label="模型">{modelName}</Descriptions.Item>
          <Descriptions.Item label="实际 seed URL 数">{seedCount}</Descriptions.Item>
          <Descriptions.Item label="字段">{selectedFields.join(', ') || '-'}</Descriptions.Item>
          <Descriptions.Item label="导出路径">{(task.export_config || wizard.export).output_path || '-'}</Descriptions.Item>
        </Descriptions>
        <div className="section-gap">
          <Progress percent={Math.round(completion * 100)} status={completion >= 1 ? 'success' : 'active'} />
        </div>
      </Card>

      <MetricStrip
        metrics={[
          { label: '记录数', value: status?.record_count ?? task.record_count },
          { label: '已完成', value: progress?.done ?? 0 },
          { label: '队列中', value: progress?.queued ?? 0 },
          { label: '完成度', value: percent(completion) }
        ]}
      />

      {status?.error ? <Alert type="error" showIcon message="任务运行失败" description={status.error} /> : null}

      <AiManagedPanel
        title="AI 托管与模型决策"
        settings={settings}
        managedMode={String(managedMode)}
        managedAi={managedAi}
        modelName={modelName}
        llmAnalysis={wizard.analysis?.llm_analysis}
        aiDecisions={aiDecisions}
        aiDiagnostics={aiDiagnostics}
        aiRepairSuggestions={aiRepairSuggestions}
      />

      <div className="two-column-grid">
        <div>
          <Card title="事件流">
            <EventTimeline events={eventList} />
          </Card>
        </div>
        <div>
          <Card title="质量与导出">
            <Table
              size="small"
              pagination={false}
              rowKey="key"
              columns={[
                { title: '指标', dataIndex: 'key', width: 180 },
                { title: '值', dataIndex: 'value' }
              ]}
              dataSource={qualityRows}
            />
            <div className="section-gap export-line">
              <Select
                value={format}
                onChange={syncFormat}
                options={['xlsx', 'csv', 'json', 'sqlite', 'db'].map((value) => ({ value, label: value }))}
              />
              <Input
                value={outputPath}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setOutputPath(event.target.value)}
                onBlur={() => setOutputPath((current) => replaceExportPathSuffix(current, format))}
              />
              <Button onClick={chooseExportDirectory}>选择目录</Button>
            </div>
            {browserDirectoryName ? <Alert type="info" showIcon message={`浏览器目录选择：${browserDirectoryName}`} /> : null}
            {task.export ? <Alert type="success" showIcon message={`导出文件：${task.export.output_path}`} /> : null}
          </Card>
        </div>
      </div>
    </Space>
  );
}
