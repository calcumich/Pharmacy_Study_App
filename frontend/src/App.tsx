import { useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { getDrugClasses, getDrugsByClass, getAttributeTypes, getDrug, getTable, createSession } from './api';
import { getQueue, setAuthToken } from './api/client';
import { supabase } from './lib/supabase';
import { ClassBrowser } from './components/ClassBrowser';
import { DrugSelector } from './components/DrugSelector';
import { AttributeSelector } from './components/AttributeSelector';
import { TableView } from './components/TableView';
import { FlashcardView } from './components/FlashcardView';
import type {
  AttributeType,
  DrugClassNode,
  DrugDetail,
  DrugSummary,
  InteractionEntry,
  QueueItem,
  TableResponse,
} from './types/api';

// ── Step type ─────────────────────────────────────────────────────────────────

type Step = 'browse' | 'drugs' | 'configure' | 'study';
type StudyMode = 'flashcard' | 'table';

// ── FlashcardView card shape ──────────────────────────────────────────────────

interface Card {
  drug: DrugDetail;
  attributeType: AttributeType;
}

// ── Stepper header ────────────────────────────────────────────────────────────

const STEPS: { key: Step; label: string }[] = [
  { key: 'browse',    label: '1. Class'      },
  { key: 'drugs',     label: '2. Drugs'      },
  { key: 'configure', label: '3. Configure'  },
  { key: 'study',     label: '4. Study'      },
];

function StepIndicator({ current }: { current: Step }) {
  const currentIndex = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center gap-2 text-sm">
      {STEPS.map((s, i) => (
        <div key={s.key} className="flex items-center gap-2">
          <span
            className={`font-medium ${
              i < currentIndex
                ? 'text-blue-400'
                : i === currentIndex
                ? 'text-white'
                : 'text-gray-600'
            }`}
          >
            {s.label}
          </span>
          {i < STEPS.length - 1 && <span className="text-gray-700">›</span>}
        </div>
      ))}
    </div>
  );
}

// ── Login form ────────────────────────────────────────────────────────────────

function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setError(error.message);
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <p className="text-4xl mb-3">💊</p>
          <h1 className="text-xl font-bold">Pharmacy Study App</h1>
          <p className="text-sm text-gray-500 mt-1">Sign in to continue</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  // ── Auth state ────────────────────────────────────────────────────────────
  const [session, setSession] = useState<Session | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  // ── Data loaded once ──────────────────────────────────────────────────────
  const [classes, setClasses] = useState<DrugClassNode[]>([]);
  const [attributeTypes, setAttributeTypes] = useState<AttributeType[]>([]);

  // ── Step state ────────────────────────────────────────────────────────────
  const [step, setStep] = useState<Step>('browse');

  // ── Selection state ───────────────────────────────────────────────────────
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedClassName, setSelectedClassName] = useState<string>('');
  const [drugs, setDrugs] = useState<DrugSummary[]>([]);
  const [selectedDrugIds, setSelectedDrugIds] = useState<Set<string>>(new Set());
  const [selectedAtIds, setSelectedAtIds] = useState<Set<string>>(new Set());
  const [studyMode, setStudyMode] = useState<StudyMode>('flashcard');

  // ── Study data ────────────────────────────────────────────────────────────
  const [tableData, setTableData] = useState<TableResponse | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ddisByDrugId, setDdisByDrugId] = useState<Record<string, InteractionEntry[]>>({});
  const [queueByDrugId, setQueueByDrugId] = useState<Record<string, QueueItem>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Auth bootstrap ────────────────────────────────────────────────────────
  useEffect(() => {
    const useMock = import.meta.env.VITE_USE_MOCK === 'true';
    if (useMock) { setAuthLoading(false); return; }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setAuthToken(session?.access_token ?? null);
      setAuthLoading(false);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setAuthToken(session?.access_token ?? null);
    });
    return () => subscription.unsubscribe();
  }, []);

  // ── Data bootstrap ────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([getDrugClasses(), getAttributeTypes()])
      .then(([c, a]) => {
        setClasses(c);
        setAttributeTypes(a);
        // Pre-select all attribute types
        setSelectedAtIds(new Set(a.map((x) => x.id)));
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handleClassSelect(id: string, name: string) {
    setSelectedClassId(id);
    setSelectedClassName(name);
    setSelectedDrugIds(new Set());
    setDrugs([]);
    setLoading(true);
    setError(null);
    getDrugsByClass(id)
      .then((d) => {
        setDrugs(d);
        setStep('drugs');
      })
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }

  function toggleDrug(id: string) {
    setSelectedDrugIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAt(id: string) {
    setSelectedAtIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function startStudy() {
    const drugIds = Array.from(selectedDrugIds);
    const atIds = Array.from(selectedAtIds);
    if (drugIds.length === 0 || atIds.length === 0) return;

    setLoading(true);
    setError(null);
    try {
      if (studyMode === 'table') {
        const data = await getTable(drugIds, atIds);
        setTableData(data);
        setCards([]);
      } else {
        const ats = attributeTypes.filter((a) => atIds.includes(a.id));
        const relationalAtIds = ats.filter((a) => a.shape === 'relational').map((a) => a.id);

        // Create the session first; queue/DDI fetches can run concurrently with drug detail fetches.
        const session = await createSession({ drug_ids: drugIds, mode: 'flashcard' });

        const [details, queueResp, ddiTable] = await Promise.all([
          Promise.all(drugIds.map((id) => getDrug(id))),
          // Queue is drug-level SRS state; degrade gracefully if it fails.
          getQueue(drugIds, 200).catch(() => ({ items: [] as QueueItem[] })),
          relationalAtIds.length > 0
            ? getTable(drugIds, relationalAtIds)
            : Promise.resolve(null),
        ]);

        // Index DDI cells by drug for FlashcardView lookup (one fetch covers every relational AT).
        const ddiMap: Record<string, InteractionEntry[]> = {};
        if (ddiTable) {
          for (const cell of ddiTable.cells) {
            ddiMap[cell.drug_id] = (cell.content as InteractionEntry[]) ?? [];
          }
        }

        // Sort cards by SRS due-rank — cards whose drug is due come first, in queue order.
        const queueRank: Record<string, number> = {};
        const queueMap: Record<string, QueueItem> = {};
        queueResp.items.forEach((item, i) => {
          queueRank[item.drug_id] = i;
          queueMap[item.drug_id] = item;
        });

        const newCards: Card[] = details.flatMap((drug) =>
          ats.map((at) => ({ drug, attributeType: at })),
        );
        newCards.sort((a, b) => {
          const aRank = queueRank[a.drug.id] ?? Number.POSITIVE_INFINITY;
          const bRank = queueRank[b.drug.id] ?? Number.POSITIVE_INFINITY;
          return aRank - bRank;
        });

        setSessionId(session.session_id);
        setDdisByDrugId(ddiMap);
        setQueueByDrugId(queueMap);
        setCards(newCards);
        setTableData(null);
      }
      setStep('study');
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setStep('browse');
    setSelectedClassId(null);
    setSelectedClassName('');
    setDrugs([]);
    setSelectedDrugIds(new Set());
    setTableData(null);
    setCards([]);
  }

  // ── Auth gates ────────────────────────────────────────────────────────────

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-500 text-sm animate-pulse">Loading…</p>
      </div>
    );
  }

  if (!session && import.meta.env.VITE_USE_MOCK !== 'true') {
    return <LoginForm />;
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const canStartStudy = selectedDrugIds.size > 0 && selectedAtIds.size > 0;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold tracking-tight">
            Pharmacy Study App
          </h1>
          <p className="text-xs text-gray-500">Spaced-repetition for pharmacy students</p>
        </div>
        <div className="flex items-center gap-3">
          {import.meta.env.VITE_USE_MOCK === 'true' && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-yellow-900/50 border border-yellow-700 text-yellow-400 font-mono">
              mock data
            </span>
          )}
          {session && (
            <button
              onClick={() => supabase.auth.signOut()}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Sign out
            </button>
          )}
        </div>
      </header>

      {step !== 'study' && (
        <div className="px-6 py-3 border-b border-gray-900">
          <StepIndicator current={step} />
        </div>
      )}

      {error && (
        <div className="mx-6 mt-4 px-4 py-3 rounded-lg bg-red-950 border border-red-800 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* ── Study view (full-width) ──────────────────────────────────────── */}
      {step === 'study' && (
        <div className="px-6 py-4">
          <div className="flex items-center gap-4 mb-6">
            <button
              onClick={reset}
              className="text-sm text-gray-500 hover:text-gray-300 flex items-center gap-1 transition-colors"
            >
              ← New session
            </button>
            <span className="text-gray-700">|</span>
            <span className="text-sm text-gray-400">
              {selectedClassName} · {selectedDrugIds.size} drug{selectedDrugIds.size !== 1 ? 's' : ''} ·{' '}
              {studyMode === 'flashcard' ? `${cards.length} cards` : `${selectedAtIds.size} attributes`}
            </span>
          </div>

          {studyMode === 'table' && tableData && (
            <TableView
              data={tableData}
              drugs={drugs.filter((d) => selectedDrugIds.has(d.id))}
              attributeTypes={attributeTypes.filter((a) => selectedAtIds.has(a.id))}
            />
          )}
          {studyMode === 'flashcard' && (
            <FlashcardView
              cards={cards}
              sessionId={sessionId}
              ddisByDrugId={ddisByDrugId}
              queueByDrugId={queueByDrugId}
              onDone={reset}
            />
          )}
        </div>
      )}

      {/* ── Setup steps (two-column layout) ─────────────────────────────── */}
      {step !== 'study' && (
        <div className="flex h-[calc(100vh-7rem)]">
          {/* Left sidebar: class browser */}
          <aside className="w-64 shrink-0 border-r border-gray-800 p-4 overflow-y-auto">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
              Drug Classes
            </h2>
            {classes.length === 0 && !loading ? (
              <p className="text-xs text-gray-600 italic">Loading…</p>
            ) : (
              <ClassBrowser
                classes={classes}
                selectedId={selectedClassId}
                onSelect={handleClassSelect}
              />
            )}
          </aside>

          {/* Main area */}
          <main className="flex-1 overflow-y-auto p-6 space-y-8">
            {loading && (
              <p className="text-gray-500 text-sm animate-pulse">Loading…</p>
            )}

            {/* Step 2: drug selector */}
            {(step === 'drugs' || step === 'configure') && drugs.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
                  {selectedClassName} — Select drugs
                </h2>
                <DrugSelector
                  drugs={drugs}
                  selectedIds={selectedDrugIds}
                  onToggle={toggleDrug}
                  onSelectAll={() => setSelectedDrugIds(new Set(drugs.map((d) => d.id)))}
                  onClearAll={() => setSelectedDrugIds(new Set())}
                />
                {selectedDrugIds.size > 0 && step === 'drugs' && (
                  <button
                    onClick={() => setStep('configure')}
                    className="mt-4 px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-xl transition-colors"
                  >
                    Configure session →
                  </button>
                )}
              </section>
            )}

            {/* Step 3: configure */}
            {step === 'configure' && (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
                  Attributes to study
                </h2>
                <AttributeSelector
                  attributeTypes={attributeTypes}
                  selectedIds={selectedAtIds}
                  onToggle={toggleAt}
                />

                <div className="mt-6">
                  <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-3">
                    Study mode
                  </h2>
                  <div className="flex gap-3">
                    {(['flashcard', 'table'] as StudyMode[]).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => setStudyMode(mode)}
                        className={`px-5 py-2.5 rounded-xl border text-sm font-medium capitalize transition-colors
                          ${studyMode === mode
                            ? 'border-blue-500 bg-blue-600 text-white'
                            : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white'}`}
                      >
                        {mode === 'flashcard' ? '🃏 Flashcard' : '📊 Table'}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  onClick={startStudy}
                  disabled={!canStartStudy || loading}
                  className="mt-6 px-8 py-3 bg-green-600 hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
                >
                  {loading ? 'Loading…' : 'Start studying →'}
                </button>
              </section>
            )}

            {/* Placeholder when no class selected */}
            {step === 'browse' && !loading && (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <p className="text-4xl mb-4">💊</p>
                <p className="text-gray-400 text-sm">Select a drug class from the left to begin.</p>
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
