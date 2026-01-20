#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import argparse
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

from bs4 import BeautifulSoup, Tag

# BeautifulSoup usa "soupsieve" internamente para CSS selectors.
# pip install beautifulsoup4 soupsieve

# ----------------------------
# Utilidades de normalização
# ----------------------------

def norm(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def visible_text(el: Tag) -> str:
    # Textos internos (inclui descendentes), normalizados
    return norm(el.get_text(" ", strip=True))

def safe_css_ident(value: str) -> bool:
    # Identificador simples pra usar como #id ou .class sem precisar escapar.
    # (Mantemos simples e seguro.)
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9\-_:.]*", value or ""))

def css_attr_equals(attr: str, value: str) -> str:
    # Usa aspas duplas e escapa apenas aspas duplas
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
    # "clico no botão acessar"
    re.compile(r"^\s*(?:eu\s*)?(?:clico|clique|clicar|pressiono|aperte)\s+(?:no|na|em)\s+(?:bot[aã]o|link)\s+(.+?)\s*$", re.I),
    # "clico em acessar"
    re.compile(r"^\s*(?:eu\s*)?(?:clico|clique|clicar|pressiono|aperte)\s+(?:no|na|em)\s+(.+?)\s*$", re.I),
]

TASK_FILL_PATTERNS = [
    # "preencho o campo senha com o valor XPTO"
    re.compile(r"^\s*(?:eu\s*)?(?:preencho|preencha|digito|insiro|informo|coloco)\s+(?:o|a)\s+(?:campo|input|caixa|textarea)\s+(.+?)\s+(?:com|=)\s*(?:o\s*valor\s*)?(.+?)\s*$", re.I),
    # "preencho senha com XPTO"
    re.compile(r"^\s*(?:eu\s*)?(?:preencho|preencha|digito|insiro|informo|coloco)\s+(.+?)\s+(?:com|=)\s*(.+?)\s*$", re.I),
]

def parse_task(task_text: str) -> Task:
    t = task_text.strip()

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
            # Heurística: se o usuário escreveu "botão X" ou "link X" no texto, já estamos ok.
            return Task(action="click", target_kind="button", target_name=name)

    raise ValueError(
        "Não consegui entender a task. Exemplos aceitos: "
        '"Clico no botão Acessar", "Preencho o campo senha com o valor XPTO".'
    )

# ----------------------------
# Busca de candidatos (determinística)
# ----------------------------

CLICKABLE_TAGS = {"button", "a", "input"}
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
        # link clicável: href ou role=button costuma indicar
        return bool(el.get("href")) or norm(el.get("role")) == "button"
    if tag == "input":
        t = norm(el.get("type") or "text")
        return t in CLICKABLE_INPUT_TYPES
    # Qualquer elemento com role=button também pode ser clicável
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
        # <label for="id">
        for lab in soup.find_all("label", attrs={"for": fid}):
            lt = visible_text(lab)
            if lt:
                texts.append(lt)

    # label como ancestral: <label>Senha <input ...></label>
    parent = field.parent
    while parent and isinstance(parent, Tag):
        if parent.name and parent.name.lower() == "label":
            lt = visible_text(parent)
            if lt:
                texts.append(lt)
            break
        parent = parent.parent

    return list(dict.fromkeys(texts))  # unique, mantendo ordem

def candidate_score_click(el: Tag, target: str) -> int:
    target_n = norm(target)
    score = 0

    # Texto visível (botão/âncora)
    txt = visible_text(el)
    if txt == target_n:
        score += 100
    elif target_n and target_n in txt:
        score += 60

    # aria-label / title / value
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

    # role=button aumenta confiança quando texto bate
    if norm(el.get("role")) == "button" and target_n and (target_n in txt):
        score += 10

    return score

def candidate_score_field(soup: BeautifulSoup, el: Tag, target: str) -> int:
    target_n = norm(target)
    score = 0

    # placeholder / aria-label / name / id
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

    # textos de label associados
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

    # Ordena por score desc e desempate por "mais estável" (id > data-testid > name > etc)
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

    # 1) #id
    _id = el.get("id")
    if _id and safe_css_ident(_id):
        sel = f"{tag}#{_id}"
        if selector_is_unique(soup, sel, el):
            return sel
        sel = f"#{_id}"
        if selector_is_unique(soup, sel, el):
            return sel

    # 2) data-testid (e afins)
    for a in PREFERRED_TEST_ATTRS:
        v = el.get(a)
        if v:
            sel = f"{tag}{css_attr_equals(a, v)}"
            if selector_is_unique(soup, sel, el):
                return sel
            sel = f"{css_attr_equals(a, v)}"
            if selector_is_unique(soup, sel, el):
                return sel

    # 3) name
    nm = el.get("name")
    if nm:
        sel = f"{tag}{css_attr_equals('name', nm)}"
        if selector_is_unique(soup, sel, el):
            return sel

    # 4) aria-label / placeholder / title / value (dependendo do tipo)
    for a in ["aria-label", "placeholder", "title", "value"]:
        v = el.get(a)
        if v:
            sel = f"{tag}{css_attr_equals(a, v)}"
            if selector_is_unique(soup, sel, el):
                return sel

    # 5) class única (raro, mas vale tentar)
    classes = el.get("class") or []
    for c in classes:
        if safe_css_ident(c):
            sel = f"{tag}.{c}"
            if selector_is_unique(soup, sel, el):
                return sel

    return None

def build_structural_selector(soup: BeautifulSoup, el: Tag, max_depth: int = 6) -> Optional[str]:
    """
    Cria um selector com cadeia de ancestrais + :nth-of-type para garantir unicidade,
    mas tenta ancorar em um ancestral com atributo estável (id/data-testid/name...).
    """
    chain = []
    cur = el
    depth = 0

    while cur and isinstance(cur, Tag) and depth < max_depth:
        tag = cur.name.lower()

        # Se achar um ancestral "âncora" estável, paramos nele
        anchor = build_selector_from_attrs(soup, cur)
        if anchor:
            chain.append((anchor, None))
            break

        # Caso contrário, monta step com nth-of-type
        parent = cur.parent if isinstance(cur.parent, Tag) else None
        if not parent:
            chain.append((tag, None))
            break

        # índice nth-of-type entre irmãos do mesmo tag
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

    # chain está do elemento para cima; inverte e junta com " > "
    sel = " > ".join([x[0] for x in reversed(chain)])
    if selector_is_unique(soup, sel, el):
        return sel

    return None

def build_unique_selector(soup: BeautifulSoup, el: Tag) -> Optional[str]:
    # Primeiro tenta atributos estáveis
    sel = build_selector_from_attrs(soup, el)
    if sel:
        return sel

    # Depois tenta estrutural com âncoras
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

    # Filtra por realmente satisfazer o tipo de ação
    cands = [(el, sc, meta) for (el, sc, meta) in cands if matches_task(soup, el, task)]
    if not cands:
        raise ResolutionError("Encontrei possíveis matches por texto/atributos, mas nenhum satisfaz o tipo de ação (click/fill).")

    # Pega os melhores scores e tenta gerar selector único
    # Estratégia: tenta em ordem de score, mas falha se não conseguir garantir unicidade.
    for el, sc, meta in cands[:50]:
        sel = build_unique_selector(soup, el)
        if not sel:
            continue
        # Validação final: selector existe e é único
        matches = unique_select(soup, sel)
        if len(matches) != 1 or matches[0] is not el:
            continue
        return sel

    raise ResolutionError(
        "Encontrei candidatos, mas não consegui gerar um CSS selector que seja único e estável para o elemento correto."
    )

# ----------------------------
# CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser(description="Resolve um CSS selector único a partir de HTML + task.")
    ap.add_argument("--html-file", help="Caminho do arquivo HTML. Se omitido, lê do stdin.")
    ap.add_argument("--task", required=True, help='Task, ex: "Clico no botão Acessar"')
    args = ap.parse_args()

    if args.html_file:
        with open(args.html_file, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    else:
        html = sys.stdin.read()

    try:
        sel = resolve_selector(html, args.task)
        print(sel)
        return 0
    except (ValueError, ResolutionError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
