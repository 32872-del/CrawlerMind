import type {
  CatalogNode,
  ExportConfig,
  ExportPathStatus,
  ExportResult,
  FieldCandidate,
  FieldResolution,
  LlmModelListResponse,
  RunEventsResponse,
  RunLaunchResponse,
  RunRequest,
  RunStatusResponse,
  SettingsState,
  SiteAnalysis
} from '../types/workflow';
import { exportFilename, fileSafeHost, joinExportPath, nowIso } from '../utils/format';
import { mockCatalogTree, mockExport, mockFieldResolution, mockLlmModels, mockRunEvents, mockRunLaunch, mockRunStatus, mockSiteAnalysis } from './mockData';

async function requestJson<T>(settings: SettingsState, path: string, init?: RequestInit, mock?: () => T): Promise<T> {
  if (settings.apiMode === 'mock') return mock ? mock() : Promise.reject(new Error('mock response missing'));
  const base = settings.apiBaseUrl.replace(/\/$/, '');
  const url = `${base}${path}`;
  try {
    const response = await fetch(url, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers || {})
      }
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    // Real crawling actions must never silently fall back to mock data. A hidden
    // fallback makes the workbench look successful while no backend job ran.
    throw error;
  }
}

export async function importCatalog(settings: SettingsState, catalog: unknown): Promise<{ catalog_tree: CatalogNode[]; node_count: number; leaf_count: number }> {
  return requestJson(
    settings,
    '/catalog/import',
    { method: 'POST', body: JSON.stringify({ catalog }) },
    () => ({ catalog_tree: mockCatalogTree, node_count: 3, leaf_count: 2 })
  );
}

export async function analyzeSite(settings: SettingsState, targetUrl: string, fieldGoal: string, importedCatalog?: unknown): Promise<SiteAnalysis> {
  const llmEnabled = Boolean(settings.llm.base_url && settings.llm.model);
  return requestJson(
    settings,
    '/site/analyze',
    {
      method: 'POST',
      body: JSON.stringify({
        target_url: targetUrl,
        field_goal: fieldGoal,
        imported_catalog: importedCatalog,
        llm: {
          enabled: llmEnabled,
          provider: settings.llm.provider,
          base_url: settings.llm.base_url,
          api_key: settings.llm.api_key,
          model: settings.llm.model
        }
      })
    },
    () => mockSiteAnalysis(targetUrl)
  );
}

export async function resolveFields(settings: SettingsState, availableFields: FieldCandidate[], naturalLanguage: string, requestedFields: string[]): Promise<FieldResolution> {
  return requestJson(
    settings,
    '/fields/resolve',
    { method: 'POST', body: JSON.stringify({ available_fields: availableFields, natural_language: naturalLanguage, requested_fields: requestedFields }) },
    () => mockFieldResolution(requestedFields)
  );
}

export async function launchRun(settings: SettingsState, mode: 'test' | 'full', payload: RunRequest): Promise<RunLaunchResponse> {
  return requestJson(
    settings,
    `/runs/${mode}`,
    { method: 'POST', body: JSON.stringify(payload) },
    () => mockRunLaunch(mode)
  );
}

export async function fetchRunStatus(settings: SettingsState, taskId: string, runId: string): Promise<RunStatusResponse> {
  return requestJson(
    settings,
    `/runs/${taskId}/status`,
    { method: 'GET' },
    () => mockRunStatus(taskId, runId)
  );
}

export async function fetchRunEvents(settings: SettingsState, taskId: string): Promise<RunEventsResponse> {
  return requestJson(settings, `/runs/${taskId}/events`, { method: 'GET' }, () => mockRunEvents(taskId));
}

export async function cancelRun(settings: SettingsState, taskId: string): Promise<{ task_id: string; status: string }> {
  return requestJson(
    settings,
    `/jobs/${taskId}/cancel`,
    { method: 'POST' },
    () => ({ task_id: taskId, status: 'cancelled' })
  );
}

export async function deleteRun(settings: SettingsState, taskId: string): Promise<{ task_id: string; deleted: boolean }> {
  return requestJson(
    settings,
    `/jobs/${taskId}`,
    { method: 'DELETE' },
    () => ({ task_id: taskId, deleted: true })
  );
}

export async function exportRun(settings: SettingsState, runId: string, runtimeDir: string, exportConfig: ExportConfig): Promise<ExportResult> {
  return requestJson(
    settings,
    '/exports',
    {
      method: 'POST',
      body: JSON.stringify({
        run_id: runId,
        runtime_dir: runtimeDir,
        format: exportConfig.format,
        output_path: exportConfig.output_path,
        template_path: exportConfig.template_path || '',
        field_mapping: exportConfig.field_mapping
      })
    },
    () => mockExport(runId, exportConfig.format, exportConfig.output_path)
  );
}

export async function fetchLlmModels(settings: SettingsState): Promise<LlmModelListResponse> {
  return requestJson(
    settings,
    '/llm/models',
    {
      method: 'POST',
      body: JSON.stringify({
        provider: settings.llm.provider,
        base_url: settings.llm.base_url,
        api_key: settings.llm.api_key
      })
    },
    settings.apiMode === 'mock' ? () => mockLlmModels(settings.llm.provider) : undefined
  );
}

export async function validateExportDirectory(settings: SettingsState, directory: string, create = false): Promise<ExportPathStatus> {
  return requestJson(
    settings,
    '/exports/validate-path',
    {
      method: 'POST',
      body: JSON.stringify({ directory, create })
    },
    settings.apiMode === 'mock'
      ? () => ({
          checked_at: nowIso(),
          exists: true,
          created: create,
          writable: true,
          normalized_path: directory,
          source: 'local'
        })
      : undefined
  );
}

export async function resolveExportPath(settings: SettingsState, directory: string, targetUrl: string, format: ExportConfig['format']): Promise<ExportPathStatus> {
  const filename = exportFilename(targetUrl, format);
  const runId = fileSafeHost(targetUrl) || 'frontend-run';
  return requestJson(
    settings,
    '/exports/resolve-path',
    {
      method: 'POST',
      body: JSON.stringify({ directory, run_id: runId, filename, format })
    },
    settings.apiMode === 'mock'
      ? () => ({
          checked_at: nowIso(),
          exists: true,
          created: false,
          writable: true,
          normalized_path: directory,
          final_output_path: joinExportPath(directory, filename),
          source: 'local'
        })
      : undefined
  );
}
