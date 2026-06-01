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
  const contractItems = [
    {
      title: 'Athletic Essentials Stripe Jersey Polo Shirt',
      highest_price: 29.99,
      currency: 'GBP',
      color: 'Rich Navy Stripe',
      product_url: 'https://www.superdry.com/womens/tops/details/268112'
    },
    {
      title: 'Vintage Logo Embroidered T-Shirt',
      highest_price: 19.99,
      currency: 'GBP',
      color: 'Optic White',
      product_url: 'https://www.superdry.com/womens/tops/details/268113'
    },
    {
      title: 'Essential Logo Hoodie',
      highest_price: 54.99,
      currency: 'GBP',
      color: 'Soft Pink',
      product_url: 'https://www.superdry.com/womens/hoodies/details/268114'
    }
  ];
  const contractResult = {
    schema_version: 'contract-extraction-result/v1',
    site: 'superdry.com',
    parser_strategy: 'gtm_data_attribute_extractor',
    item_count: contractItems.length,
    fields_found: ['title', 'highest_price', 'currency', 'color', 'product_url'],
    items: contractItems
  };
  return {
    task_id: taskId,
    run_id: runId,
    kind: 'mock_profile_run',
    status: 'completed',
    record_count: 42,
    accepted: true,
    progress: {
      status: 'completed',
      records_saved: 42,
      claimed: 50,
      failed: 1,
      queued: 0,
      done: 42,
      completion: 1,
      quality: {
        quality_gate: { severity: 'warn' },
        field_completeness: { title: 1, highest_price: 1, color: 0.86, product_url: 1 },
        duplicate_rate: 0,
        failed_url_count: 1,
        pagination_stop_reason: 'test_limit_reached'
      }
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
    ],
    llm_traces: [
      {
        stage: 'managed_actions',
        status: 'ok',
        provider: 'mock',
        model: 'gpt-4o-mini',
        duration_ms: 218,
        input_summary: { preview: '发现页面包含 GTM 商品数据和 extraction contract，可先执行合同抽取。' },
        output_summary: { preview: '规划 extract_from_contract，并在成功后准备重跑。' },
        created_at: new Date().toISOString()
      }
    ],
    evidence_pack: {
      recommended_focus: ['contract_extraction', 'field_coverage'],
      failure_evidence: { failure_buckets: { field_missing: 1 } },
      access_evidence_request: { source: 'mock', include_html: true },
      access_evidence: {
        summary: { challenge_like: false, recommended_runtime: 'static', missing_evidence: [] },
        xhr_samples: [],
        runtime_events: [],
        decision_hints: ['GTM data attributes contain product-like records']
      }
    },
    managed_actions: [
      {
        created_at: new Date(Date.now() - 60_000).toISOString(),
        executed: true,
        result: {
          schema_version: 'managed-action-result/v1',
          plan: {
            source: 'mock',
            actions: [
              {
                action: 'extract_from_contract',
                priority: 'medium',
                reason: '演示错误可见性：缺少 evidence 时应显示中文原因。',
                params: { contract: { site: 'example.com', parser_strategy: { name: 'gtm_data_attribute_extractor' } } }
              }
            ]
          },
          results: [{ action: 'extract_from_contract', ok: false, error: 'missing extraction evidence' }],
          profile_patch: {},
          run_overrides: {},
          rerun_ready: false
        }
      },
      {
        created_at: new Date().toISOString(),
        executed: true,
        result: {
          schema_version: 'managed-action-result/v1',
          plan: {
            source: 'mock',
            reasoning_summary: '页面证据中已有可执行抽取合同，先用 contract extractor 抽取商品，再准备下一轮重跑。',
            actions: [
              {
                action: 'extract_from_contract',
                priority: 'high',
                reason: 'GTM data attributes expose product title, price, color and URL.',
                params: {
                  contract: {
                    site: 'superdry.com',
                    parser_strategy: { name: 'gtm_data_attribute_extractor' }
                  },
                  source_url: 'https://www.superdry.com/womens/tops',
                  max_items: 5
                }
              },
              { action: 'prepare_rerun', priority: 'medium', reason: '把合同抽取结果作为下一轮运行证据。', params: {} }
            ]
          },
          results: [
            {
              action: 'extract_from_contract',
              ok: true,
              summary: 'contract extractor produced 3 items',
              extracted_items: contractItems,
              fields_found: contractResult.fields_found,
              evidence: {
                action: 'extract_from_contract',
                contract_site: 'superdry.com',
                parser_strategy: 'gtm_data_attribute_extractor',
                item_count: contractItems.length,
                fields_found: contractResult.fields_found,
                sample_items: contractItems.slice(0, 5)
              }
            },
            { action: 'prepare_rerun', ok: true, summary: '已准备基于合同抽取结果的重跑上下文。' }
          ],
          evidence: {
            schema_version: 'managed-action-evidence/v1',
            access: { contract_site: 'superdry.com', item_count: contractItems.length },
            items: [{ contract_site: 'superdry.com', item_count: contractItems.length }]
          },
          profile_patch: {},
          run_overrides: { extraction_result: contractResult },
          rerun_ready: true
        }
      }
    ],
    managed_steps: [
      {
        schema_version: 'managed-step/v1',
        created_at: new Date().toISOString(),
        stage: 'quality_review',
        status_before: 'completed',
        progress: {},
        evidence_pack: {},
        action_record: {
          created_at: new Date().toISOString(),
          executed: true,
          result: {
            schema_version: 'managed-action-result/v1',
            plan: {
              source: 'mock',
              actions: [{ action: 'extract_from_contract', priority: 'high', reason: '合同抽取已完成，进入质量复核。', params: {} }]
            },
            results: [{ action: 'extract_from_contract', ok: true, summary: '合同抽取质量可用于下一轮重跑。' }],
            run_overrides: { extraction_result: contractResult },
            rerun_ready: true
          }
        },
        child_run: null
      }
    ]
  };
}

export function mockRunEvents(taskId: string): RunEventsResponse {
  return {
    task_id: taskId,
    events: [
      { time: new Date().toISOString(), type: '任务创建', message: 'Profile 试跑任务已创建', data: {} },
      { time: new Date().toISOString(), type: 'managed_step_executed', message: 'AI 执行 extract_from_contract，合同抽取返回 3 条商品样例。', data: { action: 'extract_from_contract', item_count: 3 } },
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
