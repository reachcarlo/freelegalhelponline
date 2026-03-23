import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace Navigation E2E Tests (V2.3b.1)
 *
 * Tests that Files, Chat, and Info render as child routes inside the
 * workspace shell, and that sidebar navigation switches between them.
 *
 * All API calls are mocked via route interception.
 */

const CASE_ID = "ws-nav-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Navigation Test Case",
  description: null,
  status: "active",
  file_count: 2,
  created_at: "2026-03-20T00:00:00",
  updated_at: "2026-03-20T00:00:00",
};

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "Navigation Test Case",
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

const MOCK_FILES = [
  {
    id: "file-a",
    case_id: CASE_ID,
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
    created_at: "2026-03-20T00:00:00",
    updated_at: "2026-03-20T00:00:00",
  },
];

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
      body: JSON.stringify(MOCK_CONTEXT),
    })
  );

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
}

test.describe("Workspace Navigation (V2.3b.1)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("sidebar navigates between Files, Chat, and Info views", async ({
    page,
  }) => {
    // Navigate to case — should redirect to /files
    await page.goto(`/cases/${CASE_ID}`);
    await page.waitForURL(`**/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Files view should be active by default — look for the file panel
    await expect(
      page.locator('[data-testid="workspace-canvas"]')
    ).toBeVisible();

    // Click Chat in the sidebar (visible on lg+)
    await page.setViewportSize({ width: 1280, height: 800 });
    const chatLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Chat" });
    await chatLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Click Info in the sidebar
    const infoLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Info" });
    await infoLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/info`);
    await expect(page.getByTestId("case-info-panel")).toBeVisible();

    // Click Files to go back
    const filesLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Files" });
    await filesLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/files`);
  });

  test("chat route renders full-panel chat with input", async ({ page }) => {
    await page.goto(`/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Should have the input textarea
    const input = page.getByPlaceholder("Ask about this case...");
    await expect(input).toBeVisible();

    // Should show suggested questions (empty files = default suggestions)
    await expect(
      page.getByText("Ask questions about your case files")
    ).toBeVisible();
  });

  test("info route renders Case Info panel", async ({ page }) => {
    await page.goto(`/cases/${CASE_ID}/info`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByTestId("case-info-panel")).toBeVisible();
  });
});
