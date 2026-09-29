import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CAPTIONS, SCENES } from "./data";

const FPS = 30;
const C = {
  bg0: "#070b1a",
  bg1: "#111a3a",
  panel: "#151f45",
  line: "#2a3a73",
  text: "#f4f6fb",
  dim: "#9aa6c8",
  yellow: "#ffd23f",
  cyan: "#4fd1c5",
  red: "#ff5d6c",
  green: "#5be49b",
};
const FONT = "'Liberation Sans', 'DejaVu Sans', Arial, sans-serif";
const MONO = "'DejaVu Sans Mono', 'Liberation Mono', monospace";

// ── helpers ─────────────────────────────────────────────────────────────────

const useSpring = (delay = 0, damping = 14) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, mass: 0.7 } });
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Scene: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const frame = useCurrentFrame();
  const total = Math.round(dur * FPS);
  const inO = interpolate(frame, [0, 10], [0, 1], clamp);
  const outO = interpolate(frame, [total - 8, total], [1, 0], clamp);
  const scale = interpolate(frame, [0, total], [1.0, 1.03]);
  return (
    <AbsoluteFill style={{ opacity: Math.min(inO, outO), transform: `scale(${scale})` }}>{children}</AbsoluteFill>
  );
};

const Title: React.FC<{ children: React.ReactNode; delay?: number; y?: number }> = ({ children, delay = 0, y = 120 }) => {
  const s = useSpring(delay);
  return (
    <div
      style={{
        position: "absolute", top: y, width: "100%", textAlign: "center", fontFamily: FONT,
        fontWeight: 700, fontSize: 64, color: C.text, letterSpacing: 1,
        opacity: s, transform: `translateY(${(1 - s) * 30}px)`,
      }}
    >
      {children}
    </div>
  );
};

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const x = 50 + 20 * Math.sin(frame / 140);
  const y = 40 + 15 * Math.cos(frame / 170);
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at ${x}% ${y}%, ${C.bg1} 0%, ${C.bg0} 65%)`,
      }}
    >
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

// ── reusable illustrations ─────────────────────────────────────────────────

const Laptop: React.FC<{ glow?: number; children?: React.ReactNode; w?: number }> = ({ glow = 0, children, w = 620 }) => (
  <div style={{ width: w, position: "relative" }}>
    <div
      style={{
        width: w, height: w * 0.6, borderRadius: 22, background: "#0c1330",
        border: `10px solid #2b355c`, boxSizing: "border-box", position: "relative", overflow: "hidden",
        boxShadow: `0 0 ${60 * glow}px ${C.cyan}66`,
      }}
    >
      {children}
    </div>
    <div style={{ width: w * 1.15, marginLeft: -w * 0.075, height: 26, background: "#3a4675", borderRadius: "0 0 26px 26px" }} />
  </div>
);

const Chip: React.FC<{ label: string; glow: number; size?: number }> = ({ label, glow, size = 150 }) => (
  <div
    style={{
      width: size, height: size, borderRadius: 18, background: "#1a2552",
      border: `4px solid ${C.cyan}`, display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: FONT, fontWeight: 700, fontSize: size * 0.32, color: C.cyan,
      boxShadow: `0 0 ${50 * glow}px ${C.cyan}`, position: "relative",
    }}
  >
    {[...Array(4)].map((_, i) => (
      <React.Fragment key={i}>
        <div style={{ position: "absolute", left: -18, top: 22 + i * 30, width: 14, height: 6, background: C.cyan }} />
        <div style={{ position: "absolute", right: -18, top: 22 + i * 30, width: 14, height: 6, background: C.cyan }} />
      </React.Fragment>
    ))}
    {label}
  </div>
);

const Pill: React.FC<{ children: React.ReactNode; color: string; s: number }> = ({ children, color, s }) => (
  <div
    style={{
      display: "inline-block", padding: "14px 34px", borderRadius: 999, background: `${color}22`,
      border: `3px solid ${color}`, color, fontFamily: FONT, fontWeight: 700, fontSize: 40,
      transform: `scale(${s})`,
    }}
  >
    {children}
  </div>
);

// ── scenes ────────────────────────────────────────────────────────────────

// 1. "You don't need a data center… the laptop you already own."
const S1: React.FC = () => {
  const frame = useCurrentFrame();
  const rack = useSpring(0);
  const cross = interpolate(frame, [40, 60], [0, 1], clamp);
  const lap = useSpring(70);
  const glow = interpolate(frame, [100, 130], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 200 }}>
      <div style={{ position: "relative", opacity: rack * (1 - 0.55 * cross), transform: `translateY(${(1 - rack) * 60}px)` }}>
        <div style={{ display: "flex", gap: 18 }}>
          {[0, 1, 2].map((r) => (
            <div key={r} style={{ width: 110, height: 380, background: "#1b244a", borderRadius: 10, padding: 12, boxSizing: "border-box" }}>
              {[...Array(9)].map((_, i) => (
                <div key={i} style={{ height: 30, marginBottom: 10, background: "#2a3668", borderRadius: 4, display: "flex", alignItems: "center", paddingLeft: 8 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 4, background: (i + r + Math.floor(frame / 6)) % 3 ? C.green : "#2a3668" }} />
                </div>
              ))}
            </div>
          ))}
        </div>
        <svg width="400" height="400" style={{ position: "absolute", left: -20, top: -10 }}>
          <line x1="20" y1="20" x2={20 + 360 * cross} y2={20 + 360 * cross} stroke={C.red} strokeWidth="18" strokeLinecap="round" />
          <line x1="380" y1="20" x2={380 - 360 * cross} y2={20 + 360 * cross} stroke={C.red} strokeWidth="18" strokeLinecap="round" />
        </svg>
        <div style={{ textAlign: "center", marginTop: 26, fontFamily: FONT, fontSize: 34, color: C.dim }}>data center</div>
      </div>
      <div style={{ transform: `scale(${lap})`, opacity: lap }}>
        <Laptop glow={glow}>
          <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
            <Chip label="AI" glow={glow} />
          </AbsoluteFill>
        </Laptop>
        <div style={{ textAlign: "center", marginTop: 26, fontFamily: FONT, fontSize: 34, color: C.yellow }}>your laptop</div>
      </div>
    </AbsoluteFill>
  );
};

// 2. "Run fully offline. No subscription, and your data never leaves your machine."
const S2: React.FC = () => {
  const frame = useCurrentFrame();
  const lap = useSpring(0);
  const wifi = useSpring(20);
  const shield = interpolate(frame, [60, 90], [0, 1], clamp);
  const price = useSpring(110);
  const docs = [0, 1, 2, 3, 4];
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "relative", transform: `scale(${lap})` }}>
        <Laptop w={560}>
          <svg width="540" height="316" style={{ position: "absolute", left: 0, top: 0 }}>
            <circle cx="270" cy="158" r={130 * shield} fill="none" stroke={C.cyan} strokeWidth="5" strokeDasharray="14 10" opacity={shield} />
            {docs.map((i) => {
              const a = frame / 25 + (i * Math.PI * 2) / docs.length;
              const r = 95 + 12 * Math.sin(frame / 9 + i);
              return <rect key={i} x={270 + r * Math.cos(a) - 18} y={158 + r * Math.sin(a) - 22} width="36" height="44" rx="5" fill={C.yellow} opacity="0.9" />;
            })}
            <text x="270" y="170" textAnchor="middle" fontFamily={FONT} fontWeight="700" fontSize="38" fill={C.text}>your data</text>
          </svg>
        </Laptop>
        {/* wifi-off badge */}
        <div style={{ position: "absolute", right: -140, top: -60, transform: `scale(${wifi})` }}>
          <svg width="150" height="150" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="48" fill={C.panel} stroke={C.red} strokeWidth="4" />
            <path d="M20 45 Q50 20 80 45" stroke={C.dim} strokeWidth="7" fill="none" strokeLinecap="round" />
            <path d="M30 57 Q50 40 70 57" stroke={C.dim} strokeWidth="7" fill="none" strokeLinecap="round" />
            <circle cx="50" cy="70" r="6" fill={C.dim} />
            <line x1="22" y1="22" x2="78" y2="80" stroke={C.red} strokeWidth="8" strokeLinecap="round" />
          </svg>
        </div>
      </div>
      <div style={{ position: "absolute", bottom: 230, display: "flex", gap: 30 }}>
        <Pill color={C.green} s={price}>$0 / month</Pill>
        <Pill color={C.cyan} s={useSpring(130)}>works offline</Pill>
      </div>
    </AbsoluteFill>
  );
};

// 3. "You need three things."
const S3: React.FC = () => {
  const items = [
    { n: "1", t: "The tool", icon: "⚙", c: C.cyan },
    { n: "2", t: "Model size", icon: "▦", c: C.yellow },
    { n: "3", t: "Memory", icon: "▤", c: C.green },
  ];
  const delays = [15, 50, 85];
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <Title>3 things you need</Title>
      <div style={{ display: "flex", gap: 60, marginTop: 80 }}>
        {items.map((it, i) => {
          const s = useSpring(delays[i], 12);
          return (
            <div
              key={i}
              style={{
                width: 400, height: 380, borderRadius: 28, background: C.panel, border: `4px solid ${it.c}`,
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                transform: `translateY(${(1 - s) * 200}px) rotate(${(1 - s) * (i - 1) * 8}deg)`, opacity: s,
                fontFamily: FONT,
              }}
            >
              <div style={{ fontSize: 130, color: it.c, lineHeight: 1 }}>{it.icon}</div>
              <div style={{ fontSize: 30, color: C.dim, marginTop: 24 }}>STEP {it.n}</div>
              <div style={{ fontSize: 50, color: C.text, fontWeight: 700, marginTop: 8 }}>{it.t}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// 4. "Ollama and LM Studio are both free, and they handle the hard parts."
const AppWindow: React.FC<{ name: string; accent: string; children: React.ReactNode }> = ({ name, accent, children }) => (
  <div style={{ width: 620, height: 420, borderRadius: 20, background: "#0d1430", border: `3px solid ${C.line}`, overflow: "hidden", fontFamily: FONT }}>
    <div style={{ height: 56, background: "#18214a", display: "flex", alignItems: "center", padding: "0 20px", gap: 10 }}>
      {[C.red, C.yellow, C.green].map((c) => <div key={c} style={{ width: 16, height: 16, borderRadius: 8, background: c }} />)}
      <div style={{ marginLeft: 20, color: accent, fontWeight: 700, fontSize: 28 }}>{name}</div>
    </div>
    <div style={{ padding: 30 }}>{children}</div>
  </div>
);

const S4: React.FC = () => {
  const frame = useCurrentFrame();
  const l = useSpring(5);
  const r = useSpring(30);
  const free = useSpring(80, 10);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 90 }}>
      <div style={{ transform: `translateX(${(1 - l) * -700}px)`, position: "relative" }}>
        <AppWindow name="Ollama" accent={C.cyan}>
          <div style={{ fontFamily: MONO, color: C.green, fontSize: 30, lineHeight: 1.7 }}>
            $ ollama list<br />
            <span style={{ color: C.dim }}>llama3.1:8b&nbsp;&nbsp;4.9 GB</span><br />
            <span style={{ color: C.dim }}>gemma2:9b&nbsp;&nbsp;&nbsp;5.4 GB</span>
          </div>
        </AppWindow>
        <div style={{ position: "absolute", top: -30, right: -30, transform: `scale(${free}) rotate(-10deg)` }}>
          <Pill color={C.green} s={1}>FREE</Pill>
        </div>
      </div>
      <svg width="140" height="140" viewBox="0 0 100 100" style={{ transform: `rotate(${frame * 3}deg)`, opacity: l }}>
        <path d="M50 15 L56 28 L70 24 L70 38 L84 44 L76 56 L84 68 L70 72 L68 86 L56 80 L50 92 L44 80 L30 86 L30 72 L16 68 L24 56 L16 44 L30 38 L30 24 L44 28 Z" fill={C.yellow} />
        <circle cx="50" cy="54" r="14" fill={C.bg0} />
      </svg>
      <div style={{ transform: `translateX(${(1 - r) * 700}px)`, position: "relative" }}>
        <AppWindow name="LM Studio" accent={C.yellow}>
          {[0.9, 0.6, 0.75].map((w, i) => (
            <div key={i} style={{ height: 34, width: `${w * 100}%`, borderRadius: 10, background: i % 2 ? "#26336b" : "#1f6b64", marginBottom: 22 }} />
          ))}
        </AppWindow>
        <div style={{ position: "absolute", top: -30, right: -30, transform: `scale(${useSpring(95, 10)}) rotate(8deg)` }}>
          <Pill color={C.green} s={1}>FREE</Pill>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// 5. "With Ollama, one command downloads a model and starts a chat."
const S5: React.FC = () => {
  const frame = useCurrentFrame();
  const cmd = "ollama run llama3.1";
  const typed = cmd.slice(0, Math.floor(interpolate(frame, [10, 50], [0, cmd.length], clamp)));
  const prog = interpolate(frame, [55, 120], [0, 1], { ...clamp, easing: Easing.out(Easing.quad) });
  const ready = frame > 125;
  const caret = Math.floor(frame / 12) % 2 === 0;
  const win = useSpring(0);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1300, height: 560, borderRadius: 24, background: "#05081a", border: `3px solid ${C.line}`, overflow: "hidden", transform: `scale(${0.9 + 0.1 * win})`, opacity: win }}>
        <div style={{ height: 60, background: "#141c40", display: "flex", alignItems: "center", padding: "0 24px", gap: 12 }}>
          {[C.red, C.yellow, C.green].map((c) => <div key={c} style={{ width: 18, height: 18, borderRadius: 9, background: c }} />)}
          <div style={{ marginLeft: 20, color: C.dim, fontFamily: FONT, fontSize: 26 }}>Terminal</div>
        </div>
        <div style={{ padding: 44, fontFamily: MONO, fontSize: 42, color: C.text, lineHeight: 1.8 }}>
          <span style={{ color: C.green }}>$ </span>{typed}{frame < 55 && caret ? "▌" : ""}
          {frame >= 55 && (
            <div style={{ fontSize: 34, color: C.dim }}>
              pulling model… {Math.round(prog * 100)}%
              <div style={{ width: 1100, height: 22, background: "#1a2350", borderRadius: 11, marginTop: 10 }}>
                <div style={{ width: 1100 * prog, height: 22, background: `linear-gradient(90deg, ${C.cyan}, ${C.green})`, borderRadius: 11 }} />
              </div>
            </div>
          )}
          {ready && (
            <div style={{ color: C.yellow, marginTop: 20 }}>
              &gt;&gt;&gt; <span style={{ color: C.dim }}>Send a message</span>{caret ? "▌" : ""}
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// 6. "LM Studio gives you a chat window."
const S6: React.FC = () => {
  const frame = useCurrentFrame();
  const bubbles = [
    { me: true, text: "Summarize my meeting notes", at: 10 },
    { me: false, text: "Here are the 3 key decisions…", at: 70 },
    { me: true, text: "Draft a follow-up email", at: 125 },
  ];
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1100, height: 700, borderRadius: 28, background: "#0d1430", border: `3px solid ${C.line}`, padding: 50, boxSizing: "border-box", fontFamily: FONT }}>
        <div style={{ color: C.yellow, fontSize: 34, fontWeight: 700, marginBottom: 40 }}>● LM Studio — chat</div>
        {bubbles.map((b, i) => {
          const s = spring({ frame: frame - b.at, fps: FPS, config: { damping: 13 } });
          const typing = !b.me && frame > b.at - 35 && frame < b.at;
          return (
            <div key={i} style={{ display: "flex", justifyContent: b.me ? "flex-end" : "flex-start", marginBottom: 30 }}>
              {typing ? (
                <div style={{ padding: "22px 34px", borderRadius: 30, background: "#1f2b5e", color: C.dim, fontSize: 44 }}>
                  {".".repeat(1 + (Math.floor(frame / 6) % 3))}
                </div>
              ) : (
                <div style={{ padding: "22px 34px", borderRadius: 30, background: b.me ? "#1f6b64" : "#1f2b5e", color: C.text, fontSize: 40, transform: `scale(${s})`, transformOrigin: b.me ? "right" : "left", opacity: s }}>
                  {b.text}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// 7. "Size is measured in billions of parameters."
const S7: React.FC = () => {
  const frame = useCurrentFrame();
  const n = Math.round(interpolate(frame, [10, 100], [0, 8_000_000_000], { ...clamp, easing: Easing.out(Easing.cubic) }));
  const dots = 400;
  const lit = Math.floor(interpolate(frame, [10, 110], [0, dots], clamp));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <Title y={110}>model size = parameters</Title>
      <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: 130, color: C.yellow, marginTop: -40, fontVariantNumeric: "tabular-nums" }}>
        {n.toLocaleString("en-US")}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(40, 22px)", gap: 8, marginTop: 40 }}>
        {[...Array(dots)].map((_, i) => (
          <div key={i} style={{ width: 22, height: 22, borderRadius: 11, background: i < lit ? C.cyan : "#1c2550", opacity: i < lit ? 0.5 + 0.5 * ((i * 7) % 10) / 10 : 1 }} />
        ))}
      </div>
      <div style={{ fontFamily: FONT, fontSize: 40, color: C.dim, marginTop: 36 }}>= an "8B" model</div>
    </AbsoluteFill>
  );
};

// 8. "Bigger models are smarter, but slower and hungrier for memory."
const S8: React.FC = () => {
  const frame = useCurrentFrame();
  const models = [
    { name: "3B", q: 0.45, sp: 0.95 },
    { name: "8B", q: 0.68, sp: 0.7 },
    { name: "70B", q: 0.92, sp: 0.18 },
  ];
  const grow = interpolate(frame, [10, 60], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const shrink = interpolate(frame, [60, 110], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <Title y={100}>bigger = smarter, but slower</Title>
      <div style={{ display: "flex", gap: 120, alignItems: "flex-end", height: 520, marginTop: 120 }}>
        {models.map((m) => (
          <div key={m.name} style={{ display: "flex", flexDirection: "column", alignItems: "center", fontFamily: FONT }}>
            <div style={{ display: "flex", gap: 22, alignItems: "flex-end", height: 440 }}>
              <div style={{ width: 90, height: 420 * m.q * grow, background: C.green, borderRadius: "12px 12px 0 0" }} />
              <div style={{ width: 90, height: 420 * (1 - (1 - m.sp) * shrink), background: C.red, borderRadius: "12px 12px 0 0", opacity: 0.9 }} />
            </div>
            <div style={{ fontSize: 56, fontWeight: 700, color: C.text, marginTop: 20 }}>{m.name}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 60, marginTop: 30, fontFamily: FONT, fontSize: 34 }}>
        <span style={{ color: C.green }}>■ quality</span>
        <span style={{ color: C.red }}>■ speed</span>
      </div>
    </AbsoluteFill>
  );
};

// 9. "An 8B model, compressed to four bits, needs about five gigabytes."
const S9: React.FC = () => {
  const frame = useCurrentFrame();
  const bits = Math.round(interpolate(frame, [30, 90], [16, 4], clamp));
  const gb = interpolate(frame, [30, 110], [16, 5], { ...clamp, easing: Easing.out(Easing.cubic) });
  const tag = useSpring(120, 10);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <Title y={110}>quantization: 16-bit → 4-bit</Title>
      <div style={{ display: "flex", gap: 10, marginTop: -30 }}>
        {[...Array(16)].map((_, i) => (
          <div key={i} style={{ width: 56, height: 90, borderRadius: 8, background: i < bits ? C.cyan : "#1a2350", opacity: i < bits ? 1 : 0.4, transform: `scaleY(${i < bits ? 1 : 0.5})` }} />
        ))}
      </div>
      <div style={{ fontFamily: FONT, fontSize: 38, color: C.dim, marginTop: 18 }}>{bits} bits per weight</div>
      <div style={{ display: "flex", alignItems: "center", gap: 40, marginTop: 70, fontFamily: FONT }}>
        <div style={{ fontSize: 44, color: C.text }}>8B model file:</div>
        <div style={{ fontSize: 120, fontWeight: 700, color: C.yellow, fontVariantNumeric: "tabular-nums", width: 480, whiteSpace: "nowrap" }}>{gb.toFixed(1)} GB</div>
        <div style={{ transform: `scale(${tag})` }}><Pill color={C.green} s={1}>≈ 5 GB</Pill></div>
      </div>
    </AbsoluteFill>
  );
};

// 10. "That fits comfortably on most laptops with 16 GB of RAM."
const S10: React.FC = () => {
  const frame = useCurrentFrame();
  const fill = interpolate(frame, [15, 70], [0, 5 / 16], { ...clamp, easing: Easing.out(Easing.cubic) });
  const check = useSpring(80, 10);
  const lap = useSpring(0);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ transform: `scale(${0.85 * lap})`, marginTop: -120 }}>
        <Laptop w={520}>
          <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", fontFamily: FONT, fontSize: 60, fontWeight: 700, color: C.text }}>
            16 GB RAM
          </AbsoluteFill>
        </Laptop>
      </div>
      <div style={{ width: 1300, height: 90, borderRadius: 45, background: "#1a2350", marginTop: 60, position: "relative", overflow: "hidden", border: `3px solid ${C.line}` }}>
        <div style={{ width: 1300 * fill, height: "100%", background: `linear-gradient(90deg, ${C.cyan}, ${C.green})` }} />
        <div style={{ position: "absolute", left: 30, top: 18, fontFamily: FONT, fontSize: 44, fontWeight: 700, color: C.bg0 }}>
          {fill > 0.1 ? "model 5 GB" : ""}
        </div>
        <div style={{ position: "absolute", right: 30, top: 18, fontFamily: FONT, fontSize: 44, color: C.dim }}>11 GB free</div>
      </div>
      <div style={{ marginTop: 50, transform: `scale(${check})` }}>
        <Pill color={C.green} s={1}>✓ fits comfortably</Pill>
      </div>
    </AbsoluteFill>
  );
};

const SCENE_COMPONENTS = [S1, S2, S3, S4, S5, S6, S7, S8, S9, S10];

// ── captions + progress ─────────────────────────────────────────────────────

const Captions: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const cap = CAPTIONS.find((c) => t >= c.start && t < c.end);
  if (!cap) return null;
  const local = (t - cap.start) * FPS;
  const s = spring({ frame: local, fps: FPS, config: { damping: 12, mass: 0.5 } });
  return (
    <div
      style={{
        position: "absolute", bottom: 70, width: "100%", textAlign: "center", fontFamily: FONT,
        fontWeight: 700, fontSize: 64, color: C.text, transform: `scale(${0.9 + 0.1 * s})`,
        textShadow: "0 0 8px #000, 0 4px 0 #000, 3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000",
      }}
    >
      {cap.words.map((w, i) => (
        <span key={i} style={{ color: cap.hi[i] ? C.yellow : C.text }}>{w} </span>
      ))}
    </div>
  );
};

const Progress: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return <div style={{ position: "absolute", top: 0, left: 0, height: 8, width: `${(frame / durationInFrames) * 100}%`, background: C.yellow }} />;
};

// captions=false renders clean scenes for use as clips inside poc/shot_video.py (it adds its own captions).
export const Explainer: React.FC<{ captions?: boolean }> = ({ captions = true }) => (
  <AbsoluteFill style={{ backgroundColor: C.bg0 }}>
    <Background />
    {SCENES.map((sc, i) => {
      const Comp = SCENE_COMPONENTS[i];
      return (
        <Sequence key={i} from={Math.round(sc.start * FPS)} durationInFrames={Math.round(sc.dur * FPS)}>
          <Scene dur={sc.dur}>
            <Comp />
          </Scene>
        </Sequence>
      );
    })}
    {captions && <Captions />}
    {captions && <Progress />}
    <Audio src={staticFile("narration.mp3")} />
  </AbsoluteFill>
);
