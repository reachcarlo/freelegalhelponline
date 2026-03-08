import { test, expect } from "@playwright/test";
import {
  setupAuth,
  fillCaseInfo,
  clickNext,
  selectClaims,
  waitForSectionsLoaded,
  waitForNextEnabled,
  interceptGenerateResponse,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";
import {
  isPdf,
  validatePdfContent,
  getPdfFieldMap,
  getPdfCheckboxes,
} from "./helpers/doc-validator";

test.describe("DISC-001 (Form Interrogatories - General)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await page.goto("/tools/discovery/frogs-general");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Form Interrogatories"
    );
  });

  test("wizard shows Case Info as first step", async ({ page }) => {
    await expect(page.getByText("Case Information")).toBeVisible();
    await expect(page.locator("#case_number")).toBeVisible();
  });

  test("Next is disabled without case info", async ({ page }) => {
    const nextBtn = page.getByRole("button", { name: "Next", exact: true });
    await expect(nextBtn).toBeDisabled();
  });

  test("can fill case info and advance to Claims", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);

    // Should be on Claims step
    await expect(page.getByText("Claim Types")).toBeVisible();
  });

  test("can select claims and advance to Sections", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);

    // Select claims
    await selectClaims(page, ["FEHA Discrimination"]);
    await expect(page.getByText(/\d+ claims? selected/)).toBeVisible();

    await clickNext(page);
    await waitForSectionsLoaded(page);

    // Should see section groups
    await expect(page.getByText(/\d+ of \d+ selected/)).toBeVisible();
  });

  test("suggested sections are auto-selected", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);

    // After sections load, suggested should be auto-selected.
    // Wait for the "X of Y selected" text to appear with X > 0.
    await expect(page.getByText(/[1-9]\d* of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("full workflow generates valid PDF", async ({ page }) => {
    // Step 1: Case Info
    await fillCaseInfo(page);
    await clickNext(page);

    // Step 2: Claims
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);

    // Step 3: Sections — auto-selected via suggestions, wait for selection + Next enabled
    await expect(page.getByText(/[1-9]\d* of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
    await waitForNextEnabled(page);
    await clickNext(page);

    // Step 4: Review
    await expect(page.getByText("Review Before Generating")).toBeVisible();
    await clickNext(page);

    // Step 5: Generate
    await expect(page.getByText("Ready to Generate")).toBeVisible();

    // Intercept and validate
    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download PDF/i })
        .click();
    });

    expect(isPdf(buffer)).toBe(true);
    expect(buffer.length).toBeGreaterThan(1000);

    // Validate PDF content
    await validatePdfContent(buffer, {
      containsText: [TEST_CASE_INFO.caseNumber],
    });
  });

  test("shows downloaded success state", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);

    await expect(page.getByText(/[1-9]\d* of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
    await waitForNextEnabled(page);
    await clickNext(page);
    await clickNext(page);

    // Generate
    await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download PDF/i })
        .click();
    });

    // Should show success
    await expect(page.getByText("Downloaded!")).toBeVisible();
  });

  test("PDF contains all case info in correct fields", async ({ page }) => {
    // Full workflow to generate
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);
    await expect(page.getByText(/[1-9]\d* of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
    await waitForNextEnabled(page);
    await clickNext(page);
    await clickNext(page);

    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download PDF/i })
        .click();
    });

    const fields = await getPdfFieldMap(buffer);

    // Attorney info
    expect(fields["Name[0]"]).toBe(TEST_CASE_INFO.attorneyName);
    expect(fields["AttyBarNo[0]"]).toBe(TEST_CASE_INFO.sbn);
    expect(fields["Street[0]"]).toBe(TEST_CASE_INFO.address);
    expect(fields["City[0]"]).toContain("Los Angeles");
    expect(fields["State[0]"]).toBe("CA");
    expect(fields["Zip[0]"]).toBe("90001");
    expect(fields["Phone[0]"]).toBe(TEST_CASE_INFO.phone);
    expect(fields["Email[0]"]).toBe(TEST_CASE_INFO.email);

    // Case info
    expect(fields["CaseNumber[0]"]).toBe(TEST_CASE_INFO.caseNumber);
    // Court county
    expect(fields["TextField4[0]"]).toContain("Los Angeles");
    // Asking party (plaintiff)
    expect(fields["TextField5[0]"]).toBe(TEST_CASE_INFO.plaintiffName);
    // Answering party (defendant)
    expect(fields["TextField6[0]"]).toBe(TEST_CASE_INFO.defendantName);
    // Short title (vs.)
    expect(fields["TextField8[0]"]).toContain("vs.");

    // At least one section checkbox should be checked
    const checked = await getPdfCheckboxes(buffer);
    expect(checked.length).toBeGreaterThan(0);
  });
});
