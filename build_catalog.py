#!/usr/bin/env python3
"""Build a static AnyWhere catalog from public GitHub metadata; never run packs."""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(data):
    def invalid_constant(value):
        raise ValueError(f"Invalid JSON constant: {value}")
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def registrations(directory):
    entries, repositories = [], set()
    for path in sorted(directory.iterdir()):
        require(path.is_file() and not path.is_symlink() and path.suffix == ".json",
                f"Unexpected registry file: {path.name}")
        require(path.stat().st_size <= 4096, f"Registration too large: {path.name}")
        entry = decode(path.read_bytes())
        require(isinstance(entry, dict) and set(entry) == {"id", "repository"},
                f"{path.name}: expected only id and repository")
        package_id, repository = entry["id"], entry["repository"]
        require(isinstance(package_id, str) and len(package_id) <= 100 and
                re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", package_id) and
                path.name == f"{package_id}.json", f"Invalid ID/filename: {path.name}")
        require(isinstance(repository, str) and re.fullmatch(
            r"https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}", repository)
            and not repository.endswith(".git") and repository.rsplit("/", 1)[-1] not in {".", ".."},
            f"{package_id}: expected https://github.com/owner/repo without .git")
        require(repository.lower() not in repositories, f"Duplicate repository: {repository}")
        repositories.add(repository.lower())
        entries.append(entry)
    return entries


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_json(url, limit=1024 * 1024):
    headers = {"User-Agent": "AnyWhere-Bazaar", "Accept": "application/vnd.github+json"}
    # Never forward the Actions token to raw files or registered repository URLs.
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        data = response.read(limit + 1)
    require(len(data) <= limit, f"Response too large: {url}")
    return decode(data)


def text(value):
    return isinstance(value, str) and bool(value.strip()) and "\0" not in value


def metadata(manifest, tree):
    """Catalog checks only; AnyWhere's native validator remains authoritative."""
    require(isinstance(manifest, dict), "manifest.json must be an object")
    schema = manifest.get("schemaVersion", 1)
    require(type(schema) is int and 1 <= schema <= 4, "Supported schemaVersion: 1..4")
    require(text(manifest.get("name")), "Missing pack name")
    for field in ("author", "description", "icon"):
        require(manifest.get(field) is None or isinstance(manifest[field], str), f"Invalid {field}")
    api = manifest.get("uiApiVersion")
    require(api is None or (type(api) is int and api == 1 and schema == 4), "Unsupported UI API")

    def resource(path):
        require(text(path) and not path.startswith("/") and "\\" not in path and
                ".." not in path.split("/"), f"Unsafe resource path: {path!r}")
        normalized = "/".join(part for part in path.split("/") if part not in {"", "."})
        require(tree.get(normalized) in {"100644", "100755"},
                f"Missing regular file (symlinks are disallowed): {path}")

    resource("manifest.json")
    actions = manifest.get("actions")
    require(isinstance(actions, list) and 0 < len(actions) <= 1000, "Expected 1..1000 actions")
    ids, normalized_ids, types = set(), set(), set()
    for action in actions:
        require(isinstance(action, dict) and text(action.get("id")) and text(action.get("title")),
                "Each action needs an id and title")
        require(action["id"].strip() not in normalized_ids, f"Duplicate action: {action['id']}")
        normalized_ids.add(action["id"].strip())
        ids.add(action["id"])
        menu = action.get("contextMenu", True)
        ui, launcher = action.get("ui"), action.get("launcher")
        require(type(menu) is bool, "contextMenu must be boolean")
        require(menu or launcher is not None, "Action needs a context menu or launcher entry")
        capabilities = action.get("capabilities", [])
        require(isinstance(capabilities, list) and all(
            isinstance(c, str) and c in {"clipboard.write", "task.run", "documents", "launcher.entries", "notifications"} for c in capabilities),
            "Unsupported capability")
        require(schema == 4 or (ui is None and launcher is None and menu and not capabilities),
                "Tool fields require schemaVersion 4")
        if action.get("script") is not None:
            resource(action["script"])
        else:
            require(ui is not None, "Action needs script or ui")
        require("task.run" not in capabilities or action.get("script") is not None,
                "task.run requires a script")
        if ui is not None:
            require(isinstance(ui, dict) and api == 1, "UI requires uiApiVersion 1")
            resource(ui.get("entry"))
            height = ui.get("height")
            require(height is None or (type(height) is int and height > 0), "Invalid UI height")
        if launcher is not None:
            require(isinstance(launcher, dict), "launcher must be an object")
            keywords = launcher.get("keywords", [])
            require(isinstance(keywords, list) and all(text(k) for k in keywords), "Invalid keywords")
            require(len({k.strip().lower() for k in keywords}) == len(keywords), "Duplicate keywords")
        if menu:
            types.add("finder")
        if ui is not None or launcher is not None:
            types.add("tool")
    workflows = manifest.get("workflows", [])
    require(isinstance(workflows, list), "workflows must be an array")
    workflow_ids = set()
    for workflow in workflows:
        require(isinstance(workflow, dict) and text(workflow.get("id")) and text(workflow.get("title")),
                "Each workflow needs an id and title")
        require(workflow["id"] not in workflow_ids, "Duplicate workflow ID")
        workflow_ids.add(workflow["id"])
        steps = workflow.get("steps")
        require(isinstance(steps, list) and steps and all(
            isinstance(step, dict) and isinstance(step.get("action"), str) and step["action"] in ids
            for step in steps), "Workflow must reference existing local actions")
    if workflows:
        types.add("workflow")
    return {"name": manifest["name"], "description": manifest.get("description"),
            "author": manifest.get("author"), "icon": manifest.get("icon") or "shippingbox",
            "manifestSchemaVersion": schema, "types": sorted(types)}


def resolve(entry):
    repo = entry["repository"].removeprefix("https://github.com/")
    api = f"https://api.github.com/repos/{repo}"
    info = fetch_json(api)
    require(info.get("private") is False and not info.get("archived"), f"Not an active public repo: {repo}")
    require(info.get("full_name", "").lower() == repo.lower(), f"Repository moved: {repo}")
    revision = fetch_json(api + "/commits/HEAD")["sha"]
    require(isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision), "Invalid commit SHA")
    tree = fetch_json(api + f"/git/trees/{revision}?recursive=1", limit=10 * 1024 * 1024)
    require(tree.get("truncated") is False, f"Repository tree too large: {repo}")
    files = {item["path"]: item["mode"] for item in tree["tree"] if item["type"] == "blob"}
    manifest = fetch_json(f"https://raw.githubusercontent.com/{repo}/{revision}/manifest.json")
    return {**entry, "revision": revision, **metadata(manifest, files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("registry"))
    parser.add_argument("--output", type=Path, default=Path("catalog.json"))
    args = parser.parse_args()
    # Resolve everything before writing. A failing pack never replaces the good catalog.
    packages = [resolve(entry) for entry in registrations(args.registry)]
    output = json.dumps({"schemaVersion": 1, "packages": packages}, ensure_ascii=False, indent=2) + "\n"
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(output, encoding="utf-8")
    temporary.replace(args.output)
    print(f"Validated {len(packages)} packages → {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError) as error:
        print(f"Catalog build failed: {error}", file=sys.stderr)
        sys.exit(1)
