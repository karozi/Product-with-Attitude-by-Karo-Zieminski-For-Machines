#!/usr/bin/env python3
"""
Parse quotes-editable.md and update for-machines.jsonld with edited quotes
"""

import json
import re
from pathlib import Path
from datetime import datetime

# Paths
MARKDOWN_FILE = Path(__file__).parent / "quotes-editable.md"
JSONLD_FILE = Path(__file__).parent / "for-machines.jsonld"

def parse_markdown_quotes(md_content):
    """Parse Markdown quotes file into structured data"""
    posts = []
    current_post = None
    current_quote = None

    lines = md_content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # New post section
        if line.startswith('## Post: '):
            if current_post and current_post['quotes']:
                posts.append(current_post)

            post_title = line[9:].strip()
            current_post = {
                'post_title': post_title,
                'post_id': '',
                'post_url': '',
                'quotes': []
            }
            current_quote = None

        # Post ID
        elif line.startswith('**ID:** `'):
            if current_post:
                current_post['post_id'] = line[9:].rstrip('`').strip()

        # Post URL
        elif line.startswith('**URL:** '):
            if current_post:
                current_post['post_url'] = line[9:].strip()

        # New quote
        elif line.startswith('### Quote '):
            if current_quote and current_post:
                current_post['quotes'].append(current_quote)

            position_match = re.search(r'Quote (\d+)', line)
            position = int(position_match.group(1)) if position_match else 1

            current_quote = {
                'position': position,
                'type': '',
                'confidence': 0,
                'text': ''
            }

        # Quote type
        elif line.startswith('**Type:** `'):
            if current_quote:
                current_quote['type'] = line[11:].rstrip('`').strip()

        # Quote confidence
        elif line.startswith('**Confidence:** `'):
            if current_quote:
                try:
                    current_quote['confidence'] = float(line[17:].rstrip('`').strip())
                except ValueError:
                    current_quote['confidence'] = 0.9

        # Quote text (in code block)
        elif line == '**Text:**' and current_quote:
            # Find the code block
            i += 1
            if i < len(lines) and lines[i].strip() == '```':
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() != '```':
                    text_lines.append(lines[i])
                    i += 1
                current_quote['text'] = '\n'.join(text_lines).strip()

        i += 1

    # Add last quote and post
    if current_quote and current_post:
        current_post['quotes'].append(current_quote)
    if current_post and current_post['quotes']:
        posts.append(current_post)

    return posts

def create_quote_id(text):
    """Create anchor ID from quote text"""
    quote_id = re.sub(r'[^a-z0-9]+', '-', text[:50].lower()).strip('-')
    return quote_id

def create_quotation_node(quote, post_slug, post_url, position):
    """Create a Quotation JSON-LD node"""
    quote_id = create_quote_id(quote['text'])

    return {
        "@type": "Quotation",
        "@id": f"#quote-{post_slug}-{position}",
        "identifier": f"quote-{quote_id}",
        "text": quote['text'],
        "author": {
            "@id": "https://karozieminski.substack.com/#karo-zieminski"
        },
        "isPartOf": {
            "@id": f"#post-{post_slug}"
        },
        "position": position,
        "citation": {
            "@type": "CreativeWork",
            "url": f"{post_url}#{quote_id}"
        },
        "pwa:quoteType": quote['type'],
        "pwa:confidence": quote['confidence']
    }

def main():
    print("📝 Parsing Markdown quotes and updating for-machines.jsonld...\n")

    # Read Markdown file
    with open(MARKDOWN_FILE, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Parse quotes from Markdown
    posts_with_quotes = parse_markdown_quotes(md_content)

    # Load current for-machines.jsonld
    with open(JSONLD_FILE, 'r', encoding='utf-8') as f:
        jsonld = json.load(f)

    # Create lookup of quotes by post_id
    quotes_by_post_id = {
        post['post_id']: post['quotes']
        for post in posts_with_quotes
    }

    # Update BlogPosting nodes with new quotes
    total_quotes = 0
    posts_updated = 0

    for node in jsonld['@graph']:
        if node.get('@type') == 'BlogPosting':
            post_id = node.get('identifier', '')
            post_url = node.get('url', '')

            if post_id in quotes_by_post_id:
                quotes = quotes_by_post_id[post_id]

                # Create Quotation nodes
                quotation_nodes = [
                    create_quotation_node(q, post_id, post_url, q['position'])
                    for q in quotes
                ]

                # Update hasPart
                node['hasPart'] = quotation_nodes

                total_quotes += len(quotation_nodes)
                posts_updated += 1

                print(f"  ✓ {node.get('headline', 'Unknown')}")
                print(f"    Updated {len(quotation_nodes)} quotes")

    # Save updated JSON-LD
    with open(JSONLD_FILE, 'w', encoding='utf-8') as f:
        json.dump(jsonld, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Success!")
    print(f"   Updated {posts_updated} posts")
    print(f"   Total quotes: {total_quotes}")
    print(f"   Saved to: {JSONLD_FILE}")
    print(f"\n💡 Next step: Review changes and commit to GitHub")

if __name__ == "__main__":
    main()
