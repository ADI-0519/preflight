import { expect, test } from '@playwright/test';

test('dropping several files is recoverable and a single script uses the normal screening flow', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  const multiple = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(new File(['VO: Treats anxiety'], 'first.txt', { type: 'text/plain' }));
    data.items.add(new File(['SUPER: Orange flavour'], 'second.txt', { type: 'text/plain' }));
    return data;
  });
  await page
    .getByRole('region', { name: 'Upload workspace' })
    .dispatchEvent('drop', { dataTransfer: multiple });
  await expect(page.getByRole('alert')).toHaveText('Choose one ad or script at a time.');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  const single = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(new File(['VO: Treats anxiety\n'], 'single.txt', { type: 'text/plain' }));
    return data;
  });
  await page
    .getByRole('region', { name: 'Upload workspace' })
    .dispatchEvent('drop', { dataTransfer: single });
  await expect(page.getByRole('region', { name: 'Script source', exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Selected claim evidence' })).toContainText(
    'CAP 15.6.2',
  );
  await single.dispose();
  await multiple.dispose();
});

test('entry layout keeps upload terms, primary action and format help usable on a phone', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await expect(page.getByRole('region', { name: 'Upload workspace' })).toContainText(
    'Do not upload confidential ads.',
  );
  await expect(page.getByLabel('Upload ad')).toBeInViewport();
  const verification = await page.locator('.replay').boundingBox();
  const introduction = await page.locator('.entry-title').boundingBox();
  expect(introduction!.y).toBeGreaterThanOrEqual(verification!.y + verification!.height);
  await page.getByText('Supported formats & retention', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Formats', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
