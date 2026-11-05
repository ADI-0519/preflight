import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

async function loginOn(page: Page, me: object) {
  // read the real config once: a fetch inside the handler can outlive the test when the page asks again
  const config = await (await page.request.get('/ui/config')).json();
  await page.route('/ui/config', (route) =>
    route.fulfill({
      json: {
        ...config,
        auth: {
          apiKey: 'test-key',
          authDomain: 'preflight-test.firebaseapp.com',
          projectId: 'preflight-test',
          appId: 'test-app',
        },
      },
    }),
  );
  await page.route('/auth/me', (route) => route.fulfill({ json: me }));
}

test('with sign-in on, a visitor sees the landing page and every action leads to sign-in', async ({
  page,
}) => {
  const workspace: string[] = [];
  await loginOn(page, { signed_in: false, email: null, login: true, pending: null });
  page.on('request', (r) => {
    if (/\/(ui\/demos|jobs|uploads|screenings)/.test(r.url())) workspace.push(r.url());
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByLabel('Upload ad')).toHaveCount(0);
  await page.getByRole('link', { name: /Log in to screen an ad/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
  await page.getByRole('button', { name: 'Create an account' }).click();
  await expect(page.getByRole('heading', { name: 'Create an account' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Explore demos' })).toHaveCount(0);
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore demos' }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(workspace).toEqual([]);
});

test('with sign-in off, the workspace opens with no sign-out button', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Explore demos' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);
});

test('creating an account shows each password requirement as it is met', async ({ page }) => {
  await loginOn(page, { signed_in: false, email: null, login: true, pending: null });
  await page.goto('/login');
  await page.getByRole('button', { name: 'Create an account' }).click();
  await page.getByLabel('Email').fill('founder@example.com');
  const password = page.getByLabel('Password', { exact: true });
  const create = page.getByRole('button', { name: 'Create account' });
  const rules = page.getByRole('list', { name: 'Password requirements' });
  await password.fill('short');
  await expect(rules.getByText('At least 12 characters')).toContainText('(not yet)');
  await expect(create).toBeDisabled();
  await password.fill('Pilot-2026-flight');
  await expect(rules.locator('li.met')).toHaveCount(6);
  await page.getByLabel('Confirm password').fill('Pilot-2026-flighx');
  await expect(page.getByText('The passwords do not match.')).toBeVisible();
  await expect(create).toBeDisabled();
  await page.getByLabel('Confirm password').fill('Pilot-2026-flight');
  await expect(create).toBeEnabled();
  await password.fill('Founder-2026-founder');
  await expect(rules.getByText('Does not contain your email name')).toContainText('(not yet)');
});

test('a sign-in waiting for its code asks for the 6 digits and then opens the workspace', async ({
  page,
}) => {
  await loginOn(page, {
    signed_in: false,
    email: null,
    login: true,
    pending: 'founder@example.com',
  });
  const tries: string[] = [];
  await page.route('/auth/code', async (route) => {
    const { code } = route.request().postDataJSON() as { code: string };
    tries.push(code);
    if (code !== '246810') return route.fulfill({ status: 400, json: { error: 'wrong_code' } });
    await page.unroute('/auth/me');
    await route.fulfill({
      json: { signed_in: true, email: 'founder@example.com', login: true, pending: null },
    });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await expect(page.getByText('founder@example.com')).toBeVisible();
  await expect(page.getByRole('button', { name: /Resend code in \d+s/ })).toBeDisabled();
  const code = page.getByLabel('Code');
  await code.fill('13579x');
  await expect(page.getByRole('button', { name: 'Verify' })).toBeDisabled();
  await code.fill('135792');
  await expect(page.getByRole('alert')).toHaveText(/That code is not right/);
  await code.fill('246810');
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Log in', exact: true })).toHaveCount(0);
  expect(tries).toEqual(['135792', '246810']);
});

test('a signed-in account opens on its workspace, not the product page', async ({
  page,
}, testInfo) => {
  await loginOn(page, {
    signed_in: true,
    email: 'founder@example.com',
    login: true,
    pending: null,
  });
  await page.route('/jobs', (route) => route.fulfill({ json: { jobs: [] } }));
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Your workspace');
  await expect(page.getByLabel('Upload ad')).toBeEnabled();
  await expect(page.getByRole('region', { name: 'Your screenings' })).toContainText(
    'No screenings yet',
  );
  await expect(page.locator('#features')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('dashboard.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('dashboard-phone.png'), fullPage: true });
});
