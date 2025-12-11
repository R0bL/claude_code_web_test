"""
Standalone script to fetch full content from a single news article URL.
"""

from rss_feed_parser import NewsWireRSSParser
import json
import sys


def fetch_article(url: str) -> dict:
    """
    Fetch full content from a single article URL.

    Args:
        url: Article URL

    Returns:
        Dictionary with article content and metadata
    """
    parser = NewsWireRSSParser()

    print(f"Fetching article from: {url}")
    print("-" * 70)

    content_data = parser.fetch_article_content(url)

    if not content_data:
        print("Failed to fetch article content")
        return None

    return content_data


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python fetch_single_article.py <article_url>")
        print("\nExample:")
        print("  python fetch_single_article.py https://www.globenewswire.com/news-release/2025/12/11/3203862/0/en/ViroMissile-Announces-First-in-Human-Phase-I-Trial-of-IDOV-Immune-for-Advanced-Solid-Tumors.html")
        sys.exit(1)

    url = sys.argv[1]

    # Fetch article
    content_data = fetch_article(url)

    if content_data:
        # Print results
        print("\n" + "=" * 70)
        print("FULL CONTENT:")
        print("=" * 70)
        print(content_data.get("full_content", "No content found"))

        print("\n" + "=" * 70)
        print("METADATA:")
        print("=" * 70)
        metadata = content_data.get("metadata", {})
        for key, value in metadata.items():
            print(f"{key}: {value}")

        # Save to JSON
        output_file = "article_content.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Content saved to {output_file}")
        print(f"✓ Full content length: {len(content_data.get('full_content', ''))} characters")
        print(f"✓ HTML content length: {len(content_data.get('content_html', ''))} characters")


if __name__ == "__main__":
    main()
