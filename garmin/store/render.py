"""Connect IQ Store images, redrawn from KumaView / KumaGlanceView (no simulator needed).

Usage: python3 render.py <out_dir>   -> <out_dir>/*.png (English) and <out_dir>/fr/*.png
Monitor names are fictitious.
"""
import math
import os
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]

TEXT = {
    "en": {"updated": "Updated", "all_up": "All up", "down": "down", "no_phone": "No phone\nconnection",
           "retry": "Tap to retry", "tagline": "Your monitors on your wrist"},
    "fr": {"updated": "MAJ", "all_up": "Tout est up", "down": "down", "no_phone": "Pas de connexion\ntéléphone",
           "retry": "Toucher pour réessayer", "tagline": "L'état de vos monitors au poignet"},
}
W = H = 390
REG = "/usr/share/fonts/TTF/Roboto-Regular.ttf"
BOLD = "/usr/share/fonts/TTF/Roboto-Bold.ttf"

# Garmin palette
RED, GREEN, ORANGE, BLUE = (255, 0, 0), (0, 255, 0), (255, 85, 0), (0, 170, 255)
WHITE, LT, DK, BLACK = (255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)

# Font heights from the device's simulator.json (ascent + descent), Roboto em ~ 1.171 of that.
def font(height, path=REG):
    return ImageFont.truetype(path, round(height / 1.171))

XTINY, GLANCE, SMALL, MEDIUM = font(30), font(35), font(45), font(53)
STATUS_COLOR = {0: RED, 1: GREEN, 2: ORANGE, 3: BLUE}

MONITORS = [
    ["ovh-vm", 0], ["mail-relay", 2], ["backup-nas", 3], ["coolify", 1], ["gitea", 1],
    ["grafana", 1], ["home-assistant-raspb", 1], ["immich", 1], ["jellyfin", 1],
    ["nextcloud", 1], ["pihole", 1], ["vaultwarden", 1],
]


def screen():
    img = Image.new("RGB", (W, H), BLACK)
    return img, ImageDraw.Draw(img)


def centered(d, y, f, color, text):
    d.multiline_text((W / 2, y), text, font=f, fill=color, anchor="mm", align="center")


def warning(d, x, y, r, color):
    d.polygon([(x, y - r), (x + r, y + r * 4 // 5), (x - r, y + r * 4 // 5)], fill=color)
    w = r // 4 + 1
    d.rectangle([x - w / 2, y - r / 3, x - w / 2 + w - 1, y - r / 3 + r * 2 / 3 - 1], fill=BLACK)
    d.rectangle([x - w / 2, y + r * 2 / 5, x - w / 2 + w - 1, y + r * 2 / 5 + w - 1], fill=BLACK)


def check(d, x, y, r, color):
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    pw = r // 4 + 1
    d.line([(x - r / 2, y), (x - r / 8, y + r * 3 / 8), (x + r / 2, y - r * 3 / 8)], fill=BLACK, width=pw, joint="curve")


def fit(d, text, f, max_w):
    if d.textlength(text, font=f) <= max_w:
        return text
    while len(text) > 1 and d.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…"


def list_screen(monitors, offset, footer):
    img, d = screen()
    cx, h = W // 2, H
    up = sum(1 for _, s in monitors if s == 1)
    down = sum(1 for _, s in monitors if s == 0)
    color = RED if down else (GREEN if up == len(monitors) else ORANGE)
    centered(d, int(h * 0.13), MEDIUM, color, f"{up}/{len(monitors)} up")

    row_h = 45 + 6
    top, bottom = int(h * 0.23), int(h * 0.77)
    rows = (bottom - top) // row_h
    top += (bottom - top - rows * row_h) // 2
    r = h // 2
    dy = max(r - top, top + rows * row_h - r)
    half = int(math.sqrt(r * r - dy * dy)) - 10
    dot_x = cx - half + 9
    text_x = dot_x + 9 + 10
    text_w = cx + half - text_x
    for i in range(rows):
        if offset + i >= len(monitors):
            break
        name, status = monitors[offset + i]
        y = top + i * row_h + row_h // 2
        d.ellipse([dot_x - 9, y - 9, dot_x + 9, y + 9], fill=STATUS_COLOR[status])
        d.text((text_x, y), fit(d, name, SMALL, text_w), font=SMALL, fill=WHITE, anchor="lm")

    if len(monitors) > rows:
        ar = h // 2 - 5
        box = [cx - ar, h / 2 - ar, cx + ar, h / 2 + ar]
        # Garmin angles are counter-clockwise from 3 o'clock; PIL's are clockwise.
        d.arc(box, -30, 30, fill=DK, width=4)
        start = 30 - 60 * offset / len(monitors)
        length = 60 * rows / len(monitors)
        d.arc(box, -start, -(start - length), fill=LT, width=4)

    centered(d, int(h * 0.86), XTINY, footer[1], footer[0])
    return img


def error_screen(text, retry):
    img, d = screen()
    warning(d, W // 2, int(H * 0.28), 22, RED)
    centered(d, H // 2, SMALL, WHITE, text)
    centered(d, int(H * 0.72), XTINY, LT, retry)
    return img


def glance_screen(down, time, t):
    # Glance content area is 274x146, drawn centred like the system glance loop.
    img, d = screen()
    gx, gy, gh = (W - 274) // 2, (H - 146) // 2, 146
    line_h = 35
    top = gy + (gh - 2 * line_h) // 2
    r = line_h // 3
    text_x = gx + 2 * r + 8
    if down:
        warning(d, gx + r, top + line_h // 2, r, RED)
        d.text((text_x, top), f"{down} {t['down']}", font=GLANCE, fill=RED, anchor="la")
    else:
        check(d, gx + r, top + line_h // 2, r, GREEN)
        d.text((text_x, top), t["all_up"], font=GLANCE, fill=GREEN, anchor="la")
    d.text((gx, top + line_h), f"{t['updated']} {time}", font=GLANCE, fill=LT, anchor="la")
    # Neighbouring glances, dimmed, as on the watch.
    for y in (gy - 70, gy + gh + 30):
        d.rounded_rectangle([gx + 20, y, gx + 254, y + 34], 17, fill=(30, 30, 30))
    return img


def round_mask(img):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, img.width - 1, img.height - 1], fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def render(lang, out):
    t = TEXT[lang]
    os.makedirs(out, exist_ok=True)
    shots = {
        "screenshot-1-list.png": list_screen(MONITORS, 0, (f"{t['updated']} 14:32", LT)),
        "screenshot-2-glance.png": glance_screen(1, "14:32", t),
        "screenshot-3-all-up.png": list_screen([[n, 1] for n, _ in MONITORS], 3, (f"{t['updated']} 09:05", LT)),
        "screenshot-4-error.png": error_screen(t["no_phone"], t["retry"]),
    }
    for name, img in shots.items():
        img.save(f"{out}/{name}")

    # Cover: 1440x720, watch on the right, title on the left.
    cover = Image.new("RGB", (1440, 720), (14, 17, 22))
    cd = ImageDraw.Draw(cover)
    wx, wy, ws = 860, 105, 510
    cd.ellipse([wx - 28, wy - 28, wx + ws + 28, wy + ws + 28], fill=(45, 48, 54))
    cd.ellipse([wx - 8, wy - 8, wx + ws + 8, wy + ws + 8], fill=(8, 8, 8))
    watch = round_mask(shots["screenshot-1-list.png"].resize((ws, ws), Image.LANCZOS))
    cover.paste(watch, (wx, wy), watch)
    cd.text((110, 250), "Uptime Kuma", font=ImageFont.truetype(BOLD, 96), fill=WHITE, anchor="ls")
    cd.text((112, 320), t["tagline"], font=ImageFont.truetype(REG, 40), fill=LT, anchor="ls")
    for i, (label, color) in enumerate([("down", RED), ("pending", ORANGE), ("maintenance", BLUE), ("up", GREEN)]):
        y = 410 + i * 62
        cd.ellipse([112, y - 14, 140, y + 14], fill=color)
        cd.text((162, y), label, font=ImageFont.truetype(REG, 38), fill=WHITE, anchor="lm")
    cover.save(f"{out}/cover.png")


render("en", OUT)
render("fr", f"{OUT}/fr")
