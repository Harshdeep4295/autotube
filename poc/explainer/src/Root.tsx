import React from "react";
import { Composition } from "remotion";
import { Explainer } from "./Explainer";
import { SCENES } from "./data";

const FPS = 30;
const last = SCENES[SCENES.length - 1];

export const Root: React.FC = () => (
  <Composition
    id="Explainer"
    component={Explainer}
    durationInFrames={Math.round((last.start + last.dur) * FPS)}
    fps={FPS}
    width={1920}
    height={1080}
    defaultProps={{ captions: true }}
  />
);
