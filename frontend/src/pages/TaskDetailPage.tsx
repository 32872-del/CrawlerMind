import { Alert, Button, Card, Descriptions, Empty, Input, List, Popconfirm, Progress, Select, Space, Table, Tag, Typography, message } from 'antd';
import { useEffect, useMemo, useState, type ChangeEvent } from 'react';
import { cancelRun, deleteRun, exportRun, fetchRunEvents, fetchRunStatus, managedRepairRun, managedStep } from '../api/client';
import { AiManagedPanel } from '../components/AiManagedPanel';
import { DiagnosisPanel } from '../components/DiagnosisPanel';
import { EventTimeline } from '../components/EventTimeline';
import { MetricStrip } from '../components/MetricStrip';
import { StatusPill } from '../components/StatusPill';
import { WorkflowOverview } from '../components/WorkflowOverview';
import { useWorkbench } from '../store/workbench';
import { formatTime, managedAiModeLabel, percent, qualitySeverityLabel, replaceExportPathSuffix, statusLabel, userFacingError } from '../utils/format';
import type { ExportFormat, ManagedActionRecord, ManagedStepRecord } from '../types/workflow';
import { seedUrlRows } from '../utils/runPayload';

function isMissingRunError(error: unknown): boolean {
  const messageText = error instanceof Error ? error.message : String(error || '');
  return messageText.includes('404') || messageText.includes('Not Found') || messageText.includes('run not found');
}

const actionLabels: Record<string, string> = {
  reanalyze_site: '重新分析站点',
  discover_catalog: '重新分析目录',
  probe_fields: '探测字段',
  inspect_access: '检查访问状态',
  repair_selectors: '修复字段选择器',
  adjust_runtime: '切换动态模式',
  evaluate_quality: '评估质量门',
  prepare_export: '准备导出',
  prepare_rerun: '准备重跑',
  patch_profile: '修补 Profile',
  extract_from_contract: '按抽取合同提取商品'
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function actionName(value: unknown): string {
  const name = String(value || '').trim();
  return actionLabels[name] || name || '-';
}

function humanError(value: unknown): string {
  const text = String(value || '').trim();
  if (!text) return '';
  if (text.includes('missing extraction contract')) return '缺少抽取合同，请先生成或传入 extraction contract。';
  if (text.includes('missing extraction evidence')) return '缺少抽取证据，请先提供页面 HTML、接口 JSON 或浏览器采样证据。';
  if (text.includes('unsupported parser_strategy.name')) return `抽取策略暂不支持：${text.replace('unsupported parser_strategy.name:', '').trim() || '未命名策略'}`;
  return text;
}

function paramsSummary(value: unknown): string {
  const params = asRecord(value);
  if (!Object.keys(params).length) return '-';
  const contract = asRecord(params.contract);
  const strategy = asRecord(contract.parser_strategy);
  const pieces = [
    contract.site ? `站点 ${String(contract.site)}` : '',
    strategy.name ? `策略 ${String(strategy.name)}` : '',
    params.source_url ? `来源 ${String(params.source_url)}` : '',
    params.max_items ? `最多 ${String(params.max_items)} 条` : ''
  ].filter(Boolean);
  return pieces.length ? pieces.join('；') : JSON.stringify(params);
}

function actionResultFor(action: Record<string, unknown>, results: unknown[]): Record<string, unknown> {
  const name = String(action.action || '');
  return asRecord(results.find((item) => String(asRecord(item).action || '') === name));
}

function fieldCoverageText(value: unknown): string {
  const fields = Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
  return fields.length ? `${fields.length} 个字段：${fields.join('、')}` : '暂无字段覆盖记录';
}

function findContractExtraction(records: ManagedActionRecord[]): Record<string, unknown> {
  for (const record of [...records].reverse()) {
    const result = asRecord(record.result);
    const extraction = asRecord(asRecord(result.run_overrides).extraction_result);
    if (extraction.schema_version === 'contract-extraction-result/v1' || extraction.item_count !== undefined) return extraction;
    const results = Array.isArray(result.results) ? result.results : [];
    for (const item of results) {
      const actionResult = asRecord(item);
      const evidence = asRecord(actionResult.evidence);
      if (actionResult.action === 'extract_from_contract' && Object.keys(evidence).length) {
        return {
          schema_version: 'contract-extraction-result/v1',
          site: evidence.contract_site,
          parser_strategy: evidence.parser_strategy,
          item_count: evidence.item_count,
          fields_found: evidence.fields_found,
          items: Array.isArray(evidence.sample_items) ? evidence.sample_items : actionResult.extracted_items
        };
      }
    }
  }
  return {};
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
  const llmTraces = status?.llm_traces || task?.llm_traces || [];
  const managedActions = status?.managed_actions || task?.managed_actions || [];
  const managedSteps = status?.managed_steps || task?.managed_steps || [];
  const evidencePack = status?.evidence_pack || task?.evidence_pack || {};
  const accessEvidenceRequest = (evidencePack.access_evidence_request || {}) as Record<string, unknown>;
  const managedAutoRepair = status?.managed_auto_repair || task?.managed_auto_repair || null;
  const parentTaskId = status?.parent_task_id || task?.parent_task_id || '';
  const repairSource = status?.repair_source || task?.repair_source || '';
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
          managed_actions: task.managed_actions,
          managed_auto_repair: task.managed_auto_repair,
          parent_task_id: task.parent_task_id,
          repair_source: task.repair_source,
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

  const triggerManagedRepairRun = async () => {
    if (!task) return;
    setBusy(true);
    try {
      const runKind: 'test' | 'full' = task.mode === 'full' ? 'full' : 'test';
      const result = await managedRepairRun(settings, task.task_id, {
        execute: true,
        use_llm: Boolean(settings.llm.base_url && settings.llm.model),
        run_kind: runKind,
        apply_diagnostics: true,
        extra_context: {
          field_goal: wizard.fieldGoal,
          selected_fields: selectedFields,
          imported_catalog: wizard.importedCatalog,
          export: {
            ...(task.export_config || wizard.export),
            format,
            output_path: replaceExportPathSuffix(outputPath, format)
          }
        },
        managed_ai: settings.managed_ai,
        llm: {
          enabled: Boolean(settings.llm.base_url && settings.llm.model),
          provider: settings.llm.provider,
          base_url: settings.llm.base_url,
          api_key: settings.llm.api_key,
          model: settings.llm.model,
          reasoning_effort: settings.llm.reasoning_effort,
          stream: settings.llm.stream,
          timeout_seconds: settings.llm.timeout_seconds,
          max_tokens: settings.llm.max_tokens
        }
      });
      const childTask = {
        ...task,
        task_id: result.task_id,
        run_id: result.run_id,
        status: result.status,
        mode: runKind,
        record_count: 0,
        accepted: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        parent_task_id: result.parent_task_id || task.task_id,
        repair_source: result.repair_source || 'managed_actions',
        managed_actions: result.managed_action ? [...managedActions, result.managed_action] : task.managed_actions,
        run_payload: task.run_payload
          ? {
              ...task.run_payload,
              selected_fields: selectedFields,
              export: {
                ...(task.export_config || wizard.export),
                format,
                output_path: replaceExportPathSuffix(outputPath, format)
              }
            }
          : task.run_payload,
        error: ''
      };
      upsertTask(childTask);
      setPolling(true);
      message.success('AI 托管修复任务已启动');
    } catch (error) {
      message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const triggerManagedStep = async () => {
    if (!task) return;
    setBusy(true);
    try {
      const runKind: 'test' | 'full' = task.mode === 'full' ? 'full' : 'test';
      const result = await managedStep(settings, task.task_id, {
        execute: true,
        use_llm: Boolean(settings.llm.base_url && settings.llm.model),
        start_child_run: false,
        run_kind: runKind,
        apply_diagnostics: true,
        extra_context: {
          field_goal: wizard.fieldGoal,
          selected_fields: selectedFields,
          imported_catalog: wizard.importedCatalog,
          export: {
            ...(task.export_config || wizard.export),
            format,
            output_path: replaceExportPathSuffix(outputPath, format)
          }
        },
        managed_ai: settings.managed_ai,
        llm: {
          enabled: Boolean(settings.llm.base_url && settings.llm.model),
          provider: settings.llm.provider,
          base_url: settings.llm.base_url,
          api_key: settings.llm.api_key,
          model: settings.llm.model,
          reasoning_effort: settings.llm.reasoning_effort,
          stream: settings.llm.stream,
          timeout_seconds: settings.llm.timeout_seconds,
          max_tokens: settings.llm.max_tokens
        }
      });
      upsertTask({
        ...task,
        managed_steps: [...managedSteps, result],
        managed_actions: result.action_record ? [...managedActions, result.action_record] : managedActions,
        evidence_pack: result.evidence_pack || evidencePack,
        updated_at: new Date().toISOString()
      });
      await refresh(true);
      message.success('AI 已执行一个托管步骤');
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
            <Button loading={busy} disabled={isRunning} onClick={triggerManagedRepairRun}>AI 托管修复并重跑</Button>
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
        title="AI 托管驾驶舱"
        settings={settings}
        status={status?.status || task.status}
        recordCount={status?.record_count ?? task.record_count}
        progress={progress}
        managedMode={String(managedMode)}
        managedAi={managedAi}
        modelName={modelName}
        llmAnalysis={wizard.analysis?.llm_analysis}
        aiDecisions={aiDecisions}
        aiDiagnostics={aiDiagnostics}
        aiRepairSuggestions={aiRepairSuggestions}
        llmTraces={llmTraces}
        managedActions={managedActions}
        managedAutoRepair={managedAutoRepair}
        parentTaskId={parentTaskId}
        repairSource={repairSource}
        onManagedRepairRun={triggerManagedRepairRun}
        onManagedStep={triggerManagedStep}
        repairLoading={busy}
        repairDisabled={isRunning}
      />

      <DiagnosisPanel
        settings={settings}
        taskId={task.task_id}
        llm={{
          enabled: Boolean(settings.llm.base_url && settings.llm.model),
          provider: settings.llm.provider,
          base_url: settings.llm.base_url,
          api_key: settings.llm.api_key,
          model: settings.llm.model
        }}
      />

      <ManagedActionTable records={managedActions} />
      <ManagedStepTable records={managedSteps} evidencePack={evidencePack} accessEvidenceRequest={accessEvidenceRequest} />

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

function ManagedActionTable({ records }: { records: ManagedActionRecord[] }) {
  const rows = records.flatMap((record, recordIndex) => {
    const plan = record.result?.plan || {};
    const actions = Array.isArray(plan.actions) ? plan.actions : [];
    const results = Array.isArray(record.result?.results) ? record.result?.results || [] : [];
    return actions.map((item, actionIndex) => {
      const action = asRecord(item);
      const result = actionResultFor(action, results);
      const failed = result.ok === false;
      return {
        key: `${record.created_at || recordIndex}-${actionIndex}`,
        time: record.created_at || '-',
        source: String(plan.source || '-'),
        action: action.action,
        reason: action.reason,
        params: action.params,
        status: failed ? '失败' : Object.keys(result).length ? '已执行' : record.executed ? '等待结果' : '已规划',
        result: failed ? humanError(result.error) : String(result.summary || result.message || (Object.keys(result).length ? '已返回执行结果' : '-')),
        rerun_ready: Boolean(record.result?.rerun_ready)
      };
    });
  });
  const extraction = findContractExtraction(records);
  const extractionItems = Array.isArray(extraction.items) ? extraction.items.slice(0, 5).map((item) => asRecord(item)) : [];

  return (
    <Card title="托管动作完整记录">
      {rows.length ? (
        <Table
          size="small"
          pagination={false}
          dataSource={rows}
          columns={[
            { title: '时间', dataIndex: 'time', width: 220 },
            { title: '来源', dataIndex: 'source', width: 120 },
            { title: '动作名称', dataIndex: 'action', width: 180, render: (value: unknown) => actionName(value) },
            { title: 'Reason', dataIndex: 'reason' },
            { title: 'Params 摘要', dataIndex: 'params', render: (value: unknown) => paramsSummary(value) },
            {
              title: '执行状态',
              dataIndex: 'status',
              width: 110,
              render: (value: string) => <Tag color={value === '失败' ? 'error' : value === '已执行' ? 'success' : 'default'}>{value}</Tag>
            },
            { title: '执行结果', dataIndex: 'result' },
            {
              title: '可重跑',
              dataIndex: 'rerun_ready',
              width: 100,
              render: (value: boolean) => <Tag color={value ? 'success' : 'default'}>{value ? '是' : '否'}</Tag>
            }
          ]}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无托管动作记录" />
      )}
      {Object.keys(extraction).length ? (
        <div className="section-gap">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="抽取策略">{String(extraction.parser_strategy || '未记录')}</Descriptions.Item>
            <Descriptions.Item label="站点">{String(extraction.site || '未记录')}</Descriptions.Item>
            <Descriptions.Item label="抽取条数">{String(extraction.item_count ?? extractionItems.length)}</Descriptions.Item>
            <Descriptions.Item label="字段覆盖">{fieldCoverageText(extraction.fields_found)}</Descriptions.Item>
          </Descriptions>
          {extractionItems.length ? (
            <List
              className="section-gap-small"
              size="small"
              header="前 5 条样例商品"
              dataSource={extractionItems}
              renderItem={(item) => (
                <List.Item>
                  <Typography.Text>{`${String(item.title || '-')} / ${String(item.highest_price ?? '-')} / ${String(item.color || '-')}`}</Typography.Text>
                </List.Item>
              )}
            />
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

function ManagedStepTable({
  records,
  evidencePack,
  accessEvidenceRequest
}: {
  records: ManagedStepRecord[];
  evidencePack: Record<string, unknown>;
  accessEvidenceRequest: Record<string, unknown>;
}) {
  const focus = Array.isArray(evidencePack.recommended_focus) ? evidencePack.recommended_focus.map((item) => String(item)) : [];
  const failureEvidence = (evidencePack.failure_evidence || {}) as Record<string, unknown>;
  const failureBuckets = (failureEvidence.failure_buckets || {}) as Record<string, unknown>;
  const accessEvidence = (evidencePack.access_evidence || {}) as Record<string, unknown>;
  const accessSummary = (accessEvidence.summary || {}) as Record<string, unknown>;
  const xhrSamples = Array.isArray(accessEvidence.xhr_samples) ? accessEvidence.xhr_samples : [];
  const runtimeEvents = Array.isArray(accessEvidence.runtime_events) ? accessEvidence.runtime_events : [];
  const missingEvidence = Array.isArray(accessSummary.missing_evidence) ? accessSummary.missing_evidence.map((item) => String(item)) : [];
  const decisionHints = Array.isArray(accessEvidence.decision_hints) ? accessEvidence.decision_hints.map((item) => String(item)) : [];
  const rows = records.map((record, index) => {
    const actions = record.action_record?.result?.plan?.actions || [];
    return {
      key: `${record.created_at || index}`,
      time: record.created_at || '-',
      stage: record.stage || '-',
      status_before: record.status_before || '-',
      action_count: Array.isArray(actions) ? actions.length : 0,
      child: record.child_run?.task_id || '-'
    };
  });

  return (
    <Card title="AI 托管步骤与证据包">
      {focus.length || Object.keys(failureBuckets).length || Object.keys(accessEvidence).length ? (
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="建议关注">
            <Space wrap>{focus.length ? focus.map((item) => <Tag key={item}>{item}</Tag>) : '-'}</Space>
          </Descriptions.Item>
          <Descriptions.Item label="失败桶">{Object.keys(failureBuckets).length ? JSON.stringify(failureBuckets) : '-'}</Descriptions.Item>
          <Descriptions.Item label="证据采样请求" span={2}>
            {Object.keys(accessEvidenceRequest).length ? JSON.stringify(accessEvidenceRequest) : '-'}
          </Descriptions.Item>
        </Descriptions>
      ) : null}
      {rows.length ? (
        <Table
          className="section-gap-small"
          size="small"
          pagination={false}
          dataSource={rows}
          columns={[
            { title: '时间', dataIndex: 'time', width: 220 },
            { title: '阶段', dataIndex: 'stage', width: 160 },
            { title: '执行前状态', dataIndex: 'status_before', width: 120 },
            { title: '动作数', dataIndex: 'action_count', width: 90 },
            { title: '子任务', dataIndex: 'child' }
          ]}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 AI 托管步骤" />
      )}
    </Card>
  );
}
