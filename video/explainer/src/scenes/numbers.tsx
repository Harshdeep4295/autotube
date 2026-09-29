import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { Body, clamp, Heading, Pill, useFitCheck, useSpring } from "../components/common";
import { Icon } from "../icons";
import { C, FONT, SAFE } from "../theme";
import { fitSize, fmtNum } from "../util";
import { SceneProps } from "./text";

// big_number ──────────────────────────────────────────────────────────────────
export const BigNumber: React.FC<SceneProps> = ({ props }) => {
  const frame = useCurrentFrame();
  const dec = Number(props.decimals ?? 0);
  const p = interpolate(frame, [6, 42], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const value = props.value * p;
  const label = useSpring(30);
  const numStr = `${props.prefix ?? ""}${fmtNum(value, dec)}`;
  const finalStr = `${props.prefix ?? ""}${fmtNum(props.value, dec)}${props.unit ? " " + props.unit : ""}`;
  const size = fitSize(finalStr, 1500, 240);
  const nRef = useFitCheck<HTMLDivElement>("number");
  const lRef = useFitCheck<HTMLDivElement>("label");
  return (
    <Body top={SAFE.top} style={{ flexDirection: "column", gap: 36 }}>
      <svg width="220" height="220" viewBox="0 0 100 100" style={{ position: "absolute", opacity: 0.25, transform: "scale(4)" }}>
        <circle cx="50" cy="50" r="40" fill="none" stroke={C.cyan} strokeWidth="1" strokeDasharray={`${251 * p} 251`} transform="rotate(-90 50 50)" />
      </svg>
      <div ref={nRef} style={{ fontFamily: FONT, fontWeight: 800, fontSize: size, color: C.yellow, whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums", maxWidth: 1600 }}>
        {numStr}
        {props.unit ? <span style={{ color: C.text, fontSize: size * 0.55 }}> {props.unit}</span> : null}
      </div>
      <div ref={lRef} style={{ fontFamily: FONT, fontWeight: 600, fontSize: fitSize(props.label, 1500, 58, "600"), color: C.dim, whiteSpace: "nowrap", maxWidth: 1600, opacity: label, transform: `translateY(${(1 - label) * 20}px)` }}>
        {props.label}
      </div>
    </Body>
  );
};

// compare ─────────────────────────────────────────────────────────────────────
const CompareCard: React.FC<{ side: "left" | "right"; label: string; value: string; win: boolean; delay: number }> = ({
  side, label, value, win, delay,
}) => {
  const s = useSpring(delay, 13);
  const w = useSpring(delay + 30, 10);
  const vRef = useFitCheck<HTMLDivElement>(`${side}-value`);
  const lRef = useFitCheck<HTMLDivElement>(`${side}-label`);
  const color = side === "left" ? C.cyan : C.yellow;
  return (
    <div
      style={{
        width: 640, height: 430, borderRadius: 30, background: C.panel, position: "relative",
        border: `4px solid ${win ? C.green : color}`, boxShadow: win ? `0 0 ${70 * w}px ${C.green}66` : "none",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 20,
        transform: `translateX(${(1 - s) * (side === "left" ? -800 : 800)}px)`,
      }}
    >
      <div ref={lRef} style={{ fontFamily: FONT, fontWeight: 600, fontSize: fitSize(label, 560, 52, "600"), color: C.dim, whiteSpace: "nowrap", maxWidth: 580 }}>{label}</div>
      <div ref={vRef} style={{ fontFamily: FONT, fontWeight: 800, fontSize: fitSize(value, 560, 130), color, whiteSpace: "nowrap", maxWidth: 580 }}>{value}</div>
      {win ? (
        <div style={{ position: "absolute", top: -34, right: -24, transform: `scale(${w}) rotate(8deg)` }}>
          <Pill color={C.green} size={34}>✓ WINNER</Pill>
        </div>
      ) : null}
    </div>
  );
};

export const Compare: React.FC<SceneProps> = ({ props }) => {
  const vs = useSpring(22, 9);
  return (
    <>
      <Heading text={props.metric} />
      <Body style={{ gap: 70 }}>
        <CompareCard side="left" label={props.left.label} value={props.left.value} win={props.winner === "left"} delay={4} />
        <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 70, color: C.text, transform: `scale(${vs})` }}>VS</div>
        <CompareCard side="right" label={props.right.label} value={props.right.value} win={props.winner === "right"} delay={14} />
      </Body>
    </>
  );
};

// meter ───────────────────────────────────────────────────────────────────────
export const Meter: React.FC<SceneProps> = ({ props }) => {
  const frame = useCurrentFrame();
  const frac = Math.max(0, Math.min(1, props.value / props.max));
  const f = interpolate(frame, [10, 55], [0, frac], { ...clamp, easing: Easing.out(Easing.cubic) });
  const note = useSpring(60, 10);
  const unit = props.unit ? ` ${props.unit}` : "";
  const barW = 1400;
  const inside = `${fmtNum(props.value * (f / (frac || 1)), Number.isInteger(props.value) ? 0 : 1)}${unit}`;
  const rest = `${fmtNum(props.max, Number.isInteger(props.max) ? 0 : 1)}${unit} total`;
  const color = frac > 0.9 ? C.red : frac > 0.7 ? C.yellow : C.green;
  const rRef = useFitCheck<HTMLDivElement>("total");
  return (
    <>
      <Heading text={props.label} />
      <Body style={{ flexDirection: "column", gap: 50 }}>
        <Icon name="memory" size={130} color={C.cyan} stroke={1.5} />
        <div style={{ width: barW, height: 110, borderRadius: 55, background: C.panel2, border: `3px solid ${C.line}`, position: "relative", overflow: "hidden" }}>
          <div style={{ width: barW * f, height: "100%", background: `linear-gradient(90deg, ${C.cyan}, ${color})` }} />
          <div style={{ position: "absolute", left: 40, top: 0, height: 110, display: "flex", alignItems: "center", fontFamily: FONT, fontWeight: 800, fontSize: 50, color: f > 0.3 ? C.bg0 : C.text, whiteSpace: "nowrap" }}>
            {inside}
          </div>
        </div>
        <div ref={rRef} style={{ width: barW, marginTop: -30, textAlign: "right", fontFamily: FONT, fontWeight: 600, fontSize: 42, color: C.dim, whiteSpace: "nowrap", overflow: "hidden" }}>
          of {rest}
        </div>
        {props.note ? <Pill color={color} scale={note} size={44}>{props.note}</Pill> : null}
      </Body>
    </>
  );
};
