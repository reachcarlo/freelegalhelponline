import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/wizard-helpers";

test.describe("Discovery Index Page", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await page.goto("/tools/discovery");
  });

  test("shows page heading", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Discovery Document Generator"
    );
  });

  test("displays all 5 tool cards", async ({ page }) => {
    const links = [
      { href: "/tools/discovery/frogs-general", text: "DISC-001" },
      { href: "/tools/discovery/frogs-employment", text: "DISC-002" },
      { href: "/tools/discovery/special-interrogatories", text: "SROGs" },
      { href: "/tools/discovery/request-production", text: "RFPDs" },
      { href: "/tools/discovery/request-admission", text: "RFAs" },
    ];

    for (const link of links) {
      const card = page.locator(`a[href="${link.href}"]`);
      await expect(card).toBeVisible();
      await expect(card).toContainText(link.text);
    }
  });

  test("tool cards link to correct pages", async ({ page }) => {
    // Click DISC-001 card
    await page.click('a[href="/tools/discovery/frogs-general"]');
    await expect(page).toHaveURL(/\/tools\/discovery\/frogs-general/);
  });

  test("shows format badges (PDF and Word)", async ({ page }) => {
    // PDF badges for FROG tools
    const pdfBadges = page.getByText("PDF", { exact: true });
    await expect(pdfBadges.first()).toBeVisible();

    // Word badges for DOCX tools
    const wordBadges = page.getByText("Word", { exact: true });
    await expect(wordBadges.first()).toBeVisible();
  });

  test("shows breadcrumb navigation", async ({ page }) => {
    const nav = page.locator("nav");
    await expect(nav.first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Home" })).toBeVisible();
  });

  test("shows legal disclaimer", async ({ page }) => {
    await expect(
      page.getByText("These tools generate discovery documents", { exact: false })
    ).toBeVisible();
  });
});
