import { describe, expect, it, vi } from 'vitest';
import { canApprove, progressMessage, request, timestamp } from './api';
import type { Fix } from './api';
import { grouped } from './evidence';

// Minimal contract fixture for the review guard, with no model responses or evaluation labels.
const fixed = {
  state: 'awaiting_approval',
  decision: null,
  screening: { stages: [{ stage: 'check', status: 'done' }], flags: [] },
} as unknown as Fix;

describe('human review guard', () => {
  it('requires a completed, unflagged fix awaiting a person', () => {
    expect(canApprove(fixed)).toBe(true);
    expect(canApprove({ ...fixed, state: 'needs_person' })).toBe(false);
    expect(canApprove({ ...fixed, decision: { by: 'Synthetic reviewer', at: '', note: '' } })).toBe(
      false,
    );
    expect(
      canApprove({ ...fixed, screening: { ...fixed.screening, stages: [] } } as unknown as Fix),
    ).toBe(false);
    expect(
      canApprove({
        ...fixed,
        screening: {
          ...fixed.screening,
          stages: [{ ...fixed.screening.stages[0], status: 'skipped' }],
        },
      }),
    ).toBe(false);
    expect(
      canApprove({
        ...fixed,
        screening: { ...fixed.screening, flags: [{}] as Fix['screening']['flags'] },
      }),
    ).toBe(false);
    expect(canApprove(null)).toBe(false);
  });
});

it('keeps sub-second evidence times visible', () => {
  expect(timestamp(63.25)).toBe('1:03.3');
  expect(timestamp(59.999)).toBe('1:00.0');
});

it.each(['null', '42', '{"status":"unknown"}', '{"status":"running","stage":42}'])(
  'rejects malformed progress data: %s',
  (value) => {
    expect(() => progressMessage(value)).toThrow();
  },
);

describe('tier summary', () => {
  it('says why the line count differs from the flag count', () => {
    expect(grouped(13, 30)).toBe(
      '13 lines hold the 30 flags; a flagged phrase inside a longer line is grouped under it.',
    );
    expect(grouped(1, 2)).toMatch(/^1 line holds the 2 flags/);
  });
});

describe('refused requests', () => {
  it('names the public limit instead of a busy queue', async () => {
    const refused = (status: number, error: string) =>
      vi.fn(async () => new Response(JSON.stringify({ error }), { status }));
    vi.stubGlobal('fetch', refused(429, 'rate_limited'));
    await expect(request('/screenings')).rejects.toThrow('a few screenings and fixes an hour');
    vi.stubGlobal('fetch', refused(429, 'job_queue_full'));
    await expect(request('/screenings')).rejects.toThrow('Every job slot is busy');
    vi.stubGlobal('fetch', refused(503, 'daily_cap_reached'));
    await expect(request('/uploads')).rejects.toThrow('closed for today');
    vi.unstubAllGlobals();
  });
});
