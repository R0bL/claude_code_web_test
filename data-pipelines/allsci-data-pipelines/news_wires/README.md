# News Wire Services Parser

Programmatic access to press releases from major news wire services via RSS feeds.

## Supported Services

- **Business Wire** (Berkshire Hathaway) - RSS feeds
- **PR Newswire** (Cision) - RSS feeds ✅ Most reliable
- **GlobeNewswire** (Intrado) - RSS feeds

## Why RSS Feeds?

All three services **block direct web scraping** (HTTP 403), but provide **official RSS feeds**:

✅ Legitimate and officially supported
✅ Free - no API key required
✅ Real-time updates
✅ Standardized XML format

## Quick Start

### Install Dependencies

```bash
pip install requests feedparser
```

### Basic Usage

```python
from wire_parser import WireServiceParser

# Initialize parser
parser = WireServiceParser()

# Fetch from PR Newswire (most reliable)
releases = parser.fetch_pr_newswire(categories=["biotechnology", "pharmaceutical"])

# Filter by keywords
fda_news = parser.filter_by_keywords(releases, ["fda", "approval", "clinical trial"])

# Filter by company
company_news = parser.filter_by_company(releases, ["Moderna", "BioNTech", "Pfizer"])

# Save to JSON
parser.save_to_json(fda_news, "fda_releases.json")
```

### Command Line

```bash
# Fetch from all services
python wire_parser.py --services prnewswire globenewswire businesswire

# Filter by keywords
python wire_parser.py --keywords "FDA approval" "clinical trial" "phase 3"

# Filter by companies
python wire_parser.py --companies "Moderna" "BioNTech" "Regeneron"

# Output to custom file
python wire_parser.py --output biotech_news.json
```

## RSS Feed URLs

### PR Newswire (Recommended - Most Accessible)

| Industry | URL |
|----------|-----|
| Biotechnology | https://www.prnewswire.com/rss/health-latest-news/biotechnology-list.rss |
| Pharmaceutical | https://www.prnewswire.com/rss/health-latest-news/pharmaceuticals-list.rss |
| Medical Devices | https://www.prnewswire.com/rss/health-latest-news/medical-devices-list.rss |
| Health Care | https://www.prnewswire.com/rss/health-latest-news/health-care-latest-news-list.rss |

### GlobeNewswire

| Category | URL |
|----------|-----|
| Healthcare | https://www.globenewswire.com/RssFeed/industry/Healthcare |
| Biotech | https://www.globenewswire.com/RssFeed/keyword/biotech |
| Clinical Trial | https://www.globenewswire.com/RssFeed/keyword/clinical%20trial |

### Business Wire

| Industry | URL |
|----------|-----|
| Biotechnology | https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001106 |
| Pharmaceutical | https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001107 |
| Health | https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001014 |
| FDA | https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001348 |

**Note:** Business Wire feeds may have stricter access controls. Use PR Newswire as primary source.

## Tutorial

See **`wire_services_tutorial.ipynb`** for a step-by-step walkthrough:

1. Understanding RSS feed structure
2. Fetching from multiple wire services
3. Parsing press releases
4. Filtering by keywords and companies
5. Saving results to JSON

## API Reference

### `WireServiceParser`

#### Methods

**`fetch_business_wire(categories=None)`**
- Fetch from Business Wire RSS feeds
- Returns: `List[PressRelease]`

**`fetch_pr_newswire(categories=None)`**
- Fetch from PR Newswire RSS feeds (recommended)
- Returns: `List[PressRelease]`

**`fetch_globe_newswire(categories=None)`**
- Fetch from GlobeNewswire RSS feeds
- Returns: `List[PressRelease]`

**`fetch_all(services=None)`**
- Fetch from all specified services
- Args: `services` - List of `["businesswire", "prnewswire", "globenewswire"]`
- Returns: `List[PressRelease]`

**`filter_by_keywords(releases, keywords)`**
- Filter by keywords in title or summary
- Returns: `List[PressRelease]`

**`filter_by_company(releases, companies)`**
- Filter by company name (partial match)
- Returns: `List[PressRelease]`

**`save_to_json(releases, output_file)`**
- Save releases to JSON file

### `PressRelease` Data Class

```python
@dataclass
class PressRelease:
    title: str              # Headline
    link: str               # URL to full release
    published_at: str       # Publication timestamp
    summary: str            # Brief description
    source: str             # "BusinessWire", "PRNewswire", "GlobeNewswire"
    category: str           # "biotechnology", "pharmaceutical", etc.
    company: str            # Extracted company name
    guid: str               # Unique identifier
    tags: List[str]         # Category tags
```

## Use Cases

### Track FDA Approvals

```python
parser = WireServiceParser()
releases = parser.fetch_all()

fda_approvals = parser.filter_by_keywords(releases, [
    "fda approval", "fda clearance", "fda granted",
    "breakthrough therapy", "fast track", "orphan drug"
])

parser.save_to_json(fda_approvals, "fda_approvals.json")
```

### Monitor Clinical Trial Results

```python
clinical_keywords = [
    "clinical trial", "phase 1", "phase 2", "phase 3",
    "trial results", "data readout", "pivotal trial",
    "patient enrollment", "dose escalation"
]

clinical_news = parser.filter_by_keywords(releases, clinical_keywords)
```

### Track Specific Companies

```python
target_companies = [
    "BeiGene", "Moderna", "BioNTech", "Regeneron",
    "Vertex", "Gilead", "Amgen", "Biogen"
]

company_releases = parser.filter_by_company(releases, target_companies)
```

## Limitations

- **Historical data:** RSS feeds typically show last 20-100 releases only
- **Full text:** Summaries only; must follow link for complete release
- **Rate limiting:** Excessive requests may result in temporary blocks
- **Access control:** Business Wire may require special authorization
- **Duplicates:** Same release may appear in multiple feeds

## Best Practices

1. **Use PR Newswire as primary source** — most reliable and accessible
2. **Add delays between requests** — 1-2 seconds between fetches
3. **Handle 403/429 errors gracefully** — retry with exponential backoff
4. **Check for duplicates** — filter by GUID or URL
5. **Cache results** — avoid refetching same data
6. **Monitor specific keywords** — focus on relevant press releases

## Related Resources

- [PR Newswire RSS Documentation](https://www.prnewswire.com/rss/)
- [GlobeNewswire RSS Feeds](https://www.globenewswire.com/Rss/List)
- [Business Wire Feed Options](https://www.businesswire.com/help/feed-options)

## License

This parser is for educational and research purposes. Always review the terms of service for each wire service before using their RSS feeds in production.
