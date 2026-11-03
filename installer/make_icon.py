"""Draws installer/EzPaste.ico (all Windows sizes) and EzPaste.png from scratch with Pillow.
Run: python installer/make_icon.py  — only needed if the design changes."""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 1024  # drawn large, scaled down for each icon size


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def draw(size=S):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    k = size / S

    # Rounded square with a diagonal blue gradient (same blues as the app's edge tab)
    grad = Image.new("RGBA", (size, size))
    top, bottom = (96, 165, 250), (29, 78, 216)  # #60a5fa -> #1d4ed8
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        gd.line([(0, y), (size, y)], fill=lerp(top, bottom, y / (size - 1)) + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([int(40 * k), int(40 * k), int(984 * k), int(984 * k)],
                                           radius=int(220 * k), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # White clipboard
    d.rounded_rectangle([int(250 * k), int(230 * k), int(774 * k), int(860 * k)], radius=int(70 * k),
                        fill=(255, 255, 255, 255))
    # Clip at the top
    d.rounded_rectangle([int(390 * k), int(165 * k), int(634 * k), int(300 * k)], radius=int(45 * k),
                        fill=(30, 41, 59, 255))
    d.rounded_rectangle([int(450 * k), int(205 * k), int(574 * k), int(245 * k)], radius=int(18 * k),
                        fill=(255, 255, 255, 255))

    # Lightning bolt ("quick") in the app's blue
    bolt = [(560, 330), (380, 590), (500, 590), (450, 790), (650, 500), (528, 500), (590, 330)]
    d.polygon([(int(x * k), int(y * k)) for x, y in bolt], fill=(37, 99, 235, 255))
    return img


if __name__ == "__main__":
    big = draw()
    big.resize((256, 256), Image.LANCZOS).save(HERE / "EzPaste.png")
    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.save(HERE / "EzPaste.ico", sizes=sizes)
    print("wrote", HERE / "EzPaste.ico")
