import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace Discovery Routes E2E Tests (V2.4.1)
 *
 * Tests that discovery tools are accessible inside the case workspace
 * via sidebar navigation and the discovery hub page.
 */

const CASE_ID = "ws-disc-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Discovery Test Case",
  description: null,
  status: "active",
  file_count: 0,
  created_at: "2026-03-23T00:00:00",
  updated_at: "2026-03-23T00:00:00",
};

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "Discovery Test Case",
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

  await page.route(`**/api/cases/${CASE_ID}/artifacts`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ artifacts: [] }),
    })
  );

  // Mock discovery API endpoints used by the wizards
  await page.route("**/api/discovery/suggest*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        srogs_categories: [],
        rfpds_categories: [],
        rfas_categories: [],
        srogs_categories_defendant: [],
        rfpds_categories_defendant: [],
        rfas_categories_defendant: [],
      }),
    })
  );
}

test.describe("Workspace Discovery Routes (V2.4.1)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("sidebar Discovery link navigates to hub, hub links to SROGs sub-route", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Set viewport large enough for sidebar labels
    await page.setViewportSize({ width: 1280, height: 800 });

    // Click Discovery in the sidebar
    const discoveryLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Discovery" });
    await expect(discoveryLink).toBeVisible();
    await discoveryLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/discovery`);

    // Discovery hub should be visible
    await expect(page.getByTestId("discovery-hub")).toBeVisible();
    await expect(page.getByText("Discovery Tools")).toBeVisible();

    // Breadcrumb should show Cases > Case Name > Discovery
    const breadcrumb = page.getByTestId("workspace-breadcrumb");
    await expect(breadcrumb).toContainText("Cases");
    await expect(breadcrumb).toContainText("Discovery Test Case");
    await expect(breadcrumb).toContainText("Discovery");

    // Click SROGs tool card in the hub
    await page.getByTestId("discovery-tool-srogs").click();
    await page.waitForURL(`**/cases/${CASE_ID}/discovery/srogs`);

    // Breadcrumb should now show Discovery > SROGs
    await expect(breadcrumb).toContainText("SROGs");
  });

  test("direct navigation to discovery sub-route renders wizard inside workspace", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Should see the SROGs wizard title
    await expect(page.getByText("Special Interrogatories")).toBeVisible();

    // Breadcrumb should show full path
    const breadcrumb = page.getByTestId("workspace-breadcrumb");
    await expect(breadcrumb).toContainText("Discovery");
    await expect(breadcrumb).toContainText("SROGs");

    // Discovery breadcrumb segment should be a clickable link back to hub
    const discoveryLink = breadcrumb.getByRole("link", { name: "Discovery", exact: true });
    await expect(discoveryLink).toBeVisible();
    await discoveryLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/discovery`);
    await expect(page.getByTestId("discovery-hub")).toBeVisible();
  });
});
