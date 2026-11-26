"""Read and present aggregate QA evidence with separate validation scopes."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.model import (
    Claim, ExportError, Metadata, decimal_text, nonnegative_int, parse_metadata, required_text,
)
from dashboard.views import RED, figure, metric_row, quantity, rate


RULE_LABELS = ("rule_id", "source_table", "category", "severity", "recommended_action")
ORIGINAL_COUNTS = ("source_rows", "rules_total", "rules_passed", "issues_total")
INJECTED_COUNTS = ("source_rows", "rules_total", "expected_findings", "detected_findings", "missed_findings", "tests_passed")
ISSUE_FIELDS = (
    "rule_id", "source_table", "record_ref", "issue_category", "severity", "resolution_status", "recommended_action"
)


@dataclass(frozen=True)
class Quality:
    original_summary: dict
    original_rules: list[dict]
    original_issues: list[dict]
    test_summary: dict
    test_rules: list[dict]


def bounded_rate(value: object, name: str, denominator: int) -> Decimal | None:
    if not denominator and value is None:
        return None
    parsed = decimal_text(value, name)
    if not denominator or not 0 <= parsed <= 1:
        raise ExportError(f"{name} must be a decimal fraction from zero to one for a positive denominator.")
    return parsed


def scope(payload: dict, name: str, count_fields: tuple[str, ...]) -> tuple[dict, list, list]:
    data = payload.get(name)
    if not isinstance(data, dict):
        raise ExportError(f"The quality export must contain its {name} scope.")
    summary, rules, issues = (data.get(key) for key in ("summary", "rules", "issues"))
    if not isinstance(summary, dict) or not isinstance(rules, list) or not isinstance(issues, list):
        raise ExportError(f"The quality {name} scope must include a summary and rule and issue arrays.")
    counts = {key: nonnegative_int(summary.get(key), key) for key in count_fields}
    if counts["rules_total"] != len(rules):
        raise ExportError(f"The quality {name} rule count does not match its summary.")
    return counts, rules, issues


def parse_rule(record: object, injected: bool) -> dict:
    count_fields = ("expected_count", "detected_count", "missed_count") if injected else ("tested_rows", "issue_count")
    rate_key = "detection_rate" if injected else "pass_rate"
    text_fields = (*RULE_LABELS, "result") if injected else RULE_LABELS
    if not isinstance(record, dict) or record.keys() != set((*text_fields, *count_fields, rate_key)):
        raise ExportError("Quality rule fields do not match the public contract.")
    parsed = {key: required_text(record[key], key) for key in text_fields}
    parsed.update({key: nonnegative_int(record[key], key) for key in count_fields})
    if injected:
        denominator = parsed["expected_count"]
        if parsed["detected_count"] + parsed["missed_count"] != denominator:
            raise ExportError("Injected-test detection totals do not reconcile.")
        if parsed["result"] not in ("pass", "fail"):
            raise ExportError("Injected-test rule results must be pass or fail.")
    else:
        denominator = parsed["tested_rows"]
        if parsed["issue_count"] > denominator:
            raise ExportError("Quality issues exceed the number of tested rows for a rule.")
    parsed[rate_key] = bounded_rate(record[rate_key], rate_key, denominator)
    return parsed


def parse_quality(payload: dict, claims_metadata: Metadata, claims: tuple[Claim, ...]) -> Quality:
    metadata = parse_metadata(payload, "validation run across seven source tables")
    if metadata.source_sha256 != claims_metadata.source_sha256:
        raise ExportError("The quality and claims exports refer to different source archives.")
    original, original_rules, issues = scope(payload, "original", ORIGINAL_COUNTS)
    tests, test_rules, test_issues = scope(payload, "injected_test", INJECTED_COUNTS)
    if metadata.record_count != original["source_rows"]:
        raise ExportError("The original QA source-row count does not match its metadata.")
    if test_issues:
        raise ExportError("The injected-test export may contain only aggregate findings.")

    original_rules = [parse_rule(rule, injected=False) for rule in original_rules]
    test_rules = [parse_rule(rule, injected=True) for rule in test_rules]
    if (
        original["issues_total"] != sum(rule["issue_count"] for rule in original_rules)
        or original["rules_passed"] != sum(rule["issue_count"] == 0 for rule in original_rules)
    ):
        raise ExportError("Original validation counts do not match the rule results.")
    if (
        tests["tests_passed"] != sum(rule["result"] == "pass" for rule in test_rules)
        or any(tests[total] != sum(rule[count] for rule in test_rules) for total, count in (
            ("expected_findings", "expected_count"), ("detected_findings", "detected_count"), ("missed_findings", "missed_count"),
        ))
    ):
        raise ExportError("Injected-test counts do not match the rule results.")
    claim_ids = {claim.claim_id for claim in claims}
    public_issues = []
    for item in issues:
        if not isinstance(item, dict) or item.keys() != set(ISSUE_FIELDS):
            raise ExportError("Quality issue fields do not match the public contract.")
        issue = {key: required_text(item[key], key) for key in ISSUE_FIELDS if key != "record_ref"}
        ref = item["record_ref"]
        issue["record_ref"] = ref if issue["source_table"] == "claims" and isinstance(ref, str) and ref in claim_ids else None
        public_issues.append(issue)
    return Quality(original, original_rules, public_issues, tests, test_rules)


def rule_table(rules: list[dict], rate_field: str) -> None:
    if not rules:
        st.info("The export contains no rules for this scope.")
        return
    rows = [dict(item, **{rate_field: rate(item[rate_field])}) for item in rules]
    st.dataframe(pd.DataFrame(rows).rename(columns=lambda name: name.replace("_", " ").capitalize()), hide_index=True)


def original_evidence(
    quality: Quality, filtered_claims: tuple[Claim, ...], open_claim: Callable[[Claim], None]
) -> None:
    summary = quality.original_summary
    st.caption("Rule metrics cover the original source archive. Claim filters apply only to linkable claim exceptions below.")
    metric_row([
        ("Source rows", quantity(summary["source_rows"]), "Rows across the seven source tables."),
        ("Rules evaluated", quantity(summary["rules_total"]), "Validation rules run on the original source."),
        ("Rules passed", quantity(summary["rules_passed"]), "Original rules with no detected issues."),
        ("Rule findings", quantity(summary["issues_total"]), "Count of findings across rules. A row can trigger multiple rules."),
    ])

    failed = sorted((item for item in quality.original_rules if item["issue_count"]),
                    key=lambda item: (-item["issue_count"], item["rule_id"]))[:6][::-1]
    if failed:
        chart = figure(255)
        chart.add_trace(go.Bar(
            x=[item["issue_count"] for item in failed], y=[item["rule_id"] for item in failed],
            marker_color=RED, orientation="h", hovertemplate="%{y}<br>%{x:,} findings<extra></extra>",
        ))
        st.subheader("Original findings by rule")
        st.plotly_chart(chart, theme=None, config={"displaylogo": False})
    elif summary["rules_total"]:
        st.success("The exported original QA rules report zero findings.")

    st.subheader("Original rule results")
    rule_table(quality.original_rules, "pass_rate")
    st.subheader("QA exception register")
    claim_ids = {claim.claim_id: claim for claim in filtered_claims}
    linked = [issue for issue in quality.original_issues if issue["record_ref"] in claim_ids]
    if not linked:
        st.info("There are no exported claim exceptions for the current filters.")
        return
    st.dataframe(pd.DataFrame(linked).rename(columns={"record_ref": "Claim ID"}), hide_index=True)
    st.caption("A claim can have several findings. The chart counts unique flagged claims.")
    flagged = {issue["record_ref"] for issue in linked}
    selection = st.selectbox("Flagged claim details", sorted(flagged), index=None, placeholder="Select a claim ID")
    if selection and st.button("Open flagged claim details"):
        open_claim(claim_ids[selection])
    groups = Counter(claim.encounter_type for claim in filtered_claims if claim.claim_id in flagged)
    items = groups.most_common()[::-1]
    chart = figure(240)
    chart.add_bar(
        x=[count for _, count in items], y=[key for key, _ in items],
        marker_color=RED, orientation="h", hovertemplate="%{y}<br>%{x:,} flagged claims<extra></extra>",
    )
    st.subheader("Flagged claims by encounter type")
    st.plotly_chart(chart, theme=None, config={"displaylogo": False})


def test_evidence(quality: Quality) -> None:
    summary = quality.test_summary
    st.caption("Deliberately corrupted test copies validate rule detection. These counts describe the test design.")
    metric_row([
        ("Expected findings", quantity(summary["expected_findings"]), "Deliberately injected findings expected by the test."),
        ("Detected findings", quantity(summary["detected_findings"]), "Expected findings detected by the rules."),
        ("Missed findings", quantity(summary["missed_findings"]), "Expected findings the rules missed."),
        ("Test rules passed", f"{summary['tests_passed']:,} / {summary['rules_total']:,}", "Rules detecting all expected findings with zero misses."),
    ])
    st.subheader("Injected-test rule results")
    rule_table(quality.test_rules, "detection_rate")
