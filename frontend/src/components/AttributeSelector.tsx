import type { AttributeType } from '../types/api';

const SHAPE_BADGE: Record<string, string> = {
  scalar:     'bg-purple-900 text-purple-300',
  list:       'bg-teal-900 text-teal-300',
  relational: 'bg-orange-900 text-orange-300',
};

interface Props {
  attributeTypes: AttributeType[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
}

export function AttributeSelector({ attributeTypes, selectedIds, onToggle }: Props) {
  return (
    <div className="space-y-2">
      {attributeTypes.map((at) => (
        <label
          key={at.id}
          className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors
            ${selectedIds.has(at.id)
              ? 'border-blue-500 bg-blue-950/40'
              : 'border-gray-700 hover:border-gray-500'}`}
        >
          <input
            type="checkbox"
            checked={selectedIds.has(at.id)}
            onChange={() => onToggle(at.id)}
            className="accent-blue-500"
          />
          <span className="text-sm text-white flex-1">{at.label}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${SHAPE_BADGE[at.shape] ?? ''}`}>
            {at.shape}
          </span>
        </label>
      ))}
    </div>
  );
}
