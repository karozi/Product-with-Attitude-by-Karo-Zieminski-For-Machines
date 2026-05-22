# For Machines weekly quality audit: PAUSED

**Status:** Paused on 2026-05-22.
**Prior cron ID:** `8daa77e6` (Sundays 06:00 UTC).
**Action taken:** Cron deleted. Config preserved in the Perplexity Computer workspace at `cron_tracking/8daa77e6/PAUSED_CONFIG.json` for reinstatement after the fixes below.

## Why it was paused

The audit script reported wildly inconsistent article counts across consecutive weeks (150 → 24 → 0) while the live schema actually contains 335 articles (322 `Article` + 13 `BlogPosting`). It also reported 0% `articleSection` coverage and grade D every week.

Direct inspection of the live schema on 2026-05-22 confirmed the audit was wrong, not the schema:

- The schema has 335 articles, not 0.
- Articles live nested inside `@graph[].hasPart[]` and `@graph[].mainEntity[]`, not at the top level. The audit script was looking at the wrong depth.
- 57 cluster nodes exist as `DefinedTerm` entries in the schema. The audit script was looking for a different shape and reported `clusters_n=0`.
- `articleSection` is genuinely empty on most articles. PR #1 (Apr 19) tightened cluster signals on 79 articles, but the schema has nearly quadrupled since then via `repurposer` runs and the new articles never got enriched.

## Required before reinstating

1. Rewrite `scripts/quality/audit.py` to walk the nested `@graph` properly and recognise `DefinedTerm` cluster nodes.
2. Configure a git identity for the bot commit (last week's run escalated on "Author identity unknown"). Plan: `karozi-bot <bot@productwithattitude.com>`.
3. Re-run PR #1's cluster enrichment on the current 335-article schema so `articleSection`, `about`, and `genre` are populated.
4. Audit the `repurposer` pipeline to ensure new article inserts include the enrichment fields. If not, this whole loop repeats every time a new Substack post ships.

## Better long-term fix

Consider replacing the weekly audit cron with a write-time gate inside `repurposer`. Catch quality problems at the source instead of detecting them a week later on a Sunday morning. The cron approach has now failed twice (silent failure for 4 consecutive weeks). The write-time gate cannot drift silently because it runs whenever new content lands.

Karo Zieminski, Product with Attitude.
