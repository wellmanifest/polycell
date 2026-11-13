# Kandydaci na komórki polycell

Źródło: `/mnt/user-data/uploads/ae507fc5-map.toon.yaml` · funkcji przeanalizowanych: 3145

    # forge | 4456f 1287084L | python:4378,rust:73,shell:4,less:1 | 2026-11-13
    # stats: 14262 func | 9665 cls | 4456 mod | CC̄=5.7 | critical:2359 | cycles:0
    # alerts[5]: CC validate_https___setuptools_pypa_io_en_latest_userguide_pyproject_config_html=352; CC validate_https___packaging_python_org_en_latest_specifications_pyproject_toml=287; CC validate_https___setuptools_pypa_io_en_latest_userguide_pyproject_config_html__definitions_ext_module=170; fan-out _execute=72; fan-out _execute=70
    # hotspots[5]: _execute fan=72; _execute fan=72; _execute fan=72; _execute fan=72; _execute fan=70
    # evolution: baseline
    # Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods

## Kolejność migracji (moduły z największą liczbą czystych funkcji)

1. `.governance/branch_intent_reconciliation.py` - 3 kandydatów
2. `.governance/branch_lifecycle_check.py` - 3 kandydatów
3. `.governance/change_lease_check.py` - 3 kandydatów
4. `.governance/decision_record.py` - 3 kandydatów
5. `.governance/policy_dsl_check.py` - 3 kandydatów
6. `.governance/ticket_allocation.py` - 3 kandydatów
7. `.governance/ticket_index_merge_driver.py` - 3 kandydatów
8. `.governance/ticket_input.py` - 3 kandydatów
9. `.governance/work_continuity.py` - 3 kandydatów
10. `.governance/check_required_checks.py` - 2 kandydatów

## Duplikaty: jedna komórka zastąpi N kopii (największy zysk, najmniejsze ryzyko)

- `canonical` - 27 implementacji w różnych modułach
- `parser` - 27 implementacji w różnych modułach
- `digest` - 17 implementacji w różnych modułach
- `resolve` - 15 implementacji w różnych modułach
- `validate_input` - 13 implementacji w różnych modułach
- `validate_bundle` - 13 implementacji w różnych modułach
- `parse_mountinfo` - 13 implementacji w różnych modułach
- `extract_baseline` - 13 implementacji w różnych modułach
- `render_markdown` - 13 implementacji w różnych modułach
- `parse_document` - 12 implementacji w różnych modułach
- `validate_entry` - 12 implementacji w różnych modułach
- `plan_offload` - 12 implementacji w różnych modułach
- `selected` - 12 implementacji w różnych modułach
- `render_text` - 4 implementacji w różnych modułach
- `validate_runtime` - 4 implementacji w różnych modułach

## Top kandydaci

| score | plik | funkcja | argumenty | proponowana komórka |
|---|---|---|---|---|
| 4.0 | `.governance/branch_intent_reconciliation.py` | `digest` | value, length | `branch_intent_reconciliation.digest` |
| 4.0 | `.governance/branch_intent_reconciliation.py` | `parse_json` | content | `branch_intent_reconciliation.parse_json` |
| 4.0 | `.governance/branch_intent_reconciliation.py` | `reconcile` | report, observation, evidence_root | `branch_intent_reconciliation.reconcile` |
| 4.0 | `.governance/branch_lifecycle_check.py` | `parse_snapshot_pulls` | pulls_value | `branch_lifecycle_check.parse_snapshot_pulls` |
| 4.0 | `.governance/branch_lifecycle_check.py` | `parse_snapshot` | value, expected_repository | `branch_lifecycle_check.parse_snapshot` |
| 4.0 | `.governance/branch_lifecycle_check.py` | `evaluate` | snapshot, focus_branch | `branch_lifecycle_check.evaluate` |
| 4.0 | `.governance/change_lease_check.py` | `validate_publication_lease_fields` | value, phase, errors | `change_lease_check.validate_publication_lease_fields` |
| 4.0 | `.governance/change_lease_check.py` | `validate_lease` | value | `change_lease_check.validate_lease` |
| 4.0 | `.governance/change_lease_check.py` | `validate_request` | value | `change_lease_check.validate_request` |
| 4.0 | `.governance/check_required_checks.py` | `resolve_source` | root, script_path | `check_required_checks.resolve_source` |
| 4.0 | `.governance/check_required_checks.py` | `compare` | required, published | `check_required_checks.compare` |
| 4.0 | `.governance/decision_record.py` | `classify_action` | action | `decision_record.classify_action` |
| 4.0 | `.governance/decision_record.py` | `parse_value` | raw | `decision_record.parse_value` |
| 4.0 | `.governance/decision_record.py` | `format_value` | value | `decision_record.format_value` |
| 4.0 | `.governance/generate_required_checks.py` | `resolved_checks_text` | text, sources, callers | `generate_required_checks.resolved_checks_text` |
| 4.0 | `.governance/policy_dsl_check.py` | `extract_markdown` | source | `policy_dsl_check.extract_markdown` |
| 4.0 | `.governance/policy_dsl_check.py` | `parse_expression` | text, line | `policy_dsl_check.parse_expression` |
| 4.0 | `.governance/policy_dsl_check.py` | `parse_condition` | text, line | `policy_dsl_check.parse_condition` |
| 4.0 | `.governance/repository_policy.py` | `selected_policy` | manifest | `repository_policy.selected_policy` |
| 4.0 | `.governance/seed_baseline.py` | `digest` | raw | `seed_baseline.digest` |
| 4.0 | `.governance/seed_baseline.py` | `canonical` | value | `seed_baseline.canonical` |
| 4.0 | `.governance/snapshot_migration.py` | `digest` | value | `snapshot_migration.digest` |
| 4.0 | `.governance/snapshot_migration.py` | `matches` | pattern, value | `snapshot_migration.matches` |
| 4.0 | `.governance/terminal_lease_release.py` | `decode` | raw | `terminal_lease_release.decode` |
| 4.0 | `.governance/terminal_lease_release.py` | `encoded` | value | `terminal_lease_release.encoded` |
| 4.0 | `.governance/ticket_activity.py` | `parse_ticket_state_text` | text | `ticket_activity.parse_ticket_state_text` |
| 4.0 | `.governance/ticket_activity.py` | `resolve` | root, ticket_dir, active_statuses | `ticket_activity.resolve` |
| 4.0 | `.governance/ticket_allocation.py` | `parse_config` | path | `ticket_allocation.parse_config` |
| 4.0 | `.governance/ticket_allocation.py` | `canonical_repository_ref` | url | `ticket_allocation.canonical_repository_ref` |
| 4.0 | `.governance/ticket_allocation.py` | `canonical_digest` | value | `ticket_allocation.canonical_digest` |
| 4.0 | `.governance/ticket_index_merge_driver.py` | `extract_table_rows` | content | `ticket_index_merge_driver.extract_table_rows` |
| 4.0 | `.governance/ticket_index_merge_driver.py` | `parse_ticket_rows` | lines | `ticket_index_merge_driver.parse_ticket_rows` |
| 4.0 | `.governance/ticket_index_merge_driver.py` | `merge_ticket_index_content` | ancestor_text, current_text, other_text | `ticket_index_merge_driver.merge_ticket_index_content` |
| 4.0 | `.governance/ticket_input.py` | `parse_json` | data | `ticket_input.parse_json` |
| 4.0 | `.governance/ticket_input.py` | `validate_document_contract` | doc, ticket | `ticket_input.validate_document_contract` |
| 4.0 | `.governance/ticket_input.py` | `validate_ticket_path` | name | `ticket_input.validate_ticket_path` |
| 4.0 | `.governance/ticket_restoration.py` | `validate_request` | request, workstream | `ticket_restoration.validate_request` |
| 4.0 | `.governance/work_continuity.py` | `canonical_bytes` | value | `work_continuity.canonical_bytes` |
| 4.0 | `.governance/work_continuity.py` | `canonical_digest` | value | `work_continuity.canonical_digest` |
| 4.0 | `.governance/work_continuity.py` | `validate_repository` | value, label | `work_continuity.validate_repository` |

Uwaga: ta sama nazwa funkcji nie oznacza identycznej implementacji - przed scaleniem porównaj ciała funkcji (make wrap + golden dla każdej kopii).

Następny krok: `make wrap FUNC=<plik>:<funkcja> CELL=<komórka>` dla 3-5 pierwszych pozycji.
