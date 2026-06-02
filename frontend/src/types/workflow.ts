export type ApiMode = 'auto' | 'live' | 'mock';
export type WorkbenchPage = 'dashboard' | 'wizard' | 'analysis' | 'detail' | 'history' | 'settings' | 'oneClickCrawl';
export type RunStatus = 'idle' | 'queued' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed' | 'unknown';
export type ExportFormat = 'json' | 'csv' | 'xlsx' | 'sqlite' | 'db';
export type UiMode = 'compact' | 'standard';
export type ManagedAiMode = 'analysis_only' | 'supervised' | 'full_managed';

export interface LlmConfig {
  provider: string;
  base_url: string;
  api_key: string;
  model: string;
  reasoning_effort?: 'low' | 'medium' | 'high' | 'xhigh';
  stream?: boolean;
  timeout_seconds?: number;
  max_tokens?: number;
}

export interface ManagedAiConfig {
  enabled: boolean;
  mode: ManagedAiMode;
  analysis_enabled: boolean;
  plan_review_enabled: boolean;
  runtime_diagnosis_enabled: boolean;
  post_run_diagnosis_enabled: boolean;
}

export interface ManagedAiPayload extends ManagedAiConfig {
  model?: string;
}

export interface LlmModelOption {
  id: string;
  label?: string;
  provider?: string;
}

export interface LlmModelListResponse {
  provider?: string;
  models: LlmModelOption[];
  raw_count?: number;
  status?: string;
  error?: string;
}

export interface RuntimeConfig {
  item_workers: number;
  timeout_seconds: number;
  max_retries: number;
  browser_enabled: boolean;
  proxy_url: string;
  default_runtime_dir: string;
  default_export_dir: string;
}

export interface SettingsState {
  apiBaseUrl: string;
  apiMode: ApiMode;
  llm: LlmConfig;
  managed_ai: ManagedAiConfig;
  runtime: RuntimeConfig;
  uiMode: UiMode;
}

export interface CatalogNode {
  id: string;
  label: string;
  url?: string;
  path: string[];
  level1?: string;
  level2?: string;
  level3?: string;
  source?: string;
  children?: CatalogNode[];
  graphql_category_uid?: string;
  [key: string]: unknown;
}

export interface FieldCandidate {
  name: string;
  label?: string;
  selected?: boolean;
  source?: string;
  selector?: string;
  api_path?: string;
  confidence?: number;
  reason?: string;
}

export interface SiteAnalysis {
  schema_version: string;
  target_url: string;
  final_url?: string;
  status_code?: number;
  fetch_error?: string;
  catalog_tree: CatalogNode[];
  discovered_catalog_tree?: CatalogNode[];
  imported_catalog_tree?: CatalogNode[];
  field_candidates: FieldCandidate[];
  profile: Record<string, unknown>;
  llm_analysis?: Record<string, unknown>;
  recon_summary?: Record<string, unknown>;
}

export interface FieldResolution {
  schema_version: string;
  selected_fields: string[];
  resolved_fields: FieldCandidate[];
  missing_fields: string[];
  needs_refinement: boolean;
}

export interface ExportConfig {
  format: ExportFormat;
  output_path: string;
  template_path?: string;
  field_mapping: Record<string, string>;
}

export interface ExportPathStatus {
  checked_at?: string;
  exists?: boolean;
  created?: boolean;
  writable?: boolean;
  normalized_path?: string;
  final_output_path?: string;
  error?: string;
  source?: 'backend' | 'local' | 'browser-picker';
}

export interface RunRequest {
  target_url: string;
  profile: Record<string, unknown>;
  catalog_nodes: CatalogNode[];
  selected_fields: string[];
  export: ExportConfig;
  run_mode: string;
  item_workers: number;
  max_sites: number;
  test_limit: number;
  runtime_dir: string;
  managed_ai?: ManagedAiPayload;
  llm?: Partial<LlmConfig> & { enabled?: boolean };
}

export interface RunLaunchResponse {
  task_id: string;
  run_id: string;
  status: RunStatus | string;
}

export interface RunProgress {
  status?: string;
  records_saved?: number;
  claimed?: number;
  failed?: number;
  queued?: number;
  done?: number;
  completion?: number;
  quality?: Record<string, unknown>;
}

export interface RunStatusResponse {
  task_id: string;
  kind?: string;
  run_id: string;
  status: RunStatus | string;
  record_count: number;
  accepted: boolean;
  error?: string;
  progress?: RunProgress;
  export?: ExportResult;
  managed_mode?: ManagedAiMode | string;
  managed_ai?: ManagedAiPayload | Record<string, unknown>;
  ai_decisions?: unknown[];
  ai_diagnostics?: unknown[] | Record<string, unknown> | null;
  ai_repair_suggestions?: unknown[];
  managed_actions?: ManagedActionRecord[];
  managed_steps?: ManagedStepRecord[];
  parent_task_id?: string;
  repair_source?: string;
  managed_auto_repair?: ManagedAutoRepairRecord | null;
  llm_traces?: LlmTraceRecord[];
  evidence_pack?: Record<string, unknown>;
}

export interface RunEvent {
  time?: string;
  type: string;
  message: string;
  data?: Record<string, unknown>;
}

export interface RunEventsResponse {
  task_id: string;
  events: RunEvent[];
}

export interface ExportResult {
  schema_version?: string;
  run_id: string;
  format: string;
  output_path: string;
  record_count?: number;
}

export interface ManagedActionRequest {
  execute?: boolean;
  use_llm?: boolean;
  run_kind?: 'test' | 'full';
  apply_diagnostics?: boolean;
  extra_context?: Record<string, unknown>;
  extra_overrides?: Record<string, unknown>;
  managed_ai?: ManagedAiPayload;
  llm?: Partial<LlmConfig> & { enabled?: boolean };
}

export interface ManagedStepRequest extends ManagedActionRequest {
  start_child_run?: boolean;
}

export interface ManagedActionRecord {
  created_at?: string;
  executed?: boolean;
  result?: {
    schema_version?: string;
    plan?: {
      source?: string;
      reasoning_summary?: string;
      actions?: Array<Record<string, unknown>>;
    };
    results?: Array<Record<string, unknown>>;
    evidence?: Record<string, unknown>;
    profile_patch?: Record<string, unknown>;
    run_overrides?: Record<string, unknown>;
    rerun_ready?: boolean;
  };
}

export interface ManagedStepRecord {
  schema_version?: string;
  created_at?: string;
  stage?: string;
  status_before?: string;
  progress?: Record<string, unknown>;
  evidence_pack?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
  action_record?: ManagedActionRecord & { task_id?: string };
  child_run?: RunLaunchResponse | null;
}

export interface ManagedStepResponse extends ManagedStepRecord {
  task_id: string;
}

export interface LlmTraceRecord {
  stage?: string;
  status?: string;
  provider?: string;
  model?: string;
  duration_ms?: number;
  input_summary?: Record<string, unknown>;
  output_summary?: Record<string, unknown>;
  error?: string;
  created_at?: string;
}

export interface ManagedRepairRunResponse extends RunLaunchResponse {
  parent_task_id?: string;
  repair_source?: string;
  patch_application?: Record<string, unknown>;
  managed_action?: ManagedActionRecord & { task_id?: string };
}

export interface ManagedAutoRepairRecord {
  attempted?: boolean;
  reason?: string;
  child_task_id?: string;
  child_run_id?: string;
  created_at?: string;
  managed_action?: ManagedActionRecord & { task_id?: string };
}

export interface FailureDiagnosis {
  category: string;
  severity: 'critical' | 'warning' | 'info';
  evidence: string;
  affected_fields: string[];
  repair_actions: string[];
  confidence: number;
}

export interface DiagnosisReport {
  diagnoses: FailureDiagnosis[];
  overall_health: 'healthy' | 'degraded' | 'critical';
  recommended_focus: string[];
  auto_repairable: boolean;
}

export interface AutoRepairCycle {
  cycle: number;
  diagnosis: DiagnosisReport;
  actions_taken: string[];
  health_before: string;
  health_after: string;
  improved: boolean;
}

export interface AutoRepairLoopResult {
  total_cycles: number;
  converged: boolean;
  final_health: 'healthy' | 'degraded' | 'critical';
  cycles: AutoRepairCycle[];
}

export interface WorkbenchTask {
  task_id: string;
  run_id: string;
  target_url: string;
  status: RunStatus | string;
  mode: 'test' | 'full';
  created_at: string;
  updated_at?: string;
  record_count: number;
  accepted?: boolean;
  export?: ExportResult;
  export_config?: ExportConfig;
  runtime_dir?: string;
  run_payload?: RunRequest;
  managed_mode?: ManagedAiMode | string;
  managed_ai?: ManagedAiPayload | Record<string, unknown>;
  ai_decisions?: unknown[];
  ai_diagnostics?: unknown[] | Record<string, unknown> | null;
  ai_repair_suggestions?: unknown[];
  managed_actions?: ManagedActionRecord[];
  managed_steps?: ManagedStepRecord[];
  parent_task_id?: string;
  repair_source?: string;
  managed_auto_repair?: ManagedAutoRepairRecord | null;
  llm_traces?: LlmTraceRecord[];
  evidence_pack?: Record<string, unknown>;
  error?: string;
  // Closed-loop results
  managed_run_result?: ManagedRunResult;
  repair_result?: ManagedRepairResult;
}

// ── 一键采集 / 一键修复 ──

export type ManagedPipelineStage = 'idle' | 'analyzing' | 'planning' | 'executing_actions' | 'running' | 'diagnosing' | 'repairing' | 'completed' | 'failed';

export interface ManagedActionTimelineEntry {
  action: string;
  label: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped';
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  result_summary?: string;
  error?: string;
}

export interface ManagedRunResult {
  schema_version?: string;
  task_id: string;
  run_id: string;
  status: RunStatus | string;
  stage?: ManagedPipelineStage;
  record_count?: number;
  actions?: ManagedActionTimelineEntry[];
  quality_gate?: {
    severity: string;
    passed: boolean;
    reason?: string;
  };
  field_coverage?: number;
  quality_score?: number;
  error?: string;
  profile_patch?: Record<string, unknown>;
  run_overrides?: Record<string, unknown>;
}

export interface ManagedRepairResult {
  schema_version?: string;
  task_id: string;
  run_id: string;
  status: RunStatus | string;
  stage?: ManagedPipelineStage;
  record_count?: number;
  repair_cycles?: number;
  before_records?: number;
  after_records?: number;
  before_coverage?: number;
  after_coverage?: number;
  before_quality?: number;
  after_quality?: number;
  actions?: ManagedActionTimelineEntry[];
  quality_gate?: {
    severity: string;
    passed: boolean;
    reason?: string;
  };
  error?: string;
  converged?: boolean;
  final_health?: string;
}

export interface OneClickCrawlState {
  targetUrl: string;
  fieldGoal: string;
  stage: ManagedPipelineStage;
  result?: ManagedRunResult;
  repairResult?: ManagedRepairResult;
  error?: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface WizardState {
  targetUrl: string;
  fieldGoal: string;
  catalogText: string;
  importedCatalog?: unknown;
  catalogTree: CatalogNode[];
  selectedCatalogIds: string[];
  analysis?: SiteAnalysis;
  analysisStatus?: 'idle' | 'running' | 'completed' | 'failed';
  analysisLog?: string[];
  workflowStep?: number;
  lastRunPayload?: RunRequest;
  availableFields: FieldCandidate[];
  selectedFields: string[];
  naturalLanguageFields: string;
  missingFields: string[];
  runMode: 'test' | 'full';
  testLimit: number;
  export: ExportConfig;
  exportDirectoryStatus?: ExportPathStatus;
  browserDirectoryName?: string;
}
