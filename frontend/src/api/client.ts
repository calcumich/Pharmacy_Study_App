import type {
  AttributeType,
  DrugClassNode,
  DrugDetail,
  DrugSummary,
  TableResponse,
} from '../types/api';

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export async function getDrugClasses(): Promise<DrugClassNode[]> {
  return get('/drug-classes');
}

export async function getDrugsByClass(classId: string): Promise<DrugSummary[]> {
  return get(`/drug-classes/${classId}/drugs`);
}

export async function getAttributeTypes(): Promise<AttributeType[]> {
  return get('/attribute-types');
}

export async function getDrug(drugId: string): Promise<DrugDetail> {
  return get(`/drugs/${drugId}`);
}

export async function getTable(
  drugIds: string[],
  attributeTypeIds: string[],
): Promise<TableResponse> {
  const params = new URLSearchParams();
  drugIds.forEach((id) => params.append('drug_ids', id));
  attributeTypeIds.forEach((id) => params.append('attribute_type_ids', id));
  return get(`/study/table?${params.toString()}`);
}
