# The README animation

The padlock that sleeps at the top of the repository's `README.md`, drawn as
1200×360, 30fps, 120 frames — four seconds that loop forever.

```bash
npm install
npm run render     # writes ../napm.gif
npm run dev        # the Remotion studio, for changing it
```

**Do not pass `--number-of-gif-loops`.** It sets a finite repeat count, and `0`
means "play once and stop", not "loop forever". Leaving it off is what writes the
`NETSCAPE2.0` block that makes the GIF repeat. Check it with:

```bash
grep -c NETSCAPE2.0 ../napm.gif
```

The drawing is the same padlock the terminal client shows in its corner
(`client/napm/art.py`). That file stays the source of truth for the shape; this
one only makes it move. The font has to exist on the machine doing the render and
nowhere else — the GIF carries pixels.

Nothing here is part of running the project. `docker compose` never sees it.
