import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Case Info E2E Tests (V2.2a.7)
 *
 * Tests the Case Info panel: toggle open/close, fact display with
 * source attribution, and confirm button interaction.
 *
 * All API calls are mocked via route interception.
 */

const MOCK_CASE = {
  id: "info-test-case-id",
  name: "Martinez v. Acme Corp",
  description: null,
  status: "active",
  file_count: 2,
  created_at: "2026-03-07T00:00:00",
  updated_at: "2026-03-07T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-complaint",
    case_id: "info-test-case-id",
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
    created_at: "2026-03-07T00:00:00",
    updated_at: "2026-03-07T00:00:00",
  },
  {
    id: "file-offer-letter",
    case_id: "info-test-case-id",
    original_filename: "offer_letter.pdf",
    file_type: "pdf",
    mime_type: "application/pdf",
    file_size_bytes: 25000,
    upload_order: 2,
    processing_status: "ready",
    error_message: null,
    ocr_confidence: null,
    page_count: 2,
    metadata: null,
    text_dirty: false,
    created_at: "2026-03-07T00:00:00",
    updated_at: "2026-03-07T00:00:00",
  },
];

const MOCK_CONTEXT = {
  case_id: "info-test-case-id",
  case_name: "Martinez v. Acme Corp",
  parties: [
    { name: "Maria Martinez", role: "plaintiff", party_type: "individual", count: null },
    { name: "Acme Corp", role: "defendant", party_type: "entity", count: null },
  ],
  court: {
    court: "Superior Court of California, County of Los Angeles",
    county: "Los Angeles",
    department: "Dept. 12",
    judge: "Hon. Sarah Chen",
  },
  attorneys: [
    { name: "John Davis", side: "plaintiff", bar_number: "123456", firm: "Davis & Partners", email: null },
  ],
  employment_history: [
    { employer: "Acme Corp", position: "Senior Engineer", department: "Engineering", compensation_rate: 150000, compensation_type: "salary", pay_period: "annual", start_date: "2020-03-15", end_date: "2025-11-01", change_reason: "terminated" },
  ],
  claims: [
    { claim_type: "wrongful_termination", status: "active", protected_class: "age", supporting_facts: null, reason: null },
  ],
  key_dates: [
    { label: "Termination Date", date: "2025-11-01", date_type: "employment" },
  ],
  financials: [
    { label: "Annual Salary", amount: 150000, date: null },
  ],
  fact_count: 8,
  confirmed_count: 3,
  extraction_sources: {
    "file-complaint": ["llm", "regex"],
    "file-offer-letter": ["llm"],
  },
};

const MOCK_FACTS = {
  facts: [
    {
      id: "fact-plaintiff",
      case_id: "info-test-case-id",
      category: "party",
      fact_type: "plaintiff",
      value: { name: "Maria Martinez", role: "plaintiff" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.95,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-07T00:00:00",
    },
    {
      id: "fact-defendant",
      case_id: "info-test-case-id",
      category: "party",
      fact_type: "defendant",
      value: { name: "Acme Corp", role: "defendant" },
      source_file_id: "file-complaint",
      extraction_method: "llm",
      confidence: 0.92,
      confirmed: true,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-07T00:00:00",
    },
    {
      id: "fact-employer",
      case_id: "info-test-case-id",
      category: "employment",
      fact_type: "employer",
      value: { employer: "Acme Corp", position: "Senior Engineer" },
      source_file_id: "file-offer-letter",
      extraction_method: "llm",
      confidence: 0.88,
      confirmed: false,
      superseded_by: null,
      effective_date: null,
      created_at: "2026-03-07T00:00:00",
    },
    {
      id: "fact-termination",
      case_id: "info-test-case-id",
      category: "date",
      fact_type: "termination_date",
      value: { label: "Termination", date: "2025-11-01" },
      source_file_id: "file-complaint",
      extraction_method: "regex",
      confidence: 0.6,
      confirmed: false,
      superseded_by: null,
      effective_date: "2025-11-01",
      created_at: "2026-03-07T00:00:00",
    },
  ],
  total: 4,
};

async function setupCaseMocks(page: Page) {
  await page.route(`**/api/cases/info-test-case-id`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_CASE),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/info-test-case-id/files`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FILES),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/info-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/info-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );

  await page.route(`**/api/cases/info-test-case-id/context`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

  await page.route(`**/api/cases/info-test-case-id/facts`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FACTS),
    })
  );

  await page.route(`**/api/cases/info-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );
}

test.describe("LITIGAGENT Case Info Panel", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupCaseMocks(page);
  });

  test("Case Info button toggles the info panel open and closed", async ({ page }) => {
    await page.goto("/tools/litigagent/info-test-case-id");
    await expect(page.getByText("Martinez v. Acme Corp")).toBeVisible();

    // Case Info panel should not be visible initially
    const infoPanel = page.getByTestId("case-info-panel");
    await expect(infoPanel).not.toBeVisible();

    // The three-panel layout should be visible (file panel exists)
    await expect(page.locator('[aria-label="Case files"]')).toBeVisible();

    // Click "Case Info" button to open
    await page.getByRole("button", { name: /case info/i }).click();

    // Info panel should appear
    await expect(infoPanel).toBeVisible({ timeout: 10_000 });

    // Three-panel layout should be hidden (file panel gone)
    await expect(page.locator('[aria-label="Case files"]')).not.toBeVisible();

    // Fact count should display
    await expect(page.getByText(/8 facts/)).toBeVisible();
    await expect(page.getByText(/3 confirmed/)).toBeVisible();

    // Click close button to dismiss
    await page.getByTitle("Close case info").click();

    // Info panel should be hidden, file panel should return
    await expect(infoPanel).not.toBeVisible();
    await expect(page.locator('[aria-label="Case files"]')).toBeVisible();
  });

  test("facts display grouped by section with source attribution and confidence", async ({ page }) => {
    await page.goto("/tools/litigagent/info-test-case-id");
    await page.getByRole("button", { name: /case info/i }).click();

    const infoPanel = page.getByTestId("case-info-panel");
    await expect(infoPanel).toBeVisible({ timeout: 10_000 });

    // Section headers should render
    await expect(infoPanel.getByText("Parties")).toBeVisible();
    await expect(infoPanel.getByText("Employment")).toBeVisible();
    await expect(infoPanel.getByText("Key Dates")).toBeVisible();

    // Fact values should display
    await expect(infoPanel.getByText(/Maria Martinez/)).toBeVisible();
    await expect(infoPanel.getByText(/Acme Corp/)).toBeVisible();
    await expect(infoPanel.getByText(/Senior Engineer/)).toBeVisible();

    // Confidence badges: 95% (high), 88% (medium), 60% (low)
    await expect(infoPanel.getByText("95%")).toBeVisible();
    await expect(infoPanel.getByText("88%")).toBeVisible();
    await expect(infoPanel.getByText("60%")).toBeVisible();

    // Extraction method tags
    await expect(infoPanel.getByText("llm").first()).toBeVisible();
    await expect(infoPanel.getByText("regex")).toBeVisible();

    // Source attribution — file names resolved from IDs
    await expect(infoPanel.getByText(/Source: complaint\.pdf/).first()).toBeVisible();
    await expect(infoPanel.getByText(/Source: offer_letter\.pdf/)).toBeVisible();

    // Effective date on the termination fact
    await expect(infoPanel.getByText(/Effective: 2025-11-01/)).toBeVisible();

    // Confirmed fact shows "Confirmed" badge (defendant fact)
    await expect(infoPanel.getByText("Confirmed")).toBeVisible();

    // Extraction Sources section at bottom
    await expect(infoPanel.getByText("Extraction Sources")).toBeVisible();
    await expect(infoPanel.getByText(/complaint\.pdf/).first()).toBeVisible();
    await expect(infoPanel.getByText(/llm, regex/)).toBeVisible();
  });

  test("clicking confirm button updates the fact", async ({ page }) => {
    // Track confirm API calls
    let confirmCalled = false;
    await page.route(`**/api/cases/info-test-case-id/facts/fact-plaintiff/confirm`, (route) => {
      if (route.request().method() === "PUT") {
        confirmCalled = true;
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

    await page.goto("/tools/litigagent/info-test-case-id");
    await page.getByRole("button", { name: /case info/i }).click();

    const infoPanel = page.getByTestId("case-info-panel");
    await expect(infoPanel).toBeVisible({ timeout: 10_000 });

    // The plaintiff fact should have a "Confirm" button (not yet confirmed)
    // Hover to reveal the confirm button (opacity-0 → group-hover:opacity-100)
    const plaintiffRow = infoPanel.locator(".group").filter({ hasText: "Maria Martinez" });
    await plaintiffRow.hover();

    const confirmButton = plaintiffRow.getByRole("button", { name: /confirm/i });
    await expect(confirmButton).toBeVisible();

    // Click confirm
    await confirmButton.click();

    // API should have been called
    expect(confirmCalled).toBe(true);

    // The button should be replaced by "Confirmed" text
    await expect(plaintiffRow.getByText("Confirmed")).toBeVisible({ timeout: 5_000 });
    await expect(confirmButton).not.toBeVisible();
  });
});
