from duckduckgo_search import DDGS


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Busca en internet usando DuckDuckGo."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return [{"title": r["title"], "snippet": r["body"], "url": r["href"]} for r in results]


def format_results(results: list[dict]) -> str:
    if not results:
        return "No se encontraron resultados."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   {r['url']}")
    return "\n\n".join(lines)
