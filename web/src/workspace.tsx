import { useEffect, useRef, useState } from 'react';
import type { ClaimView, MaySay, Round } from './api';
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

export function StageList({ stages }: { stages: Record<string, string> }) {
  const entries = Object.entries(stages);
  return (
    <>
      <h2 id="stages-title">Screening stages</h2>
      {entries.length === 0 ? (
        <p className="muted">No stage has reported yet.</p>
      ) : (
        <ol className="stages" aria-labelledby="stages-title">
          {entries.map(([name, state]) => {
            const label = name.replaceAll('_', ' ');
            return (
              <li key={name} className={state}>
                <span>{label[0].toUpperCase() + label.slice(1)}</span>
                <span>{state}</span>
              </li>
            );
          })}
        </ol>
      )}
      <p className="muted">Stages update as the server finishes them.</p>
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
  'Authorised GB register wording for this substance, with its conditions of use. It is context for the person deciding, separate from the wording suggested above.';

// rule 2: the register's authorised entries, quoted exactly, apart from any line's suggested wording
export function MaySayList({ items }: { items: MaySay[] }) {
  return (
    <>
      {items.map((m) => (
        <div className="may-say" key={m.substance}>
          <p className="pair-label">Authorised for {m.substance}</p>
          {m.entries.length === 0 ? (
            <p className="none">No authorised register entry matches.</p>
          ) : (
            <ul>
              {m.entries.map((e) => (
                <li key={e.register_id}>
                  <p className="said-small">“{e.wording}”</p>
                  <p className="id">GB register {e.register_id}</p>
                  {e.conditions && <p className="conditions">Conditions: {e.conditions}</p>}
                </li>
              ))}
            </ul>
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
              <p className="none">
                No register wording matches this claim. A person must decide what to change.
              </p>
            )}
          </div>
        );
      })}
      {maySay.length > 0 && (
        <>
          <h2>What you may say</h2>
          <p className="muted">
            Authorised GB register wording for the substances flagged above, with conditions of use.
            It is context for the person deciding, separate from the wording suggested for a line.
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
