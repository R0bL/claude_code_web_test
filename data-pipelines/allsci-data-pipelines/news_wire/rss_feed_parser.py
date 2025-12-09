"""
RSS Feed Parser for News Wire Services
Fetches and parses RSS feeds from GlobeNewswire and PR Newswire for biotechnology and pharmaceutical news.
"""

import feedparser
import json
from datetime import datetime
from typing import List, Dict, Any
import requests
from dataclasses import dataclass, asdict
import time


@dataclass
class NewsArticle:
    """Data class for news article."""
    title: str
    link: str
    published: str
    summary: str
    source: str
    categories: List[str]
    author: str = ""
    guid: str = ""
    raw_data: Dict[str, Any] = None

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)


class NewsWireRSSParser:
    """Parser for news wire RSS feeds."""

    # GlobeNewswire RSS feed URLs
    GLOBENEWSWIRE_FEEDS = {
        "clinical_study": "https://www.globenewswire.com/RssFeed/subjectcode/90-Clinical%20Study/feedTitle/GlobeNewswire%20-%20Clinical%20Study",
        "biotechnology": "https://www.globenewswire.com/RssFeed/industry/1-Biotechnology/feedTitle/GlobeNewswire%20-%20Biotechnology",
        "pharmaceuticals": "https://www.globenewswire.com/RssFeed/industry/2-Pharmaceuticals/feedTitle/GlobeNewswire%20-%20Pharmaceuticals",
    }

    # PR Newswire RSS feed URLs
    # Note: PR Newswire may require visiting https://www.prnewswire.com/rss/ to get exact feed URLs
    PRNEWSWIRE_FEEDS = {
        "biotechnology": "https://www.prnewswire.com/rss/health-latest-news/biotechnology-list.rss",
        "pharmaceuticals": "https://www.prnewswire.com/rss/health-latest-news/pharmaceuticals-list.rss",
        "healthcare": "https://www.prnewswire.com/rss/health-latest-news.rss",
    }

    def __init__(self, user_agent: str = "NewsWireParser/1.0"):
        """Initialize the parser."""
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def fetch_feed(self, url: str, max_retries: int = 3) -> feedparser.FeedParserDict:
        """
        Fetch RSS feed from URL with retry logic.

        Args:
            url: RSS feed URL
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed feed data
        """
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # Parse the feed
                feed = feedparser.parse(response.content)

                if feed.bozo:
                    print(f"Warning: Feed has malformed XML (bozo=True) for {url}")
                    if feed.bozo_exception:
                        print(f"Exception: {feed.bozo_exception}")

                return feed

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

        return None

    def parse_feed_entries(self, feed: feedparser.FeedParserDict, source: str) -> List[NewsArticle]:
        """
        Parse feed entries into NewsArticle objects.

        Args:
            feed: Parsed feed data
            source: Source name (e.g., "GlobeNewswire", "PR Newswire")

        Returns:
            List of NewsArticle objects
        """
        articles = []

        for entry in feed.entries:
            # Extract published date
            published = ""
            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated

            # Extract categories/tags
            categories = []
            if hasattr(entry, "tags"):
                categories = [tag.term for tag in entry.tags if hasattr(tag, "term")]

            # Extract author
            author = ""
            if hasattr(entry, "author"):
                author = entry.author

            # Extract GUID
            guid = ""
            if hasattr(entry, "id"):
                guid = entry.id
            elif hasattr(entry, "guid"):
                guid = entry.guid

            # Create NewsArticle object
            article = NewsArticle(
                title=entry.get("title", ""),
                link=entry.get("link", ""),
                published=published,
                summary=entry.get("summary", ""),
                source=source,
                categories=categories,
                author=author,
                guid=guid,
                raw_data=dict(entry)
            )

            articles.append(article)

        return articles

    def fetch_globenewswire(self, feed_type: str = "all") -> List[NewsArticle]:
        """
        Fetch articles from GlobeNewswire RSS feeds.

        Args:
            feed_type: Type of feed to fetch ("all", "clinical_study", "biotechnology", "pharmaceuticals")

        Returns:
            List of NewsArticle objects
        """
        articles = []

        feeds_to_fetch = self.GLOBENEWSWIRE_FEEDS.items()
        if feed_type != "all" and feed_type in self.GLOBENEWSWIRE_FEEDS:
            feeds_to_fetch = [(feed_type, self.GLOBENEWSWIRE_FEEDS[feed_type])]

        for name, url in feeds_to_fetch:
            print(f"Fetching GlobeNewswire {name}...")
            try:
                feed = self.fetch_feed(url)
                if feed:
                    parsed_articles = self.parse_feed_entries(feed, f"GlobeNewswire-{name}")
                    articles.extend(parsed_articles)
                    print(f"  Found {len(parsed_articles)} articles")
            except Exception as e:
                print(f"  Error: {e}")

        return articles

    def fetch_prnewswire(self, feed_type: str = "all") -> List[NewsArticle]:
        """
        Fetch articles from PR Newswire RSS feeds.

        Args:
            feed_type: Type of feed to fetch ("all", "biotechnology", "pharmaceuticals", "healthcare")

        Returns:
            List of NewsArticle objects
        """
        articles = []

        feeds_to_fetch = self.PRNEWSWIRE_FEEDS.items()
        if feed_type != "all" and feed_type in self.PRNEWSWIRE_FEEDS:
            feeds_to_fetch = [(feed_type, self.PRNEWSWIRE_FEEDS[feed_type])]

        for name, url in feeds_to_fetch:
            print(f"Fetching PR Newswire {name}...")
            try:
                feed = self.fetch_feed(url)
                if feed:
                    parsed_articles = self.parse_feed_entries(feed, f"PRNewswire-{name}")
                    articles.extend(parsed_articles)
                    print(f"  Found {len(parsed_articles)} articles")
            except Exception as e:
                print(f"  Error: {e}")

        return articles

    def fetch_all(self, feed_type: str = "all") -> List[NewsArticle]:
        """
        Fetch articles from all news wire services.

        Args:
            feed_type: Type of feed to fetch

        Returns:
            List of NewsArticle objects from all sources
        """
        articles = []

        print("Fetching GlobeNewswire feeds...")
        articles.extend(self.fetch_globenewswire(feed_type))

        print("\nFetching PR Newswire feeds...")
        articles.extend(self.fetch_prnewswire(feed_type))

        return articles

    def save_to_json(self, articles: List[NewsArticle], output_file: str):
        """
        Save articles to JSON file.

        Args:
            articles: List of NewsArticle objects
            output_file: Output file path
        """
        data = {
            "fetched_at": datetime.utcnow().isoformat(),
            "total_articles": len(articles),
            "articles": [article.to_dict() for article in articles]
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(articles)} articles to {output_file}")


def main():
    """Main function for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch and parse RSS feeds from news wire services"
    )
    parser.add_argument(
        "--source",
        choices=["all", "globenewswire", "prnewswire"],
        default="all",
        help="News wire source to fetch from"
    )
    parser.add_argument(
        "--type",
        default="all",
        help="Feed type (e.g., biotechnology, pharmaceuticals, clinical_study)"
    )
    parser.add_argument(
        "--output",
        default="news_articles.json",
        help="Output JSON file path"
    )

    args = parser.parse_args()

    # Initialize parser
    rss_parser = NewsWireRSSParser()

    # Fetch articles based on source
    if args.source == "globenewswire":
        articles = rss_parser.fetch_globenewswire(args.type)
    elif args.source == "prnewswire":
        articles = rss_parser.fetch_prnewswire(args.type)
    else:
        articles = rss_parser.fetch_all(args.type)

    # Save to JSON
    if articles:
        rss_parser.save_to_json(articles, args.output)

        # Print summary
        print(f"\nSummary:")
        print(f"  Total articles: {len(articles)}")
        sources = {}
        for article in articles:
            sources[article.source] = sources.get(article.source, 0) + 1
        print(f"  By source:")
        for source, count in sorted(sources.items()):
            print(f"    {source}: {count}")
    else:
        print("No articles fetched")


if __name__ == "__main__":
    main()
