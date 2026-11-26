import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { type Browser, type BrowserContext, type Page, expect, test } from "@playwright/test";

const recording = process.env["DEMO_GIF"] === "1";
const SIZE = { width: 390, height: 640 };
// The two recordings, and how long after the first the second phone appears.
const DEMO = resolve(import.meta.dirname, "../test-results/demo");

/** Keep both phones' videos, and when the second one began, for scripts/demo-gif.ts. */
async function saveRecordings(first: Seat, second: Seat): Promise<void> {
  const videos = [first.page.video()!, second.page.video()!];
  await first.context.close();
  await second.context.close();
  mkdirSync(DEMO, { recursive: true });
  await videos[0]!.saveAs(resolve(DEMO, "ana.webm"));
  await videos[1]!.saveAs(resolve(DEMO, "bo.webm"));
  const joined = (second.opened - first.opened) / 1000;
  writeFileSync(resolve(DEMO, "timing.json"), JSON.stringify({ joined }));
}

interface Seat {
  context: BrowserContext;
  page: Page;
  errors: string[];
  /** When the page, and so its recording, began. */
  opened: number;
}

/** `typed` shows the name being typed, for a recording that is about joining. */
async function sit(
  browser: Browser,
  name: string,
  link = "/",
  record = false,
  typed = record,
): Promise<Seat> {
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
  if (typed) {
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
  if (recording) await saveRecordings(ana, bo);
  else {
    await ana.context.close();
    await bo.context.close();
  }
});

test("a player with too few chips is offered a free refill", async ({ browser }) => {
  const { context, page } = await sit(browser, "Cy");
  await page.getByRole("group", { name: "Chip" }).getByRole("button", { name: "100" }).tap();
  // Put the whole bankroll on the table, without rolling.
  for (const [spot, amount] of [
    ["Pass", "pass-null"],
    ["Place 4", "place-4"],
  ] as const) {
    for (let total = 100; total <= 500; total += 100) {
      await page.getByRole("button", { name: `Add chips to ${spot}`, exact: true }).tap();
      await expect(page.getByTestId(`amount-${amount}`)).toHaveText(`${total}`);
    }
  }
  await expect(page.getByTestId("bankroll")).toHaveText("0");
  const refill = page.getByRole("button", { name: "Refill chips" });
  expect((await refill.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  // Bets can still be taken down while the refill is on offer.
  await expect(page.getByRole("button", { name: "Take chips off", exact: true })).toBeVisible();

  await refill.tap();
  await expect(page.getByTestId("bankroll")).toHaveText("1000");
  await expect(refill).toHaveCount(0);

  await page.getByRole("button", { name: "Players" }).tap();
  await expect(page.getByRole("dialog")).toContainText(/Table ref [\w-]{8}/);
  await context.close();
});

test("pedantic mode is told to the table and lowers the smallest bet", async ({ browser }) => {
  test.setTimeout(60_000);
  // Its recording starts at the table: joining is what the other one shows.
  const ana = await sit(browser, "Ana", "/", recording, false);
  const bo = await sit(browser, "Bo", ana.page.url(), recording, false);
  const [a, b] = [ana.page, bo.page];
  const pause = (ms: number) => (recording ? a.waitForTimeout(ms) : Promise.resolve());
  const players = (page: Page) => page.getByRole("button", { name: "Players" });
  const panel = (page: Page) => page.getByRole("dialog", { name: "Players" });
  const toggle = panel(b).getByRole("button", { name: /^Pedantic mode/ });
  const back = panel(b).getByRole("button", { name: "Back to the table" });

  await pause(1_500);
  await players(b).tap();
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await pause(1_800);
  await toggle.tap();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  for (const page of [a, b]) {
    await expect(page.getByText("Pedantic mode enabled for Bo")).toBeVisible();
  }
  // Gone by itself, without a tap.
  await pause(2_000);
  await back.tap();
  await expect(a.getByText("Pedantic mode enabled for Bo")).toBeHidden({ timeout: 8_000 });

  const three = b.getByRole("button", { name: "Add chips to Place 3", exact: true });
  await b.getByRole("group", { name: "Chip" }).getByRole("button", { name: "1", exact: true }).tap();
  await pause(900);
  await three.tap();
  await expect(b.getByTestId("amount-place-3")).toHaveText("4");
  await pause(2_000);

  // Switching off leaves the small bet up. The recording skips this and goes on to the rules.
  if (!recording) {
    await players(b).tap();
    await toggle.tap();
    await expect(a.getByText("Pedantic mode disabled for Bo")).toBeVisible();
    await back.tap();
    await expect(b.getByTestId("amount-place-3")).toHaveText("4");
  }

  // It ends on what it all means.
  await b.getByRole("button", { name: "How to play" }).tap();
  const rules = b.getByRole("dialog", { name: "How to play" });
  const heading = rules.getByRole("heading", { name: "Pedantic mode" });
  await pause(1_500);
  await heading.evaluate(
    (element, smooth) =>
      element.scrollIntoView({ behavior: smooth ? "smooth" : "instant", block: "start" }),
    recording,
  );
  await expect(heading).toBeInViewport();
  await expect(rules.getByText("Switch it on from the top button")).toBeInViewport({ ratio: 1 });
  await pause(7_000);

  expect([...ana.errors, ...bo.errors]).toEqual([]);
  if (recording) await saveRecordings(ana, bo);
  else {
    await ana.context.close();
    await bo.context.close();
  }
});

test("a full table's players panel can be scrolled to its first player", async ({ browser }) => {
  const first = await sit(browser, "Ana");
  const others = [];
  for (const name of ["Bo", "Cy", "Dee", "Eli", "Fay", "Gus", "Hal"]) {
    others.push(await sit(browser, name, first.page.url()));
  }
  const page = first.page;
  await page.setViewportSize({ width: 360, height: 560 });
  await page.getByRole("button", { name: "Players" }).tap();
  const players = page.getByRole("dialog", { name: "Players" }).getByRole("listitem");
  await expect(players).toHaveCount(8);
  const back = page.getByRole("button", { name: "Back to the table" });
  await expect(back).toBeInViewport({ ratio: 1 });
  await players.first().scrollIntoViewIfNeeded();
  await expect(players.first()).toBeInViewport({ ratio: 1 });
  await expect(back).toBeInViewport({ ratio: 1 });
  for (const seat of [first, ...others]) await seat.context.close();
});

test("how to play can be read before and after sitting down", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 360, height: 560 } });
  const page = await context.newPage();
  await page.goto("/");
  const open = page.getByRole("button", { name: "How to play" });
  const rules = page.getByRole("dialog", { name: "How to play" });
  const close = rules.getByRole("button", { name: "Close" });

  for (const seated of [false, true]) {
    if (seated) {
      await page.getByRole("textbox", { name: "Your name" }).fill("Dee");
      await page.getByRole("button", { name: "Sit down" }).click();
    }
    await open.click();
    await expect(rules).toContainText("seven-out");
    // Close stays on screen however long the words are, and the words scroll to the end.
    await expect(close).toBeInViewport();
    await rules.getByText("A seat is kept for 10 minutes").scrollIntoViewIfNeeded();
    await expect(rules.getByText("A seat is kept for 10 minutes")).toBeInViewport();
    await close.click();
    await expect(rules).toHaveCount(0);
  }
  await context.close();
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
    const switcher = panel.getByRole("button", { name: /^Pedantic mode/ });
    await switcher.scrollIntoViewIfNeeded();
    expect((await switcher.boundingBox())!.height).toBeGreaterThanOrEqual(44);
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
