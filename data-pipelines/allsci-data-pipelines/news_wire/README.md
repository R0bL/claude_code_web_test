# News Wire RSS Feed Parser

Programmatic access to biotechnology and pharmaceutical news from GlobeNewswire and PR Newswire via RSS feeds.

## Overview

This tool provides a Python-based RSS feed parser for fetching news articles from major news wire services. It supports:

- **GlobeNewswire**: Biotechnology, Pharmaceuticals, and Clinical Study feeds
- **PR Newswire**: Health, Biotechnology, and Pharmaceutical feeds

## Features

- ✅ Fetch RSS feeds from multiple news wire services
- ✅ Parse articles into structured data format
- ✅ Export to JSON for further processing
- ✅ Retry logic with exponential backoff
- ✅ Support for filtering by feed type
- ✅ Command-line interface

## Installation

```bash
cd data-pipelines/allsci-data-pipelines/news_wire
pip install -r requirements.txt
```

## Usage

### Basic Usage

Fetch all articles from all sources:

```bash
python rss_feed_parser.py
```

### Fetch from Specific Source

```bash
# GlobeNewswire only
python rss_feed_parser.py --source globenewswire

# PR Newswire only
python rss_feed_parser.py --source prnewswire
```

### Fetch Specific Feed Type

```bash
# Biotechnology feeds only
python rss_feed_parser.py --type biotechnology

# Clinical study feeds only (GlobeNewswire)
python rss_feed_parser.py --source globenewswire --type clinical_study
```

### Custom Output File

```bash
python rss_feed_parser.py --output biotech_news.json
```

### Programmatic Usage

```python
from rss_feed_parser import NewsWireRSSParser

# Initialize parser
parser = NewsWireRSSParser()

# Fetch from all sources
articles = parser.fetch_all()

# Fetch only from GlobeNewswire
articles = parser.fetch_globenewswire()

# Fetch specific feed type
articles = parser.fetch_globenewswire(feed_type="biotechnology")

# Save to JSON
parser.save_to_json(articles, "output.json")

# Access article data
for article in articles:
    print(f"Title: {article.title}")
    print(f"Link: {article.link}")
    print(f"Published: {article.published}")
    print(f"Source: {article.source}")
    print(f"Summary: {article.summary}")
    print("---")
```

## Available RSS Feeds

### GlobeNewswire

| Feed Type | URL | Status |
|-----------|-----|--------|
| Clinical Study | [Link](https://www.globenewswire.com/RssFeed/subjectcode/90-Clinical%20Study/feedTitle/GlobeNewswire%20-%20Clinical%20Study) | ✅ Verified |
| Biotechnology | [Link](https://www.globenewswire.com/RssFeed/industry/1-Biotechnology/feedTitle/GlobeNewswire%20-%20Biotechnology) | ⚠️ Pattern-based |
| Pharmaceuticals | [Link](https://www.globenewswire.com/RssFeed/industry/2-Pharmaceuticals/feedTitle/GlobeNewswire%20-%20Pharmaceuticals) | ⚠️ Pattern-based |

**Complete feed list**: https://www.globenewswire.com/rss/list

### PR Newswire

| Feed Type | URL | Status |
|-----------|-----|--------|
| Biotechnology | https://www.prnewswire.com/rss/health-latest-news/biotechnology-list.rss | ⚠️ Pattern-based |
| Pharmaceuticals | https://www.prnewswire.com/rss/health-latest-news/pharmaceuticals-list.rss | ⚠️ Pattern-based |
| Healthcare | https://www.prnewswire.com/rss/health-latest-news.rss | ⚠️ Pattern-based |

**Complete feed list**: https://www.prnewswire.com/rss/

⚠️ **Note**: PR Newswire feed URLs follow assumed patterns and may need verification. Visit their RSS page to confirm exact URLs.

## Output Format

The parser generates JSON output with the following structure:

```json
{
  "fetched_at": "2025-12-09T18:30:00.000000",
  "total_articles": 150,
  "articles": [
    {
      "title": "Company Announces Phase 3 Clinical Trial Results",
      "link": "https://www.globenewswire.com/news-release/...",
      "published": "Mon, 09 Dec 2025 12:00:00 GMT",
      "summary": "Article summary text...",
      "source": "GlobeNewswire-clinical_study",
      "categories": ["Clinical Trial", "Biotechnology"],
      "author": "Company Name",
      "guid": "unique-article-id",
      "raw_data": { ... }
    }
  ]
}
```

## Data Model

Each article contains:

- `title`: Article headline
- `link`: Full URL to the press release
- `published`: Publication date/time
- `summary`: Article summary or description
- `source`: Source identifier (e.g., "GlobeNewswire-biotechnology")
- `categories`: List of tags/categories
- `author`: Author or company name
- `guid`: Unique article identifier
- `raw_data`: Complete raw RSS entry data

## Integration with AWS Data Pipeline

This parser can be integrated into an AWS data pipeline similar to the NIH Reporter pipeline:

### Suggested Architecture

1. **Lambda Function**: Trigger RSS feed fetching on schedule (EventBridge)
2. **S3 Storage**: Store raw JSON output in S3 (bronze layer)
3. **Glue Jobs**: Transform and enrich data (silver layer)
4. **Athena/OpenSearch**: Query and search processed articles

### Example CDK Integration

```python
# Similar to nih_reporter_stack.py
class NewsWireStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for raw feed data
        # Lambda for RSS fetching
        # EventBridge for scheduling
        # Glue for transformation
        # Athena for querying
```

## Rate Limiting & Best Practices

- RSS feeds are publicly available and free
- Implement reasonable polling intervals (e.g., every 15-30 minutes)
- Use caching to avoid redundant fetches
- Store article GUIDs to detect duplicates
- Respect robots.txt and terms of service
- Monitor for feed URL changes

## Alternative Access Methods

### Third-Party API Services

If RSS feeds are insufficient, consider:

1. **RTPR (Real-Time PR Wire API)**: https://www.rtpr.io/
   - Provides API access to PR Newswire and other wires
   - Commercial service with pricing

2. **Benzinga Press Releases API**: https://www.benzinga.com/apis/cloud-product/press-releases/
   - Includes PR Newswire content
   - Pull (API) or Push (TCP) access

### Web Scraping

- Both sites implement anti-bot measures (403 responses)
- Requires proper headers and rate limiting
- Less reliable than RSS feeds
- May violate terms of service

## Troubleshooting

### Connection Errors

```python
# The parser includes retry logic with exponential backoff
# If you encounter persistent connection issues:

parser = NewsWireRSSParser(user_agent="YourApp/1.0 (your@email.com)")
```

### Feed URL Changes

Check feed configuration:
```bash
cat feed_config.json
```

Update URLs by visiting:
- GlobeNewswire: https://www.globenewswire.com/rss/list
- PR Newswire: https://www.prnewswire.com/rss/

### Empty Results

- Verify feed URL is correct and accessible
- Check if feed has recent articles
- Ensure internet connectivity
- Review error messages in console output

## References

- [GlobeNewswire RSS Feeds](https://www.globenewswire.com/rss/list)
- [PR Newswire RSS Feeds](https://www.prnewswire.com/rss/)
- [feedparser Documentation](https://feedparser.readthedocs.io/)

## License

This parser is provided as-is for accessing publicly available RSS feeds. Ensure compliance with the terms of service of each news wire service.
