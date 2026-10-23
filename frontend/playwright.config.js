import { defineConfig, devices } from "@playwright/test";

const python = process.env.PYTHON
  || (process.platform === "win32"
    ? "../impl/.venv/Scripts/python.exe"
    : "python");

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:18091",
    trace: "retain-on-failure",
    launchOptions: process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {},
  },
  webServer: {
    command: `"${python}" ../scripts/e2e_server.py`,
    url: "http://127.0.0.1:18091/livez",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
