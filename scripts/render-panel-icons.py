#!/usr/bin/env python3
"""Render the Voice Panel's lamp images from the approved design.

The shapes are the SVGs in docs/design/voice-panel-screens.html (lampIcon,
bulbIcon, bigLamp), redrawn with Pillow because the ESPHome image can decode
PNG but has no cairosvg for SVG. Drawn at 8x and scaled down, so the edges are
antialiased the way a browser would draw them.

    python3 scripts/render-panel-icons.py

writes configs/esphome/panel/images/{lamp,bulb,dome}_{on,off}.png movie.png, the Security icons, the launcher app tiles and its weather icons.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "configs/esphome/panel/images"
SS = 8  # supersampling factor


def rgba(hex_colour: str, alpha: float = 1.0) -> tuple[int, int, int, int]:
    h = hex_colour.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), round(alpha * 255))


def canvas(view: float, size: int):
    """A transparent canvas where one design unit is `k` pixels."""
    px = size * SS
    return Image.new("RGBA", (px, px), (0, 0, 0, 0)), px / view


def finish(img: Image.Image, size: int, name: str) -> None:
    img.resize((size, size), Image.LANCZOS).save(OUT / name)


def ellipse(draw, k, cx, cy, rx, ry, fill):
    draw.ellipse([(cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k], fill=fill)


def layer(img: Image.Image) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    return over, ImageDraw.Draw(over)


def lamp_icon(on: bool, size: int = 58) -> None:
    """lampIcon: viewBox 40, a dome lamp on its cord."""
    img, k = canvas(40, size)
    d = ImageDraw.Draw(img)
    d.line([(20 * k, 0), (20 * k, 9 * k)], fill=rgba("#D6DDE6"), width=round(1.4 * k))
    d.rounded_rectangle([17 * k, 8.5 * k, 23 * k, 13.5 * k], radius=k, fill=rgba("#C8955B"))
    # M6 27a14 13.5 0 0 1 28 0z - the top half of an ellipse centred at (20, 27)
    d.pieslice([6 * k, 13.5 * k, 34 * k, 40.5 * k], 180, 360, fill=rgba("#EEF1F5"))
    if on:
        over, od = layer(img)
        # .28 in the design, over a light card; over the panel's grey card it
        # reads as a dark smudge, so it is brighter here.
        ellipse(od, k, 20, 33, 12, 5, rgba("#FFD98A", 0.45))
        img = Image.alpha_composite(img, over)
        d = ImageDraw.Draw(img)
    ellipse(d, k, 20, 28, 4.4, 2.6, rgba("#FFD98A" if on else "#B9C0C9"))
    finish(img, size, f"lamp_{'on' if on else 'off'}.png")


def bulb_icon(on: bool, size: int = 40) -> None:
    """bulbIcon: viewBox 24, stroked outline of a bulb."""
    img, k = canvas(24, size)
    d = ImageDraw.Draw(img)
    colour = rgba("#F7D27E" if on else "#C7CED8")
    w = round(2 * k)
    # the globe: a circle of radius 6 around (12, 9), open at the bottom
    d.arc([6 * k, 3 * k, 18 * k, 15 * k], 130, 50, fill=colour, width=w)
    # the neck down to the collar at y=16
    d.line([(8.2 * k, 13.6 * k), (9 * k, 16 * k)], fill=colour, width=w)
    d.line([(15.8 * k, 13.6 * k), (15 * k, 16 * k)], fill=colour, width=w)
    d.line([(9 * k, 16 * k), (15 * k, 16 * k)], fill=colour, width=w)
    # M9 18h6 M10 21h4
    d.line([(9 * k, 18.5 * k), (15 * k, 18.5 * k)], fill=colour, width=w)
    d.line([(10 * k, 21 * k), (14 * k, 21 * k)], fill=colour, width=w)
    finish(img, size, f"bulb_{'on' if on else 'off'}.png")


def movie_icon(size: int = 40) -> None:
    """The Movie mode scene's art: viewBox 24, a clapperboard in #B9A8F2."""
    img, k = canvas(24, size)
    d = ImageDraw.Draw(img)
    colour = rgba("#B9A8F2")
    w = round(2 * k)
    # rect x=3 y=6 w=18 h=12 rx=2; M3 10h18; M7 6l2 4 M12 6l2 4 M17 6l2 4
    d.rounded_rectangle([3 * k, 6 * k, 21 * k, 18 * k], radius=round(2 * k), outline=colour, width=w)
    d.line([(3 * k, 10 * k), (21 * k, 10 * k)], fill=colour, width=w)
    for x in (7, 12, 17):
        d.line([(x * k, 6 * k), ((x + 2) * k, 10 * k)], fill=colour, width=w)
    finish(img, size, "movie.png")


def stroke_icon(name: str, draw_fn, colour: str = "#F2F5F8", alpha: float = 0.85, size: int = 32) -> None:
    """A stroked 24-unit icon from the design's Security page."""
    img, k = canvas(24, size)
    draw_fn(ImageDraw.Draw(img), k, rgba(colour, alpha), round(2 * k))
    finish(img, size, f"{name}.png")


def _person(d, k, c, w):
    # circle cx=12 cy=7 r=3; M6 20c.5-4 3-6 6-6s5.5 2 6 6
    d.ellipse([9 * k, 4 * k, 15 * k, 10 * k], outline=c, width=w)
    d.arc([6 * k, 14 * k, 18 * k, 26 * k], 180, 360, fill=c, width=w)


def _door(d, k, c, w):
    # M5 21V4h11l3 2v15; M13 12h1
    d.line([(5 * k, 21 * k), (5 * k, 4 * k), (16 * k, 4 * k), (19 * k, 6 * k), (19 * k, 21 * k)],
           fill=c, width=w, joint="curve")
    d.line([(13 * k, 12 * k), (14 * k, 12 * k)], fill=c, width=w)


def _window(d, k, c, w):
    # rect 4,4 16x16 rx1.5; M12 4v16 M4 12h16
    d.rounded_rectangle([4 * k, 4 * k, 20 * k, 20 * k], radius=round(1.5 * k), outline=c, width=w)
    d.line([(12 * k, 4 * k), (12 * k, 20 * k)], fill=c, width=w)
    d.line([(4 * k, 12 * k), (20 * k, 12 * k)], fill=c, width=w)


def _smoke(d, k, c, w):
    # A flame: the design's path, approximated with two arcs and a tip.
    d.arc([6 * k, 9 * k, 18 * k, 21 * k], 150, 30, fill=c, width=w)
    d.line([(6.8 * k, 12 * k), (10 * k, 7 * k), (12 * k, 3 * k), (14 * k, 7 * k), (17.2 * k, 12 * k)],
           fill=c, width=w, joint="curve")


def _garage(d, k, c, w):
    # M3 10l9-6 9 6v10H3z; M7 20v-6h10v6
    d.line([(3 * k, 20 * k), (3 * k, 10 * k), (12 * k, 4 * k), (21 * k, 10 * k), (21 * k, 20 * k), (3 * k, 20 * k)],
           fill=c, width=w, joint="curve")
    d.line([(7 * k, 20 * k), (7 * k, 14 * k), (17 * k, 14 * k), (17 * k, 20 * k)], fill=c, width=w, joint="curve")


def _shield(tick: bool):
    def draw(d, k, c, w):
        # M12 3l7 3v5c0 5-3 8.5-7 10-4-1.5-7-5-7-10V6z, then a tick or a "!"
        outline = [(12, 3), (19, 6), (19, 11), (18.2, 15), (15.5, 18.6), (12, 21),
                   (8.5, 18.6), (5.8, 15), (5, 11), (5, 6), (12, 3)]
        d.line([(x * k, y * k) for x, y in outline], fill=c, width=round(w * 0.9), joint="curve")
        if tick:
            d.line([(9 * k, 12 * k), (11 * k, 14 * k), (15 * k, 10 * k)], fill=c, width=w, joint="curve")
        else:
            d.line([(12 * k, 8 * k), (12 * k, 13 * k)], fill=c, width=w)
            d.ellipse([11 * k, 15 * k, 13 * k, 17 * k], fill=c)
    return draw


def security_icons() -> None:
    for name, fn in (("person", _person), ("door", _door), ("window", _window),
                     ("smoke", _smoke), ("garage", _garage)):
        stroke_icon(name, fn)
    stroke_icon("shield_ok", _shield(True), colour="#9EE6C5", alpha=1.0, size=52)
    stroke_icon("shield_alert", _shield(False), colour="#FFB3A2", alpha=1.0, size=52)


APP_TILES = {
    # name: (top colour, bottom colour) - the launcher's tints, from the design
    "lights": ("#F7C55A", "#D98A1C"),
    "climate": ("#54D1BF", "#1F8A87"),
    "scenes": ("#A993F5", "#6247CF"),
    "security": ("#6BD49E", "#2A8561"),
    "cameras": ("#6C9CF2", "#2E5EC2"),
    "panel": ("#8E97A6", "#4B5361"),
    "settings": ("#F59A7A", "#D0583E"),
}


def app_icon(name: str, size: int = 92) -> None:
    """One launcher tile: a tinted rounded square with the app's glyph in white.

    The glyphs are the design's 24-unit icons, drawn 2x in the middle 48 px.
    """
    px = size * SS
    k = px / size                        # supersampled pixels per final pixel
    top, bottom = APP_TILES[name]
    tile = vertical_gradient((px, px), rgba(top), rgba(bottom))
    mask = Image.new("L", (px, px), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, px - 1, px - 1], radius=round(26 * k), fill=255)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    img.paste(tile, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([k, k, px - 1 - k, px - 1 - k], radius=round(25 * k),
                        outline=rgba("#FFFFFF", 0.16), width=round(1.5 * k))

    u = 2 * k                            # one glyph unit
    off = 22 * k                         # glyph box starts 22 px in

    def p(x, y):
        return (off + x * u, off + y * u)

    white = rgba("#FFFFFF")
    w = round(2 * u)
    if name == "lights":
        d.arc([*p(6, 3), *p(18, 15)], 130, 50, fill=white, width=w)
        d.line([p(8.2, 13.6), p(9, 16), p(15, 16), p(15.8, 13.6)], fill=white, width=w, joint="curve")
        d.line([p(9, 18.5), p(15, 18.5)], fill=white, width=w)
        d.line([p(10, 21), p(14, 21)], fill=white, width=w)
    elif name == "climate":
        d.rounded_rectangle([*p(10, 3), *p(14, 15)], radius=round(2 * u), outline=white, width=w)
        d.ellipse([*p(8, 13.5), *p(16, 21.5)], outline=white, width=w)
        d.line([p(12, 8), p(12, 16)], fill=white, width=w)
    elif name == "scenes":
        star = [(12, 3), (14.4, 8), (20, 8.8), (16, 12.7), (16.9, 18.2), (12, 15.6),
                (7.1, 18.2), (8, 12.7), (4, 8.8), (9.6, 8), (12, 3)]
        d.line([p(x, y) for x, y in star], fill=white, width=w, joint="curve")
    elif name == "security":
        shield = [(12, 3), (19, 6), (19, 11), (18.2, 15), (15.5, 18.6), (12, 21),
                  (8.5, 18.6), (5.8, 15), (5, 11), (5, 6), (12, 3)]
        d.line([p(x, y) for x, y in shield], fill=white, width=w, joint="curve")
        d.line([p(9, 12), p(11, 14), p(15, 10)], fill=white, width=w, joint="curve")
    elif name == "cameras":
        d.rounded_rectangle([*p(3, 7), *p(16, 17)], radius=round(2 * u), outline=white, width=w)
        d.line([p(16, 11), p(21, 8), p(21, 16), p(16, 13), p(16, 11)], fill=white, width=w, joint="curve")
    elif name == "panel":
        d.rounded_rectangle([*p(3, 4), *p(21, 17)], radius=round(2 * u), outline=white, width=w)
        d.line([p(8, 21), p(16, 21)], fill=white, width=w)
        d.line([p(12, 17), p(12, 21)], fill=white, width=w)
    elif name == "settings":
        # A gear: a solid wheel with eight square teeth and a hole in the middle.
        for i in range(8):
            a = math.radians(i * 45)
            d.line([p(12, 12), p(12 + 9 * math.cos(a), 12 + 9 * math.sin(a))], fill=white, width=round(3.2 * u))
        d.ellipse([*p(5, 5), *p(19, 19)], fill=white)
        top_colour = vertical_gradient((1, px), rgba(top), rgba(bottom)).getpixel((0, px // 2))
        d.ellipse([*p(9, 9), *p(15, 15)], fill=top_colour)
    finish(img, size, f"app_{name}.png")


# The launcher's weather, one picture per group of Home Assistant conditions
# (voice-panel.yaml, weather_refresh, maps each condition to one of these).
WEATHER_ICONS = ("sunny", "night", "partlycloudy", "cloudy", "rainy", "snowy", "lightning", "fog", "windy")
SUN = "#FFC94A"
CLOUD = "#E8EDF3"


def _sun(d, k, cx, cy, r):
    ellipse(d, k, cx, cy, r, r, rgba(SUN))
    for i in range(8):
        a = math.radians(i * 45)
        d.line([((cx + (r + 1.4) * math.cos(a)) * k, (cy + (r + 1.4) * math.sin(a)) * k),
                ((cx + (r + 3.2) * math.cos(a)) * k, (cy + (r + 3.2) * math.sin(a)) * k)],
               fill=rgba(SUN), width=round(1.6 * k))


def _cloud(d, k, dx=0.0, dy=0.0):
    c = rgba(CLOUD)
    ellipse(d, k, 9 + dx, 13 + dy, 4.2, 4.2, c)
    ellipse(d, k, 14.5 + dx, 11 + dy, 5.5, 5.5, c)
    d.rounded_rectangle([(4.5 + dx) * k, (13 + dy) * k, (20.5 + dx) * k, (18.5 + dy) * k],
                        radius=round(2.75 * k), fill=c)


def weather_icon(name: str, size: int = 64) -> None:
    """A filled 24-unit weather picture, bright enough for the launcher's dark ground."""
    img, k = canvas(24, size)
    d = ImageDraw.Draw(img)
    if name == "sunny":
        _sun(d, k, 12, 12, 4.5)
    elif name == "night":
        # a crescent: a disc with an offset disc taken out of it
        mask = Image.new("L", img.size, 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([5 * k, 5 * k, 19 * k, 19 * k], fill=255)
        md.ellipse([9.5 * k, 2 * k, 23.5 * k, 16 * k], fill=0)
        img.paste(Image.new("RGBA", img.size, rgba("#E6E9F0")), (0, 0), mask)
    elif name == "partlycloudy":
        _sun(d, k, 8.5, 8.5, 3.2)
        _cloud(d, k, 1.5, 2.5)
    elif name == "cloudy":
        _cloud(d, k)
    elif name in ("rainy", "snowy", "lightning"):
        _cloud(d, k, 0, -3.5)
        if name == "rainy":
            for x in (8.5, 12.5, 16.5):
                d.line([(x * k, 17 * k), ((x - 1.3) * k, 21 * k)], fill=rgba("#7FB8FF"), width=round(1.8 * k))
        elif name == "snowy":
            for x, y in ((8.5, 18.5), (12.5, 20.5), (16.5, 18.5)):
                ellipse(d, k, x, y, 1.2, 1.2, rgba("#FFFFFF"))
        else:
            d.polygon([(13 * k, 14.5 * k), (9.5 * k, 19.5 * k), (12 * k, 19.5 * k), (10.5 * k, 23.5 * k),
                       (15.5 * k, 17.5 * k), (13 * k, 17.5 * k), (14.5 * k, 14.5 * k)], fill=rgba(SUN))
    elif name == "fog":
        for i, y in enumerate((8, 12, 16)):
            d.line([((4 + 2 * (i % 2)) * k, y * k), ((20 - 2 * (i % 2)) * k, y * k)],
                   fill=rgba("#C9D1DB"), width=round(2 * k))
    elif name == "windy":
        c = rgba("#D6DEE8")
        for (x0, x1, y) in ((3, 16, 8), (6, 21, 12), (3, 14, 16)):
            d.line([(x0 * k, y * k), (x1 * k, y * k)], fill=c, width=round(2 * k))
    finish(img, size, f"weather_{name}.png")


def vertical_gradient(size, top, bottom) -> Image.Image:
    grad = Image.new("RGBA", (1, 256))
    for y in range(256):
        t = y / 255
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return grad.resize(size)


def dome_lamp(on: bool, size: int = 260) -> None:
    """bigLamp: viewBox 200, the full-screen light page's lamp."""
    img, k = canvas(200, size)
    if on:
        # radialGradient glow: #FFE1A0 at .75 fading out below the dome. The
        # design's glow runs past its own viewBox; drawn that size here it was
        # cut off by the image edges into a visible rectangle, so it is smaller
        # and faded to nothing before the bottom edge.
        over, od = layer(img)
        ellipse(od, k, 100, 150, 66, 34, rgba("#FFE1A0", 0.75))
        over = over.filter(ImageFilter.GaussianBlur(14 * k))
        fade = Image.new("L", over.size, 0)
        fd = ImageDraw.Draw(fade)
        for y in range(over.size[1]):
            t = (y / k - 150) / (196 - 150)
            fd.line([(0, y), (over.size[0], y)], fill=round(255 * min(1.0, max(0.0, 1 - t))))
        alpha = Image.eval(over.getchannel("A"), lambda v: v)
        over.putalpha(Image.composite(alpha, Image.new("L", over.size, 0), fade))
        img = Image.alpha_composite(img, over)
    d = ImageDraw.Draw(img)
    d.line([(100 * k, 0), (100 * k, 62 * k)], fill=rgba("#E3E8EE"), width=round(1.6 * k))

    wood = vertical_gradient((round(14 * k), round(16 * k)), rgba("#B7844E"), rgba("#DDAA6E"))
    wood = wood.transpose(Image.Transpose.ROTATE_90)  # the design's gradient runs left to right
    wood = wood.resize((round(14 * k), round(16 * k)))
    mask = Image.new("L", wood.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, wood.size[0] - 1, wood.size[1] - 1], radius=round(2 * k), fill=255)
    img.paste(wood, (round(93 * k), round(58 * k)), mask)

    # M38 128a62 58 0 0 1 124 0z - top half of an ellipse centred at (100, 128)
    box = [round(38 * k), round(70 * k), round(162 * k), round(186 * k)]
    dome = vertical_gradient((box[2] - box[0], round(58 * k)), rgba("#FFFFFF"), rgba("#C9CFD7"))
    mask = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
    ImageDraw.Draw(mask).pieslice([0, 0, mask.size[0] - 1, mask.size[1] - 1], 180, 360, fill=255)
    mask = mask.crop((0, 0, mask.size[0], round(58 * k)))
    img.paste(dome, (box[0], box[1]), mask)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([38 * k, 126 * k, 162 * k, 130 * k], radius=round(2 * k), fill=rgba("#AEB5BE"))
    if on:
        over, od = layer(img)
        ellipse(od, k, 100, 134, 18, 18, rgba("#FFE1A0", 0.35))
        img = Image.alpha_composite(img, over)
        d = ImageDraw.Draw(img)
    ellipse(d, k, 100, 134, 10, 10, rgba("#FFE7B0" if on else "#DDE1E7"))
    finish(img, size, f"dome_{'on' if on else 'off'}.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for on in (True, False):
        lamp_icon(on)
        bulb_icon(on)
        dome_lamp(on)
    movie_icon()
    security_icons()
    for name in APP_TILES:
        app_icon(name)
    for name in WEATHER_ICONS:
        weather_icon(name)
    for p in sorted(OUT.glob("*.png")):
        print(p.relative_to(OUT.parents[2]), Image.open(p).size)


if __name__ == "__main__":
    main()
