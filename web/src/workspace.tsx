import { useEffect, useRef, useState } from 'react';
import type { ClaimView, JobSummary, MaySay, Round } from './api';
import { allFlags, complete } from './api';
import type { Screening } from './screening';

export function ScriptPreview({
  lines,
  selected,
}: {
  lines: Screening['script_lines'];
  selected: number[];
}) {
  const root = useRef<HTMLElement>(null);
  const first = selected[0];
  useEffect(() => {
    if (first)
      root.current?.querySelector(`[data-line="${first}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [first]);
  return (
    <section className="script-source" aria-label="Script source" ref={root}>
      <h2>Source script</h2>
      <p>Script only. Screen the finished ad separately.</p>
      <ol aria-label="Script source lines">
        {lines.map((line) => (
          <li
            key={line.line_number}
            value={line.line_number}
            data-line={line.line_number}
            className={selected.includes(line.line_number) ? 'selected' : ''}
          >
            <code>{line.text}</code>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function Preview({
  src,
  label,
  video = false,
}: {
  src: string;
  label: string;
  video?: boolean;
}) {
  const [missing, setMissing] = useState(false);
  useEffect(() => setMissing(false), [src]);
  if (missing)
    return <p className="muted">Preview unavailable. The saved text and evidence remain below.</p>;
  return video ? (
    <video controls preload="none" src={src} aria-label={label} onError={() => setMissing(true)} />
  ) : (
    <img src={src} alt={label} onError={() => setMissing(true)} />
  );
}

export function FlagCount({ screening }: { screening: Screening }) {
  const n = screening.flags.length;
  const done = complete(screening);
  return (
    <span className={`count ${done && n ? 'flagged' : ''}`}>
      {done ? `${n} flag${n === 1 ? '' : 's'}` : 'Incomplete'}
    </span>
  );
}

const STAGES = [
  ['transcribe', 'Transcribe speech', 'Turns the voiceover into timed text.'],
  ['on_screen', 'Read on-screen text', 'Reads captions and supers from the frames.'],
  ['regions', 'Find image regions', 'Locates the product and other objects in the frame.'],
  ['claims', 'Extract claims', 'Lists the claims the ad makes, with their evidence.'],
  [
    'check',
    'Check the claims',
    'Compares each claim with the GB register, the CAP Code and ASA rulings.',
  ],
] as const;

const STATE_LABEL: Record<string, string> = {
  waiting: 'Waiting',
  running: 'Running…',
  done: 'Done',
  failed: 'Failed',
  skipped: 'Skipped',
};

function useElapsed(since: number | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since === null) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [since]);
  if (since === null) return null;
  const seconds = Math.max(0, Math.floor((now - since) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

// the server reports a stage only when it ends; the first three run together, then claims, then check
export function StageList({
  stages,
  since = null,
}: {
  stages: Record<string, string>;
  since?: number | null;
}) {
  const elapsed = useElapsed(since);
  const gathered = STAGES.slice(0, 3).every(([name]) => stages[name]);
  const state = (name: string) => {
    if (stages[name]) return stages[name];
    if (name === 'claims') return gathered ? 'running' : 'waiting';
    if (name === 'check') return stages.claims ? 'running' : 'waiting';
    return 'running';
  };
  const finished = STAGES.filter(([name]) => stages[name]).length;
  return (
    <>
      <div className="stages-head">
        <h2 id="stages-title">Screening stages</h2>
        <p className="muted">
          {finished} of {STAGES.length} finished{elapsed && ` · ${elapsed} elapsed`}
        </p>
      </div>
      <ol className="stages" aria-labelledby="stages-title">
        {STAGES.map(([name, label, detail]) => {
          const now = state(name);
          return (
            <li key={name} className={now}>
              <span>
                {label}
                <small>{detail}</small>
              </span>
              <span>{STATE_LABEL[now] ?? now}</span>
            </li>
          );
        })}
      </ol>
      <p className="muted">A screening usually takes a few minutes.</p>
    </>
  );
}

export function StillStage({ file }: { file: File | null }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    if (!file) {
      setUrl('');
      return;
    }
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  return (
    <div className="stage">
      {url ? <img src={url} alt="Chosen scene still" /> : <p>No scene still chosen yet.</p>}
    </div>
  );
}

export const MAY_SAY =
  'Authorised GB register entries for this substance. Check the conditions before using any wording. These entries may differ from the suggestion above.';

export const NO_SUGGESTION =
  'No replacement wording was suggested. Check the register and the ad before deciding what to change.';

type Entry = MaySay['entries'][number];

// a generic substance ("vitamin") matches dozens of entries, so a long list opens on request, grouped by nutrient
const LONG_LIST = 6;

// register wordings open with their nutrient: "Riboflavin contributes to ...", "Vitamin D helps ..."
function nutrient(wording: string) {
  const m = wording.match(
    /^(.+?)\s+(?:contributes?|helps?|is|are|has|have|plays?|supports?|maintains?)\b/i,
  );
  return m ? m[1] : 'Other';
}

function EntryList({ entries, conditions = true }: { entries: Entry[]; conditions?: boolean }) {
  return (
    <ul>
      {entries.map((e) => (
        <li key={e.register_id}>
          <p className="said-small">“{e.wording}”</p>
          <p className="id">GB register {e.register_id}</p>
          {conditions && e.conditions && <p className="conditions">Conditions: {e.conditions}</p>}
        </li>
      ))}
    </ul>
  );
}

function LongMaySay({ item }: { item: MaySay }) {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const shown = item.entries.filter((e) => !q || e.wording.toLowerCase().includes(q));
  const groups = new Map<string, Entry[]>();
  for (const e of shown)
    groups.set(nutrient(e.wording), [...(groups.get(nutrient(e.wording)) ?? []), e]);
  return (
    <details>
      <summary className="pair-label">
        {item.entries.length} authorised claims for {item.substance} in the GB register
      </summary>
      <input
        className="may-filter"
        type="search"
        aria-label={`Filter the authorised claims for ${item.substance}`}
        placeholder="Filter, e.g. vitamin D or immune"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {shown.length === 0 && <p className="none">No authorised claim matches.</p>}
      {[...groups].map(([name, entries]) => {
        const shared = entries.every((e) => e.conditions === entries[0].conditions)
          ? entries[0].conditions
          : null;
        return (
          <details className="may-group" key={name} open={!!q}>
            <summary>
              {name} <span className="muted">{entries.length}</span>
            </summary>
            {shared && <p className="conditions">Conditions for each: {shared}</p>}
            <EntryList entries={entries} conditions={!shared} />
          </details>
        );
      })}
    </details>
  );
}

// rule 2: the register's authorised entries, quoted exactly, apart from any line's suggested wording
export function MaySayList({ items }: { items: MaySay[] }) {
  return (
    <>
      {items.map((m) => (
        <div className="may-say" key={m.substance}>
          {m.entries.length === 0 ? (
            <>
              <p className="pair-label">Authorised for {m.substance}</p>
              <p className="none">No authorised register entries were found for this substance.</p>
            </>
          ) : m.entries.length > LONG_LIST ? (
            <LongMaySay item={m} />
          ) : (
            <>
              <p className="pair-label">Authorised for {m.substance}</p>
              <EntryList entries={m.entries} />
            </>
          )}
        </div>
      ))}
    </>
  );
}

export function FlaggedList({ claims, maySay }: { claims: ClaimView[]; maySay: MaySay[] }) {
  const flagged = claims.filter((c) => allFlags(c).length);
  return (
    <div className="refs">
      <h2>Flagged in this ad</h2>
      {flagged.length === 0 && <p className="none">No claim was flagged.</p>}
      {flagged.map((c) => {
        const wording = allFlags(c).find((f) => f.suggested_wording)?.suggested_wording;
        return (
          <div className="ref" key={c.claim_id}>
            <p className="said-small">
              <span className="hl">“{c.text}”</span>
            </p>
            {wording ? (
              <>
                <p className="pair-label">Register wording, exactly</p>
                <p className="said-small">“{wording.wording}”</p>
                <p className="id">GB register {wording.register_id}</p>
              </>
            ) : (
              <p className="none">{NO_SUGGESTION}</p>
            )}
          </div>
        );
      })}
      {maySay.length > 0 && (
        <>
          <h2>What you may say</h2>
          <p className="muted">
            Check the conditions attached to each entry before using its wording. These entries may
            differ from the suggestions for individual claims.
          </p>
          <MaySayList items={maySay} />
        </>
      )}
    </div>
  );
}

export function RoundComparison({ rounds }: { rounds: Round[] }) {
  const [earlier, setEarlier] = useState<number | null>(null);
  const [later, setLater] = useState<number | null>(null);
  const first = rounds.find((r) => r.round === earlier) ?? rounds[0];
  const last = rounds.find((r) => r.round === later) ?? rounds[rounds.length - 1];
  if (!first || !last) return <p>Saved round previews are unavailable.</p>;
  const sides = [
    { r: first, other: last, label: 'Left round', pick: setEarlier },
    { r: last, other: first, label: 'Right round', pick: setLater },
  ];
  return (
    <>
      <p className="muted">Underlined lines changed between the two rounds.</p>
      <div className="rounds">
        {sides.map(({ r, other, label, pick }) => (
          <article className="round" key={label}>
            <div className="round-head">
              <h3>Round {r.round}</h3>
              <FlagCount screening={r.screening} />
              <select
                aria-label={label}
                value={r.round}
                onChange={(e) => pick(Number(e.target.value))}
              >
                {rounds.map((o) => (
                  <option key={o.round} value={o.round}>
                    Round {o.round}
                  </option>
                ))}
              </select>
            </div>
            <div className="stage">
              <Preview
                src={r.media_url}
                video={r.format === 'video'}
                label={`Round ${r.round} rendered draft`}
              />
            </div>
            <p className="round-headline">{r.screening.headline}</p>
            {r.scenes.map((s, i) => (
              <div key={i} className="round-scene">
                {r.scenes.length > 1 && <h4>Scene {i + 1}</h4>}
                {s.on_screen_text.map((t, j) => (
                  <p key={j}>{other.scenes[i]?.on_screen_text[j] !== t ? <mark>{t}</mark> : t}</p>
                ))}
                {s.voiceover && (
                  <p>
                    <span className="label">Voiceover</span>{' '}
                    {other.scenes[i]?.voiceover !== s.voiceover ? (
                      <mark>{s.voiceover}</mark>
                    ) : (
                      s.voiceover
                    )}
                  </p>
                )}
              </div>
            ))}
          </article>
        ))}
      </div>
    </>
  );
}

// the newest few keep the list beside the upload panel; the rest open on request
const RECENT = 8;

const PAST_STATUS: Record<string, string> = {
  queued: 'Queued',
  running: 'Running',
  completed: 'Finished',
  incomplete: 'Incomplete',
  failed: 'Failed',
};

function pastKind(item: JobSummary) {
  if (item.kind === 'fix') return 'Revision';
  return { video: 'Video ad', image: 'Image ad', script: 'Script' }[item.media ?? 'video'];
}

export function PastList({
  items,
  onOpen,
  onRename,
  onRetry,
}: {
  items: JobSummary[];
  onOpen: (item: JobSummary) => void;
  onRename: (id: string, title: string) => Promise<void>;
  onRetry: (item: JobSummary) => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, RECENT);

  async function save(id: string) {
    const title = draft.trim();
    if (!title) return setError('Give the screening a name, or cancel.');
    try {
      await onRename(id, title);
      setEditing(null);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The name could not be saved. Try again.');
    }
  }

  return (
    <>
      <ul hidden={items.length === 0}>
        {shown.map((item) => {
          const kind = pastKind(item);
          const name = item.title ?? kind;
          const when = item.created_at
            ? new Date(item.created_at * 1000).toLocaleString(undefined, {
                dateStyle: 'medium',
                timeStyle: 'short',
              })
            : 'Start time not recorded';
          return (
            <li key={item.job_id} className="past-item">
              {editing === item.job_id ? (
                <form
                  className="past-edit"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void save(item.job_id);
                  }}
                >
                  <input
                    aria-label="Screening name"
                    maxLength={120}
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => e.key === 'Escape' && setEditing(null)}
                  />
                  <button className="link" type="submit">
                    Save
                  </button>
                  <button className="link muted" type="button" onClick={() => setEditing(null)}>
                    Cancel
                  </button>
                  {error && <p role="alert">{error}</p>}
                </form>
              ) : (
                <button className="past-row" onClick={() => onOpen(item)}>
                  <span className="past-name">
                    {name}
                    <small>
                      {item.title ? `${kind} · ` : ''}
                      {when}
                    </small>
                  </span>
                </button>
              )}
              <span className={`past-status ${item.status}`}>
                {PAST_STATUS[item.status] ?? item.status}
                {item.kind === 'screening' && ['failed', 'incomplete'].includes(item.status) && (
                  <button
                    className="link past-retry"
                    aria-label={`Retry ${name}`}
                    onClick={() => onRetry(item)}
                  >
                    Retry
                  </button>
                )}
              </span>
              <button
                className="past-rename"
                aria-label={`Rename ${name}`}
                title="Rename"
                hidden={editing === item.job_id}
                onClick={() => {
                  setEditing(item.job_id);
                  setDraft(item.title ?? '');
                  setError('');
                }}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    d="M11.5 2.5l2 2L6 12l-3 1 1-3z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.4"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </li>
          );
        })}
      </ul>
      {items.length > RECENT && (
        <button className="link past-more" onClick={() => setAll(!all)}>
          {all ? 'Show the most recent only' : `Show all ${items.length} screenings`}
        </button>
      )}
    </>
  );
}
