import { Alert, Button, Card, Descriptions, Empty, Form, Input, Progress, Result, Space, Steps, Tag, Timeline, Typography, message } from 'antd';
import ReloadOutlined from '@ant-design/icons/lib/icons/ReloadOutlined';
import CheckCircleOutlined from '@ant-design/icons/lib/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/lib/icons/CloseCircleOutlined';
import LoadingOutlined from '@ant-design/icons/lib/icons/LoadingOutlined';
import RocketOutlined from '@ant-design/icons/lib/icons/RocketOutlined';
import ToolOutlined from '@ant-design/icons/lib/icons/ToolOutlined';
import SyncOutlined from '@ant-design/icons/lib/icons/SyncOutlined';
import { useState } from 'react';
import { managedExecuteAndRun, managedDiagnoseAndRepair } from '../api/client';
import { MetricStrip } from '../components/MetricStrip';
import { StatusPill } from '../components/StatusPill';
import { useWorkbench } from '../store/workbench';
import { nowIso, percent, userFacingError } from '../utils/format';
import type { ManagedActionTimelineEntry, ManagedPipelineStage, ManagedRepairResult, ManagedRunResult } from '../types/workflow';

const stageSteps: Array<{ key: ManagedPipelineStage; label: string; description: string }> = [
  { key: 'analyzing', label: '分析站点', description: '分析目标站点结构和字段' },
  { key: 'planning', label: '生成计划', description: 'AI 规划采集动作' },
  { key: 'executing_actions', label: '执行动作', description: '依次执行采集动作' },
  { key: 'running', label: '运行采集', description: '运行采集任务' },
  { key: 'completed', label: '完成', description: '采集完成' }
];

const repairStageSteps: Array<{ key: ManagedPipelineStage; label: string; description: string }> = [
  { key: 'diagnosing', label: '诊断问题', description: '分析采集失败原因' },
  { key: 'repairing', label: '修复执行', description: '修复字段/配置并重跑' },
  { key: 'completed', label: '完成', description: '修复完成' }
];

function stageToStepIndex(stage: ManagedPipelineStage | undefined, steps: typeof stageSteps): number {
  if (!stage || stage === 'idle') return -1;
  if (stage === 'failed') return -1;
  const idx = steps.findIndex((s) => s.key === stage);
  return idx >= 0 ? idx : steps.length - 1;
}

function actionStatusIcon(status: ManagedActionTimelineEntry['status']) {
  switch (status) {
    case 'success': return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    case 'failed': return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
    case 'running': return <LoadingOutlined style={{ color: '#1677ff' }} />;
    case 'skipped': return <Tag>跳过</Tag>;
    default: return null;
  }
}

function actionTimelineColor(status: ManagedActionTimelineEntry['status']): string {
  switch (status) {
    case 'success': return 'green';
    case 'failed': return 'red';
    case 'running': return 'blue';
    case 'skipped': return 'gray';
    default: return 'gray';
  }
}

function QualityGateDisplay({ gate }: { gate?: { severity: string; passed: boolean; reason?: string } }) {
  if (!gate) return null;
  const color = gate.passed ? 'success' : gate.severity === 'warn' ? 'warning' : 'error';
  const label = gate.passed ? '通过' : gate.severity === 'warn' ? '警告' : '未通过';
  return (
    <Alert
      type={color}
      showIcon
      message={`质量门禁：${label}`}
      description={gate.reason || (gate.passed ? '所有指标达标' : '部分指标未达标')}
    />
  );
}

function RepairComparison({ before, after }: { before: ManagedRunResult; after: ManagedRepairResult }) {
  const rows = [
    {
      key: 'records',
      metric: '采集记录数',
      before: String(before.record_count ?? '-'),
      after: String(after.after_records ?? after.record_count ?? '-'),
      improved: (after.after_records ?? 0) > (before.record_count ?? 0)
    },
    {
      key: 'coverage',
      metric: '字段覆盖率',
      before: before.field_coverage !== undefined ? percent(before.field_coverage) : '-',
      after: after.after_coverage !== undefined ? percent(after.after_coverage) : (before.field_coverage !== undefined ? percent(before.field_coverage) : '-'),
      improved: (after.after_coverage ?? 0) > (before.field_coverage ?? 0)
    },
    {
      key: 'quality',
      metric: '质量评分',
      before: before.quality_score !== undefined ? percent(before.quality_score) : '-',
      after: after.after_quality !== undefined ? percent(after.after_quality) : (before.quality_score !== undefined ? percent(before.quality_score) : '-'),
      improved: (after.after_quality ?? 0) > (before.quality_score ?? 0)
    }
  ];

  return (
    <Card size="small" title="修复前后对比">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px 120px 80px', gap: '8px 16px', alignItems: 'center' }}>
        <Typography.Text strong type="secondary">指标</Typography.Text>
        <Typography.Text strong type="secondary">修复前</Typography.Text>
        <Typography.Text strong type="secondary">修复后</Typography.Text>
        <Typography.Text strong type="secondary">变化</Typography.Text>
        {rows.map((row) => (
          <>
            <Typography.Text key={`m-${row.key}`}>{row.metric}</Typography.Text>
            <Typography.Text key={`b-${row.key}`}>{row.before}</Typography.Text>
            <Typography.Text key={`a-${row.key}`} strong>{row.after}</Typography.Text>
            <Typography.Text key={`d-${row.key}`} type={row.improved ? 'success' : 'secondary'}>
              {row.improved ? '↑ 改善' : '—'}
            </Typography.Text>
          </>
        ))}
      </div>
    </Card>
  );
}

export function OneClickCrawlPage() {
  const { settings, setPage, upsertTask, setActiveTaskId } = useWorkbench();
  const [targetUrl, setTargetUrl] = useState('');
  const [fieldGoal, setFieldGoal] = useState('');
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<ManagedPipelineStage>('idle');
  const [result, setResult] = useState<ManagedRunResult | undefined>();
  const [repairResult, setRepairResult] = useState<ManagedRepairResult | undefined>();
  const [error, setError] = useState('');

  const buildLlmPayload = () => ({
    enabled: Boolean(settings.llm.base_url && settings.llm.model),
    base_url: settings.llm.base_url,
    model: settings.llm.model,
    api_key: settings.llm.api_key
  });

  const handleExecute = async () => {
    if (!targetUrl.trim()) {
      message.warning('请输入目标 URL');
      return;
    }
    setBusy(true);
    setError('');
    setResult(undefined);
    setRepairResult(undefined);
    setStage('analyzing');

    try {
      // Simulate stage progression for UX feedback
      const stageTimer1 = setTimeout(() => setStage('planning'), 1500);
      const stageTimer2 = setTimeout(() => setStage('executing_actions'), 3500);
      const stageTimer3 = setTimeout(() => setStage('running'), 6000);

      const response = await managedExecuteAndRun(settings, {
        target_url: targetUrl.trim(),
        profile: fieldGoal.trim() ? { field_goal: fieldGoal.trim() } : undefined,
        llm_decide: Boolean(settings.llm.base_url && settings.llm.model),
        item_workers: settings.runtime.item_workers,
        llm: buildLlmPayload()
      });

      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);

      setResult(response);
      setStage(response.stage || (response.status === 'failed' ? 'failed' : 'completed'));

      if (response.task_id) {
        upsertTask({
          task_id: response.task_id,
          run_id: response.run_id,
          target_url: targetUrl.trim(),
          status: response.status,
          mode: 'test',
          created_at: nowIso(),
          record_count: response.record_count || 0,
          managed_run_result: response
        });
        setActiveTaskId(response.task_id);
      }

      if (response.status === 'completed' || response.status === 'done') {
        message.success(`采集完成！共 ${response.record_count || 0} 条记录`);
      } else if (response.status === 'failed') {
        message.error(response.error || '采集失败，可尝试一键修复');
      }
    } catch (err) {
      setStage('failed');
      setError(userFacingError(err));
      message.error(userFacingError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRepair = async () => {
    if (!targetUrl.trim()) return;
    setBusy(true);
    setError('');
    setRepairResult(undefined);
    setStage('diagnosing');

    try {
      const stageTimer1 = setTimeout(() => setStage('repairing'), 3000);

      const response = await managedDiagnoseAndRepair(settings, {
        target_url: targetUrl.trim(),
        profile: fieldGoal.trim() ? { field_goal: fieldGoal.trim() } : undefined,
        max_cycles: 3,
        item_workers: settings.runtime.item_workers,
        llm: buildLlmPayload()
      });

      clearTimeout(stageTimer1);

      setRepairResult(response);
      setStage(response.stage || (response.status === 'failed' ? 'failed' : 'completed'));

      if (response.task_id) {
        upsertTask({
          task_id: response.task_id,
          run_id: response.run_id,
          target_url: targetUrl.trim(),
          status: response.status,
          mode: 'test',
          created_at: nowIso(),
          record_count: response.record_count || 0,
          repair_result: response,
          parent_task_id: result?.task_id
        });
        setActiveTaskId(response.task_id);
      }

      if (response.status === 'completed' || response.status === 'done') {
        message.success(`修复完成！记录数 ${response.before_records ?? '?'} → ${response.after_records ?? response.record_count ?? '?'}`);
      } else {
        message.warning('修复未完全收敛');
      }
    } catch (err) {
      setStage('failed');
      setError(userFacingError(err));
      message.error(userFacingError(err));
    } finally {
      setBusy(false);
    }
  };

  const isRunning = busy;
  const isFailed = stage === 'failed' || result?.status === 'failed';
  const isCompleted = stage === 'completed' || result?.status === 'completed' || result?.status === 'done';
  const showRepairButton = isFailed || (result && result.quality_gate && !result.quality_gate.passed);
  const currentStep = stageToStepIndex(stage, stageSteps);
  const repairStep = stageToStepIndex(stage, repairStageSteps);

  // Determine which stage steps to show
  const showingRepair = stage === 'diagnosing' || stage === 'repairing' || (repairResult && stage === 'completed');
  const activeSteps = showingRepair ? repairStageSteps : stageSteps;

  return (
    <Space direction="vertical" size={16} className="page-stack">
      <Card
        title={
          <Space>
            <RocketOutlined />
            <span>一键 AI 采集</span>
          </Space>
        }
      >
        <Form layout="vertical">
          <Form.Item label="目标网站 URL" required>
            <Input
              size="large"
              placeholder="https://example.com/products"
              value={targetUrl}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTargetUrl(e.target.value)}
              disabled={isRunning}
            />
          </Form.Item>
          <Form.Item label="采集目标描述（选填）">
            <Input.TextArea
              rows={2}
              placeholder="例如：采集商品标题、价格、颜色、尺码、描述和图片"
              value={fieldGoal}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setFieldGoal(e.target.value)}
              disabled={isRunning}
            />
          </Form.Item>
          <Form.Item label="LLM 配置">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="模型">
                <Tag color={settings.llm.model ? 'blue' : 'default'}>
                  {settings.llm.model || '未配置'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="API 地址">
                {settings.llm.base_url || '未配置'}
              </Descriptions.Item>
            </Descriptions>
            {!settings.llm.model && (
              <Alert
                type="warning"
                showIcon
                message="未配置 LLM 模型，AI 采集将使用规则引擎。建议在设置中配置 LLM 以获得更好的采集效果。"
                style={{ marginTop: 8 }}
              />
            )}
          </Form.Item>
          <Space>
            <Button
              type="primary"
              size="large"
              icon={<RocketOutlined />}
              loading={isRunning && !showingRepair}
              disabled={isRunning || !targetUrl.trim()}
              onClick={handleExecute}
            >
              开始 AI 采集
            </Button>
            {showRepairButton && !isRunning && (
              <Button
                size="large"
                icon={<ToolOutlined />}
                onClick={handleRepair}
              >
                一键修复
              </Button>
            )}
            {isCompleted && (
              <Button
                size="large"
                icon={<SyncOutlined />}
                onClick={() => {
                  setStage('idle');
                  setResult(undefined);
                  setRepairResult(undefined);
                  setError('');
                }}
              >
                重新采集
              </Button>
            )}
          </Space>
        </Form>
      </Card>

      {/* Pipeline Progress */}
      {stage !== 'idle' && (
        <Card title={showingRepair ? "修复进度" : "采集进度"}>
          <Steps
            current={showingRepair ? repairStep : currentStep}
            status={isFailed ? 'error' : isRunning ? 'process' : 'finish'}
            items={activeSteps.map((s) => ({
              title: s.label,
              description: s.description,
              icon: isRunning && activeSteps.indexOf(s) === (showingRepair ? repairStep : currentStep) ? <LoadingOutlined /> : undefined
            }))}
          />
          {isRunning && (
            <div style={{ marginTop: 16 }}>
              <Progress
                percent={showingRepair
                  ? (stage === 'diagnosing' ? 30 : stage === 'repairing' ? 70 : 100)
                  : (stage === 'analyzing' ? 15 : stage === 'planning' ? 30 : stage === 'executing_actions' ? 55 : stage === 'running' ? 80 : 100)
                }
                status="active"
                showInfo={false}
              />
            </div>
          )}
        </Card>
      )}

      {/* Error Display */}
      {error && (
        <Alert type="error" showIcon message="执行失败" description={error} closable onClose={() => setError('')} />
      )}

      {/* Action Timeline */}
      {result?.actions && result.actions.length > 0 && (
        <Card title="执行动作时间线">
          <Timeline
            items={result.actions.map((action) => ({
              color: actionTimelineColor(action.status),
              dot: actionStatusIcon(action.status),
              children: (
                <div>
                  <Space style={{ marginBottom: 4 }}>
                    <Typography.Text strong>{action.label}</Typography.Text>
                    <Tag color={action.status === 'success' ? 'success' : action.status === 'failed' ? 'error' : action.status === 'running' ? 'processing' : 'default'}>
                      {action.status === 'success' ? '成功' : action.status === 'failed' ? '失败' : action.status === 'running' ? '执行中' : action.status === 'skipped' ? '跳过' : '等待中'}
                    </Tag>
                    {action.duration_ms !== undefined && (
                      <Typography.Text type="secondary">{action.duration_ms}ms</Typography.Text>
                    )}
                  </Space>
                  {action.result_summary && (
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      {action.result_summary}
                    </Typography.Paragraph>
                  )}
                  {action.error && (
                    <Typography.Paragraph type="danger" style={{ marginBottom: 0 }}>
                      错误：{action.error}
                    </Typography.Paragraph>
                  )}
                </div>
              )
            }))}
          />
        </Card>
      )}

      {/* Repair Action Timeline */}
      {repairResult?.actions && repairResult.actions.length > 0 && (
        <Card title="修复动作时间线">
          <Timeline
            items={repairResult.actions.map((action) => ({
              color: actionTimelineColor(action.status),
              dot: actionStatusIcon(action.status),
              children: (
                <div>
                  <Space style={{ marginBottom: 4 }}>
                    <Typography.Text strong>{action.label}</Typography.Text>
                    <Tag color={action.status === 'success' ? 'success' : action.status === 'failed' ? 'error' : 'default'}>
                      {action.status === 'success' ? '成功' : action.status === 'failed' ? '失败' : action.status === 'running' ? '执行中' : '等待中'}
                    </Tag>
                    {action.duration_ms !== undefined && (
                      <Typography.Text type="secondary">{action.duration_ms}ms</Typography.Text>
                    )}
                  </Space>
                  {action.result_summary && (
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      {action.result_summary}
                    </Typography.Paragraph>
                  )}
                </div>
              )
            }))}
          />
        </Card>
      )}

      {/* Result Summary */}
      {result && (isCompleted || isFailed) && (
        <Card title="采集结果">
          <MetricStrip
            metrics={[
              { label: '采集记录数', value: result.record_count ?? 0 },
              { label: '字段覆盖率', value: result.field_coverage !== undefined ? percent(result.field_coverage) : '-' },
              { label: '质量评分', value: result.quality_score !== undefined ? percent(result.quality_score) : '-' },
              { label: '任务状态', value: result.status === 'completed' || result.status === 'done' ? '已完成' : '失败' }
            ]}
          />
          <div className="section-gap">
            <QualityGateDisplay gate={result.quality_gate} />
          </div>
          {result.error && (
            <Alert className="section-gap" type="error" showIcon message="错误信息" description={result.error} />
          )}
        </Card>
      )}

      {/* Repair Result */}
      {repairResult && (
        <>
          <Card title="修复结果">
            <MetricStrip
              metrics={[
                { label: '修复轮数', value: repairResult.repair_cycles ?? '-' },
                { label: '修复后记录数', value: repairResult.after_records ?? repairResult.record_count ?? '-' },
                { label: '修复后覆盖率', value: repairResult.after_coverage !== undefined ? percent(repairResult.after_coverage) : '-' },
                { label: '修复后质量', value: repairResult.after_quality !== undefined ? percent(repairResult.after_quality) : '-' }
              ]}
            />
            {repairResult.converged !== undefined && (
              <div className="section-gap">
                <Tag color={repairResult.converged ? 'success' : 'warning'}>
                  {repairResult.converged ? '已收敛' : '未收敛'}
                </Tag>
                {repairResult.final_health && (
                  <Tag color={repairResult.final_health === 'healthy' ? 'success' : repairResult.final_health === 'degraded' ? 'warning' : 'error'}>
                    {repairResult.final_health === 'healthy' ? '健康' : repairResult.final_health === 'degraded' ? '降级' : '异常'}
                  </Tag>
                )}
              </div>
            )}
            {repairResult.quality_gate && (
              <div className="section-gap">
                <QualityGateDisplay gate={repairResult.quality_gate} />
              </div>
            )}
          </Card>

          {/* Before/After Comparison */}
          {result && (
            <RepairComparison before={result} after={repairResult} />
          )}
        </>
      )}

      {/* Empty State */}
      {stage === 'idle' && !result && (
        <Card>
          <Empty
            image={<RocketOutlined style={{ fontSize: 48, color: '#bfbfbf' }} />}
            description={
              <div>
                <Typography.Paragraph>输入目标 URL，一键完成 AI 分析→执行→采集的完整闭环</Typography.Paragraph>
                <Typography.Paragraph type="secondary">
                  AI 会自动分析站点结构、规划采集策略、执行动作并运行采集任务。
                  如果采集失败，还可以一键诊断和修复。
                </Typography.Paragraph>
              </div>
            }
          />
        </Card>
      )}
    </Space>
  );
}
