#!/usr/bin/env python3
"""
Update for-machines.jsonld with manually edited quotes from quotes-editable.json
"""

import json
import re
from pathlib import Path

# Paths
QUOTES_FILE = Path(__file__).parent / "quotes-editable.json"
JSONLD_FILE = Path(__file__).parent / "for-machines.jsonld"

def create_quote_id(text):
    """Create anchor ID from quote text"""
    # Take first 50 chars, lowercase, remove non-alphanumeric, replace spaces with hyphens
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
    print("📝 Updating for-machines.jsonld with edited quotes...\n")

    # Load edited quotes
    with open(QUOTES_FILE, 'r', encoding='utf-8') as f:
        quotes_data = json.load(f)

    # Load current for-machines.jsonld
    with open(JSONLD_FILE, 'r', encoding='utf-8') as f:
        jsonld = json.load(f)

    # Create lookup of quotes by post_id
    quotes_by_post_id = {
        post['post_id']: post['quotes']
        for post in quotes_data['posts']
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

if __name__ == "__main__":
    main()
