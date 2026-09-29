import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Body, clamp, useFitCheck, useSpring } from "../components/common";
import { C, FONT, MONO } from "../theme";
import { stagger } from "../util";
import { SceneProps } from "./text";

const WindowChrome: React.FC<{ title: string; w: number; h: number; children: React.ReactNode }> = ({ title, w, h, children }) => {
  const s = useSpring(0, 15);
  return (
    <div style={{ width: w, height: h, borderRadius: 26, background: "#070b1f", border: `3px solid ${C.line}`, overflow: "hidden", transform: `scale(${0.92 + 0.08 * s})`, opacity: s }}>
      <div style={{ height: 64, background: "#141c40", display: "flex", alignItems: "center", padding: "0 26px", gap: 12 }}>
        {[C.red, C.yellow, C.green].map((c) => <div key={c} style={{ width: 18, height: 18, borderRadius: 9, background: c }} />)}
        <div style={{ marginLeft: 20, color: C.dim, fontFamily: FONT, fontWeight: 600, fontSize: 28, whiteSpace: "nowrap" }}>{title}</div>
      </div>
      {children}
    </div>
  );
};

// terminal ────────────────────────────────────────────────────────────────────
export const Terminal: React.FC<SceneProps> = ({ props, frames }) => {
  const frame = useCurrentFrame();
  const lines: string[] = props.lines;
  // Give each line a time slot; "$ " lines type out, others appear at once.
  const slot = Math.max(10, Math.min(40, (frames * 0.7) / lines.length));
  const caret = Math.floor(frame / 12) % 2 === 0;
  const ref = useFitCheck<HTMLDivElement>("terminal-body");
  const active = lines.reduce((acc, _l, i) => (frame >= 8 + i * slot ? i : acc), -1);
  const rendered = lines.map((ln, i) => {
    const at = 8 + i * slot;
    if (frame < at) return null;
    const cmd = ln.startsWith("$ ");
    const body = cmd ? ln.slice(2) : ln;
    const shown = cmd ? body.slice(0, Math.floor(interpolate(frame, [at, at + slot * 0.8], [0, body.length], clamp))) : body;
    return (
      <div key={i} style={{ color: cmd ? C.text : C.dim, whiteSpace: "nowrap" }}>
        {cmd ? <span style={{ color: C.green }}>$ </span> : null}
        {shown}
        {i === active && caret ? <span style={{ color: C.yellow }}>▌</span> : null}
      </div>
    );
  });
  return (
    <Body top={120}>
      <WindowChrome title={props.title || "Terminal"} w={1560} h={640}>
        <div ref={ref} style={{ padding: "40px 50px", height: 520, boxSizing: "border-box", overflow: "hidden", fontFamily: MONO, fontSize: 46, lineHeight: 1.75 }}>
          {rendered}
        </div>
      </WindowChrome>
    </Body>
  );
};

// chat ────────────────────────────────────────────────────────────────────────
const Bubble: React.FC<{ i: number; n: number; sender: string; text: string; frames: number }> = ({ i, n, sender, text, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const at = stagger(i, n, frames, 0.6, 10);
  const me = sender === "user";
  const typing = !me && frame > at - 26 && frame < at;
  const s = spring({ frame: frame - at, fps, config: { damping: 13 } });
  const ref = useFitCheck<HTMLDivElement>(`bubble${i}`);
  if (frame < at - 26) return null;
  return (
    <div style={{ display: "flex", justifyContent: me ? "flex-end" : "flex-start", marginBottom: 24 }}>
      {typing ? (
        <div style={{ padding: "22px 36px", borderRadius: 32, background: C.panel2, color: C.dim, fontFamily: FONT, fontSize: 46 }}>
          {"•".repeat(1 + (Math.floor(frame / 6) % 3))}
        </div>
      ) : (
        <div
          ref={ref}
          style={{
            maxWidth: 1280, padding: "20px 34px", borderRadius: 32, background: me ? "#1f6b64" : C.panel2, color: C.text,
            fontFamily: FONT, fontWeight: 600, fontSize: 38, lineHeight: 1.28, transform: `scale(${s})`,
            transformOrigin: me ? "right" : "left", opacity: s,
          }}
        >
          {text}
        </div>
      )}
    </div>
  );
};

export const Chat: React.FC<SceneProps> = ({ props, frames }) => {
  const msgs: { sender: string; text: string }[] = props.messages;
  const ref = useFitCheck<HTMLDivElement>("chat-body");
  return (
    <Body top={120}>
      <WindowChrome title={props.title || "Chat"} w={1500} h={700}>
        <div ref={ref} style={{ padding: "34px 46px", height: 636, boxSizing: "border-box", overflow: "hidden" }}>
          {msgs.map((m, i) => <Bubble key={i} i={i} n={msgs.length} sender={m.sender} text={m.text} frames={frames} />)}
        </div>
      </WindowChrome>
    </Body>
  );
};
