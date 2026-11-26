# Indigo dashboard reference

Source: [`reference UI/rcm_dashboard_indigo.html`](../reference%20UI/rcm_dashboard_indigo.html). The page structure and behavior below come from its CSS and JavaScript. The Streamlit mapping and comparison checks are implementation guidance.

## Page hierarchy

The sidebar opens on **Executive overview**. It contains the “RCM Intelligence” brand, the “Analytics workspace” navigation, and a portfolio disclosure. Each page uses the same shell: `Analytics › [page]` breadcrumb, prototype badge, title and description, **Export claims CSV**, global filters, filtered count and active drill chip, five KPI cards, page-specific analysis, an investigation table, and a footer. The QA disclaimer appears immediately below its KPIs.

| Page | KPI cards in display order | Analysis in display order |
| --- | --- | --- |
| Executive overview | Total claims, Total billed, Total paid, Denial rate, Data quality | Billing & payment trends (switches to Monthly claim volume), Top denial reasons, Claim status distribution, Operational watchlist |
| Claims & denials | Total claims, Denied claims, Denial rate, Denied billed value, Pending claims | Denial rate over time, Denial reasons, Denied billed value by payer, Claim status distribution |
| Revenue & payments | Gross billed, Allowed amount, Total payments, Outstanding, Collection rate | Billing & payment trends, Outstanding balance by payer, Payer performance summary |
| Payer & provider | Claims, Active payers, Active providers, Collection rate, Avg. paid days | Payer collection rate, Provider claim volume, Payer performance summary, Provider performance summary |
| Data quality & QA | Claims validated, Pass rate, Flagged claims, Issue rate, Issue categories | Simulated QA pass rate by service month, Exceptions by rule, Flagged claims by encounter type, Operational watchlist |

The final table is **Claim-level investigation** on the first four pages and **QA exception register** on the fifth. KPI cards display a label, line icon, large tabular number, and a short qualifier. They have no click action. The watchlist updates with the leading denial reason and QA exception, with fallback text when there are none.

## Visual system and responsive layout

| Role | Effective reference values |
| --- | --- |
| Surfaces and text | Sidebar `#231f38`, canvas `#f6f5fa`, white cards and top bar, text `#26243a`, secondary text `#646579`, borders `#e5e3ed` |
| Indigo accents | Primary `#5145b8`, pale tint `#efedfc`, brand tile `#7061df`, selected navigation background `#3e355d` with a 3 px `#b5a7ff` inset stripe, focus outline `#6557df` |
| Chart and status colors | Billed line `#8784b5`, paid line `#5145b8`, volume line `#7776b5`, denial line `#b74660`. Donut uses `#5145b8` for paid, `#b74660` for denied, and `#dba14a` for pending. Pills use pale green for paid/pass, red for denied/issue, and amber for pending. |
| Type | `Inter, 'Segoe UI', system-ui, sans-serif` with no bundled font. Desktop body 14 px, page title 32 px, section titles 15 px, KPI values 27 px, table body 12 px, table headings 11 px. |
| Desktop composition | Sticky 244 px sidebar, 65 px white top bar, content capped at 1700 px with 30 px horizontal padding, 14 px card radii and shadow `0 2px 6px #211a3d08`. Five equal KPI columns with 14 px gaps. Main chart pairs use a 1.7:1 split, secondary cards a 1:1 split, and both use 16 px gaps. |

- **901–1190 px.** Sidebar narrows to 205 px, content padding to 20 px, and KPI figures to 21 px. Five KPI columns remain.
- **900 px and below.** Sidebar moves above the workspace as a branded header with horizontally scrolling navigation and 44 px minimum item height. The active stripe moves to the bottom. The sidebar disclosure and navigation heading hide. The top bar becomes 52 px, filters use two columns, KPIs use three, chart pairs stack, and table controls and footer can wrap.
- **520 px and below.** Content padding narrows to 12 px, the avatar hides, the page heading and export action stack, KPIs use two columns, and search/status/sort controls can wrap. Wide tables scroll within their container at all widths.

## Controls and interaction

| Control | Behavior in the reference |
| --- | --- |
| Global filters | Reporting period (full year 2025 or calendar quarter in the demo), insurance payer, provider, and encounter type intersect. Changes clear the active drill and return pagination to the first page. Switching pages retains global selections, sort, and the trend choice while clearing drill, search, table status, and pagination. Reset restores all global selections, clears drill and table filters, and restores newest-first sorting. |
| Trends | Lines show calendar months in the selected period, tooltips on markers, subdued gridlines, a faint fill below the final series, and a legend. The overview switch toggles between billed/paid amounts and claim volume. |
| Drill-down | Bars show up to six ranked categories with a value and proportional fill. Buttons on the bars, status list beside the donut, and payer/provider names in comparison tables set a single drill filter across the current page. Selecting another item replaces the drill. The chip clears it. Comparison tables sort by claim volume and show claims, billed, paid, denial rate, and collection rate. |
| Investigation | Claim ID, service date, payer, provider, status, billed, paid, and data-quality result. Case-insensitive search matches the ID, payer, provider, status, denial reason, QA issue, or encounter type. Status and newest-date/highest-billed/highest-balance sorts affect the table. The QA register limits the results to flagged claims. Each page shows six rows with a range/count and previous/next buttons. The claim ID opens a dialog with financial amounts, payment turnaround, reason, QA result, and encounter context. |
| CSV export | Downloads all rows matching both global/drill filters and table search/status, in the current sort order, across table pages. On the QA page the download contains flagged claims only. The demo uses a page-specific filename and includes claim details beyond the visible table columns. |

## Streamlit and Plotly mapping

- Use Streamlit controls and session state for page navigation, filter selections, reset rules, trend mode, drill chip, pagination, and CSV downloads. Keep the global filter row near the KPIs. A native collapsed sidebar is a practical mobile equivalent if the horizontal header requires custom markup.
- Use styled containers or metric cards for the KPIs and Plotly for line charts and the status donut. Match series colors and hover content. Use selectable marks or labeled drill controls beside the charts to preserve a clear action for bars and status values. Comparison table selection and a detail dialog or inline detail panel can replace clickable text links and the HTML dialog.
- Preserve the scope of each interaction when adapting native table sorting and row selection. A separate export built from the filtered and sorted result can preserve the CSV behavior across pagination.
- Populate only dimensions and measures supported by the export contract. The 2025 labels, category values, claim IDs, financial fields, rates, and QA flags in the HTML describe invented demo records. The QA flags are assigned by the generator. Use the deployed dashboard’s source and validation labels to identify SQL-verified results and label injected-error test results separately. Use **payer payments** where supported, and describe **denied billed value** as gross billed charges on denied claims. Undefined rates and missing fields need explicit display rules in the data contract.

## Visual and behavior acceptance

- Compare the reference and implementation at approximately 1440 px, 1024 px, 768 px, and 390 px. Review the indigo sidebar and selected state, white card hierarchy, five desktop KPI cards, chart proportions, mobile reflow, and local table scrolling. Check for clipped titles, values, controls, and labels.
- Exercise a page transition, global filter change, chart drill and clear, trend switch, empty result, table search and sort, pagination, claim detail, and download. Check that drill and global filters update KPIs and charts, table filters affect the table and CSV, and the download covers all matching pages.
- Before release, verify displayed values against executed PostgreSQL results, check that QA evidence labels stay visible on narrow screens, and inspect detail views and exports for patient identifiers.
