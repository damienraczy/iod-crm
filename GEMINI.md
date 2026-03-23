# Project Overview
BottleCRM (IOD-CRM) is a modern, full-featured Customer Relationship Management platform. It features a multi-tenant architecture utilizing PostgreSQL Row-Level Security (RLS) for enterprise-grade data isolation, along with a custom intelligence gathering module (`iod_job_intel`).

**Tech Stack:**
- **Backend:** Python 3.10+, Django 5.x, Django REST Framework, PostgreSQL (with RLS), Redis, Celery.
- **Frontend:** Node.js 18+, SvelteKit 2.x (Svelte 5 runes), TailwindCSS 4, shadcn-svelte.
- **Mobile:** Flutter / Dart (located in the `mobile/` directory).
- **Deployment:** Docker & Docker Compose.

---

# Development Conventions & Architecture Rules

### 1. Strict Code Isolation
* **Backend:** Do **NOT** modify files in native applications (e.g., `accounts`, `leads`). Place all custom business logic, models, and views in the dedicated app `iod_job_intel`.
* **Frontend:** Do **NOT** modify base components in `src/lib/components/ui/`. Create custom components in the `src/lib/components/custom/` folder.

### 2. Extension via Inheritance and Relations
* **Models:** To add data to an existing entity (like "Lead"), do not modify `leads/models.py`. Create a new model in `iod_job_intel` using a `OneToOneField` pointing to the original model.
* **Routes:** Create exclusive route folders for new features (e.g., `src/routes/(app)/job-intel/`) rather than injecting code into existing pages.

### 3. Configuration & Hooks
* **Environment:** Never hardcode sensitive values (API URLs, keys, Ollama models). Always use `.env` files.
* **Settings:** Any custom additions to `settings.py` should be placed at the very end of the file with clear comments.
* **Hooks:** Use Django **Signals** to trigger actions instead of altering core logic. On the frontend, if a button must be added to a core page, explicitly document the specific line modified.

### 4. Design System & UI
* **Font:** Geist font family.
* **Colors:** Primary brand color is Orange (`#EA580C`).
* **Tokens:** Rely heavily on defined CSS variables (e.g., `--color-brand-primary`, `--space-200`, `--radius-lg`). Always use the Tailwind utility classes derived from these tokens rather than custom CSS where possible.
* **Spacing:** 8px base grid system.

---

# Building and Running

**Using Docker (Recommended):**
```bash
# Start all services (Backend, Frontend, PostgreSQL, Redis, Celery)
docker compose up --build

# Run migrations inside the container
docker compose exec backend python manage.py migrate

# Check RLS status
docker compose exec backend python manage.py manage_rls --status
```

**Access Points:**
- **Frontend**: http://localhost:5173
- **Admin Panel**: http://localhost:8000/admin/
- **API Documentation / Swagger**: http://localhost:8000/swagger-ui/
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

**Testing:**
```bash
cd backend
pytest              # All tests with coverage
pytest --no-cov -x  # Faster testing without coverage
```
