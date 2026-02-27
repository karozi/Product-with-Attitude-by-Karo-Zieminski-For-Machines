#!/usr/bin/env python3
"""
Substack → Schema Updater + Gist Publisher + Dev.to Poster for Product with Attitude
=====================================================================================
Full pipeline:
  1. Fetch RSS feed from karozieminski.substack.com
  2. Detect new articles not yet in for_machines.json
  3. Update for_machines.json (new entries, renumber, numberOfItems)
  4. Update canonical-links-from-publication-product-with-attitude.md
  5. Update llms.txt (dates, counts)
  6. For each new FREE article: create & publish a GitHub Gist (teaser + For Machines)
  7. For each new FREE article: cross-post to dev.to (teaser + canonical URL → Substack)
  8. Push all schema changes to GitHub

Usage:
    python3 update_schema.py --token GITHUB_TOKEN [--devto-key DEVTO_API_KEY] \
                             [--dry-run] [--no-push] [--no-gist] [--no-devto]

Environment variable alternative:
    export GITHUB_TOKEN=ghp_...
    export DEVTO_API_KEY=...
    python3 update_schema.py
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape

# ─── Configuration ──────────────────────────────────────────────────────────

FEED_URL = "https://karozieminski.substack.com/feed"
AUTHOR_ID = "https://karozieminski.substack.com/#author"
AUTHOR_NAME = "Karo Zieminski"

REPO_URL_TEMPLATE = "https://{token}@github.com/{owner}/{repo}.git"
REPO_OWNER = "karozi"
REPO_NAME = "Product-with-Attitude-by-Karo-Zieminski-For-Machines"

SCHEMA_FILE = "for_machines.json"
LINKS_FILE = "canonical-links-from-publication-product-with-attitude.md"
LLMS_FILE = "llms.txt"

SERIES_PATTERNS = {
    r"Build with Attitude\s*#?\d+": "#series-build-with-attitude",
    r"AI Tools A-Z": "#series-ai-tools-az",
}

STANDARD_TAGS = [
    "#ProductThinking", "#AIForProductManagers", "#ProductStrategy",
    "#Vibecoding", "#AIAssistedCoding",
]

# ─── RSS Parsing ────────────────────────────────────────────────────────────

def fetch_rss(url=FEED_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "PWA-Schema-Updater/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    ns = {"dc": "http://purl.org/dc/elements/1.1/", "content": "http://purl.org/rss/1.0/modules/content/"}

    articles = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link")
        description = _text(item, "description")
        pub_date_str = _text(item, "pubDate")
        creator = _text(item, "dc:creator", ns)
        content_html = _text(item, "content:encoded", ns)
        date_published = _parse_rfc2822(pub_date_str) if pub_date_str else None
        plain_text = _strip_html(content_html) if content_html else ""
        word_count = len(plain_text.split())
        is_free = not _is_paywall(content_html) if content_html else True

        articles.append({
            "title": title, "link": link, "description": description,
            "datePublished": date_published, "wordCount": word_count,
            "isAccessibleForFree": is_free, "creator": creator,
            "contentHtml": content_html, "plainText": plain_text,
        })
    return articles


def _text(el, tag, ns=None):
    child = el.find(tag, ns) if ns else el.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _parse_rfc2822(s):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        return None


def _strip_html(html):
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _is_paywall(html):
    if not html:
        return False
    indicators = [
        "class=\"paywall\"", "This post is for paid subscribers",
        "This post is for paying subscribers",
    ]
    html_lower = html.lower()
    return any(ind.lower() in html_lower for ind in indicators)


# ─── Content Analysis (schema entries) ──────────────────────────────────────

def extract_keywords(title, description, plain_text):
    combined = f"{title} {title} {description} {description} {plain_text[:3000]}".lower()
    domain_terms = {
        "vibecoding": ["vibecod", "vibe cod", "vibe-cod"],
        "AI building": ["ai build", "building with ai", "build with ai"],
        "product thinking": ["product think", "product-think"],
        "critical AI literacy": ["critical ai literacy", "ai literacy"],
        "Substack": ["substack"],
        "community building": ["community build"],
        "agentic coding": ["agentic cod"],
        "spec-driven development": ["spec-driven", "speccod"],
        "prompt engineering": ["prompt engineer"],
        "ethical AI": ["ethical ai", "ai ethic"],
        "Claude": ["claude"], "Perplexity": ["perplexity"],
        "Replit": ["replit"], "Anthropic": ["anthropic"],
        "tool review": ["review", "hands-on", "deep dive"],
        "AI agents": ["ai agent", "agentic"],
        "LLM": ["llm", "large language model"],
        "workflow automation": ["workflow", "automat"],
        "context engineering": ["context engineer"],
        "open source": ["open source", "open-source"],
        "builder economy": ["builder economy"],
        "AI product management": ["product manag"],
        "Suno": ["suno"], "Recraft": ["recraft"],
        "visual design": ["visual design", "visual identity"],
        "platform analysis": ["platform analysis", "platform design"],
    }
    found = []
    for keyword, patterns in domain_terms.items():
        if any(p in combined for p in patterns):
            found.append(keyword)
    skip = {"The","How","What","Why","Who","When","Where","And","But","For","With",
            "From","Build","That","This","Here","Every","One","All","You","Your",
            "Night","Review","Examples","Compares","Built","Refuse","Let","Decide",
            "Need","Users","Speed","Guide","Source","Code","Inside","Tools","Run",
            "Choose","Between","Pays","Month","Music","Deletes","Track","Shipped",
            "Days","Using","Own","Changes","Everything","Complete","Resource","Hub",
            "Design","Start"}
    for tw in re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', title):
        if tw not in skip and tw not in found and len(tw) > 2:
            found.append(tw)
    seen = set()
    unique = []
    for k in found:
        if k.lower() not in seen:
            seen.add(k.lower())
            unique.append(k)
    return unique[:5] if unique else ["AI", "technology"]


def extract_key_concepts(title, description, plain_text):
    concepts = []
    if description:
        for p in re.split(r'[.;:–—]', description):
            p = p.strip()
            if 10 < len(p) < 80:
                concepts.append(p)
    for tp in re.split(r'[:.–—|]', title):
        tp = tp.strip()
        if tp and len(tp) > 5 and tp not in concepts:
            concepts.append(tp)
    seen = set()
    unique = []
    for c in concepts:
        cl = unescape(c).lower().strip()
        if cl not in seen and len(cl) > 5:
            seen.add(cl)
            unique.append(unescape(c).strip())
    return unique[:4] if unique else [title]


def extract_key_quotes(title, description, plain_text):
    quotes = [title]
    if description and description != title:
        quotes.append(unescape(description))
    return quotes[:3]


def detect_alternative_headline(title, description):
    if description and description != title and len(description) < 200:
        return description
    return None


def detect_series(title):
    for pattern, series_id in SERIES_PATTERNS.items():
        if re.search(pattern, title, re.IGNORECASE):
            return series_id
    return None


# ─── Schema Update Logic ────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def save_text(content, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def find_recent_articles_node(schema):
    for node in schema["@graph"]:
        if node.get("@id") == "#recent-articles":
            return node
    raise ValueError("#recent-articles node not found")


def get_existing_urls(articles_node):
    return {
        item.get("item", {}).get("url", "")
        for item in articles_node.get("itemListElement", [])
        if item.get("item", {}).get("url")
    }


def build_article_entry(rss_article, position):
    title = rss_article["title"]
    description = rss_article["description"]
    plain_text = rss_article["plainText"]
    article_obj = {
        "@type": "Article", "headline": title,
        "url": rss_article["link"],
        "datePublished": rss_article["datePublished"],
        "wordCount": rss_article["wordCount"],
        "isAccessibleForFree": rss_article["isAccessibleForFree"],
        "author": {"@id": AUTHOR_ID},
    }
    alt = detect_alternative_headline(title, description)
    if alt:
        article_obj["alternativeHeadline"] = unescape(alt)
    sid = detect_series(title)
    if sid:
        article_obj["isPartOf"] = {"@id": sid}
    article_obj["keywords"] = extract_keywords(title, description, plain_text)
    article_obj["pwa:keyConcepts"] = extract_key_concepts(title, description, plain_text)
    article_obj["pwa:keyQuotes"] = extract_key_quotes(title, description, plain_text)
    return {"@type": "ListItem", "position": position, "item": article_obj}


def update_schema(schema, new_articles_data):
    articles_node = find_recent_articles_node(schema)
    existing_urls = get_existing_urls(articles_node)
    new_articles = [a for a in new_articles_data if a["link"] not in existing_urls]
    if not new_articles:
        return schema, []
    new_articles.sort(key=lambda a: a["datePublished"] or "0000-00-00", reverse=True)
    new_entries = [build_article_entry(a, i + 1) for i, a in enumerate(new_articles)]
    combined = new_entries + articles_node.get("itemListElement", [])
    for i, item in enumerate(combined):
        item["position"] = i + 1
    articles_node["itemListElement"] = combined
    articles_node["numberOfItems"] = len(combined)
    return schema, new_articles


def update_series_if_needed(schema, new_articles):
    for article in new_articles:
        sid = detect_series(article["title"])
        if not sid:
            continue
        for node in schema["@graph"]:
            if node.get("@id") == sid:
                has_part = node.get("hasPart", [])
                if article["link"] not in {p.get("url", "") for p in has_part}:
                    has_part.append({
                        "@type": "Article", "name": article["title"],
                        "url": article["link"],
                        "position": len(has_part) + 1,
                        "datePublished": article["datePublished"],
                    })
                    node["hasPart"] = has_part
                break
    return schema


# ─── Canonical Links Update ─────────────────────────────────────────────────

def build_canonical_entry(article):
    title = article["title"]
    link = article["link"]
    try:
        formatted_date = datetime.strptime(article["datePublished"], "%Y-%m-%d").strftime("%B %d, %Y")
    except (ValueError, TypeError):
        formatted_date = article["datePublished"] or "Unknown"
    creator = article.get("creator", "")
    author = creator if creator and "," in creator else AUTHOR_NAME
    return f"""
## Article: {title}

**Author:** {author}

**Canonical Link:** {link}

**Original Publish Date:** {formatted_date}

---"""


def update_canonical_links(content, new_articles):
    if not new_articles:
        return content
    lines = content.split("\n")
    insert_idx = 0
    found_header = False
    for i, line in enumerate(lines):
        if line.startswith("# "):
            found_header = True
        if found_header and line.strip() == "---":
            insert_idx = i + 1
            break
    entries = [
        build_canonical_entry(a)
        for a in sorted(new_articles, key=lambda a: a["datePublished"] or "0000-00-00", reverse=True)
    ]
    today = datetime.now().strftime("%B %Y")
    updated = [f"Last updated: {today}" if l.startswith("Last updated:") else l for l in lines]
    before = "\n".join(updated[:insert_idx])
    after = "\n".join(updated[insert_idx:])
    return f"{before}\n{''.join(entries)}\n{after}"


# ─── llms.txt Update ────────────────────────────────────────────────────────

def update_llms_txt(content, article_count, today_str):
    content = re.sub(
        r"(\*\*Last Updated\*\*:\s*)\S+",
        rf"\g<1>{today_str}",
        content,
    )
    return content


# ─── Gist Repurposer ────────────────────────────────────────────────────────

def _parse_html_blocks(html):
    """Parse Substack HTML into a list of structured blocks for markdown conversion.
    Each block is a dict with type (paragraph, heading, list, blockquote, etc.) and content."""
    blocks = []

    # Remove noise: images, twitter embeds, subscription widgets, share widgets, referral blocks
    html = re.sub(r'<div[^>]*class="[^"]*subscription-widget[^"]*"[^>]*>.*?</form>\s*</div>\s*</div>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div[^>]*class="[^"]*captioned-image-container[^"]*"[^>]*>.*?</figure>\s*</div>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div[^>]*class="[^"]*twitter-embed[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
    html = re.sub(r'<picture>.*?</picture>', '', html, flags=re.DOTALL)
    html = re.sub(r'<img[^>]*/?>', '', html)
    html = re.sub(r'<figure[^>]*>.*?</figure>', '', html, flags=re.DOTALL)
    # Remove empty divs
    html = re.sub(r'<div[^>]*>\s*</div>', '', html, flags=re.DOTALL)
    # Remove Substack boilerplate: "Hey, I'm Karo" intro block and share/referral CTAs
    html = re.sub(r'<p>\s*<em>\s*Hey,?\s*I[^<]{0,20}Karo.*?</p>', '', html, flags=re.DOTALL)
    # Also catch HTML entity apostrophe versions
    html = re.sub(r'<p>[^<]*Hey[^<]*&#8217;[^<]*Karo.*?</p>', '', html, flags=re.DOTALL)
    # Remove "Today, we're going to look at:" table-of-contents blocks
    html = re.sub(r'<p>[^<]*Today,\s*we[^<]{0,20}going to look at:.*?</p>', '', html, flags=re.DOTALL)
    html = re.sub(r'<p>[^<]*Today,\s*we[^<]*&#8217;[^<]*going to look at.*?</p>', '', html, flags=re.DOTALL)
    # Remove share/referral blocks
    html = re.sub(r'<p>[^<]*Share this post with \d+ friends.*?</p>', '', html, flags=re.DOTALL)
    html = re.sub(r'<p>\s*\[Share\].*?</p>', '', html, flags=re.DOTALL)
    # Remove WHY SUBSCRIBE CTA headings
    html = re.sub(r'<h[2-6][^>]*>[^<]*WHY SUBSCRIBE.*?</h[2-6]>', '', html, flags=re.DOTALL)

    # Extract headings
    def process_heading(match):
        level = int(match.group(1))
        text = _inline_to_md(match.group(2))
        blocks.append({"type": "heading", "level": level, "text": text})
        return ""

    # Extract blockquotes
    def process_blockquote(match):
        text = _inline_to_md(match.group(1))
        blocks.append({"type": "blockquote", "text": text})
        return ""

    # Extract list items (gather consecutive ones)
    def process_list(match):
        items_html = match.group(0)
        items = re.findall(r'<li[^>]*>(.*?)</li>', items_html, re.DOTALL)
        items_md = [_inline_to_md(item).strip() for item in items if _inline_to_md(item).strip()]
        if items_md:
            blocks.append({"type": "list", "items": items_md})
        return ""

    # Extract paragraphs
    def process_paragraph(match):
        text = _inline_to_md(match.group(1))
        text = text.strip()
        if text and len(text) > 2:
            blocks.append({"type": "paragraph", "text": text})
        return ""

    # Process in order: headings, blockquotes, lists, then paragraphs
    # We need to process sequentially to maintain order
    # Strategy: walk through the HTML and emit blocks in document order

    # Split HTML into major elements
    # Regex to find block-level elements in order
    pattern = re.compile(
        r'<h([2-6])[^>]*>(.*?)</h\1>'        # headings
        r'|<blockquote[^>]*>(.*?)</blockquote>'  # blockquotes
        r'|(<[ou]l[^>]*>.*?</[ou]l>)'           # lists
        r'|<p[^>]*>(.*?)</p>',                   # paragraphs
        re.DOTALL
    )

    for m in pattern.finditer(html):
        if m.group(1):  # heading
            level = int(m.group(1))
            text = _inline_to_md(m.group(2)).strip()
            if text:
                blocks.append({"type": "heading", "level": level, "text": text})
        elif m.group(3) is not None:  # blockquote
            text = _inline_to_md(m.group(3)).strip()
            if text:
                blocks.append({"type": "blockquote", "text": text})
        elif m.group(4):  # list
            items = re.findall(r'<li[^>]*>(.*?)</li>', m.group(4), re.DOTALL)
            items_md = [_inline_to_md(i).strip() for i in items if _inline_to_md(i).strip()]
            if items_md:
                blocks.append({"type": "list", "items": items_md})
        elif m.group(5) is not None:  # paragraph
            text = _inline_to_md(m.group(5)).strip()
            if text and len(text) > 2:
                blocks.append({"type": "paragraph", "text": text})

    return blocks


def _inline_to_md(html_fragment):
    """Convert inline HTML (bold, italic, links) to Markdown.
    Carefully handles edge cases that break GitHub markdown rendering:
    - No bold/italic markers spanning line breaks
    - No trailing/leading spaces inside markers
    - Headings don't need bold wrapping (they're already bold)
    """
    text = html_fragment
    # Links
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)
    # Bold — but only for single-line spans; multi-line bold breaks GitHub rendering
    def _bold_replace(m):
        inner = m.group(1)
        # If the bold content contains newlines, just return content without markers
        if '\n' in inner or '<br' in inner:
            return inner
        inner = inner.strip()
        if not inner:
            return ''
        return f'**{inner}**'
    text = re.sub(r'<(?:strong|b)>(.*?)</(?:strong|b)>', _bold_replace, text, flags=re.DOTALL)
    # Italic — same single-line guard
    def _italic_replace(m):
        inner = m.group(1)
        if '\n' in inner or '<br' in inner:
            return inner
        inner = inner.strip()
        if not inner:
            return ''
        return f'*{inner}*'
    text = re.sub(r'<(?:em|i)>(.*?)</(?:em|i)>', _italic_replace, text, flags=re.DOTALL)
    # Line breaks
    text = re.sub(r'<br\s*/?>', '\n', text)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode entities
    text = unescape(text)
    # Clean up whitespace within lines
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _clean_heading_text(text):
    """Strip bold/italic markers from heading text — headings are already bold."""
    # Remove wrapping **...** from the entire heading
    text = re.sub(r'^\*\*(.+?)\*\*$', r'\1', text.strip())
    # Remove wrapping *...* from the entire heading
    text = re.sub(r'^\*(.+?)\*$', r'\1', text.strip())
    return text.strip()


def _clean_paragraph_text(text):
    """Fix common markdown rendering issues in paragraph text."""
    # Fix bold markers with trailing/leading spaces: ** text ** → **text**
    text = re.sub(r'\*\*\s+', '**', text)
    text = re.sub(r'\s+\*\*', '**', text)
    # Fix italic markers with trailing/leading spaces
    text = re.sub(r'(?<!\*)\*\s+', '*', text)
    text = re.sub(r'\s+\*(?!\*)', '*', text)
    # Ensure space before opening italic/bold that follows a word char
    text = re.sub(r'(\w)(\*{1,2}\w)', r'\1 \2', text)
    # Ensure space after closing italic/bold that precedes a word char
    text = re.sub(r'(\w\*{1,2})(\w)', r'\1 \2', text)
    # Fix missing space after sentence-ending punctuation
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
    # Remove bold markers that wrap the ENTIRE paragraph (just noise)
    stripped = text.strip()
    if stripped.startswith('**') and stripped.endswith('**') and stripped.count('**') == 2:
        stripped = stripped[2:-2].strip()
        if stripped:
            text = stripped
    # Fix empty bold markers
    text = re.sub(r'\*\*\s*\*\*', '', text)
    text = re.sub(r'\*\s*\*', '', text)
    return text.strip()


def _blocks_to_markdown(blocks):
    """Render a list of blocks into clean Markdown."""
    lines = []
    for block in blocks:
        btype = block["type"]
        if btype == "heading":
            prefix = "#" * block["level"]
            clean = _clean_heading_text(block['text'])
            lines.append(f"\n{prefix} {clean}\n")
        elif btype == "paragraph":
            clean = _clean_paragraph_text(block['text'])
            if clean:
                lines.append(f"\n{clean}\n")
        elif btype == "blockquote":
            quote_lines = block["text"].split("\n")
            quoted = "\n".join(f"> {l.strip()}" for l in quote_lines if l.strip())
            lines.append(f"\n{quoted}\n")
        elif btype == "list":
            items_md = "\n".join(f"- {item}" for item in block["items"])
            lines.append(f"\n{items_md}\n")
    # Clean up excessive blank lines
    result = "\n".join(lines).strip()
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def _count_words_in_blocks(blocks):
    """Count total words across blocks."""
    total = 0
    for b in blocks:
        if b["type"] == "list":
            for item in b["items"]:
                total += len(item.split())
        else:
            total += len(b.get("text", "").split())
    return total


def _find_break_block_index(blocks, total_words):
    """Find the block index where we should cut for the teaser (30-40% of content).
    Returns the index of the last block to INCLUDE."""
    if total_words < 400:
        return len(blocks) - 1  # Include everything

    target_start = int(total_words * 0.30)
    target_end = int(total_words * 0.40)

    running_words = 0
    best_idx = 0
    best_score = -1

    for i, block in enumerate(blocks):
        if block["type"] == "list":
            block_words = sum(len(item.split()) for item in block["items"])
        else:
            block_words = len(block.get("text", "").split())

        running_words += block_words

        # Only consider break points in our target range
        if running_words < target_start:
            continue
        if running_words > target_end + 50:  # Small buffer
            break

        # Score this break point
        score = 0
        text = block.get("text", "").lower()

        # Prefer breaking BEFORE a heading (so end on the block before it)
        if i + 1 < len(blocks) and blocks[i + 1]["type"] == "heading":
            score += 5

        # Tension triggers in the current block
        tension = ["but", "however", "except", "the catch", "what most people miss",
                    "here's the", "the question", "turns out", "the problem"]
        if any(t in text for t in tension):
            score += 3

        # Questions create curiosity
        if "?" in text:
            score += 4

        # Paragraphs are cleaner break points than mid-list
        if block["type"] == "paragraph":
            score += 2

        if score > best_score:
            best_score = score
            best_idx = i

    # Fallback: if nothing scored well, just cut at the first paragraph
    # end after 30% words
    if best_score <= 0:
        running = 0
        for i, block in enumerate(blocks):
            if block["type"] == "list":
                running += sum(len(item.split()) for item in block["items"])
            else:
                running += len(block.get("text", "").split())
            if running >= target_start and block["type"] == "paragraph":
                best_idx = i
                break

    return best_idx


def _extract_gist_triples(blocks_text, title):
    """Extract semantic triples from the included portion."""
    triples = [
        ("Karo Zieminski", "authored", f'"{title}"'),
        ("Product with Attitude", "published", f'"{title}"'),
    ]

    sentences = re.split(r'[.!?]+', blocks_text)
    for sent in sentences[:20]:
        sent = sent.strip()
        if len(sent) < 20:
            continue
        m = re.match(r'^([A-Z][^,]{3,30})\s+(?:is|are|was|were)\s+(.{10,60})', sent)
        if m:
            triples.append((m.group(1).strip(), "is", m.group(2).strip()))
            continue
        m = re.match(r'^([A-Z][^,]{3,30})\s+(enables?|requires?|creates?|builds?|transforms?|connects?|uses?|runs?|offers?)\s+(.{10,60})', sent)
        if m:
            triples.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))

    seen = set()
    unique = []
    for t in triples:
        key = (t[0].lower(), t[1].lower())
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique[:8]


def _extract_gist_entities(text, title):
    entities = {"Karo Zieminski", "Product with Attitude"}
    skip = {"The","This","That","These","Those","Here","There","What","When","Where",
            "Why","How","But","And","For","With","From","About","Into","Your","You",
            "Our","Their","His","Her","Not","Now","Just","Also","Even","Still",
            "Only","Most","Some","Every","Many","Each","All","Both","Other",
            "Want","Read","Short","Regular","Before","After"}
    for c in re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text):
        if c not in skip and len(c) > 2:
            entities.add(c)
    tools = re.findall(r'\b(Claude|Perplexity|Replit|Cursor|Anthropic|OpenAI|ChatGPT|Gemini|Suno|Recraft|Substack|GitHub|Notion|OpenClaw|Cowork)\b', text)
    entities.update(tools)
    return sorted(entities)[:15]


def _extract_gist_keywords(text, title, description):
    keywords = {"Product with Attitude", "Karo Zieminski"}
    combined = f"{title} {description} {text[:2000]}".lower()
    kw_map = {
        "vibecoding": ["vibecod"], "AI building": ["ai build", "build with ai"],
        "product thinking": ["product think"], "critical AI literacy": ["ai literacy"],
        "agentic workflows": ["agentic workflow"], "context engineering": ["context engineer"],
        "AI product management": ["product manag"], "AI tools": ["ai tool"],
        "LLM optimization": ["llm", "llmo"], "builder economy": ["builder economy"],
        "multi-model orchestration": ["multi-model", "orchestrat"],
        "AI agents": ["ai agent", "agentic"], "Substack": ["substack"],
    }
    for kw, patterns in kw_map.items():
        if any(p in combined for p in patterns):
            keywords.add(kw)
    return sorted(keywords)[:12]


def _generate_post_specific_tags(title, description):
    combined = f"{title} {description}".lower()
    tag_map = {
        "#CriticalAILiteracy": ["critical ai literacy", "ai literacy"],
        "#BuilderEconomy": ["builder economy", "indie build"],
        "#ContextEngineering": ["context engineer"],
        "#AgenticWorkflows": ["agentic workflow", "agentic cod"],
        "#AIToolReview": ["review", "deep dive", "hands-on"],
        "#SpecDrivenDev": ["spec-driven", "speccod"],
        "#SubstackGrowth": ["substack growth", "bestseller"],
        "#PlatformDesign": ["platform design", "platform analysis"],
        "#OpenSource": ["open source", "open-source"],
        "#EthicalAI": ["ethical ai", "responsible"],
        "#BuildInPublic": ["build in public", "building in public"],
        "#MultiModelAI": ["multi-model", "orchestrat"],
    }
    tags = [tag for tag, patterns in tag_map.items() if any(p in combined for p in patterns)]
    return tags[:3]


def create_gist_content(article):
    """Create a GitHub gist: teaser at 30-40% with curiosity break + For Machines section."""
    title = article["title"]
    link = article["link"]
    description = article["description"]
    content_html = article["contentHtml"]
    word_count = article["wordCount"]

    # Parse HTML into structured blocks
    blocks = _parse_html_blocks(content_html)
    total_words = _count_words_in_blocks(blocks)

    # Find the break point
    if total_words < 400:
        # Short post: include all, link at end
        teaser_blocks = blocks
        needs_break = False
    else:
        cut_idx = _find_break_block_index(blocks, total_words)
        teaser_blocks = blocks[:cut_idx + 1]
        needs_break = True

    # Render teaser as Markdown
    teaser_md = _blocks_to_markdown(teaser_blocks)

    # Get plain text of teaser for metadata extraction
    teaser_plain = " ".join(
        " ".join(b.get("items", [])) if b["type"] == "list" else b.get("text", "")
        for b in teaser_blocks
    )

    # Fresh intro for GitHub audience
    desc_clean = unescape(description).strip() if description else ""
    if desc_clean:
        intro = f"{desc_clean} A read for builders, PMs, and anyone who refuses to ship without thinking."
    else:
        intro = f"A deep dive from Product with Attitude — for builders, PMs, and anyone shipping AI-powered products."

    # Metadata
    triples = _extract_gist_triples(teaser_plain, title)
    entities = _extract_gist_entities(teaser_plain, title)
    keywords = _extract_gist_keywords(teaser_plain, title, description)
    specific_tags = _generate_post_specific_tags(title, description)
    all_tags = STANDARD_TAGS + specific_tags

    # Assemble gist
    gist_parts = [f"# {title}", "", intro, ""]
    gist_parts.append(teaser_md)

    if needs_break:
        gist_parts.extend([
            "", "---", "",
            f"**Want to read the rest?** The full post is here → [Read on Substack]({link})",
        ])
    else:
        gist_parts.extend([
            "", "---", "",
            f"**Read more from Product with Attitude** → [Visit on Substack]({link})",
        ])

    gist_parts.extend([
        "", "---", "",
        "### For Machines", "",
        "#### Semantic Triples (Subject-Predicate-Object)", "",
    ])
    for s, p, o in triples:
        gist_parts.append(f"- ({s}, {p}, {o})")

    gist_parts.extend(["", "#### Entities", ""])
    gist_parts.append("- " + ", ".join(entities))

    gist_parts.extend(["", "#### Keywords (SEO + AIO)", ""])
    gist_parts.append("- " + ", ".join(keywords))

    gist_parts.extend(["", "## Tags", ""])
    gist_parts.append(" ".join(f"`{t}`" for t in all_tags))

    return "\n".join(gist_parts)


def _slugify(title):
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s_]+', '-', slug)
    return re.sub(r'-+', '-', slug).strip('-')[:80]


def publish_gist(token, article, gist_content):
    """Publish a public GitHub gist and return the URL."""
    filename = f"{_slugify(article['title'])}.md"
    payload = json.dumps({
        "description": f"{article['title']} — Product with Attitude by Karo Zieminski",
        "public": True,
        "files": {filename: {"content": gist_content}},
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.github.com/gists",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "PWA-Schema-Updater/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("html_url", "")
    except Exception as e:
        print(f"      ERROR creating gist: {e}")
        return None


def update_gist(token, gist_id, article, gist_content):
    """Update an existing gist."""
    filename = f"{_slugify(article['title'])}.md"
    payload = json.dumps({
        "description": f"{article['title']} — Product with Attitude by Karo Zieminski",
        "files": {filename: {"content": gist_content}},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.github.com/gists/{gist_id}",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "PWA-Schema-Updater/1.0",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("html_url", "")
    except Exception as e:
        print(f"      ERROR updating gist: {e}")
        return None


# ─── Dev.to Cross-Posting ────────────────────────────────────────────────────

DEVTO_API_URL = "https://dev.to/api/articles"
DEVTO_USER_AGENT = "PWA-Schema-Updater/1.0"


def _devto_tags_from_article(title, description):
    """Generate up to 4 dev.to-friendly tags (lowercase, no spaces, no special chars).
    Prioritizes tool/product-specific tags, then topic tags, then generic ones."""
    combined = f"{title} {description}".lower()

    # Priority 1: Specific tools/products (most valuable for discoverability)
    specific_tags = {
        "claude": ["claude", "anthropic", "cowork"],
        "perplexity": ["perplexity"],
        "replit": ["replit"],
        "chatgpt": ["chatgpt", "openai"],
        "substack": ["substack"],
    }
    # Priority 2: Domain-specific topics
    topic_tags = {
        "vibecoding": ["vibecod", "vibe cod", "vibe-cod", "speccod"],
        "product": ["product think", "product manag", "product strateg", "product decision"],
        "ux": ["ux", "user experience", "design system", "visual system"],
        "opensource": ["open source", "open-source"],
        "machinelearning": ["machine learn", "deep learn", "neural"],
    }
    # Priority 3: Broad categories (fill remaining slots)
    broad_tags = {
        "programming": ["coding", "code", "programming", "developer", "source code", "builder"],
        "productivity": ["workflow", "automat", "productiv", "tools i use"],
        "beginners": ["beginner", "getting started", "101", "guide", "resource hub"],
        "tutorial": ["tutorial", "how to", "step by step", "playbook"],
        "webdev": ["web dev", "html", "css", "javascript", "website"],
    }

    found = []
    for tag_group in [specific_tags, topic_tags, broad_tags]:
        for tag, patterns in tag_group.items():
            if tag not in found and any(p in combined for p in patterns):
                found.append(tag)

    # Always include "ai" if not already present and we have room
    if "ai" not in found:
        found.insert(0, "ai")

    return found[:4]


def _normalize_title(title):
    """Normalize a title for comparison: lowercase, strip, normalize quotes/dashes."""
    t = title.strip().lower()
    # Normalize curly quotes and apostrophes to straight ones
    t = t.replace("\u2018", "'").replace("\u2019", "'")  # ' '
    t = t.replace("\u201c", '"').replace("\u201d", '"')  # " "
    # Normalize dashes
    t = t.replace("\u2014", "-").replace("\u2013", "-")  # — –
    return t


def _get_existing_devto_urls(devto_key):
    """Fetch all published article canonical_urls from dev.to to avoid duplicates."""
    existing = set()
    page = 1
    while True:
        req = urllib.request.Request(
            f"{DEVTO_API_URL}/me?page={page}&per_page=100",
            headers={
                "api-key": devto_key,
                "User-Agent": DEVTO_USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                articles = json.loads(resp.read())
                if not articles:
                    break
                for a in articles:
                    existing.add(a.get("canonical_url", ""))
                    existing.add(a.get("url", ""))
                    # Normalized title for fuzzy dedup
                    existing.add(_normalize_title(a.get("title", "")))
                page += 1
        except Exception:
            break
    return existing


def create_devto_article_body(article, gist_content=None):
    """Create a short teaser for dev.to: description + opening hook + CTA.
    Much shorter than the gist — just enough to spark interest and drive
    clicks to Substack."""
    title = article["title"]
    link = article["link"]
    description = unescape(article.get("description", "")).strip() if article.get("description") else ""
    content_html = article.get("contentHtml", "")

    # Parse the content into blocks and grab the first few paragraphs as a hook
    blocks = _parse_html_blocks(content_html) if content_html else []

    # Collect opening paragraphs until we hit ~60-100 words
    hook_parts = []
    hook_words = 0
    for block in blocks:
        if hook_words >= 60:
            break
        if block["type"] == "paragraph":
            text = _clean_paragraph_text(block["text"])
            if text:
                hook_parts.append(text)
                hook_words += len(text.split())
        elif block["type"] == "heading" and hook_words > 0:
            # Stop at the first heading after we've collected some text
            break
        elif block["type"] == "list" and hook_words > 15:
            break

    hook_md = "\n\n".join(hook_parts)

    # Assemble the teaser
    parts = []
    if description:
        parts.append(description)
        parts.append("")  # blank line
    if hook_md:
        parts.append(hook_md)
        parts.append("")  # blank line
    parts.append("---")
    parts.append("")
    parts.append(f"**[Continue reading on Substack \u2192]({link})**")

    return "\n".join(parts)


def publish_to_devto(devto_key, article, body_markdown):
    """Publish an article to dev.to and return the URL."""
    tags = _devto_tags_from_article(article["title"], article.get("description", ""))
    desc = article.get("description", "")
    if desc:
        desc = unescape(desc)[:200]

    payload = json.dumps({
        "article": {
            "title": article["title"],
            "body_markdown": body_markdown,
            "published": True,
            "tags": tags,
            "canonical_url": article["link"],
            "description": desc,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        DEVTO_API_URL,
        data=payload,
        headers={
            "api-key": devto_key,
            "Content-Type": "application/json",
            "User-Agent": DEVTO_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("url", "")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"      ERROR posting to dev.to ({e.code}): {error_body[:200]}")
        return None
    except Exception as e:
        print(f"      ERROR posting to dev.to: {e}")
        return None


# ─── GitHub Push ─────────────────────────────────────────────────────────────

def git_push(token, repo_dir, new_count, old_count, num_new):
    def run(cmd, **kwargs):
        return subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, **kwargs)

    run(["git", "config", "user.email", "karo@productwithattitude.com"])
    run(["git", "config", "user.name", "Karo Zieminski"])
    run(["git", "add", SCHEMA_FILE, LINKS_FILE, LLMS_FILE])

    commit_msg = (
        f"Update schema: add {num_new} new article(s) from Substack feed\n\n"
        f"- Updated #recent-articles: {old_count} → {new_count} articles\n"
        f"- Updated canonical-links and llms.txt\n"
        f"- Auto-generated by update_schema.py"
    )
    result = run(["git", "commit", "-m", commit_msg])
    if result.returncode != 0:
        if "nothing to commit" in (result.stdout + result.stderr):
            print("      No changes to commit.")
            return False
        print(f"      Commit error: {result.stderr.strip()}")
        return False

    push_url = REPO_URL_TEMPLATE.format(token=token, owner=REPO_OWNER, repo=REPO_NAME)
    result = run(["git", "push", push_url, "main"])
    if result.returncode != 0:
        print(f"      Push failed: {result.stderr.strip()}")
        return False
    return True


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Update Product with Attitude schema from Substack RSS feed"
    )
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                        help="GitHub token for repo push (or set GITHUB_TOKEN env var)")
    parser.add_argument("--gist-token", default=os.environ.get("GITHUB_GIST_TOKEN"),
                        help="GitHub classic token for gist creation (or set GITHUB_GIST_TOKEN). Falls back to --token.")
    parser.add_argument("--devto-key", default=os.environ.get("DEVTO_API_KEY"),
                        help="Dev.to API key (or set DEVTO_API_KEY env var)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing files")
    parser.add_argument("--no-push", action="store_true",
                        help="Update local files but don't push to GitHub")
    parser.add_argument("--no-gist", action="store_true",
                        help="Skip gist creation")
    parser.add_argument("--no-devto", action="store_true",
                        help="Skip dev.to cross-posting")
    args = parser.parse_args()

    if not args.token and not args.dry_run:
        print("ERROR: --token required (or set GITHUB_TOKEN env var). Use --dry-run to preview.")
        sys.exit(1)

    # Resolve gist token: prefer --gist-token, fall back to --token
    gist_token = getattr(args, 'gist_token', None) or args.token

    print("=" * 65)
    print("  Product with Attitude — Schema Updater + Gist + Dev.to")
    print("=" * 65)
    print()

    # Clone repo
    if args.no_push or args.dry_run:
        repo_dir = "."
        print("[0/8] Using local files")
    else:
        repo_dir = tempfile.mkdtemp(prefix="pwa_schema_")
        print("[0/8] Cloning repo...")
        push_url = REPO_URL_TEMPLATE.format(token=args.token, owner=REPO_OWNER, repo=REPO_NAME)
        result = subprocess.run(["git", "clone", push_url, repo_dir], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"      Clone failed: {result.stderr.strip()}")
            sys.exit(1)
        print("      Cloned to temp directory")

    schema_path = os.path.join(repo_dir, SCHEMA_FILE)
    links_path = os.path.join(repo_dir, LINKS_FILE)
    llms_path = os.path.join(repo_dir, LLMS_FILE)

    # Fetch RSS
    print("[1/8] Fetching RSS feed...")
    try:
        rss_articles = fetch_rss()
        print(f"      Found {len(rss_articles)} articles in feed")
    except Exception as e:
        print(f"      ERROR: {e}")
        sys.exit(1)

    # Load schema
    print("[2/8] Loading schema...")
    try:
        schema = load_json(schema_path)
        articles_node = find_recent_articles_node(schema)
        existing_count = articles_node.get("numberOfItems", 0)
        existing_urls = get_existing_urls(articles_node)
        print(f"      Schema has {existing_count} articles")
    except Exception as e:
        print(f"      ERROR: {e}")
        sys.exit(1)

    # Detect new
    print("[3/8] Detecting new articles...")
    new_articles = [a for a in rss_articles if a["link"] not in existing_urls]

    if not new_articles:
        print("      No new articles found. Schema is up to date.")
        print("\nDone. No changes needed.")
        return

    new_articles.sort(key=lambda a: a["datePublished"] or "0000-00-00", reverse=True)
    print(f"      Found {len(new_articles)} new article(s):")
    for a in new_articles:
        status = "FREE" if a["isAccessibleForFree"] else "PAID"
        print(f"        + [{a['datePublished']}] {a['title']} ({a['wordCount']} words, {status})")

    # Update schema
    print("[4/8] Updating for_machines.json...")
    schema, inserted = update_schema(schema, new_articles)
    schema = update_series_if_needed(schema, new_articles)
    new_count = find_recent_articles_node(schema)["numberOfItems"]
    print(f"      Articles: {existing_count} -> {new_count}")

    # Update canonical links
    print("[5/8] Updating canonical links...")
    try:
        links_content = load_text(links_path)
        links_content = update_canonical_links(links_content, new_articles)
        print(f"      Added {len(new_articles)} new entries")
    except FileNotFoundError:
        print(f"      WARNING: {LINKS_FILE} not found, skipping")
        links_content = None

    # Update llms.txt
    print("[6/8] Updating llms.txt...")
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        llms_content = load_text(llms_path)
        llms_content = update_llms_txt(llms_content, new_count, today_str)
        print(f"      Updated date to {today_str}")
    except FileNotFoundError:
        print(f"      WARNING: {LLMS_FILE} not found, skipping")
        llms_content = None

    # Create & publish gists (free articles only)
    print("[7/8] Creating GitHub gists...")
    gist_urls = {}
    gist_contents = {}  # title -> markdown content, reused for dev.to
    for article in new_articles:
        if not article["isAccessibleForFree"]:
            print(f"      SKIPPED (paid): {article['title']}")
            continue
        gist_md = create_gist_content(article)
        gist_contents[article["title"]] = gist_md
        if args.dry_run:
            print(f"\n      [DRY RUN] Gist for: {article['title']}")
            print("      " + "-" * 50)
            for line in gist_md.split("\n")[:25]:
                print(f"      {line}")
            print(f"      ... ({len(gist_md)} chars total)")
        elif args.no_gist:
            print(f"      [SKIPPED] {article['title']}")
        else:
            url = publish_gist(gist_token, article, gist_md)
            if url:
                gist_urls[article["title"]] = url
                print(f"      Published: {article['title']}")
                print(f"        -> {url}")
            else:
                print(f"      FAILED: {article['title']}")

    # Cross-post to dev.to (free articles only)
    print("[8/8] Cross-posting to dev.to...")
    devto_urls = {}
    devto_key = getattr(args, 'devto_key', None)
    if args.no_devto:
        print("      [SKIPPED] --no-devto flag set")
    elif not devto_key:
        print("      [SKIPPED] No dev.to API key provided (use --devto-key or DEVTO_API_KEY)")
    else:
        # Fetch existing dev.to articles to avoid duplicates
        print("      Checking for existing articles on dev.to...")
        existing_devto = _get_existing_devto_urls(devto_key)
        print(f"      Found {len(existing_devto)} existing entries on dev.to")

        devto_publish_count = 0
        for article in new_articles:
            if not article["isAccessibleForFree"]:
                print(f"      SKIPPED (paid): {article['title']}")
                continue

            # Check for duplicates by canonical URL or title
            if article["link"] in existing_devto:
                print(f"      SKIPPED (already on dev.to): {article['title']}")
                continue
            if _normalize_title(article["title"]) in existing_devto:
                print(f"      SKIPPED (title match on dev.to): {article['title']}")
                continue

            body_md = create_devto_article_body(article)

            if args.dry_run:
                tags = _devto_tags_from_article(article["title"], article.get("description", ""))
                print(f"\n      [DRY RUN] Dev.to for: {article['title']}")
                print(f"        canonical: {article['link']}")
                print(f"        tags: {tags}")
                print(f"        body: {len(body_md)} chars")
            else:
                # Rate-limit: dev.to allows ~2 posts/minute
                if devto_publish_count > 0:
                    import time as _time
                    _time.sleep(35)

                url = publish_to_devto(devto_key, article, body_md)
                if url:
                    devto_urls[article["title"]] = url
                    devto_publish_count += 1
                    print(f"      Published: {article['title']}")
                    print(f"        -> {url}")
                else:
                    print(f"      FAILED: {article['title']}")

    # Write & push
    if args.dry_run:
        print(f"\n{'=' * 65}")
        print("  DRY RUN — No files modified, nothing pushed")
        print("=" * 65)
    else:
        save_json(schema, schema_path)
        print(f"\n      Saved {SCHEMA_FILE}")
        if links_content is not None:
            save_text(links_content, links_path)
            print(f"      Saved {LINKS_FILE}")
        if llms_content is not None:
            save_text(llms_content, llms_path)
            print(f"      Saved {LLMS_FILE}")

        if not args.no_push:
            print("\nPushing to GitHub...")
            if git_push(args.token, repo_dir, new_count, existing_count, len(new_articles)):
                print("      Pushed successfully.")
            else:
                print("      Push failed.")

    # Summary
    print(f"\n{'=' * 65}")
    print(f"  Done. {len(new_articles)} new article(s) processed.")
    if gist_urls:
        print("\n  Published gists:")
        for t, u in gist_urls.items():
            print(f"    {t}")
            print(f"      {u}")
    if devto_urls:
        print("\n  Published to dev.to:")
        for t, u in devto_urls.items():
            print(f"    {t}")
            print(f"      {u}")
    print("=" * 65)


if __name__ == "__main__":
    main()
