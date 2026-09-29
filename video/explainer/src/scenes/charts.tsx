import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Body, clamp, Heading, useFitCheck } from "../components/common";
import { C, FONT, SERIES } from "../theme";
import { fitSize, fmtNum, stagger } from "../util";
import { SceneProps } from "./text";

// bar_chart ───────────────────────────────────────────────────────────────────
const Bar: React.FC<{ i: number; n: number; label: string; value: number; max: number; unit: string; frames: number; colW: number }> = ({
  i, n, label, value, max, unit, frames, colW,
}) => {
  const frame = useCurrentFrame();
  const start = stagger(i, n, frames, 0.4, 8);
  const g = interpolate(frame, [start, start + 24], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const maxH = 400;
  const h = Math.max(6, (Math.max(value, 0) / (max || 1)) * maxH * g);
  const vRef = useFitCheck<HTMLDivElement>(`bar${i}-value`);
  const lRef = useFitCheck<HTMLDivElement>(`bar${i}-label`);
  const vText = `${fmtNum(value * g, Number.isInteger(value) ? 0 : 1)}${unit ? " " + unit : ""}`;
  const vFinal = `${fmtNum(value, Number.isInteger(value) ? 0 : 1)}${unit ? " " + unit : ""}`;
  return (
    <div style={{ width: colW, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div ref={vRef} style={{ width: colW, textAlign: "center", overflow: "hidden", fontFamily: FONT, fontWeight: 800, fontSize: fitSize(vFinal, colW - 12, 46, "800", 16), color: C.text, whiteSpace: "nowrap", opacity: g, marginBottom: 12, fontVariantNumeric: "tabular-nums" }}>
        {vText}
      </div>
      <div style={{ height: maxH, display: "flex", alignItems: "flex-end" }}>
        <div style={{ width: Math.min(150, colW * 0.62), height: h, borderRadius: "14px 14px 0 0", background: SERIES[i % SERIES.length] }} />
      </div>
      <div ref={lRef} style={{ marginTop: 16, width: colW, textAlign: "center", overflow: "hidden", fontFamily: FONT, fontWeight: 600, fontSize: fitSize(label, colW - 12, 44, "600", 16), color: C.dim, whiteSpace: "nowrap" }}>
        {label}
      </div>
    </div>
  );
};

export const BarChart: React.FC<SceneProps> = ({ props, frames }) => {
  const items: { label: string; value: number }[] = props.items;
  const max = Math.max(...items.map((d) => d.value), 0);
  const colW = Math.min(300, 1500 / items.length);
  return (
    <>
      <Heading text={props.title} />
      <Body top={220}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 20, borderBottom: `4px solid ${C.line}`, paddingBottom: 0 }}>
          {items.map((d, i) => (
            <Bar key={i} i={i} n={items.length} label={d.label} value={d.value} max={max} unit={props.unit} frames={frames} colW={colW} />
          ))}
        </div>
      </Body>
    </>
  );
};

// line_trend ──────────────────────────────────────────────────────────────────
export const LineTrend: React.FC<SceneProps> = ({ props, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pts: { x: string; y: number }[] = props.points;
  const Wd = 1400, Ht = 420, pad = 40;
  const ys = pts.map((p) => p.y);
  const lo = Math.min(...ys, 0), hi = Math.max(...ys);
  const span = hi - lo || 1;
  const xy = pts.map((p, i) => [pad + (i * (Wd - 2 * pad)) / (pts.length - 1), Ht - pad - ((p.y - lo) / span) * (Ht - 2 * pad)]);
  const drawEnd = Math.min(frames * 0.6, 20 + pts.length * 12);
  const draw = interpolate(frame, [6, drawEnd], [0, 1], { ...clamp, easing: Easing.inOut(Easing.quad) });
  let len = 0;
  for (let i = 1; i < xy.length; i++) len += Math.hypot(xy[i][0] - xy[i - 1][0], xy[i][1] - xy[i - 1][1]);
  const path = xy.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ");
  const area = `${path} L${xy[xy.length - 1][0]},${Ht - pad} L${xy[0][0]},${Ht - pad} Z`;
  const unit = props.unit ? ` ${props.unit}` : "";
  return (
    <>
      <Heading text={props.title} />
      <Body top={230} style={{ flexDirection: "column" }}>
        <svg width={Wd} height={Ht + 70} style={{ overflow: "visible" }}>
          <defs>
            <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.cyan} stopOpacity="0.35" />
              <stop offset="100%" stopColor={C.cyan} stopOpacity="0" />
            </linearGradient>
          </defs>
          <line x1={pad} y1={Ht - pad} x2={Wd - pad} y2={Ht - pad} stroke={C.line} strokeWidth="4" />
          <path d={area} fill="url(#area)" opacity={draw} />
          <path d={path} fill="none" stroke={C.cyan} strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={`${len * draw} ${len}`} />
          {xy.map(([x, y], i) => {
            const at = 6 + (i / Math.max(1, xy.length - 1)) * (drawEnd - 6);
            const s = spring({ frame: frame - at, fps, config: { damping: 11 } });
            const val = `${fmtNum(pts[i].y, Number.isInteger(pts[i].y) ? 0 : 1)}${unit}`;
            const slotW = Math.min(220, (Wd - 2 * pad) / Math.max(1, xy.length - 1)) - 14;
            return (
              <g key={i} opacity={s}>
                <circle cx={x} cy={y} r={14 * s} fill={C.yellow} stroke={C.bg0} strokeWidth="4" />
                <text x={x} y={y - 30} textAnchor="middle" fontFamily={FONT} fontWeight={800} fontSize={fitSize(val, slotW, 40, "800", 14)} fill={C.text}>{val}</text>
                <text x={x} y={Ht + 10} textAnchor="middle" fontFamily={FONT} fontWeight={600} fontSize={fitSize(pts[i].x, slotW, 38, "600", 14)} fill={C.dim}>{pts[i].x}</text>
              </g>
            );
          })}
        </svg>
      </Body>
    </>
  );
};

// timeline ────────────────────────────────────────────────────────────────────
const Event: React.FC<{ i: number; n: number; date: string; label: string; frames: number; w: number }> = ({ i, n, date, label, frames, w }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const at = stagger(i, n, frames, 0.55, 12);
  const s = spring({ frame: frame - at, fps, config: { damping: 12 } });
  const dRef = useFitCheck<HTMLDivElement>(`event${i}-date`);
  const lRef = useFitCheck<HTMLDivElement>(`event${i}-label`);
  const up = i % 2 === 0;
  return (
    <div style={{ width: w, height: 480, position: "relative", display: "flex", justifyContent: "center", opacity: s }}>
      <div style={{ position: "absolute", top: 222, width: 36, height: 36, borderRadius: 18, background: C.yellow, border: `6px solid ${C.bg0}`, transform: `scale(${s})` }} />
      <div ref={dRef} style={{ position: "absolute", top: up ? 150 : 280, fontFamily: FONT, fontWeight: 800, fontSize: fitSize(date, w - 20, 50), color: C.yellow, whiteSpace: "nowrap" }}>{date}</div>
      <div
        ref={lRef}
        style={{
          position: "absolute", top: up ? 20 : 350, width: w - 20, height: 126, overflow: "hidden", textAlign: "center",
          fontFamily: FONT, fontWeight: 600, fontSize: n >= 5 ? 30 : 36, lineHeight: 1.2, color: C.text,
          transform: `translateY(${(1 - s) * (up ? -20 : 20)}px)`,
        }}
      >
        {label}
      </div>
    </div>
  );
};

export const Timeline: React.FC<SceneProps> = ({ props, frames }) => {
  const frame = useCurrentFrame();
  const ev: { date: string; label: string }[] = props.events;
  const line = interpolate(frame, [4, frames * 0.55], [0, 1], clamp);
  const w = Math.min(420, 1640 / ev.length);
  return (
    <>
      <Heading text={props.title} />
      <Body top={250}>
        <div style={{ position: "relative", display: "flex" }}>
          <div style={{ position: "absolute", top: 236, left: 0, height: 8, width: `${line * 100}%`, borderRadius: 4, background: C.line }} />
          {ev.map((e, i) => <Event key={i} i={i} n={ev.length} date={e.date} label={e.label} frames={frames} w={w} />)}
        </div>
      </Body>
    </>
  );
};
