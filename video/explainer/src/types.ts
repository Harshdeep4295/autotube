// Contract with agents/explainer_agent.py (props.json). Keep in sync with agents/scene_schema.py.
export type Word = { w: string; s: number; e: number; hi: boolean };
export type CaptionPage = { start: number; end: number; words: Word[] };
export type SceneSpec = { type: string; props: Record<string, any> };
export type Shot = {
  start: number; // seconds from video start
  duration: number; // seconds (narration + pause)
  speech: number; // seconds of actual speech inside the shot
  text: string;
  emphasis: string[];
  scene: SceneSpec;
};
export type ExplainerProps = {
  shots: Shot[];
  captions: CaptionPage[];
  voice: string | null; // file in the public dir
  music: string | null;
  musicVolume: number;
  channel: string;
  showCaptions: boolean;
  debugChecks: boolean;
};
export type SceneTestProps = { type: string; props: Record<string, any>; debugChecks: boolean };
export type ThumbnailProps = { text: string; subtext: string; icon: string };
