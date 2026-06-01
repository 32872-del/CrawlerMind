import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type {
  CatalogNode,
  ExportConfig,
  RunEventsResponse,
  RunStatusResponse,
  SettingsState,
  WizardState,
  WorkbenchPage,
  WorkbenchTask
} from '../types/workflow';
import { fileSafeHost, nowIso } from '../utils/format';

interface WorkbenchContextValue {
  page: WorkbenchPage;
  setPage: (page: WorkbenchPage) => void;
  settings: SettingsState;
  setSettings: React.Dispatch<React.SetStateAction<SettingsState>>;
  wizard: WizardState;
  setWizard: React.Dispatch<React.SetStateAction<WizardState>>;
  tasks: WorkbenchTask[];
  activeTaskId: string;
  setActiveTaskId: (taskId: string) => void;
  statuses: Record<string, RunStatusResponse>;
  events: Record<string, RunEventsResponse>;
  upsertTask: (task: WorkbenchTask) => void;
  removeTask: (taskId: string) => void;
  prepareNewTarget: (targetUrl: string, options?: { reset?: boolean }) => void;
  updateTaskStatus: (status: RunStatusResponse) => void;
  updateTaskEvents: (taskId: string, response: RunEventsResponse) => void;
  resetWizardExport: (targetUrl: string, format?: ExportConfig['format']) => void;
}

const defaultExport: ExportConfig = {
  format: 'csv',
  output_path: 'dev_logs/exports/clm-run.csv',
  field_mapping: {
    title: '商品标题',
    highest_price: '最高价格',
    colors: '颜色',
    sizes: '尺码',
    description: '商品描述',
    image_urls: '商品图 URL'
  }
};

const defaultSettings: SettingsState = {
  apiBaseUrl: 'http://127.0.0.1:8000',
  apiMode: 'auto',
  llm: {
    provider: 'openai-compatible',
    base_url: '',
    api_key: '',
    model: '',
    reasoning_effort: 'medium',
    stream: false,
    timeout_seconds: 60,
    max_tokens: 1200
  },
  managed_ai: {
    enabled: false,
    mode: 'analysis_only',
    analysis_enabled: true,
    plan_review_enabled: false,
    runtime_diagnosis_enabled: false,
    post_run_diagnosis_enabled: false
  },
  runtime: {
    item_workers: 8,
    timeout_seconds: 30,
    max_retries: 3,
    browser_enabled: false,
    proxy_url: '',
    default_runtime_dir: 'dev_logs/runtime/frontend-run',
    default_export_dir: 'dev_logs/exports'
  },
  uiMode: 'standard'
};

const defaultWizard: WizardState = {
  targetUrl: 'https://dummyjson.com/products',
  fieldGoal: '采集商品标题、价格、颜色、尺码、描述和图片',
  catalogText: JSON.stringify(
    {
      Products: {
        Beauty: 'https://dummyjson.com/products/category/beauty',
        Groceries: 'https://dummyjson.com/products/category/groceries'
      }
    },
    null,
    2
  ),
  catalogTree: [],
  selectedCatalogIds: [],
  analysisStatus: 'idle',
  analysisLog: [],
  workflowStep: 0,
  availableFields: [],
  selectedFields: ['title', 'highest_price', 'description', 'image_urls'],
  naturalLanguageFields: '我要标题、价格、描述、图片',
  missingFields: [],
  runMode: 'test',
  testLimit: 100,
  export: defaultExport
};

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);
const STORAGE_KEY = 'clm-workbench-state-v3';

interface StoredWorkbenchState {
  settings?: Partial<SettingsState>;
  wizard?: Partial<WizardState>;
  tasks?: WorkbenchTask[];
  activeTaskId?: string;
  page?: WorkbenchPage;
}

function mergeSettings(stored?: Partial<SettingsState>): SettingsState {
  return {
    ...defaultSettings,
    ...(stored || {}),
    llm: {
      ...defaultSettings.llm,
      ...(stored?.llm || {})
    },
    managed_ai: {
      ...defaultSettings.managed_ai,
      ...(stored?.managed_ai || {})
    },
    runtime: {
      ...defaultSettings.runtime,
      ...(stored?.runtime || {})
    }
  };
}

function mergeWizard(stored?: Partial<WizardState>): WizardState {
  return {
    ...defaultWizard,
    ...(stored || {}),
    export: {
      ...defaultWizard.export,
      ...(stored?.export || {}),
      field_mapping: {
        ...defaultWizard.export.field_mapping,
        ...(stored?.export?.field_mapping || {})
      }
    }
  };
}

function loadStoredState(): StoredWorkbenchState {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY) || window.localStorage.getItem('clm-workbench-state-v2');
    if (!raw) return {};
    return JSON.parse(raw) as StoredWorkbenchState;
  } catch {
    return {};
  }
}

export function WorkbenchProvider({ children }: { children: React.ReactNode }) {
  const stored = useMemo(loadStoredState, []);
  const [page, setPage] = useState<WorkbenchPage>(stored.page || 'dashboard');
  const [settings, setSettings] = useState<SettingsState>(() => mergeSettings(stored.settings));
  const [wizard, setWizard] = useState<WizardState>(() => mergeWizard(stored.wizard));
  const [tasks, setTasks] = useState<WorkbenchTask[]>(stored.tasks || []);
  const [activeTaskId, setActiveTaskId] = useState(stored.activeTaskId || '');
  const [statuses, setStatuses] = useState<Record<string, RunStatusResponse>>({});
  const [events, setEvents] = useState<Record<string, RunEventsResponse>>({});

  useEffect(() => {
    const payload: StoredWorkbenchState = {
      page,
      settings,
      wizard: {
        targetUrl: wizard.targetUrl,
        fieldGoal: wizard.fieldGoal,
        catalogText: wizard.catalogText,
        catalogTree: wizard.catalogTree,
        selectedCatalogIds: wizard.selectedCatalogIds,
        importedCatalog: wizard.importedCatalog,
        analysis: wizard.analysis,
        analysisStatus: wizard.analysisStatus,
        analysisLog: wizard.analysisLog,
        workflowStep: wizard.workflowStep,
        lastRunPayload: wizard.lastRunPayload,
        availableFields: wizard.availableFields,
        selectedFields: wizard.selectedFields,
        missingFields: wizard.missingFields,
        naturalLanguageFields: wizard.naturalLanguageFields,
        runMode: wizard.runMode,
        testLimit: wizard.testLimit,
        export: wizard.export,
        browserDirectoryName: wizard.browserDirectoryName,
        exportDirectoryStatus: wizard.exportDirectoryStatus
      },
      tasks,
      activeTaskId
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [activeTaskId, page, settings, tasks, wizard]);

  const value = useMemo<WorkbenchContextValue>(() => {
    const upsertTask = (task: WorkbenchTask) => {
      setTasks((current) => {
        const existing = current.find((item) => item.task_id === task.task_id);
        const merged = existing ? { ...existing, ...task } : task;
        const rest = current.filter((item) => item.task_id !== task.task_id);
        return [merged, ...rest].slice(0, 50);
      });
      setActiveTaskId(task.task_id);
    };

    const updateTaskStatus = (status: RunStatusResponse) => {
      setStatuses((current) => ({ ...current, [status.task_id]: status }));
      setTasks((current) =>
        current.map((task) =>
          task.task_id === status.task_id
            ? {
                ...task,
                status: status.status,
                run_id: status.run_id || task.run_id,
                record_count: status.record_count,
                accepted: status.accepted,
                export: status.export || task.export,
                managed_mode: status.managed_mode || task.managed_mode,
                managed_ai: status.managed_ai || task.managed_ai,
                ai_decisions: status.ai_decisions || task.ai_decisions,
                ai_diagnostics: status.ai_diagnostics || task.ai_diagnostics,
                ai_repair_suggestions: status.ai_repair_suggestions || task.ai_repair_suggestions,
                managed_actions: status.managed_actions || task.managed_actions,
                managed_steps: status.managed_steps || task.managed_steps,
                managed_auto_repair: status.managed_auto_repair || task.managed_auto_repair,
                llm_traces: status.llm_traces || task.llm_traces,
                evidence_pack: status.evidence_pack || task.evidence_pack,
                parent_task_id: status.parent_task_id || task.parent_task_id,
                repair_source: status.repair_source || task.repair_source,
                error: status.error || '',
                updated_at: nowIso()
              }
            : task
        )
      );
    };

    const removeTask = (taskId: string) => {
      setTasks((current) => current.filter((task) => task.task_id !== taskId));
      setStatuses((current) => {
        const next = { ...current };
        delete next[taskId];
        return next;
      });
      setEvents((current) => {
        const next = { ...current };
        delete next[taskId];
        return next;
      });
      setActiveTaskId((current) => (current === taskId ? '' : current));
    };

    const prepareNewTarget = (targetUrl: string, options?: { reset?: boolean }) => {
      const nextUrl = targetUrl.trim();
      const reset = options?.reset === true;
      const host = fileSafeHost(nextUrl);
      setWizard((current) => ({
        ...current,
        targetUrl: nextUrl,
        ...(reset
          ? {
              importedCatalog: undefined,
              catalogTree: [],
              selectedCatalogIds: [],
              analysis: undefined,
              analysisStatus: 'idle' as const,
              analysisLog: nextUrl ? [`已设置目标网站：${nextUrl}`] : [],
              workflowStep: 0,
              lastRunPayload: undefined,
              availableFields: [],
              selectedFields: ['title', 'highest_price', 'description', 'image_urls'],
              missingFields: []
            }
          : {}),
        export: {
          ...current.export,
          output_path: nextUrl ? `${settings.runtime.default_export_dir}/${host}.${current.export.format}` : current.export.output_path
        }
      }));
    };

    const updateTaskEvents = (taskId: string, response: RunEventsResponse) => {
      setEvents((current) => ({ ...current, [taskId]: response }));
    };

    const resetWizardExport = (targetUrl: string, format?: ExportConfig['format']) => {
      const host = fileSafeHost(targetUrl);
      setWizard((current) => ({
        ...current,
        export: {
          ...current.export,
          format: format || current.export.format,
          output_path: `${settings.runtime.default_export_dir}/${host}.${format || current.export.format}`
        }
      }));
    };

    return {
      page,
      setPage,
      settings,
      setSettings,
      wizard,
      setWizard,
      tasks,
      activeTaskId,
      setActiveTaskId,
      statuses,
      events,
      upsertTask,
      removeTask,
      prepareNewTarget,
      updateTaskStatus,
      updateTaskEvents,
      resetWizardExport
    };
  }, [activeTaskId, events, page, settings, statuses, tasks, wizard]);

  return <WorkbenchContext.Provider value={value}>{children}</WorkbenchContext.Provider>;
}

export function useWorkbench() {
  const context = useContext(WorkbenchContext);
  if (!context) throw new Error('useWorkbench must be used inside WorkbenchProvider');
  return context;
}

export function catalogCount(nodes: CatalogNode[]): number {
  return nodes.reduce((total, node) => total + 1 + catalogCount(node.children || []), 0);
}
