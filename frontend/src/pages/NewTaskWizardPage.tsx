import { Alert, Button, Card, Checkbox, Form, Input, InputNumber, Radio, Select, Space, Steps, Table, message } from 'antd';
import { useState, type ChangeEvent } from 'react';
import type { RadioChangeEvent } from 'antd';
import { analyzeSite, importCatalog, launchRun, resolveExportPath, validateExportDirectory, resolveFields } from '../api/client';
import { CatalogTreeView } from '../components/CatalogTreeView';
import { FieldSelector } from '../components/FieldSelector';
import { WorkflowOverview } from '../components/WorkflowOverview';
import { catalogCount, useWorkbench } from '../store/workbench';
import { buildRunPayload } from '../utils/runPayload';
import { exportFilename, joinExportPath, nowIso, replaceExportPathSuffix, runModeLabel, tryParseJson, userFacingError } from '../utils/format';

type DirectoryPickerWindow = Window & {
  showDirectoryPicker?: () => Promise<{ name: string }>;
};

export function NewTaskWizardPage() {
  const {
    settings,
    wizard,
    setWizard,
    upsertTask,
    resetWizardExport,
    setPage,
    setActiveTaskId,
    prepareNewTarget,
    tasks,
    activeTaskId
  } = useWorkbench();
  const [step, setStep] = useState(wizard.workflowStep || 0);
  const [busy, setBusy] = useState(false);
  const activeTask = tasks.find((task) => task.task_id === activeTaskId);

  const moveToStep = (next: number) => {
    setStep(next);
    setWizard((current) => ({ ...current, workflowStep: next }));
  };

  const importCatalogJson = async () => {
    setBusy(true);
    try {
      const parsed = tryParseJson(wizard.catalogText);
      const response = await importCatalog(settings, parsed);
      setWizard((current) => ({
        ...current,
        importedCatalog: parsed,
        catalogTree: response.catalog_tree,
        selectedCatalogIds: [],
        analysisLog: [...(current.analysisLog || []), `已导入目录 JSON：${response.leaf_count} 个叶子节点`]
      }));
      message.success(`已导入 ${response.leaf_count} 个叶子目录`);
      moveToStep(2);
    } catch (error) {
      message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const analyze = async (options?: { useImportedCatalog?: boolean }) => {
    const useImportedCatalog = options?.useImportedCatalog === true;
    setBusy(true);
    setWizard((current) => ({
      ...current,
      importedCatalog: useImportedCatalog ? current.importedCatalog : undefined,
      analysisStatus: 'running',
      analysisLog: [
        ...(current.analysisLog || []),
        `开始分析：${current.targetUrl}${useImportedCatalog ? '（带导入目录）' : '（覆盖旧目录）'}`,
        settings.llm.base_url && settings.llm.model ? `使用 LLM：${settings.llm.model}` : '未启用 LLM，使用规则分析'
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
          `目录节点：${response.catalog_tree?.length || 0}`,
          `字段候选：${response.field_candidates?.length || 0}`,
          response.llm_analysis?.enabled ? `LLM 分析：${response.llm_analysis.fallback_used ? '已回退' : '已参与'}` : 'LLM 分析：未启用'
        ],
        catalogTree: response.catalog_tree || [],
        selectedCatalogIds: [],
        availableFields: response.field_candidates,
        selectedFields: response.field_candidates.filter((field) => field.selected !== false).map((field) => field.name),
        workflowStep: 3
      }));
      resetWizardExport(wizard.targetUrl, wizard.export.format);
      message.success('站点分析已完成');
      moveToStep(3);
    } catch (error) {
      setWizard((current) => ({
        ...current,
        analysisStatus: 'failed',
        analysisLog: [...(current.analysisLog || []), `分析失败：${userFacingError(error)}`]
      }));
      message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const resolveNaturalLanguageFields = async () => {
    setBusy(true);
    try {
      const response = await resolveFields(settings, wizard.availableFields, wizard.naturalLanguageFields, wizard.selectedFields);
      setWizard((current) => ({
        ...current,
        selectedFields: response.selected_fields,
        missingFields: response.missing_fields,
        analysisLog: [...(current.analysisLog || []), `自然语言字段解析完成：${response.selected_fields.join(', ') || '-'}`]
      }));
      message.success('字段已解析');
    } catch (error) {
      message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const finalExportPath = wizard.export.output_path || joinExportPath(
    settings.runtime.default_export_dir,
    exportFilename(wizard.targetUrl, wizard.export.format)
  );

  const syncExportFormat = (format: string) => {
    setWizard((current) => ({
      ...current,
      export: {
        ...current.export,
        format: format as typeof current.export.format,
        output_path: replaceExportPathSuffix(
          current.export.output_path || joinExportPath(settings.runtime.default_export_dir, exportFilename(current.targetUrl, format as typeof current.export.format)),
          format as typeof current.export.format
        )
      }
    }));
  };

  const chooseExportDirectory = async () => {
    const picker = window as DirectoryPickerWindow;
    if (!picker.showDirectoryPicker) {
      message.warning('当前浏览器不支持目录选择器，请直接填写后端可访问的本地路径。');
      return;
    }
    try {
      const handle = await picker.showDirectoryPicker();
      setWizard((current) => ({ ...current, browserDirectoryName: handle.name }));
      message.success(`已选择浏览器目录：${handle.name}。后端导出仍以本地路径为准。`);
    } catch {
      message.info('已取消目录选择');
    }
  };

  const validateExportPath = async (create: boolean) => {
    setBusy(true);
    try {
      const directory = settings.runtime.default_export_dir;
      const [directoryStatus, resolvedPath] = await Promise.all([
        validateExportDirectory(settings, directory, create),
        resolveExportPath(settings, directory, wizard.targetUrl, wizard.export.format)
      ]);
      setWizard((current) => ({
        ...current,
        exportDirectoryStatus: {
          ...directoryStatus,
          final_output_path: resolvedPath.final_output_path || joinExportPath(directory, exportFilename(current.targetUrl, current.export.format))
        },
        export: {
          ...current.export,
          output_path: resolvedPath.final_output_path || current.export.output_path
        }
      }));
      message.success('导出路径已检查');
    } catch (error) {
      const fallbackPath = joinExportPath(settings.runtime.default_export_dir, exportFilename(wizard.targetUrl, wizard.export.format));
      setWizard((current) => ({
        ...current,
        exportDirectoryStatus: {
          checked_at: nowIso(),
          normalized_path: settings.runtime.default_export_dir,
          final_output_path: fallbackPath,
          error: userFacingError(error)
        },
        export: { ...current.export, output_path: current.export.output_path || fallbackPath }
      }));
      message.warning(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const launch = async () => {
    setBusy(true);
    try {
      const payload = buildRunPayload(wizard, settings);
      setWizard((current) => ({
        ...current,
        lastRunPayload: payload,
        analysisLog: [...(current.analysisLog || []), `提交${runModeLabel(current.runMode)}：${payload.target_url}`]
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
      message.error(userFacingError(error));
    } finally {
      setBusy(false);
    }
  };

  const steps = [
    {
      title: '基础配置',
      content: (
        <Card title="基础配置">
          <Form layout="vertical">
            <Form.Item label="目标网站">
              <Input
                value={wizard.targetUrl}
                onChange={(event: ChangeEvent<HTMLInputElement>) => prepareNewTarget(event.target.value)}
                onBlur={() => prepareNewTarget(wizard.targetUrl, { reset: !wizard.analysis || wizard.analysis.target_url !== wizard.targetUrl })}
              />
            </Form.Item>
            <Form.Item label="采集目标">
              <Input.TextArea
                rows={3}
                value={wizard.fieldGoal}
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setWizard((current) => ({ ...current, fieldGoal: event.target.value }))}
              />
            </Form.Item>
            <Space>
              <Button type="primary" onClick={() => moveToStep(1)}>
                继续
              </Button>
              <Button onClick={() => setPage('settings')}>打开设置</Button>
            </Space>
          </Form>
        </Card>
      )
    },
    {
      title: '站点分析',
      content: (
        <Card title="站点分析">
          <Space direction="vertical" className="page-stack">
            <Alert type="info" showIcon message="可以直接分析目标网站，也可以先导入目录 JSON 后带目录分析。" />
            <Button type="primary" loading={busy} onClick={() => analyze()}>
              分析站点
            </Button>
          </Space>
        </Card>
      )
    },
    {
      title: '目录',
      content: (
        <Card title="目录导入 / 编辑">
          <Form layout="vertical">
            <Form.Item label="目录 JSON">
              <Input.TextArea
                rows={10}
                value={wizard.catalogText}
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setWizard((current) => ({ ...current, catalogText: event.target.value }))}
              />
            </Form.Item>
            <Space>
              <Button loading={busy} onClick={importCatalogJson}>导入目录 JSON</Button>
              <Button type="primary" loading={busy} onClick={() => analyze({ useImportedCatalog: true })}>带目录分析</Button>
            </Space>
            <div className="section-gap">
              <CatalogTreeView
                nodes={wizard.catalogTree}
                checkable
                selectedIds={wizard.selectedCatalogIds}
                onSelectionChange={(selectedCatalogIds) => setWizard((current) => ({ ...current, selectedCatalogIds }))}
              />
            </div>
          </Form>
        </Card>
      )
    },
    {
      title: '字段',
      content: (
        <Card title="字段选择">
          <Space direction="vertical" className="page-stack">
            <Input.Search
              value={wizard.naturalLanguageFields}
              enterButton="解析字段"
              loading={busy}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setWizard((current) => ({ ...current, naturalLanguageFields: event.target.value }))}
              onSearch={resolveNaturalLanguageFields}
            />
            {wizard.missingFields.length ? <Alert type="warning" showIcon message={`未找到字段：${wizard.missingFields.join(', ')}`} /> : null}
            <FieldSelector
              fields={wizard.availableFields}
              selected={wizard.selectedFields}
              onChange={(selectedFields) => setWizard((current) => ({ ...current, selectedFields }))}
            />
          </Space>
        </Card>
      )
    },
    {
      title: '运行',
      content: (
        <Card title="运行模式">
          <Space direction="vertical" className="page-stack">
            <Radio.Group
              value={wizard.runMode}
              onChange={(event: RadioChangeEvent) => setWizard((current) => ({ ...current, runMode: event.target.value }))}
            >
              <Radio.Button value="test">试跑</Radio.Button>
              <Radio.Button value="full">全量运行</Radio.Button>
            </Radio.Group>
            <Form layout="inline">
              <Form.Item label="试跑上限">
                <InputNumber
                  min={1}
                  max={10000}
                  value={wizard.testLimit}
                  onChange={(value) => setWizard((current) => ({ ...current, testLimit: Number(value || 100) }))}
                />
              </Form.Item>
              <Form.Item label="并发 worker">
                <InputNumber min={1} max={128} value={settings.runtime.item_workers} disabled />
              </Form.Item>
            </Form>
            <Alert type="success" showIcon message={`${catalogCount(wizard.catalogTree)} 个目录节点，已勾选 ${wizard.selectedCatalogIds.length} 个目录节点，已选择 ${wizard.selectedFields.length} 个字段`} />
            <WorkflowOverview wizard={wizard} settings={settings} activeTask={activeTask} />
          </Space>
        </Card>
      )
    },
    {
      title: '导出',
      content: (
        <Card title="导出计划">
          <Form layout="vertical">
            <Form.Item label="导出格式">
              <Select
                value={wizard.export.format}
                options={['xlsx', 'csv', 'json', 'sqlite', 'db'].map((value) => ({ value, label: value }))}
                onChange={syncExportFormat}
              />
            </Form.Item>
            <Form.Item label="导出目录">
              <Space.Compact className="full-width">
                <Input value={settings.runtime.default_export_dir} readOnly />
                <Button onClick={chooseExportDirectory}>选择目录</Button>
                <Button loading={busy} onClick={() => validateExportPath(false)}>检查路径</Button>
                <Button loading={busy} onClick={() => validateExportPath(true)}>检查并创建</Button>
              </Space.Compact>
              <div className="form-help">目录选择器只代表浏览器授权目录；后端导出仍以服务器可访问路径为准。</div>
            </Form.Item>
            <Form.Item label="最终文件路径">
              <Input
                value={finalExportPath}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setWizard((current) => ({ ...current, export: { ...current.export, output_path: event.target.value } }))}
                onBlur={() => setWizard((current) => ({ ...current, export: { ...current.export, output_path: replaceExportPathSuffix(current.export.output_path, current.export.format) } }))}
              />
            </Form.Item>
            {wizard.exportDirectoryStatus?.error ? (
              <Alert type="warning" showIcon message={wizard.exportDirectoryStatus.error} />
            ) : wizard.exportDirectoryStatus ? (
              <Alert
                type={wizard.exportDirectoryStatus.writable === false ? 'warning' : 'success'}
                showIcon
                message={`路径检查：${wizard.exportDirectoryStatus.exists ? '目录存在' : '目录不存在'}，${wizard.exportDirectoryStatus.writable ? '可写' : '写入状态未知'}`}
              />
            ) : null}
            {wizard.browserDirectoryName ? <Alert type="info" showIcon message={`浏览器目录选择：${wizard.browserDirectoryName}`} /> : null}
            <Checkbox checked disabled>
              随导出请求保存字段映射
            </Checkbox>
            <div className="section-gap">
              <Button type="primary" size="large" loading={busy} onClick={launch}>
                提交{runModeLabel(wizard.runMode)}
              </Button>
            </div>
          </Form>
        </Card>
      )
    }
  ];

  return (
    <Space direction="vertical" size={16} className="page-stack">
      <WorkflowOverview wizard={wizard} settings={settings} activeTask={activeTask} compact />
      <Steps current={step} items={steps.map(({ title }) => ({ title }))} />
      {steps[step].content}
      <Space>
        <Button disabled={step === 0} onClick={() => moveToStep(step - 1)}>上一步</Button>
        <Button disabled={step >= steps.length - 1} onClick={() => moveToStep(step + 1)}>下一步</Button>
      </Space>
    </Space>
  );
}
