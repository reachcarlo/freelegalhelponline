import { test, expect, Page } from "@playwright/test";

const MOCK_USER = {
  id: "test-user-id",
  email: "test@lawfirm.com",
  display_name: "Jane Attorney",
  avatar_url: null,
  provider: "google",
  organization: {
    id: "test-org-id",
    name: "Jane Attorney",
    slug: "user-abc12345",
    plan_tier: "individual",
  },
  role: "owner",
};

const MOCK_SESSIONS = {
  sessions: [
    {
      id: "sess-current",
      ip_address: "10.0.0.1",
      browser: "Chrome",
      os: "macOS",
      device: "Desktop",
      created_at: new Date(Date.now() - 3600000).toISOString(),
      last_used_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 604800000).toISOString(),
      is_current: true,
    },
    {
      id: "sess-other-1",
      ip_address: "192.168.1.5",
      browser: "Firefox",
      os: "Windows",
      device: "Desktop",
      created_at: new Date(Date.now() - 86400000).toISOString(),
      last_used_at: new Date(Date.now() - 7200000).toISOString(),
      expires_at: new Date(Date.now() + 604800000).toISOString(),
      is_current: false,
    },
    {
      id: "sess-other-2",
      ip_address: "172.16.0.10",
      browser: "Safari",
      os: "iOS",
      device: "Mobile",
      created_at: new Date(Date.now() - 172800000).toISOString(),
      last_used_at: new Date(Date.now() - 43200000).toISOString(),
      expires_at: new Date(Date.now() + 604800000).toISOString(),
      is_current: false,
    },
  ],
};

async function setupAuth(page: Page) {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    })
  );

  await page.route("**/api/auth/sessions", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_SESSIONS),
      });
    }
    // DELETE (revoke all others)
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", revoked_count: 2 }),
    });
  });

  await page.route("**/api/auth/sessions/*", (route) => {
    if (route.request().method() === "DELETE") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    }
    return route.continue();
  });

  await page.context().addCookies([
    {
      name: "access_token",
      value: "mock-access-token",
      domain: "localhost",
      path: "/",
    },
  ]);
}

// ── Account Page ──────────────────────────────────────────────

test.describe("Account Page", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("shows profile information", async ({ page }) => {
    await page.goto("/account");

    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();
    await expect(page.getByText("Jane Attorney")).toBeVisible();
    await expect(page.getByText("test@lawfirm.com")).toBeVisible();
    await expect(page.getByText("Google")).toBeVisible();
  });

  test("redirects unauthenticated users to login", async ({ page }) => {
    await page.unrouteAll();
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authentication required" }),
      })
    );

    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?redirect=/);
  });

  test("has back to home link", async ({ page }) => {
    await page.goto("/account");

    const backLink = page.getByRole("link", { name: "Back to home" });
    await expect(backLink).toBeVisible();
    await expect(backLink).toHaveAttribute("href", "/");
  });
});

// ── Active Sessions ───────────────────────────────────────────

test.describe("Active Sessions", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("lists all active sessions", async ({ page }) => {
    await page.goto("/account");

    await expect(
      page.getByRole("heading", { name: "Active Sessions" })
    ).toBeVisible();

    await expect(page.getByText("Chrome on macOS")).toBeVisible();
    await expect(page.getByText("Firefox on Windows")).toBeVisible();
    await expect(page.getByText("Safari on iOS")).toBeVisible();
  });

  test("marks current session with badge", async ({ page }) => {
    await page.goto("/account");

    await expect(page.getByText("Current")).toBeVisible();
  });

  test("shows revoke button on non-current sessions", async ({ page }) => {
    await page.goto("/account");

    const revokeButtons = page.getByRole("button", { name: "Revoke", exact: true });
    await expect(revokeButtons).toHaveCount(2); // 2 non-current sessions
  });

  test("shows revoke all others button", async ({ page }) => {
    await page.goto("/account");

    await expect(
      page.getByRole("button", { name: "Revoke all other sessions" })
    ).toBeVisible();
  });

  test("revokes individual session", async ({ page }) => {
    await page.goto("/account");

    // Click first Revoke button (for Firefox session)
    const revokeButtons = page.getByRole("button", { name: "Revoke" });
    await revokeButtons.first().click();

    // Should remove that session from the list
    await expect(page.getByText("Firefox on Windows")).not.toBeVisible();
  });

  test("revokes all other sessions", async ({ page }) => {
    await page.goto("/account");

    await page
      .getByRole("button", { name: "Revoke all other sessions" })
      .click();

    // Both non-current sessions should be removed
    await expect(page.getByText("Firefox on Windows")).not.toBeVisible();
    await expect(page.getByText("Safari on iOS")).not.toBeVisible();

    // Current session should remain
    await expect(page.getByText("Chrome on macOS")).toBeVisible();
  });

  test("shows IP addresses", async ({ page }) => {
    await page.goto("/account");

    await expect(page.getByText("10.0.0.1")).toBeVisible();
    await expect(page.getByText("192.168.1.5")).toBeVisible();
  });
});

// ── User Menu Account Link ────────────────────────────────────

test.describe("User Menu Account Link", () => {
  test("shows Account link in user menu dropdown", async ({ page }) => {
    await setupAuth(page);
    await page.goto("/");

    await page.getByRole("button", { name: "User menu" }).click();

    const accountLink = page.getByRole("link", { name: "Account" });
    await expect(accountLink).toBeVisible();
    await expect(accountLink).toHaveAttribute("href", "/account");
  });
});
