"""
Example script demonstrating how to use the News Wire RSS parser.
"""

from rss_feed_parser import NewsWireRSSParser


def example_fetch_all():
    """Example: Fetch articles from all sources."""
    print("=" * 70)
    print("Example 1: Fetch from all sources")
    print("=" * 70)

    parser = NewsWireRSSParser()
    articles = parser.fetch_all()

    print(f"\nFetched {len(articles)} total articles")

    # Display first 3 articles
    for i, article in enumerate(articles[:3], 1):
        print(f"\nArticle {i}:")
        print(f"  Title: {article.title}")
        print(f"  Source: {article.source}")
        print(f"  Published: {article.published}")
        print(f"  Link: {article.link}")
        print(f"  Summary: {article.summary[:200]}...")

    return articles


def example_fetch_globenewswire_only():
    """Example: Fetch only from GlobeNewswire."""
    print("\n" + "=" * 70)
    print("Example 2: Fetch from GlobeNewswire only")
    print("=" * 70)

    parser = NewsWireRSSParser()
    articles = parser.fetch_globenewswire()

    print(f"\nFetched {len(articles)} articles from GlobeNewswire")

    return articles


def example_fetch_specific_feed():
    """Example: Fetch specific feed type."""
    print("\n" + "=" * 70)
    print("Example 3: Fetch biotechnology feeds only")
    print("=" * 70)

    parser = NewsWireRSSParser()

    # Fetch biotechnology from GlobeNewswire
    gn_articles = parser.fetch_globenewswire(feed_type="biotechnology")

    # Fetch biotechnology from PR Newswire
    prn_articles = parser.fetch_prnewswire(feed_type="biotechnology")

    total = len(gn_articles) + len(prn_articles)
    print(f"\nFetched {total} biotechnology articles")
    print(f"  GlobeNewswire: {len(gn_articles)}")
    print(f"  PR Newswire: {len(prn_articles)}")

    return gn_articles + prn_articles


def example_save_to_json():
    """Example: Save articles to JSON file."""
    print("\n" + "=" * 70)
    print("Example 4: Save articles to JSON")
    print("=" * 70)

    parser = NewsWireRSSParser()
    articles = parser.fetch_globenewswire(feed_type="clinical_study")

    output_file = "clinical_study_news.json"
    parser.save_to_json(articles, output_file)

    print(f"\nSaved to {output_file}")

    return articles


def example_filter_by_keyword():
    """Example: Filter articles by keyword."""
    print("\n" + "=" * 70)
    print("Example 5: Filter articles by keyword")
    print("=" * 70)

    parser = NewsWireRSSParser()
    articles = parser.fetch_all()

    # Filter for articles containing specific keywords
    keywords = ["FDA", "approval", "clinical trial", "phase 3"]

    filtered = []
    for article in articles:
        text = f"{article.title} {article.summary}".lower()
        if any(keyword.lower() in text for keyword in keywords):
            filtered.append(article)

    print(f"\nFound {len(filtered)} articles matching keywords: {', '.join(keywords)}")

    for i, article in enumerate(filtered[:5], 1):
        print(f"\n{i}. {article.title}")
        print(f"   Source: {article.source}")
        print(f"   Link: {article.link}")

    return filtered


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("News Wire RSS Parser - Examples")
    print("=" * 70)

    try:
        # Run examples
        example_fetch_all()
        example_fetch_globenewswire_only()
        example_fetch_specific_feed()
        example_save_to_json()
        example_filter_by_keyword()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
