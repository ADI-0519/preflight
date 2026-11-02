import { test, expect } from '@playwright/test';
import path from 'node:path';

const media = path.resolve(import.meta.dirname, '../../tests/fixtures/models/media/captions.mp4');

test.use({ colorScheme: 'dark' });

async function checkTextContrast(page: import('@playwright/test').Page) {
  const tokens = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    return Object.fromEntries(
      ['ink', 'graphite', 'paper', 'sheet', 'raised', 'blue', 'on-ink', 'hl', 'on-hl'].map(
        (name) => [name, style.getPropertyValue(`--${name}`).trim()],
      ),
    );
  });
  const luminance = (hex: string) => {
    const raw = hex.slice(1);
    const normalized = raw.length === 3 ? [...raw].map((c) => c + c).join('') : raw;
    expect(normalized).toMatch(/^[0-9a-f]{6}$/i);
    const values = normalized.match(/../g)!.map((pair) => {
      const n = parseInt(pair, 16) / 255;
      return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
  };
  for (const [text, surface] of [
    ['ink', 'sheet'],
    ['ink', 'paper'],
    ['graphite', 'sheet'],
    ['graphite', 'paper'],
    ['graphite', 'raised'],
    ['blue', 'sheet'],
    ['on-ink', 'ink'],
    ['on-hl', 'hl'],
  ]) {
    const a = luminance(tokens[text]),
      b = luminance(tokens[surface]);
    expect(
      (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
      `${text} on ${surface}`,
    ).toBeGreaterThanOrEqual(4.5);
  }
}

test('loaded evidence leads on desktop and appearance preserves the selected claim', async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  const evidence = page.getByRole('region', { name: 'Selected claim evidence' });
  await expect(evidence).toBeVisible({ timeout: 30000 });
  const video = page.getByRole('region', { name: 'Ad and claim timeline' }).locator('video');
  const frame = await video.boundingBox();
  expect(frame!.y).toBeLessThan(600);
  expect(frame!.y + 100).toBeLessThan(800);
  const title = await evidence.locator('h3').innerText();
  await checkTextContrast(page);
  const theme = page.getByRole('button', { name: 'Light appearance', exact: true });
  await theme.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('html')).toHaveAttribute('data-appearance', 'light');
  await checkTextContrast(page);
  await expect(evidence.locator('h3')).toHaveText(title);
  await expect(page.getByRole('note')).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath('evidence-light.png'), fullPage: true });
  await page.getByRole('button', { name: 'Dark appearance', exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath('evidence-dark.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('each claim row is keyboard selectable and seeks to recorded evidence', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  const lane = page.locator('.claim-row:has(time)').last();
  await expect(lane).toBeVisible({ timeout: 30000 });
  await lane.focus();
  await page.keyboard.press('Enter');
  await expect(lane).toHaveAttribute('aria-pressed', 'true');
  const selected = page.locator('.claim-row[aria-pressed="true"]');
  const time = (await selected.locator('time').innerText()).split(':').map(Number);
  await expect
    .poll(() => page.locator('.viewer video').evaluate((v) => (v as HTMLVideoElement).currentTime))
    .toBeCloseTo(time[0] * 60 + time[1], 0);
  expect(await page.locator('.claim-row[aria-pressed="true"]').count()).toBe(1);
});

test('a loaded result remains readable on mobile and at doubled content scale', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  await expect(page.locator('.claim-row').first()).toBeVisible({ timeout: 30000 });
  const noOverflow = () => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
  expect(await noOverflow()).toBe(true);
  await page.getByRole('button', { name: 'Prepare revision', exact: true }).click();
  await expect(page.getByLabel('On-screen captions')).toBeVisible();
  expect(await noOverflow()).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('editor-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.evaluate(() => {
    document.body.style.zoom = '2';
  });
  expect(await noOverflow()).toBe(true);
  await expect(page.getByRole('note')).toBeVisible();
});

test('leaving the evidence view pauses the ad video', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  const video = page.locator('.viewer video');
  await expect(video).toBeVisible({ timeout: 30000 });
  await video.evaluate((v: HTMLVideoElement) => {
    v.muted = true;
    v.loop = true;
    return v.play();
  });
  expect(await video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(false);
  await page.getByRole('button', { name: 'Prepare revision', exact: true }).click();
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);
});

test('the reveal button is on the first screen of a demo at 1440 by 900', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore demos' }).click();
  await page.getByRole('button', { name: 'Synthetic replay · flagged', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Synthetic replay · flagged' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reveal ASA outcome' })).toBeInViewport();
});

test('on a phone the selected claim evidence follows the claim rows', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  const evidence = page.getByRole('region', { name: 'Selected claim evidence' });
  await expect(evidence).toBeVisible({ timeout: 30000 });
  const row = (await page.locator('.claim-row').last().boundingBox())!;
  const top = (await evidence.boundingBox())!.y;
  expect(top).toBeGreaterThan(row.y);
  // one 24px gutter at most between the last claim row and the inspector
  expect(top - (row.y + row.height)).toBeLessThanOrEqual(24);
  await expect(evidence.getByText('Possible breach', { exact: true }).first()).toBeVisible();
});

test('a heading scrolled into view is not covered by the sticky header', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 420 });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  const heading = page.getByRole('heading', { name: 'Screening evidence' });
  await expect(heading).toBeVisible({ timeout: 30000 });
  await heading.evaluate((h) => h.scrollIntoView({ block: 'start' }));
  expect(await page.evaluate(() => scrollY)).toBeGreaterThan(0);
  const header = await page.locator('.chrome').boundingBox();
  const top = (await heading.boundingBox())!.y;
  expect(top).toBeGreaterThanOrEqual(header!.y + header!.height);
});

test.describe('light system preference', () => {
  test.use({ colorScheme: 'light' });

  test('initial appearance follows prefers-color-scheme', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('html')).toHaveAttribute('data-appearance', 'light');
    expect(await page.evaluate(() => document.documentElement.dataset.appearance)).toBe('light');
    await expect(page.getByRole('button', { name: 'Dark appearance', exact: true })).toBeVisible();
  });
});
