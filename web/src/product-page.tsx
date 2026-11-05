import './product-page.css';

export function Brand() {
  return (
    <a className="brand" href="/" aria-label="PreFlight home">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
        <rect
          x="1"
          y="1"
          width="20"
          height="20"
          rx="3"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
        />
        <path d="M6 16V6h10" fill="none" stroke="currentColor" strokeWidth="2.4" />
      </svg>
      PreFlight
    </a>
  );
}

export function ProductSections() {
  return (
    <div className="product-sections">
      <section className="product-story" id="features" aria-labelledby="features-heading">
        <div className="section-intro">
          <p className="eyebrow">Evidence</p>
          <h2 id="features-heading">See what was flagged, and where</h2>
          <p>
            A flag ties a claim to where it appears in the ad: a script line, a stretch of speech, a
            caption or a cropped region of the frame. It gives the reason and the CAP rules or
            register entries it relies on, so you can judge whether the concern holds.
          </p>
        </div>
        <figure className="receipt-example">
          <figcaption>Illustrative example / synthetic script</figcaption>
          <div className="example-source">
            <span className="label">Script · line 2</span>
            <blockquote>
              SUPER: <mark>Clinically proven formula</mark>
            </blockquote>
          </div>
          <div className="example-receipt">
            <p className="eyebrow">Possible breach</p>
            <h3>An objective claim needs evidence</h3>
            <p>
              Viewers will read &ldquo;clinically proven&rdquo; as a factual claim. The advertiser
              must hold documentary evidence for it before the ad runs.
            </p>
            <a
              href="https://www.asa.org.uk/type/non_broadcast/code_section/03.html"
              target="_blank"
              rel="noreferrer"
            >
              Source: CAP Code 3.7 ↗
            </a>
          </div>
        </figure>
      </section>

      <section className="format-section" aria-labelledby="format-heading">
        <div className="section-heading">
          <p className="eyebrow">Inputs</p>
          <h2 id="format-heading">Screen the script, then the finished ad</h2>
        </div>
        <div className="format-grid">
          <article>
            <div className="format-art script-art" aria-hidden="true">
              <span>VO:</span>
              <i />
              <span>SUPER:</span>
              <i className="flagged" />
              <i />
            </div>
            <span className="label">Before production</span>
            <h3>The script</h3>
            <p>
              Screen the copy before anything is shot. Flags point to numbered lines. Start spoken
              lines with VO: and on-screen text with SUPER:.
            </p>
            <p className="format-detail">UTF-8 .txt or .md</p>
          </article>
          <article>
            <div className="format-art image-art" aria-hidden="true">
              <div>
                <i />
              </div>
              <span>FRAME / 01</span>
            </div>
            <span className="label">Before it runs</span>
            <h3>The finished creative</h3>
            <p>
              Screen a still or a video. The evidence shows the spoken passage, on-screen text or
              image region behind a claim.
            </p>
            <p className="format-detail">Images and video</p>
          </article>
          <article>
            <div className="format-art revision-art" aria-hidden="true">
              <span>Draft 01</span>
              <s>Beats fatigue in seven days</s>
              <span>Draft 02</span>
              <b>Magnesium contributes to a reduction of tiredness and fatigue</b>
            </div>
            <span className="label">Revisions</span>
            <h3>The next draft</h3>
            <p>
              Upload the scene as a still without text and type its captions. PreFlight renders the
              draft, screens it again and keeps each round for comparison. Text burned into a video
              cannot be edited.
            </p>
            <p className="format-detail">An image or a one-scene video</p>
          </article>
        </div>
      </section>

      <section className="process-section" id="how-it-works" aria-labelledby="process-heading">
        <div className="section-intro">
          <p className="eyebrow">How it works</p>
          <h2 id="process-heading">From upload to decision</h2>
          <p>
            A flag asks you to check something. Open its evidence, read the cited rule and decide
            whether the reason fits your ad.
          </p>
          <a className="text-action" href="#workspace">
            Upload an ad
          </a>
        </div>
        <ol className="process-list">
          <li>
            <span>01</span>
            <div>
              <h3>Upload the ad</h3>
              <p>
                One script, image or video at a time. Screening can take several minutes; the stage
                list shows what has finished.
              </p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <h3>Check the evidence</h3>
              <p>
                Select a claim to see where it appears in the ad and the sources each flag cites.
              </p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <h3>Revise and screen again</h3>
              <p>
                Change the wording and screen the next draft. A clean script does not clear the
                finished ad, so screen that as well.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <section className="data-section" id="data-handling" aria-labelledby="data-heading">
        <div>
          <p className="eyebrow">Data handling</p>
          <h2 id="data-heading">How your ad is processed and stored</h2>
        </div>
        <div>
          <p>
            Screening uses the Meta Model API in Standard mode. Meta&apos;s{' '}
            <a href="https://dev.meta.ai/legal/terms-of-service" target="_blank" rel="noreferrer">
              Standard-mode terms
            </a>{' '}
            exclude using submitted content to train its models. The upload form shows how long
            uploads are kept before you send a file.
          </p>
          <p>
            Uploads, model responses and generated revisions are stored on the server running
            PreFlight. With sign-in on, each account sees only its own uploads and screenings;
            without it, everyone on the server shares one workspace. This is a prototype, so do not
            upload confidential ads. The demos are labelled as reconstructions of ruled ads or as
            synthetic ads made by the team.
          </p>
          <a href="/docs">API documentation</a>
        </div>
      </section>

      <section className="faq-section" id="questions" aria-labelledby="faq-heading">
        <div className="section-intro">
          <p className="eyebrow">Questions</p>
          <h2 id="faq-heading">Before you upload</h2>
        </div>
        <div className="faq-list">
          <details>
            <summary>Does PreFlight approve my ad?</summary>
            <p>
              No. It screens against the named sources and shows issues for a person to review. It
              is not legal advice and cannot guarantee an outcome from Meta or the ASA.
            </p>
          </details>
          <details>
            <summary>Which sources does it check?</summary>
            <p>
              The GB nutrition and health claims register, the CAP Code and an index of ASA rulings.
              The source report for each screening lists the dated snapshot of each source. Claims
              for substances whose health claims are still on hold in GB are marked On hold rather
              than Possible breach.
            </p>
          </details>
          <details>
            <summary>Can I start with a script?</summary>
            <p>
              Yes. Upload UTF-8 .txt or .md and start lines with VO: or SUPER: to separate speech
              from on-screen text. Flags cite the exact line. Screen the finished creative as well,
              since only that shows what is actually seen and heard.
            </p>
          </details>
          <details>
            <summary>What if a model stage fails?</summary>
            <p>
              The result is marked Incomplete and lists the stages that did not finish. Claims the
              checker did not reach are labelled Couldn&apos;t check, so a failed stage never reads
              as a clean result.
            </p>
          </details>
          <details>
            <summary>Can I use it for confidential client work?</summary>
            <p>
              No. Each signed-in account sees only its own screenings, but this prototype has not
              had the security review client work needs. Do not upload confidential material.
            </p>
          </details>
        </div>
      </section>

      <section className="closing-section" aria-labelledby="closing-heading">
        <p className="eyebrow">Start a screening</p>
        <h2 id="closing-heading">Screen your next ad</h2>
        <a className="primary" href="#workspace">
          Screen an ad
        </a>
      </section>
    </div>
  );
}

// with real sign-in on, the account links to the preview pages are hidden
export function SiteFooter({ signedIn = false }: { signedIn?: boolean }) {
  return (
    <footer className="site-footer">
      <div className="footer-main">
        <div className="footer-brand">
          <Brand />
          <p>
            Screens health and supplement ads against the GB claims register, the CAP Code and ASA
            rulings.
          </p>
        </div>
        <nav aria-label="Product">
          <h2>Product</h2>
          <a href="/#workspace">Screen an ad</a>
          {/* signed in, the workspace replaces the product page these sections live on */}
          {!signedIn && <a href="/#features">What it does</a>}
          {!signedIn && <a href="/#how-it-works">How it works</a>}
        </nav>
        <nav aria-label="Resources">
          <h2>Resources</h2>
          {!signedIn && <a href="/#questions">Questions & answers</a>}
          {!signedIn && <a href="/#data-handling">Data handling</a>}
          <a href="/docs">API documentation</a>
        </nav>
        {!signedIn && (
          <nav aria-label="Account">
            <h2>Account</h2>
            <a href="/login">Log in</a>
            <a href="/signup">Sign up</a>
          </nav>
        )}
      </div>
      <div className="footer-bottom">
        <span>PreFlight / GB ad screening prototype</span>
        <p>Screening only, not legal advice. A person decides whether an ad runs.</p>
      </div>
    </footer>
  );
}

export function AccountPage({ mode }: { mode: 'login' | 'signup' }) {
  const signup = mode === 'signup';
  return (
    <>
      <header className="account-header">
        <Brand />
        <a href="/">Back to PreFlight</a>
      </header>
      <main className="account-page">
        <section className="account-intro">
          <p className="eyebrow">PreFlight</p>
          <h1>Screen health and supplement ads</h1>
          <p>Check claims against the GB claims register, the CAP Code and past ASA rulings.</p>
        </section>
        <section className="account-card" aria-labelledby="account-heading">
          <p className="eyebrow">{signup ? 'Registration preview' : 'Sign-in preview'}</p>
          <h2 id="account-heading">{signup ? 'Create your account' : 'Log in'}</h2>
          <p>
            {signup ? 'Already have an account?' : 'New to PreFlight?'}{' '}
            <a href={signup ? '/login' : '/signup'}>{signup ? 'Log in' : 'Sign up'}</a>
          </p>
          <div className="account-unavailable" role="status">
            <strong>Accounts are not connected in this build.</strong>
            <p>
              This form shows the planned sign-in. It is switched off and sends nothing you type.
            </p>
          </div>
          <form
            aria-label={signup ? 'Create account' : 'Log in'}
            onSubmit={(e) => e.preventDefault()}
          >
            <fieldset disabled>
              {signup && (
                <label>
                  Your name
                  <input autoComplete="name" placeholder="Your name" />
                </label>
              )}
              <label>
                Email address
                <input type="email" autoComplete="email" placeholder="you@yourteam.com" />
              </label>
              <label>
                Password
                <input
                  type="password"
                  autoComplete={signup ? 'new-password' : 'current-password'}
                  placeholder={signup ? 'Create a password' : 'Your password'}
                />
              </label>
              <button className="primary" type="submit">
                {signup ? 'Create account' : 'Log in'}
              </button>
            </fieldset>
          </form>
          <a className="account-workspace" href="/">
            Use PreFlight without an account
          </a>
          <p className="account-fine-print">
            Without an account, everyone on this server shares one workspace. Do not upload
            confidential ads.
          </p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
