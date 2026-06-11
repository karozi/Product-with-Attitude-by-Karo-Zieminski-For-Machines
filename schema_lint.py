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
Exit code 0 = clean, 1 = at least one article has a gap.
"""
import json, sys

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

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    path = args[0] if args else "for_machines.json"
    total, gaps = lint(path)

    if as_json:
        print(json.dumps({"total": total, "gaps": gaps, "clean": not gaps}, indent=2, ensure_ascii=False))
    else:
        print(f"Schema lint: {path}")
        print(f"  Articles checked: {total}")
        if not gaps:
            print("  ✅ No gaps. All articles have description, speakable, claims, dateModified, and image.")
        else:
            print(f"  ❌ {len(gaps)} article(s) with gaps:")
            for gp in sorted(gaps, key=lambda x: x["date"], reverse=True):
                print(f"    {gp['date']}  [{', '.join(gp['missing'])}]  {gp['headline']}")
    sys.exit(1 if gaps else 0)

if __name__ == "__main__":
    main()
