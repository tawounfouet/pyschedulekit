# Changelog

All notable changes to PyScheduleKit will be documented in this file.

The project follows Semantic Versioning once public contracts begin to stabilize.

## [Unreleased]

### Added

- Core temporal Value Objects: `Instant`, `Duration`, `Timezone`, `TimeWindow`, and `GracePeriod`.
- Explicit `Clock` port with `SystemClock` production adapter.
- Deterministic `FixedClock` and `MutableClock` testing adapters.
- Explicit DST nonexistent/ambiguous civil-time validation.
- LOT-01 temporal qualification tests.
- Initial repository and packaging foundation.
- Domain-first package boundaries.
- Static architecture fitness tests.
- CI quality gates.
