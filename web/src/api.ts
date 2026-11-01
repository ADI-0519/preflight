import type { Screening } from './screening';

export interface Evidence {
  kind: string;
  start: number;
  end: number;
  text: string;
  timing: string | null;
  crop_url: string | null;
}
export interface ClaimView {
  claim_id: string;
  text: string;
  evidence: Evidence[];
  flags: (Screening['flags'][number] & {
    source_details: { label: string; text: string; url: string | null }[];
  })[];
}
export interface Result {
  screening: Screening;
  claims: ClaimView[];
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
export interface Config {
  notice: string;
  verification_label: string | null;
  retention_seconds: number;
  max_upload_bytes: number;
  scoreboard: Scoreboard;
}

export const NOTICE =
  'PreFlight screens ads against the dated sources named in this report. It is not legal advice, and it does not decide whether an ad may run: a person makes that call.';

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: 'no-store' });
  if (!response.ok) {
    const code = response.status;
    if (code === 404 || code === 410)
      throw new Error(
        'This item is unavailable or its retention period has ended. Upload it again.',
      );
    if (code === 413) throw new Error('The file or request is too large.');
    if (code === 415)
      throw new Error('The file could not be decoded as a supported image or video.');
    if (code === 429) throw new Error('All job slots are busy. Please try again shortly.');
    if (code === 409)
      throw new Error(
        'This result is not available for that action. Refresh its status before retrying.',
      );
    throw new Error(`Request failed (${code}). Please check the input and try again.`);
  }
  return response.json() as Promise<T>;
}

export function post<T>(url: string, fields: unknown): Promise<T> {
  return request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  });
}

export async function upload(file: File): Promise<{ upload_id: string }> {
  return request('/uploads', {
    method: 'POST',
    headers: { 'Content-Type': file.type },
    body: file,
  });
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
