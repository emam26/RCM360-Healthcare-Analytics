"""Dashboard behavior with explicitly test-only, privacy-minimized exports."""

import csv
import io
import json
from datetime import date
from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from dashboard import app
from dashboard.model import (
    ClaimFilters, ExportError, claims_csv, denial_reason_pareto, filter_claims, parse_claims, search_claims, summarize,
)
from dashboard.quality import parse_quality


def fixture_metadata(grain, rows):
    return {
        "schema_version": "1.0.0", "generated_at": "2026-01-01T00:00:00Z",
        "dataset_name": "TEST FIXTURE", "source_sha256": "a" * 64, "source_license": "CC0",
        "record_count": rows, "record_grain": grain, "reconciled_with_postgres": True,
    }


@pytest.fixture
def claim_payload():
    paid = {
        "claim_id": "TEST-PAID", "submitted_at": "2025-01-01T12:00:00", "payer": "test_a",
        "encounter_type": "outpatient", "provider_id": "TEST-PROV-A", "status": "paid",
        "billed_amount": "0.30", "allowed_amount": "0.10", "payer_paid_amount": "0.10",
        "patient_responsibility": "0.20", "allowed_ratio": "0.3333", "paid_at": "2025-01-03T12:00:00",
        "denied_at": None, "denial_reason": None, "submission_to_payment_days": "2.000000",
    }
    denied = dict(
        paid, claim_id="TEST-DENIED", submitted_at="2025-02-02T12:00:00", payer="test_b",
        provider_id="TEST-PROV-B", encounter_type="inpatient", status="denied",
        billed_amount="0.10", payer_paid_amount="0.00", patient_responsibility="0.00", paid_at=None,
        denied_at="2025-02-04T12:00:00", denial_reason="test_reason", submission_to_payment_days=None,
    )
    return {"metadata": fixture_metadata("one row per claim", 2), "records": [paid, denied]}


@pytest.fixture
def quality_payload():
    rule = {"rule_id": "TEST-RULE", "source_table": "claims", "category": "test_only",
            "severity": "warning", "recommended_action": "TEST ACTION"}
    return {
        "metadata": fixture_metadata("validation run across seven source tables", 2),
        "original": {
            "summary": {"source_rows": 2, "rules_total": 1, "rules_passed": 0, "issues_total": 1},
            "rules": [dict(rule, tested_rows=2, issue_count=1, pass_rate="0.5")],
            "issues": [{"rule_id": "TEST-RULE", "source_table": "claims", "record_ref": "TEST-DENIED",
                        "issue_category": "test_only", "severity": "warning",
                        "resolution_status": "open", "recommended_action": "TEST ACTION"}],
        },
        "injected_test": {
            "summary": {"source_rows": 2, "rules_total": 1, "expected_findings": 1,
                        "detected_findings": 1, "missed_findings": 0, "tests_passed": 1},
            "rules": [dict(rule, expected_count=1, detected_count=1, missed_count=0, detection_rate="1.0", result="pass")],
            "issues": [],
        },
    }


def test_exact_claim_measures_and_csv(claim_payload):
    _, claims = parse_claims(claim_payload)
    metrics = summarize(claims)
    assert metrics.count == 2
    assert metrics.billed == Decimal("0.40")
    assert metrics.payer_paid == Decimal("0.10")
    assert metrics.responsibility == Decimal("0.20")
    assert metrics.denied_billed == Decimal("0.10")
    assert metrics.denial_rate == Decimal("0.5")
    assert metrics.average_days == Decimal("2")
    output = list(csv.DictReader(io.StringIO(claims_csv(search_claims(claims, "REASON", "Newest submission")))))
    assert len(output) == 1
    assert output[0]["claim_id"] == "TEST-DENIED"
    assert output[0]["billed_amount"] == "0.10"
    assert output[0]["submission_to_payment_days"] == ""


def test_date_and_dimension_intersection_with_drill(claim_payload):
    _, claims = parse_claims(claim_payload)
    filters = ClaimFilters(date(2025, 2, 2), date(2025, 2, 2), payer="test_b", status="denied")
    assert [row.claim_id for row in filter_claims(claims, filters, ("encounter_type", "inpatient"))] == ["TEST-DENIED"]
    empty = summarize(filter_claims(claims, filters, ("provider_id", "TEST-PROV-A")))
    assert (empty.count, empty.denial_rate, empty.average_days) == (0, None, None)


@pytest.mark.parametrize("field, value", [("billed_amount", 0.3), ("allowed_ratio", "NaN"), ("patient_id", "TEST-SENSITIVE")])
def test_claim_contract_rejects_bad_record_fields(claim_payload, field, value):
    claim_payload["records"][0][field] = value
    with pytest.raises(ExportError):
        parse_claims(claim_payload)


def test_claim_contract_rejects_unreconciled_or_duplicate_claims(claim_payload):
    claim_payload["metadata"]["reconciled_with_postgres"] = False
    with pytest.raises(ExportError, match="awaiting PostgreSQL"):
        parse_claims(claim_payload)
    claim_payload["metadata"]["reconciled_with_postgres"] = True
    claim_payload["records"][1]["claim_id"] = claim_payload["records"][0]["claim_id"]
    with pytest.raises(ExportError, match="duplicate claim keys"):
        parse_claims(claim_payload)


def test_quality_scope_separation_and_privacy(claim_payload, quality_payload):
    metadata, claims = parse_claims(claim_payload)
    quality = parse_quality(quality_payload, metadata, claims)
    assert quality.original_rules[0]["pass_rate"] == Decimal("0.5")
    assert quality.original_issues[0]["record_ref"] == "TEST-DENIED"
    quality_payload["original"]["issues"][0]["record_ref"] = "TEST-UNKNOWN-KEY"
    assert parse_quality(quality_payload, metadata, claims).original_issues[0]["record_ref"] is None
    quality_payload["injected_test"]["issues"] = quality_payload["original"]["issues"]
    with pytest.raises(ExportError, match="aggregate findings"):
        parse_quality(quality_payload, metadata, claims)


def run_dashboard():
    from dashboard.app import main

    main()


def write_fixture(directory, name, payload):
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_missing_and_empty_export(monkeypatch, tmp_path, claim_payload):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    view = AppTest.from_function(run_dashboard).run()
    assert not view.exception
    assert "claims.json export is missing" in view.warning[0].value
    claim_payload["records"] = []
    claim_payload["metadata"]["record_count"] = 0
    write_fixture(tmp_path, "claims.json", claim_payload)
    view.run()
    assert not view.exception
    assert "zero records" in view.info[0].value


def test_empty_filters_offer_recovery_and_keep_source_qa_available(monkeypatch, tmp_path, claim_payload, quality_payload):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    write_fixture(tmp_path, "quality.json", quality_payload)
    view = AppTest.from_function(run_dashboard).run()
    view.selectbox(key="filter_payer").select("test_a").run()
    view.selectbox(key="filter_status").select("denied").run()
    assert not view.exception
    assert len(view.info) == 1 and "No claims match the current filters" in view.info[0].value
    assert not view.metric and not view.get("download_button")
    view.radio(key="report_page").set_value("Data quality & QA").run()
    assert not view.exception
    assert view.metric[0].label == "Source rows"
    next(button for button in view.button if button.label == "Reset filters").click().run()
    assert view.selectbox(key="filter_payer").value is None
    assert view.selectbox(key="filter_status").value is None


def test_all_pages_retain_global_filters_and_clear_drill(monkeypatch, tmp_path, claim_payload, quality_payload):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    write_fixture(tmp_path, "quality.json", quality_payload)
    view = AppTest.from_function(run_dashboard).run()
    assert not view.exception
    assert view.metric[0].value == "2"
    view.selectbox(key="overview_reasons_choose").select("test_reason").run()
    assert not view.exception
    assert view.session_state["drill"] == ("denial_reason", "test_reason")
    assert view.metric[0].value == "1"
    view.selectbox(key="filter_payer").select("test_a").run()
    assert not view.exception
    assert view.session_state["drill"] is None
    assert view.metric[0].value == "1"
    for page in app.PAGES[1:]:
        view.radio(key="report_page").set_value(page).run()
        assert not view.exception
        assert view.selectbox(key="filter_payer").value == "test_a"
        assert any(title.value == page for title in view.title)
    assert [tab.label for tab in view.tabs] == ["Original source QA", "Injected-error tests"]


def test_investigation_can_open_claim_and_reset_filters(monkeypatch, tmp_path, claim_payload):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    view = AppTest.from_function(run_dashboard).run()
    view.text_input(key="claim_search").set_value("test-paid").run()
    view.selectbox(key="detail_choice_0").select("TEST-PAID").run()
    next(button for button in view.button if button.label == "Open claim details").click().run()
    assert not view.exception
    assert any(item.value == "TEST-PAID" for item in view.subheader)
    assert "Assigned patient responsibility" in view.table[0].value["Field"].tolist()
    next(button for button in view.button if button.label == "Reset filters").click().run()
    assert not view.exception
    assert view.text_input(key="claim_search").value == ""


def test_pareto_uses_denied_claims_with_recorded_reasons(monkeypatch, tmp_path, claim_payload):
    paid, denied = claim_payload["records"]
    paid["denial_reason"] = "test_paid_excluded"
    reasons = ["beta", "alpha", "beta", "gamma", None]
    claim_payload["records"] = [paid, *[
        dict(denied, claim_id=f"TEST-DENIAL-{index}", denial_reason=reason)
        for index, reason in enumerate(reasons)
    ]]
    claim_payload["metadata"]["record_count"] = len(claim_payload["records"])
    _, claims = parse_claims(claim_payload)
    assert denial_reason_pareto(claims) == [
        ("beta", 2, Decimal("0.50")), ("alpha", 1, Decimal("0.75")), ("gamma", 1, Decimal("1.00")),
    ]
    assert denial_reason_pareto(claims[:1]) == []

    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    view = AppTest.from_function(run_dashboard).run()
    view.radio(key="report_page").set_value("Claims & denials").run()
    assert not view.exception
    assert any("denominator for this selection is 4" in caption.value for caption in view.caption)
    pareto = next(table.value for table in view.dataframe if "Cumulative share" in table.value)
    assert pareto["Denied claims"].tolist() == [2, 1, 1]
    assert pareto["Cumulative share"].tolist() == ["50.00%", "75.00%", "100.00%"]


def test_payer_and_provider_groups_flag_only_counts_below_30(monkeypatch, tmp_path, claim_payload):
    paid, denied = claim_payload["records"]
    claim_payload["records"] = [dict(paid, claim_id=f"TEST-A-{index}") for index in range(29)]
    claim_payload["records"].extend(dict(denied, claim_id=f"TEST-B-{index}") for index in range(30))
    claim_payload["metadata"]["record_count"] = 59
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    view = AppTest.from_function(run_dashboard).run()
    view.radio(key="report_page").set_value("Payer & provider").run()
    assert not view.exception
    comparisons = [table.value for table in view.dataframe if "Sample caution" in table.value]
    assert len(comparisons) == 2
    for comparison in comparisons:
        assert comparison["Claims"].tolist() == [30, 29]
        assert comparison["Denied"].tolist() == [30, 0]
        assert comparison["Sample caution"].tolist() == ["—", "Small sample"]
    assert any("30 claims" in caption.value and "display caution" in caption.value for caption in view.caption)


def test_denial_comparisons_use_the_full_filtered_cohort(monkeypatch, tmp_path, claim_payload):
    paid, denied = claim_payload["records"]
    claim_payload["records"].append(dict(
        denied, claim_id="TEST-MIXED-DENIED", payer=paid["payer"], provider_id=paid["provider_id"],
    ))
    claim_payload["metadata"]["record_count"] = 3
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    view = AppTest.from_function(run_dashboard).run()
    view.radio(key="report_page").set_value("Claims & denials").run()
    assert not view.exception
    comparisons = [table.value for table in view.dataframe if "Sample caution" in table.value]
    assert len(comparisons) == 2
    for comparison in comparisons:
        assert comparison["Claims"].tolist() == [2, 1]
        assert comparison["Denied"].tolist() == [1, 1]
        assert comparison["Observed denial rate"].tolist() == ["50.00%", "100.00%"]


def test_revenue_status_reconciliation_displays_exact_sums(monkeypatch, tmp_path, claim_payload):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    view = AppTest.from_function(run_dashboard).run()
    view.radio(key="report_page").set_value("Revenue & payments").run()
    assert not view.exception
    values = next(table.value for table in view.dataframe if "Assigned patient responsibility" in table.value)
    assert values.to_records(index=False).tolist() == [
        ("Paid", 1, "$0.30", "$0.10", "$0.10", "$0.20"),
        ("Denied", 1, "$0.10", "$0.10", "$0.00", "$0.00"),
        ("Pending", 0, "$0.00", "$0.00", "$0.00", "$0.00"),
        ("Total", 2, "$0.40", "$0.20", "$0.10", "$0.20"),
    ]
    view.selectbox(key="filter_status").select("denied").run()
    filtered = next(table.value for table in view.dataframe if "Assigned patient responsibility" in table.value)
    assert filtered.iloc[-1].tolist() == ["Total", 1, "$0.10", "$0.10", "$0.00", "$0.00"]


def test_heatmap_hover_exposes_claim_counts_and_marks_small_cells(monkeypatch, tmp_path, claim_payload):
    paid, denied = claim_payload["records"]
    claim_payload["records"].append(dict(
        denied, claim_id="TEST-MIXED-DENIED", payer=paid["payer"], encounter_type=paid["encounter_type"],
    ))
    claim_payload["metadata"]["record_count"] = 3
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    write_fixture(tmp_path, "claims.json", claim_payload)
    view = AppTest.from_function(run_dashboard).run()
    view.radio(key="report_page").set_value("Payer & provider").run()
    assert not view.exception
    traces = [trace for plot in view.get("plotly_chart") for trace in json.loads(plot.proto.spec)["data"]]
    heatmap = next(trace for trace in traces if trace["type"] == "heatmap")
    assert heatmap["x"] == ["Inpatient", "Outpatient"]
    assert heatmap["y"] == ["test_a", "test_b"]
    assert heatmap["z"] == [[None, 0.5], [1.0, None]]
    assert heatmap["text"] == [["", "50.00%*"], ["100.00%*", ""]]
    assert heatmap["customdata"][0][1][:2] == [2, 1]
    assert "customdata[1]:,} denied / %{customdata[0]:,} claims" in heatmap["hovertemplate"]
    view.selectbox(key="heatmap_encounter_choose").select("outpatient").run()
    assert not view.exception
    assert view.session_state["drill"] == ("encounter_type", "outpatient")
    assert view.metric[0].value == "2"
