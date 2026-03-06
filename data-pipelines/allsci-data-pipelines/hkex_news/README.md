# HKEX News Announcement Parser

Programmatic access to listed company announcements from HKEXnews (Hong Kong Stock Exchange).

## How It Works

The HKEXnews website at [hkexnews.hk](https://www1.hkexnews.hk/listedco/listconews/index/lci.html?lang=en) uses an internal JSON API to load announcement data. This parser taps into that endpoint to fetch structured announcement data.

### API Endpoint

```
https://www1.hkexnews.hk/ncms/json/eds/lcisehk1relsdc_{page}.json
```

- Paginated (pages 1-N)
- Returns JSON with a `newsInfoLst` array
- Each entry contains: stock code, stock name, release time, category, title, document link, file size

**Note**: This is an **undocumented** endpoint discovered from the website's network requests. It could change without notice. There is no official public API for HKEXnews listed company announcements.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### CLI

```bash
# Fetch latest 5 pages of announcements
python hkex_parser.py

# Fetch more pages
python hkex_parser.py --pages 10

# Filter by stock code(s)
python hkex_parser.py --stock-codes 00005 01177 02269

# Filter by category
python hkex_parser.py --categories "Announcements" "Financial"

# Filter by keywords in title (e.g., biotech/pharma related)
python hkex_parser.py --keywords "clinical" "trial" "FDA" "drug" "pharmaceutical"

# Custom output file
python hkex_parser.py --output my_announcements.json

# Combine filters
python hkex_parser.py --pages 10 --keywords "results" "interim" --output results.json
```

### Programmatic

```python
from hkex_parser import HKEXNewsParser

# Initialize parser
parser = HKEXNewsParser()

# Fetch 5 pages of announcements
announcements = parser.fetch_announcements(pages=5)

# Filter by stock code
filtered = parser.filter_by_stock_code(announcements, ["00005", "01177"])

# Filter by category
financial = parser.filter_by_category(announcements, ["Financial"])

# Filter by keywords (e.g., biotech/pharma)
biotech = parser.filter_by_keywords(announcements, [
    "clinical", "trial", "drug", "FDA", "pharmaceutical",
    "biotech", "oncology", "therapy", "pipeline"
])

# Access announcement data
for a in biotech:
    print(f"[{a.stock_code}] {a.stock_name}")
    print(f"  Title: {a.title}")
    print(f"  Released: {a.released_at}")
    print(f"  Category: {a.category} - {a.category_detail}")
    print(f"  Document: {a.full_link}")
    print()

# Save to JSON
parser.save_to_json(announcements, "hkex_announcements.json")
```

## JSON Response Structure

The HKEX JSON endpoint returns data in this format:

```json
{
  "newsInfoLst": [
    {
      "relTime": "11-12-2025 14:51",
      "stock": [
        { "sc": "00005", "sn": "HSBC Holdings" }
      ],
      "lTxt": "Announcements and Notices - General",
      "title": "Example Announcement Title",
      "webPath": "/listedco/listconews/sehk/2025/1211/...",
      "size": "123KB",
      "lang": "EN"
    }
  ]
}
```

## Output Format

```json
{
  "fetched_at": "2025-12-11T16:00:00.000000",
  "source": "HKEXnews",
  "total_announcements": 100,
  "announcements": [
    {
      "title": "Announcement Title",
      "stock_code": "00005",
      "stock_name": "HSBC Holdings",
      "released_at": "11-12-2025 14:51",
      "category": "Announcements and Notices",
      "category_detail": "General",
      "link": "/listedco/listconews/sehk/2025/...",
      "full_link": "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/...",
      "document_size": "123KB",
      "language": "EN",
      "all_stock_codes": [
        { "code": "00005", "name": "HSBC Holdings" }
      ]
    }
  ]
}
```

## Announcement Categories

HKEX uses a two-tier headline category system defined in [Appendix 24 of the Listing Rules](https://en-rules.hkex.com.hk/rulebook/headline-categories-1).

### Tier-1 Document Types

| Category | Description |
|----------|-------------|
| Announcements and Notices | General company announcements |
| Circulars | Circulars to shareholders |
| Financial Statements/ESG Information | Financial reports and ESG disclosures |
| Listing Documents | IPO and listing documents |
| Monthly Returns | Monthly return filings |
| Next Day Disclosure Returns | Post-trade disclosure returns |
| Debt and Structured Products | Bond and structured product filings |
| Trading Information | Trading halts, resumptions |

### Key Tier-2 Sub-Categories (within Announcements and Notices)

| Sub-Category | Relevance |
|-------------|-----------|
| Inside Information | Material non-public information disclosures |
| Final/Interim/Quarterly Results | Financial performance |
| Profit Warning | Earnings alerts |
| Connected Transaction | Related-party dealings |
| Suspension / Resumption | Trading status changes |
| Rights Issue / Placing | Capital raising |
| Change of Directors | Board changes |

Full headline categories index: [PDF](https://www2.hkexnews.hk/-/media/HKEXnews/Homepage/Listed-Company-Publications/Search-Guide/HeadlineCategoriesIndex_e.pdf)

## Finding Biotech/Pharma Companies

HKEX does not categorize announcements by industry sector in the JSON feed. To find biotech/pharma announcements:

### Option 1: Filter by Known Stock Codes

Some notable HKEX-listed biotech/pharma companies:

```python
BIOTECH_STOCK_CODES = [
    "01177",  # Sino Biopharmaceutical
    "02269",  # WuXi Biologics
    "02359",  # WuXi AppTec
    "06160",  # BeiGene
    "09926",  # Akeso
    "09995",  # RemeGen
    "02162",  # Keymed Biosciences
    "06978",  # Imeik Technology Development
    "01801",  # Innovent Biologics
    "09969",  # InnoCare Pharma
    "09688",  # Zai Lab
    "09939",  # Kintor Pharmaceutical
    "03692",  # Hansoh Pharmaceutical
]

filtered = parser.filter_by_stock_code(announcements, BIOTECH_STOCK_CODES)
```

**Finding more biotech stock codes:**
- **Chapter 18A "B" marker**: Pre-revenue biotech companies listed under Chapter 18A rules have a "B" marker in their stock name
- **Hang Seng Biotech Index**: Tracks 30 largest biotech/pharma/medtech companies on HKEX
- **CES HK Biotechnology Index**: Another index of HK-listed biotech companies
- **HKEX Biotech listing page**: [hkex.com.hk/Listing/Rules-and-Guidance/Listing-of-Biotech-Companies](https://www.hkex.com.hk/Listing/Rules-and-Guidance/Listing-of-Biotech-Companies?sc_lang=en)
- **Securities list Excel**: [ListOfSecurities.xlsx](https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx)

### Option 2: Filter by Keywords

```python
biotech_keywords = [
    "clinical", "trial", "FDA", "drug", "pharmaceutical",
    "biotech", "oncology", "therapy", "pipeline", "Phase",
    "biologic", "vaccine", "antibody", "protein",
]

filtered = parser.filter_by_keywords(announcements, biotech_keywords)
```

## Alternative Access Methods

### 1. HKEX Issuer Information Feed Service (IIS)
- Official real-time feed for company announcements
- **Paid institutional service** requiring subscription
- [More info](https://www.hkex.com.hk/Services/Market-Data-Services/Infrastructure/Issuer-Information-feed-Service-(IIS)?sc_lang=en)

### 2. HKEX RSS Feeds
- Available at [hkex.com.hk/Services/RSS-Feeds](https://www.hkex.com.hk/Services/RSS-Feeds?sc_lang=en)
- Covers HKEX's own news releases (not listed company announcements)

### 3. Title Search
- Web-based search at [hkexnews.hk/search/titlesearch.xhtml](https://www1.hkexnews.hk/search/titlesearch.xhtml)
- Supports filtering by stock code, date range, and document type

### 4. HKEX Data Marketplace
- Paid historical data products at [data.hkex.com.hk/catalog](https://data.hkex.com.hk/catalog)
- Includes a [Programmatic Download API](https://www.hkex.com.hk/-/media/HKEX-Market/Global/Exchange/FAQ/Market-Data/Getting-Market-Data/Historical-Data/Programmatic-Download-API-Interface-Specification-v1,-d-,0.pdf) (for market data, not announcements)

### 5. Third-Party Data Vendors
- **LSEG (Refinitiv)**: Redistributes HKEX IIS feed; real-time streaming
- **FactSet Global Filings API**: Includes HKEX filings
- **AASTOCKS**: Free web aggregator at [aastocks.com/en/lci/listconews.aspx](https://www.aastocks.com/en/lci/listconews.aspx)
- **Twelve Data**: Commercial API with HKEX data

## Important Notes

- **Undocumented API**: The JSON endpoint is not officially supported and may change
- **Copyright**: HKEX materials are copyrighted. Review their [terms of use](https://www.hkexnews.hk/)
- **Rate limiting**: Be respectful with request frequency. Add delays between pages
- **Date format**: Release times are in DD-MM-YYYY HH:mm format (not ISO 8601)
- **Document links**: Full documents are typically PDFs hosted on HKEXnews

## References

- [HKEXnews Listed Company Information](https://www1.hkexnews.hk/listedco/listconews/index/lci.html?lang=en)
- [HKEX RSS Feeds](https://www.hkex.com.hk/Services/RSS-Feeds?sc_lang=en)
- [HKEX IIS Service](https://www.hkex.com.hk/Services/Market-Data-Services/Infrastructure/Issuer-Information-feed-Service-(IIS)?sc_lang=en)
- [twhtanghk/hkex](https://github.com/twhtanghk/hkex) - Reference implementation
