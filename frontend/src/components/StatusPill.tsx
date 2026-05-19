import { Tag } from 'antd';
import { statusColor, statusLabel } from '../utils/format';

export function StatusPill({ status }: { status?: string }) {
  return <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>;
}
