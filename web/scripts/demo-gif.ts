// Re-records docs/demo.gif: plays the browser test slowly with video on, then converts the
// video with ffmpeg in Docker (an image pinned by digest, so nothing is installed).
//
//   npm run demo:gif --prefix web      (needs Docker and `npx playwright install chromium`)
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, statSync } from "node:fs";
import { resolve } from "node:path";

const FFMPEG =
  "jrottenberg/ffmpeg:9.0.1-alpine320@sha256:2c3d71587b80173373ff52f2573ec5be9f527f2ba4fe601de6641299b1d68211";
const web = resolve(import.meta.dirname, "..");
const root = resolve(web, "..");
const work = resolve(web, "test-results");

execFileSync("npx", ["playwright", "test"], {
  cwd: web,
  stdio: "inherit",
  env: { ...process.env, DEMO_GIF: "1" },
});

// 10 frames a second and one shared palette keep the file small.
const filter = [
  "[0:v]fps=10,scale=320:-1:flags=lanczos,split[a][b]",
  "[a]palettegen=max_colors=64:stats_mode=diff[p]",
  "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
].join(";");
const user = `${process.getuid?.() ?? 0}:${process.getgid?.() ?? 0}`;
execFileSync(
  "docker",
  ["run", "--rm", "--network", "none", "--user", user, "-v", `${work}:/work`, "-w", "/work", FFMPEG]
    .concat(["-hide_banner", "-loglevel", "error", "-y", "-i", "demo/hand.webm"])
    .concat(["-filter_complex", filter, "-loop", "0", "demo/hand.gif"]),
  { stdio: "inherit" },
);

mkdirSync(resolve(root, "docs"), { recursive: true });
copyFileSync(resolve(work, "demo/hand.gif"), resolve(root, "docs/demo.gif"));
console.log(`docs/demo.gif: ${(statSync(resolve(root, "docs/demo.gif")).size / 1e6).toFixed(1)} MB`);
