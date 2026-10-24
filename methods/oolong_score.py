"""Scoring of Oolong-real answers, copied in behaviour from the authors' harness (github.com/abertsch72/oolong,
src/eval/eval_helpers.py at commit 0bb7eabe839218fee7fe8d007f41cfc2fd3ae24c: dnd_parse_answer, dnd_parse_response,
dnd_process_response).

As in the harness:
  parse response  the first \\boxed{\\text{...}} or \\boxed{...} (one or more opening and closing braces, no '}'
                  inside); without a box the whole output is returned unparsed (confidence 'low')
  parse answer    int if it converts, else a list if it contains a comma (split, stripped, empties dropped), else
                  the string
  int             0.75 ** |gold - prediction|
  string          exact match after strip().lower()
  list            |set(gold) & set(prediction)| / |gold|   (no penalty for extra items)
  types differ    0.0
"""
import re

BOXED_TEXT = re.compile(r"\\boxed\{\\text\{([^}]*)\}\}")
BOXED = re.compile(r"\\boxed[\{]+([^}]*)[\}]+")


def parse_answer(answer):
    try:
        return int(answer)
    except ValueError:
        pass
    if "," in answer:
        return [item.strip() for item in answer.split(",") if item.strip()]
    return answer


def parse_response(output):
    match = BOXED_TEXT.search(output) or BOXED.search(output)
    if match:
        return parse_answer(match.group(1)), "high"
    return output, "low"


def score(gold_answer, output):
    gold = parse_answer(gold_answer)
    pred, conf = parse_response(output)
    if isinstance(gold, int) and isinstance(pred, int):
        return 0.75 ** abs(gold - pred), conf
    if isinstance(gold, str) and isinstance(pred, str):
        return float(gold.strip().lower() == pred.strip().lower()), conf
    if isinstance(gold, list) and isinstance(pred, list):
        return (len(set(gold) & set(pred)) / len(gold) if gold else 0.0), conf
    return 0.0, conf


if __name__ == "__main__":
    assert score("84", r"so \boxed{84}")[0] == 1.0
    assert abs(score("84", r"\boxed{86}")[0] - 0.5625) < 1e-9
    assert score("Attack", r"\boxed{\text{Attack}}")[0] == 1.0
    assert score("4, 3", r"\boxed{3, 4, 5}")[0] == 1.0
    assert score("4, 3", r"\boxed{4}")[0] == 0.0
    assert score("84", "84")[0] == 0.0  # no box: the raw output is a string, the gold an int
    assert score("Attack", "Attack")[0] == 1.0  # no box: string compared as a whole
    assert score("84", r"\boxed{{84}}")[0] == 1.0
    print("ok")
