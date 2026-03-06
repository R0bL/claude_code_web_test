"""
HKEX News Announcement Parser
Fetches and parses listed company announcements from HKEXnews (Hong Kong Stock Exchange).

Uses the undocumented JSON API endpoint that powers the HKEXnews Listed Company Information page.
Endpoint: https://www1.hkexnews.hk/ncms/json/eds/lcisehk1relsdc_{page}.json
"""

import json
import requests
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field


HKEX_BASE_URL = "https://www1.hkexnews.hk"
HKEX_JSON_ENDPOINT = "https://www1.hkexnews.hk/ncms/json/eds/lcisehk1relsdc_{page}.json"

# Title search endpoint for filtered queries
HKEX_TITLE_SEARCH_URL = "https://www1.hkexnews.hk/search/titlesearch.xhtml"

# HKEX announcement category codes (commonly seen in lTxt field)
ANNOUNCEMENT_CATEGORIES = {
    "Announcements and Notices": "General announcements",
    "Circulars": "Circulars to shareholders",
    "Financial Statements/ESG Information": "Financial reports and ESG disclosures",
    "Listing Documents": "IPO and listing related documents",
    "Monthly Returns": "Monthly return filings",
    "Next Day Disclosure Returns": "Post-trade disclosure returns",
    "Proxy Forms": "Shareholder proxy forms",
    "Takeovers Code – Loss of Listing": "Takeover related announcements",
    "Regulatory Announcement & News": "Regulatory updates",
    "Trading Information": "Trading halts, resumptions, etc.",
}


@dataclass
class HKEXAnnouncement:
    """Data class for an HKEX listed company announcement."""
    title: str
    stock_code: str
    stock_name: str
    released_at: str
    category: str
    category_detail: str
    link: str
    document_size: str
    language: str = ""
    all_stock_codes: List[Dict[str, str]] = field(default_factory=list)
    raw_data: Dict[str, Any] = None

    @property
    def full_link(self) -> str:
        """Get the full URL for the announcement document."""
        if self.link.startswith("http"):
            return self.link
        return f"{HKEX_BASE_URL}{self.link}"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = asdict(self)
        d["full_link"] = self.full_link
        return d


class HKEXNewsParser:
    """
    Parser for HKEXnews listed company announcements.

    Uses the undocumented JSON API that powers the HKEXnews website.
    The endpoint returns paginated JSON data with announcement listings.
    """

    def __init__(self, user_agent: str = "HKEXNewsParser/1.0"):
        """
        Initialize the parser.

        Args:
            user_agent: User agent string for HTTP requests
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Referer": "https://www1.hkexnews.hk/listedco/listconews/index/lci.html?lang=en",
        })

    def fetch_page(self, page: int = 1, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Fetch a single page of announcements from the HKEX JSON endpoint.

        Args:
            page: Page number (1-indexed)
            max_retries: Maximum retry attempts

        Returns:
            JSON response dictionary or None on failure
        """
        url = HKEX_JSON_ENDPOINT.format(page=page)

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                data = response.json()
                return data

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed for page {page}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"Failed to fetch page {page}")
                    return None
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON from page {page}: {e}")
                return None

        return None

    def parse_announcements(self, data: Dict[str, Any]) -> List[HKEXAnnouncement]:
        """
        Parse the JSON response into HKEXAnnouncement objects.

        The JSON response contains a 'newsInfoLst' array with announcement entries.
        Each entry has fields like:
          - relTime: Release time (DD-MM-YYYY HH:mm format)
          - stock: Array of {sc: stock_code, sn: stock_name}
          - lTxt: Category text (e.g., "Announcements and Notices - [type]")
          - title: Announcement title
          - webPath: URL path to the document
          - size: Document file size

        Args:
            data: JSON response dictionary

        Returns:
            List of HKEXAnnouncement objects
        """
        announcements = []

        news_list = data.get("newsInfoLst", [])
        if not news_list:
            return announcements

        for item in news_list:
            # Extract stock information
            stocks = item.get("stock", [])
            stock_code = ""
            stock_name = ""
            all_stocks = []

            if stocks:
                stock_code = stocks[0].get("sc", "")
                stock_name = stocks[0].get("sn", "")
                all_stocks = [{"code": s.get("sc", ""), "name": s.get("sn", "")} for s in stocks]

            # Parse category from lTxt field (format: "Category - Detail")
            l_txt = item.get("lTxt", "")
            parts = l_txt.split(" - ", 1)
            category = parts[0].strip() if parts else ""
            category_detail = parts[1].strip() if len(parts) > 1 else ""

            # Parse release time
            rel_time = item.get("relTime", "")

            # Extract language info
            lang = item.get("lang", "")

            announcement = HKEXAnnouncement(
                title=item.get("title", ""),
                stock_code=stock_code,
                stock_name=stock_name,
                released_at=rel_time,
                category=category,
                category_detail=category_detail,
                link=item.get("webPath", ""),
                document_size=item.get("size", ""),
                language=lang,
                all_stock_codes=all_stocks,
                raw_data=item,
            )
            announcements.append(announcement)

        return announcements

    def fetch_announcements(self, pages: int = 5) -> List[HKEXAnnouncement]:
        """
        Fetch announcements from multiple pages.

        Args:
            pages: Number of pages to fetch (1-indexed)

        Returns:
            List of HKEXAnnouncement objects
        """
        all_announcements = []

        for page in range(1, pages + 1):
            print(f"Fetching HKEX announcements page {page}/{pages}...")
            data = self.fetch_page(page)
            if data:
                announcements = self.parse_announcements(data)
                all_announcements.extend(announcements)
                print(f"  Found {len(announcements)} announcements")
            else:
                print(f"  Failed to fetch page {page}, stopping.")
                break

        return all_announcements

    def filter_by_stock_code(
        self, announcements: List[HKEXAnnouncement], stock_codes: List[str]
    ) -> List[HKEXAnnouncement]:
        """
        Filter announcements by stock code(s).

        Args:
            announcements: List of announcements
            stock_codes: List of stock codes to filter by (e.g., ["00005", "01177"])

        Returns:
            Filtered list of announcements
        """
        codes_set = set(stock_codes)
        return [
            a for a in announcements
            if a.stock_code in codes_set
            or any(s["code"] in codes_set for s in a.all_stock_codes)
        ]

    def filter_by_category(
        self, announcements: List[HKEXAnnouncement], categories: List[str]
    ) -> List[HKEXAnnouncement]:
        """
        Filter announcements by category.

        Args:
            announcements: List of announcements
            categories: List of category strings to match (partial match)

        Returns:
            Filtered list of announcements
        """
        return [
            a for a in announcements
            if any(cat.lower() in a.category.lower() or cat.lower() in a.category_detail.lower()
                   for cat in categories)
        ]

    def filter_by_keywords(
        self, announcements: List[HKEXAnnouncement], keywords: List[str]
    ) -> List[HKEXAnnouncement]:
        """
        Filter announcements by keywords in title.

        Args:
            announcements: List of announcements
            keywords: List of keywords to search for (case-insensitive)

        Returns:
            Filtered list of announcements
        """
        return [
            a for a in announcements
            if any(kw.lower() in a.title.lower() for kw in keywords)
        ]

    def save_to_json(self, announcements: List[HKEXAnnouncement], output_file: str):
        """
        Save announcements to JSON file.

        Args:
            announcements: List of HKEXAnnouncement objects
            output_file: Output file path
        """
        data = {
            "fetched_at": datetime.utcnow().isoformat(),
            "source": "HKEXnews",
            "endpoint": HKEX_JSON_ENDPOINT,
            "total_announcements": len(announcements),
            "announcements": [a.to_dict() for a in announcements],
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(announcements)} announcements to {output_file}")


def main():
    """Main function for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch listed company announcements from HKEXnews"
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=5,
        help="Number of pages to fetch (default: 5)"
    )
    parser.add_argument(
        "--stock-codes",
        nargs="+",
        help="Filter by stock code(s) (e.g., 00005 01177)"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        help="Filter by category (e.g., 'Announcements' 'Financial')"
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        help="Filter by title keywords (e.g., 'clinical' 'trial' 'FDA')"
    )
    parser.add_argument(
        "--output",
        default="hkex_announcements.json",
        help="Output JSON file path (default: hkex_announcements.json)"
    )

    args = parser.parse_args()

    # Initialize parser
    hkex_parser = HKEXNewsParser()

    # Fetch announcements
    announcements = hkex_parser.fetch_announcements(pages=args.pages)

    if not announcements:
        print("No announcements fetched")
        return

    # Apply filters
    if args.stock_codes:
        announcements = hkex_parser.filter_by_stock_code(announcements, args.stock_codes)
        print(f"\nFiltered to {len(announcements)} announcements for stock codes: {', '.join(args.stock_codes)}")

    if args.categories:
        announcements = hkex_parser.filter_by_category(announcements, args.categories)
        print(f"\nFiltered to {len(announcements)} announcements for categories: {', '.join(args.categories)}")

    if args.keywords:
        announcements = hkex_parser.filter_by_keywords(announcements, args.keywords)
        print(f"\nFiltered to {len(announcements)} announcements matching keywords: {', '.join(args.keywords)}")

    # Save results
    if announcements:
        hkex_parser.save_to_json(announcements, args.output)

        # Print summary
        print(f"\nSummary:")
        print(f"  Total announcements: {len(announcements)}")

        categories = {}
        for a in announcements:
            categories[a.category] = categories.get(a.category, 0) + 1
        print(f"  By category:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")

        # Print first few
        print(f"\nLatest announcements:")
        for a in announcements[:5]:
            print(f"  [{a.stock_code}] {a.stock_name}")
            print(f"    {a.title}")
            print(f"    {a.released_at} | {a.category}")
            print(f"    {a.full_link}")
            print()
    else:
        print("No announcements matched the filters")


if __name__ == "__main__":
    main()
