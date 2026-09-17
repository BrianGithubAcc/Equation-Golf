# Equation Golf

Equation Golf is an approximation-golf game. Players submit equations for a
daily target function; the server evaluates the submission over the target's
domain and ranks results by error and expression cost.

## Local development

Requirements: Docker, Python 3.12, Node 22, and either the Nix development
shell or equivalent local tooling.

Start PostgreSQL:

```bash
docker compose up -d db
```

Enter the development shell and use an explicit local database URL:

```bash
nix develop
export DATABASE_URL='postgresql+psycopg://equationgolf:equationgolf@127.0.0.1:5432/equationgolf'
```

Apply migrations and seed development challenges:

```bash
python -m backend.seed_dev
```

Run the backend and frontend in separate terminals:

```bash
uvicorn backend.main:app --reload --port 8000
npm run dev
```

The development seed scripts are for local use only. They must not be used to
write production data.

## Production deployment

The Vercel adapter is [api/index.py](api/index.py), and API requests are routed
by [vercel.json](vercel.json). Deploy with the Vercel CLI from the Nix shell:

```bash
nix develop --command npx vercel --prod
```

Configure these Vercel production environment variables before deploying:

```text
DATABASE_URL
SESSION_SECRET
FRONTEND_URL=https://your-domain.example
BACKEND_URL=https://your-domain.example
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
```

`SESSION_SECRET` must be at least 32 characters. Never commit real secrets or
production `.env` files; use [.env.production.example](.env.production.example)
as the template.

For Google OAuth, the authorized redirect URI must exactly equal:

```text
https://your-domain.example/api/auth/google/callback
```

## Production challenge generation

The production challenge generator is separate from the development seed
scripts. It creates a deterministic candidate pool across multiple supported
function families, validates candidates using the application's parser and
target evaluator, derives padded graph ranges, and selects 365 consecutive UTC
dates. Determinism comes from the private `PRODUCTION_CHALLENGE_SEED`
environment variable; do not commit that seed or the generated JSON.

Generate the reviewed artifact:

```bash
export PRODUCTION_CHALLENGE_SEED="${PRODUCTION_CHALLENGE_SEED:?set this privately}"
python -m backend.generate_production_challenges \
  --output data/production_challenges.json
```

Validate it:

```bash
python -m backend.generate_production_challenges \
  --validate data/production_challenges.json
```

The importer never runs automatically. It requires an explicit
`DATABASE_URL`, prints its plan before any write, and requires `--apply`:

```bash
python -m backend.import_production_challenges \
  data/production_challenges.json \
  --dry-run

python -m backend.import_production_challenges \
  data/production_challenges.json \
  --apply
```

Existing dates are skipped. Use `--replace` only when intentionally replacing
existing challenge rows. The importer never deletes rows. The generated JSON
is intentionally ignored by Git and must be supplied privately to the machine
performing the import.

## Tests

Run the backend test suite with a disposable PostgreSQL test database:

```bash
pytest
```

The CI workflow creates separate disposable databases for the application and
test suite, builds the frontend, and builds both Docker images.

## Target privacy

The API deliberately omits `target_expr` and `target_latex` from public current
challenge responses. Production target equations are not stored in this public
repository: the generated JSON, its seed, and the database credentials must be
kept in private deployment storage.
