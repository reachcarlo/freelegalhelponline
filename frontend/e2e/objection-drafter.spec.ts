import { test, expect } from "@playwright/test";

/**
 * Mock API responses for the objection drafter wizard.
 * These intercept fetch calls to avoid hitting the real backend.
 */

const MOCK_PARSE_RESPONSE = {
  requests: [
    {
      id: "parsed-1",
      request_number: 1,
      request_text:
        "State all facts supporting your contention that Defendant discriminated against you on the basis of race.",
      discovery_type: "interrogatories",
      is_selected: true,
    },
    {
      id: "parsed-2",
      request_number: 2,
      request_text:
        "Identify all documents that support your claims of wrongful termination.",
      discovery_type: "interrogatories",
      is_selected: true,
    },
    {
      id: "parsed-3",
      request_number: 3,
      request_text: "State your total income for the past five years.",
      discovery_type: "interrogatories",
      is_selected: true,
    },
  ],
  skipped_sections: [
    {
      section_type: "definitions",
      content: 'As used herein, "DOCUMENT" means...',
      defined_terms: ["DOCUMENT", "INCIDENT"],
    },
    {
      section_type: "instructions",
      content: "In answering these interrogatories...",
      defined_terms: [],
    },
  ],
  metadata: {
    propounding_party: "Henderson",
    responding_party: "Acme Corp",
    set_number: 1,
    case_name: "Henderson v. Acme Corp",
  },
  detected_type: "interrogatories",
  is_response_shell: false,
  warnings: [],
};

const MOCK_GENERATE_RESPONSE = {
  results: [
    {
      request_number: 1,
      request_text:
        "State all facts supporting your contention that Defendant discriminated against you on the basis of race.",
      discovery_type: "interrogatories",
      objections: [
        {
          ground_id: "overbroad",
          label: "Overbroad",
          category: "form",
          explanation:
            'This request seeks "all facts" without reasonable limitation as to time period or scope.',
          strength: "high",
          statutory_citations: [
            { code: "CCP", section: "§2030.060(f)", description: "Scope" },
          ],
          case_citations: [
            {
              name: "Calcor Space Facility, Inc. v. Superior Court",
              year: 1997,
              citation: "(1997) 53 Cal.App.4th 216",
              reporter_key: "53 Cal.App.4th 216",
            },
          ],
          citation_warnings: [],
        },
        {
          ground_id: "relevance",
          label: "Relevance",
          category: "substantive",
          explanation:
            "To the extent this interrogatory seeks information beyond the specific claims in this action.",
          strength: "medium",
          statutory_citations: [
            { code: "CCP", section: "§2017.010", description: "Scope" },
          ],
          case_citations: [
            {
              name: "Emerson Electric Co. v. Superior Court",
              year: 1997,
              citation: "(1997) 16 Cal.4th 1101, 1108",
              reporter_key: "16 Cal.4th 1101",
            },
          ],
          citation_warnings: [],
        },
      ],
      no_objections_rationale: null,
      formatted_output:
        'Objection: Overbroad: This request seeks "all facts" without reasonable limitation. (CCP §2030.060(f); Calcor Space Facility, Inc. v. Superior Court (1997) 53 Cal.App.4th 216); Objection: Relevance: To the extent this interrogatory seeks information beyond the specific claims in this action. (CCP §2017.010; Emerson Electric Co. v. Superior Court (1997) 16 Cal.4th 1101, 1108)',
    },
    {
      request_number: 2,
      request_text:
        "Identify all documents that support your claims of wrongful termination.",
      discovery_type: "interrogatories",
      objections: [
        {
          ground_id: "overbroad",
          label: "Overbroad",
          category: "form",
          explanation:
            'Seeks "all documents" without limitation as to time or category.',
          strength: "medium",
          statutory_citations: [
            { code: "CCP", section: "§2030.060(f)", description: "Scope" },
          ],
          case_citations: [],
          citation_warnings: [],
        },
      ],
      no_objections_rationale: null,
      formatted_output: "Objection: Overbroad: ...",
    },
    {
      request_number: 3,
      request_text: "State your total income for the past five years.",
      discovery_type: "interrogatories",
      objections: [],
      no_objections_rationale:
        "This request is proper and seeks relevant financial information.",
      formatted_output: "",
    },
  ],
  formatted_text: "INTERROGATORY NO. 1:\n...",
  model_used: "claude-haiku-4-5-20251001",
  input_tokens: 3500,
  output_tokens: 800,
  cost_estimate: 0.0042,
  duration_ms: 3200,
  warnings: [],
  disclaimer:
    "This tool provides draft objections for attorney review. All objections must be reviewed by a licensed attorney before service. Meritless objections may result in sanctions under CCP §2023.010(e) and §2023.050.",
};

const SAMPLE_SROG_TEXT = `PROPOUNDING PARTY: Henderson
RESPONDING PARTY: Acme Corp

DEFINITIONS

As used herein, "DOCUMENT" means any written or recorded material.

INSTRUCTIONS

In answering these interrogatories, provide complete and accurate responses.

SPECIAL INTERROGATORY NO. 1:
State all facts supporting your contention that Defendant discriminated against you on the basis of race.

SPECIAL INTERROGATORY NO. 2:
Identify all documents that support your claims of wrongful termination.

SPECIAL INTERROGATORY NO. 3:
State your total income for the past five years.`;

test.describe("Objection Drafter", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tools/discovery/objection-drafter");
  });

  // ── Step 1: Setup ───────────────────────────────────────────────

  test("shows Setup step on initial load", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Objection Drafter Setup" })
    ).toBeVisible();
    await expect(page.getByText("1 / 4")).toBeVisible();
  });

  test("shows discovery type controls", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Auto-detect" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Interrogatories" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Requests for Production" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Requests for Admission" })
    ).toBeVisible();
  });

  test("shows verbosity controls", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Short" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Medium" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Long" })).toBeVisible();
  });

  test("shows party role controls", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Plaintiff" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Defendant" })
    ).toBeVisible();
  });

  test("shows waiver language toggle", async ({ page }) => {
    // The switch button has role="switch" with aria-checked
    await expect(page.getByRole("switch")).toBeVisible();
    // And the label text is nearby
    await expect(
      page.getByText(/^.Subject to and without waiving.+ preamble$/)
    ).toBeVisible();
  });

  test("can select discovery type", async ({ page }) => {
    const btn = page.getByRole("button", { name: "Interrogatories" });
    await btn.click();
    await expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  test("can select verbosity", async ({ page }) => {
    const btn = page.getByRole("button", { name: "Long" });
    await btn.click();
    await expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  test("can toggle party role", async ({ page }) => {
    const plaintiff = page.getByRole("button", { name: "Plaintiff" });
    await plaintiff.click();
    await expect(plaintiff).toHaveAttribute("aria-pressed", "true");
  });

  test("Next button advances to Input step", async ({ page }) => {
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: /Upload or Paste Discovery Requests/i })
    ).toBeVisible();
    await expect(page.getByText("2 / 4")).toBeVisible();
  });

  // ── Step 2: Input ────────────────────────────────────────────────

  test("Input step has textarea", async ({ page }) => {
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(
      page.getByLabel("Discovery request text")
    ).toBeVisible();
  });

  test("Parse button appears when text entered", async ({ page }) => {
    await page.getByRole("button", { name: "Next", exact: true }).click();

    // Type text into textarea
    await page.getByLabel("Discovery request text").fill("SPECIAL INTERROGATORY NO. 1: State all facts.");

    // Parse button should be visible (both inline and in footer)
    await expect(
      page.getByRole("button", { name: "Parse Requests" }).first()
    ).toBeVisible();
  });

  test("shows character count", async ({ page }) => {
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page
      .getByLabel("Discovery request text")
      .fill("Some test text here");
    await expect(page.getByText("19 characters")).toBeVisible();
  });

  // ── Step 3: Review (Parse Preview) ───────────────────────────────

  test("Parse submits to API and shows review step", async ({ page }) => {
    // Mock parse endpoint
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });

    // Navigate to Input step
    await page.getByRole("button", { name: "Next", exact: true }).click();

    // Fill text
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);

    // Click Parse
    await page.getByRole("button", { name: "Parse Requests" }).first().click();

    // Should advance to Review step (step 3)
    await expect(page.getByText("3 / 4")).toBeVisible();

    // Should show parsed requests
    await expect(page.getByText("3 requests found")).toBeVisible();

    // Should show request text
    await expect(
      page.getByText("State all facts supporting your contention")
    ).toBeVisible();
  });

  test("shows skipped sections info", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();

    // Should show skipped sections count
    await expect(page.getByText(/skipped/i)).toBeVisible();
  });

  test("can toggle request selection", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();

    // Find a checkbox and toggle it
    const checkboxes = page.getByRole("checkbox");
    const firstCheckbox = checkboxes.first();
    await expect(firstCheckbox).toBeVisible();
    await expect(firstCheckbox).toBeChecked();
    await firstCheckbox.uncheck();
    await expect(firstCheckbox).not.toBeChecked();
  });

  // ── Step 4: Results (Generate) ───────────────────────────────────

  test("Generate button triggers LLM and shows results", async ({ page }) => {
    // Mock both endpoints
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    // Navigate through Setup → Input → Parse → Review
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();

    // Click Generate
    await page
      .getByRole("button", { name: /Generate Objections/i })
      .click();

    // Should advance to Results step
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Should show results heading
    await expect(
      page.getByRole("heading", { name: "Generated Objections" })
    ).toBeVisible();

    // Should show objection count
    await expect(
      page.getByText(/3 objections across 3 requests/i)
    ).toBeVisible();
  });

  test("Results show accordion panels with strength badges", async ({
    page,
  }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page
      .getByRole("button", { name: /Generate Objections/i })
      .click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Should show strength badges
    await expect(page.getByText("High").first()).toBeVisible();
    await expect(page.getByText("Medium").first()).toBeVisible();

    // Should show "No objections" for request 3
    await expect(page.getByText("No objections")).toBeVisible();
  });

  test("Results show disclaimer", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page
      .getByRole("button", { name: /Generate Objections/i })
      .click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Should show disclaimer
    await expect(
      page.getByText("sanctions", { exact: false })
    ).toBeVisible();
  });

  test("Copy All and Download buttons visible", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page
      .getByRole("button", { name: /Generate Objections/i })
      .click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    await expect(
      page.getByRole("button", { name: "Copy All" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Download .txt" })
    ).toBeVisible();
  });

  test("content scope toggle switches between modes", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page
      .getByRole("button", { name: /Generate Objections/i })
      .click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Toggle to "Request + Objections"
    const requestToggle = page.getByRole("radio", {
      name: "Request + Objections",
    });
    await requestToggle.click();
    await expect(requestToggle).toHaveAttribute("aria-checked", "true");
  });

  // ── Navigation ───────────────────────────────────────────────────

  test("Back button navigates to previous step", async ({ page }) => {
    // Go to Input
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("2 / 4")).toBeVisible();

    // Go back
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByText("1 / 4")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Objection Drafter Setup" })
    ).toBeVisible();
  });

  test("Exit link goes to discovery tools", async ({ page }) => {
    const exitLink = page.getByRole("link", { name: /Exit/i });
    await expect(exitLink).toBeVisible();
    await expect(exitLink).toHaveAttribute("href", "/tools/discovery");
  });

  test("Start Over resets wizard", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    // Navigate all the way to results
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page
      .getByRole("button", { name: /Generate Objections/i })
      .click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Click Start Over
    await page.getByRole("button", { name: "Start Over" }).click();

    // Should be back at Setup
    await expect(page.getByText("1 / 4")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Objection Drafter Setup" })
    ).toBeVisible();
  });

  // ── Breadcrumb ───────────────────────────────────────────────────

  test("shows breadcrumb navigation", async ({ page }) => {
    await expect(page.getByRole("link", { name: "Home" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Tools" })).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Discovery" })
    ).toBeVisible();
    await expect(
      page.getByText("Objection Drafter", { exact: true })
    ).toBeVisible();
  });

  // ── Error handling ──────────────────────────────────────────────

  test("shows error on parse failure", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Internal server error" }),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();

    // Should show error message (could be "Internal server error" or "Parse failed")
    await expect(
      page.getByText(/error|failed/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  // ── Posture control (Phase O.2A) ─────────────────────────────────

  test("shows litigation posture controls on setup", async ({ page }) => {
    await expect(page.getByText("Litigation Posture")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Aggressive" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Balanced" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Selective" })
    ).toBeVisible();
  });

  test("aggressive posture is selected by default", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Aggressive" })
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Balanced" })
    ).toHaveAttribute("aria-pressed", "false");
    await expect(
      page.getByRole("button", { name: "Selective" })
    ).toHaveAttribute("aria-pressed", "false");
  });

  test("can select different posture", async ({ page }) => {
    const balanced = page.getByRole("button", { name: "Balanced" });
    await balanced.click();
    await expect(balanced).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Aggressive" })
    ).toHaveAttribute("aria-pressed", "false");
  });

  test("posture descriptions are visible", async ({ page }) => {
    await expect(
      page.getByText("Object broadly to preserve all arguable grounds")
    ).toBeVisible();
    await expect(
      page.getByText("Object where genuinely warranted")
    ).toBeVisible();
    await expect(
      page.getByText("Object only to the strongest, most defensible grounds")
    ).toBeVisible();
  });

  test("posture selection persists through wizard steps", async ({ page }) => {
    // Select "Selective" posture
    await page.getByRole("button", { name: "Selective" }).click();

    // Navigate to Input step and back
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("2 / 4")).toBeVisible();
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByText("1 / 4")).toBeVisible();

    // Posture should still be "Selective"
    await expect(
      page.getByRole("button", { name: "Selective" })
    ).toHaveAttribute("aria-pressed", "true");
  });

  test("generate request includes posture parameter", async ({ page }) => {
    let capturedBody: string | null = null;

    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      capturedBody = route.request().postData();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    // Select "balanced" posture before proceeding
    await page.getByRole("button", { name: "Balanced" }).click();

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page
      .getByRole("button", { name: /Generate Objections/i })
      .click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Verify the request body contains expected fields including posture
    expect(capturedBody).not.toBeNull();
    const body = JSON.parse(capturedBody!);
    expect(body.requests).toHaveLength(3);
    expect(body.verbosity).toBe("medium");
    expect(body.party_role).toBe("defendant");
    expect(body.posture).toBe("balanced");
  });

  // ── File upload (Phase O.2B) ─────────────────────────────────────

  test("drop zone visible in Input step", async ({ page }) => {
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(
      page.getByText("Upload .docx or .pdf")
    ).toBeVisible();
    await expect(
      page.getByText("or paste text")
    ).toBeVisible();
  });

  test("file upload replaces textarea", async ({ page }) => {
    await page.getByRole("button", { name: "Next", exact: true }).click();

    // Upload a file via the hidden input
    const fileInput = page.getByLabel("File upload input");
    await fileInput.setInputFiles({
      name: "discovery.docx",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: Buffer.from("PK mock docx content"),
    });

    // File card should be visible
    await expect(page.getByText("discovery.docx")).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();

    // Textarea and divider should be hidden
    await expect(page.getByLabel("Discovery request text")).not.toBeVisible();
    await expect(page.getByText("or paste text")).not.toBeVisible();
  });

  test("remove file restores textarea", async ({ page }) => {
    await page.getByRole("button", { name: "Next", exact: true }).click();

    // Upload a file
    const fileInput = page.getByLabel("File upload input");
    await fileInput.setInputFiles({
      name: "test.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF mock"),
    });

    // File card should show
    await expect(page.getByText("test.pdf")).toBeVisible();

    // Remove file
    await page.getByRole("button", { name: "Remove" }).click();

    // Textarea should reappear
    await expect(page.getByLabel("Discovery request text")).toBeVisible();
    await expect(page.getByText("Upload .docx or .pdf")).toBeVisible();
  });

  test("parse works with uploaded file (mocked API)", async ({ page }) => {
    await page.route("**/api/objections/parse-document", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();

    // Upload a file
    const fileInput = page.getByLabel("File upload input");
    await fileInput.setInputFiles({
      name: "srog_set_one.docx",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: Buffer.from("PK mock docx content"),
    });

    await expect(page.getByText("srog_set_one.docx")).toBeVisible();

    // Click parse
    await page.getByRole("button", { name: "Parse Requests" }).first().click();

    // Should advance to Review step
    await expect(page.getByText("3 / 4")).toBeVisible();
    await expect(page.getByText("3 requests found")).toBeVisible();
  });

  test("Download .docx button visible in Results", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page.getByRole("button", { name: /Generate Objections/i }).click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    await expect(
      page.getByRole("button", { name: "Download .docx" })
    ).toBeVisible();
  });

  test("Download .docx calls export API (mocked)", async ({ page }) => {
    let exportCalled = false;

    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });
    await page.route("**/api/objections/export", async (route) => {
      exportCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers: {
          "Content-Disposition": 'attachment; filename="objections.docx"',
        },
        body: Buffer.from("PK mock docx"),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page.getByRole("button", { name: /Generate Objections/i }).click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    await page.getByRole("button", { name: "Download .docx" }).click();

    // Wait for the export request
    await page.waitForTimeout(500);
    expect(exportCalled).toBe(true);
  });

  test("Insert into Shell hidden for non-shell text uploads", async ({ page }) => {
    await page.route("**/api/objections/parse", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PARSE_RESPONSE),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    // Use text input (not file upload), so no file + not a shell
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Discovery request text").fill(SAMPLE_SROG_TEXT);
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();
    await page.getByRole("button", { name: /Generate Objections/i }).click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Insert into Shell should NOT be visible (no file uploaded)
    await expect(
      page.getByRole("button", { name: "Insert into Shell" })
    ).not.toBeVisible();
  });

  test("Insert into Shell shown for docx shell uploads", async ({ page }) => {
    // Mock parse-document to return is_response_shell: true
    const shellParseResponse = {
      ...MOCK_PARSE_RESPONSE,
      is_response_shell: true,
    };

    await page.route("**/api/objections/parse-document", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(shellParseResponse),
      });
    });
    await page.route("**/api/objections/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_GENERATE_RESPONSE),
      });
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();

    // Upload a file
    const fileInput = page.getByLabel("File upload input");
    await fileInput.setInputFiles({
      name: "response_shell.docx",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: Buffer.from("PK mock shell docx"),
    });

    await expect(page.getByText("response_shell.docx")).toBeVisible();

    // Parse
    await page.getByRole("button", { name: "Parse Requests" }).first().click();
    await expect(page.getByText("3 / 4")).toBeVisible();

    // Generate
    await page.getByRole("button", { name: /Generate Objections/i }).click();
    await expect(page.getByText("4 / 4")).toBeVisible();

    // Insert into Shell should be visible
    await expect(
      page.getByRole("button", { name: "Insert into Shell" })
    ).toBeVisible();
  });
});
