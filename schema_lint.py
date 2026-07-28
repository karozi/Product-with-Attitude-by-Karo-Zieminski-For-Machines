#!/usr/bin/env python3
"""Schema completeness linter for for_machines.json.

Prevents the May 2026 regression where new articles auto-appended by the
repurposer pipeline shipped without speakable / description / claims.

Run as a pre-commit / pre-push gate:
    python3 schema_lint.py            # lint for_machines.json, exit 1 on gaps
    python3 schema_lint.py --json     # machine-readable report
    python3 schema_lint.py path.json  # lint a specific file

Required per-article fields (the AIO/GEO surface area that broke):
    - description OR alternativeHeadline   (human + AI summary)
    - speakable                            (voice/answer extraction)
    - pwa:extractableClaims OR >=1 entry in #extractable-claims  (citable claims)

Also checks (added 2026-07-27):
    - version drift: llms.txt '# Version:' header and 'schema_version:' block
      must match for_machines.json schemaVersion (the 5.9.34-vs-5.9.35 drift class)

Also reports (added 2026-07-28):
    - claim capsule budget: claims over ~150 chars arrive truncated through the
      commercial-scraper retrieval pipe. Reported here, enforced separately by
      scripts/claim_capsule_lint.py. Non-fatal until the corpus is backfilled.

Exit code 0 = clean, 1 = at least one article has a gap or versions drift.
To repair gaps, run: python3 scripts/schema_backfill.py --data <extracted.json>
"""
import json, os, re, sys

REQUIRED_DESC = ("description", "alternativeHeadline")  # at least one

def norm(u):
    return (u or "").split("?")[0].rstrip("/")

def lint(path):
    d = json.load(open(path))
    g = {n.get("@id"): n for n in d["@graph"]}
    arts = g.get("#recent-articles", {}).get("itemListElement", [])
    claims = g.get("#extractable-claims", {}).get("itemListElement", [])

    claim_urls = set()
    for c in claims:
        ap = c.get("appearance")
        u = ap.get("url") if isinstance(ap, dict) else None
        if u:
            claim_urls.add(norm(u))

    gaps = []
    for el in arts:
        a = el["item"]
        url = norm(a.get("url"))
        missing = []
        if not any(a.get(k) for k in REQUIRED_DESC):
            missing.append("description/alternativeHeadline")
        if "speakable" not in a:
            missing.append("speakable")
        has_claims = bool(a.get("pwa:extractableClaims")) or (url in claim_urls)
        if not has_claims:
            missing.append("extractableClaims")
        if not a.get("dateModified"):
            missing.append("dateModified")
        if not a.get("image"):
            missing.append("image")
        if missing:
            gaps.append({
                "headline": a.get("headline", "")[:70],
                "date": a.get("datePublished", ""),
                "url": url,
                "missing": missing,
            })
    return len(arts), gaps

def lint_version_drift(schema_path):
    """Compare schemaVersion against llms.txt version markers, if llms.txt is nearby."""
    llms_path = os.path.join(os.path.dirname(os.path.abspath(schema_path)), "llms.txt")
    if not os.path.exists(llms_path):
        return []
    version = json.load(open(schema_path)).get("schemaVersion")
    text = open(llms_path, encoding="utf-8").read()
    drift = []
    for label, pattern in (("# Version:", r"^# Version:\s*(\S+)"),
                           ("schema_version:", r"^schema_version:\s*(\S+)")):
        m = re.search(pattern, text, re.M)
        if m and m.group(1) != version:
            drift.append(f"llms.txt {label} {m.group(1)} != for_machines.json schemaVersion {version}")
    return drift

def capsule_summary(path):
    """Non-fatal snippet-budget summary. Silent if the capsule linter is absent."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(path)), "scripts"))
        import claim_capsule_lint as ccl
    except Exception:
        return None
    items = ccl.collect(path)
    errors = warns = 0
    for it in items:
        res = ccl.check(it["text"])
        if any(s == "error" for s, _, _ in res):
            errors += 1
        elif res:
            warns += 1
    return {"checked": len(items), "errors": errors, "warnings": warns}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    path = args[0] if args else "for_machines.json"
    total, gaps = lint(path)
    drift = lint_version_drift(path)
    caps = capsule_summary(path)

    if as_json:
        print(json.dumps({"total": total, "gaps": gaps, "version_drift": drift,
                          "capsules": caps, "clean": not (gaps or drift)},
                         indent=2, ensure_ascii=False))
    else:
        print(f"Schema lint: {path}")
        print(f"  Articles checked: {total}")
        if not gaps:
            print("  ✅ No gaps. All articles have description, speakable, claims, dateModified, and image.")
        else:
            print(f"  ❌ {len(gaps)} article(s) with gaps:")
            for gp in sorted(gaps, key=lambda x: x["date"], reverse=True):
                print(f"    {gp['date']}  [{', '.join(gp['missing'])}]  {gp['headline']}")
            print("  Repair: python3 scripts/schema_backfill.py --data <extracted.json>")
        for d in drift:
            print(f"  ❌ Version drift: {d}")
        if caps:
            if caps["errors"] or caps["warnings"]:
                print(f"  ⚠️  Capsule budget: {caps['errors']} error(s), {caps['warnings']} "
                      f"warning(s) across {caps['checked']} claims (non-fatal)")
                print("     Detail: python3 scripts/claim_capsule_lint.py --suggest")
            else:
                print(f"  ✅ Capsule budget: all {caps['checked']} claims fit 150 chars.")
    sys.exit(1 if (gaps or drift) else 0)

if __name__ == "__main__":
    main()
