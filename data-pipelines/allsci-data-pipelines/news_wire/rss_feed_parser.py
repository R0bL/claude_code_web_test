"""
RSS Feed Parser for News Wire Services
Fetches and parses RSS feeds from GlobeNewswire and PR Newswire for biotechnology and pharmaceutical news.
"""

import feedparser
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from dataclasses import dataclass, asdict, field
import time
import re
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("Warning: BeautifulSoup4 not available. Article content extraction will be disabled.")


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
    full_content: Optional[str] = None
    content_html: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
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

    def __init__(self, user_agent: str = "NewsWireParser/1.0", fetch_full_content: bool = False):
        """
        Initialize the parser.

        Args:
            user_agent: User agent string for HTTP requests
            fetch_full_content: If True, fetch full article content from HTML pages
        """
        self.user_agent = user_agent
        self.fetch_full_content = fetch_full_content
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

    def fetch_article_content(self, url: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Fetch full article content from article URL.

        Args:
            url: Article URL
            max_retries: Maximum number of retry attempts

        Returns:
            Dictionary with full_content, content_html, and metadata
        """
        if not BS4_AVAILABLE:
            return None

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')

                # Determine source and parse accordingly
                if "globenewswire.com" in url:
                    return self._parse_globenewswire_article(soup, url)
                elif "prnewswire.com" in url:
                    return self._parse_prnewswire_article(soup, url)
                else:
                    return None

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"Failed to fetch article content from {url}")
                    return None

        return None

    def _parse_globenewswire_article(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Parse GlobeNewswire article HTML.

        Args:
            soup: BeautifulSoup object
            url: Article URL

        Returns:
            Dictionary with content and metadata
        """
        result = {
            "full_content": "",
            "content_html": "",
            "metadata": {}
        }

        # Extract main article content
        # GlobeNewswire typically uses div with class 'article-body' or similar
        article_body = soup.find('div', class_='article-body')
        if not article_body:
            article_body = soup.find('div', id='article-body')
        if not article_body:
            # Try to find the main content area
            article_body = soup.find('article')

        if article_body:
            # Get HTML content
            result["content_html"] = str(article_body)

            # Get plain text content
            # Remove script and style elements
            for script in article_body(["script", "style"]):
                script.decompose()

            text = article_body.get_text(separator='\n', strip=True)
            result["full_content"] = text

        # Extract metadata
        # Company name
        company = soup.find('meta', {'property': 'og:site_name'})
        if company:
            result["metadata"]["company"] = company.get('content', '')

        # Publication date
        pub_date = soup.find('meta', {'property': 'article:published_time'})
        if pub_date:
            result["metadata"]["published_time"] = pub_date.get('content', '')

        # Author/contributor
        author = soup.find('span', class_='article-author')
        if author:
            result["metadata"]["author"] = author.get_text(strip=True)

        # Extract any contact information
        contact_section = soup.find('div', class_='contact-info')
        if contact_section:
            result["metadata"]["contact"] = contact_section.get_text(strip=True)

        return result

    def _parse_prnewswire_article(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Parse PR Newswire article HTML.

        Args:
            soup: BeautifulSoup object
            url: Article URL

        Returns:
            Dictionary with content and metadata
        """
        result = {
            "full_content": "",
            "content_html": "",
            "metadata": {}
        }

        # Extract main article content
        # PR Newswire uses different class names
        article_body = soup.find('div', class_='release-body')
        if not article_body:
            article_body = soup.find('section', class_='release')
        if not article_body:
            article_body = soup.find('article')

        if article_body:
            # Get HTML content
            result["content_html"] = str(article_body)

            # Get plain text content
            for script in article_body(["script", "style"]):
                script.decompose()

            text = article_body.get_text(separator='\n', strip=True)
            result["full_content"] = text

        # Extract metadata
        company = soup.find('meta', {'property': 'og:site_name'})
        if company:
            result["metadata"]["company"] = company.get('content', '')

        pub_date = soup.find('meta', {'property': 'article:published_time'})
        if pub_date:
            result["metadata"]["published_time"] = pub_date.get('content', '')

        # Extract dateline (location and date info)
        dateline = soup.find('p', class_='mb-no')
        if dateline:
            result["metadata"]["dateline"] = dateline.get_text(strip=True)

        return result

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

            # Optionally fetch full article content
            if self.fetch_full_content:
                article_url = entry.get("link", "")
                if article_url:
                    print(f"  Fetching content for: {article.title[:60]}...")
                    content_data = self.fetch_article_content(article_url)
                    if content_data:
                        article.full_content = content_data.get("full_content", "")
                        article.content_html = content_data.get("content_html", "")
                        article.metadata = content_data.get("metadata", {})

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
    parser.add_argument(
        "--full-content",
        action="store_true",
        help="Fetch full article content from HTML pages (requires BeautifulSoup4)"
    )

    args = parser.parse_args()

    # Check if full content fetching is requested but BeautifulSoup4 is not available
    if args.full_content and not BS4_AVAILABLE:
        print("Error: --full-content requires BeautifulSoup4. Install with: pip install beautifulsoup4")
        return

    # Initialize parser
    rss_parser = NewsWireRSSParser(fetch_full_content=args.full_content)

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
