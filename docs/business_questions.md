# RCM360 business questions

These questions translate revenue-cycle operations work into analyses supported by the verified Misata synthetic dataset. They are questions to answer after loading and validating the source in PostgreSQL; they are not findings. Use a claim-level denominator for claim and financial measures, and pre-aggregate one-to-many clinical tables before joining them to claims.

The target Data Operations Analyst role emphasizes QA, process adherence, SQL discrepancy analysis, documentation, clear communication, and cross-team problem solving. This project can demonstrate artifacts and methods for those skills; a synthetic portfolio project does not establish on-the-job performance. The role description is at <https://jobs.ashbyhq.com/Commure/4f984c29-f4f8-465b-a20e-b9c9e81a8e1c/>.

## Claim flow and denials

1. **How does submitted claim volume change by month, payer, and encounter type?** Group by `submitted_at` month; show counts and avoid interpreting the synthetic sample as a live workload forecast.
2. **How does the observed status mix vary by submission month?** Report paid, denied, and pending counts with cohort sizes; no observation cutoff is available, so newer cohorts may have less time to mature.
3. **What is the overall observed denial rate, and how does it change across submission cohorts?** Define the denominator as all claims in the stated cohort; label monthly values as snapshot status rates.
4. **Which payers have the highest observed denial rates, and how much claim volume supports each rate?** Show denominators and uncertainty or a small-sample flag; do not rank tiny groups as stable payer performance.
5. **How do observed denial rates differ among providers after accounting for claim volume?** Join via encounter and show counts alongside rates; provider differences are descriptive and may reflect case mix or synthetic generation.
6. **Which recorded denial reasons occur most often?** Count denied claims only; preserve the source reason categories without inferring unrecorded root causes.
7. **Do recorded denial reasons differ across payers or encounter types?** Compare claim counts and rates with denominators; do not interpret association as payer policy or clinical causation.
8. **What billed amount is attached to denied claims by reason, payer, and month?** Label this gross billed exposure, not confirmed loss, write-off, or recoverable revenue.
9. **How concentrated are denied-claim counts and billed exposure among denial reasons?** Use cumulative Pareto shares with the selected denominator stated; do not infer that addressing one reason will recover the corresponding billed amount.
10. **How many claims remain pending in each submission cohort and payer group?** Report counts only; there is no cutoff or due-date rule to classify a pending claim as overdue or aged.

## Financial reconciliation and payment timing

11. **How do billed, allowed, recorded payer payment, and assigned patient responsibility totals compare by status and payer?** Sum each source field separately; patient responsibility is assigned, not proof of patient cash received.
12. **What is the billed-minus-allowed difference by payer, encounter type, or claim?** Call it a difference only; the source has no adjustment ledger to identify contractual adjustments or explain the difference.
13. **What are descriptive payer-payment-to-billed and payer-payment-to-allowed ratios by group?** Name the numerator and denominator; do not label either a collection rate because payment completeness and an observation cutoff are absent.
14. **Does the stored `allowed_ratio` agree with `allowed_amount / billed_amount` within a documented rounding tolerance?** Compare at claim grain and report the tolerance; preserve source amounts rather than replacing them with recomputed values.
15. **Do source financial relationships satisfy `0 <= payer payment <= allowed <= billed`?** Treat failures as rule-level exceptions for investigation, not as proof of a specific business cause.
16. **Does the assigned patient responsibility reconcile to billed minus allowed in each status?** Report source behavior separately by status; do not present the assigned amount as a receivable balance or collected cash.
17. **What is the submission-to-payment time distribution for paid claims, and how does it vary by payer or encounter type?** Restrict to observed paid claims and label as a paid-subset description, not cohort-wide turnaround or aging.
18. **Do claim payer, encounter type, and billed amount agree with the linked encounter?** Compare one claim to its one encounter before aggregating; flag record-level discrepancies without multiplying claim dollars.

## Operational context and data quality

19. **How often are claims submitted, paid, or denied before encounter discharge, by encounter type?** Describe timestamps only; the publisher supplies no rule requiring submission or outcome after discharge.
20. **How does denial status vary with encounter-level diagnosis categories or diagnosis counts?** Aggregate diagnoses to encounter before joining; report descriptive associations and avoid causal, severity, or clinical conclusions.
21. **What does the source's `paid_amount` contain for claims labeled `self_pay`?** Quantify the observed field values and disclose this generator behavior; do not silently reinterpret or remove them.
22. **Do primary keys, foreign keys, required fields, status-dependent fields, and date-order rules pass documented validation?** State tested rows and denominators per rule, and distinguish a source exception from an injected test error.
23. **Can deterministic, deliberately injected test errors be detected at the intended rule and record grain?** Compare expected, detected, and missed counts; retain corrupted records locally and keep their results separate from original-data QA.
24. **Which original-data exceptions should an operations team investigate first?** Prioritize by documented severity, affected rows, and potential process impact; do not call an unusual but valid value a defect without a violated rule.

## Interpretation rules

- All observations describe a historical synthetic dataset, not actual Commure, payer, provider, or patient operations.
- Report exact source totals and cohort definitions, include sample sizes, and reconcile claim-level financial totals against PostgreSQL before publishing results.
- The source has no appeal/resubmission history, service-line detail, adjustment or remittance ledger, patient-payment transaction, currency field, or observation cutoff. Do not claim appeal outcomes, contractual adjustment amounts, total collections, collection rate, outstanding balance, or claim aging.
- A recorded denial reason is a reason label in the source, not a verified root cause. Recommendations must be framed as process hypotheses until supported by operational evidence.
