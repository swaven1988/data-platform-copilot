import { expect, test } from "@playwright/test";

const PAGES: Array<{ path: string; title: RegExp }> = [
    { path: "/", title: /Dashboard/i },
    { path: "/modeling", title: /Modeling/i },
    { path: "/execution", title: /Execution/i },
    { path: "/preflight", title: /Preflight/i },
    { path: "/billing", title: /Billing/i },
    { path: "/health", title: /System Health|Health/i },
    { path: "/audit", title: /Audit Log/i },
];

test.describe("Core page smoke", () => {
    test.beforeEach(async ({ context }) => {
        await context.addInitScript(() => {
            localStorage.setItem("COPILOT_TOKEN", "dev_admin_token");
            localStorage.setItem("COPILOT_TENANT", "default");
        });
    });

    for (const pageCase of PAGES) {
        test(`renders ${pageCase.path}`, async ({ page }) => {
            await page.goto(pageCase.path, { waitUntil: "domcontentloaded" });
            await expect(page.getByRole("main")).toBeVisible();
            await expect(page.getByRole("heading", { level: 1, name: pageCase.title })).toBeVisible();
        });
    }
});

