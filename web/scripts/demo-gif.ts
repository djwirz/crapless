// Re-records the README GIFs: plays a browser test slowly with video on both phones, then puts
// them side by side with ffmpeg in Docker (an image pinned by digest, so nothing is installed).
// The second phone slides up when it joins.
//
//   npm run demo:gif --prefix web                  every GIF
//   npm run demo:gif --prefix web -- pedantic      just one
//
// Needs Docker and `npx playwright install chromium`.
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";

const FFMPEG =
  "jrottenberg/ffmpeg:9.0.1-alpine320@sha256:2c3d71587b80173373ff52f2573ec5be9f527f2ba4fe601de6641299b1d68211";
const web = resolve(import.meta.dirname, "..");
const root = resolve(web, "..");
const work = resolve(web, "test-results");

/** Each GIF: the browser test that plays it, and where it goes. */
const GIFS = {
  table: { test: "two players", file: "docs/demo.gif" },
  pedantic: { test: "pedantic mode", file: "docs/pedantic.gif" },
};

const asked = process.argv.slice(2);
const unknown = asked.filter((name) => !(name in GIFS));
if (unknown.length) {
  throw new Error(`No such GIF: ${unknown.join(", ")}. Try ${Object.keys(GIFS).join(" or ")}.`);
}
const names = (asked.length ? asked : Object.keys(GIFS)) as (keyof typeof GIFS)[];

function record(name: keyof typeof GIFS): void {
  const { test, file } = GIFS[name];
  // Playwright empties test-results first, so each recording starts clean.
  execFileSync("npx", ["playwright", "test", "--grep", test], {
    cwd: web,
    stdio: "inherit",
    env: { ...process.env, DEMO_GIF: "1" },
  });

  const { joined } = JSON.parse(readFileSync(resolve(work, "demo/timing.json"), "utf8")) as {
    joined: number;
  };

  // Two 390 px phones with a 12 px gap. The second is delayed by when it joined, and slides up
  // over 0.4 s. Few frames and colors, and one shared palette, keep the file small.
  const filter = [
    "[0:v]setpts=PTS-STARTPTS,fps=8,pad=iw*2+12:ih:0:0:color=0x120a05[table]",
    `[1:v]setpts=PTS-STARTPTS+${joined}/TB,fps=8[second]`,
    `[table][second]overlay=x=(W+12)/2:y='max(0,H-(t-${joined})*H/0.4)':enable='gte(t,${joined})'[both]`,
    "[both]scale=640:-1:flags=lanczos,split[a][b]",
    "[a]palettegen=max_colors=64:stats_mode=diff[p]",
    "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
  ].join(";");
  const user = `${process.getuid?.() ?? 0}:${process.getgid?.() ?? 0}`;
  execFileSync(
    "docker",
    ["run", "--rm", "--network", "none", "--user", user, "-v", `${work}:/work`, "-w", "/work", FFMPEG]
      .concat(["-hide_banner", "-loglevel", "error", "-y"])
      .concat(["-i", "demo/ana.webm", "-i", "demo/bo.webm"])
      .concat(["-filter_complex", filter, "-loop", "0", "demo/out.gif"]),
    { stdio: "inherit" },
  );

  mkdirSync(resolve(root, "docs"), { recursive: true });
  copyFileSync(resolve(work, "demo/out.gif"), resolve(root, file));
  // What the page looked like in this GIF, for the browser tests to compare with.
  mkdirSync(resolve(web, "e2e/looks"), { recursive: true });
  copyFileSync(resolve(work, "demo/look.html"), resolve(web, `e2e/looks/${name}.html`));
  console.log(`${file}: ${(statSync(resolve(root, file)).size / 1e6).toFixed(1)} MB`);
}

for (const name of names) record(name);
