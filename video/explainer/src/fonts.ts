import { useEffect, useState } from "react";
import { continueRender, delayRender } from "remotion";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/800.css";

/**
 * Wait for the bundled Inter font (OFL) and return true once it is usable.
 * Compositions render nothing until then: text auto-fitting measures (and caches)
 * text widths, so measuring with a fallback font would size text wrongly.
 *
 * Called inside the composition components, NOT at module load: a module-level
 * loadFont() also runs in the page Remotion keeps open only to read composition
 * metadata; that page never renders, its delayRender() times out and cancels any
 * render longer than the timeout.
 */
export const useFontsReady = (): boolean => {
  const [handle] = useState(() => delayRender("Loading Inter font"));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const weights = ["400", "600", "800"];
    Promise.all(weights.map((w) => document.fonts.load(`${w} 40px Inter`)))
      .catch((e) => console.warn("font load failed", e))
      .finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (ready) continueRender(handle); // after the ready re-render has committed
  }, [ready, handle]);
  return ready;
};
