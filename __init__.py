#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Deterministic CSS selector resolver (no AI).

Input:
  - HTML (string via file or stdin)
  - User task in PT-BR like:
      "clico no botão Acessar"
      "preencho o campo Login do usuario com o valor qapablo"
      "digito senha com XPTO"
      "seleciono o campo UF com o valor SP"
      "habilito o campo Lembrar-me"  (checkbox/switch)

Output:
  - A UNIQUE CSS selector that:
      1) exists in DOM
      2) matches exactly 1 element
      3) corresponds to the requested interaction type

If it cannot guarantee the above, it fails with ERROR.
"""

import re
import sys
import argparse
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

from bs4 import BeautifulSoup, Tag

# ----------------------------
# Normalização / utilidades
# ----------------------------

def norm(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # normaliza acentos básicos em comparações (leve)
    # (mantém simples; se quiser robusto: unidecode)
    s = s.replace("á", "a").replace("ã", "a").replace("â", "a")
    s = s.replace("é", "e").replace("ê", "e")
    s = s.replace("í", "i")
    s = s.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    s = s.replace("ú", "u")
    s = s.replace("ç", "c")
    return s

def visible_text(el: Tag) -> str:
    return norm(el.get_text(" ", strip=True))

def safe_css_ident(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9\-_:.]*", value or ""))

def css_attr_equals(attr: str, value: str) -> str:
    v = (value or "").replace('"', '\\"')
    return f'[{attr}="{v}"]'

# ----------------------------
# Modelo de task
# ----------------------------

@dataclass
class Task:
    action: str               # click | fill | select | enable
    target_name: str          # texto alvo do usuário (ex: "login do usuario")
    value: Optional[str] = None

# Aceita: clico, preencho, digito, seleciono, habilito
TASK_FILL_PATTERNS = [
    re.compile(
        r"^\s*(?:eu\s*)?(?:preencho|preencha|preenche|preencher|digito|digite|digitar)\s+"
        r"(?:o|a)?\s*(?:campo|input|caixa|textarea)?\s*"
        r"(.+?)\s+(?:com|=)\s*(?:o\s*valor\s*)?(.+?)\s*$",
        re.I,
    ),
]

TASK_CLICK_PATTERNS = [
    re.compile(
        r"^\s*(?:eu\s*)?(?:clico|clique|clicar|pressiono|aperte|aperto)\s+"
        r"(?:no|na|em)\s+(?:bot[aã]o|link)?\s*(.+?)\s*$",
        re.I,
    ),
]

TASK_SELECT_PATTERNS = [
    re.compile(
        r"^\s*(?:eu\s*)?(?:seleciono|selecione|selecionar)\s+"
        r"(?:o|a)?\s*(?:campo|select|lista|combobox)?\s*"
        r"(.+?)\s+(?:com|=)\s*(?:o\s*valor\s*)?(.+?)\s*$",
        re.I,
    ),
]

TASK_ENABLE_PATTERNS = [
    re.compile(
        r"^\s*(?:eu\s*)?(?:habilito|habilite|habilitar|ativo|ative|ativar|marco|marque)\s+"
        r"(?:o|a)?\s*(?:campo|op[cç][aã]o|checkbox|caixa)?\s*"
        r"(.+?)\s*$",
        re.I,
    ),
]

def parse_task(task_text: str) -> Task:
    t = task_text.strip()

    for pat in TASK_SELECT_PATTERNS:
        m = pat.match(t)
        if m:
            return Task(action="select", target_name=norm(m.group(1)), value=m.group(2).strip())

    for pat in TASK_FILL_PATTERNS:
        m = pat.match(t)
        if m:
            return Task(action="fill", target_name=norm(m.group(1)), value=m.group(2).strip())

    for pat in TASK_CLICK_PATTERNS:
        m = pat.match(t)
        if m:
            return Task(action="click", target_name=norm(m.group(1)))

    for pat in TASK_ENABLE_PATTERNS:
        m = pat.match(t)
        if m:
            return Task(action="enable", target_name=norm(m.group(1)))

    raise ValueError(
        "Não consegui entender a task. Exemplos aceitos: "
        '"clico no botão Acessar", '
        '"preencho o campo Login do usuario com o valor qapablo", '
        '"digito senha com XPTO", '
        '"seleciono o campo UF com o valor SP", '
        '"habilito o campo Lembrar-me".'
    )

# ----------------------------
# Tipos de elementos
# ----------------------------

FIELD_TAGS = {"input", "textarea", "select"}
FIELD_INVALID_TYPES = {"hidden", "submit", "button", "reset", "image", "file"}

CLICKABLE_TAGS = {"button", "a", "input"}
CLICKABLE_INPUT_TYPES = {"button", "submit", "reset", "image"}

def element_is_clickable(el: Tag) -> bool:
    if not isinstance(el, Tag) or not el.name:
        return False
    tag = el.name.lower()
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
    if not isinstance(el, Tag) or not el.name:
        return False
    tag = el.name.lower()
    if tag not in FIELD_TAGS:
        return False
    if tag == "input":
        t = norm(el.get("type") or "text")
        if t in FIELD_INVALID_TYPES:
            return False
    return True

def element_is_select(el: Tag) -> bool:
    if not isinstance(el, Tag) or not el.name:
        return False
    if el.name.lower() == "select":
        return True
    # Alguns combos customizados: role="combobox"
    if norm(el.get("role")) in {"combobox", "listbox"}:
        return True
    return False

def element_is_enable_target(el: Tag) -> bool:
    # checkbox/switch: input type=checkbox, ou role=switch/checkbox
    if not isinstance(el, Tag) or not el.name:
        return False
    tag = el.name.lower()
    if tag == "input" and norm(el.get("type") or "") == "checkbox":
        return True
    if norm(el.get("role")) in {"switch", "checkbox"}:
        return True
    return False

# ----------------------------
# Labels / hints (inclui pseudo-labels em div/span)
# ----------------------------

def label_text_for_field(soup: BeautifulSoup, field: Tag) -> List[str]:
    texts: List[str] = []

    fid = field.get("id")
    if fid:
        for lab in soup.find_all("label", attrs={"for": fid}):
            lt = visible_text(lab)
            if lt:
                texts.append(lt)

    # <label>...<input/></label>
    parent = field.parent
    while parent and isinstance(parent, Tag):
        if parent.name and parent.name.lower() == "label":
            lt = visible_text(parent)
            if lt:
                texts.append(lt)
            break
        parent = parent.parent

    return list(dict.fromkeys(texts))

def nearby_text_hints(field: Tag, max_len: int = 80) -> List[str]:
    """
    Captura textos curtos no mesmo container do input (irmãos),
    cobrindo cenários tipo:
      <div class="input-conteudo">
        <input ...>
        <div>Login do usuário</div>
      </div>
    """
    texts: List[str] = []
    parent = field.parent if isinstance(field.parent, Tag) else None
    if not parent:
        return texts

    for ch in parent.find_all(recursive=False):
        if ch is field:
            continue
        if isinstance(ch, Tag):
            t = visible_text(ch)
            if t and len(t) <= max_len:
                texts.append(t)

    return list(dict.fromkeys(texts))

# ----------------------------
# Score de candidatos
# ----------------------------

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
        ("title", 95, 55),          # <-- importante pro seu caso
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

    for lt in nearby_text_hints(el):
        if lt == target_n:
            score += 110
        elif target_n and target_n in lt:
            score += 60

    return score

def candidate_score_enable(soup: BeautifulSoup, el: Tag, target: str) -> int:
    # checkbox/switch pode ter label associado ou texto próximo
    target_n = norm(target)
    score = 0

    for attr, w_exact, w_sub in [
        ("aria-label", 95, 55),
        ("title", 80, 40),
        ("name", 60, 30),
        ("id", 50, 25),
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

    for lt in nearby_text_hints(el):
        if lt == target_n:
            score += 110
        elif target_n and target_n in lt:
            score += 60

    return score

def candidate_score_select(soup: BeautifulSoup, el: Tag, target: str) -> int:
    # select ou combobox: usa os mesmos sinais de campo
    return candidate_score_field(soup, el, target) + 5

def find_candidates(soup: BeautifulSoup, task: Task) -> List[Tuple[Tag, int, Dict[str, Any]]]:
    candidates: List[Tuple[Tag, int, Dict[str, Any]]] = []
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

    elif task.action == "select":
        # select real + combos customizados (role)
        for el in soup.find_all(True):
            if not (element_is_select(el) or (element_is_field(el) and el.name.lower() == "select")):
                continue
            sc = candidate_score_select(soup, el, target)
            if sc > 0:
                candidates.append((el, sc, {"match": "select"}))

    elif task.action == "enable":
        for el in soup.find_all(True):
            if not element_is_enable_target(el):
                continue
            sc = candidate_score_enable(soup, el, target)
            if sc > 0:
                candidates.append((el, sc, {"match": "enable"}))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates

# ----------------------------
# Geração de selector único
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

    for a in ["aria-label", "placeholder", "title", "value", "role"]:
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

def build_structural_selector(soup: BeautifulSoup, el: Tag, max_depth: int = 7) -> Optional[str]:
    """
    Selector estrutural com ancôras estáveis quando possível.
    Ex: form#loginForm > div:nth-of-type(2) > input:nth-of-type(1)
    """
    chain: List[str] = []
    cur: Optional[Tag] = el
    depth = 0

    while cur and isinstance(cur, Tag) and depth < max_depth:
        tag = cur.name.lower()

        anchor = build_selector_from_attrs(soup, cur)
        if anchor:
            chain.append(anchor)
            break

        parent = cur.parent if isinstance(cur.parent, Tag) else None
        if not parent:
            chain.append(tag)
            break

        siblings_same = [s for s in parent.find_all(tag, recursive=False)]
        idx = 1
        for i, s in enumerate(siblings_same, start=1):
            if s is cur:
                idx = i
                break

        chain.append(f"{tag}:nth-of-type({idx})")
        cur = parent
        depth += 1

    sel = " > ".join(reversed(chain))
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
# Verificação do tipo pedido
# ----------------------------

def matches_task_type(el: Tag, task: Task) -> bool:
    if task.action == "click":
        return element_is_clickable(el)
    if task.action == "fill":
        return element_is_field(el)
    if task.action == "select":
        return element_is_select(el) or (el.name and el.name.lower() == "select")
    if task.action == "enable":
        return element_is_enable_target(el)
    return False

# ----------------------------
# Resolver principal
# ----------------------------

class ResolutionError(Exception):
    pass

def resolve_selector(html: str, task_text: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    task = parse_task(task_text)

    cands = find_candidates(soup, task)
    if not cands:
        raise ResolutionError("Nenhum candidato encontrado que corresponda ao alvo descrito na task.")

    # filtra por tipo correto
    cands = [(el, sc, meta) for (el, sc, meta) in cands if matches_task_type(el, task)]
    if not cands:
        raise ResolutionError("Encontrei possíveis matches, mas nenhum satisfaz o tipo de ação (click/fill/select/enable).")

    # tenta gerar selector único nos melhores candidatos
    for el, sc, meta in cands[:80]:
        sel = build_unique_selector(soup, el)
        if not sel:
            continue
        matches = unique_select(soup, sel)
        if len(matches) == 1 and matches[0] is el:
            return sel

    raise ResolutionError("Encontrei candidatos, mas não consegui gerar um CSS selector que seja único para o elemento correto.")

# ----------------------------
# CLI
# ----------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve um CSS selector único a partir de HTML + task (PT-BR).")
    ap.add_argument("--html-file", help="Caminho do arquivo HTML. Se omitido, lê do stdin.")
    ap.add_argument("--task", required=True, help='Task, ex: "clico no botão Acessar"')
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
