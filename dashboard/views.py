"""Streamlit presentation helpers for the claim-grain report."""

from collections import Counter
from datetime import date
from decimal import Decimal
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dashboard.model import STATUSES, denial_reason_pareto, group_by, ratio, summarize


INDIGO = "#5145B8"
LAVENDER = "#8784B5"
RED = "#B74660"
AMBER = "#DBA14A"
GRID = "#E5E3ED"
INK = "#26243A"
STATUS_COLORS = {"paid": INDIGO, "denied": RED, "pending": AMBER}
MATURITY = (
    "The source provides no observation cutoff or completion window. "
    "Recent submission cohorts may have incomplete follow-up."
)
SELF_PAY = "The synthetic source reports payer payments under the self_pay label."
SMALL_SAMPLE_THRESHOLD = 30


def money(value: Decimal) -> str:
    return f"${value:,.2f}"


def rate(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.2%}"


def quantity(value: int) -> str:
    return f"{value:,}"


def days(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.1f} days"


def label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def metric_row(items: list[tuple[str, str, str]], *, key: str = "rcm-kpis") -> None:
    with st.container(key=key):
        cards = []
        for title, value, definition in items:
            lowered = title.casefold()
            tone = "red" if any(word in lowered for word in ("denial", "finding", "flagged")) else "indigo"
            if "payment" in lowered or "time" in lowered:
                icon = '<path d="M3 12h3l2.3-6 4.2 12 2.3-6H21"/>'
            elif "denial" in lowered or "finding" in lowered or "flagged" in lowered:
                icon = '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4m0 3h.01"/>'
            elif "pass" in lowered or "test" in lowered:
                icon = '<path d="m5 12 4 4L19 6"/><path d="M21 12a9 9 0 1 1-2.64-6.36"/>'
            elif any(word in lowered for word in ("amount", "billed", "responsibility")):
                icon = '<path d="M12 2v20m5-16H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'
            else:
                icon = '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/>'
            cards.append(
                f'<article class="rcm-kpi-card" data-kpi-label="{escape(title)}" data-kpi-value="{escape(str(value))}">'
                f'<div class="rcm-kpi-top"><span class="rcm-kpi-label">{escape(title)}</span>'
                f'<span class="rcm-kpi-icon {tone}" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" '
                f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{icon}</svg></span></div>'
                f'<div class="rcm-kpi-value">{escape(str(value))}</div>'
                f'<div class="rcm-kpi-foot">{escape(definition)}</div></article>'
            )
        st.markdown('<div class="rcm-kpi-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def figure(height: int = 300) -> go.Figure:
    return go.Figure().update_layout(
        height=height,
        margin=dict(l=10, r=10, t=12, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK, family='Inter, "Segoe UI", system-ui, sans-serif', size=12),
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center", font=dict(color=INK, size=11)),
        xaxis=dict(automargin=True, gridcolor=GRID, tickfont=dict(color=INK, size=10), title_font=dict(color=INK)),
        yaxis=dict(automargin=True, gridcolor=GRID, tickfont=dict(color=INK, size=10), title_font=dict(color=INK)),
    )


def month_range(start: date, end: date) -> list[date]:
    start_index = start.year * 12 + start.month - 1
    end_index = end.year * 12 + end.month - 1
    return [date(index // 12, index % 12 + 1, 1) for index in range(start_index, end_index + 1)]


def monthly_chart(claims, start: date, end: date, mode: str, key: str) -> None:
    if not claims:
        st.info("No claims match this view.")
        return
    groups = group_by(claims, "month")
    months = month_range(start, end)
    series = [summarize(groups.get(month, [])) for month in months]
    chart = figure()
    chart.update_xaxes(tickformat="%b %Y", showgrid=False)
    if mode == "volume":
        chart.add_scatter(
            x=months, y=[item.count for item in series], name="Submitted claims",
            mode="lines+markers", line=dict(color=INDIGO), fill="tozeroy",
            hovertemplate="%{x|%B %Y}<br>%{y:,} submitted claims<extra></extra>",
        )
        chart.update_yaxes(rangemode="tozero", tickformat=",d")
    elif mode == "denials":
        chart.add_scatter(
            x=months, y=[float(item.denial_rate) if item.denial_rate is not None else None for item in series],
            customdata=[(item.denied, item.count) for item in series], name="Observed denial rate",
            mode="lines+markers", line=dict(color=RED),
            hovertemplate=("%{x|%B %Y}<br>%{y:.2%} observed denial rate"
                           "<br>%{customdata[0]:,} denied / %{customdata[1]:,} claims<extra></extra>"),
        )
        chart.update_yaxes(rangemode="tozero", tickformat=".0%")
    else:
        for name, field, color in (("Billed", "billed", LAVENDER), ("Payer payments", "payer_paid", INDIGO)):
            totals = [getattr(item, field) for item in series]
            chart.add_scatter(
                x=months, y=[float(amount) for amount in totals], name=name,
                customdata=[money(amount) for amount in totals], mode="lines+markers",
                line=dict(color=color),
                hovertemplate=f"%{{x|%B %Y}}<br>{name}: %{{customdata}}<extra></extra>",
            )
        chart.update_yaxes(rangemode="tozero", tickprefix="$")
    st.plotly_chart(chart, key=key, theme=None, config={"displaylogo": False})


def set_drill(field: str, value: str) -> None:
    st.session_state.drill = (field, value)
    st.session_state.claim_table_page = 0


def select_drill(key: str, field: str) -> None:
    points = st.session_state[key].selection.points
    if points:
        set_drill(field, str(points[-1]["customdata"][0]))


def filter_drill(key: str, field: str) -> None:
    value = st.session_state[key]
    if value is not None:
        set_drill(field, value)


def drill_control(key: str, field: str, options: list[str], title: str) -> None:
    if not options or (len(options) == 1 and st.session_state.drill == (field, options[0])):
        return
    widget_key = f"{key}_choose"
    st.selectbox(
        title, options, index=None, key=widget_key, placeholder="Select a category",
        format_func=str if field in ("payer", "provider_id") else label,
        on_change=filter_drill, args=(widget_key, field),
    )


def ranked_chart(
    values: dict[str, int | Decimal], field: str, key: str, *, color: str = INDIGO,
    formatter=quantity, axis_format: str | None = None,
) -> None:
    if not values:
        st.info("No matching categories for this view.")
        return
    ranked = sorted(values, key=lambda item: (-values[item], item))[:6]
    shown = ranked[::-1]
    names = [item if field in ("payer", "provider_id") else label(item) for item in shown]
    texts = [formatter(values[item]) for item in shown]
    chart = figure(255)
    chart.add_bar(
        x=[float(values[item]) for item in shown], y=names,
        marker_color=color, orientation="h", text=texts, textposition="outside",
        textfont=dict(color=INK, size=11), cliponaxis=False,
        customdata=list(zip(shown, texts)), hovertemplate="%{y}<br>%{customdata[1]}<extra></extra>",
    )
    chart.update_xaxes(tickformat=axis_format, rangemode="tozero")
    chart.update_yaxes(showgrid=False, type="category")
    st.plotly_chart(
        chart, key=key, theme=None, selection_mode="points",
        on_select=lambda: select_drill(key, field), config={"displaylogo": False},
    )
    drill_control(key, field, ranked, "Filter by category")


def pareto_chart(claims, key: str) -> None:
    rows = denial_reason_pareto(claims)
    if not rows:
        st.info("No recorded denial reasons match this view.")
        return

    reasons, counts, cumulative = zip(*rows)
    denominator = sum(counts)
    st.caption(
        "Cumulative share is based on denied claims with a recorded reason. "
        f"The denominator for this selection is {denominator:,}."
    )
    names = [label(reason) for reason in reasons]
    chart = figure(330)
    chart.add_bar(
        x=reasons, y=counts, name="Denied claims", marker_color=RED,
        customdata=list(zip(reasons, names)),
        hovertemplate="%{customdata[1]}<br>%{y:,} denied claims<extra></extra>",
    )
    chart.add_scatter(
        x=reasons, y=[float(share) for share in cumulative], name="Cumulative share", yaxis="y2",
        mode="lines+markers", line=dict(color=INDIGO), customdata=list(zip(reasons, names)),
        hovertemplate="%{customdata[1]}<br>%{y:.2%} cumulative share<extra></extra>",
    )
    chart.update_xaxes(type="category", tickvals=reasons, ticktext=names, showgrid=False)
    chart.update_yaxes(title_text="Denied claims", rangemode="tozero", tickformat=",d")
    chart.update_layout(yaxis2=dict(
        title_text="Cumulative share", range=[0, 1.05], tickformat=".0%", dtick=0.25,
        overlaying="y", side="right", showgrid=False, automargin=True,
    ))
    st.plotly_chart(
        chart, key=key, theme=None, selection_mode="points",
        on_select=lambda: select_drill(key, "denial_reason"), config={"displaylogo": False},
    )
    drill_control(key, "denial_reason", list(reasons), "Filter by denial reason")
    with st.expander("Denial-reason counts and shares"):
        st.dataframe(pd.DataFrame({
            "Recorded reason": names, "Denied claims": counts,
            "Cumulative share": [rate(share) for share in cumulative],
        }), hide_index=True)


def status_chart(claims, key: str) -> None:
    if not claims:
        st.info("No claims match this view.")
        return
    counts = Counter(claim.status for claim in claims)
    ordered = [status for status in STATUS_COLORS if counts[status]]
    chart = figure(220)
    chart.add_pie(
        labels=[label(status) for status in ordered], values=[counts[status] for status in ordered],
        hole=0.67, sort=False, marker=dict(colors=[STATUS_COLORS[status] for status in ordered]),
        textinfo="none", hovertemplate="%{label}<br>%{value:,} claims · %{percent}<extra></extra>",
    )
    chart.add_annotation(text=f"{len(claims):,}<br>claims", x=0.5, y=0.5, showarrow=False)
    chart_column, status_column = st.columns([1, 1.15], vertical_alignment="center")
    with chart_column:
        st.plotly_chart(chart, key=key, theme=None, config={"displaylogo": False}, width="stretch")
    with status_column:
        for status in ordered:
            count = counts[status]
            share = ratio(count, len(claims))
            st.button(
                f"{label(status)}  ·  {count:,}  ·  {rate(share)}",
                key=f"{key}_{status}",
                on_click=set_drill,
                args=("status", status),
                width="stretch",
            )


def comparison(claims, field: str, title: str) -> None:
    with st.container(border=True):
        st.subheader(title)
        groups = group_by(claims, field)
        if not groups:
            st.info("No claims match this view.")
            return
        grouped = [(key, summarize(rows)) for key, rows in groups.items()]
        grouped.sort(key=lambda item: (-item[1].count, item[0]))
        st.caption(
            f"Fewer than {SMALL_SAMPLE_THRESHOLD} claims triggers a small-sample display caution. "
            "Statistical reliability depends on the data and analysis."
        )
        rows = [{
            "Provider ID" if field == "provider_id" else "Payer": key,
            "Claims": item.count, "Denied": item.denied,
            "Sample caution": "Small sample" if item.count < SMALL_SAMPLE_THRESHOLD else "—",
            "Billed": money(item.billed),
            "Payer payments": money(item.payer_paid), "Observed denial rate": rate(item.denial_rate),
        } for key, item in grouped]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        drill_control(f"comparison_{field}", field, [key for key, _ in grouped], "Filter by group")


def status_reconciliation(claims) -> None:
    with st.container(border=True):
        st.subheader("Financial reconciliation by claim status")
        st.caption(
            "Each amount column sums a separate source field. Assigned patient responsibility records an "
            "allocation. Cash-balance calculations require a separate payment ledger."
        )
        if not claims:
            st.info("No claims match this view.")
            return
        groups = group_by(claims, "status")
        totals = [(label(status), summarize(groups.get(status, []))) for status in STATUSES]
        totals.append(("Total", summarize(claims)))
        st.dataframe(pd.DataFrame([{
            "Claim status": status, "Claims": metrics.count, "Billed amount": money(metrics.billed),
            "Allowed amount": money(metrics.allowed), "Payer payment": money(metrics.payer_paid),
            "Assigned patient responsibility": money(metrics.responsibility),
        } for status, metrics in totals]), hide_index=True)


def denial_heatmap(claims) -> None:
    with st.container(border=True):
        st.subheader("Observed denial rate by payer and encounter type")
        st.caption(
            f"An asterisk marks fewer than {SMALL_SAMPLE_THRESHOLD} claims. Rates in these cells can change sharply "
            "with a few claims. Blank cells have zero claims. Rates describe the observed synthetic cohort."
        )
        if not claims:
            st.info("No claims match this view.")
            return

        types = sorted({claim.encounter_type for claim in claims})
        payers = sorted({claim.payer for claim in claims})
        counts = Counter((claim.payer, claim.encounter_type) for claim in claims)
        denials = Counter((claim.payer, claim.encounter_type) for claim in claims if claim.status == "denied")
        values, texts, details = [], [], []
        for payer in payers:
            value_row, text_row, detail_row = [], [], []
            for encounter in types:
                count, denied = counts[payer, encounter], denials[payer, encounter]
                observed = ratio(denied, count)
                small = 0 < count < SMALL_SAMPLE_THRESHOLD
                value_row.append(float(observed) if observed is not None else None)
                text_row.append(f"{rate(observed)}{'*' if small else ''}" if count else "")
                detail_row.append([count, denied, "<br>Small cell" if small else ""])
            values.append(value_row)
            texts.append(text_row)
            details.append(detail_row)

        chart = figure(305)
        chart.add_heatmap(
            x=[label(item) for item in types], y=payers, z=values, text=texts, texttemplate="%{text}",
            customdata=details, zmin=0, zmax=1, colorscale=[[0, "#EFEDFC"], [1, INDIGO]],
            colorbar=dict(tickformat=".0%"), hoverongaps=False,
            hovertemplate=("%{y} · %{x}<br>%{z:.2%} observed denial rate"
                           "<br>%{customdata[1]:,} denied / %{customdata[0]:,} claims%{customdata[2]}<extra></extra>"),
        )
        chart.update_xaxes(type="category", showgrid=False)
        chart.update_yaxes(type="category", showgrid=False, autorange="reversed")
        st.plotly_chart(chart, key="denial_heatmap", theme=None, config={"displaylogo": False})
        payer, encounter = st.columns(2)
        with payer:
            drill_control("heatmap_payer", "payer", payers, "Filter by payer")
        with encounter:
            drill_control("heatmap_encounter", "encounter_type", types, "Filter by encounter type")


def denial_watchlist(denied, qa_issues=()) -> None:
    counts = Counter(claim.denial_reason for claim in denied if claim.denial_reason)
    if counts:
        reason, count = min(counts.items(), key=lambda item: (-item[1], item[0]))
        st.markdown(f"**{label(reason)} is the leading recorded denial reason**")
        st.caption(f"{count:,} denied claims in this selection. The label does not establish root cause.")
    else:
        st.caption("No recorded denial reasons match this view.")
    qa_counts = Counter(issue["issue_category"] for issue in qa_issues)
    if qa_counts:
        issue, issue_count = min(qa_counts.items(), key=lambda item: (-item[1], item[0]))
        st.markdown(f"**{label(issue)} leads linked source QA findings**")
        st.caption(f"{issue_count:,} issue records in this filtered claim cohort.")
    else:
        st.caption("Linked original-source QA findings are unavailable or absent for this selection.")
