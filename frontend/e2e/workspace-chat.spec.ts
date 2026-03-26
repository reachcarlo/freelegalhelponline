import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace Chat E2E Tests (V2.6.1)
 *
 * Verifies that `/cases/[caseId]/chat` renders the chat interface at full
 * canvas width (not 450px drawer overlay) inside the workspace shell,
 * and that chat functionality works in this full-panel mode.
 */

const CASE_ID = "ws-chat-case-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Workspace Chat Test",
  description: null,
  status: "active",
  file_count: 1,
  created_at: "2026-03-20T00:00:00",
  updated_at: "2026-03-20T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-1",
    case_id: CASE_ID,
    original_filename: "complaint.pdf",
    file_type: "pdf",
    mime_type: "application/pdf",
    file_size_bytes: 50000,
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

function makeChatSSE(
  text: string,
  sessionId: string,
  opts?: {
    caseSources?: { title: string; file_id: string }[];
    kbSources?: { title: string }[];
  }
): string {
  const caseSources = (opts?.caseSources || []).map((s) => ({
    source_type: "case_file",
    title: s.title,
    relevance_score: 0.92,
    file_id: s.file_id,
    chunk_id: "chunk-1",
    heading_path: null,
  }));
  const kbSources = (opts?.kbSources || []).map((s) => ({
    source_type: "knowledge_base",
    title: s.title,
    relevance_score: 0.85,
    chunk_id: "kb-chunk-1",
    content_category: "STATUTE",
    heading_path: s.title,
  }));

  let sse = "";
  sse += `event: sources\ndata: ${JSON.stringify({ case_sources: caseSources, kb_sources: kbSources })}\n\n`;
  for (const word of text.split(" ")) {
    sse += `event: token\ndata: ${JSON.stringify({ text: word + " " })}\n\n`;
  }
  sse += `event: done\ndata: ${JSON.stringify({
    query_id: "q-1",
    session_id: sessionId,
    turn_number: 1,
    max_turns: 10,
    is_final_turn: false,
    model: "claude-haiku-4.5-20251001",
    input_tokens: 500,
    output_tokens: 100,
    cost_estimate: 0.003,
    duration_ms: 1200,
  })}\n\n`;
  return sse;
}

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
        case_name: MOCK_CASE.name,
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
        body: JSON.stringify(MOCK_FILES),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/cases/${CASE_ID}/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );

  await page.route(`**/api/cases/${CASE_ID}/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
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

test.describe("Workspace Chat — Full Canvas (V2.6.1)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("chat renders full-width inside workspace shell, not as 450px drawer", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`/cases/${CASE_ID}/chat`);

    // Workspace shell wraps the page
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // ChatPanel (not ChatDrawer) should render
    const chatPanel = page.getByTestId("chat-panel");
    await expect(chatPanel).toBeVisible();

    // ChatPanel should NOT be a fixed overlay — it flows within the workspace canvas
    const position = await chatPanel.evaluate(
      (el) => window.getComputedStyle(el).position
    );
    expect(position).not.toBe("fixed");

    // ChatPanel width should be significantly wider than the 450px drawer
    const box = await chatPanel.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(600);

    // Chat sidebar link should show active state
    const sidebar = page.getByTestId("workspace-sidebar");
    const chatLink = sidebar.getByRole("link", { name: "Chat" });
    await expect(chatLink).toHaveAttribute("aria-current", "page");

    // Input + suggestions should render within the panel
    await expect(
      page.getByPlaceholder("Ask about this case...")
    ).toBeVisible();
    await expect(
      page.getByText("Ask questions about your case files")
    ).toBeVisible();
  });

  test("chat accepts messages and streams responses in full-panel mode", async ({
    page,
  }) => {
    const sessionId = "sess-ws-chat";

    await page.route(`**/api/cases/${CASE_ID}/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE(
            "The complaint alleges wrongful termination under FEHA.",
            sessionId,
            {
              caseSources: [
                { title: "complaint.pdf", file_id: "file-1" },
              ],
              kbSources: [
                { title: "Gov. Code § 12940" },
              ],
            }
          ),
        });
      }
      return route.continue();
    });

    await page.goto(`/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Send a message
    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("What does the complaint allege?");
    await page.getByTitle("Send message").click();

    // User message should appear
    await expect(
      page.getByText("What does the complaint allege?")
    ).toBeVisible();

    // Streamed response should appear
    await expect(
      page.getByText(/wrongful termination under FEHA/)
    ).toBeVisible({ timeout: 10_000 });

    // Source badges should render
    await expect(page.getByText("complaint.pdf")).toBeVisible();
    await expect(page.getByText(/Gov\. Code/)).toBeVisible();

    // Suggestions should be gone after first message
    await expect(
      page.getByText("Ask questions about your case files")
    ).not.toBeVisible();
  });

  test("case file source badge navigates to Files view via workspace routing (V2.6.3)", async ({
    page,
  }) => {
    const sessionId = "sess-nav-test";

    await page.route(`**/api/cases/${CASE_ID}/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE("Here is the analysis.", sessionId, {
            caseSources: [
              { title: "complaint.pdf", file_id: "file-1" },
            ],
          }),
        });
      }
      return route.continue();
    });

    await page.goto(`/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Send a message to trigger source badges
    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("Summarize the complaint");
    await page.getByTitle("Send message").click();

    // Wait for response and source badge
    await expect(
      page.getByText(/Here is the analysis/)
    ).toBeVisible({ timeout: 10_000 });

    // Source badge should be a clickable button with navigation title
    const badge = page.getByTestId("citation-link-file-1");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveAttribute("title", "Go to complaint.pdf");

    // Click the badge — should navigate to /cases/[caseId]/files
    await badge.click();
    await page.waitForURL(`**/cases/${CASE_ID}/files`);

    // Verify we landed on the files view within the workspace shell
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByTestId("workspace-sidebar")).toBeVisible();
  });

  test("suggested questions reference specific claims from CaseContext (V2.6.4)", async ({
    page,
  }) => {
    // Override context endpoint with claims data
    await page.route(`**/api/cases/${CASE_ID}/context`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          case_id: CASE_ID,
          case_name: MOCK_CASE.name,
          parties: [],
          court: null,
          attorneys: [],
          employment_history: [],
          claims: [
            { claim_type: "feha_discrimination", status: "active", protected_class: "race", supporting_facts: null, reason: null },
            { claim_type: "wrongful_termination", status: "active", protected_class: null, supporting_facts: null, reason: null },
          ],
          key_dates: [],
          financials: [],
          fact_count: 5,
          confirmed_count: 2,
          extraction_sources: {},
        }),
      })
    );

    await page.goto(`/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Should see claim-specific suggestion
    await expect(
      page.getByText(/feha discrimination claim/)
    ).toBeVisible({ timeout: 5_000 });

    // Should see multi-claim prioritization suggestion
    await expect(
      page.getByText(/2 active claims/)
    ).toBeVisible();
  });

  test("suggested questions include timeline when employment history exists (V2.6.4)", async ({
    page,
  }) => {
    // Override context endpoint with employment history
    await page.route(`**/api/cases/${CASE_ID}/context`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          case_id: CASE_ID,
          case_name: MOCK_CASE.name,
          parties: [],
          court: null,
          attorneys: [],
          employment_history: [
            { employer: "Acme Corp", position: "Manager", start_date: "2020-03-01", end_date: "2025-12-15", department: null, compensation_rate: null, compensation_type: null, pay_period: null, change_reason: null },
          ],
          claims: [],
          key_dates: [
            { label: "Complaint filed", date: "2026-01-15" },
          ],
          financials: [],
          fact_count: 3,
          confirmed_count: 1,
          extraction_sources: {},
        }),
      })
    );

    await page.goto(`/cases/${CASE_ID}/chat`);
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Should see timeline suggestion from employment history
    await expect(
      page.getByText(/timeline of key employment events/)
    ).toBeVisible({ timeout: 5_000 });

    // Should see deadlines suggestion from key dates
    await expect(
      page.getByText(/deadlines or statute of limitations/)
    ).toBeVisible();
  });
});
