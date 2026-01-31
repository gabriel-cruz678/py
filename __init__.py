def transform_html(**kwargs):
    import re
    import os
    import unicodedata
    from lxml import html as lxml_html

    TASK = kwargs.get("TASK")

    # ==========================================================
    # MUDANÇA PEDIDA: ler HTML via repositório (arquivo)
    # - segue o mesmo estilo do exemplo (kwargs.get + open/read)
    # - sem mudar o comportamento do filtro
    # ==========================================================
    html_source = kwargs.get("HTML_PATH") or kwargs.get("input_path") or kwargs.get("HTML")

    if not isinstance(TASK, str) or not TASK.strip():
        # Mantém comportamento: se não tem task, devolve o HTML original (ou vazio se não houver)
        if isinstance(html_source, str):
            # Se for path e existir, devolve conteúdo; se for HTML inline, devolve inline
            try:
                if os.path.isfile(html_source):
                    with open(html_source, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read()
            except Exception:
                pass
            return html_source
        return ""

    if not isinstance(html_source, str) or not html_source.strip():
        return ""

    # Se for um arquivo existente, lê do repo; senão trata como HTML inline (compatibilidade)
    HTML = html_source
    try:
        if os.path.isfile(html_source):
            with open(html_source, "r", encoding="utf-8", errors="ignore") as f:
                HTML = f.read()
    except Exception:
        # Se falhar a leitura, continua como estava (não muda comportamento)
        HTML = html_source

    if not isinstance(HTML, str) or not HTML.strip():
        return ""

    # -----------------------------
    # Normalização
    # -----------------------------
    PT_STOPWORDS = {
        "o","a","os","as","um","uma","uns","umas",
        "de","do","da","dos","das","em","no","na","nos","nas",
        "para","pra","por","com","sem","sobre","entre","ate","até",
        "e","ou","se","que","qual","quais","como","quando","onde",
        "clico","clicar","clique","pressiono","pressionar","aperte","apertar",
        "preencho","preencher","digito","digitar","insiro","inserir","escrevo","escrever",
        "seleciono","selecionar","escolho","escolher",
        "marco","marcar","desmarco","desmarcar","habilito","habilitar","desabilito","desabilitar",
        "ativo","ativar","desativo","desativar","liga","ligar","desliga","desligar",
        "campo","botao","botão","opcao","opção","valor",
        "checkbox","radio","radian","switch",
    }

    def strip_accents(s: str) -> str:
        s = unicodedata.normalize("NFKD", s)
        return "".join(ch for ch in s if not unicodedata.combining(ch))

    def norm(s: str) -> str:
        s = (s or "").strip().lower()
        s = strip_accents(s)
        s = re.sub(r"\s+", " ", s)
        return s

    def extract_quoted_phrases(task: str):
        out = []
        for m in re.finditer(r"([\"'])(.+?)\1", task):
            p = m.group(2).strip()
            if p:
                out.append(p)
        return out

    def extract_keywords(task: str):
        t = norm(task)
        raw = re.findall(r"[a-z0-9][a-z0-9_\-\.]{1,}", t)
        quoted = [norm(x) for x in extract_quoted_phrases(task)]
        seen = set()
        out = []
        for w in raw:
            if w in PT_STOPWORDS:
                continue
            if len(w) < 2:
                continue
            if w not in seen:
                out.append(w)
                seen.add(w)
        for q in quoted:
            if q and q not in seen:
                out.insert(0, q)
                seen.add(q)
        return out

    # -----------------------------
    # Intenção
    # -----------------------------
    INTENT_PATTERNS = {
        "click": [
            r"\b(clic(ar|o|que|ke|k)|clique)\b", r"\bpression(ar|o|e)\b", r"\baperte\b", r"\btoque\b",
            r"\babri(r|o)\b", r"\bentr(ar|o)\b"
        ],
        "fill": [
            r"\bpreench(er|o|a)\b", r"\bdigit(ar|o|e)\b", r"\binsir(o|a|ir)\b",
            r"\bescrev(o|a|er)\b", r"\binform(e|ar)\b"
        ],
        "select": [
            r"\bselecion(ar|o|e)\b", r"\bescolh(er|o|a)\b", r"\bdefin(ir|o)\b.*\bvalor\b"
        ],
        "check": [
            r"\bmarc(ar|o|e)\b", r"\bhabilit(ar|o|e)\b", r"\bativ(ar|o|e)\b", r"\blig(ar|o|a)\b", r"\bcheck\b"
        ],
        "uncheck": [
            r"\bdesmarc(ar|o|e)\b", r"\bdesabilit(ar|o|e)\b", r"\bdesativ(ar|o|e)\b", r"\bdeslig(ar|o|a)\b", r"\buncheck\b"
        ],
    }

    def detect_intents(task: str):
        t = norm(task)
        intents = set()
        for intent, pats in INTENT_PATTERNS.items():
            for p in pats:
                if re.search(p, t):
                    intents.add(intent)
                    break
        if not intents:
            intents.add("click")
        return intents

    intents = detect_intents(TASK)
    keywords = extract_keywords(TASK)

    # -----------------------------
    # Parse HTML
    # -----------------------------
    try:
        root = lxml_html.fromstring(HTML)
    except Exception:
        root = lxml_html.fromstring(f"<html><body>{HTML}</body></html>")

    # remove ruído
    for bad in root.xpath("//script|//style|//noscript"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)
    for c in root.xpath("//comment()"):
        p = c.getparent()
        if p is not None:
            p.remove(c)

    # -----------------------------
    # Regras de candidatos
    # -----------------------------
    MATCH_ATTRS = (
        "id","name","value","placeholder","title","aria-label","aria-labelledby","aria-describedby",
        "data-testid","data-test","data-qa","data-cy","for","href","src","alt","role","type"
    )

    def element_text(el):
        try:
            return " ".join(el.itertext())
        except Exception:
            return ""

    def has_interactive_signals(el):
        attrs = el.attrib or {}
        role = (attrs.get("role") or "").lower()
        if role in {"button","link","checkbox","radio","switch","combobox","listbox","menuitem","tab"}:
            return True
        if "onclick" in attrs:
            return True
        if "tabindex" in attrs:
            return True
        if "aria-pressed" in attrs or "aria-checked" in attrs:
            return True
        if (attrs.get("aria-haspopup") or "").lower() in {"listbox","menu"}:
            return True
        return False

    def is_click_candidate(el):
        tag = (el.tag or "").lower()
        attrs = el.attrib or {}
        if tag in {"button","a","summary","label"}:
            return True
        if tag == "input":
            t = (attrs.get("type") or "text").lower()
            return t in {"button","submit","reset","image","checkbox","radio"}
        if has_interactive_signals(el):
            return True
        if "href" in attrs:
            return True
        return False

    def is_fill_candidate(el):
        tag = (el.tag or "").lower()
        attrs = el.attrib or {}
        if tag == "textarea":
            return True
        if tag == "input":
            t = (attrs.get("type") or "text").lower()
            return t in {
                "text","email","password","number","search","tel","url","date","datetime-local",
                "month","week","time","color"
            }
        ce = (attrs.get("contenteditable") or "").lower()
        if ce in {"true","", "plaintext-only"}:
            return True
        return False

    def is_select_candidate(el):
        tag = (el.tag or "").lower()
        attrs = el.attrib or {}
        role = (attrs.get("role") or "").lower()
        if tag == "select":
            return True
        if role in {"combobox","listbox"}:
            return True
        if tag == "input" and "list" in attrs:
            return True
        if (attrs.get("aria-haspopup") or "").lower() in {"listbox","menu"}:
            return True
        return False

    def is_check_candidate(el):
        tag = (el.tag or "").lower()
        attrs = el.attrib or {}
        if tag == "input":
            t = (attrs.get("type") or "").lower()
            return t in {"checkbox","radio"}
        role = (attrs.get("role") or "").lower()
        if role in {"checkbox","radio","switch"}:
            return True
        if "aria-checked" in attrs:
            return True
        return False

    def strong_match_score(el, keys):
        if not keys:
            return 0
        attrs = el.attrib or {}
        hay_parts = []
        for a in MATCH_ATTRS:
            v = attrs.get(a)
            if v:
                hay_parts.append(str(v))
        cls = attrs.get("class")
        if cls:
            hay_parts.append(cls)
        txt = element_text(el)
        if txt:
            hay_parts.append(txt)
        hay = norm(" ".join(hay_parts))
        score = 0
        for k in keys:
            kk = norm(k)
            if not kk:
                continue
            if " " in kk:
                if kk in hay:
                    score += 10
            else:
                if kk in hay:
                    score += 4
        return score

    def is_declarative_shadow_template(el):
        if (el.tag or "").lower() != "template":
            return False
        attrs = el.attrib or {}
        return any(k.lower() in ("shadowrootmode", "shadowroot") for k in attrs.keys())

    # -----------------------------
    # Redução de atributos
    # -----------------------------
    def trim_class(value, max_tokens=6):
        toks = re.split(r"\s+", (value or "").strip())
        toks = [t for t in toks if t]
        if len(toks) <= max_tokens:
            return " ".join(toks)
        return " ".join(toks[:max_tokens])

    def shrink_attributes(el, max_attr_len=180, keep_class_tokens=6):
        attrs = dict(el.attrib or {})
        new_attrs = {}
        for k, v in attrs.items():
            lk = k.lower()
            if lk == "style":
                continue
            if lk.startswith("on") and lk != "onclick":
                continue
            keep = False
            if lk in MATCH_ATTRS:
                keep = True
            if lk.startswith("aria-") or lk.startswith("data-"):
                keep = True
            if lk == "srcdoc":
                keep = True
            if not keep:
                continue

            vv = str(v)
            if lk == "class":
                vv = trim_class(vv, keep_class_tokens)
            if lk == "srcdoc":
                vv = vv[: max_attr_len * 5]
            if len(vv) > max_attr_len:
                vv = vv[:max_attr_len]

            new_attrs[k] = vv

        el.attrib.clear()
        el.attrib.update(new_attrs)

    # -----------------------------
    # Coleta candidatos + scoring + fallback
    # -----------------------------
    MAX_KEPT = 3500
    MIN_KEPT = 25

    always_keep = set()
    for el in root.xpath("//iframe|//frame|//frameset"):
        always_keep.add(el)
    for el in root.xpath("//template"):
        if is_declarative_shadow_template(el):
            always_keep.add(el)

    candidates = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.lower()
        if tag in {"html","head","body"}:
            continue

        if el in always_keep:
            candidates.append((el, 9999))
            continue

        is_cand = False
        intent_weight = 0

        if "fill" in intents and is_fill_candidate(el):
            is_cand = True
            intent_weight = max(intent_weight, 50)
        if "select" in intents and is_select_candidate(el):
            is_cand = True
            intent_weight = max(intent_weight, 55)
        if ("check" in intents or "uncheck" in intents) and is_check_candidate(el):
            is_cand = True
            intent_weight = max(intent_weight, 60)
        if "click" in intents and is_click_candidate(el):
            is_cand = True
            intent_weight = max(intent_weight, 45)

        score_terms = strong_match_score(el, keywords)

        if not is_cand and has_interactive_signals(el):
            is_cand = True
            intent_weight = max(intent_weight, 35)

        if is_cand or score_terms >= 8:
            candidates.append((el, intent_weight + score_terms))

    candidates.sort(key=lambda x: x[1], reverse=True)

    kept = set()
    strong_threshold = 60 if keywords else 45

    for el, sc in candidates:
        if sc >= strong_threshold:
            kept.add(el)
            if len(kept) >= MAX_KEPT:
                break

    if len(kept) < MIN_KEPT:
        for el, sc in candidates:
            kept.add(el)
            if len(kept) >= min(MAX_KEPT, 250):
                break

    if len(kept) < MIN_KEPT and candidates:
        for el, sc in candidates:
            kept.add(el)
            if len(kept) >= min(MAX_KEPT, 1200):
                break

    # preservar pais
    def add_ancestors(el):
        p = el.getparent()
        while p is not None and isinstance(p.tag, str):
            kept.add(p)
            p = p.getparent()

    for el in list(kept):
        add_ancestors(el)

    # embrulhar em html/body se necessário
    if (root.tag or "").lower() != "html":
        wrapper = lxml_html.fromstring("<html><head></head><body></body></html>")
        body = wrapper.xpath("//body")[0]
        body.append(root)
        root = wrapper

    # prune
    def prune(node):
        if node not in kept and node.tag not in ("html","head","body"):
            return False
        for child in list(node):
            if not isinstance(child.tag, str):
                node.remove(child)
                continue
            if not prune(child):
                node.remove(child)
        if isinstance(node.tag, str):
            shrink_attributes(node)
        return True

    prune(root)

    return lxml_html.tostring(root, encoding="unicode", method="html")
