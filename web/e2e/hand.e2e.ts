import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { type Page, expect, test } from "@playwright/test";

const recording = process.env["DEMO_GIF"] === "1";
const SIZE = { width: 390, height: 640 };
const VIDEO = resolve(import.meta.dirname, "../test-results/demo/hand.webm");

test("a hand: bets, a travelling Come bet, and the point made", async ({ browser }) => {
  test.setTimeout(90_000);
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
  const add = async (spot: string, amount: string, total: number) => {
    await page.getByRole("button", { name: `Add chips to ${spot}`, exact: true }).tap();
    await expect(page.getByTestId(`amount-${amount}`)).toHaveText(`${total}`);
    await pause(450);
  };
  const rollButton = page.getByRole("button", { name: "Roll", exact: true });
  // The bankroll must not move until the dice have landed.
  const roll = async (result: string, bankroll: number, point: string, flick = false) => {
    const before = await page.getByTestId("bankroll").textContent();
    if (flick) await flickDice(page);
    else await rollButton.tap();
    await expect(page.getByTestId("result")).toHaveText("…");
    await expect(page.getByTestId("bankroll")).toHaveText(before!);
    await expect(page.getByTestId("result")).toHaveText(result);
    await expect(page.getByTestId("bankroll")).toHaveText(`${bankroll}`);
    await expect(page.getByTestId("point")).toHaveText(point);
    await pause(1_900);
  };

  await page.goto("/");
  await pause(1_200);
  await add("Pass", "pass-null", 5);
  await add("Pass", "pass-null", 10);
  await roll("3 + 3 = 6", 990, "Point 6");
  await expect(page.getByTestId("banner")).toHaveText("The point is 6");

  await chip(25).tap();
  await add("Pass odds", "pass_odds-null", 25);
  await chip(5).tap();
  await add("Come", "come-null", 5);
  await add("Come", "come-null", 10);
  await add("Place 8", "place-8", 6);
  await add("Place 8", "place-8", 12);
  await roll("5 + 4 = 9", 943, "Point 6", true);

  await chip(25).tap();
  await add("Come 9 odds", "come_odds-9", 26);
  await roll("4 + 4 = 8 +14", 931, "Point 6");

  await roll("6 + 3 = 9 +49", 1016, "Point 6");
  await roll("4 + 2 = 6 +40", 1091, "Come-out");
  await expect(page.getByTestId("banner")).toHaveText("Point 6 made!");
  await pause(1_500);

  const video = page.video();
  if (!video) {
    // Coming back shows the table as it was, without throwing the dice again.
    await page.reload();
    await expect(page.getByTestId("result")).toHaveText("4 + 2 = 6");
    await expect(page.getByTestId("bankroll")).toHaveText("1091");
    await expect(page.getByTestId("banner")).toHaveCount(0);
  }

  expect(errors).toEqual([]);
  await context.close();
  if (video) {
    mkdirSync(resolve(VIDEO, ".."), { recursive: true });
    await video.saveAs(VIDEO);
  }
});

// Small phones, with the browser's bars taking their share of the height.
for (const viewport of [
  { width: 360, height: 560 },
  { width: 375, height: 553 },
  { width: 430, height: 750 },
]) {
  test(`the table fits ${viewport.width} by ${viewport.height}`, async ({ browser }) => {
    const context = await browser.newContext({ viewport, isMobile: true, hasTouch: true });
    const page = await context.newPage();
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Roll", exact: true })).toBeVisible();

    const buttons = await page.getByRole("button").all();
    expect(buttons.length).toBeGreaterThan(15);
    for (const button of buttons) {
      const box = (await button.boundingBox())!;
      const name = (await button.getAttribute("aria-label")) ?? "?";
      expect(Math.min(box.width, box.height), `${name} is big enough`).toBeGreaterThanOrEqual(44);
      expect(box.y + box.height, `${name} is on screen`).toBeLessThanOrEqual(viewport.height);
      expect(box.x + box.width, `${name} is on screen`).toBeLessThanOrEqual(viewport.width);
    }
    const scrolls = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollHeight > root.clientHeight || root.scrollWidth > root.clientWidth;
    });
    expect(scrolls).toBe(false);
    await context.close();
  });
}

async function flickDice(page: Page): Promise<void> {
  const box = (await page.locator("g.dice .area").boundingBox())!;
  const x = box.x + box.width / 2;
  await page.mouse.move(x, box.y + box.height - 8);
  await page.mouse.down();
  await page.mouse.move(x, box.y + 4, { steps: 4 });
  await page.mouse.up();
}

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
