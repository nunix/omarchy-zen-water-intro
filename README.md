# omarchy-zen-water-intro

A boot-intro video for [Omarchy](https://omarchy.org/): gold-ink letters of
OMARCHY rise one at a time from ripples on dark water, in a jade palette,
generated procedurally (no stock footage).

Install:

```
omarchy-intro-install https://github.com/nunix/omarchy-zen-water-intro.git
```

This clones the repo to `~/.config/omarchy/intros/zen-water/` and sets it as
the active boot-intro. Switch back to it later with:

```
intro=$(omarchy-intro-switcher); [[ -n $intro ]] && omarchy-intro-set "$intro"
```

or `omarchy-intro-set zen-water` directly.

## Audio

`mrlawrence-6s.wav` is a 6-second excerpt (0:56-1:02) of Ryuichi Sakamoto's
"Merry Christmas Mr. Lawrence", used here for a personal, non-commercial
desktop customization. It is not original work — if you fork this repo for
your own redistribution, swap it for audio you have the rights to use.

## Regenerating intro.mp4

```
uv run --with numpy --with pillow make-intro.py
```

Requires `ffmpeg`, `mrlawrence-6s.wav` alongside the script, and the
`JetBrainsMonoNerdFont-Bold` font.

## Pairs well with

Visually, this fits a dark, muted, natural-tone theme — e.g.
[Osaka Jade](https://omarchy.org/). This is just a suggestion for your own
theme; Omarchy boot-intros aren't tied to a specific theme.
