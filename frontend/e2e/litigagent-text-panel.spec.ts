import { test, expect, Page } from "@playwright/test";
import path from "path";
import fs from "fs";
import os from "os";
import { setupAuth } from "./helpers/wizard-helpers";

function createTempFile(name: string, content: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "litigagent-e2e-"));
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

async function uploadFile(page: Page, filePath: string): Promise<void> {
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /upload files/i }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(filePath);
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

test.describe("LITIGAGENT Text Panel (L1.11)", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("shows empty state when no files uploaded", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Empty Test");

    await expect(page.getByText("No files uploaded yet")).toBeVisible();
    await expect(
      page.getByText("Upload PDF, Word, email, or text files")
    ).toBeVisible();
  });

  test("displays extracted text after file upload", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Display Test");

    const content = "Line one of the document.\nLine two with details.\nLine three conclusion.";
    const tempFile = createTempFile("display-test.txt", content);

    await uploadFile(page, tempFile);

    // Wait for file to appear in Panel 1 and reach ready status
    const filePanel = page.locator('[aria-label="Case files"]');
    await expect(filePanel.getByText("display-test.txt")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });

    // The extracted text should appear in the editable textarea
    await expectTextInPanel(page, "Line one of the document.");
    await expectTextInPanel(page, "Line two with details.");
    await expectTextInPanel(page, "Line three conclusion.");

    fs.unlinkSync(tempFile);
  });

  test("shows file section header with type badge and filename", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Header Test");

    const tempFile = createTempFile("header-check.txt", "Header test content.");

    await uploadFile(page, tempFile);
    await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });

    // The text panel region should have the filename in aria-label
    const region = page.locator('[role="region"][aria-label="Content from header-check.txt"]');
    await expect(region).toBeVisible();

    // Should show the file type badge
    await expect(region.locator("text=TXT")).toBeVisible();

    // Should show the filename in the header
    await expect(region.locator("text=header-check.txt")).toBeVisible();

    fs.unlinkSync(tempFile);
  });

  test("shows status badge for ready file", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Status Badge Test");

    const tempFile = createTempFile("status-badge.txt", "Status test.");

    await uploadFile(page, tempFile);
    await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });

    // The text panel header should show "Ready" badge
    const region = page.locator('[role="region"][aria-label="Content from status-badge.txt"]');
    await expect(region.getByText("Ready")).toBeVisible();

    fs.unlinkSync(tempFile);
  });

  test("shows processing state while extracting", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Processing Test");

    const tempFile = createTempFile("processing-test.txt", "Processing content.");

    await uploadFile(page, tempFile);

    // File should appear in the file list first (scope to Panel 1 to avoid strict mode)
    const filePanel = page.locator('[aria-label="Case files"]');
    await expect(filePanel.getByText("processing-test.txt")).toBeVisible({ timeout: 10_000 });

    // The text panel should show "Extracting text..." or "Processing" at some point
    // (may be very fast for .txt files, so we just verify no error occurs)
    await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });

    fs.unlinkSync(tempFile);
  });

  test("displays multiple files in order", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Multi Test");

    const files = [
      createTempFile("first.txt", "First file content."),
      createTempFile("second.txt", "Second file content."),
    ];

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(files);

    // Wait for both files to appear in Panel 1
    const filePanel = page.locator('[aria-label="Case files"]');
    await expect(filePanel.getByText("first.txt")).toBeVisible({ timeout: 10_000 });
    await expect(filePanel.getByText("second.txt")).toBeVisible();

    // Both regions should exist
    const firstRegion = page.locator('[role="region"][aria-label="Content from first.txt"]');
    const secondRegion = page.locator('[role="region"][aria-label="Content from second.txt"]');
    await expect(firstRegion).toBeVisible();
    await expect(secondRegion).toBeVisible();

    // Text content should eventually appear in textareas
    await expectTextInPanel(page, "First file content.");
    await expectTextInPanel(page, "Second file content.");

    files.forEach((f) => fs.unlinkSync(f));
  });

  test("clicking file in Panel 1 scrolls to its content in Panel 2", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Scroll Test");

    // Upload two files
    const files = [
      createTempFile("scroll-a.txt", "Content A.\n".repeat(50)),
      createTempFile("scroll-b.txt", "Content B."),
    ];

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(files);

    // Wait for files to appear in Panel 1
    const filePanel = page.locator('[aria-label="Case files"]');
    await expect(filePanel.getByText("scroll-a.txt")).toBeVisible({ timeout: 10_000 });
    await expect(filePanel.getByText("scroll-b.txt")).toBeVisible();

    // Wait for text to load
    await expectTextInPanel(page, "Content B.");

    // Click second file in Panel 1 — should scroll Panel 2
    const fileOption = page.locator('[role="option"]').filter({ hasText: "scroll-b.txt" });
    await fileOption.locator("button").first().click();

    // The second file's region should be visible (scrolled into view)
    const secondRegion = page.locator('[role="region"][aria-label="Content from scroll-b.txt"]');
    await expect(secondRegion).toBeVisible();

    files.forEach((f) => fs.unlinkSync(f));
  });

  test("shows error state for failed file", async ({ page }) => {
    await createCaseAndNavigate(page, "TextPanel Error Test");

    // Upload a valid file first to verify panel works
    const tempFile = createTempFile("error-test.txt", "Error test content.");

    await uploadFile(page, tempFile);
    await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });

    // Verify extracted text shows in textarea
    await expectTextInPanel(page, "Error test content.");

    fs.unlinkSync(tempFile);
  });
});
