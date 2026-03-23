import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace Header E2E Tests (V2.3a.5)
 *
 * Tests the case header in the workspace shell:
 * 1. Case name and description display
 * 2. Fact count indicator with confirmed/total
 * 3. Back-to-cases navigation
 *
 * All API calls are mocked via route interception.
 */

const CASE_ID = "ws-header-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Martinez v. Acme Corp",
  description: "Case #BC-2026-12345",
  status: "active",
  file_count: 3,
  created_at: "2026-03-15T00:00:00",
  updated_at: "2026-03-15T00:00:00",
};

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "Martinez v. Acme Corp",
  parties: [],
  court: null,
  attorneys: [],
  employment_history: [],
  claims: [],
  key_dates: [],
  financials: [],
  fact_count: 8,
  confirmed_count: 5,
  extraction_sources: {},
};

const MOCK_FILES = [
  {
    id: "file-1",
    case_id: CASE_ID,
    original_filename: "complaint.pdf",
    file_type: "pdf",
    mime_type: "application/pdf",
    file_size_bytes: 50000,
    upload_order: 1,
    processing_status: "ready",
    error_message: null,
    ocr_confidence: null,
    page_count: 5,
    metadata: null,
    text_dirty: false,
    created_at: "2026-03-15T00:00:00",
    updated_at: "2026-03-15T00:00:00",
  },
];

async function mockCaseAPIs(
  page: Page,
  opts?: { context?: typeof MOCK_CONTEXT | null }
) {
  const ctx = opts?.context !== undefined ? opts.context : MOCK_CONTEXT;

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

  await page.route(`**/api/cases/${CASE_ID}/context`, (route) => {
    if (ctx === null) {
      return route.fulfill({ status: 404, body: "Not found" });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ctx),
    });
  });

  await page.route(`**/api/cases/${CASE_ID}/files`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FILES),
      });
    }
    return route.continue();
  });

  // Mock SSE status stream
  await page.route(`**/api/cases/${CASE_ID}/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "event: ping\ndata: {}\n\n",
    })
  );

  // Mock notes
  await page.route(`**/api/cases/${CASE_ID}/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );
}

test.describe("Workspace Header (V2.3a.5)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("displays case name, description, and fact count indicator", async ({
    page,
  }) => {
    await mockCaseAPIs(page);
    await page.goto(`/cases/${CASE_ID}`);

    // Wait for the workspace shell to load
    await expect(page.getByTestId("workspace-header")).toBeVisible();

    // Case name
    const caseName = page.getByTestId("case-name");
    await expect(caseName).toHaveText("Martinez v. Acme Corp");

    // Description (case number)
    const caseDesc = page.getByTestId("case-description");
    await expect(caseDesc).toHaveText("Case #BC-2026-12345");

    // Fact count indicator: "5/8" confirmed
    const factIndicator = page.getByTestId("fact-count-indicator");
    await expect(factIndicator).toBeVisible();
    await expect(factIndicator).toContainText("5/8");
  });

  test("back-to-cases link navigates to /cases", async ({ page }) => {
    await mockCaseAPIs(page);
    await page.goto(`/cases/${CASE_ID}`);

    await expect(page.getByTestId("workspace-header")).toBeVisible();

    const backButton = page.getByTestId("back-to-cases");
    await expect(backButton).toBeVisible();
    await expect(backButton).toContainText("Cases");

    await backButton.click();
    await page.waitForURL("**/cases");
    expect(page.url()).toContain("/cases");
  });

  test("hides fact indicator when no facts exist", async ({ page }) => {
    await mockCaseAPIs(page, {
      context: { ...MOCK_CONTEXT, fact_count: 0, confirmed_count: 0 },
    });
    await page.goto(`/cases/${CASE_ID}`);

    await expect(page.getByTestId("workspace-header")).toBeVisible();

    // Case name should still show
    await expect(page.getByTestId("case-name")).toHaveText(
      "Martinez v. Acme Corp"
    );

    // Fact indicator should not be present
    await expect(page.getByTestId("fact-count-indicator")).not.toBeVisible();
  });
});
