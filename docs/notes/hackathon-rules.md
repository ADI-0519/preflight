# Hackathon rules (P01)

Initial review: 31 Oct 2026, using founder-supplied participant messages and public event pages.
Updated 4 Nov 2026 after reading the fully rendered
[Hackathon Terms & Conditions and Event Waiver](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver)
in the browser. The page identifies itself as the Official Rules; its judging weights
supersede the equal-weight statement in the earlier participant summary. Text-only web
fetches returned only a loading placeholder, while the browser exposed the full rules.
The public landing page still says the rules will be published later. The review records
what is published; it does not confirm individual eligibility, founder acceptance or
organiser permission for our use case or assets.

## What the rules fix

| Topic | What they say | Effect on us |
|---|---|---|
| Judging | The rendered Official Rules specify impact 30%, use of Meta AI tooling 25%, technical depth and execution 20%, and demo 25%. They distinguish these from application-selection criteria. | Corrects our earlier equal-weight statement. Use these project-submission weights in the pitch plan; check for participant updates before submission. |
| Startup track | "Judged on technical execution and whether it holds up in production" (event page). Prizes $250k, $150k, $75k, $50k, $25k. | Unchanged: the measured benchmark is our case for "holds up". |
| Bonus awards | Most Viral Project $20k (demo posted on X, engagement to 8 Nov); Best Build on Meta Open Weight Models $10k; Community Vote $10k (voting from 9 Nov); Best Agentic Use-Case $5k; Best Creative Build $5k. How each is judged beyond this is not stated. | The fix loop (P41) fits Best Agentic Use-Case; Glimmer triage (P43) is our only route to the open-weights award. |
| Video | 3 minutes, required, "one of the main things judges score". Judges assess the video, the code and the live product. | P54 as planned. "Live product" suggests a running demo may be looked at, not only the video. |
| New work | Founder-supplied participant messages require event-period work and a standalone extract/disclosure when building on an existing project. The Official Rules also require original work and rights to submitted components, allowing appropriately licensed open source. | Document event-period work and any earlier assets; the first Git commit alone does not prove eligibility or ownership. |
| Repo | "Your submitted repository must be public." | P55 as planned. |
| Changing idea or track | Each project picks one track. Nothing says the idea may not change after acceptance. | No constraint found. |
| Team | Up to 4 people. Everyone involved must be an approved participant, and no more approvals are being made. One representative submits, and every contributor's name goes on the submission. | Check that all three founders were approved and are listed (below). |
| Banned projects | Disqualified if they break legal, ethical or platform policies, or "use code, data or assets you don't have the rights to". Ideas to avoid include "AI medical or health advice" and "Nutrition coaches". | See gate 1. PreFlight checks ads against rules and gives no health advice to anyone, but the overlap in wording is worth confirming with the organisers. |
| Non-Meta models | Not banned. Entries must use Meta models meaningfully; partner inference (Baseten, Modal, Fireworks) is offered for open weights. | A local open-source TTS for reconstructions (plan, open decision on voiceover) appears allowed; the screening path stays on Meta models. |
| IP and licences | The Official Rules say entrants retain ownership and grant the organisers broad perpetual rights to use and adapt submitted material. Entrants must have the necessary rights; licensed open source is permitted subject to its licence. | Review the actual submission assets and dependencies. Do not include confidential partner material or assume public availability grants reuse rights. |
| Naming third parties or showing third-party content | The Official Rules require submitted work not to infringe third-party IP, contract or privacy rights. They do not explicitly resolve ASA-derived reconstructions. | Gate 1 remains open. Use team-made demo ads while permission is unresolved. |
| Eligibility | 18 or over; Meta and Cerebral Valley staff, contractors, government-affiliated people and their households are excluded (waiver). | Each founder confirms for themselves. |
| Credits | $150 of Model API credit per accepted participant, claimed individually by form by 4 Nov, 9 PM ET. A card is required; usage beyond the credit is charged. | Each founder claims their own. |
| Deadline | 4 Nov, 9:00 PM ET, at `cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit`. Late entries are not considered. | Unchanged. |

## Switch gate 1: may the demo show AI reconstructions of ads from published ASA rulings?

**Unclear.** Nothing in the summary or the FAQ mentions reconstructions, regulators' rulings or advertising. The rule that matters is disqualification for using "data or assets you don't have the rights to". Two facts bear on it:

- asa.org.uk publishes no reuse licence; its footer reserves copyright to the ASA and CAP (`docs/source-terms.md`).
- A reconstruction quotes the advertiser's claim wording from the ruling's ad description. Product rule 9 already removes branding.

Before P15 builds reconstructions, the team should get an answer to two questions, from the Official Rules or by asking the organisers in the participant help channel:

1. May the demo show AI-made reconstructions of ads described in public ASA rulings, with brands removed and short quotes of the claims?
2. Does a compliance screen for health-product ads fall under the "AI medical or health advice" category?

## Still to do

- [x] Agent read the rendered Official Rules on 4 Nov and updated judging, IP and third-party-content rows. Founders still need to review and accept the applicable rules themselves.
- [ ] Gate 1 confirmed in writing by the organisers or the Official Rules.
- [ ] All three founders confirmed as approved participants and on the team.
