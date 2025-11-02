# Product With Attitude — JSON-LD Knowledge Graph

**LLM-Friendly Structured Metadata for Substack Publications**

---

## Overview

This repository contains a comprehensive JSON-LD knowledge graph and auto-update agent that makes your Substack publication maximally discoverable by LLMs, semantic search engines, and AI assistants.

### What's Included

1. **Enhanced JSON-LD Template** (`for-machines.jsonld`)
   - Single `@graph` structure with stable IRIs
   - Rich `BlogPosting` entities for every article
   - SKOS-mapped vocabulary with Wikidata/DBpedia links
   - Provenance-tracked semantic triples
   - Complete entity graph (Organization, Person, CreativeWorkSeries, etc.)

2. **Auto-Update Agent** (`update-jsonld.js`)
   - Fetches Substack RSS feed
   - Generates structured metadata for new posts
   - Optional LLM-assisted content analysis
   - Incremental or full regeneration modes

3. **Claude Code Integration** (`update-jsonld.md`)
   - Slash command: `/update-jsonld`
   - One-command workflow automation

4. **Creator Lab Skill Documentation** (`creator-lab-skill-jsonld-agent.md`)
   - Complete setup guide
   - Best practices and troubleshooting
   - Advanced LLM optimization techniques

---

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Run the Agent

**Incremental update** (new posts only):
```bash
npm run update
```

**Full regeneration** (all posts):
```bash
npm run update:full
```

**With LLM analysis** (requires `ANTHROPIC_API_KEY`):
```bash
npm run update:analyze
```

### 3. Use with Claude Code

Copy the slash command:
```bash
cp update-jsonld.md ~/.claude/commands/
```

Then run:
```
/update-jsonld
```

---

## Why This Matters

Standard Substack doesn't provide structured metadata that LLMs can easily discover and index. This implementation:

✅ **Maximizes LLM discoverability** with rich BlogPosting metadata
✅ **Links your vocabulary** to global knowledge graphs (Wikidata/DBpedia)
✅ **Tracks provenance** on semantic claims (source, evidence, confidence)
✅ **Enforces canonical URLs** for syndicated content
✅ **Provides comprehensive entity graph** for relationship discovery

### The Difference: Valid vs. LLM-Friendly

**Basic JSON-LD** (valid but not optimized):
```json
{
  "@type": "Article",
  "headline": "My Post",
  "url": "https://example.com/post"
}
```

**LLM-Friendly JSON-LD** (this implementation):
```json
{
  "@type": "BlogPosting",
  "@id": "https://example.com/post",
  "headline": "My Post",
  "description": "...",
  "keywords": ["evergreen", "specific"],
  "about": [{"@id": "https://productwithattitude.com/vocab#Vibecoding"}],
  "isPartOf": {"@id": "https://example.com/#series"},
  "author": {"@id": "https://example.com/#person"},
  "publisher": {"@id": "https://example.com/#org"},
  "license": "https://example.com/license",
  "wordCount": 1200,
  "timeRequired": "PT6M",
  "articleSection": "Product Strategy",
  "datePublished": "2025-10-28T13:54:38Z"
}
```

---

## Structure

```
jsonld-workspace/
├── for-machines.jsonld              # Enhanced JSON-LD template
├── update-jsonld.js                 # Auto-update agent
├── package.json                     # Dependencies
├── update-jsonld.md                 # Claude Code slash command
├── creator-lab-skill-jsonld-agent.md # Full documentation
└── README.md                        # This file
```

---

## Configuration

### Environment Variables

```bash
# Optional: Claude API for content analysis
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional: Override default RSS feed
export SUBSTACK_RSS_URL="https://yoursubstack.substack.com/feed"

# Optional: GitHub auto-commit
export GITHUB_TOKEN="ghp_..."
```

### Customization

Edit `for-machines.jsonld`:
- Update `@id` URLs to match your Substack
- Customize `Person` and `Organization` entities
- Add your custom `DefinedTerm` vocabulary
- Set SKOS mappings to Wikidata/DBpedia
- Update license URL

---

## Features

### Rich BlogPosting Metadata

Every article includes:
- **Core**: headline, description, URL, dates, author, publisher
- **Content**: wordCount, timeRequired, articleSection, keywords
- **Relationships**: about, mentions, citation, isPartOf
- **Rights**: license, copyrightHolder, usageInfo
- **Images**: primaryImageOfPage with alt-text compliance

### SKOS Vocabulary Mapping

Link your custom terms to global knowledge graphs:
```json
{
  "@type": "DefinedTerm",
  "@id": "https://productwithattitude.com/vocab#Vibecoding",
  "name": "vibecoding",
  "inDefinedTermSet": {"@id": "https://productwithattitude.com/vocab#Glossary"},
  "sameAs": ["https://www.wikidata.org/entity/Q169890"],
  "skos:related": ["https://www.wikidata.org/entity/Q169890"]
}
```

### Provenance Tracking

Make your semantic claims cite-able:
```json
{
  "pwa:semanticTriples": [
    {
      "subject": "https://productwithattitude.com/vocab#Vibecoding",
      "predicate": "enables",
      "object": "rapid prototyping",
      "pwa:source": "https://karozieminski.substack.com/p/example-post",
      "pwa:evidence": "https://karozieminski.substack.com/p/example-post#section",
      "pwa:confidence": 0.95
    }
  ]
}
```

### Canonical URL Policy

Clear signals for syndicated content:
```json
{
  "@type": "WebSite",
  "@id": "https://karobuilds.dev/#hub",
  "pwa:canonicalPolicy": "All syndicated posts use rel=\"canonical\" to Substack originals."
}
```

---

## Usage

### Incremental Updates

Run after publishing a new post:
```bash
npm run update
```

This:
1. Fetches RSS feed
2. Detects new posts since last update
3. Generates BlogPosting, WebPage, ImageObject entities
4. Updates `@graph` and archive collection
5. Saves updated JSON-LD

### Full Regeneration

Rebuild entire archive:
```bash
npm run update:full
```

Useful when:
- Changing JSON-LD structure
- Adding new entity types
- Updating existing post metadata

### LLM-Assisted Analysis

Get smarter keywords and topics:
```bash
npm run update:analyze
```

Requires `ANTHROPIC_API_KEY`. Claude will:
- Analyze each post's content
- Extract 5-8 relevant keywords (evergreen + specific)
- Categorize into article sections
- Identify main topics

Cost: ~$0.01 per post

---

## Deployment

### GitHub

1. **Create repository**:
   ```bash
   git init
   git add .
   git commit -m "Initial JSON-LD knowledge graph"
   git remote add origin https://github.com/yourusername/your-repo
   git push -u origin main
   ```

2. **Make public** for LLM discovery

3. **Link from Substack**:
   - Add to About page
   - Reference in newsletter footer
   - Share in Notes/social

### Automation

**Option A: Manual** (recommended)
- Run `/update-jsonld` after each post
- Review changes before committing

**Option B: GitHub Actions** (advanced)
- See `creator-lab-skill-jsonld-agent.md` for workflow example
- Runs daily, auto-commits updates

---

## Validation

### JSON-LD Syntax

```bash
cat for-machines.jsonld | jq .
```

### Google Rich Results Test

1. Visit https://search.google.com/test/rich-results
2. Paste JSON-LD or GitHub raw URL
3. Fix warnings/errors

### SKOS Mappings

Verify links to Wikidata/DBpedia:
- https://www.wikidata.org/entity/Q169890 (Agile)
- https://www.wikidata.org/entity/Q1314903 (Specification)

---

## Monitoring

Track LLM discoverability:
- Search for your content in Claude, ChatGPT, Perplexity
- Monitor referrals from AI search engines
- Check backlinks to JSON-LD file
- Use Google Search Console for impressions

---

## Documentation

- **Quick Start**: This README
- **Full Guide**: `creator-lab-skill-jsonld-agent.md`
- **Claude Code**: `update-jsonld.md`
- **LLM Best Practices**: `~/.claude/CLAUDE.md`

---

## Credits

**Created by**: Karo Zieminski
**Publication**: [Product With Attitude](https://karozieminski.substack.com/)
**Tool**: [StackShelf](https://stackshelf.app/)
**Community**: [creator-lab](https://github.com/karozi/creator-lab)

---

## License

MIT License — Free to use, modify, and share.

Attribution appreciated: "Based on Product With Attitude JSON-LD skill"

---

## Next Steps

1. ⭐ Star the [creator-lab repo](https://github.com/karozi/creator-lab)
2. 🔔 Subscribe to [Product With Attitude](https://karozieminski.substack.com/)
3. 🚀 Add your product to [StackShelf](https://stackshelf.app/)
4. 💬 Share your results in the PWA community
5. 🎯 Build your own skills and contribute back!

**Questions?** Tag [@karozieminski](https://x.com/karozieminski) or open an issue.
