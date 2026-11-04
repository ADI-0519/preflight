import { test, expect } from '@playwright/test';

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
