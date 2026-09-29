import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT } from "../theme";
import { CaptionPage } from "../types";

/** Word-level captions: the page for the current moment, with the spoken word highlighted. */
export const Captions: React.FC<{ pages: CaptionPage[] }> = ({ pages }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const page = pages.find((p) => t >= p.start && t < p.end);
  if (!page) return null;
  const pop = spring({ frame: frame - Math.round(page.start * fps), fps, config: { damping: 13, mass: 0.5 } });
  return (
    <div
      style={{
        position: "absolute", bottom: 64, left: 120, right: 120, textAlign: "center", fontFamily: FONT,
        fontWeight: 800, fontSize: 60, lineHeight: 1.25, transform: `scale(${0.92 + 0.08 * pop})`,
      }}
    >
      {page.words.map((w, i) => {
        const active = t >= w.s && t < w.e;
        return (
          <span
            key={i}
            style={{
              color: w.hi ? C.yellow : C.text,
              padding: "0 10px",
              borderRadius: 12,
              background: active ? "rgba(79, 209, 197, 0.28)" : "transparent",
              textShadow: "0 0 10px #000, 0 4px 0 #000, 3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000",
            }}
          >
            {w.w}
          </span>
        );
      })}
    </div>
  );
};
