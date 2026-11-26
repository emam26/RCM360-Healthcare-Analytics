"""Run with `python -m streamlit run dashboard/app.py` from the repository root."""

from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_shadcn_ui import v2 as ui

from dashboard.model import (
    FILTER_FIELDS, SORTS, ClaimFilters, ExportError, claims_csv, filter_claims,
    group_by, parse_claims, read_json, search_claims, summarize,
)
from dashboard.quality import original_evidence, parse_quality, test_evidence
from dashboard.views import (
    LAVENDER, MATURITY, RED, SELF_PAY, comparison, days, denial_heatmap, denial_watchlist,
    label, metric_row, money, monthly_chart, pareto_chart, quantity, ranked_chart, rate,
    status_chart, status_reconciliation,
)


DATA_DIR = Path(__file__).resolve().parent / "data"
PAGES = (
    "Executive overview", "Claims & denials", "Revenue & payments", "Payer & provider", "Data quality & QA",
)
DESCRIPTIONS = (
    "Monitor claim volume, billed charges, payer payments, and observed denial patterns.",
    "Investigate the reasons and gross billed amounts associated with observed denials.",
    "Compare billed and allowed amounts, payer payments, and assigned patient responsibility.",
    "Compare claim volume, payer payments, and observed denial rates across payer and provider groups.",
    "Inspect original source validation and the detection of deliberately injected errors.",
)
FILTER_LABELS = ("Insurance payer", "Provider ID", "Claim status", "Encounter type")
PAGE_SIZE = 6


def clear_drill() -> None:
    st.session_state.drill = None
    st.session_state.claim_table_page = 0
    for key in list(st.session_state):
        if key.endswith("_choose"):
            del st.session_state[key]


def reset_filters(bounds) -> None:
    st.session_state.submission_dates = bounds
    for field in FILTER_FIELDS:
        st.session_state[f"filter_{field}"] = None
    st.session_state.claim_search = ""
    st.session_state.sort_mode = next(iter(SORTS))
    st.session_state.claim_sort = st.session_state.sort_mode
    clear_drill()


def choose_filters(claims, bounds) -> ClaimFilters | None:
    with st.container(border=True):
        dates, reset = st.columns([4, 1], vertical_alignment="bottom")
        with dates:
            selected = st.date_input(
                "Submission dates", value=bounds, min_value=bounds[0], max_value=bounds[1],
                key="submission_dates", on_change=clear_drill,
            )
        with reset:
            st.button("Reset filters", on_click=reset_filters, args=(bounds,), width="stretch")
        active = {}
        for column, (field, title) in zip(st.columns(4), zip(FILTER_FIELDS, FILTER_LABELS)):
            options = sorted({getattr(claim, field) for claim in claims})
            active[field] = column.selectbox(
                title, options, index=None, key=f"filter_{field}", placeholder="All",
                format_func=str if field in ("provider_id", "payer") else label, on_change=clear_drill,
            )
    if len(selected) != 2:
        st.info("Choose a start and end date to apply the submission range.")
        return None
    return ClaimFilters(*selected, **active)


def claim_metrics(rows, page: int) -> None:
    metrics = summarize(rows)
    claim_count = ("Total claims", quantity(metrics.count), "One row per claim in the current selection.")
    billed = ("Billed amount", money(metrics.billed), "Gross submitted charges in the current selection.")
    payer = ("Payer payments", money(metrics.payer_paid), "Source-reported payer payment amounts.")
    denominator = "Denied claims divided by all claims in the current selection."
    denied = ("Observed denial rate", rate(metrics.denial_rate), denominator)
    pending = ("Pending claims", quantity(metrics.pending), "Claims with observed status pending.")
    turnaround = ("Mean time to payment", days(metrics.average_days), "Submission-to-payment days among paid claims only.")
    match page:
        case 0:
            metric_row([claim_count, billed, payer, denied, pending])
        case 1:
            metric_row([
                claim_count, ("Denied claims", quantity(metrics.denied), "Claims with observed status denied."), denied,
                ("Denied billed value", money(metrics.denied_billed), "Gross billed exposure on denied claims."), pending,
            ])
        case 2:
            metric_row([
                billed, ("Allowed amount", money(metrics.allowed), "Sum of the source allowed-amount field."), payer,
                ("Assigned responsibility", money(metrics.responsibility), "Patient responsibility assigned by the source."),
                turnaround,
            ])
        case 3:
            metric_row([
                claim_count, ("Payers", quantity(len(group_by(rows, "payer"))), "Distinct payer labels in this selection."),
                ("Providers", quantity(len(group_by(rows, "provider_id"))), "Distinct provider IDs in this selection."),
                denied, turnaround,
            ])


def overview(rows, filters) -> None:
    trend, reasons = st.columns([1.7, 1])
    with trend.container(border=True):
        mode = st.segmented_control("Trend metric", ["Financial", "Claim volume"], default=st.session_state.trend,
                                    key="trend_mode", on_change=save_trend)
        st.subheader("Monthly claim volume" if mode == "Claim volume" else "Billing & payment trends")
        st.caption("Grouped by claim submission month.")
        monthly_chart(rows, filters.start, filters.end, "volume" if mode == "Claim volume" else "amount", "overview_trend")
    denied = [claim for claim in rows if claim.status == "denied"]
    with reasons.container(border=True):
        st.subheader("Top denial reasons")
        ranked_chart(Counter(claim.denial_reason for claim in denied if claim.denial_reason), "denial_reason", "overview_reasons", color=LAVENDER)
    status, watch = st.columns(2)
    with status.container(border=True):
        st.subheader("Claim status distribution")
        status_chart(rows, "overview_status")
    with watch.container(border=True):
        st.subheader("Operational watchlist")
        denial_watchlist(denied)


def denials(rows, filters) -> None:
    denied = [claim for claim in rows if claim.status == "denied"]
    trend, status = st.columns([1.7, 1])
    with trend.container(border=True):
        st.subheader("Observed denial rate by submission month")
        st.caption(MATURITY)
        monthly_chart(rows, filters.start, filters.end, "denials", "denial_trend")
        counts = []
        for month, claims in sorted(group_by(rows, "month").items()):
            result = summarize(claims)
            counts.append({"Submission month": month.isoformat()[:7], "Denied": result.denied,
                           "Claims": result.count, "Observed denial rate": rate(result.denial_rate)})
        if counts:
            with st.expander("Monthly denominators"):
                st.dataframe(pd.DataFrame(counts), hide_index=True)
    with status.container(border=True):
        st.subheader("Claim status distribution")
        status_chart(rows, "denial_status")
    with st.container(border=True):
        st.subheader("Recorded denial reasons · Pareto view")
        pareto_chart(rows, "denial_reasons")
    with st.container(border=True):
        st.subheader("Denied billed value by payer")
        st.caption("Gross billed exposure on claims with observed denied status.")
        values = {payer: summarize(claims).billed for payer, claims in group_by(denied, "payer").items()}
        ranked_chart(values, "payer", "denial_payer", color=RED, formatter=money, axis_format="$,.0f")
    comparison(rows, "payer", "Observed denial rates by payer")
    comparison(rows, "provider_id", "Observed denial rates by provider")


def revenue(rows, filters) -> None:
    st.caption(f"{SELF_PAY} Patient responsibility is an assigned amount. The source records no patient payment transactions.")
    trend, assigned = st.columns([1.7, 1])
    with trend.container(border=True):
        st.subheader("Billing & payment trends")
        st.caption("Grouped by claim submission month.")
        monthly_chart(rows, filters.start, filters.end, "amount", "revenue_trend")
    with assigned.container(border=True):
        st.subheader("Assigned responsibility by payer")
        values = {payer: summarize(claims).responsibility for payer, claims in group_by(rows, "payer").items()}
        ranked_chart(values, "payer", "revenue_responsibility", color=LAVENDER, formatter=money, axis_format="$,.0f")
    status_reconciliation(rows)
    comparison(rows, "payer", "Payer performance summary")


def performance(rows) -> None:
    st.caption(SELF_PAY)
    left, right = st.columns(2)
    with left.container(border=True):
        st.subheader("Payer payments by payer")
        values = {payer: summarize(claims).payer_paid for payer, claims in group_by(rows, "payer").items()}
        ranked_chart(values, "payer", "performance_payer", formatter=money, axis_format="$,.0f")
    with right.container(border=True):
        st.subheader("Provider claim volume")
        ranked_chart(Counter(claim.provider_id for claim in rows), "provider_id", "performance_provider", color=LAVENDER)
    denial_heatmap(rows)
    comparison(rows, "payer", "Payer performance summary")
    comparison(rows, "provider_id", "Provider performance summary")


def reset_table_page() -> None:
    st.session_state.claim_table_page = 0


def save_trend() -> None:
    st.session_state.trend = st.session_state.trend_mode


def save_sort() -> None:
    st.session_state.sort_mode = st.session_state.claim_sort
    reset_table_page()


def navigate() -> None:
    clear_drill()
    st.session_state.claim_search = ""


@st.dialog("Claim details")
def claim_detail(claim) -> None:
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
    st.table(pd.DataFrame(details.items(), columns=["Field", "Value"]), hide_index=True)


def investigation(rows, page: int) -> None:
    with st.container(border=True):
        st.subheader("Claim-level investigation")
        search, sort = st.columns([3, 2])
        query = search.text_input("Search claims", key="claim_search", on_change=reset_table_page,
                                  placeholder="Claim ID, payer, provider, status, or reason")
        sort_mode = sort.selectbox("Sort claims", list(SORTS), index=list(SORTS).index(st.session_state.sort_mode),
                                   key="claim_sort", on_change=save_sort)
        matches = search_claims(rows, query, sort_mode)
        if not matches:
            st.info("No matching claims. Adjust the report filters or search.")
            return
        page_count = (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE
        active_page = min(st.session_state.claim_table_page, page_count - 1)
        st.session_state.claim_table_page = active_page
        start = active_page * PAGE_SIZE
        displayed = matches[start:start + PAGE_SIZE]
        st.dataframe(pd.DataFrame([{
            "Claim ID": claim.claim_id, "Submitted": claim.submitted_at.date(), "Payer": claim.payer,
            "Provider ID": claim.provider_id, "Claim status": label(claim.status),
            "Billed": money(claim.billed_amount), "Payer payment": money(claim.payer_paid_amount),
        } for claim in displayed]), hide_index=True)
        info, prev, nxt = st.columns([3, 1, 1], vertical_alignment="center")
        info.caption(f"{start + 1:,}–{start + len(displayed):,} of {len(matches):,} claims")
        prev.button("Previous", disabled=active_page == 0, args=(active_page - 1,), on_click=change_table_page)
        nxt.button("Next", disabled=active_page + 1 == page_count, args=(active_page + 1,), on_click=change_table_page)
        detail, download = st.columns([3, 2], vertical_alignment="bottom")
        selection = detail.selectbox("Claim details", tuple(claim.claim_id for claim in displayed), index=None,
                                     placeholder="Select a claim ID", key=f"detail_choice_{active_page}")
        if selection is not None and detail.button("Open claim details"):
            claim_detail(next(claim for claim in displayed if claim.claim_id == selection))
        slug = PAGES[page].lower().replace(" & ", "-").replace(" ", "-")
        download.download_button("Export claims CSV", claims_csv(matches), f"rcm360-{slug}.csv", "text/csv")


def change_table_page(page: int) -> None:
    st.session_state.claim_table_page = page


def audit_page(metadata, claims, rows) -> None:
    try:
        quality = parse_quality(read_json(DATA_DIR / "quality.json"), metadata, claims)
    except ExportError as error:
        st.warning(f"QA evidence is unavailable. {error}")
        return
    original, injected = st.tabs(["Original source QA", "Injected-error tests"])
    with original:
        original_evidence(quality, rows, claim_detail)
    with injected:
        test_evidence(quality)


def main() -> None:
    st.set_page_config(page_title="RCM360 | Revenue cycle analytics", page_icon="📊", layout="wide")
    st.session_state.setdefault("drill", None)
    st.session_state.setdefault("claim_table_page", 0)
    st.session_state.setdefault("trend", "Financial")
    st.session_state.setdefault("sort_mode", next(iter(SORTS)))
    with st.sidebar:
        st.title("RCM360")
        st.caption("Revenue cycle analytics")
        selected_page = st.radio("Analytics workspace", PAGES, key="report_page", on_change=navigate)
        st.caption("Synthetic data from Misata Studio")
    page = PAGES.index(selected_page)
    st.caption(f"Analytics › {selected_page}")
    st.title(selected_page)
    st.write(DESCRIPTIONS[page])
    try:
        metadata, claims = parse_claims(read_json(DATA_DIR / "claims.json"))
    except ExportError as error:
        st.warning(f"Validated claims are unavailable. {error}")
        st.info("This dashboard reads PostgreSQL-reconciled exports from dashboard/data/. Once the export has been generated, reopen or rerun the dashboard.")
        return

    ui.badge("PostgreSQL-reconciled claims", variant="outline", key="claims_provenance")
    st.caption(f"{metadata.dataset_name} · {metadata.source_license} · Exported {metadata.generated_at:%Y-%m-%d %H:%M UTC}")
    if not claims:
        st.info("The claims export contains zero records.")
        if page == 4:
            audit_page(metadata, claims, claims)
        return
    dates = [claim.submitted_at.date() for claim in claims]
    filters = choose_filters(claims, (min(dates), max(dates)))
    if filters is None:
        return
    drill = st.session_state.drill
    rows = filter_claims(claims, filters, drill)
    count, chip = st.columns([3, 2], vertical_alignment="center")
    count.caption(f"{len(rows):,} of {len(claims):,} claims in view")
    if drill:
        chip.button(f"Clear drill · {drill[1]}", on_click=clear_drill)
    if filters.status or (drill and drill[0] in ("status", "denial_reason")):
        st.caption("This selection conditions the observed denial rate on claim outcomes. Clear outcome filters for cohort comparisons.")
    if page == 4:
        audit_page(metadata, claims, rows)
        return

    claim_metrics(rows, page)
    match page:
        case 0:
            overview(rows, filters)
        case 1:
            denials(rows, filters)
        case 2:
            revenue(rows, filters)
        case 3:
            performance(rows)
    investigation(rows, page)


if __name__ == "__main__":
    main()
