import { test, expect } from '@playwright/test';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '../..');

test('three labelled demo states, honest scoreboard and explicit reveal', async ({
  page,
}, testInfo) => {
  const exceptions: string[] = [];
  page.on('pageerror', (e) => exceptions.push(e.message));
  await page.goto('/');
  await expect(page.getByText('Network-blocked synthetic replay.', { exact: false })).toBeVisible();
  await expect(page.getByRole('note')).toContainText('a person makes that call');
  await page.getByRole('button', { name: 'Explore demos' }).click();
  await expect(page.getByRole('heading', { name: 'Registered test scoreboard' })).toBeVisible();
  await expect(
    page.getByText('No registered final test run is selected.', { exact: false }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Synthetic replay · flagged', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Synthetic replay · flagged' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Source provenance' }).first()).toBeVisible();
  const video = page.getByRole('region', { name: 'Ad and claim timeline' }).locator('video');
  await expect(video).toBeVisible();
  const buttons = page.locator('.timeline button');
  await expect(buttons.first()).toBeVisible();
  await buttons.last().click();
  await expect(buttons.last()).toHaveAttribute('aria-pressed', 'true');
  const time = (await buttons.last().locator('time').innerText()).split(':').map(Number);
  await expect
    .poll(() => video.evaluate((v) => (v as HTMLVideoElement).currentTime))
    .toBeCloseTo(time[0] * 60 + time[1], 0);
  await page.getByRole('button', { name: 'Reveal ASA outcome' }).click();
  await expect(page.getByText('Team-made synthetic fixture. No ASA outcome exists.')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('demo.png'), fullPage: true });
  await page.getByRole('button', { name: 'Synthetic replay · no flags', exact: false }).click();
  await expect(page.locator('.headline')).toContainText('No issues found against');
  await expect(page.getByRole('button', { name: 'Reveal ASA outcome' })).toBeVisible();
  await page.getByRole('button', { name: 'Synthetic replay · incomplete', exact: false }).click();
  await expect(page.locator('.headline')).toContainText('Incomplete');
  await expect(page.getByRole('button', { name: 'Record my review decision' })).toHaveCount(0);
  expect(exceptions).toEqual([]);
});

test('fresh upload uses SSE, compares fix rounds, records an explicit synthetic decision and survives reload', async ({
  page,
}, testInfo) => {
  let polling = 0;
  page.on('request', (request) => {
    if (/^\/jobs\/[a-f0-9]{32}$/.test(new URL(request.url()).pathname)) polling += 1;
  });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page
    .getByLabel('Upload ad')
    .setInputFiles(path.join(root, 'tests/fixtures/models/media/captions.mp4'));
  await expect(page.getByRole('heading', { name: 'Screening evidence' })).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByRole('heading', { name: 'Source provenance' }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Prepare revision', exact: true }).click();
  await page
    .getByLabel('Scene still')
    .setInputFiles(path.join(root, 'tests/fixtures/agent/magnesium/still.png'));
  await page
    .getByLabel('On-screen captions')
    .fill('Magnesium tablets\nBeats fatigue in seven days');
  const report = page.getByRole('link', { name: 'Open full source report' });
  const originalReport = await report.getAttribute('href');
  await page.getByRole('button', { name: 'Run fix and re-screen' }).click();
  await expect(page.getByRole('status')).toContainText('Job running');
  await expect(report).toHaveAttribute('href', originalReport!);
  await expect(page.getByRole('heading', { name: 'Round 0', exact: true })).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByRole('heading', { name: 'Round 1', exact: true })).toBeVisible();
  const preview = page.getByRole('img', { name: 'Round 1 rendered draft' });
  await expect(preview).toBeVisible();
  await expect(page.locator('.round mark').first()).toBeVisible();
  await page.getByLabel('Left round').selectOption('1');
  await page.getByLabel('Right round').selectOption('0');
  await expect(page.locator('.round h3').first()).toHaveText('Round 1');
  await expect(page.locator('.round h3').last()).toHaveText('Round 0');
  await page.getByLabel('Left round').selectOption('0');
  await page.getByLabel('Right round').selectOption('1');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect
    .poll(() => preview.evaluate((image) => (image as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);
  const roundSrc = await preview.getAttribute('src');
  const review = page.getByRole('navigation', { name: 'Review views' });
  await review.getByRole('button', { name: 'Evidence', exact: true }).click();
  const finalImage = page.getByRole('img', { name: 'Ad being screened', exact: true });
  await expect(finalImage).toBeVisible();
  await expect(finalImage).toHaveAttribute('src', roundSrc!);
  await review.getByRole('button', { name: 'Compare rounds', exact: true }).click();
  const approve = page.getByRole('button', { name: 'Record my review decision' });
  await expect(approve).toBeDisabled();
  await page.getByLabel('Your name').fill('Synthetic browser reviewer');
  await expect(approve).toBeDisabled();
  await page.getByLabel('I reviewed the final draft').check();
  await approve.click();
  await expect(page.getByRole('heading', { name: 'Human review recorded' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('fix-review.png'), fullPage: true });
  expect(polling).toBe(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Human review recorded' })).toBeVisible();
  await expect(approve).toHaveCount(0);
});

test('invalid media remains recoverable and the mobile layout does not overflow', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page
    .getByLabel('Upload ad')
    .setInputFiles({ name: 'invalid.png', mimeType: 'image/png', buffer: Buffer.from('invalid') });
  await expect(page.getByRole('alert')).toContainText('could not be decoded');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await expect(page.getByRole('note')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('mobile.png'), fullPage: true });
});
