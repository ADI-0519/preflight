import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

async function loginOn(page: Page, me: object) {
  await page.route('/ui/config', async (route) => {
    const config = await (await route.fetch()).json();
    await route.fulfill({
      json: {
        ...config,
        auth: {
          apiKey: 'test-key',
          authDomain: 'preflight-test.firebaseapp.com',
          projectId: 'preflight-test',
          appId: 'test-app',
        },
      },
    });
  });
  await page.route('/auth/me', (route) => route.fulfill({ json: me }));
}

test('with sign-in on, the sign-in screen shows before any workspace request', async ({ page }) => {
  const workspace: string[] = [];
  await page.route('/ui/config', async (route) => {
    const config = await (await route.fetch()).json();
    await route.fulfill({
      json: {
        ...config,
        auth: {
          apiKey: 'test-key',
          authDomain: 'preflight-test.firebaseapp.com',
          projectId: 'preflight-test',
          appId: 'test-app',
        },
      },
    });
  });
  await page.route('/auth/me', (route) =>
    route.fulfill({ json: { signed_in: false, email: null, login: true } }),
  );
  page.on('request', (r) => {
    if (/\/(ui\/demos|jobs|uploads|screenings)/.test(r.url())) workspace.push(r.url());
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
  await page.getByRole('button', { name: 'Create an account' }).click();
  await expect(page.getByRole('heading', { name: 'Create an account' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Explore demos' })).toHaveCount(0);
  expect(workspace).toEqual([]);
});

test('with sign-in off, the workspace opens with no sign-out button', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Explore demos' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);
});

test('creating an account shows each password requirement as it is met', async ({ page }) => {
  await loginOn(page, { signed_in: false, email: null, login: true, pending: null });
  await page.goto('/');
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
  expect(tries).toEqual(['135792', '246810']);
});
