![Thai Rule-based Anti-Scam AI — Research Project](docs/assets/ban.png)

*ภาพแสดงแนวคิดงานวิจัย*

# Thai Rule-based Anti-Scam AI

โครงการจบที่ศึกษาการพัฒนา AI ภาษาไทยแบบใช้กฎ เพื่อจำแนกเจตนาอย่างอธิบายได้ และวางพื้นฐานสำหรับการประเมินความเสี่ยงจากการหลอกลวง

[![CI on main](https://github.com/siwakon8285/thai-anti-scam-ai/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/siwakon8285/thai-anti-scam-ai/actions/workflows/ci.yml?query=branch%3Amain)

**สถานะ** Runtime และ Candidate Collection V0.1 · **Python อ้างอิง** 3.14.8 · **Runtime** Python Standard Library

[ความสามารถปัจจุบัน](#current-capabilities) · [สถาปัตยกรรม](#system-architecture) · [เริ่มต้นใช้งาน](#getting-started) · [ผลประเมิน](#testing-and-evaluation) · [เอกสาร](#documentation) · [แผนพัฒนา](#capability-roadmap)

## Project Overview

โครงการศึกษาว่ากฎที่อธิบายและทดสอบได้ช่วยตีความข้อความภาษาไทยได้อย่างไร ต้นแบบบทสนทนา V0.1 มีเป้าหมายจำแนกเจตนาเบื้องต้นและตอบข้อความตาม [Behavior Specification](docs/v0.1-behavior.md)

## Current Capabilities

| ส่วนที่ใช้งานได้ | สิ่งที่ตรวจสอบได้ |
| --- | --- |
| Runtime Foundation | ตรวจชนิดและอักขระดิบ สร้าง Matching Text ด้วย `strip()` และ NFC และตรวจโครงสร้างผลลัพธ์สามฟิลด์ |
| Candidate Collection | จับวลีที่มีหลักฐานรองรับ ตรวจบริบทของคำปฏิเสธและคำพูดที่ถูกอ้าง และคืน Candidate ที่ผ่านพร้อมตำแหน่งใน Matching Text |
| [Development Dataset v0.1](datasets/development/v0.1.json) | ข้อความสมมติภาษาไทยและกรณีข้อความว่าง รวม 32 ตัวอย่าง ครบ 8 Intent |
| [Baseline Evaluator](scripts/evaluate_baseline.py) | ตรวจ JSON และ Schema แล้ววัด Intent Accuracy และ Confusion Matrix ของตัวจำแนก Always-UNKNOWN |
| [Automated Tests](tests/) | ตรวจ Runtime Foundation, Candidate Collection, Regression Specification, ชุดข้อมูล และ Evaluator |

## System Architecture

เส้นทึบแสดงขั้นตอนที่เรียกใช้ได้ถึงการรวบรวม Candidate เส้นประแสดงการตัดสินเจตนาและเลือกคำตอบที่อยู่ในแผน

```mermaid
flowchart LR
    input["ข้อความภาษาไทย"] --> text["ตรวจและปรับข้อความ"]
    text --> matches["จับคู่และตรวจบริบท"]
    matches --> candidates["รวบรวม Candidate"]
    candidates -.-> selection["เลือกกฎ"]
    selection -.-> response["เลือกคำตอบ"]
    response -.-> output["ตรวจ Result"]
```

## Evaluation Architecture

**Current Implementation** Evaluator อ่าน Dataset แบบ UTF-8 ปฏิเสธคีย์ JSON ซ้ำและค่าตัวเลขที่แปลงเป็นอนันต์ แล้วตรวจ Schema ก่อนส่งแต่ละข้อความให้ตัวจำแนกอ้างอิง [โค้ด Evaluator](scripts/evaluate_baseline.py)

```mermaid
flowchart LR
    dataset["Dataset JSON"] --> validation["ตรวจ JSON และ Schema"]
    validation --> predictor["Always-UNKNOWN"]
    predictor --> metrics["คำนวณ Metrics"]
    metrics --> report["รายงาน JSON"]
```

## Getting Started

ใช้ Python 3.14.8 เป็นเวอร์ชันอ้างอิงและรันจาก Repository Root

```bash
git clone https://github.com/siwakon8285/thai-anti-scam-ai.git
cd thai-anti-scam-ai
python3 -B --version
python3 -B -m scripts.run_tests
python3 -B -m scripts.evaluate_baseline
```

Evaluator แสดง JSON ทาง Terminal หากต้องการเก็บผลแยก ให้ใช้ `python3 -B -m scripts.evaluate_baseline --output reports/baseline-local.json`

เรียก Runtime Foundation จาก Python ได้โดยตรง

```python
from thai_ai.normalization import normalize_text

text = normalize_text("  สวัสดีครับ  ")
assert text.raw_text == "  สวัสดีครับ  "
assert text.matching_text == "สวัสดีครับ"
assert text.kind == "content"
```

เรียก Candidate Collection เพื่อดูหลักฐานที่ผ่านกฎและ Guard

```python
from thai_ai.candidates import collect_candidates

collection = collect_candidates("สวัสดีครับ คุณคือใคร")
assert {candidate.intent for candidate in collection.candidates} == {"GREETING", "BOT_IDENTITY"}
```

## Testing and Evaluation

Test Runner ใช้ `unittest` ส่วน [GitHub Actions](.github/workflows/ci.yml) ตรวจ Python Syntax และรันชุดทดสอบเดียวกัน Badge ด้านบนแสดงสถานะ CI ของ `main` ดูผล Candidate Collection และกรณีที่รอ Engine ใน [DESIGN.md](DESIGN.md#h-034--featv01-rule-matching-guards--task-007)

| ผล Reference Baseline v0.1 | ค่า |
| --- | --- |
| Development Dataset | 32 ตัวอย่าง · 8 Intent |
| ตัวจำแนกอ้างอิง | Always-UNKNOWN |
| ผลทำนาย | ถูก 4 · ผิด 28 |
| Development Intent Accuracy | **12.5%** |

**12.5% เป็นผลของตัวจำแนกอ้างอิงบน Development Dataset** ใช้เป็นจุดเทียบในการพัฒนากฎ ความแม่นยำของ AI Engine และ Independent Evaluation ยังไม่มีผลให้รายงาน [รายงาน Baseline และ Confusion Matrix](reports/baseline-v0.1.json)

## Repository Structure

```text
thai-anti-scam-ai/
├── datasets/
│   ├── development/v0.1.json
│   └── regression/v0.1.json
├── docs/
│   ├── assets/
│   │   └── ban.png
│   ├── v0.1-behavior.md
│   ├── v0.1-behavioral-contract-analysis.md
│   ├── v0.1-thai-text-processing.md
│   ├── v0.1-rule-architecture.md
│   ├── v0.1-regression-spec.md
│   └── pybot-reference-and-design-rationale.md
├── reports/
│   ├── baseline-v0.1.json
│   └── text-processing-v0.1.json
├── scripts/
│   ├── experiments/text_processing.py
│   ├── evaluate_baseline.py
│   └── run_tests.py
├── tests/
├── thai_ai/
│   ├── _rule_metadata.py
│   ├── candidates.py
│   ├── guards.py
│   ├── matching.py
│   ├── normalization.py
│   ├── result.py
│   └── validation.py
└── DESIGN.md
```

## Documentation

- [Behavior Specification V0.1](docs/v0.1-behavior.md) — Intent ที่รองรับตามแผน พฤติกรรมที่คาดหวัง และ Proposed Contract
- [Behavioral Contract Analysis V0.1](docs/v0.1-behavioral-contract-analysis.md) — ขอบเขต Intent การตรวจย้อนกลับ 32 ตัวอย่าง และข้อเสนอด้าน Regression
- [Thai Text Processing Experiments V0.1](docs/v0.1-thai-text-processing.md) — การทดลอง Unicode และการเทียบรูปข้อความภาษาไทย
- [Rule Architecture V0.1](docs/v0.1-rule-architecture.md) — ข้อเสนอการเลือก Intent และสัญญาคำตอบ
- [Regression Specification V0.1](docs/v0.1-regression-spec.md) — กรณีอ้างอิงและผลคาดหวังสำหรับทดสอบก่อนพัฒนา Engine
- [PyBot Reference Study](docs/pybot-reference-and-design-rationale.md) — กรณีศึกษา PyBot และเหตุผลที่เลือกปรับแนวคิดให้เหมาะกับภาษาไทย
- [DESIGN.md](DESIGN.md) — สถาปัตยกรรม แนวทางประเมิน และเหตุผลด้านการออกแบบ

## Capability Roadmap

| ขอบเขต | ความสามารถ |
| --- | --- |
| ปัจจุบัน | Runtime Foundation, Candidate Collection, ชุดทดสอบ และการประเมิน Reference Baseline |
| แผนต้นแบบ V0.1 | จำแนกเจตนาและตอบข้อความภาษาไทยตามข้อกำหนด |
| ระยะถัดไปตามผลทดลอง | เพิ่มความครอบคลุมของภาษาไทย ศึกษาบริบทและ Session Memory แล้วพัฒนาการประเมินความเสี่ยงและการทดสอบอิสระ |

ลำดับการเพิ่มความสามารถปรับได้ตามผลการทดลองใน [Adaptive Roadmap](DESIGN.md)

## Limitations and Ethical Considerations

- กฎปัจจุบันรองรับวลีและรูปแบบบริบทที่มีกรณีทดสอบอนุมัติ การตัดสินเจตนา การเลือกคำตอบ และ Scam Detection ยังอยู่ในแผน
- ใช้ข้อมูลสมมติหรือข้อมูลที่ได้รับอนุญาตและตัดข้อมูลระบุตัวตน ชุด Held-out สำหรับการประเมินอิสระในอนาคตต้องแยกจากข้อมูลที่ใช้ปรับกฎ
- หากพัฒนาการประเมินความเสี่ยงในอนาคต ผลต้องอธิบายหลักฐานและข้อจำกัด หลีกเลี่ยงการกล่าวหาบุคคลหรือรับรองความปลอดภัยจากการไม่พบสัญญาณ
