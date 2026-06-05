# AI Collaboration Workflow

This workflow keeps AI assistance useful without letting agents silently become
the project author. The default loop is: decide first, implement second, review
against the decision, then check understanding.

## The Loop

1. Write a tiny issue-style goal.
   - User-visible goal.
   - Constraints.
   - What "done" means.

2. Produce a decision inventory.
   - What decisions must be made before this can be built responsibly?
   - Which decisions are already settled in `docs/decisions.md`?
   - Which decisions are reversible implementation details?

3. Prepare decision notes.
   - Do not create a second decision format unless the maintainer explicitly
     changes the convention.
   - The current canonical decision store is `docs/decisions.md`.
   - Agents may prepare a worksheet with options and questions, but the
     maintainer writes the decision, current understanding, and learning debt.
   - Keep minor implementation choices in the plan or final implementation
     summary.

4. Create an implementation plan.
   - Reference the relevant decisions.
   - Define the smallest useful diff.
   - List validation commands.

5. Implement in small diffs.
   - If the diff cannot be explained in five minutes, split the slice.
   - Do not make unrelated cleanup changes.

6. Review against the plan.
   - Compare the diff to the plan and decisions.
   - Identify implicit architecture, new dependencies, or hidden coupling.
   - Run tests/builds appropriate to the blast radius.

7. Do a learning checkout.
   - Summarize the request path, persistence path, error path, and test path.
   - Record learning debt.
   - Generate 3-5 questions the maintainer should be able to answer before
     merging.

## Decision Worksheet

Use this worksheet before implementation when a decision is needed. This is not
a second ADR format. It is a prompt for the maintainer to complete before the
decision is copied into the project's canonical decision store.

Agents may fill in:

- Decision question.
- Context.
- Options considered.
- Tradeoffs.
- Questions for the maintainer.

The maintainer fills in:

- My current understanding.
- Decision.
- Consequences.
- Reversal trigger.
- Learning debt.

Worksheet:

```md
## Decision Worksheet: Title

**Decision question.** What needs to be decided?

**Context.** Why does this matter now?

**Options considered.**
- **Option A.** What it means technically; tradeoffs.
- **Option B.** What it means technically; tradeoffs.

**Questions for the maintainer.** What must the human decide or explain?

**My current understanding.** Maintainer-owned.

**Decision.** Maintainer-owned.

**Consequences.** Maintainer-owned.

**Reversal trigger.** Maintainer-owned.

**Learning debt.** Maintainer-owned.

**Status.** Settled / Revisit-when / Open.
```

Use "Learning debt" when the project now depends on a concept, service, or
workflow that is not yet comfortably explainable by the maintainer.

## Decision Storage

Do not mix `docs/decisions.md` and separate ADR files for the same kind of
decision. If the project migrates to per-decision ADR files, first make an
explicit process decision that says:

- Where ADR files live.
- Whether `docs/decisions.md` becomes an index, is frozen, or is migrated.
- The exact ADR filename convention.
- The exact ADR template.
- Who fills which fields.

## Agent Roles

These are cognitive roles, not a fake autonomous software team. Use them to
structure prompts or subagent work. Only the implementer edits files, and only
after the plan or decision is accepted.

### Research Scout

Purpose: survey docs, prior art, constraints, and tradeoffs.

Rules:
- Does not edit code.
- Cites primary sources when current external behavior matters.
- Produces options, risks, and unknowns.

### Skeptic

Purpose: argue against the proposed design.

Rules:
- Does not edit code.
- Looks for hidden complexity, cloud cost, security holes, operational burden,
  and concepts the maintainer may not yet understand.
- Ends with concrete questions or acceptance criteria.

### Implementer

Purpose: make the smallest accepted code change.

Rules:
- Works from an accepted plan or decision.
- Avoids unrelated files and opportunistic refactors.
- Adds or updates tests for behavior changes.
- Reports validation commands and results.

### Reviewer

Purpose: review the diff against the plan, not just generic correctness.

Rules:
- Leads with bugs, regressions, missing tests, and decision drift.
- Flags implicit architectural choices.
- Checks that the implementation did not add unapproved technology.

### Teacher

Purpose: close the learning loop.

Rules:
- Explains the final diff in terms of request path, persistence path, error
  path, and test path.
- Lists learning debt.
- Produces 3-5 maintainer checkout questions.

## Deployment Application

For the Azure deployment work, use this sequence:

1. Decision inventory:
   - Backend host: Container Apps vs App Service.
   - Frontend lock-down: SWA password protection, SWA auth routes, Supabase auth
     only, or IP restrictions.
   - Error reporting: Application Insights, Sentry, or none for now.
   - Deployment ownership: Azure-generated workflows vs handwritten workflows.

2. Decision entries:
   - Prepare a backend hosting decision worksheet before committing Azure
     Container Apps.
   - Prepare an error reporting decision worksheet only if observability is
     added now.
   - The maintainer writes the final decision text before implementation.

3. Small implementation slices:
   - Task 13: configurable CORS and DB-backed `/health`.
   - Backend `Dockerfile`.
   - Frontend `staticwebapp.config.json`.
   - CI workflow.
   - Deployment workflow.
   - Deployment docs.

4. Learning checkout examples:
   - Explain how Container Apps decides a revision is healthy.
   - Explain why CORS is not an access-control mechanism.
   - Explain where Vite env vars are baked into the frontend bundle.
   - Explain how the backend validates Supabase JWTs.
   - Explain how GitHub Actions obtains permission to deploy to Azure.
