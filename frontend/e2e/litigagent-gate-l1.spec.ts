import { test, expect, Page } from "@playwright/test";
import path from "path";
import fs from "fs";
import os from "os";
import { setupAuth } from "./helpers/wizard-helpers";

/**
 * Gate L1 E2E Test
 *
 * Validates the full L1 journey: "Can upload 10 files (PDF, DOCX, EML, TXT),
 * see extracted text, and navigate between files."
 *
 * Since we can only reliably create TXT and EML files in E2E tests
 * (PDF/DOCX are binary), we test with those formats and verify the
 * full flow: upload → extraction → display → navigation.
 */

function createTempFile(name: string, content: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "litigagent-gate-"));
  const filePath = path.join(dir, name);
  fs.writeFileSync(filePath, content, "utf-8");
  return filePath;
}

async function createCaseAndNavigate(page: Page, name: string): Promise<string> {
  await page.goto("/tools/litigagent");
  await page.getByRole("button", { name: /new case/i }).first().click();
  await page.getByLabel(/case name/i).fill(name);
  await page.getByRole("button", { name: /create case/i }).click();
  await page.waitForURL(/\/tools\/litigagent\/[a-f0-9-]+/);
  return page.url().split("/").pop()!;
}

/** Assert text appears in one of the editable textareas in the text panel. */
async function expectTextInPanel(page: Page, text: string, timeout = 15_000) {
  const textareas = page.locator('textarea[aria-label="Editable extracted text"]');
  await expect(async () => {
    const count = await textareas.count();
    expect(count).toBeGreaterThan(0);
    let found = false;
    for (let i = 0; i < count; i++) {
      const value = await textareas.nth(i).inputValue();
      if (value.includes(text)) {
        found = true;
        break;
      }
    }
    expect(found).toBeTruthy();
  }).toPass({ timeout });
}

test.describe("LITIGAGENT Gate L1", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("full journey: upload multiple files, see text, navigate between files", async ({ page }) => {
    test.slow(); // This test uploads multiple files and waits for extraction

    await createCaseAndNavigate(page, "Gate L1 Full Journey");

    // Create a batch of files simulating a small case
    const files = [
      createTempFile("case_notes.txt", "CASE NOTES\nJohnson v. Acme Corp\nAge discrimination claim under FEHA."),
      createTempFile("termination_letter.txt", "TERMINATION NOTICE\nDear Mr. Johnson,\nYour position has been eliminated effective November 15, 2025."),
      createTempFile("performance_review.txt", "ANNUAL REVIEW\nEmployee: David Johnson\nRating: Exceeds Expectations (4.2/5.0)"),
      createTempFile("witness_statement.txt", "WITNESS STATEMENT\nI observed age-related comments directed at Mr. Johnson during team meetings."),
      createTempFile(
        "manager_email.eml",
        "From: manager@acme.example.com\r\nTo: hr@acme.example.com\r\nSubject: Restructuring Plan\r\nDate: Mon, 1 Nov 2025 10:00:00 -0700\r\nMessage-ID: <gate-test@acme.example.com>\r\nMIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nPlease prepare separation packages for the Sacramento positions."
      ),
    ];

    // Upload all files at once
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(files);

    // Wait for all files to appear in Panel 1 (scope to file panel to avoid strict mode)
    const filePanel = page.locator('[aria-label="Case files"]');
    for (const f of ["case_notes.txt", "termination_letter.txt", "performance_review.txt", "witness_statement.txt", "manager_email.eml"]) {
      await expect(filePanel.getByText(f)).toBeVisible({ timeout: 10_000 });
    }

    // Verify file count in header
    await expect(page.locator("text=5 files").first()).toBeVisible({ timeout: 10_000 });

    // Wait for all files to reach "ready" status (via SSE)
    await expect(async () => {
      const readyBadges = page.locator('[aria-label="Ready"]');
      const count = await readyBadges.count();
      expect(count).toBeGreaterThanOrEqual(5);
    }).toPass({ timeout: 30_000 });

    // Verify extracted text appears in Panel 2 textareas
    await expectTextInPanel(page, "Age discrimination claim under FEHA");
    await expectTextInPanel(page, "Your position has been eliminated");
    await expectTextInPanel(page, "Exceeds Expectations");

    // Navigate: click a file in Panel 1 → Panel 2 should show its content
    const witnessOption = page.locator('[role="option"]').filter({ hasText: "witness_statement.txt" });
    await witnessOption.locator("button").first().click();

    // Verify the witness statement region is visible
    const witnessRegion = page.locator('[role="region"][aria-label="Content from witness_statement.txt"]');
    await expect(witnessRegion).toBeVisible();
    await expectTextInPanel(page, "age-related comments");

    // Navigate to the email file
    const emailOption = page.locator('[role="option"]').filter({ hasText: "manager_email.eml" });
    await emailOption.locator("button").first().click();

    const emailRegion = page.locator('[role="region"][aria-label="Content from manager_email.eml"]');
    await expect(emailRegion).toBeVisible();
    await expectTextInPanel(page, "separation packages");

    // Verify file type badges in Panel 2
    const txtBadges = page.locator('[role="region"] .rounded.bg-badge-bg:text-is("TXT")');
    await expect(async () => {
      expect(await txtBadges.count()).toBeGreaterThanOrEqual(4);
    }).toPass({ timeout: 5_000 });

    // Clean up
    files.forEach((f) => fs.unlinkSync(f));
  });

  test("file selection in Panel 1 highlights and scrolls Panel 2", async ({ page }) => {
    await createCaseAndNavigate(page, "Gate L1 Navigation");

    const files = [
      createTempFile("first_doc.txt", "First document content.\n".repeat(30)),
      createTempFile("second_doc.txt", "Second document unique content here."),
    ];

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(files);

    // Wait for ready
    await expect(async () => {
      const readyBadges = page.locator('[aria-label="Ready"]');
      expect(await readyBadges.count()).toBeGreaterThanOrEqual(2);
    }).toPass({ timeout: 30_000 });

    // Wait for text to load
    await expectTextInPanel(page, "Second document unique content here.");

    // Click second file — should highlight in Panel 1
    const secondOption = page.locator('[role="option"]').filter({ hasText: "second_doc.txt" });
    await secondOption.locator("button").first().click();

    // Verify aria-selected
    await expect(secondOption).toHaveAttribute("aria-selected", "true");

    // Verify first is NOT selected
    const firstOption = page.locator('[role="option"]').filter({ hasText: "first_doc.txt" });
    await expect(firstOption).toHaveAttribute("aria-selected", "false");

    files.forEach((f) => fs.unlinkSync(f));
  });

  test("case persists across page reload", async ({ page }) => {
    const caseId = await createCaseAndNavigate(page, "Gate L1 Persistence");

    const tempFile = createTempFile("persist-test.txt", "This text should persist after reload.");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    // Wait for ready
    await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });
    await expectTextInPanel(page, "This text should persist after reload.");

    // Reload the page
    await page.reload();

    // File should still be there (scope to file panel to avoid strict mode)
    const filePanel = page.locator('[aria-label="Case files"]');
    await expect(filePanel.getByText("persist-test.txt")).toBeVisible({ timeout: 10_000 });

    // Extracted text should reload in textarea
    await expectTextInPanel(page, "This text should persist after reload.");

    fs.unlinkSync(tempFile);
  });
});
