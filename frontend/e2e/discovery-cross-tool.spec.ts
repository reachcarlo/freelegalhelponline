import { test, expect } from "@playwright/test";
import {
  fillCaseInfo,
  clickNext,
  selectClaims,
  waitForStateSaved,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";

/**
 * Helper to navigate to a tool and ensure we're on the Case Info step.
 *
 * Resets currentStep in sessionStorage before navigation to avoid race
 * conditions with the wizard's tool-reset useEffect.
 */
async function navigateToToolAndEnsureCaseInfo(page: import("@playwright/test").Page, path: string): Promise<void> {
  // Reset currentStep in sessionStorage before navigating
  await page.evaluate((key) => {
    const raw = sessionStorage.getItem(key);
    if (raw) {
      const state = JSON.parse(raw);
      state.currentStep = 0;
      sessionStorage.setItem(key, JSON.stringify(state));
    }
  }, "eh-discovery-state");

  await page.goto(path);

  // Wait for Case Info input to be visible after hydration
  await expect(page.locator("#case_number")).toBeVisible({ timeout: 10_000 });
}

test.describe("Cross-tool state persistence", () => {
  test("case info persists across tool navigation via sessionStorage", async ({
    page,
  }) => {
    // Fill case info in DISC-001
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);

    // Select claims
    await selectClaims(page, ["FEHA Discrimination"]);

    // Ensure state is persisted to sessionStorage before navigating
    await waitForStateSaved(page);

    // Navigate to SROGs and ensure we're on Case Info step
    await navigateToToolAndEnsureCaseInfo(
      page,
      "/tools/discovery/special-interrogatories"
    );

    // Case info should be pre-filled from sessionStorage
    await expect(page.locator("#case_number")).toHaveValue(
      TEST_CASE_INFO.caseNumber,
      { timeout: 10_000 }
    );
    await expect(page.locator("#atty_name")).toHaveValue(
      TEST_CASE_INFO.attorneyName
    );
    await expect(page.locator("#atty_email")).toHaveValue(
      TEST_CASE_INFO.email
    );
  });

  test("party role persists across tools", async ({ page }) => {
    // Set up in DISC-001
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);

    // Ensure state is saved
    await waitForStateSaved(page);

    // Navigate to RFPDs and ensure Case Info step
    await navigateToToolAndEnsureCaseInfo(
      page,
      "/tools/discovery/request-production"
    );

    // Wait for hydration
    await expect(page.locator("#case_number")).toHaveValue(
      TEST_CASE_INFO.caseNumber,
      { timeout: 10_000 }
    );

    // Party role should persist
    const plaintiffBtn = page.getByRole("button", { name: "Plaintiff" });
    await expect(plaintiffBtn).toHaveAttribute("aria-pressed", "true");
  });

  test("claim selections persist across tools", async ({ page }) => {
    // Select claims in DISC-001
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);
    await clickNext(page);

    await selectClaims(page, ["FEHA Discrimination", "FEHA Harassment"]);
    await expect(page.getByText("2 claims selected")).toBeVisible();

    // Ensure state is saved before navigating
    await waitForStateSaved(page);

    // Navigate to RFAs — reset step to 0 first to ensure we land on Case Info
    await navigateToToolAndEnsureCaseInfo(
      page,
      "/tools/discovery/request-admission"
    );

    // Wait for case info to be hydrated
    await expect(page.locator("#case_number")).toHaveValue(
      TEST_CASE_INFO.caseNumber,
      { timeout: 10_000 }
    );

    // Go to claims step
    await clickNext(page);

    // Claims should be pre-selected
    await expect(page.getByText("2 claims selected")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("plaintiff/defendant names persist", async ({ page }) => {
    await page.goto("/tools/discovery/frogs-general");
    await fillCaseInfo(page);

    // Ensure state is saved
    await waitForStateSaved(page);

    // Navigate to another tool
    await navigateToToolAndEnsureCaseInfo(
      page,
      "/tools/discovery/request-admission"
    );

    // Wait for hydration
    await expect(page.locator("#case_number")).toHaveValue(
      TEST_CASE_INFO.caseNumber,
      { timeout: 10_000 }
    );

    // Plaintiff and defendant names should persist
    const plaintiffInput = page
      .locator('input[placeholder="Plaintiff name"]')
      .first();
    await expect(plaintiffInput).toHaveValue(TEST_CASE_INFO.plaintiffName);

    const defendantInput = page
      .locator('input[placeholder="Defendant name"]')
      .first();
    await expect(defendantInput).toHaveValue(TEST_CASE_INFO.defendantName);
  });
});
