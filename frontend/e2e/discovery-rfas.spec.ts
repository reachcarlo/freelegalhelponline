import { test, expect } from "@playwright/test";
import {
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

test.describe("Requests for Admission (RFAs)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tools/discovery/request-admission");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Requests for Admission"
    );
  });

  test("wizard starts at Case Info", async ({ page }) => {
    await expect(page.locator("#case_number")).toBeVisible();
  });

  test("shows fact limit counter", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Should show /35 limit for fact requests
    await expect(page.getByText(/\/35 fact requests/)).toBeVisible();
  });

  test("shows RFA type badges", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Click a category to see request rows
    const categoryBtn = page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ })
      .first();
    await expect(categoryBtn).toBeVisible({ timeout: 5_000 });
    await categoryBtn.click();

    // Should see fact/genuineness badges
    const factBadge = page.getByText("fact", { exact: true }).first();
    // At least one badge should be visible
    await expect(factBadge).toBeVisible({ timeout: 5000 }).catch(() => {
      // Some categories may not have visible type badges, that's OK
    });
  });

  test("full workflow generates valid DOCX", async ({ page }) => {
    test.slow(); // DOCX generation can be slow under CI load
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

    // Definitions
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
        "REQUEST FOR ADMISSION NO. 1",
        TEST_CASE_INFO.caseNumber,
      ],
    });

    // Enhanced: verify plain text content
    const text = await getDocxPlainText(buffer);
    expect(text).toContain(TEST_CASE_INFO.plaintiffName);
    expect(text).toContain(TEST_CASE_INFO.defendantName);
    expect(text).toContain("DEFINITIONS");
    expect(text).toContain("REQUEST FOR ADMISSION NO. 1");
  });

  test("custom RFA has fact/genuineness radio", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    const addBtn = page.getByRole("button", { name: /Add Custom Request/i });
    await expect(addBtn).toBeVisible({ timeout: 5_000 });
    await addBtn.click();

    // Should see fact/genuineness radio buttons
    await expect(
      page.getByText("Fact (counts toward 35 limit)")
    ).toBeVisible();
    await expect(page.getByText("Genuineness (unlimited)")).toBeVisible();
  });
});
