#!/usr/bin/env bash
# Deploys PreFlight to Google Cloud Run as one container (docs/deploy.md).
#
#   PROJECT=my-project bash deploy/cloud-run.sh
#
# Reads settings from ENV_FILE (default: the main checkout's .env) without printing secret values.
# Secret values go to Secret Manager; the rest become plain environment variables on the service.
set -euo pipefail

PROJECT=${PROJECT:?set PROJECT to the Google Cloud project ID}
REGION=${REGION:-europe-west1}
SERVICE=${SERVICE:-preflight}
HERE=$(cd "$(dirname "$0")/.." && pwd)
DATA=${DATA:-$HERE/../preflight/data/raw}
ENV_FILE=${ENV_FILE:-$HERE/../preflight/.env}
cd "$HERE"

say() { printf '\n== %s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
value() { grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r' || true; }

[ -f "$ENV_FILE" ] || fail "no settings file at $ENV_FILE (set ENV_FILE)"
command -v gcloud >/dev/null || fail "install the Google Cloud CLI and run: gcloud auth login"

for name in META_API_KEY FIREBASE_PROJECT_ID FIREBASE_API_KEY FIREBASE_AUTH_DOMAIN FIREBASE_APP_ID \
            PREFLIGHT_SESSION_SECRET PREFLIGHT_SMTP_HOST PREFLIGHT_SMTP_USER PREFLIGHT_SMTP_PASSWORD; do
  [ -n "$(value "$name")" ] || fail "$name is empty in $ENV_FILE"
done
# every screening calls the paid model API, so a public deployment names who may sign in
# ALLOW_ANYONE=1 lets any account in and ignores the .env allowlist, which then only applies locally
if [ "${ALLOW_ANYONE:-}" = "1" ]; then
  ALLOWED=""
else
  ALLOWED=$(value PREFLIGHT_ALLOWED_EMAILS)
  [ -n "$ALLOWED" ] || fail "PREFLIGHT_ALLOWED_EMAILS is empty; set it, or run with ALLOW_ANYONE=1 to let any account in"
fi

say "Copying the git-ignored ruling pages and demo files into the build"
for dir in rulings demo; do
  [ -d "$DATA/$dir" ] || fail "missing $DATA/$dir (set DATA to the folder holding data/raw)"
  if [ "$(cd "$DATA/$dir" && pwd)" != "$HERE/data/raw/$dir" ]; then
    rm -rf "data/raw/$dir" && mkdir -p data/raw && cp -r "$DATA/$dir" "data/raw/$dir"
  fi
done
ls data/raw/rulings/*.html >/dev/null 2>&1 || fail "no ruling pages in data/raw/rulings"

say "Enabling Cloud Run, Cloud Build, Artifact Registry and Secret Manager"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com --project "$PROJECT"

NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
RUNNER="$NUMBER-compute@developer.gserviceaccount.com"
HOST="$SERVICE-$NUMBER.$REGION.run.app"
# source deploys build as the default compute account, which needs the builder role on new projects
gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$RUNNER" \
  --role roles/run.builder --condition None --quiet >/dev/null

say "Storing secrets in Secret Manager"
secrets=()
for name in META_API_KEY PREFLIGHT_SMTP_PASSWORD PREFLIGHT_SESSION_SECRET; do
  secret=$(printf '%s' "$name" | tr 'A-Z_' 'a-z-')
  wanted=$(value "$name")
  if ! gcloud secrets describe "$secret" --project "$PROJECT" >/dev/null 2>&1; then
    gcloud secrets create "$secret" --replication-policy automatic --project "$PROJECT" >/dev/null
  fi
  current=$(gcloud secrets versions access latest --secret "$secret" --project "$PROJECT" 2>/dev/null || true)
  if [ "$current" != "$wanted" ]; then
    printf '%s' "$wanted" | gcloud secrets versions add "$secret" --data-file=- --project "$PROJECT" >/dev/null
    # the free tier covers six active versions, so older ones are destroyed
    latest=$(gcloud secrets versions list "$secret" --project "$PROJECT" --filter state=ENABLED \
      --sort-by ~createTime --format 'value(name.basename())' | tr -d '\r' | head -n 1)
    # compare version numbers, not full names, without Windows carriage returns, or destroy picks the wrong one
    for old in $(gcloud secrets versions list "$secret" --project "$PROJECT" --filter 'state!=DESTROYED' \
      --format 'value(name.basename())' | tr -d '\r'); do
      [ "$old" = "$latest" ] || gcloud secrets versions destroy "$old" --secret "$secret" --project "$PROJECT" --quiet >/dev/null
    done
    echo "  $secret updated"
  else
    echo "  $secret unchanged"
  fi
  gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT" --member "serviceAccount:$RUNNER" \
    --role roles/secretmanager.secretAccessor --condition None --quiet >/dev/null
  secrets+=("$name=$secret:latest")
done

say "Building and deploying $SERVICE to $REGION (the build takes a few minutes)"
port=$(value PREFLIGHT_SMTP_PORT)
env_vars=(
  "FIREBASE_PROJECT_ID=$(value FIREBASE_PROJECT_ID)"
  "FIREBASE_API_KEY=$(value FIREBASE_API_KEY)"
  "FIREBASE_AUTH_DOMAIN=$(value FIREBASE_AUTH_DOMAIN)"
  "FIREBASE_APP_ID=$(value FIREBASE_APP_ID)"
  "PREFLIGHT_ALLOWED_EMAILS=$ALLOWED"
  "PREFLIGHT_SMTP_HOST=$(value PREFLIGHT_SMTP_HOST)"
  "PREFLIGHT_SMTP_PORT=${port:-587}"
  "PREFLIGHT_SMTP_USER=$(value PREFLIGHT_SMTP_USER)"
  "PREFLIGHT_MAIL_FROM=$(value PREFLIGHT_MAIL_FROM)"
  "PREFLIGHT_ALLOWED_HOSTS=$HOST"
)
# '|' separates the variables because the email allowlist itself contains commas
joined=$(IFS='|'; printf '%s' "${env_vars[*]}")
gcloud run deploy "$SERVICE" --project "$PROJECT" --region "$REGION" --source . \
  --allow-unauthenticated --min-instances 0 --max-instances 1 --cpu 1 --memory 2Gi \
  --no-cpu-throttling --concurrency 40 --timeout 3600 \
  --set-env-vars "^|^$joined" --set-secrets "$(IFS=,; printf '%s' "${secrets[*]}")" --quiet

say "Done"
echo "PreFlight: https://$HOST"
echo "Add $HOST to Firebase > Authentication > Settings > Authorized domains, or Google sign-in will refuse it."
