import { describe, expect, it } from 'vitest';
import { canApprove, progressMessage, timestamp } from './api';
import type { Fix } from './api';

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
