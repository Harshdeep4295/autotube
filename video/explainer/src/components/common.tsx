import React, { createContext, useContext, useLayoutEffect, useRef } from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT, H, SAFE, W } from "../theme";
import { fitSize } from "../util";
import { Mark } from "../brand/Mark";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// ── debug overflow checks (enabled by the scene tests) ──────────────────────
export const DebugContext = createContext(false);
export const SceneNameContext = createContext("scene");

/**
 * Attach to any element whose content must stay visible. In debug mode it logs
 * "OVERFLOW:<scene>:<id>" if the content is clipped or leaves the safe area.
 * test/scenes.test.mjs fails on those logs.
 */
export const useFitCheck = <T extends HTMLElement>(id: string) => {
  const ref = useRef<T>(null);
  const debug = useContext(DebugContext);
  const scene = useContext(SceneNameContext);
  useLayoutEffect(() => {
    if (!debug || !ref.current) return;
    const el = ref.current;
    const clipped = el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2;
    const r = el.getBoundingClientRect();
    const outside = r.left < -2 || r.right > W + 2 || r.top < -2 || r.bottom > SAFE.bottom + 40;
    if (clipped || outside) {
      console.error(
        `OVERFLOW:${scene}:${id} clipped=${clipped} rect=${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)}`,
      );
    }
  });
  return ref;
};

// ── animation helpers ───────────────────────────────────────────────────────
export const useSpring = (delay = 0, damping = 14) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, mass: 0.7 } });
};

export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const x = 50 + 22 * Math.sin(frame / 150);
  const y = 40 + 16 * Math.cos(frame / 180);
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at ${x}% ${y}%, ${C.bg1} 0%, ${C.bg0} 65%)` }}>
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${C.line} 1.5px, transparent 1.5px)`,
          backgroundSize: "56px 56px",
          backgroundPosition: `${-frame * 0.4}px ${-frame * 0.25}px`,
          opacity: 0.45,
        }}
      />
    </AbsoluteFill>
  );
};

/** Fade/scale in, slow push, fade out — wraps every scene. */
export const SceneFrame: React.FC<{ frames: number; children: React.ReactNode }> = ({ frames, children }) => {
  const frame = useCurrentFrame();
  const inO = interpolate(frame, [0, 9], [0, 1], clamp);
  const outO = interpolate(frame, [frames - 7, frames], [1, 0], clamp);
  const scale = interpolate(frame, [0, frames], [1.0, 1.025]);
  return (
    <AbsoluteFill style={{ opacity: Math.min(inO, outO), transform: `scale(${scale})` }}>{children}</AbsoluteFill>
  );
};

/** Scene heading at the top of the safe area. Auto-fits to one line. */
export const Heading: React.FC<{ text: string; delay?: number }> = ({ text, delay = 0 }) => {
  const s = useSpring(delay);
  const ref = useFitCheck<HTMLDivElement>("heading");
  const size = fitSize(text, 1500, 68, "800");
  return (
    <div
      ref={ref}
      style={{
        position: "absolute", top: SAFE.top + 20, left: 210, width: 1500, textAlign: "center",
        fontFamily: FONT, fontWeight: 800, fontSize: size, color: C.text, whiteSpace: "nowrap",
        opacity: s, transform: `translateY(${(1 - s) * 30}px)`,
      }}
    >
      {text}
    </div>
  );
};

/** Content area below a heading. */
export const Body: React.FC<{ children: React.ReactNode; top?: number; style?: React.CSSProperties }> = ({
  children, top = 250, style,
}) => (
  <div
    style={{
      position: "absolute", top, left: SAFE.left, width: SAFE.right - SAFE.left, height: SAFE.bottom - top,
      display: "flex", alignItems: "center", justifyContent: "center", ...style,
    }}
  >
    {children}
  </div>
);

export const Pill: React.FC<{ children: React.ReactNode; color: string; scale?: number; size?: number }> = ({
  children, color, scale = 1, size = 40,
}) => (
  <div
    style={{
      display: "inline-block", padding: `${size * 0.35}px ${size * 0.85}px`, borderRadius: 999,
      background: `${color}22`, border: `3px solid ${color}`, color, fontFamily: FONT, fontWeight: 800,
      fontSize: size, transform: `scale(${scale})`, whiteSpace: "nowrap",
    }}
  >
    {children}
  </div>
);

export const Progress: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div style={{ position: "absolute", top: 0, left: 0, height: 7, width: `${(frame / durationInFrames) * 100}%`, background: C.yellow }} />
  );
};

export const Watermark: React.FC<{ channel: string }> = ({ channel }) => (
  <div style={{ position: "absolute", top: 22, right: 30, display: "flex", alignItems: "center", gap: 12, opacity: 0.85 }}>
    <Mark size={40} />
    <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 26, color: C.text, letterSpacing: 0.5, whiteSpace: "nowrap" }}>
      {channel}
    </div>
  </div>
);

export { H, W };
