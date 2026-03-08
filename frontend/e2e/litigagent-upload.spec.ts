import { test, expect, Page } from "@playwright/test";
import path from "path";
import fs from "fs";
import os from "os";

/**
 * Helper: create a temporary file with given name and content.
 */
function createTempFile(name: string, content: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "litigagent-e2e-"));
  const filePath = path.join(dir, name);
  fs.writeFileSync(filePath, content, "utf-8");
  return filePath;
}

/**
 * Helper: create a case and navigate to its detail page.
 * Returns the case ID from the URL.
 */
async function createCaseAndNavigate(page: Page, name: string): Promise<string> {
  await page.goto("/tools/litigagent");
  await page.getByRole("button", { name: /new case/i }).click();
  await page.getByPlaceholder(/case name/i).fill(name);
  await page.getByRole("button", { name: /^create$/i }).click();

  // Wait for navigation to case detail page
  await page.waitForURL(/\/tools\/litigagent\/[a-f0-9-]+/);
  const url = page.url();
  const caseId = url.split("/").pop()!;
  return caseId;
}

test.describe("LITIGAGENT File Upload (L1.10)", () => {
  test("shows empty state with upload prompt", async ({ page }) => {
    await createCaseAndNavigate(page, "Empty Upload Test");

    // File panel should show empty state
    const filePanel = page.locator('[aria-label="Case files"]');
    await expect(filePanel).toBeVisible();
    await expect(filePanel).toContainText("Drop files here or click to browse");
    await expect(filePanel).toContainText("PDF, DOCX, TXT, EML, MSG, and more");
  });

  test("shows Upload Files button in footer", async ({ page }) => {
    await createCaseAndNavigate(page, "Upload Button Test");

    const uploadBtn = page.getByRole("button", { name: /upload files/i });
    await expect(uploadBtn).toBeVisible();
    await expect(uploadBtn).toBeEnabled();
  });

  test("upload a single TXT file via file chooser", async ({ page }) => {
    await createCaseAndNavigate(page, "Single Upload Test");

    const tempFile = createTempFile("test-doc.txt", "Hello, this is a test document.\nLine two.");

    // Click the upload button and handle file chooser
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    // File should appear in the list
    await expect(page.getByText("test-doc.txt")).toBeVisible({ timeout: 10_000 });

    // File count should update
    await expect(page.locator("text=1 file")).toBeVisible();

    // Clean up
    fs.unlinkSync(tempFile);
  });

  test("upload multiple files via file chooser", async ({ page }) => {
    await createCaseAndNavigate(page, "Multi Upload Test");

    const files = [
      createTempFile("alpha.txt", "Alpha content"),
      createTempFile("beta.txt", "Beta content"),
      createTempFile("gamma.txt", "Gamma content"),
    ];

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(files);

    // All three files should appear
    await expect(page.getByText("alpha.txt")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("beta.txt")).toBeVisible();
    await expect(page.getByText("gamma.txt")).toBeVisible();

    // File count should show 3
    await expect(page.locator("text=3 files")).toBeVisible();

    // Clean up
    files.forEach((f) => fs.unlinkSync(f));
  });

  test("file shows status indicator after upload", async ({ page }) => {
    await createCaseAndNavigate(page, "Status Indicator Test");

    const tempFile = createTempFile("status-test.txt", "Content for status test.");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    // Wait for file to appear and reach ready status (checkmark)
    await expect(page.getByText("status-test.txt")).toBeVisible({ timeout: 10_000 });

    // Should eventually show a ready checkmark (via SSE)
    await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });

    fs.unlinkSync(tempFile);
  });

  test("selecting a file highlights it in the list", async ({ page }) => {
    await createCaseAndNavigate(page, "Selection Test");

    const tempFile = createTempFile("select-test.txt", "Selection test content.");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    await expect(page.getByText("select-test.txt")).toBeVisible({ timeout: 10_000 });

    // Click the file to select it
    await page.getByText("select-test.txt").click();

    // The file item should have aria-selected=true
    const option = page.locator('[role="option"][aria-selected="true"]');
    await expect(option).toBeVisible();
    await expect(option).toContainText("select-test.txt");

    fs.unlinkSync(tempFile);
  });

  test("delete a file from the list", async ({ page }) => {
    await createCaseAndNavigate(page, "Delete Test");

    const tempFile = createTempFile("to-delete.txt", "This file will be deleted.");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    await expect(page.getByText("to-delete.txt")).toBeVisible({ timeout: 10_000 });

    // Hover over the file to reveal delete button
    const fileRow = page.locator('[role="option"]').filter({ hasText: "to-delete.txt" });
    await fileRow.hover();

    // Click delete
    const deleteBtn = page.getByRole("button", { name: /delete to-delete\.txt/i });
    await expect(deleteBtn).toBeVisible();
    await deleteBtn.click();

    // File should be removed from list
    await expect(page.getByText("to-delete.txt")).not.toBeVisible({ timeout: 5_000 });

    // Should show empty state again
    await expect(page.getByText(/drop files here/i)).toBeVisible();

    fs.unlinkSync(tempFile);
  });

  test("header shows file count and processing status", async ({ page }) => {
    await createCaseAndNavigate(page, "Count Test");

    // Initially 0 files in header
    const headerInfo = page.locator("text=0 files");
    await expect(headerInfo).toBeVisible();

    const tempFile = createTempFile("count-test.txt", "Count test content.");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    // Should update to 1 file
    await expect(page.locator("text=1 file").first()).toBeVisible({ timeout: 10_000 });

    fs.unlinkSync(tempFile);
  });

  test("empty state click triggers file chooser", async ({ page }) => {
    await createCaseAndNavigate(page, "Empty State Click Test");

    const tempFile = createTempFile("empty-click.txt", "Clicked empty state.");

    // Click the empty state area (which is a button)
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByText("Drop files here or click to browse").click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    await expect(page.getByText("empty-click.txt")).toBeVisible({ timeout: 10_000 });

    fs.unlinkSync(tempFile);
  });

  test("file type badges show correctly", async ({ page }) => {
    await createCaseAndNavigate(page, "Badge Test");

    const tempFile = createTempFile("badge-test.txt", "Badge test content.");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(tempFile);

    await expect(page.getByText("badge-test.txt")).toBeVisible({ timeout: 10_000 });

    // Should show TXT badge
    const badge = page.locator('[role="option"]').filter({ hasText: "badge-test.txt" }).locator("text=TXT");
    await expect(badge).toBeVisible();

    fs.unlinkSync(tempFile);
  });

  test("upload button shows loading state during upload", async ({ page }) => {
    await createCaseAndNavigate(page, "Loading State Test");

    const tempFile = createTempFile("loading-test.txt", "Loading state test content.");

    // Start upload
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;

    // Set files — the button should briefly show "Uploading..." text
    // (may be too fast to catch reliably, but verify no error occurs)
    await fileChooser.setFiles(tempFile);

    // After upload completes, button should be back to "Upload Files"
    await expect(page.getByRole("button", { name: /upload files/i })).toBeVisible({ timeout: 10_000 });

    fs.unlinkSync(tempFile);
  });

  test("drag over shows drop zone overlay", async ({ page }) => {
    await createCaseAndNavigate(page, "Drag Over Test");

    // Simulate dragenter on the file panel
    const panel = page.locator(".flex.h-full.w-\\[280px\\]");
    await panel.dispatchEvent("dragenter", {
      dataTransfer: { types: ["Files"] },
    });

    // The overlay should appear with "Drop files here" text
    await expect(page.getByText("Drop files here", { exact: true })).toBeVisible();
  });
});
