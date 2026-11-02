# P52 redesign plan

Drafted 2 November 2026 against `adi-branch` at `5bcb4af`. This is a proposal for the
three founders to agree before any code changes. It builds on
[p52-design-research.md](./p52-design-research.md) and changes presentation only: the API,
the output schema and the page's behaviour stay as [web.md](../web.md) describes them.

Revised the same day after static mockups of every state, built from the replay server's
recorded data. The mockups moved the ad's words and the register wording to the top of
the inspector, replaced red flags with a highlighter yellow, and moved the reveal button
into the demo's title row. They are in the ignored folder `data/work/p52-redesign/`
(`mockups/` for the three directions and the first draft of each state, `variants/` for
the palette comparison, `v3/` for every state as this plan now describes it).

## What we are asked to agree

1. The direction: **Case file with a stage** (section 4), chosen from three (section 3).
2. Two additions to the repository: four self-hosted font files under the SIL Open Font
   Licence (about 57 KB in total), and the licence text beside them.
3. One markup change that alters test selectors: the claim list and the time axis become a
   single list of claim rows (section 7).
4. Which appearance we record the demo in. This plan recommends light; the page keeps
   following the viewer's system setting and keeps the switch.

## 1. What the current screens show

The replay server (`tests/web_replay_server.py`, no network access) was driven through
every state at 1440 × 900, 1280 × 800 and 390 × 844, in the dark appearance. The
screenshots are in the ignored folder `data/work/p52-redesign/before/` and can be
regenerated from the replay server. Positions below are measured from the top of the page.

| Measurement | 1440 | 1280 | 390 |
| --- | --- | --- | --- |
| Upload button on the entry screen | 647 px | 647 px | 710 px |
| Video in the evidence view | 519 px | 519 px | 689 px |
| First flag in the inspector | 702 px | 702 px | 1,596 px |
| "Reveal ASA outcome" in a demo | 1,570 px | 1,596 px | 2,881 px |
| Scoreboard heading in demo mode | 1,682 px | 1,709 px | 2,982 px |

The page works and breaks no product rule. Six problems remain, in order of how much they
cost the reviewer or the demo:

- **The reveal is out of sight.** In a demo, the ASA outcome and its button sit 670 px
  below the first screen on desktop and three and a half screens down on a phone. The
  demo's one decisive moment needs a scroll that viewers will not see coming.
- **On a phone the evidence comes last.** Every claim row, the time axis and the key come
  before the inspector, so the first flag sits at 1,596 px.
- **Colour says two things at once.** Amber marks a possible breach, a flag count of zero
  ("0 flags" on the cleaned round), and the changed wording in the comparison. A reader
  cannot tell a breach from a correction by colour, and the cleaned round looks flagged.
- **The notice covers headings.** The sticky screening notice overlaps content when the page
  scrolls to a heading: on the recorded-review screen it hides "Round 0" and "Round 1".
- **Processing shows nothing of the ad.** After upload the page says "Uploading ad…" over
  an empty screen, although the page already holds the uploaded file's address.
- **The generated tells.** A near-black ground with one mint accent; small tracked capitals
  above sections ("Evidence before submission", "Claim inspector", "Local workspace"); a
  62 px slogan; middle-dot strings; "↗" after links; 01/02/03 on time-axis rows; identical
  rounded panels for every block; 76% of the entry screen's text under 13 px.

## 2. What stays fixed

- **Product rules** ([product-rules.md](../product-rules.md)). The full screening notice is
  visible in every state. No text says an ad is approved, compliant, passes, safe or
  cleared. Every flag keeps its source and evidence. Suggested wording appears verbatim with
  its register ID. A person records the decision. Demo outcomes stay hidden until "Reveal".
  The scoreboard shows only the registered final run, or its unavailable state.
- **No API, schema or behaviour change.** Every element below is drawn from data the page
  already receives.
- **Content security policy allows only `'self'`.** Fonts are files under `web/`. No
  component kit or animation library is needed for this plan.
- **Tests.** The 14 browser tests and 6 unit tests keep passing; selectors change only where
  the markup does (section 7).

## 3. Three directions

All three keep Aditya's structure: a dominant canvas for the ad with an inspector beside it.
They differ in where the weight sits.

### A. Screening room (dark)

The whole page on true black, like a grading suite. The ad blends into its surroundings;
panels are lighter steps of black with no borders; colour appears only on the evidence
spans.

| Role | Hex |
| --- | --- |
| Ground | `#000000` |
| Panel | `#121314` |
| Raised | `#25272A` |
| Text | `#F2F2F2` |
| Secondary text | `#A9ADB3` |
| Flag | `#E8A93A` |

One face, Atkinson Hyperlegible Next. This is closest to the research note's proposal and
to Frame.io. It is also the commonest look of generated interfaces (a near-black ground
with one bright accent), and long CAP Code and register text reads less comfortably
light-on-dark. Not recommended.

### B. Case file with a stage (light, recommended)

A light, paper-like page for reading sources, with one black **stage** that holds the ad.
The ad is the only dark object on the screen, so it leads without a hero. Flags are marked
the way a compliance reviewer marks printed copy, with a highlighter; blue belongs to the
register alone. The ad's words and the register's words are set in a serif, as quotations
of two documents, and they lead the inspector. Section 4 gives the full system.

### C. Script (light, framed)

The ad's words become the main canvas. Every on-screen line and spoken turn is set in time
order as a script, with flagged claims marked in the margin; the video shrinks to a corner.
This follows Descript's text-and-media link. It suits spoken ads well, but an image ad has
no script, and judges would watch a column of text where they expect to see the ad. It also
goes against the research note's finding that review tools lead with the media. Not
recommended.

## 4. Recommended: Case file with a stage

### 4.1 The idea

The page shows two documents: the ad, and the register and code it is checked against.
**What the ad says** and **what the register allows it to say** are the two quotations
that matter, and they open the inspector as a pair: the ad's words, highlighted when
flagged, with where and when they occur; then the register wording, quoted exactly, with
its register ID beneath. Both are set in the same serif. When no register entry matches,
the second half of the pair says so in words, since rule 2 allows no suggestion then. The
reason and the sources follow the pair. The same pair returns in the round comparison:
round 0's line beside round 1's line.

The first mockups put the register wording at the end of each flag, after its sources. In
the magnesium demo that left it about 1,000 px down the inspector, and the first screen
showed nothing a generic review tool would not. Moving the pair to the top put the
product's argument on the first screen.

The signature element is the **claim track**. Under the stage, each claim is a row: its
start time, its words, and its evidence drawn as a span on the ad's time axis. Flagged
spans are highlighter yellow with an ink outline; claims on the on-hold list are hatched
yellow and ink; unflagged spans are grey. The playhead runs through every row. This
replaces both the numbered lanes and the separate claim list.

### 4.2 Colour

Light appearance (designed first):

| Name | Hex | Role |
| --- | --- | --- |
| Paper | `#F1F2F2` | page ground, a cool grey one step off white |
| Sheet | `#FFFFFF` | inspector, forms, round columns |
| Stage | `#000000` | behind the ad only: video, image, crop, round previews |
| Ink | `#16181B` | text, links (underlined), the one filled button, selection outline, focus ring |
| Graphite | `#5A5F66` | secondary text, unflagged spans, timecodes |
| Highlighter | `#FFD83A` | a fill behind flagged words and on flag marks; never text |
| Register blue | `#1F4E8C` | the rule beside register wording and its register ID; nothing else |

Dark appearance (kept for the switch and for viewers who prefer it):

| Name | Hex |
| --- | --- |
| Paper | `#000000` |
| Sheet | `#121314` |
| Raised | `#25272A` |
| Stage | `#000000`, set off from the page by a 1 px `#3A3D42` edge |
| Ink | `#F2F2F2` |
| Graphite | `#A9ADB3` |
| Highlighter | `#FFD83A`, unchanged |
| Register blue | `#93B8F2` |

Every text colour reaches 4.5:1 on each surface it sits on. Light: Graphite 5.3 to 6.4,
Register blue 6.9 to 8.3. Dark: Graphite 6.6 to 9.3, Register blue 7.4 to 10.4. Lines are
`#E3E5E7` on light and `#2A2C2F` on dark.

The highlighter is a fill, so it is checked as a graphic. Text on it is always `#16181B`
(12.8:1), in both appearances. On the light page the yellow alone reaches only 1.2 to
1.4:1 against paper, sheet and track, under the 3:1 that WCAG asks of graphics, so every
yellow mark on light carries a 1 px `#16181B` outline. On the dark page the yellow reaches
10.8 to 15.1:1 by itself.

What each colour may mean:

- **Yellow marks only a possible breach** (solid) or an on-hold claim (hatched yellow and
  ink), always with the words "Possible breach" or "On hold" in ink beside it. Shape and
  words carry the meaning too, so colour is never the only cue. A highlighter says "look
  here", where red would read as "failed", which is close to the verdict rule 1 forbids.
- **Blue means the register.** It appears on the rule beside the register wording and on
  the register ID. Every other link (CAP rules, the source report) is underlined ink, so
  blue never means "a link".
- **A clean or zero result is ink.** "No issues found against …" and "0 flags" carry no
  colour. A green state would read as "passed", which rule 1 forbids us to imply.
- **Changed wording in the comparison is marked by a 2 px ink underline on a grey tint**,
  so a correction never looks like a breach. The `<mark>` element stays.
- **The ASA ruling sits on an inverted panel** (ink ground, paper text), so the regulator's
  outcome is never confused with our flags.
- **The replay label** ("Network-blocked synthetic replay…") becomes a plain line in
  Graphite with a 3 px ink rule on its left, not an amber box.

### 4.3 Type

| Face | Use | Files |
| --- | --- | --- |
| Atkinson Hyperlegible Next, 400 / 500 / 700 | everything except quotations | latin subsets, about 12 KB each |
| Source Serif 4, 400 | the ad's words and the register's words, nothing else | latin subset, about 20 KB |

Atkinson Hyperlegible was drawn by the Braille Institute so that easily confused letters
stay apart (0 and O, 1, l and I). Our screens are full of strings where that matters:
register IDs such as `gbhc-e1f78000ec6b`, CAP rule numbers, timecodes. Its `tnum` feature
was checked in the font file, so timecodes and counts align without a monospace face.
Source Serif 4 marks quoted text as quoted, which makes rule 2 visible: the register
wording is someone else's exact words.

| Size | Line height | Use |
| --- | --- | --- |
| 22 px serif | 29 | the pair: the ad's words and the register wording |
| 20 px / 700 | 26 | screen title (the one `h1`), round headings |
| 16 px | 24 | flag reasons, form text; round lines in the serif |
| 14 px | 20 | rows, labels, source text, buttons, notice |
| 12 px | 16 | timecodes on the axis, the register ID, the two labels naming the pair |

Weights: 400 for text, 500 for labels and buttons, 700 for titles and the flag count.
Sentence case everywhere; no tracked capitals.

### 4.4 Layout

No sidebar: the product has two destinations. A 48 px top bar holds the PreFlight mark and
name, the two modes as underline tabs ("Screen an ad", "Explore demos") and the appearance
switch. The full notice sits directly under it as one line at 14 px. The bar and the notice
form one sticky block; the page's scroll padding equals that block's measured height, which
fixes the covered headings.

Grid, with one 24 px gutter used horizontally and vertically:

- 1440: 24 + 928 (stage) + 24 + 440 (inspector) + 24 = 1440.
- 1280: 24 + 792 + 24 + 416 + 24 = 1280.
- The stage keeps the full column width and is 16:9, capped at half the window's height
  (450 px at 1440 × 900); the ad is letterboxed inside it. Without the cap, the demo's
  extra rows pushed every claim row below the first screen in the mockups.
- At 1440 × 900 the first claim rows show beneath the stage, and the inspector shows the
  pair and the first flag's reason without scrolling.
- Below 900 px the inspector moves under the stage; below 640 px the page becomes the phone
  composition (section 4.6).

Surfaces: 8 px radius on the sheet and stage, 6 px on controls, 4 px on marks. A border or a
tone step separates surfaces, never a shadow; only the open select menu floats.

One filled button per state, in Ink: "Choose image or video", "Run fix and re-screen",
"Record my review decision", "Reveal ASA outcome". Everything else is a text button or an
outlined one.

### 4.5 States at desktop width

**Entry.** The empty stage is the upload target: a dashed 1 px slot (the one place dashes
appear) with the button inside it. Formats and retention sit beside it in plain lines. The
62 px slogan goes; the title is the action itself.

```
+------------------------------------------------------------------------------+
| [mark] PreFlight    Screen an ad   Explore demos              Light appearance |
| PreFlight screens ads against the dated sources named in this report. It is ... |
+------------------------------------------------------------------------------+
|  Screen an ad                                                    (h1, 20 px)   |
|  Upload one ad. Each claim is checked against the GB register, the CAP Code    |
|  and ASA rulings, with the evidence for every flag.                            |
|                                                                                |
|  +- - - - - - - - - - - - - - - - - - - - - - -+   Formats                       |
|  :                                             :   PNG, JPEG, WebP, MP4, WebM    |
|  :      Drop an image or video here            :   or QuickTime, up to 100 MiB   |
|  :      [ Choose image or video ]              :                                 |
|  :                                             :   Retention                     |
|  +- - - - - - - - - - - - - - - - - - - - - - -+   Local copies expire after     |
|                                                    24 hours.                     |
|  | Network-blocked synthetic replay. Responses are recordings, not ...          |
+------------------------------------------------------------------------------+
```

**Processing.** The uploaded ad appears on the stage at once. The stages arrive as an
ordered list from the server's events, each with its state in words (waiting, running,
done, failed). No percentages and no invented duration. A failed stage shows the existing
recovery message beside it.

```
|  Screening captions.mp4                                                        |
|  +---------------------------------------------+   Screening stages            |
|  |                                             |   On screen       done        |
|  |          (the uploaded ad, paused)          |   Transcribe      running     |
|  |                                             |   Regions         waiting     |
|  +---------------------------------------------+   Claims          waiting     |
|                                                    Check           waiting     |
```

**Evidence.** The title row holds the screening headline (the clean wording comes from the
server), the flag count, the view tabs and the report link. The stage and track are on the
left; the inspector is on the right.

```
|  Screening evidence  ▣ 1 flag       Evidence  Prepare revision   Full source report |
|  1 flag on 1 claim, checked against the GB register (2026-05-19), the on-hold ...   |
|  +------------------------------------------+  +------------------------------+     |
|  |                                          |  | ┃ The ad says                |     |
|  |               STAGE (video)              |  | ┃ ░"Clinically proven       | <- serif 22, highlighted
|  |                                          |  | ┃ ░ formula"░               |     |
|  +------------------------------------------+  | ┃ On screen, 0:04.0 to 0:07.0|     |
|  0:00      0:02      0:04      0:06     0:08    | ┃ Register wording           | <- blue rule when present
|  0:00.2  *Vitamin D contributes to... |▬▬▬▬▬▬▬▬|  | ┃ No register wording       |     |
|  0:01.0  Supports your immune system  |  ▬▬▬▬  |  | ┃ matches this claim. ...    |     |
|  0:04.0  Clinically proven formula    |    ▣▣▣ |  | ▣ Possible breach            |     |
|                                                 | Says "Clinically proven ..." |     |
|                                                 | Source provenance            |     |
|                                                 | CAP 12.1  Objective health...|     |
|                                                 | CAP 3.7   The marketer must..|     |
|                                                 +------------------------------+     |
```

`▣` is a highlighter-yellow mark with an ink outline; `░` is the highlight behind the
flagged words. When a register entry matches, as in the magnesium demo, the second half of
the pair is that entry, quoted in the serif with "GB register gbhc-e1f78000ec6b" beneath
it, and the sources below no longer repeat it. A claim with several flags shows the pair
once; a flag whose register wording differs from the pair's shows its own quotation under
its sources.

A selected row takes the Paper-to-Sheet tone step and a 2 px ink outline. Each row is one
button: its accessible name is the claim, its time and its flag state. Overlapping claims
keep their own rows, as now. For an image ad the rows have no spans.

**Prepare revision.** The scene still the reviewer chooses is shown on the stage straight
from the browser before upload. Beside the form, each flagged claim is listed with its
register wording, so the reviewer can copy the exact words into the captions field. The
form's labels and limits are unchanged.

```
|  Prepare revision                                                               |
|  +--------------------------+   Draft format   [ Image          v ]           |
|  |  STAGE: chosen still     |   Scene still    [ still.png  Choose ]          |
|  +--------------------------+   On-screen captions, one per line              |
|  Flagged in this ad            [ Magnesium tablets                    ]       |
|  "Beats fatigue in seven days" [ Beats fatigue in seven days          ]       |
|  Register wording, exactly:                                                   |
|  "Magnesium contributes to a   [ Run fix and re-screen ]                       |
|   reduction of tiredness..."                                                  |
```

**Compare rounds and review.** Two columns, each a round: its heading ("Round 0") and flag
count, its rendered draft on a stage, its screening headline, then its scene lines. A
changed line is underlined on a grey tint. Each column's round selector sits in its header.
The review form follows full width, split into what is being recorded (the final round and
its dated headline) and the form itself.

```
|  Compare rounds                                                                |
|  Round 0   6 flags     [Round 0 v]        Round 1   0 flags     [Round 1 v]     |
|  +----------------------------+          +----------------------------+        |
|  |  STAGE: round 0 render     |          |  STAGE: round 1 render     |        |
|  +----------------------------+          +----------------------------+        |
|  6 flags on 6 claims, checked ...         No issues found against the GB ...    |
|  Magnesium tablets                        Magnesium tablets                     |
|  Beats fatigue in seven days              Magnesium contributes to a reduction  |
|  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾ (changed)      of tiredness and fatigue (changed)    |
|                                                                                 |
|  Your review decision                                                          |
|  You are recording a decision on round 1.   Your name    [                ]     |
|  Its screening: No issues found against ... Review note  [                ]     |
|                                             [ ] I reviewed the final draft ...  |
|                                             [ Record my review decision ]       |
```

After recording, the form is replaced by the record: name, local time, note, and "This
records a person's decision, not Meta approval."

**Demo and reveal.** The demo items are a row of choices above the title, each with its kind
("Synthetic replay", or "Reconstruction" with its ruling ID). "Reveal ASA outcome" is the
filled button at the right of the title row, so it is on the first screen in every demo and
the closed state costs no height. A first draft gave the closed state its own full-width
band; in the mockups that band pushed the claim rows off the first screen. Once revealed,
the outcome opens as an inverted band between the title row and the workspace.

```
|  ( Synthetic replay · flagged ) ( Synthetic replay · no flags ) ( ... )          |
|  Synthetic replay · flagged  ▣ 6 flags            Evidence  [ Reveal ASA outcome ] |
|  6 flags on 6 claims, checked against the GB register (2026-05-19), ...          |
|  +------------------------------------------+  +------------------------------+  |
|  |               STAGE                      |  |  the pair, then the flags,   |  |
|  +------------------------------------------+  |  as in Evidence              |  |
```

Opened (inverted band, replacing the button):

```
|  ████████████████████████████████████████████████████████████████████████████  |
|  █ ASA ruling {ruling_id}, {date}: {outcome}. CAP rules {rules}.               █  |
|  █ PreFlight's screening and the ASA's ruling are separate results.         █  |
|  ████████████████████████████████████████████████████████████████████████████  |
```

Braces mark fields; the band prints only what the reveal endpoint returns. A synthetic item prints its message ("Team-made synthetic
fixture. No ASA outcome exists.") in the same band.

**Scoreboard.** In demo mode, below the workspace, under its existing heading "Registered
test scoreboard". Unavailable: one sentence giving the reason, as now, and nothing that
looks like a number. Available: the provenance line (run ID, split, revision) above a table
with right-aligned tabular figures and the registered counts, rates and intervals.

```
|  Registered test scoreboard                                                     |
|  Run {run_id} on split {split}, revision {git_sha}                                       |
|  Metric              Count        Rate     95% interval                          |
|  recall          {hits}/{total}   {rate}   {low} to {high}                       |
```

### 4.6 The phone

The top bar shrinks to 44 px; the notice stays sticky beneath it at 12 px (three lines). The
evidence view reads in this order: stage, the claim rows (44 px each, one line, flag mark at
the right), then the inspector with the pair at its top. In the phone mockup of the same
screening, the first flag sits at 891 px, against 1,596 px now. Demo choices become
one row that scrolls sideways, and the reveal button stays beside the view tab. Rounds
stack, each with its own selector.

```
+--------------------------+
| [mark] PreFlight   Light  |
| PreFlight screens ads ... |
| ... a person makes that   |
| call.                     |
+--------------------------+
| Screening evidence  1 flag|
| Evidence  Prepare revision|
| +----------------------+ |
| |   STAGE (video)      | |
| +----------------------+ |
| 0:00.2 *Vitamin D ...    |
| 0:01.0 Supports your ... |
| 0:04.0 Clinically pro… ▣ |
| The ad says              |
| ░"Clinically proven      |
| ░ formula"░              |
| On screen, 0:04.0 ...    |
| Register wording ...     |
| ▣ Possible breach ...    |
+--------------------------+
```

### 4.7 Motion

One moment: opening the reveal band (height and opacity, 200 ms). Everything else is a
response to an action: selecting a claim moves the playhead and cross-fades the inspector
(120 ms); buttons and rows change tone on hover and press. Nothing animates on load.
With reduced motion set, changes are instant.

### 4.8 Words

| Now | Proposed | Reason |
| --- | --- | --- |
| "Every claim. Back to its source." (62 px) | "Screen an ad" (20 px title) | names the task |
| "Evidence before submission", "Claim inspector", "Local workspace" | removed | labels that say nothing the layout does not |
| "On screen · 0:04.0–0:07.0" | "On screen, 0:04.0 to 0:07.0" | no middle-dot strings in our own text |
| "Open full source report ↗", "CAP 12.1 ↗" | "Open full source report", "CAP 12.1", underlined ink | links open in a new tab, announced to screen readers; blue is kept for the register |
| "Claim inspector" heading over the claim | "The ad says" over the claim, "Register wording, exactly" over the register quote | each label names which document a quotation comes from |
| Lane numbers 01, 02, 03 | the claim's time and words | rows are claims, not a sequence |
| "Exact register wording · gbhc-…" | "Register wording, exactly" above; "GB register gbhc-…" below | ID beside the quote it identifies |
| Page title "PreFlight · Evidence before submission" | "PreFlight" | |

Demo titles come from the manifest and keep their own punctuation.

The rest of the page's own text follows four rules: an error says what failed and what to
do next, without "please" or an apology; no sentence explains how to use a control; plain
words replace internal ones ("a still image without text" for "a clean scene still", "each
round is re-screened" for "the fix loop"); and our strings join parts with commas, not
middle dots. For example, "Something went wrong. Please try again." becomes "The request
failed and the server gave no reason. Try again.", and "Select a claim to inspect its
evidence and seek the video." is removed. Text the server supplies (the notice, headlines,
flag reasons, source texts, the scoreboard reason and reveal messages) is unchanged, and so
are the labels the tests depend on.

Sentences built as a contrast ("X, not Y") are rewritten to state what is true. The rule
each one carries stays: "This records a person's decision, not Meta approval." becomes
"Recorded by a person in PreFlight. Meta has not reviewed this ad.", and "Timing covers the
whole transcription turn, not individual words." becomes "Timed to the whole spoken
passage."

## 5. Checked against generic defaults

We checked the first draft against the look that generated interfaces fall into, and
changed four things:

- **Accent.** The first draft kept Aditya's amber for flags on charcoal. Amber on near-black
  is the commonest generated palette, and it also forced amber to mean breach, zero and
  change at once. Flags got their own colour and shape, and change got an ink underline.
- **Figures.** The first draft set timecodes and IDs in a monospace. Small monospace labels
  are a generated tell; Atkinson's tabular figures do the alignment instead.
- **Panels.** The first draft gave every block the same rounded panel. Now only the stage and
  the sheet are surfaces; the track, title row and lists sit on the page.
- **Words.** The first draft labelled the register quote "Allowed wording". "Allowed" reads
  as a verdict, so the label became "Register wording, exactly".

The mockups then showed that the second draft carried none of the usual tells but still
read as a tidy, generic light app. Two causes were visible, and both were changed:

- **The signature was buried.** The register wording sat below the sources, so the first
  screen showed a grey page, a video and a card of text. The pair now opens the inspector.
- **The palette was the browser's own.** A link blue and an error red on light grey are
  each defensible, and together they are the default of every component kit. Flags now
  take a highlighter yellow, from the way compliance reviewers mark printed copy; blue
  is kept for the register alone, and links are underlined ink.

What remains distinctive: the black stage on a light page, the highlighted claim set over
the register's exact words, and the yellow marks on the claim track. None of these depends
on a gradient, an eyebrow label, a numbered list or a card grid.

Three weaknesses remain. The largest block on every screen is the ad, and the synthetic
test card (a flat green frame) fights the yellow; the real P53 assets will decide more of
the demo's look than any palette. Yellow is weak as a thin mark on the light track, so the
ink outline carries its shape, and we should check it on a projector before recording.
"The ad says" and "Register wording, exactly" are small labels above content; they stay
because each names the document its quotation comes from.

## 6. Product rules, screen by screen

| Rule | How the design keeps it |
| --- | --- |
| 1. Screening, not advice | Notice in the sticky header in every state; clean results in ink with the server's dated wording; no green state. |
| 2. Register wording only | Quoted in the serif exactly as received, with its register ID directly beneath; no truncation. When no entry matches, the pair says so and suggests nothing. |
| 3. Every flag cites and shows | Each flag keeps its reason, every source with rule number and text, and the evidence time and crop. |
| 4. A person decides | Review form unchanged; its record names the person and says it is not Meta approval. |
| Demo reveal | The band holds no outcome until the reveal endpoint answers; the stale-response guard is untouched. |
| Scoreboard | Renders only the API's registered run or its reason; no placeholder digits in the unavailable state. |

## 7. Tests

The browser tests depend on accessible names and a few classes. These stay: the
"Upload ad" label, the "Screening evidence" and "Source provenance" headings, the regions
"Ad and claim timeline" and "Selected claim evidence", `.viewer video`, `.headline`,
`.round h3`, `.round mark`, the "Left round" and "Right round" labels, the appearance
buttons, and `role="note"` on the notice.

One change: the claim list (`.timeline button`) and the axis rows (`.time-lane`, named
"Seek to claim N: …") merge into one list of claim rows, each a button that contains a
`<time>` element. Two places in `presentation.spec.ts` (the keyboard seek test and its
row-count check) and one in `workflow.spec.ts` (the seek check) would then target the merged
rows. Their assertions (selection state, seek to the recorded start time) stay the same. We
would add three checks: the reveal button is in the first viewport at 1440 × 900 in a demo;
at 390 px wide the selected claim's evidence starts within one gutter of the last claim row;
no heading sits under the sticky header after scrolling to it. The phone check tests that
order rather than a fixed position, because the number of flags in the recorded fixture can
change.

## 8. Where this departs from the research note

- **Light first, not charcoal.** Reviewers read long source text, and the demo will be
  watched as a compressed recording; we expect small light text on black to lose more
  detail there than dark text on light, though we have not measured it.
  The ad still leads because it sits on the only black area.
- **Highlighter yellow for flags and blue for the register, no mint accent.** One hue per
  meaning, as above.
- **The register wording leads the inspector.** The note orders the inspector as claim,
  evidence, reason, source and suggestion; we move the suggestion up beside the claim,
  so the change it proposes is seen first. Every source and the evidence still follow.
- **Serif for quotations.** The note proposes one sans family. The second face has one job
  and makes the verbatim rule visible.
- **One list instead of an axis plus a list.** The note asks for "an actual time axis …
  plus an accessible text list"; each merged row is both, and the timing semantics are
  unchanged (turn timing is still labelled as turn timing).

Everything else follows the note: a dominant canvas with an adjacent inspector, one
primary action per state, real stage events without percentages, and the demo order of
screening first and outcome on reveal.

## 9. Build order, once agreed

Work happens on a new branch from `adi-branch`. Each step is one commit with its tests, and
each passes `npm --prefix web run build`, `npm --prefix web test` and the browser suite.

1. Tokens, the two faces and their licence; the shell (top bar, sticky notice, scroll
   padding); copy changes.
2. The evidence workspace: stage, claim track, inspector.
3. Processing and entry.
4. Prepare revision and compare rounds with the review form.
5. Demo row, reveal band and scoreboard.
6. Phone composition and the three new layout checks.

After the build, every state is screenshotted at 1440, 1280 and 390 in both appearances,
measured for contrast, overflow and type sizes, and fixed until clean. The "before" images
listed in section 1 are the comparison.

## 10. Decisions for the founders

1. Agree the direction (B), or choose A or C.
2. Agree to add the font files (Atkinson Hyperlegible Next 400, 500 and 700; Source Serif 4
   400; about 57 KB; SIL Open Font Licence 1.1) under `web/src/fonts/`.
3. Agree to merge the claim list and the time axis, with the test changes in section 7.
4. Choose the appearance for the demo recording. Light is recommended.
