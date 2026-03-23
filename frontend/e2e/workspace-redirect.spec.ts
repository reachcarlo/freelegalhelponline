import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace Redirect E2E Tests (V2.3b.3 + V2.3b.4)
 *
 * Tests that legacy /tools/litigagent routes redirect to the new
 * /cases workspace routes for backward compatibility.
 */

const CASE_ID = "ws-redirect-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Redirect Test Case",
  description: null,
  status: "active",
  file_count: 0,
  created_at: "2026-03-20T00:00:00",
  updated_at: "2026-03-20T00:00:00",
};

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "Redirect Test Case",
  parties: [],
  court: null,
  attorneys: [],
  employment_history: [],
  claims: [],
  key_dates: [],
  financials: [],
  fact_count: 0,
  confirmed_count: 0,
  extraction_sources: {},
};

async function mockAPIs(page: Page) {
  await page.route(`**/api/cases/${CASE_ID}`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_CASE),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/${CASE_ID}/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/files`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/${CASE_ID}/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "event: ping\ndata: {}\n\n",
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );
}

test.describe("Legacy Route Redirects (V2.3b.3 + V2.3b.4)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("legacy /tools/litigagent/[caseId] redirects to /cases/[caseId]/files", async ({
    page,
  }) => {
    await page.goto(`/tools/litigagent/${CASE_ID}`);
    await page.waitForURL(`**/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
  });

  test("legacy /tools/litigagent redirects to /cases", async ({ page }) => {
    await page.goto("/tools/litigagent");
    await page.waitForURL("**/cases");
    // The case list page should render
    await expect(page.getByRole("heading", { name: "LITIGAGENT" })).toBeVisible();
  });
});
