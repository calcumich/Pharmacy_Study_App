/**
 * Static mock data that mirrors the real API response shapes exactly.
 * Flip VITE_USE_MOCK=false to swap in the real backend with no other changes.
 */
import type {
  AttributeType,
  DrugClassNode,
  DrugDetail,
  DrugSummary,
  TableResponse,
} from '../types/api';

// ── IDs ───────────────────────────────────────────────────────────────────────

const ID = {
  // classes
  cv:            'c1000000-0000-0000-0000-000000000001',
  betaBlockers:  'c1000000-0000-0000-0000-000000000002',
  aceInhibitors: 'c1000000-0000-0000-0000-000000000003',
  statins:       'c1000000-0000-0000-0000-000000000004',
  antibiotics:   'c2000000-0000-0000-0000-000000000001',
  betaLactams:   'c2000000-0000-0000-0000-000000000002',
  penicillins:   'c2000000-0000-0000-0000-000000000003',
  // drugs
  metoprolol:    'd0000000-0000-0000-0000-000000000001',
  atenolol:      'd0000000-0000-0000-0000-000000000002',
  carvedilol:    'd0000000-0000-0000-0000-000000000003',
  lisinopril:    'd0000000-0000-0000-0000-000000000004',
  ramipril:      'd0000000-0000-0000-0000-000000000005',
  atorvastatin:  'd0000000-0000-0000-0000-000000000006',
  amoxicillin:   'd0000000-0000-0000-0000-000000000007',
  // attribute types
  atMoa:         'a0000000-0000-0000-0000-000000000001',
  atHalfLife:    'a0000000-0000-0000-0000-000000000002',
  atIndications: 'a0000000-0000-0000-0000-000000000003',
  atAdrs:        'a0000000-0000-0000-0000-000000000004',
  atMetabolism:  'a0000000-0000-0000-0000-000000000005',
  atDdis:        'a0000000-0000-0000-0000-000000000006',
} as const;

// ── Drug class tree ───────────────────────────────────────────────────────────

const DRUG_CLASSES: DrugClassNode[] = [
  {
    id: ID.cv,
    name: 'Cardiovascular',
    slug: 'cardiovascular',
    description: 'Drugs acting on the heart and vasculature',
    direct_drug_count: 0,
    descendant_drug_count: 6,
    children: [
      {
        id: ID.betaBlockers,
        name: 'Beta-Blockers',
        slug: 'beta-blockers',
        description: 'Competitive antagonists of β-adrenoceptors',
        direct_drug_count: 3,
        descendant_drug_count: 3,
        children: [],
      },
      {
        id: ID.aceInhibitors,
        name: 'ACE Inhibitors',
        slug: 'ace-inhibitors',
        description: 'Inhibit angiotensin-converting enzyme',
        direct_drug_count: 2,
        descendant_drug_count: 2,
        children: [],
      },
      {
        id: ID.statins,
        name: 'Statins',
        slug: 'statins',
        description: 'HMG-CoA reductase inhibitors',
        direct_drug_count: 1,
        descendant_drug_count: 1,
        children: [],
      },
    ],
  },
  {
    id: ID.antibiotics,
    name: 'Antibiotics',
    slug: 'antibiotics',
    description: 'Antimicrobial agents',
    direct_drug_count: 0,
    descendant_drug_count: 1,
    children: [
      {
        id: ID.betaLactams,
        name: 'Beta-Lactams',
        slug: 'beta-lactams',
        description: 'Contain a β-lactam ring; inhibit cell-wall synthesis',
        direct_drug_count: 0,
        descendant_drug_count: 1,
        children: [
          {
            id: ID.penicillins,
            name: 'Penicillins',
            slug: 'penicillins',
            description: 'Natural and semi-synthetic penicillin derivatives',
            direct_drug_count: 1,
            descendant_drug_count: 1,
            children: [],
          },
        ],
      },
    ],
  },
];

// ── Drug summaries by class ───────────────────────────────────────────────────

const DRUGS_BY_CLASS: Record<string, DrugSummary[]> = {
  [ID.betaBlockers]: [
    { id: ID.metoprolol,  name: 'Metoprolol',  generic_name: 'metoprolol tartrate/succinate', drug_class_id: ID.betaBlockers },
    { id: ID.atenolol,    name: 'Atenolol',    generic_name: 'atenolol',                      drug_class_id: ID.betaBlockers },
    { id: ID.carvedilol,  name: 'Carvedilol',  generic_name: 'carvedilol',                    drug_class_id: ID.betaBlockers },
  ],
  [ID.aceInhibitors]: [
    { id: ID.lisinopril,  name: 'Lisinopril',  generic_name: 'lisinopril',                    drug_class_id: ID.aceInhibitors },
    { id: ID.ramipril,    name: 'Ramipril',    generic_name: 'ramipril',                      drug_class_id: ID.aceInhibitors },
  ],
  [ID.statins]: [
    { id: ID.atorvastatin, name: 'Atorvastatin', generic_name: 'atorvastatin calcium',        drug_class_id: ID.statins },
  ],
  [ID.penicillins]: [
    { id: ID.amoxicillin,  name: 'Amoxicillin',  generic_name: 'amoxicillin trihydrate',      drug_class_id: ID.penicillins },
  ],
  // Parent classes — return children's drugs
  [ID.cv]:          [], // handled in getDrugsByClass fallback
  [ID.antibiotics]: [],
  [ID.betaLactams]: [
    { id: ID.amoxicillin, name: 'Amoxicillin', generic_name: 'amoxicillin trihydrate', drug_class_id: ID.penicillins },
  ],
};

// ── Drug details ──────────────────────────────────────────────────────────────

const DRUG_DETAILS: Record<string, DrugDetail> = {
  [ID.metoprolol]: {
    id: ID.metoprolol,
    name: 'Metoprolol',
    generic_name: 'metoprolol tartrate/succinate',
    drug_class_id: ID.betaBlockers,
    attributes: {
      moa: 'Selective β1-adrenoceptor antagonist; reduces heart rate and myocardial oxygen demand without significant β2 blockade at therapeutic doses',
      half_life: '3–7 h (tartrate IR); 12–22 h (succinate XR)',
    },
    indications: ['Hypertension', 'Stable angina pectoris', 'Heart failure (HFrEF)', 'Post-MI secondary prevention', 'Atrial fibrillation (rate control)'],
    adrs: ['Bradycardia', 'Fatigue / lethargy', 'Cold extremities', 'Hypotension', 'Bronchospasm (high doses)', 'Impaired glucose tolerance'],
    metabolism: ['CYP2D6 (major substrate)', 'Extensive hepatic first-pass', 'Active metabolites: α-hydroxymetoprolol'],
  },
  [ID.atenolol]: {
    id: ID.atenolol,
    name: 'Atenolol',
    generic_name: 'atenolol',
    drug_class_id: ID.betaBlockers,
    attributes: {
      moa: 'Selective β1-adrenoceptor antagonist; hydrophilic — does not cross BBB readily',
      half_life: '6–7 h',
    },
    indications: ['Hypertension', 'Angina pectoris', 'Post-MI secondary prevention'],
    adrs: ['Bradycardia', 'Fatigue', 'Cold extremities', 'Rebound hypertension on abrupt withdrawal'],
    metabolism: ['Minimal hepatic metabolism', 'Renally excreted unchanged (~50%)', 'Dose-adjust in renal impairment'],
  },
  [ID.carvedilol]: {
    id: ID.carvedilol,
    name: 'Carvedilol',
    generic_name: 'carvedilol',
    drug_class_id: ID.betaBlockers,
    attributes: {
      moa: 'Non-selective β1/β2-blocker + α1-blocker; vasodilation via α1 blockade reduces afterload',
      half_life: '7–10 h',
    },
    indications: ['Heart failure (HFrEF)', 'Hypertension', 'Post-MI LV dysfunction'],
    adrs: ['Dizziness / orthostatic hypotension (α1 blockade)', 'Fatigue', 'Bradycardia', 'Weight gain'],
    metabolism: ['CYP2D6 and CYP2C9 (major)', 'Extensive hepatic first-pass (~85%)', 'Stereoselective metabolism'],
  },
  [ID.lisinopril]: {
    id: ID.lisinopril,
    name: 'Lisinopril',
    generic_name: 'lisinopril',
    drug_class_id: ID.aceInhibitors,
    attributes: {
      moa: 'Competitive inhibitor of ACE; prevents conversion of angiotensin I → II; reduces aldosterone secretion and bradykinin degradation',
      half_life: '12 h',
    },
    indications: ['Hypertension', 'Heart failure', 'Post-MI', 'Diabetic nephropathy'],
    adrs: ['Dry cough (bradykinin)', 'Angioedema (rare, serious)', 'Hyperkalemia', 'Fetotoxicity (CI in pregnancy)', 'First-dose hypotension'],
    metabolism: ['Not hepatically metabolised (active drug, not prodrug)', 'Renally excreted unchanged', 'Dose-adjust in renal impairment'],
  },
  [ID.ramipril]: {
    id: ID.ramipril,
    name: 'Ramipril',
    generic_name: 'ramipril',
    drug_class_id: ID.aceInhibitors,
    attributes: {
      moa: 'Prodrug; hydrolysed to ramiprilat, a high-affinity ACE inhibitor with long tissue-binding duration',
      half_life: '13–17 h (ramiprilat)',
    },
    indications: ['Hypertension', 'Heart failure', 'Post-MI', 'CV risk reduction (HOPE trial)', 'Diabetic nephropathy'],
    adrs: ['Dry cough', 'Angioedema', 'Hyperkalemia', 'Teratogenicity', 'Renal impairment (bilateral RAS)'],
    metabolism: ['Hepatic esterases → ramiprilat (active)', 'CYP minor role', 'Renal excretion'],
  },
  [ID.atorvastatin]: {
    id: ID.atorvastatin,
    name: 'Atorvastatin',
    generic_name: 'atorvastatin calcium',
    drug_class_id: ID.statins,
    attributes: {
      moa: 'Competitive HMG-CoA reductase inhibitor; reduces hepatic cholesterol synthesis → upregulates LDL-R → increased LDL clearance',
      half_life: '14 h (active metabolites up to 20–30 h)',
    },
    indications: ['Primary hypercholesterolaemia', 'Combined hyperlipidaemia', 'CV risk reduction (primary & secondary prevention)', 'Familial hypercholesterolaemia'],
    adrs: ['Myalgia / myopathy', 'Rhabdomyolysis (rare)', 'Elevated transaminases', 'New-onset diabetes', 'Headache'],
    metabolism: ['CYP3A4 (major substrate)', 'Active metabolites (ortho- and para-OH atorvastatin)', 'Biliary excretion', 'Substrate for OATP1B1'],
  },
  [ID.amoxicillin]: {
    id: ID.amoxicillin,
    name: 'Amoxicillin',
    generic_name: 'amoxicillin trihydrate',
    drug_class_id: ID.penicillins,
    attributes: {
      moa: 'Aminopenicillin; binds PBPs → inhibits peptidoglycan cross-linking → bactericidal; extended spectrum vs. gram-negatives vs. ampicillin',
      half_life: '1–1.5 h',
    },
    indications: ['Otitis media', 'Community-acquired pneumonia', 'Streptococcal pharyngitis', 'UTI (susceptible organisms)', 'H. pylori eradication (triple therapy)'],
    adrs: ['Diarrhoea / GI upset', 'Maculopapular rash', 'Hypersensitivity / anaphylaxis', 'C. difficile colitis', 'Antibiotic-associated diarrhoea'],
    metabolism: ['Minimal hepatic metabolism', 'Primarily renal excretion (tubular secretion)', 'Probenecid increases levels'],
  },
};

// ── Attribute types ───────────────────────────────────────────────────────────

const ATTRIBUTE_TYPES: AttributeType[] = [
  { id: ID.atMoa,         slug: 'moa',         label: 'Mechanism of Action',    shape: 'scalar',      source_table: 'drugs',             display_order: 1 },
  { id: ID.atHalfLife,    slug: 'half_life',   label: 'Half-life',              shape: 'scalar',      source_table: 'drugs',             display_order: 2 },
  { id: ID.atIndications, slug: 'indications', label: 'Indications',            shape: 'list',        source_table: 'drug_indications',  display_order: 3 },
  { id: ID.atAdrs,        slug: 'adrs',        label: 'Adverse Drug Reactions', shape: 'list',        source_table: 'drug_adrs',         display_order: 4 },
  { id: ID.atMetabolism,  slug: 'metabolism',  label: 'Metabolism / CYP',       shape: 'list',        source_table: 'drug_metabolism',   display_order: 5 },
  { id: ID.atDdis,        slug: 'ddis',        label: 'Major Drug Interactions', shape: 'relational', source_table: 'drug_interactions', display_order: 6 },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function delay<T>(value: T, ms = 120): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

function getCellContent(drug: DrugDetail, at: AttributeType): unknown {
  if (at.shape === 'scalar') return drug.attributes[at.slug] ?? null;
  if (at.slug === 'indications') return drug.indications;
  if (at.slug === 'adrs') return drug.adrs;
  if (at.slug === 'metabolism') return drug.metabolism;
  if (at.slug === 'ddis') return []; // no mock interactions
  return null;
}

// ── Exported API (same signatures as client.ts) ───────────────────────────────

export async function getDrugClasses(): Promise<DrugClassNode[]> {
  return delay(DRUG_CLASSES);
}

export async function getDrugsByClass(classId: string): Promise<DrugSummary[]> {
  // Collect drugs from this class and all descendants by walking the tree.
  function collectIds(nodes: DrugClassNode[], target: string): string[] {
    for (const node of nodes) {
      if (node.id === target) {
        const ids: string[] = [node.id];
        function gatherChildren(n: DrugClassNode) {
          ids.push(n.id);
          n.children.forEach(gatherChildren);
        }
        node.children.forEach(gatherChildren);
        return ids;
      }
      const found = collectIds(node.children, target);
      if (found.length) return found;
    }
    return [];
  }

  const classIds = collectIds(DRUG_CLASSES, classId);
  const seen = new Set<string>();
  const result: DrugSummary[] = [];
  for (const cid of classIds) {
    for (const drug of DRUGS_BY_CLASS[cid] ?? []) {
      if (!seen.has(drug.id)) {
        seen.add(drug.id);
        result.push(drug);
      }
    }
  }
  return delay(result.sort((a, b) => a.name.localeCompare(b.name)));
}

export async function getAttributeTypes(): Promise<AttributeType[]> {
  return delay(ATTRIBUTE_TYPES);
}

export async function getDrug(drugId: string): Promise<DrugDetail> {
  const drug = DRUG_DETAILS[drugId];
  if (!drug) throw new Error(`Mock: drug ${drugId} not found`);
  return delay(drug);
}

export async function getTable(
  drugIds: string[],
  attributeTypeIds: string[],
): Promise<TableResponse> {
  const atMap = Object.fromEntries(ATTRIBUTE_TYPES.map((a) => [a.id, a]));
  const cells = drugIds.flatMap((drugId) =>
    attributeTypeIds.map((atId) => {
      const drug = DRUG_DETAILS[drugId];
      const at = atMap[atId];
      return {
        drug_id: drugId,
        attribute_type_id: atId,
        content: drug && at ? getCellContent(drug, at) : null,
      };
    }),
  );
  return delay({ drug_ids: drugIds, attribute_type_ids: attributeTypeIds, cells } as TableResponse);
}
