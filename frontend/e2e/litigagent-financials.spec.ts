import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Financials E2E Tests (V2.2b.5)
 *
 * Tests the financials section: chronological log of demand/offer/settlement
 * entries sorted by date, with add button for new entries.
 *
 * All API calls are mocked via route interception.
 */

const MOCK_CASE = {
  id: "fin-test-case-id",
  name: "Park v. FinanceCo",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-10T00:00:00",
  updated_at: "2026-03-10T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
    case_id: "fin-test-case-id",
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
  case_id: "fin-test-case-id",
  case_name: "Park v. FinanceCo",
  parties: [],
  court: null,
  attorneys: [],
  employment_history: [],
  claims: [],
  key_dates: [],
  financials: [],
  fact_count: 3,
  confirmed_count: 0,
  extraction_sources: {},
};

const MOCK_FACTS = {
  facts: [
    {
      id: "fact-fin-demand",
      case_id: "fin-test-case-id",
      category: "financial",
      fact_type: "financial_event",
      value: { label: "Initial Demand", amount: 500000, date: "2026-01-15" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.85,
      confirmed: false,
      superseded_by: null,
      effective_date: "2026-01-15",
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-fin-salary",
      case_id: "fin-test-case-id",
      category: "financial",
      fact_type: "financial",
      value: { label: "Annual Salary", amount: 150000, date: null },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.92,
      confirmed: true,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-fin-offer",
      case_id: "fin-test-case-id",
      category: "financial",
      fact_type: "financial_event",
      value: { label: "Settlement Offer", amount: 250000, date: "2026-02-20" },
      source_file_id: null,
      extraction_method: "manual",
      confidence: 1.0,
      confirmed: true,
      superseded_by: null,
      effective_date: "2026-02-20",
      created_at: "2026-03-15T00:00:00",
    },
  ],
  total: 3,
};

async function setupMocks(page: Page) {
  await page.route(`**/api/cases/fin-test-case-id`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CASE),
    })
  );

  await page.route(`**/api/cases/fin-test-case-id/files`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FILES),
    })
  );

  await page.route(`**/api/cases/fin-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/fin-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/fin-test-case-id/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/fin-test-case-id/facts`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FACTS),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/fin-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

async function openCaseInfo(page: Page) {
  await page.goto("/tools/litigagent/fin-test-case-id");
  await expect(page.getByText("Park v. FinanceCo")).toBeVisible();
  await page.getByRole("button", { name: /case info/i }).click();
  const infoPanel = page.getByTestId("case-info-panel");
  await expect(infoPanel).toBeVisible({ timeout: 10_000 });
  return infoPanel;
}

test.describe("LITIGAGENT Financials (V2.2b.5)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupMocks(page);
  });

  test("financial facts render as chronological log sorted by date with formatted amounts", async ({ page }) => {
    const infoPanel = await openCaseInfo(page);

    // Financials section should show
    await expect(infoPanel.getByText("Financials")).toBeVisible();

    // Log container should exist
    const log = infoPanel.getByTestId("financial-log");
    await expect(log).toBeVisible();

    // Should have 3 financial rows
    const rows = log.getByTestId("financial-row");
    await expect(rows).toHaveCount(3);

    // Rows should be sorted chronologically:
    // 1st: Annual Salary (no date — sorts first as empty string)
    // 2nd: Initial Demand (2026-01-15)
    // 3rd: Settlement Offer (2026-02-20)
    const firstRow = rows.nth(0);
    const secondRow = rows.nth(1);
    const thirdRow = rows.nth(2);

    // First row: Annual Salary (no date)
    await expect(firstRow.getByTestId("financial-label")).toContainText("Annual Salary");
    await expect(firstRow.getByTestId("financial-amount")).toContainText("$150,000");
    await expect(firstRow.getByTestId("financial-date")).toContainText("—");
    await expect(firstRow.getByText("Confirmed")).toBeVisible();

    // Second row: Initial Demand
    await expect(secondRow.getByTestId("financial-label")).toContainText("Initial Demand");
    await expect(secondRow.getByTestId("financial-amount")).toContainText("$500,000");
    await expect(secondRow.getByTestId("financial-date")).toContainText("2026-01-15");
    await expect(secondRow.getByText("85%")).toBeVisible();
    await expect(secondRow.getByText("llm")).toBeVisible();

    // Third row: Settlement Offer
    await expect(thirdRow.getByTestId("financial-label")).toContainText("Settlement Offer");
    await expect(thirdRow.getByTestId("financial-amount")).toContainText("$250,000");
    await expect(thirdRow.getByTestId("financial-date")).toContainText("2026-02-20");
    await expect(thirdRow.getByText("manual")).toBeVisible();
  });

  test("adding a financial entry via + Add creates a new log entry sorted into position", async ({ page }) => {
    let addFactBody: Record<string, unknown> | null = null;

    await page.route(`**/api/cases/fin-test-case-id/facts`, async (route) => {
      if (route.request().method() === "POST") {
        addFactBody = JSON.parse(route.request().postData() || "{}");
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fact-fin-counter",
            case_id: "fin-test-case-id",
            category: "financial",
            fact_type: "financial_event",
            value: { label: "Counter Offer", amount: 375000, date: "2026-03-01" },
            source_file_id: null,
            extraction_method: "manual",
            confidence: 1.0,
            confirmed: true,
            superseded_by: null,
            effective_date: "2026-03-01",
            created_at: "2026-03-20T00:00:00",
          }),
        });
      }
      return route.continue();
    });

    const infoPanel = await openCaseInfo(page);

    // Click "+ Add" on the Financials section
    const finHeader = infoPanel.locator("div").filter({ hasText: /^Financials/ });
    await finHeader.getByRole("button", { name: /\+ Add/i }).click();

    const addForm = infoPanel.getByTestId("fact-add-form");
    await expect(addForm).toBeVisible();

    // Fill in the form
    await addForm.getByLabel("New label").fill("Counter Offer");
    await addForm.getByLabel("New amount").fill("375000");
    await addForm.getByLabel("New date").fill("2026-03-01");

    // Click Add
    await addForm.getByRole("button", { name: "Add" }).click();

    // API should have been called
    await expect(async () => {
      expect(addFactBody).not.toBeNull();
    }).toPass({ timeout: 5_000 });

    expect(addFactBody).toMatchObject({
      category: "financial",
      fact_type: "financial_event",
      value: { label: "Counter Offer", amount: "375000", date: "2026-03-01" },
    });

    // Form should close
    await expect(addForm).not.toBeVisible();

    // New entry should appear in the log — sorted last (latest date: 2026-03-01)
    const log = infoPanel.getByTestId("financial-log");
    const rows = log.getByTestId("financial-row");
    await expect(rows).toHaveCount(4);

    const lastRow = rows.nth(3);
    await expect(lastRow.getByTestId("financial-label")).toContainText("Counter Offer");
    await expect(lastRow.getByTestId("financial-amount")).toContainText("$375,000");
    await expect(lastRow.getByTestId("financial-date")).toContainText("2026-03-01");
  });
});
