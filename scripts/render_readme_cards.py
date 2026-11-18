"""Disegna le card SVG animate del profilo GitHub in cards/.

    python3 scripts/render_readme_cards.py           # card animate
    STATIC=1 python3 scripts/render_readme_cards.py  # solo il fotogramma finale

Legge profile.json (testi), data/contributions.json (contributi, aggiornato
dalla GitHub Action), assets/portrait.txt (ritratto ASCII) e assets/fonts/.
Solo libreria standard: la Action non installa niente.

Un SVG mostrato con <img> non esegue script ne carica file esterni, ma il suo
<style> funziona: le animazioni sono keyframe CSS piu qualche elemento SMIL
(<set>, <animateTransform>) per le cose che il CSS non sa fare (cambiare un
testo, spostare un gradiente). Con prefers-reduced-motion e con STATIC=1 tutto
si ferma sul fotogramma finale.
"""

import base64
import json
import os
import struct
import zlib
from collections import OrderedDict
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
STATIC = os.environ.get("STATIC") == "1"

PROFILE = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))

# Palette di CIAKO
BG = "#050505"
CARD = "#0b0b0b"
BAR = "#111111"
BORDER = "#1f1f1f"
TEXT = "#ffffff"
DIM = "#d7d7d7"
MUTED = "#888888"
MUTED2 = "#555555"
ORANGE = "#ff7a1a"
YELLOW = "#e4c260"
BLUE = "#60a5e4"
HEAT = ["#161616", "#4d2507", "#8f430d", "#cc5f13", ORANGE]
LANG_COLORS = {"TypeScript": "#3178c6", "Python": "#3572a5", "JavaScript": "#f1e05a", "HTML": "#e34c26"}
STATUS_COLORS = {"RUN": ORANGE, "PoC": YELLOW, "OK": BLUE}

MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
MONO = "'JB Mono', ui-monospace, Menlo, monospace"

PORTRAIT_WIDTH = int(os.environ.get("PORTRAIT_WIDTH", 400))
PORTRAIT_STRETCH = float(os.environ.get("PORTRAIT_STRETCH", 2.0))  # allungamento verticale dei caratteri
PORTRAIT_INK = "#d4d4d4"  # grigio morbido: meno contrasto, ogni carattere disturba meno  # larghezza del ritratto nell'hero

# Ritmo della pagina. Il browser avvia l'animazione di un'immagine solo quando
# entra nello schermo: le card sotto la piega quindi partono quasi subito,
# altrimenti chi scorre vedrebbe spazio vuoto per secondi.
T_HERO, T_GRAPH, T_ACTIVITY, T_TILES, T_PROJECTS = 0.0, 0.9, 1.3, 0.3, 0.4


# --------------------------------------------------------------------------- base

def font_face(family: str, file: str, weight: int) -> str:
    b64 = base64.b64encode((ROOT / "assets" / "fonts" / file).read_bytes()).decode()
    return f"@font-face{{font-family:'{family}';font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2')}}"


FONTS = {
    "mono400": font_face("JB Mono", "mono-400.woff2", 400),
    "mono700": font_face("JB Mono", "mono-700.woff2", 700),
}

KEYFRAMES = """
@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes gone{to{opacity:0}}
@keyframes pop{0%{opacity:0;transform:scale(.2)}70%{opacity:1;transform:scale(1.25)}100%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes slideIn{from{opacity:0;transform:translateX(-28px)}to{opacity:1;transform:none}}
@keyframes swing{0%{opacity:0;transform:translateY(70px) rotate(-9deg)}55%{opacity:1;transform:translateY(-8px) rotate(2deg)}78%{transform:translateY(3px) rotate(-.6deg)}100%{opacity:1;transform:none}}
@keyframes nudge{0%,80%,100%{transform:none}88%{transform:translateX(4px)}}
@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
@keyframes pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(3.2);opacity:0}}
@keyframes sweep{0%{transform:translateX(-260px) skewX(-20deg)}35%,100%{transform:translateX(560px) skewX(-20deg)}}
text{font-family:MONOFONT}
.box{transform-box:fill-box;transform-origin:center}
.bottom{transform-box:fill-box;transform-origin:50% 100%}
"""

FREEZE = "*{animation:none!important}.frames,.shine,.cover,.ring{display:none}"


def svg(width: int, height: int, title: str, body: str, fonts: list[str], extra_css: str = "") -> str:
    css = "".join(FONTS[f] for f in fonts) + KEYFRAMES.replace("MONOFONT", MONO) + extra_css
    css += FREEZE if STATIC else f"@media (prefers-reduced-motion:reduce){{{FREEZE}}}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title><style>{css}</style>{body}</svg>\n"
    )


def anim(name: str, dur: float, delay: float, ease: str = "cubic-bezier(.2,.8,.2,1)", extra: str = "") -> str:
    return f'style="animation:{name} {dur}s {ease} {delay:.2f}s both{extra}"'


def window(width: int, height: int, title: str) -> str:
    """Cornice da finestra di terminale con i tre pallini."""
    dots = "".join(
        f'<circle cx="{22 + i * 18}" cy="19" r="6" fill="{c}"/>'
        for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"])
    )
    return (
        f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="14" fill="{CARD}" stroke="{BORDER}"/>'
        f'<path d="M14.5 .5h{width - 29}a14 14 0 0 1 14 14V38H.5V14.5a14 14 0 0 1 14-14z" fill="{BAR}"/>'
        f'<line x1="1" y1="38" x2="{width - 1}" y2="38" stroke="{BORDER}"/>{dots}'
        f'<text x="{width / 2}" y="24" text-anchor="middle" font-size="12" fill="{MUTED}">{escape(title)}</text>'
    )


def typed(x: float, y: float, cmd: str, delay: float, size: int = 15, bg: str = CARD) -> str:
    """Un comando che si scrive lettera per lettera: '$ cmd'.

    Una copertura del colore dello sfondo, con il cursore arancione sul bordo,
    scorre verso destra a scatti di un carattere e scopre il testo.
    """
    cw = size * 0.6
    n = len(cmd)
    dur = max(0.25, n * 0.045)
    name = f"t{zlib.crc32(f'{x},{y},{cmd}'.encode()):x}"  # stabile tra un run e l'altro
    kf = f"@keyframes {name}{{from{{transform:translateX(0)}}to{{transform:translateX({n * cw:.1f}px)}}}}"
    text_x = x + 2 * cw
    return (
        f"<style>{kf}</style>"
        f'<text x="{x}" y="{y}" font-size="{size}"><tspan fill="{ORANGE}" font-weight="700">$</tspan>'
        f'<tspan x="{text_x}" fill="{DIM}">{escape(cmd)}</tspan></text>'
        f'<g class="cover" style="animation:{name} {dur:.2f}s steps({n}) {delay:.2f}s both,gone .01s linear {delay + dur + 0.15:.2f}s both">'
        f'<rect x="{text_x - 1}" y="{y - size}" width="{n * cw + 14}" height="{size * 1.45}" fill="{bg}"/>'
        f'<rect x="{text_x}" y="{y - size + 2}" width="{cw}" height="{size * 1.15}" fill="{ORANGE}"/></g>'
    )


def count_up(x: float, y: float, value: int, start: float, attrs: str, frames: int = 18, dur: float = 1.1, fmt=str) -> str:
    """Numero che sale da zero: il CSS non puo cambiare un testo, quindi ogni
    valore intermedio e un <text> a parte che SMIL mostra per pochi millisecondi."""
    dt = dur / frames
    parts = []
    for k in range(frames):
        v = round(value * (1 - (1 - k / frames) ** 3))
        parts.append(
            f'<text x="{x}" y="{y}" {attrs} opacity="0">{fmt(v)}'
            f'<set attributeName="opacity" to="1" begin="{start + k * dt:.3f}s" dur="{dt:.3f}s"/></text>'
        )
    final = f'<text x="{x}" y="{y}" {attrs} {anim("fadeIn", 0.01, start + dur, "linear")}>{fmt(value)}</text>'
    return f'<g class="frames">{"".join(parts)}</g>{final}'


# ------------------------------------------------------------------------- dati

def load_days() -> list[dict]:
    path = ROOT / "data" / "contributions.json"
    if not path.exists():
        raise SystemExit("Manca data/contributions.json: lancia prima scripts/fetch_contributions.py")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"date": date.fromisoformat(d["date"]), "count": d["count"]} for d in data["days"]]


def stats(days: list[dict]) -> dict:
    counts = [d["count"] for d in days]
    total = sum(counts)
    active = sum(1 for c in counts if c)

    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)

    current = 0
    tail = counts[:-1] if counts and counts[-1] == 0 else counts  # oggi non e ancora finito
    for c in reversed(tail):
        if not c:
            break
        current += 1

    top = max(days, key=lambda d: (d["count"], d["date"]))
    months: "OrderedDict[tuple[int, int], int]" = OrderedDict()
    for d in days:
        key = (d["date"].year, d["date"].month)
        months[key] = months.get(key, 0) + d["count"]
    months_list = list(months.items())[-12:]
    best_month = max(months_list, key=lambda m: (m[1], m[0]))

    first_sunday = days[0]["date"].toordinal() - (days[0]["date"].weekday() + 1) % 7
    weeks: dict[int, int] = {}
    for d in days:
        w = (d["date"].toordinal() - first_sunday) // 7
        weeks[w] = weeks.get(w, 0) + d["count"]

    return {
        "total": total,
        "active": active,
        "longest": longest,
        "current": current,
        "top": top,
        "months": months_list,
        "best_month": best_month,
        "active_weeks": sum(1 for v in weeks.values() if v),
        "weeks": len(weeks),
        "per_active_day": total / active if active else 0,
        "days": len(days),
        "updated": days[-1]["date"],
        "last_active": max((d["date"] for d in days if d["count"]), default=days[-1]["date"]),
    }


def fmt_day(d: date) -> str:
    return f"{d.day} {MESI[d.month - 1]}"


def portrait_row(chars: str, tones: str) -> str:
    """Una riga del ritratto: i caratteri consecutivi con la stessa luminosita
    finiscono in un unico <tspan>, cosi il file resta leggero."""
    if not tones:
        return escape(chars)
    out, run, level = [], "", None
    for i, ch in enumerate(chars):
        lv = tones[i] if i < len(tones) else " "
        if lv != level and run:
            out.append(tone_span(run, level))
            run = ""
        level = lv
        run += ch
    if run:
        out.append(tone_span(run, level))
    return "".join(out)


def tone_span(text: str, level: str | None) -> str:
    if not level or not level.isdigit():
        return escape(text)
    opacity = 0.22 + 0.78 * int(level) / 7  # anche il nero resta visibile: la sagoma non sparisce
    return f'<tspan fill-opacity="{opacity:.2f}">{escape(text)}</tspan>'


# ------------------------------------------------------------------------ card

def hero(s: dict) -> str:
    W, H = 1000, 440
    p = PROFILE
    body = [window(W, H, f"{p['host']}: ~")]
    t = T_HERO
    body.append(typed(40, 82, "whoami", t + 0.3))

    # nome, con un riflesso arancione che lo attraversa ogni tanto
    name = escape(p["name"])
    body.append(
        '<defs><linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="-260" y1="0" x2="0" y2="0">'
        f'<stop offset="0" stop-color="{ORANGE}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{ORANGE}" stop-opacity="1"/>'
        f'<stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/>'
        '<animateTransform attributeName="gradientTransform" type="translate" values="0 0;0 0;800 0" '
        f'keyTimes="0;.65;1" dur="5s" begin="{t + 2.2:.1f}s" repeatCount="indefinite"/>'
        "</linearGradient>"
        '<clipPath id="win"><rect x="1" y="39" width="998" height="400" rx="13"/></clipPath></defs>'
    )
    body.append(
        f'<g class="box" {anim("fadeUp", 0.7, t + 1.0)}>'
        f'<text x="36" y="150" font-weight="700" font-size="68" letter-spacing="-1" fill="{TEXT}">{name}</text>'
        f'<text class="shine" x="36" y="150" font-weight="700" font-size="68" letter-spacing="-1" fill="url(#shine)">{name}</text></g>'
    )
    role_w = len(p["role"]) * 24 * 0.6
    body.append(
        f'<g class="box" {anim("fadeUp", 0.6, t + 1.35)}>'
        f'<text x="40" y="194" font-size="24" font-weight="700" fill="{ORANGE}">{escape(p["role"])}</text>'
        f'<rect x="{40 + role_w + 6:.1f}" y="175" width="13" height="24" fill="{ORANGE}" '
        f'style="animation:blink 1.1s steps(1) {t + 1.9:.2f}s infinite"/></g>'
    )

    body.append(typed(40, 244, "cat about.txt", t + 1.8))
    for i, line in enumerate(p["about"]):
        body.append(
            f'<text class="box" x="40" y="{274 + i * 25}" font-size="15" fill="{DIM}" '
            f'{anim("fadeUp", 0.5, t + 2.45 + i * 0.15)}>{escape(line)}</text>'
        )

    body.append(typed(40, 342, "ls stack/", t + 2.7))
    x = 40
    for i, tech in enumerate(p["stack"]):
        w = len(tech) * 7.8 + 22
        body.append(
            f'<g class="box" {anim("pop", 0.45, t + 3.15 + i * 0.08)}>'
            f'<rect x="{x}" y="358" width="{w:.1f}" height="26" rx="6" fill="{ORANGE}" fill-opacity=".1" stroke="{ORANGE}" stroke-opacity=".35"/>'
            f'<text x="{x + w / 2:.1f}" y="375.5" text-anchor="middle" font-size="13" fill="{ORANGE}">{escape(tech)}</text></g>'
        )
        x += w + 8

    # barra di stato in basso, tipo tmux
    body.append(
        f'<rect x="1" y="404" width="998" height="35" fill="{BAR}" clip-path="url(#win)"/>'
        f'<line x1="1" y1="404" x2="999" y2="404" stroke="{BORDER}"/>'
        f'<circle class="ring box" cx="24" cy="421.5" r="4.5" fill="{ORANGE}" style="animation:pulse 1.8s ease-out {t + 1:.1f}s infinite"/>'
        f'<circle cx="24" cy="421.5" r="4.5" fill="{ORANGE}"/>'
        f'<text x="38" y="426" font-size="13" fill="{DIM}">{escape(p["now"])}</text>'
        f'<text x="{W - 20}" y="426" text-anchor="end" font-size="13" fill="{MUTED}">github.com/{escape(p["username"])}</text>'
    )

    # ritratto: l'avatar illustrato (profile.json "portrait": "avatar") oppure
    # quello ASCII che si stampa riga per riga
    avatar = ROOT / "assets" / "avatar.png"
    portrait = ROOT / "assets" / "portrait.txt"
    if p.get("portrait") == "avatar" and avatar.exists():
        data = avatar.read_bytes()
        aw, ah = struct.unpack(">II", data[16:24])  # larghezza e altezza dall'intestazione PNG
        bottom, max_w, max_h = 403, PORTRAIT_WIDTH, 403 - 52
        scale = min(max_w / aw, max_h / ah)
        w, h = aw * scale, ah * scale
        x = W - 24 - max_w + (max_w - w) / 2
        b64 = base64.b64encode(data).decode()
        body.append(
            f'<g clip-path="url(#win)"><g class="box" {anim("fadeUp", 0.9, t + 0.5)}>'
            f'<image x="{x:.1f}" y="{bottom - h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'href="data:image/png;base64,{b64}"/></g></g>'
        )
    elif portrait.exists():
        rows = portrait.read_text(encoding="utf-8").rstrip("\n").split("\n")
        cols = max(len(r) for r in rows)
        box_w, bottom = PORTRAIT_WIDTH, 403
        max_h = bottom - 52  # sotto la barra della finestra, con un po' di aria
        cw = min(box_w / cols, max_h / (2 * len(rows)))  # entra sia in larghezza sia in altezza
        fs = cw / 0.6
        lh = cw * 2
        x0 = W - 24 - box_w + (box_w - cols * cw) / 2
        top0 = bottom - len(rows) * lh
        tone_file = ROOT / "assets" / "portrait-tone.txt"
        tones = tone_file.read_text(encoding="utf-8").rstrip("\n").split("\n") if tone_file.exists() else []
        step = min(0.035, 2.0 / len(rows))  # tutto il ritratto si stampa in circa 2 secondi
        lines = []
        for i, r in enumerate(rows):
            if not r.strip():
                continue
            content = portrait_row(r, tones[i] if i < len(tones) else "")
            # i caratteri occupano solo il centro della riga: li allungo in verticale
            # attorno al centro della riga, cosi tra una riga e l'altra non resta
            # una striscia nera (che su schermi grandi si vede come righe)
            cy = top0 + (i + 0.5) * lh
            k = PORTRAIT_STRETCH
            lines.append(
                f'<text x="{x0:.1f}" y="{cy + 0.33 * fs:.2f}" font-size="{fs:.2f}" xml:space="preserve" '
                f'transform="matrix(1 0 0 {k} 0 {cy * (1 - k):.2f})" '
                f'{anim("fadeIn", 0.25, t + 0.4 + i * step, "linear")}>{content}</text>'
            )
        body.append(f'<g clip-path="url(#win)" fill="{PORTRAIT_INK}">{"".join(lines)}</g>')

    title = f"{p['name']} - {p['role']}"
    return svg(W, H, title, "".join(body), ["mono400", "mono700"])


def graph(days: list[dict], s: dict) -> str:
    W, H = 1000, 262
    t = T_GRAPH
    body = [window(W, H, "git log --graph")]
    body.append(typed(40, 74, "git log --graph --since=1.year", t))
    body.append(
        f'<text x="{W - 40}" y="74" text-anchor="end" font-size="13" fill="{MUTED}" {anim("fadeIn", 0.5, t + 0.6)}>'
        f'aggiornato il {fmt_day(s["updated"])}</text>'
    )

    cell, gap = 13, 3.4
    step = cell + gap
    x0, y0 = 72, 112
    first_sunday = days[0]["date"].toordinal() - (days[0]["date"].weekday() + 1) % 7
    # livelli come su GitHub: quartili dei giorni attivi, non il picco
    # (un solo giorno enorme renderebbe "deboli" tutti gli altri)
    active = sorted(d["count"] for d in days if d["count"])
    quart = [active[min(len(active) - 1, int(len(active) * q))] for q in (0.25, 0.5, 0.75)] if active else [1, 1, 1]
    rects, labels = [], []
    last_month = None
    for d in days:
        col = (d["date"].toordinal() - first_sunday) // 7
        row = (d["date"].weekday() + 1) % 7
        c = d["count"]
        level = 0 if c == 0 else 1 + sum(c > t for t in quart)
        x, y = x0 + col * step, y0 + row * step
        rects.append(
            f'<rect class="box" x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" fill="{HEAT[level]}" '
            f'{anim("pop", 0.35, t + 0.5 + col * 0.022)}/>'
        )
        if d["date"].day <= 7 and row == 0 and d["date"].month != last_month:
            last_month = d["date"].month
            if col < 52:
                labels.append(f'<text x="{x:.1f}" y="{y0 - 10}" font-size="11" fill="{MUTED}">{MESI[d["date"].month - 1]}</text>')
    for row, lab in ((1, "lun"), (3, "mer"), (5, "ven")):
        labels.append(f'<text x="40" y="{y0 + row * step + 10:.1f}" font-size="11" fill="{MUTED2}">{lab}</text>')

    legend_x = W - 40 - 5 * step - 70
    legend = [f'<text x="{legend_x}" y="{H - 18}" font-size="11" fill="{MUTED2}">meno</text>']
    for i, c in enumerate(HEAT):
        legend.append(f'<rect x="{legend_x + 38 + i * step:.1f}" y="{H - 28}" width="{cell}" height="{cell}" rx="3" fill="{c}"/>')
    legend.append(f'<text x="{legend_x + 42 + 5 * step:.1f}" y="{H - 18}" font-size="11" fill="{MUTED2}">più</text>')

    body += labels + rects
    body.append(f'<g {anim("fadeIn", 0.5, t + 1.6)}>{"".join(legend)}</g>')
    return svg(W, H, f"Grafico dei contributi: {s['total']} nell'ultimo anno", "".join(body), ["mono400", "mono700"])


def fmt_int(n: int) -> str:
    """883 -> '883', 8355 -> '8.355' (separatore delle migliaia all'italiana)."""
    return f"{n:,}".replace(",", ".")


def activity(s: dict) -> str:
    """Totale grande, barre per mese e tre statistiche, nel tema del terminale."""
    W, H = 1000, 372
    t = T_ACTIVITY
    body = [window(W, H, "stats")]
    body.append(typed(40, 74, "stats --last 12m", t))

    # titolo e totale
    body.append(
        f'<text x="40" y="114" font-size="11" letter-spacing="2" fill="{MUTED}" {anim("fadeIn", 0.4, t + 0.5)}>'
        "ULTIMI 12 MESI SU GITHUB</text>"
    )
    total = s["total"]
    num_w = len(fmt_int(total)) * 0.6 * 46
    body.append(count_up(38, 166, total, t + 0.6, 'font-size="46" font-weight="700" fill="#ffffff"', fmt=fmt_int))
    body.append(
        f'<text x="{38 + num_w + 14:.1f}" y="166" font-size="30" fill="{ORANGE}" {anim("fadeIn", 0.4, t + 0.9)}>contributi</text>'
    )

    # barre per mese: il migliore in arancione, il mese in corso piu tenue
    months = s["months"]
    peak = max(v for _, v in months) or 1
    base, max_h, x0, area = 322, 112, 40, 560
    gap = 12
    bw = (area - gap * (len(months) - 1)) / len(months)
    best = s["best_month"][0]
    for i, ((y, m), v) in enumerate(months):
        x = x0 + i * (bw + gap)
        h = max(3, v / peak * max_h)
        is_best = (y, m) == best
        is_current = i == len(months) - 1
        fill = ORANGE if is_best else ("#262626" if is_current else "#4a4a4a")
        body.append(
            f'<rect class="bottom" x="{x:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="{fill}" '
            f'{anim("grow", 0.7, t + 0.7 + i * 0.06)}/>'
            f'<text x="{x + bw / 2:.1f}" y="{base + 22}" text-anchor="middle" font-size="12" '
            f'fill="{TEXT if is_best else MUTED}">{MESI[m - 1]}</text>'
        )
        if is_best:
            body.append(
                f'<text class="box" x="{x + bw / 2:.1f}" y="{base - h - 10:.1f}" text-anchor="middle" font-size="13" '
                f'font-weight="700" fill="{ORANGE}" {anim("pop", 0.45, t + 1.6)}>{fmt_int(v)}</text>'
            )

    # tre statistiche a destra, separate da linee
    cur, longest, top = s["current"], s["longest"], s["top"]
    giorni = lambda n: "giorno" if n == 1 else "giorni"
    streak_label = "streak attuale, ed è il record" if cur and cur == longest else f"streak attuale · record {longest} {giorni(longest)}"
    blocks = [
        (f'<tspan fill="#ffffff" font-weight="700">{cur}</tspan><tspan fill="{ORANGE}" font-size="22"> {giorni(cur)}</tspan>', streak_label),
        (
            f'<tspan fill="#ffffff" font-weight="700">{s["active"]}</tspan>'
            f'<tspan fill="{MUTED2}" font-size="30"> / {s["days"]}</tspan>',
            "giorni con almeno un contributo",
        ),
        (f'<tspan fill="#ffffff" font-weight="700">{fmt_int(top["count"])}</tspan>', f"nel giorno più attivo, il {fmt_day(top['date'])}"),
    ]
    px, top_y, step = 650, 106, 80
    for i, (value, label) in enumerate(blocks):
        y = top_y + i * step
        line = f'<line x1="{px}" y1="{y + 66}" x2="{W - 40}" y2="{y + 66}" stroke="{BORDER}"/>' if i < 2 else ""
        body.append(
            f'<g class="box" {anim("slideIn", 0.5, t + 0.8 + i * 0.12)}>'
            f'<text x="{px}" y="{y + 32}" font-size="36">{value}</text>'
            f'<text x="{px}" y="{y + 54}" font-size="13" fill="{MUTED}">{escape(label)}</text>{line}</g>'
        )
    return svg(W, H, f"{total} contributi negli ultimi 12 mesi", "".join(body), ["mono400", "mono700"])


# Loghi in un riquadro 24x24: LinkedIn da Simple Icons (CC0), Gmail dal logo ufficiale
LOGOS = {
    "linkedin": (
        '<rect x="2" y="2" width="20" height="20" rx="2" fill="#ffffff"/>'
        '<path fill="#0A66C2" d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>'
    ),
    # la M di Gmail a quattro colori (viewBox originale 52 42 88 66, portata nel riquadro 24x24)
    "gmail": (
        '<g transform="translate(0 3) scale(0.2727) translate(-52 -42)">'
        '<path fill="#4285F4" d="M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6"/>'
        '<path fill="#34A853" d="M120 108h14c3.32 0 6-2.69 6-6V59l-20 15"/>'
        '<path fill="#FBBC04" d="M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2"/>'
        '<path fill="#EA4335" d="M72 74V48l24 18 24-18v26L96 92"/>'
        '<path fill="#C5221F" d="M52 51v8l20 15V48l-5.6-4.2c-5.94-4.45-14.4-.22-14.4 7.2"/>'
        "</g>"
    ),
}
LINKEDIN_BLUE = "#0A66C2"
GMAIL_RED = "#EA4335"


def wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + ([line] if line else [])


def contact_tile(key: str, label: str, title: str, title_size: int, caption: str, color: str, delay: float,
                 logo: str | None = None, label_color: str | None = None) -> str:
    """Tile cliccabile (il link sta nel README): barra colorata, logo, contatto in grande, freccia."""
    W, H = 330, 200
    icon = (
        f'<g transform="translate({W - 60} 22) scale({34 / 24:.4f})">{LOGOS[logo]}</g>'
        if logo
        else f'<g transform="translate({W - 34} 38)"><circle class="ring box" r="5" fill="{color}" '
        f'style="animation:pulse 2.2s ease-out {delay + 1:.1f}s infinite"/><circle r="5" fill="{color}"/></g>'
    )
    captions = "".join(
        f'<text x="26" y="{150 + i * 18}" font-size="13" fill="{MUTED}">{escape(c)}</text>'
        for i, c in enumerate(wrap(caption, 30))
    )
    body = [
        f'<defs><clipPath id="c-{key}"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="13"/></clipPath>'
        f'<linearGradient id="g-{key}" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="#fff" stop-opacity=".09"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>',
        f'<g class="box" {anim("swing", 0.9, delay)}>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{CARD}" stroke="{BORDER}"/>',
        f'<rect x="1" y="1" width="{W - 2}" height="4" fill="{color}" clip-path="url(#c-{key})"/>',
        f'<text x="26" y="44" font-size="12" font-weight="700" letter-spacing="2" fill="{label_color or color}">{escape(label)}</text>',
        icon,
        f'<text x="26" y="{112}" font-size="{title_size}" font-weight="700" fill="{TEXT}" {anim("fadeUp", 0.5, delay + 0.45)}>{escape(title)}</text>',
        captions,
        f'<text x="{W - 26}" y="{H - 24}" text-anchor="end" font-size="18" fill="{label_color or color}" class="box" '
        f'style="animation:nudge 3s ease-in-out {delay + 1.2:.1f}s infinite">→</text>',
        f'<g clip-path="url(#c-{key})"><rect class="shine" x="-120" y="-20" width="120" height="{H + 40}" fill="url(#g-{key})" '
        f'style="animation:sweep 5s ease-in-out {delay + 1.6:.1f}s infinite"/></g>',
        "</g>",
    ]
    return svg(W, H, f"{label}: {title}", "".join(body), ["mono400", "mono700"])


def projects() -> str:
    items = PROFILE["projects"]
    W = 1000
    row_h = 46
    H = 134 + row_h * len(items)
    t = T_PROJECTS
    body = [window(W, H, "progetti")]
    body.append(typed(40, 74, "ps aux | grep progetti", t))
    cols = (40, 130, 720, 880)
    for x, head in zip(cols, ("STATO", "PROGETTO", "LINGUAGGIO", "ACCESSO")):
        body.append(f'<text x="{x}" y="110" font-size="11" letter-spacing="1.5" fill="{MUTED2}" {anim("fadeIn", 0.4, t + 0.9)}>{head}</text>')
    body.append(f'<line x1="40" y1="121" x2="{W - 40}" y2="121" stroke="{BORDER}" {anim("fadeIn", 0.4, t + 0.9)}/>')

    for i, p in enumerate(items):
        y = 152 + i * row_h
        color = STATUS_COLORS.get(p["status"], MUTED)
        lang_c = LANG_COLORS.get(p["lang"], MUTED)
        ring = ""
        if p["status"] == "RUN":
            ring = (
                f'<circle class="ring box" cx="{cols[0] + 9}" cy="{y - 4.5}" r="3.5" fill="{color}" '
                f'style="animation:pulse 1.8s ease-out {t + 2 + i * 0.3:.1f}s infinite"/>'
            )
        body.append(
            f'<g class="box" {anim("slideIn", 0.55, t + 1.1 + i * 0.15)}>'
            f'<rect x="{cols[0]}" y="{y - 17}" width="64" height="24" rx="5" fill="{color}" fill-opacity=".12" stroke="{color}" stroke-opacity=".4"/>'
            f'{ring}<circle cx="{cols[0] + 9}" cy="{y - 4.5}" r="3.5" fill="{color}"/>'
            f'<text x="{cols[0] + 18}" y="{y}" font-size="12" font-weight="700" fill="{color}">{escape(p["status"])}</text>'
            f'<text x="{cols[1]}" y="{y}" font-size="15" fill="{TEXT}">{escape(p["title"])}</text>'
            f'<circle cx="{cols[2] + 5}" cy="{y - 5}" r="5" fill="{lang_c}"/>'
            f'<text x="{cols[2] + 16}" y="{y}" font-size="13" fill="{DIM}">{escape(p["lang"])}</text>'
            f'<text x="{cols[3]}" y="{y}" font-size="13" fill="{MUTED}">{escape(p["visibility"])}</text>'
            f'<line x1="40" y1="{y + 17}" x2="{W - 40}" y2="{y + 17}" stroke="{BORDER}" stroke-opacity=".6"/></g>'
        )
    return svg(W, H, "Progetti in corso", "".join(body), ["mono400", "mono700"])


# ------------------------------------------------------------------------ main

def main() -> None:
    days = load_days()
    s = stats(days)
    CARDS.mkdir(exist_ok=True)
    contacts = PROFILE["contacts"]
    out = {
        "hero.svg": hero(s),
        "graph.svg": graph(days, s),
        "activity.svg": activity(s),
        "tile-linkedin.svg": contact_tile("li", "LINKEDIN", f"in/{contacts['linkedin']}", 22, "connettiamoci",
                                          LINKEDIN_BLUE, T_TILES, logo="linkedin", label_color=BLUE),
        "tile-email.svg": contact_tile("em", "EMAIL", contacts["email"], 19, "scrivimi quando vuoi",
                                       GMAIL_RED, T_TILES + 0.15, logo="gmail"),
        "tile-collab.svg": contact_tile("co", "COLLABORIAMO", "Hai un progetto?", 24, contacts["collab"],
                                        ORANGE, T_TILES + 0.3),
        "projects.svg": projects(),
    }
    for name, content in out.items():
        (CARDS / name).write_text(content, encoding="utf-8")
        print(f"cards/{name}  {len(content.encode()) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
