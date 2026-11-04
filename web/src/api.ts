import type { Screening } from './screening';

export interface Evidence {
  line_number?: number | null;
  kind: string;
  start: number;
  end: number;
  text: string;
  timing: string | null;
  timed: boolean;
  crop_url: string | null;
}
export type FlagView = Screening['flags'][number] & {
  source_details: { label: string; text: string; url: string | null }[];
};
export type Tier = 'high' | 'medium' | 'low' | 'unchecked';
export const TIER_LABEL: Record<Tier, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  unchecked: "Couldn't check",
};
export type TierCounts = Record<Tier, number>;
export interface ClaimView {
  claim_id: string;
  text: string;
  start: number | null;
  tier: Tier | null;
  substance: string | null;
  evidence: Evidence[];
  flags: FlagView[];
  rules: { primary: string[]; other: string[] } | null;
  folded: { claim_id: string; text: string; flags: FlagView[] }[];
}
export interface MaySay {
  substance: string;
  entries: { register_id: string; wording: string; conditions: string | null }[];
}
export interface Result {
  screening: Screening;
  claims: ClaimView[];
  may_say: MaySay[];
  incomplete_stages: string[];
  tiers: TierCounts;
  media_url?: string;
  title?: string;
  kind?: string;
}
export interface Job {
  job_id: string;
  kind: 'screening' | 'fix';
  status: string;
}
export interface Progress {
  status: string;
  stage?: string;
  stage_status?: string;
}

export function progressMessage(text: string): Progress {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== 'object') throw new Error('Invalid progress event');
  const data = value as Record<string, unknown>;
  if (
    typeof data.status !== 'string' ||
    !['queued', 'running', 'completed', 'incomplete', 'failed'].includes(data.status)
  )
    throw new Error('Invalid progress status');
  if (
    (data.stage !== undefined && typeof data.stage !== 'string') ||
    (data.stage_status !== undefined && typeof data.stage_status !== 'string')
  )
    throw new Error('Invalid progress stage');
  return {
    status: data.status,
    stage: data.stage as string | undefined,
    stage_status: data.stage_status as string | undefined,
  };
}
export interface Scene {
  still_url?: string;
  on_screen_text: string[];
  voiceover: string;
  duration_seconds: number;
}
export interface Decision {
  by: string;
  at: string;
  note: string;
}
export interface Fix {
  state: 'awaiting_approval' | 'needs_person';
  draft: { format: 'image' | 'video'; scenes: Scene[] };
  decision: Decision | null;
  screening: Screening;
}
export interface Round {
  round: number;
  screening: Screening;
  format: string;
  scenes: Scene[];
  media_url: string;
}
export interface Demo {
  id: string;
  title: string;
  kind: string;
  ruling_id: string | null;
}
export interface Reveal {
  kind: string;
  message?: string;
  ruling_id?: string;
  date?: string;
  outcome?: string;
  rules?: string[];
  url?: string;
}
export interface Scoreboard {
  available: boolean;
  reason?: string;
  run_id?: string;
  git_sha?: string;
  split?: string;
  created_at?: string;
  metrics: { name: string; hits: number; total: number; low: number | null; high: number | null }[];
}
export interface FirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
}
export interface Account {
  signed_in: boolean;
  email: string | null;
  login: boolean;
  // the email a sign-in code was sent to, while the workspace waits for it
  pending?: string | null;
}
export interface Config {
  auth: FirebaseConfig | null;
  notice: string;
  verification_label: string | null;
  retention_seconds: number;
  max_upload_bytes: number;
  max_seconds: number;
  public_mode: 'off' | 'on' | 'replay';
  upload_notice: string;
  uploads_closed: 'uploads_paused' | 'daily_cap_reached' | null;
  scoreboard: Scoreboard;
}

export const NOTICE =
  'PreFlight screens ads against the dated sources named in this report. It is not legal advice, and it does not decide whether an ad may run: a person makes that call.';

export const PUBLIC_ERRORS: Record<string, string> = {
  empty_script: 'The script needs at least one nonblank line of ad copy.',
  invalid_script_encoding: 'Save the script as UTF-8 text and try again.',
  invalid_script_content: 'The script contains binary or unsupported control characters.',
  script_too_large: 'The script is too large. Use at most 64 KiB of UTF-8 text.',
  script_too_many_lines: 'The script is too long. Use at most 1,000 lines.',
  script_fix_not_supported:
    'Edit the source script and screen it again. Media regeneration is not available for scripts.',
  rate_limited:
    'An hourly limit for uploads, screenings or revisions has been reached. Try again later.',
  daily_cap_reached: 'Uploads are closed for today. The labelled demos still run.',
  uploads_paused: 'Uploads are paused. The labelled demos still run.',
  media_too_long: 'The video is too long. Choose a shorter one.',
};

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: 'no-store' });
  if (!response.ok) await refuse(response);
  return response.json() as Promise<T>;
}

// turns a refused response into the message the page shows
async function refuse(response: Response): Promise<never> {
  const code = response.status;
  const error = await response
    .json()
    .then((body: { error?: string }) => body.error)
    .catch(() => undefined);
  if (error === 'login_required') {
    // the session ended; the page reloads to the sign-in screen
    location.reload();
    throw new Error('Your session has ended. Sign in again.');
  }
  if (error && error in PUBLIC_ERRORS) throw new Error(PUBLIC_ERRORS[error]);
  if (code === 404 || code === 410)
    throw new Error('This item is unavailable or its retention period has ended. Upload it again.');
  if (code === 413) throw new Error('The file is too large to upload.');
  if (code === 415) throw new Error('The file could not be decoded as a supported image or video.');
  if (code === 429) throw new Error('Every job slot is busy. Try again in a minute.');
  if (code === 409)
    throw new Error('This result cannot do that yet. Reload the page to get its current state.');
  throw new Error(`The server refused the request (HTTP ${code}). Check the file and try again.`);
}

export function post<T>(url: string, fields: unknown): Promise<T> {
  return request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  });
}

// Cloud Run refuses any request over 32 MiB, so larger files go in parts of this size
export const PART_BYTES = 16 * 1024 * 1024;
const PART_RETRIES = 3;

function mediaType(file: File): string {
  if (/\.md$/i.test(file.name)) return 'text/markdown';
  if (/\.txt$/i.test(file.name)) return 'text/plain';
  return file.type;
}

export async function upload(
  file: File,
  onProgress?: (fraction: number) => void,
  partBytes = PART_BYTES,
  pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms)),
): Promise<{ upload_id: string }> {
  if (file.size <= partBytes)
    return request('/uploads', {
      method: 'POST',
      headers: { 'Content-Type': mediaType(file) },
      body: file,
    });
  const started = await post<{ upload_id: string; part_bytes: number }>('/uploads/parts', {
    media_type: mediaType(file),
    bytes: file.size,
  });
  const size = Math.min(partBytes, started.part_bytes);
  const parts = `/uploads/${started.upload_id}/parts`;
  let offset = 0;
  let failures = 0;
  while (offset < file.size) {
    let response: Response | null = null;
    try {
      response = await fetch(`${parts}?offset=${offset}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: file.slice(offset, offset + size),
        cache: 'no-store',
      });
    } catch {
      // a dropped connection; the retry asks the server where to carry on
    }
    if (response?.ok) {
      offset = ((await response.json()) as { received: number }).received;
      failures = 0;
      onProgress?.(offset / file.size);
      continue;
    }
    if (response?.status === 409) {
      const body = (await response.json().catch(() => ({}))) as { received?: number };
      if (typeof body.received === 'number') {
        offset = body.received;
        continue;
      }
    }
    if (response && response.status < 500) await refuse(response);
    if (++failures > PART_RETRIES)
      throw new Error('The connection kept dropping while uploading. Try again.');
    await pause(1000 * failures);
    // after a failure the part may have arrived; a wrong offset reply says how much did
  }
  return request(`/uploads/${started.upload_id}/complete`, { method: 'POST' });
}

export function complete(screening: Screening): boolean {
  return (
    screening.stages.some((s) => s.stage === 'check' && s.status === 'done') &&
    !screening.stages.some((s) => s.status === 'failed')
  );
}

export function canApprove(fix: Fix | null): boolean {
  return (
    !!fix &&
    fix.state === 'awaiting_approval' &&
    !fix.decision &&
    complete(fix.screening) &&
    fix.screening.flags.length === 0
  );
}

export function timestamp(seconds: number): string {
  const rounded = Math.round(seconds * 10) / 10;
  return `${Math.floor(rounded / 60)}:${(rounded % 60).toFixed(1).padStart(4, '0')}`;
}

export const allFlags = (claim: ClaimView) => [
  ...claim.flags,
  ...claim.folded.flatMap((n) => n.flags),
];
