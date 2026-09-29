import React from "react";
import { AbsoluteFill } from "remotion";
import { useFontsReady } from "../fonts";
import { Icon } from "../icons";
import { C, FONT } from "../theme";
import { Mark } from "./Mark";

export type BrandProps = { name: string; tagline: string };

const Dots: React.FC<{ step?: number; opacity?: number }> = ({ step = 56, opacity = 0.4 }) => (
  <AbsoluteFill style={{ backgroundImage: `radial-gradient(${C.line} 2px, transparent 2px)`, backgroundSize: `${step}px ${step}px`, opacity }} />
);

/** 800×800 profile picture (YouTube shows it as a circle). */
export const BrandLogo: React.FC<BrandProps> = () => {
  const ready = useFontsReady();
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 40%, #1b2a66 0%, ${C.bg0} 72%)`, alignItems: "center", justifyContent: "center" }}>
      <Dots step={40} opacity={0.35} />
      {ready ? <Mark size={520} /> : null}
    </AbsoluteFill>
  );
};

/** 150×150 video watermark (YouTube Studio → Customization → Branding). Transparent outside the mark. */
export const BrandWatermark: React.FC<BrandProps> = () => (
  <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
    <Mark size={150} />
  </AbsoluteFill>
);

/** 2560×1440 channel banner. Everything important sits in the 1546×423 area visible on every device. */
export const BrandBanner: React.FC<BrandProps> = ({ name, tagline }) => {
  const ready = useFontsReady();
  const icons = ["laptop", "lock", "offline", "cpu", "terminal"];
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 50%, #18246010 0%, transparent 60%), linear-gradient(135deg, ${C.bg0} 0%, #111a44 55%, ${C.bg0} 100%)`, fontFamily: FONT }}>
      <Dots />
      {ready ? (
        <div style={{ position: "absolute", left: 507, top: 508, width: 1546, height: 423, display: "flex", alignItems: "center", gap: 60 }}>
          <Mark size={300} />
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ fontWeight: 800, fontSize: 150, lineHeight: 1, color: C.text, whiteSpace: "nowrap" }}>{name}</div>
            <div style={{ fontWeight: 600, fontSize: 50, color: C.dim, whiteSpace: "nowrap" }}>{tagline}</div>
            <div style={{ display: "flex", gap: 30, marginTop: 14 }}>
              {icons.map((i) => (
                <div key={i} style={{ width: 70, height: 70, borderRadius: 18, border: `3px solid ${C.cyan}66`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Icon name={i} size={40} color={C.cyan} stroke={1.8} />
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
