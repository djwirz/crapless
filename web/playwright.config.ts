// The browser test: one hand on a phone-sized screen, against the real server with scripted
// dice (scripts/demo_server.py). `npm run demo:gif` records the same run for the README.
import { defineConfig, devices } from "@playwright/test";

const URL = "http://127.0.0.1:8766";

export default defineConfig({
  testDir: "e2e",
  testMatch: "*.e2e.ts",
  workers: 1,
  // The scripted dice run in order, so a retry needs a fresh server, not a rerun.
  retries: 0,
  reporter: "list",
  use: { ...devices["Pixel 7"], baseURL: URL, trace: "retain-on-failure" },
  webServer: {
    command: "npm run build && uv run python ../scripts/demo_server.py",
    url: `${URL}/healthz`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
