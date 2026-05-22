#!/usr/bin/env python3
"""
Tests for the repurposer publication safety gate.

Run with:
    python3 -m unittest tests.test_repurpose_safety -v

These tests are intentionally hermetic: no network, no filesystem, no secrets.
They lock in the deny-by-default contract documented in `repurpose_safety.py`.
"""

from __future__ import annotations

import os
import sys
import unittest

# Allow running both as `python -m unittest tests.test_repurpose_safety` from
# the repo root and as `python tests/test_repurpose_safety.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repurpose_safety import (  # noqa: E402
    PublicationRejected,
    enforce_publication,
    validate_publication,
)


def _normal_rss_article(**overrides) -> dict:
    """A baseline article shaped exactly like fetch_rss() output for a public,
    free Substack post — the only thing the pipeline should ever publish."""
    base = {
        "title": "10 Tools I Use To Run A Bestselling Substack Publication in 2026",
        "link": "https://karozieminski.substack.com/p/10-tools-i-use",
        "description": "A practical tour of the stack.",
        "datePublished": "2026-02-10",
        "wordCount": 1800,
        "isAccessibleForFree": True,
        "creator": "Karo Zieminski",
    }
    base.update(overrides)
    return base


class NormalArticleAllowed(unittest.TestCase):

    def test_normal_public_rss_article_is_allowed(self):
        decision = validate_publication(_normal_rss_article())
        self.assertTrue(decision.allowed, msg=decision.as_log_line())
        self.assertEqual(decision.rule, "allow")
        self.assertEqual(decision.visibility, "public")
        self.assertIn("canonical-host-allowed", decision.checks_passed)
        self.assertIn("deny-terms-clean", decision.checks_passed)
        self.assertIn("free-and-public", decision.checks_passed)

    def test_enforce_does_not_raise_on_normal_article(self):
        try:
            enforce_publication(_normal_rss_article())
        except PublicationRejected as e:  # pragma: no cover
            self.fail(f"enforce_publication raised on a normal article: {e}")


class InternalResearchBlocked(unittest.TestCase):

    def test_internal_research_markdown_is_blocked_by_title(self):
        a = _normal_rss_article(
            title="Internal Research: Competitor Pricing Tear-down",
        )
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "deny-term")
        self.assertIn("internal", decision.reason.lower())

    def test_research_slug_is_blocked(self):
        a = _normal_rss_article(slug="research-notes-on-perplexity")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "deny-term")

    def test_private_title_prefix_is_blocked(self):
        a = _normal_rss_article(title="[DRAFT] Half-finished thoughts on agents")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "private-title-prefix")

    def test_enforce_raises_publication_rejected(self):
        a = _normal_rss_article(title="Internal: do not publish")
        with self.assertRaises(PublicationRejected) as ctx:
            enforce_publication(a)
        self.assertFalse(ctx.exception.decision.allowed)


class LocalAndIntermediateFilesBlocked(unittest.TestCase):

    def test_reddit_teaser_filename_is_blocked(self):
        a = _normal_rss_article(filename="reddit-teaser-en-2026-05-22.txt")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "deny-filename")

    def test_draft_markdown_filename_is_blocked(self):
        a = _normal_rss_article(filename="my-post.draft.md")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "deny-filename")

    def test_tmp_prefixed_filename_is_blocked(self):
        a = _normal_rss_article(filename="tmp-scratch-output.md")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        # Could be matched by either filename pattern or deny term; both are fine.
        self.assertIn(decision.rule, {"deny-filename", "deny-term"})

    def test_generated_intermediate_artifact_is_blocked_by_slug(self):
        a = _normal_rss_article(slug="pipeline-output-2026-05-22")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "deny-term")


class MissingCanonicalBlocked(unittest.TestCase):

    def test_missing_canonical_url_is_blocked(self):
        a = _normal_rss_article(link="")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "missing-canonical-url")

    def test_non_https_canonical_is_blocked(self):
        a = _normal_rss_article(link="http://karozieminski.substack.com/p/foo")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        # Host allow-list runs before scheme check (host is fine) — so scheme
        # catches it next. Both rules are acceptable outcomes.
        self.assertIn(decision.rule, {"non-https-canonical"})

    def test_file_url_is_blocked(self):
        a = _normal_rss_article(link="file:///home/user/scratch/draft.md")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        # file:// has no host on the allowlist.
        self.assertEqual(decision.rule, "source-host-not-allowed")

    def test_off_host_canonical_is_blocked(self):
        a = _normal_rss_article(link="https://example.com/p/some-leaked-doc")
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "source-host-not-allowed")

    def test_mismatched_source_url_is_blocked(self):
        a = _normal_rss_article(
            link="https://karozieminski.substack.com/p/real",
            source_url="https://internal-notes.local/draft.md",
        )
        decision = validate_publication(a)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "source-host-not-allowed")


class SuspiciousTitleAndSlugBlocked(unittest.TestCase):

    def test_scratch_title_blocked(self):
        a = _normal_rss_article(title="Scratch: testing tone for next week")
        self.assertFalse(validate_publication(a).allowed)

    def test_prompts_term_blocked(self):
        a = _normal_rss_article(title="My system prompt for Claude")
        d = validate_publication(a)
        self.assertFalse(d.allowed)
        self.assertEqual(d.rule, "deny-term")

    def test_notes_term_blocked_as_whole_word(self):
        a = _normal_rss_article(title="Field notes from a Substack relaunch")
        self.assertFalse(validate_publication(a).allowed)

    def test_noteworthy_is_not_blocked_by_notes_term(self):
        # Whole-word matching: 'notes' must not flag 'noteworthy'.
        a = _normal_rss_article(title="Noteworthy patterns in PM hiring")
        self.assertTrue(validate_publication(a).allowed)

    def test_claude_md_substring_blocked(self):
        a = _normal_rss_article(slug="claude.md-conventions-for-our-repo")
        d = validate_publication(a)
        self.assertFalse(d.allowed)
        self.assertEqual(d.rule, "deny-term")


class PaywallStateMustBeExplicit(unittest.TestCase):

    def test_missing_is_free_field_is_denied(self):
        a = _normal_rss_article()
        del a["isAccessibleForFree"]
        d = validate_publication(a)
        self.assertFalse(d.allowed)
        self.assertEqual(d.rule, "paywall-status-unknown")

    def test_paid_article_is_skipped_with_distinct_rule(self):
        a = _normal_rss_article(isAccessibleForFree=False)
        d = validate_publication(a)
        self.assertFalse(d.allowed)
        self.assertEqual(d.rule, "paid-not-eligible")
        # paid is *eligible to exist*, just not for the public-gist path.
        self.assertEqual(d.visibility, "paid")


class DecisionLoggingDoesNotLeakBody(unittest.TestCase):
    """Defense-in-depth: a denied decision must be safe to print to logs."""

    def test_decision_log_line_does_not_contain_body(self):
        secret_body = "TOP SECRET research finding: <leak>"
        a = _normal_rss_article(
            title="Internal: pricing tear-down",
            description=secret_body,
        )
        # The dataclass intentionally doesn't accept body fields; even if a
        # caller stuffs them into the article dict, they must not surface.
        a["contentHtml"] = secret_body
        a["plainText"] = secret_body
        d = validate_publication(a)
        line = d.as_log_line()
        self.assertNotIn(secret_body, line)
        self.assertNotIn("TOP SECRET", line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
