# Engine V0.1 — Regression Test Report

TASK-011 · Python 3.14.8 / Darwin arm64 · 2026-11-28

## Coverage

เมทริกซ์อ้าง [Regression JSON V0.1](../datasets/regression/v0.1.json) และบันทึก Case ID จาก subtests ที่ผ่านจริงด้วย `python3 -B -` (Exit `0`) ใช้ `unittest` เรียก test methods ที่มี Case IDs โดยตรง จับ `addSubTest` และตรวจเซตที่สังเกตได้เทียบกับ Mandatory ทั้งชุด

| ขอบเขต | จำนวน Case IDs |
| --- | ---: |
| Engine end-to-end แบบเรียก API จริงโดยตรง | 93 |
| Engine และ JSON wire | 3 |
| Engine Configuration และการส่งต่อ fault | 6 |
| Component เท่านั้น | 44 |
| Pending | 2 |

Engine faults มี Configuration จริงหนึ่งกรณีและฉีดความผิดพลาดรายขั้นอีกห้ากรณี กลุ่ม Component มี Normalization 17, Resolver + Response 13 และ Rubric fixtures 14 รายการ ทดสอบตามขอบเขตข้อมูลของแต่ละ fixture ผล Rubric มาจากการตรวจข้อความและกรณีปฏิเสธตามเกณฑ์เดิม

## Case Matrix

ชื่อ Template ในผลจริงแสดงว่าข้อความตอบตรงกับ Template นั้น `winner` หมายถึงกฎที่ชนะจริง ส่วน `None` คือ Python None และ `null` คือค่า JSON ตารางใช้รูปแบบย่อ โดยเก็บถ้อยคำเต็มและ typed fixture ไว้ใน Regression JSON

| Case ID | Expected Outcome | Actual Outcome | Test Level | Status |
| --- | --- | --- | --- | --- |
| `DEV-001` | `GREETING` / `greeting` / `winner` | `GREETING` / `greeting` / `greeting.direct` | Engine · end-to-end | Pass |
| `DEV-002` | `GREETING` / `greeting` / `winner` | `GREETING` / `greeting` / `greeting.direct` | Engine · end-to-end | Pass |
| `DEV-003` | `GREETING` / `greeting` / `winner` | `GREETING` / `greeting` / `greeting.direct` | Engine · end-to-end | Pass |
| `DEV-004` | `GREETING` / `greeting` / `winner` | `GREETING` / `greeting` / `greeting.direct` | Engine · end-to-end | Pass |
| `DEV-005` | `BOT_IDENTITY` / `identity` / `winner` | `BOT_IDENTITY` / `identity` / `identity.direct` | Engine · end-to-end | Pass |
| `DEV-006` | `BOT_IDENTITY` / `identity` / `winner` | `BOT_IDENTITY` / `identity` / `identity.direct` | Engine · end-to-end | Pass |
| `DEV-007` | `BOT_IDENTITY` / `identity` / `winner` | `BOT_IDENTITY` / `identity` / `identity.bot-reference` | Engine · end-to-end | Pass |
| `DEV-008` | `BOT_IDENTITY` / `identity` / `winner` | `BOT_IDENTITY` / `identity` / `identity.bot-reference` | Engine · end-to-end | Pass |
| `DEV-009` | `BOT_CAPABILITIES` / `capabilities` / `winner` | `BOT_CAPABILITIES` / `capabilities` / `capabilities.direct` | Engine · end-to-end | Pass |
| `DEV-010` | `BOT_CAPABILITIES` / `capabilities` / `winner` | `BOT_CAPABILITIES` / `capabilities` / `capabilities.bot-reference` | Engine · end-to-end | Pass |
| `DEV-011` | `BOT_CAPABILITIES` / `capabilities` / `winner` | `BOT_CAPABILITIES` / `capabilities` / `capabilities.direct` | Engine · end-to-end | Pass |
| `DEV-012` | `BOT_CAPABILITIES` / `capabilities` / `winner` | `BOT_CAPABILITIES` / `capabilities` / `capabilities.direct` | Engine · end-to-end | Pass |
| `DEV-013` | `THANKS` / `thanks` / `winner` | `THANKS` / `thanks` / `thanks.direct` | Engine · end-to-end | Pass |
| `DEV-014` | `THANKS` / `thanks` / `winner` | `THANKS` / `thanks` / `thanks.direct` | Engine · end-to-end | Pass |
| `DEV-015` | `THANKS` / `thanks` / `winner` | `THANKS` / `thanks` / `thanks.direct` | Engine · end-to-end | Pass |
| `DEV-016` | `THANKS` / `thanks` / `winner` | `THANKS` / `thanks` / `thanks.direct` | Engine · end-to-end | Pass |
| `DEV-017` | `FAREWELL` / `farewell` / `winner` | `FAREWELL` / `farewell` / `farewell.direct` | Engine · end-to-end | Pass |
| `DEV-018` | `FAREWELL` / `farewell` / `winner` | `FAREWELL` / `farewell` / `farewell.direct` | Engine · end-to-end | Pass |
| `DEV-019` | `FAREWELL` / `farewell` / `winner` | `FAREWELL` / `farewell` / `farewell.direct` | Engine · end-to-end | Pass |
| `DEV-020` | `FAREWELL` / `farewell` / `winner` | `FAREWELL` / `farewell` / `farewell.direct` | Engine · end-to-end | Pass |
| `DEV-021` | `HELP` / `help` / `winner` | `HELP` / `help` / `help.general` | Engine · end-to-end | Pass |
| `DEV-022` | `HELP` / `help` / `winner` | `HELP` / `help` / `help.general` | Engine · end-to-end | Pass |
| `DEV-023` | `HELP` / `help` / `winner` | `HELP` / `help` / `help.general` | Engine · end-to-end | Pass |
| `DEV-024` | `HELP` / `help` / `winner` | `HELP` / `help` / `help.general` | Engine · end-to-end | Pass |
| `DEV-025` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `DEV-026` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `DEV-027` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `DEV-028` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `DEV-029` | `EMPTY_INPUT` / `empty` / `None` | `EMPTY_INPUT` / `empty` / `None` | Engine · end-to-end | Pass |
| `DEV-030` | `EMPTY_INPUT` / `empty` / `None` | `EMPTY_INPUT` / `empty` / `None` | Engine · end-to-end | Pass |
| `DEV-031` | `EMPTY_INPUT` / `empty` / `None` | `EMPTY_INPUT` / `empty` / `None` | Engine · end-to-end | Pass |
| `DEV-032` | `EMPTY_INPUT` / `empty` / `None` | `EMPTY_INPUT` / `empty` / `None` | Engine · end-to-end | Pass |
| `IN-01` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-02` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-03` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-04` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-05` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-06` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-07` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-08` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `IN-09` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-10` | `ValueError` / `disallowed_control` / offset 0 | `ValueError` / `disallowed_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-11` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-12` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-13` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-14` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-15` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-16` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-17` | `ValueError` / `disallowed_control` / offset 1 | `ValueError` / `disallowed_control` / offset 1 | Engine · end-to-end | Pass |
| `IN-18` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-19` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-20` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-21` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-22` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-23` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-24` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-25` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-26` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-27` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-28` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-29` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-30` | `ValueError` / `surrogate` / offset 0 | `ValueError` / `surrogate` / offset 0 | Engine · end-to-end | Pass |
| `IN-31` | `ValueError` / `surrogate` / offset 1 | `ValueError` / `surrogate` / offset 1 | Engine · end-to-end | Pass |
| `IN-32` | `ValueError` / `surrogate` / offset 0 | `ValueError` / `surrogate` / offset 0 | Engine · end-to-end | Pass |
| `IN-33` | `ValueError` / `disallowed_control` / offset 0 | `ValueError` / `disallowed_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-34` | `ValueError` / `surrogate` / offset 0 | `ValueError` / `surrogate` / offset 0 | Engine · end-to-end | Pass |
| `IN-35` | `ValueError` / `bidi_control` / offset 0 | `ValueError` / `bidi_control` / offset 0 | Engine · end-to-end | Pass |
| `IN-SUBCLASS-PRECEDENCE` | `TypeError` / `invalid_type` | `TypeError` / `invalid_type` | Engine · end-to-end | Pass |
| `NORM-01` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (10 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-02` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (10 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-03` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (8 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-04` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (8 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-05` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (2 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-06` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (2 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-07` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (3 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-08` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (7 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-09` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (7 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-10` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (3 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-11` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (6 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-12` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (9 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-13` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (43 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-14` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (35 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-15` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (10 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-16` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (1 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `NORM-17` | Matching Text, Raw และ idempotence ตาม fixture | Matching Text ตรง (528 code points) คง Raw และ idempotent | Component · Normalization | Pass |
| `INT-01` | `BOT_IDENTITY` / `identity` / `winner` | `BOT_IDENTITY` / `identity` / `identity.direct` | Engine · end-to-end | Pass |
| `INT-02` | `BOT_CAPABILITIES` / `capabilities` / `winner` | `BOT_CAPABILITIES` / `capabilities` / `capabilities.direct` | Engine · end-to-end | Pass |
| `INT-03` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `INT-04` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `INT-05` | `THANKS` / `thanks` / `winner` | `THANKS` / `thanks` / `thanks.direct` | Engine · end-to-end | Pass |
| `INT-06` | `EMPTY_INPUT` / `empty` / `None` | `EMPTY_INPUT` / `empty` / `None` | Engine · end-to-end | Pass |
| `INT-07` | `EMPTY_INPUT` / `empty` / `None` | `EMPTY_INPUT` / `empty` / `None` | Engine · end-to-end | Pass |
| `INT-08` | `GREETING` / `greeting` / `winner` | `GREETING` / `greeting` / `greeting.direct` | Engine · end-to-end | Pass |
| `INT-09` | `UNKNOWN` / `unknown_format_only` / `None` | `UNKNOWN` / `unknown_format_only` / `None` | Engine · end-to-end | Pass |
| `INT-10` | `UNKNOWN` / `unknown_format_only` / `None` | `UNKNOWN` / `unknown_format_only` / `None` | Engine · end-to-end | Pass |
| `INT-11` | `UNKNOWN` / `unknown_format_only` / `None` | `UNKNOWN` / `unknown_format_only` / `None` | Engine · end-to-end | Pass |
| `INT-12` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `INT-13` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `INT-14` | `UNKNOWN` / `unknown_ambiguity` / `None` | `UNKNOWN` / `unknown_ambiguity` / `None` | Engine · end-to-end | Pass |
| `INT-15` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `INT-16` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `INT-17` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `INT-18` | `BOT_CAPABILITIES` / `capabilities` / `winner` | `BOT_CAPABILITIES` / `capabilities` / `capabilities.bot-reference` | Engine · end-to-end | Pass |
| `INT-19` | `BOT_IDENTITY` / `identity` / `winner` | `BOT_IDENTITY` / `identity` / `identity.direct` | Engine · end-to-end | Pass |
| `INT-CR-ONLY` | `EMPTY_INPUT` / `empty` / `None` | `EMPTY_INPUT` / `empty` / `None` | Engine · end-to-end | Pass |
| `INT-ZWSP-ONLY` | `UNKNOWN` / `unknown_format_only` / `None` | `UNKNOWN` / `unknown_format_only` / `None` | Engine · end-to-end | Pass |
| `RES-01` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Component · Resolver + Response | Pass |
| `RES-02` | `GREETING` / `greeting` / `single` | `GREETING` / `greeting` / `single` | Component · Resolver + Response | Pass |
| `RES-03` | `UNKNOWN` / `unknown_explicit` / `origin` | `UNKNOWN` / `unknown_explicit` / `origin` | Component · Resolver + Response | Pass |
| `RES-04` | `GREETING` / `greeting` / `a` | `GREETING` / `greeting` / `a` | Component · Resolver + Response | Pass |
| `RES-05` | `GREETING` / `greeting` / `b` | `GREETING` / `greeting` / `b` | Component · Resolver + Response | Pass |
| `RES-06` | `GREETING` / `greeting` / `a.9` | `GREETING` / `greeting` / `a.9` | Component · Resolver + Response | Pass |
| `RES-07` | `HELP` / `help` / `b` | `HELP` / `help` / `b` | Component · Resolver + Response | Pass |
| `RES-08` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Component · Resolver + Response | Pass |
| `RES-09` | `BOT_IDENTITY` / `identity` / `z` | `BOT_IDENTITY` / `identity` / `z` | Component · Resolver + Response | Pass |
| `RES-10` | `BOT_CAPABILITIES` / `capabilities` / `z` | `BOT_CAPABILITIES` / `capabilities` / `z` | Component · Resolver + Response | Pass |
| `RES-11` | `UNKNOWN` / `unknown_ambiguity` / `None` | `UNKNOWN` / `unknown_ambiguity` / `None` | Component · Resolver + Response | Pass |
| `RES-12` | `UNKNOWN` / `unknown_ambiguity` / `None` | `UNKNOWN` / `unknown_ambiguity` / `None` | Component · Resolver + Response | Pass |
| `RES-13` | `UNKNOWN` / `unknown_ambiguity` / `None` | `UNKNOWN` / `unknown_ambiguity` / `None` | Component · Resolver + Response | Pass |
| `ERR-MATCHING` | `RuntimeError` / `propagate_fixture_fault` | `RuntimeError` / `propagate_fixture_fault` / exception และ cause เดิม | Engine · injected fault | Pass |
| `ERR-GUARD` | `RuntimeError` / `propagate_fixture_fault` | `RuntimeError` / `propagate_fixture_fault` / exception และ cause เดิม | Engine · injected fault | Pass |
| `ERR-SELECTION` | `RuntimeError` / `propagate_fixture_fault` | `RuntimeError` / `propagate_fixture_fault` / exception และ cause เดิม | Engine · injected fault | Pass |
| `ERR-RESPONSE` | `RuntimeError` / `propagate_fixture_fault` | `RuntimeError` / `propagate_fixture_fault` / exception และ cause เดิม | Engine · injected fault | Pass |
| `ERR-OUTPUT` | `RuntimeError` / `invalid_result` | `RuntimeError` / `invalid_result` | Engine · injected fault | Pass |
| `ERR-CONFIG` | `RuntimeError` / `duplicate_rule_id` | `RuntimeError` / `duplicate_rule_id` | Engine · configuration | Pass |
| `REVIEW-GREETING` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-IDENTITY` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-CAPABILITIES` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-THANKS` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-FAREWELL` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-HELP` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-UNKNOWN-EXPLICIT` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-UNKNOWN-NO-MATCH` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-UNKNOWN-FORMAT-ONLY` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-UNKNOWN-AMBIGUITY` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REVIEW-EMPTY` | `accept` | `accept` | Component · Rubric fixtures | Pass |
| `REJECT-CAPABILITIES` | `reject` | `reject` | Component · Rubric fixtures | Pass |
| `REJECT-HELP` | `reject` | `reject` | Component · Rubric fixtures | Pass |
| `REJECT-UNKNOWN-NO-MATCH` | `reject` | `reject` | Component · Rubric fixtures | Pass |
| `WIRE-EMPTY` | JSON 3 ฟิลด์ / rule_id `null` | JSON 3 ฟิลด์ / rule_id `null` / round-trip ตรง | Engine + JSON wire | Pass |
| `WIRE-UNKNOWN-NO-MATCH` | JSON 3 ฟิลด์ / rule_id `null` | JSON 3 ฟิลด์ / rule_id `null` / round-trip ตรง | Engine + JSON wire | Pass |
| `WIRE-UNKNOWN-EXPLICIT` | JSON 3 ฟิลด์ / rule_id `fixture-a` | JSON 3 ฟิลด์ / rule_id `fixture-a` / round-trip ตรง | Engine + JSON wire | Pass |
| `OPEN-BOM-PREFIX` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `OPEN-ZWSP-IN-WORD` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `OPEN-COMBINING-ONLY` | `UNKNOWN` / `unknown_no_match` / `None` | `UNKNOWN` / `unknown_no_match` / `None` | Engine · end-to-end | Pass |
| `OPEN-MIXED-REQUEST` | `HELP` / `help` / `winner` | `HELP` / `help` / `help.general` | Engine · end-to-end | Pass |
| `OPEN-LENGTH-LIMIT` | `Q-05` รอตัดสิน | — | Pending | Pending |
| `OPEN-REGEX-BUDGET` | `Q-14` รอตัดสิน | — | Pending | Pending |

## Performance · ปริมาณงานทดลอง

ใช้ `python3 -B -` เรียก child process แบบแยกกรณีและแยกการจับเวลาออกจากการเก็บหน่วยความจำ ใช้ deadline 2 วินาทีต่อ child ผ่าน 14/14 (Exit `0`) จับเวลาด้วย `perf_counter_ns` หลัง warm-up 3 รอบแล้วใช้ median จาก 21 การเรียก วัด peak ด้วย `tracemalloc` ระหว่าง `process_text` หนึ่งครั้งหลังสร้าง Input

ข้อความสั้นใช้ INT-01 ข้อความยาวใช้ `ก` ซ้ำตามขนาด Near-match ใช้ `ช่วยบอกสูตร` + `ก` ซ้ำ + LF + `ก` ให้ครบขนาด ตรวจว่า `specific_request` fullmatch รับรูปที่แทน LF ด้วย `ก` และปฏิเสธรูปที่มี LF ตรวจ Intent และ Rule ID ของ Engine ทุก child ส่วนการวัด Response เรียก `select_response` ด้วย Decision และ Registry ที่เตรียมไว้

| Input | Raw code points | Engine median (µs) | Normalization median (µs) | Response median (µs) | Engine peak traced (bytes) |
| --- | ---: | ---: | ---: | ---: | ---: |
| short | 20 | 30.12 | 1.83 | 9.12 | 5,566 |
| long | 128 | 20.29 | 8.25 | 6.08 | 2,952 |
| near_match | 128 | 21.25 | 8.08 | 6.04 | 2,952 |
| long | 2,048 | 139.92 | 123.96 | 6.00 | 2,952 |
| near_match | 2,048 | 151.04 | 122.88 | 6.17 | 2,952 |
| long | 32,768 | 2069.83 | 2140.12 | 6.04 | 2,952 |
| near_match | 32,768 | 2236.62 | 2031.25 | 5.71 | 2,952 |

ค่ามัธยฐานวัดแยกกันและอาจต่างจากกันตามความแปรปรวนของแต่ละรอบ ค่า peak ครอบคลุม Python allocations ระหว่างเรียก Engine ตามที่ trace ได้ ขอบเขต 32,768 code points และ 2 วินาทีใช้เฉพาะการทดลอง ส่วน Production Limit และ Regex Budget ยัง Pending
