import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { type Page, expect, test } from "@playwright/test";

const recording = process.env["DEMO_GIF"] === "1";
const SIZE = { width: 390, height: 844 };
const VIDEO = resolve(import.meta.dirname, "../test-results/demo/hand.webm");

test("a hand: bets, a travelling Come bet, and the point made", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: SIZE,
    isMobile: true,
    hasTouch: true,
    colorScheme: "dark",
    ...(recording ? { recordVideo: { dir: resolve(VIDEO, ".."), size: SIZE } } : {}),
  });
  const page = await context.newPage();
  if (recording) await showTaps(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  // Only the recording lingers, so that a person can follow it.
  const pause = (ms: number) => (recording ? page.waitForTimeout(ms) : Promise.resolve());

  const chip = (value: number) =>
    page.getByRole("group", { name: "Chip" }).getByRole("button", { name: `${value}`, exact: true });
  const add = async (spot: string, total: number) => {
    const button = page.getByRole("button", { name: `Add chips to ${spot}`, exact: true });
    await button.tap();
    await expect(page.locator(".spot", { has: button }).locator(".amount")).toHaveText(`${total}`);
    await pause(500);
  };
  const roll = async (summary: string) => {
    await page.getByRole("button", { name: "Roll", exact: true }).tap();
    await expect(page.locator(".summary")).toHaveText(summary);
    await pause(900);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await pause(1_600);
  };

  await page.goto("/");
  await pause(1_200);
  await add("Pass", 5);
  await add("Pass", 10);
  await roll("Rolled 6 · Point 6 · Bankroll 990");

  await chip(25).tap();
  await add("Pass odds", 25);
  await chip(5).tap();
  await add("Come", 5);
  await add("Come", 10);
  await add("Place 8", 6);
  await add("Place 8", 12);
  await roll("Rolled 9 · Point 6 · Bankroll 943");

  await chip(25).tap();
  await add("Come 9 odds", 26);
  await roll("Rolled 8 · Point 6 · Bankroll 931");
  await expect(page.getByText("Place 8: won 14")).toBeVisible();

  await roll("Rolled 9 · Point 6 · Bankroll 1016");
  await expect(page.getByText("Come 9 odds: won 39")).toBeVisible();

  await roll("Rolled 6 · Come-out · Bankroll 1091");
  await expect(page.getByText("Pass odds: won 30")).toBeVisible();
  await pause(2_000);

  expect(errors).toEqual([]);
  const video = page.video();
  await context.close();
  if (video) {
    mkdirSync(resolve(VIDEO, ".."), { recursive: true });
    await video.saveAs(VIDEO);
  }
});

/** A recording has no finger in it, so mark each tap. */
async function showTaps(page: Page): Promise<void> {
  await page.addInitScript(() => {
    document.addEventListener(
      "pointerdown",
      ({ clientX, clientY }) => {
        const dot = document.createElement("div");
        dot.style.cssText = `position:fixed;left:${clientX - 22}px;top:${clientY - 22}px;
          width:44px;height:44px;border-radius:50%;background:rgb(255 200 0 / 55%);
          pointer-events:none;z-index:9999`;
        document.body.append(dot);
        setTimeout(() => dot.remove(), 350);
      },
      true,
    );
  });
}
