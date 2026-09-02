# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository context

This is a downstream fork of `mshade/kronic` (a Flask-based Kubernetes CronJob admin UI). The fork's purpose is captured in its name: destructive/write-side UI controls have been commented out in the Jinja templates (see `templates/namespace.html` — Create/Clone/Delete/Suspend switches), and upstream GitHub Actions workflows have been renamed to `*.disabled` in `.github/workflows/` to keep the fork's CI silent until a local replacement is wired up. **The Flask API routes for those write actions (`/api/.../delete`, `/clone`, `/suspend`, etc.) still exist and still work** — the "read-only" property is enforced only in the UI. Keep this in mind before removing "unused" backend code.

The `develop` branch is the main branch for PRs (per `git config`).

## Common commands

Local development runs in Docker Compose against a real cluster via mounted `~/.kube/config` and `~/.aws` (the dev image includes `aws-cli` for EKS auth):

```bash
docker compose build
docker compose up               # serves on http://localhost:5000 (flask --debug)
```

Direct Python (no Docker) — expects a working kubeconfig on the host. Dependencies are managed with Poetry (`pyproject.toml` + `poetry.lock`):

```bash
poetry install --with dev
poetry run flask --app app run --debug     # or: poetry run gunicorn -w 4 -b 0.0.0.0 app:app
```

Tests use pytest. The suite sets `config.TEST = True` before importing `kron`, which skips kubeconfig loading, so no cluster is required:

```bash
poetry run pytest                          # all tests
poetry run pytest tests/test_kron.py::test_namespace_filter_allows_access   # single test
```

Format with `black` (only dev dep besides pytest):

```bash
poetry run black .
```

Helm chart lives at `chart/kronic/`. `chart/kronic/ci/` contains chart-test values consumed by the (currently disabled) `chart-testing` workflow.

## Configuration surface

All runtime config is env-var driven in `config.py`:

- `KRONIC_ADMIN_USERNAME` / `KRONIC_ADMIN_PASSWORD` — if password is unset, **auth is disabled entirely** (`verify_password` returns `True` for every request). The helm chart generates a random password by default; local dev in `docker-compose.yml` hard-codes `test2`.
- `KRONIC_ALLOW_NAMESPACES` — comma-separated allow-list. Enforced in two places (see below).
- `KRONIC_NAMESPACE_ONLY` — if truthy, requires `KRONIC_NAMESPACE` to also be set; the app hard-fails at import time otherwise. This mode overrides `ALLOW_NAMESPACES` to just the pod's own namespace and redirects the index/API-index straight to that namespace's view. The helm chart also switches from `ClusterRole` to namespaced `Role` when this is enabled.
- `KRONIC_TEST` — disables kubeconfig loading in `kron.py`. Used by the test suite.

## Architecture

Three-file backend, no framework beyond Flask:

- **`app.py`** — Flask routes only. Two route families share the same URL shape: HTML pages under `/namespaces/...` (Jinja-rendered) and JSON under `/api/namespaces/...`. Both are gated by `@auth.login_required` and `@namespace_filter`. The `_strip_immutable_fields` helper is called before rendering YAML into the edit form and before `clone` writes back — without it, the K8s API rejects the PATCH because `status`, `uid`, and `resourceVersion` are immutable.
- **`kron.py`** — All Kubernetes client calls. Instantiates `CoreV1Api` and `BatchV1Api` at import time; loads in-cluster config first and falls back to `~/.kube/config`. Every mutating operation returns either a cleaned dict or an `{"error": 500, "exception": {...}}` payload — callers should not assume success. `_clean_api_object` runs everything through `ApiClient.sanitize_for_serialization` and strips `managedFields`, so downstream code (routes, templates) always sees plain dicts, never K8s model objects.
- **`config.py`** — Module-level state; imported for side effects (password hashing, `NAMESPACE_ONLY` validation).

### Namespace filtering — two independent layers

There are **two** `namespace_filter` decorators, one in `app.py` and one in `kron.py`, and they are not the same. Both must be understood when changing access control:

- `app.py::namespace_filter` — HTTP-facing. Returns a 403 `denied.html` (or JSON `{"error": ...}` for `/api/` paths) when the request's `<namespace>` path segment is outside `ALLOW_NAMESPACES`.
- `kron.py::namespace_filter` — Library-facing. Returns `False` when a `kron.*` function is called with a disallowed namespace. This is a defense-in-depth belt-and-suspenders check for callers that bypass the Flask layer (tests, future scripts).

When `ALLOW_NAMESPACES` is unset, both layers are effectively no-ops and Kronic reaches for all namespaces (`list_cron_job_for_all_namespaces`). When it is set, `get_cronjobs()` with no namespace argument iterates the allow-list and concatenates results.

### Job / Pod ownership model

Jobs are matched to their parent CronJob via `pod_is_owned_by` (walks `metadata.ownerReferences`) **and** via a label check for `kronic.mshade.org/created-from`. Manually-triggered jobs (`trigger_cronjob`) set that label plus `kronic.mshade.org/manually-triggered=true` so they appear under the parent CronJob in the UI even though K8s doesn't set an ownerReference on manual invocations. Do not remove the label filter — it's the only signal for the manual case.

### Frontend

Server-rendered Jinja templates (`templates/`) with progressive enhancement via **AlpineJS** (bundled locally at `static/js/alpinejs@3.13.0.min.js`) and **PicoCSS** (`static/css/pico.min.css`). Interactivity is inline `x-data` / `@click` handlers in the templates; there is no build step and no separate JS source tree. The single API-client helper (`apiClient(...)` in `templates/namespace.html`) is the mechanism by which the SPA-ish parts talk to the JSON API.

## Scope notes for edits

- Editing `kron.py` API-shape changes (return types, error dict shape) ripples through both Flask handlers and Jinja templates — templates access nested keys like `cronjob.spec.jobTemplate.spec.template.spec.containers[0].image` directly and will crash on missing keys rather than degrade.
- The read-only-fork convention is: comment out the UI element (leave `<!-- -->` markers in place), do not delete the backend route. Preserves upstream merge-ability.
- `chart/kronic/README.md` is generated by `.github/gen-chart-readme.sh` from `README.md.gotmpl` + `values.yaml` — do not hand-edit it.
