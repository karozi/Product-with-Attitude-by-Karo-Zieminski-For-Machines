#!/usr/bin/env node

/**
 * Product With Attitude - JSON-LD Auto-Update Agent
 *
 * Automatically updates for-machines.jsonld with new Substack posts.
 *
 * Usage:
 *   node update-jsonld.js [--full] [--analyze]
 *
 * Options:
 *   --full      Regenerate entire archive (default: incremental)
 *   --analyze   Use Claude API for LLM-assisted content analysis
 *
 * Environment Variables:
 *   ANTHROPIC_API_KEY    Claude API key for content analysis (optional)
 *   SUBSTACK_RSS_URL     Override default RSS feed URL (optional)
 */

const fs = require('fs');
const https = require('https');
const { parseString } = require('xml2js');

// Configuration
const CONFIG = {
  rssUrl: process.env.SUBSTACK_RSS_URL || 'https://karozieminski.substack.com/feed',
  jsonldPath: './for-machines.jsonld',
  license: 'https://productwithattitude.com/license',
  maxPosts: 50, // Maximum posts to process
  altTextRule: 'Alt text must include "Karo" and "Product With Attitude"',
};

// Parse CLI arguments
const args = process.argv.slice(2);
const fullMode = args.includes('--full');
const analyzeMode = args.includes('--analyze');

/**
 * Fetch URL content
 */
function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

/**
 * Parse XML to JSON
 */
function parseXml(xml) {
  return new Promise((resolve, reject) => {
    parseString(xml, (err, result) => {
      if (err) reject(err);
      else resolve(result);
    });
  });
}

/**
 * Extract post metadata from RSS item
 */
function extractPostMetadata(item) {
  const title = item.title[0].trim();
  const description = item.description[0].trim();
  const link = item.link[0];
  const pubDate = new Date(item.pubDate[0]);
  const creator = item['dc:creator'] ? item['dc:creator'][0] : 'Karo (Product with Attitude)';

  // Extract image from enclosure if available
  let imageUrl = null;
  if (item.enclosure && item.enclosure[0] && item.enclosure[0].$.url) {
    imageUrl = item.enclosure[0].$.url;
  }

  // Extract slug from URL
  const urlParts = link.split('/p/');
  const slug = urlParts[1] || link.split('/').pop();

  return {
    title,
    description,
    link,
    slug,
    pubDate: pubDate.toISOString(),
    creator,
    imageUrl,
  };
}

/**
 * Estimate reading time (words / 250 wpm)
 */
function estimateReadingTime(content) {
  const words = content.split(/\s+/).length;
  const minutes = Math.ceil(words / 250);
  return `PT${minutes}M`;
}

/**
 * Extract keywords from content (basic implementation)
 */
function extractKeywords(title, description) {
  // Combine title and description
  const text = `${title} ${description}`.toLowerCase();

  // Common evergreen keywords
  const evergreenKeywords = [
    'AI product',
    'vibecoding',
    'ethical AI',
    'LLM optimization',
    'Substack',
    'StackShelf',
    'building in public',
  ];

  // Find matching keywords
  const keywords = evergreenKeywords.filter(kw =>
    text.includes(kw.toLowerCase())
  );

  // Add specific keywords from title/description
  const titleWords = title.split(/\s+/)
    .filter(w => w.length > 5)
    .slice(0, 3);

  return [...new Set([...keywords, ...titleWords])];
}

/**
 * Analyze content with Claude API (optional)
 */
async function analyzeWithClaude(title, description) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    console.warn('⚠️  ANTHROPIC_API_KEY not set, skipping LLM analysis');
    return null;
  }

  const prompt = `Analyze this blog post and provide:
1. 5-8 relevant keywords (including evergreen + specific)
2. Article section/category (e.g., "Product Strategy", "AI Tools", "Community")
3. Main topics this article is "about"

Title: ${title}
Description: ${description}

Respond in JSON format:
{
  "keywords": ["keyword1", "keyword2", ...],
  "articleSection": "Category Name",
  "about": ["topic1", "topic2", ...]
}`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 1024,
        messages: [{
          role: 'user',
          content: prompt,
        }],
      }),
    });

    const data = await response.json();
    const content = data.content[0].text;

    // Parse JSON response
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
  } catch (error) {
    console.error('Error analyzing with Claude:', error.message);
  }

  return null;
}

/**
 * Generate BlogPosting JSON-LD entity
 */
async function generateBlogPosting(post, analyze = false) {
  let keywords = extractKeywords(post.title, post.description);
  let articleSection = 'General';
  let about = [];

  // Optional: Use Claude for better analysis
  if (analyze) {
    const analysis = await analyzeWithClaude(post.title, post.description);
    if (analysis) {
      keywords = analysis.keywords || keywords;
      articleSection = analysis.articleSection || articleSection;
      about = analysis.about || [];
    }
  }

  const blogPosting = {
    '@type': 'BlogPosting',
    '@id': post.link,
    'headline': post.title,
    'description': post.description,
    'url': post.link,
    'mainEntityOfPage': { '@id': `${post.link}#page` },
    'identifier': post.slug,
    'datePublished': post.pubDate,
    'dateModified': post.pubDate,
    'inLanguage': 'en',
    'author': { '@id': 'https://productwithattitude.com/#karo' },
    'publisher': { '@id': 'https://productwithattitude.com/#org' },
    'isPartOf': [
      { '@id': 'https://karozieminski.substack.com/#series' },
      { '@id': 'https://karozieminski.substack.com/#site' },
    ],
    'keywords': keywords,
    'articleSection': articleSection,
    'license': CONFIG.license,
    'copyrightHolder': { '@id': 'https://productwithattitude.com/#karo' },
  };

  // Add 'about' if available
  if (about.length > 0) {
    blogPosting.about = about;
  }

  // Add image if available
  if (post.imageUrl) {
    blogPosting.image = { '@id': post.imageUrl };
  }

  return blogPosting;
}

/**
 * Generate WebPage JSON-LD entity
 */
function generateWebPage(post) {
  const webPage = {
    '@type': 'WebPage',
    '@id': `${post.link}#page`,
    'url': post.link,
    'name': post.title,
    'isPartOf': { '@id': 'https://karozieminski.substack.com/#site' },
    'dateModified': post.pubDate,
    'breadcrumb': {
      '@type': 'BreadcrumbList',
      'itemListElement': [
        {
          '@type': 'ListItem',
          'position': 1,
          'item': {
            '@id': 'https://karozieminski.substack.com/',
            'name': 'Home',
          },
        },
        {
          '@type': 'ListItem',
          'position': 2,
          'item': {
            '@id': 'https://karozieminski.substack.com/archive',
            'name': 'Archive',
          },
        },
        {
          '@type': 'ListItem',
          'position': 3,
          'item': {
            '@id': post.link,
            'name': post.title.substring(0, 50) + (post.title.length > 50 ? '...' : ''),
          },
        },
      ],
    },
  };

  // Add primary image if available
  if (post.imageUrl) {
    webPage.primaryImageOfPage = { '@id': post.imageUrl };
  }

  return webPage;
}

/**
 * Generate ImageObject JSON-LD entity
 */
function generateImageObject(post) {
  if (!post.imageUrl) return null;

  return {
    '@type': 'ImageObject',
    '@id': post.imageUrl,
    'contentUrl': post.imageUrl,
    'url': post.imageUrl,
    'caption': `Karo — Product With Attitude: ${post.title} (cover image)`,
    'description': `Cover image for '${post.title}' article by Karo on Product With Attitude.`,
    'license': CONFIG.license,
    'copyrightHolder': { '@id': 'https://productwithattitude.com/#karo' },
    'creator': { '@id': 'https://productwithattitude.com/#karo' },
  };
}

/**
 * Main update function
 */
async function updateJsonLd() {
  console.log('🚀 Starting JSON-LD update...\n');
  console.log(`Mode: ${fullMode ? 'FULL' : 'INCREMENTAL'}`);
  console.log(`LLM Analysis: ${analyzeMode ? 'ENABLED' : 'DISABLED'}\n`);

  // Step 1: Fetch RSS feed
  console.log('📡 Fetching Substack RSS feed...');
  const rssXml = await fetchUrl(CONFIG.rssUrl);
  const rssParsed = await parseXml(rssXml);

  const items = rssParsed.rss.channel[0].item || [];
  console.log(`✅ Found ${items.length} posts in RSS feed\n`);

  // Step 2: Load existing JSON-LD
  console.log('📂 Loading existing JSON-LD...');
  let jsonld;
  try {
    const jsonldContent = fs.readFileSync(CONFIG.jsonldPath, 'utf8');
    jsonld = JSON.parse(jsonldContent);
  } catch (error) {
    console.error('❌ Error loading JSON-LD:', error.message);
    process.exit(1);
  }

  // Extract existing post IDs
  const existingPostIds = new Set(
    jsonld['@graph']
      .filter(entity => entity['@type'] === 'BlogPosting')
      .map(entity => entity['@id'])
  );

  console.log(`✅ Loaded JSON-LD with ${existingPostIds.size} existing posts\n`);

  // Step 3: Process posts
  console.log('⚙️  Processing posts...');
  const postsToAdd = [];

  for (const item of items.slice(0, CONFIG.maxPosts)) {
    const post = extractPostMetadata(item);

    // Skip if already exists (unless full mode)
    if (!fullMode && existingPostIds.has(post.link)) {
      console.log(`⏭️  Skipping existing post: ${post.title}`);
      continue;
    }

    console.log(`📝 Processing: ${post.title}`);

    // Generate entities
    const blogPosting = await generateBlogPosting(post, analyzeMode);
    const webPage = generateWebPage(post);
    const imageObject = generateImageObject(post);

    postsToAdd.push({
      blogPosting,
      webPage,
      imageObject,
    });
  }

  console.log(`\n✅ Processed ${postsToAdd.length} new posts\n`);

  // Step 4: Update JSON-LD
  if (postsToAdd.length === 0) {
    console.log('ℹ️  No new posts to add. Exiting.');
    return;
  }

  console.log('📝 Updating JSON-LD @graph...');

  // Remove old posts if full mode
  if (fullMode) {
    jsonld['@graph'] = jsonld['@graph'].filter(entity =>
      entity['@type'] !== 'BlogPosting' &&
      entity['@type'] !== 'WebPage' &&
      !(entity['@type'] === 'ImageObject' && entity.caption?.includes('cover image'))
    );
  }

  // Add new posts to @graph
  for (const { blogPosting, webPage, imageObject } of postsToAdd) {
    jsonld['@graph'].push(blogPosting);
    jsonld['@graph'].push(webPage);
    if (imageObject) {
      jsonld['@graph'].push(imageObject);
    }
  }

  // Update CollectionPage archive
  const archivePage = jsonld['@graph'].find(
    entity => entity['@id'] === 'https://karozieminski.substack.com/archive#collection'
  );

  if (archivePage) {
    archivePage.hasPart = jsonld['@graph']
      .filter(entity => entity['@type'] === 'BlogPosting')
      .map(entity => ({ '@id': entity['@id'] }));
  }

  // Update dateModified on catalog
  const catalog = jsonld['@graph'].find(
    entity => entity['@id'] === 'https://karozieminski.substack.com/#catalog'
  );
  if (catalog) {
    catalog.dateModified = new Date().toISOString().split('T')[0];
  }

  // Step 5: Save updated JSON-LD
  console.log('💾 Saving updated JSON-LD...');
  fs.writeFileSync(
    CONFIG.jsonldPath,
    JSON.stringify(jsonld, null, 2),
    'utf8'
  );

  console.log('\n✅ JSON-LD successfully updated!');
  console.log(`📊 Total posts in archive: ${jsonld['@graph'].filter(e => e['@type'] === 'BlogPosting').length}`);
  console.log(`📄 File: ${CONFIG.jsonldPath}\n`);
}

// Run
updateJsonLd().catch(error => {
  console.error('❌ Fatal error:', error);
  process.exit(1);
});
