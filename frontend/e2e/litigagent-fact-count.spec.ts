import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Fact Count Indicator E2E Test (V2.2b.6)
 *
 * Tests the header fact count indicator shows live "N of M confirmed"
 * and updates when a fact is confirmed.
 *
 * All API calls are mocked via route interception.
 */

const MOCK_CASE = {
  id: "count-test-case-id",
  name: "Kim v. DataCo",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-10T00:00:00",
  updated_at: "2026-03-10T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
    case_id: "count-test-case-id",
    original_filename: "complaint.pdf",
    file_type: "pdf",
    mime_type: "application/pdf",
    file_size_bytes: 30000,
    upload_order: 1,
    processing_status: "ready",
    error_message: null,
    ocr_confidence: null,
    page_count: 3,
    metadata: null,
    text_dirty: false,
    created_at: "2026-03-10T00:00:00",
    updated_at: "2026-03-10T00:00:00",
  },
];

const MOCK_CONTEXT = {
  case_id: "count-test-case-id",
  case_name: "Kim v. DataCo",
  parties: [],
  court: null,
  attorneys: [],
  employment_history: [],
  claims: [],
  key_dates: [],
  financials: [],
  fact_count: 3,
  confirmed_count: 1,
  extraction_sources: {},
};

const MOCK_FACTS = {
  facts: [
    {
      id: "fact-plaintiff",
      case_id: "count-test-case-id",
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Sarah Kim", role: "plaintiff" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.95,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-defendant",
      case_id: "count-test-case-id",
      category: "party",
      fact_type: "defendant",
      value: { name: "DataCo Inc", role: "defendant" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.92,
      confirmed: true,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-termination",
      case_id: "count-test-case-id",
      category: "date",
      fact_type: "termination_date",
      value: { label: "Termination", date: "2025-08-01" },
      source_file_id: "file-complaint",
      extraction_method: "regex",
      confidence: 0.7,
      confirmed: false,
      superseded_by: null,
      effective_date: "2025-08-01",
      created_at: "2026-03-10T00:00:00",
    },
  ],
  total: 3,
};

async function setupMocks(page: Page) {
  await page.route(`**/api/cases/count-test-case-id`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CASE),
    })
  );

  await page.route(`**/api/cases/count-test-case-id/files`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FILES),
    })
  );

  await page.route(`**/api/cases/count-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/count-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/count-test-case-id/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/count-test-case-id/facts`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FACTS),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/count-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

test.describe("LITIGAGENT Fact Count Indicator (V2.2b.6)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupMocks(page);
  });

  test("header shows live fact count that updates when a fact is confirmed", async ({ page }) => {
    // Mock confirm endpoint for the plaintiff fact
    await page.route(`**/api/cases/count-test-case-id/facts/fact-plaintiff/confirm`, (route) => {
      if (route.request().method() === "PUT") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...MOCK_FACTS.facts[0],
            confirmed: true,
          }),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/count-test-case-id");
    await expect(page.getByText("Kim v. DataCo")).toBeVisible();
    await page.getByRole("button", { name: /case info/i }).click();

    const infoPanel = page.getByTestId("case-info-panel");
    await expect(infoPanel).toBeVisible({ timeout: 10_000 });

    // Header should show live counts: 3 facts, 1 of 3 confirmed
    const indicator = infoPanel.getByTestId("fact-count-indicator");
    await expect(indicator).toContainText("3 facts");
    await expect(indicator).toContainText("1 of 3 confirmed");

    // Confirm the plaintiff fact
    const plaintiffRow = infoPanel.locator(".group").filter({ hasText: "Sarah Kim" });
    await plaintiffRow.hover();
    await plaintiffRow.getByRole("button", { name: /confirm/i }).click();

    // Count should update to 2 of 3 confirmed
    await expect(indicator).toContainText("2 of 3 confirmed");
  });
});
