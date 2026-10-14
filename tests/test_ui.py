from pathlib import Path
from streamlit.testing.v1 import AppTest
from unittest.mock import patch


def test_dashboard_loads_and_navigation_works():
    app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=15).run()
    assert not app.exception


def test_start_research_button_passes_constraints_to_pipeline(monkeypatch):
    """Exercise the actual button and function boundary without external requests."""
    monkeypatch.setenv("TINYFISH_API_KEY", "test-fixture-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    root = Path(__file__).resolve().parent.parent
    with patch("careerpilot.tinyfish_client.TinyFish.search", return_value={"results": []}) as search:
        app = AppTest.from_file(str(root / "app.py"), default_timeout=15).run()
        app.sidebar.radio[0].set_value("Research lab").run()
        app.sidebar.number_input[0].set_value(0).run()
        next(b for b in app.button if b.label == "Start live TinyFish research").click().run()
        assert not app.exception
        assert search.call_count == 5
        assert any(" free" in call.args[0] for call in search.call_args_list)
        assert app.session_state["report"].sources == []
    app.sidebar.radio[0].set_value("Profile").run()
    assert not app.exception
    app.sidebar.radio[0].set_value("Research lab").run()
    assert not app.exception


def test_snapshot_portfolio_and_recalculation():
    root = Path(__file__).resolve().parent.parent
    if not (root / "samples/live_report.json").exists():
        return
    app = AppTest.from_file(str(root / "app.py"), default_timeout=15).run()
    next(b for b in app.button if b.label == "Explore captured live research").click().run()
    app.sidebar.radio[0].set_value("Portfolio").run()
    assert not app.exception
    before = app.metric[0].value
    app.sidebar.slider[0].set_value(2).run()
    assert not app.exception
    assert app.metric[0].value != before
    for page in ["Skill gaps", "Roadmap", "Network", "Research lab"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
