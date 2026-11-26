// Whether the README GIFs still show the page as it is. The tests that play them note the markup
// of the screens along the way. scripts/demo-gif.ts keeps those notes beside each new GIF, and
// an ordinary run compares with them. Markup, not pixels: fonts differ between machines.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, type Locator } from "@playwright/test";

const web = resolve(import.meta.dirname, "..");

export function looks(gif: "table" | "pedantic", recording: boolean) {
  // Styling changes what is seen without changing the markup. Comments and spacing do not.
  const css = readFileSync(resolve(web, "src/styles.css"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\s+/g, " ");
  const screens = [`styles.css ${createHash("sha256").update(css).digest("hex")}`];

  return {
    async see(title: string, what: Locator): Promise<void> {
      const markup = await what.evaluate((element) => element.outerHTML);
      const steady = markup
        // Different on every run, or on every machine.
        .replace(/Table ref [\w-]+/g, "Table ref …")
        .replace(/<label class="link">.*?<\/label>/g, "")
        // A line per element, so that a change can be read in a diff.
        .replace(/></g, ">\n<");
      screens.push(`== ${title}\n${steady}`);
    },

    check(): void {
      const now = `${screens.join("\n")}\n`;
      if (recording) {
        // Only kept once the GIF has been made from this run.
        mkdirSync(resolve(web, "test-results/demo"), { recursive: true });
        writeFileSync(resolve(web, "test-results/demo/look.html"), now);
        return;
      }
      const kept = readFileSync(resolve(web, `e2e/looks/${gif}.html`), "utf8");
      expect(
        now,
        `A screen in the ${gif} GIF has changed. Re-record it, and commit the GIF with its ` +
          `look: npm run demo:gif --prefix web -- ${gif}`,
      ).toBe(kept);
    },
  };
}
