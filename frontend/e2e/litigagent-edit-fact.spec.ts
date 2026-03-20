import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Inline Edit Fact E2E Tests (V2.2b.1)
 *
 * Tests the inline edit mode: clicking Edit on a fact shows a form,
 * saving creates a superseding fact via POST /supersede, cancelling
 * dismisses the form.
 *
 * All API calls are mocked via route interception.
 */

const MOCK_CASE = {
  id: "edit-test-case-id",
  name: "Garcia v. BigCo",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-10T00:00:00",
  updated_at: "2026-03-10T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
    case_id: "edit-test-case-id",
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
  case_id: "edit-test-case-id",
  case_name: "Garcia v. BigCo",
  parties: [
    { name: "Ana Garcia", role: "plaintiff", party_type: "individual", count: null },
    { name: "BigCo Inc", role: "defendant", party_type: "entity", count: null },
  ],
  court: null,
  attorneys: [],
  employment_history: [],
  claims: [],
  key_dates: [],
  financials: [],
  fact_count: 3,
  confirmed_count: 1,
  extraction_sources: {
    "file-complaint": ["llm"],
  },
};

const MOCK_FACTS = {
  facts: [
    {
      id: "fact-plaintiff",
      case_id: "edit-test-case-id",
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Ana Garcia", role: "plaintiff" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.92,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-defendant",
      case_id: "edit-test-case-id",
      category: "party",
      fact_type: "defendant",
      value: { name: "BigCo Inc", role: "defendant" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.88,
      confirmed: true,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-termination",
      case_id: "edit-test-case-id",
      category: "date",
      fact_type: "termination_date",
      value: { label: "Termination", date: "2025-06-15" },
      source_file_id: "file-complaint",
      extraction_method: "regex",
      confidence: 0.65,
      confirmed: false,
      superseded_by: null,
      effective_date: "2025-06-15",
      created_at: "2026-03-10T00:00:00",
    },
  ],
  total: 3,
};

async function setupMocks(page: Page) {
  await page.route(`**/api/cases/edit-test-case-id`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CASE),
    })
  );

  await page.route(`**/api/cases/edit-test-case-id/files`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FILES),
    })
  );

  await page.route(`**/api/cases/edit-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/edit-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/edit-test-case-id/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/edit-test-case-id/facts`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FACTS),
    })
  );

  await page.route(`**/api/cases/edit-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

async function openCaseInfo(page: Page) {
  await page.goto("/tools/litigagent/edit-test-case-id");
  await expect(page.getByText("Garcia v. BigCo")).toBeVisible();
  await page.getByRole("button", { name: /case info/i }).click();
  const infoPanel = page.getByTestId("case-info-panel");
  await expect(infoPanel).toBeVisible({ timeout: 10_000 });
  return infoPanel;
}

test.describe("LITIGAGENT Inline Edit Facts (V2.2b.1)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupMocks(page);
  });

  test("clicking Edit on a fact shows an edit form with pre-populated fields", async ({ page }) => {
    const infoPanel = await openCaseInfo(page);

    // Hover over the plaintiff fact row to reveal the Edit button
    const plaintiffRow = infoPanel.locator(".group").filter({ hasText: "Ana Garcia" });
    await plaintiffRow.hover();

    const editButton = plaintiffRow.getByRole("button", { name: /edit/i });
    await expect(editButton).toBeVisible();

    // Click Edit
    await editButton.click();

    // Edit form should appear
    const editForm = infoPanel.getByTestId("fact-edit-form");
    await expect(editForm).toBeVisible();

    // Fields should be pre-populated with current values
    const nameInput = editForm.getByLabel("Edit name");
    await expect(nameInput).toHaveValue("Ana Garcia");

    const roleInput = editForm.getByLabel("Edit role");
    await expect(roleInput).toHaveValue("plaintiff");

    // Save and Cancel buttons should be visible
    await expect(editForm.getByRole("button", { name: "Save" })).toBeVisible();
    await expect(editForm.getByRole("button", { name: "Cancel" })).toBeVisible();
  });

  test("cancelling edit dismisses form and returns to display mode", async ({ page }) => {
    const infoPanel = await openCaseInfo(page);

    // Open edit on plaintiff fact
    const plaintiffRow = infoPanel.locator(".group").filter({ hasText: "Ana Garcia" });
    await plaintiffRow.hover();
    await plaintiffRow.getByRole("button", { name: /edit/i }).click();

    const editForm = infoPanel.getByTestId("fact-edit-form");
    await expect(editForm).toBeVisible();

    // Click Cancel
    await editForm.getByRole("button", { name: "Cancel" }).click();

    // Edit form should disappear
    await expect(editForm).not.toBeVisible();

    // Original fact display should return
    await expect(infoPanel.getByText(/Ana Garcia/)).toBeVisible();
  });

  test("saving edit calls supersede API and updates the fact display", async ({ page }) => {
    let supersedeCalled = false;
    let supersedeBody: Record<string, unknown> | null = null;

    await page.route(`**/api/cases/edit-test-case-id/facts/fact-plaintiff/supersede`, async (route) => {
      if (route.request().method() === "POST") {
        supersedeCalled = true;
        supersedeBody = JSON.parse(route.request().postData() || "{}");
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fact-plaintiff-v2",
            case_id: "edit-test-case-id",
            category: "party",
            fact_type: "plaintiff",
            value: { name: "Ana M. Garcia", role: "plaintiff" },
            source_file_id: null,
            extraction_method: "manual",
            confidence: 1.0,
            confirmed: true,
            superseded_by: null,
            effective_date: null,
            created_at: "2026-03-19T00:00:00",
          }),
        });
      }
      return route.continue();
    });

    const infoPanel = await openCaseInfo(page);

    // Open edit on plaintiff fact
    const plaintiffRow = infoPanel.locator(".group").filter({ hasText: "Ana Garcia" });
    await plaintiffRow.hover();
    await plaintiffRow.getByRole("button", { name: /edit/i }).click();

    const editForm = infoPanel.getByTestId("fact-edit-form");
    await expect(editForm).toBeVisible();

    // Change the name
    const nameInput = editForm.getByLabel("Edit name");
    await nameInput.clear();
    await nameInput.fill("Ana M. Garcia");

    // Click Save
    await editForm.getByRole("button", { name: "Save" }).click();

    // API should have been called with correct body
    await expect(async () => {
      expect(supersedeCalled).toBe(true);
    }).toPass({ timeout: 5_000 });

    expect(supersedeBody).toMatchObject({
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Ana M. Garcia", role: "plaintiff" },
    });

    // Edit form should close
    await expect(editForm).not.toBeVisible();

    // Updated fact should show new value and manual extraction method
    await expect(infoPanel.getByText(/Ana M\. Garcia/)).toBeVisible({ timeout: 5_000 });
    await expect(infoPanel.getByText("manual")).toBeVisible();
    await expect(infoPanel.getByText("100%")).toBeVisible();
  });

  test("editing a date fact pre-fills effective date and sends it with supersede", async ({ page }) => {
    let supersedeBody: Record<string, unknown> | null = null;

    await page.route(`**/api/cases/edit-test-case-id/facts/fact-termination/supersede`, async (route) => {
      if (route.request().method() === "POST") {
        supersedeBody = JSON.parse(route.request().postData() || "{}");
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fact-termination-v2",
            case_id: "edit-test-case-id",
            category: "date",
            fact_type: "termination_date",
            value: { label: "Termination", date: "2025-07-01" },
            source_file_id: null,
            extraction_method: "manual",
            confidence: 1.0,
            confirmed: true,
            superseded_by: null,
            effective_date: "2025-07-01",
            created_at: "2026-03-19T00:00:00",
          }),
        });
      }
      return route.continue();
    });

    const infoPanel = await openCaseInfo(page);

    // Open edit on termination date fact
    const dateRow = infoPanel.locator(".group").filter({ hasText: "Termination" });
    await dateRow.hover();
    await dateRow.getByRole("button", { name: /edit/i }).click();

    const editForm = infoPanel.getByTestId("fact-edit-form");
    await expect(editForm).toBeVisible();

    // Effective date should be pre-filled
    const effectiveDateInput = editForm.getByLabel("Edit effective date");
    await expect(effectiveDateInput).toHaveValue("2025-06-15");

    // Change the date value
    const dateInput = editForm.getByLabel("Edit date");
    await dateInput.clear();
    await dateInput.fill("2025-07-01");

    // Change effective date
    await effectiveDateInput.fill("2025-07-01");

    // Save
    await editForm.getByRole("button", { name: "Save" }).click();

    // Verify the API was called with the effective date
    await expect(async () => {
      expect(supersedeBody).not.toBeNull();
    }).toPass({ timeout: 5_000 });

    expect(supersedeBody).toMatchObject({
      category: "date",
      fact_type: "termination_date",
      value: { label: "Termination", date: "2025-07-01" },
      effective_date: "2025-07-01",
    });

    // Updated fact should display
    await expect(editForm).not.toBeVisible();
    await expect(infoPanel.getByText("manual")).toBeVisible();
  });
});
