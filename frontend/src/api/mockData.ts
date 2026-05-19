import type {
  CatalogNode,
  ExportResult,
  FieldCandidate,
  FieldResolution,
  LlmModelListResponse,
  RunEventsResponse,
  RunLaunchResponse,
  RunStatusResponse,
  SiteAnalysis
} from '../types/workflow';

export const mockCatalogTree: CatalogNode[] = [
  {
    id: 'women',
    label: '女装',
    path: ['女装'],
    source: 'mock',
    children: [
      {
        id: 'women-shoes',
        label: '鞋履',
        url: 'https://shop.test/women/shoes',
        path: ['女装', '鞋履'],
        level1: '女装',
        level2: '鞋履',
        source: 'mock'
      },
      {
        id: 'women-leggings',
        label: '裤装',
        url: 'https://shop.test/women/leggings',
        path: ['女装', '裤装'],
        level1: '女装',
        level2: '裤装',
        source: 'mock'
      }
    ]
  }
];

export const mockFields: FieldCandidate[] = [
  { name: 'title', label: '商品标题', selected: true, source: 'dom', selector: 'h1', confidence: 0.92 },
  { name: 'highest_price', label: '最高价格', selected: true, source: 'dom', selector: '.price', confidence: 0.88 },
  { name: 'colors', label: '颜色', selected: true, source: 'default', confidence: 0.52 },
  { name: 'sizes', label: '尺码', selected: true, source: 'default', confidence: 0.52 },
  { name: 'description', label: '商品描述', selected: true, source: 'dom', selector: '.description', confidence: 0.77 },
  { name: 'image_urls', label: '商品图 URL', selected: true, source: 'dom', selector: 'img@src', confidence: 0.81 }
];

export function mockSiteAnalysis(targetUrl: string): SiteAnalysis {
  return {
    schema_version: 'site-analysis/v1',
    target_url: targetUrl,
    final_url: targetUrl,
    status_code: 200,
    catalog_tree: mockCatalogTree,
    field_candidates: mockFields,
    profile: {
      name: 'mock-profile',
      crawl_preferences: { seed_urls: ['https://shop.test/women/shoes'], seed_kind: 'list' },
      target_fields: mockFields.map((field) => field.name)
    },
    llm_analysis: {
      enabled: true,
      mode: 'analysis_only',
      summary: '演示模型建议先用列表页试跑，再扩展到全量目录。',
      fallback_used: false
    },
    recon_summary: {
      framework: '静态页面',
      rendering: 'SSR',
      anti_bot: { detected: false, label: '未发现明显拦截' },
      item_count: 24
    }
  };
}

export function mockFieldResolution(selected: string[]): FieldResolution {
  const fields = selected.length ? selected : ['title', 'highest_price', 'image_urls'];
  return {
    schema_version: 'field-resolution/v1',
    selected_fields: fields,
    resolved_fields: mockFields.filter((field) => fields.includes(field.name)),
    missing_fields: [],
    needs_refinement: false
  };
}

export function mockRunLaunch(mode: 'test' | 'full'): RunLaunchResponse {
  const id = `${mode}-${Math.random().toString(16).slice(2, 8)}`;
  return { task_id: id, run_id: `${mode}-run-${id}`, status: 'running' };
}

export function mockRunStatus(taskId: string, runId: string): RunStatusResponse {
  return {
    task_id: taskId,
    run_id: runId,
    kind: 'mock_profile_run',
    status: 'running',
    record_count: 42,
    accepted: false,
    progress: {
      status: 'running',
      records_saved: 42,
      claimed: 50,
      failed: 1,
      queued: 8,
      done: 42,
      completion: 0.72,
      quality: { quality_gate: { severity: 'warn' } }
    },
    managed_mode: 'supervised',
    managed_ai: {
      enabled: true,
      mode: 'supervised',
      analysis_enabled: true,
      plan_review_enabled: true,
      runtime_diagnosis_enabled: true,
      post_run_diagnosis_enabled: true,
      model: 'gpt-4o-mini'
    },
    ai_decisions: [
      { stage: 'plan_review', decision: '建议先保留 title/highest_price/image_urls 字段进行试跑。' }
    ],
    ai_diagnostics: [
      { stage: 'runtime', message: '当前失败数较低，继续观察即可。' }
    ],
    ai_repair_suggestions: [
      { field: 'sizes', suggestion: '如果尺码缺失，下一轮可以开启详情页补采。' }
    ]
  };
}

export function mockRunEvents(taskId: string): RunEventsResponse {
  return {
    task_id: taskId,
    events: [
      { time: new Date().toISOString(), type: '任务创建', message: 'Profile 试跑任务已创建', data: {} },
      { time: new Date().toISOString(), type: '批次进度', message: '已保存 42 条商品记录', data: { records_saved: 42 } }
    ]
  };
}

export function mockExport(runId: string, format: string, outputPath: string): ExportResult {
  return {
    schema_version: 'export-result/v1',
    run_id: runId,
    format,
    output_path: outputPath || `dev_logs/exports/${runId}.${format}`,
    record_count: 42
  };
}

export function mockLlmModels(provider: string): LlmModelListResponse {
  return {
    provider,
    status: 'mock',
    raw_count: 4,
    models: [
      { id: 'gpt-4o-mini', label: 'gpt-4o-mini', provider },
      { id: 'deepseek-chat', label: 'deepseek-chat', provider },
      { id: 'Qwen/Qwen2.5-72B-Instruct', label: 'Qwen2.5 72B Instruct', provider },
      { id: 'llama3.1:8b', label: 'llama3.1:8b', provider }
    ]
  };
}
