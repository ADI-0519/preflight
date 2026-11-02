## ADDED Requirements

### Requirement: Evidence-led screening workspace
The page SHALL upload supported synthetic/ad media, follow SSE without polling,
and show source-verified claim evidence, exact source provenance and register wording.

#### Scenario: Select a video claim
- **WHEN** a viewer selects a claim in a completed screening
- **THEN** the video seeks to its cited time and the selected claim's evidence,
  sources and available exact-frame crop are shown

#### Scenario: Processing is incomplete or media expired
- **WHEN** a job fails, lacks a completed check or its retained data expires
- **THEN** the page explains the unavailable/incomplete result and cannot imply a
  clean screening or enable a review decision

#### Scenario: Loaded result presentation
- **WHEN** a retained result opens on a desktop viewport
- **THEN** the media and selected evidence appear without the entry-page introduction,
  appearance can change without resetting selection, and the full notice stays visible

#### Scenario: Overlapping evidence navigation
- **WHEN** multiple claims cite the same time
- **THEN** every claim remains independently keyboard-selectable on the time axis
  and full text list, with timing taken from its recorded evidence

### Requirement: Visible fix rounds and explicit human review
The page SHALL compare saved re-screened rounds and require an explicit human action
to record a decision on an eligible final draft, without claiming platform approval.

#### Scenario: Review an unflagged completed draft
- **WHEN** a person supplies their name, confirms reviewing the evidence and presses
  the review button after a completed unflagged fix
- **THEN** the server records their decision and the page retains it after reload

#### Scenario: A prior decision exists
- **WHEN** the page reloads an already-reviewed fix
- **THEN** it shows the persisted decision and no repeat review action

#### Scenario: Compare saved revisions
- **WHEN** a viewer selects two saved rounds
- **THEN** their rendered media and exact captions appear side by side on desktop,
  changed lines are highlighted, and mobile stacks the same content without overflow

### Requirement: Retention and private asset boundaries
The API SHALL confine media/crop reads to retained inputs or explicitly configured
demo assets, keep filesystem paths out of results and serve built static assets only.

#### Scenario: A crop attempts to escape its root
- **WHEN** a stored crop references a path outside its owning directory
- **THEN** the API rejects the asset request without exposing its contents
