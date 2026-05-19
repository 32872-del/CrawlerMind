import { Alert, Card, Descriptions, Empty, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ManagedAiPayload, SettingsState } from '../types/workflow';
import { managedAiModeLabel } from '../utils/format';

interface Props {
  title?: string;
  settings?: SettingsState;
  managedMode?: string;
  managedAi?: ManagedAiPayload | Record<string, unknown>;
  modelName?: string;
  llmAnalysis?: Record<string, unknown>;
  aiDecisions?: unknown[];
  aiDiagnostics?: unknown[];
  aiRepairSuggestions?: unknown[];
}

function asRows(value: unknown): Array<{ key: string; value: string }> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
  return Object.entries(value as Record<string, unknown>).map(([key, item]) => ({
    key,
    value: typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item)
  }));
}

function listRows(items: unknown[] | undefined): Array<{ index: number; value: string }> {
  return (items || []).map((item, index) => ({
    index: index + 1,
    value: typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item)
  }));
}

const listColumns: ColumnsType<{ index: number; value: string }> = [
  { title: '#', dataIndex: 'index', width: 64 },
  { title: '内容', dataIndex: 'value' }
];

export function AiManagedPanel({
  title = 'AI 托管模式',
  settings,
  managedMode,
  managedAi,
  modelName,
  llmAnalysis,
  aiDecisions,
  aiDiagnostics,
  aiRepairSuggestions
}: Props) {
  const configured = managedAi || settings?.managed_ai;
  const enabled = Boolean((configured as ManagedAiPayload | undefined)?.enabled);
  const mode = managedMode || String((configured as ManagedAiPayload | undefined)?.mode || (enabled ? settings?.managed_ai.mode : 'deterministic'));
  const analysisRows = asRows(llmAnalysis);
  const decisionRows = listRows(aiDecisions);
  const diagnosticRows = listRows(aiDiagnostics);
  const repairRows = listRows(aiRepairSuggestions);

  return (
    <Card title={title}>
      <Descriptions size="small" column={2}>
        <Descriptions.Item label="托管状态">
          <Tag color={enabled ? 'processing' : 'default'}>{enabled ? '已启用' : '未启用'}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="托管模式">{managedAiModeLabel(enabled ? mode : 'deterministic')}</Descriptions.Item>
        <Descriptions.Item label="模型">{modelName || settings?.llm.model || '未选择模型'}</Descriptions.Item>
        <Descriptions.Item label="运行前计划审阅">{(configured as ManagedAiPayload | undefined)?.plan_review_enabled ? '开启' : '关闭'}</Descriptions.Item>
        <Descriptions.Item label="运行时诊断">{(configured as ManagedAiPayload | undefined)?.runtime_diagnosis_enabled ? '开启' : '关闭'}</Descriptions.Item>
        <Descriptions.Item label="运行后质量诊断">{(configured as ManagedAiPayload | undefined)?.post_run_diagnosis_enabled ? '开启' : '关闭'}</Descriptions.Item>
      </Descriptions>

      {!enabled ? (
        <Alert className="section-gap" type="info" showIcon message="当前任务按规则模式运行；LLM 不参与运行计划、监控或修复建议。" />
      ) : null}

      <div className="section-gap">
        <Card size="small" title="模型分析摘要">
          {analysisRows.length ? (
            <Table size="small" pagination={false} rowKey="key" columns={[{ title: '键', dataIndex: 'key', width: 220 }, { title: '值', dataIndex: 'value' }]} dataSource={analysisRows} />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模型分析记录" />
          )}
        </Card>
      </div>

      <div className="two-column-grid section-gap">
        <Card size="small" title="模型决策记录">
          {decisionRows.length ? <Table size="small" pagination={false} rowKey="index" columns={listColumns} dataSource={decisionRows} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模型决策记录" />}
        </Card>
        <Card size="small" title="AI 诊断记录">
          {diagnosticRows.length ? <Table size="small" pagination={false} rowKey="index" columns={listColumns} dataSource={diagnosticRows} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模型决策记录" />}
        </Card>
      </div>

      <div className="section-gap">
        <Card size="small" title="修复建议">
          {repairRows.length ? <Table size="small" pagination={false} rowKey="index" columns={listColumns} dataSource={repairRows} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模型决策记录" />}
        </Card>
      </div>
    </Card>
  );
}
