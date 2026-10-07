# Equation Golf

Equation Golf is a daily game about approximating curves with equations. Each
day has a hidden target curve. You write the shortest expression you can that
matches it closely, then compare your score with the other players.

The project is a React/Vite frontend backed by a FastAPI application and
PostgreSQL. Google is used for sign-in, and the scoring code lives on the
server so the target equation is not exposed to the browser during an active
challenge.

## How the repository is organised

| Path | What it contains |
| --- | --- |
| `src/` | React interface, graphing, equation input, and client-side display logic |
| `backend/` | FastAPI routes, authentication, scoring, models, seeds, and challenge tools |
| `alembic/` | Database migrations |
| `tests/` | API, scoring, privacy, archive, generator, and importer tests |
| `api/index.py` | Vercel entry point for the FastAPI application |
| `compose.yaml` | Local PostgreSQL service |
| `data/production_challenges.json` | Private generated challenge artifact; intentionally ignored by Git |

## Run it locally

You will need Docker, Python 3.12, Node 22, and either Nix or equivalent
Python and Node tooling.

### 1. Start PostgreSQL

From the project directory:

```bash
docker compose up -d db
```

The local database listens on `127.0.0.1:5432` and uses the development
credentials from `compose.yaml`.

### 2. Set up the development shell

The Nix shell provides the project versions of Node and Python. It also
activates `.venv` automatically when that directory exists.

```bash
nix develop

export APP_ENV=development
export DATABASE_URL='postgresql+psycopg://equationgolf:equationgolf@127.0.0.1:5432/equationgolf'
```

If this is a fresh checkout and `.venv` does not exist yet, create it and
install the locked Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
npm ci
```

### 3. Load development data

The development seed applies the migrations and loads a local challenge set:

```bash
python -m backend.seed_dev
```

The seed is development-only. It expects
`data/production_challenges.json` to exist locally because challenge targets
are kept out of the public repository. You can generate that file with the
private seed described in [Production challenges](#production-challenges), or
copy it from a secure development location.

### 4. Start the application

Run the API and frontend in separate terminals, inside the development shell:

```bash
uvicorn backend.main:app --reload --port 8000
```

```bash
npm run dev
```

Open <http://localhost:5173> in your browser. In development, the frontend
sends API requests to `http://localhost:8000`; in a production build it uses
the same public origin as the page.

To stop the database later:

```bash
docker compose down
```

## Useful commands

```bash
# Backend tests; PostgreSQL must be running
pytest

# Frontend checks
npm run lint
npm run build

# Create tables directly, when needed for a local experiment
python -m backend.init_db
```

The test suite uses `TEST_DATABASE_URL` when it is set. Keep it separate from
`DATABASE_URL`; the tests create and remove their own test database when
possible.

## Deploy to Vercel

Vercel uses [`api/index.py`](api/index.py) as the FastAPI entry point and
[`vercel.json`](vercel.json) to route `/api/*` requests. From the repository
root, deploy with:

```bash
nix develop --command npx vercel --prod
```

Before deploying, add these variables to the Vercel project’s **Production**
environment. Use real values in Vercel or a secret manager, not in Git:

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://...
SESSION_SECRET=<at least 32 random characters>
FRONTEND_URL=https://your-domain.example
BACKEND_URL=https://your-domain.example
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

In the usual single-domain setup, `FRONTEND_URL` and `BACKEND_URL` are the
same public origin. Production startup refuses to run when the database URL,
public URLs, or a sufficiently long session secret are missing.

### Google sign-in

The Google OAuth client must contain this exact authorised redirect URI, with
your real domain substituted:

```text
https://your-domain.example/api/auth/google/callback
```

The client ID and secret in Google Cloud must match the values configured in
Vercel. After changing Vercel environment variables, deploy again so the new
values are used.

## Publish Docker images to Azure Container Registry

The GitHub Actions workflow tests and builds the backend and frontend on pull
requests and pushes to `main`. After a successful push to `main`, it publishes
both images to Azure Container Registry (ACR) and updates the backend and
frontend Container Apps to the commit-tagged images. Production deployments
are serialized, and the workflow verifies that each deployed revision is
healthy and running the expected commit-tagged image.

Configure Azure once:

1. Create an ACR and an Entra ID application/service principal for GitHub
   Actions. Add a federated credential that trusts this repository's
   `main` branch using the GitHub Actions OIDC provider:
   - Issuer: `https://token.actions.githubusercontent.com`
   - Subject: `repo:BrianGithubAcc/Equation-Golf:ref:refs/heads/main`
   - Audience: `api://AzureADTokenExchange`
2. Give that identity **Container Registry Repository Writer** access to the
   `equation-golf` and `equation-golf-backend` repositories in ACR. Since this
   registry uses repository ABAC permissions, scope the role assignment with a
   condition for those two repositories rather than using the legacy `AcrPush`
   role.
3. Give the identity **Container Apps Contributor** access scoped to the
   `equation-golf` and `equation-golf-api` Container App resources in the
   `equation_golf` resource group.
4. In the GitHub repository's **Settings → Secrets and variables → Actions**,
   add these repository secrets:
   - `AZURE_CLIENT_ID`
   - `AZURE_TENANT_ID`
   - `AZURE_SUBSCRIPTION_ID`
5. Add the repository variable `ACR_NAME` with the ACR resource name
   (`equationgolf`, not its `*.azurecr.io` login server).

Do not enable ACR's admin account or store a registry password in GitHub. The
workflow signs in through OIDC and needs no long-lived registry credentials.
After setup, pushing to `main` publishes and deploys:

```text
<your-acr>.azurecr.io/equation-golf-backend:latest
<your-acr>.azurecr.io/equation-golf-backend:<commit-sha>
<your-acr>.azurecr.io/equation-golf:latest
<your-acr>.azurecr.io/equation-golf:<commit-sha>
```

For a production Compose deployment, copy `.env.production.example` to
`.env.production`, set `ACR_LOGIN_SERVER` to the registry login server and
`IMAGE_TAG` to the image tag, then authenticate to ACR and deploy:

```bash
az acr login --name your-registry
docker compose --env-file .env.production -f compose.prod.yaml pull
docker compose --env-file .env.production -f compose.prod.yaml up -d
```

Use the same commit SHA for `IMAGE_TAG` to deploy the matching backend and
frontend images. Keep `.env.production` private; registry credentials should
come from the Azure/Docker login mechanism rather than that file.

### Azure Container Apps

The `equation-golf` image built from `Dockerfile.frontend` is the web/Caddy
container. It listens on `:80` (all interfaces), so configure the Container
App ingress target port as `80`. The API is a separate backend container,
which listens on `0.0.0.0:8000`; set the web Container App's
`BACKEND_ADDRESS` environment variable to the backend Container App's internal
FQDN without a port (for example,
`equation-golf-api.internal.<environment-domain>`). Container Apps routes
requests to the backend's configured target port. Keep backend ingress
internal-only; if Caddy proxies over HTTP, allow insecure traffic on that
internal ingress so requests aren't redirected to an internal HTTPS address
that public browsers cannot reach. The default `backend:8000` address is for
Docker Compose networking.

## Production challenges

Production challenges are generated separately from the development seed.
The generator creates a large candidate pool using the supported Equation
Golf grammar, evaluates candidates with the same parser and sampling logic as
the API, rejects unsafe or uninteresting curves, and selects exactly 365
consecutive dates starting from the current UTC date.

Generation is deterministic for a given generator version, private seed, and
UTC start date. Keep the seed and the generated JSON file private: knowing the
target expressions would defeat the game.

To initialize an empty production database directly, run
`python -m backend.initialize_production_challenges` with `DATABASE_URL` and
`PRODUCTION_CHALLENGE_SEED` set in the environment. It inserts any missing
dates without printing target expressions; the seed must remain private.

Set the seed through the environment rather than putting it in a command or
source file:

```bash
export PRODUCTION_CHALLENGE_SEED="${PRODUCTION_CHALLENGE_SEED:?set this privately}"
python -m backend.generate_production_challenges \
  --output data/production_challenges.json
```

Validate the resulting file before any database operation:

```bash
python -m backend.generate_production_challenges \
  --validate data/production_challenges.json
```

The importer requires an explicit `DATABASE_URL`. It first prints the complete
plan, skips existing dates by default, never deletes rows, and only writes
when `--apply` is present:

```bash
export DATABASE_URL='postgresql+psycopg://user:password@host:5432/database'

# Preview only; this makes no database changes.
python -m backend.import_production_challenges \
  data/production_challenges.json \
  --dry-run

# Apply inserts after reviewing the preview.
python -m backend.import_production_challenges \
  data/production_challenges.json \
  --apply
```

Use `--replace` only when replacing existing challenge rows is intentional:

```bash
python -m backend.import_production_challenges \
  data/production_challenges.json \
  --replace --apply
```

Do not run the importer against production until the generated file has been
reviewed and the dry run looks correct.

## Privacy and security notes

During an active challenge, the API returns sampled graph points rather than
the target expression or its LaTeX. The target can be revealed only through
the existing archive behaviour after the challenge is complete.

Google sign-in stores the stable Google account identifier, display name,
profile image URL, and Equation Golf submissions. The application does not
request Gmail, Drive, Contacts, or Calendar access and does not store Google
access or refresh tokens.

Before making a public repository, check both the working tree and Git history
for credentials. Keep `.env` files, production environment files, session
secrets, OAuth secrets, database URLs, and `data/production_challenges.json`
out of Git. The development seed is for local development only; production
targets should stay in the private artifact/database workflow.

The built-in submission limiter is process-local. For a multi-instance or
high-traffic deployment, put rate limiting at the edge or use a shared store
such as Redis.

## Contributing

Small, focused changes are easiest to review. Before opening a pull request,
run:

```bash
pytest
npm run lint
npm run build
git diff --check
```

The GitHub Actions workflow runs the backend tests against disposable
PostgreSQL databases and checks the frontend and Docker builds.

## Troubleshooting

**`npx: command not found`**

Run Vercel from the Nix shell:

```bash
nix develop --command npx vercel --prod
```

**Google reports `invalid_client`**

Check that the Google client secret in Vercel is current and belongs to the
same client ID being used by the deployment. Then check the redirect URI,
including the domain and `/api/auth/google/callback` path.

**`curl -I /api/auth/google` returns `405`**

That request uses the HTTP `HEAD` method. The sign-in route expects `GET`; a
405 response to `curl -I` does not by itself indicate that the route is broken.

**The API cannot connect to PostgreSQL**

Make sure Docker is running the database and that `DATABASE_URL` points to the
same host, port, database, username, and password as `compose.yaml`.
