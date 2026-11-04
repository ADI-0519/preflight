# Deploying to Google Cloud Run

PreFlight runs as one container on Cloud Run's free tier: the FastAPI service, the built web page and FFmpeg
(`Dockerfile`). `deploy/cloud-run.sh` builds it with Cloud Build and deploys it. Sign-in (Firebase, with an
emailed code) is required on the deployed service.

## Why one Cloud Run instance

- A screening runs for minutes in a background thread after the upload request returns, so the service uses
  instance-based billing (`--no-cpu-throttling`); with the default request-based billing the CPU is cut when the
  response is sent.
- Jobs, sessions and sign-in codes live in the process, so there is exactly one instance (`--max-instances 1`).
  A restart or scale-to-zero ends running jobs and signs everyone out.
- Uploads are deleted after 24 hours by design and live on the container's in-memory disk, so no storage
  service is needed. The disk counts against the 2 GiB of memory.
- Cloud Run allows outbound SMTP on port 587, which the sign-in code email uses (Render's free tier blocks it).

## Free tier and what it costs

Cloud Run's monthly free tier (instance-based billing) is 240,000 vCPU-seconds and 450,000 GiB-seconds. At 1 vCPU
and 2 GiB that is about 60 hours with the service up. An instance stays up at most 15 minutes after its last
request and costs nothing while scaled to zero. Building and storing the image can cost a few pence. Set a budget
alert before the first deploy.

Hosting being free does not make screening free: every screening calls the Meta model API on the team's key.
The script refuses to deploy without `PREFLIGHT_ALLOWED_EMAILS` unless `ALLOW_ANYONE=1` is set. With
`ALLOW_ANYONE=1` the service gets an empty allowlist, so any Google or email account can sign in, whatever
`.env` says.

## One-time setup

1. Create a Google Cloud account at console.cloud.google.com, add a billing account and create a project.
   Note the project ID.
2. Billing > Budgets & alerts: create a budget of £1 with email alerts at 50%, 90% and 100%.
3. Install the Google Cloud CLI and sign in: `gcloud auth login`.
4. In the main checkout's `.env`, set everything `.env.example` lists for sign-in, the SMTP code email and
   `META_API_KEY`, and set `PREFLIGHT_ALLOWED_EMAILS`.
5. The git-ignored ASA ruling pages must be complete in `data/raw/rulings/` (see `data/README.md`); the image
   build fails if a page the precedent list needs is missing.

## Deploy

From a checkout of the branch to deploy, in Git Bash:

```bash
PROJECT=your-project-id bash deploy/cloud-run.sh
```

The script reads settings from `../preflight/.env` (`ENV_FILE`) and the ruling pages and demo files from
`../preflight/data/raw` (`DATA`), copies those two folders into the build, stores `META_API_KEY`,
`PREFLIGHT_SMTP_PASSWORD` and `PREFLIGHT_SESSION_SECRET` in Secret Manager, and deploys the service `preflight`
in `europe-west1` (`SERVICE`, `REGION`). It prints the service address,
`https://preflight-<project number>.europe-west1.run.app`.

After the first deploy, add that host name in Firebase > Authentication > Settings > Authorized domains, or
Google sign-in refuses it.

Run the same command to deploy a new version. The service only answers on the host names in
`PREFLIGHT_ALLOWED_HOSTS`, which the script sets to that address and the service's older `*.a.run.app`
address (where Firebase Hosting forwards; it exists only after the first deploy, so run the script twice the first
time), plus `<SITE>.web.app` and
`<SITE>.firebaseapp.com` when `SITE` names a Firebase Hosting site.

The team's deployment runs open to any account, under public mode's per-account limits:

```bash
ALLOW_ANYONE=1 SITE=preflight-ai PROJECT=preflight-513720 bash deploy/cloud-run.sh
```

`PUBLIC_MODE` (default `on`) sets `PREFLIGHT_PUBLIC_MODE`: each signed-in account may start 3 screenings,
1 fix and 10 uploads an hour, with uploads up to 25 MiB and 60 seconds. `DAILY_CAP_USD` (default 10) sets
`PREFLIGHT_DAILY_CAP_USD`, the day's model spend across everyone, after which new screenings are refused until
midnight UTC.

## A free web.app address

Cloud Run's own address cannot be renamed, and a custom domain costs money. Firebase Hosting gives a free
`<name>.web.app` address that forwards every path to the service. A Hosting rewrite only reaches Cloud Run in
the same Google Cloud project, so Firebase was added to `preflight-513720` and the site `preflight-ai` created
there, with a release whose only config is a rewrite of `**` to the service `preflight` in `europe-west1`.
`preflight-ai.web.app` and `preflight-ai.firebaseapp.com` are authorized domains in the sign-in Firebase
project.

Hosting forwards only a cookie named `__session`, which is why the session and the half-signed-in state share
that name. It also ends a forwarded request after 60 seconds, so a screening's progress stream reconnects
during long screenings; the run.app address has no such limit.

## Checks

- `https://<address>/health` answers `ready`.
- The page opens on the landing page signed out; a sign-in emails a code.
- Logs: `gcloud run services logs read preflight --region europe-west1 --project <project>`.

## What the image holds

`src`, `prompts`, `results`, `eval/splits` (the split lists that keep held-out rulings out of the precedent
pool), `data/snapshots`, and the git-ignored `data/raw/rulings` and `data/raw/demo`. It holds no `.env`, test
items, ground truth or team media; the only reconstructions are the labelled demos the manifest in
`data/raw/demo` names. The ruling pages reach Google's private build storage and
image registry in the team's project; they are never committed or published.
