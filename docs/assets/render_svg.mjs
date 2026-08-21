// Rasterise every hero SVG to a PNG so it can be looked at.
// SVG text does not wrap or elide; the source cannot show a clipped line.
//   node render_svg.mjs            # renders every *-light.svg and *-dark.svg here
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));

function findPlaywright() {
  let dir = here;
  for (;;) {
    for (const name of ["playwright", "playwright-core", "@playwright/test"]) {
      if (existsSync(join(dir, "node_modules", name))) return { base: dir, name };
      const fe = join(dir, "frontend", "node_modules", name);
      if (existsSync(fe)) return { base: join(dir, "frontend"), name };
    }
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

const found = findPlaywright();
if (!found) {
  console.error("playwright not found; run: npm install --no-save playwright");
  process.exit(2);
}
const require = createRequire(join(found.base, "noop.js"));
const mod = await import(pathToFileURL(require.resolve(found.name)).href);
const chromium = mod.chromium ?? mod.default?.chromium;

const svgs = readdirSync(here).filter((f) => f.endsWith(".svg"));
const browser = await chromium.launch();
for (const svg of svgs) {
  const body = readFileSync(join(here, svg), "utf8");
  const m = body.match(/height="([\d.]+)"/);
  const wm = body.match(/width="([\d.]+)"/);
  const height = m ? Math.ceil(Number(m[1])) : 800;
  const width = wm ? Math.ceil(Number(wm[1])) : 1280;
  const page = await browser.newPage({ viewport: { width, height } });
  await page.goto(pathToFileURL(join(here, svg)).href);
  const out = join(here, svg.replace(/\.svg$/, ".png"));
  await page.screenshot({ path: out });
  await page.close();
  console.log(`rendered ${svg} -> ${width}x${height}`);
}
await browser.close();
