from bs4 import BeautifulSoup
from unidecode import unidecode
import re


def normalize(text: str) -> str:
    if not text:
        return ""
    text = unidecode(text.lower())
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return text.strip()


def extract_keywords(task: str) -> list[str]:
    task = normalize(task)
    stopwords = {"preencher", "campo", "digitar", "informar", "com", "valor", "o", "a", "do"}
    return [word for word in task.split() if word not in stopwords]


def get_label_map(soup: BeautifulSoup) -> dict:
    labels = {}
    for label in soup.find_all("label"):
        label_text = normalize(label.get_text())
        target_id = label.get("for")
        if target_id:
            labels[target_id] = label_text
    return labels


def score_element(element, labels, keywords) -> int:
    score = 0

    attributes = {
        "id": element.get("id"),
        "name": element.get("name"),
        "placeholder": element.get("placeholder"),
        "aria-label": element.get("aria-label"),
    }

    for attr, value in attributes.items():
        normalized = normalize(value)
        for kw in keywords:
            if kw in normalized:
                if attr == "id":
                    score += 5
                elif attr == "name":
                    score += 4
                elif attr == "aria-label":
                    score += 4
                elif attr == "placeholder":
                    score += 3

    element_id = element.get("id")
    if element_id and element_id in labels:
        for kw in keywords:
            if kw in labels[element_id]:
                score += 6

    return score


def build_css_selector(element) -> str:
    if element.get("id"):
        return f"#{element['id']}"
    if element.get("name"):
        return f"{element.name}[name='{element['name']}']"
    if element.get("aria-label"):
        return f"{element.name}[aria-label='{element['aria-label']}']"
    return element.name


def find_css_selector(html: str, task: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    labels = get_label_map(soup)
    keywords = extract_keywords(task)

    candidates = soup.find_all(["input", "textarea", "select", "button"])

    scored = []
    for el in candidates:
        score = score_element(el, labels, keywords)
        if score > 0:
            scored.append((score, el))

    if not scored:
        raise ValueError("Nenhum elemento compatível encontrado")

    scored.sort(key=lambda x: x[0], reverse=True)
    best_element = scored[0][1]

    return build_css_selector(best_element)
