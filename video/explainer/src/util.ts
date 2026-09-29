import { fitText } from "@remotion/layout-utils";
import { FONT } from "./theme";

/** Largest font size ≤ max at which `text` fits on one line within `width`. */
export const fitSize = (text: string, width: number, max: number, weight = "800", min = 28) => {
  if (!text) return max;
  try {
    const { fontSize } = fitText({ text, withinWidth: width, fontFamily: FONT, fontWeight: weight });
    return Math.max(min, Math.min(max, Math.floor(fontSize * 0.97)));
  } catch {
    return Math.max(min, Math.min(max, Math.floor((width / Math.max(text.length, 1)) * 1.7)));
  }
};

export const fmtNum = (v: number, decimals = 0): string => {
  const a = Math.abs(v);
  if (a >= 1e9) return (v / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
  if (a >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  if (a >= 1e5) return (v / 1e3).toFixed(0) + "K";
  return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

/** Evenly spread `n` reveal times across the first `frac` of a shot (in frames). */
export const stagger = (i: number, n: number, totalFrames: number, frac = 0.55, first = 6) =>
  Math.round(first + (n <= 1 ? 0 : (i * (totalFrames * frac - first)) / (n - 1)));
