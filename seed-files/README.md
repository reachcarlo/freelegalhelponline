# Seed Files — Test Data for Manual Testing & Demos

This folder contains copy-paste-ready test data for every tool in the Employee Help platform. Use these to quickly test features or demo the product.

## Structure

| Folder | Tool | Files |
|--------|------|-------|
| `chatbot/` | AI Chat (Consumer & Attorney modes) | Sample queries, follow-ups, edge cases |
| `discovery/` | Discovery Document Generator (5 tools) | Case info sets, claim combos |
| `deadline-calculator/` | Statute of Limitations Calculator | Claim type + date scenarios |
| `unpaid-wages-calculator/` | Unpaid Wages Calculator | Pay scenarios with different statuses |
| `agency-routing/` | Agency Routing Guide | Issue type scenarios |
| `guided-intake/` | Guided Rights Intake Questionnaire | Answer path walkthroughs |
| `incident-docs/` | Incident Documentation Helper | Per-incident-type field data |

## How to Use

1. Open the tool in the browser
2. Open the matching seed file
3. Copy values field-by-field into the UI
4. For the chatbot, copy queries directly into the input box

## Maintenance

See `SEED-DATA-REVIEW.md` for the development process that keeps seed data in sync with the application.
