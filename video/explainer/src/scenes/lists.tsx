import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Body, Heading, useFitCheck } from "../components/common";
import { Icon } from "../icons";
import { C, FONT, SERIES } from "../theme";
import { fitSize, stagger } from "../util";
import { SceneProps } from "./text";

const useReveal = (i: number, n: number, frames: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - stagger(i, n, frames, 0.55, 10), fps, config: { damping: 13 } });
};

// steps ───────────────────────────────────────────────────────────────────────
const StepRow: React.FC<{ i: number; n: number; text: string; frames: number }> = ({ i, n, text, frames }) => {
  const s = useReveal(i, n, frames);
  const ref = useFitCheck<HTMLDivElement>(`step${i}`);
  const rowH = n > 4 ? 96 : 116;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 36, height: rowH, opacity: s, transform: `translateX(${(1 - s) * -120}px)` }}>
      <div style={{ width: 88, height: 88, borderRadius: 44, background: SERIES[i % SERIES.length], display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT, fontWeight: 800, fontSize: 48, color: C.bg0, flexShrink: 0 }}>
        {i + 1}
      </div>
      <div ref={ref} style={{ width: 1200, fontFamily: FONT, fontWeight: 600, fontSize: fitSize(text, 1190, 58, "600"), color: C.text, whiteSpace: "nowrap", overflow: "hidden" }}>
        {text}
      </div>
    </div>
  );
};

export const Steps: React.FC<SceneProps> = ({ props, frames }) => (
  <>
    <Heading text={props.title} />
    <Body top={230}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {props.items.map((t: string, i: number) => <StepRow key={i} i={i} n={props.items.length} text={t} frames={frames} />)}
      </div>
    </Body>
  </>
);

// checklist ───────────────────────────────────────────────────────────────────
const CheckRow: React.FC<{ i: number; n: number; text: string; ok: boolean; frames: number }> = ({ i, n, text, ok, frames }) => {
  const s = useReveal(i, n, frames);
  const ref = useFitCheck<HTMLDivElement>(`check${i}`);
  const color = ok ? C.green : C.red;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 34, height: n > 4 ? 96 : 116, opacity: Math.min(1, s * 1.5) }}>
      <div style={{ width: 84, height: 84, borderRadius: 20, border: `4px solid ${color}`, background: `${color}22`, display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${s})`, flexShrink: 0 }}>
        <Icon name={ok ? "check" : "x"} size={56} color={color} stroke={3} />
      </div>
      <div ref={ref} style={{ width: 1200, fontFamily: FONT, fontWeight: 600, fontSize: fitSize(text, 1190, 58, "600"), color: C.text, whiteSpace: "nowrap", overflow: "hidden" }}>
        {text}
      </div>
    </div>
  );
};

export const Checklist: React.FC<SceneProps> = ({ props, frames }) => (
  <>
    <Heading text={props.title} />
    <Body top={230}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {props.items.map((it: { text: string; ok: boolean }, i: number) => (
          <CheckRow key={i} i={i} n={props.items.length} text={it.text} ok={it.ok} frames={frames} />
        ))}
      </div>
    </Body>
  </>
);

// icon_grid ───────────────────────────────────────────────────────────────────
const GridCard: React.FC<{ i: number; n: number; icon: string; label: string; frames: number; w: number; h: number }> = ({
  i, n, icon, label, frames, w, h,
}) => {
  const s = useReveal(i, n, frames);
  const ref = useFitCheck<HTMLDivElement>(`card${i}`);
  const color = SERIES[i % SERIES.length];
  return (
    <div
      style={{
        width: w, height: h, borderRadius: 28, background: C.panel, border: `4px solid ${color}`,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 22,
        transform: `translateY(${(1 - s) * 140}px) scale(${0.8 + 0.2 * s})`, opacity: s,
      }}
    >
      <Icon name={icon} size={h > 300 ? 120 : 96} color={color} stroke={1.7} />
      <div ref={ref} style={{ width: w - 30, textAlign: "center", fontFamily: FONT, fontWeight: 800, fontSize: fitSize(label, w - 40, 46), color: C.text, whiteSpace: "nowrap", overflow: "hidden" }}>
        {label}
      </div>
    </div>
  );
};

export const IconGrid: React.FC<SceneProps> = ({ props, frames }) => {
  const items: { icon: string; label: string }[] = props.items;
  const n = items.length;
  const cols = n <= 3 ? n : n === 4 ? 2 : 3;
  const rows = Math.ceil(n / cols);
  const w = cols === 2 && rows === 2 ? 520 : 440;
  const h = rows === 1 ? 380 : 250;
  return (
    <>
      <Heading text={props.title} />
      <Body top={220}>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, ${w}px)`, gap: 36 }}>
          {items.map((it, i) => <GridCard key={i} i={i} n={n} icon={it.icon} label={it.label} frames={frames} w={w} h={h} />)}
        </div>
      </Body>
    </>
  );
};
