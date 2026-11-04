import { NOTICE } from './api';
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
          <p className="eyebrow">01 / A closer look</p>
          <h2 id="features-heading">
            Every flag.
            <br />
            <em>Something to go on.</em>
          </h2>
          <p>
            A warning on its own creates more work. PreFlight puts the words, the evidence and the
            source together, so you can investigate.
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
            <p className="eyebrow">A question for the reviewer</p>
            <h3>Where is the evidence?</h3>
            <p>Check the substantiation behind this objective claim.</p>
            <a
              href="https://www.asa.org.uk/type/non_broadcast/code_section/03.html"
              target="_blank"
              rel="noreferrer"
            >
              Source: CAP Code 3.7 ↗
            </a>
          </div>
          <p className="example-caption">
            An explanation to investigate, not a regulatory verdict.
          </p>
        </figure>
      </section>

      <section className="format-section" aria-labelledby="format-heading">
        <div className="section-heading">
          <p className="eyebrow">02 / Made for the whole creative</p>
          <h2 id="format-heading">
            Start with the words.
            <br />
            Come back with the cut.
          </h2>
        </div>
        <div className="format-grid">
          <article>
            <div className="format-art script-art" aria-hidden="true">
              <span>VO:</span>
              <i />
              <span>SUPER:</span>
              <i />
              <i />
            </div>
            <span className="label">Before production</span>
            <h3>The script</h3>
            <p>
              Check copy early. Return to exact numbered lines and distinguish spoken words from
              on-screen captions.
            </p>
            <p className="format-detail">UTF-8 .txt or .md</p>
          </article>
          <article>
            <div className="format-art image-art" aria-hidden="true">
              <div />
              <i />
              <span>FRAME / 01</span>
            </div>
            <span className="label">Before submission</span>
            <h3>The finished creative</h3>
            <p>
              Review a still or video, with spoken passages, on-screen text and image regions beside
              the claims they support.
            </p>
            <p className="format-detail">Images and video</p>
          </article>
          <article>
            <div className="format-art revision-art" aria-hidden="true">
              <span>Draft 01</span>
              <i />
              <span>Draft 02</span>
              <i />
            </div>
            <span className="label">After a rethink</span>
            <h3>The next draft</h3>
            <p>
              Prepare an editable scene, compare saved revisions and re-screen. Where available,
              suggested wording comes verbatim from the register.
            </p>
            <p className="format-detail">A person makes the final decision</p>
          </article>
        </div>
      </section>

      <section className="process-section" id="how-it-works" aria-labelledby="process-heading">
        <div className="section-intro">
          <p className="eyebrow">03 / Your review, with receipts</p>
          <h2 id="process-heading">
            Less searching.
            <br />
            <em>More context.</em>
          </h2>
          <p>
            Follow a claim from the creative to the source. Keep the judgement with the person
            reviewing it.
          </p>
          <a className="text-action" href="#workspace">
            Put an ad on the desk <span aria-hidden="true">↗</span>
          </a>
        </div>
        <ol className="process-list">
          <li>
            <span>01</span>
            <div>
              <h3>Bring the creative</h3>
              <p>
                Upload a script, image or video. The workflow reads the available speech, text and
                visual context.
              </p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <h3>Go straight to the evidence</h3>
              <p>
                Select a claim to see its source line, video passage or image region, alongside the
                dated policy sources behind a flag.
              </p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <h3>Decide what changes</h3>
              <p>
                Investigate the reasons, revise your creative and check again. A script check does
                not replace screening the finished ad.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <section className="data-section" id="data-handling" aria-labelledby="data-heading">
        <div>
          <p className="eyebrow">Know what goes where</p>
          <h2 id="data-heading">
            Clear boundaries.
            <br />
            No fine-print promises.
          </h2>
        </div>
        <div>
          <p>
            Screening uses the Meta Model API in Standard mode, which does not use your inputs for
            training. The upload desk shows the retention period before you send a file.
          </p>
          <p>
            This build is a local prototype without account-based access controls. Do not upload
            confidential ads. Examples in the gallery are labelled reconstructions or synthetic
            creative.
          </p>
          <a href="/docs">Explore the API documentation ↗</a>
        </div>
      </section>

      <section className="faq-section" id="questions" aria-labelledby="faq-heading">
        <div className="section-intro">
          <p className="eyebrow">A few useful answers</p>
          <h2 id="faq-heading">
            Before you
            <br />
            <em>send it live.</em>
          </h2>
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
              The GB nutrition and health claims register, the CAP Code rule pack and the ASA
              rulings index held by the project. Each result identifies the dated snapshots used.
              On-hold claims are shown separately.
            </p>
          </details>
          <details>
            <summary>Can I start with a script?</summary>
            <p>
              Yes. Upload UTF-8 .txt or .md and use VO: and SUPER: to distinguish channels. Evidence
              refers to exact source lines. Screen the finished creative separately to check what
              actually appears and is heard.
            </p>
          </details>
          <details>
            <summary>What if a model stage fails?</summary>
            <p>
              The result is marked incomplete and identifies the stage that did not finish. An
              incomplete screening is never presented as a clean result.
            </p>
          </details>
          <details>
            <summary>Can I use it for confidential client work?</summary>
            <p>
              Not in this local prototype. It has no account-based isolation or production
              authentication. Do not upload confidential material.
            </p>
          </details>
        </div>
      </section>

      <section className="closing-section" aria-labelledby="closing-heading">
        <p className="eyebrow">A second look, before the world sees it</p>
        <h2 id="closing-heading">
          Give good creative
          <br />
          <em>a considered send-off.</em>
        </h2>
        <a className="primary" href="#workspace">
          Screen an ad <span aria-hidden="true">↗</span>
        </a>
        <p>A script, an image or the finished cut. Your judgement stays yours.</p>
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
            Evidence before submission.
            <br />A second look for health and supplement creative.
          </p>
        </div>
        <nav aria-label="Product">
          <h2>Product</h2>
          <a href="/#workspace">Screen an ad</a>
          <a href="/#features">What it does</a>
          <a href="/#how-it-works">How it works</a>
        </nav>
        <nav aria-label="Resources">
          <h2>Resources</h2>
          <a href="/#questions">Questions & answers</a>
          <a href="/#data-handling">Data handling</a>
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
        <span>PreFlight / Built for considered decisions</span>
        <p>{NOTICE}</p>
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
        <a href="/">Back to the review desk ↗</a>
      </header>
      <main className="account-page">
        <section className="account-intro">
          <p className="eyebrow">The PreFlight review desk</p>
          <h1>
            Good creative.
            <br />
            <em>A second look.</em>
          </h1>
          <p>Keep the creative in view. Keep the evidence close. Keep a person in the loop.</p>
          <div className="account-note">
            <span>01 / Read the claim</span>
            <span>02 / Follow the source</span>
            <span>03 / Make the call</span>
          </div>
        </section>
        <section className="account-card" aria-labelledby="account-heading">
          <p className="eyebrow">{signup ? 'Make room for a second look' : 'Back to the desk'}</p>
          <h2 id="account-heading">{signup ? 'Create your account' : 'Welcome back.'}</h2>
          <p>
            {signup ? 'Already have an account?' : 'New to PreFlight?'}{' '}
            <a href={signup ? '/login' : '/signup'}>{signup ? 'Log in' : 'Sign up'}</a>
          </p>
          <div className="account-unavailable" role="status">
            <strong>Accounts are not connected in this build.</strong>
            <p>
              These pages preview the account experience. Sign-in and registration are unavailable,
              and this page does not collect credentials.
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
                {signup ? 'Create account' : 'Log in'} <span aria-hidden="true">↗</span>
              </button>
            </fieldset>
          </form>
          <a className="account-workspace" href="/">
            Continue to the local review desk ↗
          </a>
          <p className="account-fine-print">
            The local desk is not a private account. Do not upload confidential ads.
          </p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
