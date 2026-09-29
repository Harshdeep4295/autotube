import React from "react";
import { AbsoluteFill } from "remotion";
import { Icon } from "./icons";
import { useFontsReady } from "./fonts";
import { C, FONT } from "./theme";
import { ThumbnailProps } from "./types";
import { Mark } from "./brand/Mark";


/** 1280×720 thumbnail in the same visual style as the video. Big words left, icon right. */
export const Thumbnail: React.FC<ThumbnailProps> = ({ text, subtext, icon, channel }) => {
  const fontsReady = useFontsReady();
  if (!fontsReady) return <AbsoluteFill style={{ backgroundColor: C.bg0 }} />;
  const words = text.toUpperCase().split(/\s+/).filter(Boolean);
  // Two lines max: split words roughly in half.
  const cut = Math.ceil(words.length / 2);
  const lines = words.length > 2 ? [words.slice(0, cut).join(" "), words.slice(cut).join(" ")] : [words.join(" ")];
  const longest = Math.max(...lines.map((l) => l.length), 1);
  const size = Math.min(150, Math.floor(1500 / longest));
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 75% 45%, #1d2d6b 0%, ${C.bg0} 70%)`, fontFamily: FONT }}>
      <AbsoluteFill style={{ backgroundImage: `radial-gradient(${C.line} 2px, transparent 2px)`, backgroundSize: "40px 40px", opacity: 0.35 }} />
      {channel ? (
        <div style={{ position: "absolute", left: 60, bottom: 34, display: "flex", alignItems: "center", gap: 12 }}>
          <Mark size={46} />
          <div style={{ fontWeight: 800, fontSize: 30, color: C.text, opacity: 0.9 }}>{channel}</div>
        </div>
      ) : null}
      <div style={{ position: "absolute", right: 70, top: 150, width: 420, height: 420, borderRadius: "50%", background: `${C.yellow}22`, border: `8px solid ${C.yellow}`, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 0 120px ${C.yellow}66` }}>
        <Icon name={icon} size={250} color={C.yellow} stroke={1.6} />
      </div>
      <div style={{ position: "absolute", left: 60, top: 0, bottom: 0, width: 740, display: "flex", flexDirection: "column", justifyContent: "center", gap: 10 }}>
        {lines.map((l, i) => (
          <div key={i} style={{ fontWeight: 800, fontSize: size, lineHeight: 1.02, color: i === lines.length - 1 ? C.yellow : C.text, whiteSpace: "nowrap", textShadow: "0 8px 0 #000, 0 0 30px #000" }}>
            {l}
          </div>
        ))}
        {subtext ? (
          <div style={{ marginTop: 26, alignSelf: "flex-start", padding: "14px 34px", borderRadius: 999, background: C.red, color: "#fff", fontWeight: 800, fontSize: 52, whiteSpace: "nowrap" }}>
            {subtext.toUpperCase()}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
