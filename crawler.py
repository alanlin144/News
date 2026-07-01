"""
crawler.py
Lấy danh sách bài viết mới từ một nguồn tin (source).
Ưu tiên dùng RSS feed nếu tìm thấy (nhanh, dữ liệu sạch).
Nếu trang không có RSS, sẽ thử parse thẻ <a> trong HTML để tìm link bài viết
(phương án dự phòng, độ chính xác thấp hơn).
"""

import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

TIMEOUT = 10


def discover_feed_url(page_url: str) -> str | None:
    """Thử tìm link RSS/Atom feed khai báo trong <head> của trang."""
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for link_tag in soup.find_all("link"):
            rel = link_tag.get("rel") or []
            type_ = link_tag.get("type", "")
            if ("alternate" in rel and
                    ("rss" in type_ or "atom" in type_)):
                href = link_tag.get("href")
                if href:
                    return urljoin(page_url, href)
        # Thử vài đường dẫn RSS phổ biến
        parsed = urlparse(page_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for guess in ("/rss", "/feed", "/rss.xml", "/feed.xml", "/rss/home.rss"):
            candidate = base + guess
            try:
                r = requests.head(candidate, headers=HEADERS, timeout=5)
                if r.status_code == 200:
                    return candidate
            except requests.RequestException:
                continue
    except requests.RequestException:
        pass
    return None


def fetch_from_feed(feed_url: str, max_items: int = 20):
    """Trả về danh sách dict {title, link, summary, published} từ RSS feed."""
    parsed = feedparser.parse(feed_url)
    items = []
    for entry in parsed.entries[:max_items]:
        items.append({
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", "").strip(),
            "summary": BeautifulSoup(
                entry.get("summary", entry.get("description", "")),
                "html.parser"
            ).get_text().strip()[:1000],
            "published": entry.get("published", entry.get("updated", "")),
        })
    return items


def fetch_from_html(page_url: str, max_items: int = 20):
    """Phương án dự phòng: quét link bài viết trực tiếp trên trang HTML.
    Độ chính xác thấp hơn RSS vì heuristic đơn giản (lọc theo độ dài text, domain)."""
    items = []
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        parsed_base = urlparse(page_url)
        seen_links = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text().strip()
            href = a["href"]
            if len(text) < 25:  # tiêu đề bài báo thường dài
                continue
            full_link = urljoin(page_url, href)
            link_domain = urlparse(full_link).netloc
            if link_domain != parsed_base.netloc:
                continue
            if full_link in seen_links:
                continue
            seen_links.add(full_link)
            items.append({
                "title": text,
                "link": full_link,
                "summary": "",
                "published": "",
            })
            if len(items) >= max_items:
                break
    except requests.RequestException:
        pass
    return items


def fetch_articles_for_source(source: dict, max_items: int = 20):
    """source: dict có url, feed_url (có thể None).
    Trả về (items, feed_url_used_or_none)."""
    feed_url = source.get("feed_url")
    if not feed_url:
        feed_url = discover_feed_url(source["url"])

    if feed_url:
        items = fetch_from_feed(feed_url, max_items=max_items)
        if items:
            return items, feed_url

    # Không có feed hoặc feed rỗng -> fallback HTML
    items = fetch_from_html(source["url"], max_items=max_items)
    return items, None
