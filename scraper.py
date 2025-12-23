import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

USER_AGENT = "Mozilla/5.0 (compatible; n8n-ai-scraper/1.0; +https://n8n.io)"


def fetch_html(url: str, timeout: int = 15) -> str:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.encoding or response.apparent_encoding
    return response.text


def clean_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()
    return soup


def normalize_text(node: Tag) -> str:
    text = node.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def pick_best_node(soup: BeautifulSoup) -> Optional[Tag]:
    selectors = [
        "article",
        "main",
        "[role=main]",
        "div[itemprop=articleBody]",
    ]
    for selector in selectors:
        candidate = soup.select_one(selector)
        if candidate:
            return candidate

    candidates = [
        *soup.find_all("article"),
        *soup.find_all("main"),
        *soup.find_all("section"),
        *soup.find_all("div"),
    ]
    scored = []
    for candidate in candidates:
        text = normalize_text(candidate)
        if len(text) < 200:
            continue
        scored.append((len(text), candidate))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    return soup.body or soup


def extract_content(html: str, url: str, selector: Optional[str] = None) -> dict:
    soup = clean_soup(html)

    node: Optional[Tag]
    if selector:
        node = soup.select_one(selector)
    else:
        node = pick_best_node(soup)

    text_content = normalize_text(node) if node else ""
    title = (soup.title.string or "").strip() if soup.title else ""

    return {
        "url": url,
        "title": title,
        "text": text_content,
        "length": len(text_content),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape textual content from a web page and emit JSON for n8n AI agents.",
    )
    parser.add_argument("url", help="Target URL to scrape")
    parser.add_argument(
        "--selector",
        help="Optional CSS selector for the main content (overrides automatic detection)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        html = fetch_html(args.url)
        content = extract_content(html, args.url, selector=args.selector)
        json.dump(content, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    except requests.RequestException as exc:
        print(json.dumps({"error": str(exc), "url": args.url}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
