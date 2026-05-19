import { Alert, Button, Card, Descriptions, Form, Input, Space, Table, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState, type ChangeEvent } from 'react';
import { analyzeSite, importCatalog, launchRun } from '../api/client';
import { AiManagedPanel } from '../components/AiManagedPanel';
import { CatalogTreeView } from '../components/CatalogTreeView';
import { FieldSelector } from '../components/FieldSelector';
import { WorkflowOverview } from '../components/WorkflowOverview';
import { catalogCount, useWorkbench } from '../store/workbench';
import type { FieldCandidate, RunRequest } from '../types/workflow';
import { buildRunPayload, runPayloadSummary, seedUrlRows } from '../utils/runPayload';
import { fieldLabel, nowIso, runModeLabel, sourceLabel, tryParseJson, userFacingError } from '../utils/format';

export function AnalysisPage() {
  const { settings, wizard, setWizard, upsertTask, setActiveTaskId, setPage, prepareNewTarget, tasks, activeTaskId, resetWizardExport } = useWorkbench();
  const [busy, setBusy] = useState(false);
  const [lastPayload, setLastPayload] = useState<RunRequest | undefined>(wizard.lastRunPayload);
  const analysis = wizard.analysis;
  const activeTask = tasks.find((task) => task.task_id === activeTaskId);
  const previewPayload = useMemo(() => {
    try {
      return lastPayload || buildRunPayload(wizard, settings);
    } catch {
      return undefined;
    }
  }, [lastPayload, settings, wizard]);

  const appendLog = (line: string) => {
    setWizard((current) => ({
      ...current,
      analysisLog: [...(current.analysisLog || []), `${new Date().toLocaleTimeString('zh-CN', { hour12: false })} ${line}`]
    }));
  };

  const resetCurrentAnalysis = () => {
    setLastPayload(undefined);
    setWizard((current) => ({
      ...current,
      importedCatalog: undefined,
      catalogTree: [],
      selectedCatalogIds: [],
      analysis: undefined,
      analysisStatus: 'idle',
      analysisLog: current.targetUrl ? [`已重置当前站点分析：${current.targetUrl}`] : [],
      workflowStep: 0,
      lastRunPayload: undefined,
      availableFields: [],
      selectedFields: ['title', 'highest_price', 'description', 'image_urls'],
      missingFields: []
    }));
    message.success('已重置当前站点分析状态');
  };

  const importCatalogJson = async () => {
    setBusy(true);
    appendLog('开始导入目录 JSON');
    try {
      const parsed = tryParseJson(wizard.catalogText);
      const response = await importCatalog(settings, parsed);
      setWizard((current) => ({
        ...current,
        importedCatalog: parsed,
        catalogTree: response.catalog_tree,
        selectedCatalogIds: [],
        analysisLog: [...(current.analysisLog || []), `目录导入完成：${response.leaf_count} 个叶子节点`]
      }));
      message.success(`已导入 ${response.leaf_count} 个叶子目录`);
    } catch (error) {
      const text = userFacingError(error);
      appendLog(`目录导入失败：${text}`);
      message.error(text);
    } finally {
      setBusy(false);
    }
  };

  const runAnalysis = async (options?: { useImportedCatalog?: boolean }) => {
    const useImportedCatalog = options?.useImportedCatalog === true;
    setBusy(true);
    setLastPayload(undefined);
    setWizard((current) => ({
      ...current,
      importedCatalog: useImportedCatalog ? current.importedCatalog : undefined,
      analysisStatus: 'running',
      analysisLog: [
        ...(current.analysisLog || []),
        `开始分析：${current.targetUrl}${useImportedCatalog ? '（带导入目录）' : '（重新发现目录）'}`,
        settings.llm.base_url && settings.llm.model ? `使用 LLM：${settings.llm.model}` : '未启用 LLM：使用规则分析'
      ]
    }));
    try {
      const importedCatalog = useImportedCatalog ? wizard.importedCatalog : undefined;
      const response = await analyzeSite(settings, wizard.targetUrl, wizard.fieldGoal, importedCatalog);
      setWizard((current) => ({
        ...current,
        analysis: response,
        importedCatalog,
        analysisStatus: 'completed',
        analysisLog: [
          ...(current.analysisLog || []),
          `分析完成：HTTP ${response.status_code || '-'}`,
          `目录节点：${catalogCount(response.catalog_tree || [])}`,
          `字段候选：${response.field_candidates?.length || 0}`,
          response.llm_analysis?.enabled ? `LLM 分析：${response.llm_analysis.fallback_used ? '已回退' : '已参与'}` : 'LLM 分析：未启用'
        ],
        catalogTree: response.catalog_tree || [],
        selectedCatalogIds: [],
        availableFields: response.field_candidates || [],
        selectedFields: (response.field_candidates || []).filter((field) => field.selected !== false).map((field) => field.name),
        workflowStep: 3
      }));
      resetWizardExport(wizard.targetUrl, wizard.export.format);
      message.success('站点分析完成，可以直接启动采集');
    } catch (error) {
      const text = userFacingError(error);
      setWizard((current) => ({
        ...current,
        analysisStatus: 'failed',
        analysisLog: [...(current.analysisLog || []), `分析失败：${text}`]
      }));
      message.error(text);
    } finally {
      setBusy(false);
    }
  };

  const launchFromAnalysis = async () => {
    setBusy(true);
    try {
      const payload = buildRunPayload(wizard, settings);
      setLastPayload(payload);
      setWizard((current) => ({
        ...current,
        lastRunPayload: payload,
        analysisLog: [...(current.analysisLog || []), `提交${runModeLabel(current.runMode)}：${payload.target_url}，seed=${seedUrlRows(payload).length}`]
      }));
      const response = await launchRun(settings, wizard.runMode, payload);
      upsertTask({
        task_id: response.task_id,
        run_id: response.run_id,
        target_url: wizard.targetUrl,
        status: response.status,
        mode: wizard.runMode,
        created_at: nowIso(),
        record_count: 0,
        runtime_dir: payload.runtime_dir,
        export_config: payload.export,
        run_payload: payload
      });
      setActiveTaskId(response.task_id);
      message.success(`${runModeLabel(wizard.runMode)}已提交`);
      setPage('detail');
    } catch (error) {
      const text = userFacingError(error);
      appendLog(`任务提交失败：${text}`);
      message.error(text);
    } finally {
      setBusy(false);
    }
  };

  const fieldColumns: ColumnsType<FieldCandidate> = [
    { title: '字段', dataIndex: 'name', width: 150, render: (value) => fieldLabel(value) },
    { title: '原始字段名', dataIndex: 'name', width: 160 },
    { title: '来源', dataIndex: 'source', width: 110, render: (value) => <Tag>{sourceLabel(value)}</Tag> },
    { title: '选择器/API 路径', render: (_, row) => row.selector || row.api_path || '-' },
    { title: '原因', dataIndex: 'reason' }
  ];

  return (
    <Space direction="vertical" size={16} className="page-stack">
      <WorkflowOverview wizard={wizard} settings={settings} activeTask={activeTask} payload={previewPayload} />

      <Card title="站点分析控制台">
        <Form layout="vertical">
          <Form.Item label="目标网站">
            <Input
              value={wizard.targetUrl}
              placeholder="https://example.com"
              onChange={(event: ChangeEvent<HTMLInputElement>) => prepareNewTarget(event.target.value)}
              onBlur={() => prepareNewTarget(wizard.targetUrl, { reset: !analysis || analysis.target_url !== wizard.targetUrl })}
            />
          </Form.Item>
          <Form.Item label="采集目标">
            <Input.TextArea
              rows={3}
              value={wizard.fieldGoal}
              onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setWizard((current) => ({ ...current, fieldGoal: event.target.value }))}
              placeholder="例如：采集商品标题、最高价格、颜色、尺码、描述、图片 URL"
            />
          </Form.Item>
          <Form.Item label="可选：导入目录 JSON">
            <Input.TextArea
              rows={6}
              value={wizard.catalogText}
              onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setWizard((current) => ({ ...current, catalogText: event.target.value }))}
            />
          </Form.Item>
          <Space wrap>
            <Button loading={busy} onClick={importCatalogJson}>导入目录 JSON</Button>
            <Button type="primary" loading={busy} onClick={() => runAnalysis()}>分析站点</Button>
            <Button loading={busy} disabled={!wizard.importedCatalog} onClick={() => runAnalysis({ useImportedCatalog: true })}>带导入目录分析</Button>
            <Button type="primary" loading={busy} disabled={!analysis || !wizard.selectedFields.length} onClick={launchFromAnalysis}>
              用当前分析启动采集
            </Button>
            <Button disabled={busy} onClick={resetCurrentAnalysis}>重置当前分析</Button>
            <Button onClick={() => setPage('wizard')}>进入完整向导</Button>
          </Space>
        </Form>
      </Card>

      <Card title="工作流过程日志">
        <Table
          size="small"
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          rowKey="index"
          columns={[
            { title: '#', dataIndex: 'index', width: 80 },
            { title: '事件', dataIndex: 'message' }
          ]}
          dataSource={(wizard.analysisLog || []).map((item, index) => ({ index: index + 1, message: item }))}
          locale={{ emptyText: '还没有过程日志，先点击“分析站点”。' }}
        />
      </Card>

      {analysis ? (
        <>
          <Card title="站点分析结果">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="目标网址">{analysis.target_url}</Descriptions.Item>
              <Descriptions.Item label="最终网址">{analysis.final_url || '-'}</Descriptions.Item>
              <Descriptions.Item label="HTTP 状态">{analysis.status_code || '-'}</Descriptions.Item>
              <Descriptions.Item label="抓取错误">{analysis.fetch_error || '-'}</Descriptions.Item>
              <Descriptions.Item label="目录总数">{catalogCount(wizard.catalogTree)}</Descriptions.Item>
              <Descriptions.Item label="字段候选">{analysis.field_candidates?.length || 0}</Descriptions.Item>
            </Descriptions>
          </Card>

          <div className="split-grid">
            <Card title="目录树">
              <CatalogTreeView
                nodes={wizard.catalogTree}
                checkable
                selectedIds={wizard.selectedCatalogIds}
                onSelectionChange={(selectedCatalogIds) => setWizard((current) => ({ ...current, selectedCatalogIds }))}
              />
            </Card>
            <Card title="字段选择">
              <FieldSelector
                fields={wizard.availableFields}
                selected={wizard.selectedFields}
                onChange={(selectedFields) => setWizard((current) => ({ ...current, selectedFields }))}
              />
            </Card>
          </div>

          {previewPayload ? (
            <Card title="实际启动参数预览">
              <div className="two-column-grid">
                <Table
                  size="small"
                  pagination={false}
                  rowKey="key"
                  columns={[
                    { title: '参数', dataIndex: 'key', width: 160 },
                    { title: '值', dataIndex: 'value' }
                  ]}
                  dataSource={runPayloadSummary(previewPayload)}
                />
                <Table
                  size="small"
                  pagination={{ pageSize: 8, hideOnSinglePage: true }}
                  rowKey="index"
                  columns={[
                    { title: '#', dataIndex: 'index', width: 64 },
                    { title: '实际会采集的 seed URL', dataIndex: 'url', ellipsis: true }
                  ]}
                  dataSource={seedUrlRows(previewPayload)}
                />
              </div>
            </Card>
          ) : null}

          <Card title="侦察摘要">
            <Table
              size="small"
              pagination={false}
              rowKey="key"
              columns={[
                { title: '指标', dataIndex: 'key', width: 220 },
                { title: '值', dataIndex: 'value' }
              ]}
              dataSource={Object.entries(analysis.recon_summary || {}).map(([key, value]) => ({
                key,
                value: typeof value === 'object' ? JSON.stringify(value) : String(value)
              }))}
            />
          </Card>

          <Card title="字段候选详情">
            <Table size="small" rowKey="name" columns={fieldColumns} dataSource={analysis.field_candidates} pagination={false} />
          </Card>

          <AiManagedPanel
            title="AI 托管与模型分析"
            settings={settings}
            managedMode={settings.managed_ai.enabled ? settings.managed_ai.mode : 'deterministic'}
            managedAi={settings.managed_ai}
            llmAnalysis={analysis.llm_analysis}
          />
        </>
      ) : (
        <Alert
          type="info"
          showIcon
          message="还没有站点分析结果"
          description="输入 URL 后点击“分析站点”。分析完成后会展示目录、字段、实际 seed URL 和启动参数。"
        />
      )}
    </Space>
  );
}
