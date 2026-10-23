import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.ODF_ACCEPTANCE_URL
  || process.env.ODF_ACCEPTANCE_BASE || "http://127.0.0.1:18090";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "acceptance.spec.js",
  timeout: 30000,
  retries: 1,
  workers: 1,
  reporter: "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    ignoreHTTPSErrors: true,
    launchOptions: process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
