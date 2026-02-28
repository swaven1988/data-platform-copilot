import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
    testDir: "./tests/e2e",
    timeout: 30_000,
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 1 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: "list",
    use: {
        baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4173",
        trace: "on-first-retry",
    },
    webServer: {
        command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4173",
        port: 4173,
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
    },
    projects: [
        {
            name: "chromium",
            use: { ...devices["Desktop Chrome"] },
        },
    ],
});

