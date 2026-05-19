import { Checkbox, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { FieldCandidate } from '../types/workflow';
import { fieldLabel, sourceLabel } from '../utils/format';

interface Props {
  fields: FieldCandidate[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function FieldSelector({ fields, selected, onChange }: Props) {
  const columns: ColumnsType<FieldCandidate> = [
    {
      title: '',
      width: 44,
      render: (_, field) => (
        <Checkbox
          checked={selected.includes(field.name)}
          onChange={(event) => {
            const next = event.target.checked
              ? Array.from(new Set([...selected, field.name]))
              : selected.filter((name) => name !== field.name);
            onChange(next);
          }}
        />
      )
    },
    { title: '字段', dataIndex: 'name', width: 160, render: (value) => fieldLabel(value) },
    { title: '原始字段名', dataIndex: 'name', width: 160 },
    {
      title: '来源',
      dataIndex: 'source',
      width: 120,
      render: (value) => <Tag>{sourceLabel(value)}</Tag>
    },
    { title: '选择器 / API 路径', render: (_, field) => field.selector || field.api_path || '-' },
    {
      title: '置信度',
      dataIndex: 'confidence',
      width: 110,
      render: (value) => (typeof value === 'number' ? Math.round(value * 100) + '%' : '-')
    }
  ];

  return (
    <Table
      size="small"
      rowKey="name"
      pagination={false}
      dataSource={fields}
      columns={columns}
      scroll={{ x: 760 }}
    />
  );
}
