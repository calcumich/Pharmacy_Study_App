# AI Collaboration Rules

This project is optimized for learning and deliberate engineering practice, not
maximum autonomous code generation. AI agents may help research, critique,
explain, test, and implement, but the human maintainer owns the design loop.

## Before Non-Trivial Implementation

1. Identify the design decisions involved.
2. List at least two viable options when tradeoffs exist.
3. State the recommended option and why.
4. Ask whether a decision worksheet is needed for any architectural decision.
   The maintainer owns the final decision text.
5. Do not introduce new frameworks, services, libraries, hosting models,
   databases, queues, auth flows, or architectural patterns without explicit
   approval.
6. Prefer a small written plan before editing code.

## During Implementation

1. Prefer small, reviewable diffs.
2. Do not change unrelated files.
3. Follow the existing project structure unless an accepted decision says
   otherwise.
4. Add or update tests when behavior changes.
5. Keep code comments sparse and useful.
6. Include build/test commands used for validation.

## After Implementation

1. Summarize what changed.
2. Explain any assumptions.
3. Identify any new learning debt: project behavior that now depends on
   something the maintainer may not yet be able to explain.
4. Provide 3-5 questions the maintainer should be able to answer before merging
   when the change is non-trivial.
5. Compare the diff to the accepted plan or decision and call out any implicit
   architectural choices that slipped into the code.

## Decision Rule

New technology requires an explicit maintainer-owned decision. A new helper
library may be small enough to explain in the implementation notes, but these
changes require a decision worksheet and maintainer approval before code:

- New hosting model or cloud service.
- New database, cache, queue, search service, or background job system.
- New authentication or authorization approach.
- New frontend framework, backend framework, or major runtime dependency.
- New cross-cutting observability, deployment, or infrastructure pattern.

Use the workflow in `docs/ai-collaboration.md` for larger tasks.
