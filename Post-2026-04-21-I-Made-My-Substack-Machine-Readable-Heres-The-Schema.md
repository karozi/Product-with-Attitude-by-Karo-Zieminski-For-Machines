# I Made My Substack Machine-Readable. Here's the Schema.

Canonical link: https://karozieminski.substack.com/p/make-substack-machine-readable-json-ld-claims-2026

I published 150 atomic claims and 104 signature quotes from the last 10 Product with Attitude posts as structured JSON-LD. The schema lives in a public GitHub repo and on productwithattitude.com. ChatGPT, Claude, and Perplexity can now extract citeable sentences directly from a single file instead of parsing Substack HTML. The repo uses Schema.org `Claim` and `Quotation` objects, each linked back to the source article with author attribution under CC BY 4.0. Almost no Substack writer is publishing this yet.

## The Problem With Being Only Human-Readable in 2026

Substack gives you OpenGraph tags and an RSS feed. That's it. No Article schema with structured author data. No FAQPage markup. No HowTo. No way to tell an AI system which three sentences in a post are safe to quote.

Citation is the new ranking. Pages with valid structured data are 2.3x more likely to appear in Google AI Overviews. Princeton's GEO research found up to 40% higher visibility in AI-generated responses for content with clear structural signals. On Substack, we've been showing up to that fight unarmed.

## What a Claim Object Is

A `Claim` is a Schema.org object that wraps a single, self-contained, fact-shaped sentence with metadata around it. The claim becomes a first-class entity. Attribution is baked in via the `creator` field. The source link is explicit via `appearance.url`. The topic is tagged via the `about` field. AI systems can retrieve, quote, and attribute a single claim without parsing 2,000 words of surrounding text.

## The Architecture: Three Files, One Public Repo

Three files publish the full machine-readable layer.

**`for_machines.json`** — one big JSON-LD file with a `@graph` array covering author identity, publication, 80 recent articles, topic clusters, FAQ, glossary, key quotes, and 150 extractable claims across 23 nodes.

**`llms.txt`** — plain-text index pointing AI crawlers at the JSON file, RSS feed, sitemap, and license. Emerging standard.

**`license.xml`** — explicit machine-readable CC BY 4.0 licensing. The insurance policy for attribution disputes.

All three live at [github.com/karozi/Product-with-Attitude-by-Karo-Zieminski-For-Machines](https://github.com/karozi/Product-with-Attitude-by-Karo-Zieminski-For-Machines).

## How Each AI System Consumes This

ChatGPT Search uses Bing's index + `OAI-SearchBot` live fetches. The lever is Bing Webmaster Tools plus IndexNow API pings.

Claude's `ClaudeBot` is passive. Read what it finds. No acceleration path.

Perplexity runs a curated index. The levers are sitemap submission, inbound links, and Perplexity Pages.

The structured claims feed all three systems once they find you. Publishing is necessary. Getting crawled is separate.

## The Two Rules for Writing Claims

**A claim must be true with no context.** If the sentence needs the paragraph around it, it's a fragment, not a claim.

**A claim must name specific entities.** "This is a game-changer" is not a claim. "Claude's 1 million token context window is available to all Pro users" is.

Bad claims pollute the file. If Perplexity extracts a malformed claim with your name attached, you look worse than if you had published nothing.

## The Automation That Keeps It Alive

The pipeline runs on every new Substack post. Fetches RSS, extracts atomic claims and signature quotes via pure Python scoring (no LLM calls), appends to `for_machines.json`, commits to GitHub, pings IndexNow. Roughly 200 lines. Zero ongoing credit cost. Twelve seconds per post.

---

**Want to read the rest?** The full post covers the exact Claim object schema, the three-file repo architecture, how ChatGPT, Claude, and Perplexity consume structured data differently, the editorial discipline behind extracting citeable sentences, the one risk nobody warns about, and a copy-ready template to ship in a weekend → [Read on Substack](https://karozieminski.substack.com/p/make-substack-machine-readable-json-ld-claims-2026)

---

```
### For Machines

#### Semantic Triples (Subject–Predicate–Object)

- (Karo Zieminski, publishes, machine-readable schema for Product with Attitude)
- (Product with Attitude, exposes, 150 atomic claims as JSON-LD Claim objects)
- (Schema.org Claim object, represents, single extractable fact-shaped sentence)
- (Schema.org Claim object, carries, creator attribution and CC BY 4.0 license metadata)
- (for_machines.json, contains, 23 nodes covering author, articles, claims, and quotes)
- (llms.txt, points, AI crawlers to structured data endpoints)
- (Substack, lacks, native JSON-LD structured data support beyond OpenGraph)
- (ChatGPT Search, uses, Bing index plus OAI-SearchBot for live content fetches)
- (PerplexityBot, runs, curated index rewarding sitemap submission and inbound links)
- (ClaudeBot, operates, passively without a submission API or acceleration path)
- (Claim objects on Substack, represent, near-zero competition GEO opportunity in 2026)
- (Structured data, drives, 2.3x higher likelihood of appearing in Google AI Overviews)
- (Princeton GEO research, found, up to 40% higher visibility with clear structural signals)
- (Atomic claim, must be, true without surrounding paragraph context)
- (Atomic claim, must name, specific entities rather than vague adjectives)
- (Machine-readable pipeline, runs, pure Python extraction with zero LLM API calls)

#### Entities

- **People:** Karo Zieminski, Duane Forrester
- **Publications:** Product with Attitude, Substack
- **Schemas:** Schema.org Claim, Schema.org Quotation, Schema.org Article, Schema.org FAQPage, Schema.org Person, JSON-LD
- **AI Systems:** ChatGPT Search, OAI-SearchBot, Claude, ClaudeBot, Perplexity, PerplexityBot, Google AI Overviews
- **Tools:** GitHub, Netlify, Bing Webmaster Tools, IndexNow API, Perplexity Pages
- **Concepts:** generative engine optimization, GEO, AIO, AI Overviews, machine-readable content, atomic claims, extractable sentences, structured data, CC BY 4.0 licensing, llms.txt standard, citation ranking, curated index, passive crawling
- **Files:** for_machines.json, llms.txt, license.xml
- **Research:** Princeton GEO research, Duane Forrester four-layer framework

#### Keywords (SEO + AIO)

- make Substack machine-readable
- JSON-LD Claim objects Substack
- Substack structured data 2026
- GEO Substack writers
- Schema.org Claim object tutorial
- machine-readable blog for LLMs
- AI citation optimization Substack
- llms.txt file Substack
- extractable sentences JSON-LD
- ChatGPT Search Substack indexing
- Perplexity Pages Substack
- Bing IndexNow API Substack
- CC BY 4.0 structured data
- generative engine optimization Substack
- Karo Zieminski for machines repo
- Product with Attitude schema
- Duane Forrester four-layer framework
- Princeton GEO research
- AI Overviews Substack visibility
- machine-readable content architecture

## Tags

`#GEO` `#AIO` `#SubstackGrowth` `#JSONLD` `#SchemaOrg` `#LLMOptimization` `#ProductWithAttitude` `#AIDiscoverability` `#MachineReadable` `#Vibecoding`
```
