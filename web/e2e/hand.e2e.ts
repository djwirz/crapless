import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { type Browser, type BrowserContext, type Page, expect, test } from "@playwright/test";

const recording = process.env["DEMO_GIF"] === "1";
const SIZE = { width: 390, height: 640 };
// The two recordings, and how long after the first the second phone appears.
const DEMO = resolve(import.meta.dirname, "../test-results/demo");

interface Seat {
  context: BrowserContext;
  page: Page;
  errors: string[];
  /** When the page, and so its recording, began. */
  opened: number;
}

async function sit(browser: Browser, name: string, link = "/", record = false): Promise<Seat> {
  const context = await browser.newContext({
    viewport: SIZE,
    isMobile: true,
    hasTouch: true,
    colorScheme: "dark",
    ...(record ? { recordVideo: { dir: DEMO, size: SIZE } } : {}),
  });
  const page = await context.newPage();
  const opened = Date.now();
  if (record) await showTaps(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(link);
  const field = page.getByRole("textbox", { name: "Your name" });
  if (record) {
    await page.waitForTimeout(900);
    await field.pressSequentially(name, { delay: 180 });
    await page.waitForTimeout(500);
  } else await field.fill(name);
  await page.getByRole("button", { name: "Sit down" }).tap();
  await expect(page.getByTestId("bankroll")).toHaveText("1000");
  return { context, page, errors, opened };
}

// Two phones at one table, each taking a full turn with the dice (spec §8).
test("two players, a shooter turn each", async ({ browser }) => {
  test.setTimeout(120_000);
  const ana = await sit(browser, "Ana", "/", recording);
  const a = ana.page;
  await expect(a).toHaveURL(/#t=[\w-]{12,}$/);
  // Only the recording lingers, so that a person can follow it.
  const pause = (ms: number) => (recording ? a.waitForTimeout(ms) : Promise.resolve());

  // Ana invites; Bo opens the link the panel shows.
  await pause(900);
  await a.getByRole("button", { name: "Players" }).tap();
  const panel = a.getByRole("dialog", { name: "Players" });
  await pause(900);
  await panel.getByRole("button", { name: "Invite" }).tap();
  const link = await panel.getByRole("textbox").inputValue();
  expect(link).toBe(a.url());
  await pause(1_800);
  const bo = await sit(browser, "Bo", link, recording);
  const b = bo.page;
  await expect(panel).toContainText("Bo");
  await pause(1_800);
  await panel.getByRole("button", { name: "Back to the table" }).tap();

  const chip = (page: Page, value: number) =>
    page.getByRole("group", { name: "Chip" }).getByRole("button", { name: `${value}`, exact: true });
  const add = async (page: Page, spot: string, amount: string, total: number) => {
    await page.getByRole("button", { name: `Add chips to ${spot}`, exact: true }).tap();
    await expect(page.getByTestId(`amount-${amount}`)).toHaveText(`${total}`);
    await pause(450);
  };
  const rollButton = (page: Page) => page.getByRole("button", { name: "Roll", exact: true });
  // Both phones see the same dice, and neither bankroll moves until they have landed.
  const roll = async (by: Page, result: RegExp, point: string, flick = false) => {
    if (flick) {
      await expect(rollButton(by)).toBeEnabled(); // held a moment after another's bet
      await flickDice(by);
    } else await rollButton(by).tap();
    for (const page of [a, b]) await expect(page.getByTestId("result")).toHaveText("…");
    for (const page of [a, b]) {
      await expect(page.getByTestId("result")).toHaveText(result);
      await expect(page.getByTestId("point")).toHaveText(point);
    }
    await pause(1_500);
  };
  const bankrolls = async (anas: number, bos: number) => {
    await expect(a.getByTestId("bankroll")).toHaveText(`${anas}`);
    await expect(b.getByTestId("bankroll")).toHaveText(`${bos}`);
  };

  await pause(1_200);
  await expect(rollButton(b)).toBeDisabled();
  await add(a, "Pass", "pass-null", 5);
  await add(a, "Pass", "pass-null", 10);
  await add(b, "Pass", "pass-null", 5);
  await expect(a.getByTestId("dot-pass")).toHaveCount(1);
  await roll(a, /^3 \+ 3 = 6$/, "Point 6");

  await chip(a, 25).tap();
  await add(a, "Pass odds", "pass_odds-null", 25);
  await chip(a, 5).tap();
  await add(a, "Come", "come-null", 5);
  await add(a, "Come", "come-null", 10);
  await add(a, "Place 8", "place-8", 6);
  await add(a, "Place 8", "place-8", 12);
  await add(b, "Place 5", "place-5", 5);
  await expect(a.getByTestId("dot-place:5")).toHaveCount(1);
  await roll(a, /^5 \+ 4 = 9$/, "Point 6", true);

  // Coming back finds the seat and the chips, and does not throw the dice again.
  if (!recording) {
    await b.reload();
    await expect(b.getByTestId("bankroll")).toHaveText("990");
    await expect(b.getByTestId("amount-place-5")).toHaveText("5");
    await expect(b.getByTestId("result")).not.toHaveText("…");
    await expect(b.getByTestId("banner")).toHaveCount(0);
  }

  await chip(a, 25).tap();
  await add(a, "Come 9 odds", "come_odds-9", 26);
  await roll(a, /^4 \+ 4 = 8/, "Point 6");
  // Each phone shows its own winnings.
  await expect(a.getByTestId("result")).toContainText("+14");
  await expect(b.getByTestId("result")).not.toContainText("+14");
  await bankrolls(931, 990);

  await roll(a, /^3 \+ 4 = 7 /, "Come-out");
  await expect(a.getByTestId("banner")).toHaveText("Seven out");
  await bankrolls(931, 990);

  // The dice have moved to the left.
  await expect(rollButton(a)).toBeDisabled();
  await expect(a.getByRole("button", { name: "Players" })).toContainText("Bo · 2");
  await expect(b.getByRole("button", { name: "Players" })).toContainText("Your dice · 2");
  await add(b, "Pass", "pass-null", 5);
  await pause(600);
  await roll(b, /^2 \+ 2 = 4/, "Point 4");
  await roll(b, /^4 \+ 3 = 7/, "Come-out");
  await bankrolls(931, 985);
  await expect(a.getByRole("button", { name: "Players" })).toContainText("Your dice · 2");

  await a.getByRole("button", { name: "Players" }).tap();
  await expect(panel).toContainText("985");
  await pause(2_500);

  expect([...ana.errors, ...bo.errors]).toEqual([]);
  const videos = [a.video(), b.video()];
  await ana.context.close();
  await bo.context.close();
  if (recording) {
    mkdirSync(DEMO, { recursive: true });
    await videos[0]!.saveAs(resolve(DEMO, "ana.webm"));
    await videos[1]!.saveAs(resolve(DEMO, "bo.webm"));
    const joined = (bo.opened - ana.opened) / 1000;
    writeFileSync(resolve(DEMO, "timing.json"), JSON.stringify({ joined }));
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
    await page.getByRole("textbox", { name: "Your name" }).fill("Wwwwwwwwwwww");
    await page.getByRole("button", { name: "Sit down" }).tap();

    const check = async (least: number) => {
      const buttons = await page.getByRole("button").all();
      expect(buttons.length).toBeGreaterThan(least);
      for (const button of buttons) {
        const box = (await button.boundingBox())!;
        const name = (await button.getAttribute("aria-label")) ?? (await button.innerText());
        expect(Math.min(box.width, box.height), `${name} is big enough`).toBeGreaterThanOrEqual(44);
        expect(box.y + box.height, `${name} is on screen`).toBeLessThanOrEqual(viewport.height);
        expect(box.x + box.width, `${name} is on screen`).toBeLessThanOrEqual(viewport.width);
      }
    };
    await expect(page.getByRole("button", { name: "Roll", exact: true })).toBeVisible();
    await check(15);
    // The button must not run into the numbers either side of it.
    const who = (await page.locator(".who .area").boundingBox())!;
    const point = (await page.getByTestId("point").boundingBox())!;
    const bankroll = (await page.getByTestId("bankroll").boundingBox())!;
    expect(who.x + who.width).toBeLessThanOrEqual(point.x);
    expect(bankroll.x + bankroll.width).toBeLessThanOrEqual(who.x);
    const scrolls = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollHeight > root.clientHeight || root.scrollWidth > root.clientWidth;
    });
    expect(scrolls).toBe(false);

    await page.getByRole("button", { name: "Players" }).tap();
    const panel = page.getByRole("dialog", { name: "Players" });
    await panel.getByRole("button", { name: "Invite" }).tap();
    await expect(panel.getByRole("textbox")).toHaveValue(/#t=[\w-]{12,}$/);
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
