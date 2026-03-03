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
import { isPdf, validatePdfContent } from "./helpers/doc-validator";

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
    await expect(page.getByText(/[1-9]\d* of \d+ selected/)).toBeVisible({
      timeout: 10_000,
    });
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
});
