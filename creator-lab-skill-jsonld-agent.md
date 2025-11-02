# JSON-LD Auto-Update Agent for LLM-Friendly Substack

**Attitude Vault Skill**
*Category: Automation | Workflow | LLM Optimization*

---

## Context

**Problem**: Substack doesn't provide structured, LLM-friendly metadata for posts. Search engines and AI models struggle to discover, index, and cite your content effectively.

**Goal**: Automatically generate and maintain a comprehensive JSON-LD knowledge graph that makes your Substack publication maximally discoverable by LLMs and semantic search engines.

**Constraints**:
- Must follow Schema.org and JSON-LD best practices
- Must include SKOS mappings to Wikidata/DBpedia for vocabulary terms
- Must add provenance to semantic claims
- Must enforce canonical URL policies and alt-text rules
- Must run automatically whenever new posts are published

---

## Why This Matters

LLMs and semantic search engines rely on structured metadata to:
1. **Discover** your content in their training/indexing pipelines
2. **Understand** the relationships between your concepts and existing knowledge graphs
3. **Cite** your work accurately with proper attribution
4. **Recommend** your content to users searching for related topics

A basic JSON-LD implementation isn't enough. You need:
- **Rich BlogPosting** entities with keywords, reading time, citations, topics
- **SKOS mappings** that link your custom vocabulary to Wikidata/DBpedia
- **Provenance tracking** on semantic triples (source, evidence, confidence)
- **Canonical URL signals** for syndicated content
- **Comprehensive entity graph** (Organization, Person, CreativeWorkSeries, etc.)

---

## Inputs

### Required
- **Substack RSS feed URL** (e.g., `https://yoursubstack.substack.com/feed`)
- **GitHub repository** for storing the JSON-LD file
- **License URL** for your content

### Optional
- **ANTHROPIC_API_KEY**: For LLM-assisted content analysis (keywords, topics)
- **GITHUB_TOKEN**: For auto-committing updates to your repo

### Files Included
1. `for-machines.jsonld` — Enhanced JSON-LD knowledge graph template
2. `update-jsonld.js` — Node.js automation script
3. `package.json` — Dependencies
4. `.claude/commands/update-jsonld.md` — Slash command for Claude Code

---

## Procedure

### Step 1: Set Up Your JSON-LD Template

1. **Clone the template**:
   ```bash
   cd ~/your-workspace
   mkdir jsonld-workspace
   cd jsonld-workspace
   ```

2. **Copy the enhanced `for-machines.jsonld`** (provided in this skill)

3. **Customize key fields**:
   - Update `@id` URLs to match your Substack
   - Update `Person` and `Organization` entities with your details
   - Add your custom `DefinedTerm` vocabulary with SKOS mappings
   - Set your `license` URL

**Key improvements in this template**:
- ✅ Single `@graph` structure (not mixed arrays)
- ✅ SKOS mappings on all DefinedTerms → Wikidata/DBpedia
- ✅ Provenance on semantic triples (`pwa:source`, `pwa:evidence`, `pwa:confidence`)
- ✅ `CreativeWorkSeries` for your publication
- ✅ Rich `BlogPosting` with keywords, reading time, articleSection
- ✅ `WebPage` with breadcrumbs and primary images
- ✅ `Organization` and enhanced `Person` entities
- ✅ License and copyright info on all creative works

### Step 2: Install the Auto-Update Agent

1. **Copy `update-jsonld.js` and `package.json`** to your workspace

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure environment** (optional):
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."  # For LLM analysis
   export SUBSTACK_RSS_URL="https://yoursubstack.substack.com/feed"
   ```

### Step 3: Run the Agent

**Incremental update** (new posts only):
```bash
npm run update
```

**Full regeneration** (all posts):
```bash
npm run update:full
```

**With LLM-assisted analysis** (better keywords/topics):
```bash
npm run update:analyze
```

**What the agent does**:
1. Fetches your Substack RSS feed
2. Parses new posts (or all posts in `--full` mode)
3. Generates rich `BlogPosting` JSON-LD for each:
   - Headline, description, URL, dates
   - Keywords (evergreen + specific)
   - Article section/category
   - Topics the post is "about"
   - Reading time estimate
   - Image metadata with alt-text compliance
4. Creates `WebPage` entities with breadcrumbs
5. Creates `ImageObject` entities with proper attribution
6. Updates the `@graph` in `for-machines.jsonld`
7. Updates `CollectionPage` archive with all posts

### Step 4: Add Slash Command to Claude Code

1. **Copy `update-jsonld.md`** to `~/.claude/commands/`

2. **Usage**:
   ```
   /update-jsonld
   ```

Claude will:
- Navigate to your workspace
- Run the update script
- Show you the changes
- Offer to commit to GitHub

### Step 5: Deploy to GitHub

1. **Create/update your GitHub repo**:
   ```bash
   git init
   git add for-machines.jsonld
   git commit -m "Add enhanced JSON-LD knowledge graph"
   git remote add origin https://github.com/yourusername/your-repo
   git push -u origin main
   ```

2. **Make it public** so LLMs can discover it

3. **Link from your Substack**:
   - Add a link in your About page
   - Reference in newsletter footer
   - Share in Notes/social media

### Step 6: Automate Updates

**Option A: Manual** (recommended initially)
- Run `/update-jsonld` whenever you publish a new post
- Review changes before committing

**Option B: GitHub Actions** (advanced)
- Set up a workflow that runs daily
- Auto-commits changes to your repo
- Example workflow (create `.github/workflows/update-jsonld.yml`):

```yaml
name: Update JSON-LD
on:
  schedule:
    - cron: '0 12 * * *'  # Daily at noon UTC
  workflow_dispatch:  # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm run update
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - uses: stefanzweifel/git-auto-commit-action@v4
        with:
          commit_message: "Auto-update JSON-LD with new posts"
```

---

## Output

### Expected Result

1. **Enhanced `for-machines.jsonld`** with:
   - Complete `@graph` of all entities
   - Rich `BlogPosting` for each article
   - SKOS-mapped vocabulary terms
   - Provenance-tracked semantic triples
   - Proper canonical URLs and licensing

2. **Verification checklist**:
   - [ ] All posts have `headline`, `description`, `url`, `datePublished`
   - [ ] Keywords include both evergreen and specific terms
   - [ ] Images have alt-text with "Karo" and "Product With Attitude" (or your brand)
   - [ ] SKOS mappings link to Wikidata/DBpedia
   - [ ] Provenance includes `pwa:source`, `pwa:confidence`
   - [ ] `CreativeWorkSeries` links all posts
   - [ ] `Organization` and `Person` have `sameAs` links
   - [ ] License URL is set on all creative works

3. **LLM Discoverability Score**: ⭐⭐⭐⭐⭐
   - Schema.org compliant: ✅
   - Linked data (SKOS): ✅
   - Provenance: ✅
   - Rich metadata: ✅
   - Canonical URLs: ✅

---

## Verification

### Test Your JSON-LD

1. **Validate syntax**:
   ```bash
   cat for-machines.jsonld | jq .
   ```

2. **Check with Google's Rich Results Test**:
   - Go to https://search.google.com/test/rich-results
   - Paste your JSON-LD or provide GitHub raw URL
   - Fix any warnings/errors

3. **Verify SKOS mappings**:
   - Visit your Wikidata links (e.g., `https://www.wikidata.org/entity/Q169890`)
   - Confirm they match your concepts

4. **Check provenance**:
   - Look for `pwa:source`, `pwa:evidence`, `pwa:confidence` on triples
   - Ensure source URLs are canonical Substack posts

### Monitor Impact

Track how LLMs discover and cite your work:
- Search for your content in Claude, ChatGPT, Perplexity
- Monitor referrals from AI search engines
- Check backlinks to your JSON-LD file
- Use tools like Google Search Console for impressions

---

## Advanced: LLM-Assisted Analysis

**Why use it**: The agent can automatically extract keywords and topics from your posts using Claude's advanced language understanding.

**Setup**:
1. Get an Anthropic API key: https://console.anthropic.com/
2. Set environment variable:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

3. Run with analysis:
   ```bash
   npm run update:analyze
   ```

**What it does**:
- Analyzes each post's title and description
- Extracts 5-8 relevant keywords (evergreen + specific)
- Categorizes into article sections
- Identifies main topics the post is "about"
- Returns structured JSON for BlogPosting metadata

**Cost**: ~$0.01 per post (Claude Haiku pricing)

---

## Troubleshooting

### RSS feed not loading
- Verify your Substack RSS URL in browser
- Check for network/firewall issues
- Try with curl: `curl https://yoursubstack.substack.com/feed`

### LLM analysis failing
- Verify `ANTHROPIC_API_KEY` is set correctly
- Check API rate limits
- Fall back to basic keyword extraction (default)

### JSON-LD validation errors
- Use `jq` to find syntax errors: `cat for-machines.jsonld | jq .`
- Check for missing required fields: `@id`, `@type`, `name`
- Verify all IRIs are valid URLs

### Posts not appearing
- Check `maxPosts` config (default: 50)
- Use `--full` mode to regenerate all posts
- Verify RSS feed contains the post

---

## Files

All files for this skill are available at:
- GitHub: `https://github.com/karozi/Product-with-Attitude-by-Karo-Zieminski-For-Machines`
- Creator Lab: `https://github.com/karozi/creator-lab`

**Package contents**:
1. `for-machines.jsonld` — Enhanced JSON-LD template (2.0)
2. `update-jsonld.js` — Auto-update agent
3. `package.json` — Dependencies
4. `update-jsonld.md` — Claude Code slash command
5. `creator-lab-skill-jsonld-agent.md` — This documentation

---

## Credits

**Created by**: Karo Zieminski
**Publication**: Product With Attitude
**Website**: https://karozieminski.substack.com/
**Tool**: https://stackshelf.app/

**Skill Type**: Automation
**Tool Stack**: Node.js, Claude API, Schema.org, SKOS
**Complexity**: Intermediate
**Time to Setup**: 30 minutes
**Maintenance**: Automated (5 min/week for review)

---

## Related Skills

- **Vibecoding Tips**: Build fast, iterate, ship
- **PRD Builder**: Spec-driven product development
- **AIO + SEO Optimization**: LLM discoverability best practices
- **Attitude Vault**: Community skill sharing

---

## License

MIT License — Free to use, modify, and share.
Attribution appreciated: "Based on Product With Attitude JSON-LD skill"

---

## Next Steps

1. ⭐ Star the creator-lab repo: https://github.com/karozi/creator-lab
2. 🔔 Subscribe to Product With Attitude: https://karozieminski.substack.com/
3. 🚀 Add your product to StackShelf: https://stackshelf.app/
4. 💬 Share your results in the PWA community chat
5. 🎯 Build your own skills and contribute back!

**Questions?** Drop them in the Product With Attitude community or tag @karozieminski on X/LinkedIn.
