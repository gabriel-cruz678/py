import re
import unicodedata
from typing import Dict, List, Set, Tuple, Optional

try:
    from lxml import html as lxml_html
    from lxml.etree import _Element
except Exception as e:
    raise RuntimeError(
        "Este código requer lxml. Instale com: pip install lxml"
    ) from e


# -----------------------------
# Normalização / utilidades
# -----------------------------
_PT_STOPWORDS = {
    "o","a","os","as","um","uma","uns","umas",
    "de","do","da","dos","das","em","no","na","nos","nas",
    "para","pra","por","com","sem","sobre","entre","ate","até",
    "e","ou","se","que","qual","quais","como","quando","onde",
    "clico","clicar","clique","pressiono","pressionar","aperte","apertar",
    "preencho","preencher","digito","digitar","insiro","inserir","escrevo","escrever",
    "seleciono","selecionar","escolho","escolher",
    "marco","marcar","desmarco","desmarcar","habilito","habilitar","desabilito","desabilitar",
    "ativo","ativar","desativo","desativar","liga","ligar","desliga","desligar",
    "campo","botao","botão","opcao","opção","valor","no","na","do","da",
    "checkbox","radio","radian","switch",
}

def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = _strip_accents(s)
    s = re.sub(r"\s+", " ", s)
    return s

def _extract_quoted_phrases(task: str) -> List[str]:
    # captura "..." e '...'
    phrases = []
    for m in re.finditer(r"([\"'])(.+?)\1", task):
        p = m.group(2).strip()
        if p:
            phrases.append(p)
    return phrases

def _extract_keywords(task: str) -> List[str]:
    t = _norm(task)

    # Mantém números e palavras com pelo menos 2 chars
    raw = re.findall(r"[a-z0-9][a-z0-9_\-\.]{1,}", t)
    quoted = [_norm(x) for x in _extract_quoted_phrases(task)]

    # Remove stopwords e dupes, preservando ordem
    seen = set()
    out = []
    for w in raw:
        if w in _PT_STOPWORDS:
            continue
        if len(w) < 2:
            continue
        if w not in seen:
            out.append(w)
            seen.add(w)

    # Frases entre aspas são “fortes”
    for q in quoted:
        if q and q not in seen:
            out.insert(0, q)
            seen.add(q)

    return out


# -----------------------------
# Intenção / ações
# -----------------------------
_INTENT_PATTERNS = {
    "click": [
        r"\bclic(ar|o|que|ke|k|k)\b", r"\bpression(ar|o|e)\b", r"\baperte\b", r"\btoque\b",
        r"\babri(r|o)\b", r"\bentr(ar|o)\b"
    ],
    "fill": [
        r"\bpreench(er|o|a)\b", r"\bdigit(ar|o|e)\b", r"\binsir(o|a|ir)\b",
        r"\bescrev(o|a|er)\b", r"\binform(e|ar)\b"
    ],
    "select": [
        r"\bselecion(ar|o|e)\b", r"\bescolh(er|o|a)\b", r"\bmarc(ar|o)\b.*\bopcao\b",
        r"\bdefin(ir|o)\b.*\bvalor\b"
    ],
    "check": [
        r"\bmarc(ar|o|e)\b", r"\bhabilit(ar|o|e)\b", r"\bativ(ar|o|e)\b",
        r"\blig(ar|o|a)\b", r"\bcheck\b"
    ],
    "uncheck": [
        r"\bdesmarc(ar|o|e)\b", r"\bdesabilit(ar|o|e)\b", r"\bdesativ(ar|o|e)\b",
        r"\bdeslig(ar|o|a)\b", r"\buncheck\b"
    ],
}

def _detect_intents(task: str) -> Set[str]:
    t = _norm(task)
    intents = set()
    for intent, pats in _INTENT_PATTERNS.items():
        for p in pats:
            if re.search(p, t):
                intents.add(intent)
                break

    # fallback: se nada detectado, assume "click" como mais comum
    if not intents:
        intents.add("click")

    # Se task menciona "seleciono" e "preencho", mantém ambos
    return intents


# -----------------------------
# Regras de “elementos candidatos”
# -----------------------------
def _is_declarative_shadow_template(el: _Element) -> bool:
    if el.tag != "template":
        return False
    # Declarative Shadow DOM: template com shadowrootmode/shadowroot
    attrs = el.attrib or {}
    return any(k.lower() in ("shadowrootmode", "shadowroot") for k in attrs.keys())

def _has_interactive_signals(el: _Element) -> bool:
    # Sinais gerais de interatividade para “custom components”
    attrs = el.attrib or {}
    role = (attrs.get("role") or "").lower()
    if role in {"button","link","checkbox","radio","switch","combobox","listbox","menuitem","tab"}:
        return True
    if "onclick" in attrs:
        return True
    tabindex = attrs.get("tabindex")
    if tabindex is not None:
        try:
            return int(tabindex) >= 0
        except:
            return True
    # aria-pressed / aria-checked frequentemente indicam controles
    if "aria-pressed" in attrs or "aria-checked" in attrs:
        return True
    return False

def _is_click_candidate(el: _Element) -> bool:
    tag = (el.tag or "").lower()
    attrs = el.attrib or {}
    if tag in {"button","a","summary","label"}:
        return True
    if tag == "input":
        t = (attrs.get("type") or "text").lower()
        return t in {"button","submit","reset","image","checkbox","radio"}
    # elementos custom clicáveis
    if _has_interactive_signals(el):
        return True
    # elementos com href (mesmo se tag não for 'a')
    if "href" in attrs:
        return True
    return False

def _is_fill_candidate(el: _Element) -> bool:
    tag = (el.tag or "").lower()
    attrs = el.attrib or {}
    if tag == "textarea":
        return True
    if tag == "input":
        t = (attrs.get("type") or "text").lower()
        # inclui a maioria que aceita entrada
        return t in {
            "text","email","password","number","search","tel","url","date","datetime-local",
            "month","week","time","color"
        }
    # contenteditable
    ce = (attrs.get("contenteditable") or "").lower()
    if ce in {"true","", "plaintext-only"}:
        return True
    return False

def _is_select_candidate(el: _Element) -> bool:
    tag = (el.tag or "").lower()
    attrs = el.attrib or {}
    role = (attrs.get("role") or "").lower()

    if tag == "select":
        return True

    # Combobox/listbox custom
    if role in {"combobox","listbox"}:
        return True

    # input com list (datalist)
    if tag == "input" and "list" in attrs:
        return True

    # aria-haspopup listbox
    if (attrs.get("aria-haspopup") or "").lower() in {"listbox","menu"}:
        return True

    return False

def _is_check_candidate(el: _Element) -> bool:
    tag = (el.tag or "").lower()
    attrs = el.attrib or {}
    if tag == "input":
        t = (attrs.get("type") or "").lower()
        return t in {"checkbox","radio"}
    role = (attrs.get("role") or "").lower()
    if role in {"checkbox","radio","switch"}:
        return True
    # aria-checked como indicativo
    if "aria-checked" in attrs:
        return True
    return False


# -----------------------------
# Matching por termos-alvo
# -----------------------------
_MATCH_ATTRS = (
    "id","name","value","placeholder","title","aria-label","aria-labelledby","aria-describedby",
    "data-testid","data-test","data-qa","data-cy","for","href","src","alt","role","type"
)

def _element_text(el: _Element) -> str:
    # texto visível aproximado (sem scripts/styles)
    try:
        return " ".join(el.itertext())
    except Exception:
        return ""

def _strong_match_score(el: _Element, keywords: List[str]) -> int:
    if not keywords:
        return 0

    hay_parts = []
    attrs = el.attrib or {}
    for a in _MATCH_ATTRS:
        v = attrs.get(a)
        if v:
            hay_parts.append(str(v))
    # Inclui classes porque muitas vezes o usuário chama por “xpto”
    cls = attrs.get("class")
    if cls:
        hay_parts.append(cls)

    txt = _element_text(el)
    if txt:
        hay_parts.append(txt)

    hay = _norm(" ".join(hay_parts))
    score = 0

    for k in keywords:
        kk = _norm(k)
        if not kk:
            continue
        # Frases com espaço: exige substring
        if " " in kk:
            if kk in hay:
                score += 10
        else:
            # palavra simples: substring também (mais tolerante)
            if kk in hay:
                score += 4

    return score


# -----------------------------
# Sanitização / redução de atributos
# -----------------------------
_KEEP_ATTR_PREFIXES = ("aria-", "data-")

def _trim_class(value: str, max_tokens: int = 6) -> str:
    toks = re.split(r"\s+", (value or "").strip())
    toks = [t for t in toks if t]
    if len(toks) <= max_tokens:
        return " ".join(toks)
    return " ".join(toks[:max_tokens])

def _shrink_attributes(el: _Element, max_attr_len: int = 180, keep_class_tokens: int = 6) -> None:
    attrs = dict(el.attrib or {})
    new_attrs = {}

    for k, v in attrs.items():
        lk = k.lower()
        if lk in {"style"}:
            continue  # estilo explode tokens
        if lk.startswith("on"):
            # mantém onclick (bom sinal de interatividade), remove outros on*
            if lk != "onclick":
                continue

        keep = False
        if lk in _MATCH_ATTRS:
            keep = True
        if lk.startswith(_KEEP_ATTR_PREFIXES):
            keep = True
        if lk in {"srcdoc"}:
            # srcdoc pode ser enorme; limita (mas preserva uma parte)
            keep = True

        if not keep:
            continue

        vv = str(v)
        if lk == "class":
            vv = _trim_class(vv, keep_class_tokens)

        if lk == "srcdoc":
            # evita explodir tokens; mantém um prefixo útil
            vv = vv[: max_attr_len * 5]

        if len(vv) > max_attr_len:
            vv = vv[:max_attr_len]

        new_attrs[k] = vv

    el.attrib.clear()
    el.attrib.update(new_attrs)

def _drop_noise_nodes(root: _Element) -> None:
    # remove scripts, styles, comments (lxml remove comments via xpath)
    for bad in root.xpath("//script|//style|//noscript"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)

    # remove comments
    for c in root.xpath("//comment()"):
        p = c.getparent()
        if p is not None:
            p.remove(c)


# -----------------------------
# Núcleo: filtrar HTML por task
# -----------------------------
def filter_html_for_task(
    html_str: str,
    task: str,
    *,
    max_kept_candidates: int = 3500,
    min_kept_candidates: int = 25,
    max_attr_len: int = 180,
    keep_class_tokens: int = 6,
) -> Dict[str, str]:
    """
    Retorna um HTML reduzido contendo apenas elementos relevantes para a task,
    preservando: ancestors, iframes, declarative shadow dom (template shadowrootmode),
    e sinais de interatividade.

    Saída:
      {
        "filtered_html": "<html>...</html>",
        "intents": "click,fill",
        "keywords": "xpto,iptu,1234",
        "kept_candidates": "123"
      }
    """
    if not isinstance(html_str, str) or not html_str.strip():
        return {
            "filtered_html": "",
            "intents": "",
            "keywords": "",
            "kept_candidates": "0",
        }

    intents = _detect_intents(task)
    keywords = _extract_keywords(task)

    # parse robusto
    try:
        root = lxml_html.fromstring(html_str)
    except Exception:
        # fallback: tenta embrulhar
        root = lxml_html.fromstring(f"<html><body>{html_str}</body></html>")

    _drop_noise_nodes(root)

    # Sempre manter iframes e declarative shadow dom
    always_keep = set()

    for el in root.xpath("//iframe|//frame|//frameset"):
        always_keep.add(el)

    for el in root.xpath("//template"):
        if _is_declarative_shadow_template(el):
            always_keep.add(el)

    # coleta candidatos
    candidates: List[Tuple[_Element, int]] = []

    # iteração em todos elementos (rápido em lxml)
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.lower()

        # ignora raiz html/head/body como candidatos
        if tag in {"html", "head", "body"}:
            continue

        # sempre manter certos nós
        if el in always_keep:
            candidates.append((el, 9999))
            continue

        # match por intenção
        is_candidate = False
        intent_weight = 0

        if "fill" in intents and _is_fill_candidate(el):
            is_candidate = True
            intent_weight = max(intent_weight, 50)

        if "select" in intents and _is_select_candidate(el):
            is_candidate = True
            intent_weight = max(intent_weight, 55)

        if ("check" in intents or "uncheck" in intents) and _is_check_candidate(el):
            is_candidate = True
            intent_weight = max(intent_weight, 60)

        if "click" in intents and _is_click_candidate(el):
            is_candidate = True
            intent_weight = max(intent_weight, 45)

        # Mesmo que não seja candidato, pode ser “custom element” relevante via termos
        score_terms = _strong_match_score(el, keywords)

        # Heurística de segurança: se tem sinais interativos, trate como candidato leve
        if not is_candidate and _has_interactive_signals(el):
            is_candidate = True
            intent_weight = max(intent_weight, 35)

        if is_candidate or score_terms >= 8:
            score = intent_weight + score_terms
            candidates.append((el, score))

    # Ordena por score (desc)
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Seleção com fallback:
    # 1) pega todos com score alto
    kept_set: Set[_Element] = set()
    strong_threshold = 60 if keywords else 45

    for el, sc in candidates:
        if sc >= strong_threshold:
            kept_set.add(el)
            if len(kept_set) >= max_kept_candidates:
                break

    # 2) se ficou pouco, complementa com top-N
    if len(kept_set) < min_kept_candidates:
        for el, sc in candidates:
            kept_set.add(el)
            if len(kept_set) >= min(max_kept_candidates, max(min_kept_candidates, 250)):
                break

    # 3) se ainda ficou muito pouco (ou task vaga), adiciona todos candidatos básicos até um limite maior
    if len(kept_set) < min_kept_candidates and candidates:
        for el, sc in candidates:
            kept_set.add(el)
            if len(kept_set) >= min(max_kept_candidates, 1200):
                break

    # Preserva ancestors (para não “perder referências” e manter hierarquia)
    def add_ancestors(el: _Element) -> None:
        p = el.getparent()
        while p is not None and isinstance(p.tag, str):
            kept_set.add(p)
            p = p.getparent()

    for el in list(kept_set):
        add_ancestors(el)

    # Agora podar árvore: remove subárvores que não estão em kept_set
    def prune(node: _Element) -> bool:
        # retorna True se deve manter node
        if node not in kept_set and node.tag not in ("html", "head", "body"):
            return False

        # percorre filhos
        for child in list(node):
            if not isinstance(child.tag, str):
                # comment etc.
                node.remove(child)
                continue
            keep_child = prune(child)
            if not keep_child:
                node.remove(child)

        # encolhe atributos nos nós mantidos
        if isinstance(node.tag, str):
            _shrink_attributes(node, max_attr_len=max_attr_len, keep_class_tokens=keep_class_tokens)

        return True

    # garante html/body
    # se root não for html, embrulha
    if (root.tag or "").lower() != "html":
        wrapper = lxml_html.fromstring("<html><head></head><body></body></html>")
        body = wrapper.xpath("//body")[0]
        body.append(root)
        root = wrapper

    prune(root)

    filtered_html = lxml_html.tostring(root, encoding="unicode", method="html")
    return {
        "filtered_html": filtered_html,
        "intents": ",".join(sorted(intents)),
        "keywords": ",".join(keywords[:30]),
        "kept_candidates": str(len(kept_set)),
    }


# -----------------------------
# Exemplo de uso rápido
# -----------------------------
if __name__ == "__main__":
    html_in = """
    <html><body>
      <div>
        <button id="btnXPTO">XPTO</button>
        <input name="iptu" placeholder="IPTU" />
        <div role="combobox" aria-label="campo xpto">...</div>
        <iframe id="frame1" src="/x"></iframe>
        <template shadowrootmode="open"><div><button>Dentro</button></div></template>
        <script>var a = "gigante";</script>
      </div>
    </body></html>
    """
    task = 'clico no botao "XPTO"'
    out = filter_html_for_task(html_in, task)
    print(out["intents"], out["keywords"], out["kept_candidates"])
    print(out["filtered_html"])
