import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Employment History E2E Tests (V2.2b.3)
 *
 * Tests the specialized employment history section: multi-entry timeline UI
 * with start/end dates, position, employer, compensation, reason per period,
 * ordered by start_date.
 *
 * All API calls are mocked via route interception.
 */

const MOCK_CASE = {
  id: "emp-test-case-id",
  name: "Rivera v. MegaCorp",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-10T00:00:00",
  updated_at: "2026-03-10T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
    case_id: "emp-test-case-id",
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
  case_id: "emp-test-case-id",
  case_name: "Rivera v. MegaCorp",
  parties: [
    { name: "Carlos Rivera", role: "plaintiff", party_type: "individual", count: null },
    { name: "MegaCorp LLC", role: "defendant", party_type: "entity", count: null },
  ],
  court: null,
  attorneys: [],
  employment_history: [],
  claims: [],
  key_dates: [],
  financials: [],
  fact_count: 4,
  confirmed_count: 0,
  extraction_sources: {
    "file-complaint": ["llm"],
  },
};

// Two employment periods to test ordering and multi-entry display
const MOCK_FACTS = {
  facts: [
    {
      id: "fact-plaintiff",
      case_id: "emp-test-case-id",
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Carlos Rivera", role: "plaintiff" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.95,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-emp-2",
      case_id: "emp-test-case-id",
      category: "employment",
      fact_type: "employment_period",
      value: {
        employer: "MegaCorp LLC",
        position: "Senior Manager",
        department: "Operations",
        compensation_rate: 180000,
        compensation_type: "salary",
        pay_period: "annual",
        start_date: "2022-06-01",
        end_date: "2025-09-15",
        change_reason: "terminated",
      },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.88,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-emp-1",
      case_id: "emp-test-case-id",
      category: "employment",
      fact_type: "employment_period",
      value: {
        employer: "MegaCorp LLC",
        position: "Associate Manager",
        department: "Sales",
        compensation_rate: 120000,
        compensation_type: "salary",
        pay_period: "annual",
        start_date: "2019-03-15",
        end_date: "2022-05-31",
        change_reason: "promoted",
      },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.85,
      confirmed: true,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-emp-3",
      case_id: "emp-test-case-id",
      category: "employment",
      fact_type: "employer",
      value: {
        employer: "StartupCo",
        position: "Intern",
        start_date: "2018-06-01",
        end_date: null,
        compensation_rate: null,
        compensation_type: null,
        pay_period: null,
        department: null,
        change_reason: null,
      },
      source_file_id: null,
      extraction_method: "manual",
      confidence: 1.0,
      confirmed: true,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
  ],
  total: 4,
};

async function setupMocks(page: Page) {
  await page.route(`**/api/cases/emp-test-case-id`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CASE),
    })
  );

  await page.route(`**/api/cases/emp-test-case-id/files`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FILES),
    })
  );

  await page.route(`**/api/cases/emp-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/emp-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/emp-test-case-id/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/emp-test-case-id/facts`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FACTS),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/emp-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

async function openCaseInfo(page: Page) {
  await page.goto("/tools/litigagent/emp-test-case-id");
  await expect(page.getByText("Rivera v. MegaCorp")).toBeVisible();
  await page.getByRole("button", { name: /case info/i }).click();
  const infoPanel = page.getByTestId("case-info-panel");
  await expect(infoPanel).toBeVisible({ timeout: 10_000 });
  return infoPanel;
}

test.describe("LITIGAGENT Employment History (V2.2b.3)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupMocks(page);
  });

  test("employment facts render as timeline cards ordered by start_date with structured fields", async ({ page }) => {
    const infoPanel = await openCaseInfo(page);

    // Employment section should show
    await expect(infoPanel.getByText("Employment")).toBeVisible();

    // Timeline container should exist
    const timeline = infoPanel.getByTestId("employment-timeline");
    await expect(timeline).toBeVisible();

    // Should have 3 employment rows
    const rows = timeline.getByTestId("employment-row");
    await expect(rows).toHaveCount(3);

    // Rows should be ordered by start_date:
    // 1st: StartupCo (2018-06-01)
    // 2nd: MegaCorp Associate Manager (2019-03-15)
    // 3rd: MegaCorp Senior Manager (2022-06-01)
    const firstRow = rows.nth(0);
    const secondRow = rows.nth(1);
    const thirdRow = rows.nth(2);

    // First row: StartupCo (earliest start_date)
    await expect(firstRow.getByText("StartupCo")).toBeVisible();
    await expect(firstRow.getByText("Intern")).toBeVisible();
    // No end_date → shows "present"
    await expect(firstRow.getByTestId("employment-dates")).toContainText("2018-06-01 → present");

    // Second row: Associate Manager
    await expect(secondRow.getByText("MegaCorp LLC")).toBeVisible();
    await expect(secondRow.getByText(/Associate Manager/)).toBeVisible();
    await expect(secondRow.getByText(/Sales/)).toBeVisible();
    await expect(secondRow.getByTestId("employment-dates")).toContainText("2019-03-15 → 2022-05-31");
    await expect(secondRow.getByTestId("employment-compensation")).toContainText("$120,000");
    await expect(secondRow.getByTestId("employment-reason")).toContainText("promoted");
    // This one is confirmed
    await expect(secondRow.getByText("Confirmed")).toBeVisible();

    // Third row: Senior Manager
    await expect(thirdRow.getByText(/Senior Manager/)).toBeVisible();
    await expect(thirdRow.getByText(/Operations/)).toBeVisible();
    await expect(thirdRow.getByTestId("employment-dates")).toContainText("2022-06-01 → 2025-09-15");
    await expect(thirdRow.getByTestId("employment-compensation")).toContainText("$180,000");
    await expect(thirdRow.getByTestId("employment-reason")).toContainText("terminated");

    // Confidence badges should show
    await expect(thirdRow.getByText("88%")).toBeVisible();

    // Source attribution
    await expect(thirdRow.getByText(/Source: complaint\.pdf/)).toBeVisible();
  });

  test("adding an employment period via + Add creates a new timeline entry", async ({ page }) => {
    let addFactBody: Record<string, unknown> | null = null;

    await page.route(`**/api/cases/emp-test-case-id/facts`, async (route) => {
      if (route.request().method() === "POST") {
        addFactBody = JSON.parse(route.request().postData() || "{}");
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fact-emp-new",
            case_id: "emp-test-case-id",
            category: "employment",
            fact_type: "employment_period",
            value: {
              employer: "OldJob Inc",
              position: "Analyst",
              department: "Finance",
              compensation_rate: 85000,
              compensation_type: "salary",
              pay_period: "annual",
              start_date: "2016-01-10",
              end_date: "2019-03-01",
              change_reason: "resigned",
            },
            source_file_id: null,
            extraction_method: "manual",
            confidence: 1.0,
            confirmed: true,
            superseded_by: null,
            effective_date: null,
            created_at: "2026-03-20T00:00:00",
          }),
        });
      }
      return route.continue();
    });

    const infoPanel = await openCaseInfo(page);

    // Click "+ Add" on the Employment section
    const empHeader = infoPanel.locator("div").filter({ hasText: /^Employment/ });
    await empHeader.getByRole("button", { name: /\+ Add/i }).click();

    const addForm = infoPanel.getByTestId("fact-add-form");
    await expect(addForm).toBeVisible();

    // Fill in employment period fields
    await addForm.getByLabel("New employer").fill("OldJob Inc");
    await addForm.getByLabel("New position").fill("Analyst");
    await addForm.getByLabel("New department").fill("Finance");
    await addForm.getByLabel("New compensation_rate").fill("85000");
    await addForm.getByLabel("New compensation_type").fill("salary");
    await addForm.getByLabel("New pay_period").fill("annual");
    await addForm.getByLabel("New start_date").fill("2016-01-10");
    await addForm.getByLabel("New end_date").fill("2019-03-01");
    await addForm.getByLabel("New change_reason").fill("resigned");

    // Click Add
    await addForm.getByRole("button", { name: "Add" }).click();

    // API should have been called
    await expect(async () => {
      expect(addFactBody).not.toBeNull();
    }).toPass({ timeout: 5_000 });

    expect(addFactBody).toMatchObject({
      category: "employment",
      fact_type: "employment_period",
      value: {
        employer: "OldJob Inc",
        position: "Analyst",
        start_date: "2016-01-10",
        end_date: "2019-03-01",
      },
    });

    // Form should close
    await expect(addForm).not.toBeVisible();

    // New entry should appear in the timeline, sorted first (earliest start_date)
    const timeline = infoPanel.getByTestId("employment-timeline");
    const rows = timeline.getByTestId("employment-row");
    await expect(rows).toHaveCount(4);

    // OldJob Inc (2016-01-10) should be first since it's earliest
    const firstRow = rows.nth(0);
    await expect(firstRow.getByText("OldJob Inc")).toBeVisible();
    await expect(firstRow.getByTestId("employment-dates")).toContainText("2016-01-10 → 2019-03-01");
    await expect(firstRow.getByTestId("employment-reason")).toContainText("resigned");
  });
});
