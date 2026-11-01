const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

test('synthetic replay exposes its limits, claim evidence and policy reference', async ({ page }) => {
  const filename = process.env.PREFLIGHT_REPLAY_REPORT;
  if (!filename) throw new Error('Set PREFLIGHT_REPLAY_REPORT to a generated replay report.html.');
  await page.route('**/*', route => route.abort());
  await page.setContent(fs.readFileSync(path.resolve(filename), 'utf8'));
  await expect(page.locator('body')).toContainText('Synthetic replay verification');
  await expect(page.locator('body')).toContainText('not a live model run');
  await expect(page.locator('body')).toContainText('Clinically proven formula');
  await expect(page.locator('body')).toContainText('12.1');
  const broken = await page.locator('img').evaluateAll(images =>
    images.filter(image => !image.complete || image.naturalWidth === 0).length);
  expect(broken).toBe(0);
});
