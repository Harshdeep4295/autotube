import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import { Explainer, SceneTest } from "./Explainer";
import { Thumbnail } from "./Thumbnail";
import { BrandBanner, BrandLogo, BrandProps, BrandWatermark } from "./brand/Brand";
import { FPS, H, W } from "./theme";
import { ExplainerProps, SceneTestProps, ThumbnailProps } from "./types";

const calc: CalculateMetadataFunction<ExplainerProps> = ({ props }) => {
  const last = props.shots[props.shots.length - 1];
  const end = last ? last.start + last.duration : 5;
  return { durationInFrames: Math.max(1, Math.round(end * FPS)) };
};

const demo: ExplainerProps = {
  shots: [
    { start: 0, duration: 4, speech: 3.5, text: "Run AI offline on your laptop.", emphasis: ["offline"],
      scene: { type: "title_hook", props: { headline: "RUN AI OFFLINE", subline: "on the laptop you already own", icon: "laptop" } } },
    { start: 4, duration: 4, speech: 3.5, text: "An 8B model needs about 5 GB.", emphasis: [],
      scene: { type: "big_number", props: { value: 5, prefix: "", unit: "GB", label: "for an 8B model at 4-bit", decimals: "0" } } },
  ],
  captions: [],
  voice: null,
  music: null,
  musicVolume: 0.08,
  channel: "Run It Local",
  showCaptions: true,
  debugChecks: false,
};

const BRAND: BrandProps = { name: "Run It Local", tagline: "Free & open-source AI you can run yourself" };

export const Root: React.FC = () => (
  <>
    <Composition id="Explainer" component={Explainer} fps={FPS} width={W} height={H} durationInFrames={240}
      defaultProps={demo} calculateMetadata={calc} />
    <Composition id="SceneTest" component={SceneTest} fps={FPS} width={W} height={H} durationInFrames={150}
      defaultProps={{ type: "key_point", props: { text: "Hello", sub: "", icon: "lightbulb" }, debugChecks: true } as SceneTestProps} />
    <Composition id="Thumbnail" component={Thumbnail} fps={FPS} width={1280} height={720} durationInFrames={1}
      defaultProps={{ text: "Run AI offline", subtext: "free", icon: "laptop", channel: "Run It Local" } as ThumbnailProps} />
    <Composition id="BrandLogo" component={BrandLogo} fps={FPS} width={800} height={800} durationInFrames={1}
      defaultProps={BRAND} />
    <Composition id="BrandBanner" component={BrandBanner} fps={FPS} width={2560} height={1440} durationInFrames={1}
      defaultProps={BRAND} />
    <Composition id="BrandWatermark" component={BrandWatermark} fps={FPS} width={150} height={150} durationInFrames={1}
      defaultProps={BRAND} />
  </>
);
