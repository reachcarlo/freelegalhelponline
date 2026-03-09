import { test, expect, Page, Route } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Chat Drawer E2E Tests (Phase L3.7)
 *
 * Tests the chat drawer UI: open/close, send messages, SSE streaming,
 * source display, multi-turn conversation, error handling.
 *
 * All chat API calls are mocked via route interception since the backend
 * requires a real LLM service.
 */

const MOCK_CASE = {
  id: "chat-test-case-id",
  name: "Chat Test Case",
  description: null,
  status: "active",
  file_count: 2,
  created_at: "2026-03-07T00:00:00",
  updated_at: "2026-03-07T00:00:00",
};

const MOCK_FILES = [
  {
    id: "file-1",
    case_id: "chat-test-case-id",
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
    created_at: "2026-03-07T00:00:00",
    updated_at: "2026-03-07T00:00:00",
  },
  {
    id: "file-2",
    case_id: "chat-test-case-id",
    original_filename: "evidence.docx",
    file_type: "docx",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    file_size_bytes: 25000,
    upload_order: 2,
    processing_status: "ready",
    error_message: null,
    ocr_confidence: null,
    page_count: 1,
    metadata: null,
    text_dirty: false,
    created_at: "2026-03-07T00:00:00",
    updated_at: "2026-03-07T00:00:00",
  },
];

function makeChatSSE(
  text: string,
  sessionId: string,
  turnNumber: number = 1,
  opts?: {
    caseSources?: { title: string; file_id: string }[];
    kbSources?: { title: string }[];
    isFinal?: boolean;
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

  // Stream text in small chunks
  const words = text.split(" ");
  for (const word of words) {
    sse += `event: token\ndata: ${JSON.stringify({ text: word + " " })}\n\n`;
  }

  sse += `event: done\ndata: ${JSON.stringify({
    query_id: "q-" + turnNumber,
    session_id: sessionId,
    turn_number: turnNumber,
    max_turns: 10,
    is_final_turn: opts?.isFinal || false,
    model: "claude-haiku-4.5-20251001",
    input_tokens: 500,
    output_tokens: 100,
    cost_estimate: 0.003,
    duration_ms: 1200,
  })}\n\n`;

  return sse;
}

async function setupCaseMocks(page: Page) {
  // Mock case API
  await page.route(`**/api/cases/chat-test-case-id`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_CASE),
      });
    }
    return route.continue();
  });

  // Mock files list
  await page.route(`**/api/cases/chat-test-case-id/files`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_FILES),
      });
    }
    return route.continue();
  });

  // Mock SSE status stream (empty, no processing files)
  await page.route(`**/api/cases/chat-test-case-id/status-stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "",
    })
  );

  // Mock chat sessions (empty by default)
  await page.route(`**/api/cases/chat-test-case-id/chat/sessions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [] }),
    })
  );

  // Mock notes
  await page.route(`**/api/cases/chat-test-case-id/notes*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ notes: [] }),
    })
  );
}

test.describe("LITIGAGENT Chat Drawer", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupCaseMocks(page);
  });

  test("chat button opens and closes the drawer", async ({ page }) => {
    await page.goto("/tools/litigagent/chat-test-case-id");
    await expect(page.getByText("Chat Test Case")).toBeVisible();

    // Chat drawer should be hidden initially
    const drawer = page.getByRole("heading", { name: "Chat with Case" });
    await expect(drawer).not.toBeVisible();

    // Click Chat button to open
    await page.getByRole("button", { name: /chat/i }).first().click();
    await expect(drawer).toBeVisible();

    // Click close button
    await page.getByTitle("Close chat").click();
    await expect(drawer).not.toBeVisible();
  });

  test("shows suggestion buttons when empty", async ({ page }) => {
    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    await expect(page.getByText("Suggested questions")).toBeVisible();
    await expect(
      page.getByText("Summarize all damages evidence")
    ).toBeVisible();
    await expect(
      page.getByText("Create a timeline of key events")
    ).toBeVisible();
    await expect(
      page.getByText("What witnesses are identified?")
    ).toBeVisible();
  });

  test("sends a message and streams the response", async ({ page }) => {
    const sessionId = "sess-test-1";

    // Mock the chat endpoint to return streaming SSE
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE(
            "Based on the complaint, the plaintiff alleges wrongful termination.",
            sessionId,
            1,
            {
              caseSources: [
                { title: "complaint.pdf", file_id: "file-1" },
              ],
              kbSources: [
                { title: "Labor Code \u00a7 1102.5" },
              ],
            }
          ),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Type and send
    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("What does the complaint allege?");
    await page.getByTitle("Send message").click();

    // User message should appear
    await expect(
      page.getByText("What does the complaint allege?")
    ).toBeVisible();

    // Assistant response should stream in
    await expect(
      page.getByText(/plaintiff alleges wrongful termination/)
    ).toBeVisible({ timeout: 10_000 });

    // Sources should appear
    await expect(page.getByText("complaint.pdf")).toBeVisible();
    await expect(page.getByText(/Labor Code/)).toBeVisible();

    // Suggestions should be gone
    await expect(page.getByText("Suggested questions")).not.toBeVisible();
  });

  test("suggestion button sends message directly", async ({ page }) => {
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE(
            "Here is a summary of the damages evidence found in your case files.",
            "sess-suggest",
            1
          ),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Click a suggestion
    await page.getByText("Summarize all damages evidence").click();

    // User message from suggestion should appear
    await expect(
      page.getByText("Summarize all damages evidence")
    ).toBeVisible();

    // Response should stream
    await expect(
      page.getByText(/summary of the damages evidence/)
    ).toBeVisible({ timeout: 10_000 });
  });

  test("multi-turn conversation sends history", async ({ page }) => {
    const sessionId = "sess-multi";
    let requestCount = 0;

    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        requestCount++;
        const body = JSON.parse(route.request().postData() || "{}");

        if (requestCount === 1) {
          // First turn — no history expected
          expect(body.conversation_history).toBeUndefined();
          return route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: makeChatSSE("First response.", sessionId, 1),
          });
        } else {
          // Second turn — history should include first turn
          expect(body.session_id).toBe(sessionId);
          expect(body.conversation_history).toHaveLength(2);
          expect(body.conversation_history[0].role).toBe("user");
          expect(body.conversation_history[1].role).toBe("assistant");
          return route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: makeChatSSE("Second response.", sessionId, 2),
          });
        }
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // First message
    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("First question");
    await page.getByTitle("Send message").click();
    await expect(page.getByText("First response.")).toBeVisible({
      timeout: 10_000,
    });

    // Second message (follow-up)
    await input.fill("Follow-up question");
    await page.getByTitle("Send message").click();
    await expect(page.getByText("Second response.")).toBeVisible({
      timeout: 10_000,
    });

    expect(requestCount).toBe(2);
  });

  test("handles error from API gracefully", async ({ page }) => {
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: `event: error\ndata: ${JSON.stringify({ message: "LLM service unavailable" })}\n\n`,
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("Will this fail?");
    await page.getByTitle("Send message").click();

    // Error banner should appear
    await expect(
      page.getByText("LLM service unavailable")
    ).toBeVisible({ timeout: 10_000 });

    // Dismiss error
    const errorBanner = page.locator(".bg-error-bg");
    await errorBanner.locator("button").click();
    await expect(
      page.getByText("LLM service unavailable")
    ).not.toBeVisible();
  });

  test("handles turn limit exceeded", async ({ page }) => {
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: `event: error\ndata: ${JSON.stringify({ message: "TURN_LIMIT_EXCEEDED", max_turns: 10 })}\n\n`,
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("One more question");
    await page.getByTitle("Send message").click();

    // Turn limit banner should appear
    await expect(
      page.getByText("Conversation limit reached")
    ).toBeVisible({ timeout: 10_000 });

    // "New conversation" link should be available
    await expect(
      page.getByRole("button", { name: "New conversation" })
    ).toBeVisible();
  });

  test("new conversation button resets state", async ({ page }) => {
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE("Some response.", "sess-reset", 1),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Send a message
    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("Test message");
    await page.getByTitle("Send message").click();
    await expect(page.getByText("Some response.")).toBeVisible({
      timeout: 10_000,
    });

    // Click "New conversation" in header
    await page.getByTitle("New conversation").click();

    // Suggestions should reappear (empty state)
    await expect(page.getByText("Suggested questions")).toBeVisible();

    // Previous messages should be gone
    await expect(page.getByText("Test message")).not.toBeVisible();
    await expect(page.getByText("Some response.")).not.toBeVisible();
  });

  test("restores previous session on drawer open", async ({ page }) => {
    // Mock sessions with a previous session
    await page.route(`**/api/cases/chat-test-case-id/chat/sessions`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          sessions: [
            {
              id: "sess-prev",
              case_id: "chat-test-case-id",
              created_at: "2026-03-07T12:00:00",
              updated_at: "2026-03-07T12:05:00",
              turn_count: 2,
            },
          ],
        }),
      })
    );

    // Mock session history
    await page.route(
      `**/api/cases/chat-test-case-id/chat/sess-prev`,
      (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "sess-prev",
            case_id: "chat-test-case-id",
            turns: [
              {
                id: "t1",
                session_id: "sess-prev",
                turn_number: 1,
                role: "user",
                content: "What are the key claims?",
                sources: null,
                created_at: "2026-03-07T12:00:01",
              },
              {
                id: "t2",
                session_id: "sess-prev",
                turn_number: 1,
                role: "assistant",
                content:
                  "The case involves claims of wrongful termination and FEHA discrimination.",
                sources: null,
                created_at: "2026-03-07T12:00:10",
              },
            ],
          }),
        })
    );

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Previous messages should be restored
    await expect(
      page.getByText("What are the key claims?")
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText(/wrongful termination and FEHA discrimination/)
    ).toBeVisible();

    // Suggestions should NOT show (has messages)
    await expect(page.getByText("Suggested questions")).not.toBeVisible();
  });

  test("enter key sends message, shift+enter adds newline", async ({
    page,
  }) => {
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE("Response.", "sess-key", 1),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    const input = page.getByPlaceholder("Ask about this case...");

    // Shift+Enter should add newline, not send
    await input.fill("Line 1");
    await input.press("Shift+Enter");
    await input.type("Line 2");

    // Message should not have been sent
    await expect(page.getByText("Line 1")).not.toBeVisible();

    // Enter should send
    await input.press("Enter");
    await expect(page.getByText("Response.")).toBeVisible({
      timeout: 10_000,
    });
  });
});
