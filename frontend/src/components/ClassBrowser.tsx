import { useState } from 'react';
import type { DrugClassNode } from '../types/api';

interface Props {
  classes: DrugClassNode[];
  selectedId: string | null;
  onSelect: (id: string, name: string) => void;
}

function ClassNode({
  node,
  selectedId,
  onSelect,
  depth,
}: {
  node: DrugClassNode;
  selectedId: string | null;
  onSelect: (id: string, name: string) => void;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(depth === 0);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <button
        onClick={() => {
          if (hasChildren) setExpanded((e) => !e);
          onSelect(node.id, node.name);
        }}
        className={`w-full text-left flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors
          ${selectedId === node.id ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700 hover:text-white'}`}
        style={{ paddingLeft: `${0.75 + depth * 1.25}rem` }}
      >
        {hasChildren && (
          <span className="text-xs w-3 shrink-0">{expanded ? '▾' : '▸'}</span>
        )}
        {!hasChildren && <span className="w-3 shrink-0" />}
        {node.name}
      </button>

      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <ClassNode
              key={child.id}
              node={child}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function ClassBrowser({ classes, selectedId, onSelect }: Props) {
  return (
    <div className="space-y-0.5">
      {classes.map((node) => (
        <ClassNode
          key={node.id}
          node={node}
          selectedId={selectedId}
          onSelect={onSelect}
          depth={0}
        />
      ))}
    </div>
  );
}
