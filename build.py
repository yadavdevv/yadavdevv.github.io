"""Build the article page from ../wsp-article/article.md.

    .venv/bin/python build.py            -> blogs/wsp-exp/index.html (+ figures copied)

Markdown with a few block directives (each starts with a line ':::name args' and ends with ':::'):

  :::tabs                         switchable visuals, one at a time
  @tab Label | figures/x.gif | caption
  :::

  :::trace Title                  Claude's reasoning, step by step
  @saw text        @thought text        @tried code | note        @failed text
  @edit code | how many weights        @result text        @img figures/x.png | caption
  :::

  :::stats                        big numbers
  @ 0% → 100% | lander landings, gusty crosswind
  :::

  :::meme name                    an original meme card from site/cards/<name>.html (one line, no closing :::)
  :::dial                         the interactive mood dial, data read from the repo (one line)

Other conventions: front matter (title/subtitle/author/date); <p align="center"><img><br><sub>cap</sub></p> -> figure;
blockquote starting with **Claude's ...** -> labelled note; other blockquotes -> bridge; ```chat -> terminal window.
"""
import html, json, re, shutil
from pathlib import Path
import markdown

HERE = Path(__file__).parent
SRC = HERE.parent / "wsp-article" / "article.md"
REPO = HERE.parent / "wsp"
OUT = HERE / "blogs" / "wsp-exp"


def inline(t):
    return markdown.markdown(t.strip(), extensions=["smarty"]).removeprefix("<p>").removesuffix("</p>")


def front_matter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(re.findall(r'^(\w+):\s*"?(.*?)"?\s*$', m.group(1), re.M)), text[m.end():]


# ---------- directives ----------
def d_tabs(args, lines, n):
    tabs = [[p.strip() for p in l[4:].split("|", 2)] for l in lines if l.startswith("@tab")]
    btn = "".join(f'<button role="tab" aria-selected="{str(i == 0).lower()}" data-i="{i}">{html.escape(t[0])}</button>'
                  for i, t in enumerate(tabs))
    pan = ""
    for i, (lab, src, *cap) in enumerate(tabs):
        attr = f'src="{src}"' if i == 0 else f'data-src="{src}"'
        cap_html = f'<p class="cap">{inline(cap[0])}</p>' if cap and cap[0] else ""
        media = (f'<video {attr} autoplay muted loop playsinline aria-label="{html.escape(lab)}"></video>' if src.endswith(".mp4")
                 else f'<img {attr} alt="{html.escape(lab)}">')
        pan += f'<div class="tab-panel{" on" if i == 0 else ""}" role="tabpanel">{media}{cap_html}</div>'
    return f'<div class="tabs wide reveal"><div class="tab-bar" role="tablist">{btn}<span class="tab-ink"></span></div><div class="tab-panels">{pan}</div></div>'


STEP = {"saw": ("Observed", "o"), "thought": ("Reasoned", "r"), "tried": ("First try", "t"), "failed": ("Didn't work", "f"),
        "edit": ("The edit", "e"), "result": ("Result", "s")}


def d_trace(args, lines, n):
    why, act, img = [], [], ""                  # how Claude worked it out (folds away in quick mode), then the edit and result
    for l in lines:
        m = re.match(r"@(\w+)\s+(.*)", l)
        if not m: continue
        k, v = m.groups()
        if k == "img":
            src, *cap = [p.strip() for p in v.split("|", 1)]
            cap_html = f"<figcaption>{inline(cap[0])}</figcaption>" if cap else ""
            img = f'<figure class="trace-img"><img src="{src}" alt="which weights changed" loading="lazy">{cap_html}</figure>'
            continue
        lab, cls = STEP[k]
        if k in ("edit", "tried"):
            code, *note = [p.strip() for p in v.split("|", 1)]
            body = f'<code class="edit-code">{html.escape(code)}</code>' + (f'<span class="edit-note">{inline(note[0])}</span>' if note else "")
        else:
            body = inline(v)
        step = f'<li class="step s-{cls}"><span class="step-lab">{lab}</span><div class="step-body">{body}</div></li>'
        (act if k in ("edit", "result") else why).append(step)
    fails = sum("s-f" in w for w in why)
    label = f'How Claude worked it out · {len(why)} steps' + (f', {fails} failed tr{"y" if fails == 1 else "ies"}' if fails else "")
    steps = (f'<details class="trace-why"><summary>{label}</summary><ol class="steps">{"".join(why)}</ol></details>' if why else "")
    steps += f'<ol class="steps">{"".join(act)}</ol>'
    return (f'<div class="trace wide reveal{" has-img" if img else ""}"><div class="trace-h"><span class="trace-kick">How Claude did it</span>'
            f'<span class="trace-title">{inline(args)}</span></div><div class="trace-steps">{steps}</div>{img}</div>')


def d_stats(args, lines, n):
    cells = ""
    for l in lines:
        if not l.startswith("@"): continue
        parts = [p.strip() for p in l[1:].split("|")]
        kick, val, lab = parts if len(parts) == 3 else ("", *parts)   # "@ kicker | value | label" or "@ value | label"
        kick = f'<div class="stat-k">{html.escape(kick)}</div>' if kick else ""
        cells += f'<div class="stat">{kick}<div class="stat-v">{html.escape(val)}</div><div class="stat-l">{inline(lab)}</div></div>'
    return f'<div class="stats wide reveal">{cells}</div>'


def d_meme(args, lines, n):
    return f'<div class="meme reveal">{(HERE / "cards" / f"{args.strip()}.html").read_text()}</div>'


def d_dial(args, lines, n):
    d = REPO / "case12-mood-dial"
    ans = json.loads((d / "dial_answers.json").read_text()); tone = json.loads((d / "dial_tone_gemma_judge.json").read_text())
    show = json.loads((d / "dial_showcase.json").read_text())          # longer sampled answers and follow-ups (gen_showcase.py)
    ns = {}; exec((d / "prompts.py").read_text(), ns)
    facts = {s: round(100 * sum(any(k in a.lower() for k in kw) for a, (_, kw) in zip(ans[s]["fact"], ns["TEST"])) / len(ns["TEST"]))
             for s in ans}
    convs = [[q] for q in show["single"]] + show["chats"]
    labels = ["My train is late", "Plan a birthday party", "Homework?", "💬 Blue Hulk vs green Avatar · 3 turns", "💬 I got a puppy · 3 turns"]
    data = {"q": convs, "a": {str(int(s)): [[x] for x in a["single"]] + a["chats"] for s, a in show["a"].items()},
            "tone": tone, "facts": facts}
    qbtn = "".join(f'<button data-q="{i}" aria-pressed="{str(i == 0).lower()}">{html.escape(q)}</button>' for i, q in enumerate(labels))
    return (f'<div class="dial wide reveal" id="dial"><div class="dial-head">Try it: drag the dial</div><div class="dial-qs">{qbtn}</div>'
            '<div class="dial-ctl"><span>😠 grumpy</span><input type="range" min="-4" max="4" step="1" value="0" aria-label="mood dial">'
            '<span>cheerful 😄</span></div><div class="dial-meter"><div><b data-k="s"></b><small>dial setting</small></div>'
            '<div><b data-k="tone"></b><small>tone (1 grumpy · 5 cheerful)</small></div>'
            '<div><b data-k="facts"></b><small>factual questions right</small></div></div>'
            '<div class="dial-ans"><span class="dial-who">Gemma 3 1B, edited</span><div class="dial-chat"></div></div>'
            '<p class="w-foot">Answers up to 220 tokens, sampled (temperature 0.7, same seed at every setting); the follow-ups are one '
            'conversation. Tone and facts are measured separately, on held-out questions with greedy answers.</p>'
            f'<script type="application/json" id="dial-data">{json.dumps(data, ensure_ascii=False)}</script></div>')


def d_photo(args, lines, n):
    f = {}
    for l in lines:
        m = re.match(r"@(\w+)\s+(.*)", l)
        if m: f[m.group(1)] = m.group(2).strip()
    over = "".join(f'<span class="ph-{k}">{html.escape(f[k])}</span>' for k in ("top", "bottom") if k in f)
    cap = f'<p class="ph-cap">{inline(f["cap"])}</p>' if "cap" in f else ""
    credit = f'<p class="ph-credit">{inline(f["credit"])}</p>' if "credit" in f else ""
    size = f' ph-{args.strip()}' if args.strip() else ""
    if not (SRC.parent / f["src"]).exists():                    # image not added yet: a visible slot instead
        print(f"  missing photo: {f['src']}")
        img = f'<div class="ph-missing">Image goes here: <code>{f["src"]}</code><br>{html.escape(f.get("alt", ""))}</div>'
    else:
        img = f'<img src="{f["src"]}" alt="{html.escape(f.get("alt", ""))}" loading="lazy">'
    return f'<figure class="photo reveal{size}"><div class="ph-frame">{img}{over}</div><figcaption>{cap}{credit}</figcaption></figure>'


def d_explain(args, lines, n):
    body = markdown.markdown("\n".join(lines), extensions=["tables", "smarty"])
    return (f'<details class="explain reveal"><summary><span class="ex-kick">New to this?</span>'
            f'<span class="ex-title">{inline(args)}</span></summary><div class="ex-body">{body}</div></details>')


def d_deep(args, lines, n):
    body = markdown.markdown(sidenotes("\n".join(lines)), extensions=["tables", "fenced_code", "smarty"])
    return (f'<details class="deep reveal"><summary><span class="ex-kick">Deep dive</span>'
            f'<span class="ex-title">{inline(args)}</span></summary><div class="ex-body">{body}</div></details>')


def d_widget(name):                         # interactive pieces; their JS lives in template.html
    return lambda args, lines, n: (HERE / "widgets" / f"{name}.html").read_text()


DIRECTIVES = {"tabs": d_tabs, "trace": d_trace, "stats": d_stats, "meme": d_meme, "dial": d_dial, "photo": d_photo,
              "explain": d_explain, "deep": d_deep, "race": d_widget("race"), "lander": d_widget("lander"),
              "life": d_widget("life")}
KINDS = []                                                      # directive name of each block, in order
RAW = {"explain", "deep"}                                       # body passed through as markdown, not @ lines
ONE_LINE = {"meme", "dial", "race", "lander", "life"}           # no closing :::


def directives(text):
    out, blocks, lines, i = [], [], text.split("\n"), 0
    while i < len(lines):
        m = re.match(r"^:::(\w+)\s*(.*)$", lines[i])
        if m and m.group(1) in DIRECTIVES:
            name, args, body = m.group(1), m.group(2), []
            i += 1
            if name not in ONE_LINE:
                while lines[i].strip() != ":::":
                    s = lines[i].strip()
                    if name in RAW:
                        body.append(lines[i])
                    elif s.startswith("@") or not body:
                        body.append(s)
                    elif s:
                        body[-1] += " " + s                         # wrapped continuation of the previous @ line
                    i += 1
                i += 1
            blocks.append(DIRECTIVES[name](args, body if name in RAW else [b for b in body if b], len(blocks)))
            KINDS.append(name)
            out += ["", f"DIRECTIVE{len(blocks) - 1}X", ""]
            continue
        out.append(lines[i]); i += 1
    return "\n".join(out), blocks


def sidenotes(text):
    """((side: text)) -> a numbered margin note (inline on narrow screens)."""
    return re.sub(r"\(\(side:\s*(.*?)\)\)", lambda m: f'<span class="sn-ref"></span><span class="sidenote">{inline(m.group(1))}</span>',
                  text, flags=re.S)


# ---------- post-processing of converted markdown ----------
def figures(text):
    pat = re.compile(r'<p align="center"><img src="([^"]+)"[^>]*?alt="([^"]*)"\s*>(?:<br>\s*<sub>(.*?)</sub>)?</p>', re.S)
    return pat.sub(lambda m: f'<figure class="reveal"><img src="{m.group(1)}" alt="{m.group(2)}" loading="lazy">'
                             + (f"<figcaption>{inline(m.group(3))}</figcaption>" if m.group(3) else "") + "</figure>", text)


def chat_blocks(body):
    def rep(m):
        raw = html.unescape(m.group(1)).rstrip("\n").split("\n")
        lines = []
        for ln in raw:
            if ln.startswith(" ") and ln.strip() and lines and not lines[-1].startswith("you>"):
                lines[-1] += " " + ln.strip()
            else:
                lines.append(ln)
        out = []
        for ln in lines:
            if ln.startswith("you>"):
                out.append(f'<div class="t-you"><span class="t-prompt">you&gt;</span>{html.escape(ln[4:].strip())}</div>')
                continue
            mm = re.match(r"(ORIGINAL|EDITED(?: \([^)]*\))?|BEFORE|AFTER)(\s+)(.*)", ln)
            if mm:
                tag = mm.group(1); kind = "orig" if tag in ("ORIGINAL", "BEFORE") else "edit"
                out.append(f'<div class="t-ans"><span class="t-tag t-{kind}">{html.escape(tag)}</span><span class="t-text">{html.escape(mm.group(3))}</span></div>')
            elif ln.strip():
                out.append(f'<div class="t-ans"><span class="t-tag"></span><span class="t-text">{html.escape(ln.strip())}</span></div>')
            else:
                out.append('<div class="t-gap"></div>')
        return ('<div class="terminal wide reveal"><div class="t-bar"><span></span><span></span><span></span>'
                f'<em>playground · original vs edited weights</em></div><div class="t-body">{"".join(out)}</div></div>')
    return re.sub(r'<pre><code class="language-chat">(.*?)</code></pre>', rep, body, flags=re.S)


def notes(body):
    def rep(m):
        inner = m.group(1).strip()
        lab = re.match(r"<p><strong>(Claude's [^<]+)</strong>\s*·\s*(.*?)</p>", inner, re.S)
        if lab:
            return (f'<aside class="note reveal"><div class="note-label"><span class="note-who">{lab.group(1)}</span>'
                    f'<span class="note-src">{lab.group(2)}</span></div>{inner[lab.end():].strip()}</aside>')
        return f'<aside class="bridge reveal">{inner}</aside>'
    return re.sub(r"<blockquote>(.*?)</blockquote>", rep, body, flags=re.S)


def setups(body):
    return re.sub(r"<ul>\s*(<li><strong>Claude gets:</strong>.*?)</ul>",
                  r'<div class="setup reveal"><div class="setup-h">The rules of the test</div><ul>\1</ul></div>', body, flags=re.S)


def tables(body):
    return re.sub(r"(<table>.*?</table>)", r'<div class="table-wrap wide reveal">\1</div>', body, flags=re.S)


def cost(h):
    """(words, glances, tables) in a piece of html. Glances are images, code blocks and interactive pieces."""
    g, t = h.count("<img") + h.count("<pre") + h.count('class="ph-missing"'), h.count("<table")
    h = re.sub(r'<script.*?</script>|<table.*?</table>|<pre.*?</pre>|<figure.*?</figure>|<p align="center">.*?</p>', " ", h, flags=re.S)
    return len(re.sub(r"<[^>]+>", " ", h).split()), g, t


def reading_minutes(prose, blocks):
    """(quick, full) minutes: prose at 230 words a minute, 20 s per table, and images the way Medium counts them
    (12 s for the first, one second less for each after, never under 3 s). Quick skips deep dives, explainers and the
    folded reasoning inside traces."""
    q = f = cost(prose)
    add = lambda a, b: tuple(x + y for x, y in zip(a, b))
    for kind, b in zip(KINDS, blocks):
        if kind == "trace":
            q = add(q, cost(re.sub(r'<details class="trace-why".*?</details>', " ", b, flags=re.S))); f = add(f, cost(b))
        elif kind in RAW:
            f = add(f, cost(b))
        else:                                                      # widgets, cards, photos, tabs, stats: one glance each
            q = add(q, (0, 1, 0)); f = add(f, (0, 1, 0))
    sec = lambda w, g, t: 60 * w / 230 + sum(max(3, 12 - i) for i in range(g)) + 20 * t
    return round(sec(*q) / 60), round(sec(*f) / 60)


def toc(body):
    items = []
    for lvl, hid, title in re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', body):
        items.append(f'<li class="toc-{lvl}"><a href="#{hid}">{re.sub(r"<[^>]+>", "", title)}</a></li>')
    return "<ul>" + "".join(items) + "</ul>"


def main():
    meta, text = front_matter(SRC.read_text())
    text = text.replace("TITLE_PLAIN", meta["title"].split(" | ")[0].replace("*", ""))   # citation: headline only
    text, blocks = directives(sidenotes(text))
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "md_in_html", "smarty"])
    body = md.convert(text)
    quick, minutes = reading_minutes(body, blocks)
    for k, b in enumerate(blocks):
        body = body.replace(f"<p>DIRECTIVE{k}X</p>", b)
    body = setups(tables(notes(chat_blocks(figures(body)))))
    body = body.replace("<p><strong>TL;DR.</strong>", '<p class="tldr reveal"><strong>TL;DR.</strong>', 1)
    words = len(re.sub(r"<script.*?</script>|<[^>]+>", " ", body, flags=re.S).split())
    page = (HERE / "template.html").read_text()
    for k, v in {"title": meta["title"].replace("*", "").replace(" | ", " · "), "title_html": re.sub(r" \| (.+)$", r'<span class="h1-sub">\1</span>', re.sub(r"\*(.+?)\*", r'<span class="hl">\1</span>', meta["title"])), "subtitle": meta.get("subtitle", ""), "author": meta.get("author", ""),
                 "date": meta.get("date", ""), "minutes": str(minutes), "quick": str(quick), "toc": toc(body), "body": body}.items():
        page = page.replace("{{" + k + "}}", v)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page)
    shutil.copytree(SRC.parent / "figures", OUT / "figures", dirs_exist_ok=True)
    left = re.findall(r"DIRECTIVE\d+X|:::\w+", page)
    print(f"built {OUT / 'index.html'}: {words} words, quick read {quick} min, full {minutes} min, {len(blocks)} components"
          + (f"  UNRESOLVED: {left}" if left else ""))


if __name__ == "__main__":
    main()
