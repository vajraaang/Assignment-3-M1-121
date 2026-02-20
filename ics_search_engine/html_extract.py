from bs4 import BeautifulSoup


def extract_visible_text(html: str) -> tuple[str, str]:
    if not html:
        return "", ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    important_parts = []
    if soup.title and soup.title.string:
        important_parts.append(soup.title.get_text(" ", strip=True))
    for tag in soup.find_all(["h1", "h2", "h3", "b", "strong"]):
        important_parts.append(tag.get_text(" ", strip=True))
    important_text = " ".join(p for p in important_parts if p)
    return text, important_text

