import React from "react";
import { SceneProps, TitleHook, KeyPoint, QuoteScene, CtaEnd } from "./text";
import { BigNumber, Compare, Meter } from "./numbers";
import { BarChart, LineTrend, Timeline } from "./charts";
import { Steps, Checklist, IconGrid } from "./lists";
import { Terminal, Chat } from "./apps";

// Keys must match CATALOGUE in agents/scene_schema.py.
export const SCENES: Record<string, React.FC<SceneProps>> = {
  title_hook: TitleHook,
  key_point: KeyPoint,
  big_number: BigNumber,
  compare: Compare,
  bar_chart: BarChart,
  line_trend: LineTrend,
  steps: Steps,
  checklist: Checklist,
  icon_grid: IconGrid,
  meter: Meter,
  terminal: Terminal,
  chat: Chat,
  timeline: Timeline,
  quote: QuoteScene,
  cta_end: CtaEnd,
};
