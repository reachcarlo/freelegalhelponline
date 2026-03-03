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
import { isDocx, validateDocxContent } from "./helpers/doc-validator";

test.describe("Requests for Production of Documents (RFPDs)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tools/discovery/request-production");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Requests for Production"
    );
  });

  test("wizard starts at Case Info", async ({ page }) => {
    await expect(page.locator("#case_number")).toBeVisible();
  });

  test("does not show a limit counter (RFPDs unlimited)", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Should NOT show /35 limit counter
    await expect(page.getByText(/\/35/)).toBeHidden();
  });

  test("has 7 steps including Instructions", async ({ page }) => {
    // RFPDs have an extra "Instructions" step — nav counter shows "1 / 7"
    await expect(page.getByText("1 / 7")).toBeVisible();
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

    // Instructions step (RFPD-specific)
    await expect(
      page.getByRole("heading", { name: "Production Instructions" })
    ).toBeVisible();
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
        "REQUEST FOR PRODUCTION NO. 1",
        TEST_CASE_INFO.caseNumber,
        TEST_CASE_INFO.attorneyName,
      ],
    });
  });

  test("DOCX includes production instructions", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    await selectAllInFirstCategory(page);

    await waitForNextEnabled(page);
    await clickNext(page); // Instructions
    await clickNext(page); // Definitions
    await clickNext(page); // Review
    await clickNext(page); // Generate

    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download .docx/i })
        .click();
    });

    await validateDocxContent(buffer, {
      containsText: ["possession, custody, or control"],
    });
  });
});
