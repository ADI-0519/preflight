import { test, expect } from '@playwright/test';

test('product sections, source example, FAQ and footer navigation work', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  for (const name of ['features', 'how-it-works', 'data-handling', 'questions']) {
    await expect(page.locator(`#${name}`)).toBeVisible();
  }
  await expect(page.locator('.receipt-example')).toContainText('synthetic script');
  await expect(page.locator('.receipt-example a')).toHaveAttribute(
    'href',
    'https://www.asa.org.uk/type/non_broadcast/code_section/03.html',
  );
  const question = page.getByText('Does PreFlight approve my ad?', { exact: true });
  await question.click();
  await expect(page.locator('.faq-list details').first()).toHaveAttribute('open', '');
  await expect(page.locator('.faq-list details').first()).toContainText('cannot guarantee');
  const footer = page.getByRole('contentinfo');
  await footer.getByRole('link', { name: 'How it works', exact: true }).click();
  await expect(page).toHaveURL(/#how-it-works$/);
  await expect(page.locator('#how-it-works')).toBeInViewport();
  await page.getByRole('link', { name: 'Upload an ad', exact: false }).click();
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  expect(errors).toEqual([]);
});

test('account pages support direct visits, refresh and navigation without pretending to authenticate', async ({
  page,
}) => {
  let submitted = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST') submitted += 1;
  });
  await page.goto('/');
  await page.locator('header').getByRole('link', { name: 'Log in', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Log in', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Accounts are not connected');
  await expect(page.getByRole('textbox', { name: 'Email address' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Log in', exact: false })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Log in', exact: true })).toBeVisible();
  await page.locator('.account-card').getByRole('link', { name: 'Sign up', exact: true }).click();
  await expect(page).toHaveURL(/\/signup$/);
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Your name' })).toBeDisabled();
  await expect(page.getByLabel('Password', { exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Create account', exact: false })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await page.getByRole('link', { name: 'Use PreFlight without an account', exact: false }).click();
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  expect(submitted).toBe(0);
});

test('landing, footer and account pages remain usable on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ['/', '/login', '/signup']) {
    await page.goto(route);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await expect(page.getByRole('contentinfo')).toBeVisible();
    if (route === '/') await expect(page.getByLabel('Upload ad')).toBeInViewport();
    else await expect(page.locator('.account-card')).toBeVisible();
  }
});
