# Employee Help — Frontend

Next.js 16 (App Router) + Tailwind CSS + TypeScript frontend for the Employee Help platform.

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The FastAPI backend must also be running on port 8000:

```bash
cd .. && uv run uvicorn employee_help.api.main:app --port 8000
```

## E2E Tests (Playwright)

49 end-to-end tests covering all 5 discovery tool workflows with PDF/DOCX content validation.

### Setup

```bash
npx playwright install chromium
```

### Run

```bash
# Run all E2E tests (auto-starts both servers if not running)
npx playwright test

# Run with visible browser
npx playwright test --headed

# Run a single spec file
npx playwright test e2e/discovery-srogs.spec.ts

# Run with verbose output
npx playwright test --reporter=list
```

### Test Specs

| File | Tests | Coverage |
|------|-------|----------|
| `discovery-disc001.spec.ts` | 7 | DISC-001 wizard, PDF form field validation |
| `discovery-disc002.spec.ts` | 4 | DISC-002 employment interrogatories, PDF generation |
| `discovery-srogs.spec.ts` | 7 | SROGs 35-limit, select/deselect, custom requests, DOCX |
| `discovery-rfpds.spec.ts` | 5 | RFPDs 7-step wizard, production instructions, DOCX |
| `discovery-rfas.spec.ts` | 5 | RFAs fact limit, type badges, DOCX validation |
| `discovery-cross-tool.spec.ts` | 4 | Cross-tool state persistence via sessionStorage |
| `discovery-limits.spec.ts` | 4 | Declaration of Necessity warnings |
| `discovery-mobile.spec.ts` | 6 | 375x812 viewport, touch targets, responsive layout |
| `discovery-index.spec.ts` | 5 | Discovery hub page, navigation, format badges |

### Helpers

- `e2e/helpers/wizard-helpers.ts` — Shared wizard interaction functions (fillCaseInfo, clickNext, selectClaims, interceptGenerateResponse)
- `e2e/helpers/doc-validator.ts` — PDF form field validation (pdf-lib) and DOCX content validation (jszip)
