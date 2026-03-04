# Guided Intake Questionnaire — Seed Scenarios

URL: `/tools/guided-intake`

Each scenario shows the answer to select at each step. The questionnaire has conditional branching — not all questions appear for every path.

---

## Scenario 1: Unpaid Wages + Retaliation (Most Common Path)

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **I wasn't paid correctly** |
| 2 | What is the pay issue? | **I didn't receive wages I earned** |
| 3 | *(skipped — not "treated unfairly")* | — |
| 4 | Did problems happen after you complained? | **Yes, I think it was retaliation** |
| 5 | What did you complain about? | **Pay or wage violations** |
| 6 | Current employment status? | **I was fired or laid off** |
| 7 | Type of employer? | **Private company** |
| 8 | Benefits needed? | **Unemployment insurance** |

**Expected output:** Identifies wage theft + retaliation issues, flags deadline urgency, suggests DLSE + CRD filing, auto-generates rights summary.

---

## Scenario 2: Discrimination — Still Employed

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **I was treated unfairly** |
| 2 | *(skipped — not "not paid")* | — |
| 3 | How were you treated unfairly? | **Because of race, gender, age, disability, or other protected characteristic** |
| 4 | Did problems happen after you complained? | **No, or I'm not sure** |
| 5 | *(skipped — no retaliation)* | — |
| 6 | Current employment status? | **I still work there** |
| 7 | Type of employer? | **Private company** |
| 8 | Benefits needed? | **None of these** |

**Expected output:** Identifies FEHA discrimination, suggests CRD filing, no benefits guidance needed.

---

## Scenario 3: Harassment + Retaliation — Fired

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **I was treated unfairly** |
| 2 | *(skipped)* | — |
| 3 | How were you treated unfairly? | **Ongoing harassment or hostile work environment** |
| 4 | Did problems happen after you complained? | **Yes, I think it was retaliation** |
| 5 | What did you complain about? | **Discrimination or harassment** |
| 6 | Current employment status? | **I was fired or laid off** |
| 7 | Type of employer? | **Private company** |
| 8 | Benefits needed? | **Unemployment insurance** and **State disability insurance (SDI)** |

**Expected output:** Identifies harassment + retaliation + wrongful termination, high confidence, urgent deadlines. Multiple benefit applications flagged.

---

## Scenario 4: Unsafe Workplace — Government Employee

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **My workplace is unsafe** |
| 2 | *(skipped)* | — |
| 3 | *(skipped)* | — |
| 4 | Did problems happen after you complained? | **No, or I'm not sure** |
| 5 | *(skipped)* | — |
| 6 | Current employment status? | **I still work there** |
| 7 | Type of employer? | **Government agency** |
| 8 | Benefits needed? | **None of these** |

**Expected output:** Identifies workplace safety issue, routes to Cal/OSHA, flags special government employee rules (shorter deadlines).

---

## Scenario 5: Fired After Reporting — Whistleblower Path

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **I reported a problem and faced consequences** |
| 2 | *(skipped)* | — |
| 3 | *(skipped)* | — |
| 4 | Did problems happen after you complained? | **Yes, I think it was retaliation** |
| 5 | What did you complain about? | **Other illegal activity** |
| 6 | Current employment status? | **I was fired or laid off** |
| 7 | Type of employer? | **Private company** |
| 8 | Benefits needed? | **Unemployment insurance** |

**Expected output:** Identifies whistleblower retaliation (LC 1102.5), wrongful termination, suggests DLSE filing. Shows the reporting-specific pathway.

---

## Scenario 6: Misclassification — Contractor Issue

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **I wasn't paid correctly** |
| 2 | What is the pay issue? | **I'm classified as independent contractor but should be employee** |
| 3 | *(skipped)* | — |
| 4 | Did problems happen after you complained? | **No, or I'm not sure** |
| 5 | *(skipped)* | — |
| 6 | Current employment status? | **I still work there** |
| 7 | Type of employer? | **Not sure** |
| 8 | Benefits needed? | **None of these** |

**Expected output:** Identifies misclassification, explains ABC test, routes to EDD + DLSE. "Not sure" employer type still works.

---

## Scenario 7: Family Leave Denied — Quit

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **I was treated unfairly** |
| 2 | *(skipped)* | — |
| 3 | How were you treated unfairly? | **I was denied family or medical leave** |
| 4 | Did problems happen after you complained? | **No, or I'm not sure** |
| 5 | *(skipped)* | — |
| 6 | Current employment status? | **I quit** |
| 7 | Type of employer? | **Private company** |
| 8 | Benefits needed? | **Paid family leave** |

**Expected output:** Identifies CFRA/FMLA violation, constructive discharge possibility, routes to CRD, flags PFL benefit application.

---

## Scenario 8: Benefits Only — No Employment Dispute

| Step | Question | Select |
|------|----------|--------|
| 1 | Which best describes your situation? | **I need help with benefits** |
| 2 | *(skipped)* | — |
| 3 | *(skipped)* | — |
| 4 | Did problems happen after you complained? | **No, or I'm not sure** |
| 5 | *(skipped)* | — |
| 6 | Current employment status? | **I was fired or laid off** |
| 7 | Type of employer? | **Private company** |
| 8 | Benefits needed? | **Unemployment insurance** and **State disability insurance (SDI)** and **Paid family leave** |

**Expected output:** Focuses on benefits guidance (UI, SDI, PFL) via EDD. Minimal legal claims identified. Shows the benefits-focused pathway.
