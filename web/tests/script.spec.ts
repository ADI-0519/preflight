import { expect, test } from '@playwright/test';

async function uploadScript(page: import('@playwright/test').Page, text: string) {
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await page
    .locator('input[type=file]')
    .first()
    .setInputFiles({
      name: 'synthetic-script.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from(text),
    });
}

test('script upload, numbered evidence, sources, report and reload stay script-only', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await uploadScript(
    page,
    'VO: Treats anxiety\n\nSUPER: <script>window.scriptExecuted = true</script>\n',
  );
  await expect(page.locator('.stages')).toBeVisible();
  await expect(page.locator('.stages')).toContainText('Transcribe');
  await expect(page.locator('.stages')).toContainText('Skipped');
  await expect(page.getByRole('region', { name: 'Script source', exact: true })).toBeVisible();
  await expect(page.locator('.script-source li')).toHaveCount(2);
  await expect(page.locator('.script-source li').last()).toHaveAttribute('value', '3');
  await expect(page.locator('.script-source')).toContainText(
    '<script>window.scriptExecuted = true</script>',
  );
  await page.locator('.claim-row').first().click();
  await expect(page.locator('.script-source li.selected')).toHaveAttribute('value', '1');
  await expect(page.getByRole('region', { name: 'Selected claim evidence' })).toContainText(
    'Script line 1',
  );
  await expect(page.getByRole('region', { name: 'Selected claim evidence' })).toContainText(
    'CAP 15.6.2',
  );
  await expect(page.getByRole('button', { name: 'Prepare revision' })).toHaveCount(0);
  await expect(page.locator('.viewer video, .viewer img')).toHaveCount(0);
  const reportPageOpened = page.waitForEvent('popup');
  await page.getByRole('link', { name: 'Open full source report' }).click();
  const reportPage = await reportPageOpened;
  await expect(reportPage.locator('body')).toContainText('Script line 1');
  await expect(reportPage.locator('body')).not.toContainText('None × None');
  await reportPage.close();
  await page.reload();
  await expect(page.getByRole('region', { name: 'Script source', exact: true })).toContainText(
    'Treats anxiety',
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  expect(await page.evaluate(() => 'scriptExecuted' in window)).toBeFalsy();
  expect(errors).toEqual([]);
});

test('script clean and incomplete results keep the finished-ad limitation', async ({ page }) => {
  await uploadScript(page, '\uFEFFSUPER: Orange flavour\n');
  await expect(page.getByRole('region', { name: 'Script source', exact: true })).toBeVisible();
  await expect(page.getByText('No issues found against', { exact: false })).toBeVisible();
  await expect(page.locator('.script-source')).toContainText('Screen the finished ad separately');
  await uploadScript(page, 'VO: Synthetic incomplete\n');
  await expect(page.getByRole('region', { name: 'Script source', exact: true })).toBeVisible();
  await expect(page.getByText('Incomplete:', { exact: false }).first()).toBeVisible();
  await expect(page.locator('.script-source')).toContainText('Screen the finished ad separately');
});

test('an incomplete screening retries from its result and from the list', async ({ page }) => {
  await uploadScript(page, 'VO: Synthetic incomplete\n');
  await expect(page.getByText('Incomplete:', { exact: false }).first()).toBeVisible();
  const first = new URL(page.url()).searchParams.get('job');
  await page.getByRole('button', { name: 'Retry the unfinished stages' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('job')).not.toBe(first);
  await expect(page.getByText('Incomplete:', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Screen an ad', exact: true }).click();
  const list = page.getByRole('region', { name: 'Your screenings' });
  const retries = list.getByRole('button', { name: /^Retry / });
  await expect(retries.first()).toBeVisible();
  await retries.first().click();
  await expect(page.getByText('Incomplete:', { exact: false }).first()).toBeVisible();
});
