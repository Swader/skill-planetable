---
name: planetable
description: Operate local Planetable/Planet REST API servers for listing, searching, creating, editing, deleting, publishing, and smoke-testing planets and articles. Use when Codex needs to automate Planetable API access, discover the local Planet server base URL or port, upload article attachments or planet avatars, generate curl/client code for Planetable, or safely inspect Planetable content without leaking private configuration fields.
---

# Planetable

## Core Workflow

1. Discover the API base URL before making calls. Prefer `PLANETABLE_BASE_URL` when set; otherwise probe `http://127.0.0.1:9191` first and `http://127.0.0.1:8086` second. The upstream technote uses `8086`, while current local Planet apps may listen on `9191`.
2. Use `scripts/planetable.py` for safe probes and common operations:
   - `python3 scripts/planetable.py discover`
   - `python3 scripts/planetable.py list-planets`
   - `python3 scripts/planetable.py search "term"`
   - `python3 scripts/planetable.py list-articles <planet_uuid>`
3. Read `references/api.md` before mutating data, writing a custom client, or using an endpoint not covered by the helper script.
4. For multipart writes, send form fields exactly as the API expects. Use `attachments[0]`, `attachments[1]`, etc. for article uploads and `avatar=@file` for planet avatars.
5. Verify write operations by reading the changed resource back. For publish operations, also check `GET /v0/planets/my/:uuid/public` when the user wants generated public HTML.

## Safety Rules

- Treat `GET /v0/planets/my` as sensitive. Live responses can include service tokens, custom code, sync settings, and publishing configuration. Summarize names, UUIDs, dates, domains, and non-secret metadata unless the user explicitly asks for raw payloads.
- Do not expose `*token*`, `*key*`, `*secret*`, `customCode*`, SSH/rsync, or provider credential fields in final answers.
- Require a clear user request before `DELETE` or `publish`. Confirm the target by UUID and, when possible, by current name/title from a read call.
- Prefer loopback URLs. If the base URL is not localhost/127.0.0.1, warn before sending content or files because the API has no documented auth in the public technote.
- Keep created skills, scripts, and examples secret-free. Do not commit local Planet response bodies or user content unless explicitly requested.

## Common Tasks

### Inspect Availability

Run:

```bash
python3 scripts/planetable.py smoke
```

Report the resolved base URL, HTTP success/failure, and sanitized planet/search summaries. If discovery fails, check whether `/Applications/Planet.app` is running and inspect listening ports with `lsof -nP -iTCP -sTCP:LISTEN | rg 'Planet|8086|9191'`.

### Search Content

Use:

```bash
python3 scripts/planetable.py search "query"
```

Search returns matching planets and articles. Article previews may include private draft text; quote sparingly and only as needed.

### Create Or Update Articles

Use multipart form data. At least `title` or `content` is required by the API. `date` is optional and should be ISO 8601 when supplied.

```bash
python3 scripts/planetable.py create-article <planet_uuid> \
  --title "Post title" \
  --content '<p>HTML content</p>' \
  --date "2026-05-01T12:00:00Z" \
  --attach ./image.jpg
```

For updates:

```bash
python3 scripts/planetable.py update-article <planet_uuid> <article_uuid> \
  --title "Updated title" \
  --content '<p>Updated HTML</p>'
```

### Create Or Update Planets

Use multipart form data. Provide `name`, `about`, `template`, and optionally `avatar`.

```bash
python3 scripts/planetable.py create-planet \
  --name "New Planet" \
  --about "Short description" \
  --template "Grid" \
  --avatar ./avatar.png
```

### Raw API Work

Use `--raw` on helper commands only when a raw response is necessary. Otherwise keep output sanitized.

For direct curl examples and endpoint details, load `references/api.md`.
