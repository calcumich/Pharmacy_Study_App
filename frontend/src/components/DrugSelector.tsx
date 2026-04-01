import type { DrugSummary } from '../types/api';

interface Props {
  drugs: DrugSummary[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
}

export function DrugSelector({ drugs, selectedIds, onToggle, onSelectAll, onClearAll }: Props) {
  if (drugs.length === 0) {
    return <p className="text-gray-500 text-sm italic">No drugs in this class.</p>;
  }

  const allSelected = drugs.every((d) => selectedIds.has(d.id));

  return (
    <div className="space-y-2">
      <div className="flex gap-3 text-xs">
        <button
          onClick={onSelectAll}
          className="text-blue-400 hover:text-blue-300 underline-offset-2 hover:underline"
        >
          Select all
        </button>
        <button
          onClick={onClearAll}
          className="text-gray-500 hover:text-gray-300 underline-offset-2 hover:underline"
        >
          Clear
        </button>
        <span className="text-gray-600 ml-auto">
          {selectedIds.size} / {drugs.length} selected
        </span>
      </div>

      {drugs.map((drug) => (
        <label
          key={drug.id}
          className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors
            ${selectedIds.has(drug.id)
              ? 'border-blue-500 bg-blue-950/40'
              : 'border-gray-700 hover:border-gray-500'}`}
        >
          <input
            type="checkbox"
            checked={selectedIds.has(drug.id)}
            onChange={() => onToggle(drug.id)}
            className="mt-0.5 accent-blue-500"
          />
          <div>
            <p className="text-sm font-medium text-white">{drug.name}</p>
            {drug.generic_name && (
              <p className="text-xs text-gray-500">{drug.generic_name}</p>
            )}
          </div>
        </label>
      ))}

      {!allSelected && drugs.length > 3 && (
        <button
          onClick={onSelectAll}
          className="w-full py-2 text-sm text-gray-400 border border-dashed border-gray-700 rounded-lg hover:border-gray-500 hover:text-gray-200 transition-colors"
        >
          + Select remaining {drugs.length - selectedIds.size}
        </button>
      )}
    </div>
  );
}
