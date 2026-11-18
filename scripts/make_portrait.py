"""Trasforma una foto nel ritratto ASCII dell'hero (assets/portrait.txt).

Si lancia una volta sola, in locale (serve `pip install pillow numpy`):

    python3 scripts/make_portrait.py foto.png --crop 0.1,0,0.9,0.72 --calib 0.22,0,0.78,0.64

Stile "a inchiostro", come un disegno: la pelle e le zone chiare restano
vuote, solo le zone scure (capelli, occhiali, barba, vestiti) si riempiono di
caratteri e i contorni del viso sono tracciati con - | / \\. Un solo colore,
niente grana: e quello che lo rende pulito.
Se la foto e un PNG scontornato, lo sfondo trasparente resta vuoto.

Opzioni:
  --crop    sinistra,alto,destra,basso in frazioni 0-1, per ingrandire il volto
  --cols    colonne (piu colonne = piu dettaglio, caratteri piu piccoli)
  --dark    quota (0-1) del soggetto, dalla parte piu scura, che diventa "piena"
  --mid     quota del soggetto che riceve almeno un carattere leggero
  --edge    sensibilita dei contorni (piu basso = piu linee)
  --smooth  quanto ammorbidire la foto prima (toglie la grana)
  --calib   zona (frazioni dell'immagine ritagliata) su cui calcolare toni e
            soglie, di solito la testa: cosi una maglietta nera non falsa il
            "nero" del viso e dei capelli
  --body    come disegnare cio che sta fuori da --calib (il busto):
            "light" trama leggera (predefinito), "outline" solo contorni,
            "full" pieno come la testa
  --landmarks  JSON di scripts/face_landmarks.swift: i lineamenti (occhi,
            sopracciglia, naso, bocca, mascella) vengono disegnati come linee
            pulite dai punti del viso, e dentro il viso la foto non aggiunge
            altro che la barba. E il modo per avere un volto semplice e nitido.
  --no-beard   con --landmarks, niente puntini della barba

  --style      "ink" (predefinito, descritto sopra) oppure "classic": l'ASCII
            classico, solo densita e niente linee di contorno. E lo stile
            giusto per un avatar illustrato. Su fondo scuro la parte chiara
            diventa piena; con --invert il contrario (per fondi chiari).
  --gamma      solo per "classic": <1 schiarisce, >1 scurisce
  --simplify N toglie i tratti piu sottili di N pixel di lavoro (contorni a
            china, rughe, ciocche): restano solo le zone grandi come occhi,
            sopracciglia e la massa dei capelli. 0 = spento
  --hair-smooth N  ammorbidimento piu forte solo nella fascia alta, quella dei
            capelli, per togliere le "righe" delle ciocche
  --hair-until F   dove finisce la fascia dei capelli (frazione dell'altezza
            del ritaglio, es. 0.32: poco sopra le sopracciglia)

Con --landmarks il flusso completo e:
    swift scripts/face_landmarks.swift foto.png landmarks.json
    python3 scripts/make_portrait.py foto.png --landmarks landmarks.json --crop ... --calib ...
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CW, CH = 6, 12  # pixel di lavoro per carattere: un monospace e alto il doppio di quanto e largo
DENSE = "=+*#%@"  # zone scure, dalla meno alla piu scura
LIGHT = ".:-"  # mezzi toni


def edge_char(angle: float) -> str:
    """Il gradiente e perpendicolare al contorno: lo ruoto di 90 gradi e scelgo
    il carattere con la stessa inclinazione."""
    a = (np.degrees(angle) + 90) % 180
    if a < 22.5 or a >= 157.5:
        return "-"
    if a < 67.5:
        return "\\"  # l'asse y dell'immagine punta in basso
    if a < 112.5:
        return "|"
    return "/"


def line_char(dx: float, dy: float) -> str:
    """Carattere con l'inclinazione di un segmento (dx, dy in pixel, y in basso)."""
    a = math.degrees(math.atan2(dy, dx)) % 180
    if a < 22.5 or a >= 157.5:
        return "-"
    if a < 67.5:
        return "\\"
    if a < 112.5:
        return "|"
    return "/"


def draw_face(reg: dict, rows: int, cols: int):
    """Disegna i lineamenti come linee pulite a partire dai punti del viso.

    Restituisce i caratteri dei lineamenti, la maschera del viso (dove la foto
    non deve aggiungere segni) e la riga da cui inizia la barba."""
    feats: dict[tuple[int, int], str] = {}

    def put(x: float, y: float, ch: str, overwrite: bool = True) -> None:
        cell = (int(y), int(x))
        if 0 <= cell[0] < rows and 0 <= cell[1] < cols and (overwrite or cell not in feats):
            feats[cell] = ch

    def segment(p, q, ch=None, overwrite=True):
        (x0, y0), (x1, y1) = p, q
        c = ch or line_char((x1 - x0) * CW, (y1 - y0) * CH)
        n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) * 3))
        for i in range(n + 1):
            t = i / n
            put(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, c, overwrite)

    def polyline(pts, closed=False, ch=None, overwrite=True):
        seq = pts + ([pts[0]] if closed else [])
        for p, q in zip(seq, seq[1:]):
            segment(p, q, ch, overwrite)

    def fill(pts, ch):
        scale = 4
        img = Image.new("L", (cols * scale, rows * scale), 0)
        ImageDraw.Draw(img).polygon([(x * scale, y * scale) for x, y in pts], fill=255)
        cov = np.asarray(img, dtype=float).reshape(rows, scale, cols, scale).mean(axis=(1, 3)) / 255
        for y, x in zip(*np.nonzero(cov >= 0.35)):
            feats[(int(y), int(x))] = ch

    # maschera del viso: mascella chiusa in alto poco sopra le sopracciglia
    contour = reg.get("faceContour", [])
    brows = reg.get("leftEyebrow", []) + reg.get("rightEyebrow", [])
    eyes = reg.get("leftEye", []) + reg.get("rightEye", [])
    face = np.zeros((rows, cols), dtype=bool)
    if contour and brows:
        brow_top = min(y for _, y in brows)
        eye_mid = sum(y for _, y in eyes) / len(eyes) if eyes else brow_top + 2
        top = brow_top - 0.6 * (eye_mid - brow_top)
        poly = contour + [(contour[-1][0], top), (contour[0][0], top)]
        img = Image.new("L", (cols * 4, rows * 4), 0)
        ImageDraw.Draw(img).polygon([(x * 4, y * 4) for x, y in poly], fill=255)
        face = np.asarray(img, dtype=float).reshape(rows, 4, cols, 4).mean(axis=(1, 3)) >= 128

    # mascella e mento
    if contour:
        polyline(contour)
    # sopracciglia: piene
    for name in ("leftEyebrow", "rightEyebrow"):
        if name in reg:
            fill(reg[name], "#")
            polyline(reg[name], closed=True, ch="=", overwrite=False)
    # occhi: contorno e pupilla
    for eye, pupil in (("leftEye", "leftPupil"), ("rightEye", "rightPupil")):
        if eye in reg:
            polyline(reg[eye], closed=True)
        if pupil in reg:
            px, py = reg[pupil][0]
            put(px, py, "@")
            put(px - 1, py, "(")
            put(px + 1, py, ")")
    # naso: solo la base e le narici, il dorso resta suggerito dalla luce
    if "nose" in reg:
        polyline(reg["nose"])
    # bocca
    if "outerLips" in reg:
        polyline(reg["outerLips"], closed=True)
    if "innerLips" in reg:
        polyline(reg["innerLips"], closed=True, ch="-")

    nose_bottom = max((y for _, y in reg.get("nose", [])), default=rows)
    return feats, face, int(nose_bottom) + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--cols", type=int, default=190)
    ap.add_argument("--crop", help="sinistra,alto,destra,basso in frazioni, es. 0.24,0,0.76,0.46")
    ap.add_argument("--dark", type=float, default=0.35)
    ap.add_argument("--mid", type=float, default=0.45)
    ap.add_argument("--edge", type=float, default=0.18)
    ap.add_argument("--smooth", type=int, default=7)
    ap.add_argument("--calib", help="sinistra,alto,destra,basso in frazioni del ritaglio, es. 0.3,0,0.7,0.55")
    ap.add_argument("--body", choices=["light", "outline", "full"], default="light")
    ap.add_argument("--landmarks")
    ap.add_argument("--no-beard", action="store_true")
    ap.add_argument("--style", choices=["ink", "classic"], default="ink")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--simplify", type=int, default=0)
    ap.add_argument("--hair-smooth", type=int, default=0)
    ap.add_argument("--hair-until", type=float, default=0.3)
    ap.add_argument("--out", default=str(ROOT / "assets" / "portrait.txt"))
    args = ap.parse_args()

    src = ImageOps.exif_transpose(Image.open(args.image)).convert("RGBA")
    ox = oy = 0
    if args.crop:
        l, t, r, b = (float(v) for v in args.crop.split(","))
        ox, oy = round(l * src.width), round(t * src.height)
        src = src.crop((ox, oy, round(r * src.width), round(b * src.height)))

    cols = args.cols
    rows = round(cols * src.height / src.width * CW / CH)
    work = src.resize((cols * CW, rows * CH), Image.LANCZOS)
    alpha = np.asarray(work.getchannel("A"), dtype=float) / 255

    # ammorbidisco: la grana della pelle e del tessuto sparisce, restano le forme
    def simplify(img: Image.Image, k: int) -> Image.Image:
        k = k | 1
        # chiusura (toglie i tratti scuri sottili) e apertura (toglie quelli chiari)
        img = img.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k))
        return img.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))

    base = work.convert("L")
    gray = simplify(base, args.simplify) if args.simplify else base
    if args.hair_smooth:
        hair = simplify(base, args.hair_smooth).filter(ImageFilter.GaussianBlur(args.hair_smooth / 4))
        H = gray.height
        end, fade = args.hair_until * H, 0.06 * H
        w = np.clip((end - np.arange(H)) / fade + 0.5, 0, 1)[:, None]  # 1 sopra, 0 sotto, sfumato
        mixed = np.asarray(hair, dtype=float) * w + np.asarray(gray, dtype=float) * (1 - w)
        gray = Image.fromarray(mixed.astype(np.uint8))
    gray = gray.filter(ImageFilter.MedianFilter(args.smooth | 1)).filter(ImageFilter.GaussianBlur(1.2))
    g = np.asarray(gray, dtype=float) / 255
    inside = alpha > 0.5
    calib = inside.copy()
    region = np.ones_like(inside)
    if args.calib:
        cl, ct, cr, cb = (float(v) for v in args.calib.split(","))
        H, Wd = inside.shape
        region = np.zeros_like(inside)
        region[round(ct * H):round(cb * H), round(cl * Wd):round(cr * Wd)] = True
        calib &= region
    lo, hi = np.percentile(g[calib], [2, 98])
    g = np.clip((g - lo) / max(hi - lo, 1e-6), 0, 1)
    g_plain = g.copy()
    # contrasto locale: il viso in ombra si stacca dal cappello e dagli occhiali
    local = Image.fromarray((g * 255).astype(np.uint8)).filter(ImageFilter.UnsharpMask(radius=60, percent=170, threshold=0))
    g = np.asarray(local, dtype=float) / 255

    # contorni (Sobel)
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    gy[1:-1, :] = g[2:, :] - g[:-2, :]
    mag = np.hypot(gx, gy)
    mag = mag / (np.percentile(mag[calib], 99) or 1)
    ang = np.arctan2(gy, gx)

    def per_cell(a: np.ndarray) -> np.ndarray:
        return a.reshape(rows, CH, cols, CW).swapaxes(1, 2).reshape(rows, cols, CH * CW)

    dark = 1 - per_cell(g).mean(axis=2)
    cover = per_cell(alpha).mean(axis=2)
    if args.style == "classic":
        write(args.out, classic(per_cell(g_plain).mean(axis=2), cover, args), cols, rows)
        return

    cell_mag = per_cell(mag)
    emax = cell_mag.max(axis=2)
    # angolo del punto di contorno piu forte di ogni cella
    eang = np.take_along_axis(per_cell(ang), cell_mag.argmax(axis=2)[..., None], axis=2)[..., 0]

    # soglie calcolate sulla foto: le quote piu scure del soggetto diventano piene
    calib_cells = per_cell(calib.astype(float)).mean(axis=2) >= 0.5
    head_cells = per_cell(region.astype(float)).mean(axis=2) >= 0.5
    subject = dark[calib_cells]
    t_dark = np.quantile(subject, 1 - args.dark)
    t_mid = np.quantile(subject, 1 - args.mid)

    # lineamenti dai punti del viso (facoltativo)
    features: dict[tuple[int, int], str] = {}
    face_cells = np.zeros((rows, cols), dtype=bool)
    beard_from = rows
    if args.landmarks:
        lm = json.loads(Path(args.landmarks).read_text())
        sx, sy = cols * CW / src.width, rows * CH / src.height

        def to_cells(points):
            return [((px - ox) * sx / CW, (py - oy) * sy / CH) for px, py in points]

        reg = {k: to_cells(v) for k, v in lm["regions"].items()}
        features, face_cells, beard_from = draw_face(reg, rows, cols)

    lines = []
    for y in range(rows):
        line = ""
        for x in range(cols):
            c = cover[y, x]
            if (y, x) in features:
                line += features[(y, x)]
                continue
            if c < 0.5:
                line += " "
                continue
            d = dark[y, x]
            if face_cells[y, x]:
                # dentro il viso la foto aggiunge solo la barba, a puntini
                if not args.no_beard and y >= beard_from and d >= t_mid:
                    line += ":" if d >= t_dark else "."
                else:
                    line += " "
                continue
            border = c < 0.95  # bordo della sagoma
            if not head_cells[y, x] and args.body != "full":
                # il busto: contorni e, se "light", una trama leggera al posto del pieno
                if border or emax[y, x] >= args.edge * 1.8:
                    line += edge_char(eang[y, x])
                elif args.body == "light" and d >= t_mid:
                    line += LIGHT[1] if d >= t_dark else LIGHT[0]
                else:
                    line += " "
                continue
            if d >= t_dark:
                k = (d - t_dark) / max(1 - t_dark, 1e-6)
                line += DENSE[min(len(DENSE) - 1, int(k * len(DENSE)))]
            elif emax[y, x] >= args.edge or border:
                line += edge_char(eang[y, x])
            elif d >= t_mid:
                k = (d - t_mid) / max(t_dark - t_mid, 1e-6)
                line += LIGHT[min(len(LIGHT) - 1, int(k * len(LIGHT)))]
            else:
                line += " "
        lines.append(line.rstrip())

    write(args.out, lines, cols, rows)


CLASSIC = " .:-=+*#%@"  # - e = riempiono la cella in orizzontale: il ritratto sembra continuo


def classic(bright: np.ndarray, cover: np.ndarray, args) -> list[str]:
    """ASCII classico: ogni cella prende un carattere piu o meno pieno secondo
    la luminosita, senza linee di contorno."""
    rows, cols = bright.shape
    lines = []
    for y in range(rows):
        line = ""
        for x in range(cols):
            if cover[y, x] < 0.5:
                line += " "
                continue
            v = bright[y, x] ** args.gamma
            if args.invert:
                v = 1 - v
            # dentro la figura almeno un punto, cosi la sagoma resta leggibile
            line += CLASSIC[1 + min(len(CLASSIC) - 2, int(v * (len(CLASSIC) - 1)))]
        lines.append(line.rstrip())
    return lines


def write(path: str, lines: list[str], cols: int, rows: int) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # il ritratto e monocromatico: niente file dei toni
    if out.resolve() == (ROOT / "assets" / "portrait.txt").resolve():
        out.with_name(out.stem + "-tone.txt").unlink(missing_ok=True)
    print(f"{cols}x{rows} -> {out}")


if __name__ == "__main__":
    main()
