import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 0,
  workers: 4,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command:
        "cd .. && uv run uvicorn employee_help.api.main:app --port 8000",
      port: 8000,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: "npm run dev",
      port: 3000,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
