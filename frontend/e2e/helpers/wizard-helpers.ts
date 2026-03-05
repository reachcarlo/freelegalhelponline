/**
 * Shared helpers for interacting with discovery wizard UI in E2E tests.
 */

import { type Page, expect } from "@playwright/test";

/** Standard case info for all wizard tests. */
export const TEST_CASE_INFO = {
  caseNumber: "24STCV99999",
  county: "Los Angeles",
  plaintiffName: "Test Plaintiff",
  defendantName: "Test Employer Inc",
  attorneyName: "Test Attorney",
  sbn: "999999",
  address: "100 Test Street",
  cityStateZip: "Los Angeles, CA 90001",
  phone: "(555) 999-0000",
  email: "test@example.com",
} as const;

/**
 * Fill the case info form with standard test data.
 * Assumes the wizard is on the Case Info step.
 */
export async function fillCaseInfo(page: Page): Promise<void> {
  // Wait for case number field to be visible (React hydration complete)
  await page.locator("#case_number").waitFor({ state: "visible", timeout: 5_000 });

  // Case number
  await page.fill("#case_number", TEST_CASE_INFO.caseNumber);

  // County select
  await page.selectOption("#court_county", { label: TEST_CASE_INFO.county });

  // Plaintiff name (first one)
  const plaintiffInput = page.locator('input[placeholder="Plaintiff name"]').first();
  await plaintiffInput.fill(TEST_CASE_INFO.plaintiffName);

  // Defendant name (first one)
  const defendantInput = page.locator('input[placeholder="Defendant name"]').first();
  await defendantInput.fill(TEST_CASE_INFO.defendantName);

  // Attorney info
  await page.fill("#atty_name", TEST_CASE_INFO.attorneyName);
  await page.fill("#atty_sbn", TEST_CASE_INFO.sbn);
  await page.fill("#atty_address", TEST_CASE_INFO.address);
  await page.fill("#atty_csz", TEST_CASE_INFO.cityStateZip);
  await page.fill("#atty_phone", TEST_CASE_INFO.phone);
  await page.fill("#atty_email", TEST_CASE_INFO.email);
}

/**
 * Click the Next button to advance the wizard.
 *
 * Uses `exact: true` to avoid matching the Next.js Dev Tools button
 * which has aria-label "Open Next.js Dev Tools".
 */
export async function clickNext(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Next", exact: true }).click();
}

/**
 * Click the Back button.
 */
export async function clickBack(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Back" }).click();
}

/**
 * Select one or more claim types by clicking their pill buttons.
 */
export async function selectClaims(
  page: Page,
  claims: string[]
): Promise<void> {
  for (const claim of claims) {
    await page.getByRole("button", { name: claim, exact: false }).click();
  }
}

/**
 * Wait for the request bank to load (DocxWizard requests step).
 *
 * The component uses a Unicode ellipsis (…) not three dots.
 */
export async function waitForBankLoaded(page: Page): Promise<void> {
  await expect(
    page.getByText("Loading request bank\u2026")
  ).toBeHidden({ timeout: 15_000 });
}

/**
 * Wait for sections to load (FrogWizard sections step).
 *
 * The component uses a Unicode ellipsis (…) not three dots.
 */
export async function waitForSectionsLoaded(page: Page): Promise<void> {
  await expect(
    page.getByText("Loading sections\u2026")
  ).toBeHidden({ timeout: 15_000 });
}

/**
 * Wait for the Next button to become enabled (canProceed = true).
 */
export async function waitForNextEnabled(page: Page): Promise<void> {
  await expect(
    page.getByRole("button", { name: "Next", exact: true })
  ).toBeEnabled({ timeout: 15_000 });
}

/**
 * Select all requests in the first category (DocxWizard requests step).
 *
 * Uses robust waits instead of instant isVisible() checks.
 */
export async function selectAllInFirstCategory(page: Page): Promise<void> {
  // Wait for at least one category tab to be visible
  const categoryBtn = page
    .locator("button")
    .filter({ hasText: /\d+\/\d+/ })
    .first();
  await expect(categoryBtn).toBeVisible({ timeout: 10_000 });
  await categoryBtn.click();

  // Wait for "Select all in category" button to appear and click it
  const selectAll = page.getByRole("button", {
    name: /Select all in category/i,
  });
  await expect(selectAll).toBeVisible({ timeout: 5_000 });
  await selectAll.click();
}

/**
 * Small delay to let React state settle before navigating away.
 * State no longer persists to sessionStorage — it resets on unmount.
 */
export async function waitForStateSaved(page: Page): Promise<void> {
  // No-op: state resets on navigation now. Kept for backward compat.
}

/**
 * Intercept the generate response and return the buffer.
 *
 * Uses page.route() to intercept the fetch before it reaches the network,
 * capturing the full binary response body. Playwright's response.body()
 * returns 0 bytes for blob/binary responses consumed by the page's fetch().
 */
export async function interceptGenerateResponse(
  page: Page,
  triggerGenerate: () => Promise<void>
): Promise<Buffer> {
  let capturedBody: Buffer | null = null;

  await page.route("**/api/discovery/generate**", async (route) => {
    const response = await route.fetch();
    capturedBody = await response.body();
    await route.fulfill({ response });
  });

  await triggerGenerate();

  // Wait for the UI to confirm download succeeded
  await expect(page.getByText("Downloaded!")).toBeVisible({ timeout: 30_000 });

  // Clean up the route handler
  await page.unroute("**/api/discovery/generate**");

  if (!capturedBody || (capturedBody as Buffer).length === 0) {
    throw new Error("No response body captured from generate endpoint");
  }
  return capturedBody as Buffer;
}
