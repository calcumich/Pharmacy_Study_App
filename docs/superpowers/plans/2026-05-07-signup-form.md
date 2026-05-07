# Sign-up Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `LoginForm` from `App.tsx` into a new `AuthForm` component that supports both sign-in and sign-up, with a "check your email" confirmation screen after registration.

**Architecture:** A single new component `AuthForm.tsx` encapsulates all auth UI state (mode, emailSent, error). `App.tsx` is simplified to just render `<AuthForm />` in the unauthenticated gate. No new API calls — both sign-in and sign-up use the existing Supabase client.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, `@supabase/supabase-js`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/components/AuthForm.tsx` | Create | All auth UI: sign-in form, sign-up form, confirmation screen |
| `frontend/src/App.tsx` | Modify | Remove `LoginForm`, import and render `AuthForm` |

---

## Task 1: Create `AuthForm.tsx`

**Files:**
- Create: `frontend/src/components/AuthForm.tsx`

- [ ] **Step 1: Create the file with full implementation**

```tsx
import { useState } from 'react';
import { supabase } from '../lib/supabase';

type Mode = 'signin' | 'signup';

const INPUT_CLS =
  'w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500';

export function AuthForm() {
  const [mode, setMode] = useState<Mode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailSent, setEmailSent] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setPassword('');
    setConfirmPassword('');
    // email is intentionally kept so the user doesn't have to retype it
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    if (mode === 'signin') {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setError(error.message);
    } else {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) setError(error.message);
      else setEmailSent(true);
    }
    setLoading(false);
  }

  if (emailSent) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="w-full max-w-sm text-center space-y-6">
          <p className="text-4xl">📬</p>
          <div>
            <h1 className="text-xl font-bold">Check your email</h1>
            <p className="text-sm text-gray-400 mt-3 leading-relaxed">
              We sent a confirmation link to{' '}
              <span className="text-white font-medium">{email}</span>.
              <br />
              Click the link to activate your account, then come back to sign in.
            </p>
          </div>
          <button
            onClick={() => { setEmailSent(false); switchMode('signin'); }}
            className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            ← Back to sign in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <p className="text-4xl mb-3">💊</p>
          <h1 className="text-xl font-bold">Pharmacy Study App</h1>
          <p className="text-sm text-gray-500 mt-1">
            {mode === 'signin' ? 'Sign in to continue' : 'Create an account'}
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className={INPUT_CLS}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className={INPUT_CLS}
          />
          {mode === 'signup' && (
            <input
              type="password"
              placeholder="Confirm password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className={INPUT_CLS}
            />
          )}
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
          >
            {loading
              ? mode === 'signin' ? 'Signing in…' : 'Creating account…'
              : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <p className="text-center text-sm text-gray-500">
          {mode === 'signin' ? (
            <>
              No account?{' '}
              <button
                type="button"
                onClick={() => switchMode('signup')}
                className="text-blue-400 hover:text-blue-300 transition-colors"
              >
                Sign up →
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => switchMode('signin')}
                className="text-blue-400 hover:text-blue-300 transition-colors"
              >
                Sign in →
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the file exists**

```bash
ls frontend/src/components/AuthForm.tsx
```

Expected: file listed with no error.

---

## Task 2: Update `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`

`App.tsx` currently contains a `LoginForm` function (lines 68–120) and renders `<LoginForm />` at the auth gate (line 304). Both need to change.

- [ ] **Step 1: Remove the `LoginForm` function**

Delete the entire block from `// ── Login form ────` through the closing `}` of `LoginForm` (lines 66–120 inclusive). The file should jump straight from `StepIndicator`'s closing brace to `// ── Main App ──`.

- [ ] **Step 2: Add the `AuthForm` import**

Replace the existing import block at the top of the file. Find:

```ts
import { ClassBrowser } from './components/ClassBrowser';
```

Change to:

```ts
import { AuthForm } from './components/AuthForm';
import { ClassBrowser } from './components/ClassBrowser';
```

- [ ] **Step 3: Replace `<LoginForm />` with `<AuthForm />`**

Find:

```tsx
  if (!session && import.meta.env.VITE_USE_MOCK !== 'true') {
    return <LoginForm />;
  }
```

Change to:

```tsx
  if (!session && import.meta.env.VITE_USE_MOCK !== 'true') {
    return <AuthForm />;
  }
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AuthForm.tsx frontend/src/App.tsx
git commit -m "feat: add sign-up form; extract AuthForm from App"
```

---

## Task 3: Build check and manual verification

**Files:** none (verification only)

- [ ] **Step 1: Run TypeScript build**

```bash
cd frontend && npm run build
```

Expected: build completes with no type errors. Vite output ends with something like:

```
✓ built in Xs
```

If you see type errors, fix them before continuing.

- [ ] **Step 2: Start the dev server**

```bash
cd frontend && npm run dev
```

Open http://localhost:5173 in a browser.

- [ ] **Step 3: Verify sign-in still works**

With `VITE_USE_MOCK=false` (check `frontend/.env`):
- The login form appears on load
- Subtitle reads "Sign in to continue"
- Entering valid credentials and submitting signs you in and shows the main app
- The "Sign out" button in the header ends the session and returns to the login form

- [ ] **Step 4: Verify sign-up form appears**

- Click "Sign up →" below the sign-in form
- Subtitle changes to "Create an account"
- A third "Confirm password" field appears
- Clicking "Sign in →" at the bottom returns to sign-in mode

- [ ] **Step 5: Verify password mismatch error**

- In sign-up mode, enter any email, a password, and a *different* confirm password
- Click "Create account"
- Inline error "Passwords do not match." appears
- No Supabase call is made (no network request in browser DevTools)

- [ ] **Step 6: Verify mode switch clears passwords**

- In sign-up mode, type something in the password fields
- Click "Sign in →"
- Return to sign-up mode via "Sign up →"
- Password and Confirm password fields are empty; email is retained

- [ ] **Step 7: Verify mock mode is unaffected**

Set `VITE_USE_MOCK=true` in `frontend/.env`, restart the dev server, and confirm the app loads directly into the main UI (no auth gate).

Restore `VITE_USE_MOCK=false` when done.
