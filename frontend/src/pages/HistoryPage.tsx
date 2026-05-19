import { Button, Card, Input, Select, Space, Table, Tag } from 'antd';
import { useMemo, useState, type ChangeEvent } from 'react';
import type { ColumnsType } from 'antd/es/table';
import { StatusPill } from '../components/StatusPill';
import { useWorkbench } from '../store/workbench';
import type { WorkbenchTask } from '../types/workflow';
import { formatTime, runModeLabel } from '../utils/format';

export function HistoryPage() {
  const { tasks, setActiveTaskId, setPage } = useWorkbench();
  const [status, setStatus] = useState('all');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    return tasks.filter((task) => {
      const statusOk = status === 'all' || String(task.status).toLowerCase() === status;
      const queryOk = !query || `${task.task_id} ${task.target_url} ${task.run_id}`.toLowerCase().includes(query.toLowerCase());
      return statusOk && queryOk;
    });
  }, [query, status, tasks]);

  const columns: ColumnsType<WorkbenchTask> = [
    { title: '任务', dataIndex: 'task_id', width: 130 },
    { title: '运行 ID', dataIndex: 'run_id', width: 190 },
    { title: '目标站点', dataIndex: 'target_url', ellipsis: true },
    { title: '模式', dataIndex: 'mode', width: 100, render: (value) => <Tag>{runModeLabel(value)}</Tag> },
    { title: '状态', dataIndex: 'status', width: 120, render: (value) => <StatusPill status={value} /> },
    { title: '记录数', dataIndex: 'record_count', width: 100 },
    { title: '创建时间', dataIndex: 'created_at', width: 170, render: formatTime },
    {
      title: '',
      width: 130,
      render: (_, task) => (
        <Button
          size="small"
          onClick={() => {
            setActiveTaskId(task.task_id);
            setPage('detail');
          }}
        >
          查看详情
        </Button>
      )
    }
  ];

  return (
    <Card
      title="历史任务"
      extra={
        <Space>
          <Input.Search placeholder="搜索任务、运行 ID、网址" value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} />
          <Select
            value={status}
            onChange={setStatus}
            options={[
              { value: 'all', label: '全部' },
              { value: 'running', label: '运行中' },
              { value: 'completed', label: '已完成' },
              { value: 'failed', label: '失败' },
              { value: 'paused', label: '已暂停' },
              { value: 'cancelled', label: '已终止' }
            ]}
          />
        </Space>
      }
    >
      <Table size="small" rowKey="task_id" columns={columns} dataSource={filtered} />
    </Card>
  );
}
