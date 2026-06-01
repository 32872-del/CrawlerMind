import type { CatalogNode, RunRequest, SettingsState, WizardState } from '../types/workflow';
import { effectiveManagedAiMode, fileSafeHost, filterCatalogByIds, leafCatalog, managedAiModeLabel, replaceExportPathSuffix, runSafeTimestamp } from './format';

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function isCatalogNode(value: unknown): value is CatalogNode {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value) && 'label' in value);
}

function normalizeSeedUrlNodes(seedUrls: unknown, targetUrl: string): CatalogNode[] {
  if (!Array.isArray(seedUrls)) return [];
  return seedUrls
    .map((value, index) => String(value || '').trim())
    .filter(Boolean)
    .filter((url) => url !== targetUrl)
    .map((url, index) => ({
      id: `seed-${index + 1}`,
      label: `Seed ${index + 1}`,
      url,
      path: [`Seed ${index + 1}`],
      level1: `Seed ${index + 1}`,
      source: 'profile'
    }));
}

function collectProfileCatalogNodes(value: unknown): CatalogNode[] {
  if (!Array.isArray(value)) return [];
  const output: CatalogNode[] = [];
  const visit = (items: unknown[]) => {
    items.forEach((item) => {
      if (!isCatalogNode(item)) return;
      output.push(item);
      if (Array.isArray(item.children)) visit(item.children);
    });
  };
  visit(value);
  return output;
}

function mergeNodeMetadataFromAnalysis(node: CatalogNode, wizard: WizardState): CatalogNode {
  const discovered = collectProfileCatalogNodes(wizard.analysis?.discovered_catalog_tree);
  const byUrl = new Map(discovered.filter((item) => item.url).map((item) => [String(item.url), item]));
  const byPath = new Map(discovered.map((item) => [(item.path || []).join(' > ').toLowerCase(), item]));
  const match = byUrl.get(String(node.url || '')) || byPath.get((node.path || []).join(' > ').toLowerCase());
  if (!match) return node;
  return {
    ...node,
    graphql_category_uid: node.graphql_category_uid || match.graphql_category_uid,
    source: node.source || match.source
  };
}

function profileCatalogNodes(wizard: WizardState): CatalogNode[] {
  const profile = asRecord(wizard.analysis?.profile);
  const prefs = asRecord(profile.crawl_preferences);
  const catalogTree = prefs.catalog_tree;
  if (Array.isArray(catalogTree)) {
    return catalogTree.filter(isCatalogNode);
  }
  return normalizeSeedUrlNodes(prefs.seed_urls, wizard.targetUrl);
}

export function buildRunPayload(wizard: WizardState, settings: SettingsState): RunRequest {
  const host = fileSafeHost(wizard.targetUrl);
  const selectedTree = filterCatalogByIds(wizard.catalogTree, wizard.selectedCatalogIds || []);
  const visibleCatalogLeaves = leafCatalog(selectedTree).map((node) => mergeNodeMetadataFromAnalysis(node, wizard));
  const fallbackCatalogNodes = leafCatalog(profileCatalogNodes(wizard)).map((node) => mergeNodeMetadataFromAnalysis(node, wizard));
  const catalogNodes = (visibleCatalogLeaves.length ? visibleCatalogLeaves : fallbackCatalogNodes)
    .filter((node, index, items) => items.findIndex((other) => other.url === node.url) === index);
  const existingPreferences = asRecord(asRecord(wizard.analysis?.profile).crawl_preferences);
  const seedUrls = catalogNodes.length
    ? catalogNodes.map((node) => node.url).filter((url): url is string => Boolean(url))
    : ((existingPreferences.seed_urls as string[] | undefined) || [wizard.targetUrl]);
  const profile = {
    ...(wizard.analysis?.profile || {}),
    crawl_preferences: {
      ...existingPreferences,
      seed_urls: seedUrls,
      seed_kind: existingPreferences.seed_kind || (catalogNodes.length ? 'catalog' : 'entry')
    }
  };
  const exportConfig = {
    ...wizard.export,
    output_path: replaceExportPathSuffix(
      wizard.export.output_path || `dev_logs/exports/${host}.${wizard.export.format}`,
      wizard.export.format
    )
  };
  const llmEnabled = Boolean(settings.llm.base_url && settings.llm.model);
  const managedMode = effectiveManagedAiMode(settings.managed_ai.enabled, settings.managed_ai.mode);
  const payload: RunRequest = {
    target_url: wizard.targetUrl,
    profile,
    catalog_nodes: catalogNodes,
    selected_fields: wizard.selectedFields,
    export: exportConfig,
    run_mode: 'direct',
    item_workers: settings.runtime.item_workers,
    max_sites: 1,
    test_limit: wizard.testLimit,
    runtime_dir: `${(settings.runtime.default_runtime_dir || 'dev_logs/runtime').replace(/[\\/]+$/, '')}/${host}-${runSafeTimestamp()}`,
    managed_ai: {
      ...settings.managed_ai,
      enabled: settings.managed_ai.enabled,
      mode: settings.managed_ai.mode,
      model: settings.llm.model || undefined
    },
    llm: {
      enabled: llmEnabled || settings.managed_ai.enabled,
      provider: settings.llm.provider,
      base_url: settings.llm.base_url,
      model: settings.llm.model,
      reasoning_effort: settings.llm.reasoning_effort,
      stream: settings.llm.stream,
      timeout_seconds: settings.llm.timeout_seconds,
      max_tokens: settings.llm.max_tokens,
      ...(settings.llm.api_key ? { api_key: settings.llm.api_key } : {})
    }
  };
  if (!settings.managed_ai.enabled) {
    payload.managed_ai = {
      ...payload.managed_ai,
      enabled: false,
      mode: 'analysis_only',
      analysis_enabled: false,
      plan_review_enabled: false,
      runtime_diagnosis_enabled: false,
      post_run_diagnosis_enabled: false
    };
  }
  payload.profile = {
    ...payload.profile,
    managed_mode: managedMode
  };
  return payload;
}

export function runPayloadSummary(payload: RunRequest): Array<{ key: string; value: string }> {
  const prefs = (payload.profile.crawl_preferences || {}) as Record<string, unknown>;
  const seedUrls = Array.isArray(prefs.seed_urls) ? prefs.seed_urls : [];
  return [
    { key: '目标网站', value: payload.target_url },
    { key: '目录 URL 数', value: String(payload.catalog_nodes.length) },
    { key: '实际 seed_urls 数', value: String(seedUrls.length) },
    { key: '采集字段', value: payload.selected_fields.join(', ') || '-' },
    { key: '并发 worker', value: String(payload.item_workers) },
    { key: '试跑上限', value: String(payload.test_limit) },
    { key: '运行目录', value: payload.runtime_dir },
    { key: '导出路径', value: payload.export.output_path || '-' },
    { key: 'AI 托管', value: managedAiModeLabel(payload.managed_ai?.enabled ? payload.managed_ai.mode : 'deterministic') },
    { key: '模型', value: payload.llm?.model || '-' }
  ];
}

export function seedUrlRows(payload: RunRequest): Array<{ index: number; url: string }> {
  const prefs = (payload.profile.crawl_preferences || {}) as Record<string, unknown>;
  const seedUrls = Array.isArray(prefs.seed_urls) ? prefs.seed_urls : [];
  return seedUrls.map((url, index) => ({ index: index + 1, url: String(url) }));
}
