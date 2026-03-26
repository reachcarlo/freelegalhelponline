import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace Objection Drafter E2E Tests (V2.5.1)
 *
 * Tests that the objection drafter is accessible inside the case workspace
 * via sidebar navigation at /cases/[caseId]/objections.
 */

const CASE_ID = "ws-obj-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Objections Test Case",
  description: null,
  status: "active",
  file_count: 0,
  created_at: "2026-03-25T00:00:00",
  updated_at: "2026-03-25T00:00:00",
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
      body: JSON.stringify({
        case_id: CASE_ID,
        case_name: "Objections Test Case",
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
      }),
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

  await page.route(`**/api/cases/${CASE_ID}/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/facts*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ facts: [], total: 0 }),
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/artifacts`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ artifacts: [] }),
    })
  );
}

test.describe("Workspace Objection Drafter (V2.5.1)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("sidebar Objections link navigates to objection drafter inside workspace", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Set viewport large enough for sidebar labels
    await page.setViewportSize({ width: 1280, height: 800 });

    // Click Objections in the sidebar
    const objectionsLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Objections" });
    await expect(objectionsLink).toBeVisible();
    await objectionsLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/objections`);

    // Objection Drafter wizard should render
    await expect(
      page.getByRole("heading", { name: "Objection Drafter Setup" }),
    ).toBeVisible();

    // Breadcrumb should show Cases > Case Name > Objections
    const breadcrumb = page.getByTestId("workspace-breadcrumb");
    await expect(breadcrumb).toContainText("Cases");
    await expect(breadcrumb).toContainText("Objections Test Case");
    await expect(breadcrumb).toContainText("Objections");
  });
});

test.describe("Objection CaseContext Pre-fill (V2.5.2)", () => {
  test("default party role is Defendant without CaseContext attorney match", async ({
    page,
  }) => {
    await setupAuth(page);
    await mockAPIs(page);
    await page.goto(`/cases/${CASE_ID}/objections`);

    await expect(
      page.getByRole("heading", { name: "Objection Drafter Setup" }),
    ).toBeVisible();

    // Default: Defendant should be selected
    const defendantBtn = page.getByRole("button", { name: "Defendant" });
    await expect(defendantBtn).toHaveAttribute("aria-pressed", "true");

    const plaintiffBtn = page.getByRole("button", { name: "Plaintiff" });
    await expect(plaintiffBtn).toHaveAttribute("aria-pressed", "false");
  });

  test("party role inferred as Plaintiff when user email matches plaintiff attorney", async ({
    page,
  }) => {
    await setupAuth(page);

    // Override context mock: add a plaintiff attorney whose email matches the test user (e2e@lawfirm.com)
    const contextWithAttorney = {
      case_id: CASE_ID,
      case_name: "Objections Test Case",
      parties: [],
      court: null,
      attorneys: [
        {
          name: "E2E Attorney",
          bar_number: "12345",
          firm: "E2E Law",
          email: "e2e@lawfirm.com",
          phone: null,
          address: null,
          side: "plaintiff",
        },
      ],
      employment_history: [],
      claims: [],
      key_dates: [],
      financials: [],
      fact_count: 0,
      confirmed_count: 0,
      extraction_sources: {},
    };

    await mockAPIs(page);

    // Override context route AFTER mockAPIs to use our custom context
    await page.route(`**/api/cases/${CASE_ID}/context`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(contextWithAttorney),
      })
    );

    await page.goto(`/cases/${CASE_ID}/objections`);
    await expect(
      page.getByRole("heading", { name: "Objection Drafter Setup" }),
    ).toBeVisible();

    // Plaintiff should be pre-selected via party role inference
    const plaintiffBtn = page.getByRole("button", { name: "Plaintiff" });
    await expect(plaintiffBtn).toHaveAttribute("aria-pressed", "true");

    const defendantBtn = page.getByRole("button", { name: "Defendant" });
    await expect(defendantBtn).toHaveAttribute("aria-pressed", "false");
  });
});

test.describe("Discovery Request Detection (V2.5.3)", () => {
  const FILE_ID = "disc-req-file-001";
  const FILENAME = "Interrogatories_Set_1.pdf";
  const EXTRACTED_TEXT = "INTERROGATORY NO. 1: State your full legal name.";

  test("shows banner when discovery_request facts exist in case files", async ({
    page,
  }) => {
    await setupAuth(page);
    await mockAPIs(page);

    // Override facts to include a discovery_request fact
    await page.route(`**/api/cases/${CASE_ID}/facts*`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          facts: [
            {
              id: "fact-dr-1",
              case_id: CASE_ID,
              category: "discovery",
              fact_type: "discovery_request",
              value: { tool: "interrogatories" },
              source_file_id: FILE_ID,
              extraction_method: "llm",
              confidence: 0.9,
              confirmed: false,
              superseded_by: null,
              effective_date: null,
              created_at: "2026-03-25T00:00:00",
            },
          ],
          total: 1,
        }),
      })
    );

    // Override files to include the source file
    await page.route(`**/api/cases/${CASE_ID}/files`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: FILE_ID,
              case_id: CASE_ID,
              original_filename: FILENAME,
              file_type: "pdf",
              mime_type: "application/pdf",
              file_size_bytes: 12345,
              upload_order: 1,
              processing_status: "ready",
              error_message: null,
              ocr_confidence: null,
              page_count: 2,
              metadata: null,
              text_dirty: false,
              created_at: "2026-03-25T00:00:00",
              updated_at: "2026-03-25T00:00:00",
            },
          ]),
        });
      }
      return route.continue();
    });

    await page.goto(`/cases/${CASE_ID}/objections`);

    // Banner should appear
    const banner = page.getByTestId("discovery-request-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("Discovery requests detected");
    await expect(banner).toContainText(FILENAME);
  });

  test("clicking file button fetches text and pre-populates drafter input", async ({
    page,
  }) => {
    await setupAuth(page);
    await mockAPIs(page);

    // Override facts
    await page.route(`**/api/cases/${CASE_ID}/facts*`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          facts: [
            {
              id: "fact-dr-1",
              case_id: CASE_ID,
              category: "discovery",
              fact_type: "discovery_request",
              value: {},
              source_file_id: FILE_ID,
              extraction_method: "llm",
              confidence: 0.9,
              confirmed: false,
              superseded_by: null,
              effective_date: null,
              created_at: "2026-03-25T00:00:00",
            },
          ],
          total: 1,
        }),
      })
    );

    // Override files list
    await page.route(`**/api/cases/${CASE_ID}/files`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: FILE_ID,
              case_id: CASE_ID,
              original_filename: FILENAME,
              file_type: "pdf",
              mime_type: "application/pdf",
              file_size_bytes: 12345,
              upload_order: 1,
              processing_status: "ready",
              error_message: null,
              ocr_confidence: null,
              page_count: 2,
              metadata: null,
              text_dirty: false,
              created_at: "2026-03-25T00:00:00",
              updated_at: "2026-03-25T00:00:00",
            },
          ]),
        });
      }
      return route.continue();
    });

    // Mock file detail endpoint
    await page.route(`**/api/cases/${CASE_ID}/files/${FILE_ID}`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: FILE_ID,
            case_id: CASE_ID,
            original_filename: FILENAME,
            file_type: "pdf",
            mime_type: "application/pdf",
            file_size_bytes: 12345,
            upload_order: 1,
            processing_status: "ready",
            error_message: null,
            ocr_confidence: null,
            page_count: 2,
            metadata: null,
            text_dirty: false,
            created_at: "2026-03-25T00:00:00",
            updated_at: "2026-03-25T00:00:00",
            extracted_text: EXTRACTED_TEXT,
            edited_text: null,
          }),
        });
      }
      return route.continue();
    });

    await page.goto(`/cases/${CASE_ID}/objections`);

    // Click the file button
    const fileBtn = page.getByTestId(`use-file-${FILE_ID}`);
    await expect(fileBtn).toBeVisible();
    await fileBtn.click();

    // Should advance to Input step and pre-fill textarea
    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible();
    await expect(textarea).toHaveValue(EXTRACTED_TEXT);

    // Banner should be hidden after use
    await expect(page.getByTestId("discovery-request-banner")).not.toBeVisible();
  });
});
