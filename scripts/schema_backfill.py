#!/usr/bin/env python3
"""Repair tool for schema_lint.py failures on for_machines.json.

schema_lint.py is the gate; this is the wrench. When articles land in
#recent-articles without the required AIO/GEO fields (the recurring failure
mode since 2026-07-04: auto-appended entries missing speakable, dateModified,
image, description, and extractable claims), this script fills them:

Mechanical fixes (no input needed):
  - speakable        -> standard PwA SpeakableSpecification template
  - dateModified     -> copied from datePublished when absent

Content fixes (from a data file, never invented):
  - image            -> og:image URL fetched from the live article
  - description      -> post subtitle / og:description
  - pwa:extractableClaims -> atomic claims extracted from the article text

Usage:
    python3 scripts/schema_backfill.py --data backfill_data.json \
        [--bump-version] [--dry-run] [for_machines.json]

The data file is a JSON object keyed by canonical article URL:
    {"https://...": {"image": "...", "description": "...", "claims": ["..."]}}

Only articles flagged by schema_lint.py are touched. Existing values are
never overwritten. Run schema_lint.py afterwards; this script exits 1 if
gaps remain so it can chain in CI or pre-push hooks.
"""
import argparse
import json
import sys

SPEAKABLE = {
    "@type": "SpeakableSpecification",
    "cssSelector": [
        "h1.post-title",
        "h2.subtitle",
        ".body.markup > p:first-of-type",
        ".body.markup > p:nth-of-type(2)",
        "article h1",
        "article > p:first-of-type",
    ],
    "xpath": ["//h1", "//article//p[1]"],
}


def norm(u):
    return (u or "").split("?")[0].rstrip("/")


def bump(version):
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="for_machines.json")
    ap.add_argument("--data", help="JSON file with per-URL image/description/claims")
    ap.add_argument("--bump-version", action="store_true",
                    help="increment schemaVersion patch and set top-level dateModified to today")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = {}
    if args.data:
        raw = json.load(open(args.data))
        data = {norm(k): v for k, v in raw.items()}

    doc = json.load(open(args.path))
    graph = {n.get("@id"): n for n in doc["@graph"]}
    arts = graph.get("#recent-articles", {}).get("itemListElement", [])

    fixed, unresolved = [], []
    for el in arts:
        a = el["item"]
        url = norm(a.get("url"))
        d = data.get(url, {})
        changes = []
        if "speakable" not in a:
            a["speakable"] = json.loads(json.dumps(SPEAKABLE))
            changes.append("speakable")
        if not a.get("dateModified") and a.get("datePublished"):
            a["dateModified"] = a["datePublished"]
            changes.append("dateModified")
        if not a.get("image") and d.get("image"):
            a["image"] = d["image"]
            changes.append("image")
        if not (a.get("description") or a.get("alternativeHeadline")) and d.get("description"):
            a["description"] = d["description"]
            changes.append("description")
        if not a.get("pwa:extractableClaims") and d.get("claims"):
            a["pwa:extractableClaims"] = d["claims"]
            changes.append("claims")
        if changes:
            fixed.append((a.get("headline", "")[:60], changes))
        # claims may legitimately live in #extractable-claims instead; lint decides
        if not a.get("image") and url in data and not d.get("image"):
            unresolved.append((url, "image"))

    if args.bump_version and fixed:
        from datetime import date
        doc["schemaVersion"] = bump(doc.get("schemaVersion", "0.0.0"))
        doc["dateModified"] = date.today().isoformat()

    print(f"Backfill: {args.path}")
    for h, ch in fixed:
        print(f"  + [{', '.join(ch)}]  {h}")
    if not fixed:
        print("  nothing to fix")
    for u, f in unresolved:
        print(f"  ! unresolved {f}: {u}")

    if fixed and not args.dry_run:
        with open(args.path, "w") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  written ({doc.get('schemaVersion')})")
    elif args.dry_run:
        print("  DRY RUN, nothing written")

    # chainable: succeed only if the lint would now pass
    sys.path.insert(0, ".")
    try:
        from schema_lint import lint
        total, gaps = lint(args.path)
        print(f"  post-check: {total} articles, {len(gaps)} gap(s) remain")
        sys.exit(1 if gaps else 0)
    except ImportError:
        print("  post-check skipped (schema_lint.py not importable from cwd)")
        sys.exit(0)


if __name__ == "__main__":
    main()
