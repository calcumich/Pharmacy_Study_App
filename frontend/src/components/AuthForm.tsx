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
