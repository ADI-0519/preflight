# Script screening

## Purpose

Let users screen an ad's written copy before production, with evidence anchored to its original lines
and a clear distinction between the script and the eventual finished ad.

## ADDED Requirements

### Requirement: Script evidence has an agreed product interpretation
Implementation SHALL begin only after all three founders agree that a script flag can cite a quoted,
numbered script line and that agreement is recorded in the dated decision log.

#### Scenario: Agreement is not recorded
- **WHEN** the proposed feature is ready for implementation without the required recorded agreement
- **THEN** it remains a proposal and the existing product rule is not silently amended

### Requirement: Script inputs preserve source line identity
The system SHALL accept bounded UTF-8 `.txt` and `.md` scripts, preserve their original physical line
numbers and wording, and distinguish optional `VO:` and `SUPER:` hints from unlabelled lines. It SHALL
treat markdown as literal text without executing markup or fetching referenced assets.

#### Scenario: Blank lines and channel hints
- **WHEN** a script contains a voiceover line, a blank line and an on-screen line
- **THEN** the nonblank lines retain source numbers 1 and 3, their exact wording and their channel hints

#### Scenario: Markdown contains an image link
- **WHEN** a script includes markdown with an image URL or HTML-like text
- **THEN** the source text remains text and no URL is fetched or HTML executed

### Requirement: Invalid scripts fail before inference
The system SHALL reject empty or whitespace-only scripts, invalid UTF-8, binary content and configured
size or line-limit violations before making any model call. Failure responses and logs SHALL omit the
script text.

#### Scenario: Invalid script upload
- **WHEN** a caller uploads a binary payload as a script or exceeds a script limit
- **THEN** a bounded content-free error is returned and no screening model is called

### Requirement: Script flags refer to existing source lines
Every script claim SHALL cite at least one existing script line. Script evidence SHALL include a positive
line number and the exact source line text; unknown lines or mismatched text SHALL fail validation.
Script evidence SHALL be valid only for script screenings.

#### Scenario: Fabricated evidence
- **WHEN** a claim cites line 3 with text different from the stored third source line
- **THEN** validation rejects that claim rather than showing invented evidence

#### Scenario: Script evidence attached to a media result
- **WHEN** an image, video or page result cites a script line
- **THEN** validation rejects it and the existing media evidence requirements remain in force

### Requirement: Script screening skips perception
CLI, API and agent-tool script screening SHALL use the shared screening path and existing policy checker.
Scripts SHALL bypass transcription, on-screen reading and region detection. Extraction SHALL use supplied
script lines without fabricated media, timestamps or visual observations.

#### Scenario: Script is screened with media clients disabled
- **WHEN** a valid synthetic script is screened while media clients fail on any invocation
- **THEN** extraction and checking complete using script lines and none of those clients is called

### Requirement: Script output is explicit about its limits
Every script result SHALL identify its script-only scope and state that the finished ad requires a separate
screening. A successful result without flags SHALL name the dated sources checked. A failed or unfinished
check SHALL remain incomplete, never a clean result.

#### Scenario: Script check finds no issues
- **WHEN** a script check finishes with zero flags
- **THEN** its result names the checked sources, identifies the script-only scope and requires a finished-ad check

#### Scenario: Checker fails
- **WHEN** extraction or checking fails or checking never finishes
- **THEN** the script result is incomplete and does not claim that no issues were found

### Requirement: Delivery surfaces show script evidence
The CLI, upload API, web workspace, HTML report and `screen_ad` tool SHALL support script screenings.
Each displayed flag SHALL retain its policy-source provenance and quoted numbered script evidence.
The web workspace SHALL navigate to the source line without depending on a media player or image crop.

#### Scenario: Reviewer opens a saved script result
- **WHEN** a reviewer opens a result, selects a flag, reloads it and opens its HTML report
- **THEN** the same quoted source line and policy evidence are accessible in each view

### Requirement: Scripts retain customer-data protections
Uploaded scripts and all their derivatives SHALL remain inside the upload's private retention boundary.
Public-mode quotas and expiry SHALL apply. Journals, progress events and application logs SHALL contain
metadata only; they SHALL NOT contain script text or filesystem paths exposed to customers.

#### Scenario: Script expires
- **WHEN** an uploaded script reaches its retention deadline
- **THEN** its source, derived script lines, results and model cache expire together under the existing policy

#### Scenario: Progress is streamed
- **WHEN** a script is screened with progress events enabled
- **THEN** progress identifies stage state without reproducing script text

### Requirement: Media compatibility survives the schema addition
New screenings SHALL use schema version 3, while valid stored version-1 and version-2 media screenings
remain readable. Scripts SHALL have no image dimensions, frame rate or duration, and media inputs SHALL
retain their current metadata and evidence validation.

#### Scenario: An old media result is loaded
- **WHEN** an existing valid v1 or v2 image or video screening is opened after the update
- **THEN** its evidence, vote information when present, result and report remain usable

### Requirement: Media fix controls do not fabricate script support
The initial script feature SHALL NOT offer image/video regeneration, media timeline controls or a
finished-ad approval based solely on a script result. Direct unsupported operations SHALL fail explicitly.

#### Scenario: A media fix is requested for a script result
- **WHEN** a caller tries to start the media fix workflow from a script screening
- **THEN** the operation is rejected with a clear unsupported-operation response
