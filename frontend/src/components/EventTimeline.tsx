import { Empty, Timeline } from 'antd';
import type { RunEvent } from '../types/workflow';
import { formatTime } from '../utils/format';

export function EventTimeline({ events }: { events: RunEvent[] }) {
  if (!events.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行事件" />;
  return (
    <Timeline
      items={events.map((event) => ({
        children: (
          <div>
            <div className="event-title">{event.type}</div>
            <div className="muted">{event.message}</div>
            {event.time ? <div className="event-time">{formatTime(event.time)}</div> : null}
          </div>
        )
      }))}
    />
  );
}
