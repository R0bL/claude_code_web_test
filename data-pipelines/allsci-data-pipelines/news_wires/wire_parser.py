"""
News Wire Services Parser
Fetches press releases from Business Wire, PR Newswire, and GlobeNewswire RSS feeds.

Supported Services:
- Business Wire (RSS)
- PR Newswire (RSS)
- GlobeNewswire (RSS)

Focus: Biotech, pharmaceutical, and life sciences press releases.
"""

import requests
import feedparser
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urlencode


# Business Wire RSS feed URLs (industry-specific)
# Note: Business Wire has 403 protection on direct scraping, but RSS feeds are available
BUSINESS_WIRE_FEEDS = {
    "biotechnology": "https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001106",
    "pharmaceutical": "https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001107",
    "health": "https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001014",
    "fda": "https://www.businesswire.com/portal/site/home/template.PAGE/news/rss/?ndmConfigId=1001348",
}

# PR Newswire RSS feeds (more accessible)
PR_NEWSWIRE_FEEDS = {
    "biotechnology": "https://www.prnewswire.com/rss/health-latest-news/biotechnology-list.rss",
    "pharmaceutical": "https://www.prnewswire.com/rss/health-latest-news/pharmaceuticals-list.rss",
    "health": "https://www.prnewswire.com/rss/health-latest-news/health-care-latest-news-list.rss",
    "medical_devices": "https://www.prnewswire.com/rss/health-latest-news/medical-devices-list.rss",
}

# GlobeNewswire RSS feeds
GLOBE_NEWSWIRE_FEEDS = {
    "healthcare": "https://www.globenewswire.com/RssFeed/industry/Healthcare/feedTitle/GlobeNewswire%20-%20Healthcare",
    "biotech": "https://www.globenewswire.com/RssFeed/keyword/biotech/feedTitle/GlobeNewswire%20-%20Biotech",
    "clinical_trial": "https://www.globenewswire.com/RssFeed/keyword/clinical%20trial/feedTitle/GlobeNewswire%20-%20Clinical%20Trial",
}


@dataclass
class PressRelease:
    """Data class for a press release from any wire service."""
    title: str
    link: str
    published_at: str
    summary: str
    source: str  # "BusinessWire", "PRNewswire", "GlobeNewswire"
    category: str  # "biotechnology", "pharmaceutical", etc.
    company: str = ""

    # Optional fields
    guid: str = ""
    tags: List[str] = None
    raw_entry: Dict[str, Any] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = asdict(self)
        # Remove raw_entry from output to keep it clean
        d.pop("raw_entry", None)
        return d


class WireServiceParser:
    """
    Parser for multiple news wire services via RSS feeds.

    Supports:
    - Business Wire (RSS only - direct scraping blocked)
    - PR Newswire (RSS - most accessible)
    - GlobeNewswire (RSS - good alternative)
    """

    def __init__(self, user_agent: str = "WireServiceParser/1.0 (RSS Reader)"):
        """
        Initialize the parser.

        Args:
            user_agent: User agent string for HTTP requests
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml",
        })

    def fetch_feed(self, url: str, max_retries: int = 3) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse an RSS feed.

        Args:
            url: RSS feed URL
            max_retries: Maximum retry attempts

        Returns:
            Parsed feed dictionary or None on failure
        """
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # Parse RSS feed
                feed = feedparser.parse(response.content)

                if feed.bozo:
                    print(f"Warning: Feed parsing issue at {url}: {feed.bozo_exception}")

                return feed

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"Failed to fetch feed: {url}")
                    return None

        return None

    def parse_feed_entries(
        self,
        feed: feedparser.FeedParserDict,
        source: str,
        category: str
    ) -> List[PressRelease]:
        """
        Parse feed entries into PressRelease objects.

        Args:
            feed: Parsed feed dictionary
            source: Wire service name ("BusinessWire", "PRNewswire", "GlobeNewswire")
            category: Category/industry tag

        Returns:
            List of PressRelease objects
        """
        releases = []

        for entry in feed.entries:
            # Extract basic fields
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", entry.get("description", ""))

            # Parse published date
            published_at = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
            elif hasattr(entry, "published"):
                published_at = entry.published

            # Extract GUID
            guid = entry.get("id", entry.get("guid", ""))

            # Extract tags/categories
            tags = []
            if hasattr(entry, "tags"):
                tags = [tag.term for tag in entry.tags if hasattr(tag, "term")]

            # Try to extract company name from title (first part before dash or pipe)
            company = ""
            if " - " in title:
                company = title.split(" - ")[0].strip()
            elif " | " in title:
                company = title.split(" | ")[0].strip()
            elif ":" in title:
                parts = title.split(":", 1)
                if len(parts[0]) < 50:  # Likely a company name
                    company = parts[0].strip()

            release = PressRelease(
                title=title,
                link=link,
                published_at=published_at,
                summary=summary,
                source=source,
                category=category,
                company=company,
                guid=guid,
                tags=tags,
                raw_entry=dict(entry),
            )
            releases.append(release)

        return releases

    def fetch_business_wire(self, categories: List[str] = None) -> List[PressRelease]:
        """
        Fetch press releases from Business Wire RSS feeds.

        Args:
            categories: List of categories to fetch (defaults to all biotech/pharma)

        Returns:
            List of PressRelease objects
        """
        if categories is None:
            categories = ["biotechnology", "pharmaceutical", "fda"]

        all_releases = []

        for category in categories:
            if category not in BUSINESS_WIRE_FEEDS:
                print(f"Warning: Unknown Business Wire category '{category}'")
                continue

            url = BUSINESS_WIRE_FEEDS[category]
            print(f"Fetching Business Wire {category}...")

            feed = self.fetch_feed(url)
            if feed:
                releases = self.parse_feed_entries(feed, "BusinessWire", category)
                all_releases.extend(releases)
                print(f"  Found {len(releases)} press releases")

        return all_releases

    def fetch_pr_newswire(self, categories: List[str] = None) -> List[PressRelease]:
        """
        Fetch press releases from PR Newswire RSS feeds.

        Args:
            categories: List of categories to fetch (defaults to all biotech/pharma)

        Returns:
            List of PressRelease objects
        """
        if categories is None:
            categories = ["biotechnology", "pharmaceutical"]

        all_releases = []

        for category in categories:
            if category not in PR_NEWSWIRE_FEEDS:
                print(f"Warning: Unknown PR Newswire category '{category}'")
                continue

            url = PR_NEWSWIRE_FEEDS[category]
            print(f"Fetching PR Newswire {category}...")

            feed = self.fetch_feed(url)
            if feed:
                releases = self.parse_feed_entries(feed, "PRNewswire", category)
                all_releases.extend(releases)
                print(f"  Found {len(releases)} press releases")

        return all_releases

    def fetch_globe_newswire(self, categories: List[str] = None) -> List[PressRelease]:
        """
        Fetch press releases from GlobeNewswire RSS feeds.

        Args:
            categories: List of categories to fetch (defaults to healthcare/biotech)

        Returns:
            List of PressRelease objects
        """
        if categories is None:
            categories = ["healthcare", "biotech"]

        all_releases = []

        for category in categories:
            if category not in GLOBE_NEWSWIRE_FEEDS:
                print(f"Warning: Unknown GlobeNewswire category '{category}'")
                continue

            url = GLOBE_NEWSWIRE_FEEDS[category]
            print(f"Fetching GlobeNewswire {category}...")

            feed = self.fetch_feed(url)
            if feed:
                releases = self.parse_feed_entries(feed, "GlobeNewswire", category)
                all_releases.extend(releases)
                print(f"  Found {len(releases)} press releases")

        return all_releases

    def fetch_all(self, services: List[str] = None) -> List[PressRelease]:
        """
        Fetch from all wire services.

        Args:
            services: List of services to fetch from (default: all)
                     Options: "businesswire", "prnewswire", "globenewswire"

        Returns:
            Combined list of PressRelease objects
        """
        if services is None:
            services = ["prnewswire", "globenewswire", "businesswire"]

        all_releases = []

        if "businesswire" in services:
            all_releases.extend(self.fetch_business_wire())

        if "prnewswire" in services:
            all_releases.extend(self.fetch_pr_newswire())

        if "globenewswire" in services:
            all_releases.extend(self.fetch_globe_newswire())

        return all_releases

    def filter_by_keywords(
        self,
        releases: List[PressRelease],
        keywords: List[str]
    ) -> List[PressRelease]:
        """
        Filter press releases by keywords in title or summary.

        Args:
            releases: List of press releases
            keywords: List of keywords to search for (case-insensitive)

        Returns:
            Filtered list of press releases
        """
        return [
            r for r in releases
            if any(
                kw.lower() in r.title.lower() or kw.lower() in r.summary.lower()
                for kw in keywords
            )
        ]

    def filter_by_company(
        self,
        releases: List[PressRelease],
        companies: List[str]
    ) -> List[PressRelease]:
        """
        Filter press releases by company name.

        Args:
            releases: List of press releases
            companies: List of company names to match (partial, case-insensitive)

        Returns:
            Filtered list of press releases
        """
        return [
            r for r in releases
            if any(comp.lower() in r.company.lower() for comp in companies)
        ]

    def save_to_json(self, releases: List[PressRelease], output_file: str):
        """
        Save press releases to JSON file.

        Args:
            releases: List of PressRelease objects
            output_file: Output file path
        """
        data = {
            "fetched_at": datetime.utcnow().isoformat(),
            "source": "WireServices",
            "total_releases": len(releases),
            "releases": [r.to_dict() for r in releases],
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(releases)} press releases to {output_file}")


def main():
    """Main function for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch press releases from wire services (Business Wire, PR Newswire, GlobeNewswire)"
    )
    parser.add_argument(
        "--services",
        nargs="+",
        default=["prnewswire", "globenewswire"],
        help="Wire services to fetch from (businesswire, prnewswire, globenewswire)"
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        help="Filter by keywords (e.g., 'clinical trial' 'FDA approval')"
    )
    parser.add_argument(
        "--companies",
        nargs="+",
        help="Filter by company names"
    )
    parser.add_argument(
        "--output",
        default="wire_releases.json",
        help="Output JSON file path (default: wire_releases.json)"
    )

    args = parser.parse_args()

    # Initialize parser
    wire_parser = WireServiceParser()

    # Fetch press releases
    print(f"Fetching from: {', '.join(args.services)}\n")
    releases = wire_parser.fetch_all(services=args.services)

    if not releases:
        print("No press releases fetched")
        return

    print(f"\nTotal fetched: {len(releases)} press releases")

    # Apply filters
    if args.keywords:
        releases = wire_parser.filter_by_keywords(releases, args.keywords)
        print(f"Filtered by keywords: {len(releases)} releases")

    if args.companies:
        releases = wire_parser.filter_by_company(releases, args.companies)
        print(f"Filtered by companies: {len(releases)} releases")

    # Save results
    if releases:
        wire_parser.save_to_json(releases, args.output)

        # Print summary
        print(f"\nSummary:")
        print(f"  Total releases: {len(releases)}")

        # By source
        from collections import Counter
        sources = Counter(r.source for r in releases)
        print(f"  By source:")
        for source, count in sources.most_common():
            print(f"    {source}: {count}")

        # Print latest
        print(f"\nLatest press releases:")
        for r in releases[:5]:
            print(f"  [{r.source}] {r.company or '(no company)'}")
            print(f"    {r.title}")
            print(f"    {r.published_at}")
            print(f"    {r.link}")
            print()
    else:
        print("No press releases matched the filters")


if __name__ == "__main__":
    main()
