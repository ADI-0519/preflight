import { test, expect } from '@playwright/test';
import path from 'node:path';

const media = path.resolve(import.meta.dirname, '../../tests/fixtures/models/media/captions.mp4');

test('a missing ad preview keeps its claims usable and another demo recovers', async ({ page }) => {
  await page.route('**/ui/demos/flagged/media', (route) => route.fulfill({ status: 410 }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore demos', exact: true }).click();
  await page.getByRole('button', { name: 'Synthetic replay · flagged', exact: false }).click();
  await expect(page.getByText('Ad preview unavailable.', { exact: false })).toBeVisible();
  await expect(page.locator('.claim-row')).toHaveCount(4);
  await page.locator('.claim-row:visible').last().click();
  await expect(page.locator('.claim-row:visible').last()).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Synthetic replay · no flags', exact: false }).click();
  await expect(page.getByLabel('Ad video')).toBeVisible();
  await expect(page.getByText('Ad preview unavailable.', { exact: false })).toHaveCount(0);
});

test('a malformed progress stream leaves the user able to start again', async ({ page }) => {
  await page.route('**/jobs/*/events', (route) =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: 'id: 1\nevent: progress\ndata: not-json\n\n',
    }),
  );
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  await expect(page.getByRole('alert')).toContainText('progress stream');
  await expect(page.getByLabel('Upload ad')).toBeEnabled({ timeout: 2000 });
  await expect(page.getByRole('button', { name: 'Explore demos' })).toBeEnabled();
  await page.unroute('**/jobs/*/events');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Screening evidence' })).toBeVisible({
    timeout: 30000,
  });
});

test('a refused revision keeps the original evidence and can be retried', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  await page.getByRole('button', { name: 'Prepare revision', exact: true }).click();
  await page
    .getByLabel('Scene still')
    .setInputFiles(
      path.resolve(import.meta.dirname, '../../tests/fixtures/agent/magnesium/still.png'),
    );
  await page
    .getByLabel('On-screen captions')
    .fill('Magnesium tablets\nBeats fatigue in seven days');
  const originalReport = await page
    .getByRole('link', { name: 'Open full source report' })
    .getAttribute('href');
  await page.route('**/fixes', (route) =>
    route.fulfill({ status: 503, json: { error: 'worker_unavailable' } }),
  );
  const declined = page.waitForResponse(
    (response) => response.url().endsWith('/fixes') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Run fix and re-screen' }).click();
  await declined;
  await expect(page.getByRole('alert')).toContainText('HTTP 503');
  await expect(page.getByRole('link', { name: 'Open full source report' })).toHaveAttribute(
    'href',
    originalReport!,
  );
  await expect(page.getByLabel('On-screen captions')).toHaveValue(
    'Magnesium tablets\nBeats fatigue in seven days',
  );
  await page.unroute('**/fixes');
  await page.getByRole('button', { name: 'Run fix and re-screen' }).click();
  await expect(page.getByRole('heading', { name: 'Round 1', exact: true })).toBeVisible({
    timeout: 30000,
  });
});

test('a delayed reveal cannot attach one demos outcome to a different demo', async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/ui/demos/flagged/reveal', async (route) => {
    await gate;
    await route.fulfill({
      json: { kind: 'synthetic', message: 'Response for the previous synthetic fixture' },
    });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore demos' }).click();
  await page.getByRole('button', { name: 'Synthetic replay · flagged', exact: false }).click();
  const pending = page.waitForRequest('**/ui/demos/flagged/reveal');
  await page.getByRole('button', { name: 'Reveal ASA outcome' }).click();
  await pending;
  await page.getByRole('button', { name: 'Synthetic replay · no flags', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Synthetic replay · no flags' })).toBeVisible();
  const response = page.waitForResponse('**/ui/demos/flagged/reveal');
  release();
  await response;
  await expect(page.getByText('Response for the previous synthetic fixture')).toHaveCount(0, {
    timeout: 2000,
  });
  await expect(page.getByRole('button', { name: 'Reveal ASA outcome' })).toBeVisible();
});

test('starting another ad clears the previous editable draft', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  await expect(page.getByRole('button', { name: 'Prepare revision', exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole('button', { name: 'Prepare revision', exact: true }).click();
  await expect(page.getByLabel('On-screen captions')).toBeVisible();
  await page.getByLabel('On-screen captions').fill('Previous synthetic draft captions');
  await page.getByRole('button', { name: 'Explore demos' }).click();
  await page.getByRole('button', { name: 'Screen an ad' }).click();
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  await page.getByRole('button', { name: 'Prepare revision', exact: true }).click();
  await expect(page.getByLabel('On-screen captions')).toBeVisible();
  await expect(page.getByLabel('On-screen captions')).toHaveValue('', { timeout: 2000 });
});

test('an expired job link is recoverable without offering approval', async ({ page }) => {
  await page.route('**/jobs/ffffffffffffffffffffffffffffffff', (route) =>
    route.fulfill({
      status: 410,
      json: { error: 'upload_expired' },
    }),
  );
  await page.goto('/?job=ffffffffffffffffffffffffffffffff');
  await expect(page.getByRole('alert')).toContainText('retention period has ended');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Record my review decision' })).toHaveCount(0);
});

test('a dropped SSE connection resumes without replaying earlier events', async ({ page }) => {
  await page.addInitScript(() => {
    const original = window.EventSource;
    (window as unknown as { streamEvents: string[] }).streamEvents = [];
    window.EventSource = class extends original {
      constructor(url: string | URL, config?: EventSourceInit) {
        super(url, config);
        this.addEventListener('progress', (e) => {
          (window as unknown as { streamEvents: string[] }).streamEvents.push(
            (e as MessageEvent).lastEventId,
          );
        });
      }
    };
  });
  let requests = 0;
  await page.route('**/jobs/*/events', async (route) => {
    requests += 1;
    if (requests === 1) {
      await route.fulfill({
        contentType: 'text/event-stream',
        body: 'id: 1\nevent: progress\ndata: {"status":"running"}\n\n',
      });
    } else {
      await route.fallback();
    }
  });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page.getByLabel('Upload ad').setInputFiles(media);
  await expect(page.getByRole('heading', { name: 'Screening evidence' })).toBeVisible({
    timeout: 15000,
  });
  expect(requests).toBeGreaterThan(1);
  const delivered = await page.evaluate(
    () => (window as unknown as { streamEvents: string[] }).streamEvents,
  );
  expect(delivered.slice(0, 2)).toEqual(['1', '2']);
  expect(new Set(delivered).size).toBe(delivered.length);
});

test('long demo titles do not break the narrow-screen layout', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/ui/demos', (route) =>
    route.fulfill({
      json: [
        { id: 'flagged', title: 'Synthetic' + 'x'.repeat(140), kind: 'synthetic', ruling_id: null },
      ],
    }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore demos' }).click();
  await expect(
    page.getByRole('button', { name: 'Synthetic' + 'x'.repeat(140), exact: false }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
