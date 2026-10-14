"""Batch-convert .piskel files to PNG + GIF (Pillow only).

    python3 tools/piskel_export.py [DIR] [--scale N] [--out DIR]

Finds every .piskel under DIR (default: the current folder, recursive) and writes, next to each
source (or into --out):
    <name>.png     horizontal spritesheet of all frames
    <name>_f0.png  first frame only
    <name>.gif     animated, 1000/fps ms per frame, loops forever, transparency kept
<name> is the sprite name stored in the .piskel. Offline only: no network.
"""
import base64
import io
import json
import os
import sys

from PIL import Image


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def decode_png(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGBA")


def layer_frames(layer, width, height):
    """One layer -> list of RGBA frames, indexed by frame number."""
    count = layer["frameCount"]
    frames = [None] * count
    # Older files: a single horizontal strip on the layer itself.
    chunks = layer.get("chunks") or [{"layout": [[i] for i in range(count)], "base64PNG": layer["base64PNG"]}]
    for chunk in chunks:
        sheet = decode_png(chunk["base64PNG"])
        # layout is a list of columns; each column lists frame indices top to bottom.
        for col, column in enumerate(chunk["layout"]):
            for row, index in enumerate(column):
                x, y = col * width, row * height
                frames[index] = sheet.crop((x, y, x + width, y + height))
    missing = [i for i, f in enumerate(frames) if f is None]
    if missing:
        raise ValueError(f"layer {layer.get('name')!r} has no image for frames {missing}")
    return frames


def apply_opacity(img, opacity):
    if opacity >= 1:
        return img
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r, g, b, a.point(lambda v: round(v * opacity))))


def load_piskel(path):
    """-> (name, fps, width, height, [RGBA frames]) with all layers composited bottom to top."""
    with open(path) as f:
        piskel = json.load(f)["piskel"]
    width, height = piskel["width"], piskel["height"]
    layers = [json.loads(l) if isinstance(l, str) else l for l in piskel["layers"]]
    count = max(l["frameCount"] for l in layers)
    frames = [Image.new("RGBA", (width, height), (0, 0, 0, 0)) for _ in range(count)]
    for layer in layers:  # layers[0] is the bottom layer
        opacity = float(layer.get("opacity", 1))
        for i, img in enumerate(layer_frames(layer, width, height)):
            frames[i] = Image.alpha_composite(frames[i], apply_opacity(img, opacity))
    name = piskel.get("name") or os.path.splitext(os.path.basename(path))[0]
    return name, piskel.get("fps") or 12, width, height, frames


def save_gif(frames, path, fps):
    """Animated GIF with transparency: map fully transparent pixels to one reserved palette index."""
    paletted = []
    for frame in frames:
        alpha = frame.getchannel("A")
        p = frame.convert("RGB").quantize(colors=255, method=Image.Quantize.FASTOCTREE)
        p.putpalette(p.getpalette()[: 255 * 3] + [0, 0, 0])
        p.paste(255, mask=alpha.point(lambda v: 255 if v < 128 else 0))
        p.info["transparency"] = 255
        paletted.append(p)
    paletted[0].save(path, save_all=True, append_images=paletted[1:], duration=round(1000 / fps),
                     loop=0, disposal=2, transparency=255, optimize=False)


def export(path, scale, out_dir):
    name, fps, width, height, frames = load_piskel(path)
    if scale != 1:
        frames = [f.resize((width * scale, height * scale), Image.Resampling.NEAREST) for f in frames]
    w, h = width * scale, height * scale
    dest = out_dir or os.path.dirname(path)
    os.makedirs(dest, exist_ok=True)
    sheet = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * w, 0))
    sheet.save(os.path.join(dest, f"{name}.png"))
    frames[0].save(os.path.join(dest, f"{name}_f0.png"))
    save_gif(frames, os.path.join(dest, f"{name}.gif"), fps)
    return name, len(frames), f"{w}x{h}", fps


def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1)
            if not a.startswith("--") and sys.argv[i - 1] not in ("--scale", "--out")]
    root = args[0] if args else "."
    scale = int(arg("--scale", 1))
    out_dir = arg("--out")
    paths = sorted(os.path.join(d, f) for d, _, files in os.walk(root) for f in files if f.endswith(".piskel"))
    if not paths:
        raise SystemExit(f"No .piskel files under {os.path.abspath(root)}")
    rows = []
    for path in paths:
        try:
            rows.append((os.path.relpath(path, root), *export(path, scale, out_dir)))
        except Exception as e:  # one bad file shouldn't stop the batch
            print(f"FAILED {path}: {e}")
    print(f"\n{'File':<45} {'Name':<16} {'Frames':>6} {'Size':>9} {'FPS':>4}")
    for file, name, count, size, fps in rows:
        print(f"{file:<45} {name:<16} {count:>6} {size:>9} {fps:>4}")


if __name__ == "__main__":
    main()
