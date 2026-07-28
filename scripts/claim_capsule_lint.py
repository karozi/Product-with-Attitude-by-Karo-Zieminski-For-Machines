#!/usr/bin/env python3
"""Claim capsule linter for for_machines.json.

Why this exists
---------------
ChatGPT does not read your page. A fetcher reads it and hands over a snippet.
On the July 2026 network captures, the commercial-scraper pipe that carried
558 of 595 results returned a mean snippet of ~153 characters, against ~1,217
for the licensed publisher pipe.
  https://suganthan.com/blog/how-chatgpt-picks-sources-part-2/

So an extractable claim longer than ~150 characters is not a richer claim.
It is a claim that arrives truncated mid-thought, or does not arrive at all.
A claim whose subject is buried behind a lead-in clause ("According to...",
"In this post...", "It is...") wastes the budget before it says anything.

This linter enforces the capsule contract on every claim in the graph:

    <= CAPSULE_MAX characters, subject front-loaded, self-contained.

Checked surfaces
----------------
  1. #recent-articles[].item.pwa:extractableClaims   (list of strings)
  2. #extractable-claims.itemListElement[].text      (Claim objects)
  3. #key-quotes / #recognition-claims text fields   (--all only)

Usage
-----
    python3 scripts/claim_capsule_lint.py                    # human report
    python3 scripts/claim_capsule_lint.py --json             # machine report
    python3 scripts/claim_capsule_lint.py --suggest          # + proposed rewrites
    python3 scripts/claim_capsule_lint.py --fail-on error    # CI gate, errors only
    python3 scripts/claim_capsule_lint.py --fail-on warn     # CI gate, strict
    python3 scripts/claim_capsule_lint.py --budget 150 path.json

Exit codes
----------
    0  clean at the chosen --fail-on threshold (default: never fails)
    1  at least one finding at or above the threshold

Start with --fail-on none (report only), backfill, then flip the workflow to
--fail-on error, then to warn once the corpus is clean.
"""
import json
import re
import sys

CAPSULE_MAX = 150      # scraper-pipe snippet budget, characters
HARD_MAX = 200         # beyond this the claim is certainly cut mid-thought

# Lead-in openers that spend the budget before the subject appears.
LEADIN = re.compile(
    r"^\s*(according to|as (?:noted|described|explained|per)|in (?:this|the|her|his|2026|2025)"
    r"|there (?:are|is|was|were)|it (?:is|was|turns out|means|takes)|one of the"
    r"|the (?:reason|point|idea|thing|question|answer|problem|takeaway) (?:is|was|here)"
    r"|when you|if you|while |because |what (?:makes|matters)|for (?:most|many|anyone)"
    r"|this (?:means|is|was|post|article|piece)|that (?:means|is)|these |those "
    r"|karo (?:says|notes|explains|writes|argues) that)\b",
    re.I,
)

# A claim that opens on a bare pronoun has no subject a model can attribute.
PRONOUN_START = re.compile(r"^\s*(it|this|that|they|these|those|he|she|there)\b[,\s]", re.I)

# Sentence boundary that ignores common abbreviations and decimals.
SENT_END = re.compile(r"(?<![A-Z])(?<!\b[A-Z]\w)(?<!\d)[.!?](?=\s+[A-Z(\"']|$)")


def norm(u):
    return (u or "").split("?")[0].rstrip("/")


def first_sentence(text):
    m = SENT_END.search(text)
    return text[: m.end()].strip() if m else text.strip()


def strip_leadin(text):
    """Drop a leading throat-clearing clause if the remainder still stands alone."""
    m = LEADIN.match(text)
    if not m:
        return text
    rest = text[m.end():].lstrip(" ,:;-\u2014")
    # only accept if what's left starts with a capital-able subject and is substantial
    if len(rest) >= 40:
        return rest[0].upper() + rest[1:]
    return text


def suggest(text, budget=CAPSULE_MAX):
    """Propose a capsule <= budget.

    Returns (capsule, mechanical) where mechanical=True means the cut was made
    mid-sentence and the result needs a human or LLM pass before shipping.
    Returns (None, False) when no safe cut exists.
    """
    cand = strip_leadin(first_sentence(text))
    if len(cand) <= budget:
        return (cand, False) if cand != text else (None, False)
    # cut at the last clause boundary that fits
    window = cand[: budget + 1]
    for sep in (" \u2014 ", "; ", ", and ", ", but ", ", which ", ", "):
        idx = window.rfind(sep)
        if idx >= 60:
            out = cand[:idx].rstrip(" ,;\u2014")
            if not out.endswith((".", "!", "?")):
                out += "."
            return (out, True)
    # last resort: last whole word
    idx = window.rfind(" ")
    if idx >= 60:
        return (cand[:idx].rstrip(" ,;\u2014") + ".", True)
    return (None, False)


def check(text, budget=CAPSULE_MAX):
    """Return a list of (severity, code, message) findings for one claim string."""
    out = []
    n = len(text)
    if n > HARD_MAX:
        out.append(("error", "over-hard-max",
                    f"{n} chars, past the {HARD_MAX}-char hard cap \u2014 certainly truncated"))
    elif n > budget:
        out.append(("warn", "over-budget",
                    f"{n} chars, over the {budget}-char scraper snippet budget"))
    if PRONOUN_START.match(text):
        out.append(("error", "pronoun-subject",
                    "opens on a bare pronoun \u2014 unattributable when lifted alone"))
    elif LEADIN.match(text):
        out.append(("warn", "buried-subject",
                    "opens on a lead-in clause \u2014 subject is not at character 1"))
    fs = first_sentence(text)
    if len(fs) > budget and n > budget:
        out.append(("warn", "no-capsule",
                    f"first sentence alone is {len(fs)} chars \u2014 no sentence fits the budget"))
    return out


def collect(path, include_all=False):
    d = json.load(open(path, encoding="utf-8"))
    g = {n.get("@id"): n for n in d["@graph"]}
    items = []

    for el in g.get("#recent-articles", {}).get("itemListElement", []):
        a = el.get("item", {})
        url = norm(a.get("url"))
        for i, c in enumerate(a.get("pwa:extractableClaims") or []):
            if isinstance(c, str) and c.strip():
                items.append({"surface": "article", "url": url,
                              "ref": f"{url}#claim{i}", "text": c})

    for c in g.get("#extractable-claims", {}).get("itemListElement", []):
        t = c.get("text") or ""
        if t.strip():
            ap = c.get("appearance")
            url = norm(ap.get("url")) if isinstance(ap, dict) else ""
            items.append({"surface": "extractable-claims", "url": url,
                          "ref": f"#extractable-claims[{c.get('position')}]", "text": t})

    if include_all:
        for node in ("#key-quotes", "#recognition-claims"):
            for c in g.get(node, {}).get("itemListElement", []):
                t = c.get("text") or c.get("claimReviewed") or ""
                if isinstance(t, str) and t.strip():
                    items.append({"surface": node.lstrip("#"), "url": "",
                                  "ref": f"{node}[{c.get('position')}]", "text": t})
    return items


def main():
    argv = sys.argv[1:]
    as_json = "--json" in argv
    want_suggest = "--suggest" in argv
    include_all = "--all" in argv
    budget = CAPSULE_MAX
    fail_on = "none"
    if "--budget" in argv:
        budget = int(argv[argv.index("--budget") + 1])
    if "--fail-on" in argv:
        fail_on = argv[argv.index("--fail-on") + 1]
    positional = [a for a in argv if not a.startswith("--")]
    skip = set()
    for flag in ("--budget", "--fail-on"):
        if flag in argv:
            skip.add(argv[argv.index(flag) + 1])
    positional = [p for p in positional if p not in skip]
    path = positional[0] if positional else "for_machines.json"

    items = collect(path, include_all)
    findings = []
    for it in items:
        res = check(it["text"], budget)
        if res:
            entry = dict(it)
            entry["findings"] = [{"severity": s, "code": c, "message": m} for s, c, m in res]
            entry["length"] = len(it["text"])
            if want_suggest:
                cap, mech = suggest(it["text"], budget)
                entry["suggested"] = cap
                entry["suggestion_is_mechanical"] = mech
            findings.append(entry)

    errors = [f for f in findings if any(x["severity"] == "error" for x in f["findings"])]
    warns = [f for f in findings if f not in errors]

    if as_json:
        print(json.dumps({
            "path": path, "budget": budget, "claims_checked": len(items),
            "errors": len(errors), "warnings": len(warns), "findings": findings,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"Claim capsule lint: {path}")
        print(f"  Budget: {budget} chars (hard cap {HARD_MAX})")
        print(f"  Claims checked: {len(items)}")
        if not findings:
            print("  \u2705 Every claim fits the snippet budget with a front-loaded subject.")
        else:
            print(f"  \u274c {len(errors)} error(s), {len(warns)} warning(s)")
            for f in sorted(findings, key=lambda x: -x["length"])[:200]:
                codes = ", ".join(x["code"] for x in f["findings"])
                print(f"\n    [{f['length']}] {codes}")
                print(f"    {f['ref']}")
                print(f"    was: {f['text'][:180]}")
                if want_suggest and f.get("suggested"):
                    tag = " [MECHANICAL CUT \u2014 needs a rewrite pass]" if f.get("suggestion_is_mechanical") else ""
                    print(f"    fix: {f['suggested']}{tag}")
            if len(findings) > 200:
                print(f"\n    ... and {len(findings) - 200} more")
        print("\n  Rule: <=150 chars, subject at character 1, self-contained when lifted alone.")

    if fail_on == "error":
        sys.exit(1 if errors else 0)
    if fail_on == "warn":
        sys.exit(1 if findings else 0)
    sys.exit(0)


if __name__ == "__main__":
    main()
