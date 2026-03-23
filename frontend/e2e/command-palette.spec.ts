import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Command Palette E2E Tests (V2.3b.7)
 *
 * Tests that Cmd+K opens a command palette for quick-switching
 * between workspace tools.
 */

const CASE_ID = "cmd-palette-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Palette Test Case",
  description: null,
  status: "active",
  file_count: 0,
  created_at: "2026-03-20T00:00:00",
  updated_at: "2026-03-20T00:00:00",
};

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "Palette Test Case",
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
}

test.describe("Command Palette (V2.3b.7)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("Cmd+K opens palette, navigates to Chat on selection", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Palette should not be visible initially
    await expect(page.getByTestId("command-palette")).not.toBeVisible();

    // Open palette with Cmd+K (Meta+K)
    await page.keyboard.press("Meta+k");
    await expect(page.getByTestId("command-palette")).toBeVisible();
    await expect(page.getByTestId("command-palette-input")).toBeFocused();

    // Current tool (Files) should NOT be in the list
    await expect(page.getByTestId("palette-item-files")).not.toBeVisible();

    // Chat should be visible and selectable
    await expect(page.getByTestId("palette-item-chat")).toBeVisible();

    // Click Chat to navigate
    await page.getByTestId("palette-item-chat").click();

    // Palette should close and URL should change
    await expect(page.getByTestId("command-palette")).not.toBeVisible();
    await page.waitForURL(`**/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();
  });

  test("palette filters items and supports keyboard navigation", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Open palette with Ctrl+K
    await page.keyboard.press("Control+k");
    await expect(page.getByTestId("command-palette")).toBeVisible();

    // Type "inf" to filter to Case Info
    await page.getByTestId("command-palette-input").fill("inf");

    // Only Info should match (non-disabled enabled items)
    await expect(page.getByTestId("palette-item-info")).toBeVisible();
    await expect(page.getByTestId("palette-item-chat")).not.toBeVisible();

    // Press Enter to select
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("command-palette")).not.toBeVisible();
    await page.waitForURL(`**/cases/${CASE_ID}/info`);
    await expect(page.getByTestId("case-info-panel")).toBeVisible();
  });
});
