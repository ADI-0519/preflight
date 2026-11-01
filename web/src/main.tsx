import { StrictMode, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  canApprove,
  complete,
  NOTICE,
  post,
  progressMessage,
  request,
  timestamp,
  upload,
} from './api';
import type { Config, Demo, Fix, Job, Result, Reveal, Round, Scoreboard } from './api';
import './style.css';
import { ClaimTimeline, Preview, RoundComparison } from './workspace';

function Metrics({ board }: { board: Scoreboard }) {
  return (
    <section className="panel scoreboard" aria-labelledby="score-title">
      <h2 id="score-title">Registered test scoreboard</h2>
      {!board.available ? (
        <p>{board.reason} Development runs and synthetic replays are not final test results.</p>
      ) : (
        <>
          <p>
            Run <code>{board.run_id}</code> · split {board.split} · revision{' '}
            <code>{board.git_sha}</code>
          </p>
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Count</th>
                <th>Rate</th>
                <th>95% interval</th>
              </tr>
            </thead>
            <tbody>
              {board.metrics.map((m) => (
                <tr key={m.name}>
                  <td>{m.name.replaceAll('_', ' ')}</td>
                  <td>
                    {m.hits} / {m.total}
                  </td>
                  <td>
                    {m.total > 0 ? `${((100 * m.hits) / m.total).toFixed(1)}%` : 'Not measured'}
                  </td>
                  <td>
                    {m.low !== null && m.high !== null
                      ? `${(m.low * 100).toFixed(1)}–${(m.high * 100).toFixed(1)}%`
                      : 'Not registered'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [mode, setMode] = useState<'screen' | 'demo'>('screen');
  const [demos, setDemos] = useState<Demo[]>([]);
  const [demo, setDemo] = useState<Demo | null>(null);
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [resultOwner, setResultOwner] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [media, setMedia] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('Choose an ad to begin.');
  const [stages, setStages] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [fix, setFix] = useState<Fix | null>(null);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [by, setBy] = useState('');
  const [note, setNote] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [format, setFormat] = useState<'image' | 'video'>('image');
  const [draftText, setDraftText] = useState('');
  const [voiceover, setVoiceover] = useState('');
  const [still, setStill] = useState<File | null>(null);
  const [view, setView] = useState<'evidence' | 'edit' | 'compare'>('evidence');
  const [appearance, setAppearance] = useState<'dark' | 'light'>('dark');
  const [currentTime, setCurrentTime] = useState(0);
  const player = useRef<HTMLVideoElement>(null);
  const generation = useRef(0);
  const active = busy || (!!job && !['completed', 'incomplete', 'failed'].includes(job.status));

  useEffect(() => {
    document.documentElement.dataset.appearance = appearance;
  }, [appearance]);

  function fail(e: unknown) {
    setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.');
  }

  useEffect(() => {
    const controller = new AbortController();
    request<Config>('/ui/config', { signal: controller.signal })
      .then(setConfig)
      .catch((e) => {
        if (!controller.signal.aborted) fail(e);
      });
    request<Demo[]>('/ui/demos', { signal: controller.signal })
      .then(setDemos)
      .catch((e) => {
        if (!controller.signal.aborted) fail(e);
      });
    const id = new URLSearchParams(location.search).get('job');
    if (id && /^[0-9a-f]{32}$/.test(id))
      request<Job>(`/jobs/${id}`, { signal: controller.signal })
        .then(setJob)
        .catch((e) => {
          if (!controller.signal.aborted) fail(e);
        });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!job) return;
    const controller = new AbortController();
    const current = generation.current;
    const isCurrent = () => !controller.signal.aborted && current === generation.current;
    let fetching = false;
    const events = new EventSource(`/jobs/${job.job_id}/events`);
    async function finish(status: string) {
      if (fetching || !isCurrent()) return;
      fetching = true;
      events.close();
      setJob((j) => (j ? { ...j, status } : j));
      setStatus(
        status === 'failed'
          ? 'Processing failed. No complete result is available.'
          : status === 'incomplete'
            ? 'Screening is incomplete. Review the stage details.'
            : 'Screening finished. Review the evidence.',
      );
      if (status === 'failed') return;
      try {
        const value = await request<Result>(`/ui/jobs/${job!.job_id}`, {
          signal: controller.signal,
        });
        if (!isCurrent()) return;
        setResult(value);
        setResultOwner(job!.job_id);
        if (value.media_url) setMedia(value.media_url);
        setSelected(
          value.claims.find((c) => c.flags.length)?.claim_id ?? value.claims[0]?.claim_id ?? null,
        );
        if (job!.kind === 'fix') {
          const [fixed, history] = await Promise.all([
            request<Fix>(`/fixes/${job!.job_id}`, { signal: controller.signal }),
            request<Round[]>(`/ui/fixes/${job!.job_id}/rounds`, { signal: controller.signal }),
          ]);
          if (isCurrent()) {
            setFix(fixed);
            setRounds(history);
            setView('compare');
            if (history.length) setMedia(history[history.length - 1].media_url);
          }
        } else setSource(job!.job_id);
      } catch (e) {
        if (isCurrent()) fail(e);
      }
    }
    events.addEventListener('progress', (event) => {
      if (!isCurrent()) return;
      try {
        const data = progressMessage((event as MessageEvent).data);
        if (data.stage)
          setStages((old) => ({ ...old, [data.stage!]: data.stage_status ?? 'unknown' }));
        if (['completed', 'incomplete', 'failed'].includes(data.status)) void finish(data.status);
        else
          setStatus(
            data.stage
              ? `${data.stage.replaceAll('_', ' ')}: ${data.stage_status}`
              : `Job ${data.status}…`,
          );
      } catch {
        events.close();
        setJob((j) => (j ? { ...j, status: 'failed' } : j));
        setStatus('Progress stream closed. Reload to reconnect to the saved job.');
        setError('The progress stream could not be read. Reload to reconnect.');
      }
    });
    events.onerror = () => {
      if (fetching || !isCurrent()) return;
      if (events.readyState === EventSource.CLOSED) {
        setJob((j) => (j ? { ...j, status: 'failed' } : j));
        setError('Progress is unavailable. The item may have expired; reload or upload again.');
        setStatus('Progress stream closed.');
      } else setStatus('Progress connection interrupted; reconnecting…');
    };
    return () => {
      events.close();
      controller.abort();
    };
    // Status updates must not create a second stream for the same job.
  }, [job?.job_id]);

  function reset() {
    generation.current += 1;
    setJob(null);
    setResult(null);
    setResultOwner(null);
    setFix(null);
    setRounds([]);
    setError('');
    setReveal(null);
    setSelected(null);
    setSource(null);
    setMedia('');
    setStages({});
    setConfirmed(false);
    setBy('');
    setNote('');
    setFormat('image');
    setDraftText('');
    setVoiceover('');
    setStill(null);
    setView('evidence');
    setCurrentTime(0);
    setStatus('Choose an ad to begin.');
    history.replaceState(null, '', location.pathname);
  }

  async function screenFile(file: File) {
    reset();
    setDemo(null);
    setBusy(true);
    setStatus('Uploading ad…');
    const current = generation.current;
    try {
      if (!config) throw new Error('Service configuration is not ready. Reload and try again.');
      if (file.size > config.max_upload_bytes)
        throw new Error('The upload limit is 100 MiB. Choose a smaller file.');
      const saved = await upload(file);
      const queued = await post<Job>('/screenings', { upload_id: saved.upload_id, align: false });
      if (current !== generation.current) return;
      setMedia(`/uploads/${saved.upload_id}/media`);
      setJob(queued);
      history.replaceState(null, '', `?job=${queued.job_id}`);
    } catch (e) {
      if (current === generation.current) {
        fail(e);
        setStatus('The ad was not screened.');
      }
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }

  async function chooseDemo(item: Demo) {
    reset();
    setDemo(item);
    setBusy(true);
    const current = generation.current;
    try {
      const value = await request<Result>(`/ui/demos/${item.id}`);
      if (current !== generation.current) return;
      setResult(value);
      setMedia(value.media_url ?? '');
      setStatus('Recorded demo result. No live model call.');
      setSelected(
        value.claims.find((c) => c.flags.length)?.claim_id ?? value.claims[0]?.claim_id ?? null,
      );
    } catch (e) {
      if (current === generation.current) fail(e);
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }

  async function revealDemo() {
    if (!demo) return;
    const current = generation.current;
    try {
      const value = await request<Reveal>(`/ui/demos/${demo.id}/reveal`);
      if (current === generation.current) setReveal(value);
    } catch (e) {
      if (current === generation.current) fail(e);
    }
  }

  async function startFix(event: React.FormEvent) {
    event.preventDefault();
    if (!source || !still) return;
    setBusy(true);
    setError('');
    setConfirmed(false);
    try {
      const saved = await upload(still);
      const queued = await post<Job>('/fixes', {
        screening_id: source,
        format,
        rounds: 3,
        align: false,
        scenes: [
          {
            upload_id: saved.upload_id,
            on_screen_text: draftText.split('\n').filter((t) => t.trim()),
            voiceover,
            duration_seconds: 4,
          },
        ],
      });
      setJob(queued);
      setStages({});
      setStatus('Fix queued…');
      history.replaceState(null, '', `?job=${queued.job_id}`);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function approve(event: React.FormEvent) {
    event.preventDefault();
    if (!job || !confirmed || !by.trim() || !canApprove(fix)) return;
    setBusy(true);
    setError('');
    try {
      await post(`/fixes/${job.job_id}/approve`, { by, note });
      setFix(await request<Fix>(`/fixes/${job.job_id}`));
      setStatus('Your review decision was recorded. This is not a Meta decision.');
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  const claim = result?.claims.find((c) => c.claim_id === selected);
  function select(id: string, seconds: number) {
    setSelected(id);
    setCurrentTime(seconds);
    if (player.current) player.current.currentTime = seconds;
  }

  return (
    <>
      <header>
        <a className="brand" href="/">
          <span className="brand-mark" aria-hidden="true" />
          PreFlight
        </a>
        <div className="header-actions">
          <span className="local">Local workspace</span>
          <button
            className="appearance"
            aria-pressed={appearance === 'light'}
            onClick={() => setAppearance(appearance === 'dark' ? 'light' : 'dark')}
          >
            {appearance === 'dark' ? 'Light appearance' : 'Dark appearance'}
          </button>
        </div>
      </header>
      <aside className="notice" role="note">
        {config?.notice ?? NOTICE}
      </aside>
      <main id="workspace" className={result ? 'has-result' : ''}>
        {!result && !active && (
          <section className="intro">
            <p className="eyebrow">Evidence before submission</p>
            <h1>
              Every claim.
              <br />
              <span>Back to its source.</span>
            </h1>
            <p>
              Review the ad, inspect the evidence and compare revisions. You make the final call.
            </p>
          </section>
        )}
        {config?.verification_label && <p className="verification">{config.verification_label}</p>}
        <div className={result && mode === 'screen' ? 'workspace-tools' : ''}>
          <nav className="tabs" aria-label="Workspace mode">
            <button
              aria-pressed={mode === 'screen'}
              disabled={active}
              onClick={() => {
                reset();
                setMode('screen');
                setDemo(null);
              }}
            >
              Screen an ad
            </button>
            <button
              aria-pressed={mode === 'demo'}
              disabled={active}
              onClick={() => {
                reset();
                setMode('demo');
              }}
            >
              Explore demos
            </button>
          </nav>
          {mode === 'screen' ? (
            <section className={`upload panel ${result || active ? 'compact-upload' : ''}`}>
              <div>
                <h2>{result ? 'Screen another ad' : 'Start with your ad'}</h2>
                <details className="upload-details" open={!result}>
                  <summary>Formats and retention</summary>
                  <p>PNG, JPEG, WebP, MP4, WebM or QuickTime · up to 100 MiB.</p>
                  <p className="muted">
                    Local copies expire after {config ? config.retention_seconds / 3600 : 24} hours;
                    running jobs may defer deletion. Screening uses configured model credits.
                  </p>
                </details>
              </div>
              <label className="file-button">
                {result ? 'Choose another ad' : 'Choose image or video'}
                <input
                  aria-label="Upload ad"
                  type="file"
                  accept="image/png,image/jpeg,image/webp,video/mp4,video/webm,video/quicktime"
                  disabled={active || !config}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = '';
                    if (file) void screenFile(file);
                  }}
                />
              </label>
            </section>
          ) : (
            <section className={`panel demo-library ${result ? 'compact-library' : ''}`}>
              <h2>Demo library</h2>
              <p>
                Reconstructions and team-made fixtures only. Outcomes stay hidden until you reveal
                them.
              </p>
              {demos.length === 0 ? (
                <p>No demo reconstructions are available yet.</p>
              ) : (
                <div className="demo-list">
                  {demos.map((d) => (
                    <button
                      key={d.id}
                      disabled={active}
                      aria-pressed={demo?.id === d.id}
                      onClick={() => void chooseDemo(d)}
                    >
                      {d.title}
                      <small>
                        {d.kind === 'synthetic'
                          ? 'Synthetic replay'
                          : `Reconstruction · ${d.ruling_id}`}
                      </small>
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <p className="status" role="status" aria-live="polite">
          <span className={active ? 'dot working' : 'dot'} />
          {status}
        </p>
        {Object.keys(stages).length > 0 && (
          <ol className="stages" aria-label="Screening stages">
            {Object.entries(stages).map(([name, state]) => (
              <li key={name}>
                {name.replaceAll('_', ' ')} <strong>{state}</strong>
              </li>
            ))}
          </ol>
        )}
        {result && (
          <>
            <div className="result-heading">
              <h2>{demo?.title ?? 'Screening evidence'}</h2>
              <span className="badge">
                {complete(result.screening)
                  ? `${result.screening.flags.length} flag${result.screening.flags.length === 1 ? '' : 's'}`
                  : 'Incomplete'}
              </span>
            </div>
            <p className="headline">{result.screening.headline}</p>
            {resultOwner && (
              <a
                className="report-link"
                href={`/screenings/${resultOwner}/report`}
                target="_blank"
                rel="noreferrer"
              >
                Open full source report ↗
              </a>
            )}
            <nav className="view-tabs" aria-label="Review views">
              <button aria-pressed={view === 'evidence'} onClick={() => setView('evidence')}>
                Evidence
              </button>
              {mode === 'screen' && source && !fix && complete(result.screening) && (
                <button aria-pressed={view === 'edit'} onClick={() => setView('edit')}>
                  Prepare revision
                </button>
              )}
              {fix && (
                <button aria-pressed={view === 'compare'} onClick={() => setView('compare')}>
                  Compare rounds
                </button>
              )}
            </nav>
            <div className="workspace" hidden={view !== 'evidence'}>
              <section className="panel viewer" aria-label="Ad and claim timeline">
                {media ? (
                  (fix ? fix.draft.format === 'video' : result.screening.ad.media === 'video') ? (
                    <video
                      ref={player}
                      onLoadedMetadata={(e) => {
                        const start = claim?.evidence[0]?.start ?? 0;
                        e.currentTarget.currentTime = start;
                        setCurrentTime(start);
                      }}
                      onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                      controls
                      preload="metadata"
                      src={media}
                      aria-label="Ad video"
                    />
                  ) : (
                    <img className="ad-image" src={media} alt="Ad being screened" />
                  )
                ) : (
                  <p>Preview unavailable after reload. The retained evidence is shown below.</p>
                )}
                <h3>Claim timeline</h3>
                {result.screening.ad.media === 'video' &&
                  !(fix && fix.draft.format !== 'video') && (
                    <ClaimTimeline
                      claims={result.claims}
                      duration={result.screening.ad.duration ?? 0}
                      selected={selected}
                      currentTime={currentTime}
                      onSelect={select}
                    />
                  )}
                <p className="muted">
                  Select a claim to inspect its evidence
                  {result.screening.ad.media === 'video' ? ' and seek the video' : ''}.
                </p>
                <div className="timeline">
                  {result.claims.map((c) => (
                    <button
                      key={c.claim_id}
                      aria-pressed={selected === c.claim_id}
                      onClick={() => select(c.claim_id, c.evidence[0]?.start ?? 0)}
                    >
                      <time>{timestamp(c.evidence[0]?.start ?? 0)}</time>
                      <span>{c.text}</span>
                      <small>
                        {c.flags.length
                          ? `${c.flags.length} flag${c.flags.length > 1 ? 's' : ''}`
                          : 'No flag'}
                      </small>
                    </button>
                  ))}
                </div>
                {result.claims.length === 0 && (
                  <p>
                    {complete(result.screening)
                      ? 'No claims were extracted.'
                      : 'No complete claim result is available.'}
                  </p>
                )}
              </section>
              <section className="panel evidence" aria-label="Selected claim evidence">
                <p className="eyebrow">Claim inspector</p>
                <h3>{claim?.text ?? 'Choose a claim'}</h3>
                {claim?.evidence.map((e, i) => (
                  <article className="evidence-item" key={i}>
                    <h4>
                      {e.kind} · {timestamp(e.start)}–{timestamp(e.end)}
                    </h4>
                    <p>{e.text}</p>
                    {e.timing === 'turn' && (
                      <small>
                        Timing covers the whole transcription turn, not individual words.
                      </small>
                    )}
                    {e.crop_url && (
                      <div className="crop">
                        <Preview
                          src={e.crop_url}
                          label={`Cited region at ${timestamp(e.start)}: ${e.text}`}
                        />
                      </div>
                    )}
                  </article>
                ))}
                {claim?.flags.map((f) => (
                  <article className="flag" key={f.flag_id}>
                    <span className="badge">
                      {f.kind === 'on_hold' ? 'On hold' : 'Possible breach'}
                    </span>
                    <p>{f.reason}</p>
                    <h4>Source provenance</h4>
                    {f.source_details.map((s, i) => (
                      <div className="source" key={i}>
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noreferrer">
                            {s.label} ↗
                          </a>
                        ) : (
                          <strong>{s.label}</strong>
                        )}
                        <p>{s.text}</p>
                      </div>
                    ))}
                    {f.suggested_wording ? (
                      <blockquote>
                        <small>Exact register wording · {f.suggested_wording.register_id}</small>
                        {f.suggested_wording.wording}
                      </blockquote>
                    ) : (
                      <p className="muted">
                        No register wording suggested. A person must decide what to change.
                      </p>
                    )}
                  </article>
                ))}
                {claim && claim.flags.length === 0 && (
                  <p>
                    No flag was returned for this claim. This does not predict platform enforcement.
                  </p>
                )}
              </section>
            </div>
            {demo && (
              <section className="panel">
                <h2>Compare with the ruling</h2>
                {!reveal ? (
                  <button onClick={() => void revealDemo()}>Reveal ASA outcome</button>
                ) : reveal.kind === 'synthetic' ? (
                  <p>{reveal.message}</p>
                ) : (
                  <>
                    <p>
                      <a href={reveal.url} target="_blank" rel="noreferrer">
                        ASA {reveal.ruling_id}
                      </a>{' '}
                      · {reveal.date}
                    </p>
                    <p>
                      Outcome: {reveal.outcome}. CAP rules: {reveal.rules?.join(', ')}.
                    </p>
                    <p>PreFlight's screening and the ASA's ruling are separate results.</p>
                  </>
                )}
              </section>
            )}
          </>
        )}
        {mode === 'screen' && source && !fix && result && complete(result.screening) && (
          <section className="panel editor-panel" hidden={view !== 'edit'}>
            <h2>Make the ad editable</h2>
            <p>
              Supply a clean scene still and the actual caption/script. The fix loop re-screens this
              draft; it does not edit an opaque uploaded video.
            </p>
            <form onSubmit={startFix} className="draft-form">
              <label>
                Draft format
                <select
                  value={format}
                  disabled={active}
                  onChange={(e) => setFormat(e.target.value as 'image' | 'video')}
                >
                  <option value="image">Image</option>
                  <option value="video">Video · one scene</option>
                </select>
              </label>
              <label>
                Scene still
                <input
                  required
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  disabled={active}
                  onChange={(e) => setStill(e.target.files?.[0] ?? null)}
                />
              </label>
              <label>
                On-screen captions · one per line
                <textarea
                  rows={4}
                  maxLength={80000}
                  value={draftText}
                  disabled={active}
                  onChange={(e) => setDraftText(e.target.value)}
                />
              </label>
              {format === 'video' && (
                <label>
                  Voiceover
                  <textarea
                    rows={3}
                    maxLength={4000}
                    value={voiceover}
                    disabled={active}
                    onChange={(e) => setVoiceover(e.target.value)}
                  />
                  <small>Local rendering dependencies must be installed for voiced video.</small>
                </label>
              )}
              <button type="submit" disabled={active || !still}>
                Run fix and re-screen
              </button>
            </form>
          </section>
        )}
        {fix && (
          <section className="panel comparison-panel" hidden={view !== 'compare'}>
            <h2>Fix rounds</h2>
            <p>
              Each column is a saved, re-screened draft. Remaining flags need a person; the loop
              never makes the final decision.
            </p>
            <RoundComparison rounds={rounds} />
            <p className="muted">
              The Evidence view shows the final saved screening and its source provenance.
            </p>
            {fix.decision ? (
              <div className="decision">
                <h3>Human review recorded</h3>
                <p>
                  {fix.decision.by} · {new Date(fix.decision.at).toLocaleString()}
                </p>
                <p>{fix.decision.note}</p>
                <p>This records a person's decision, not Meta approval.</p>
              </div>
            ) : canApprove(fix) ? (
              <form onSubmit={approve} className="review-form">
                <h3>Your review decision</h3>
                <label>
                  Your name
                  <input
                    required
                    maxLength={100}
                    value={by}
                    onChange={(e) => setBy(e.target.value)}
                  />
                </label>
                <label>
                  Review note
                  <textarea
                    maxLength={2000}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </label>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  I reviewed the final draft and evidence. This is my decision, not a platform
                  verdict.
                </label>
                <button type="submit" disabled={busy || !by.trim() || !confirmed}>
                  Approve · record my review
                </button>
              </form>
            ) : (
              <p className="notice">
                This draft needs a person. Approval is unavailable while flags remain or screening
                is incomplete.
              </p>
            )}
          </section>
        )}
        {mode === 'demo' && config && <Metrics board={config.scoreboard} />}
      </main>
      <footer>
        <span>PreFlight · Evidence before submission</span>
        <a href="/docs">API documentation ↗</a>
      </footer>
    </>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
