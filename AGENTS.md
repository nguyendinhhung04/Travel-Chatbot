# Project instructions

## Browser verification

- After implementing or changing any browser-observable feature, add or update the relevant Playwright coverage. Run `cd frontend && npm run test:e2e` only when the user explicitly requests Playwright/E2E execution.
- When Playwright is explicitly requested, run it with the configured Microsoft Edge project (`channel: "msedge"`). Do not silently substitute another browser; if Edge cannot run, report the limitation explicitly.
- Keep E2E tests deterministic by mocking Gemini and Mapbox at the HTTP boundary unless the task explicitly requires live-provider validation. Report mocked E2E results separately from live-provider results.
- When a Playwright test fails, diagnose and fix the product code, test code, or configuration as appropriate. Do not weaken assertions merely to make the suite pass.
- Also run the unit, lint, build, and service-specific checks relevant to the files changed; Playwright does not replace those checks.
