def transform_html(**kwargs):
    import re
    import unicodedata
    from lxml import html as lxml_html

    TASK = kwargs.get("TASK")
    HTML = kwargs.get("HTML")

    if not TASK or not HTML:
        return HTML

    # =========================
    # Helpers
    # =========================
    def norm(txt):
        txt = txt.lower().strip()
        txt = unicodedata.normalize("NFKD", txt)
        txt = "".join(c for c in txt if not unicodedata.combining(c))
        return re.sub(r"\s+", " ", txt)

    task_n = norm(TASK)

    # =========================
    # Detectar intenção
    # =========================
    intents = set()

    if re.search(r"\b(clico|clicar|pressiono|pressionar|aperte|toque)\b", task_n):
        intents.add("click")

    if re.search(r"\b(preencho|preencher|digito|digitar|insiro|escrevo)\b", task_n):
        intents.add("fill")

    if re.search(r"\b(seleciono|selecionar|escolho)\b", task_n):
        intents.add("select")

    if re.search(r"\b(marco|desmarco|habilito|desabilito|ativo|desativo)\b", task_n):
        intents.add("check")

    if not intents:
        intents.add("click")

    # =========================
    # Keywords da task
    # =========================
    keywords = re.findall(r"[a-z0-9]{2,}", task_n)

    # =========================
    # Parse HTML
    # =========================
    try:
        root = lxml_html.fromstring(HTML)
    except Exception:
        root = lxml_html.fromstring(f"<html><body>{HTML}</body></html>")

    # =========================
    # Remover ruído pesado
    # =========================
    for bad in root.xpath("//script|//style|//noscript"):
        bad.getparent().remove(bad)

    # =========================
    # Detectores de elementos
    # =========================
    def has_interaction(el):
        attrs = el.attrib or {}
        role = (attrs.get("role") or "").lower()
        if role in {
            "button","link","checkbox","radio",
            "switch","combobox","listbox"
        }:
            return True
        if "onclick" in attrs:
            return True
        if "tabindex" in attrs:
            return True
        if "aria-checked" in attrs or "aria-pressed" in attrs:
            return True
        return False

    def is_candidate(el):
        tag = el.tag.lower()
        t = (el.attrib.get("type") or "").lower()

        if "fill" in intents:
            if tag == "textarea":
                return True
            if tag == "input" and t not in {"checkbox","radio","button","submit"}:
                return True
            if el.attrib.get("contenteditable"):
                return True

        if "select" in intents:
            if tag == "select":
                return True
            if el.attrib.get("role") in {"combobox","listbox"}:
                return True

        if "check" in intents:
            if tag == "input" and t in {"checkbox","radio"}:
                return True
            if el.attrib.get("role") in {"checkbox","radio","switch"}:
                return True

        if "click" in intents:
            if tag in {"button","a","summary","label"}:
                return True
            if tag == "input" and t in {"button","submit","image"}:
                return True
            if has_interaction(el):
                return True

        return False

    def matches_keywords(el):
        hay = []
        hay.append(" ".join(el.itertext()))
        for v in el.attrib.values():
            hay.append(v)
        hay = norm(" ".join(hay))
        return any(k in hay for k in keywords)

    # =========================
    # Coletar elementos relevantes
    # =========================
    keep = set()

    for el in root.iter():
        if not isinstance(el.tag, str):
            continue

        tag = el.tag.lower()

        # Sempre preservar iframe e shadowroot
        if tag in {"iframe","frame","frameset"}:
            keep.add(el)
            continue

        if tag == "template" and any(
            k.lower().startswith("shadowroot") for k in el.attrib
        ):
            keep.add(el)
            continue

        if is_candidate(el) or matches_keywords(el):
            keep.add(el)

    # =========================
    # Preservar hierarquia DOM
    # =========================
    def keep_parents(el):
        p = el.getparent()
        while p is not None:
            keep.add(p)
            p = p.getparent()

    for el in list(keep):
        keep_parents(el)

    # =========================
    # Podar árvore
    # =========================
    def prune(node):
        for child in list(node):
            if child not in keep:
                node.remove(child)
            else:
                prune(child)

    prune(root)

    # =========================
    # Retorno final
    # =========================
    return lxml_html.tostring(root, encoding="unicode", method="html")
