import { Alert, Button, Card, Collapse, Descriptions, Empty, List, Space, Table, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type {
  ManagedActionRecord,
  ManagedAiPayload,
  ManagedAutoRepairRecord,
  LlmTraceRecord,
  RunProgress,
  SettingsState
} from '../types/workflow';
import { formatTime, managedAiModeLabel, percent, qualitySeverityLabel } from '../utils/format';

interface Props {
  title?: string;
  settings?: SettingsState;
  status?: string;
  recordCount?: number;
  progress?: RunProgress;
  managedMode?: string;
  managedAi?: ManagedAiPayload | Record<string, unknown>;
  modelName?: string;
  llmAnalysis?: Record<string, unknown>;
  aiDecisions?: unknown[];
  aiDiagnostics?: unknown[] | Record<string, unknown> | null;
  aiRepairSuggestions?: unknown[];
  llmTraces?: LlmTraceRecord[];
  managedActions?: ManagedActionRecord[];
  managedAutoRepair?: ManagedAutoRepairRecord | null;
  parentTaskId?: string;
  repairSource?: string;
  onManagedStep?: () => void;
  onManagedRepairRun?: () => void;
  repairLoading?: boolean;
  repairDisabled?: boolean;
}

interface TextRow {
  index: number;
  title: string;
  description: string;
  detail?: string;
  tags?: string[];
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

const priorityLabels: Record<string, string> = {
  high: '高优先级',
  medium: '中优先级',
  low: '低优先级'
};

const sensitiveKeyPattern = /(api[_-]?key|authorization|cookie|password|secret|token)/i;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (value && typeof value === 'object') return [value];
  if (value === undefined || value === null || value === '') return [];
  return [value];
}

function sanitizeValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map((item) => sanitizeValue(item));
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => [
      key,
      sensitiveKeyPattern.test(key) ? '已隐藏' : sanitizeValue(item)
    ])
  );
}

function stringifyDetail(value: unknown): string {
  if (value === undefined || value === null || value === '') return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(sanitizeValue(value), null, 2);
}

function humanError(value: unknown): string {
  const text = String(value || '').trim();
  if (!text) return '';
  if (text.includes('missing extraction contract')) return '缺少抽取合同，请先让后端生成或传入 extraction contract。';
  if (text.includes('missing extraction evidence')) return '缺少抽取证据，请先提供页面 HTML、接口 JSON 或浏览器采样证据。';
  if (text.includes('unsupported parser_strategy.name')) return `抽取策略暂不支持：${text.replace('unsupported parser_strategy.name:', '').trim() || '未命名策略'}`;
  if (text.includes('HTTP 404') || text.includes('run not found')) return '后端没有找到这个任务，可能任务已过期或当前页面来自本地缓存。';
  return text;
}

function firstText(record: Record<string, unknown>, keys: string[], fallback = ''): string {
  for (const key of keys) {
    const value = record[key];
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      const joined = value.map((item) => stringifyDetail(item)).filter(Boolean).join('；');
      if (joined) return joined;
    } else if (typeof value === 'object') {
      const text = firstText(asRecord(value), ['message', 'summary', 'reasoning_summary', 'rationale', 'reason', 'description']);
      if (text) return text;
    } else {
      return String(value);
    }
  }
  return fallback;
}

function compactText(value: unknown, fallback = '暂无说明'): string {
  if (value === undefined || value === null || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  const record = asRecord(value);
  return firstText(record, ['decision', 'message', 'summary', 'reasoning_summary', 'suggestion', 'rationale', 'reason', 'status_assessment'], fallback);
}

function actionName(value: unknown): string {
  const name = String(value || '').trim();
  return actionLabels[name] || name || '建议动作';
}

function paramsSummary(value: unknown): string {
  const params = asRecord(value);
  if (!Object.keys(params).length) return '-';
  const summary: string[] = [];
  const contract = asRecord(params.contract);
  if (contract.site) summary.push(`站点 ${String(contract.site)}`);
  const strategy = asRecord(contract.parser_strategy);
  if (strategy.name) summary.push(`策略 ${String(strategy.name)}`);
  if (params.source_url) summary.push(`来源 ${String(params.source_url)}`);
  if (params.max_items) summary.push(`最多 ${String(params.max_items)} 条`);
  if (params.mode) summary.push(`运行模式 ${String(params.mode)}`);
  if (params.wait_until) summary.push(`等待 ${String(params.wait_until)}`);
  const fields = Array.isArray(params.fields) ? params.fields.map((item) => String(item)).join(', ') : '';
  if (fields) summary.push(`字段 ${fields}`);
  if (summary.length) return summary.join('；');
  return stringifyDetail(params);
}

function actionResultFor(action: Record<string, unknown>, results: unknown[]): Record<string, unknown> {
  const name = String(action.action || '');
  const matched = results.find((item) => {
    const record = asRecord(item);
    return String(record.action || '') === name;
  });
  return asRecord(matched);
}

function actionStatus(action: Record<string, unknown>, results: unknown[], executed: boolean | undefined): { label: string; color: string; error?: string } {
  const result = actionResultFor(action, results);
  if (Object.keys(result).length) {
    if (result.ok === false) return { label: '失败', color: 'error', error: humanError(result.error) };
    return { label: '已执行', color: 'success' };
  }
  if (executed) return { label: '等待结果', color: 'processing' };
  return { label: '已规划', color: 'default' };
}

function resultSummary(record: Record<string, unknown>): string {
  if (!Object.keys(record).length) return '暂无执行结果';
  if (record.error) return humanError(record.error);
  return firstText(record, ['summary', 'message', 'reason'], stringifyDetail(record));
}

function findContractExtraction(records: ManagedActionRecord[] | undefined): Record<string, unknown> {
  const items = [...(records || [])].reverse();
  for (const record of items) {
    const result = asRecord(record.result);
    const runOverrides = asRecord(result.run_overrides);
    const extractionResult = asRecord(runOverrides.extraction_result);
    if (extractionResult.schema_version === 'contract-extraction-result/v1' || extractionResult.item_count !== undefined) {
      return extractionResult;
    }
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
      if (actionResult.action === 'extract_from_contract' && Array.isArray(actionResult.extracted_items)) {
        return {
          schema_version: 'contract-extraction-result/v1',
          site: '',
          parser_strategy: '',
          item_count: actionResult.extracted_items.length,
          fields_found: actionResult.fields_found,
          items: actionResult.extracted_items
        };
      }
    }
  }
  return {};
}

function fieldCoverageText(value: unknown): string {
  const fields = Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
  if (!fields.length) return '暂无字段覆盖记录';
  return `${fields.length} 个字段：${fields.join('、')}`;
}

function actionPriorityTag(value: unknown) {
  const priority = String(value || 'medium').toLowerCase();
  const color = priority === 'high' ? 'red' : priority === 'low' ? 'default' : 'gold';
  return <Tag color={color}>{priorityLabels[priority] || priority}</Tag>;
}

function normalizeRows(items: unknown, fallbackTitle: string): TextRow[] {
  return asArray(items).map((item, index) => {
    const record = asRecord(item);
    const title = firstText(record, ['stage', 'field', 'action', 'status_assessment', 'type'], fallbackTitle);
    const description = compactText(item);
    const tags = ['risk_level', 'priority', 'source']
      .map((key) => record[key])
      .filter((value) => value !== undefined && value !== null && value !== '')
      .map((value) => String(value));
    return {
      index: index + 1,
      title,
      description,
      detail: stringifyDetail(item),
      tags
    };
  });
}

function latestItem(items: unknown[] | undefined): unknown {
  if (!items || !items.length) return undefined;
  return items[items.length - 1];
}

function latestManagedAction(records: ManagedActionRecord[] | undefined): ManagedActionRecord | undefined {
  if (!records || !records.length) return undefined;
  return records[records.length - 1];
}

function normalizeDiagnosticItems(value: unknown[] | Record<string, unknown> | null | undefined): unknown[] {
  if (Array.isArray(value)) return value;
  if (value && typeof value === 'object') return [value];
  return [];
}

function fieldCompletenessIssues(quality: Record<string, unknown>): string[] {
  const completeness = asRecord(quality.field_completeness);
  return Object.entries(completeness)
    .filter(([, value]) => typeof value === 'number' && value < 0.8)
    .map(([field, value]) => `${field} 字段覆盖率偏低（${percent(Number(value))}）`);
}

function collectMissingFields(diagnostics: unknown[] | Record<string, unknown> | null | undefined): string[] {
  const output = new Set<string>();
  for (const item of normalizeDiagnosticItems(diagnostics)) {
    const record = asRecord(item);
    const missing = record.missing_fields;
    if (Array.isArray(missing)) missing.forEach((field) => output.add(String(field)));
    const causes = record.likely_causes;
    if (Array.isArray(causes)) {
      causes
        .filter((cause) => String(cause).toLowerCase().includes('field') || String(cause).includes('字段'))
        .forEach((cause) => output.add(String(cause)));
    }
  }
  return Array.from(output);
}

function deriveQualityIssues(params: {
  status?: string;
  recordCount?: number;
  progress?: RunProgress;
  aiDiagnostics?: unknown[] | Record<string, unknown> | null;
}): string[] {
  const status = String(params.status || params.progress?.status || '').toLowerCase();
  const progress = params.progress || {};
  const quality = asRecord(progress.quality);
  const gate = asRecord(quality.quality_gate);
  const issues: string[] = [];
  const recordsSaved = Number(progress.records_saved ?? params.recordCount ?? 0);
  const failed = Number(progress.failed ?? 0);
  const done = Number(progress.done ?? 0);
  const failedUrlCount = Number(quality.failed_url_count ?? 0);
  const duplicateRate = Number(quality.duplicate_rate ?? 0);
  const fieldCoverage = Number(quality.field_coverage ?? quality.coverage ?? -1);
  const severity = String(gate.severity || '').toLowerCase();

  if (status === 'paused') issues.push('任务已暂停，需要人工或 AI 托管确认下一步。');
  if (status === 'failed' || status === 'error') issues.push('任务运行失败，需要查看访问、字段或运行时诊断。');
  if (recordsSaved === 0 && ['completed', 'failed', 'paused', 'done', 'finished'].includes(status)) issues.push('空数据：当前运行没有保存商品记录。');
  if (failed > 0) {
    const denominator = Math.max(done + failed, failed);
    const failedRate = denominator ? failed / denominator : 0;
    issues.push(failedRate >= 0.2 ? `失败率偏高（${percent(failedRate)}）。` : `存在失败任务（${failed} 个）。`);
  }
  if (failedUrlCount > 0) issues.push(`失败 URL 数为 ${failedUrlCount}。`);
  if (fieldCoverage >= 0 && fieldCoverage < 0.8) issues.push(`字段覆盖率偏低（${percent(fieldCoverage)}）。`);
  if (duplicateRate > 0.05) issues.push(`重复率偏高（${percent(duplicateRate)}）。`);
  if (severity === 'fail') issues.push('质量门禁未通过。');
  if (severity === 'warn') issues.push('质量门禁存在警告。');
  fieldCompletenessIssues(quality).forEach((issue) => issues.push(issue));
  collectMissingFields(params.aiDiagnostics).forEach((field) => issues.push(`字段缺失或疑似缺失：${field}`));

  return Array.from(new Set(issues));
}

function deriveNextActions(issues: string[], suggestions: unknown[]): string[] {
  const suggestionRows = normalizeRows(suggestions, '建议');
  if (suggestionRows.length) return suggestionRows.slice(0, 5).map((row) => row.description);
  const text = issues.join(' ');
  const actions = new Set<string>();
  if (!issues.length) actions.add('继续观察当前任务，完成后检查质量门禁和导出结果。');
  if (text.includes('空数据') || text.includes('字段')) {
    actions.add('重新分析目录并探测字段候选。');
    actions.add('修复字段选择器后发起小批量试跑。');
  }
  if (text.includes('覆盖率') || text.includes('质量门禁')) actions.add('降低必填字段阈值或补充详情页字段采集。');
  if (text.includes('失败') || text.includes('暂停')) actions.add('检查访问诊断，必要时切换动态模式并调整等待策略。');
  if (text.includes('失败率')) actions.add('降低并发或缩小目录范围后重跑。');
  actions.add('使用 AI 托管修复并重跑生成子任务。');
  return Array.from(actions).slice(0, 5);
}

function modeTagColor(mode: string, enabled: boolean): string {
  if (!enabled) return 'default';
  if (mode === 'full_managed') return 'purple';
  if (mode === 'supervised') return 'blue';
  if (mode === 'analysis_only') return 'cyan';
  return 'default';
}

function renderTextRows(rows: TextRow[], emptyText: string) {
  if (!rows.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />;
  return (
    <List
      size="small"
      dataSource={rows}
      renderItem={(row) => (
        <List.Item>
          <List.Item.Meta
            title={
              <Space wrap>
                <span>{row.title}</span>
                {row.tags?.map((tag) => <Tag key={`${row.index}-${tag}`}>{tag}</Tag>)}
              </Space>
            }
            description={<Typography.Text>{row.description}</Typography.Text>}
          />
        </List.Item>
      )}
    />
  );
}

const actionColumns: ColumnsType<Record<string, unknown>> = [
  {
    title: '动作',
    dataIndex: 'action',
    width: 180,
    render: (value) => actionName(value)
  },
  {
    title: '参数摘要',
    dataIndex: 'params',
    ellipsis: true,
    render: (value) => paramsSummary(value)
  },
  {
    title: '优先级',
    dataIndex: 'priority',
    width: 110,
    render: (value) => actionPriorityTag(value)
  },
  {
    title: '原因',
    dataIndex: 'reason',
    render: (value, record) => String(value || record.rationale || record.description || '-')
  }
];

const resultColumns: ColumnsType<Record<string, unknown>> = [
  {
    title: '执行动作',
    dataIndex: 'action',
    width: 180,
    render: (value) => actionName(value)
  },
  {
    title: '结果',
    dataIndex: 'ok',
    width: 100,
    render: (value) => <Tag color={value === false ? 'error' : 'success'}>{value === false ? '失败' : '已执行'}</Tag>
  },
  {
    title: '说明',
    render: (_, record) => resultSummary(record)
  }
];

function managedActionDetailRows(actions: unknown[], results: unknown[], executed: boolean | undefined): Array<Record<string, unknown>> {
  return actions.map((item, index) => {
    const action = asRecord(item);
    const result = actionResultFor(action, results);
    const status = actionStatus(action, results, executed);
    return {
      key: `${String(action.action || 'action')}-${index}`,
      action: action.action,
      reason: action.reason,
      params: action.params,
      priority: action.priority,
      status,
      result
    };
  });
}

const actionDetailColumns: ColumnsType<Record<string, unknown>> = [
  {
    title: '动作名称',
    dataIndex: 'action',
    width: 180,
    render: (value) => actionName(value)
  },
  {
    title: '原因',
    dataIndex: 'reason',
    render: (value) => String(value || '-')
  },
  {
    title: '参数摘要',
    dataIndex: 'params',
    render: (value) => paramsSummary(value)
  },
  {
    title: '执行状态',
    dataIndex: 'status',
    width: 120,
    render: (value) => {
      const status = asRecord(value);
      return <Tag color={String(status.color || 'default')}>{String(status.label || '-')}</Tag>;
    }
  },
  {
    title: '执行结果',
    dataIndex: 'result',
    render: (value, record) => {
      const status = asRecord(record.status);
      const error = status.error ? `错误原因：${String(status.error)}` : '';
      return error || resultSummary(asRecord(value));
    }
  }
];

const sampleColumns: ColumnsType<Record<string, unknown>> = [
  {
    title: '标题',
    dataIndex: 'title',
    ellipsis: true,
    render: (value) => String(value || '-')
  },
  {
    title: '价格',
    dataIndex: 'highest_price',
    width: 110,
    render: (value, record) => {
      const currency = String(record.currency || '');
      return value === undefined || value === null || value === '' ? '-' : `${currency ? `${currency} ` : ''}${String(value)}`;
    }
  },
  {
    title: '颜色',
    dataIndex: 'color',
    width: 120,
    render: (value) => String(value || '-')
  },
  {
    title: '商品链接',
    dataIndex: 'product_url',
    ellipsis: true,
    render: (value) => String(value || '-')
  }
];

const stageLabels: Record<string, string> = {
  pre_run_review: '运行前计划审阅',
  post_run_diagnosis: '运行后诊断',
  managed_actions: '托管动作规划',
  site_analysis: '站点分析',
  planner: '任务规划',
  strategy: '采集策略'
};

function stageName(value: unknown): string {
  const stage = String(value || '').trim();
  return stageLabels[stage] || stage || '模型调用';
}

function summaryPreview(value: unknown): string {
  const record = asRecord(value);
  const preview = record.preview;
  if (typeof preview === 'string' && preview.trim()) return preview;
  const keys = Array.isArray(record.keys) ? record.keys.join(', ') : '';
  if (keys) return `字段：${keys}`;
  return stringifyDetail(value) || '-';
}

const traceColumns: ColumnsType<LlmTraceRecord> = [
  {
    title: '阶段',
    dataIndex: 'stage',
    width: 150,
    render: (value) => stageName(value)
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 90,
    render: (value) => {
      const status = String(value || '').toLowerCase();
      return <Tag color={status === 'ok' ? 'success' : status === 'error' ? 'error' : 'default'}>{status || '-'}</Tag>;
    }
  },
  {
    title: '模型',
    width: 180,
    render: (_, record) => record.model || record.provider || '-'
  },
  {
    title: '耗时',
    dataIndex: 'duration_ms',
    width: 90,
    render: (value) => (typeof value === 'number' ? `${value}ms` : '-')
  },
  {
    title: '输入摘要',
    dataIndex: 'input_summary',
    ellipsis: true,
    render: (value) => summaryPreview(value)
  },
  {
    title: '输出摘要 / 错误',
    ellipsis: true,
    render: (_, record) => record.error || summaryPreview(record.output_summary)
  }
];

export function AiManagedPanel({
  title = 'AI 托管驾驶舱',
  settings,
  status,
  recordCount,
  progress,
  managedMode,
  managedAi,
  modelName,
  llmAnalysis,
  aiDecisions,
  aiDiagnostics,
  aiRepairSuggestions,
  llmTraces,
  managedActions,
  managedAutoRepair,
  parentTaskId,
  repairSource,
  onManagedStep,
  onManagedRepairRun,
  repairLoading,
  repairDisabled
}: Props) {
  const configured = managedAi || settings?.managed_ai;
  const enabled = Boolean((configured as ManagedAiPayload | undefined)?.enabled);
  const mode = managedMode || String((configured as ManagedAiPayload | undefined)?.mode || (enabled ? settings?.managed_ai.mode : 'deterministic'));
  const decision = latestItem(aiDecisions);
  const latestAction = latestManagedAction(managedActions);
  const plan = latestAction?.result?.plan || {};
  const planActions = Array.isArray(plan.actions) ? plan.actions : [];
  const executionResults = Array.isArray(latestAction?.result?.results) ? latestAction?.result?.results || [] : [];
  const rerunTaskId = managedAutoRepair?.child_task_id || (latestAction as ManagedActionRecord & { task_id?: string } | undefined)?.task_id || '';
  const actionDetailRows = managedActionDetailRows(planActions, executionResults, latestAction?.executed);
  const extraction = findContractExtraction(managedActions);
  const extractionItems = Array.isArray(extraction.items) ? extraction.items.slice(0, 5).map((item) => asRecord(item)) : [];
  const extractionFields = Array.isArray(extraction.fields_found) ? extraction.fields_found : [];
  const diagnostics = normalizeDiagnosticItems(aiDiagnostics);
  const issues = deriveQualityIssues({ status, recordCount, progress, aiDiagnostics });
  const nextActions = deriveNextActions(issues, aiRepairSuggestions || []);
  const decisionRows = normalizeRows(decision ? [decision] : [], '最近决策');
  const diagnosticRows = normalizeRows(diagnostics, '诊断');
  const repairRows = normalizeRows(aiRepairSuggestions || [], '修复建议');
  const analysisRows = normalizeRows(llmAnalysis ? [llmAnalysis] : [], '模型分析');
  const traceRows = [...(llmTraces || [])].reverse();

  return (
    <Card
      title={<span>{title}</span>}
      extra={
        onManagedStep || onManagedRepairRun ? (
          <Space>
            {onManagedStep ? (
              <Button loading={repairLoading} onClick={onManagedStep}>
                让 AI 执行下一步
              </Button>
            ) : null}
            {onManagedRepairRun ? (
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                loading={repairLoading}
                disabled={repairDisabled}
                onClick={onManagedRepairRun}
              >
                AI 托管修复并重跑
              </Button>
            ) : null}
          </Space>
        ) : null
      }
    >
      <Descriptions size="small" column={2}>
        <Descriptions.Item label="当前托管模式">
          <Tag color={modeTagColor(mode, enabled)}>{managedAiModeLabel(enabled ? mode : 'deterministic')}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="托管状态">
          <Tag color={enabled ? 'processing' : 'default'}>{enabled ? '已启用' : '关闭'}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="模型">{modelName || settings?.llm.model || '未选择模型'}</Descriptions.Item>
        <Descriptions.Item label="运行前计划审阅">{(configured as ManagedAiPayload | undefined)?.plan_review_enabled ? '开启' : '关闭'}</Descriptions.Item>
        <Descriptions.Item label="运行时诊断">{(configured as ManagedAiPayload | undefined)?.runtime_diagnosis_enabled ? '开启' : '关闭'}</Descriptions.Item>
        <Descriptions.Item label="运行后质量诊断">{(configured as ManagedAiPayload | undefined)?.post_run_diagnosis_enabled ? '开启' : '关闭'}</Descriptions.Item>
        {parentTaskId ? <Descriptions.Item label="父任务 ID">{parentTaskId}</Descriptions.Item> : null}
        {repairSource ? <Descriptions.Item label="修复来源">{repairSource}</Descriptions.Item> : null}
      </Descriptions>

      {!enabled ? (
        <Alert className="section-gap" type="info" showIcon message="当前任务按关闭模式运行；LLM 不参与运行计划、监控或修复建议。" />
      ) : null}

      {managedAutoRepair?.attempted ? (
        <Alert
          className="section-gap"
          type="success"
          showIcon
          message="全托管自动修复已触发"
          description={`原因：${managedAutoRepair.reason || '质量诊断需要重跑'}；子任务：${managedAutoRepair.child_task_id || '等待后端返回'}`}
        />
      ) : null}

      <div className="two-column-grid section-gap">
        <Card size="small" title="最近一次 AI 决策">
          {renderTextRows(decisionRows, '暂无模型决策记录')}
        </Card>
        <Card size="small" title="当前质量问题">
          {issues.length ? (
            <List
              size="small"
              dataSource={issues}
              renderItem={(item) => (
                <List.Item>
                  <Tag color="warning">需关注</Tag>
                  <Typography.Text>{item}</Typography.Text>
                </List.Item>
              )}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未发现明显质量问题" />
          )}
        </Card>
      </div>

      <div className="two-column-grid section-gap">
        <Card size="small" title="动作计划">
          {planActions.length ? (
            <>
              {plan.reasoning_summary ? <Typography.Paragraph>{plan.reasoning_summary}</Typography.Paragraph> : null}
              <Table size="small" pagination={false} rowKey={(_: Record<string, unknown>, index: number) => String(index)} columns={actionColumns} dataSource={planActions as Record<string, unknown>[]} />
            </>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无托管动作计划" />
          )}
        </Card>
        <Card size="small" title="执行动作与重跑">
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="最近动作时间">{formatTime(latestAction?.created_at)}</Descriptions.Item>
            <Descriptions.Item label="动作来源">{String(plan.source || '-')}</Descriptions.Item>
            <Descriptions.Item label="执行状态">
              <Tag color={latestAction?.executed ? 'success' : 'default'}>{latestAction?.executed ? '已执行' : '未执行'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="可重跑">
              <Tag color={latestAction?.result?.rerun_ready ? 'success' : 'default'}>{latestAction?.result?.rerun_ready ? '是' : '否'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="重跑任务 ID">{rerunTaskId || '暂无'}</Descriptions.Item>
          </Descriptions>
          {executionResults.length ? (
            <Table className="section-gap-small" size="small" pagination={false} rowKey={(_: Record<string, unknown>, index: number) => String(index)} columns={resultColumns} dataSource={executionResults as Record<string, unknown>[]} />
          ) : null}
        </Card>
      </div>

      <div className="section-gap">
        <Card size="small" title="AI Action Plan 完整过程">
          {actionDetailRows.length ? (
            <Table
              size="small"
              pagination={false}
              rowKey="key"
              columns={actionDetailColumns}
              dataSource={actionDetailRows}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 AI action plan" />
          )}
        </Card>
      </div>

      {Object.keys(extraction).length ? (
        <div className="section-gap">
          <Card size="small" title="合同抽取结果 extract_from_contract">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="抽取策略">{String(extraction.parser_strategy || '未记录')}</Descriptions.Item>
              <Descriptions.Item label="站点">{String(extraction.site || '未记录')}</Descriptions.Item>
              <Descriptions.Item label="抽取条数">{String(extraction.item_count ?? extractionItems.length)}</Descriptions.Item>
              <Descriptions.Item label="字段覆盖">{fieldCoverageText(extractionFields)}</Descriptions.Item>
            </Descriptions>
            {extractionItems.length ? (
              <Table
                className="section-gap-small"
                size="small"
                pagination={false}
                rowKey={(_: Record<string, unknown>, index?: number) => String(index ?? 0)}
                columns={sampleColumns}
                dataSource={extractionItems}
              />
            ) : (
              <Alert className="section-gap-small" type="warning" showIcon message="合同抽取没有返回样例商品" />
            )}
          </Card>
        </div>
      ) : null}

      <div className="section-gap">
        <Card size="small" title="模型调用轨迹">
          {traceRows.length ? (
            <Table
              size="small"
              pagination={{ pageSize: 5, hideOnSinglePage: true }}
              rowKey={(record: LlmTraceRecord, index?: number) => `${record.created_at || record.stage || 'trace'}-${index ?? 0}`}
              columns={traceColumns}
              dataSource={traceRows}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模型调用轨迹" />
          )}
        </Card>
      </div>

      <div className="section-gap">
        <Card size="small" title="下一步建议动作">
          <List
            size="small"
            dataSource={nextActions}
            renderItem={(item) => (
              <List.Item>
                <Typography.Text>{item}</Typography.Text>
              </List.Item>
            )}
          />
        </Card>
      </div>

      <Collapse
        className="section-gap"
        size="small"
        items={[
          {
            key: 'diagnostics',
            label: 'AI 诊断和修复建议详情',
            children: (
              <div className="two-column-grid">
                <div>{renderTextRows(diagnosticRows, '暂无模型决策记录')}</div>
                <div>{renderTextRows(repairRows, '暂无模型决策记录')}</div>
              </div>
            )
          },
          {
            key: 'analysis',
            label: '运行前模型分析摘要',
            children: renderTextRows(analysisRows, '暂无模型分析记录')
          },
          {
            key: 'raw',
            label: '原始证据摘要（已脱敏）',
            children: (
              <Typography.Paragraph>
                <pre>{stringifyDetail({ llmAnalysis, aiDecisions, aiDiagnostics, aiRepairSuggestions, llmTraces, managedActions, managedAutoRepair })}</pre>
              </Typography.Paragraph>
            )
          }
        ]}
      />
    </Card>
  );
}
