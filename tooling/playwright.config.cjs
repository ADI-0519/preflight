const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './browser',
  outputDir: '../data/work/browser-results',
  workers: 1,
  reporter: 'list',
  use: { browserName: 'chromium', headless: true },
});
