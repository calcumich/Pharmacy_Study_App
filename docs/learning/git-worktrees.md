# Git Worktrees

A short field guide, written after using one for the ingestion pipeline branch.

## The one-sentence definition

A worktree is **a second working directory that shares the same `.git` database** as the main repo. Different folder on disk, same history.

## Mental model

Most people start with this assumption:

> A git repo is one folder. The `.git/` directory inside it is the brain;
> the rest is the current snapshot of whatever branch is checked out.

That's true — but git lets you have *multiple* working-directory snapshots pointing at the same brain. Each one is a worktree. The original folder is itself a worktree — just the "main" one, the one with `.git/` actually inside it. Additional worktrees are folders elsewhere with a tiny `.git` file (not directory) that points back at the main `.git/`.

```
PharmacyStudyApp/                    ← main worktree, has real .git/
  .git/                              (the shared brain)
  app/
  docs/
  .claude/worktrees/
    ingestion-pipeline/              ← secondary worktree
      .git                           (a file, not a dir — points at ../../.git)
      app/                           (different files — different branch checked out)
      docs/
```

Both folders are valid checkouts. Commits in either show up immediately in the other's `git log`, because there's only one history.

## The one rule that matters

**A branch can only be checked out by one worktree at a time.**

This is why `git checkout main` in a worktree fails if `main` is already checked out in the main folder. Git refuses to give you two writable copies of the same branch — they'd diverge silently and you'd corrupt history. Each worktree is locked to its own branch.

Corollary: every worktree is on its *own* branch. There's no concept of a "worktree-only" branch — they're just normal branches that happen to be checked out in a non-default folder.

## Why use one

Mainly: **work on two branches simultaneously without `git stash` or losing your in-progress diff**.

Concrete example from this project:
- You were mid-flight on `seedData` with uncommitted changes.
- I needed to start a new feature (`ingestion-pipeline`) off `main`.
- Without worktrees, I'd have to: stash → switch → work → switch back → unstash. Risk of forgetting, conflicts, or interrupting your flow.
- With a worktree: I got my own folder on my own branch. You kept working in yours. Two `git status` outputs, two independent dev servers possible, zero interference.

Other good fits:
- Running tests on one branch while editing another.
- Reviewing a PR (checking it out) without disturbing your feature work.
- Long-running CI-like operations (large builds, type-checks) on a branch you don't want to interrupt.

## The commands you actually use

```bash
# Create a new worktree on a new branch off main:
git worktree add ../feature-x -b feature-x main

# Create a worktree tracking an existing remote branch:
git worktree add ../review-pr-42 origin/pr-42

# List all worktrees and what branch each is on:
git worktree list

# Remove a worktree (the directory; the branch stays in git):
git worktree remove ../feature-x

# If git complains the worktree is dirty/in-use and you really mean it:
git worktree remove --force ../feature-x

# Tidy stale entries (e.g., after you manually rm'd a worktree folder):
git worktree prune
```

## What surprised me

A few things that aren't obvious:

1. **Worktree folders are not gitignored anywhere.** You typically put them outside the main repo path (e.g., `../feature-x`) or inside a gitignored subdir (this project uses `.claude/worktrees/`, which is gitignored).
2. **Branches created by a worktree aren't special.** The branch this session is on, `worktree-ingestion-pipeline`, is just a regular branch. I can rename it with `git branch -m`, push it, merge it, anything. The "worktree-" prefix is just a default name from the tool I used — it's not a marker.
3. **Removing a worktree does NOT delete the branch.** The folder is gone, but the branch lives on in `git branch --list`. To also delete the branch: `git branch -d <name>` afterward.
4. **`git fetch` once, all worktrees see it.** Because they share `.git/`, you don't need to fetch in each worktree separately. Same for `git config` settings.
5. **Hooks live in the shared `.git/hooks/`.** So a pre-commit hook installed once applies to commits made from any worktree.

## Common stumbling blocks

- **"fatal: 'main' is already checked out at ..."** — exactly the one-branch-one-worktree rule. Either switch to a different branch in this worktree, or remove the other worktree.
- **`pip install -e .` works in one worktree but not the other** — each worktree has the same code, but your *Python environment* is global (unless you use a venv per worktree). Re-running `pip install -e .` from one worktree updates the install for whichever env was active. If you're using `uv` with `uv sync`, the lockfile is shared, but the `.venv/` it creates lives in the worktree.
- **".env not found"** — `.env` is gitignored, so it doesn't auto-copy into a new worktree. Either copy it manually, point env-loading at the main repo's `.env`, or have your settings tolerate missing config gracefully (the lesson from `ingestion-vs-app-config.md`).

## When NOT to use a worktree

- Quick one-off "let me check what `main` looks like" — a stash + checkout is faster.
- You're solo and not mid-task — just switch branches normally.
- You're on a network filesystem where two checkouts will fight over OS-level file locks.

## Further reading

- `git help worktree` — the official manual
- [git-scm Pro Git book, ch. "Git Tools - Worktrees"](https://git-scm.com/docs/git-worktree)
