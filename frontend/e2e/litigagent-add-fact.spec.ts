import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Add New Fact E2E Tests (V2.2b.2)
 *
 * Tests the [+ Add] buttons on each section: clicking Add shows a form,
 * saving creates a new fact via POST /facts, cancelling dismisses the form.
 *
 * All API calls are mocked via route interception.
 */

const MOCK_CASE = {
  id: "add-test-case-id",
  name: "Lee v. TechCo",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-10T00:00:00",
  updated_at: "2026-03-10T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
    case_id: "add-test-case-id",
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
  case_id: "add-test-case-id",
  case_name: "Lee v. TechCo",
  parties: [],
  court: null,
  attorneys: [],
  employment_history: [],
  claims: [],
  key_dates: [],
  financials: [],
  fact_count: 1,
  confirmed_count: 0,
  extraction_sources: {},
};

const MOCK_FACTS = {
  facts: [
    {
      id: "fact-plaintiff",
      case_id: "add-test-case-id",
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Jenny Lee", role: "plaintiff" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.92,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
  ],
  total: 1,
};

async function setupMocks(page: Page) {
  await page.route(`**/api/cases/add-test-case-id`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CASE),
    })
  );

  await page.route(`**/api/cases/add-test-case-id/files`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FILES),
    })
  );

  await page.route(`**/api/cases/add-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/add-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/add-test-case-id/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/add-test-case-id/facts`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FACTS),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/add-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

async function openCaseInfo(page: Page) {
  await page.goto("/tools/litigagent/add-test-case-id");
  await expect(page.getByText("Lee v. TechCo")).toBeVisible();
  await page.getByRole("button", { name: /case info/i }).click();
  const infoPanel = page.getByTestId("case-info-panel");
  await expect(infoPanel).toBeVisible({ timeout: 10_000 });
  return infoPanel;
}

test.describe("LITIGAGENT Add New Facts (V2.2b.2)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupMocks(page);
  });

  test("clicking + Add shows a new fact form and Cancel dismisses it", async ({ page }) => {
    const infoPanel = await openCaseInfo(page);

    // Each section should have a "+ Add" button
    const addButtons = infoPanel.getByRole("button", { name: /\+ Add/i });
    // There are 7 sections (party, court, attorney, employment, claim, date, financial)
    await expect(addButtons.first()).toBeVisible();

    // Click "+ Add" on the Key Dates section
    const datesHeader = infoPanel.locator("div").filter({ hasText: /Key Dates/i });
    const addDateButton = datesHeader.getByRole("button", { name: /\+ Add/i });
    await addDateButton.click();

    // Add form should appear
    const addForm = infoPanel.getByTestId("fact-add-form");
    await expect(addForm).toBeVisible();

    // Form should have empty fields for the date template (label, date)
    const labelInput = addForm.getByLabel("New label");
    await expect(labelInput).toBeVisible();
    await expect(labelInput).toHaveValue("");

    const dateInput = addForm.getByLabel("New date");
    await expect(dateInput).toBeVisible();

    // Add and Cancel buttons should be visible
    await expect(addForm.getByRole("button", { name: "Add" })).toBeVisible();
    await expect(addForm.getByRole("button", { name: "Cancel" })).toBeVisible();

    // Click Cancel — form should disappear
    await addForm.getByRole("button", { name: "Cancel" }).click();
    await expect(addForm).not.toBeVisible();
  });

  test("adding a new fact calls POST /facts and shows the new fact", async ({ page }) => {
    let addFactCalled = false;
    let addFactBody: Record<string, unknown> | null = null;

    await page.route(`**/api/cases/add-test-case-id/facts`, async (route) => {
      if (route.request().method() === "POST") {
        addFactCalled = true;
        addFactBody = JSON.parse(route.request().postData() || "{}");
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fact-new-date",
            case_id: "add-test-case-id",
            category: "date",
            fact_type: "key_date",
            value: { label: "Filing Date", date: "2026-01-15" },
            source_file_id: null,
            extraction_method: "manual",
            confidence: 1.0,
            confirmed: true,
            superseded_by: null,
            effective_date: "2026-01-15",
            created_at: "2026-03-20T00:00:00",
          }),
        });
      }
      return route.continue();
    });

    const infoPanel = await openCaseInfo(page);

    // Click "+ Add" on the Key Dates section
    const datesHeader = infoPanel.locator("div").filter({ hasText: /Key Dates/i });
    await datesHeader.getByRole("button", { name: /\+ Add/i }).click();

    const addForm = infoPanel.getByTestId("fact-add-form");
    await expect(addForm).toBeVisible();

    // Fill in the form
    await addForm.getByLabel("New label").fill("Filing Date");
    await addForm.getByLabel("New date").fill("2026-01-15");
    await addForm.getByLabel("New effective date").fill("2026-01-15");

    // Click Add
    await addForm.getByRole("button", { name: "Add" }).click();

    // API should have been called with correct body
    await expect(async () => {
      expect(addFactCalled).toBe(true);
    }).toPass({ timeout: 5_000 });

    expect(addFactBody).toMatchObject({
      category: "date",
      fact_type: "key_date",
      value: { label: "Filing Date", date: "2026-01-15" },
      effective_date: "2026-01-15",
    });

    // Add form should close
    await expect(addForm).not.toBeVisible();

    // New fact should display in the panel
    await expect(infoPanel.getByText(/Filing Date/)).toBeVisible({ timeout: 5_000 });
    await expect(infoPanel.getByText("manual")).toBeVisible();
    await expect(infoPanel.getByText("100%")).toBeVisible();
  });

  test("adding a party fact with type selector sends correct category and fact_type", async ({ page }) => {
    let addFactBody: Record<string, unknown> | null = null;

    await page.route(`**/api/cases/add-test-case-id/facts`, async (route) => {
      if (route.request().method() === "POST") {
        addFactBody = JSON.parse(route.request().postData() || "{}");
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fact-new-defendant",
            case_id: "add-test-case-id",
            category: "party",
            fact_type: "defendant",
            value: { name: "TechCo Inc", role: "defendant" },
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

    // Click "+ Add" on the Parties section
    const partiesHeader = infoPanel.locator("div").filter({ hasText: /^Parties/ });
    await partiesHeader.getByRole("button", { name: /\+ Add/i }).click();

    const addForm = infoPanel.getByTestId("fact-add-form");
    await expect(addForm).toBeVisible();

    // Parties section should have a type selector (plaintiff/defendant)
    const typeSelector = addForm.getByLabel("Fact type");
    await expect(typeSelector).toBeVisible();

    // Select "defendant"
    await typeSelector.selectOption({ label: "defendant" });

    // Fill in the fields
    await addForm.getByLabel("New name").fill("TechCo Inc");
    await addForm.getByLabel("New role").fill("defendant");

    // Click Add
    await addForm.getByRole("button", { name: "Add" }).click();

    // API should have been called
    await expect(async () => {
      expect(addFactBody).not.toBeNull();
    }).toPass({ timeout: 5_000 });

    expect(addFactBody).toMatchObject({
      category: "party",
      fact_type: "defendant",
      value: { name: "TechCo Inc", role: "defendant" },
    });

    // Form should close and new fact should appear
    await expect(addForm).not.toBeVisible();
    await expect(infoPanel.getByText(/TechCo Inc/)).toBeVisible({ timeout: 5_000 });
  });
});
