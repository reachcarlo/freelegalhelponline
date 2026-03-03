import { test, expect } from "@playwright/test";
import { fillCaseInfo, clickNext, selectClaims } from "./helpers/wizard-helpers";

test.describe("Mobile viewport (375x812)", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("discovery index page displays correctly", async ({ page }) => {
    await page.goto("/tools/discovery");
    await expect(
      page.getByRole("heading", { level: 1 })
    ).toBeVisible();

    // All 5 tool cards should be visible (may need scrolling)
    const cards = page.locator('a[href^="/tools/discovery/"]');
    await expect(cards).toHaveCount(5);
  });

  test("wizard stepper shows mobile step text", async ({ page }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    // Mobile stepper shows "Step N of M" text (sm:hidden, visible at 375px)
    await expect(
      page.getByText(/Step \d+ of \d+/, { exact: false })
    ).toBeVisible();
  });

  test("Back and Next buttons have 44px touch targets", async ({ page }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    const nextBtn = page.getByRole("button", { name: "Next", exact: true });
    await expect(nextBtn).toBeVisible();

    // Check minimum height via computed style
    const minHeight = await nextBtn.evaluate(
      (el) => window.getComputedStyle(el).minHeight
    );
    const heightPx = parseInt(minHeight);
    expect(heightPx).toBeGreaterThanOrEqual(44);
  });

  test("case info form does not overflow horizontally", async ({ page }) => {
    await page.goto("/tools/discovery/special-interrogatories");

    // Check that the page doesn't have horizontal scrollbar
    const hasOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    expect(hasOverflow).toBe(false);
  });

  test("wizard navigation works on mobile", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");

    // Fill case info
    await fillCaseInfo(page);
    await clickNext(page);

    // Claims step should be visible
    await expect(page.getByText("Claim Types")).toBeVisible();

    // Select a claim
    await selectClaims(page, ["FEHA Discrimination"]);

    // Navigate back
    const backBtn = page.getByRole("button", { name: "Back" });
    await backBtn.click();

    // Should be back on case info
    await expect(page.locator("#case_number")).toBeVisible();
  });

  test("claim selector pills wrap on narrow screen", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);

    // Claim buttons should be visible and not overflow
    const hasOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    expect(hasOverflow).toBe(false);

    // At least some claim buttons should be visible
    const claimBtns = page.getByRole("button", { name: /FEHA/ });
    await expect(claimBtns.first()).toBeVisible();
  });

  test("step counter updates when navigating", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");

    // Step 1 — mobile stepper visible at 375px
    await expect(page.getByText("Step 1 of 5")).toBeVisible();

    await fillCaseInfo(page);
    await clickNext(page);

    // Step 2
    await expect(page.getByText("Step 2 of 5")).toBeVisible();
  });
});
