import { describe, expect, it, vi } from 'vitest';
import { canApprove, progressMessage, request, timestamp, upload } from './api';
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
    await expect(request('/screenings')).rejects.toThrow(
      'An hourly limit for uploads, screenings or revisions has been reached.',
    );
    vi.stubGlobal('fetch', refused(429, 'job_queue_full'));
    await expect(request('/screenings')).rejects.toThrow('Every job slot is busy');
    vi.stubGlobal('fetch', refused(503, 'daily_cap_reached'));
    await expect(request('/uploads')).rejects.toThrow('closed for today');
    vi.unstubAllGlobals();
  });
});

describe('uploading in parts', () => {
  it('sends a large file in order, resumes after a drop and a retried part, then completes', async () => {
    const file = new File(['0123456789'], 'ad.mp4', { type: 'video/mp4' });
    const sent: string[] = [];
    let received = 0;
    let dropped = false;
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      });
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/uploads/parts') {
        expect(JSON.parse(String(init?.body))).toEqual({ media_type: 'video/mp4', bytes: 10 });
        return json({ upload_id: 'a'.repeat(32), part_bytes: 4 }, 201);
      }
      if (url.endsWith('/complete')) return json({ upload_id: 'a'.repeat(32) }, 201);
      const offset = Number(new URL(url, 'http://x').searchParams.get('offset'));
      const part = await (init?.body as Blob).text();
      sent.push(`${offset}:${part}`);
      if (offset !== received) return json({ error: 'wrong_offset', received }, 409);
      received += part.length;
      // the second part arrives but its reply is lost, so the browser sends it again
      if (offset === 4 && !dropped) {
        dropped = true;
        throw new TypeError('network');
      }
      return json({ received });
    });
    vi.stubGlobal('fetch', fetcher);
    const progress: number[] = [];
    const saved = await upload(
      file,
      (f) => progress.push(f),
      4,
      async () => undefined,
    );
    vi.unstubAllGlobals();
    expect(saved.upload_id).toBe('a'.repeat(32));
    expect(sent).toEqual(['0:0123', '4:4567', '4:4567', '8:89']);
    expect(progress).toEqual([0.4, 1]);
  });

  it('keeps a small file to one request', async () => {
    const fetcher = vi.fn(async (_url: string) => new Response(JSON.stringify({ upload_id: 'b' })));
    vi.stubGlobal('fetch', fetcher);
    await upload(new File(['VO: hello'], 'script.txt'), undefined, 4096);
    vi.unstubAllGlobals();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe('/uploads');
  });
});
