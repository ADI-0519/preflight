# Hackathon rules (P01)

Read 31 Oct 2026. Sources: the participant FAQ and the rules summary posted to participants (copied from the participant channels by a founder), and the public event pages `cerebralvalley.ai/e/meta-ai-developer-hackathon` and `dev.meta.ai/events/global-hackathon`. Both public pages still say the Official Rules "will be published before the Hackathon begins" and link only the application overview and event waiver. **The formal Official Rules document itself has not been read yet**; where it may say more than the summary (IP, licences, third-party content), that is marked below.

## What the rules fix

| Topic | What they say | Effect on us |
|---|---|---|
| Judging | Entries must fit a theme and "meaningfully use Meta Model API and/or Meta open-weight models". Then they are "scored equally" on impact, use of Meta AI tooling, technical depth and execution, and demo quality. The top 5 per track go to the finals. | The 30/25/25/20 weights in our research were wrong: the four criteria are equal. |
| Startup track | "Judged on technical execution and whether it holds up in production" (event page). Prizes $250k, $150k, $75k, $50k, $25k. | Unchanged: the measured benchmark is our case for "holds up". |
| Bonus awards | Most Viral Project $20k (demo posted on X, engagement to 8 Nov); Best Build on Meta Open Weight Models $10k; Community Vote $10k (voting from 9 Nov); Best Agentic Use-Case $5k; Best Creative Build $5k. How each is judged beyond this is not stated. | The fix loop (P41) fits Best Agentic Use-Case; Glimmer triage (P43) is our only route to the open-weights award. |
| Video | 3 minutes, required, "one of the main things judges score". Judges assess the video, the code and the live product. | P54 as planned. "Live product" suggests a running demo may be looked at, not only the video. |
| New work | "Everything you present has to be built during the hackathon, Oct 26 to Nov 4." Building on an existing project requires a fresh repo with only event work, and the video must open with one line saying what was pre-existing. | Our repo starts on 27 Oct, so it qualifies. The research done before 26 Oct is not code; the video can still say that the idea was researched before the event. |
| Repo | "Your submitted repository must be public." | P55 as planned. |
| Changing idea or track | Each project picks one track. Nothing says the idea may not change after acceptance. | No constraint found. |
| Team | Up to 4 people. Everyone involved must be an approved participant, and no more approvals are being made. One representative submits, and every contributor's name goes on the submission. | Check that all three founders were approved and are listed (below). |
| Banned projects | Disqualified if they break legal, ethical or platform policies, or "use code, data or assets you don't have the rights to". Ideas to avoid include "AI medical or health advice" and "Nutrition coaches". | See gate 1. PreFlight checks ads against rules and gives no health advice to anyone, but the overlap in wording is worth confirming with the organisers. |
| Non-Meta models | Not banned. Entries must use Meta models meaningfully; partner inference (Baseten, Modal, Fireworks) is offered for open weights. | A local open-source TTS for reconstructions (plan, open decision on voiceover) appears allowed; the screening path stays on Meta models. |
| IP and licences | Not covered by the summary or the FAQ. | Read in the Official Rules. |
| Naming third parties or showing third-party content | Only the general rule on assets without rights. | Read in the Official Rules; see gate 1. |
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

- [ ] A founder reads the formal Official Rules document (if it is linked from the logged-in event page) and fills in the IP, licence and third-party content rows.
- [ ] Gate 1 confirmed in writing by the organisers or the Official Rules.
- [ ] All three founders confirmed as approved participants and on the team.
