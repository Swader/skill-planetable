# Planetable REST API Reference

Source: Planetable/Planet `Technotes/API.md` on GitHub, checked 2026-05-01.

## Base URL

- Upstream examples use `http://localhost:8086`.
- Current local Planet.app instances may listen on `http://127.0.0.1:9191`.
- Prefer `PLANETABLE_BASE_URL` when the user or environment provides it.
- Discover by probing `GET /v0/planets/my` or `GET /v0/search?q=...`.

The public technote documents no authentication. Keep calls on loopback unless the user explicitly provides and approves a remote base URL.

## Response Notes

- `GET /v0/planets/my` can return private provider configuration, service tokens, custom code, and sync settings. Sanitize by default.
- Date fields may be ISO 8601 strings in examples, but live responses can also use numeric timestamps. Do not assume one format.
- Errors are JSON such as `{"error": true, "reason": "Not Found"}` for missing routes.

## Endpoints

### Planets

`GET /v0/planets/my`

List all local "My Planets".

`POST /v0/planets/my`

Create a planet with `multipart/form-data`.

Fields:
- `name`: string
- `about`: string
- `template`: string
- `avatar`: JPEG, PNG, or GIF file, 5 MB max

The upstream technote says "Parameter title is required" in this section, but the form field is `name`.

`GET /v0/planets/my/:uuid`

Get one planet.

`POST /v0/planets/my/:uuid`

Modify a planet with `multipart/form-data`.

Fields:
- `name`: string
- `about`: string
- `template`: string
- `avatar`: JPEG, PNG, or GIF file, 5 MB max

`DELETE /v0/planets/my/:uuid`

Delete one planet. Use only after explicit user intent and target confirmation.

`POST /v0/planets/my/:uuid/publish`

Publish one planet. Use only after explicit user intent and target confirmation.

`GET /v0/planets/my/:uuid/public`

Return built public HTML for a planet.

Public resource paths:
- `GET /:planet_uuid/avatar.png`
- `GET /:planet_uuid/:article_uuid/attachment_image.png`

### Articles

`GET /v0/planets/my/:planet_uuid/articles`

List articles under a planet.

`POST /v0/planets/my/:planet_uuid/articles`

Create an article with `multipart/form-data`.

Fields:
- `title`: string
- `date`: optional ISO 8601 string
- `content`: string, often HTML
- `attachments`: files at any supported type, 50 MB max total

At least `title` or `content` is required. Attach files as `attachments[0]`, `attachments[1]`, etc.

`GET /v0/planets/my/:planet_uuid/articles/:article_uuid`

Get one article.

`POST /v0/planets/my/:planet_uuid/articles/:article_uuid`

Modify an article with `multipart/form-data`.

Fields:
- `title`: string
- `date`: ISO 8601 string
- `content`: string, often HTML
- `attachments`: files at any supported type, 50 MB max total

`DELETE /v0/planets/my/:planet_uuid/articles/:article_uuid`

Delete one article. Use only after explicit user intent and target confirmation.

### Search

`GET /v0/search?q=<term>`

Search across My Planets by name/about and articles by title, slug, tags, attachments, and content. Matching is case-insensitive and diacritics-insensitive.

Response shape:

```json
{
  "planets": [
    {
      "id": "planet_uuid",
      "name": "Hello World Blog",
      "about": "Say hi to planet",
      "created": "2024-01-15T10:30:00Z",
      "updated": "2024-06-20T14:22:00Z"
    }
  ],
  "articles": [
    {
      "articleID": "article_uuid",
      "articleCreated": "2024-06-19T09:15:00Z",
      "title": "Hello from Planet",
      "preview": "snippet...",
      "planetID": "planet_uuid",
      "planetName": "Hello World Blog"
    }
  ]
}
```

## Curl Patterns

List planets:

```bash
curl -sS http://127.0.0.1:9191/v0/planets/my
```

Create article:

```bash
curl -sS -X POST http://127.0.0.1:9191/v0/planets/my/<planet_uuid>/articles \
  -F 'title=New Article' \
  -F 'date=2026-05-01T12:00:00Z' \
  -F 'content=<p>Hello</p>' \
  -F 'attachments[0]=@/path/to/image.jpg'
```

Search:

```bash
curl -sS 'http://127.0.0.1:9191/v0/search?q=hello'
```
