# Unpaid Wages Calculator — Seed Scenarios

URL: `/tools/unpaid-wages-calculator`

---

## Scenario 1: Terminated Employee — Waiting Time Penalties

| Field | Value |
|-------|-------|
| **Hourly Rate** | 25.00 |
| **Unpaid Hours** | 120 |
| **Employment Status** | Terminated/Fired |
| **Termination Date** | 2025-12-01 |
| **Final Wages Paid Date** | 2026-01-15 |
| **Missed Meal Breaks** | 0 |
| **Missed Rest Breaks** | 0 |

**Expected output:** $3,000 unpaid wages + up to 30 days of waiting time penalties ($200/day = $6,000). Total ~$9,000. Demos the big impact of waiting time penalties.

---

## Scenario 2: Still Employed — Meal and Rest Break Premiums

| Field | Value |
|-------|-------|
| **Hourly Rate** | 20.00 |
| **Unpaid Hours** | 0 |
| **Employment Status** | Still Employed |
| **Missed Meal Breaks** | 50 |
| **Missed Rest Breaks** | 50 |

**Expected output:** $0 unpaid wages, $1,000 meal break premiums (50 x $20), $1,000 rest break premiums (50 x $20). Total $2,000. No waiting time penalties since still employed.

---

## Scenario 3: Quit With Notice — Mixed Issues

| Field | Value |
|-------|-------|
| **Hourly Rate** | 35.00 |
| **Unpaid Hours** | 80 |
| **Employment Status** | Quit (72+ hours notice) |
| **Termination Date** | 2026-01-10 |
| **Final Wages Paid Date** | 2026-01-25 |
| **Missed Meal Breaks** | 20 |
| **Missed Rest Breaks** | 15 |

**Expected output:** $2,800 unpaid wages + $700 meal break + $525 rest break + waiting time penalties (72-hour window, then 15 days late). Demos how quit-with-notice has same-day final pay requirement.

---

## Scenario 4: Quit Without Notice — Minimal Penalties

| Field | Value |
|-------|-------|
| **Hourly Rate** | 18.50 |
| **Unpaid Hours** | 40 |
| **Employment Status** | Quit (no notice) |
| **Termination Date** | 2026-02-01 |
| **Final Wages Paid Date** | 2026-02-04 |
| **Missed Meal Breaks** | 0 |
| **Missed Rest Breaks** | 0 |

**Expected output:** $740 unpaid wages + minimal/no waiting time penalties (employer has 72 hours when employee quits without notice, paid within 3 days). Demos the different rules for quit-without-notice.

---

## Scenario 5: High-Value — Executive Termination

| Field | Value |
|-------|-------|
| **Hourly Rate** | 150.00 |
| **Unpaid Hours** | 200 |
| **Employment Status** | Terminated/Fired |
| **Termination Date** | 2025-10-15 |
| **Final Wages Paid Date** | (leave blank — still unpaid) |
| **Missed Meal Breaks** | 10 |
| **Missed Rest Breaks** | 10 |

**Expected output:** $30,000 unpaid wages + $1,500 meal + $1,500 rest + max waiting time penalties (30 days x $1,200/day = $36,000) + interest. Massive total. Demos high-value scenario.

---

## Scenario 6: Minimum Wage Worker — Break Violations Only

| Field | Value |
|-------|-------|
| **Hourly Rate** | 16.00 |
| **Unpaid Hours** | 0 |
| **Employment Status** | Terminated/Fired |
| **Termination Date** | 2026-01-20 |
| **Final Wages Paid Date** | 2026-01-20 |
| **Missed Meal Breaks** | 100 |
| **Missed Rest Breaks** | 100 |

**Expected output:** $0 unpaid wages, $1,600 meal premiums, $1,600 rest premiums, $0 waiting time penalties (paid on time). Total $3,200. Demos break-only scenario.

---

## Scenario 7: Interest Calculation

| Field | Value |
|-------|-------|
| **Hourly Rate** | 30.00 |
| **Unpaid Hours** | 160 |
| **Employment Status** | Terminated/Fired |
| **Termination Date** | 2024-06-01 |
| **Final Wages Paid Date** | (leave blank) |
| **Missed Meal Breaks** | 0 |
| **Missed Rest Breaks** | 0 |
| **Unpaid Since** | 2024-06-01 |

**Expected output:** $4,800 unpaid wages + waiting time penalties + ~1.5 years of interest. Demos the interest accumulation over time.
