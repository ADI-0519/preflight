import type { ClaimView, Evidence } from './api';
import { timestamp } from './api';
import { Preview } from './workspace';

type Mark = 'none' | 'breach' | 'hold';

const markOf = (claim: ClaimView): Mark =>
  !claim.flags.length
    ? 'none'
    : claim.flags.some((f) => f.kind === 'possible_breach')
      ? 'breach'
      : 'hold';

function flagState(claim: ClaimView) {
  const mark = markOf(claim);
  if (mark === 'none') return 'no flag';
  const count = `${claim.flags.length} flag${claim.flags.length === 1 ? '' : 's'}`;
  return `${count}, ${mark === 'breach' ? 'possible breach' : 'on hold'}`;
}

const range = (e: Evidence) =>
  e.end > e.start ? `${timestamp(e.start)} to ${timestamp(e.end)}` : `at ${timestamp(e.start)}`;

export function ClaimTrack({
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
  const lanes = duration > 0;
  const position = (seconds: number) => Math.max(0, Math.min(100, (100 * seconds) / duration));
  return (
    <div className={`track ${lanes ? '' : 'no-lanes'}`}>
      {lanes && (
        <div className="ruler" aria-hidden="true">
          <span />
          <div>
            {[0, 0.25, 0.5, 0.75, 1].map((n) => (
              <span key={n}>{timestamp(duration * n)}</span>
            ))}
          </div>
        </div>
      )}
      {claims.map((c) => {
        const start = c.evidence[0]?.start ?? 0;
        const mark = markOf(c);
        return (
          <button
            key={c.claim_id}
            className="claim-row"
            aria-pressed={selected === c.claim_id}
            aria-label={`${c.text}, ${timestamp(start)}, ${flagState(c)}`}
            onClick={() => onSelect(c.claim_id, start)}
          >
            <time>{timestamp(start)}</time>
            <span className="words">{c.text}</span>
            {lanes && (
              <span className="lane" aria-hidden="true">
                {c.evidence.map((e, i) => (
                  <i
                    key={i}
                    className={`span ${mark}`}
                    style={{
                      left: `${position(e.start)}%`,
                      width: e.end > e.start ? `${position(e.end) - position(e.start)}%` : '0.6%',
                    }}
                  />
                ))}
                <i className="head" style={{ left: `${position(currentTime)}%` }} />
              </span>
            )}
            <span className={`mark ${mark}`} aria-hidden="true" />
          </button>
        );
      })}
      {lanes && (
        <p className="key">
          <span>
            <i className="sw breach" />
            Possible breach
          </span>
          <span>
            <i className="sw hold" />
            On hold
          </span>
          <span>
            <i className="sw none" />
            No flag
          </span>
        </p>
      )}
    </div>
  );
}

function RegisterQuote({ wording, id }: { wording: string; id: string }) {
  return (
    <>
      <p className="pair-label">Register wording, exactly</p>
      <p className="said">“{wording}”</p>
      <p className="id">GB register {id}</p>
    </>
  );
}

export function Inspector({ claim }: { claim: ClaimView | undefined }) {
  const paired = claim?.flags.find((f) => f.suggested_wording)?.suggested_wording;
  const places = claim?.evidence.filter(
    (e, i, all) => all.findIndex((x) => x.kind === e.kind && x.start === e.start) === i,
  );
  return (
    <section className="sheet inspector" aria-label="Selected claim evidence">
      {!claim ? (
        <h3 className="said">Choose a claim</h3>
      ) : (
        <div className="inspector-body" key={claim.claim_id}>
          <div className="pair">
            <div className="pair-said">
              <p className="pair-label">The ad says</p>
              <h3 className="said">
                {claim.flags.length ? (
                  <span className="hl">“{claim.text}”</span>
                ) : (
                  <>“{claim.text}”</>
                )}
              </h3>
              <p className="where">
                {places?.map((e, i) => (
                  <span key={i}>
                    {e.kind}, {range(e)}
                    {e.text.trim() !== claim.text.trim() && <>: “{e.text}”</>}
                  </span>
                ))}
                {claim.evidence.some((e) => e.timing === 'turn') && (
                  <span>Timed to the whole spoken passage.</span>
                )}
              </p>
              {claim.evidence.map(
                (e, i) =>
                  e.crop_url && (
                    <div className="crop" key={i}>
                      <Preview
                        src={e.crop_url}
                        label={`Cited region at ${timestamp(e.start)}: ${e.text}`}
                      />
                    </div>
                  ),
              )}
            </div>
            {paired ? (
              <div className="pair-register">
                <RegisterQuote wording={paired.wording} id={paired.register_id} />
              </div>
            ) : (
              claim.flags.length > 0 && (
                <div className="pair-register empty">
                  <p className="pair-label">Register wording</p>
                  <p className="none">
                    No register wording matches this claim. A person must decide what to change.
                  </p>
                </div>
              )
            )}
          </div>
          {claim.flags.map((f) => {
            const sources = f.source_details.filter((s) => !(paired && s.text === paired.wording));
            const own =
              f.suggested_wording && f.suggested_wording.wording !== paired?.wording
                ? f.suggested_wording
                : null;
            return (
              <article className="flag" key={f.flag_id}>
                <span className={`kind ${f.kind === 'on_hold' ? 'hold' : ''}`}>
                  {f.kind === 'on_hold' ? 'On hold' : 'Possible breach'}
                </span>
                <p className="reason">{f.reason}</p>
                <h4>Source provenance</h4>
                {sources.length === 0 && (
                  <p className="none">The register source is quoted above.</p>
                )}
                {sources.map((s, i) => (
                  <div className="source" key={i}>
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noreferrer">
                        {s.label}
                      </a>
                    ) : (
                      <strong>{s.label}</strong>
                    )}
                    <p>{s.text}</p>
                  </div>
                ))}
                {own && (
                  <div className="pair-register own">
                    <RegisterQuote wording={own.wording} id={own.register_id} />
                  </div>
                )}
              </article>
            );
          })}
          {claim.flags.length === 0 && (
            <p className="none">No flag for this claim. Meta or the ASA may still act on it.</p>
          )}
        </div>
      )}
    </section>
  );
}
