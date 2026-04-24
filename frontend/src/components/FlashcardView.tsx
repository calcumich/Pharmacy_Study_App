import { useState } from 'react';
import type { AttributeType, DrugDetail, InteractionEntry } from '../types/api';
import { submitReview } from '../api';

interface Card {
  drug: DrugDetail;
  attributeType: AttributeType;
}

interface Props {
  cards: Card[];
  sessionId: string | null;
  userId: string;
  onDone: () => void;
}

function renderContent(content: unknown, shape: string): React.ReactNode {
  if (content == null) return <span className="text-gray-500 italic">No data</span>;

  if (shape === 'scalar') {
    return <p className="text-lg text-gray-100 leading-relaxed">{String(content)}</p>;
  }

  if (shape === 'list') {
    const items = content as string[];
    if (items.length === 0) return <span className="text-gray-500 italic">None recorded</span>;
    return (
      <ul className="space-y-2 text-left">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3 text-gray-200">
            <span className="text-blue-400 font-bold shrink-0">{i + 1}.</span>
            {item}
          </li>
        ))}
      </ul>
    );
  }

  if (shape === 'relational') {
    const interactions = content as InteractionEntry[];
    if (interactions.length === 0) {
      return <span className="text-gray-500 italic">No significant interactions recorded</span>;
    }
    const SEVERITY_STYLE: Record<string, string> = {
      minor:           'border-yellow-600 bg-yellow-900/30 text-yellow-200',
      moderate:        'border-orange-600 bg-orange-900/30 text-orange-200',
      major:           'border-red-600 bg-red-900/30 text-red-200',
      contraindicated: 'border-red-500 bg-red-950 text-red-100',
    };
    return (
      <div className="space-y-2 text-left w-full">
        {interactions.map((iact, i) => (
          <div key={i} className={`border rounded-lg p-3 ${SEVERITY_STYLE[iact.severity] ?? ''}`}>
            <p className="text-xs font-bold uppercase tracking-widest mb-1">{iact.severity}</p>
            {iact.description && <p className="text-sm">{iact.description}</p>}
          </div>
        ))}
      </div>
    );
  }

  return <pre className="text-sm text-gray-300">{JSON.stringify(content, null, 2)}</pre>;
}

function getCardContent(card: Card): unknown {
  const { drug, attributeType: at } = card;
  if (at.shape === 'scalar') return drug.attributes[at.slug] ?? null;
  if (at.slug === 'indications') return drug.indications;
  if (at.slug === 'adrs') return drug.adrs;
  if (at.slug === 'metabolism') return drug.metabolism;
  if (at.slug === 'ddis') return [];
  return null;
}

const RATING_LABELS: Record<number, string> = { 1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy' };
const RATING_STYLES: Record<number, string> = {
  1: 'border-red-700 bg-red-900/40 hover:bg-red-800/60 text-red-200',
  2: 'border-yellow-700 bg-yellow-900/40 hover:bg-yellow-800/60 text-yellow-200',
  3: 'border-green-700 bg-green-900/40 hover:bg-green-800/60 text-green-200',
  4: 'border-blue-600 bg-blue-900/40 hover:bg-blue-800/60 text-blue-200',
};

export function FlashcardView({ cards, userId, onDone }: Props) {
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (cards.length === 0) {
    return (
      <div className="text-center py-20 text-gray-500">
        <p>No cards to show.</p>
        <button onClick={onDone} className="mt-4 text-blue-400 hover:text-blue-300 underline">
          Back
        </button>
      </div>
    );
  }

  const card = cards[index];
  const content = getCardContent(card);
  const progress = `${index + 1} / ${cards.length}`;

  function next() {
    if (index + 1 >= cards.length) {
      onDone();
    } else {
      setIndex((i) => i + 1);
      setRevealed(false);
    }
  }

  function prev() {
    if (index > 0) {
      setIndex((i) => i - 1);
      setRevealed(false);
    }
  }

  async function rate(rating: 1 | 2 | 3 | 4) {
    const card = cards[index];
    setSubmitting(true);
    try {
      await submitReview({
        user_id: userId,
        drug_id: card.drug.id,
        attribute_type_id: card.attributeType.id,
        rating,
      });
    } catch (err) {
      console.error('Review submission failed:', err);
    } finally {
      setSubmitting(false);
      next();
    }
  }

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      {/* Progress */}
      <div className="flex items-center gap-4 text-sm text-gray-500">
        <span>{progress}</span>
        <div className="w-48 h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 transition-all"
            style={{ width: `${((index + 1) / cards.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Card */}
      <div className="w-full max-w-2xl">
        {/* Front */}
        <div className="rounded-2xl border border-gray-700 bg-gray-800 p-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-400 mb-2">
            {card.attributeType.label}
          </p>
          <h2 className="text-3xl font-bold text-white mb-1">{card.drug.name}</h2>
          {card.drug.generic_name && (
            <p className="text-sm text-gray-500">{card.drug.generic_name}</p>
          )}

          {!revealed ? (
            <button
              onClick={() => setRevealed(true)}
              className="mt-8 px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition-colors"
            >
              Show answer
            </button>
          ) : (
            <>
              <div className="mt-8 pt-6 border-t border-gray-700 text-left">
                {renderContent(content, card.attributeType.shape)}
              </div>
              <div className="flex gap-2 justify-center mt-6">
                {([1, 2, 3, 4] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => rate(r)}
                    disabled={submitting}
                    className={`px-4 py-2 rounded-xl border text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${RATING_STYLES[r]}`}
                  >
                    {RATING_LABELS[r]}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex gap-3">
        <button
          onClick={prev}
          disabled={index === 0}
          className="px-5 py-2 rounded-xl border border-gray-700 text-gray-400 disabled:opacity-30 hover:enabled:border-gray-500 hover:enabled:text-white transition-colors"
        >
          ← Prev
        </button>
        {/* Next/Finish only shown before the answer is revealed (skip without rating) */}
        {!revealed && (
          <button
            onClick={next}
            className="px-5 py-2 rounded-xl bg-gray-700 hover:bg-gray-600 text-white font-medium transition-colors"
          >
            {index + 1 >= cards.length ? 'Finish' : 'Skip →'}
          </button>
        )}
      </div>

      <button onClick={onDone} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
        Exit session
      </button>
    </div>
  );
}
