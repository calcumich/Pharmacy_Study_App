import type { AttributeType, DrugSummary, InteractionEntry, TableResponse } from '../types/api';

interface Props {
  data: TableResponse;
  drugs: DrugSummary[];
  attributeTypes: AttributeType[];
}

function CellContent({ content, shape }: { content: unknown; shape: string }) {
  if (content == null) return <span className="text-gray-600 italic text-xs">—</span>;

  if (shape === 'scalar') {
    return <span className="text-sm text-gray-200">{String(content)}</span>;
  }

  if (shape === 'list') {
    const items = content as string[];
    if (items.length === 0) return <span className="text-gray-600 italic text-xs">—</span>;
    return (
      <ul className="space-y-0.5">
        {items.map((item, i) => (
          <li key={i} className="text-xs text-gray-300 flex gap-1.5">
            <span className="text-gray-600 mt-0.5">•</span>
            {item}
          </li>
        ))}
      </ul>
    );
  }

  if (shape === 'relational') {
    const interactions = content as InteractionEntry[];
    if (interactions.length === 0) return <span className="text-gray-600 italic text-xs">None recorded</span>;

    const SEVERITY_COLOR: Record<string, string> = {
      minor:           'bg-yellow-900/50 text-yellow-300 border-yellow-700',
      moderate:        'bg-orange-900/50 text-orange-300 border-orange-700',
      major:           'bg-red-900/50 text-red-300 border-red-700',
      contraindicated: 'bg-red-950 text-red-200 border-red-600',
    };

    return (
      <div className="space-y-1">
        {interactions.map((iact, i) => (
          <div key={i} className={`text-xs px-2 py-1 rounded border ${SEVERITY_COLOR[iact.severity] ?? ''}`}>
            <span className="font-semibold uppercase tracking-wide text-[10px]">{iact.severity}</span>
            {iact.description && <p className="mt-0.5 opacity-80">{iact.description}</p>}
          </div>
        ))}
      </div>
    );
  }

  return <span className="text-gray-400 text-xs">{JSON.stringify(content)}</span>;
}

export function TableView({ data, drugs, attributeTypes }: Props) {
  const drugMap = Object.fromEntries(drugs.map((d) => [d.id, d]));
  const atMap = Object.fromEntries(attributeTypes.map((a) => [a.id, a]));

  // Index cells for O(1) lookup
  const cellIndex: Record<string, Record<string, unknown>> = {};
  for (const cell of data.cells) {
    cellIndex[cell.drug_id] ??= {};
    cellIndex[cell.drug_id][cell.attribute_type_id] = cell.content;
  }

  const visibleDrugs = data.drug_ids.map((id) => drugMap[id]).filter(Boolean);
  const visibleAts = data.attribute_type_ids.map((id) => atMap[id]).filter(Boolean);

  return (
    <div className="overflow-auto rounded-lg border border-gray-700">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-gray-800 border-b border-gray-700">
            <th className="px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider w-40 sticky left-0 bg-gray-800">
              Drug
            </th>
            {visibleAts.map((at) => (
              <th key={at.id} className="px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider min-w-48">
                {at.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleDrugs.map((drug, i) => (
            <tr
              key={drug.id}
              className={`border-b border-gray-800 ${i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-900/50'}`}
            >
              <td className="px-4 py-3 sticky left-0 bg-inherit border-r border-gray-800">
                <p className="text-sm font-semibold text-white">{drug.name}</p>
                {drug.generic_name && (
                  <p className="text-xs text-gray-500">{drug.generic_name}</p>
                )}
              </td>
              {visibleAts.map((at) => (
                <td key={at.id} className="px-4 py-3 align-top">
                  <CellContent
                    content={cellIndex[drug.id]?.[at.id]}
                    shape={at.shape}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
