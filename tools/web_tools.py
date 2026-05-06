from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

def web_search(query: str, max_results: int = 6) -> list[dict]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        out = []
        for r in results:
            out.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
        return out
    except Exception as e:
        return [{"error": str(e)}]


def fetch_page_text(url: str, max_chars: int = 6000) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; EngineeringAssistant/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"Could not fetch page: {e}"


def search_engineering_standards(topic: str) -> list[dict]:
    query = f"{topic} engineering standard calculation formula site:engineeringtoolbox.com OR site:chemengonline.com OR site:isa.org"
    return web_search(query, max_results=5)


def search_industry_examples(doc_type: str, process_type: str = "") -> list[dict]:
    query = f"{doc_type} example {process_type} oil gas chemical engineering"
    return web_search(query, max_results=5)


def format_search_results(results: list[dict]) -> str:
    if not results:
        return "No results found."
    parts = []
    for i, r in enumerate(results, 1):
        if "error" in r:
            parts.append(f"{i}. Error: {r['error']}")
            continue
        parts.append(f"{i}. {r.get('title', 'No title')}\n   {r.get('url', '')}\n   {r.get('snippet', '')}")
    return "\n\n".join(parts)