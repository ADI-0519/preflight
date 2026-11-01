import { useEffect, useState } from 'react';
import type { ClaimView, Round } from './api';
import { complete, timestamp } from './api';

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

export function ClaimTimeline({
  claims,
  duration,
  selected,
  currentTime,
  onSelect,
}: {
  claims: ClaimView[];
  duration: number;
  selected: string | null;
  currentTime: number;
  onSelect: (id: string, seconds: number) => void;
}) {
  if (!(duration > 0)) return null;
  const position = (seconds: number) => Math.max(0, Math.min(100, (100 * seconds) / duration));
  return (
    <div className="time-axis" aria-label="Evidence time axis">
      <div className="time-ruler" aria-hidden="true">
        {[0, 0.25, 0.5, 0.75, 1].map((n) => (
          <span key={n}>{timestamp(duration * n)}</span>
        ))}
      </div>
      <div className="time-lanes">
        {claims.map((c, i) => (
          <button
            key={c.claim_id}
            className="time-lane"
            aria-pressed={selected === c.claim_id}
            aria-label={`Seek to claim ${i + 1}: ${c.text}`}
            onClick={() => onSelect(c.claim_id, c.evidence[0]?.start ?? 0)}
          >
            <span className="lane-number" aria-hidden="true">
              {String(i + 1).padStart(2, '0')}
            </span>
            <span className="lane-track" aria-hidden="true">
              {c.evidence.map((e, j) => (
                <span
                  key={j}
                  className={`evidence-span ${c.flags.length ? 'flagged' : ''}`}
                  style={{
                    left: `${position(e.start)}%`,
                    width: e.end > e.start ? `${position(e.end) - position(e.start)}%` : '2px',
                  }}
                />
              ))}
              <span className="playhead" style={{ left: `${position(currentTime)}%` }} />
            </span>
          </button>
        ))}
      </div>
      <p className="timeline-key">
        One row per claim · amber indicates a flag · spans use recorded evidence timing
      </p>
    </div>
  );
}

export function RoundComparison({ rounds }: { rounds: Round[] }) {
  const [earlier, setEarlier] = useState<number | null>(null);
  const [later, setLater] = useState<number | null>(null);
  const first = rounds.find((r) => r.round === earlier) ?? rounds[0];
  const last = rounds.find((r) => r.round === later) ?? rounds[rounds.length - 1];
  if (!first || !last) return <p>Saved round previews are unavailable.</p>;
  const pair = first.round === last.round ? [first] : [first, last];
  return (
    <>
      <div className="comparison-selectors">
        <label>
          Left round
          <select value={first.round} onChange={(e) => setEarlier(Number(e.target.value))}>
            {rounds.map((r) => (
              <option key={r.round} value={r.round}>
                Round {r.round}
              </option>
            ))}
          </select>
        </label>
        <label>
          Right round
          <select value={last.round} onChange={(e) => setLater(Number(e.target.value))}>
            {rounds.map((r) => (
              <option key={r.round} value={r.round}>
                Round {r.round}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">
        Highlighted lines differ between the selected rounds. All saved rounds remain selectable.
      </p>
      <div className="rounds">
        {pair.map((r, side) => {
          const other = pair[1 - side];
          return (
            <article className="round" key={r.round}>
              <div className="panel-heading">
                <h3>Round {r.round}</h3>
                <span className="badge">
                  {complete(r.screening)
                    ? `${r.screening.flags.length} flag${r.screening.flags.length === 1 ? '' : 's'}`
                    : 'Incomplete'}
                </span>
              </div>
              <Preview
                src={r.media_url}
                video={r.format === 'video'}
                label={`Round ${r.round} rendered draft`}
              />
              <p className="round-headline">{r.screening.headline}</p>
              {r.scenes.map((s, i) => (
                <div key={i} className="round-scene">
                  <h4>Scene {i + 1}</h4>
                  {s.on_screen_text.map((t, j) => (
                    <p key={j}>
                      {other && other.scenes[i]?.on_screen_text[j] !== t ? <mark>{t}</mark> : t}
                    </p>
                  ))}
                  {s.voiceover && (
                    <p>
                      Voiceover:{' '}
                      {other && other.scenes[i]?.voiceover !== s.voiceover ? (
                        <mark>{s.voiceover}</mark>
                      ) : (
                        s.voiceover
                      )}
                    </p>
                  )}
                </div>
              ))}
            </article>
          );
        })}
      </div>
    </>
  );
}
