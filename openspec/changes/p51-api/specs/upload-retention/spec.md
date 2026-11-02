# Upload retention

## Purpose

Keep confidential uploads and their derivatives inside a bounded retention lifecycle
without exposing file contents, user filenames or machine paths in operational logs.

## ADDED Requirements

### Requirement: Upload storage is private and bounded
The API SHALL stream supported media directly into private storage, impose a byte
limit, and use server-generated opaque identifiers instead of client filenames.

#### Scenario: Excessive upload
- **WHEN** an upload exceeds the configured byte limit
- **THEN** the request is rejected and its partial file is removed

### Requirement: Retention covers derived artifacts
Expired uploads and associated derived artifacts SHALL be deleted automatically.
Active jobs SHALL retain their inputs until processing ends, then become eligible
for deletion. Storage/deletion events SHALL contain only opaque IDs and timestamps.

#### Scenario: Expiry
- **WHEN** the retention deadline passes and no active job holds the upload
- **THEN** media, caches, screenings, fix outputs and private audits are removed

#### Scenario: Active processing
- **WHEN** an upload expires during processing
- **THEN** deletion waits for processing to end and does not interrupt it

### Requirement: Private content is absent from public errors
Validation and processing errors SHALL omit supplied captions, media contents,
filenames, filesystem paths and exception messages.

#### Scenario: Private text in an invalid request
- **WHEN** a request includes private text that fails validation
- **THEN** the error response does not echo that text
