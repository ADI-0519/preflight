import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  outputDir: '../data/work/web-browser-results',
  timeout: 45000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:8011', browserName: 'chromium', headless: true },
  webServer: {
    command:
      'uv run --offline uvicorn web_replay_server:create_app --app-dir tests --factory --host 127.0.0.1 --port 8011 --no-access-log',
    cwd: '..',
    url: 'http://127.0.0.1:8011/health',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
