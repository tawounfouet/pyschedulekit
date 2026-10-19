# V1 Persistence Golden Fixtures

These files are immutable compatibility evidence for persisted PyScheduleKit serialization.

## Policy

- **Append-only:** do not rewrite an existing golden fixture after merge.
- **Hash-protected:** every fixture SHA-256 is recorded in `manifest.json` and duplicated in
  `tests/compatibility/test_v1_golden_persistence_fixtures.py`.
- **Historical provenance:** released fixtures point to immutable release ref
  `v0.1.0a3`; final pre-1.0 fixtures point to immutable commit
  `945ec1732fc03419f4d82bd81750bf7bf1032fd6`.
- **Legacy reads:** old ScheduleDefinition v1/v2 bytes must remain readable throughout 1.x,
  but current writers are not required to keep emitting those old versions.
- **Current-byte stability evidence:** formats whose writer version has not changed are
  re-encoded in tests and must reproduce the committed bytes exactly.
- **Database migration fixtures:** SQLite database/schema fixtures belong to V1-02.C and are
  deliberately not mixed into this serialization fixture set.

## Layout

```text
persistence/v1/
├── manifest.json
├── released/
│   └── v0.1.0a3/
│       ├── schedule_definition_v1_interval.json
│       ├── retry_policy_v1_exponential.json
│       └── execution_result_v1_failure.json
└── pre1/
    └── 945ec1732fc03419f4d82bd81750bf7bf1032fd6/
        ├── schedule_definition_v2_business_day.json
        ├── schedule_definition_v3_composite.json
        ├── calendar_value_v1.json
        └── calendar_collection_v1.json
```

## Change discipline

If a future compatible writer version is introduced, add a new fixture with a new versioned
filename/source directory and update the manifest. Never modify a historical fixture merely
to make a new writer test pass.

If a fixture must be corrected because the captured bytes were proven not to represent the
declared source, treat that as a compatibility-evidence incident: document the correction
explicitly in the changelog and V1 compatibility record.
