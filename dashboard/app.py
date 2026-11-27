"""Reference-aligned Streamlit dashboard for validated, claim-grain exports."""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.model import (
    SORTS, Claim, ClaimFilters, ExportError, claims_csv, filter_claims, group_by,
    parse_claims, read_json, search_claims, summarize,
)
from dashboard.quality import (
    Quality, parse_quality, rule_table, test_evidence,
)
from dashboard.theme import apply_theme
from dashboard.views import (
    INDIGO, LAVENDER, MATURITY, RED, SELF_PAY, comparison, days, denial_heatmap,
    denial_watchlist, figure, label, metric_row, money, monthly_chart,
    pareto_chart, payment_timing_comparison, quantity, ranked_chart, rate, status_chart, status_reconciliation,
)


DATA_DIR = Path(__file__).resolve().parent / "data"
PAGES = (
    "Executive overview", "Claims & denials", "Revenue & payments", "Payer & provider", "Data quality & QA",
)
DESCRIPTIONS = (
    "Monitor claim volume, submitted charges, payer payments and observed denial patterns.",
    "Explore observed denial rates and gross billed amounts on denied claims.",
    "Compare source-reported billed, allowed, payment and assigned-responsibility amounts.",
    "Compare claim volume, payer payments and observed denial rates by payer and provider.",
    "Review original source validation separately from injected-error test evidence.",
)
GLOBAL_FILTER_FIELDS = ("payer", "provider_id", "encounter_type")
FILTER_LABELS = {"payer": "Insurance payer", "provider_id": "Provider", "encounter_type": "Encounter type"}
FILTER_PLACEHOLDERS = {"payer": "Any payer", "provider_id": "Any provider", "encounter_type": "Any type"}
NAV_MARKS = {
    "Executive overview": "▦",
    "Claims & denials": "↗",
    "Revenue & payments": "◒",
    "Payer & provider": "⇄",
    "Data quality & QA": "✓",
}
PAGE_SIZE = 6
REPORT_PERIOD_KEY = "report_period"
TABLE_STATUSES = ("All statuses", "Paid", "Denied", "Pending")
TABLE_COLUMNS = (
    "Claim ID", "Submission date", "Payer", "Provider ID", "Status", "Billed amount", "Payer payment", "Data quality",
)


def clear_drill() -> None:
    st.session_state.drill = None
    st.session_state.claim_table_page = 0
    for key in list(st.session_state):
        if key.endswith("_choose"):
            del st.session_state[key]


def reset_filters(default_period: str) -> None:
    st.session_state[REPORT_PERIOD_KEY] = default_period
    for field in GLOBAL_FILTER_FIELDS:
        st.session_state[f"filter_{field}"] = None
    st.session_state.claim_search = ""
    st.session_state.table_status = TABLE_STATUSES[0]
    st.session_state.sort_mode = next(iter(SORTS))
    st.session_state.claim_sort = st.session_state.sort_mode
    clear_drill()


def reset_table_page() -> None:
    st.session_state.claim_table_page = 0


def change_table_page(page: int) -> None:
    st.session_state.claim_table_page = page


def save_trend() -> None:
    st.session_state.trend = st.session_state.trend_mode


def save_sort() -> None:
    st.session_state.sort_mode = st.session_state.claim_sort
    reset_table_page()


def navigate() -> None:
    clear_drill()
    st.session_state.claim_search = ""
    st.session_state.table_status = TABLE_STATUSES[0]


def reporting_periods(bounds: tuple[date, date]) -> tuple[dict[str, tuple[date, date]], str]:
    """Build calendar-year and quarter filters clipped to dates in the export."""
    first, last = bounds
    periods = {"All available dates": bounds}
    for year in range(first.year, last.year + 1):
        year_start = max(first, date(year, 1, 1))
        year_end = min(last, date(year, 12, 31))
        if year_start <= year_end:
            if year_start == date(year, 1, 1) and year_end == date(year, 12, 31):
                title = f"Full year {year}"
            else:
                title = f"{year} · available dates"
            if (year_start, year_end) != bounds:
                periods[title] = (year_start, year_end)
        for quarter in range(4):
            month = quarter * 3 + 1
            quarter_start = date(year, month, 1)
            next_month = month + 3
            quarter_end = (
                date(year + 1, 1, 1) - timedelta(days=1)
                if next_month > 12 else date(year, next_month, 1) - timedelta(days=1)
            )
            clipped_start = max(first, quarter_start)
            clipped_end = min(last, quarter_end)
            if clipped_start <= clipped_end and (clipped_start, clipped_end) != bounds:
                periods[f"Q{quarter + 1} {year}"] = (clipped_start, clipped_end)
    default = next((title for title in periods if title.startswith("Full year ")), "All available dates")
    return periods, default


def initialize_filter_state(claims: tuple[Claim, ...], periods: dict[str, tuple[date, date]], default_period: str) -> None:
    if st.session_state.get(REPORT_PERIOD_KEY) not in periods:
        st.session_state[REPORT_PERIOD_KEY] = default_period
    for field in GLOBAL_FILTER_FIELDS:
        key = f"filter_{field}"
        available = {getattr(claim, field) for claim in claims}
        if st.session_state.get(key) not in available:
            st.session_state[key] = None
    if st.session_state.get("table_status") not in TABLE_STATUSES:
        st.session_state.table_status = TABLE_STATUSES[0]
    if st.session_state.get("claim_sort") not in SORTS:
        st.session_state.claim_sort = st.session_state.get("sort_mode", next(iter(SORTS)))
    if st.session_state.get("claim_sort") not in SORTS:
        st.session_state.claim_sort = next(iter(SORTS))
    st.session_state.sort_mode = st.session_state.claim_sort
    st.session_state.setdefault("claim_search", "")
    st.session_state.setdefault("claim_table_page", 0)
    st.session_state.setdefault("drill", None)
    st.session_state.setdefault("trend", "Financial")
    if st.session_state.trend not in ("Financial", "Claim volume"):
        st.session_state.trend = "Financial"


def selected_filters(periods: dict[str, tuple[date, date]]) -> ClaimFilters:
    start, end = periods[st.session_state[REPORT_PERIOD_KEY]]
    return ClaimFilters(
        start=start,
        end=end,
        payer=st.session_state.get("filter_payer"),
        provider_id=st.session_state.get("filter_provider_id"),
        encounter_type=st.session_state.get("filter_encounter_type"),
    )


def choose_filters(claims: tuple[Claim, ...], periods: dict[str, tuple[date, date]], default_period: str) -> None:
    with st.container(key="rcm-filters"):
        columns = st.columns([1.2, 1.2, 1.15, 1.2, 0.95], vertical_alignment="bottom")
        columns[0].selectbox(
            "Reporting period", list(periods), key=REPORT_PERIOD_KEY, on_change=clear_drill,
        )
        for column, field in zip(columns[1:4], GLOBAL_FILTER_FIELDS):
            options = sorted({getattr(claim, field) for claim in claims})
            column.selectbox(
                FILTER_LABELS[field], options, index=None, key=f"filter_{field}", placeholder=FILTER_PLACEHOLDERS[field],
                format_func=str if field in ("payer", "provider_id") else label,
                on_change=clear_drill,
            )
        columns[4].button(
            "Reset filters", on_click=reset_filters, args=(default_period,),
            width="stretch", key="reset_filters",
        )


def quality_issue_index(quality: Quality | None) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    if quality is None:
        return index
    for issue in quality.original_issues:
        claim_id = issue["record_ref"]
        if claim_id:
            index.setdefault(claim_id, []).append(issue)
    return index


def table_matches(
    claims: tuple[Claim, ...], query: str, status: str, sort_mode: str,
    issues_by_claim: dict[str, list[dict]], flagged_only: bool = False,
) -> list[Claim]:
    candidates = claims
    if flagged_only:
        candidates = tuple(claim for claim in candidates if claim.claim_id in issues_by_claim)
    if status != TABLE_STATUSES[0]:
        selected_status = status.casefold()
        candidates = tuple(claim for claim in candidates if claim.status == selected_status)
    term = query.strip().casefold()
    if term:
        fields = ("claim_id", "payer", "provider_id", "status", "denial_reason", "encounter_type")
        candidates = tuple(
            claim for claim in candidates
            if any(term in (getattr(claim, field) or "").casefold() for field in fields)
            or any(
                term in " ".join(str(issue.get(field) or "") for field in (
                    "rule_id", "source_table", "issue_category", "severity", "resolution_status", "recommended_action",
                )).casefold()
                for issue in issues_by_claim.get(claim.claim_id, ())
            )
        )
    return search_claims(candidates, "", sort_mode)


def count_linked_findings(rows: tuple[Claim, ...], issues_by_claim: dict[str, list[dict]]) -> int:
    return sum(claim.claim_id in issues_by_claim for claim in rows)


def compact_money(value: Decimal) -> str:
    """Keep KPI amounts legible in the five-column reference layout."""
    if abs(value) >= Decimal("1000000"):
        return f"${value / Decimal('1000000'):,.2f}M"
    if abs(value) >= Decimal("1000"):
        return f"${value / Decimal('1000'):,.1f}K"
    return money(value)


def claim_metrics(rows: tuple[Claim, ...], page: int, quality: Quality | None,
                  issues_by_claim: dict[str, list[dict]]) -> None:
    metrics = summarize(rows)
    claim_count = ("Total claims", quantity(metrics.count), "Unique claims in this view.")
    billed = ("Billed amount", compact_money(metrics.billed), "Gross submitted charges; rounded for display.")
    payer = ("Payer payments", compact_money(metrics.payer_paid), "Source-reported payer payments; rounded for display.")
    denied = (
        "Observed denial rate", rate(metrics.denial_rate),
        "Denied claims divided by claims in view.",
    )
    pending = ("Pending claims", quantity(metrics.pending), "Claims with observed pending status.")
    turnaround = (
        "Mean time to payment", days(metrics.average_days),
        "Submission-to-payment days for paid claims.",
    )
    match page:
        case 0:
            qa_value = "Unavailable" if quality is None else quantity(count_linked_findings(rows, issues_by_claim))
            qa_note = "Unique claims with linkable source QA findings."
            if quality is None:
                qa_note = "Source QA evidence is not available in the validated export pair."
            metric_row([
                claim_count,
                billed,
                payer,
                ("Denied claims", quantity(metrics.denied), "Claims with observed denied status."),
                denied,
                ("Claims with QA findings", qa_value, qa_note),
            ])
        case 1:
            metric_row([
                claim_count,
                ("Denied claims", quantity(metrics.denied), "Claims with observed denied status."),
                denied,
                ("Denied billed value", compact_money(metrics.denied_billed), "Gross charges on claims marked denied."),
                pending,
            ])
        case 2:
            metric_row([
                billed, ("Allowed amount", compact_money(metrics.allowed), "Source-reported allowed amounts; rounded for display."),
                payer, ("Patient responsibility", compact_money(metrics.responsibility), "Assigned source amount; rounded for display."),
                turnaround,
            ])
        case 3:
            metric_row([
                claim_count,
                ("Active payers", quantity(len(group_by(rows, "payer"))), "Distinct payer labels in this view."),
                ("Active providers", quantity(len(group_by(rows, "provider_id"))), "Distinct provider IDs in this view."),
                denied,
                turnaround,
            ])
        case 4:
            if quality is None:
                missing_quality_metrics()
                return
            original = quality.original_summary
            tests = quality.test_summary
            pass_rate = Decimal(original["rules_passed"]) / Decimal(original["rules_total"]) if original["rules_total"] else None
            metric_row([
                ("Source rows", quantity(original["source_rows"]), "Rows across the seven source tables."),
                ("Rule pass rate", rate(pass_rate), "Passing rules divided by rules evaluated."),
                ("Original findings", quantity(original["issues_total"]), "Rule findings across original source tables."),
                ("Claims with findings", quantity(count_linked_findings(rows, issues_by_claim)), "Unique filtered claims with linkable findings."),
                ("Injected tests passed", f"{tests['tests_passed']:,} / {tests['rules_total']:,}", "Rules tested on separate corrupted copies."),
            ])


def page_metric_labels(page: int) -> tuple[str, ...]:
    return (
        ("Total claims", "Billed amount", "Payer payments", "Denied claims", "Observed denial rate", "Claims with QA findings"),
        ("Total claims", "Denied claims", "Observed denial rate", "Denied billed value", "Pending claims"),
        ("Billed amount", "Allowed amount", "Payer payments", "Patient responsibility", "Mean time to payment"),
        ("Total claims", "Active payers", "Active providers", "Observed denial rate", "Mean time to payment"),
        ("Source rows", "Rule pass rate", "Original findings", "Claims with findings", "Injected tests passed"),
    )[page]


def missing_quality_metrics() -> None:
    metric_row([
        (title, "—", "Requires a matching PostgreSQL-reconciled quality export.")
        for title in page_metric_labels(4)
    ])


def overview(rows: tuple[Claim, ...], filters: ClaimFilters, qa_issues: list[dict]) -> None:
    trend, reasons = st.columns([1.7, 1])
    with trend.container(border=True):
        heading, selector = st.columns([3, 1], vertical_alignment="center")
        mode = selector.selectbox(
            "Trend metric", ["Financial", "Claim volume"],
            index=0 if st.session_state.trend == "Financial" else 1,
            key="trend_mode", on_change=save_trend, label_visibility="collapsed",
        )
        heading.subheader("Monthly claim volume" if mode == "Claim volume" else "Billing & payment trends")
        st.caption("Grouped by claim submission month.")
        monthly_chart(rows, filters.start, filters.end, "volume" if mode == "Claim volume" else "amount", "overview_trend")
    denied = tuple(claim for claim in rows if claim.status == "denied")
    with reasons.container(border=True):
        st.subheader("Top denial reasons")
        ranked_chart(
            Counter(claim.denial_reason for claim in denied if claim.denial_reason),
            "denial_reason", "overview_reasons", color=LAVENDER,
        )
    status, watch = st.columns(2)
    with status.container(border=True):
        st.subheader("Claim status distribution")
        status_chart(rows, "overview_status")
    with watch.container(border=True):
        st.subheader("Operational watchlist")
        denial_watchlist(denied, qa_issues)


def denials(rows: tuple[Claim, ...], filters: ClaimFilters) -> None:
    denied = tuple(claim for claim in rows if claim.status == "denied")
    trend, reasons = st.columns([1.7, 1])
    with trend.container(border=True):
        st.subheader("Denial rate over time")
        st.caption(MATURITY)
        monthly_chart(rows, filters.start, filters.end, "denials", "denial_trend")
        monthly_counts = []
        for month, claims in sorted(group_by(rows, "month").items()):
            metrics = summarize(claims)
            monthly_counts.append({
                "Submission month": month.isoformat()[:7], "Denied claims": metrics.denied,
                "Total claims": metrics.count, "Observed denial rate": rate(metrics.denial_rate),
            })
        if monthly_counts:
            with st.expander("Monthly denominators"):
                st.dataframe(pd.DataFrame(monthly_counts), hide_index=True)
    with reasons.container(border=True):
        st.subheader("Denial reasons")
        st.caption("Recorded denied-claim count · select a reason to filter")
        ranked_chart(
            Counter(claim.denial_reason for claim in denied if claim.denial_reason),
            "denial_reason", "denial_reasons", color=RED,
        )
        with st.expander("Cumulative denial-reason analysis"):
            pareto_chart(rows, "denial_reasons_pareto")
    denied_value, status = st.columns(2)
    with denied_value.container(border=True):
        st.subheader("Denied billed value by payer")
        st.caption("Gross billed charges on claims with observed denied status.")
        values = {payer: summarize(claims).billed for payer, claims in group_by(denied, "payer").items()}
        ranked_chart(values, "payer", "denial_payer", color=RED, formatter=money, axis_format="$,.0f")
    with status.container(border=True):
        st.subheader("Claim status distribution")
        status_chart(rows, "denial_status")
    with st.expander("Compare observed denial rates by payer and provider"):
        comparison(rows, "payer", "Payer denial-rate comparison")
        comparison(rows, "provider_id", "Provider denial-rate comparison")


def revenue(rows: tuple[Claim, ...], filters: ClaimFilters) -> None:
    st.caption(f"{SELF_PAY} Patient responsibility is an assigned amount; the source has no patient-payment transactions.")
    trend, assigned = st.columns([1.7, 1])
    with trend.container(border=True):
        st.subheader("Billing & payment trends")
        st.caption("Monthly submitted charges and source-reported payer payments.")
        monthly_chart(rows, filters.start, filters.end, "amount", "revenue_trend")
    with assigned.container(border=True):
        st.subheader("Patient responsibility by payer")
        st.caption("Assigned source amount; not evidence of payment received.")
        values = {payer: summarize(claims).responsibility for payer, claims in group_by(rows, "payer").items()}
        ranked_chart(values, "payer", "revenue_responsibility", color=LAVENDER, formatter=money, axis_format="$,.0f")
    comparison(rows, "payer", "Payer performance summary")
    payment_timing_comparison(rows)
    with st.expander("Financial reconciliation by claim status"):
        status_reconciliation(rows)


def performance(rows: tuple[Claim, ...]) -> None:
    st.caption(SELF_PAY)
    left, right = st.columns(2)
    with left.container(border=True):
        st.subheader("Payer payments by payer")
        values = {payer: summarize(claims).payer_paid for payer, claims in group_by(rows, "payer").items()}
        ranked_chart(values, "payer", "performance_payer", formatter=money, axis_format="$,.0f")
    with right.container(border=True):
        st.subheader("Provider claim volume")
        ranked_chart(Counter(claim.provider_id for claim in rows), "provider_id", "performance_provider", color=LAVENDER)
    comparison(rows, "payer", "Payer performance summary")
    comparison(rows, "provider_id", "Provider performance summary")
    with st.expander("Explore denial rates by payer and encounter type"):
        denial_heatmap(rows)


def quality_page(
    quality: Quality | None, rows: tuple[Claim, ...], issues_by_claim: dict[str, list[dict]], quality_error: str | None,
) -> None:
    if quality is None:
        st.warning(f"QA evidence is unavailable. {quality_error or 'A matching quality.json export has not been provided.'}")
        left, right = st.columns([1.7, 1])
        with left:
            placeholder_panel("Original rule pass rate", "This panel requires the PostgreSQL-reconciled quality export.")
        with right:
            placeholder_panel("Exceptions by rule", "No rule-level findings are shown without validated QA evidence.")
        left, right = st.columns(2)
        with left:
            placeholder_panel("Flagged claims by encounter type", "Linkable source QA findings are not available.")
        with right:
            placeholder_panel("Operational watchlist", "Validated denial and QA evidence is required for these insights.")
        return

    summary = quality.original_summary
    st.info("Original-source findings and deliberately injected test-copy detections are reported separately.")
    rule_rows = quality.original_rules
    rate_rows = [row for row in rule_rows if row["pass_rate"] is not None]
    rate_rows = sorted(rate_rows, key=lambda item: (item["pass_rate"], item["rule_id"]))[:8]
    issue_rows = sorted((row for row in rule_rows if row["issue_count"]),
                        key=lambda item: (-item["issue_count"], item["rule_id"]))[:6]
    left, right = st.columns([1.7, 1])
    with left.container(border=True):
        st.subheader("Original rule pass rate")
        st.caption("Rule-level share of tested rows with no finding.")
        if rate_rows:
            shown = rate_rows[::-1]
            chart = figure(260)
            chart.add_bar(
                x=[float(item["pass_rate"]) for item in shown], y=[item["rule_id"] for item in shown],
                marker_color=INDIGO, orientation="h", text=[rate(item["pass_rate"]) for item in shown],
                textposition="auto", customdata=[[item["tested_rows"], item["issue_count"]] for item in shown],
                hovertemplate="%{y}<br>%{x:.2%} pass rate<br>%{customdata[1]:,} findings / %{customdata[0]:,} tested rows<extra></extra>",
            )
            chart.update_xaxes(range=[0, 1], tickformat=".0%", showgrid=True)
            chart.update_yaxes(showgrid=False)
            st.plotly_chart(chart, theme=None, config={"displaylogo": False}, width="stretch")
        else:
            st.info("No original-source rules were evaluated.")
    with right.container(border=True):
        st.subheader("Exceptions by rule")
        st.caption("Original-source rule findings.")
        if issue_rows:
            shown = issue_rows[::-1]
            chart = figure(260)
            chart.add_bar(
                x=[item["issue_count"] for item in shown], y=[item["rule_id"] for item in shown],
                marker_color=RED, orientation="h", text=[quantity(item["issue_count"]) for item in shown],
                textposition="auto", hovertemplate="%{y}<br>%{x:,} findings<extra></extra>",
            )
            chart.update_xaxes(rangemode="tozero", tickformat=",d")
            chart.update_yaxes(showgrid=False)
            st.plotly_chart(chart, theme=None, config={"displaylogo": False}, width="stretch")
        else:
            st.success("The exported original rules report zero findings.")

    flagged_ids = {claim.claim_id for claim in rows}.intersection(issues_by_claim)
    encounter_counts = Counter(claim.encounter_type for claim in rows if claim.claim_id in flagged_ids)
    type_card, watch = st.columns(2)
    with type_card.container(border=True):
        st.subheader("Flagged claims by encounter type")
        st.caption("Unique claims with linkable claim-level original-source findings.")
        if encounter_counts:
            ranked_chart(encounter_counts, "encounter_type", "qa_encounter_type", color=RED)
        else:
            st.info("No linkable claim-level source findings match the current filters.")
    with watch.container(border=True):
        st.subheader("Operational watchlist")
        denied = tuple(claim for claim in rows if claim.status == "denied")
        selected_issues = [issue for claim_id in flagged_ids for issue in issues_by_claim[claim_id]]
        denial_watchlist(denied, selected_issues)

    with st.expander("Original source rule results"):
        st.caption("The rule table includes all source tables; linked claim details in the register are limited to claim IDs in the validated export.")
        rule_table(quality.original_rules, "pass_rate")
    with st.expander("Injected-error test evidence"):
        test_evidence(quality)


def page_slug(page: int) -> str:
    return PAGES[page].lower().replace(" & ", "-").replace(" ", "-")


def claim_detail(claim: Claim, issues: list[dict] | None = None) -> None:
    st.subheader(claim.claim_id)
    details = {
        "Submitted": claim.submitted_at.isoformat(sep=" "), "Claim status": label(claim.status),
        "Insurance payer": claim.payer, "Provider ID": claim.provider_id,
        "Encounter type": label(claim.encounter_type), "Billed amount": money(claim.billed_amount),
        "Allowed amount": money(claim.allowed_amount), "Payer payment": money(claim.payer_paid_amount),
        "Assigned patient responsibility": money(claim.patient_responsibility),
        "Submission to payment": days(claim.submission_to_payment_days),
        "Denial reason": label(claim.denial_reason) if claim.denial_reason else "—",
    }
    if issues:
        details["Source QA findings"] = "; ".join(sorted({label(issue["issue_category"]) for issue in issues}))
    st.table(pd.DataFrame(details.items(), columns=["Field", "Value"]), hide_index=True)


@st.dialog("Claim details")
def open_claim_detail(claim: Claim, issues: list[dict] | None = None) -> None:
    claim_detail(claim, issues)


def investigation(
    rows: tuple[Claim, ...], page: int, matches: list[Claim], issues_by_claim: dict[str, list[dict]], quality_available: bool,
) -> None:
    with st.container(border=True):
        title = "QA exception register" if page == 4 else "Claim-level investigation"
        caption = (
            "Linkable original-source claim findings; injected-error test details remain separate."
            if page == 4 else "Search, sort and open a claim to inspect its financial and source context."
        )
        st.subheader(title)
        st.caption(caption)
        with st.container(key="rcm-table-controls"):
            search, status_col, sort = st.columns([2.5, 1.15, 1.25])
            search.text_input(
                "Search claims", key="claim_search", on_change=reset_table_page,
                placeholder="Claim ID, payer, provider, status, reason, or QA issue",
            )
            status_col.selectbox("Claim status", TABLE_STATUSES, key="table_status", on_change=reset_table_page)
            sort.selectbox("Sort claims", list(SORTS), key="claim_sort", on_change=save_sort)
        if not matches:
            st.dataframe(pd.DataFrame(columns=TABLE_COLUMNS), hide_index=True, width="stretch", height=188)
            if page == 4 and not quality_available:
                st.info("QA exceptions cannot be filtered or exported until the matching quality.json is available.")
            else:
                st.info("No matching claims. Adjust the report filters or search, or reset filters to restore the cohort.")
            st.session_state.claim_table_page = 0
            return

        page_count = (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE
        active_page = min(st.session_state.claim_table_page, page_count - 1)
        st.session_state.claim_table_page = active_page
        start = active_page * PAGE_SIZE
        displayed = matches[start:start + PAGE_SIZE]
        table_data = []
        for claim in displayed:
            issues = issues_by_claim.get(claim.claim_id, [])
            if not quality_available:
                quality_text = "Unavailable"
            elif issues:
                quality_text = "; ".join(sorted({label(issue["issue_category"]) for issue in issues}))
            else:
                quality_text = "No linked finding"
            table_data.append({
                "Claim ID": claim.claim_id,
                "Submission date": claim.submitted_at.date(),
                "Payer": claim.payer,
                "Provider ID": claim.provider_id,
                "Status": label(claim.status),
                "Billed amount": money(claim.billed_amount),
                "Payer payment": money(claim.payer_paid_amount),
                "Data quality": quality_text,
            })
        st.dataframe(pd.DataFrame(table_data, columns=TABLE_COLUMNS), hide_index=True, width="stretch", height=292)

        info, previous, next_page = st.columns([3, 1, 1], vertical_alignment="center")
        info.caption(f"{start + 1:,}–{start + len(displayed):,} of {len(matches):,} claims")
        previous.button("Previous", disabled=active_page == 0, on_click=change_table_page,
                        args=(active_page - 1,), width="stretch", key="claim_previous")
        next_page.button("Next", disabled=active_page + 1 == page_count, on_click=change_table_page,
                         args=(active_page + 1,), width="stretch", key="claim_next")
        detail, _ = st.columns([2, 3], vertical_alignment="bottom")
        selection = detail.selectbox(
            "Claim details", tuple(claim.claim_id for claim in displayed), index=None,
            placeholder="Select a claim ID", key=f"detail_choice_{page}_{active_page}",
        )
        if selection and detail.button("Open claim details", key="open_claim_detail"):
            claim = next(item for item in displayed if item.claim_id == selection)
            open_claim_detail(claim, issues_by_claim.get(claim.claim_id, []))


def render_brand_and_nav() -> str:
    with st.sidebar:
        with st.container(key="rcm-brand"):
            st.markdown(
                '<div class="rcm-brand-mark"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 12h4l3-7 4 14 3-7h4"/></svg></div>'
                '<div><strong>RCM Intelligence</strong><small>Operations analytics</small></div>',
                unsafe_allow_html=True,
            )
        with st.container(key="rcm-nav-title"):
            st.markdown("ANALYTICS WORKSPACE")
        selected_page = st.radio(
            "Analytics workspace", PAGES, key="report_page", on_change=navigate,
            format_func=lambda page: f"{NAV_MARKS[page]}   {page}",
            label_visibility="collapsed",
        )
    return selected_page


def render_topbar(page_title: str) -> None:
    with st.container(key="rcm-topbar"):
        st.markdown(f"Analytics&nbsp;&nbsp;›&nbsp;&nbsp;<strong>{escape(page_title)}</strong>", unsafe_allow_html=True)


def render_heading(page: int, export_rows: list[Claim], verified: bool) -> None:
    with st.container(key="rcm-heading"):
        title, action = st.columns([4.2, 1.6], vertical_alignment="center")
        title.markdown("<div class='rcm-eyebrow'>Revenue cycle management</div>", unsafe_allow_html=True)
        title.title(PAGES[page])
        title.caption(DESCRIPTIONS[page])
        with action.container(key="rcm-heading-action"):
            if verified:
                st.download_button(
                    "Export claims CSV", claims_csv(export_rows), f"rcm360-{page_slug(page)}.csv",
                    "text/csv", key=f"export_{page}", disabled=not export_rows, on_click="ignore",
                    width="content", icon=":material/download:",
                )
            else:
                st.button("Export claims CSV", disabled=True, width="content", icon=":material/download:")
        if page == 0:
            st.markdown(
                "<div class='rcm-health-banner'>"
                "<span class='rcm-health-banner-mark' aria-hidden='true'>"
                "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'>"
                "<path d='M12 3v7m0 4v7M3 12h7m4 0h7'/><path d='M2 12h5l2-4 4 8 3-5h6'/></svg></span>"
                "<span class='rcm-health-banner-copy'><strong>Healthcare revenue cycle</strong>"
                "<small>Claims · payments · denial patterns</small></span>"
                "<svg class='rcm-health-banner-art' viewBox='0 0 300 56' fill='none' aria-hidden='true'>"
                "<path d='M2 30h68l10-2 9-17 13 31 14-23 10 11h63l9-2 9-15 13 28 12-22 10 11h58' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>"
                "<path d='M276 9v18m-9-9h18' stroke='currentColor' stroke-width='2' stroke-linecap='round'/></svg>"
                "</div>",
                unsafe_allow_html=True,
            )


def render_empty_filters() -> None:
    with st.container(key="rcm-empty-filters"):
        cols = st.columns([1.2, 1.2, 1.15, 1.2, 0.95], vertical_alignment="bottom")
        cols[0].selectbox("Reporting period", ["Waiting for validated export"], disabled=True)
        cols[1].selectbox("Insurance payer", ["Unavailable"], disabled=True)
        cols[2].selectbox("Provider", ["Unavailable"], disabled=True)
        cols[3].selectbox("Encounter type", ["Unavailable"], disabled=True)
        cols[4].button("Reset filters", disabled=True, width="stretch")


def render_count(rows: tuple[Claim, ...], claims: tuple[Claim, ...], drill) -> None:
    with st.container(key="rcm-count-row"):
        count, chip = st.columns([3, 2], vertical_alignment="center")
        count.markdown(f"Showing <strong>{len(rows):,}</strong> of {len(claims):,} validated claims", unsafe_allow_html=True)
        if drill:
            chip.button(f"Clear drill · {label(drill[1])}", on_click=clear_drill, key="clear_drill")


def render_missing_metrics(page: int) -> None:
    metric_row([
        (title, "—", "Requires a PostgreSQL-reconciled claim export.")
        for title in page_metric_labels(page)
    ])


def placeholder_panel(title: str, message: str) -> None:
    with st.container(border=True):
        st.subheader(title)
        st.info(message)


def render_missing_analytics(page: int, quality_missing: bool) -> None:
    message = "No chart is shown until the validated claim export is available."
    if page == 0:
        left, right = st.columns([1.7, 1])
        with left:
            placeholder_panel("Billing & payment trends", message)
        with right:
            placeholder_panel("Top denial reasons", message)
        left, right = st.columns(2)
        with left:
            placeholder_panel("Claim status distribution", message)
        with right:
            placeholder_panel("Operational watchlist", "Validated claim and QA evidence is required for these insights.")
    elif page == 1:
        left, right = st.columns([1.7, 1])
        with left:
            placeholder_panel("Denial rate over time", message)
        with right:
            placeholder_panel("Denial reasons", message)
        left, right = st.columns(2)
        with left:
            placeholder_panel("Denied billed value by payer", message)
        with right:
            placeholder_panel("Claim status distribution", message)
    elif page == 2:
        left, right = st.columns([1.7, 1])
        with left:
            placeholder_panel("Billing & payment trends", message)
        with right:
            placeholder_panel("Patient responsibility by payer", "No source amounts are shown until the validated claim export is available.")
        placeholder_panel("Payer performance summary", message)
    elif page == 3:
        left, right = st.columns(2)
        with left:
            placeholder_panel("Payer payments by payer", message)
        with right:
            placeholder_panel("Provider claim volume", message)
        placeholder_panel("Payer performance summary", message)
        placeholder_panel("Provider performance summary", message)
    else:
        qa_message = "A matching quality.json export is required to show original-source findings." if quality_missing else message
        left, right = st.columns([1.7, 1])
        with left:
            placeholder_panel("Original rule pass rate", qa_message)
        with right:
            placeholder_panel("Exceptions by rule", qa_message)
        left, right = st.columns(2)
        with left:
            placeholder_panel("Flagged claims by encounter type", qa_message)
        with right:
            placeholder_panel("Operational watchlist", qa_message)


def render_missing_investigation(page: int, error: str) -> None:
    with st.container(border=True):
        st.subheader("QA exception register" if page == 4 else "Claim-level investigation")
        st.caption("Search and inspect records after a reconciled claim export is provided.")
        query, status, sort = st.columns([2.5, 1.15, 1.25])
        query.text_input("Search claims", disabled=True, placeholder="Waiting for validated records")
        status.selectbox("Claim status", ["Unavailable"], disabled=True)
        sort.selectbox("Sort claims", ["Unavailable"], disabled=True)
        st.dataframe(pd.DataFrame(columns=TABLE_COLUMNS), hide_index=True, width="stretch", height=188)
        st.info(error)


def render_footer() -> None:
    with st.container(key="rcm-footer"):
        st.markdown("RCM360 · Revenue cycle analytics")


def main() -> None:
    st.set_page_config(page_title="RCM360 | Revenue cycle analytics", page_icon="📊", layout="wide")
    apply_theme()
    st.session_state.setdefault("drill", None)
    st.session_state.setdefault("claim_table_page", 0)
    st.session_state.setdefault("trend", "Financial")
    st.session_state.setdefault("sort_mode", next(iter(SORTS)))
    selected_page = render_brand_and_nav()
    page = PAGES.index(selected_page)

    metadata = None
    claims: tuple[Claim, ...] = ()
    export_error = None
    try:
        metadata, claims = parse_claims(read_json(DATA_DIR / "claims.json"))
    except ExportError as error:
        export_error = str(error)

    quality = None
    quality_error = None
    if metadata is not None and claims:
        try:
            quality = parse_quality(read_json(DATA_DIR / "quality.json"), metadata, claims)
        except ExportError as error:
            quality_error = str(error)
    issues_by_claim = quality_issue_index(quality)
    verified = metadata is not None
    render_topbar(selected_page)

    if not claims:
        render_heading(page, [], verified=metadata is not None)
        render_empty_filters()
        with st.container(key="rcm-count-row"):
            st.markdown("No validated claim records are available for this view.")
        render_missing_metrics(page)
        message = export_error or "The validated claims export contains zero records."
        with st.container(key="rcm-empty-state"):
            st.markdown(
                f"**Validated dashboard data is unavailable.** {escape(message)} "
                "The dashboard reads PostgreSQL-reconciled JSON and does not substitute prototype or test values.",
                unsafe_allow_html=True,
            )
        render_missing_analytics(page, quality_missing=True)
        render_missing_investigation(page, message)
        render_footer()
        return

    dates = [claim.submitted_at.date() for claim in claims]
    bounds = (min(dates), max(dates))
    periods, default_period = reporting_periods(bounds)
    initialize_filter_state(claims, periods, default_period)
    filters = selected_filters(periods)
    drill = st.session_state.drill
    rows = filter_claims(claims, filters, drill)
    only_flagged = page == 4
    export_rows = table_matches(
        rows, st.session_state.claim_search, st.session_state.table_status,
        st.session_state.claim_sort, issues_by_claim, flagged_only=only_flagged,
    )

    render_heading(page, export_rows, verified=True)
    choose_filters(claims, periods, default_period)
    render_count(rows, claims, drill)
    if drill and drill[0] in ("status", "denial_reason"):
        st.caption("Outcome filters condition observed denial rates on selected claim status. Clear outcome filters to return to the full cohort.")
    if page != 4:
        claim_metrics(rows, page, quality, issues_by_claim)
        qa_issues = [issue for claim in rows for issue in issues_by_claim.get(claim.claim_id, [])]
        match page:
            case 0:
                overview(rows, filters, qa_issues)
            case 1:
                denials(rows, filters)
            case 2:
                revenue(rows, filters)
            case 3:
                performance(rows)
    else:
        claim_metrics(rows, page, quality, issues_by_claim)
        quality_page(quality, rows, issues_by_claim, quality_error)
    investigation(rows, page, export_rows, issues_by_claim, quality_available=quality is not None)
    render_footer()


if __name__ == "__main__":
    main()
