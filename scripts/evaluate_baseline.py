"""ประเมินตัวจำแนกอ้างอิง Always-UNKNOWN บน Development Dataset V0.1."""

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import platform


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "datasets/development/v0.1.json"
INTENTS = (
    "GREETING", "BOT_IDENTITY", "BOT_CAPABILITIES", "THANKS",
    "FAREWELL", "HELP", "UNKNOWN", "EMPTY_INPUT",
)


def _reject_json_constant(token: str):
    raise ValueError(f"Non-standard JSON constant: {token}")


def _parse_finite_float(token: str) -> float:
    value = float(token)
    if not isfinite(value):
        raise ValueError("JSON number exceeds the finite float range.")
    return value


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def parse_dataset_json(text: str):
    """อ่าน JSON โดยปฏิเสธชื่อสมาชิกซ้ำ ค่าพิเศษ และตัวเลขที่แปลงเป็น float อนันต์."""
    return json.loads(
        text,
        parse_constant=_reject_json_constant,
        parse_float=_parse_finite_float,
        object_pairs_hook=_unique_json_object,
    )


def validate_dataset(dataset):
    """ตรวจข้อมูลทุกตัวอย่างก่อนเริ่มทำนายและคืนรายการตัวอย่างที่ผ่านการตรวจ."""
    if not isinstance(dataset, dict):
        raise ValueError("Dataset must be a JSON object.")
    for field in ("version", "purpose"):
        value = dataset.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Dataset {field} must be a non-empty string.")

    samples = dataset.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("Dataset samples must be a non-empty list.")

    seen_ids = set()
    seen_inputs = set()
    for index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict):
            raise ValueError(f"Sample {index} must be an object.")
        sample_id = sample.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError(f"Sample {index} id must be a non-empty string.")
        if sample_id in seen_ids:
            raise ValueError(f"{sample_id}: duplicate id.")
        seen_ids.add(sample_id)

        text = sample.get("input")
        if not isinstance(text, str):
            raise ValueError(f"{sample_id}: input must be a string.")
        if text in seen_inputs:
            raise ValueError(f"{sample_id}: duplicate input.")
        seen_inputs.add(text)

        expected = sample.get("expected_intent")
        if not isinstance(expected, str) or expected not in INTENTS:
            raise ValueError(f"{sample_id}: expected_intent must be in the taxonomy.")
        if (expected == "EMPTY_INPUT") != (not text.strip()):
            raise ValueError(f"{sample_id}: EMPTY_INPUT requires a blank input and vice versa.")
        behavior = sample.get("expected_behavior")
        if not isinstance(behavior, str) or not behavior.strip():
            raise ValueError(f"{sample_id}: expected_behavior must be a non-empty string.")
    return samples


def always_unknown(_text: str) -> str:
    """คืน UNKNOWN สำหรับข้อความทุกประเภท รวมถึงข้อความว่าง."""
    return "UNKNOWN"


def evaluate(dataset, predictor):
    """วัด Intent ด้วย predictor ที่รับข้อความและคืน Label หนึ่งค่า."""
    samples = validate_dataset(dataset)
    matrix = {expected: dict.fromkeys(INTENTS, 0) for expected in INTENTS}
    for sample in samples:
        predicted = predictor(sample["input"])
        if not isinstance(predicted, str) or predicted not in INTENTS:
            raise ValueError(f"{sample['id']}: prediction must be in the taxonomy.")
        matrix[sample["expected_intent"]][predicted] += 1

    per_intent = {}
    for intent, row in matrix.items():
        support = sum(row.values())
        correct = row[intent]
        per_intent[intent] = {
            "support": support,
            "correct": correct,
            "accuracy": correct / support if support else None,
        }
    correct = sum(result["correct"] for result in per_intent.values())
    total = len(samples)
    return {
        "total_samples": total,
        "correct_predictions": correct,
        "incorrect_predictions": total - correct,
        "intent_accuracy": correct / total,
        "per_intent": per_intent,
        "confusion_matrix": matrix,
    }


def build_report():
    """โหลด Dataset UTF-8 แล้วสร้างรายงานจากผลประเมินและไบต์ต้นฉบับ."""
    data = DATASET_PATH.read_bytes()
    dataset = parse_dataset_json(data.decode("utf-8"))
    metrics = evaluate(dataset, always_unknown)
    return {
        "baseline_strategy": "Always-UNKNOWN",
        "dataset": {
            "path": DATASET_PATH.relative_to(ROOT).as_posix(),
            "version": dataset["version"],
            "purpose": dataset["purpose"],
            "sha256": sha256(data).hexdigest(),
        },
        "evaluation_method": (
            "เปรียบเทียบ Intent ที่ทำนายกับค่าที่คาดหวังทีละตัวอย่าง "
            "โดยคำนวณ Accuracy จากจำนวนที่ทายถูกหารด้วยจำนวนตัวอย่าง"
        ),
        "confusion_matrix_axes": {"rows": "expected_intent", "columns": "predicted_intent"},
        "python_version": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "limitations": (
            "ผลจากตัวจำแนกอ้างอิงบน Development Dataset เท่านั้น "
            "ยังไม่มี AI V0.1 ที่ Implement แล้วสำหรับการวัด และยังไม่มีผลประเมินอิสระ"
        ),
        "metrics": metrics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="บันทึกรายงาน JSON ไปยังไฟล์ที่ระบุ")
    args = parser.parse_args()
    try:
        report = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            if args.output.resolve() == DATASET_PATH.resolve():
                raise ValueError("Report output must not overwrite the input dataset.")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8", newline="\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Evaluation error: {error}\n")
    print(report, end="")


if __name__ == "__main__":
    main()
