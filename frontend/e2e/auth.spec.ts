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

/** Set up an authenticated session by mocking /api/auth/me and setting cookie. */
async function loginAs(page: Page) {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    })
  );

  await page.context().addCookies([
    {
      name: "access_token",
      value: "mock-access-token",
      domain: "localhost",
      path: "/",
    },
  ]);
}

// ── Login Page ──────────────────────────────────────────────────

test.describe("Login Page", () => {
  test.beforeEach(async ({ page }) => {
    // Ensure unauthenticated state
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authentication required" }),
      })
    );
  });

  test("renders Google and Microsoft sign-in buttons", async ({ page }) => {
    await page.goto("/login");

    await expect(
      page.getByRole("heading", { name: "Employee Help" })
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Sign in with Google" })
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Sign in with Microsoft" })
    ).toBeVisible();
  });

  test("Google button links to OAuth endpoint", async ({ page }) => {
    await page.goto("/login");

    const googleLink = page.getByRole("link", { name: "Sign in with Google" });
    await expect(googleLink).toHaveAttribute("href", "/api/auth/google/login");
  });

  test("Microsoft button links to OAuth endpoint", async ({ page }) => {
    await page.goto("/login");

    const msLink = page.getByRole("link", {
      name: "Sign in with Microsoft",
    });
    await expect(msLink).toHaveAttribute("href", "/api/auth/microsoft/login");
  });

  test("shows error message for oauth_denied", async ({ page }) => {
    await page.goto("/login?error=oauth_denied");

    await expect(page.getByText("Sign-in was cancelled")).toBeVisible();
  });

  test("shows error message for auth_failed", async ({ page }) => {
    await page.goto("/login?error=auth_failed");

    await expect(page.getByText("Authentication failed")).toBeVisible();
  });

  test("shows error message for invalid_state", async ({ page }) => {
    await page.goto("/login?error=invalid_state");

    await expect(page.getByText("Sign-in session expired")).toBeVisible();
  });

  test("shows generic error for unknown error code", async ({ page }) => {
    await page.goto("/login?error=unknown_code");

    await expect(page.getByText("An error occurred")).toBeVisible();
  });

  test("shows terms and privacy links", async ({ page }) => {
    await page.goto("/login");

    const main = page.getByRole("main");
    await expect(main.getByRole("link", { name: "Terms of Service" })).toBeVisible();
    await expect(main.getByRole("link", { name: "Privacy Policy" })).toBeVisible();
  });

  test("shows trust signal about passwords", async ({ page }) => {
    await page.goto("/login");

    await expect(
      page.getByText("We never store your password")
    ).toBeVisible();
  });

  test("redirects authenticated user away from login", async ({ page }) => {
    // Override: authenticated
    await page.unrouteAll();
    await loginAs(page);

    await page.goto("/login");

    await page.waitForURL("/");
  });
});

// ── Middleware Redirect ─────────────────────────────────────────

test.describe("Middleware Redirect", () => {
  test("redirects unauthenticated user from /tools/litigagent to login", async ({
    page,
  }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authentication required" }),
      })
    );

    await page.goto("/tools/litigagent");

    await expect(page).toHaveURL(/\/login\?redirect=/);
    expect(page.url()).toContain(
      "redirect=%2Ftools%2Flitigagent"
    );
  });

  test("redirects unauthenticated user from /tools/discovery to login", async ({
    page,
  }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authentication required" }),
      })
    );

    await page.goto("/tools/discovery");

    await expect(page).toHaveURL(/\/login\?redirect=/);
    expect(page.url()).toContain(
      "redirect=%2Ftools%2Fdiscovery"
    );
  });

  test("allows authenticated user to access /tools/litigagent", async ({
    page,
  }) => {
    await loginAs(page);

    // Mock the cases API to avoid backend errors
    await page.route("**/api/cases", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      }
      return route.continue();
    });

    await page.goto("/tools/litigagent");

    // Should NOT be redirected to login
    await expect(page).toHaveURL(/\/tools\/litigagent/);
  });
});

// ── User Menu ──────────────────────────────────────────────────

test.describe("User Menu", () => {
  test("shows user menu when authenticated", async ({ page }) => {
    await loginAs(page);
    await page.goto("/");

    const menuButton = page.getByRole("button", { name: "User menu" });
    await expect(menuButton).toBeVisible();
  });

  test("shows initials when no avatar", async ({ page }) => {
    await loginAs(page);
    await page.goto("/");

    // "Jane Attorney" → initials "JA"
    const menuButton = page.getByRole("button", { name: "User menu" });
    await expect(menuButton).toBeVisible();
    await expect(menuButton.locator("div")).toContainText("JA");
  });

  test("shows user name and email in dropdown", async ({ page }) => {
    await loginAs(page);
    await page.goto("/");

    await page.getByRole("button", { name: "User menu" }).click();

    await expect(page.getByText("Jane Attorney")).toBeVisible();
    await expect(page.getByText("test@lawfirm.com")).toBeVisible();
  });

  test("closes dropdown on Escape", async ({ page }) => {
    await loginAs(page);
    await page.goto("/");

    await page.getByRole("button", { name: "User menu" }).click();
    await expect(page.getByText("Sign out")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByText("Sign out")).not.toBeVisible();
  });

  test("closes dropdown on outside click", async ({ page }) => {
    await loginAs(page);
    await page.goto("/");

    await page.getByRole("button", { name: "User menu" }).click();
    await expect(page.getByText("Sign out")).toBeVisible();

    await page.click("body", { position: { x: 10, y: 10 } });
    await expect(page.getByText("Sign out")).not.toBeVisible();
  });

  test("logout clears user and redirects to home", async ({ page }) => {
    await loginAs(page);

    await page.route("**/api/auth/logout", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      })
    );

    await page.goto("/");

    await page.getByRole("button", { name: "User menu" }).click();
    await page.getByText("Sign out").click();

    await expect(page).toHaveURL("/");
    await expect(
      page.getByRole("button", { name: "User menu" })
    ).not.toBeVisible();
  });

  test("does not show user menu when not authenticated", async ({ page }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authentication required" }),
      })
    );

    await page.goto("/");

    // Wait for auth check to complete
    await page.waitForTimeout(500);
    await expect(
      page.getByRole("button", { name: "User menu" })
    ).not.toBeVisible();
  });
});

// ── Gate A1.5 ───────────────────────────────────────────────────

test.describe("Gate A1.5", () => {
  test("full auth flow: protected page → login → authenticated → user menu → logout", async ({
    page,
  }) => {
    // Start unauthenticated
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authentication required" }),
      })
    );

    // 1. Visit protected page → redirected to login with redirect param
    await page.goto("/tools/litigagent");
    await expect(page).toHaveURL(/\/login\?redirect=/);

    // 2. Login page shows OAuth buttons
    await expect(
      page.getByRole("link", { name: "Sign in with Google" })
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Sign in with Microsoft" })
    ).toBeVisible();

    // 3. Simulate successful OAuth: set cookie + update mock
    await page.context().addCookies([
      {
        name: "access_token",
        value: "mock-access-token",
        domain: "localhost",
        path: "/",
      },
    ]);

    await page.unrouteAll();
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER),
      })
    );

    // Mock cases API
    await page.route("**/api/cases", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      }
      return route.continue();
    });

    // Navigate to protected page (simulating post-OAuth redirect)
    await page.goto("/tools/litigagent");
    await expect(page).toHaveURL(/\/tools\/litigagent/);

    // 4. User menu shows name/avatar
    const menuButton = page.getByRole("button", { name: "User menu" });
    await expect(menuButton).toBeVisible();
    await menuButton.click();
    await expect(page.getByText("Jane Attorney")).toBeVisible();
    await expect(page.getByText("test@lawfirm.com")).toBeVisible();

    // 5. Logout → redirected to home
    await page.route("**/api/auth/logout", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      })
    );

    // After logout, /api/auth/me should return 401
    await page.unrouteAll();
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authentication required" }),
      })
    );
    await page.route("**/api/auth/logout", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      })
    );

    // Re-open menu (need to re-mock auth/me first for the currently rendered state)
    // Actually the menu is still open from step 4, click Sign out
    await page.getByText("Sign out").click();

    await expect(page).toHaveURL("/");
    await expect(
      page.getByRole("button", { name: "User menu" })
    ).not.toBeVisible();
  });
});
