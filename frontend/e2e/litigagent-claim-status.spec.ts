import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Claims Status E2E Tests (V2.2b.4)
 *
 * Tests the claim status dropdown: claim facts show a status dropdown
 * (Active/Dropped/Amended/Settled), changing it creates a superseding
 * claim fact via POST /supersede.
 *
 * All API calls are mocked via route interception.
 */

const MOCK_CASE = {
  id: "claim-test-case-id",
  name: "Nguyen v. RetailCo",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-10T00:00:00",
  updated_at: "2026-03-10T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
    case_id: "claim-test-case-id",
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
  case_id: "claim-test-case-id",
  case_name: "Nguyen v. RetailCo",
  parties: [
    { name: "Linh Nguyen", role: "plaintiff", party_type: "individual", count: null },
    { name: "RetailCo Inc", role: "defendant", party_type: "entity", count: null },
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

const MOCK_FACTS = {
  facts: [
    {
      id: "fact-plaintiff",
      case_id: "claim-test-case-id",
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Linh Nguyen", role: "plaintiff" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.95,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
    {
      id: "fact-claim-wt",
      case_id: "claim-test-case-id",
      category: "claim",
      fact_type: "claim",
      value: {
        claim_type: "wrongful_termination",
        status: "active",
        protected_class: "age",
        reason: "Plaintiff alleges age-based termination",
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
      id: "fact-claim-disc",
      case_id: "claim-test-case-id",
      category: "claim",
      fact_type: "claim",
      value: {
        claim_type: "discrimination",
        status: "active",
        protected_class: "national_origin",
        reason: null,
      },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.75,
      confirmed: true,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-10T00:00:00",
    },
  ],
  total: 3,
};

async function setupMocks(page: Page) {
  await page.route(`**/api/cases/claim-test-case-id`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CASE),
    })
  );

  await page.route(`**/api/cases/claim-test-case-id/files`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FILES),
    })
  );

  await page.route(`**/api/cases/claim-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/claim-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/claim-test-case-id/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/claim-test-case-id/facts`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FACTS),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/claim-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

async function openCaseInfo(page: Page) {
  await page.goto("/tools/litigagent/claim-test-case-id");
  await expect(page.getByText("Nguyen v. RetailCo")).toBeVisible();
  await page.getByRole("button", { name: /case info/i }).click();
  const infoPanel = page.getByTestId("case-info-panel");
  await expect(infoPanel).toBeVisible({ timeout: 10_000 });
  return infoPanel;
}

test.describe("LITIGAGENT Claims Status (V2.2b.4)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupMocks(page);
  });

  test("claim facts render with status dropdown showing current status and structured fields", async ({ page }) => {
    const infoPanel = await openCaseInfo(page);

    // Claims section should show
    await expect(infoPanel.getByText("Claims")).toBeVisible();

    // Should have 2 claim rows
    const claimRows = infoPanel.getByTestId("claim-row");
    await expect(claimRows).toHaveCount(2);

    // First claim: wrongful_termination
    const wtRow = claimRows.nth(0);
    await expect(wtRow.getByText("wrongful termination")).toBeVisible();
    await expect(wtRow.getByText(/Protected class: age/)).toBeVisible();
    await expect(wtRow.getByText(/age-based termination/)).toBeVisible();
    await expect(wtRow.getByText("88%")).toBeVisible();

    // Status dropdown should show "Active"
    const wtStatus = wtRow.getByTestId("claim-status-select");
    await expect(wtStatus).toHaveValue("active");

    // Second claim: discrimination (confirmed)
    const discRow = claimRows.nth(1);
    await expect(discRow.getByText("discrimination")).toBeVisible();
    await expect(discRow.getByText(/Protected class: national_origin/)).toBeVisible();
    await expect(discRow.getByText("Confirmed")).toBeVisible();

    const discStatus = discRow.getByTestId("claim-status-select");
    await expect(discStatus).toHaveValue("active");

    // Dropdown should have all 4 options
    const options = wtStatus.locator("option");
    await expect(options).toHaveCount(4);
    await expect(options.nth(0)).toHaveText("Active");
    await expect(options.nth(1)).toHaveText("Dropped");
    await expect(options.nth(2)).toHaveText("Amended");
    await expect(options.nth(3)).toHaveText("Settled");
  });

  test("changing claim status dropdown calls supersede API and updates the display", async ({ page }) => {
    let supersedeCalled = false;
    let supersedeBody: Record<string, unknown> | null = null;

    await page.route(`**/api/cases/claim-test-case-id/facts/fact-claim-wt/supersede`, async (route) => {
      if (route.request().method() === "POST") {
        supersedeCalled = true;
        supersedeBody = JSON.parse(route.request().postData() || "{}");
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fact-claim-wt-v2",
            case_id: "claim-test-case-id",
            category: "claim",
            fact_type: "claim",
            value: {
              claim_type: "wrongful_termination",
              status: "settled",
              protected_class: "age",
              reason: "Plaintiff alleges age-based termination",
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

    // Find the wrongful termination claim row
    const claimRows = infoPanel.getByTestId("claim-row");
    const wtRow = claimRows.nth(0);

    // Change status from Active to Settled
    const statusSelect = wtRow.getByTestId("claim-status-select");
    await expect(statusSelect).toHaveValue("active");
    await statusSelect.selectOption("settled");

    // API should have been called with supersede
    await expect(async () => {
      expect(supersedeCalled).toBe(true);
    }).toPass({ timeout: 5_000 });

    expect(supersedeBody).toMatchObject({
      category: "claim",
      fact_type: "claim",
      value: {
        claim_type: "wrongful_termination",
        status: "settled",
        protected_class: "age",
        reason: "Plaintiff alleges age-based termination",
      },
    });

    // After API response, the row should update to show manual extraction and 100%
    await expect(wtRow.getByText("manual")).toBeVisible({ timeout: 5_000 });
    await expect(wtRow.getByText("100%")).toBeVisible();

    // Status dropdown should now show "settled"
    await expect(statusSelect).toHaveValue("settled");
  });
});
