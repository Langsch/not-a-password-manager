/**
 * The padlock asleep on the job, and the wordmark next to it.
 *
 * The drawing is the same one the terminal client shows in its corner
 * (`client/napm/art.py`) — spelled out rather than generated, and the padlock's
 * halves are still mirrors of each other, so an edit on the left needs the same
 * edit on the right with `/\()[]<>` flipped.
 *
 * The loop is 120 frames and every moving value returns to its frame-0 state by
 * then, so the GIF repeats with no visible seam. Anything animated here has to
 * either finish before frame 120 or have a period that divides it.
 */

import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

export const DURATION = 120;
export const FPS = 30;
export const WIDTH = 1200;
export const HEIGHT = 360;

// Rendering happens in headless Chrome on the machine that runs the render, so
// the font only has to exist there — the GIF carries pixels, not text.
const MONO = '"JetBrains Mono", "DejaVu Sans Mono", "Noto Sans Mono", monospace';

const INK = "#7ee787";
const MUTED = "#8b949e";
const ALARM = "#f0883e";
const PAPER = "#0d1117";

// The shackle, closed and sprung. Both are eight columns wide on the second
// line so the body underneath never has to move with them.
//
// Unlike `art.py`, these carry no left margin: the drawing is placed by the
// layout here, and leading spaces would only push it off its own box.
const SHACKLE_CLOSED = ["   .--.", " / |  | \\"];
const SHACKLE_SPRUNG = ["  .-''-.", " /|    |\\"];

const BODY_TOP = ".--'--'--.";
const BODY_BOTTOM = "'--------'";

const WORDMARK = [
  "  ___  ___ ____  __ _",
  " / _ \\/ _ `/ _ \\/  ' \\",
  "/_//_/\\_,_/ .__/_/_/_/",
  "         /_/",
];

const LEGEND = "definitely not a password manager";

/** The eyes, over the beat: shut, startled, blinking down, shut again. */
function eyes(frame: number): string {
  if (frame < 75) {
    return "^  ^";
  }

  if (frame < 92) {
    return "O  O";
  }

  if (frame < 99) {
    return "o  o";
  }

  if (frame < 105) {
    return "-  -";
  }

  return "^  ^";
}

function shackle(frame: number): string[] {
  if (frame >= 75 && frame < 93) {
    return SHACKLE_SPRUNG;
  }

  return SHACKLE_CLOSED;
}

function mascot(frame: number): string {
  const lines = [...shackle(frame), BODY_TOP, `|  ${eyes(frame)}  |`, BODY_BOTTOM];

  return lines.join("\n");
}

/**
 * How far the whole padlock has jumped, in pixels.
 *
 * Up hard on the fright, past the resting line on the way down, then settled.
 * Zero everywhere outside the jolt, which is what lets the loop close.
 */
function jump(frame: number): number {
  return interpolate(frame, [75, 79, 86, 96], [0, -14, 3, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
}

/** The shiver after the jump: a sine that runs out of energy by frame 95. */
function shiver(frame: number): number {
  if (frame < 79 || frame > 95) {
    return 0;
  }

  const age = frame - 79;
  const fading = 1 - age / 16;

  return Math.sin(age * 1.9) * 3.4 * fading;
}

/** The sleeping rise and fall: two whole cycles per loop, so it closes. */
function breathe(frame: number): number {
  return Math.sin((frame / DURATION) * Math.PI * 4) * 2;
}

/**
 * One drifting `z`.
 *
 * The period is 60, which divides the 120-frame loop — that is the only reason
 * these can keep moving across the seam without a jump.
 */
const Zed: React.FC<{ frame: number; offset: number; group: number }> = ({
  frame,
  offset,
  group,
}) => {
  const age = (frame + offset) % 60;
  const progress = age / 60;

  const opacity = interpolate(progress, [0, 0.2, 0.7, 1], [0, 1, 0.7, 0]) * group;
  const size = interpolate(progress, [0, 1], [0.7, 1.25]);

  // Clear of the drawing on purpose: the padlock ends at x=241, so the z's
  // start to the right of it and drift up and away.
  return (
    <span
      style={{
        position: "absolute",
        left: 244 + progress * 52,
        top: 118 - progress * 92,
        color: INK,
        fontFamily: MONO,
        fontSize: 30 * size,
        opacity,
      }}
    >
      z
    </span>
  );
};

export const Mascot: React.FC = () => {
  const frame = useCurrentFrame();

  // The z's stop while the padlock is awake, and are back before the loop ends.
  const dreaming = interpolate(frame, [70, 76, 110, 118], [1, 0, 0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bangOpacity =
    interpolate(frame, [74, 76], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }) *
    interpolate(frame, [88, 93], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

  const bangScale = interpolate(frame, [74, 77, 81], [0, 1.4, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: PAPER,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 64,
      }}
    >
      <div style={{ position: "relative", width: 320, height: 260 }}>
        <Zed frame={frame} offset={0} group={dreaming} />
        <Zed frame={frame} offset={20} group={dreaming} />
        <Zed frame={frame} offset={40} group={dreaming} />

        <span
          style={{
            position: "absolute",
            left: 252,
            top: 22,
            color: ALARM,
            fontFamily: MONO,
            fontSize: 52,
            fontWeight: 700,
            opacity: bangOpacity,
            transform: `scale(${bangScale})`,
          }}
        >
          !
        </span>

        <pre
          style={{
            position: "absolute",
            left: 0,
            bottom: 0,
            margin: 0,
            color: INK,
            fontFamily: MONO,
            fontSize: 40,
            lineHeight: 1.25,
            letterSpacing: 0,
            transform: `translate(${shiver(frame)}px, ${jump(frame) + breathe(frame)}px)`,
          }}
        >
          {mascot(frame)}
        </pre>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <pre
          style={{
            margin: 0,
            color: INK,
            fontFamily: MONO,
            fontSize: 40,
            lineHeight: 1.25,
            letterSpacing: 0,
          }}
        >
          {WORDMARK.join("\n")}
        </pre>

        <span
          style={{
            color: MUTED,
            fontFamily: MONO,
            fontSize: 22,
            fontStyle: "italic",
            letterSpacing: 0.5,
          }}
        >
          {LEGEND}
        </span>
      </div>
    </AbsoluteFill>
  );
};
