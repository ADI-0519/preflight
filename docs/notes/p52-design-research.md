# P52 design research and proposed direction

Researched 1 November 2026 against implementation `dd0ba9b`. This is a proposal,
not a record of a shipped redesign. Runtime code is unchanged by this research.

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
