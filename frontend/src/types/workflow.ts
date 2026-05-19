export type ApiMode = 'auto' | 'live' | 'mock';
export type WorkbenchPage = 'dashboard' | 'wizard' | 'analysis' | 'detail' | 'history' | 'settings';
export type RunStatus = 'idle' | 'queued' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed' | 'unknown';
export type ExportFormat = 'json' | 'csv' | 'xlsx' | 'sqlite' | 'db';
export type UiMode = 'compact' | 'standard';
export type ManagedAiMode = 'analysis_only' | 'supervised' | 'full_managed';

export interface LlmConfig {
  provider: string;
  base_url: string;
  api_key: string;
  model: string;
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
  ai_diagnostics?: unknown[];
  ai_repair_suggestions?: unknown[];
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
  ai_diagnostics?: unknown[];
  ai_repair_suggestions?: unknown[];
  error?: string;
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
