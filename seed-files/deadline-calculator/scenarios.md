# Deadline Calculator — Seed Scenarios

URL: `/tools/deadline-calculator`

Each scenario provides a **Claim Type** dropdown selection and an **Incident Date** to enter.

---

## Scenario 1: FEHA Discrimination — Recent Incident

| Field | Value |
|-------|-------|
| **Claim Type** | FEHA Discrimination/Harassment |
| **Incident Date** | 2025-11-15 |

**Expected output:** CRD complaint deadline (~3 years), right-to-sue letter timeline, court filing deadline after right-to-sue. Should show urgency as "normal" with plenty of time remaining.

---

## Scenario 2: Wage Theft — Urgent

| Field | Value |
|-------|-------|
| **Claim Type** | Wage Theft/Unpaid Wages |
| **Incident Date** | 2023-04-01 |

**Expected output:** DLSE complaint deadline (3 years from last violation), civil suit deadline. Should show as "urgent" — approaching the 3-year mark.

---

## Scenario 3: Wrongful Termination — 2-Year SOL

| Field | Value |
|-------|-------|
| **Claim Type** | Wrongful Termination |
| **Incident Date** | 2024-06-15 |

**Expected output:** 2-year statute of limitations for tort claims, potential FEHA administrative exhaustion requirements. Should show as "normal."

---

## Scenario 4: PAGA — Short Window

| Field | Value |
|-------|-------|
| **Claim Type** | PAGA (Private Attorneys General Act) |
| **Incident Date** | 2025-09-01 |

**Expected output:** LWDA notice requirement (65-day cure period), 1-year SOL. Shows the unique PAGA administrative steps.

---

## Scenario 5: Government Employee — Special Rules

| Field | Value |
|-------|-------|
| **Claim Type** | Government Employee Claims |
| **Incident Date** | 2025-12-01 |

**Expected output:** Government tort claim deadline (6 months!), shows as "critical." Demos the much shorter window for government employees.

---

## Scenario 6: CFRA/Family Leave — Moderate Timeline

| Field | Value |
|-------|-------|
| **Claim Type** | CFRA/Family Leave Violations |
| **Incident Date** | 2025-03-01 |

**Expected output:** CRD filing requirements, 2-year SOL for related tort claims. Should show as "normal."

---

## Scenario 7: Expired Deadline (Edge Case)

| Field | Value |
|-------|-------|
| **Claim Type** | Wage Theft/Unpaid Wages |
| **Incident Date** | 2022-01-15 |

**Expected output:** Some or all deadlines should show as "expired." Demos the red expired state and how the tool handles stale claims.

---

## Scenario 8: Whistleblower Retaliation

| Field | Value |
|-------|-------|
| **Claim Type** | Retaliation/Whistleblower |
| **Incident Date** | 2025-08-20 |

**Expected output:** Multiple filing options (DLSE, civil suit), different SOL periods. Shows the multiple-path analysis.

---

## Scenario 9: Worker Misclassification

| Field | Value |
|-------|-------|
| **Claim Type** | Worker Misclassification |
| **Incident Date** | 2024-11-01 |

**Expected output:** EDD filing, DLSE complaint, civil suit options with different deadlines. Shows agency routing alongside deadlines.
