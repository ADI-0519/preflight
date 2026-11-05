import type { ClaimView, Evidence, FlagView, MaySay, Tier, TierCounts } from './api';
import { allFlags, TIER_LABEL, timestamp } from './api';
import { MAY_SAY, MaySayList, NO_SUGGESTION, Preview } from './workspace';

type Mark = 'none' | 'breach' | 'hold';

function markOf(claim: ClaimView): Mark {
  const flags = allFlags(claim);
  if (!flags.length) return 'none';
  return flags.some((f) => f.kind === 'possible_breach') ? 'breach' : 'hold';
}

function flagState(claim: ClaimView) {
  const mark = markOf(claim);
  if (mark === 'none') return 'no flag';
  const n = allFlags(claim).length;
  return `${n} flag${n === 1 ? '' : 's'}, ${mark === 'breach' ? 'possible breach' : 'on hold'}`;
}

export const TIER_CAPTION =
  'Tiers set the review order from the CAP rules cited: CAP 12 and 15.6 first, then other section 15 and section 3 rules. A line that only some checker runs flagged drops one tier. A tier sets the order of review and nothing more.';

export function TierChip({ tier }: { tier: Tier }) {
  return <span className={`tier ${tier}`}>{TIER_LABEL[tier]}</span>;
}

// the header counts flags, the tiers count lines; say why they differ
export const grouped = (lines: number, flags: number) =>
  `${lines} ${lines === 1 ? 'line holds' : 'lines hold'} the ${flags} flags; a flagged phrase inside a longer line is grouped under it.`;

// rule 1: an order for review, not a verdict
export function TierSummary({ tiers, flags }: { tiers: TierCounts; flags: number }) {
  const flagged = tiers.high + tiers.medium + tiers.low;
  if (flagged + tiers.unchecked === 0) return null;
  const order = `Review order: ${tiers.high} high · ${tiers.medium} medium · ${tiers.low} low`;
  const unchecked = `Couldn't check: ${tiers.unchecked}`;
  return (
    <div className="tier-summary">
      {flags !== flagged && flagged > 0 && <p>{grouped(flagged, flags)}</p>}
      <p>
        {flagged > 0 && order}
        {flagged > 0 && tiers.unchecked > 0 && ' · '}
        {tiers.unchecked > 0 && unchecked}
      </p>
      <p className="muted">{TIER_CAPTION}</p>
    </div>
  );
}

// a still has no time axis, and an untimed caption must not read as 0:00.0
function when(e: Evidence, still: boolean) {
  if (e.line_number) return `Script line ${e.line_number}`;
  if (still) return `${e.kind} (still)`;
  if (!e.timed) return `${e.kind}, time not read`;
  // only the passage is known: screenings from before word timing, or speech the aligner could not place
  if (e.timing === 'turn') return `${e.kind}, within ${timestamp(e.start)} to ${timestamp(e.end)}`;
  return e.end > e.start
    ? `${e.kind}, ${timestamp(e.start)} to ${timestamp(e.end)}`
    : `${e.kind}, at ${timestamp(e.start)}`;
}

const untimed = (still: boolean) => (still ? 'Still' : 'Time not read');

// a turn-timed spoken passage holds the claim somewhere inside it, so it never sets the claim's place
const exact = (e: Evidence) => e.timed && e.timing !== 'turn';

function placement(c: ClaimView) {
  const timed = c.evidence.filter((e) => e.timed);
  const precise = timed.filter(exact);
  const spans = precise.length ? precise : timed;
  return {
    spans,
    rough: !precise.length && timed.length > 0,
    start: spans.length ? Math.min(...spans.map((e) => e.start)) : c.start,
    end: spans.length ? Math.max(...spans.map((e) => e.end)) : c.start,
  };
}

const flagged = (c: ClaimView) => allFlags(c).length > 0 || c.tier === 'unchecked';

export function ClaimTrack({
  claims,
  duration,
  still,
  selected,
  currentTime,
  onSelect,
}: {
  claims: ClaimView[];
  duration: number;
  still: boolean;
  selected: string | null;
  currentTime: number;
  onSelect: (id: string, seconds: number | null) => void;
}) {
  const lanes = duration > 0;
  const position = (seconds: number) => Math.max(0, Math.min(100, (100 * seconds) / duration));
  const row = (c: ClaimView) => {
    const mark = markOf(c);
    const place = placement(c);
    const scriptLine = c.evidence.find((e) => e.line_number)?.line_number;
    const at = scriptLine
      ? `Line ${scriptLine}`
      : place.start === null
        ? untimed(still)
        : `${place.rough ? '≈' : ''}${timestamp(place.start)}`;
    const span =
      c.tier === 'unchecked'
        ? 'unchecked'
        : mark === 'none'
          ? 'none'
          : mark === 'hold'
            ? 'hold'
            : (c.tier ?? 'high');
    const where = place.rough
      ? `, said somewhere between ${timestamp(place.start!)} and ${timestamp(place.end!)}`
      : '';
    return (
      <button
        key={c.claim_id}
        className="claim-row"
        aria-pressed={selected === c.claim_id}
        aria-label={`${c.text}, ${at}${where}, ${flagState(c)}${c.tier ? `, ${TIER_LABEL[c.tier]}` : ''}`}
        onClick={() => onSelect(c.claim_id, place.start)}
      >
        {place.start === null ? <span className="untimed">{at}</span> : <time>{at}</time>}
        <span className="words">
          {c.tier && <TierChip tier={c.tier} />}
          {c.text}
        </span>
        {lanes && (
          <span className="lane" aria-hidden="true">
            {place.spans.map((e, i) => (
              <i
                key={i}
                className={`span ${span}${place.rough ? ' rough' : ''}`}
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
  };
  const open = claims.filter(flagged);
  const clean = claims.filter((c) => !flagged(c));
  const rough = lanes && claims.some((c) => placement(c).rough);
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
      {open.map(row)}
      {clean.length > 0 && (
        <details className="clean-claims" open={open.length === 0}>
          <summary>
            {clean.length} {clean.length === 1 ? 'claim' : 'claims'} with no flag
          </summary>
          {clean.map(row)}
        </details>
      )}
      {lanes && (
        <p className="key">
          <span>
            <i className="sw high" />
            High
          </span>
          <span>
            <i className="sw medium" />
            Medium
          </span>
          <span>
            <i className="sw low" />
            Low
          </span>
          <span>
            <i className="sw hold" />
            On hold
          </span>
          <span>
            <i className="sw none" />
            No flag
          </span>
          {rough && (
            <span>
              <i className="sw rough" />
              Said somewhere in this spoken passage; exact time not read
            </span>
          )}
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

function Rules({ claim }: { claim: ClaimView }) {
  if (!claim.rules || !(claim.rules.primary.length || claim.rules.other.length)) return null;
  const urls = new Map(
    allFlags(claim).flatMap((f) => f.source_details.map((s) => [s.label, s.url] as const)),
  );
  const links = (rules: string[]) =>
    rules.map((r, i) => {
      const url = urls.get(`CAP ${r}`);
      return (
        <span key={r}>
          {i > 0 && ', '}
          {url ? (
            <a href={url} target="_blank" rel="noreferrer">
              CAP {r}
            </a>
          ) : (
            `CAP ${r}`
          )}
        </span>
      );
    });
  return (
    <div className="rules">
      <p className="pair-label">CAP Code rules</p>
      <p>
        {links(claim.rules.primary)}
        {claim.rules.other.length > 0 && <>; also under {links(claim.rules.other)}</>}
      </p>
    </div>
  );
}

function SourceLabel({ source }: { source: FlagView['source_details'][number] }) {
  return source.url ? (
    <a href={source.url} target="_blank" rel="noreferrer">
      {source.label}
    </a>
  ) : (
    <strong>{source.label}</strong>
  );
}

// rule 3: a folded phrase still cites every source; ones its line already shows in full are named only
function FlagBlock({
  flag,
  paired,
  shown = new Set(),
}: {
  flag: FlagView;
  paired: string | undefined;
  shown?: Set<string>;
}) {
  const cited = flag.source_details.filter((s) => !(paired && s.text === paired));
  const sources = cited.filter((s) => !shown.has(s.label));
  const repeated = cited.filter((s) => shown.has(s.label));
  const own =
    flag.suggested_wording && flag.suggested_wording.wording !== paired
      ? flag.suggested_wording
      : null;
  return (
    <article className="flag">
      <span className={`kind ${flag.kind === 'on_hold' ? 'hold' : ''}`}>
        {flag.kind === 'on_hold' ? 'On hold' : 'Possible breach'}
      </span>
      <p className="reason">{flag.reason}</p>
      <h4>Source provenance</h4>
      {cited.length === 0 && <p className="none">The register source is quoted above.</p>}
      {repeated.length > 0 && (
        <p className="as-above">
          As above:{' '}
          {repeated.map((s, i) => (
            <span key={s.label}>
              {i > 0 && ', '}
              <SourceLabel source={s} />
            </span>
          ))}
        </p>
      )}
      {sources.map((s, i) => (
        <div className="source" key={i}>
          <SourceLabel source={s} />
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
}

const sameSubstance = (a: string, b: string) =>
  a.toLowerCase().split(/\s+/).join(' ') === b.toLowerCase().split(/\s+/).join(' ');

export function Inspector({
  claim,
  still,
  maySay,
}: {
  claim: ClaimView | undefined;
  still: boolean;
  maySay: MaySay[];
}) {
  const paired = claim && allFlags(claim).find((f) => f.suggested_wording)?.suggested_wording;
  const places = claim?.evidence.filter(
    (e, i, all) => all.findIndex((x) => x.kind === e.kind && x.start === e.start) === i,
  );
  const flagged = !!claim && allFlags(claim).length > 0;
  const lineSources = new Set(claim?.flags.flatMap((f) => f.source_details.map((s) => s.label)));
  const context = maySay.filter(
    (m) => claim?.substance && sameSubstance(m.substance, claim.substance),
  );
  return (
    <section className="sheet inspector" aria-label="Selected claim evidence">
      {!claim ? (
        <h3 className="said">Choose a claim</h3>
      ) : (
        <div className="inspector-body" key={claim.claim_id}>
          <div className="pair">
            <div className="pair-said">
              <p className="pair-label">Claim identified in the ad</p>
              {claim.tier && <TierChip tier={claim.tier} />}
              <h3 className="said">
                {flagged ? <span className="hl">“{claim.text}”</span> : <>“{claim.text}”</>}
              </h3>
              <p className="where">
                {places?.map((e, i) => (
                  <span key={i}>
                    {when(e, still)}
                    {e.text.trim() !== claim.text.trim() && <>: “{e.text}”</>}
                  </span>
                ))}
              </p>
              {claim.evidence.map(
                (e, i) =>
                  e.crop_url && (
                    <div className="crop" key={i}>
                      <Preview
                        src={e.crop_url}
                        label={`Cited region, ${when(e, still)}: ${e.text}`}
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
              flagged && (
                <div className="pair-register empty">
                  <p className="pair-label">Register wording</p>
                  <p className="none">{NO_SUGGESTION}</p>
                </div>
              )
            )}
          </div>
          <Rules claim={claim} />
          {claim.flags.map((f) => (
            <FlagBlock key={f.flag_id} flag={f} paired={paired?.wording} />
          ))}
          {claim.folded.length > 0 && (
            <section className="folded">
              <h4>Flagged phrases inside this line</h4>
              {claim.folded.map((n) => (
                <div className="phrase" key={n.claim_id}>
                  <p className="said-small">
                    <span className="hl">“{n.text}”</span>
                  </p>
                  {n.flags.map((f) => (
                    <FlagBlock
                      key={f.flag_id}
                      flag={f}
                      paired={paired?.wording}
                      shown={lineSources}
                    />
                  ))}
                </div>
              ))}
            </section>
          )}
          {!flagged &&
            (claim.tier === 'unchecked' ? (
              <p className="none">
                The checker did not reach this claim, so it has no flags. Treat it as unreviewed.
              </p>
            ) : (
              <p className="none">No flag for this claim. Meta or the ASA may still act on it.</p>
            ))}
          {flagged && context.length > 0 && (
            <details className="may-say-panel">
              <summary>What you may say</summary>
              <p className="muted">{MAY_SAY}</p>
              <MaySayList items={context} />
            </details>
          )}
        </div>
      )}
    </section>
  );
}
