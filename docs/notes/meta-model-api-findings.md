# Meta Model API findings (P03)

Calls made on 31 Oct 2026 from a UK machine, with a pay-as-you-go key, by `scripts/smoke_models.py` plus two follow-up checks on SAM 3.1. Every input was made by us: a 30-second ad for a fictional brand ("Brightleaf Daily D") with a synthetic voiceover, a quiet chord under it, and three timed on-screen claims, plus a generated product shot. Raw outputs are in `data/raw/smoke/` (git-ignored). Docs read the same day: `dev.meta.ai/docs` (models, pricing and rate limits, structured output, video understanding, speech to text, image generation, SAM segmenting and reading output).

Costs are the measured usage multiplied by the published prices. The account's billing page has not been checked against them.

## Summary

| Model | Called | Result | Measured | Cost |
|---|---|---|---|---|
| `muse-spark-1.3` structured output (text) | yes | Valid JSON against a strict schema; 4 claims found | 17.2 s; 64 in, 4,225 out (4,129 reasoning) | $0.018 |
| `muse-spark-1.3` image | yes | Read both lines of on-screen text exactly, including the small-print footnote | 3.6 s; 1,217 in, 428 out | $0.003 |
| `muse-spark-1.3` video (30 s, Files API) | yes | On-screen text with correct start and end seconds; spoken claims listed but their times are wrong | 14.8 s; 8,210 in, 2,553 out | $0.021 |
| `muse-voice-transcribe-1.0` | yes | Accurate transcript with music underneath; one turn for the whole voiceover | 7.9 s for 30 s of audio | $0.0015 |
| `sam-3.1` image | yes | Nothing returned for any text prompt; objects found | about 2 s | $0.0025 per image |
| `sam-3.1` video | yes | One call returns stable object IDs across every frame | 18–22 s per 125-frame clip; first frame after 2–3 s | $0.20 per 1,000 frames |
| `muse-image-1.0` generate and edit | yes | Both worked; no block on a supplement with a health claim | 8 s per image | $0.01 per image |
| Muse Glimmer | no | Open weights only; not served by Model API. Baseten's `GET /v1/models` listed no Glimmer model on 31 Oct (it lists `meta-models/muse-spark-open`) | — | — |

`GET /v1/models` lists `muse-image-1.0`, `muse-spark-1.1`, `muse-spark-1.2`, `muse-spark-1.2-contributor`, `muse-spark-1.3`, `muse-spark-1.3-contributor`, `muse-voice-transcribe-1.0`, `muse-wonder-1.0` and `sam-3.1`.

## Muse Spark 1.3

- **Standard and Contributor mode are separate model IDs.** `muse-spark-1.3` is Standard mode, and the response echoes that ID. Contributor mode is `muse-spark-1.3-contributor`. The docs mention no header or account setting. Rule 10 holds as long as the code never names a `-contributor` model.
- **Structured output** works on the Responses API through `text.format` with `{"type": "json_schema", "strict": true}`. With `strict` the schema must set `additionalProperties: false` and list every property in `required`. Recursive schemas are rejected, and nesting is capped at 10 levels.
- **Reasoning effort drives the cost.** On the same 64-token prompt, the default used 4,225 output tokens, `medium` 1,631 and `low` 996, taking 17.2 s, 7.8 s and 5.7 s. The pipeline should set the effort per stage and record it with the prompt version.
- **Video:** upload with `files.create(purpose="user_data")`, then pass `{"type": "input_file", "file_id": ...}`. A 30-second 720p clip with audio cost 8,210 input tokens.
- **Spark reads on-screen text from video well.** All three timed overlays and the footnote were read with start and end times correct to the second.
- **Spark's timing of speech in video is wrong.** It spread the voiceover across the full 30 seconds; in fact it ends at 16.2 s. Its spoken text was right. The docs say audio is not fully supported on 1.3.

## Muse Voice Transcribe

- `POST /v1/asr/transcribe`, multipart: a `request` JSON part (`mode`, `model`, `audioEncoding`) and an `audio` part. Audio must be WAV, mono, 16-bit PCM at 16 or 24 kHz, at most 10 minutes and 32 MB.
- **There are no word-level timestamps.** The docs say they are not available. The output gives turns with `startMs` and `endMs`. In `DIARIZATION` mode the whole voiceover came back as one turn (60–16,220 ms), because the synthetic voice has no long pauses. A real ad with pauses may split into more turns; that is untested.
- The transcript was accurate under music, apart from "moms" for "mums" and two repeated words.

## SAM 3.1

- **SAM does not find text as a concept.** "text overlay", "text", "caption", "subtitle", "words" and "banner" returned nothing on our ad frame, and "text" returned nothing on the product shot, whose label is covered in text. There was no error: the response is simply empty.
- **SAM finds the visual shapes text sits on.** "black rectangle" returned the box behind the headline exactly (x 394–884, y 503–563). "label" returned the bottle's label, and "bottle" the bottle. Text without a background shape (our footnote) cannot be found this way.
- **One video call tracks objects across frames.** On a 5-second, 125-frame clip, "bottle" kept ID 0 on all 125 frames and "gummy bear" kept 15 IDs stable throughout. This answers P25: one call per prompt per video, not per frame.
- **Output** is one text line per frame, streamed as `response.output_text.delta`: `<Nf>` frame index, then each object as `id<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..;c=..|><|mask;x=..;y=..;c=..;data=...|>`, with objects on one line joined by commas. `w` and `h` are the frame size, not the box size, and `c` is the confidence, present when `include_confidence` is set. An image call returns a single `<0f>` frame. Checked on 31 Oct (P22) with two drawn rectangles in one frame. Masks can reach about 20,000 characters per frame and use characters outside plain base85, such as `{`, so masks belong on disk, never in logs.
- `usage` reports `images_processed` or `video_frames_processed`. A 15-frame clip at 5 fps was billed 50 frames, the per-request minimum.
- **Video is billed on every frame the server decodes.** Our 30-second clip at 25 fps was billed 750 frames ($0.15), and each request is billed at least 50 frames. Re-encoding at a lower frame rate before upload is the only way to cut this. The plan's estimate of 60 frames per 30-second ad assumed we chose the frames.
- Accepted video: MP4 or MOV with H.264, H.265 or MPEG-4; up to 15,000 frames; up to 16 objects per frame.

## Muse Image

- The `size` parameter is ignored: `256x256` returned a 1600x1600 image of about 2.6 MB (31 Oct, P22).
- Generation returns WebP by default. The edit endpoint rejects a WebP declared as PNG, so request `output_format="png"` or declare the true type.
- Generating a supplement bottle with "Supports Bone, Immune & Mood Health" on the label, and then adding "Boosts Immunity" by edit, were both allowed. A content block would return 400 with `code: content_policy_violation`. The docs list no rule on health products.
- The model invents label text that wasn't asked for (dosage, flavour, "Supports Bone, Immune & Mood Health"). A reconstruction built with it must be checked so that it carries only the claims from the ruling's ad description (rule 8).

## Limits and credits

- Rate limits are per team, shared by every key: 3,000 RPM and 4M TPM for Spark 1.3 Standard, 3,000 RPM for SAM, 150 RPM for Muse Image, 256 concurrent transcription streams.
- Credits ($150 per accepted participant) are claimed individually with a form, using the team ID from the dev.meta.ai URL. A card is required, and spending beyond the credits is charged. A spend-limit alert does not stop billing.

## What this changes in the plan

1. **P24 (transcription): word timestamps must come from somewhere else.** Options: accept turn-level timing and tie claims to turns; split audio on silences first, so each short clip gets its own turn; or align words locally with an open-source aligner. This is a founders' call because it affects how precise the evidence timestamps are.
2. **P25 (on-screen evidence): Spark should read on-screen text straight from the video**, with its own start and end times. SAM keeps the visual job: the product, labels, before/after shots and boxed captions, through shape prompts such as "label" or "black rectangle", tracked in one call.
3. **Cost model:** a 30-second ad costs about $0.15 in SAM at native frame rate, or about $0.03 if re-encoded at 5 fps, plus about $0.02–0.05 in Spark at low or medium effort. A 60-item benchmark run stays under $15.
