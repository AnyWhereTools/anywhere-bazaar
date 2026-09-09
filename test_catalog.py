"""Offline trust-boundary and catalog regression checks: python3 -m unittest -v."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_catalog as catalog


class CatalogTests(unittest.TestCase):
    def test_registration_contract(self):
        entry = {"id": "dev.example", "repository": "https://github.com/dev/example"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "dev.example.json"
            path.write_text(json.dumps(entry))
            self.assertEqual(catalog.registrations(root), [entry])
            for bad in ({**entry, "comment": "not a schema field"},
                        {**entry, "id": "../example"},
                        {**entry, "repository": "https://github.com.evil.test/dev/example"},
                        {**entry, "repository": "https://github.com/dev/example.git"}):
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    catalog.registrations(root)
            path.write_text(json.dumps(entry))
            (root / "dev.other.json").write_text(json.dumps(
                {"id": "dev.other", "repository": "https://github.com/DEV/EXAMPLE"}))
            with self.assertRaisesRegex(ValueError, "Duplicate repository"):
                catalog.registrations(root)
        for invalid in ('{"id":"a","id":"b"}', '{"number":NaN}', '{/*comment*/"id":"a"}'):
            with self.assertRaises(ValueError):
                catalog.decode(invalid)

    def test_manifest_categories_and_resources(self):
        manifest = {"schemaVersion": 4, "uiApiVersion": 1, "name": "Example",
                    "actions": [{"id": "a", "title": "A", "contextMenu": False,
                                 "ui": {"entry": "panel.html"}, "launcher": {"keywords": ["a"]}}],
                    "workflows": [{"id": "flow", "title": "Flow", "steps": [{"action": "a"}]}]}
        files = {"manifest.json": "100644", "panel.html": "100644", "run.sh": "100755"}
        self.assertEqual(catalog.metadata(manifest, files)["types"], ["tool", "workflow"])
        legacy = {"name": "Finder", "actions": [{"id": "a", "title": "A", "script": "run.sh"}]}
        self.assertEqual(catalog.metadata(legacy, files)["types"], ["finder"])
        for path in ("../panel.html", "/panel.html", "missing.html", "a\\panel.html"):
            bad = copy.deepcopy(manifest)
            bad["actions"][0]["ui"]["entry"] = path
            with self.assertRaises(ValueError):
                catalog.metadata(bad, files)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            catalog.metadata(manifest, {**files, "panel.html": "120000"})
        for bad in ({**manifest, "schemaVersion": True}, {**manifest, "schemaVersion": 5},
                    {**manifest, "actions": manifest["actions"] * 2},
                    {**manifest, "workflows": [{"id": "f", "title": "F", "steps": [{"action": "absent"}]}]}):
            with self.assertRaises(ValueError):
                catalog.metadata(bad, files)

    def test_remote_resolution_pins_every_resource(self):
        entry = {"id": "dev.example", "repository": "https://github.com/dev/example"}
        revision = "a" * 40
        replies = [{"private": False, "full_name": "dev/example"}, {"sha": revision},
                   {"truncated": False, "tree": [
                       {"path": p, "type": "blob", "mode": "100644"} for p in ("manifest.json", "run.sh")]},
                   {"name": "Example", "actions": [{"id": "a", "title": "A", "script": "run.sh"}]}]
        with patch.object(catalog, "fetch_json", side_effect=replies) as fetch:
            self.assertEqual(catalog.resolve(entry)["revision"], revision)
            self.assertIn(f"/git/trees/{revision}?", fetch.call_args_list[2].args[0])
            self.assertIn(f"/{revision}/manifest.json", fetch.call_args_list[3].args[0])
        for info in ({"private": True}, {"private": False, "full_name": "someone/else"}):
            with patch.object(catalog, "fetch_json", return_value=info):
                with self.assertRaises(ValueError):
                    catalog.resolve(entry)

    def test_failed_refresh_preserves_published_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            output.write_text("previous good catalog\n")
            with patch("sys.argv", ["build_catalog.py", "--output", str(output)]), \
                    patch.object(catalog, "registrations", return_value=[{}]), \
                    patch.object(catalog, "resolve", side_effect=ValueError("unavailable")):
                with self.assertRaises(ValueError):
                    catalog.main()
            self.assertEqual(output.read_text(), "previous good catalog\n")


if __name__ == "__main__":
    unittest.main()
