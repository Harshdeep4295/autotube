import React from "react";
import { AbsoluteFill, Audio, interpolate, Sequence, staticFile, useVideoConfig } from "remotion";
import { Background, DebugContext, Progress, SceneFrame, SceneNameContext, Watermark } from "./components/common";
import { Captions } from "./components/Captions";
import { SCENES } from "./scenes/registry";
import { KeyPoint } from "./scenes/text";
import { useFontsReady } from "./fonts";
import { ExplainerProps, SceneTestProps, Shot } from "./types";


const SceneFor: React.FC<{ shot: Pick<Shot, "scene">; frames: number }> = ({ shot, frames }) => {
  const Cmp = SCENES[shot.scene.type] ?? KeyPoint;
  return (
    <SceneNameContext.Provider value={shot.scene.type}>
      <SceneFrame frames={frames}>
        <Cmp props={shot.scene.props} frames={frames} />
      </SceneFrame>
    </SceneNameContext.Provider>
  );
};

/** Music volume: ducked under speech, a little louder in the pauses, faded at both ends. */
const musicVolume = (shots: Shot[], base: number, fps: number, total: number) => (f: number) => {
  const t = f / fps;
  const inSpeech = shots.some((s) => t >= s.start - 0.15 && t <= s.start + s.speech + 0.15);
  const v = inSpeech ? base : base * 2.2;
  const edges = interpolate(f, [0, fps, total - 2 * fps, total], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return v * edges;
};

export const Explainer: React.FC<ExplainerProps> = (p) => {
  const fontsReady = useFontsReady();
  const { fps, durationInFrames } = useVideoConfig();
  if (!fontsReady) return <AbsoluteFill style={{ backgroundColor: "#070b1a" }} />;
  return (
    <DebugContext.Provider value={p.debugChecks}>
      <AbsoluteFill style={{ backgroundColor: "#070b1a" }}>
        <Background />
        {p.shots.map((shot, i) => {
          const from = Math.round(shot.start * fps);
          const frames = Math.max(1, Math.round((shot.start + shot.duration) * fps) - from);
          return (
            <Sequence key={i} from={from} durationInFrames={frames} name={`${i + 1} ${shot.scene.type}`}>
              <SceneFor shot={shot} frames={frames} />
            </Sequence>
          );
        })}
        {p.showCaptions ? <Captions pages={p.captions} /> : null}
        <Progress />
        <Watermark channel={p.channel} />
        {p.voice ? <Audio src={staticFile(p.voice)} /> : null}
        {p.music ? (
          <Audio src={staticFile(p.music)} loop volume={musicVolume(p.shots, p.musicVolume, fps, durationInFrames)} />
        ) : null}
      </AbsoluteFill>
    </DebugContext.Provider>
  );
};

/** One scene on the background — used by test/scenes.test.mjs. */
export const SceneTest: React.FC<SceneTestProps> = ({ type, props, debugChecks }) => {
  const fontsReady = useFontsReady();
  const { durationInFrames } = useVideoConfig();
  if (!fontsReady) return <AbsoluteFill style={{ backgroundColor: "#070b1a" }} />;
  return (
    <DebugContext.Provider value={debugChecks}>
      <AbsoluteFill style={{ backgroundColor: "#070b1a" }}>
        <Background />
        <SceneFor shot={{ scene: { type, props } }} frames={durationInFrames} />
      </AbsoluteFill>
    </DebugContext.Provider>
  );
};
