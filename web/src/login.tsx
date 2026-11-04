import { useState } from 'react';
import type { FormEvent } from 'react';
import { initializeApp } from 'firebase/app';
import {
  createUserWithEmailAndPassword,
  getAuth,
  GoogleAuthProvider,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from 'firebase/auth';
import type { Auth, User } from 'firebase/auth';
import { NOTICE } from './api';
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
  'auth/weak-password': 'Choose a password of at least 6 characters.',
  'auth/too-many-requests': 'Too many attempts. Wait a minute and try again.',
  'auth/popup-closed-by-user': 'The Google window was closed before signing in.',
  'auth/popup-blocked': 'The browser blocked the Google window. Allow pop-ups for this site.',
  'auth/network-request-failed': 'Could not reach Google. Check the connection and try again.',
};

const REFUSED: Record<string, string> = {
  not_allowed: 'This account is not on the list of people who can use this workspace.',
  email_not_verified:
    'Verify your email first: open the link we sent you, then sign in again. Check spam if it has not arrived.',
  invalid_sign_in: 'The sign-in could not be checked. Try again.',
};

function reason(e: unknown): string {
  const code = (e as { code?: string })?.code;
  if (code && code in REASONS) return REASONS[code];
  return e instanceof Error ? e.message : 'Signing in failed. Try again.';
}

// trades Firebase's ID token for the server's session cookie, which media and progress requests carry
async function session(user: User): Promise<Account> {
  const response = await fetch('/auth/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: await user.getIdToken(true) }),
    cache: 'no-store',
  });
  const body = (await response.json().catch(() => ({}))) as Account & { error?: string };
  if (!response.ok) {
    await signOut(signedInAuth());
    throw new Error(REFUSED[body.error ?? ''] ?? 'The server refused the sign-in. Try again.');
  }
  return body;
}

function signedInAuth(): Auth {
  if (!auth) throw new Error('Sign-in is not set up.');
  return auth;
}

export async function signOutEverywhere(): Promise<void> {
  await fetch('/auth/logout', { method: 'POST', cache: 'no-store' }).catch(() => undefined);
  if (auth) await signOut(auth).catch(() => undefined);
}

export function Login({
  config,
  onSignedIn,
}: {
  config: FirebaseConfig;
  onSignedIn: (account: Account) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

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

  const google = () =>
    attempt(async () => {
      const { user } = await signInWithPopup(firebase(config), new GoogleAuthProvider());
      onSignedIn(await session(user));
    });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    return attempt(async () => {
      const a = firebase(config);
      if (creating) {
        const { user } = await createUserWithEmailAndPassword(a, email, password);
        await sendEmailVerification(user);
        setMessage(`We sent a verification link to ${email}. Open it, then sign in.`);
        try {
          onSignedIn(await session(user));
        } catch {
          // a workspace with an allowlist waits for the verified email; the message above says what to do
          setCreating(false);
        }
        return;
      }
      const { user } = await signInWithEmailAndPassword(a, email, password);
      onSignedIn(await session(user));
    });
  };

  const reset = () =>
    attempt(async () => {
      if (!email) throw new Error('Enter your email first, then choose reset.');
      await sendPasswordResetEmail(firebase(config), email);
      setMessage(`If ${email} has an account, a reset link is on its way.`);
    });

  return (
    <main className="login">
      <section className="login-card" aria-labelledby="login-title">
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
        <h1 id="login-title">{creating ? 'Create an account' : 'Sign in'}</h1>
        <p className="login-lede">
          Screen a health or supplement ad against the GB claims register, the CAP Code and past ASA
          rulings.
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
          <label>
            Password
            <input
              type="password"
              autoComplete={creating ? 'new-password' : 'current-password'}
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="primary" type="submit" disabled={busy}>
            {creating ? 'Create account' : 'Sign in'}
          </button>
        </form>
        <p className="login-switch">
          <button className="link" type="button" onClick={() => setCreating(!creating)}>
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
        <p className="login-notice">{NOTICE}</p>
      </section>
    </main>
  );
}
