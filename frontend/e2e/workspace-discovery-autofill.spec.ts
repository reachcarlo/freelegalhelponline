import { test, expect, Page } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Workspace Discovery Auto-fill E2E Tests (V2.4.2)
 *
 * Tests that CaseContext data pre-fills discovery wizard fields
 * when accessing discovery tools from within the case workspace.
 */

const CASE_ID = "ws-disc-autofill-id";

const MOCK_CASE = {
  id: CASE_ID,
  name: "Auto-fill Test Case",
  description: null,
  status: "active",
  file_count: 0,
  created_at: "2026-03-23T00:00:00",
  updated_at: "2026-03-23T00:00:00",
};

const MOCK_CONTEXT = {
  case_id: CASE_ID,
  case_name: "Auto-fill Test Case",
  parties: [
    { name: "Jane Smith", role: "plaintiff", party_type: "individual", count: null },
    { name: "Acme Corp", role: "defendant", party_type: "corporation", count: null },
    { name: "John Doe", role: "defendant", party_type: "individual", count: null },
  ],
  court: {
    court: "Superior Court of California, County of Los Angeles",
    county: "Los Angeles",
    department: "42",
    judge: "Hon. Maria Garcia",
  },
  attorneys: [
    {
      name: "Robert Chen",
      side: "plaintiff",
      bar_number: "123456",
      firm: "Chen & Associates",
      email: "rchen@chen-law.com",
    },
    {
      name: "Lisa Park",
      side: "defendant",
      bar_number: "789012",
      firm: "BigLaw LLP",
      email: "lpark@biglaw.com",
    },
  ],
  employment_history: [],
  claims: [
    { claim_type: "feha_discrimination", status: "active", protected_class: "race", supporting_facts: null, reason: null },
    { claim_type: "wrongful_termination_public_policy", status: "active", protected_class: null, supporting_facts: null, reason: null },
    { claim_type: "wage_theft", status: "active", protected_class: null, supporting_facts: null, reason: null },
  ],
  key_dates: [
    { label: "Complaint Filed", date: "2026-01-15", date_type: "complaint_filed" },
    { label: "Trial Date", date: "2026-09-01", date_type: "trial" },
  ],
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

  await page.route("**/api/discovery/banks/*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "srog-var-1",
            text: "State all facts supporting {EMPLOYEE}'s claim that {EMPLOYER} engaged in discrimination.",
            category: "general",
            order: 1,
            rfa_type: null,
            applicable_roles: null,
            applicable_claims: null,
          },
        ],
        categories: [{ key: "general", label: "General" }],
        total_items: 1,
        limit: 35,
      }),
    })
  );
}

test.describe("Discovery Auto-fill from CaseContext (V2.4.2)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockAPIs(page);
  });

  test("SROGs wizard pre-fills plaintiff name, defendant name, and court from CaseContext", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByText("Special Interrogatories")).toBeVisible();

    // Step 0 is the case info form — check pre-filled fields
    // Plaintiff name
    const plaintiffInput = page.locator("#plaintiff-0-name");
    await expect(plaintiffInput).toHaveValue("Jane Smith");

    // Defendant names (2 defendants)
    const defendant0 = page.locator("#defendant-0-name");
    await expect(defendant0).toHaveValue("Acme Corp");
    const defendant1 = page.locator("#defendant-1-name");
    await expect(defendant1).toHaveValue("John Doe");

    // Court county
    const countySelect = page.locator("#court_county");
    await expect(countySelect).toHaveValue("Los Angeles");

    // Judge
    const judgeInput = page.locator("#judge_name");
    await expect(judgeInput).toHaveValue("Hon. Maria Garcia");

    // Department
    const deptInput = page.locator("#department");
    await expect(deptInput).toHaveValue("42");
  });

  test("SROGs wizard pre-fills attorney info from CaseContext", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByText("Special Interrogatories")).toBeVisible();

    // Attorney name (first plaintiff-side attorney)
    const attyName = page.locator("#atty_name");
    await expect(attyName).toHaveValue("Robert Chen");

    // State bar number
    const attySbn = page.locator("#atty_sbn");
    await expect(attySbn).toHaveValue("123456");

    // Firm name
    const attyFirm = page.locator("#atty_firm");
    await expect(attyFirm).toHaveValue("Chen & Associates");

    // Email
    const attyEmail = page.locator("#atty_email");
    await expect(attyEmail).toHaveValue("rchen@chen-law.com");
  });

  test("SROGs wizard pre-fills key dates from CaseContext", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByText("Special Interrogatories")).toBeVisible();

    // Complaint filed date
    const filedDate = page.locator("#complaint_filed_date");
    await expect(filedDate).toHaveValue("2026-01-15");

    // Trial date
    const trialDate = page.locator("#trial_date");
    await expect(trialDate).toHaveValue("2026-09-01");
  });

  test("SROGs wizard pre-selects claims from CaseContext in Step 2", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByText("Special Interrogatories")).toBeVisible();

    // Fill required fields not provided by CaseContext
    await page.fill("#case_number", "2026-TEST-001");
    await page.fill("#atty_address", "100 Test St");
    await page.fill("#atty_csz", "Los Angeles, CA 90001");
    await page.fill("#atty_phone", "(555) 123-4567");

    // Navigate to Step 2 (Claims)
    await page.getByRole("button", { name: "Next" }).click();

    // Verify the 3 claims from CaseContext are pre-selected (aria-pressed="true")
    await expect(
      page.getByRole("button", { name: "FEHA Discrimination" }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Wrongful Termination (Public Policy)" }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Wage Theft / Unpaid Wages" }),
    ).toHaveAttribute("aria-pressed", "true");

    // Verify a claim NOT in CaseContext is not selected
    await expect(
      page.getByRole("button", { name: "FEHA Harassment" }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  test("Claims count reflects pre-selected claims from CaseContext", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Fill required fields not provided by CaseContext
    await page.fill("#case_number", "2026-TEST-001");
    await page.fill("#atty_address", "100 Test St");
    await page.fill("#atty_csz", "Los Angeles, CA 90001");
    await page.fill("#atty_phone", "(555) 123-4567");

    // Navigate to Step 2 (Claims)
    await page.getByRole("button", { name: "Next" }).click();

    // Verify the "3 claims selected" text
    await expect(page.getByText("3 claims selected")).toBeVisible();
  });

  test("Request builder resolves {EMPLOYEE}/{EMPLOYER} variables from CaseContext", async ({
    page,
  }) => {
    await page.goto(`/cases/${CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();

    // Fill required fields not provided by CaseContext
    await page.fill("#case_number", "2026-TEST-001");
    await page.fill("#atty_address", "100 Test St");
    await page.fill("#atty_csz", "Los Angeles, CA 90001");
    await page.fill("#atty_phone", "(555) 123-4567");

    // Navigate to Step 2 (Claims) then Step 3 (Requests)
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Next" }).click();

    // The bank item text has {EMPLOYEE} and {EMPLOYER} variables.
    // With CaseContext, {EMPLOYEE} → "Jane Smith", {EMPLOYER} → "Acme Corp"
    await expect(
      page.getByText("Jane Smith", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByText("Acme Corp", { exact: false }),
    ).toBeVisible();

    // The raw placeholders should NOT appear
    await expect(page.getByText("{EMPLOYEE}")).toHaveCount(0);
    await expect(page.getByText("{EMPLOYER}")).toHaveCount(0);
  });
});

test.describe("Party role inference from CaseContext (V2.4.5)", () => {
  const ROLE_CASE_ID = "ws-role-infer-id";

  const ROLE_MOCK_CASE = {
    id: ROLE_CASE_ID,
    name: "Role Inference Case",
    description: null,
    status: "active",
    file_count: 0,
    created_at: "2026-03-23T00:00:00",
    updated_at: "2026-03-23T00:00:00",
  };

  // The mock auth user email is "e2e@lawfirm.com" (from wizard-helpers).
  // This context has that email on the DEFENDANT side attorney.
  const ROLE_MOCK_CONTEXT = {
    case_id: ROLE_CASE_ID,
    case_name: "Role Inference Case",
    parties: [
      { name: "Alice Worker", role: "plaintiff", party_type: "individual", count: null },
      { name: "MegaCorp Inc", role: "defendant", party_type: "corporation", count: null },
    ],
    court: { court: "Superior Court of California", county: "San Francisco", department: null, judge: null },
    attorneys: [
      { name: "Outside Counsel", side: "plaintiff", bar_number: "111111", firm: "Other Firm", email: "other@firm.com" },
      { name: "E2E Attorney", side: "defendant", bar_number: "222222", firm: "E2E Law", email: "e2e@lawfirm.com" },
    ],
    employment_history: [],
    claims: [],
    key_dates: [],
    financials: [],
    fact_count: 0,
    confirmed_count: 0,
    extraction_sources: {},
  };

  test.beforeEach(async ({ page }) => {
    await setupAuth(page);

    await page.route(`**/api/cases/${ROLE_CASE_ID}`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ROLE_MOCK_CASE) });
      }
      return route.continue();
    });
    await page.route(`**/api/cases/${ROLE_CASE_ID}/context`, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ROLE_MOCK_CONTEXT) })
    );
    await page.route(`**/api/cases/${ROLE_CASE_ID}/files`, (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      }
      return route.continue();
    });
    await page.route(`**/api/cases/${ROLE_CASE_ID}/status-stream`, (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: ping\ndata: {}\n\n" })
    );
    await page.route(`**/api/cases/${ROLE_CASE_ID}/notes*`, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ notes: [] }) })
    );
    await page.route(`**/api/cases/${ROLE_CASE_ID}/chat/sessions`, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sessions: [] }) })
    );
    await page.route(`**/api/cases/${ROLE_CASE_ID}/facts*`, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ facts: [], total: 0 }) })
    );
    await page.route("**/api/discovery/suggest*", (route) =>
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ srogs_categories: [], rfpds_categories: [], rfas_categories: [], srogs_categories_defendant: [], rfpds_categories_defendant: [], rfas_categories_defendant: [] }),
      })
    );
    await page.route("**/api/discovery/banks/*", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], categories: [], total_items: 0, limit: 35 }) })
    );
  });

  test("Party role defaults to defendant when user email matches defendant-side attorney", async ({
    page,
  }) => {
    await page.goto(`/cases/${ROLE_CASE_ID}/discovery/srogs`);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
    await expect(page.getByText("Special Interrogatories")).toBeVisible();

    // The Defendant button should be selected (aria-pressed="true")
    await expect(
      page.getByRole("button", { name: "Defendant" }),
    ).toHaveAttribute("aria-pressed", "true");

    // The Plaintiff button should NOT be selected
    await expect(
      page.getByRole("button", { name: "Plaintiff" }),
    ).toHaveAttribute("aria-pressed", "false");
  });
});
