#!/usr/bin/env python3
"""Collect the files dbt docs needs into one folder that can be published as a website.

Usage:
    python scripts/prepare_docs_site.py dbt/target site

Copies index.html, manifest.json and catalog.json. Table owners (which are
account email addresses in Unity Catalog) are removed from the catalog first,
because the site is public.
"""
from __future__ import annotations

import json
import os
import shutil
import sys

REQUIRED = ("index.html", "manifest.json", "catalog.json")


def scrub_catalog(catalog: dict) -> int:
    """Blank every 'owner' in the catalog. Returns how many were removed."""
    removed = 0
    for group in ("nodes", "sources"):
        for entry in (catalog.get(group) or {}).values():
            metadata = entry.get("metadata") or {}
            if metadata.get("owner"):
                metadata["owner"] = None
                removed += 1
    return removed


def build_site(target_dir: str, site_dir: str) -> int:
    missing = [name for name in REQUIRED if not os.path.exists(os.path.join(target_dir, name))]
    if missing:
        raise FileNotFoundError(f"{target_dir} is missing {missing}; run 'dbt docs generate' first")

    os.makedirs(site_dir, exist_ok=True)
    shutil.copyfile(os.path.join(target_dir, "index.html"), os.path.join(site_dir, "index.html"))
    shutil.copyfile(os.path.join(target_dir, "manifest.json"), os.path.join(site_dir, "manifest.json"))

    with open(os.path.join(target_dir, "catalog.json")) as handle:
        catalog = json.load(handle)
    removed = scrub_catalog(catalog)
    with open(os.path.join(site_dir, "catalog.json"), "w") as handle:
        json.dump(catalog, handle)
    return removed


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    removed = build_site(sys.argv[1], sys.argv[2])
    print(f"site written to {sys.argv[2]} ({removed} owner fields removed)")


if __name__ == "__main__":
    main()
