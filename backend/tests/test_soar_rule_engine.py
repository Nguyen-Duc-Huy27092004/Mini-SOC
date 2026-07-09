import pytest
from app.soar.rule_engine import RuleEngine

class MockRule:
    def __init__(self, condition_logic, condition_config):
        self.condition_logic = condition_logic
        self.condition_config = condition_config

def test_rule_engine_empty_rules():
    trigger_data = {"severity": "critical"}
    assert RuleEngine.evaluate([], trigger_data) == True

def test_rule_engine_and_logic():
    rule = MockRule(
        "AND",
        [
            {"field": "severity", "operator": "==", "value": "critical"},
            {"field": "agent.name", "operator": "==", "value": "web-server-01"}
        ]
    )
    trigger_data_match = {
        "severity": "critical",
        "agent": {"name": "web-server-01"}
    }
    assert RuleEngine.evaluate([rule], trigger_data_match) == True

    trigger_data_fail = {
        "severity": "critical",
        "agent": {"name": "db-server"}
    }
    assert RuleEngine.evaluate([rule], trigger_data_fail) == False

def test_rule_engine_or_logic():
    rule = MockRule(
        "OR",
        [
            {"field": "severity", "operator": "==", "value": "critical"},
            {"field": "rule_id", "operator": "==", "value": "5710"}
        ]
    )
    trigger_data_1 = {"severity": "critical", "rule_id": "1234"}
    trigger_data_2 = {"severity": "low", "rule_id": "5710"}
    trigger_data_fail = {"severity": "low", "rule_id": "1234"}

    assert RuleEngine.evaluate([rule], trigger_data_1) == True
    assert RuleEngine.evaluate([rule], trigger_data_2) == True
    assert RuleEngine.evaluate([rule], trigger_data_fail) == False

def test_rule_engine_operators():
    rule = MockRule(
        "AND",
        [
            {"field": "cpu", "operator": ">=", "value": "90"},
            {"field": "message", "operator": "contains", "value": "failed"}
        ]
    )
    trigger_data = {"cpu": 95, "message": "login failed"}
    assert RuleEngine.evaluate([rule], trigger_data) == True
    
    trigger_data_fail = {"cpu": 80, "message": "login failed"}
    assert RuleEngine.evaluate([rule], trigger_data_fail) == False
