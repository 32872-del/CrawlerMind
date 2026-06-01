import type { CatalogNode, ExportFormat, ManagedAiMode, RunStatus } from '../types/workflow';

export function statusColor(status: string | undefined): 'default' | 'processing' | 'success' | 'error' | 'warning' {
  const value = String(status || '').toLowerCase();
  if (value === 'running' || value === 'queued') return 'processing';
  if (value === 'completed' || value === 'done') return 'success';
  if (value === 'failed' || value === 'error') return 'error';
  if (value === 'paused' || value === 'cancelled') return 'warning';
  return 'default';
}

export function statusLabel(status: string | undefined): RunStatus | string {
  const value = String(status || 'unknown').toLowerCase();
  const labels: Record<string, string> = {
    idle: '未开始',
    queued: '排队中',
    running: '运行中',
    paused: '已暂停',
    cancelled: '已终止',
    completed: '已完成',
    done: '已完成',
    failed: '失败',
    error: '失败',
    unknown: '未知',
    starting: '启动中',
    crawling: '采集中',
    finishing: '收尾中',
    stopped: '已停止',
    finished: '已结束'
  };
  return labels[value] || value;
}

export function apiModeLabel(mode: string): string {
  const labels: Record<string, string> = {
    auto: '自动',
    live: '真实后端',
    mock: '演示数据'
  };
  return labels[mode] || mode;
}

export function runModeLabel(mode: string): string {
  return mode === 'full' ? '全量运行' : '试跑';
}

export function managedAiModeLabel(mode: string | undefined): string {
  const labels: Record<string, string> = {
    deterministic: '关闭',
    disabled: '关闭',
    analysis_only: '观察',
    supervised: '自动修复',
    full_managed: '全托管'
  };
  return labels[String(mode || 'disabled')] || String(mode || '关闭');
}

export function effectiveManagedAiMode(enabled: boolean, mode: ManagedAiMode): ManagedAiMode | 'deterministic' {
  return enabled ? mode : 'deterministic';
}

export function fieldLabel(name: string | undefined): string {
  const labels: Record<string, string> = {
    title: '商品标题',
    highest_price: '最高价格',
    price: '价格',
    colors: '颜色',
    sizes: '尺码',
    description: '商品描述',
    image_urls: '商品图 URL',
    category: '目录'
  };
  return labels[String(name || '')] || String(name || '-');
}

export function sourceLabel(source: string | undefined): string {
  const labels: Record<string, string> = {
    dom: '页面',
    api: '接口',
    default: '默认',
    mock: '演示',
    profile: 'Profile',
    llm: 'LLM'
  };
  return labels[String(source || 'default')] || String(source || '默认');
}

export function qualitySeverityLabel(value: unknown): string {
  const severity = String(value || '-').toLowerCase();
  const labels: Record<string, string> = {
    pass: '通过',
    warn: '警告',
    fail: '失败',
    '-': '-'
  };
  return labels[severity] || severity;
}

export function flattenCatalog(nodes: CatalogNode[]): CatalogNode[] {
  const output: CatalogNode[] = [];
  const visit = (items: CatalogNode[]) => {
    items.forEach((item) => {
      output.push(item);
      if (item.children?.length) visit(item.children);
    });
  };
  visit(nodes || []);
  return output;
}

export function filterCatalogByIds(nodes: CatalogNode[], selectedIds: string[]): CatalogNode[] {
  const wanted = new Set(selectedIds || []);
  if (!wanted.size) return nodes;
  const visit = (items: CatalogNode[]): CatalogNode[] => {
    const output: CatalogNode[] = [];
    items.forEach((item) => {
      const children = visit(item.children || []);
      if (wanted.has(item.id) || children.length) {
        output.push({ ...item, children });
      }
    });
    return output;
  };
  return visit(nodes || []);
}

export function leafCatalog(nodes: CatalogNode[]): CatalogNode[] {
  return flattenCatalog(nodes).filter((item) => Boolean(item.url));
}

export function replaceExportPathSuffix(path: string, format: ExportFormat): string {
  const suffix = format === 'sqlite' || format === 'db' ? 'sqlite3' : format;
  const value = String(path || '').trim();
  if (!value) return value;
  const base = value.replace(/\.(csv|xlsx|json|sqlite3?|db)$/i, '');
  return `${base}.${suffix}`;
}

export function percent(value: number | undefined): string {
  const number = Number(value || 0);
  return `${Math.round(number * 100)}%`;
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function runSafeTimestamp(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds())
  ].join('');
}

export function tryParseJson(text: string): unknown {
  const value = text.trim();
  if (!value) return undefined;
  return JSON.parse(value);
}

export function fileSafeHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/[^a-zA-Z0-9_-]+/g, '-');
  } catch {
    return 'clm-run';
  }
}

export function joinExportPath(directory: string, filename: string): string {
  const base = directory.trim().replace(/[\\/]+$/, '');
  if (!base) return filename;
  const separator = base.includes('\\') && !base.includes('/') ? '\\' : '/';
  return `${base}${separator}${filename}`;
}

export function exportFilename(targetUrl: string, format: ExportFormat): string {
  return `${fileSafeHost(targetUrl)}.${format}`;
}

export function formatTime(value: string | undefined): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

export function userFacingError(error: unknown): string {
  if (!(error instanceof Error)) return '操作失败，请查看后端日志。';
  const message = error.message || '';
  if (message.includes('Failed to fetch') || message.includes('NetworkError') || message.includes('fetch')) {
    return '无法连接后端服务，请确认 CLM API 已启动，或切换为演示数据模式。';
  }
  if (message.includes('LLM') || message.includes('llm') || message.includes('model') || message.includes('api_key')) {
    return `LLM 配置可能无效：${message}`;
  }
  if (message.includes('path') || message.includes('directory') || message.includes('export')) {
    return `导出路径可能无效：${message}`;
  }
  return message;
}
