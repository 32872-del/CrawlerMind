import { Empty, Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { Key } from 'react';
import type { CatalogNode } from '../types/workflow';

function toTreeData(nodes: CatalogNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.id,
    title: node.url ? `${node.label}  ->  ${node.url}` : node.label,
    children: toTreeData(node.children || [])
  }));
}

interface Props {
  nodes: CatalogNode[];
  checkable?: boolean;
  selectedIds?: string[];
  onSelectionChange?: (ids: string[]) => void;
}

export function CatalogTreeView({ nodes, checkable = false, selectedIds = [], onSelectionChange }: Props) {
  if (!nodes.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未导入或发现目录" />;
  return (
    <Tree
      treeData={toTreeData(nodes)}
      defaultExpandAll
      blockNode
      checkable={checkable}
      checkedKeys={selectedIds}
      onCheck={(keys: Key[] | { checked: Key[]; halfChecked: Key[] }) => {
        const checked = Array.isArray(keys) ? keys : keys.checked;
        onSelectionChange?.(checked.map(String));
      }}
    />
  );
}
