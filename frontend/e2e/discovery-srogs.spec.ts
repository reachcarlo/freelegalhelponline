import { test, expect } from "@playwright/test";
import {
  setupAuth,
  fillCaseInfo,
  clickNext,
  selectClaims,
  waitForBankLoaded,
  waitForNextEnabled,
  selectAllInFirstCategory,
  interceptGenerateResponse,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";
import {
  isDocx,
  validateDocxContent,
  getDocxPlainText,
} from "./helpers/doc-validator";

test.describe("Special Interrogatories (SROGs)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await page.goto("/tools/discovery/special-interrogatories");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Special Interrogatories"
    );
  });

  test("wizard starts at Case Info", async ({ page }) => {
    await expect(page.locator("#case_number")).toBeVisible();
    // Nav shows step counter "1 / 6" (always visible, unlike mobile-only stepper text)
    await expect(page.getByText("1 / 6")).toBeVisible();
  });

  test("can fill case info and advance through wizard", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);

    // Claims step
    await expect(page.getByText("Claim Types")).toBeVisible();
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    // Requests step - wait for bank to load
    await waitForBankLoaded(page);
    await expect(page.getByText(/\d+\/35 interrogatories/)).toBeVisible();
  });

  test("shows 35-limit counter", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Should show limit counter
    await expect(page.getByText(/\/35/)).toBeVisible();
  });

  test("can select and deselect requests", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Click first category tab to see its requests
    const firstCategory = page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ })
      .first();
    await expect(firstCategory).toBeVisible({ timeout: 10_000 });
    await firstCategory.click();

    // Should see request checkboxes after category opens
    const checkbox = page.getByRole("checkbox", { name: "Select request 1" });
    await expect(checkbox).toBeVisible({ timeout: 5_000 });

    // Select
    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Counter should update
    await expect(page.getByText(/1\/35 interrogatories/)).toBeVisible();

    // Deselect
    await checkbox.uncheck();
    await expect(checkbox).not.toBeChecked();
    await expect(page.getByText(/0\/35 interrogatories/)).toBeVisible();
  });

  test("can add custom request", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Click add custom request — uses Unicode ellipsis in placeholder
    const addBtn = page.getByRole("button", { name: /Add Custom Request/i });
    await expect(addBtn).toBeVisible({ timeout: 5_000 });
    await addBtn.click();

    const textarea = page.locator(
      'textarea[placeholder="Enter your custom request text\u2026"]'
    );
    await expect(textarea).toBeVisible({ timeout: 5_000 });
    await textarea.fill("State the reason for EMPLOYEE's termination.");
    await page.getByRole("button", { name: "Add Request" }).click();
  });

  test("full workflow generates valid DOCX", async ({ page }) => {
    // Case Info
    await fillCaseInfo(page);
    await clickNext(page);

    // Claims
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);

    // Requests
    await waitForBankLoaded(page);
    await selectAllInFirstCategory(page);
    await waitForNextEnabled(page);
    await clickNext(page);

    // Definitions step
    await expect(page.getByText("Legal Definitions")).toBeVisible();
    await clickNext(page);

    // Review
    await expect(page.getByText("Review Before Generating")).toBeVisible();
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

    await validateDocxContent(buffer, {
      containsText: [
        "SPECIAL INTERROGATORY NO. 1",
        TEST_CASE_INFO.caseNumber,
        TEST_CASE_INFO.attorneyName,
      ],
    });

    // Enhanced: verify plain text content (handles text split across XML tags)
    const text = await getDocxPlainText(buffer);
    expect(text).toContain(TEST_CASE_INFO.plaintiffName);
    expect(text).toContain(TEST_CASE_INFO.defendantName);
    expect(text).toContain("DEFINITIONS");
    // At least one interrogatory
    expect((text.match(/SPECIAL INTERROGATORY NO\./g) || []).length).toBeGreaterThanOrEqual(1);
    // Signature block
    expect(text).toContain(TEST_CASE_INFO.attorneyName);
  });

  test("DOCX contains court county", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Select some requests
    await selectAllInFirstCategory(page);

    // Navigate to generate
    await waitForNextEnabled(page);
    await clickNext(page); // Definitions
    await clickNext(page); // Review
    await clickNext(page); // Generate

    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download .docx/i })
        .click();
    });

    await validateDocxContent(buffer, {
      containsText: ["LOS ANGELES"],
    });
  });
});
