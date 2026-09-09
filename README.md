# AnyWhere Bazaar

[简体中文](README.zh.md) · [AnyWhere](https://github.com/appdev/AnyWhere) · [Catalog](catalog.json)

The community registry for AnyWhere extension packs. Authors keep their code and `manifest.json` in their own public GitHub repositories. This repository stores one small JSON registration per pack and generates a static catalog. Finder actions, tools with panels and workflows all use the existing extension-pack format.

## Register a package

1. Publish a public GitHub repository with a root `manifest.json`, its resources, a license and usage instructions. Test it in AnyWhere. See the [pack author guide](https://github.com/appdev/AnyWhere/blob/main/docs/pack-spec.md) and [working example](https://github.com/appdev/anywhere-tool-chain-demo).
2. Fork this repository. Add `registry/<id>.json`, for example:

   ```json
   {
     "id": "appdev.tool-chain-demo",
     "repository": "https://github.com/appdev/anywhere-tool-chain-demo"
   }
   ```

3. Open a pull request explaining the package and its permissions. CI validates the registration and fetches metadata. A maintainer reviews repository ownership, licensing and source before merging. Passing CI alone does not approve a package.
4. After merge, the publishing workflow updates `catalog.json`. Do not edit that generated file yourself.

IDs must be globally unique lowercase letters/digits separated by dots or hyphens, at most 100 characters, and exactly match the filename. Prefer `owner.package-name`; this is a catalog identity, not a new manifest field or the host's local `packKey`. Keep it stable. Repository addresses must be canonical `https://github.com/owner/repo` URLs without `.git`, query strings or branch paths. One repository can register once. Renames/transfers require a reviewed registration PR; do not reuse an old ID for an unrelated package.

Only `id` and `repository` are allowed. Standard JSON has no comments: put submission explanations in the PR and usage details in the package README. Package name, description, author and icon remain in `manifest.json`; types are derived from entries, not manually duplicated in the registry.

## Updates and removal

Update the package's default branch and root manifest in its own repository. No new registration PR is needed for ordinary updates. An hourly scheduled workflow resolves each default-branch HEAD, reads the manifest and file tree **at that exact 40-character Git commit**, then refreshes the catalog. GitHub may delay scheduled runs; maintainers can also run **Actions → Catalog → Run workflow**. This first version tracks commits, not releases or semantic versions.

The latest valid catalog remains available if fetching or validating any package fails; CI reports the failure and the entire refresh stops. Fix the package, or remove its registration by PR if necessary, then rerun. Removing an entry removes discovery after publication; it does not uninstall anything from users' computers.

Initial registration receives human review. Ordinary upstream commits are automatically indexed and are not individually reviewed by the registry maintainer. Catalog presence is not a security endorsement. AnyWhere's source-review and enablement steps still apply.

## Catalog contract

Client endpoint: [raw catalog.json](https://raw.githubusercontent.com/appdev/anywhere-bazaar/main/catalog.json).

```json
{
  "schemaVersion": 1,
  "packages": [
    {
      "id": "owner.example",
      "repository": "https://github.com/owner/example",
      "revision": "0123456789012345678901234567890123456789",
      "name": "Example",
      "description": null,
      "author": null,
      "icon": "shippingbox",
      "manifestSchemaVersion": 4,
      "types": ["tool", "workflow"]
    }
  ]
}
```

The example above is illustrative; use the generated file for real entries. Types are any combination of `finder` (context-menu actions), `tool` (launcher/UI actions) and `workflow` (declared workflows). `description` and `author` may be null. `revision` is a full Git commit, not an archive hash. Entries are sorted by ID and unchanged inputs produce identical output.

AnyWhere's Plugin Marketplace reads this catalog, rejects unsupported schemas and duplicate identities/sources, and installs the recorded full commit after verifying checkout and manifest. Source review and default-disabled installation still apply. Updates retain the selected catalog revision through diff review. Existing HTTPS GitHub installations match by canonical repository without replacing their keys or user data; subsequent catalog updates persist the registry identity. Removed or remapped bound entries report an error instead of following repository HEAD. Manual Git/local imports remain available; GitHub topics no longer determine in-app listings. Catalog fetch failures are visible and retryable. Use a current AnyWhere build containing the Bazaar client integration.

## Run validation

Python 3.9+ with only the standard library:

```sh
python3 -m unittest -v
python3 build_catalog.py
```

The second command requires network access to GitHub. Optional `GITHUB_TOKEN` raises the GitHub API rate limit; use a read-only token locally. CI uses its scoped Actions token. Tokens are never sent to raw content URLs.

Checks cover strict registration JSON, duplicate keys/repositories, public active source repositories, supported manifest schema 1–4, metadata types, action/workflow references, and regular files for declared scripts/UI entries. Symlink resources, unsafe paths, oversized responses and truncated file trees fail validation. Unknown manifest fields remain compatible. These catalog checks do **not** replace AnyWhere's full native validation, permission enforcement, source inspection or runtime tests.

Pull-request validation has read-only permissions and does not execute plugin files or build plugin projects. Only reviewed code on this repository's `main` can publish; its separate job commits only `catalog.json`. The publisher never follows remote redirects and does not check out package code. A failed refresh does not overwrite the published catalog. The registry provides metadata, not a plugin sandbox or a package download server.

MIT licensed; registered packages retain their own licenses.
