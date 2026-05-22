# Repurposer publication safety

After an incident where the repurposer pipeline occasionally published
internal research docs as public Gists, the public-publication path is now
guarded by a deny-by-default validation layer.

## Files

- [`repurpose_safety.py`](repurpose_safety.py) — the safety gate. A single
  function, `validate_publication(article)`, returns a `PublicationDecision`
  with `allowed: bool` and a machine-readable `rule`. `enforce_publication`
  wraps it and raises `PublicationRejected` on denial.
- [`tests/test_repurpose_safety.py`](tests/test_repurpose_safety.py) — 23
  hermetic tests covering allow, deny-by-title, deny-by-slug, deny-by-
  filename, missing canonical URL, off-host source, paywall handling, and a
  log-line leak check.

## Safety model

Every artifact that reaches a public publisher (Gist, Dev.to, Qiita,
Bluesky) must pass all of the following:

1. **Title present** and not prefixed with `[draft]` / `[internal]` /
   `[private]` / `[wip]` / `[research]`.
2. **Canonical URL present**, `https://`, and on the **host allowlist**
   (currently `karozieminski.substack.com`).
3. **Source URL** (when distinct from canonical) also on the allowlist.
4. **Title / slug / URL path** must not contain any deny term — covering
   `internal`, `private`, `confidential`, `draft`, `scratch`, `notes`,
   `research`, `prompt`, `pipeline-output`, `tmp`, `temp`, `cache`,
   `generated`, `claude.md`, `agents.md`, and similar.
5. **Filename** (when supplied) must not match a pipeline-output pattern
   (`reddit-teaser-*.txt`, `*.draft.md`, `*.scratch.md`, `tmp*`, `*.local.md`).
6. **`isAccessibleForFree`** must be explicitly `True`. Missing → deny.
   Paid → distinct `paid-not-eligible` rule (skipped, not unsafe).

Whole-word matching is used for single-word deny terms so `notes` does not
flag `noteworthy`. Multi-word/hyphenated/dotted terms are matched as
substrings.

## Calling from the private repurposer pipeline

```python
from repurpose_safety import enforce_publication, PublicationRejected

for article in new_articles:
    try:
        decision = enforce_publication(article)
    except PublicationRejected as e:
        print(f"      SKIP {e.decision.as_log_line()}")
        continue
    publish_gist(gist_token, article, create_gist_content(article))
```

`PublicationDecision.as_log_line()` is the only thing that should be logged
about a denial — it carries metadata (title, slug, source, rule, reason)
but never article body, description, or content HTML.

## Running the tests

```bash
python3 -m unittest tests.test_repurpose_safety -v
```

No network, filesystem, or credentials required.

## Operational follow-ups

- Wire `enforce_publication` into the private Computer skill at the
  top of every publisher loop (Gist, Dev.to, Qiita, Bluesky).
- Extend `ALLOWED_SOURCE_HOSTS` only with an explicit code change — never
  by configuration, env var, or CLI flag.
- Audit any past Gists that may have leaked internal research and delete
  them; the gate is preventative, not retroactive.
- Rotate any tokens that were embedded in artifacts or sat next to
  drafts on disk during the incident window.
