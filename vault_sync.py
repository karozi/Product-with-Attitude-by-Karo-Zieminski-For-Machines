#!/usr/bin/env python3
"""
AttitudeVault → For Machines Full Sync Pipeline
=================================================
One script. Zero AI credits. Fetches vault data, updates schema + llms.txt, pushes to GitHub.

Full pipeline:
  1. Fetch vault items from AttitudeVault API (or Neon DB fallback)
  2. Clone the For Machines repo
  3. Run sync: update for_machines.json + llms.txt
  4. Commit and push to GitHub

Usage:
    python3 vault_sync.py --token GITHUB_TOKEN [--dry-run] [--no-push] [--use-db]

Environment variable alternative:
    export GITHUB_TOKEN=ghp_...
    python3 vault_sync.py
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
from datetime import datetime, timezone


# ─── Configuration ──────────────────────────────────────────────────────────

VAULT_API_URL = "https://vault.productwithattitude.com/api/items"
VAULT_URL = "https://vault.productwithattitude.com"
VAULT_NODE_ID = "#product-attitudevault"
CATALOG_NODE_ID = "#attitudevault-catalog"
FAQ_NODE_ID = "#faq"
AUTHOR_ID = "https://karozieminski.substack.com/#author"

REPO_OWNER = "karozi"
REPO_NAME = "Product-with-Attitude-by-Karo-Zieminski-For-Machines"
REPO_URL_TEMPLATE = "https://{token}@github.com/{owner}/{repo}.git"

SCHEMA_FILE = "for_machines.json"
LLMS_FILE = "llms.txt"

NEON_DB_URL = (
    "postgresql://neondb_owner:npg_Rge2PLqGu7Ad@"
    "ep-solitary-night-adn99yqm.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"
)

CATEGORY_DISPLAY = {
    "everyday-prompts": "AI Prompts for Everyday Work",
    "coding-with-ai": "Vibe Coding Prompts",
    "vibe-coding": "Vibe Coding Prompts",
    "vibecoding-prompts": "Vibe Coding Prompts",
    "vibecoding-specs": "Vibe Coding Prompts",
    "guides-templates": "AI Prompt Templates",
    "automation": "AI Automation Workflows",
    "claude-skills": "Claude Skills Library",
    "codeblock": "Vibe Coding Prompts",
    "prompt": "AI Prompt Templates",
    "template": "AI Prompt Templates",
    "AI Prompts for Everyday Work": "AI Prompts for Everyday Work",
    "Vibe Coding Prompts": "Vibe Coding Prompts",
    "AI Prompt Templates": "AI Prompt Templates",
    "AI Automation Workflows": "AI Automation Workflows",
    "Claude Skills Library": "Claude Skills Library",
}


# ─── Vault Data Fetching ───────────────────────────────────────────────────

def fetch_vault_api():
    """Fetch vault items from the AttitudeVault API."""
    req = urllib.request.Request(
        VAULT_API_URL,
        headers={"User-Agent": "PWA-VaultSync/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            elif isinstance(data, list):
                return data
            else:
                print("      WARNING: Unexpected API response format")
                return None
    except Exception as e:
        print(f"      API error: {e}")
        return None


def fetch_vault_db():
    """Fetch vault items directly from Neon DB (fallback)."""
    query = (
        "SELECT json_agg(row_to_json(t)) FROM ("
        "SELECT i.*, c.name as creator_name, c.substack_url as creator_substack_url "
        "FROM items i JOIN creators c ON i.creator_id = c.id ORDER BY i.id"
        ") t;"
    )
    try:
        result = subprocess.run(
            ["psql", NEON_DB_URL, "-c", query, "-t", "-A"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"      DB error: {result.stderr.strip()}")
            return None
        raw = result.stdout.strip()
        if not raw or raw == "null":
            return None
        return json.loads(raw)
    except FileNotFoundError:
        print("      psql not found — cannot use DB fallback")
        return None
    except Exception as e:
        print(f"      DB error: {e}")
        return None


# ─── Helpers ────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def find_node(graph, node_id):
    for i, node in enumerate(graph):
        if node.get("@id") == node_id:
            return i, node
    return None, None


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def quill_to_plain(delta):
    if isinstance(delta, str):
        return delta.strip()
    if isinstance(delta, dict) and "ops" in delta:
        parts = []
        for op in delta["ops"]:
            insert = op.get("insert", "")
            if isinstance(insert, str):
                parts.append(insert)
        return "".join(parts).strip()
    return str(delta).strip() if delta else ""


def normalize_category(raw_cat):
    if raw_cat in CATEGORY_DISPLAY:
        return CATEGORY_DISPLAY[raw_cat]
    return raw_cat


def normalize_item(item):
    creator = item.get("creator", {})
    if isinstance(creator, dict):
        creator_name = creator.get("name", "Karo Zieminski")
        creator_url = (
            creator.get("substackUrl")
            or creator.get("substack_url")
            or creator.get("contact", "")
        )
    else:
        creator_name = item.get("creator_name", "Karo Zieminski")
        creator_url = item.get("creator_substack_url", "")

    desc_raw = item.get("description", "")
    description = quill_to_plain(desc_raw)
    if len(description) > 300:
        description = description[:297] + "..."

    created = item.get("createdAt") or item.get("created_at") or today_str()
    if isinstance(created, str) and "T" in created:
        created = created[:10]

    is_premium = item.get("isPremium") or item.get("premium") or False

    tools = item.get("tools", [])
    if isinstance(tools, str):
        try:
            tools = json.loads(tools)
        except (json.JSONDecodeError, TypeError):
            tools = [tools] if tools else []

    tags = item.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = [tags] if tags else []

    return {
        "title": item.get("title", "Untitled"),
        "slug": item.get("slug", slugify(item.get("title", "untitled"))),
        "description": description,
        "category": normalize_category(item.get("category", "Uncategorized")),
        "isPremium": is_premium,
        "tools": tools,
        "tags": tags,
        "learnMoreLink": item.get("learnMoreLink") or item.get("learn_more_link"),
        "createdAt": created,
        "creatorName": creator_name,
        "creatorUrl": creator_url,
    }


# ─── Build Vault Catalog Node ──────────────────────────────────────────────

def build_catalog_items(items):
    categorized = {}
    for item in items:
        cat = item["category"]
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(item)

    list_elements = []
    position = 1
    for cat in sorted(categorized.keys()):
        for item in sorted(categorized[cat], key=lambda x: x["title"]):
            element = {
                "@type": "ListItem",
                "position": position,
                "item": {
                    "@type": "CreativeWork",
                    "name": item["title"],
                    "url": f"{VAULT_URL}/item/{item['slug']}",
                    "description": item["description"],
                    "category": cat,
                    "creator": {
                        "@type": "Person",
                        "name": item["creatorName"],
                    },
                    "isAccessibleForFree": not item["isPremium"],
                    "datePublished": item["createdAt"],
                },
            }
            if item["tools"]:
                element["item"]["keywords"] = item["tools"]
            if item["tags"]:
                element["item"]["about"] = item["tags"]
            list_elements.append(element)
            position += 1

    return list_elements


# ─── Update for_machines.json ───────────────────────────────────────────────

def update_for_machines(schema, items):
    graph = schema.get("@graph", [])
    changes = []

    categories = sorted(set(item["category"] for item in items))
    category_counts = {}
    for item in items:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # 1. Update #product-attitudevault
    idx, vault_node = find_node(graph, VAULT_NODE_ID)
    if vault_node is not None:
        old_desc = vault_node.get("description", "")
        vault_node["description"] = (
            f"Free, curated prompt library with {len(items)} production-tested prompts, "
            f"templates, and workflows across {len(categories)} categories: "
            f"{', '.join(categories)}. "
            f"Each prompt includes context, variables, and expected output format. "
            f"Featured on vibecoding.builders."
        )
        vault_node["dateModified"] = today_str()
        vault_node["pwa:itemCount"] = len(items)
        vault_node["pwa:categories"] = categories
        if old_desc != vault_node["description"]:
            changes.append(f"Updated #product-attitudevault ({len(items)} items, {len(categories)} categories)")
        else:
            changes.append("No changes to #product-attitudevault")
        graph[idx] = vault_node
    else:
        changes.append("WARNING: #product-attitudevault node not found")

    # 2. Update or create #attitudevault-catalog
    cat_idx, cat_node = find_node(graph, CATALOG_NODE_ID)
    catalog_node = {
        "@type": "ItemList",
        "@id": CATALOG_NODE_ID,
        "name": "AttitudeVault Prompt Catalog",
        "description": (
            f"Complete catalog of {len(items)} production-tested prompts, templates, "
            f"and workflows in AttitudeVault."
        ),
        "numberOfItems": len(items),
        "url": VAULT_URL,
        "dateModified": today_str(),
        "itemListElement": build_catalog_items(items),
    }

    if cat_idx is not None:
        old_count = cat_node.get("numberOfItems", 0)
        graph[cat_idx] = catalog_node
        changes.append(f"Updated #attitudevault-catalog ({old_count} -> {len(items)} items)")
    else:
        graph.append(catalog_node)
        changes.append(f"Created #attitudevault-catalog ({len(items)} items)")

    # 3. Update FAQ
    faq_idx, faq_node = find_node(graph, FAQ_NODE_ID)
    if faq_node is not None:
        main_entity = faq_node.get("mainEntity", [])
        for q in main_entity:
            qname = q.get("name", "")
            if "AttitudeVault" in qname or "Attitude Vault" in qname:
                cat_summary = ", ".join(
                    f"{cat} ({count})" for cat, count in sorted(category_counts.items())
                )
                q["acceptedAnswer"]["text"] = (
                    f"AttitudeVault (attitudevault.dev) is a free, curated prompt library "
                    f"with {len(items)} production-tested prompts, templates, and workflows "
                    f"for vibecoding practitioners. Categories: {cat_summary}. "
                    f"Each prompt includes context, variables, and expected output. "
                    f"Featured on vibecoding.builders. No login required."
                )
                changes.append("Updated FAQ answer for AttitudeVault")
                break
        graph[faq_idx] = faq_node

    schema["@graph"] = graph
    return schema, changes


# ─── Update llms.txt ────────────────────────────────────────────────────────

def update_llms_txt(text, items):
    changes = []
    categories = sorted(set(item["category"] for item in items))

    vault_pattern = r"(- \*\*AttitudeVault\*\*:)[^\n]*\n(  - [^\n]*\n)*"
    vault_replacement = (
        f"- **AttitudeVault**: Free, curated prompt library with {len(items)} "
        f"production-tested prompts, templates, and workflows for vibecoding practitioners. "
        f"Categories: {', '.join(categories)}.\n"
        f"  - URL: https://attitudevault.dev\n"
        f"  - Featured on: https://www.vibecoding.builders/projects/attitude-vault\n"
    )

    new_text, count = re.subn(vault_pattern, vault_replacement, text, count=1)
    if count > 0:
        changes.append(f"Updated AttitudeVault in Products & Tools ({len(items)} items)")
        text = new_text

    text = re.sub(
        r"(- \*\*Last Updated\*\*:) \d{4}-\d{2}-\d{2}",
        f"\\1 {today_str()}",
        text,
    )
    text = re.sub(
        r"(\*\*Last Updated\*\*:) \d{4}-\d{2}-\d{2}",
        f"\\1 {today_str()}",
        text,
    )
    changes.append(f"Updated Last Updated to {today_str()}")

    return text, changes


# ─── Git Operations ─────────────────────────────────────────────────────────

def git_push(token, repo_dir, item_count, category_count):
    def run(cmd, **kwargs):
        return subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, **kwargs)

    run(["git", "config", "user.email", "karo@productwithattitude.com"])
    run(["git", "config", "user.name", "Karo Zieminski"])
    run(["git", "add", SCHEMA_FILE, LLMS_FILE])

    commit_msg = (
        f"sync: AttitudeVault catalog update ({today_str()})\n\n"
        f"- {item_count} items across {category_count} categories\n"
        f"- Updated for_machines.json, llms.txt\n"
        f"- Auto-generated by vault_sync.py"
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
        description="AttitudeVault -> For Machines Full Sync Pipeline"
    )
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                        help="GitHub token for repo push (or GITHUB_TOKEN env)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes without writing or pushing")
    parser.add_argument("--no-push", action="store_true",
                        help="Update local files but don't push to GitHub")
    parser.add_argument("--use-db", action="store_true",
                        help="Fetch from Neon DB instead of API")
    args = parser.parse_args()

    if not args.token and not args.dry_run:
        print("ERROR: --token required (or set GITHUB_TOKEN env). Use --dry-run to preview.")
        sys.exit(1)

    TOTAL_STEPS = 4

    print("=" * 65)
    print("  AttitudeVault -> For Machines Sync Pipeline")
    print("=" * 65)
    print()

    # ── Step 1: Fetch vault data ────────────────────────────────────────
    print(f"[1/{TOTAL_STEPS}] Fetching vault data...")
    if args.use_db:
        print("      Using Neon DB...")
        raw_items = fetch_vault_db()
    else:
        print("      Using AttitudeVault API...")
        raw_items = fetch_vault_api()
        if raw_items is None:
            print("      API failed, falling back to Neon DB...")
            raw_items = fetch_vault_db()

    if not raw_items:
        print("      ERROR: No vault items found. Aborting.")
        sys.exit(1)

    items = [normalize_item(item) for item in raw_items]
    categories = sorted(set(item["category"] for item in items))
    category_counts = {}
    for item in items:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print(f"      Loaded {len(items)} items across {len(categories)} categories:")
    for cat in categories:
        print(f"        - {cat}: {category_counts[cat]}")

    # ── Step 2: Clone repo ──────────────────────────────────────────────
    print(f"\n[2/{TOTAL_STEPS}] Cloning repo...")
    if args.no_push or args.dry_run:
        # For dry-run, clone without auth
        repo_dir = tempfile.mkdtemp(prefix="pwa_vault_sync_")
        result = subprocess.run(
            ["git", "clone", f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git", repo_dir],
            capture_output=True, text=True,
        )
    else:
        repo_dir = tempfile.mkdtemp(prefix="pwa_vault_sync_")
        push_url = REPO_URL_TEMPLATE.format(token=args.token, owner=REPO_OWNER, repo=REPO_NAME)
        result = subprocess.run(
            ["git", "clone", push_url, repo_dir],
            capture_output=True, text=True,
        )

    if result.returncode != 0:
        print(f"      Clone failed: {result.stderr.strip()}")
        sys.exit(1)
    print("      Cloned successfully")

    schema_path = os.path.join(repo_dir, SCHEMA_FILE)
    llms_path = os.path.join(repo_dir, LLMS_FILE)

    # ── Step 3: Run sync ────────────────────────────────────────────────
    print(f"\n[3/{TOTAL_STEPS}] Updating schema + llms.txt...")

    schema = load_json(schema_path)
    llms_text = load_text(llms_path)

    schema, json_changes = update_for_machines(schema, items)
    for c in json_changes:
        print(f"      {c}")

    llms_text, txt_changes = update_llms_txt(llms_text, items)
    for c in txt_changes:
        print(f"      {c}")

    # ── Step 4: Write & push ────────────────────────────────────────────
    print(f"\n[4/{TOTAL_STEPS}] Writing & pushing...")

    if args.dry_run:
        print(f"\n{'=' * 65}")
        print("  DRY RUN — No files modified, nothing pushed")
        print("=" * 65)
    else:
        save_json(schema_path, schema)
        save_text(llms_path, llms_text)
        print(f"      Saved {SCHEMA_FILE}")
        print(f"      Saved {LLMS_FILE}")

        if not args.no_push:
            print("\n      Pushing to GitHub...")
            if git_push(args.token, repo_dir, len(items), len(categories)):
                print("      Pushed successfully.")
            else:
                print("      Push failed (or no changes).")

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print(f"  DONE — {len(items)} vault items synced")
    print(f"{'=' * 65}")
    print(f"\n  Items: {len(items)}")
    print(f"  Categories: {len(categories)}")
    for cat in categories:
        print(f"    - {cat}: {category_counts[cat]}")
    print(f"  Changes: {len(json_changes) + len(txt_changes)}")
    print(f"\n  Repo: https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
