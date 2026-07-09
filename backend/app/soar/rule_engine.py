import operator
from typing import Any, Dict, List
import structlog

logger = structlog.get_logger()

# Supported operators for condition logic
OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "contains": lambda a, b: b in a if isinstance(a, (str, list, dict)) else False,
    "not_contains": lambda a, b: b not in a if isinstance(a, (str, list, dict)) else True,
}

class RuleEngine:
    """
    Evaluates trigger data against a set of configured rules.
    """

    @staticmethod
    def evaluate(rules: List[Any], trigger_data: Dict[str, Any]) -> bool:
        """
        Evaluate a list of rules (from SoarRule model).
        Since multiple rules might belong to a playbook, a playbook triggers if ALL its active rules evaluate to True.
        Alternatively, logic could be handled at playbook level, but here we evaluate all rules.
        """
        if not rules:
            return True # No rules = always trigger

        for rule in rules:
            if not RuleEngine._evaluate_rule(rule, trigger_data):
                return False # If one rule fails, the playbook doesn't trigger
        return True

    @staticmethod
    def _evaluate_rule(rule: Any, trigger_data: Dict[str, Any]) -> bool:
        """
        Evaluate a single SoarRule.
        Condition config is expected to be a list of dicts:
        [
            {"field": "severity", "operator": "==", "value": "critical"},
            {"field": "rule_id", "operator": "==", "value": "5710"}
        ]
        """
        conditions = rule.condition_config
        logic = rule.condition_logic.upper() # AND / OR

        if not conditions:
            return True

        results = []
        for cond in conditions:
            field = cond.get("field")
            op_str = cond.get("operator", "==")
            expected_value = cond.get("value")

            actual_value = RuleEngine._get_field_value(trigger_data, field)
            op_func = OPERATORS.get(op_str, operator.eq)

            try:
                # Type cast if necessary (simple string comparison mostly)
                # But handle numeric if strings represent numbers
                if isinstance(actual_value, (int, float)) and isinstance(expected_value, str):
                    if expected_value.replace('.','',1).isdigit():
                        expected_value = float(expected_value)

                res = op_func(actual_value, expected_value)
                results.append(res)
            except Exception as e:
                logger.warning("rule_evaluation_error", field=field, error=str(e))
                results.append(False)

        if logic == "OR":
            return any(results)
        return all(results) # Default AND

    @staticmethod
    def _get_field_value(data: Dict[str, Any], field_path: str) -> Any:
        """
        Get value from a nested dict using dot notation.
        E.g., "agent.name" -> data["agent"]["name"]
        """
        if not field_path:
            return None

        keys = field_path.split(".")
        val = data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return None
        return val
