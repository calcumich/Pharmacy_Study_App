export interface DrugClassNode {
  id: string;
  name: string;
  slug: string;
  description?: string;
  direct_drug_count: number;
  descendant_drug_count: number;
  children: DrugClassNode[];
}

export interface DrugSummary {
  id: string;
  name: string;
  generic_name?: string;
  drug_class_id?: string;
}

export interface DrugDetail {
  id: string;
  name: string;
  generic_name?: string;
  drug_class_id?: string;
  attributes: Record<string, unknown>;
  indications: string[];
  adrs: string[];
  metabolism: string[];
}

export interface AttributeType {
  id: string;
  slug: string;
  label: string;
  shape: 'scalar' | 'list' | 'relational';
  source_table: string;
  display_order: number;
}

export interface InteractionEntry {
  severity: 'minor' | 'moderate' | 'major' | 'contraindicated';
  description?: string;
  partner_id: string;
}

export interface TableCell {
  drug_id: string;
  attribute_type_id: string;
  // scalar → string | null; list → string[]; relational → InteractionEntry[]
  content: string | string[] | InteractionEntry[] | null;
}

export interface TableResponse {
  drug_ids: string[];
  attribute_type_ids: string[];
  cells: TableCell[];
}

// ── Sessions ──────────────────────────────────────────────────────────────────

export interface SessionCreate {
  drug_ids: string[];
  mode: 'flashcard' | 'table';
}

export interface SessionResponse {
  session_id: string;
  started_at: string;
}

// ── Reviews ───────────────────────────────────────────────────────────────────

export interface ReviewRequest {
  drug_id: string;
  rating: 1 | 2 | 3 | 4;
  attribute_type_id?: string;
}

export interface ReviewResponse {
  drug_id: string;
  state: string;
  stability: number;
  difficulty: number;
  due_date: string;
  review_count: number;
}

// ── Queue ─────────────────────────────────────────────────────────────────────

export interface QueueItem {
  drug_id: string;
  state: string;
  stability: number | null;
  due_date: string | null;
}

export interface QueueResponse {
  items: QueueItem[];
}
