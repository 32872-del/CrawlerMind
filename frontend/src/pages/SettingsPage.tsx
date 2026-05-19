import { Alert, Button, Card, Form, Input, InputNumber, Radio, Select, Space, Switch, Tag, message } from 'antd';
import type { RadioChangeEvent } from 'antd';
import { useState, type ChangeEvent } from 'react';
import { fetchLlmModels, validateExportDirectory } from '../api/client';
import { useWorkbench } from '../store/workbench';
import type { LlmModelOption } from '../types/workflow';
import { apiModeLabel, userFacingError } from '../utils/format';

const providerPresets = [
  {
    key: 'openai-compatible',
    label: 'OpenAI 兼容',
    provider: 'openai-compatible',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini'
  },
  {
    key: 'deepseek-compatible',
    label: 'DeepSeek 兼容',
    provider: 'deepseek-compatible',
    base_url: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat'
  },
  {
    key: 'siliconflow-compatible',
    label: 'SiliconFlow 兼容',
    provider: 'siliconflow-compatible',
    base_url: 'https://api.siliconflow.cn/v1',
    model: 'Qwen/Qwen2.5-72B-Instruct'
  },
  {
    key: 'ollama-local',
    label: '本地 Ollama 类',
    provider: 'ollama-like',
    base_url: 'http://127.0.0.1:11434/v1',
    model: 'llama3.1:8b'
  },
  {
    key: 'custom-relay',
    label: '自定义中转',
    provider: 'custom-relay',
    base_url: 'http://127.0.0.1:8001/v1',
    model: ''
  }
];

export function SettingsPage() {
  const { settings, setSettings } = useWorkbench();
  const [models, setModels] = useState<LlmModelOption[]>(settings.llm.model ? [{ id: settings.llm.model }] : []);
  const [modelError, setModelError] = useState('');
  const [modelLoading, setModelLoading] = useState(false);
  const [pathChecking, setPathChecking] = useState(false);
  const [pathMessage, setPathMessage] = useState('');

  const applyPreset = (key: string) => {
    const preset = providerPresets.find((item) => item.key === key);
    if (!preset) return;
    setSettings((current) => ({
      ...current,
      llm: {
        ...current.llm,
        provider: preset.provider,
        base_url: preset.base_url,
        model: preset.model || current.llm.model
      }
    }));
    message.success(`已套用 ${preset.label} 预设，仍可手动修改。`);
  };

  const loadModels = async () => {
    setModelLoading(true);
    setModelError('');
    try {
      const response = await fetchLlmModels(settings);
      const nextModels = response.models || [];
      setModels(nextModels);
      if (nextModels.length && !settings.llm.model) {
        setSettings((current) => ({ ...current, llm: { ...current.llm, model: nextModels[0].id } }));
      }
      message.success(`获取到 ${nextModels.length} 个模型`);
    } catch (error) {
      setModelError(userFacingError(error));
    } finally {
      setModelLoading(false);
    }
  };

  const checkExportDir = async (create: boolean) => {
    setPathChecking(true);
    setPathMessage('');
    try {
      const response = await validateExportDirectory(settings, settings.runtime.default_export_dir, create);
      const parts = [
        response.exists ? '目录存在' : '目录不存在',
        response.created ? '已尝试创建' : '',
        response.writable ? '可写' : '不可写'
      ].filter(Boolean);
      setPathMessage(parts.join('，') || '路径已检查');
      message.success('导出目录检查完成');
    } catch (error) {
      setPathMessage(userFacingError(error));
    } finally {
      setPathChecking(false);
    }
  };

  return (
    <Space direction="vertical" size={16} className="page-stack">
      <Card title="后端与运行参数">
        <Form layout="vertical">
          <Form.Item label="CLM API 地址">
            <Input
              value={settings.apiBaseUrl}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, apiBaseUrl: event.target.value }))}
            />
          </Form.Item>
          <Form.Item label="API 模式">
            <Radio.Group
              value={settings.apiMode}
              onChange={(event: RadioChangeEvent) => setSettings((current) => ({ ...current, apiMode: event.target.value }))}
            >
              <Radio.Button value="auto">{apiModeLabel('auto')}</Radio.Button>
              <Radio.Button value="live">{apiModeLabel('live')}</Radio.Button>
              <Radio.Button value="mock">{apiModeLabel('mock')}</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item label="并发 worker">
            <InputNumber
              min={1}
              max={128}
              value={settings.runtime.item_workers}
              onChange={(value) => setSettings((current) => ({ ...current, runtime: { ...current.runtime, item_workers: Number(value || 1) } }))}
            />
          </Form.Item>
          <Form.Item label="超时时间（秒）">
            <InputNumber
              min={1}
              max={300}
              value={settings.runtime.timeout_seconds}
              onChange={(value) => setSettings((current) => ({ ...current, runtime: { ...current.runtime, timeout_seconds: Number(value || 30) } }))}
            />
          </Form.Item>
          <Form.Item label="默认运行目录">
            <Input
              value={settings.runtime.default_runtime_dir}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, runtime: { ...current.runtime, default_runtime_dir: event.target.value } }))}
            />
          </Form.Item>
          <Form.Item label="默认导出目录">
            <Space.Compact className="full-width">
              <Input
                value={settings.runtime.default_export_dir}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, runtime: { ...current.runtime, default_export_dir: event.target.value } }))}
              />
              <Button loading={pathChecking} onClick={() => checkExportDir(false)}>检查</Button>
              <Button loading={pathChecking} onClick={() => checkExportDir(true)}>检查并创建</Button>
            </Space.Compact>
            {pathMessage ? <div className="form-help">{pathMessage}</div> : null}
          </Form.Item>
          <Form.Item label="浏览器模式">
            <Switch
              checked={settings.runtime.browser_enabled}
              onChange={(checked) => setSettings((current) => ({ ...current, runtime: { ...current.runtime, browser_enabled: checked } }))}
            />
          </Form.Item>
          <Form.Item label="代理地址">
            <Input
              value={settings.runtime.proxy_url}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, runtime: { ...current.runtime, proxy_url: event.target.value } }))}
            />
          </Form.Item>
        </Form>
      </Card>

      <Card title="AI 托管模式">
        <Form layout="vertical">
          <Alert
            type="info"
            showIcon
            message="AI 托管模式会把模型配置和托管策略随试跑/全量运行一起提交给后端；关闭后保持规则采集模式。"
          />
          <Form.Item className="section-gap" label="启用 AI 托管模式">
            <Switch
              checked={settings.managed_ai.enabled}
              onChange={(enabled) => setSettings((current) => ({
                ...current,
                managed_ai: {
                  ...current.managed_ai,
                  enabled,
                  analysis_enabled: enabled ? current.managed_ai.analysis_enabled : false
                }
              }))}
            />
          </Form.Item>
          <Form.Item label="托管模式">
            <Radio.Group
              value={settings.managed_ai.mode}
              onChange={(event: RadioChangeEvent) => setSettings((current) => ({
                ...current,
                managed_ai: { ...current.managed_ai, mode: event.target.value }
              }))}
            >
              <Radio.Button value="analysis_only">仅分析增强</Radio.Button>
              <Radio.Button value="supervised">监督托管</Radio.Button>
              <Radio.Button value="full_managed">全托管</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <div className="two-column-grid">
            <Form.Item label="站点分析使用模型">
              <Switch
                checked={settings.managed_ai.analysis_enabled}
                onChange={(checked) => setSettings((current) => ({
                  ...current,
                  managed_ai: { ...current.managed_ai, analysis_enabled: checked }
                }))}
              />
            </Form.Item>
            <Form.Item label="运行前计划审阅">
              <Switch
                checked={settings.managed_ai.plan_review_enabled}
                onChange={(checked) => setSettings((current) => ({
                  ...current,
                  managed_ai: { ...current.managed_ai, plan_review_enabled: checked }
                }))}
              />
            </Form.Item>
            <Form.Item label="运行时监控诊断">
              <Switch
                checked={settings.managed_ai.runtime_diagnosis_enabled}
                onChange={(checked) => setSettings((current) => ({
                  ...current,
                  managed_ai: { ...current.managed_ai, runtime_diagnosis_enabled: checked }
                }))}
              />
            </Form.Item>
            <Form.Item label="运行后质量诊断">
              <Switch
                checked={settings.managed_ai.post_run_diagnosis_enabled}
                onChange={(checked) => setSettings((current) => ({
                  ...current,
                  managed_ai: { ...current.managed_ai, post_run_diagnosis_enabled: checked }
                }))}
              />
            </Form.Item>
          </div>
          <div className="section-gap">
            <Tag color={settings.managed_ai.enabled ? 'processing' : 'default'}>{settings.managed_ai.enabled ? 'AI 托管已启用' : '规则模式'}</Tag>
            <Tag color={settings.managed_ai.plan_review_enabled ? 'success' : 'default'}>运行前计划审阅</Tag>
            <Tag color={settings.managed_ai.post_run_diagnosis_enabled ? 'success' : 'default'}>运行后质量诊断</Tag>
          </div>
        </Form>
      </Card>

      <Card title="LLM 模型配置">
        <Form layout="vertical">
          <Form.Item label="服务商预设">
            <Space wrap>
              {providerPresets.map((preset) => (
                <Button key={preset.key} onClick={() => applyPreset(preset.key)}>
                  {preset.label}
                </Button>
              ))}
            </Space>
          </Form.Item>
          <Form.Item label="服务商标识">
            <Input
              value={settings.llm.provider}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, llm: { ...current.llm, provider: event.target.value } }))}
            />
          </Form.Item>
          <Form.Item label="接口 Base URL">
            <Input
              value={settings.llm.base_url}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, llm: { ...current.llm, base_url: event.target.value } }))}
            />
          </Form.Item>
          <Form.Item label="API Key">
            <Input.Password
              value={settings.llm.api_key}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, llm: { ...current.llm, api_key: event.target.value } }))}
            />
          </Form.Item>
          <Form.Item label="模型">
            <Space.Compact className="full-width">
              <Select
                showSearch
                value={settings.llm.model || undefined}
                placeholder="先获取模型列表，或手动输入"
                options={models.map((model) => ({ value: model.id, label: model.label || model.id }))}
                onChange={(model) => setSettings((current) => ({ ...current, llm: { ...current.llm, model } }))}
              />
              <Button loading={modelLoading} onClick={loadModels}>获取模型列表</Button>
            </Space.Compact>
            <Input
              className="section-gap-small"
              placeholder="模型列表不可用时，可在这里手动输入模型名"
              value={settings.llm.model}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSettings((current) => ({ ...current, llm: { ...current.llm, model: event.target.value } }))}
            />
            {modelError ? <Alert className="section-gap-small" type="warning" showIcon message={modelError} /> : null}
          </Form.Item>
          <Alert
            type="info"
            showIcon
            message="设置会自动保存到本机浏览器 localStorage；API Key 只用于本地工作台请求，不会写入仓库。"
          />
          <div className="section-gap">
            <Tag color={settings.llm.model ? 'success' : 'warning'}>{settings.llm.model ? '模型已选择' : '模型未选择'}</Tag>
            <Tag color={settings.llm.base_url ? 'success' : 'warning'}>{settings.llm.base_url ? '接口地址已填写' : '接口地址未填写'}</Tag>
          </div>
          <Button className="section-gap" type="primary" onClick={() => message.success('设置已保存在本机浏览器')}>
            保存设置
          </Button>
        </Form>
      </Card>
    </Space>
  );
}
