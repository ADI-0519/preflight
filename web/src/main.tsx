import { StrictMode, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  canApprove,
  complete,
  NOTICE,
  post,
  progressMessage,
  PUBLIC_ERRORS,
  request,
  upload,
} from './api';
import type { Account, Config, Demo, Fix, Job, Result, Reveal, Round, Scoreboard } from './api';
import { Login, signOutEverywhere } from './login';
import './style.css';
import { ClaimTrack, Inspector, TierSummary } from './evidence';
import { UploadPanel } from './upload-panel';
import { AccountPage, Brand, ProductSections, SiteFooter } from './product-page';
import {
  FlagCount,
  FlaggedList,
  RoundComparison,
  ScriptPreview,
  StageList,
  StillStage,
} from './workspace';

function mebibytes(bytes: number): number {
  return Math.round((bytes / 1024 / 1024) * 10) / 10;
}

function Metrics({ board }: { board: Scoreboard }) {
  return (
    <section className="score" aria-labelledby="score-title">
      <h2 id="score-title">Registered test scoreboard</h2>
      {!board.available ? (
        <p>{board.reason} Only the registered final test run is shown here.</p>
      ) : (
        <>
          <p>
            Run {board.run_id} on split {board.split}, revision {board.git_sha}
          </p>
          <p>
            These figures describe that recorded test run, not this upload. The current build may
            use different settings.
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
                      ? `${(m.low * 100).toFixed(1)} to ${(m.high * 100).toFixed(1)}%`
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

// guest: sign-in is on and nobody is signed in, so the landing page shows and every action leads to sign-in
function App({ account, guest = false }: { account: Account | null; guest?: boolean }) {
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
  const [unavailableMedia, setUnavailableMedia] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('No ad loaded.');
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
  const [appearance, setAppearance] = useState<'dark' | 'light'>('light');
  const [chosen, setChosen] = useState<{ name: string; video: boolean } | null>(null);
  const chrome = useRef<HTMLDivElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const player = useRef<HTMLVideoElement>(null);
  const generation = useRef(0);
  // with sign-in on, the account's email is the approver
  const approver = account?.signed_in ? (account.email ?? '') : by;
  const active = busy || (!!job && !['completed', 'incomplete', 'failed'].includes(job.status));

  useEffect(() => {
    document.documentElement.dataset.appearance = appearance;
  }, [appearance]);

  useEffect(() => {
    if (view !== 'evidence') player.current?.pause();
  }, [view]);

  function fail(e: unknown) {
    setError(
      e instanceof Error
        ? e.message
        : 'The request failed and the server gave no reason. Try again.',
    );
  }

  useEffect(() => {
    const controller = new AbortController();
    request<Config>('/ui/config', { signal: controller.signal })
      .then(setConfig)
      .catch((e) => {
        if (!controller.signal.aborted) fail(e);
      });
    if (!guest)
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
          ? 'Screening failed before it produced a result.'
          : status === 'incomplete'
            ? 'Some stages did not finish. They are listed under Screening stages.'
            : 'Screening finished.',
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
        setError(
          'Progress is unavailable. The item may have expired. Reload, or upload the ad again.',
        );
        setStatus('Progress stream closed.');
      } else setStatus('Connection lost. Reconnecting…');
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
    setUnavailableMedia(null);
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
    setChosen(null);
    setStatus('No ad loaded.');
    history.replaceState(null, '', location.pathname);
  }

  async function screenFile(file: File) {
    reset();
    setDemo(null);
    setChosen({ name: file.name, video: file.type.startsWith('video/') });
    setBusy(true);
    setStatus('Uploading ad…');
    const current = generation.current;
    try {
      if (!config)
        throw new Error('The page has not loaded its settings yet. Reload and try again.');
      if (file.size > config.max_upload_bytes)
        throw new Error(
          `The upload limit is ${mebibytes(config.max_upload_bytes)} MiB. Choose a smaller file.`,
        );
      const saved = await upload(file, (done) => {
        if (current === generation.current) setStatus(`Uploading ad… ${Math.round(done * 100)}%`);
      });
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
      setStatus('Replaying a recorded screening. Nothing is sent to a model.');
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
    setStatus('Uploading revision…');
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
      setStatus('Revision queued…');
      history.replaceState(null, '', `?job=${queued.job_id}`);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function approve(event: React.FormEvent) {
    event.preventDefault();
    if (!job || !confirmed || !approver.trim() || !canApprove(fix)) return;
    setBusy(true);
    setError('');
    try {
      await post(`/fixes/${job.job_id}/approve`, { by: approver, note });
      setFix(await request<Fix>(`/fixes/${job.job_id}`));
      setStatus('Your decision is recorded. Meta has not reviewed this ad.');
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  const claim = result?.claims.find((c) => c.claim_id === selected);
  const script = result?.screening.ad.media === 'script';
  function select(id: string, seconds: number | null) {
    setSelected(id);
    if (seconds === null) return;
    setCurrentTime(seconds);
    if (player.current) player.current.currentTime = seconds;
  }

  function openScreen() {
    reset();
    setMode('screen');
    setDemo(null);
  }

  function openDemos() {
    if (guest) return location.assign('/login');
    reset();
    setMode('demo');
  }

  useEffect(() => {
    const el = chrome.current!;
    const measure = () =>
      document.documentElement.style.setProperty('--chrome-h', `${el.offsetHeight}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const processing =
    mode === 'screen' && !result && (active || (!!job && job.status !== 'failed' && !error));
  const entry = mode === 'screen' && !result && !processing;
  const lanes = result?.screening.ad.media === 'video' && !(fix && fix.draft.format !== 'video');
  const lastRound = rounds[rounds.length - 1];

  const demoChoices =
    demos.length === 0 ? (
      <p>No demo reconstructions are available yet.</p>
    ) : (
      <div className="demos">
        {demos.map((d) => (
          <button
            key={d.id}
            className="outline"
            disabled={active}
            aria-pressed={demo?.id === d.id}
            onClick={() => void chooseDemo(d)}
          >
            {d.title}
            <small>
              {d.kind === 'synthetic'
                ? 'Synthetic replay'
                : `Reconstruction of ASA ruling ${d.ruling_id}`}
            </small>
          </button>
        ))}
      </div>
    );

  return (
    <>
      <div className="chrome" ref={chrome}>
        <header className={`bar${entry ? ' with-account' : ''}`}>
          <Brand />
          <nav className="modes" aria-label="Workspace mode">
            <button aria-pressed={mode === 'screen'} disabled={active} onClick={openScreen}>
              Screen an ad
            </button>
            <button aria-pressed={mode === 'demo'} disabled={active} onClick={openDemos}>
              Explore demos
            </button>
          </nav>
          {entry && !account && (
            <nav className="account-nav" aria-label="Account">
              <a href="/login">Log in</a>
              <a className="outline" href="/signup">
                Sign up
              </a>
            </nav>
          )}
          <button
            className="appearance outline"
            aria-label={appearance === 'dark' ? 'Light appearance' : 'Dark appearance'}
            aria-pressed={appearance === 'light'}
            onClick={() => setAppearance(appearance === 'dark' ? 'light' : 'dark')}
          >
            {appearance === 'dark' ? 'Light' : 'Dark'}
            <span className="long"> appearance</span>
          </button>
          {account?.signed_in && (
            <button
              className="outline"
              title={account.email ?? undefined}
              onClick={() => signOutEverywhere().then(() => location.reload())}
            >
              Sign out
            </button>
          )}
        </header>
        <aside className="notice" role="note">
          {config?.notice ?? NOTICE}
        </aside>
      </div>
      <main id="workspace" className={entry ? 'entry' : undefined}>
        {config?.verification_label && <p className="replay">{config.verification_label}</p>}
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <p className="sr-only" role="status" aria-live="polite">
          {status}
        </p>
        {mode === 'demo' && !result && (
          <>
            <div className="title-row">
              <div className="what">
                <h1>Explore demos</h1>
                <p className="lead">
                  Review reconstructions of ruled ads and team-made examples. For reconstructions,
                  reveal the ASA outcome after reviewing the screening.
                </p>
              </div>
            </div>
            {demoChoices}
          </>
        )}
        {mode === 'demo' && result && demoChoices}
        {entry && (
          <>
            <div className="title-row entry-title">
              <div className="what">
                <p className="eyebrow">Health and supplement ad screening</p>
                <h1>
                  Check the claims.
                  <br />
                  <em>Review the evidence.</em>
                </h1>
                <p className="lead">
                  Upload a script, image or video. Review possible issues against the GB register
                  and CAP Code, with evidence from your ad and the sources behind each flag.
                </p>
                <p className="entry-sources">
                  GB health claims register <span aria-hidden="true">/</span> CAP Code{' '}
                  <span aria-hidden="true">/</span> ASA rulings
                </p>
              </div>
            </div>
            <div className="work entry-work">
              <UploadPanel
                disabled={active || !config || Boolean(config.uploads_closed)}
                notice={config?.upload_notice ?? 'Loading upload terms…'}
                closedReason={
                  config?.uploads_closed ? PUBLIC_ERRORS[config.uploads_closed] : undefined
                }
                onFile={(file) => void screenFile(file)}
                signIn={guest}
              />
              <div className="facts">
                <details className="input-details">
                  <summary>Supported formats & retention</summary>
                  <h2>Formats</h2>
                  <p>
                    PNG, JPEG, WebP, MP4, WebM or QuickTime, up to{' '}
                    {config ? mebibytes(config.max_upload_bytes) : 150} MiB
                    {config ? `, and video up to ${config.max_seconds} seconds` : ''}. Scripts:
                    UTF-8 .txt or .md, up to 64 KiB and 1,000 lines. Use VO: or SUPER: to
                    distinguish spoken and on-screen copy.
                  </p>
                  <h2>Retention</h2>
                  <p>
                    Uploads expire after {config ? config.retention_seconds / 3600 : 24} hours.
                    Local deletion runs while the server is on and may wait for active jobs.
                    Screening uses model credits.
                  </p>
                </details>
                <div>
                  <h2>Demos</h2>
                  <p>
                    <button className="link" onClick={openDemos}>
                      Explore labelled demos
                    </button>
                    . Reconstructions have ASA outcomes you can reveal; team-made examples do not.
                  </p>
                </div>
              </div>
            </div>
            <ProductSections />
          </>
        )}
        {processing && (
          <>
            <div className="title-row">
              <div className="what">
                <h1>{chosen ? `Screening ${chosen.name}` : 'Screening your ad'}</h1>
                <p className="headline" aria-hidden="true">
                  {status}
                </p>
              </div>
            </div>
            <div className="work">
              <section className="stage-col">
                <div className="stage">
                  {/\.(txt|md)$/i.test(chosen?.name ?? '') ? (
                    <p>
                      Reading your script. The numbered source lines will appear with the result.
                    </p>
                  ) : media && unavailableMedia !== media ? (
                    chosen?.video ? (
                      <video src={media} controls preload="metadata" aria-label="Uploaded ad" />
                    ) : (
                      <img src={media} alt="Uploaded ad" />
                    )
                  ) : (
                    <p>{busy ? 'Uploading the ad…' : 'No preview is available for this job.'}</p>
                  )}
                </div>
              </section>
              <section className="facts">
                <StageList stages={stages} />
              </section>
            </div>
          </>
        )}
        {result && (
          <>
            <div className="title-row">
              <div className="what">
                <div className="title-line">
                  <h1>{demo?.title ?? 'Screening evidence'}</h1>
                  <FlagCount screening={result.screening} />
                </div>
                <p className="headline">{result.screening.headline}</p>
                {result.incomplete_stages.length > 0 && (
                  <p className="unfinished">
                    Stages that did not finish:{' '}
                    {result.incomplete_stages.map((s) => s.replaceAll('_', ' ')).join(', ')}.
                  </p>
                )}
                {demo && (
                  <p className="muted">
                    {demo.kind === 'synthetic'
                      ? 'Synthetic replay of a recorded screening.'
                      : `Recorded screening of a reconstruction of ASA ruling ${demo.ruling_id}.`}{' '}
                    Nothing is sent to a model.
                  </p>
                )}
              </div>
              <div className="views">
                <nav aria-label="Review views">
                  <button aria-pressed={view === 'evidence'} onClick={() => setView('evidence')}>
                    Evidence
                  </button>
                  {mode === 'screen' && source && !fix && !script && complete(result.screening) && (
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
                {resultOwner && (
                  <a href={`/screenings/${resultOwner}/report`} target="_blank" rel="noreferrer">
                    Open full source report
                  </a>
                )}
                {demo && !reveal && (
                  <button className="primary" onClick={() => void revealDemo()}>
                    Reveal ASA outcome
                  </button>
                )}
              </div>
            </div>
            {reveal && (
              <div className="reveal">
                <div className="band">
                  {reveal.kind === 'synthetic' ? (
                    <strong>{reveal.message}</strong>
                  ) : (
                    <strong>
                      ASA ruling{' '}
                      <a href={reveal.url} target="_blank" rel="noreferrer">
                        {reveal.ruling_id}
                      </a>
                      , {reveal.date}: {reveal.outcome}. CAP rules: {reveal.rules?.join(', ')}.
                    </strong>
                  )}
                  <p>PreFlight's screening and the ASA's ruling are separate results.</p>
                </div>
              </div>
            )}
            {active && (
              <section className="fix-progress">
                <p className="headline" aria-hidden="true">
                  {status}
                </p>
                <StageList stages={stages} />
              </section>
            )}
            <div className="workspace" hidden={view !== 'evidence'}>
              <section className="viewer" aria-label="Ad and claim timeline">
                <div className="panel-heading">
                  <span>{script ? 'Source script' : 'Your creative'}</span>
                  <span className="panel-meta">
                    {script
                      ? 'Numbered copy'
                      : result.screening.ad.media === 'video'
                        ? 'Video review'
                        : 'Image review'}
                  </span>
                </div>
                <div className="stage">
                  {script ? (
                    <ScriptPreview
                      lines={result.screening.script_lines}
                      selected={
                        claim?.evidence.map((e) => e.line_number).filter((n): n is number => !!n) ??
                        []
                      }
                    />
                  ) : media && unavailableMedia !== media ? (
                    (fix ? fix.draft.format === 'video' : result.screening.ad.media === 'video') ? (
                      <video
                        ref={player}
                        onLoadedMetadata={(e) => {
                          const start = claim?.start ?? 0;
                          e.currentTarget.currentTime = start;
                          setCurrentTime(start);
                        }}
                        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                        controls
                        preload="metadata"
                        src={media}
                        onError={() => setUnavailableMedia(media)}
                        aria-label="Ad video"
                      />
                    ) : (
                      <img
                        className="ad-image"
                        src={media}
                        alt="Ad being screened"
                        onError={() => setUnavailableMedia(media)}
                      />
                    )
                  ) : (
                    <p>Ad preview unavailable. The saved claims and evidence remain below.</p>
                  )}
                </div>
                <TierSummary tiers={result.tiers} flags={result.screening.flags.length} />
                <ClaimTrack
                  claims={result.claims}
                  duration={lanes ? (result.screening.ad.duration ?? 0) : 0}
                  still={result.screening.ad.media === 'image'}
                  selected={selected}
                  currentTime={currentTime}
                  onSelect={select}
                />
                {result.claims.length === 0 && (
                  <p>
                    {complete(result.screening)
                      ? 'No claims were extracted.'
                      : 'Screening stopped before claims were extracted.'}
                  </p>
                )}
              </section>
              <Inspector
                claim={claim}
                still={result.screening.ad.media === 'image'}
                maySay={result.may_say}
              />
            </div>
          </>
        )}
        {mode === 'screen' && source && !fix && result && !script && complete(result.screening) && (
          <div className="work editor" hidden={view !== 'edit'}>
            <section className="stage-col">
              <StillStage file={still} />
              <FlaggedList claims={result.claims} maySay={result.may_say} />
            </section>
            <form onSubmit={startFix} className="sheet draft-form">
              <h2>Editable draft</h2>
              <p className="muted">
                Upload the scene as a still image without text, then type the captions the ad shows.
                Each round is re-screened. Text burned into an uploaded video cannot be edited.
              </p>
              <label>
                Draft format
                <select
                  value={format}
                  disabled={active}
                  onChange={(e) => setFormat(e.target.value as 'image' | 'video')}
                >
                  <option value="image">Image</option>
                  <option value="video">Video, one scene</option>
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
                On-screen captions, one per line
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
                  <small>Voiced video needs the local rendering tools installed.</small>
                </label>
              )}
              <button className="primary" type="submit" disabled={active || !still}>
                Run fix and re-screen
              </button>
            </form>
          </div>
        )}
        {fix && (
          <section className="comparison" hidden={view !== 'compare'}>
            <p className="muted">
              Each column is one saved draft and its screening. A person decides what to do about
              any flag that remains.
            </p>
            <RoundComparison rounds={rounds} />
            <div className="review sheet">
              <div className="summary">
                <h2>Your review decision</h2>
                {lastRound && (
                  <p>
                    You are recording a decision on round {lastRound.round}, the last saved draft.
                  </p>
                )}
                <p>Its screening: {fix.screening.headline}</p>
                <p className="muted">Evidence shows the last round's screening and its sources.</p>
              </div>
              {fix.decision ? (
                <div className="decision">
                  <h3>Human review recorded</h3>
                  <p>
                    {fix.decision.by}, {new Date(fix.decision.at).toLocaleString()}
                  </p>
                  <p>{fix.decision.note}</p>
                  <p>Recorded by a person in PreFlight. Meta has not reviewed this ad.</p>
                </div>
              ) : canApprove(fix) ? (
                <form onSubmit={approve} className="review-form">
                  <label>
                    Your name
                    <input
                      required
                      maxLength={100}
                      value={approver}
                      readOnly={!!account?.signed_in}
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
                    I reviewed the final draft and its evidence, and I am making this decision
                    myself.
                  </label>
                  <button
                    className="primary"
                    type="submit"
                    disabled={busy || !approver.trim() || !confirmed}
                  >
                    Record my review decision
                  </button>
                </form>
              ) : (
                <p className="needs-person">
                  Flags remain or screening is incomplete, so no review decision can be recorded for
                  this draft.
                </p>
              )}
            </div>
          </section>
        )}
        {mode === 'demo' && config && <Metrics board={config.scoreboard} />}
      </main>
      <SiteFooter signedIn={account !== null} />
    </>
  );
}

// with sign-in on, nothing in the workspace loads until the server holds a session for this browser
function Gate() {
  const [state, setState] = useState<{ config: Config; account: Account } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      request<Config>('/ui/config'),
      fetch('/auth/me', { cache: 'no-store' }).then((r) => r.json() as Promise<Account>),
    ])
      .then(([config, account]) => setState({ config, account }))
      .catch(() => setError('PreFlight could not reach its server. Reload the page to try again.'));
  }, []);

  if (error)
    return (
      <p className="login-error" role="alert">
        {error}
      </p>
    );
  if (!state) return null;
  const { config, account } = state;
  const accountPath = location.pathname === '/login' || location.pathname === '/signup';
  // without sign-in, /login and /signup stay design previews; with it, they are the real sign-in and
  // every other path shows the landing page until the visitor signs in
  if (!config.auth && accountPath)
    return <AccountPage mode={location.pathname === '/signup' ? 'signup' : 'login'} />;
  if (config.auth && !account.signed_in && !account.pending && !accountPath)
    return <App account={null} guest />;
  if (config.auth && !account.signed_in)
    return (
      <Login
        config={config.auth}
        pending={account.pending ?? null}
        onSignedIn={(a) => setState({ config, account: a })}
      />
    );
  if (accountPath) history.replaceState(null, '', '/');
  return <App account={config.auth ? account : null} />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Gate />
  </StrictMode>,
);
