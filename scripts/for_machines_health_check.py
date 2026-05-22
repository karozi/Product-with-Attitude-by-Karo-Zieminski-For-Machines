#!/usr/bin/env python3
"""
For Machines schema health checker.

Read-only end-to-end check across the three places the schema lives:
  1. Source repo (this one): for_machines.json + llms.txt at repo root.
  2. pwa-site mirror: assets/for_machines.json + llms.txt on the karozi/pwa-site repo.
  3. Live site: https://productwithattitude.com/assets/for_machines.json and /llms.txt.

Produces PASS / WARN / FAIL per check. Exits 0 if no FAILs, 1 otherwise.
WARN does not fail the run.

Usage:
    python3 scripts/for_machines_health_check.py
    python3 scripts/for_machines_health_check.py --no-live
    python3 scripts/for_machines_health_check.py --json
    python3 scripts/for_machines_health_check.py --linear-markdown
    python3 scripts/for_machines_health_check.py --timeout 20

No writes, no pushes, no Linear calls. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

DEFAULT_PWA_SITE_RAW = "https://raw.githubusercontent.com/karozi/pwa-site/main"
LIVE_BASE = "https://productwithattitude.com"

REQUIRED_IDS = ("#product-attitudevault", "#attitudevault-catalog", "#faq")

# Patterns we never want in a *URL value*. Most apply to the host segment of a
# URL only — applying them to the whole string would false-flag article slugs
# like ".../ai-tool-cant-access-localhost-...".
HOST_SUSPECT_PATTERNS = [
    re.compile(r"^localhost(?::\d+)?$", re.I),
    re.compile(r"^127\.0\.0\.1(?::\d+)?$"),
    re.compile(r"\.netlify\.app$", re.I),
    re.compile(r"^staging\.", re.I),
    re.compile(r"\.local$", re.I),
    # Bare .dev hosts (e.g. foo.dev). Real products like attitudevault.dev are
    # whitelisted by domain below.
]

# Hosts that look "staging-y" by suffix but are real production sites we ship.
HOST_ALLOWLIST = {
    "attitudevault.dev",
    "productwithattitude.com",
    "karozieminski.substack.com",
}

# Patterns applied to the whole URL string.
URL_SUSPECT_PATTERNS = [
    re.compile(r"^file://", re.I),
    re.compile(r"^/home/[^/]+/"),
    re.compile(r"^/Users/[^/]+/"),
    re.compile(r"^[A-Za-z]:\\\\Users\\\\", re.I),
]

URL_FIELD_HINTS = ("url", "href", "id", "sameas", "contenturl", "image", "logo")


# --- result model ---------------------------------------------------------

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> CheckResult:
        r = CheckResult(name=name, status=status, detail=detail)
        self.checks.append(r)
        return r

    def has_fail(self) -> bool:
        return any(c.status == FAIL for c in self.checks)

    def counts(self) -> dict[str, int]:
        c = Counter(check.status for check in self.checks)
        return {PASS: c[PASS], WARN: c[WARN], FAIL: c[FAIL]}


# --- helpers --------------------------------------------------------------


def http_get(url: str, timeout: float) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "for-machines-health-check/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read() if hasattr(e, "read") else b"", dict(e.headers or {})


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_html(body: bytes) -> bool:
    head = body[:512].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def is_suspect_url(val: str) -> bool:
    """True if a string looks like a leaked local/staging URL or workspace path."""
    if not isinstance(val, str) or not val:
        return False
    for pat in URL_SUSPECT_PATTERNS:
        if pat.search(val):
            return True
    # Only inspect the host of http(s) URLs — slugs are not hosts.
    m = re.match(r"^https?://([^/?#]+)", val, re.I)
    if not m:
        return False
    host = m.group(1).split("@")[-1]  # strip userinfo if any
    bare_host = host.split(":")[0].lower()
    if bare_host in HOST_ALLOWLIST:
        return False
    for pat in HOST_SUSPECT_PATTERNS:
        if pat.search(host):
            return True
    # Bare .dev TLDs that aren't in the allowlist are suspicious.
    if bare_host.endswith(".dev"):
        return True
    return False


def walk_url_like_strings(node: Any, path: str = ""):
    """Yield (json_path, value) for any string field that looks URL-ish."""
    if isinstance(node, dict):
        for k, v in node.items():
            sub = f"{path}.{k}" if path else k
            if isinstance(v, str) and any(h in k.lower() for h in URL_FIELD_HINTS):
                yield sub, v
            else:
                yield from walk_url_like_strings(v, sub)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_url_like_strings(v, f"{path}[{i}]")


def llms_item_count(text: str) -> int | None:
    """Best-effort count of catalog-style item lines in llms.txt.

    Returns None when we can't confidently identify a catalog block — the format
    is loose enough that a false positive is worse than no signal. We require
    at least 3 list-style lines to call something a list.
    """
    count = 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^(?:[-*]|\d+\.)\s+.*https?://", s):
            count += 1
    return count if count >= 3 else None


# --- individual checks ----------------------------------------------------


def check_source_files(repo_root: Path, report: Report) -> tuple[bytes | None, bytes | None]:
    fm_path = repo_root / "for_machines.json"
    llms_path = repo_root / "llms.txt"

    fm_bytes = llms_bytes = None

    if fm_path.is_file():
        fm_bytes = fm_path.read_bytes()
        report.add("source.for_machines.json exists", PASS, str(fm_path))
    else:
        report.add("source.for_machines.json exists", FAIL, f"missing: {fm_path}")

    if llms_path.is_file():
        llms_bytes = llms_path.read_bytes()
        report.add("source.llms.txt exists", PASS, str(llms_path))
    else:
        report.add("source.llms.txt exists", FAIL, f"missing: {llms_path}")

    return fm_bytes, llms_bytes


def check_json_shape(fm_bytes: bytes | None, report: Report) -> dict | None:
    if not fm_bytes:
        report.add("source.json parses", FAIL, "no source file")
        return None
    try:
        doc = json.loads(fm_bytes)
    except json.JSONDecodeError as e:
        report.add("source.json parses", FAIL, f"{e}")
        return None
    report.add("source.json parses", PASS, "")

    if not isinstance(doc, dict) or "@context" not in doc:
        report.add("source.json has @context", FAIL, "missing @context")
    else:
        report.add("source.json has @context", PASS, "")

    graph = doc.get("@graph") if isinstance(doc, dict) else None
    if not isinstance(graph, list) or len(graph) == 0:
        report.add("source.json @graph non-empty", FAIL, "missing or empty @graph")
        return doc

    report.add("source.json @graph non-empty", PASS, f"{len(graph)} nodes")

    ids = [n.get("@id") for n in graph if isinstance(n, dict)]
    id_set = {i for i in ids if isinstance(i, str)}

    for req in REQUIRED_IDS:
        if req in id_set:
            report.add(f"source.json has node {req}", PASS, "")
        else:
            report.add(f"source.json has node {req}", FAIL, "missing required @id")

    dupes = [i for i, n in Counter(i for i in ids if i).items() if n > 1]
    if dupes:
        report.add(
            "source.json @id uniqueness",
            FAIL,
            "duplicate @id: " + ", ".join(sorted(dupes)),
        )
    else:
        report.add("source.json @id uniqueness", PASS, "")

    # suspect URL scan
    bad = []
    for jpath, val in walk_url_like_strings(doc):
        if is_suspect_url(val):
            bad.append(f"{jpath}={val}")
    if bad:
        sample = "; ".join(bad[:3])
        more = "" if len(bad) <= 3 else f" (+{len(bad) - 3} more)"
        report.add("source.json no local/staging URLs", WARN, sample + more)
    else:
        report.add("source.json no local/staging URLs", PASS, "")

    return doc


def check_catalog_vs_llms(
    doc: dict | None, llms_bytes: bytes | None, report: Report
) -> None:
    if not doc or not llms_bytes:
        return
    graph = doc.get("@graph") if isinstance(doc, dict) else None
    if not isinstance(graph, list):
        return
    catalog = next(
        (n for n in graph if isinstance(n, dict) and n.get("@id") == "#attitudevault-catalog"),
        None,
    )
    if not catalog:
        return
    items = catalog.get("itemListElement")
    catalog_count = (
        catalog.get("numberOfItems")
        if isinstance(catalog.get("numberOfItems"), int)
        else (len(items) if isinstance(items, list) else None)
    )
    if catalog_count is None:
        return

    llms_count = llms_item_count(llms_bytes.decode("utf-8", errors="replace"))
    if llms_count is None:
        report.add(
            "llms.txt item count vs catalog",
            WARN,
            f"could not detect a list in llms.txt; catalog has {catalog_count}",
        )
        return
    if llms_count == catalog_count:
        report.add(
            "llms.txt item count vs catalog",
            PASS,
            f"both={catalog_count}",
        )
    else:
        report.add(
            "llms.txt item count vs catalog",
            WARN,
            f"llms.txt={llms_count}, catalog={catalog_count}",
        )


def check_mirror(
    fm_bytes: bytes | None,
    llms_bytes: bytes | None,
    mirror_base: str,
    timeout: float,
    report: Report,
) -> tuple[bytes | None, bytes | None]:
    mirror_fm = mirror_llms = None

    fm_url = f"{mirror_base.rstrip('/')}/assets/for_machines.json"
    llms_url = f"{mirror_base.rstrip('/')}/llms.txt"

    try:
        status, body, _ = http_get(fm_url, timeout)
        if status == 200:
            mirror_fm = body
            report.add("mirror.for_machines.json reachable", PASS, fm_url)
        else:
            report.add("mirror.for_machines.json reachable", FAIL, f"{fm_url} -> {status}")
    except Exception as e:
        report.add("mirror.for_machines.json reachable", FAIL, f"{fm_url}: {e}")

    try:
        status, body, _ = http_get(llms_url, timeout)
        if status == 200:
            mirror_llms = body
            report.add("mirror.llms.txt reachable", PASS, llms_url)
        else:
            report.add("mirror.llms.txt reachable", FAIL, f"{llms_url} -> {status}")
    except Exception as e:
        report.add("mirror.llms.txt reachable", FAIL, f"{llms_url}: {e}")

    if fm_bytes and mirror_fm is not None:
        if sha256(fm_bytes) == sha256(mirror_fm):
            report.add("source==mirror for_machines.json", PASS, "")
        else:
            report.add(
                "source==mirror for_machines.json",
                FAIL,
                f"sha source={sha256(fm_bytes)[:12]} mirror={sha256(mirror_fm)[:12]}",
            )

    if llms_bytes and mirror_llms is not None:
        if sha256(llms_bytes) == sha256(mirror_llms):
            report.add("source==mirror llms.txt", PASS, "")
        else:
            report.add(
                "source==mirror llms.txt",
                FAIL,
                f"sha source={sha256(llms_bytes)[:12]} mirror={sha256(mirror_llms)[:12]}",
            )

    return mirror_fm, mirror_llms


def check_live(
    mirror_fm: bytes | None,
    mirror_llms: bytes | None,
    timeout: float,
    report: Report,
) -> None:
    fm_url = f"{LIVE_BASE}/assets/for_machines.json"
    llms_url = f"{LIVE_BASE}/llms.txt"

    # JSON
    live_fm = None
    try:
        status, body, headers = http_get(fm_url, timeout)
        if status != 200:
            report.add("live.for_machines.json 200", FAIL, f"{fm_url} -> {status}")
        else:
            report.add("live.for_machines.json 200", PASS, fm_url)
            live_fm = body
            try:
                json.loads(body)
                report.add("live.for_machines.json parses", PASS, "")
            except json.JSONDecodeError as e:
                report.add("live.for_machines.json parses", FAIL, str(e))
    except Exception as e:
        report.add("live.for_machines.json 200", FAIL, f"{fm_url}: {e}")

    # llms.txt
    live_llms = None
    try:
        status, body, headers = http_get(llms_url, timeout)
        if status != 200:
            report.add("live.llms.txt 200", FAIL, f"{llms_url} -> {status}")
        else:
            report.add("live.llms.txt 200", PASS, llms_url)
            live_llms = body
            if is_html(body):
                report.add(
                    "live.llms.txt looks like text",
                    FAIL,
                    "response starts with HTML markup (likely SPA fallback)",
                )
            else:
                report.add("live.llms.txt looks like text", PASS, "")
    except Exception as e:
        report.add("live.llms.txt 200", FAIL, f"{llms_url}: {e}")

    # cross-check vs mirror
    if mirror_fm is not None and live_fm is not None:
        if sha256(mirror_fm) == sha256(live_fm):
            report.add("live==mirror for_machines.json", PASS, "")
        else:
            report.add(
                "live==mirror for_machines.json",
                FAIL,
                f"sha mirror={sha256(mirror_fm)[:12]} live={sha256(live_fm)[:12]}",
            )
    if mirror_llms is not None and live_llms is not None:
        if sha256(mirror_llms) == sha256(live_llms):
            report.add("live==mirror llms.txt", PASS, "")
        else:
            report.add(
                "live==mirror llms.txt",
                FAIL,
                f"sha mirror={sha256(mirror_llms)[:12]} live={sha256(live_llms)[:12]}",
            )


# --- output renderers -----------------------------------------------------


def render_text(report: Report) -> str:
    width = max((len(c.name) for c in report.checks), default=0)
    lines = []
    for c in report.checks:
        lines.append(f"  [{c.status:<4}] {c.name:<{width}}  {c.detail}".rstrip())
    counts = report.counts()
    lines.append("")
    lines.append(
        f"Summary: PASS={counts[PASS]}  WARN={counts[WARN]}  FAIL={counts[FAIL]}"
    )
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(
        {
            "checks": [c.to_dict() for c in report.checks],
            "summary": report.counts(),
            "ok": not report.has_fail(),
        },
        indent=2,
    )


def render_linear_markdown(report: Report) -> str:
    """A Linear-safe report block.

    Contains only live/public URLs and check names — no workspace paths, no
    hostnames, no secrets. Another approved automation can paste this verbatim.
    """
    counts = report.counts()
    overall = "FAIL" if counts[FAIL] else ("WARN" if counts[WARN] else "PASS")
    lines = [
        "## For Machines health check",
        "",
        f"**Status:** {overall}  ·  PASS {counts[PASS]} · WARN {counts[WARN]} · FAIL {counts[FAIL]}",
        "",
        "| Status | Check | Notes |",
        "|---|---|---|",
    ]
    safe_url = re.compile(r"https://(?:productwithattitude\.com|raw\.githubusercontent\.com)/\S+")
    for c in report.checks:
        # Only let through publicly reachable URLs; strip everything else.
        urls = safe_url.findall(c.detail or "")
        notes = " ".join(urls) if urls else ""
        lines.append(f"| {c.status} | {c.name} | {notes} |")
    return "\n".join(lines)


# --- self-test ------------------------------------------------------------


def self_test() -> int:
    """Lightweight self-test using a tempdir. Returns 0 on success."""
    import tempfile

    failures: list[str] = []

    def expect(cond: bool, msg: str):
        if not cond:
            failures.append(msg)

    # --- happy path: minimal valid doc + matching llms list ---
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        doc = {
            "@context": "https://schema.org",
            "@graph": [
                {"@id": "#product-attitudevault", "url": "https://productwithattitude.com/"},
                {
                    "@id": "#attitudevault-catalog",
                    "numberOfItems": 3,
                    "itemListElement": [
                        {"url": "https://productwithattitude.com/a"},
                        {"url": "https://productwithattitude.com/b"},
                        {"url": "https://productwithattitude.com/c"},
                    ],
                },
                {"@id": "#faq"},
            ],
        }
        (root / "for_machines.json").write_text(json.dumps(doc))
        (root / "llms.txt").write_text(
            "# llms.txt\n\n## Articles\n"
            "- First https://productwithattitude.com/a\n"
            "- Second https://productwithattitude.com/b\n"
            "- Third https://productwithattitude.com/c\n"
        )
        rep = Report()
        fm, llms = check_source_files(root, rep)
        parsed = check_json_shape(fm, rep)
        check_catalog_vs_llms(parsed, llms, rep)
        expect(not rep.has_fail(), f"happy path should not fail: {render_text(rep)}")
        expect(
            any(c.name == "llms.txt item count vs catalog" and c.status == PASS for c in rep.checks),
            "expected matching catalog/llms counts",
        )

    # --- missing required @id + duplicate @id + local URL ---
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bad = {
            "@context": "https://schema.org",
            "@graph": [
                {"@id": "#product-attitudevault", "url": "http://localhost:8080/preview"},
                {"@id": "#product-attitudevault"},  # duplicate
                # missing #attitudevault-catalog and #faq
            ],
        }
        (root / "for_machines.json").write_text(json.dumps(bad))
        (root / "llms.txt").write_text("# llms.txt\n")
        rep = Report()
        fm, llms = check_source_files(root, rep)
        check_json_shape(fm, rep)
        expect(rep.has_fail(), "expected at least one FAIL on bad doc")
        statuses = {c.name: c.status for c in rep.checks}
        expect(
            statuses.get("source.json has node #attitudevault-catalog") == FAIL,
            "missing catalog node should FAIL",
        )
        expect(
            statuses.get("source.json @id uniqueness") == FAIL,
            "duplicate @id should FAIL",
        )
        expect(
            statuses.get("source.json no local/staging URLs") == WARN,
            "localhost URL should WARN",
        )

    # --- malformed JSON ---
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "for_machines.json").write_text("{not valid json")
        (root / "llms.txt").write_text("x")
        rep = Report()
        fm, _ = check_source_files(root, rep)
        check_json_shape(fm, rep)
        expect(
            any(c.name == "source.json parses" and c.status == FAIL for c in rep.checks),
            "broken json should FAIL parse",
        )

    # --- is_html detector ---
    expect(is_html(b"<!DOCTYPE html><html>"), "is_html should catch real HTML")
    expect(not is_html(b"# llms.txt\nhello"), "is_html should pass plain text")

    # --- llms_item_count ---
    expect(
        llms_item_count(
            "- a https://x.com/1\n- b https://x.com/2\n- c https://x.com/3"
        )
        == 3,
        "count three list items",
    )
    expect(
        llms_item_count("- a https://x.com/1\n- b https://x.com/2") is None,
        "two items is under threshold, should be None",
    )
    expect(
        llms_item_count("nothing here") is None,
        "should return None when no list found",
    )

    # --- is_suspect_url: slugs containing 'localhost' aren't suspect ---
    expect(
        not is_suspect_url("https://karozieminski.substack.com/p/access-localhost-fix"),
        "article slug with 'localhost' should not warn",
    )
    expect(
        is_suspect_url("http://localhost:8080/preview"),
        "real localhost URL should warn",
    )
    expect(
        not is_suspect_url("https://attitudevault.dev/item/foo"),
        "allowlisted .dev host should not warn",
    )
    expect(
        is_suspect_url("https://random-thing.dev/x"),
        "non-allowlisted .dev host should warn",
    )
    expect(
        is_suspect_url("https://staging.example.com/x"),
        "staging.* host should warn",
    )
    expect(
        is_suspect_url("file:///home/user/for_machines.json"),
        "file:// URL should warn",
    )

    # --- linear markdown is workspace-path free ---
    rep = Report()
    rep.add("x", PASS, "/home/user/secret/path and https://productwithattitude.com/llms.txt")
    md = render_linear_markdown(rep)
    expect("/home/user" not in md, "linear markdown must not leak workspace paths")
    expect("productwithattitude.com/llms.txt" in md, "should keep safe public URL")

    if failures:
        print("SELF-TEST FAILED:")
        for f in failures:
            print(" -", f)
        return 1
    print("SELF-TEST OK")
    return 0


# --- main -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    p.add_argument(
        "--repo-root",
        default=".",
        help="Path to the For Machines repo root (default: current dir).",
    )
    p.add_argument("--no-live", action="store_true", help="Skip live HTTP checks.")
    p.add_argument(
        "--no-mirror",
        action="store_true",
        help="Skip pwa-site mirror checks (also disables source==mirror compare).",
    )
    p.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout seconds.")
    p.add_argument(
        "--mirror-base",
        default=DEFAULT_PWA_SITE_RAW,
        help=(
            "Raw base URL for the pwa-site mirror. Default points at the "
            "karozi/pwa-site GitHub repo; override if the mirror lives elsewhere."
        ),
    )
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    p.add_argument(
        "--linear-markdown",
        action="store_true",
        help="Linear-safe markdown report. Does not touch Linear.",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run internal sanity tests instead of the real check.",
    )
    return p


def run(args: argparse.Namespace) -> Report:
    repo_root = Path(args.repo_root).resolve()
    report = Report()

    fm, llms = check_source_files(repo_root, report)
    doc = check_json_shape(fm, report)
    check_catalog_vs_llms(doc, llms, report)

    mirror_fm = mirror_llms = None
    if not args.no_mirror:
        mirror_fm, mirror_llms = check_mirror(
            fm, llms, args.mirror_base, args.timeout, report
        )

    if not args.no_live:
        check_live(mirror_fm, mirror_llms, args.timeout, report)

    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.self_test:
        return self_test()

    report = run(args)

    if args.json:
        print(render_json(report))
    elif args.linear_markdown:
        print(render_linear_markdown(report))
    else:
        print(render_text(report))

    return 1 if report.has_fail() else 0


if __name__ == "__main__":
    sys.exit(main())
