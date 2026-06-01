import { Empty, Timeline } from 'antd';
import type { RunEvent } from '../types/workflow';
import { formatTime } from '../utils/format';

const eventTypeLabels: Record<string, string> = {
  job_created: '任务已创建',
  export_ready: '导出完成',
  export_failed: '导出失败',
  failure: '采集失败',
  managed_actions_planned: 'AI 已规划动作',
  managed_actions_executed: 'AI 已执行动作',
  managed_step_executed: 'AI 托管步骤已执行',
  managed_control_loop_completed: 'AI 托管闭环已完成',
  access_probe_completed: '访问探测已完成',
  extract_from_contract: '合同抽取已执行',
  managed_auto_repair_started: '全托管修复已启动',
  managed_auto_repair_skipped: '全托管修复未触发'
};

function eventLabel(type: string): string {
  if (type.startsWith('llm_trace_')) return `模型调用：${type.replace('llm_trace_', '')}`;
  if (type.startsWith('ai_')) return `AI 决策：${type.replace('ai_', '')}`;
  if (type.startsWith('supervision_')) return `运行监督：${type.replace('supervision_', '')}`;
  if (type.startsWith('job_')) return `任务状态：${type.replace('job_', '')}`;
  return eventTypeLabels[type] || type;
}

export function EventTimeline({ events }: { events: RunEvent[] }) {
  if (!events.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行事件" />;
  return (
    <Timeline
      items={events.map((event) => ({
        children: (
          <div>
            <div className="event-title">{eventLabel(event.type)}</div>
            <div className="muted">{event.message}</div>
            {event.time ? <div className="event-time">{formatTime(event.time)}</div> : null}
          </div>
        )
      }))}
    />
  );
}
