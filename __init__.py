def resolve_css_selector(**kwargs):
    import re
    from dataclasses import dataclass
    from typing import List, Optional, Tuple, Dict, Any

    from bs4 import BeautifulSoup, Tag

    # ----------------------------
    # Entradas no padrão da plataforma
    # ----------------------------
    # Seguindo seu exemplo: input_path vem do kwargs.get("input_path")
    input_path = kwargs.get("input_path")
    task_text = kwargs.get("TASK") or kwargs.get("task")

    if not input_path or not task_text:
        return {"error": "Parâmetros obrigatórios ausentes: input_path e TASK (ou task)."}

    try:
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    except Exception as e:
        return {"error": f"Falha ao ler arquivo HTML em input_path: {str(e)}"}

    # ----------------------------
    # Utilidades de normalização
    # ----------------------------
    def norm(s: str) -> str:
        s = s or ""
        s = s.strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s

    def visible_text(el: Tag) -> str:
        return norm(el.get_text(" ", strip=True))

    def safe_css_ident(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9\-_:.]*", value or ""))

    def css_attr_equals(attr: str, value: str) -> str:
        v = (value or "").replace('"', '\\"')
        return f'[{attr}="{v}"]'

    # ----------------------------
    # Modelo de Task
    # ----------------------------
    @dataclass
    class Task:
        action: str               # "click" | "fill"
        target_kind: str          # "button" | "field"
        target_name: str          # "acessar" | "senha" | etc
        fill_value: Optional[str] = None

    TASK_CLICK_PATTERNS = [
        re.compile(r"^\s*(?:eu\s*)?(?:clico|clique|clicar|pressiono|aperte)\s+(?:no|na|em)\s+(?:bot[aã]o|link)\s+(.+?)\s*$", re.I),
        re.compile(r"^\s*(?:eu\s*)?(?:clico|clique|clicar|pressiono|aperte)\s+(?:no|na|em)\s+(.+?)\s*$", re.I),
    ]

    TASK_FILL_PATTERNS = [
        re.compile(r"^\s*(?:eu\s*)?(?:preencho|preencha|digito|insiro|informo|coloco)\s+(?:o|a)\s+(?:campo|input|caixa|textarea)\s+(.+?)\s+(?:com|=)\s*(?:o\s*valor\s*)?(.+?)\s*$", re.I),
        re.compile(r"^\s*(?:eu\s*)?(?:preencho|preencha|digito|insiro|informo|coloco)\s+(.+?)\s+(?:com|=)\s*(.+?)\s*$", re.I),
    ]

    def parse_task(text: str) -> Task:
        t = text.strip()

        for pat in TASK_FILL_PATTERNS:
            m = pat.match(t)
            if m:
                field = norm(m.group(1))
                val = m.group(2).strip()
                return Task(action="fill", target_kind="field", target_name=field, fill_value=val)

        for pat in TASK_CLICK_PATTERNS:
            m = pat.match(t)
            if m:
                name = norm(m.group(1))
                return Task(action="click", target_kind="button", target_name=name)

        raise ValueError(
            "Não consegui entender a task. Exemplos aceitos: "
            '"Clico no botão Acessar", "Preencho o campo senha com o valor XPTO".'
        )

    # ----------------------------
    # Busca de candidatos (determinística)
    # ----------------------------
    CLICKABLE_INPUT_TYPES = {"button", "submit", "reset", "image"}
    FIELD_TAGS = {"input", "textarea", "select"}
    FIELD_INVALID_TYPES = {"hidden", "submit", "button", "reset", "image", "file"}

    def element_is_clickable(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        tag = (el.name or "").lower()
        if tag == "button":
            return True
        if tag == "a":
            return bool(el.get("href")) or norm(el.get("role")) == "button"
        if tag == "input":
            t = norm(el.get("type") or "text")
            return t in CLICKABLE_INPUT_TYPES
        if norm(el.get("role")) == "button":
            return True
        return False

    def element_is_field(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        tag = (el.name or "").lower()
        if tag not in FIELD_TAGS:
            return False
        if tag == "input":
            t = norm(el.get("type") or "text")
            if t in FIELD_INVALID_TYPES:
                return False
        return True

    def label_text_for_field(soup: BeautifulSoup, field: Tag) -> List[str]:
        texts = []
        fid = field.get("id")
        if fid:
            for lab in soup.find_all("label", attrs={"for": fid}):
                lt = visible_text(lab)
                if lt:
                    texts.append(lt)

        parent = field.parent
        while parent and isinstance(parent, Tag):
            if (parent.name or "").lower() == "label":
                lt = visible_text(parent)
                if lt:
                    texts.append(lt)
                break
            parent = parent.parent

        return list(dict.fromkeys(texts))

    def candidate_score_click(el: Tag, target: str) -> int:
        target_n = norm(target)
        score = 0

        txt = visible_text(el)
        if txt == target_n:
            score += 100
        elif target_n and target_n in txt:
            score += 60

        for attr, w_exact, w_sub in [
            ("aria-label", 90, 50),
            ("title", 70, 40),
            ("value", 80, 45),
            ("name", 25, 10),
            ("id", 20, 8),
        ]:
            v = norm(el.get(attr) or "")
            if not v:
                continue
            if v == target_n:
                score += w_exact
            elif target_n and target_n in v:
                score += w_sub

        if norm(el.get("role")) == "button" and target_n and (target_n in txt):
            score += 10

        return score

    def candidate_score_field(soup: BeautifulSoup, el: Tag, target: str) -> int:
        target_n = norm(target)
        score = 0

        for attr, w_exact, w_sub in [
            ("placeholder", 95, 55),
            ("aria-label", 95, 55),
            ("name", 80, 40),
            ("id", 70, 35),
            ("autocomplete", 20, 8),
        ]:
            v = norm(el.get(attr) or "")
            if not v:
                continue
            if v == target_n:
                score += w_exact
            elif target_n and target_n in v:
                score += w_sub

        for lt in label_text_for_field(soup, el):
            if lt == target_n:
                score += 120
            elif target_n and target_n in lt:
                score += 70

        return score

    def find_candidates(soup: BeautifulSoup, task: Task) -> List[Tuple[Tag, int, Dict[str, Any]]]:
        candidates = []
        target = task.target_name

        if task.action == "click":
            for el in soup.find_all(True):
                if not element_is_clickable(el):
                    continue
                sc = candidate_score_click(el, target)
                if sc > 0:
                    candidates.append((el, sc, {"match": "click"}))

        elif task.action == "fill":
            for el in soup.find_all(FIELD_TAGS):
                if not element_is_field(el):
                    continue
                sc = candidate_score_field(soup, el, target)
                if sc > 0:
                    candidates.append((el, sc, {"match": "fill"}))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    # ----------------------------
    # Geração de CSS selector único
    # ----------------------------
    PREFERRED_TEST_ATTRS = ["data-testid", "data-test", "data-qa", "data-cy"]

    def unique_select(soup: BeautifulSoup, selector: str) -> List[Tag]:
        try:
            return soup.select(selector)
        except Exception:
            return []

    def selector_is_unique(soup: BeautifulSoup, selector: str, el: Tag) -> bool:
        matches = unique_select(soup, selector)
        return len(matches) == 1 and matches[0] is el

    def build_selector_from_attrs(soup: BeautifulSoup, el: Tag) -> Optional[str]:
        tag = el.name.lower()

        _id = el.get("id")
        if _id and safe_css_ident(_id):
            sel = f"{tag}#{_id}"
            if selector_is_unique(soup, sel, el):
                return sel
            sel = f"#{_id}"
            if selector_is_unique(soup, sel, el):
                return sel

        for a in PREFERRED_TEST_ATTRS:
            v = el.get(a)
            if v:
                sel = f"{tag}{css_attr_equals(a, v)}"
                if selector_is_unique(soup, sel, el):
                    return sel
                sel = f"{css_attr_equals(a, v)}"
                if selector_is_unique(soup, sel, el):
                    return sel

        nm = el.get("name")
        if nm:
            sel = f"{tag}{css_attr_equals('name', nm)}"
            if selector_is_unique(soup, sel, el):
                return sel

        for a in ["aria-label", "placeholder", "title", "value"]:
            v = el.get(a)
            if v:
                sel = f"{tag}{css_attr_equals(a, v)}"
                if selector_is_unique(soup, sel, el):
                    return sel

        classes = el.get("class") or []
        for c in classes:
            if safe_css_ident(c):
                sel = f"{tag}.{c}"
                if selector_is_unique(soup, sel, el):
                    return sel

        return None

    def build_structural_selector(soup: BeautifulSoup, el: Tag, max_depth: int = 6) -> Optional[str]:
        chain = []
        cur = el
        depth = 0

        while cur and isinstance(cur, Tag) and depth < max_depth:
            tag = cur.name.lower()

            anchor = build_selector_from_attrs(soup, cur)
            if anchor:
                chain.append((anchor, None))
                break

            parent = cur.parent if isinstance(cur.parent, Tag) else None
            if not parent:
                chain.append((tag, None))
                break

            siblings_same = [s for s in parent.find_all(tag, recursive=False)]
            idx = 1
            for i, s in enumerate(siblings_same, start=1):
                if s is cur:
                    idx = i
                    break
            step = f"{tag}:nth-of-type({idx})"
            chain.append((step, None))

            cur = parent
            depth += 1

        sel = " > ".join([x[0] for x in reversed(chain)])
        if selector_is_unique(soup, sel, el):
            return sel

        return None

    def build_unique_selector(soup: BeautifulSoup, el: Tag) -> Optional[str]:
        sel = build_selector_from_attrs(soup, el)
        if sel:
            return sel
        sel = build_structural_selector(soup, el)
        if sel:
            return sel
        return None

    # ----------------------------
    # Verificação de correspondência com a Task
    # ----------------------------
    def matches_task(soup: BeautifulSoup, el: Tag, task: Task) -> bool:
        if task.action == "click":
            return element_is_clickable(el)
        if task.action == "fill":
            return element_is_field(el)
        return False

    # ----------------------------
    # Resolvedor principal
    # ----------------------------
    class ResolutionError(Exception):
        pass

    def resolve_selector(html: str, task_text: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        task = parse_task(task_text)

        cands = find_candidates(soup, task)
        if not cands:
            raise ResolutionError("Nenhum candidato encontrado que corresponda ao alvo descrito na task.")

        cands = [(el, sc, meta) for (el, sc, meta) in cands if matches_task(soup, el, task)]
        if not cands:
            raise ResolutionError("Encontrei possíveis matches por texto/atributos, mas nenhum satisfaz o tipo de ação (click/fill).")

        for el, sc, meta in cands[:50]:
            sel = build_unique_selector(soup, el)
            if not sel:
                continue
            matches = unique_select(soup, sel)
            if len(matches) != 1 or matches[0] is not el:
                continue
            return sel

        raise ResolutionError("Encontrei candidatos, mas não consegui gerar um CSS selector único e estável para o elemento correto.")

    # ----------------------------
    # Execução no padrão da plataforma
    # ----------------------------
    try:
        selector = resolve_selector(html, task_text)
        return {"selector": selector}
    except Exception as e:
        return {"error": str(e)}
