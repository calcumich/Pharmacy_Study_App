# Sign-up Form — Design Spec

**Date:** 2026-05-07
**Status:** Approved

## Problem

`LoginForm` in `App.tsx` only handles sign-in. New users have no way to register.

## Decision

Extract `LoginForm` from `App.tsx` into a new `AuthForm` component that handles both sign-in and sign-up modes. The sign-in view gains a "No account? Sign up →" link that swaps in the sign-up form.

## Component: `AuthForm`

**File:** `frontend/src/components/AuthForm.tsx`

### Internal state

| Field | Type | Purpose |
|---|---|---|
| `mode` | `'signin' \| 'signup'` | Which form is shown |
| `email` | `string` | Controlled input |
| `password` | `string` | Controlled input |
| `confirmPassword` | `string` | Sign-up only |
| `loading` | `boolean` | Disables submit during request |
| `error` | `string \| null` | Inline error message |
| `emailSent` | `boolean` | Triggers confirmation screen |

### Sign-in path

Calls `supabase.auth.signInWithPassword({ email, password })`. Behavior identical to current `LoginForm`. On error, sets `error` to `error.message`.

### Sign-up path

1. Validates `password === confirmPassword` client-side; sets `error` and aborts if not.
2. Calls `supabase.auth.signUp({ email, password })`.
3. On success: sets `emailSent = true`.
4. On error: sets `error` to `error.message`.

### "Check your email" screen

Rendered when `emailSent === true`. Replaces the form entirely. Shows:
- 📬 icon
- "Check your email" heading
- The submitted email address
- Instruction to click the confirmation link, then return to sign in
- "← Back to sign in" link — resets `mode` to `'signin'` and clears `emailSent`

### Mode switching

- Sign-in form footer: "No account? Sign up →"
- Sign-up form footer: "Already have an account? Sign in →"
- Switching modes clears `error`, resets `password` and `confirmPassword` to `''`, and retains `email` so the user doesn't have to retype it.

### Error handling

All errors (Supabase errors + mismatched passwords) surface through the same inline `error` state, displayed as red text above the submit button.

## Changes to `App.tsx`

- Delete the `LoginForm` function.
- Add `import { AuthForm } from './components/AuthForm'`.
- Replace `<LoginForm />` with `<AuthForm />` in the auth gate render path.

## Files touched

| File | Change |
|---|---|
| `frontend/src/components/AuthForm.tsx` | New file |
| `frontend/src/App.tsx` | Remove `LoginForm`, import and render `AuthForm` |

## Out of scope

- Password reset / "forgot password" flow
- OAuth / social login
- Email resend button on confirmation screen
