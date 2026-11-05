# Deploying to Google Cloud Run

PreFlight deploys as a single container holding the FastAPI service, the built web page and FFmpeg (`Dockerfile`). `deploy/cloud-run.sh` builds the image with Cloud Build and deploys it to Cloud Run. The deployed service always requires sign-in: Firebase Authentication with a code sent by email.

## Why the service runs as one instance

The service keeps state in memory and does long work after a request has returned, and the deployment settings follow from that.

- A screening runs for several minutes in a background thread after the upload request has been answered. With Cloud Run's default request-based billing the CPU is throttled once the response is sent, so the service uses instance-based billing (`--no-cpu-throttling`).
- Jobs, sessions and sign-in codes are held in the process, so the service is limited to one instance (`--max-instances 1`). A restart or a scale to zero ends any running job and signs every user out.
- Uploads are deleted after 24 hours and are kept on the container's in-memory file system, so no storage service is needed. That file system counts against the instance's 2 GiB of memory.
- Cloud Run allows outbound SMTP on port 587, which the sign-in email uses.

## Cost

Cloud Run's monthly free tier for instance-based billing is 240,000 vCPU-seconds and 450,000 GiB-seconds. At 1 vCPU and 2 GiB this covers about 60 hours of the service being up. An idle instance shuts down at most 15 minutes after its last request and costs nothing while scaled to zero. Building and storing the image may cost a few pence. Set a budget alert before the first deploy.

Free hosting does not make screening free, since every screening calls the Meta Model API on the configured key. For that reason the script refuses to deploy without `PREFLIGHT_ALLOWED_EMAILS` unless `ALLOW_ANYONE=1` is set. With `ALLOW_ANYONE=1` the service receives an empty allowlist, so any Google or email account can sign in, whatever `.env` says.

## One-time setup

1. Create a Google Cloud account at console.cloud.google.com, add a billing account and create a project. Note the project ID.
2. Under Billing > Budgets & alerts, create a budget (for example £1) with email alerts at 50%, 90% and 100%.
3. Install the Google Cloud CLI and sign in with `gcloud auth login`.
4. In the settings file the script reads (below), set `META_API_KEY`, the four `FIREBASE_*` values, `PREFLIGHT_SESSION_SECRET`, `PREFLIGHT_SMTP_HOST`, `PREFLIGHT_SMTP_USER` and `PREFLIGHT_SMTP_PASSWORD`, and normally `PREFLIGHT_ALLOWED_EMAILS`. The script stops if any of the first nine is empty. [README.md](../README.md#settings-env) explains each variable.
5. Make sure the ASA ruling pages are complete in `data/raw/rulings/` ([data/README.md](../data/README.md) explains how to fetch them). These pages are not in the repository. The image build fails if a page the precedent index needs is missing, so the fault shows at build time instead of at the first screening.

## Deploy

From a checkout of the branch to deploy, in a Bash shell (Git Bash on Windows):

```bash
PROJECT=your-project-id bash deploy/cloud-run.sh
```

The script:

1. reads settings from `ENV_FILE`, by default `../preflight/.env` beside the checkout, without printing secret values;
2. copies the git-ignored `rulings` and `demo` folders from `DATA`, by default `../preflight/data/raw`, into the build;
3. enables Cloud Run, Cloud Build, Artifact Registry and Secret Manager in the project;
4. stores `META_API_KEY`, `PREFLIGHT_SMTP_PASSWORD` and `PREFLIGHT_SESSION_SECRET` in Secret Manager, adding a version only when a value has changed and destroying older versions;
5. deploys the service `preflight` (`SERVICE`) in `europe-west1` (`REGION`) with the remaining settings as plain environment variables;
6. prints the service address, `https://preflight-<project number>.europe-west1.run.app`.

After the first deploy, add that host name under Firebase > Authentication > Settings > Authorized domains, or Google sign-in will refuse it. Running the same command again deploys a new version.

The service answers only on the host names in `PREFLIGHT_ALLOWED_HOSTS`. The script sets that list to the printed address and the service's older `*.a.run.app` address, which is where Firebase Hosting forwards requests. The older address exists only once the service does, so on a first deploy that uses Firebase Hosting the script must be run twice. When `SITE` names a Firebase Hosting site, `<SITE>.web.app` and `<SITE>.firebaseapp.com` are added as well.

### Public mode

Two further variables set the limits for a deployment open to the public:

- `PUBLIC_MODE` (default `on`) sets `PREFLIGHT_PUBLIC_MODE`. With `on`, each signed-in account may make 10 uploads, start 3 screenings and run 1 fix an hour, a fix runs a single round, and uploads are limited to 150 MiB and 60 seconds of media. With `replay`, uploads are refused and only the preloaded demos run.
- `DAILY_CAP_USD` (default 10) sets `PREFLIGHT_DAILY_CAP_USD`, the total model spend allowed per day across all users. Once it is reached, new screenings are refused until midnight UTC.

Cloud Run refuses any request body over 32 MiB, so the web page sends files larger than 16 MiB in parts ([docs/api.md](api.md#uploading-in-parts)).

The project's own deployment lets any account sign in, under the public-mode limits:

```bash
ALLOW_ANYONE=1 SITE=preflight-ai PROJECT=preflight-513720 bash deploy/cloud-run.sh
```

## A web.app address

A Cloud Run address cannot be renamed, and a custom domain costs money. Firebase Hosting provides a free `<name>.web.app` address that forwards every path to the service. A Hosting rewrite can reach Cloud Run only in the same Google Cloud project, so the Hosting site must be created in the project that runs the service. For the project's deployment, the site `preflight-ai` in project `preflight-513720` has a single rewrite of `**` to the service `preflight` in `europe-west1`. Both `preflight-ai.web.app` and `preflight-ai.firebaseapp.com` are authorised domains in the Firebase project used for sign-in.

Two Hosting limits affect the service. Hosting forwards only one cookie, named `__session`, so the session cookie and the half-signed-in state both use that name. Hosting also ends a forwarded request after 60 seconds, so the progress stream of a long screening reconnects; the run.app address has no such limit.

## Checks after a deploy

- `https://<address>/health` answers `ready`.
- The page opens signed out on the landing page, and signing in sends a code by email.
- Logs: `gcloud run services logs read preflight --region europe-west1 --project <project>`.

## What the image holds

The image holds `src`, `prompts`, `results`, `eval/splits`, `data/snapshots`, the built web page, and the git-ignored `data/raw/rulings` and `data/raw/demo`. The split lists are included because they keep the held-out test rulings out of the precedent index. The image holds no `.env`, test items, ground truth or test media: `.gcloudignore` and `.dockerignore` exclude them, along with `tests` and `docs`. The only rebuilt ads it contains are the labelled demos listed in the manifest in `data/raw/demo`.

The ruling pages are uploaded to the project's private Cloud Build storage and image registry. They are never committed or published. The container runs as an unprivileged user, with one uvicorn worker, because jobs, sessions and sign-in codes live in that one process.
