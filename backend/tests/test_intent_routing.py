"""Which questions start an agent run.

A historical data question ("how has GBP/INR changed over the last 20 years")
used to fall through to the plain-chat branch, which has no tools — so it
answered "I cannot generate charts" and offered matplotlib code instead. Worse,
it was self-trapping: no run existed, so the follow-up "generate graphically"
was also treated as chat.
"""
import pytest

from app.agents.engine.planner import _template, classify_kind
from app.agents.pipeline import classify_intent

RETROSPECTIVE = [
    "How has UK Sterling and Indian INR exhange rate changed over the last 20 years?",
    "How have oil prices changed over the past decade?",
    "Show me the historical trend in US unemployment",
    "Compare German and French GDP since 2000",
    "What is the history of Japanese inflation?",
]

EXPLICIT_OUTPUT = [
    "Generate graphically.",
    "Output a time series graph of GBP/INR",
    "Plot the data",
    "Draw me a chart of US CPI",
    "Can you visualise that?",
]


@pytest.mark.parametrize("question", RETROSPECTIVE)
def test_retrospective_questions_start_a_run(question):
    assert classify_intent(question, has_prior_run=False) == "forecast_request"


@pytest.mark.parametrize("question", EXPLICIT_OUTPUT)
def test_explicit_chart_requests_always_start_a_run(question):
    # ...both cold and mid-conversation: this is the loop that used to trap users
    assert classify_intent(question, has_prior_run=False) == "forecast_request"
    assert classify_intent(question, has_prior_run=True) == "forecast_request"


def test_forecast_questions_still_start_a_run():
    assert classify_intent("Nowcast US GDP growth", False) == "forecast_request"
    assert classify_intent("What is the risk of an Argentine default?", False) == "forecast_request"


def test_genuine_followups_still_route_to_followup():
    assert classify_intent("Why did you choose ARIMA?", True) == "followup"
    assert classify_intent("Explain the methodology", True) == "followup"
    assert classify_intent("What data did you use?", True) == "followup"


def test_greetings_are_still_smalltalk():
    assert classify_intent("hello", False) == "smalltalk"
    assert classify_intent("who are you?", False) == "smalltalk"


@pytest.mark.parametrize("question", RETROSPECTIVE)
def test_retrospective_questions_classify_as_history(question):
    assert classify_kind(question) == "history"


def test_forward_looking_questions_never_classify_as_history():
    # contains "trend", but asks for a forecast
    assert classify_kind("Forecast the trend in US unemployment next year") != "history"
    assert classify_kind("How has inflation changed, and what will it be next quarter?") != "history"


def test_specific_forecast_kinds_win_over_history():
    assert classify_kind("How has the yield curve changed over the last 5 years?") == "yield_curve"


def test_history_template_skips_modeling_and_still_charts():
    plan = _template("history", "How has GBP/INR changed over 20 years?")
    roles = [n["role"] for n in plan["nodes"]]
    assert "modeler" not in roles
    assert "validator" not in roles
    assert "chart_builder" in roles
    assert roles[-1] == "explainer"
    # the explainer is told not to invent a forecast
    assert "Do not forecast." in plan["nodes"][-1]["instructions"]


def test_history_template_is_a_valid_dag():
    from app.agents.engine.planner import validate_plan

    plan = _template("history", "How has GBP/INR changed?")
    assert validate_plan(plan)["kind"] == "history"
