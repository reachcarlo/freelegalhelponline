import { test, expect } from "@playwright/test";
import {
  fillCaseInfo,
  clickNext,
  selectClaims,
  waitForStateSaved,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";

test.describe("Cross-tool state reset", () => {
  test("navigating to a new tool starts with empty case info", async ({
    page,
  }) => {
    // Fill case info in DISC-001
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination"]);
    await waitForStateSaved(page);

    // Navigate to SROGs
    await page.goto("/tools/discovery/special-interrogatories");
    await expect(page.locator("#case_number")).toBeVisible({ timeout: 10_000 });

    // Case info should be empty (reset on tool switch)
    await expect(page.locator("#case_number")).toHaveValue("");
  });

  test("party role resets to default on tool switch", async ({ page }) => {
    // Set up in DISC-001 — default role is "plaintiff"
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await waitForStateSaved(page);

    // Navigate to RFPDs
    await page.goto("/tools/discovery/request-production");
    await expect(page.locator("#case_number")).toBeVisible({ timeout: 10_000 });

    // Party role should be back to default (Plaintiff pressed)
    const plaintiffBtn = page.getByRole("button", { name: "Plaintiff" });
    await expect(plaintiffBtn).toHaveAttribute("aria-pressed", "true");

    // Case number should be empty
    await expect(page.locator("#case_number")).toHaveValue("");
  });

  test("claim selections reset on tool switch", async ({ page }) => {
    // Select claims in DISC-001
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["FEHA Discrimination", "FEHA Harassment"]);
    await expect(page.getByText("2 claims selected")).toBeVisible();
    await waitForStateSaved(page);

    // Navigate to RFAs
    await page.goto("/tools/discovery/request-admission");
    await expect(page.locator("#case_number")).toBeVisible({ timeout: 10_000 });

    // Fill case info so we can advance to claims step
    await fillCaseInfo(page);
    await clickNext(page);

    // No claims should be selected — the "X claims selected" text is hidden when 0
    await expect(page.getByText(/claims? selected/)).toBeHidden({
      timeout: 10_000,
    });
  });

  test("party names reset on tool switch", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await waitForStateSaved(page);

    // Navigate to another tool
    await page.goto("/tools/discovery/request-admission");
    await expect(page.locator("#case_number")).toBeVisible({ timeout: 10_000 });

    // Plaintiff and defendant names should be empty
    const plaintiffInput = page
      .locator('input[placeholder="Plaintiff name"]')
      .first();
    await expect(plaintiffInput).toHaveValue("");

    const defendantInput = page
      .locator('input[placeholder="Defendant name"]')
      .first();
    await expect(defendantInput).toHaveValue("");
  });
});
