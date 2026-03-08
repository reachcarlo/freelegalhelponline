import { test, expect } from "@playwright/test";
import {
  fillCaseInfo,
  clickNext,
  selectClaims,
  waitForSectionsLoaded,
  waitForNextEnabled,
  interceptGenerateResponse,
  TEST_CASE_INFO,
} from "./helpers/wizard-helpers";
import {
  isPdf,
  validatePdfContent,
  getPdfFieldMap,
  getPdfCheckboxes,
} from "./helpers/doc-validator";

test.describe("DISC-002 (Form Interrogatories - Employment)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tools/discovery/frogs-employment");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Form Interrogatories"
    );
  });

  test("wizard shows Case Info step", async ({ page }) => {
    await expect(page.locator("#case_number")).toBeVisible();
  });

  test("shows responding party entity checkbox", async ({ page }) => {
    await expect(
      page.getByText("Responding party is a business entity")
    ).toBeVisible();
  });

  test("can advance through claims to sections", async ({ page }) => {
    await fillCaseInfo(page);
    // Check entity checkbox
    await page.getByText("Responding party is a business entity").click();
    await clickNext(page);

    await selectClaims(page, ["FEHA Harassment"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);

    // Should see employment-specific sections
    await expect(page.getByText(/\d+ of \d+ selected/)).toBeVisible();
  });

  test("full workflow generates valid PDF", async ({ page }) => {
    // Case Info
    await fillCaseInfo(page);
    await clickNext(page);

    // Claims
    await selectClaims(page, ["Wrongful Termination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);

    // Sections — auto-selected, wait for selection to appear + Next enabled
    await expect(page.getByText(/\d+ of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
    // If no sections were auto-selected, click "Select all"
    const selText = await page.getByText(/\d+ of \d+ selected/).textContent();
    if (selText?.startsWith("0 of")) {
      await page.getByRole("button", { name: "Select all" }).click();
    }
    await waitForNextEnabled(page);
    await clickNext(page);

    // Review
    await expect(page.getByText("Review Before Generating")).toBeVisible();
    await clickNext(page);

    // Generate
    await expect(page.getByText("Ready to Generate")).toBeVisible();

    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download PDF/i })
        .click();
    });

    expect(isPdf(buffer)).toBe(true);
    expect(buffer.length).toBeGreaterThan(1000);

    await validatePdfContent(buffer, {
      containsText: [TEST_CASE_INFO.caseNumber],
    });
  });

  test("PDF contains all case info in correct fields", async ({ page }) => {
    await fillCaseInfo(page);
    await clickNext(page);
    await selectClaims(page, ["Wrongful Termination"]);
    await clickNext(page);
    await waitForSectionsLoaded(page);
    await expect(page.getByText(/\d+ of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
    // If no sections were auto-selected, click "Select all"
    const selText = await page.getByText(/\d+ of \d+ selected/).textContent();
    if (selText?.startsWith("0 of")) {
      await page.getByRole("button", { name: "Select all" }).click();
    }
    await waitForNextEnabled(page);
    await clickNext(page);
    await clickNext(page);

    const buffer = await interceptGenerateResponse(page, async () => {
      await page
        .getByRole("button", { name: /Generate & Download PDF/i })
        .click();
    });

    const fields = await getPdfFieldMap(buffer);

    // Case number
    expect(fields["TextField1[0]"]).toBe(TEST_CASE_INFO.caseNumber);
    // Attorney block (multi-line)
    expect(fields["AttyCity_ft[0]"]).toContain(TEST_CASE_INFO.attorneyName);
    expect(fields["AttyCity_ft[0]"]).toContain(TEST_CASE_INFO.sbn);
    expect(fields["AttyCity_ft[0]"]).toContain(TEST_CASE_INFO.address);
    // Phone + email
    expect(fields["Phone_ft[0]"]).toBe(TEST_CASE_INFO.phone);
    expect(fields["Email_ft[0]"]).toBe(TEST_CASE_INFO.email);
    // Answering party
    expect(fields["TextField2[0]"]).toBe(TEST_CASE_INFO.defendantName);

    // At least one section checkbox should be checked
    const checked = await getPdfCheckboxes(buffer);
    expect(checked.length).toBeGreaterThan(0);
  });
});
