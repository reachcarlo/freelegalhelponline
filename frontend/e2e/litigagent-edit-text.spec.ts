import { test, expect, Page } from "@playwright/test";
import path from "path";
import fs from "fs";
import os from "os";

function createTempFile(name: string, content: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "litigagent-edit-"));
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

async function uploadFileAndWaitReady(page: Page, filePath: string): Promise<void> {
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /upload files/i }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(filePath);
  await expect(page.locator('[aria-label="Ready"]')).toBeVisible({ timeout: 15_000 });
}

test.describe("LITIGAGENT Editable Text Panel (L2.1)", () => {
  test("text area is editable for ready files", async ({ page }) => {
    await createCaseAndNavigate(page, "Edit Text Test");
    const tempFile = createTempFile("editable.txt", "Original content here.");
    await uploadFileAndWaitReady(page, tempFile);

    // The textarea should contain the extracted text
    const textarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textarea).toBeVisible({ timeout: 10_000 });
    await expect(textarea).toHaveValue("Original content here.");

    // Should be editable
    await textarea.click();
    await textarea.fill("Modified content here.");
    await expect(textarea).toHaveValue("Modified content here.");

    fs.unlinkSync(tempFile);
  });

  test("shows 'Editing...' indicator while typing", async ({ page }) => {
    await createCaseAndNavigate(page, "Editing Indicator Test");
    const tempFile = createTempFile("editing-indicator.txt", "Some text.");
    await uploadFileAndWaitReady(page, tempFile);

    const textarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Type something to trigger the unsaved state
    await textarea.click();
    await textarea.fill("Some text. Plus edits.");

    // The "Editing..." indicator should appear
    await expect(page.getByText("Editing...")).toBeVisible();

    fs.unlinkSync(tempFile);
  });

  test("debounced auto-save triggers after typing stops", async ({ page }) => {
    await createCaseAndNavigate(page, "Auto Save Test");
    const tempFile = createTempFile("autosave.txt", "Before editing.");
    await uploadFileAndWaitReady(page, tempFile);

    const textarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Edit text
    await textarea.click();
    await textarea.fill("After editing.");

    // Wait for debounce (2s) + save to complete — "Saving..." should appear
    await expect(page.getByText("Saving...")).toBeVisible({ timeout: 5_000 });

    // Then "Saved" should appear
    await expect(page.getByText("Saved")).toBeVisible({ timeout: 10_000 });

    fs.unlinkSync(tempFile);
  });

  test("edited text persists after page reload", async ({ page }) => {
    await createCaseAndNavigate(page, "Persist Edit Test");
    const tempFile = createTempFile("persist.txt", "Original text for persistence.");
    await uploadFileAndWaitReady(page, tempFile);

    const textarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Edit and wait for save
    await textarea.click();
    await textarea.fill("Edited text for persistence.");
    await expect(page.getByText("Saved")).toBeVisible({ timeout: 10_000 });

    // Reload the page
    await page.reload();

    // The textarea should show the edited text
    const reloadedTextarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(reloadedTextarea).toBeVisible({ timeout: 15_000 });
    await expect(reloadedTextarea).toHaveValue("Edited text for persistence.");

    fs.unlinkSync(tempFile);
  });

  test("'Saved' indicator disappears after a few seconds", async ({ page }) => {
    await createCaseAndNavigate(page, "Saved Fade Test");
    const tempFile = createTempFile("saved-fade.txt", "Fade test content.");
    await uploadFileAndWaitReady(page, tempFile);

    const textarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Edit and wait for save
    await textarea.click();
    await textarea.fill("Updated fade test.");
    await expect(page.getByText("Saved")).toBeVisible({ timeout: 10_000 });

    // "Saved" should disappear after ~3 seconds
    await expect(page.getByText("Saved")).not.toBeVisible({ timeout: 6_000 });

    fs.unlinkSync(tempFile);
  });

  test("multiple files can be edited independently", async ({ page }) => {
    await createCaseAndNavigate(page, "Multi Edit Test");

    const files = [
      createTempFile("file-a.txt", "Content A original."),
      createTempFile("file-b.txt", "Content B original."),
    ];

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /upload files/i }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(files);

    // Wait for both files ready
    await expect(page.getByText("Content A original.")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Content B original.")).toBeVisible({ timeout: 15_000 });

    // Get both textareas
    const textareas = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textareas).toHaveCount(2);

    // Edit first file
    await textareas.nth(0).click();
    await textareas.nth(0).fill("Content A edited.");

    // Edit second file
    await textareas.nth(1).click();
    await textareas.nth(1).fill("Content B edited.");

    // Both should show their edited values
    await expect(textareas.nth(0)).toHaveValue("Content A edited.");
    await expect(textareas.nth(1)).toHaveValue("Content B edited.");

    // Wait for saves to complete
    await page.waitForTimeout(3000);

    // Reload and verify both edits persisted
    await page.reload();
    const reloadedAreas = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(reloadedAreas.nth(0)).toBeVisible({ timeout: 15_000 });
    await expect(reloadedAreas.nth(0)).toHaveValue("Content A edited.");
    await expect(reloadedAreas.nth(1)).toHaveValue("Content B edited.");

    files.forEach((f) => fs.unlinkSync(f));
  });

  test("rapid edits debounce correctly (only last value saved)", async ({ page }) => {
    await createCaseAndNavigate(page, "Debounce Test");
    const tempFile = createTempFile("debounce.txt", "Initial.");
    await uploadFileAndWaitReady(page, tempFile);

    const textarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Type rapidly — each keystroke resets the debounce
    await textarea.click();
    await textarea.fill("First edit");
    await page.waitForTimeout(500);
    await textarea.fill("Second edit");
    await page.waitForTimeout(500);
    await textarea.fill("Final edit");

    // Wait for the debounce and save
    await expect(page.getByText("Saved")).toBeVisible({ timeout: 10_000 });

    // Reload — should have the final value
    await page.reload();
    const reloaded = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(reloaded).toBeVisible({ timeout: 15_000 });
    await expect(reloaded).toHaveValue("Final edit");

    fs.unlinkSync(tempFile);
  });

  test("textarea uses monospace font", async ({ page }) => {
    await createCaseAndNavigate(page, "Font Test");
    const tempFile = createTempFile("font-test.txt", "Monospace check.");
    await uploadFileAndWaitReady(page, tempFile);

    const textarea = page.locator('textarea[aria-label="Editable extracted text"]');
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Verify the textarea has the font-mono class
    await expect(textarea).toHaveClass(/font-mono/);

    fs.unlinkSync(tempFile);
  });
});
