#!/usr/bin/env python3
"""Small standard-library CLI for the local Planetable/Planet REST API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASES = (
    "http://127.0.0.1:9191",
    "http://localhost:9191",
    "http://127.0.0.1:8086",
    "http://localhost:8086",
)
SENSITIVE_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "credential",
    "private",
    "apikey",
    "api_key",
    "customcode",
    "custom_code",
    "rsync",
    "ssh",
)


class PlanetableError(RuntimeError):
    pass


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def candidate_base_urls(cli_base_url: str | None) -> list[str]:
    bases: list[str] = []
    for value in (cli_base_url, os.environ.get("PLANETABLE_BASE_URL")):
        if value:
            bases.append(normalize_base_url(value))
    bases.extend(DEFAULT_BASES)
    deduped: list[str] = []
    for base in bases:
        if base not in deduped:
            deduped.append(base)
    return deduped


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    query: dict[str, str] | None = None,
    fields: dict[str, str | None] | None = None,
    files: list[tuple[str, Path]] | None = None,
    timeout: float = 8.0,
) -> Any:
    data = None
    headers: dict[str, str] = {"Accept": "application/json"}
    url = normalize_base_url(base_url) + path
    if query:
        url += "?" + urlencode(query)
    if fields or files:
        data, content_type = encode_multipart(fields or {}, files or [])
        headers["Content-Type"] = content_type
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get("content-type", "")
    except HTTPError as exc:
        body = exc.read()
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = body.decode("utf-8", errors="replace")
        raise PlanetableError(f"HTTP {exc.code} {method} {url}: {payload}") from exc
    except URLError as exc:
        raise PlanetableError(f"{method} {url}: {exc.reason}") from exc
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    if "json" not in content_type:
        return text
    return json.loads(text)


def encode_multipart(fields: dict[str, str | None], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = "----planetable-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        if value is None:
            continue
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ]
        )
    for name, path in files:
        if not path.is_file():
            raise PlanetableError(f"Attachment not found: {path}")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{path.name}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def discover_base_url(cli_base_url: str | None) -> str:
    errors: list[str] = []
    for base_url in candidate_base_urls(cli_base_url):
        try:
            request_json(base_url, "GET", "/v0/planets/my", timeout=3.0)
            return base_url
        except PlanetableError as exc:
            errors.append(str(exc))
    raise PlanetableError("Could not discover Planetable API base URL:\n" + "\n".join(errors))


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if is_sensitive_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def summarize_planet(planet: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "name",
        "about",
        "domain",
        "templateName",
        "created",
        "updated",
        "lastPublished",
        "archived",
        "tags",
    )
    return {key: planet[key] for key in keys if key in planet}


def summarize_article(article: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "articleID",
        "title",
        "slug",
        "created",
        "articleCreated",
        "updated",
        "planetID",
        "planetName",
        "attachments",
        "tags",
    )
    return {key: article[key] for key in keys if key in article}


def sanitize(payload: Any) -> Any:
    payload = redact(payload)
    if isinstance(payload, list):
        if all(isinstance(item, dict) and ("name" in item or "templateName" in item) for item in payload):
            return [summarize_planet(item) for item in payload]
        if all(isinstance(item, dict) and ("title" in item or "articleID" in item) for item in payload):
            return [summarize_article(item) for item in payload]
    if isinstance(payload, dict):
        if "planets" in payload or "articles" in payload:
            result = {key: sanitize(value) for key, value in payload.items()}
            if isinstance(result.get("planets"), list):
                result["planets"] = [summarize_planet(item) for item in result["planets"]]
            if isinstance(result.get("articles"), list):
                result["articles"] = [summarize_article(item) for item in result["articles"]]
            return result
        if "name" in payload or "templateName" in payload:
            return summarize_planet(payload)
        if "title" in payload or "articleID" in payload:
            return summarize_article(payload)
    return payload


def print_payload(payload: Any, *, raw: bool = False) -> None:
    if not raw:
        payload = sanitize(payload)
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def resolve_base(args: argparse.Namespace) -> str:
    return normalize_base_url(args.base_url) if args.base_url else discover_base_url(None)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", help="Planetable API base URL. Defaults to PLANETABLE_BASE_URL or discovery.")
    parser.add_argument("--raw", action="store_true", help="Print raw API payloads. Default output is sanitized.")


def field_values(args: argparse.Namespace, names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: getattr(args, name.replace("-", "_"), None) for name in names}


def article_files(paths: list[str] | None) -> list[tuple[str, Path]]:
    return [(f"attachments[{index}]", Path(path)) for index, path in enumerate(paths or [])]


def cmd_discover(args: argparse.Namespace) -> None:
    print(discover_base_url(args.base_url))


def cmd_smoke(args: argparse.Namespace) -> None:
    base_url = discover_base_url(args.base_url)
    planets = request_json(base_url, "GET", "/v0/planets/my")
    search = request_json(base_url, "GET", "/v0/search", query={"q": args.query})
    print_payload(
        {
            "base_url": base_url,
            "planet_count": len(planets) if isinstance(planets, list) else None,
            "planets": planets,
            "search": search,
        },
        raw=args.raw,
    )


def cmd_list_planets(args: argparse.Namespace) -> None:
    print_payload(request_json(resolve_base(args), "GET", "/v0/planets/my"), raw=args.raw)


def cmd_get_planet(args: argparse.Namespace) -> None:
    print_payload(request_json(resolve_base(args), "GET", f"/v0/planets/my/{args.planet_uuid}"), raw=args.raw)


def cmd_create_planet(args: argparse.Namespace) -> None:
    files = [("avatar", Path(args.avatar))] if args.avatar else []
    payload = request_json(
        resolve_base(args),
        "POST",
        "/v0/planets/my",
        fields=field_values(args, ("name", "about", "template")),
        files=files,
    )
    print_payload(payload, raw=args.raw)


def cmd_update_planet(args: argparse.Namespace) -> None:
    files = [("avatar", Path(args.avatar))] if args.avatar else []
    payload = request_json(
        resolve_base(args),
        "POST",
        f"/v0/planets/my/{args.planet_uuid}",
        fields=field_values(args, ("name", "about", "template")),
        files=files,
    )
    print_payload(payload, raw=args.raw)


def cmd_delete_planet(args: argparse.Namespace) -> None:
    if not args.yes:
        raise PlanetableError("Refusing to delete without --yes.")
    print_payload(request_json(resolve_base(args), "DELETE", f"/v0/planets/my/{args.planet_uuid}"), raw=args.raw)


def cmd_publish(args: argparse.Namespace) -> None:
    if not args.yes:
        raise PlanetableError("Refusing to publish without --yes.")
    print_payload(request_json(resolve_base(args), "POST", f"/v0/planets/my/{args.planet_uuid}/publish"), raw=args.raw)


def cmd_public(args: argparse.Namespace) -> None:
    print_payload(request_json(resolve_base(args), "GET", f"/v0/planets/my/{args.planet_uuid}/public"), raw=True)


def cmd_list_articles(args: argparse.Namespace) -> None:
    print_payload(request_json(resolve_base(args), "GET", f"/v0/planets/my/{args.planet_uuid}/articles"), raw=args.raw)


def cmd_get_article(args: argparse.Namespace) -> None:
    path = f"/v0/planets/my/{args.planet_uuid}/articles/{args.article_uuid}"
    print_payload(request_json(resolve_base(args), "GET", path), raw=args.raw)


def cmd_create_article(args: argparse.Namespace) -> None:
    payload = request_json(
        resolve_base(args),
        "POST",
        f"/v0/planets/my/{args.planet_uuid}/articles",
        fields=field_values(args, ("title", "date", "content")),
        files=article_files(args.attach),
    )
    print_payload(payload, raw=args.raw)


def cmd_update_article(args: argparse.Namespace) -> None:
    payload = request_json(
        resolve_base(args),
        "POST",
        f"/v0/planets/my/{args.planet_uuid}/articles/{args.article_uuid}",
        fields=field_values(args, ("title", "date", "content")),
        files=article_files(args.attach),
    )
    print_payload(payload, raw=args.raw)


def cmd_delete_article(args: argparse.Namespace) -> None:
    if not args.yes:
        raise PlanetableError("Refusing to delete without --yes.")
    path = f"/v0/planets/my/{args.planet_uuid}/articles/{args.article_uuid}"
    print_payload(request_json(resolve_base(args), "DELETE", path), raw=args.raw)


def cmd_search(args: argparse.Namespace) -> None:
    print_payload(request_json(resolve_base(args), "GET", "/v0/search", query={"q": args.query}), raw=args.raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate a local Planetable/Planet REST API.")
    add_common(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="Print the discovered API base URL.")
    discover.set_defaults(func=cmd_discover)

    smoke = subparsers.add_parser("smoke", help="Run sanitized availability checks.")
    smoke.add_argument("--query", default="test", help="Search term for smoke check.")
    smoke.set_defaults(func=cmd_smoke)

    list_planets = subparsers.add_parser("list-planets", help="List planets with sanitized fields.")
    list_planets.set_defaults(func=cmd_list_planets)

    get_planet = subparsers.add_parser("get-planet", help="Get one planet.")
    get_planet.add_argument("planet_uuid")
    get_planet.set_defaults(func=cmd_get_planet)

    create_planet = subparsers.add_parser("create-planet", help="Create a planet.")
    create_planet.add_argument("--name")
    create_planet.add_argument("--about")
    create_planet.add_argument("--template")
    create_planet.add_argument("--avatar")
    create_planet.set_defaults(func=cmd_create_planet)

    update_planet = subparsers.add_parser("update-planet", help="Update a planet.")
    update_planet.add_argument("planet_uuid")
    update_planet.add_argument("--name")
    update_planet.add_argument("--about")
    update_planet.add_argument("--template")
    update_planet.add_argument("--avatar")
    update_planet.set_defaults(func=cmd_update_planet)

    delete_planet = subparsers.add_parser("delete-planet", help="Delete a planet.")
    delete_planet.add_argument("planet_uuid")
    delete_planet.add_argument("--yes", action="store_true")
    delete_planet.set_defaults(func=cmd_delete_planet)

    publish = subparsers.add_parser("publish", help="Publish a planet.")
    publish.add_argument("planet_uuid")
    publish.add_argument("--yes", action="store_true")
    publish.set_defaults(func=cmd_publish)

    public = subparsers.add_parser("public", help="Print built public HTML for a planet.")
    public.add_argument("planet_uuid")
    public.set_defaults(func=cmd_public)

    list_articles = subparsers.add_parser("list-articles", help="List articles for a planet.")
    list_articles.add_argument("planet_uuid")
    list_articles.set_defaults(func=cmd_list_articles)

    get_article = subparsers.add_parser("get-article", help="Get one article.")
    get_article.add_argument("planet_uuid")
    get_article.add_argument("article_uuid")
    get_article.set_defaults(func=cmd_get_article)

    create_article = subparsers.add_parser("create-article", help="Create an article.")
    create_article.add_argument("planet_uuid")
    create_article.add_argument("--title")
    create_article.add_argument("--date")
    create_article.add_argument("--content")
    create_article.add_argument("--attach", action="append")
    create_article.set_defaults(func=cmd_create_article)

    update_article = subparsers.add_parser("update-article", help="Update an article.")
    update_article.add_argument("planet_uuid")
    update_article.add_argument("article_uuid")
    update_article.add_argument("--title")
    update_article.add_argument("--date")
    update_article.add_argument("--content")
    update_article.add_argument("--attach", action="append")
    update_article.set_defaults(func=cmd_update_article)

    delete_article = subparsers.add_parser("delete-article", help="Delete an article.")
    delete_article.add_argument("planet_uuid")
    delete_article.add_argument("article_uuid")
    delete_article.add_argument("--yes", action="store_true")
    delete_article.set_defaults(func=cmd_delete_article)

    search = subparsers.add_parser("search", help="Search planets and articles.")
    search.add_argument("query")
    search.set_defaults(func=cmd_search)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except PlanetableError as exc:
        print(f"planetable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
