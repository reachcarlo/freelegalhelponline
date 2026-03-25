import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Discovery Hub Artifacts E2E Tests (V2.4.7)
 *
 * Tests that the discovery hub displays existing artifacts
 * and supports deletion.
 */

const CASE_ID = "ws-disc-artifacts-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Artifact Test Case",
  description: null,
  status: "active",
  file_count: 0,
  created_at: "2026-03-10T00:00:00",
  updated_at: "2026-03-10T00:00:00",
};

// Backend returns newest-first (ORDER BY created_at DESC)
const MOCK_ARTIFACTS = [
  {
    id: "art-2",
    case_id: CASE_ID,
    artifact_type: "discovery",
    tool_source: "rfpds",
    summary: "RFPDs generated (RFPDs_24STCV99999.docx)",
    file_path: null,
    metadata: { filename: "RFPDs_24STCV99999.docx" },
    created_at: "2026-03-12T09:15:00",
    created_by: null,
  },
  {
    id: "art-1",
    case_id: CASE_ID,
    artifact_type: "discovery",
    tool_source: "srogs",
    summary: "SROGs generated (SROGs_24STCV99999.docx)",
    file_path: null,
    metadata: { filename: "SROGs_24STCV99999.docx" },
    created_at: "2026-03-10T14:30:00",
    created_by: null,
  },
];

async function mockAPIs(page: Page, artifacts = MOCK_ARTIFACTS) {
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
        case_name: "Artifact Test Case",
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

  await page.route(`**/api/cases/${CASE_ID}/artifacts`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ artifacts }),
      });
    }
    return route.continue();
  });

  // Mock delete
  await page.route(`**/api/cases/${CASE_ID}/artifacts/*`, (route) => {
    if (route.request().method() === "DELETE") {
      return route.fulfill({ status: 204 });
    }
    return route.continue();
  });
}

test.describe("Discovery Hub Artifacts (V2.4.7)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("displays existing artifacts with tool labels and dates", async ({
    page,
  }) => {
    await mockAPIs(page);
    await page.goto(`/cases/${CASE_ID}/discovery`);

    // Artifacts section visible
    const section = page.getByTestId("artifacts-section");
    await expect(section).toBeVisible();
    await expect(section.getByText("Generated Documents")).toBeVisible();

    // Two artifact items
    const items = section.getByTestId("artifact-item");
    await expect(items).toHaveCount(2);

    // First artifact (rfpds — newest first from API)
    await expect(items.nth(0)).toContainText("RFPDs");
    await expect(items.nth(0)).toContainText("Mar 12");

    // Second artifact (srogs)
    await expect(items.nth(1)).toContainText("SROGs");
    await expect(items.nth(1)).toContainText("Mar 10");
  });

  test("delete removes artifact from list", async ({ page }) => {
    await mockAPIs(page);
    await page.goto(`/cases/${CASE_ID}/discovery`);

    const section = page.getByTestId("artifacts-section");
    await expect(section.getByTestId("artifact-item")).toHaveCount(2);

    // Delete the first artifact
    const deleteButtons = section.getByTestId("artifact-delete");
    await deleteButtons.nth(0).click();

    // Should now show 1 artifact
    await expect(section.getByTestId("artifact-item")).toHaveCount(1);
  });
});
