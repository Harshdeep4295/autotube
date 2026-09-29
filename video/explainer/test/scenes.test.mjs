// Scene tests: render every fixture (catalogue example + every-limit "max" case) as a
// still with debug overflow checks on. Fails if any scene logs OVERFLOW (text clipped
// or pushed out of the safe area) or fails to render.
//
//   npm run test:scenes            # all scenes
//   SCENE=bar_chart npm run test:scenes
//
// Fixtures come from agents/scene_schema.py:  python -m agents.scene_schema --fixtures > test/fixtures.json
// Stills are written to test-output/scenes/ for a human look (CI uploads them as an artifact).
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const outDir = path.join(root, "test-output", "scenes");
fs.mkdirSync(outDir, { recursive: true });

const only = process.env.SCENE;
const fixtures = JSON.parse(fs.readFileSync(path.join(here, "fixtures.json"), "utf8")).filter(
  (f) => !only || f.type === only,
);
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || null;

const serveUrl = await bundle({ entryPoint: path.join(root, "src", "index.ts") });
const browser = await openBrowser("chrome", { browserExecutable });
const failures = [];

for (const fx of fixtures) {
  const inputProps = { type: fx.type, props: fx.props, debugChecks: true };
  const logs = [];
  try {
    const composition = await selectComposition({ serveUrl, id: "SceneTest", inputProps, puppeteerInstance: browser, browserExecutable });
    await renderStill({
      composition, serveUrl, inputProps, frame: 130, puppeteerInstance: browser, browserExecutable,
      output: path.join(outDir, `${fx.id}.png`),
      onBrowserLog: (l) => logs.push(l.text),
    });
    const overflow = logs.filter((t) => t.includes("OVERFLOW"));
    if (overflow.length) failures.push(`${fx.id}: ${overflow.join(" | ")}`);
    console.log(`${overflow.length ? "✗" : "✓"} ${fx.id}`);
  } catch (e) {
    failures.push(`${fx.id}: render error ${String(e).slice(0, 300)}`);
    console.log(`✗ ${fx.id} (render error)`);
  }
}
await browser.close({ silent: true });

if (failures.length) {
  console.error(`\n${failures.length} scene fixture(s) failed:\n` + failures.join("\n"));
  process.exit(1);
}
console.log(`\nAll ${fixtures.length} scene fixtures passed.`);
