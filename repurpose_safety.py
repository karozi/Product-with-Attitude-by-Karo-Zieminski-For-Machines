#!/usr/bin/env python3
"""
Repurposer publication safety gate.

Deny-by-default validation that protects the public Gist / Dev.to / Bluesky
publication path from accidentally exposing internal research, drafts, scratch
notes, prompt docs, or generated pipeline artifacts.

The pipeline that imports this module is private (Computer skill). This file
lives in the public repo so that:
  - the safety rules are reviewable and testable in the open,
  - the same `validate_publication` is the single chokepoint used by every
    publisher (Gist, Dev.to, Qiita, Bluesky, Reddit).

Usage from the pipeline:

    from repurpose_safety import validate_publication, PublicationRejected

    decision = validate_publication(article)
    if not decision.allowed:
        log_skip(decision)            # safe — never prints content
        continue
    publish_gist(...)

The decision object never carries article body content, only metadata and the
reason for rejection — so safety logs can be emitted without leaking drafts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse


# ─── Configuration ──────────────────────────────────────────────────────────

# Hosts that are accepted as canonical public sources. Anything else is denied.
# Keep this list short and explicit. Subdomains are matched exactly — wildcard
# expansion is intentionally avoided.
ALLOWED_SOURCE_HOSTS: frozenset[str] = frozenset({
    "karozieminski.substack.com",
    "www.karozieminski.substack.com",
})

# Substrings (case-insensitive) that, if found anywhere in the title, slug,
# source path, or filename, cause the artifact to be rejected. These cover the
# common shapes of internal work product that has historically slipped through.
DENY_TERMS: tuple[str, ...] = (
    # workflow status
    "internal", "private", "confidential", "do-not-publish", "do not publish",
    "unpublished", "wip", "work-in-progress", "work in progress",
    # drafting / scratch
    "draft", "drafts", "scratch", "scratchpad", "sandbox",
    "notes", "memo", "todo", "fixme",
    # research / pre-publication
    "research", "research-doc", "research-notes", "investigation",
    "exploration", "exploratory", "spike",
    # pipeline output
    "pipeline-output", "pipeline_output", "intermediate", "tmp",
    "temp", "temporary", "cache", "cached", "generated",
    # prompt / instruction docs
    "prompt-doc", "prompt-docs", "prompts", "system-prompt", "instructions",
    # source-control / agent artifacts
    "claude.md", "agents.md", "readme-internal", "for-machines-only",
)

# Filename patterns that look like pipeline / scratch output. Filename match is
# in addition to the title/slug DENY_TERMS check.
DENY_FILENAME_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)^reddit-teaser-.*\.txt$"),
    re.compile(r"(?i).*\.draft\.md$"),
    re.compile(r"(?i).*\.scratch\.md$"),
    re.compile(r"(?i)^(tmp|temp|cache|_)"),
    re.compile(r"(?i).*\.local\.md$"),
)

# Title prefixes Substack uses for private posts. If the RSS happens to expose
# any of these we still want to refuse to publish.
PRIVATE_TITLE_PREFIXES: tuple[str, ...] = (
    "[draft]", "[internal]", "[private]", "[wip]", "[research]",
)


# ─── Decision type ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PublicationDecision:
    """Result of evaluating a candidate artifact for public publication.

    Carries metadata only — never the article body — so it is safe to log.
    """
    allowed: bool
    reason: str
    rule: str = ""
    title: str = ""
    slug: str = ""
    source_url: str = ""
    canonical_url: str = ""
    visibility: str = "private"  # "public" only when allowed=True
    checks_passed: tuple[str, ...] = field(default_factory=tuple)

    def as_log_line(self) -> str:
        verdict = "ALLOW" if self.allowed else "DENY"
        return (
            f"[{verdict}] rule={self.rule or 'n/a'} "
            f"visibility={self.visibility} "
            f"title={_short(self.title)!r} "
            f"slug={self.slug!r} "
            f"source={self.source_url!r} "
            f"reason={self.reason}"
        )


class PublicationRejected(Exception):
    """Raised by `enforce_publication` when an artifact is denied."""

    def __init__(self, decision: PublicationDecision):
        super().__init__(decision.reason)
        self.decision = decision


# ─── Public API ─────────────────────────────────────────────────────────────

def validate_publication(
    article: dict,
    *,
    allowed_hosts: Iterable[str] | None = None,
    extra_deny_terms: Iterable[str] | None = None,
) -> PublicationDecision:
    """Decide whether `article` may be published to a public destination.

    Deny-by-default: every required field must be present and recognized.
    Returns a `PublicationDecision`. Never raises.

    Required fields on `article`:
      - title:           non-empty string
      - link:            canonical/public source URL (must be on an allowed host)
      - isAccessibleForFree: True (paid posts are skipped, not denied — but a
                              missing key is treated as a denial)

    Optional but checked when present:
      - slug             — checked against deny terms
      - filename         — checked against deny patterns
      - source_url       — alternate origin (also host-checked)
    """
    hosts = frozenset(allowed_hosts) if allowed_hosts is not None else ALLOWED_SOURCE_HOSTS
    deny_terms = tuple(DENY_TERMS) + tuple(extra_deny_terms or ())

    title = (article.get("title") or "").strip()
    link = (article.get("link") or "").strip()
    source_url = (article.get("source_url") or link).strip()
    slug = (article.get("slug") or _derive_slug(title)).strip()
    filename = (article.get("filename") or "").strip()
    is_free = article.get("isAccessibleForFree")

    passed: list[str] = []

    # 1. Title must exist.
    if not title:
        return _deny("missing-title", "Artifact has no title", title, slug, source_url, link)
    passed.append("title-present")

    # 2. Private-title prefix.
    lower_title = title.lower()
    for prefix in PRIVATE_TITLE_PREFIXES:
        if lower_title.startswith(prefix):
            return _deny(
                "private-title-prefix",
                f"Title begins with private marker {prefix!r}",
                title, slug, source_url, link,
            )
    passed.append("title-prefix-ok")

    # 3. Canonical/public URL must be present.
    if not link:
        return _deny(
            "missing-canonical-url",
            "No canonical/public URL on article — refuse to publish",
            title, slug, source_url, link,
        )
    passed.append("canonical-url-present")

    # 4. Canonical/public URL host must be on the allowlist.
    canonical_host = _host_of(link)
    if canonical_host not in hosts:
        return _deny(
            "source-host-not-allowed",
            f"Canonical host {canonical_host!r} is not on the allowlist",
            title, slug, source_url, link,
        )
    passed.append("canonical-host-allowed")

    # 5. If source_url is different from link, it must also be allowlisted.
    if source_url and source_url != link:
        source_host = _host_of(source_url)
        if source_host not in hosts:
            return _deny(
                "source-host-not-allowed",
                f"Source host {source_host!r} is not on the allowlist",
                title, slug, source_url, link,
            )
        passed.append("source-host-allowed")

    # 6. URL scheme must be https. Anything else (file://, http://localhost…)
    #    is a strong sign of a local artifact masquerading as canonical.
    if urlparse(link).scheme != "https":
        return _deny(
            "non-https-canonical",
            "Canonical URL is not https — refusing",
            title, slug, source_url, link,
        )
    passed.append("scheme-https")

    # 7. Title / slug / source path must not match any deny term.
    haystack = " | ".join((lower_title, slug.lower(), urlparse(link).path.lower()))
    for term in deny_terms:
        if _term_hit(term, haystack):
            return _deny(
                "deny-term",
                f"Matched internal/scratch deny term {term!r}",
                title, slug, source_url, link,
            )
    passed.append("deny-terms-clean")

    # 8. Filename, if supplied, must not match a pipeline-output pattern.
    if filename:
        for rx in DENY_FILENAME_REGEXES:
            if rx.match(filename):
                return _deny(
                    "deny-filename",
                    f"Filename matches pipeline/scratch pattern: {rx.pattern}",
                    title, slug, source_url, link,
                )
        passed.append("filename-ok")

    # 9. Paywall status must be explicit. Missing field → deny.
    if is_free is None:
        return _deny(
            "paywall-status-unknown",
            "isAccessibleForFree is missing — cannot determine if public",
            title, slug, source_url, link,
        )
    if is_free is not True:
        # Paid posts are not denied as unsafe — they're simply not eligible for
        # the public-gist path. Caller treats this as a skip, same as a deny,
        # but the rule name makes the difference visible in logs.
        return _deny(
            "paid-not-eligible",
            "Paid article — not eligible for public repurposing",
            title, slug, source_url, link, visibility="paid",
        )
    passed.append("free-and-public")

    return PublicationDecision(
        allowed=True,
        reason="All publication checks passed",
        rule="allow",
        title=title,
        slug=slug,
        source_url=source_url,
        canonical_url=link,
        visibility="public",
        checks_passed=tuple(passed),
    )


def enforce_publication(article: dict, **kwargs) -> PublicationDecision:
    """Validate and raise `PublicationRejected` on denial.

    Use this at the immediate boundary of any publisher call to make accidental
    bypass impossible: ``enforce_publication(article); publish_gist(...)`` is
    safe regardless of upstream changes.
    """
    decision = validate_publication(article, **kwargs)
    if not decision.allowed:
        raise PublicationRejected(decision)
    return decision


# ─── Helpers ────────────────────────────────────────────────────────────────

def _deny(
    rule: str,
    reason: str,
    title: str,
    slug: str,
    source_url: str,
    canonical_url: str,
    visibility: str = "private",
) -> PublicationDecision:
    return PublicationDecision(
        allowed=False,
        reason=reason,
        rule=rule,
        title=title,
        slug=slug,
        source_url=source_url,
        canonical_url=canonical_url,
        visibility=visibility,
    )


def _host_of(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _derive_slug(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")[:80]


def _term_hit(term: str, haystack: str) -> bool:
    """Match a deny term against title/slug/path.

    Multi-word terms are checked as substrings. Single-word terms must appear
    as whole tokens (separated by non-word chars) to avoid e.g. flagging
    'noteworthy' because of 'notes'.
    """
    term = term.lower().strip()
    if not term:
        return False
    if " " in term or "-" in term or "_" in term or "." in term:
        return term in haystack
    return re.search(rf"(?:^|\W){re.escape(term)}(?:\W|$)", haystack) is not None


def _short(s: str, limit: int = 80) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"
