import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { initializeApp } from 'firebase/app';
import {
  createUserWithEmailAndPassword,
  getAuth,
  GoogleAuthProvider,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from 'firebase/auth';
import type { Auth, User } from 'firebase/auth';
import type { Account, FirebaseConfig } from './api';

let auth: Auth | null = null;

function firebase(config: FirebaseConfig): Auth {
  auth ??= getAuth(initializeApp(config));
  return auth;
}

// Firebase reports failures as codes; these are the ones a person can act on
const REASONS: Record<string, string> = {
  'auth/invalid-credential': 'That email and password do not match an account.',
  'auth/invalid-email': 'Enter a valid email address.',
  'auth/email-already-in-use': 'An account already uses this email. Sign in instead.',
  'auth/weak-password': 'Choose a stronger password.',
  'auth/password-does-not-meet-requirements': 'The password does not meet the requirements below.',
  'auth/too-many-requests': 'Too many attempts. Wait a minute and try again.',
  'auth/popup-closed-by-user': 'The Google window was closed before signing in.',
  'auth/popup-blocked': 'The browser blocked the Google window. Allow pop-ups for this site.',
  'auth/network-request-failed': 'Could not reach Google. Check the connection and try again.',
};

const REFUSED: Record<string, string> = {
  not_allowed: 'This account is not on the list of people who can use this workspace.',
  invalid_sign_in: 'The sign-in could not be checked. Try again.',
  email_codes_not_configured:
    'Sign-in codes cannot be emailed yet. Ask whoever runs this workspace.',
  code_not_sent: 'The code email could not be sent. Try again in a minute.',
  wrong_code: 'That code is not right. Check the latest email and try again.',
  code_expired: 'That code has expired or was used. Send a new one.',
  too_many_attempts: 'Too many wrong codes. Send a new one.',
  code_recently_sent: 'A code was sent less than a minute ago. Check your inbox and spam.',
  code_session_expired: 'The sign-in timed out. Start again.',
};

export const PASSWORD_RULES: {
  label: string;
  test: (password: string, email: string) => boolean;
}[] = [
  { label: 'At least 12 characters', test: (p) => p.length >= 12 },
  { label: 'An uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { label: 'A lowercase letter', test: (p) => /[a-z]/.test(p) },
  { label: 'A number', test: (p) => /[0-9]/.test(p) },
  { label: 'A symbol, such as ! ? # or %', test: (p) => /[^A-Za-z0-9\s]/.test(p) },
  {
    label: 'Does not contain your email name',
    test: (p, email) => {
      const name = email.split('@')[0].toLowerCase();
      return name.length < 3 || !p.toLowerCase().includes(name);
    },
  },
];

function reason(e: unknown): string {
  const code = (e as { code?: string })?.code;
  if (code && code in REASONS) return REASONS[code];
  return e instanceof Error ? e.message : 'Signing in failed. Try again.';
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  });
  const result = (await response.json().catch(() => ({}))) as T & { error?: string };
  if (!response.ok) {
    throw Object.assign(
      new Error(REFUSED[result.error ?? ''] ?? 'The server refused the request. Try again.'),
      { server: result.error },
    );
  }
  return result;
}

// trades Firebase's ID token for a wait on the emailed code; the session cookie comes after the code
async function session(user: User): Promise<Account> {
  try {
    return await post<Account>('/auth/session', { id_token: await user.getIdToken(true) });
  } catch (e) {
    if (auth) await signOut(auth).catch(() => undefined);
    throw e;
  }
}

export async function signOutEverywhere(): Promise<void> {
  await fetch('/auth/logout', { method: 'POST', cache: 'no-store' }).catch(() => undefined);
  if (auth) await signOut(auth).catch(() => undefined);
}

function Brand() {
  return (
    <p className="brand">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
        <rect
          x="1"
          y="1"
          width="20"
          height="20"
          rx="3"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
        />
        <path d="M6 16V6h10" fill="none" stroke="currentColor" strokeWidth="2.4" />
      </svg>
      PreFlight
    </p>
  );
}

function CodeStep({
  email,
  onSignedIn,
  onCancel,
}: {
  email: string;
  onSignedIn: (account: Account) => void;
  onCancel: () => void;
}) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [wait, setWait] = useState(60);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  async function verify(value: string) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      onSignedIn(await post<Account>('/auth/code', { code: value }));
    } catch (e) {
      const server = (e as { server?: string }).server;
      if (server === 'code_session_expired') return onCancel();
      setError(reason(e));
      setCode('');
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setBusy(true);
    setError('');
    try {
      await post('/auth/code/resend');
      setMessage(`A new code is on its way to ${email}.`);
      setWait(60);
    } catch (e) {
      if ((e as { server?: string }).server === 'code_session_expired') return onCancel();
      setError(reason(e));
    } finally {
      setBusy(false);
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (code.length === 6) void verify(code);
  };

  return (
    <>
      <h1 id="login-title">Check your email</h1>
      <p className="login-lede">
        We sent a 6-digit code to <strong>{email}</strong>. It expires in 10 minutes.
      </p>
      <form onSubmit={submit} className="login-form">
        <label>
          Code
          <input
            className="code-input"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            required
            autoFocus
            value={code}
            onChange={(e) => {
              const digits = e.target.value.replace(/\D/g, '').slice(0, 6);
              setCode(digits);
              if (digits.length === 6 && !busy) void verify(digits);
            }}
          />
        </label>
        <button className="primary" type="submit" disabled={busy || code.length !== 6}>
          Verify
        </button>
      </form>
      <p className="login-switch">
        <button className="link" type="button" disabled={busy || wait > 0} onClick={resend}>
          {wait > 0 ? `Resend code in ${wait}s` : 'Resend code'}
        </button>
        <button className="link" type="button" disabled={busy} onClick={onCancel}>
          Use a different account
        </button>
      </p>
      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
    </>
  );
}

export function Login({
  config,
  pending,
  onSignedIn,
}: {
  config: FirebaseConfig;
  pending: string | null;
  onSignedIn: (account: Account) => void;
}) {
  const [waiting, setWaiting] = useState<string | null>(pending);
  const [creating, setCreating] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [shown, setShown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const rules = PASSWORD_RULES.map((rule) => ({ ...rule, met: rule.test(password, email) }));
  const strong = rules.every((rule) => rule.met);
  const matches = password === confirm;

  async function attempt(work: () => Promise<void>) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await work();
    } catch (e) {
      setError(reason(e));
    } finally {
      setBusy(false);
    }
  }

  // every sign-in, new or returning, stops for the emailed code
  async function arrive(user: User) {
    const account = await session(user);
    if (account.signed_in) onSignedIn(account);
    else setWaiting(account.pending ?? user.email ?? '');
  }

  const google = () =>
    attempt(async () => {
      const { user } = await signInWithPopup(firebase(config), new GoogleAuthProvider());
      await arrive(user);
    });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (creating && (!strong || !matches)) {
      setError(
        !strong
          ? 'The password does not meet every requirement yet.'
          : 'The passwords do not match.',
      );
      return;
    }
    return attempt(async () => {
      const a = firebase(config);
      const { user } = creating
        ? await createUserWithEmailAndPassword(a, email, password)
        : await signInWithEmailAndPassword(a, email, password);
      await arrive(user);
    });
  };

  const reset = () =>
    attempt(async () => {
      if (!email) throw new Error('Enter your email first, then choose reset.');
      await sendPasswordResetEmail(firebase(config), email);
      setMessage(`If ${email} has an account, a reset link is on its way.`);
    });

  const switchMode = () => {
    setCreating(!creating);
    setError('');
    setMessage('');
    setConfirm('');
  };

  const cancel = async () => {
    await signOutEverywhere();
    setWaiting(null);
    setPassword('');
    setConfirm('');
  };

  return (
    <main className="login">
      <section className="login-card" aria-labelledby="login-title">
        <Brand />
        {waiting !== null ? (
          <CodeStep email={waiting} onSignedIn={onSignedIn} onCancel={cancel} />
        ) : (
          <>
            <h1 id="login-title">{creating ? 'Create an account' : 'Sign in'}</h1>
            <p className="login-lede">
              Screen a health or supplement ad against the GB claims register, the CAP Code and past
              ASA rulings.
            </p>
            <button className="outline google" type="button" disabled={busy} onClick={google}>
              Continue with Google
            </button>
            <p className="login-or">or with email</p>
            <form onSubmit={submit} className="login-form">
              <label>
                Email
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <div className="password-field">
                <label>
                  Password
                  <input
                    type={shown ? 'text' : 'password'}
                    autoComplete={creating ? 'new-password' : 'current-password'}
                    required
                    value={password}
                    aria-describedby={creating ? 'password-rules' : undefined}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                <button
                  className="link"
                  type="button"
                  aria-label={shown ? 'Hide password' : 'Show password'}
                  onClick={() => setShown(!shown)}
                >
                  {shown ? 'Hide' : 'Show'}
                </button>
              </div>
              {creating && (
                <>
                  <ul
                    id="password-rules"
                    className="password-rules"
                    aria-label="Password requirements"
                  >
                    {rules.map((rule) => (
                      <li key={rule.label} className={rule.met ? 'met' : undefined}>
                        <span aria-hidden="true">{rule.met ? '✓' : '○'}</span> {rule.label}
                        <span className="sr-only">{rule.met ? ' (done)' : ' (not yet)'}</span>
                      </li>
                    ))}
                  </ul>
                  <label>
                    Confirm password
                    <input
                      type={shown ? 'text' : 'password'}
                      autoComplete="new-password"
                      required
                      value={confirm}
                      aria-invalid={confirm.length > 0 && !matches}
                      onChange={(e) => setConfirm(e.target.value)}
                    />
                  </label>
                  {confirm.length > 0 && !matches && (
                    <p className="login-hint">The passwords do not match.</p>
                  )}
                </>
              )}
              <button
                className="primary"
                type="submit"
                disabled={busy || (creating && (!strong || !matches))}
              >
                {creating ? 'Create account' : 'Sign in'}
              </button>
            </form>
            <p className="login-switch">
              <button className="link" type="button" onClick={switchMode}>
                {creating ? 'I already have an account' : 'Create an account'}
              </button>
              {!creating && (
                <button className="link" type="button" disabled={busy} onClick={reset}>
                  Forgot password
                </button>
              )}
            </p>
            {error && (
              <p className="login-error" role="alert">
                {error}
              </p>
            )}
            {message && <p role="status">{message}</p>}
          </>
        )}
      </section>
    </main>
  );
}
