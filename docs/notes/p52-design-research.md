# P52 design research and proposed direction

## Chalk and petrol light appearance, 4 November 2026

At the user's request before committing/pushing, refined light appearance to chalk
and white surfaces, ink text and a deep petrol accent. This supersedes the vermilion
light palette below. The neutral background is lighter and less blue-grey; the
accent is concentrated in headings, identity and actions. Dark appearance keeps its
steel/copper palette, including its previous evidence-highlight colours. Review-tier
red/amber remain separate. No layout, model, authentication or screening behaviour
was changed in this follow-up.

## Porcelain, graphite and vermilion, 4 November 2026

Following the user's request for a different, more futuristic colourway, replaced
the editorial pass's olive/cream palette with cool porcelain, graphite and a
controlled vermilion action accent. Dark appearance uses blue-black steel surfaces
and a lighter copper accent. Evidence highlights use muted steel blue, separate
from both the action colour and the labelled red/amber review tiers. No glow,
neon gradients, additional decoration or new dependency was introduced. Typography,
layout and all screening behaviour remain as in the editorial pass below.

## Editorial direction, 4 November 2026

This supersedes the Linear visual direction below, following the user's request
for a more individual interface inspired by Granola and Chris Williams Art Gallery.
Inspected both live websites and their actual typography in Chromium:

- [Granola](https://www.granola.ai/) pairs its Quadrant display face with Melange
  body text, quiet white surfaces, an olive action colour and a prominent product
  workspace. The useful principle is the distinction between expressive introduction
  and readable working content. Neither proprietary typeface is copied.
- [Chris Williams Art Gallery](https://www.chriswilliamsart.com/) uses generous
  negative space, fine grid lines, small captions and asymmetrically placed artwork.
  Its WebGL presentation took a long time to load during inspection. Adopt the
  restraint and content hierarchy; keep the ad review desk directly usable with
  ordinary HTML controls, no loading gate, canvas navigation or borrowed artwork.

Implemented warm paper/ink surfaces, a restrained olive accent and a split entry
composition: a large Source Serif 4 headline beside an upload desk, then three
short workflow steps. Source Serif is already licensed and bundled; Inter remains
the working typeface for evidence and controls. The small document illustration
is original SVG built in the component. No third-party image, font request, new
framework or animation dependency is required. Light starts by default and a
quiet dark palette remains available. Removed the purple glow and backdrop blur.
Mobile stacks the same sections and keeps the upload notice and file input intact.

This is presentation work: the model configuration, evidence, source wording,
retention contract, report and evaluation split are unchanged. The merged P73
scoreboard selector is checked against the actual registry as well as fixtures;
the live page identifies `screen-20261104T052428`, v2 test, with all five metrics.
Retained source screenings/media for building that run's demo gallery are not
present locally, so a public gallery build remains unverified here.

## Linear visual direction, 4 November 2026

The user rejected the conservative initial refresh and explicitly requested Linear's
type/background style and glass-like elegance. Inspected the live Linear page's
computed styles: body/headings use Inter Variable with system fallbacks, on an
`rgb(8, 9, 10)` background. Also read Linear's
[redesign account](https://linear.app/now/how-we-redesigned-the-linear-ui), which
describes improving application chrome and views while bounding navigation changes.

The revised implementation uses Inter Variable v4.1 from the
[font's official repository](https://github.com/rsms/inter/tree/v4.1), self-hosted
with its SIL Open Font Licence. It replaces the previous Atkinson face in the active
stylesheet. Dark appearance now opens by default, including for light-system users;
an explicit light toggle is retained. The document declares the dark appearance
before React starts. Existing source, policy, retention and review wording remains.

The new appearance uses near-black charcoal, low-intensity background lighting,
translucent blurred panels, thin edge highlights and soft shadows. The entry surface
centres the primary task and groups the three explanatory steps below it. Loaded
results retain the two-panel evidence workflow. No copied Linear assets, new
framework or new model behaviour was introduced.

Built the actual page and inspected desktop entry/review captures, phone evidence
after scrolling, and light appearance. A separate Chromium capture confirmed the
Inter face was loaded rather than falling back, and measured a 390-pixel document
at a 390-pixel viewport. The full-page screenshot of an offscreen blurred surface
can omit compositor content; inspected its scrolled viewport capture as well.
Build, 8 unit tests, 23 browser scenarios (including contrast, keyboard and updated
dark-default/light-toggle checks), 696 non-live Python tests, Ruff and formatting
passed. Two Python tests skipped for environmental reasons; seven live tests were
deselected. No additional provider requests or benchmark changes were made.

This direction supersedes the typography, palette and system-preference default
described in the initial refresh below.

## Workspace refresh, 4 November 2026

The user asked for a more intuitive, contemporary product interface. Reviewed the
current [Lovable homepage](https://lovable.dev/) in the browser and visually inspected
its entry surface, [Linear's product features](https://linear.app/features), and
[Vercel's interface guidelines](https://vercel.com/design/guidelines). These are
references, not evidence that a particular appearance wins the hackathon.

Applied principles: make the starting action obvious; separate navigation from
content; give the media and evidence their own surfaces; disclose secondary input
details without hiding the screening or upload notices. Adopted a restrained cobalt
accent, cool neutral surfaces, sans-serif claim typography, clearer selected states
and rounded panels. Kept evidence-risk colours distinct from interface accents.
No copied assets, new font download, framework or dependency was introduced.

The entry screen now explains three actions (bring creative, follow evidence,
make the call) alongside one upload panel. The panel supports file selection and
drag-and-drop through the same existing upload function, rejects multiple dropped
files with a recoverable message and respects disabled/public-mode controls.
Format and retention details expand on demand; the upload terms stay visible.
The loaded workspace has a labelled creative panel, pill review navigation,
sans-serif quoted claims and separate evidence inspector. Mobile navigation uses
two rows and the video height leaves more room for claim selection.

Verification: production build, 8 frontend unit cases, 23 full browser scenarios,
696 non-live Python tests (2 environmental skips, 7 live tests deselected), Ruff
and formatting passed. The browser checks include contrast in both appearances,
keyboard selection, 200% content scaling, phone layout, recovery, revisions,
reports, script evidence and two new upload scenarios. Ten focused presentation
and upload scenarios also passed after mobile target sizing changes.

Direct inspection used the retained real-model video result on the restarted live
application: selected claims, changed appearance, opened the revision form and
returned to evidence. A separate browser capture at 390 pixels measured document
width 390, without horizontal overflow; inspected entry and review screenshots.
The final visual pass found wrapped step numbers on phones; gave their column a
fixed minimum width. This is engineering/exploratory verification, not a usability
study with representative agency reviewers. No new provider calls, benchmark
changes, fake dashboard metrics or public deployment were part of this refresh.

The earlier research below remains a historical account of the previous design.

Researched 1 November 2026 against implementation `dd0ba9b`. This note is the
research record and the proposal as it stood then; the direction was implemented in
`4b09f25`, and the shipped behaviour is described in [web.md](../web.md).

## Assessment of the current page

The current page implements the P52 functional paths, but its presentation needs
another pass. The cream/green palette, large Georgia headline, slogan and vertically
stacked forms were implementation choices, not requirements in
[issue #28](https://github.com/ADI-0519/preflight/issues/28).

On the retained video result at a browser viewport of 1511 × 870, the header takes
106 pixels, the introduction starts at y=155, the upload panel starts at y=603,
and the video starts at y=1018. A returning reviewer sees no ad or evidence in the
first viewport. The draft editor begins at y=2061. These are measured layout
positions, not user-study results. A functional test that finds the expected
element does not demonstrate that the page has a good visual hierarchy.

The principal problems are the amount of space before the task, weak separation
between entry and review states, an oversized text-list substitute for the time
axis, and a fix comparison that is buried in the page. Serif typography is not
inherently dated, nor does dark mode inherently make a product modern. The present
combination communicates an editorial website more strongly than a media-review
application. That is a design assessment, not an objective age classification.

## What the issue actually requires

| Requirement | Current position | Redesign implication |
| --- | --- | --- |
| Video, claim timeline, seek, crop, sources, suggested wording | Implemented and exercised with synthetic examples | Make the video and selected evidence the first visual focus; improve the time axis without changing evidence semantics. |
| Fix rounds side by side, ending in explicit review | Implemented, with server-side decision guards | Give comparison its own view; expose the changed wording and retained evidence near both rounds. |
| Demo reconstruction, screening, then ASA outcome/rules reveal | Implemented contract with labelled replay tests | Use the same viewer before and after reveal, preserving clear separation between the two results. |
| Scoreboard from the selected registered final test run | Reader and unavailable state implemented | Keep provenance, denominators and intervals visible; no decorative scores. |
| Notice on every screen | Present | Keep the full repository notice readable in each workspace state. |
| Three final demo items and one fresh ad | Fresh synthetic path checked; final P53 selections absent | Acceptance remains incomplete until the real selected assets are exercised. |
| Numbers from the registered final test run | Final selection absent | Acceptance remains incomplete until P33 supplies it. |

The React/TypeScript/Vite stack, FastAPI serving, SSE, no browser credentials and
no component kit without a concrete need are explicit issue constraints. A visual
refresh needs no backend rewrite or new frontend framework.

## Winner evidence: what was actually inspected

These are a small, selected set of winners, not a controlled study of winners and
non-winners. Their appearance cannot establish why they won. Repository screenshots
may also differ from the exact screen shown during judging.

| Project and verified award | Frontend evidence | Useful observation for PreFlight |
| --- | --- | --- |
| OrgLens, LlamaCon 2025 first place | [Creator's dashboard screenshot](https://github.com/TheCl3m/llama-hack/blob/c07af10f61a50e2e12b8600b3492504f952eb8ab/images/orglens-dashboard.png), visually inspected | Conventional dark sidebar/light workspace, prominent organisation graph, search and supporting counts. Its domain-specific graph is the distinctive product artifact. |
| Llama CCTV Operator, LlamaCon 2025 third place | [Creator's detected-event screenshot](https://github.com/torayeff/llamacon-hackathon-2025-sf/blob/3875f7874f7723421557a3ce5a09fbdd0fa76fbb/images/step_5.png), visually inspected | Large video beside an event inspector, with time, explanation and acknowledgement. Closest structural match to our evidence-review task. |
| GibberLink, ElevenLabs Worldwide 2025 global top prize | [Organiser announcement](https://elevenlabs.io/blog/announcing-the-winners-of-the-elevenlabs-worldwide-hackathon), [creator's demo repository](https://github.com/PennyroyalTea/gibberlink), [organiser walkthrough](https://showcase.elevenlabs.io/projects/p/gibberlink) | A conspicuous working transition between two communication modes gives the demonstration one memorable event. The organiser explicitly highlights the demo. We should give our evidence-to-revision transition similar clarity. |

The two LlamaCon placements are confirmed by
[Meta's official winner report](https://ai.meta.com/blog/llamacon-hackathon/).
The inference is to organise the interface around a visible domain task and a
convincing working transformation. It is not evidence that a particular colour,
CSS framework, animation library or amount of visual complexity improves winning
odds.

An additional caution from reading the public Compliance Wizards frontend source:
its current main page includes simulated analysis delays and sample transactions.
That does not establish what its full judging demo did. We should not adopt such
simulation for live progress or imply that a recording came from the current ad.
See the [creator's source](https://github.com/michaelwaves/llamacon-hackathon/blob/main/frontend/app/page.tsx).

## Relevant contemporary design references

| Reference | Why it is relevant | What to adapt |
| --- | --- | --- |
| [Linear's March 2026 interface refresh](https://linear.app/now/behind-the-latest-design-refresh) | A current first-party account of hierarchy, quieter navigation and restrained separation | Predictable actions, less prominent navigation, compact headers and considered information density. |
| [Linear's 2024 redesign process](https://linear.app/now/how-we-redesigned-the-linear-ui) | Includes visually inspected before/after product screenshots and a stress-testing process | Test hierarchy and appearance in complete screens with real content rather than approving isolated component samples. |
| [Frame.io review and approval](https://frame.io/features/review-and-approval) | A real media-review product; its full viewer screenshot was visually inspected | Dominant creative canvas, time-anchored evidence, adjacent inspector and precise playback controls. Its workflow features are references, not a reason to add collaboration/accounts. |
| [Raycast design rationale](https://www.raycast.com/blog/a-fresh-look-and-feel) and [current appearance guidance](https://manual.raycast.com/settings) | Task emphasis and contextual actions, with readable sizing and light/dark appearances | Make the next action easy to find and keep details secondary; shortcuts should remain optional. |
| [Framer 2025 award winners](https://www.framer.com/awards/) | First-party examples of deliberate typography, interaction and storytelling | Use the gallery for finish and identity. Its portfolio/marketing winners are not proof that cinematic scrolling belongs in an evidence workspace. |

Descript's [text-and-video editing workflow](https://www.descript.com/) is another
useful interaction reference: words connect directly to media. Our claim selection
should feel similarly direct, while preserving the distinction between exact
word timing and transcription-turn timing.

## Proposed visual direction

A precise, media-first review workspace. Default charcoal for the competition
viewer, with an equally considered light appearance for prolonged source reading.
This is a design hypothesis to compare with users, not a claim that dark mode
will win. Keep one muted mint accent for selection/action and amber for possible
breaches. Status meaning must also use words and shape; it cannot depend on colour.

| Decision | Proposal |
| --- | --- |
| Page structure | Compact application header, ad title/status, task navigation, then the work. Remove the large slogan once an ad or retained job is open. |
| Type | One well-spaced sans-serif family; tabular numerals for time/counts. Local system fonts initially, or a licensed self-hosted font later. No remote font dependency needed. |
| Surfaces | Three restrained surface levels, subtle dividers, roughly 6–10 px corner radii; stronger contrast for content than navigation. |
| Review | Approximately 55/45 canvas/inspector split on desktop; crop and evidence adjacent to the selected claim. Stack on mobile without losing the active selection. |
| Timeline | Actual time axis, claim markers and evidence spans, plus an accessible text list. Overlapping marks must remain individually selectable. Do not manufacture word precision from turn timing. |
| Inspector | Exact claim, evidence, reason, source/date and verbatim suggestion. Longer source detail expands within the inspector rather than displacing the video. |
| Comparison | Two visible rounds and a caption change view, clear round numbers, check status and sources. Image rounds compare images; video rounds compare rendered videos. |
| Action | One relevant primary action in each state. New-ad input is prominent at entry, secondary during review; explicit human review follows the final completed fix. |
| Motion | Short focus/selection/state transitions, with reduced-motion support. Show actual SSE stage transitions, without invented percentages or timed fake analysis. |
| Identity | A small custom visual motif based on evidence spans and frame brackets, consistent icon strokes, concise domain-specific labels. Avoid a checkmark/shield as the main brand mark because it may imply approval. |

The exploratory concept uses a simple frame-shaped mark. The concept
abbreviates source descriptions into linked identifiers; the shipped
inspector must retain the existing full provenance descriptions and evidence crops.

Avoiding a generic generated appearance is a matter of specific design decisions
and careful review, not an authorship detector: coherent spacing, real content,
state-specific actions, legible evidence and purposeful transitions. A generic
gradient hero, decorative orbiting objects, sparkle icons, repeated slogan cards
or invented trust badges would weaken that specificity. This is a recommendation
for this product, not a universal rule about those visual devices.

## Concrete states to design

1. **Entry:** concise purpose, upload zone with real supported formats/retention,
   and a secondary route to labelled demos. No fake project history.
2. **Processing:** source preview and actual stage states; an uncertain duration
   stays uncertain. An interrupted or failed stage has a visible recovery action.
3. **Review:** selected claim, matching media/crop, linked sources and exact
   wording in the first desktop work area. Full report remains reachable.
4. **Revise:** real editable still/captions/voiceover requirements, not a promise
   that opaque video layers can be reconstructed.
5. **Compare:** original and selected revised round, exact wording change and
   the check result. Human decision remains separate from model output.
6. **Demo:** reconstruction label and ruling ID; screen first, reveal later.
   Preserve an obvious visual distinction between our flags and the ASA outcome.
7. **Benchmark:** registered final rates, counts, intervals and run/source
   provenance; explicit unavailable state before the final run exists.

Do not consolidate overlapping extracted claims by changing their data or hiding
flags during this refresh. A presentation-only grouping would need to expose all
constituent claim IDs, flags and evidence, with separate regression checks.

## Demo structure informed by the research

The public [Meta event page](https://dev.meta.ai/events/global-hackathon) describes
working capability and technical execution as central to the tracks. Detailed
equal-weight criteria in our [rules notes](./hackathon-rules.md) come from the
participant-supplied summary; the formal rules remain a separate unresolved read.
General [Devpost guidance](https://info.devpost.com/blog/understanding-hackathon-submission-and-judging-criteria)
also includes usability, implementation and demonstration. It does not override
this event's rules or prove a winning recipe.

Proposed three-minute sequence, to rehearse and revise rather than treat as a
measured optimal formula:

| Time | Visible proof |
| --- | --- |
| 0:00–0:20 | A specific risky claim in an ad and the person who must review it. Put the actual product on screen immediately. |
| 0:20–0:55 | Select the claim; seek to its evidence; show the exact source and wording. Name the Meta model roles while their real artifacts are visible. |
| 0:55–1:25 | Reveal the ASA outcome for the reconstruction after showing our screening; show final registered evaluation counts when available. |
| 1:25–2:25 | Fresh editable draft, actual rendered revision, re-screened result and a legible original/revision comparison. Label any recording or time cut. |
| 2:25–2:45 | Explicit human review, audit record and one honest limit. No automatic publishing. |
| 2:45–3:00 | Recap measured evidence and the practical user benefit, without inventing accuracy or time-saved figures. |

## How to prove the redesign is better

Capture the old and new screens with the same ad, selected claim, viewport and
browser zoom. Have 3–5 people unfamiliar with the flow try both, alternating which
version they see first. That small test can reveal problems; it is not a
statistically representative preference study.

Record task completion, wrong turns and time to find the first flag, seek to it,
identify its rule, locate the exact suggested wording, compare rounds and explain
who decides whether the ad runs. Ask them to distinguish a synthetic replay, live
screening and ASA reveal. Compare task evidence before asking aesthetic preference.

Proposed acceptance checks for implementation:

- At 1440 × 900 and 1280 × 800, a retained result opens with the video and selected
  claim visible without scrolling through entry copy. Keep long evidence scrollable
  without obscuring the player or keyboard focus.
- At 390 px width and at 200% zoom, no page-wide horizontal overflow or hidden
  primary action. Full notice remains readable and does not cover controls.
- Keyboard users can select claims, play/seek, open sources, change views and
  complete the explicit review form; focus follows a predictable order.
- Target WCAG AA text contrast (4.5:1 for ordinary text, 3:1 for qualifying large
  text), plus focus and control checks. See [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
- Respect reduced-motion preference; [W3C's interaction-animation guidance](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)
  is AAA, adopted here as a design preference rather than mislabeled an AA rule.
- Keep all existing workflow/recovery browser tests passing and add layout/focus
  checks for the new views. Use stable, labelled synthetic fixtures for screenshots.
- No lost sources, altered suggestion text, hidden flags, pre-revealed ASA answers,
  unregistered benchmark values or browser model calls.

## Deliverables and scope

An ignored local interactive concept is at
`data/work/design-research/preflight-concept.html`. It supports dark/light
appearance, three evidence examples with actual video seek, a separate recorded
image-round comparison and an honest absent-demo/scoreboard state. It embeds only
existing synthetic media and receipts. Keyboard activation, the 0.14-second seek,
both themes, view switching and the 390 px stacked layout were checked in Chromium.
This is not a complete frontend: upload, crop presentation, actual round-media
comparison and the decision form are not implemented in the concept.

Third-party reference screenshots were visually inspected and kept only in the
ignored research directory; they are not proposed product assets. No external
design framework, subscription or animation package is needed for the next step.

Implement the agreed presentation direction in a bounded frontend pass, retaining
the existing API and product rules. First restructure the loaded-review state and
comparison, then polish entry/demo states, then repeat visual, keyboard and
workflow verification. P33/P53 remain independent acceptance dependencies.
