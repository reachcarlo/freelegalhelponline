import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace State Preservation E2E Tests (V2.3b.2)
 *
 * Tests that switching between Files, Chat, and Info views does not
 * lose in-progress state. State is preserved via WorkspaceContext
 * (React context with ref-based store at the layout level).
 *
 * All API calls are mocked via route interception.
 */

const CASE_ID = "ws-state-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "State Preservation Case",
  description: null,
  status: "active",
  file_count: 2,
  created_at: "2026-03-20T00:00:00",
  updated_at: "2026-03-20T00:00:00",
};

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "State Preservation Case",
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
    id: "file-alpha",
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
  {
    id: "file-beta",
    case_id: CASE_ID,
    original_filename: "contract.docx",
    file_type: "docx",
    mime_type:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    file_size_bytes: 15000,
    upload_order: 2,
    processing_status: "ready",
    error_message: null,
    ocr_confidence: null,
    page_count: 5,
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

  await page.route(`**/api/cases/${CASE_ID}/files/*/detail`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "file-alpha",
        case_id: CASE_ID,
        original_filename: "complaint.pdf",
        extracted_text: "Sample extracted text for complaint.",
        edited_text: null,
        file_type: "pdf",
        processing_status: "ready",
        metadata: null,
      }),
    })
  );

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

test.describe("Workspace State Preservation (V2.3b.2)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("files view preserves selected file after navigating away and back", async ({
    page,
  }) => {
    // Use wide viewport for sidebar
    await page.setViewportSize({ width: 1280, height: 800 });

    // Navigate to files view
    await page.goto(`/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Select the second file
    await page.getByRole("option").filter({ hasText: "contract.docx" }).getByRole("button").click();

    // Verify it's selected
    await expect(
      page.getByRole("option").filter({ hasText: "contract.docx" })
    ).toHaveAttribute("aria-selected", "true");

    // Navigate to Chat
    const chatLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Chat" });
    await chatLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Navigate back to Files
    const filesLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Files" });
    await filesLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/files`);

    // The second file should still be selected
    await expect(
      page.getByRole("option").filter({ hasText: "contract.docx" })
    ).toHaveAttribute("aria-selected", "true");
  });

  test("chat view preserves draft input after navigating away and back", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    // Navigate to Chat
    await page.goto(`/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Type a draft message
    const input = page.getByPlaceholder("Ask about this case...");
    await expect(input).toBeVisible();
    await input.fill("What are the key claims in this case?");

    // Navigate to Info
    const infoLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Info" });
    await infoLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/info`);
    await expect(page.getByTestId("case-info-panel")).toBeVisible();

    // Navigate back to Chat
    const chatLink = page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Chat" });
    await chatLink.click();
    await page.waitForURL(`**/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Draft input should be preserved
    const restoredInput = page.getByPlaceholder("Ask about this case...");
    await expect(restoredInput).toHaveValue(
      "What are the key claims in this case?"
    );
  });

  test("full round-trip: Files → Chat → Info → Files preserves all state", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    // 1. Start at Files, select a file
    await page.goto(`/cases/${CASE_ID}/files`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await page.getByRole("option").filter({ hasText: "contract.docx" }).getByRole("button").click();

    // 2. Go to Chat, type a draft
    await page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Chat" })
      .click();
    await page.waitForURL(`**/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();
    const chatInput = page.getByPlaceholder("Ask about this case...");
    await chatInput.fill("Draft question about discovery");

    // 3. Go to Info
    await page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Info" })
      .click();
    await page.waitForURL(`**/cases/${CASE_ID}/info`);
    await expect(page.getByTestId("case-info-panel")).toBeVisible();

    // 4. Go back to Files — file selection preserved
    await page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Files" })
      .click();
    await page.waitForURL(`**/cases/${CASE_ID}/files`);
    await expect(
      page.getByRole("option").filter({ hasText: "contract.docx" })
    ).toHaveAttribute("aria-selected", "true");

    // 5. Go back to Chat — draft preserved
    await page
      .getByTestId("workspace-sidebar")
      .getByRole("link", { name: "Chat" })
      .click();
    await page.waitForURL(`**/cases/${CASE_ID}/chat`);
    const restoredChatInput = page.getByPlaceholder("Ask about this case...");
    await expect(restoredChatInput).toHaveValue(
      "Draft question about discovery"
    );
  });
});
