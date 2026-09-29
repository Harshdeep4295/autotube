import React from "react";
import { C } from "../theme";

/**
 * Channel mark: a terminal prompt ">_" — the ">" doubles as a play button.
 * Reads at 24 px and survives YouTube's circular avatar crop (content inside the
 * central 70%).
 */
export const Mark: React.FC<{ size: number; bg?: boolean; cursorOn?: boolean }> = ({ size, bg = true, cursorOn = true }) => (
  <svg width={size} height={size} viewBox="0 0 100 100">
    {bg ? (
      <>
        <rect x="0" y="0" width="100" height="100" rx="24" fill="#0b1230" />
        <rect x="2.5" y="2.5" width="95" height="95" rx="22" fill="none" stroke={C.cyan} strokeOpacity="0.55" strokeWidth="2.5" />
      </>
    ) : null}
    <polyline points="29,28 52,50 29,72" fill="none" stroke={C.yellow} strokeWidth="12" strokeLinecap="round" strokeLinejoin="round" />
    {cursorOn ? <rect x="57" y="63" width="20" height="9" rx="3" fill={C.cyan} /> : null}
  </svg>
);
