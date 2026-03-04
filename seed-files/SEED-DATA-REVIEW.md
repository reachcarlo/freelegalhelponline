# Seed Data Review Process

## Purpose

Seed data files in `seed-files/` provide copy-paste-ready test inputs for every tool in the application. They must stay in sync with the application as features evolve.

## When to Review Seed Data

Review seed data **any time** you:

1. **Add a new tool or feature** — Create a new sub-folder with seed scenarios
2. **Add, rename, or remove a form field** — Update affected seed files to match
3. **Change dropdown options or enum values** — Update all scenarios that reference old values
4. **Change validation rules** — Ensure seed values still pass validation
5. **Change API request/response schemas** — Verify seed data matches new schema
6. **Change wizard step order or flow** — Update scenario walkthrough instructions
7. **Change claim types or categories** — Update discovery and intake scenarios
8. **Change rate limits or turn limits** — Update chatbot scenario notes

## Review Checklist

When a feature change triggers a seed data review, verify:

- [ ] All field names in seed files match the current UI labels
- [ ] All dropdown/select values match current options (exact spelling)
- [ ] All scenario walkthroughs follow the current step order
- [ ] Conditional fields are only listed when their condition is met
- [ ] Validation constraints are respected (min/max, required, format)
- [ ] "Expected output" notes are still accurate
- [ ] New features/fields have seed data coverage
- [ ] Removed features/fields are cleaned from seed files

## File Inventory

| Seed File | Covers | Key Dependencies |
|-----------|--------|-----------------|
| `chatbot/consumer-queries.md` | Consumer chat | `config/rag.yaml` (tone, turns), content categories |
| `chatbot/attorney-queries.md` | Attorney chat | `config/rag.yaml` (tone, turns), statutory/case law sources |
| `discovery/case-*.md` (5 files) | All 5 discovery wizards | `CLAIM_TYPES` in `discovery-api.ts`, `case-info-form.tsx`, `field_mapping.py` |
| `deadline-calculator/scenarios.md` | Deadline calculator | Claim type enum in API schemas, SOL rules |
| `unpaid-wages-calculator/scenarios.md` | Wages calculator | Employment status enum, field ranges in API schemas |
| `agency-routing/scenarios.md` | Agency routing | Issue type enum in API schemas |
| `guided-intake/scenarios.md` | Intake questionnaire | Question flow in `intake.py`, answer option values |
| `incident-docs/scenarios.md` | Incident documentation | Incident types, per-type fields in API schemas |

## Automation

The pre-existing E2E test suite (`frontend/e2e/`) uses overlapping test data from `frontend/e2e/helpers/wizard-helpers.ts`. When E2E tests pass, it confirms the core field mappings work. Seed data goes beyond this by covering:

- All tool types (not just happy-path)
- Realistic multi-claim combinations
- Edge cases (pro per, defendant side, expired dates)
- Demo-quality narratives and descriptions
- Chatbot conversation flows

## Adding a New Tool

When a new tool is added:

1. Create `seed-files/<tool-name>/scenarios.md`
2. Include at least 3 scenarios covering common, edge, and error cases
3. For each scenario, list every field with its exact value
4. Add an "Expected output" note describing what the tool should produce
5. Update the inventory table above
6. Update `seed-files/README.md` if the folder structure changed
