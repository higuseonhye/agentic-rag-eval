import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

// Prefer IPv4 loopback because some environments refuse IPv6 localhost.
// Allow overriding via argv: `node take_screenshots.mjs http://127.0.0.1:4000`
const baseUrl = process.argv[2] ?? process.env.BASE_URL ?? "http://127.0.0.1:3999";
const outDir = process.env.OUT_DIR ?? path.resolve(process.cwd(), "..", "docs", "screenshots");

async function main() {
  await fs.mkdir(outDir, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const shots = [
    { url: `${baseUrl}/`, file: "home.png" },
    { url: `${baseUrl}/traces`, file: "traces.png" },
    { url: `${baseUrl}/evaluations`, file: "evaluations.png" },
  ];

  for (const s of shots) {
    await page.goto(s.url, { waitUntil: "networkidle" });
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(outDir, s.file), fullPage: true });
    // eslint-disable-next-line no-console
    console.log(`wrote ${path.join(outDir, s.file)}`);
  }

  await browser.close();
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});

