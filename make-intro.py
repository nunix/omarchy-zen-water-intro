# Generate a zen "drops on water" OMARCHY boot intro -> intro.mp4
# Ink-gold letters surface one at a time where a drop lands on dark jade water.
# Audio is an 8s excerpt of Ryuichi Sakamoto's "Merry Christmas Mr. Lawrence"
# (0:56-1:04), placed at MUSIC_START, plus a few synthesized water-drop plinks.
# Run: uv run --with numpy --with pillow make-intro.py
import os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TEXT = "OMARCHY"
FONT = "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Bold.ttf"
MUSIC_CLIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mrlawrence-8s.wav")
OUT_W, OUT_H = 1728, 1116
SCALE = 2  # water-sim downsample factor
W, H = OUT_W // SCALE, OUT_H // SCALE
FPS, DUR = 30, 8.3
MUSIC_START = 0.3
LETTER_START = [0.3, 1.0, 1.7, 2.4, 3.1, 3.8, 4.5]  # one per letter of OMARCHY
# The music clip's own fade-out starts at 7.4s in (baked into the wav) and the
# clip is 8s long, so its fade spans MUSIC_START+7.4 to MUSIC_START+8.0 here.
# Match the visual fade to that window exactly -- no silent hold afterward.
FADE_OUT = MUSIC_START + 7.4

# Osaka Jade palette (~/.config/omarchy/themes/osaka-jade or the stock theme)
BG = np.array([0x11, 0x1C, 0x18], np.float32)
ACCENT = np.array([0x50, 0x94, 0x75], np.float32)
INK = np.array([0xF7, 0xE8, 0xB2], np.float32)  # bright_foreground, molten gold ink

rng = np.random.default_rng(2026)

def blur(a, k):
    for axis in (0, 1):
        a = sum(np.roll(a, d, axis=axis) for d in range(-k, k + 1)) / (2 * k + 1)
    return a

# Slow ambient shimmer across the water, independent of the ripples.
shimmer_noise = blur(rng.random((H, W)).astype(np.float32), 4)
shimmer_noise = (shimmer_noise - shimmer_noise.min()) / np.ptp(shimmer_noise)

def font_for(width, draw):
    size = 10
    while True:
        f = ImageFont.truetype(FONT, size)
        if draw.textbbox((0, 0), TEXT, font=f)[2] > width:
            return ImageFont.truetype(FONT, size - 1)
        size += 1

# --- Lay out the word once at output resolution, then split into per-letter masks ---
probe = ImageDraw.Draw(Image.new("L", (OUT_W, OUT_H)))
font = font_for(int(OUT_W * 0.72), probe)
x0, y0, x1, y1 = probe.textbbox((0, 0), TEXT, font=font)
origin_x = (OUT_W - (x1 - x0)) / 2 - x0
origin_y = (OUT_H - (y1 - y0)) / 2 - y0 + OUT_H * 0.05

letters = []
for i, ch in enumerate(TEXT):
    prefix = TEXT[:i]
    dx = probe.textlength(prefix, font=font)
    img = Image.new("L", (OUT_W, OUT_H), 0)
    ImageDraw.Draw(img).text((origin_x + dx, origin_y), ch, font=font, fill=255)
    mask = np.array(img, np.float32)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        continue
    bx0, bx1 = xs.min(), xs.max()
    by0, by1 = ys.min(), ys.max()
    pad = 60
    cx0, cx1 = max(bx0 - pad, 0), min(bx1 + pad, OUT_W)
    cy0, cy1 = max(by0 - pad, 0), min(by1 + pad, OUT_H)
    crop = mask[cy0:cy1, cx0:cx1]
    cyy, cxx = np.mgrid[cy0:cy1, cx0:cx1]
    # Drop lands at the letter's bottom-center; ink spreads upward from there.
    drop_x, drop_y = (bx0 + bx1) / 2, by1
    dist = np.sqrt((cxx - drop_x) ** 2 + (cyy - drop_y) ** 2)
    letters.append(dict(t0=LETTER_START[i], crop=(cy0, cy1, cx0, cx1),
                         mask=crop, dist=dist, drop=(drop_x, drop_y)))

REVEAL_SPEED = 700.0   # px/sec the ink front races outward
REVEAL_SOFT = 50.0     # px of feathered edge

def text_layer(t):
    """RGBA ink layer (letters + soft glow) at time t, output resolution."""
    alpha = Image.new("L", (OUT_W, OUT_H), 0)
    alpha_arr = np.array(alpha, np.float32)
    for L in letters:
        age = t - L["t0"]
        if age <= 0:
            continue
        radius = REVEAL_SPEED * age
        front = np.clip((radius - L["dist"]) / REVEAL_SOFT, 0, 1)
        cy0, cy1, cx0, cx1 = L["crop"]
        alpha_arr[cy0:cy1, cx0:cx1] = np.maximum(
            alpha_arr[cy0:cy1, cx0:cx1], L["mask"] * front
        )
    alpha_img = Image.fromarray(alpha_arr.astype(np.uint8))
    glow = alpha_img.filter(ImageFilter.GaussianBlur(14))
    layer = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    glow_rgba = Image.new("RGBA", (OUT_W, OUT_H), tuple(ACCENT.astype(int)) + (0,))
    glow_rgba.putalpha(glow.point(lambda v: int(v * 0.55)))
    layer.alpha_composite(glow_rgba)
    fill = Image.new("RGBA", (OUT_W, OUT_H), tuple(INK.astype(int)) + (0,))
    fill.putalpha(alpha_img)
    layer.alpha_composite(fill)
    return layer

def reflection_of(layer, t):
    """Faint, softened mirror of the ink below the baseline, on the water."""
    band_top = int(origin_y + (y1 - y0) * 0.35)
    strip = layer.crop((0, band_top, OUT_W, OUT_H))
    flipped = strip.transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = flipped.split()
    fade = np.linspace(70, 0, flipped.height).clip(0, 255).astype(np.uint8)
    fade_col = np.tile(fade[:, None], (1, OUT_W))
    a = Image.fromarray((np.array(a, np.float32) * (fade_col / 70.0)).astype(np.uint8))
    flipped = Image.merge("RGBA", (r, g, b, a)).filter(ImageFilter.GaussianBlur(6))
    canvas = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    canvas.paste(flipped, (0, band_top + 10), flipped)
    return canvas

# --- Water ripple field: one ring per letter-drop, plus a bright impact flash ---
drops = []
for L in letters:
    gx, gy = L["drop"][0] / SCALE, L["drop"][1] / SCALE
    ys, xs = np.mgrid[0:H, 0:W]
    dist = np.sqrt((xs - gx) ** 2 + (ys - gy) ** 2).astype(np.float32)
    drops.append((L["t0"], dist))

WAVE_SPEED, WAVE_DECAY, WAVE_SIGMA = 140.0 / SCALE, 1.1, 10.0

def water_frame(t):
    ripple = np.zeros((H, W), np.float32)
    flash = np.zeros((H, W), np.float32)
    for t0, dist in drops:
        age = t - t0
        if age <= 0:
            continue
        r = WAVE_SPEED * age
        ring = np.exp(-((dist - r) ** 2) / (2 * WAVE_SIGMA ** 2)) * np.exp(-WAVE_DECAY * age)
        ripple += ring
        if age < 0.2:
            flash += np.exp(-dist / 8.0) * (1 - age / 0.2)
    shimmer = 0.05 * shimmer_noise * (0.6 + 0.4 * np.sin(t * 0.6))
    k = np.clip(ripple + shimmer, 0, 1.4)
    rgb = BG + k[..., None] * (ACCENT - BG) * 0.85
    rgb += np.clip(flash, 0, 1)[..., None] * (INK - BG)
    return np.clip(rgb, 0, 255).astype(np.uint8)

def frames():
    for i in range(int(FPS * DUR)):
        t = i / FPS
        water = Image.fromarray(water_frame(t)).resize((OUT_W, OUT_H), Image.BICUBIC)
        water = water.filter(ImageFilter.GaussianBlur(1.2)).convert("RGBA")
        water.alpha_composite(reflection_of(text_layer(t), t))
        water.alpha_composite(text_layer(t))
        if t >= FADE_OUT:
            k = np.clip((t - FADE_OUT) / (DUR - FADE_OUT), 0, 1)
            black = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, int(255 * k)))
            water.alpha_composite(black)
        yield water.convert("RGB").tobytes()

# --- Audio: the licensed 8s excerpt plus a few synthesized drop plinks ---
SR = 48000
n = int(SR * DUR)
audio = np.zeros(n, np.float32)

with wave.open(MUSIC_CLIP, "rb") as wf:
    sr_in, nch = wf.getframerate(), wf.getnchannels()
    raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if nch > 1:
        raw = raw.reshape(-1, nch).mean(axis=1)
    assert sr_in == SR, f"expected {SR}Hz clip, got {sr_in}"
start = int(MUSIC_START * SR)
end = min(start + len(raw), n)
audio[start:end] += raw[: end - start] * 0.9

t_axis = np.arange(n) / SR
for t0, _ in drops:
    dt = t_axis - t0
    plink = np.sin(2 * np.pi * (1100 - 500 * np.clip(dt, 0, 0.15) / 0.15) * dt) * np.exp(-dt * 18)
    plink *= (dt >= 0) & (dt < 0.3)
    audio += plink * 0.10

audio = np.clip(audio, -1, 1)
with wave.open("/tmp/omarchy-zen-intro.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((audio * 32767).astype(np.int16).tobytes())

ff = subprocess.Popen([
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-",
    "-i", "/tmp/omarchy-zen-intro.wav",
    "-map", "0:v", "-map", "1:a", "-t", str(DUR),
    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
    "intro.mp4",
], stdin=subprocess.PIPE)
for fr in frames():
    ff.stdin.write(fr)
ff.stdin.close()
ff.wait()
print("wrote intro.mp4")
