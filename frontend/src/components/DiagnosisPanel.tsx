import { Alert, Badge, Button, Card, Collapse, Descriptions, Empty, List, Progress, Space, Steps, Tag, Typography, message } from 'antd';
import { useState } from 'react';
import { diagnoseRun, runAutoRepairLoop } from '../api/client';
import type { AutoRepairCycle, AutoRepairLoopResult, DiagnosisReport, FailureDiagnosis, LlmConfig, SettingsState } from '../types/workflow';

interface Props {
  settings: SettingsState;
  taskId: string;
  executionResult?: Record<string, unknown>;
  llm?: Partial<LlmConfig> & { enabled?: boolean };
  onComplete?: (result: AutoRepairLoopResult) => void;
}

const severityColor: Record<string, string> = {
  critical: 'red',
  warning: 'gold',
  info: 'blue'
};

const severityLabel: Record<string, string> = {
  critical: '严重',
  warning: '警告',
  info: '提示'
};

const healthColor: Record<string, string> = {
  healthy: 'green',
  degraded: 'gold',
  critical: 'red'
};

const healthLabel: Record<string, string> = {
  healthy: '健康',
  degraded: '降级',
  critical: '严重异常'
};

const categoryLabel: Record<string, string> = {
  field_extraction: '字段提取',
  access: '访问问题',
  pagination: '分页问题',
  data_quality: '数据质量',
  runtime: '运行时错误',
  configuration: '配置问题'
};

function DiagnosisItem({ diagnosis }: { diagnosis: FailureDiagnosis }) {
  return (
    <List.Item>
      <div style={{ width: '100%' }}>
        <Space style={{ marginBottom: 4 }}>
          <Tag color={severityColor[diagnosis.severity] || 'default'}>
            {severityLabel[diagnosis.severity] || diagnosis.severity}
          </Tag>
          <Typography.Text strong>
            {categoryLabel[diagnosis.category] || diagnosis.category}
          </Typography.Text>
          <Typography.Text type="secondary">
            置信度 {Math.round(diagnosis.confidence * 100)}%
          </Typography.Text>
        </Space>
        <Typography.Paragraph style={{ marginBottom: 4 }}>
          {diagnosis.evidence}
        </Typography.Paragraph>
        {diagnosis.affected_fields.length > 0 && (
          <div style={{ marginBottom: 4 }}>
            <Typography.Text type="secondary">影响字段：</Typography.Text>
            <Space wrap size={4}>
              {diagnosis.affected_fields.map((field) => (
                <Tag key={field} bordered={false}>{field}</Tag>
              ))}
            </Space>
          </div>
        )}
        {diagnosis.repair_actions.length > 0 && (
          <div>
            <Typography.Text type="secondary">建议动作：</Typography.Text>
            <Space wrap size={4}>
              {diagnosis.repair_actions.map((action) => (
                <Tag key={action} color="processing">{action}</Tag>
              ))}
            </Space>
          </div>
        )}
      </div>
    </List.Item>
  );
}

function CycleStep({ cycle }: { cycle: AutoRepairCycle }) {
  const status = cycle.improved ? 'finish' : cycle.health_after === cycle.health_before ? 'wait' : 'finish';
  return (
    <Steps.Step
      status={status}
      title={`第 ${cycle.cycle} 轮`}
      description={
        <div>
          <Space size={8}>
            <Tag>{healthLabel[cycle.health_before] || cycle.health_before}</Tag>
            <Typography.Text type="secondary">→</Typography.Text>
            <Tag color={healthColor[cycle.health_after] || 'default'}>
              {healthLabel[cycle.health_after] || cycle.health_after}
            </Tag>
            {cycle.improved ? (
              <Tag color="success">改善</Tag>
            ) : (
              <Tag>未改善</Tag>
            )}
          </Space>
          {cycle.actions_taken.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <Typography.Text type="secondary">执行动作：</Typography.Text>
              <Space wrap size={4}>
                {cycle.actions_taken.map((action) => (
                  <Tag key={action} bordered={false}>{action}</Tag>
                ))}
              </Space>
            </div>
          )}
          {cycle.diagnosis.diagnoses.length > 0 && (
            <Collapse
              size="small"
              ghost
              items={[{
                key: 'diagnosis',
                label: `诊断详情（${cycle.diagnosis.diagnoses.length} 项）`,
                children: (
                  <List
                    size="small"
                    dataSource={cycle.diagnosis.diagnoses}
                    renderItem={(item) => <DiagnosisItem diagnosis={item} />}
                  />
                )
              }]}
            />
          )}
        </div>
      }
    />
  );
}

export function DiagnosisPanel({ settings, taskId, executionResult, llm, onComplete }: Props) {
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [repairLoading, setRepairLoading] = useState(false);
  const [report, setReport] = useState<DiagnosisReport | null>(null);
  const [repairResult, setRepairResult] = useState<AutoRepairLoopResult | null>(null);

  const handleDiagnose = async () => {
    setDiagnosisLoading(true);
    try {
      const result = await diagnoseRun(settings, taskId, executionResult);
      setReport(result);
      message.success('诊断完成');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '诊断失败');
    } finally {
      setDiagnosisLoading(false);
    }
  };

  const handleAutoRepair = async () => {
    setRepairLoading(true);
    setRepairResult(null);
    try {
      const result = await runAutoRepairLoop(settings, taskId, undefined, llm);
      setRepairResult(result);
      if (result.converged && result.final_health === 'healthy') {
        message.success('自动修复完成，状态已恢复健康');
      } else if (result.converged) {
        message.warning(`自动修复完成，最终状态：${healthLabel[result.final_health] || result.final_health}`);
      } else {
        message.warning('自动修复未完全收敛，可能需要手动干预');
      }
      onComplete?.(result);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '自动修复失败');
    } finally {
      setRepairLoading(false);
    }
  };

  return (
    <Card
      title={
        <span>故障诊断与自动修复</span>
      }
      extra={
        <Space>
          <Button
            loading={diagnosisLoading}
            onClick={handleDiagnose}
          >
            运行诊断
          </Button>
          <Button
            type="primary"
            loading={repairLoading}
            onClick={handleAutoRepair}
          >
            自动修复
          </Button>
        </Space>
      }
    >
      {!report && !repairResult && (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="点击「运行诊断」查看故障分析，或点击「自动修复」执行诊断 + 修复闭环。" />
      )}

      {report && (
        <div className="section-gap">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="整体健康状态">
              <Badge
                color={healthColor[report.overall_health] || 'default'}
                text={healthLabel[report.overall_health] || report.overall_health}
              />
            </Descriptions.Item>
            <Descriptions.Item label="可自动修复">
              <Tag color={report.auto_repairable ? 'success' : 'default'}>
                {report.auto_repairable ? '是' : '否'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>

          {report.recommended_focus.length > 0 && (
            <div style={{ marginTop: 8, marginBottom: 8 }}>
              <Typography.Text type="secondary">建议关注：</Typography.Text>
              <Space wrap size={4}>
                {report.recommended_focus.map((focus) => (
                  <Tag key={focus} color="orange">{categoryLabel[focus] || focus}</Tag>
                ))}
              </Space>
            </div>
          )}

          {report.diagnoses.length > 0 ? (
            <Card size="small" title={`诊断详情（${report.diagnoses.length} 项）`}>
              <List
                size="small"
                dataSource={report.diagnoses}
                renderItem={(item) => <DiagnosisItem diagnosis={item} />}
              />
            </Card>
          ) : (
            <Alert type="success" showIcon message="未发现故障" />
          )}
        </div>
      )}

      {repairResult && (
        <div className="section-gap">
          <Card size="small" title="自动修复结果">
            <Descriptions size="small" column={3}>
              <Descriptions.Item label="修复轮数">{repairResult.total_cycles}</Descriptions.Item>
              <Descriptions.Item label="是否收敛">
                <Tag color={repairResult.converged ? 'success' : 'warning'}>
                  {repairResult.converged ? '已收敛' : '未收敛'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="最终健康状态">
                <Badge
                  color={healthColor[repairResult.final_health] || 'default'}
                  text={healthLabel[repairResult.final_health] || repairResult.final_health}
                />
              </Descriptions.Item>
            </Descriptions>

            {repairResult.cycles.length > 0 && (
              <div className="section-gap-small">
                <Typography.Text strong>修复过程：</Typography.Text>
                <Steps
                  direction="vertical"
                  size="small"
                  current={repairResult.cycles.length}
                  style={{ marginTop: 8 }}
                >
                  {repairResult.cycles.map((cycle) => (
                    <CycleStep key={cycle.cycle} cycle={cycle} />
                  ))}
                </Steps>
              </div>
            )}

            {repairResult.final_health === 'healthy' && (
              <Progress percent={100} status="success" showInfo={false} style={{ marginTop: 8 }} />
            )}
          </Card>
        </div>
      )}
    </Card>
  );
}
