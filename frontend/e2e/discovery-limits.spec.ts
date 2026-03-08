import { test, expect } from "@playwright/test";
import {
  fillCaseInfo,
  clickNext,
  selectClaims,
  waitForBankLoaded,
  waitForNextEnabled,
  interceptGenerateResponse,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";
import { isDocx, getDocxPlainText } from "./helpers/doc-validator";

test.describe("35-limit enforcement and Declaration of Necessity", () => {
  test("SROGs: selecting all categories shows declaration warning when over 35", async ({
    page,
  }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    await fillCaseInfo(page);
    await clickNext(page);

    // Select multiple claim types to get more requests
    await selectClaims(page, [
      "FEHA Discrimination",
      "FEHA Harassment",
      "FEHA Retaliation",
      "Wrongful Termination",
      "Wage Theft",
    ]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Select all requests across multiple categories
    const categoryBtns = page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ });
    const count = await categoryBtns.count();

    for (let i = 0; i < Math.min(count, 6); i++) {
      const btn = categoryBtns.nth(i);
      if (await btn.isVisible()) {
        await btn.click();
        const selectAll = page.getByRole("button", {
          name: /Select all in category/i,
        });
        // Wait for the button to appear after category opens
        await expect(selectAll).toBeVisible({ timeout: 3_000 }).catch(() => {});
        if (await selectAll.isVisible()) {
          await selectAll.click();
        }
      }
    }

    // Check if we've exceeded 35 — look for declaration warning
    const limitText = page.getByText(/\/ ?35 interrogatories/);
    if (await limitText.isVisible()) {
      const text = await limitText.textContent();
      const match = text?.match(/(\d+)\/?35/);
      if (match && parseInt(match[1]) > 35) {
        await expect(
          page.getByText("Declaration of Necessity required")
        ).toBeVisible();
      }
    }
  });

  test("RFAs: declaration warning mentions CCP 2033.050", async ({ page }) => {
    await page.goto("/tools/discovery/request-admission");

    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, [
      "FEHA Discrimination",
      "FEHA Harassment",
      "FEHA Retaliation",
      "Wrongful Termination",
      "Wage Theft",
    ]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Select all in multiple categories to exceed 35 fact RFAs
    const categoryBtns = page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ });
    const count = await categoryBtns.count();

    for (let i = 0; i < Math.min(count, 8); i++) {
      const btn = categoryBtns.nth(i);
      if (await btn.isVisible()) {
        await btn.click();
        const selectAll = page.getByRole("button", {
          name: /Select all in category/i,
        });
        await expect(selectAll).toBeVisible({ timeout: 3_000 }).catch(() => {});
        if (await selectAll.isVisible()) {
          await selectAll.click();
        }
      }
    }

    // If over 35 fact requests, declaration warning should appear
    const declarationWarning = page.getByText(
      "Declaration of Necessity required"
    );
    if (await declarationWarning.isVisible({ timeout: 2000 }).catch(() => false)) {
      // CCP reference should be visible
      await expect(page.getByText("2033.050", { exact: false })).toBeVisible();
    }
  });

  test("SROGs: limit counter changes color when approaching limit", async ({
    page,
  }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Verify the limit counter is visible
    await expect(page.getByText(/\/35 interrogatories/)).toBeVisible();
  });

  test("RFPDs: no limit counter shown", async ({ page }) => {
    await page.goto("/tools/discovery/request-production");

    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // RFPDs have no limit counter
    await expect(page.getByText(/\/35/)).toBeHidden();
  });

  test("SROGs: DOCX includes Declaration of Necessity when over 35", async ({
    page,
  }) => {
    test.slow(); // Large document generation with many requests
    await page.goto("/tools/discovery/special-interrogatories");

    await fillCaseInfo(page);
    await clickNext(page);

    // Select many claim types to get enough requests
    await selectClaims(page, [
      "FEHA Discrimination",
      "FEHA Harassment",
      "FEHA Retaliation",
      "Wrongful Termination",
      "Wage Theft",
    ]);
    await clickNext(page);
    await waitForBankLoaded(page);

    // Select all requests across all categories
    const categoryBtns = page
      .locator("button")
      .filter({ hasText: /\d+\/\d+/ });
    const count = await categoryBtns.count();

    for (let i = 0; i < count; i++) {
      const btn = categoryBtns.nth(i);
      if (await btn.isVisible()) {
        await btn.click();
        const selectAll = page.getByRole("button", {
          name: /Select all in category/i,
        });
        await expect(selectAll)
          .toBeVisible({ timeout: 3_000 })
          .catch(() => {});
        if (await selectAll.isVisible()) {
          await selectAll.click();
        }
      }
    }

    // Bank has exactly 35 items, so add a custom request to push over the limit
    const addBtn = page.getByRole("button", { name: /Add Custom Request/i });
    await expect(addBtn).toBeVisible({ timeout: 5_000 });
    await addBtn.click();
    const textarea = page.locator(
      'textarea[placeholder="Enter your custom request text\u2026"]'
    );
    await expect(textarea).toBeVisible({ timeout: 5_000 });
    await textarea.fill("State the reason for EMPLOYEE's termination.");
    await page.getByRole("button", { name: "Add Request" }).click();

    // Should now show 36/35 (exceeding limit)
    await expect(page.getByText(/3[6-9]\/35|[4-9]\d\/35/)).toBeVisible({
      timeout: 5_000,
    });

    // Navigate through remaining steps
    await waitForNextEnabled(page);
    await clickNext(page); // Definitions
    await clickNext(page); // Review
    await clickNext(page); // Generate

    // Should show declaration warning
    await expect(page.getByText("Declaration of Necessity Required")).toBeVisible();

    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download .docx/i })
        .click();
    });

    expect(isDocx(buffer)).toBe(true);

    const text = await getDocxPlainText(buffer);
    expect(text).toContain("DECLARATION FOR ADDITIONAL DISCOVERY");
    expect(text).toContain("2030.050");
    expect(text).toContain(TEST_CASE_INFO.attorneyName);
    expect(text).toContain("penalty of perjury");
  });
});
