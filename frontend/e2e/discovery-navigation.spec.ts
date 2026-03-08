import { test, expect } from "@playwright/test";
import {
  fillCaseInfo,
  clickNext,
  clickBack,
  selectClaims,
  waitForSectionsLoaded,
  waitForNextEnabled,
  interceptGenerateResponse,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";

test.describe("Discovery navigation", () => {
  test("breadcrumb visible in FROG wizard", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    await expect(page.getByTestId("breadcrumb-discovery")).toBeVisible();
  });

  test("breadcrumb visible in DOCX wizard", async ({ page }) => {
    await page.goto("/tools/discovery/special-interrogatories");
    await expect(page.getByTestId("breadcrumb-discovery")).toBeVisible();
  });

  test("breadcrumb navigates to hub", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    await page.getByTestId("breadcrumb-discovery").click();

    await expect(page).toHaveURL(/\/tools\/discovery\/?$/);
    await expect(
      page.getByRole("heading", { name: "Discovery Document Generator" })
    ).toBeVisible();
  });

  test("back button preserves data within wizard", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);

    // Should be on Claims
    await expect(page.getByText("Claim Types")).toBeVisible();

    // Go back
    await clickBack(page);

    // Case info should still be filled
    await expect(page.locator("#case_number")).toHaveValue(
      TEST_CASE_INFO.caseNumber
    );
    await expect(page.locator("#atty_name")).toHaveValue(
      TEST_CASE_INFO.attorneyName
    );
  });

  test("exit link shown on first step", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    const exitLink = page.getByRole("link", { name: /Exit/i });
    await expect(exitLink).toBeVisible();
    await expect(exitLink).toHaveAttribute("href", "/tools/discovery");
  });

  test("Start Over resets wizard after generation", async ({ page }) => {
    // Full FROG workflow
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);

    // Ensure sections are selected (auto-suggestion may not fire under CI load)
    await expect(page.getByText(/\d+ of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
    // If no sections were auto-selected, click "Select all"
    const selText = await page.getByText(/\d+ of \d+ selected/).textContent();
    if (selText?.startsWith("0 of")) {
      await page.getByRole("button", { name: "Select all" }).first().click();
    }
    await waitForNextEnabled(page);
    await clickNext(page);
    await clickNext(page);

    // Generate
    await expect(page.getByText("Ready to Generate")).toBeVisible();
    await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download PDF/i })
        .click();
    });

    await expect(page.getByText("Downloaded!")).toBeVisible();

    // Click Start Over
    await page.getByTestId("start-over").click();

    // Should be back on Case Info with empty fields
    await expect(page.locator("#case_number")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("#case_number")).toHaveValue("");
  });

  test("breadcrumb works from any step", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);

    // We're on step 3 (Sections). Click breadcrumb.
    await page.getByTestId("breadcrumb-discovery").click();
    await expect(page).toHaveURL(/\/tools\/discovery\/?$/);
    await expect(
      page.getByRole("heading", { name: "Discovery Document Generator" })
    ).toBeVisible();
  });
});
