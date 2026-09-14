#!/usr/bin/env python3
"""Render the Voice Panel's lamp images from the approved design.

The shapes are the SVGs in docs/design/voice-panel-screens.html (lampIcon,
bulbIcon, bigLamp), redrawn with Pillow because the ESPHome image can decode
PNG but has no cairosvg for SVG. Drawn at 8x and scaled down, so the edges are
antialiased the way a browser would draw them.

    python3 scripts/render-panel-icons.py

writes configs/esphome/panel/images/{lamp,bulb,dome}_{on,off}.png and movie.png.
"""

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
    for p in sorted(OUT.glob("*.png")):
        print(p.relative_to(OUT.parents[2]), Image.open(p).size)


if __name__ == "__main__":
    main()
