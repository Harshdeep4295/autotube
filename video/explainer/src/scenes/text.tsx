import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Body, clamp, Pill, useFitCheck, useSpring } from "../components/common";
import { Icon } from "../icons";
import { C, FONT, SAFE } from "../theme";
import { fitSize } from "../util";

export type SceneProps = { props: Record<string, any>; frames: number };

const IconBadge: React.FC<{ name: string; delay?: number; size?: number; color?: string }> = ({
  name, delay = 0, size = 150, color = C.cyan,
}) => {
  const s = useSpring(delay, 11);
  const frame = useCurrentFrame();
  const bob = Math.sin(frame / 18) * 6;
  return (
    <div
      style={{
        width: size * 1.6, height: size * 1.6, borderRadius: "50%", background: `${color}1c`,
        border: `4px solid ${color}`, display: "flex", alignItems: "center", justifyContent: "center",
        transform: `scale(${s}) translateY(${bob}px)`, boxShadow: `0 0 ${60 * s}px ${color}55`,
      }}
    >
      <Icon name={name} size={size} color={color} stroke={1.8} />
    </div>
  );
};

// title_hook ──────────────────────────────────────────────────────────────────
export const TitleHook: React.FC<SceneProps> = ({ props }) => {
  const frame = useCurrentFrame();
  const h = useSpring(8);
  const sub = useSpring(22);
  const bar = interpolate(frame, [14, 34], [0, 1], clamp);
  const hRef = useFitCheck<HTMLDivElement>("headline");
  const sRef = useFitCheck<HTMLDivElement>("subline");
  const size = fitSize(props.headline, 1560, 150);
  return (
    <Body top={SAFE.top} style={{ flexDirection: "column", gap: 34 }}>
      <IconBadge name={props.icon} size={120} color={C.yellow} />
      <div
        ref={hRef}
        style={{
          fontFamily: FONT, fontWeight: 800, fontSize: size, color: C.text, whiteSpace: "nowrap", maxWidth: 1600,
          opacity: h, transform: `translateY(${(1 - h) * 40}px)`, letterSpacing: 1,
        }}
      >
        {props.headline}
      </div>
      <div style={{ width: 360 * bar, height: 12, borderRadius: 6, background: C.yellow }} />
      {props.subline ? (
        <div
          ref={sRef}
          style={{ fontFamily: FONT, fontWeight: 600, fontSize: fitSize(props.subline, 1500, 54, "600"), color: C.dim, opacity: sub, whiteSpace: "nowrap", maxWidth: 1600 }}
        >
          {props.subline}
        </div>
      ) : null}
    </Body>
  );
};

// key_point ───────────────────────────────────────────────────────────────────
export const KeyPoint: React.FC<SceneProps> = ({ props }) => {
  const t = useSpring(10);
  const sub = useSpring(22);
  const tRef = useFitCheck<HTMLDivElement>("text");
  const sRef = useFitCheck<HTMLDivElement>("sub");
  return (
    <Body top={SAFE.top} style={{ flexDirection: "column", gap: 40 }}>
      <IconBadge name={props.icon} />
      <div
        ref={tRef}
        style={{
          fontFamily: FONT, fontWeight: 800, fontSize: fitSize(props.text, 1560, 110), color: C.text,
          whiteSpace: "nowrap", maxWidth: 1600, opacity: t, transform: `translateY(${(1 - t) * 30}px)`,
        }}
      >
        {props.text}
      </div>
      {props.sub ? (
        <div ref={sRef} style={{ fontFamily: FONT, fontWeight: 600, fontSize: fitSize(props.sub, 1500, 50, "600"), color: C.dim, opacity: sub, whiteSpace: "nowrap", maxWidth: 1600 }}>
          {props.sub}
        </div>
      ) : null}
    </Body>
  );
};

// quote ───────────────────────────────────────────────────────────────────────
export const QuoteScene: React.FC<SceneProps> = ({ props }) => {
  const frame = useCurrentFrame();
  const q = useSpring(0, 12);
  const words = String(props.text).split(" ");
  const shown = Math.floor(interpolate(frame, [8, 8 + words.length * 2.2], [0, words.length], clamp));
  const a = useSpring(10 + words.length * 2.2);
  const ref = useFitCheck<HTMLDivElement>("quote");
  const size = props.text.length > 90 ? 58 : props.text.length > 60 ? 66 : 76;
  return (
    <Body top={SAFE.top} style={{ flexDirection: "column", gap: 30 }}>
      <div style={{ fontFamily: "Georgia, serif", fontSize: 260, lineHeight: 0.6, color: C.yellow, opacity: q, transform: `scale(${q})`, height: 130 }}>“</div>
      <div
        ref={ref}
        style={{ width: 1450, maxHeight: 360, overflow: "hidden", textAlign: "center", fontFamily: FONT, fontWeight: 600, fontSize: size, lineHeight: 1.3, color: C.text }}
      >
        {words.map((w, i) => (
          <span key={i} style={{ opacity: i < shown ? 1 : 0.12 }}>{w} </span>
        ))}
      </div>
      {props.attribution ? (
        <div style={{ fontFamily: FONT, fontSize: 40, color: C.cyan, opacity: a, whiteSpace: "nowrap" }}>— {props.attribution}</div>
      ) : null}
    </Body>
  );
};

// cta_end ─────────────────────────────────────────────────────────────────────
export const CtaEnd: React.FC<SceneProps> = ({ props }) => {
  const frame = useCurrentFrame();
  const q = useSpring(6);
  const btn = useSpring(26, 9);
  const pulse = 1 + 0.04 * Math.sin(frame / 6);
  const ring = interpolate(frame % 45, [0, 45], [0, 1]);
  const ref = useFitCheck<HTMLDivElement>("question");
  return (
    <Body top={SAFE.top} style={{ flexDirection: "column", gap: 60 }}>
      <Icon name="chat" size={120} color={C.cyan} stroke={1.6} />
      <div
        ref={ref}
        style={{ fontFamily: FONT, fontWeight: 800, fontSize: fitSize(props.question, 1560, 96), color: C.text, whiteSpace: "nowrap", maxWidth: 1600, opacity: q, transform: `translateY(${(1 - q) * 30}px)` }}
      >
        {props.question}
      </div>
      <div style={{ position: "relative", transform: `scale(${btn * pulse})` }}>
        <div style={{ position: "absolute", inset: -10 - 30 * ring, borderRadius: 999, border: `3px solid ${C.red}`, opacity: 1 - ring }} />
        <div style={{ padding: "26px 70px", borderRadius: 999, background: C.red, fontFamily: FONT, fontWeight: 800, fontSize: 48, color: "#fff", whiteSpace: "nowrap" }}>
          SUBSCRIBE
        </div>
      </div>
      {props.sub ? <Pill color={C.dim} size={34} scale={useSpring(40)}>{props.sub}</Pill> : null}
    </Body>
  );
};
