import { test, expect } from "@playwright/test";
import {
  setupAuth,
  fillCaseInfo,
  clickNext,
  clickBack,
  selectClaims,
  waitForBankLoaded,
  waitForNextEnabled,
  selectAllInFirstCategory,
  interceptGenerateResponse,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";
import { isDocx, getDocxPlainText } from "./helpers/doc-validator";

/**
 * Helper: select the defendant party role in the case info step.
 * The PartyRoleSelector renders buttons with text "Defendant" + description.
 */
async function selectDefendantRole(page: import("@playwright/test").Page) {
  await page
    .getByRole("button", { name: /^Defendant/ })
    .click();
}

test.describe("Defendant-side discovery flows", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("defendant SROGs — defendant categories appear, bank loads", async ({
    page,
  }) => {
    await page.goto("/tools/discovery/special-interrogatories");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Special Interrogatories"
    );

    // Set defendant role
    await selectDefendantRole(page);
    await fillCaseInfo(page);
    await clickNext(page);

    // Claims
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    // Requests — bank should load with defendant-filtered items
    await waitForBankLoaded(page);

    // Should have category pills visible (defendant gets different categories)
    const categoryButtons = page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ });
    await expect(categoryButtons.first()).toBeVisible({ timeout: 10_000 });

    // Should show the limit counter
    await expect(page.getByText(/\/35/)).toBeVisible();
  });

  test("defendant RFPDs — defendant categories appear, document generates", async ({
    page,
  }) => {
    await page.goto("/tools/discovery/request-production");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Requests for Production"
    );

    await selectDefendantRole(page);
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    await waitForBankLoaded(page);
    await selectAllInFirstCategory(page);
    await waitForNextEnabled(page);
    await clickNext(page);

    // Production instructions
    await expect(page.getByRole("heading", { name: "Production Instructions" })).toBeVisible();
    await clickNext(page);

    // Definitions
    await expect(page.getByText("Legal Definitions")).toBeVisible();
    await clickNext(page);

    // Review
    await expect(page.getByText("Review Before Generating")).toBeVisible();
    // Party role shows Defendant
    await expect(page.getByText("Defendant", { exact: true })).toBeVisible();
    await clickNext(page);

    // Generate
    await expect(page.getByText("Ready to Generate")).toBeVisible();
    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download .docx/i })
        .click();
    });

    expect(isDocx(buffer)).toBe(true);
    expect(buffer.length).toBeGreaterThan(1000);
  });

  test("defendant RFAs — defendant categories appear, fact/genuineness works", async ({
    page,
  }) => {
    await page.goto("/tools/discovery/request-admission");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Requests for Admission"
    );

    await selectDefendantRole(page);
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    await waitForBankLoaded(page);

    // Should have fact/genuineness counter
    await expect(page.getByText(/\d+ fact \+ \d+ genuineness/)).toBeVisible({ timeout: 10_000 });

    // Should have category pills
    const categoryButtons = page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ });
    await expect(categoryButtons.first()).toBeVisible({ timeout: 10_000 });
  });

  test("role switch — change party role mid-wizard, bank re-filters", async ({
    page,
  }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    // Start as plaintiff
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    // Load bank as plaintiff
    await waitForBankLoaded(page);
    const plaintiffCategories = await page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ })
      .count();
    expect(plaintiffCategories).toBeGreaterThan(0);

    // Go back to case info and switch to defendant
    await clickBack(page); // Claims
    await clickBack(page); // Case Info

    await selectDefendantRole(page);
    await clickNext(page); // Claims
    await clickNext(page); // Requests — should re-fetch bank

    await waitForBankLoaded(page);

    // Bank should now show defendant-filtered categories
    const defendantCategories = await page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ })
      .count();
    expect(defendantCategories).toBeGreaterThan(0);
  });

  test("variable resolution — resolved text visible in preview", async ({
    page,
  }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    await selectDefendantRole(page);
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    await waitForBankLoaded(page);
    await selectAllInFirstCategory(page);
    await waitForNextEnabled(page);
    await clickNext(page);

    // Definitions
    await expect(page.getByText("Legal Definitions")).toBeVisible();
    await clickNext(page);

    // Review — should show resolved text with actual party names
    await expect(page.getByText("Review Before Generating")).toBeVisible();

    // The preview should contain the plaintiff/defendant names from case info
    const previewSection = page.locator('[class*="space-y-6"]');
    const previewText = await previewSection.textContent();

    // Verify party names appear in the preview
    expect(previewText).toContain(TEST_CASE_INFO.plaintiffName);
    expect(previewText).toContain(TEST_CASE_INFO.defendantName);

    // Should show "Defendant" as party role
    expect(previewText).toContain("Defendant");
  });

  test("defendant full workflow generates valid DOCX", async ({ page }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    await selectDefendantRole(page);
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    await waitForBankLoaded(page);
    await selectAllInFirstCategory(page);
    await waitForNextEnabled(page);
    await clickNext(page);

    // Definitions
    await clickNext(page);

    // Review
    await clickNext(page);

    // Generate
    await expect(page.getByText("Ready to Generate")).toBeVisible();
    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download .docx/i })
        .click();
    });

    expect(isDocx(buffer)).toBe(true);

    const text = await getDocxPlainText(buffer);
    expect(text).toContain(TEST_CASE_INFO.plaintiffName);
    expect(text).toContain(TEST_CASE_INFO.defendantName);
    expect(text).toContain("SPECIAL INTERROGATORY NO. 1");
  });
});
