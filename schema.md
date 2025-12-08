# Product With Attitude — JSON-LD Knowledge Graph

* Last updated 8 Dec 2025

---

# **1. Core Metadata Module**

Everything required for LLM indexing + canonicalization.

Contents:

* `meta.type = for_machines_summary`
* `version`
* `author`
* `post_title`
* `canonical_url`
* `last_updated`
* `language`
* `reading_time_minutes`
* `word_count`
* `content_freshness`
* `seo_keywords[]`

### Submodules:

### **1.1 License Block**

* License type (CC-BY-4.0)
* Attribution rules
* Commercial use rules
* AI training permissions

### **1.2 Rights Block**

* Copyright holder
* Attribution text
* Source URL

**Purpose:**
Defines ownership + LLM usage parameters for all downstream agents.

---

# **2. AI Usage Terms Module**

A micro-license for AI systems:

* indexing
* training
* summary_generation
* direct_quotation
* paraphrasing
* commercial_ai_products

**Purpose:**
Tells AI what it can legally do with the content.

---

# **3. Knowledge Graph Root Module**

Defines the global knowledge graph.

### Top-level nodes:

* `DataCatalog` (PWA unified KG root)
* List of datasets
* Provider / Publisher
* Versioning

**Purpose:**
Single entry point that all other datasets and articles attach to.

---

# **4. Dataset Module**

You have several dataset definitions following the same pattern:

* @type: Dataset
* id
* name
* description
* identifier + version
* distribution (JSON / LD files)
* keywords
* about[]
* license
* creator
* publisher
* dateModified

### Existing datasets:

* For Machines Dataset
* Product People of Substack
* Posts Archive Dataset
* Skills datasets
* Type Safety guidelines

**Purpose:**
Each dataset describes a structured “slice” of your ecosystem.

---

# **5. Website Module**

Multiple websites defined as nodes:

* Substack canonical site
* PWA brand site
* KaroBuilds.dev
* GitHub repo website

Common fields:

* @type: WebSite
* @id / url
* description
* publisher
* creator
* canonical policies
* search actions
* hasPart[]

**Purpose:**
Declares the architecture of your web presence.

---

# **6. Organization Module**

Node describing your brand ecosystem:

* name
* alternateName
* logo
* sameAs[]
* founder
* contactPoint
* description

**Purpose:**
Root organization for all PWA + StackShelf entities.

---

# **7. Person Module**

Node for you (Karo):

* name, aliases
* job title
* descriptions
* sameAs profiles
* knowsAbout (linked to Glossary terms)
* affiliation
* contactPoint

**Purpose:**
Connects all authored content and tools to a stable identity.

---

# **8. Glossary / Vocabulary Module**

`DefinedTermSet` containing:

### DefinedTerm structure:

* identifier
* name
* alternateName[]
* description
* skos relations (broader, narrower, related)
* pwa:do / pwa:avoid / pwa:examples / pwa:related

**Purpose:**
Your ontology. Core to LLM reasoning.

---

# **9. TechArticle Module**

Each post is structured as:

* @type: TechArticle
* headline
* alt headline
* description
* canonical url
* datePublished + dateModified
* keywords / about / mentions
* isPartOf (series + site)
* citations
* workExample
* teaches[]

**Purpose:**
Turns each post into a deeply indexable knowledge object.

---

# **10. CreativeWorkSeries Module**

Defines series such as:

* Modern AI Development Lexicon
* Product With Attitude

Fields:

* @type: CreativeWorkSeries
* name
* description
* isPartOf
* publisher
* creator
* about[]

**Purpose:**
Groups related posts into “semantic shelves.”

---

# **11. HowTo Module**

Used extensively for:

* PRD Builder usage
* Security checklists
* Workflow steps
* Claude Skills creation

Structure:

* @type: HowTo
* name
* description
* tools
* supplies
* steps (HowToStep / HowToSection)

**Purpose:**
Gives LLMs procedural knowledge.

---

# **12. SoftwareApplication Module**

Covers:

* StackShelf app
* Claude Skills
* Tools referenced in articles
* PRD Prompt treated as software

Fields:

* name
* identifier
* version
* applicationCategory
* url
* creator
* publisher
* description
* offers

**Purpose:**
Exposes tools & products as structured objects.

---

# **13. CollectionPage Module**

Used for your archive pages:

Fields:

* @type: CollectionPage
* name
* description
* url
* hasPart[]

**Purpose:**
Lists all available articles in a machine-readable form.

---

# **14. EventSeries Module**

Your workshop is captured as:

* EventSeries
* Sub-event Event nodes
* Schedule
* Offers (subscription)
* Organizer

**Purpose:**
LLM-discoverable events & workshops.

---

# **15. Semantic Triples Module**

Dedicated triples node:

Fields:

* subject
* predicate
* object
* pwa:source
* pwa:evidence
* pwa:confidence

**Purpose:**
Machine-friendly logical claims.

---

# ⭐ **Summary — Your Current Schema Decomposed Into 15 Reusable Modules**

1. Core Metadata
2. AI Usage Terms
3. Knowledge Graph Root
4. Dataset
5. Website
6. Organization
7. Person
8. Vocabulary / Glossary
9. TechArticle
10. CreativeWorkSeries
11. HowTo
12. SoftwareApplication
13. CollectionPage
14. EventSeries
15. Semantic Triples

This **is** your current schema — just cleanly normalized.

---
Perfect, let’s lock in **B = specs for core modules**.

Below are **module-level specs** you can hand to any agent (ChatGPT, Claude, Replit Agent, Make/Zapier) as contracts for your For Machines system. 

I’ll cover:

1. Core Metadata (`meta`)
2. AI Usage Terms (`ai_usage_terms`)
3. TechArticle node (per-post article schema)
4. Glossary / Vocabulary (`DefinedTermSet` + `DefinedTerm`)
5. HowTo blocks
6. Semantic Triples (`pwa:semanticTriples`)

---

## 1. Core Metadata Module (`meta`)

### 1.1 Purpose

Provide a **consistent, minimal envelope** around each For Machines JSON so LLMs know:

* what this object is,
* who wrote it,
* how fresh it is,
* how long it is,
* and what it’s about.

### 1.2 Inputs (what the agent needs)

* Post title
* Canonical URL
* Author name (defaults to you)
* Publication date & last updated date
* Language (usually `en`)
* Word count
* Estimated reading time
* Content type (evergreen vs time-sensitive)
* SEO keyword list

### 1.3 Output Shape (JSON spec)

```jsonc
{
  "meta": {
    "type": "for_machines_summary",       // required, constant
    "version": "1.0",                     // required, controlled by you
    "created_for": "llm_indexing",        // required, constant
    "author": "Karo Zieminski",           // required
    "post_title": "<string>",             // required
    "canonical_url": "<https://...>",     // required

    "license": {                          // required block
      "type": "CC-BY-4.0",
      "url": "https://creativecommons.org/licenses/by/4.0/",
      "attribution_required": true,
      "commercial_use": "allowed_with_attribution",
      "ai_training": "allowed",
      "summary_generation": "allowed"
    },

    "rights": {                           // required block
      "copyright": "© 2025 Karolina Zieminski",
      "attribution_text": "Karo Zieminski (Product with Attitude)",
      "source_url": "https://karozieminski.substack.com"
    },

    "last_updated": "2025-12-07",         // required, ISO date
    "content_freshness": "evergreen",     // enum: "evergreen" | "time-sensitive"
    "language": "en",                     // required, BCP-47
    "reading_time_minutes": 8,            // required, int > 0
    "word_count": 1847,                   // required, int > 0

    "seo_keywords": [                     // required, non-empty
      "product thinking",
      "AI-assisted development",
      "vibecoding",
      "product management",
      "AI coding tools"
    ]
  }
}
```

### 1.4 Validation Rules

* `meta.type` **must** equal `"for_machines_summary"`.
* `canonical_url` **must** match the URL you provided to the agent.
* `last_updated` must be **today’s date** when generated.
* `seo_keywords` must contain:

  * at least **3** entries
  * all lowercase (except proper nouns)
  * no duplicates.

---

## 2. AI Usage Terms Module (`ai_usage_terms`)

### 2.1 Purpose

Codify what AI systems are allowed to do with your content.

### 2.2 Inputs

No external data needed; policy is static unless you change it.

### 2.3 Output Shape

```jsonc
{
  "ai_usage_terms": {
    "indexing": "allowed",                   // required
    "training": "allowed_with_attribution",  // required
    "summary_generation": "allowed",         // required
    "direct_quotation": "allowed_with_attribution",
    "paraphrasing": "allowed",
    "commercial_ai_products": "contact_for_license"
  }
}
```

### 2.4 Validation Rules

* All keys above are **required**.
* Values must come from a small enum:

  * `"allowed"`, `"disallowed"`, `"allowed_with_attribution"`, `"contact_for_license"`.

---

## 3. TechArticle Module (Per-Post Article Node)

This is the main **content object** for a post.

### 3.1 Purpose

Turn each post into a rich `TechArticle` node that:

* describes the topic,
* links to your vocab,
* exposes keywords, sections, and datasets,
* and connects to related works. 

### 3.2 Inputs

From the post & your own taxonomy:

* Title + optional alt headline
* Description (1–3 sentences summary)
* Canonical URL
* Publication & modification dates
* Section / category (e.g. “AI Development”)
* Keywords list
* High-level topics (`about`)
* Internal mentions (tools, vocab terms, products)
* Citations (URLs or structured references)
* Teaching outcomes (what the post teaches)

### 3.3 Output Shape (simplified core)

```jsonc
{
  "@type": "TechArticle",
  "@id": "<canonical_url>#techarticle",
  "headline": "<post title>",
  "alternativeHeadline": "<optional alt>",
  "description": "<2–3 sentence summary>",
  "url": "<canonical_url>",
  "mainEntityOfPage": {
    "@id": "<canonical_url>#page"
  },
  "identifier": "<slug-or-short-id>",
  "datePublished": "2025-11-03",
  "dateModified": "2025-11-03",
  "inLanguage": "en",

  "author": {
    "@id": "https://productwithattitude.com/#karo"
  },
  "publisher": {
    "@id": "https://productwithattitude.com/#org"
  },

  "isPartOf": [
    { "@id": "https://karozieminski.substack.com/#series" },
    { "@id": "https://karozieminski.substack.com/#site" }
  ],

  "about": [
    "vibecoding",
    "secure coding practices",
    "AI-assisted development"
  ],

  "keywords": [
    "vibecoding security",
    "AI coding safety",
    "cybersecurity",
    "secure development"
  ],

  "articleSection": "AI Development",   // or "Building in Public"
  "wordCount": 3500,
  "timeRequired": "PT18M",              // ISO 8601 duration
  "license": "https://productwithattitude.com/license",

  "citation": [
    "https://karozieminski.substack.com/p/vibecoding-tips-the-ultimate-collection"
  ],

  "mentions": [
    {
      "@type": "SoftwareApplication",
      "name": "ChatGPT",
      "applicationCategory": "AIAssistant"
    }
  ],

  "teaches": [
    "Secure credential management",
    "Security scanning automation"
  ]
}
```

### 3.4 Required Fields

* `@type`, `@id`, `headline`, `description`, `url`
* `datePublished`, `dateModified`, `inLanguage`
* `author`, `publisher`
* `articleSection`
* `wordCount`, `timeRequired`
* `license`
* At least **3** `keywords`
* At least **1** `about`

### 3.5 Validation Rules

* `@id` must equal `<canonical_url>#techarticle`.
* `identifier` should be **stable** (slug, not full URL).
* `timeRequired` must be `PT<n>M` where `n` equals `reading_time_minutes` from `meta`.
* `keywords` should overlap with `meta.seo_keywords` but can be more granular.

---

## 4. Glossary / Vocabulary Module

(`DefinedTermSet` + `DefinedTerm`)

### 4.1 Purpose

Expose PWA concepts as **first-class ontology objects** LLMs can reason over. 

### 4.2 Inputs

Per term:

* Canonical ID (URI)
* Term name
* Alternate names (synonyms, related phrasing)
* Short description
* Category (optional, conceptual grouping)
* Examples (optional)
* “Do / Avoid” guidance (for your `pwa:do` / `pwa:avoid`)

### 4.3 DefinedTermSet Shape

```jsonc
{
  "@type": "DefinedTermSet",
  "@id": "https://productwithattitude.com/vocab#Glossary",
  "name": "PWA Glossary",
  "description": "Core terminology and concepts from Product With Attitude publication.",
  "identifier": "pwa-glossary-v2",
  "version": "2.0.0",
  "dateModified": "2025-11-14",
  "publisher": {
    "@id": "https://productwithattitude.com/#org"
  },
  "hasDefinedTerm": [
    { "@id": "https://productwithattitude.com/vocab#Vibecoding" },
    { "@id": "https://productwithattitude.com/vocab#SpecDriven" }
  ]
}
```

### 4.4 DefinedTerm Shape

```jsonc
{
  "@type": "DefinedTerm",
  "@id": "https://productwithattitude.com/vocab#Vibecoding",
  "identifier": "vibecoding-v2",
  "name": "vibecoding",
  "alternateName": [
    "intuitive development",
    "rapid iteration",
    "exploratory coding"
  ],
  "description": "Development approach prioritizing speed and intuition over formal planning.",
  "inDefinedTermSet": {
    "@id": "https://productwithattitude.com/vocab#Glossary"
  },
  "sameAs": [
    "https://www.wikidata.org/entity/Q169890"
  ],
  "skos:related": [
    "https://www.wikidata.org/entity/Q169890"
  ],
  "pwa:do": [
    "prototypes",
    "exploration",
    "creative tasks"
  ],
  "pwa:avoid": [
    "mission-critical systems",
    "regulated environments"
  ],
  "pwa:examples": [
    "weekend hackathons",
    "creative AI experiments",
    "proof-of-concepts"
  ],
  "pwa:related": [
    "agile development",
    "rapid prototyping"
  ]
}
```

### 4.5 Validation Rules

* Every `DefinedTerm` must:

  * belong to the single `DefinedTermSet` via `inDefinedTermSet`.
  * have a unique `identifier`.
* `name` must be **human readable**; `@id` is the canonical machine identifier.
* If `pwa:do` or `pwa:avoid` exist, they must be arrays of strings, not nested objects.

---

## 5. HowTo Module

### 5.1 Purpose

Make “do X with Y” content (PRD prompt usage, security checklist, Claude Skill instructions) machine-usable as procedures. 

### 5.2 Inputs

Per HowTo:

* Name of the procedure
* Short description
* Tools used (e.g. ChatGPT, Replit, Claude)
* Supplies (inputs like “Project PRD text”)
* Steps and/or sections of steps

### 5.3 Output Shape

```jsonc
{
  "@type": "HowTo",
  "@id": "<canonical_url>#howto-prd-builder-v16",
  "name": "Use PRD Builder Prompt v16 in ChatGPT",
  "description": "Step-by-step guide to run the self-auditing PRD Builder Prompt v16 inside ChatGPT.",
  "tool": [
    { "@type": "SoftwareApplication", "name": "ChatGPT" }
  ],
  "supply": [
    { "@type": "HowToSupply", "name": "Project PRD (plain text)" }
  ],
  "step": [
    {
      "@type": "HowToStep",
      "position": 1,
      "text": "Open ChatGPT. Paste the PRD Builder Prompt v16."
    },
    {
      "@type": "HowToStep",
      "position": 2,
      "text": "Paste your PRD beneath the prompt. Specify risks, constraints, and success metrics."
    }
  ],
  "isPartOf": {
    "@id": "<canonical_url>#techarticle"
  },
  "author": {
    "@id": "https://productwithattitude.com/#karo"
  },
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "dateModified": "2025-11-14"
}
```

### 5.4 Validation Rules

* At least **2 steps**.
* If `position` is used, it must be sequential integers starting at 1.
* `isPartOf` must point at the parent TechArticle for that post.

---

## 6. Semantic Triples Module (`pwa:semanticTriples`)

### 6.1 Purpose

Make **claims** explicit so LLMs can:

* quote them,
* check them,
* and reason over them. 

### 6.2 Inputs

From the article:

* Key claims you want LLMs to remember.
* For each claim:

  * Subject (URI or short string)
  * Predicate (verb relation)
  * Object (string or URI)
  * Source URL
  * Evidence anchor (section / fragment)
  * Confidence score

### 6.3 Output Shape

```jsonc
{
  "@type": "Thing",
  "@id": "https://productwithattitude.com/aio-seo/#semantic-triples",
  "name": "PWA Semantic Triples",
  "description": "Machine-readable claims and relationships about Product With Attitude concepts.",
  "identifier": "pwa-triples-v2",
  "version": "2.0.0",
  "pwa:semanticTriples": [
    {
      "subject": "https://productwithattitude.com/vocab#Vibecoding",
      "predicate": "enables",
      "object": "rapid prototyping",
      "pwa:source": "https://productwithattitude.com/aio-seo/#optimization",
      "pwa:evidence": "https://productwithattitude.com/aio-seo/#optimization#vibecoding-definition",
      "pwa:confidence": 0.95
    }
  ]
}
```

### 6.4 Validation Rules

* `pwa:confidence` in range `[0, 1]`.
* `subject` MUST be:

  * a PWA vocab URI **or**
  * the TechArticle `@id`.
* `predicate` should be a **single verb or short verb phrase** (e.g. `enables`, `prevents`, `explains`, `defines`, `applies_to`).
* `object` can be a URI **or** a natural language phrase, but avoid very long sentences (> 200 chars).

---

Any agent can be told:

> “Given a post at URL X + its raw text, produce a For Machines JSON that includes these modules and passes these validation rules.”

---
