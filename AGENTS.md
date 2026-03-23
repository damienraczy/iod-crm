# AGENTS.md

This file provides guidance for agentic coding agents working in this repository.

---

## Build / Lint / Test Commands

### Backend (Django)

```bash
cd backend
source venv/bin/activate

# Development
python manage.py runserver            # Dev server on :8000
python manage.py migrate              # Run migrations
celery -A crm worker --loglevel=INFO  # Celery worker
celery -A crm beat --loglevel=INFO    # Celery beat scheduler

# iod_job_intel management commands
python manage.py run_sync --source GOUV_NC   # Run single scraper
python manage.py run_sync --all              # Run all scrapers
python manage.py manage_rls --status         # Check RLS status
python manage.py manage_rls --verify-user    # Verify non-superuser for RLS

# Tests
pytest                                # All tests with coverage
pytest --no-cov -x                    # Fast, stop on first failure
 pytest accounts/tests/               # Single app tests
pytest leads/tests/test_models.py     # Specific test file
pytest -k "test_login"                # Tests matching pattern

# Code quality
black .                               # Format code
isort .                               # Sort imports
```

### Frontend (SvelteKit)

```bash
cd frontend
pnpm run dev                          # Dev server on :5173
pnpm run check                        # svelte-check type checking
pnpm run lint                         # ESLint + Prettier check
pnpm run format                       # Auto-format with Prettier
pnpm run build                        # Production build
```

### Docker (recommended)

```bash
docker compose up --build             # Start all services
docker compose exec backend python manage.py migrate
docker compose exec backend python -m pytest
docker compose down -v                # Stop and delete data
```

---

## Backend Code Style (Django/Python)

### Imports
Use `isort` ordering: stdlib → third-party → local → from same package.

```python
import json                           # stdlib
from datetime import datetime

import requests                       # third-party
from django.db import models
from rest_framework import serializers

from accounts.models import Account   # local
from .utils import helper_func
```

### Formatting
Run `black .` and `isort .` before committing. Black uses 88-char line length.

### BaseModel Pattern
All models inherit from `common.base.BaseModel`:
- UUID primary keys (`id`, not integer IDs)
- Auto fields: `created_at`, `updated_at`, `created_by`, `updated_by`
- Organization isolation: `org = models.ForeignKey(Org, on_delete=models.CASCADE)`

### Multi-tenancy & Row-Level Security (RLS)
- Middleware sets RLS context automatically for requests: `set_config('app.current_org', '<org_id>')`
- **Critical:** DB user MUST be non-superuser (superusers bypass RLS)
- In management commands/Celery tasks: use `set_rls_context(org_id)` before ORM writes
- RLS-protected tables: 24 tables including core business (lead, accounts, contacts, opportunity, case, task, invoice) and supporting tables
- Check status: `python manage.py manage_rls --status`

### Testing
- Test files: `test_*.py` or `*_test.py` in `*/tests/` directories
- Use `@pytest.mark.django_db` decorator for DB tests
- Fixtures in `backend/conftest.py`: `org_a`, `admin_client`, `user_client`, `unauthenticated_client`
- Use `APIClient` from `rest_framework.test` for API tests
- Test isolation: use `with pytest.raises(SomeException)` for exception testing

### Error Handling
- Use Django exceptions: `ValidationError`, `PermissionDenied`, `AuthenticationFailed`
- LLM service calls (`AIService` in iod_job_intel): wrap in try/except, retry on network errors
- Return structured DRF Response objects with appropriate status codes

### API Patterns
View classes inherit from `APIView`, serializer classes from `serializers.ModelSerializer`.
Filter by org: `queryset = MyModel.objects.filter(org=request.profile.org)`
Use `@extend_schema` decorator for Swagger docs.

---

## iod_job_intel Module (Job Market Intelligence)

### Scrapers

| Constant | Source | Description |
|----------|--------|-------------|
| `GOUV_NC` | data.gouv.nc | OpenDataSoft API |
| `PSUD` | emploi.province-sud.nc | Province Sud job board |
| `JOB_NC` | job.nc | Drupal CMS |
| `LEMPLOI_NC` | lemploi.nc | Job portal |
| `INFOGREFFE` | infogreffe.nc | Executives/legal info |
| `AVISRIDET` | avisridet.isee.nc | PDF → structured data |

### LLM Prompts — Mandatory Pattern

Prompts are **NEVER** hardcoded in Python. Required workflow:

1. Write prompt in `iod_job_intel/prompts/<slug>.txt`
2. Create data migration (`RunPython`) calling `PromptTemplate.objects.update_or_create(name="<slug>", ...)`
3. In `ai_service.py`: load with `self._read_prompt("<slug>")`
4. Renaming: migration updates `name` in DB and all Python call sites
5. Increment `version` when prompt content changes

### Classifier vs General Model

- `_require_model("classifier")` — structured JSON tasks (`classify_offer`, `extract_ridet_pdf`); `temperature=0.0`
- `_current_model()` — free-text generation (`diagnose_offer`, `generate_questions_brulantes`, `generate_email`)

### RIDET Format (Critical)

- Always store as **7-character zero-padded string**: `"0038380"`, NOT `38380`
- Use `.zfill(7)`; never cast through `int()`
- Used for deduplication and cross-referencing between sources

### RidetEntry.description

This field is **edited manually in the frontend**:
- Must never appear in `update_fields` during automated consolidation (Infogreffe, PDF extraction, etc.)
- Preserves user-written descriptions

### Playwright / Browserless (SPA Scraping)

```python
p.chromium.connect_over_cdp(BROWSERLESS_WS)
page.on("response", handler)  # Intercept PDF URLs
# response.body() returns 0 bytes for downloads
requests.get(url, cookies=context.cookies())  # Download with cookies
# Dismiss consent banners BEFORE any click actions
```

---

## Frontend Code Style (SvelteKit/Svelte 5)

### Imports
Organize by type and use barrel files (`index.js`) for re-exports.

```javascript
// External
import { enhance } from '$app/forms';
import { toast } from 'svelte-sonner';
import { Mail, Phone } from '@lucide/svelte';

// Internal
import { Button } from '$lib/components/ui/button';
import { getAccessToken } from '$lib/api.js';
import { orgSettings } from '$lib/stores/org.js';
```

### Formatting
Prettier config: 2 spaces, single quotes, 100-char width, no trailing commas.
Run `pnpm run format` before committing.

### Components
- Use Svelte 5 runes: `$state`, `$derived`, `$effect`
- Props with JSDoc: `/** @param {string} name */ export let name;`
- Or object props: `/** @typedef {{ name: string, age?: number }} Person */ export let person;`
- Accessing env: `import { env } from '$env/dynamic/public'`

### Routes
- `routes/(app)/` — authenticated pages (sidebar layout)
- `routes/(no-layout)/` — public/auth pages (login, invoice portal, new org)
- `routes/api/` — SvelteKit server-side API routes (thin proxy to Django)
- Page files: `+page.svelte`, `+page.server.js` (load functions)

### API Calls
Use centralized client in `lib/api.js`:
- `getAccessToken()`, `apiRequest(endpoint, options)`
- JWT stored in localStorage: `access_token`, `refresh_token`, `org_id`
- Base URL: `env.PUBLIC_DJANGO_API_URL` or `http://localhost:8000`
- Auto-refresh on 401, redirect to login on auth failure

### Types
JSDoc comments for type hints (jsconfig.json allows JSDoc checking).
Example: `/** @typedef {{ id: string, name: string }} ColumnDef */`

### Error Handling
Show user-friendly messages with `svelte-sonner` toast:
`toast.success('Saved successfully')`, `toast.error('Failed to save')`

### UI Components
Use shadcn-svelte components from `lib/components/ui/`.
Avoid direct `$app` imports (use SvelteKit APIs via `$app/stores` etc.).

### Design System
Colors use semantic tokens (see DESIGN_SYSTEM.md):
- Primary: #EA580C (orange)
- Pipeline stages: new (#EA580C), qualified (#3B82F6), won (#22C55E), lost (#EF4444)
- Activity types: call (#22C55E), email (#3B82F6), meeting (#8B5CF6)
- 8px grid spacing, Geist font, rounded borders
- Use `svelte-sonner` for toasts, `lucide-svelte` for icons

---

## Critical Constraints

1. **Never commit secrets** (.env, credentials.json)
2. **RIDET format**: Always 7-char zero-padded string, never int
3. **LLM prompts**: Must be in DB via migration, never hardcoded
4. **RLS context**: Set manually in mgmt commands/tasks, never assume
5. **Frontend env**: Use `import { env } from '$env/dynamic/public'`
6. **Multi-tenancy**: Always filter by org in backend queries
7. **DB user**: MUST be non-superuser for RLS to work
8. **RidetEntry.description**: Preserve manual edits, never update during consolidation