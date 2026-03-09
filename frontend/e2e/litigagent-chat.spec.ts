import { test, expect, Page, Route } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * LITIGAGENT Chat Drawer E2E Tests (Phase L3.7 + L3.8 + L3.9 + L3.10)
 *
 * Tests the chat drawer UI: open/close, send messages, SSE streaming,
 * source display, multi-turn conversation, error handling.
 * L3.8: Clickable file citations navigate to Panel 2.
 * L3.9: Contextual suggested questions based on case files.
 * L3.10: Chat session persistence (history panel, switch, delete).
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

  test("shows contextual suggestion buttons based on case files", async ({ page }) => {
    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    await expect(page.getByText("Suggested questions")).toBeVisible();
    // complaint.pdf triggers complaint-specific suggestion
    await expect(
      page.getByText("Analyze the complaint and identify all causes of action")
    ).toBeVisible();
    // General questions fill remaining slots
    await expect(
      page.getByText("Create a timeline of key events from these documents")
    ).toBeVisible();
    await expect(
      page.getByText("What potential employment law claims")
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
            "The complaint alleges three causes of action.",
            "sess-suggest",
            1
          ),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Click the complaint-specific suggestion
    await page.getByText("Analyze the complaint and identify all causes of action").click();

    // User message from suggestion should appear
    await expect(
      page.getByText("Analyze the complaint and identify all causes of action")
    ).toBeVisible();

    // Response should stream
    await expect(
      page.getByText(/three causes of action/)
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

  test("clicking a case file citation closes chat and navigates to file in Panel 2", async ({
    page,
  }) => {
    const sessionId = "sess-citation";

    // Mock file detail endpoints so text panel can load content
    await page.route(`**/api/cases/chat-test-case-id/files/file-1`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...MOCK_FILES[0],
            extracted_text: "This is the complaint text content.",
            edited_text: null,
          }),
        });
      }
      return route.continue();
    });

    await page.route(`**/api/cases/chat-test-case-id/files/file-2`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...MOCK_FILES[1],
            extracted_text: "This is the evidence document content.",
            edited_text: null,
          }),
        });
      }
      return route.continue();
    });

    // Mock the chat endpoint with case file sources
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE(
            "The complaint alleges wrongful termination.",
            sessionId,
            1,
            {
              caseSources: [
                { title: "complaint.pdf", file_id: "file-1" },
                { title: "evidence.docx", file_id: "file-2" },
              ],
            }
          ),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await expect(page.getByText("Chat Test Case")).toBeVisible();

    // Wait for file text to load in Panel 2
    await expect(
      page.getByText("This is the complaint text content.")
    ).toBeVisible({ timeout: 10_000 });

    // Open chat and send a message
    await page.getByRole("button", { name: /chat/i }).first().click();
    const chatHeading = page.getByRole("heading", { name: "Chat with Case" });
    await expect(chatHeading).toBeVisible();

    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("Tell me about the complaint");
    await page.getByTitle("Send message").click();

    // Wait for response to finish streaming
    await expect(
      page.getByText(/wrongful termination/)
    ).toBeVisible({ timeout: 10_000 });

    // Case file source badges should be clickable buttons
    const citationButton = page.getByTestId("citation-link-file-1");
    await expect(citationButton).toBeVisible();
    await expect(citationButton).toHaveText(/complaint\.pdf/);

    // Click the citation — should close chat and navigate to file
    await citationButton.click();

    // Chat drawer should transition to closed state
    const drawer = page.getByTestId("chat-drawer");
    await expect(drawer).toHaveAttribute("data-state", "closed");

    // The file section in Panel 2 should be visible (scrolled into view)
    const fileSection = page.locator("#file-file-1");
    await expect(fileSection).toBeVisible();
  });

  test("citation badge has correct hover title", async ({ page }) => {
    await page.route(`**/api/cases/chat-test-case-id/chat`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: makeChatSSE(
            "Response with sources.",
            "sess-hover",
            1,
            {
              caseSources: [
                { title: "complaint.pdf", file_id: "file-1" },
              ],
            }
          ),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    const input = page.getByPlaceholder("Ask about this case...");
    await input.fill("question");
    await page.getByTitle("Send message").click();

    await expect(page.getByText("Response with sources.")).toBeVisible({ timeout: 10_000 });

    // Citation should have a "Go to" title
    const citation = page.getByTestId("citation-link-file-1");
    await expect(citation).toHaveAttribute("title", "Go to complaint.pdf");
  });

  test("shows upload suggestions when no files exist", async ({ page }) => {
    // Override files mock to return empty list
    await page.route(`**/api/cases/chat-test-case-id/files`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    await expect(page.getByText("Suggested questions")).toBeVisible();
    await expect(
      page.getByText("What types of documents should I upload for my case?")
    ).toBeVisible();
    await expect(
      page.getByText("What employment claims might apply to my situation?")
    ).toBeVisible();
  });

  test("shows email-specific suggestions for email files", async ({ page }) => {
    // Override files mock with email files
    await page.route(`**/api/cases/chat-test-case-id/files`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "file-email",
              case_id: "chat-test-case-id",
              original_filename: "hr-correspondence.eml",
              file_type: "eml",
              mime_type: "message/rfc822",
              file_size_bytes: 15000,
              upload_order: 1,
              processing_status: "ready",
              error_message: null,
              ocr_confidence: null,
              page_count: null,
              metadata: null,
              text_dirty: false,
              created_at: "2026-03-07T00:00:00",
              updated_at: "2026-03-07T00:00:00",
            },
            {
              id: "file-pay",
              case_id: "chat-test-case-id",
              original_filename: "paystubs-2025.xlsx",
              file_type: "xlsx",
              mime_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
              file_size_bytes: 80000,
              upload_order: 2,
              processing_status: "ready",
              error_message: null,
              ocr_confidence: null,
              page_count: null,
              metadata: null,
              text_dirty: false,
              created_at: "2026-03-07T00:00:00",
              updated_at: "2026-03-07T00:00:00",
            },
          ]),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    await expect(page.getByText("Suggested questions")).toBeVisible();
    // Pay record filename triggers pay-specific suggestion
    await expect(
      page.getByText("Analyze the pay records for wage and hour violations")
    ).toBeVisible();
    // Email file type triggers email-specific suggestion
    await expect(
      page.getByText("Summarize key email communications")
    ).toBeVisible();
  });

  test("suggestions update when files change", async ({ page }) => {
    // Start with empty files
    let filesList: typeof MOCK_FILES = [];
    await page.route(`**/api/cases/chat-test-case-id/files`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(filesList),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Should show upload suggestions initially
    await expect(
      page.getByText("What types of documents should I upload for my case?")
    ).toBeVisible();

    // Close chat, update files, re-open
    await page.getByTitle("Close chat").click();

    // Update the route to return files now
    filesList = [...MOCK_FILES];
    await page.route(`**/api/cases/chat-test-case-id/files`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(filesList),
        });
      }
      return route.continue();
    });
    // Trigger reload by navigating
    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Should now show contextual suggestions for complaint.pdf
    await expect(
      page.getByText("Analyze the complaint and identify all causes of action")
    ).toBeVisible({ timeout: 10_000 });
  });

  test("history button toggles session list panel", async ({ page }) => {
    // Mock sessions list with two sessions
    await page.route(`**/api/cases/chat-test-case-id/chat/sessions`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          sessions: [
            {
              id: "sess-1",
              case_id: "chat-test-case-id",
              created_at: "2026-03-07T10:00:00",
              updated_at: "2026-03-07T10:05:00",
              turn_count: 4,
            },
            {
              id: "sess-2",
              case_id: "chat-test-case-id",
              created_at: "2026-03-06T08:00:00",
              updated_at: "2026-03-06T08:10:00",
              turn_count: 2,
            },
          ],
        }),
      })
    );

    // Mock history for both sessions (for preview loading)
    await page.route(
      `**/api/cases/chat-test-case-id/chat/sess-1`,
      (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "sess-1",
            case_id: "chat-test-case-id",
            turns: [
              { id: "t1", session_id: "sess-1", turn_number: 1, role: "user", content: "What are the key claims?", sources: null, created_at: "2026-03-07T10:00:01" },
              { id: "t2", session_id: "sess-1", turn_number: 1, role: "assistant", content: "The complaint alleges...", sources: null, created_at: "2026-03-07T10:00:10" },
            ],
          }),
        })
    );

    await page.route(
      `**/api/cases/chat-test-case-id/chat/sess-2`,
      (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "sess-2",
            case_id: "chat-test-case-id",
            turns: [
              { id: "t3", session_id: "sess-2", turn_number: 1, role: "user", content: "Summarize the evidence", sources: null, created_at: "2026-03-06T08:00:01" },
              { id: "t4", session_id: "sess-2", turn_number: 1, role: "assistant", content: "The evidence shows...", sources: null, created_at: "2026-03-06T08:00:10" },
            ],
          }),
        })
    );

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // History panel should not be visible initially
    await expect(page.getByTestId("session-history-panel")).not.toBeVisible();

    // Click history toggle
    await page.getByTestId("chat-history-toggle").click();

    // History panel should appear
    await expect(page.getByTestId("session-history-panel")).toBeVisible();
    await expect(page.getByText("Previous conversations")).toBeVisible();

    // Session previews should load
    await expect(page.getByText("What are the key claims?")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Summarize the evidence")).toBeVisible();

    // Turn counts visible
    await expect(page.getByText(/4 turns/)).toBeVisible();
    await expect(page.getByText(/2 turns/)).toBeVisible();

    // Click toggle again to close
    await page.getByTestId("chat-history-toggle").click();
    await expect(page.getByTestId("session-history-panel")).not.toBeVisible();
  });

  test("switching sessions loads conversation history", async ({ page }) => {
    // Mock sessions
    await page.route(`**/api/cases/chat-test-case-id/chat/sessions`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          sessions: [
            {
              id: "sess-a",
              case_id: "chat-test-case-id",
              created_at: "2026-03-07T10:00:00",
              updated_at: "2026-03-07T10:05:00",
              turn_count: 2,
            },
          ],
        }),
      })
    );

    // Mock session history
    await page.route(
      `**/api/cases/chat-test-case-id/chat/sess-a`,
      (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "sess-a",
            case_id: "chat-test-case-id",
            turns: [
              { id: "t1", session_id: "sess-a", turn_number: 1, role: "user", content: "Explain the timeline", sources: null, created_at: "2026-03-07T10:00:01" },
              { id: "t2", session_id: "sess-a", turn_number: 1, role: "assistant", content: "The timeline shows three key events.", sources: null, created_at: "2026-03-07T10:00:10" },
            ],
          }),
        })
    );

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Should start with suggestions (no messages)
    await expect(page.getByText("Suggested questions")).toBeVisible();

    // Open history and click session
    await page.getByTestId("chat-history-toggle").click();
    await expect(page.getByText("Explain the timeline")).toBeVisible({ timeout: 10_000 });

    // Click to switch to that session
    await page.getByTestId("session-item-sess-a").locator("button").first().click();

    // History panel should close, messages should be loaded
    await expect(page.getByTestId("session-history-panel")).not.toBeVisible();
    await expect(page.getByText("Explain the timeline")).toBeVisible();
    await expect(page.getByText("The timeline shows three key events.")).toBeVisible();

    // Suggestions should be gone
    await expect(page.getByText("Suggested questions")).not.toBeVisible();
  });

  test("deleting a session removes it from the list", async ({ page }) => {
    await page.route(`**/api/cases/chat-test-case-id/chat/sessions`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          sessions: [
            {
              id: "sess-del",
              case_id: "chat-test-case-id",
              created_at: "2026-03-07T10:00:00",
              updated_at: "2026-03-07T10:05:00",
              turn_count: 1,
            },
          ],
        }),
      })
    );

    await page.route(
      `**/api/cases/chat-test-case-id/chat/sess-del`,
      (route) => {
        if (route.request().method() === "DELETE") {
          return route.fulfill({ status: 204 });
        }
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "sess-del",
            case_id: "chat-test-case-id",
            turns: [
              { id: "t1", session_id: "sess-del", turn_number: 1, role: "user", content: "Delete me", sources: null, created_at: "2026-03-07T10:00:01" },
            ],
          }),
        });
      }
    );

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Open history
    await page.getByTestId("chat-history-toggle").click();
    await expect(page.getByText("Delete me")).toBeVisible({ timeout: 10_000 });

    // Delete the session
    await page.getByTestId("delete-session-sess-del").click({ force: true });

    // Session should be removed, show empty state
    await expect(page.getByText("No previous conversations")).toBeVisible();
  });

  test("deleting current session resets chat to empty state", async ({ page }) => {
    // Start with a restored session
    await page.route(`**/api/cases/chat-test-case-id/chat/sessions`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          sessions: [
            {
              id: "sess-current",
              case_id: "chat-test-case-id",
              created_at: "2026-03-07T12:00:00",
              updated_at: "2026-03-07T12:05:00",
              turn_count: 2,
            },
          ],
        }),
      })
    );

    await page.route(
      `**/api/cases/chat-test-case-id/chat/sess-current`,
      (route) => {
        if (route.request().method() === "DELETE") {
          return route.fulfill({ status: 204 });
        }
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session_id: "sess-current",
            case_id: "chat-test-case-id",
            turns: [
              { id: "t1", session_id: "sess-current", turn_number: 1, role: "user", content: "Active question", sources: null, created_at: "2026-03-07T12:00:01" },
              { id: "t2", session_id: "sess-current", turn_number: 1, role: "assistant", content: "Active answer", sources: null, created_at: "2026-03-07T12:00:10" },
            ],
          }),
        });
      }
    );

    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Session auto-restores
    await expect(page.getByText("Active question")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Active answer")).toBeVisible();

    // Open history and delete current session
    await page.getByTestId("chat-history-toggle").click();
    await expect(page.getByText("(current)")).toBeVisible();
    await page.getByTestId("delete-session-sess-current").click({ force: true });

    // Messages should be cleared, suggestions should reappear
    await expect(page.getByText("Active question")).not.toBeVisible();
    await expect(page.getByText("Suggested questions")).toBeVisible();
  });

  test("shows empty state when no previous sessions exist", async ({ page }) => {
    await page.goto("/tools/litigagent/chat-test-case-id");
    await page.getByRole("button", { name: /chat/i }).first().click();

    // Open history — default mock returns empty sessions
    await page.getByTestId("chat-history-toggle").click();
    await expect(page.getByText("No previous conversations")).toBeVisible();
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
