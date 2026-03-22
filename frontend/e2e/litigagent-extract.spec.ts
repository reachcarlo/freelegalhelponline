import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Tier 2 Extraction Trigger E2E Tests (V2.2c.6)
 *
 * Tests the "Extract more details from [filename]" button in the
 * Case Info panel: loading state, success feedback, and error handling.
 *
 * All API calls are mocked via route interception.
 */

const CASE_ID = "extract-test-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Extraction Test Case",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-21T00:00:00",
  updated_at: "2026-03-21T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
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
    created_at: "2026-03-21T00:00:00",
    updated_at: "2026-03-21T00:00:00",
  },
];

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "Extraction Test Case",
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

const INITIAL_FACTS = { facts: [], total: 0 };

const EXTRACTED_FACTS = {
  facts: [
    {
      id: "fact-new-1",
      case_id: CASE_ID,
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Jane Doe", role: "plaintiff" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.95,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-21T00:00:00",
    },
    {
      id: "fact-new-2",
      case_id: CASE_ID,
      category: "claim",
      fact_type: "claim",
      value: { claim_type: "feha_discrimination", status: "active", protected_class: "age" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.92,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-21T00:00:00",
    },
  ],
  total: 2,
};

async function setupCaseMocks(page: Page) {
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

  await page.route(`**/api/cases/${CASE_ID}/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

test.describe("LITIGAGENT Tier 2 Extraction Trigger (V2.2c.6)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupCaseMocks(page);
  });

  test("extract button triggers extraction, shows loading, and refreshes facts", async ({ page }) => {
    // Track fact list calls to switch from empty to populated after extraction
    let factsCallCount = 0;
    await page.route(`**/api/cases/${CASE_ID}/facts`, (route) => {
      factsCallCount++;
      // First call returns empty, subsequent calls return extracted facts
      const body = factsCallCount <= 1 ? INITIAL_FACTS : EXTRACTED_FACTS;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    });

    // Mock the extract endpoint with a short delay to verify loading state
    let extractCalled = false;
    let extractFileId: string | null = null;
    await page.route(`**/api/cases/${CASE_ID}/extract`, async (route) => {
      extractCalled = true;
      const reqBody = route.request().postDataJSON();
      extractFileId = reqBody?.file_id || null;
      // Small delay to make loading state observable
      await new Promise((r) => setTimeout(r, 200));
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          facts_created: 2,
          files_processed: 1,
          factual_summary: "Age discrimination complaint.",
          facts: EXTRACTED_FACTS.facts,
        }),
      });
    });

    await page.goto(`/tools/litigagent/${CASE_ID}`);
    await expect(page.getByText("Extraction Test Case")).toBeVisible();

    // Open Case Info panel
    await page.getByRole("button", { name: /case info/i }).click();
    const infoPanel = page.getByTestId("case-info-panel");
    await expect(infoPanel).toBeVisible({ timeout: 10_000 });

    // Extract section should be visible with the button
    const extractSection = page.getByTestId("extract-section");
    await expect(extractSection).toBeVisible();

    const extractBtn = page.getByTestId("extract-file-button").first();
    await expect(extractBtn).toContainText("Extract more details from complaint.pdf");

    // Click the extract button
    await extractBtn.click();

    // Loading state should appear
    await expect(extractBtn).toContainText("Extracting...");

    // Wait for success
    await expect(page.getByTestId("extract-success")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("extract-success")).toContainText("Extracted 2 new facts");

    // Verify API was called with correct file_id
    expect(extractCalled).toBe(true);
    expect(extractFileId).toBe("file-complaint");

    // Facts should now be displayed (refreshed after extraction)
    await expect(infoPanel.getByText("Jane Doe")).toBeVisible();
    await expect(infoPanel.getByText(/feha discrimination/)).toBeVisible();
  });

  test("extract button shows error when extraction fails", async ({ page }) => {
    await page.route(`**/api/cases/${CASE_ID}/facts`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(INITIAL_FACTS),
      })
    );

    // Mock extract endpoint to return an error
    await page.route(`**/api/cases/${CASE_ID}/extract`, (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "LLM service not available" }),
      })
    );

    await page.goto(`/tools/litigagent/${CASE_ID}`);
    await page.getByRole("button", { name: /case info/i }).click();

    const infoPanel = page.getByTestId("case-info-panel");
    await expect(infoPanel).toBeVisible({ timeout: 10_000 });

    // Click extract
    await page.getByTestId("extract-file-button").first().click();

    // Error message should appear
    await expect(page.getByTestId("extract-error")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("extract-error")).toContainText("LLM service not available");

    // No success message
    await expect(page.getByTestId("extract-success")).not.toBeVisible();
  });
});
