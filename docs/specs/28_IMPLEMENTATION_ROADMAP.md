# PyScheduleKit — Implementation Roadmap

**Document :** `28_IMPLEMENTATION_ROADMAP.md`  
**Projet :** PyScheduleKit  
**Statut :** Roadmap d’implémentation de référence  
**Nature :** Delivery Plan — Milestones / Lots / Dependencies / Exit Criteria / Qualification Levels  
**Langue :** Français

**Documents de référence :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
- `03_SCHEDULING_DOMAIN_VOCABULARY.md`
- `04_SCHEDULING_BUSINESS_OBJECTS.md`
- `05_SCHEDULING_ENTITIES_AND_VALUE_OBJECTS.md`
- `07_SCHEDULING_ERD.md`
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`
- `11_DATE_INTERVAL_AND_CRON_TRIGGERS.md`
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`
- `14_CONCURRENCY_AND_OVERLAP_MODEL.md`
- `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`
- `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`
- `17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md`
- `18_SCHEDULER_RUNTIME_AND_WAKEUP_MODEL.md`
- `19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md`
- `20_DISTRIBUTED_COORDINATION_LEASES_AND_LEADER_ELECTION.md`
- `21_OBSERVABILITY_AUDIT_EVENTS_AND_DIAGNOSTICS_MODEL.md`
- `23_TARGET_ARCHITECTURE.md`
- `24_PUBLIC_API_SPEC.md`
- `25_ERROR_MODEL.md`
- `26_SECURITY_AND_CONFIGURATION_POLICY.md`
- `27_TEST_MATRIX_AND_ACCEPTANCE_CRITERIA.md`

---

# 1. Objectif

Cette roadmap répond à :

> **Dans quel ordre construire PyScheduleKit afin d’obtenir rapidement un scheduler fonctionnel, tout en ajoutant progressivement les garanties de correction, persistance, récupération, concurrence et distribution ?**

L’objectif n’est pas :

```text
d'implémenter tous les documents
en même temps
```

mais de construire une succession de :

```text
vertical slices
```

chacune :

```text
fonctionnelle

testable

qualifiable

réutilisable dans le lot suivant
```

---

# 2. Philosophie de livraison

PyScheduleKit suit la progression :

```text
Semantic Correctness
        ↓
In-Memory Execution
        ↓
Persistent Execution
        ↓
Crash Safety
        ↓
Multi-Worker
        ↓
Multi-Scheduler
        ↓
Distributed Ownership
```

---

# 3. Règle principale

> **Ne jamais introduire une complexité distribuée avant d’avoir prouvé la même sémantique en mémoire puis en persistance locale.**

---

# 4. Anti-roadmap

L’ordre suivant serait mauvais :

```text
Kafka
↓
PostgreSQL
↓
Kubernetes Lease
↓
OpenTelemetry
↓
Cron
↓
Schedule
```

---

# 5. Ordre cible

L’ordre cible est :

```text
Time
↓
Trigger
↓
Schedule
↓
Occurrence
↓
SchedulerEngine
↓
Execution
↓
Runtime
↓
Policies
↓
Persistence
↓
Observability
↓
Outbox
↓
Crash Recovery
↓
Distributed Coordination
```

---

# 6. Vertical Slice comme unité de progression

Chaque milestone doit pouvoir être démontré par :

```text
un scénario utilisateur complet
```

et pas seulement par :

```text
des classes isolées
```

---

# 7. Premier scénario de référence

Le premier scénario cible est volontairement minimal :

```text
10:00

Schedule every 10 minutes

↓ 10:10

Occurrence

↓

ExecutionRequest

↓

Execution

↓

Attempt

↓

SUCCESS
```

---

# 8. Niveau de qualification

La roadmap reprend les niveaux du document 27 :

```text
Level 0 — Conceptual

Level 1 — Unit Qualified

Level 2 — In-Memory Qualified

Level 3 — Persistent Qualified

Level 4 — Crash Qualified

Level 5 — Distributed Qualified
```

---

# 9. Grandes phases

La roadmap est organisée en six phases :

```text
PHASE A — Core Semantics

PHASE B — Functional In-Memory Scheduler

PHASE C — Policies & Public API

PHASE D — Persistence & Reliability

PHASE E — Distributed Runtime

PHASE F — Production Qualification
```

---

# 10. Vue d’ensemble

```text
PHASE A
Domain Foundations
    │
    ▼
PHASE B
Working Scheduler
    │
    ▼
PHASE C
Usable Framework
    │
    ▼
PHASE D
Durable Scheduler
    │
    ▼
PHASE E
Distributed Scheduler
    │
    ▼
PHASE F
Production Qualification
```

---

# 11. Roadmap globale

```text
LOT-00  Repository & Packaging Foundation

LOT-01  Time Model

LOT-02  Trigger Foundations

LOT-03  DateTrigger & IntervalTrigger

LOT-04  CronTrigger

LOT-05  Schedule Aggregate

LOT-06  Occurrence Planning

LOT-07  In-Memory Persistence

LOT-08  SchedulerEngine

LOT-09  ExecutionRequest & Execution Lifecycle

LOT-10  Local Executor

LOT-11  Manual run_pending()

LOT-12  SchedulerRuntime

LOT-13  Misfire

LOT-14  Catch-Up & Coalescing

LOT-15  Concurrency

LOT-16  Retry & Backoff

LOT-17  Public Scheduler API

LOT-18  Testing Toolkit

LOT-19  Error Model

LOT-20  Serialization & Security

LOT-21  SQLite Persistence

LOT-22  Restart Recovery

LOT-23  Observability & Audit

LOT-24  PostgreSQL Adapter

LOT-25  Transactional Outbox

LOT-26  Crash Consistency Qualification

LOT-27  Multi-Worker Runtime

LOT-28  Distributed Concurrency

LOT-29  Multi-Scheduler Coordination

LOT-30  Worker Leases

LOT-31  Fencing

LOT-32  Leader Election

LOT-33  Distributed Recovery

LOT-34  Public Compatibility & Documentation

LOT-35  Performance / Security / Production Qualification
```

---

# PHASE A — CORE SEMANTICS

---

# 12. LOT-00 — Repository & Packaging Foundation

## Objectif

Créer le squelette minimal du projet sans sur-construire.

---

# 13. Livrables

```text
pyproject.toml

src/pyschedulekit/

tests/

README.md

LICENSE

CHANGELOG.md

py.typed
```

---

# 14. Arborescence initiale

```text
src/
└── pyschedulekit/
    ├── __init__.py
    ├── domain/
    ├── application/
    ├── ports/
    ├── infrastructure/
    └── testing/
```

---

# 15. Tooling

Mettre en place :

```text
pytest

type checking

linting

formatting

coverage

pre-commit
```

---

# 16. Architecture fitness rules

Dès LOT-00 :

```text
domain must not import infrastructure
```

---

# 17. CI baseline

Pipeline :

```text
lint
type-check
unit tests
```

---

# 18. Critères de sortie

```text
package importable

pytest green

typing green

CI green

src layout stable
```

---

# 19. Qualification

```text
Level 0
```

---

# 20. LOT-01 — Time Model

## Objectif

Créer les primitives temporelles sur lesquelles tout le reste dépend.

---

# 21. Objets

```text
Instant

Duration

Timezone

TimeWindow

GracePeriod
```

---

# 22. Ports

```text
Clock
```

---

# 23. Adapters de test

```text
FixedClock

MutableClock
```

---

# 24. Adapter production

```text
SystemClock
```

---

# 25. Décisions à implémenter

```text
timezone-aware datetime only

UTC internal instant semantics

IANA timezone

[start, end) windows
```

---

# 26. Tests minimum

```text
T-TIME-001 → T-TIME-012
```

---

# 27. Architecture test

Interdire :

```text
datetime.now()
```

hors adapter `SystemClock`.

---

# 28. Critères de sortie

```text
all time objects validated

FixedClock deterministic

MutableClock usable in tests

naive datetime rejected

DST test fixtures ready
```

---

# 29. Qualification

```text
Level 1
```

---

# 30. LOT-02 — Trigger Foundations

## Objectif

Définir le contrat fondamental :

```text
reference instant
→
next occurrence
```

---

# 31. Types

```text
Trigger

TriggerKind

TriggerExhausted representation
```

---

# 32. Contrat principal

```python
next_after(reference) -> Instant | None
```

avec :

```text
result > reference
```

---

# 33. Invariants

```text
deterministic

immutable

no I/O

no hidden Clock

bounded
```

---

# 34. TriggerContractSuite

Créer immédiatement une suite de conformité réutilisable.

---

# 35. Critères de sortie

```text
base Trigger protocol stable

contract test reusable

strict progression proven
```

---

# 36. Qualification

```text
Level 1
```

---

# 37. LOT-03 — DateTrigger & IntervalTrigger

## DateTrigger

Implement :

```text
one-shot occurrence
```

---

# 38. IntervalTrigger

Implement :

```text
fixed-rate elapsed-duration recurrence
```

---

# 39. Important

Ne pas implémenter :

```text
fixed-delay
```

dans ce lot.

---

# 40. Interval math

Utiliser :

```text
anchor + n * interval
```

sans boucle linéaire.

---

# 41. Tests

```text
T-TRG-001 → 015
```

---

# 42. Démo de sortie

```python
IntervalTrigger(minutes=10)
```

doit produire :

```text
10:10
10:20
10:30
```

depuis anchor 10:00.

---

# 43. Qualification

```text
Level 1
```

---

# 44. LOT-04 — CronTrigger

## Objectif

Introduire le scheduling calendaire.

---

# 45. Scope V1

```text
5-field cron

minute

hour

day-of-month

month

day-of-week
```

---

# 46. Timezone

Chaque CronTrigger doit avoir :

```text
effective timezone
```

---

# 47. À figer

```text
DOM / DOW semantics

DST ambiguity policy

DST nonexistent time policy
```

---

# 48. Search horizon

Obligatoire.

---

# 49. CronExpression

Créer VO dédiée.

---

# 50. Tests

```text
T-TRG-020 → T-TRG-030
```

plus property tests.

---

# 51. Exit criteria

```text
daily cron works

month boundaries

leap year

DST tests green

serialization model ready
```

---

# 52. Qualification

```text
Level 1
```

---

# 53. LOT-05 — Schedule Aggregate

## Objectif

Créer le cœur durable du domaine.

---

# 54. Types

```text
ScheduleId

ScheduleRevision

PersistenceVersion

ScheduleState

TargetRef

ScheduleDefinition

Schedule
```

---

# 55. ScheduleDefinition

Contient :

```text
TargetRef

Trigger

Timezone

CalendarRef optional

ScheduleWindow

SchedulingPolicySet

ExecutionPolicySet
```

---

# 56. State V1

```text
ACTIVE

PAUSED

CANCELLED

COMPLETED
```

---

# 57. Domain Methods

```text
pause()

resume()

reschedule()

cancel()

complete()
```

---

# 58. Invariants

```text
terminal state immutable

revision changes only on definition change

operational checkpoint does not change revision
```

---

# 59. Tests

```text
T-SCH-001 → 015
```

---

# 60. Qualification

```text
Level 1
```

---

# 61. LOT-06 — Occurrence Planning

## Objectif

Passer de :

```text
Schedule + Trigger
```

à :

```text
Occurrence
```

---

# 62. Types

```text
Occurrence

OccurrenceKey

NextRunTime
```

---

# 63. OccurrenceKey

Canonical :

```text
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

---

# 64. OccurrencePlanner

Responsable :

```text
Trigger

Timezone

Calendar

ScheduleWindow
```

---

# 65. First implementation

Calendar peut être :

```text
AlwaysCalendar
```

uniquement.

---

# 66. Important

Ne pas bloquer progression sur BusinessCalendar avancé.

---

# 67. Tests

```text
T-SCH-020 → 022
```

et planning basics.

---

# 68. Qualification

```text
Level 1
```

---

# PHASE B — FUNCTIONAL IN-MEMORY SCHEDULER

---

# 69. LOT-07 — In-Memory Persistence

## Objectif

Créer les premiers ports Repository + UnitOfWork.

---

# 70. Ports

```text
ScheduleRepository

ExecutionRequestRepository

ExecutionRepository

UnitOfWork

UnitOfWorkFactory
```

---

# 71. In-memory implementations

```text
InMemoryScheduleRepository

InMemoryExecutionRequestRepository

InMemoryExecutionRepository

InMemoryUnitOfWork
```

---

# 72. Très important

InMemory doit respecter :

```text
transactional semantics
```

au niveau logique.

---

# 73. Pas simple dictionnaire partagé sans rollback

---

# 74. Tests

Première version du :

```text
PersistenceContractSuite
```

---

# 75. Critères de sortie

```text
save/load round-trip

commit

rollback

optimistic version simulation
```

---

# 76. Qualification

```text
Level 2 foundation
```

---

# 77. LOT-08 — SchedulerEngine

## Objectif

Créer le premier moteur d’évaluation réel.

---

# 78. Input

```text
evaluation_now
```

---

# 79. Flow minimal

```text
find due Schedule

reload

plan occurrence

create ExecutionRequest

advance next_run_time

commit
```

---

# 80. Pas encore

```text
misfire

catch-up

concurrency

retry
```

---

# 81. Pourquoi ?

Valider d’abord la chaîne fondamentale.

---

# 82. Same-now

Implement explicitement.

---

# 83. Per-Schedule transaction

Recommandation dès ce lot.

---

# 84. Tests

```text
T-RUN-001 → 010
```

pour sous-ensemble applicable.

---

# 85. Démo

```text
IntervalTrigger 10m
+
MutableClock
+
run engine
```

produit Request.

---

# 86. Qualification

```text
Level 2
```

---

# 87. LOT-09 — ExecutionRequest & Execution Lifecycle

## Objectif

Créer la frontière entre scheduling et exécution.

---

# 88. Types

```text
ExecutionRequest

Execution

Attempt

ExecutionResult

AttemptResult

Failure
```

---

# 89. States

Implémenter state machines de :

```text
Request

Execution

Attempt
```

---

# 90. ExecutionPolicySnapshot

Créer dès ce lot.

---

# 91. Tests

```text
T-EXE-001 → 015
```

---

# 92. Important

Aucun Executor réel nécessaire encore.

---

# 93. Qualification

```text
Level 1
```

---

# 94. LOT-10 — Local Executor

## Objectif

Exécuter un Target Python local.

---

# 95. First adapter

```text
CallableExecutor
```

---

# 96. Scope

```text
trusted local callable
```

---

# 97. Flow

```text
Execution QUEUED

↓

Attempt RUNNING committed

↓

invoke callable outside transaction

↓

normalize result

↓

complete Attempt + Execution
```

---

# 98. FakeExecutor

Créer parallèlement.

---

# 99. ScriptedExecutor

Pour tests de retries futurs.

---

# 100. Tests

```text
success

target exception

normalization

no exception leakage
```

---

# 101. Qualification

```text
Level 2
```

---

# 102. LOT-11 — `run_pending()`

## Objectif

Obtenir le premier PyScheduleKit utilisable sans background runtime.

---

# 103. Public primitive

```python
scheduler.run_pending()
```

---

# 104. Flow V0

```text
SchedulerEngine
↓
ExecutionRequest
↓
ExecutionService
↓
CallableExecutor
```

---

# 105. Première grande milestone

À la fin LOT-11 :

```text
PyScheduleKit fonctionne réellement
```

---

# 106. Demo

```python
clock = MutableClock(...)
scheduler = Scheduler(clock=clock)

scheduler.add_schedule(
    target=my_task,
    trigger=IntervalTrigger(minutes=10),
)

clock.advance(minutes=10)
scheduler.run_pending()
```

---

# 107. Expected

```text
one successful execution
```

---

# 108. Tests

```text
T-E2E-001

T-E2E-002 partial
```

---

# 109. Qualification

```text
Level 2 — In-Memory Qualified
```

---

# 110. MILESTONE M1

## `IN-MEMORY SCHEDULER`

PyScheduleKit peut :

```text
schedule

advance virtual time

evaluate

execute

record result
```

sans :

```text
sleep

DB

threads

network
```

---

# 111. LOT-12 — SchedulerRuntime

## Objectif

Ajouter le fonctionnement continu.

---

# 112. Components

```text
SchedulerRuntime

WakeUpPlanner

WakeUpCoordinator

RuntimeState

RuntimeHealth
```

---

# 113. First runtime strategy

```text
fixed bounded polling
```

---

# 114. Thread model

```text
one scheduler thread
```

---

# 115. Public lifecycle

```text
start()

run_forever()

shutdown()
```

---

# 116. Tests

```text
T-RUN-020 → 047
```

---

# 117. Important

Pas de :

```text
asyncio
```

encore.

---

# 118. Qualification

```text
Level 2
```

---

# PHASE C — POLICIES & PUBLIC FRAMEWORK

---

# 119. LOT-13 — Misfire

## Objectif

Gérer le retard.

---

# 120. Types

```text
GracePeriod

MisfirePolicy

LatenessClassification

SchedulingDecision
```

---

# 121. V1 behaviors

```text
SKIP

RUN_NOW
```

---

# 122. Pipeline

```text
Occurrence
↓
lateness classification
↓
MisfirePolicy
↓
SchedulingDecision
```

---

# 123. Tests

```text
T-MIS-001 → 006
```

---

# 124. Qualification

```text
Level 2
```

---

# 125. LOT-14 — Catch-Up & Coalescing

## Objectif

Gérer les occurrences ratées pendant outage.

---

# 126. Types

```text
CatchUpPlanner

RecoveryPlan

CoalescingPolicy
```

---

# 127. V1 coalescing

```text
NONE

LATEST
```

---

# 128. Required bounds

```text
max_occurrences

search horizon

batch size
```

---

# 129. Tests

```text
T-CAT-001 → 007
```

---

# 130. Qualification

```text
Level 2
```

---

# 131. LOT-15 — Concurrency

## Objectif

Empêcher des overlaps incompatibles.

---

# 132. First domain layer

```text
ConcurrencyPolicy

ConcurrencyKey

ConcurrencyEvaluator
```

---

# 133. V1

```text
ALLOW

LIMIT

DROP

QUEUE
```

---

# 134. InMemoryConcurrencyCoordinator

Ensuite.

---

# 135. Important split

```text
SHOULD admit
```

versus :

```text
CAN atomically admit
```

---

# 136. Tests

```text
T-CON-001 → 009
```

puis InMemory atomic coordinator.

---

# 137. Qualification

```text
Level 2
```

---

# 138. LOT-16 — Retry & Backoff

## Objectif

Ajouter les retries d’Execution.

---

# 139. Types

```text
RetryPolicy

RetryDecision

BackoffPolicy

FailureCategory

ExecutionCompletionReason
```

---

# 140. V1 policies

```text
NONE

FIXED

EXPONENTIAL
```

---

# 141. Required semantics

```text
same Execution

new Attempt

max_attempts includes first

stable IdempotencyKey
```

---

# 142. Tests

```text
T-RET-001 → 015

T-E2E-009

T-E2E-010
```

---

# 143. Qualification

```text
Level 2
```

---

# 144. MILESTONE M2

## `FULL IN-MEMORY DOMAIN`

PyScheduleKit sait désormais gérer :

```text
Date

Interval

Cron

Pause/Resume

Misfire

Catch-Up

Concurrency

Retry

Runtime
```

en mémoire.

---

# 145. LOT-17 — Public Scheduler API

## Objectif

Faire correspondre l’implémentation à :

```text
24_PUBLIC_API_SPEC.md
```

---

# 146. Public types

```text
Scheduler

ScheduleHandle

ScheduleSnapshot

ExecutionSnapshot

DateTrigger

IntervalTrigger

CronTrigger

TargetRef
```

---

# 147. Methods

```text
add_schedule

get_schedule

list_schedules

pause_schedule

resume_schedule

reschedule_schedule

cancel_schedule

run_pending

start

run_forever

shutdown

health
```

---

# 148. Public imports

Figés provisoirement.

---

# 149. Root namespace

Keep compact.

---

# 150. Tests

```text
T-API-001 → 020
```

---

# 151. Documentation examples

Doivent être exécutables.

---

# 152. Qualification

```text
Level 2
```

---

# 153. LOT-18 — Testing Toolkit

## Objectif

Transformer la testabilité en feature officielle.

---

# 154. Public tools

```text
FixedClock

MutableClock

SchedulerHarness

FakeExecutor

ScriptedExecutor
```

---

# 155. Harness API

```text
advance()

run_pending()

run_until_idle()

executions()
```

---

# 156. Guard

```text
max_cycles
```

sur `run_until_idle`.

---

# 157. Important

Le Harness utilise :

```text
real SchedulerEngine
```

---

# 158. Qualification

```text
Level 2
```

---

# 159. LOT-19 — Error Model

## Objectif

Implémenter :

```text
25_ERROR_MODEL.md
```

---

# 160. Public hierarchy

```text
PyScheduleKitError

ValidationError

ConfigurationError

DomainError

NotFoundError

ConflictError

PersistenceError

CoordinationError

ExecutorError

SchedulerRuntimeError
```

---

# 161. Failure remains separate.

---

# 162. Vendor error normalization

Même si seulement InMemory/Callable au début.

---

# 163. Stable error codes

Implémenter dès maintenant.

---

# 164. Tests

```text
T-ERR-001 → 022
```

---

# 165. Qualification

```text
Level 2
```

---

# 166. LOT-20 — Serialization & Security Baseline

## Objectif

Avant toute vraie persistance, sécuriser les formats.

---

# 167. Implement

```text
Trigger codecs

Policy codecs

TargetRef codecs

Failure codecs
```

---

# 168. Rules

```text
JSON-like only

schema_version

strict fields

no pickle

no eval

no arbitrary class path
```

---

# 169. Registries

```text
TriggerCodecRegistry

ExecutorRegistry
```

---

# 170. Python Target modes

```text
local callable

registered TargetRef
```

---

# 171. Tests

```text
T-SEC-001 → 020

T-SEC-040 → 045
```

---

# 172. MILESTONE M3

## `USABLE LOCAL FRAMEWORK`

À ce stade :

```text
pip install
```

peut raisonnablement permettre un usage local avec :

```text
clean public API

testing toolkit

error model

secure serialization
```

---

# PHASE D — PERSISTENCE & RELIABILITY

---

# 173. LOT-21 — SQLite Persistence

## Objectif

Premier adapter durable.

---

# 174. Pourquoi SQLite d’abord ?

```text
simple

local

zero external service

excellent for learning persistence
```

---

# 175. Implement

```text
SQLite UnitOfWork

ScheduleRepository

ExecutionRequestRepository

ExecutionRepository

Attempt persistence
```

---

# 176. Migrations

Initial schema.

---

# 177. Tables minimales

```text
schedules

execution_requests

executions

attempts
```

---

# 178. Unique constraints

```text
OccurrenceKey

RequestId → Execution

ExecutionId + AttemptNumber
```

---

# 179. Tests

```text
T-PER-001 → 035
```

---

# 180. Qualification

```text
Level 3
```

---

# 181. LOT-22 — Restart Recovery

## Objectif

Prouver que persistence ≠ stockage passif.

---

# 182. Scenarios

```text
Schedule persists across restart

RETRY_WAIT persists

WAITING_ADMISSION persists

future next_run_time persists
```

---

# 183. RuntimeReconciler baseline

Créer :

```text
startup reconciliation
```

---

# 184. Local RUNNING Attempt after crash

V1 local rule à définir précisément.

Probable :

```text
mark stale / worker-lost
```

puis recovery policy.

---

# 185. Tests

```text
T-E2E-011 → 013
```

---

# 186. Qualification

```text
Level 3
```

---

# 187. MILESTONE M4

## `DURABLE LOCAL SCHEDULER`

Le framework peut maintenant :

```text
stop

restart

resume scheduling
```

sans perdre son état principal.

---

# 188. LOT-23 — Observability & Audit

## Objectif

Implémenter le modèle 21 avant distribution.

---

# 189. Baseline

```text
structured logging

CorrelationId

EventId

AuditRecord

DecisionEvidence

RuntimeHealth
```

---

# 190. First event catalogue

```text
ScheduleCreated

ScheduleStateChanged

SchedulingDecisionRecorded

ExecutionRequestCreated

ExecutionCreated

AttemptStarted

AttemptCompleted

RetryScheduled

ExecutionCompleted
```

---

# 191. Metrics abstraction

Minimal.

---

# 192. Tracing

OpenTelemetry adapter peut rester optionnel.

---

# 193. Explain baseline

```text
inspect_schedule

inspect_execution
```

---

# 194. Tests

```text
T-OBS-001 → 034
```

---

# 195. Qualification

```text
Level 3
```

---

# 196. LOT-24 — PostgreSQL Adapter

## Objectif

Ajouter le backend de référence production/distribué.

---

# 197. Prefer

```text
SQLAlchemy
```

possible, mais adapter-specific.

---

# 198. Implement

```text
PostgreSQL repositories

UnitOfWork

locking primitives

indexes
```

---

# 199. Conformance

PostgreSQL doit passer :

```text
same PersistenceContractSuite
```

que SQLite/InMemory.

---

# 200. Additional tests

```text
row locking

SKIP LOCKED

real concurrent transactions
```

---

# 201. Qualification

```text
Level 3
```

---

# 202. LOT-25 — Transactional Outbox

## Objectif

Séparer transaction durable et livraison externe.

---

# 203. Tables

```text
outbox_messages
```

---

# 204. Flow

```text
state mutation
+
outbox insert
+
commit
```

---

# 205. Publisher

Créer :

```text
OutboxPublisher
```

---

# 206. Local first transport

Peut être :

```text
in-process dispatcher
```

pour prouver la sémantique.

---

# 207. Pas besoin de Kafka immédiatement.

---

# 208. Tests

```text
T-OUT-001 → 009
```

---

# 209. Qualification

```text
Level 4 foundation
```

---

# 210. LOT-26 — Crash Consistency Qualification

## Objectif

Prouver la vraie durabilité.

---

# 211. Fault injection

Introduire :

```text
FaultInjectingUnitOfWork

FaultInjectingPublisher
```

---

# 212. Crash points

```text
before insert

after insert

before checkpoint

after checkpoint

before commit

after commit

before publish

after publish
```

---

# 213. Tests

```text
T-PER-040 → 072
```

---

# 214. Exit criteria

Aucun point de crash testé ne produit :

```text
silent lost occurrence

double logical request

advanced checkpoint without durable intent
```

---

# 215. Qualification

```text
Level 4 — Crash Qualified
```

---

# 216. MILESTONE M5

## `CRASH-SAFE PERSISTENT SCHEDULER`

À ce stade :

```text
PostgreSQL

Outbox

Crash Recovery

Audit
```

forment une base production sérieuse.

---

# PHASE E — DISTRIBUTED RUNTIME

---

# 217. LOT-27 — Multi-Worker Runtime

## Objectif

Scaler l’exécution avant de scaler le scheduler.

---

# 218. Pourquoi cet ordre ?

Parce que :

```text
one scheduler

many workers
```

est plus simple que :

```text
many schedulers

many workers
```

---

# 219. Implement

```text
Execution claiming

atomic Attempt start

worker identity
```

---

# 220. First mechanism

PostgreSQL :

```text
FOR UPDATE SKIP LOCKED
```

ou equivalent claim.

---

# 221. Tests

```text
T-DIST-010 → 013
```

---

# 222. Qualification

```text
Level 5 for worker coordination
```

---

# 223. LOT-28 — Distributed Concurrency

## Objectif

Faire respecter :

```text
ConcurrencyKey
```

entre plusieurs workers/schedulers.

---

# 224. Implement

```text
SqlConcurrencyCoordinator
```

---

# 225. Recommended model

```text
row-backed serialization point
```

---

# 226. Tests

```text
T-CON-020

T-CON-021

T-E2E-017
```

---

# 227. Qualification

```text
Level 5
```

---

# 228. LOT-29 — Multi-Scheduler Coordination

## Objectif

Autoriser plusieurs SchedulerRuntime sur même DB.

---

# 229. First strategy

```text
row claiming
```

avec :

```text
FOR UPDATE SKIP LOCKED
```

ou optimistic competition.

---

# 230. Pas de Lease obligatoire

---

# 231. Core protections

```text
OccurrenceKey uniqueness

PersistenceVersion

short transactions
```

---

# 232. Tests

```text
T-DIST-001 → 006

T-E2E-015
```

---

# 233. Qualification

```text
Level 5
```

---

# 234. MILESTONE M6

## `MULTI-NODE SCHEDULER`

Architecture :

```text
Scheduler A
Scheduler B
Scheduler C
      │
      ▼
 PostgreSQL
      │
      ▼
Workers
```

---

# 235. LOT-30 — Worker Leases

## Objectif

Gérer l’ownership de longue durée des Attempts.

---

# 236. Pourquoi seulement maintenant ?

Les claims transactionnels suffisent pour :

```text
starting work
```

Les leases deviennent nécessaires pour :

```text
long-running ownership
```

---

# 237. Implement

```text
Lease

ResourceKey

NodeId

LeaseManager

LeaseDuration
```

---

# 238. Lease table

```text
resource_key

owner_id

fencing_token

expires_at
```

---

# 239. Coordination time

Utiliser :

```text
DB authoritative time
```

si possible.

---

# 240. Tests

```text
T-DIST-020 → 027
```

---

# 241. Qualification

```text
Level 5
```

---

# 242. LOT-31 — Fencing

## Objectif

Empêcher le stale owner d’agir après takeover.

---

# 243. Implement

```text
FencingToken
```

---

# 244. Rules

```text
monotonic per resource

checked on protected mutation

never reset
```

---

# 245. Tests

```text
T-DIST-030 → 032

T-DIST-050
```

---

# 246. Important

Documenter clairement :

```text
fencing only protects resources that verify it
```

---

# 247. Qualification

```text
Level 5
```

---

# 248. LOT-32 — Leader Election

## Objectif

Ajouter leadership seulement pour les tâches globales.

---

# 249. Non-goal

Ne pas faire du leader :

```text
le seul scheduler
```

---

# 250. Implement

```text
LeaderElectionPort

LeadershipRole

LeadershipEpoch
```

---

# 251. First use cases

Possible :

```text
retention cleanup

global reconciliation

maintenance
```

---

# 252. Tests

```text
T-DIST-040 → 045
```

---

# 253. Qualification

```text
Level 5
```

---

# 254. LOT-33 — Distributed Recovery

## Objectif

Fermer les scénarios de panne difficiles.

---

# 255. Scenarios

```text
worker dies mid-attempt

scheduler dies after claim

lease expires

old worker result arrives late

leader failover

outbox duplicates

network partition
```

---

# 256. RuntimeReconciler advanced

Doit gérer :

```text
stale Attempts

orphaned Requests

expired ownership

late results
```

---

# 257. Important

Ne pas inventer :

```text
exactly-once
```

---

# 258. Guarantee cible

```text
durable logical identities

recoverable state

at-least-once delivery

idempotence/fencing where available
```

---

# 259. Tests

Chaos/fault injection distribué.

---

# 260. Qualification

```text
Level 5
```

---

# PHASE F — PRODUCTION QUALIFICATION

---

# 261. LOT-34 — Public Compatibility & Documentation

## Objectif

Préparer la stabilisation de l’API.

---

# 262. Tasks

```text
public namespace audit

__all__

type hints

py.typed

docstrings

examples

migration notes

deprecation framework
```

---

# 263. API compatibility tests

```text
T-COMP-005
```

---

# 264. Documentation tests

Tous les snippets :

```text
README

quickstart

24_PUBLIC_API_SPEC
```

doivent être exécutables.

---

# 265. User Guide

Minimum :

```text
Quickstart

Triggers

Policies

Persistence

Testing

Production Deployment
```

---

# 266. Qualification

```text
release readiness
```

---

# 267. LOT-35 — Performance / Security / Production Qualification

## Objectif

Dernier gate avant stable.

---

# 268. Security suite

Exécuter :

```text
T-SEC-001 → 045
```

---

# 269. Static checks

```text
no pickle

no eval

no exec

no forbidden domain imports

no datetime.now outside adapters
```

---

# 270. Performance tests

```text
T-PERF-001 → 006
```

---

# 271. Load scenarios

```text
10k schedules

midnight burst

retry storm

outbox backlog
```

---

# 272. Chaos scenarios

```text
scheduler kill

worker kill

DB outage

duplicate signal

lost signal

lease expiry
```

---

# 273. Migration tests

```text
T-MIG-001 → 005
```

---

# 274. Acceptance

Toutes les features marquées :

```text
SUPPORTED
```

doivent réussir leurs suites.

---

# 275. MILESTONE M7

## `PRODUCTION-QUALIFIED CORE`

PyScheduleKit possède :

```text
stable public API

persistent scheduling

restart recovery

crash safety

observability

security baseline

distributed option
```

---

# 276. Versioning Strategy

La roadmap ne force pas les numéros, mais une progression possible est :

```text
0.1.x
Core semantics

0.2.x
In-memory Scheduler

0.3.x
Policies + Runtime

0.4.x
Public API + Testing

0.5.x
SQLite persistence

0.6.x
PostgreSQL + Outbox

0.7.x
Crash recovery

0.8.x
Multi-worker

0.9.x
Multi-scheduler

1.0.0
Public contract freeze
```

---

# 277. Alternative

La distribution avancée peut rester :

```text
1.1+

1.2+
```

si 1.0 vise d’abord un scheduler durable single-node.

---

# 278. Recommandation

Ne pas bloquer :

```text
1.0
```

sur :

```text
leader election

fencing

full distributed mode
```

si la valeur V1 principale est déjà solide.

---

# 279. V1 Core recommandé

Pour une vraie première version stable, le minimum pertinent est :

```text
DateTrigger

IntervalTrigger

CronTrigger

Schedule lifecycle

Misfire

Catch-Up

Concurrency local

Retry

Public API

Testing Harness

SQLite/PostgreSQL

Restart recovery

Observability

Security

Outbox
```

---

# 280. Distributed features

Peuvent être :

```text
experimental
```

jusqu’à qualification complète.

---

# 281. Feature Delivery Policy

Chaque feature possède :

```text
status
```

parmi :

```text
NOT_IMPLEMENTED

EXPERIMENTAL

SUPPORTED
```

---

# 282. `NOT_IMPLEMENTED`

API absente ou derrière internal code.

---

# 283. `EXPERIMENTAL`

API possible, mais :

```text
compatibility not guaranteed
```

et tests incomplets pour stable contract.

---

# 284. `SUPPORTED`

Tous acceptance criteria requis sont verts.

---

# 285. Lot Definition of Done

Chaque lot doit produire :

```text
code

tests

documentation

changelog entry if public

acceptance evidence
```

---

# 286. Pas seulement code

Un lot sans tests :

```text
not done
```

---

# 287. Lot Template

Chaque lot d’implémentation pourra être géré avec :

```text
Goal

Scope

Non-goals

Domain objects

Public/API impact

Persistence impact

Security impact

Tests

Acceptance criteria

Migration impact

Docs impact
```

---

# 288. Exemple task breakdown

LOT-03 pourrait devenir :

```text
TASK-0301 DateTrigger Value Object

TASK-0302 Interval Duration Validation

TASK-0303 Interval Anchor Model

TASK-0304 DateTrigger Contract Tests

TASK-0305 Interval Property Tests

TASK-0306 Trigger Documentation
```

---

# 289. PR Size

Préférer :

```text
small coherent PRs
```

plutôt qu’un :

```text
PR implementing entire scheduler
```

---

# 290. Merge Rule

Une PR ne doit pas laisser :

```text
broken architecture
```

même si feature globale est incomplète.

---

# 291. Feature flags internes

Possible pour progression.

Mais éviter :

```text
dead experimental branches
```

permanents.

---

# 292. Vertical Slice Principle

Chaque série de lots devrait se terminer par :

```text
something demonstrable
```

---

# 293. M1 demonstration

```text
virtual-time in-memory scheduler
```

---

# 294. M2 demonstration

```text
Cron + Misfire + Retry
```

---

# 295. M3 demonstration

```text
public API quickstart
```

---

# 296. M4 demonstration

```text
restart scheduler and preserve schedule
```

---

# 297. M5 demonstration

```text
kill after commit, outbox recovers
```

---

# 298. M6 demonstration

```text
two scheduler nodes, one occurrence
```

---

# 299. M7 demonstration

```text
release candidate qualification
```

---

# 300. Dependency Graph

```text
LOT-00
  │
  ▼
LOT-01
  │
  ▼
LOT-02
  │
  ├──────► LOT-03
  │
  └──────► LOT-04
              │
              ▼
           LOT-05
              │
              ▼
           LOT-06
              │
              ▼
           LOT-07
              │
              ▼
           LOT-08
              │
              ▼
           LOT-09
              │
              ▼
           LOT-10
              │
              ▼
           LOT-11
```

---

# 301. Then

```text
LOT-11
  │
  ├──► LOT-12 Runtime
  ├──► LOT-13 Misfire
  ├──► LOT-14 Catch-Up
  ├──► LOT-15 Concurrency
  └──► LOT-16 Retry
           │
           ▼
        LOT-17 Public API
           │
           ▼
        LOT-18 Testing Toolkit
           │
           ▼
        LOT-19 Error Model
           │
           ▼
        LOT-20 Security/Serialization
```

---

# 302. Persistence line

```text
LOT-20
  │
  ▼
LOT-21 SQLite
  │
  ▼
LOT-22 Restart
  │
  ▼
LOT-23 Observability
  │
  ▼
LOT-24 PostgreSQL
  │
  ▼
LOT-25 Outbox
  │
  ▼
LOT-26 Crash Qualification
```

---

# 303. Distributed line

```text
LOT-26
  │
  ▼
LOT-27 Multi-Worker
  │
  ▼
LOT-28 Distributed Concurrency
  │
  ▼
LOT-29 Multi-Scheduler
  │
  ▼
LOT-30 Worker Leases
  │
  ▼
LOT-31 Fencing
  │
  ▼
LOT-32 Leader Election
  │
  ▼
LOT-33 Distributed Recovery
```

---

# 304. Release line

```text
LOT-33
  │
  ▼
LOT-34 API Compatibility
  │
  ▼
LOT-35 Production Qualification
```

---

# 305. Critical Path

La première version utilisable dépend seulement de :

```text
00
01
02
03
05
06
07
08
09
10
11
```

---

# 306. Important

Cron n’est même pas nécessaire pour la première preuve.

---

# 307. Why?

On peut démontrer tout le moteur avec :

```text
IntervalTrigger
```

---

# 308. Cela réduit considérablement le risque initial.

---

# 309. First 10-day implementation philosophy

Sans donner de durée projet rigide, le premier effort devrait surtout viser :

```text
working vertical slice
```

et non :

```text
complete architecture skeleton
```

---

# 310. Premier ordre pratique recommandé

```text
1. Instant / Duration / Clock

2. IntervalTrigger

3. Schedule

4. OccurrenceKey

5. InMemoryRepository

6. SchedulerEngine

7. ExecutionRequest

8. Execution + Attempt

9. FakeExecutor

10. run_pending()
```

---

# 311. Only after that

Ajouter :

```text
DateTrigger

CronTrigger

Runtime thread

Policies
```

---

# 312. Why Interval first?

Parce qu’il permet d’apprendre :

```text
recurrence

anchor

next occurrence

checkpoint

missed occurrences
```

sans complexité calendrier de Cron.

---

# 313. Why DateTrigger second?

Il valide :

```text
finite Trigger

Schedule completion
```

---

# 314. Why Cron after?

Il ajoute :

```text
civil time

timezone

DST

calendar complexity
```

sur un moteur déjà fonctionnel.

---

# 315. Why Persistence late but not too late?

Trop tôt :

```text
domain model constrained by ORM
```

Trop tard :

```text
persistence assumptions contaminate code
```

---

# 316. Correct point

Une fois :

```text
in-memory E2E semantics proven
```

mais avant distribution.

---

# 317. Why Observability before Distribution?

Parce qu’un système distribué sans :

```text
correlation

audit

diagnostics
```

est extrêmement difficile à comprendre.

---

# 318. Why Outbox before Multi-Worker?

Parce que :

```text
durable dispatch
```

doit être prouvé avant de multiplier les consumers.

---

# 319. Why Multi-Worker before Multi-Scheduler?

Pour isoler deux problèmes :

```text
execution distribution
```

puis :

```text
scheduling distribution
```

---

# 320. Why Lease late?

Parce que :

```text
row claim
```

résout déjà énormément de problèmes.

---

# 321. Why Leader Election very late?

Parce que le scheduling ordinaire :

```text
does not need a leader
```

---

# 322. Risk Register

---

# 323. Risk R1 — Over-engineering

Symptôme :

```text
many abstractions

no executable scheduler
```

Mitigation :

```text
M1 must arrive early
```

---

# 324. Risk R2 — Cron dominates project

Mitigation :

```text
IntervalTrigger vertical slice first
```

---

# 325. Risk R3 — ORM-driven domain

Mitigation :

```text
InMemory domain first
```

---

# 326. Risk R4 — Too many policies

Mitigation :

```text
one policy at a time
```

---

# 327. Risk R5 — Threading introduces flaky tests

Mitigation :

```text
run_pending first

virtual time

controlled runtime
```

---

# 328. Risk R6 — Distributed complexity too early

Mitigation :

```text
distribution begins only after crash-safe PostgreSQL
```

---

# 329. Risk R7 — Public API freezes too soon

Mitigation :

```text
API experimental until core semantics proven
```

---

# 330. Risk R8 — Persistence schema churn

Mitigation :

```text
version serialized contracts

delay 1.0 freeze
```

---

# 331. Risk R9 — Retry duplicates external effects

Mitigation :

```text
RetryPolicy default NONE

IdempotencyKey

clear docs
```

---

# 332. Risk R10 — Security regressions

Mitigation :

```text
Security Gate before persistent public release
```

---

# 333. Technical Debt Policy

Tous les shortcuts doivent être explicitement classés :

```text
Temporary

Experimental

Production-ready
```

---

# 334. Example

InMemory repository without isolation :

```text
acceptable only before contract suite
```

---

# 335. Once LOT-07 exits

Il doit respecter :

```text
documented logical transaction semantics
```

---

# 336. Temporary shortcuts forbidden

Même en prototype :

```text
pickle

eval

hidden datetime.now

sleep in domain

commit inside repository
```

---

# 337. Pourquoi ?

Ces shortcuts contaminent directement l’architecture.

---

# 338. Areas where simplification is acceptable

```text
single process

single scheduler thread

limited Trigger set

local executor

minimal telemetry
```

---

# 339. Simplify topology, not semantics

Principe important :

> **Le premier prototype peut être petit, mais ses concepts doivent déjà avoir la bonne signification.**

---

# 340. Example

Acceptable :

```text
single-node
```

Not acceptable :

```text
Job = current thread callback
```

si cela détruit le modèle durable.

---

# 341. Roadmap Artifacts

Chaque lot majeur peut produire un document court :

```text
LOT-XX_IMPLEMENTATION_PLAN.md
```

---

# 342. Content

```text
Context

Goal

Changes

Files

Tests

Acceptance

Deferred items
```

---

# 343. End-of-lot report

Optional :

```text
LOT-XX_COMPLETION_REPORT.md
```

---

# 344. Useful for learning objective

Permet de documenter :

```text
what was learned

what changed from design

what remains uncertain
```

---

# 345. Architecture Decision Records

Créer ADR seulement pour décisions réellement structurantes.

Exemples :

```text
ADR-001 Interval fixed-rate semantics

ADR-002 OccurrenceKey composition

ADR-003 Schedule/Execution aggregate split

ADR-004 No pickle

ADR-005 Outbox delivery model
```

---

# 346. Avoid ADR explosion

Pas un ADR pour chaque classe.

---

# 347. Documentation Reconciliation

Lorsqu’une implémentation force une modification de conception :

```text
code and docs must be reconciled
```

---

# 348. Do not let docs become historical fiction.

---

# 349. Roadmap Acceptance by Milestone

## M1 — In-Memory Scheduler

Required :

```text
Interval Trigger

Schedule

Occurrence

Request

Execution

Attempt

run_pending

virtual clock
```

---

# 350. M1 tests

```text
T-TIME core

T-TRG interval

T-SCH lifecycle subset

T-E2E-001/002
```

---

# 351. M2 — Full In-Memory Domain

Required :

```text
Cron

Misfire

Catch-Up

Concurrency

Retry

Runtime
```

---

# 352. M3 — Local Framework

Required :

```text
Public API

Testing Toolkit

Errors

Security codecs
```

---

# 353. M4 — Durable Scheduler

Required :

```text
SQLite

restart recovery
```

---

# 354. M5 — Crash-Safe Scheduler

Required :

```text
PostgreSQL

Outbox

fault injection

audit
```

---

# 355. M6 — Distributed Scheduler

Required :

```text
multi-worker

distributed concurrency

multi-scheduler claims
```

---

# 356. M7 — Advanced Distributed Ownership

Required :

```text
leases

fencing

leader-only tasks

distributed recovery
```

---

# 357. M8 — Stable Release

Required :

```text
compatibility

security

performance

migration

docs
```

---

# 358. Suggested Version Map

One possible release line:

```text
0.1.0a1 — Time + IntervalTrigger

0.1.0a2 — Schedule + Occurrence

0.1.0a3 — InMemory SchedulerEngine

0.1.0b1 — Execution lifecycle + run_pending

0.2.0a1 — Date/Cron

0.2.0a2 — Misfire/Catch-Up

0.2.0b1 — Concurrency/Retry

0.3.0a1 — SchedulerRuntime

0.3.0b1 — Public API

0.4.0a1 — SQLite

0.4.0b1 — Restart Recovery

0.5.0a1 — Observability

0.5.0b1 — PostgreSQL

0.6.0a1 — Outbox

0.6.0b1 — Crash Qualification

0.7.0a1 — Multi-Worker

0.8.0a1 — Multi-Scheduler

0.9.0a1 — Leases/Fencing

1.0.0rc1 — Contract Freeze

1.0.0 — Stable Core
```

---

# 359. Important

Les numéros sont indicatifs.

La vraie progression doit suivre :

```text
capability maturity
```

et non :

```text
calendar dates
```

---

# 360. Release Freeze Criteria

Avant 1.0 :

```text
Public API

Persisted Schemas

Error Codes

Event Contracts
```

doivent être explicitement revus.

---

# 361. Things that should NOT freeze too early

```text
internal class layout

private repository helpers

internal planner structure

thread implementation
```

---

# 362. Compatibility surface

Freeze :

```text
public imports

documented public behavior

persisted formats

public error codes
```

---

# 363. Internal freedom

Preserve :

```text
refactoring ability
```

---

# 364. Test Mapping per Lot

Chaque lot référence les IDs du document 27.

Exemple :

```text
LOT-16 Retry

required:
T-RET-001
T-RET-002
...
T-RET-015
T-E2E-009
T-E2E-010
```

---

# 365. No vague DoD

Éviter :

```text
"retry works"
```

---

# 366. Prefer

```text
max_attempts includes initial attempt

same ExecutionId across retry

AttemptNumber increments

deadline stops retry

last Failure preserved
```

---

# 367. Roadmap Governance

À tout moment, on doit pouvoir répondre :

```text
Current lot

Current milestone

Qualification level

Remaining blockers

Deferred features
```

---

# 368. Recommended tracking file

Future :

```text
ROADMAP_STATUS.md
```

---

# 369. Fields

```text
Lot

Status

PR

Version

Qualification

Tests Green

Known Gaps
```

---

# 370. Status values

```text
PLANNED

IN_PROGRESS

IMPLEMENTED

QUALIFIED

MERGED

RELEASED
```

---

# 371. Important distinction

```text
IMPLEMENTED
≠
QUALIFIED
```

---

# 372. Example

A LeaseManager may be :

```text
IMPLEMENTED
```

mais tant que :

```text
T-DIST-020 → 027
```

ne passent pas :

```text
not QUALIFIED
```

---

# 373. Release Evidence

Pour chaque release :

```text
commit SHA

version

test report

feature matrix
```

---

# 374. Framework learning journal

Comme le projet a aussi un objectif pédagogique, on peut produire :

```text
IMPLEMENTATION_LEARNINGS.md
```

par milestone.

---

# 375. Exemple M1

Documenter :

```text
why Trigger != Schedule

why Clock is explicit

why run_pending is useful
```

---

# 376. M5

Documenter :

```text
why DB transaction isn't enough for external dispatch

why Outbox exists

why unknown commit matters
```

---

# 377. M7

Documenter :

```text
why lease != lock

why fencing exists

why leader election doesn't solve duplicates
```

---

# 378. This aligns directly with original goal

PyScheduleKit existe d’abord pour :

```text
comprendre le scheduling
```

en le construisant.

---

# 379. Recommended First Implementation Sprint

Commencer par seulement :

```text
LOT-00
LOT-01
LOT-02
LOT-03
```

---

# 380. Why?

Après ces quatre lots, on possède :

```text
project skeleton

time model

Trigger abstraction

working IntervalTrigger
```

---

# 381. Second Sprint

```text
LOT-05
LOT-06
LOT-07
```

---

# 382. Result

```text
Schedule

Occurrence

Persistence boundary
```

---

# 383. Third Sprint

```text
LOT-08
LOT-09
LOT-10
LOT-11
```

---

# 384. Result

Premier :

```text
end-to-end scheduler
```

---

# 385. Cron can be introduced either before or after M1

Recommendation :

```text
after first E2E
```

---

# 386. Revised practical sequence

Même si les lots sont numérotés conceptuellement :

```text
00
01
02
03
05
06
07
08
09
10
11
04
12...
```

peut être un meilleur ordre d’exécution réel.

---

# 387. Why defer LOT-04 Cron?

Pour ne pas bloquer le premier end-to-end sur :

```text
DST

DOM/DOW

cron parser complexity
```

---

# 388. Thus roadmap has two views

```text
Logical Documentation Order

Implementation Critical Path
```

---

# 389. Critical Implementation Path

```text
00
↓
01
↓
02
↓
03 Interval
↓
05 Schedule
↓
06 Occurrence
↓
07 InMemory
↓
08 SchedulerEngine
↓
09 Execution
↓
10 Executor
↓
11 run_pending
```

---

# 390. Then branch

```text
Cron

Runtime

Policies

Public API
```

---

# 391. This is the recommended real start.

---

# 392. Acceptance of Roadmap Itself

Cette roadmap est considérée cohérente si :

```text
a useful scheduler appears early

domain semantics precede infrastructure

persistence precedes distribution

outbox precedes distributed delivery

observability precedes complex distributed debugging

row claims precede leases

leases precede fencing tests

leader election is last, not first

every lot maps to executable acceptance criteria
```

---

# 393. Core Implementation Principles

```text
1.
Build vertical slices.

2.
Keep domain pure.

3.
Use virtual time from day one.

4.
Implement IntervalTrigger before Cron complexity.

5.
Reach run_pending() early.

6.
Do not start persistence before in-memory semantics work.

7.
Do not start distribution before crash-safe persistence works.

8.
Do not use Leader Election as a shortcut.

9.
Do not freeze public API before real usage.

10.
Every lot ends in tests.
```

---

# 394. Roadmap Invariants

```text
1.
No lot may introduce hidden wall-clock access.

2.
No repository may commit internally.

3.
No external side effect occurs before durable intent
once persistence is enabled.

4.
No distributed feature may bypass stable identity.

5.
No security relaxation is introduced only for convenience.

6.
No experimental feature becomes public stable
without qualification tests.

7.
Documentation and implementation are reconciled
at each milestone.

8.
Every persisted format is versioned before release.

9.
Every public error has stable semantic classification.

10.
Every announced guarantee maps to tests.
```

---

# 395. Final Target Architecture Evolution

```text
STEP 1
Pure Domain
    │
    ▼
STEP 2
In-Memory Scheduler
    │
    ▼
STEP 3
Local Runtime
    │
    ▼
STEP 4
Durable Scheduler
    │
    ▼
STEP 5
Crash-Safe Scheduler
    │
    ▼
STEP 6
Multi-Worker Runtime
    │
    ▼
STEP 7
Multi-Scheduler Runtime
    │
    ▼
STEP 8
Lease / Fenced Distributed Runtime
```

---

# 396. End-State

À terme :

```text
                           TIME
                            │
                            ▼
                    SchedulerRuntime
                            │
                            ▼
                     SchedulerEngine
                            │
                            ▼
                        Schedule
                            │
                            ▼
                       Occurrence
                            │
                            ▼
                 SchedulingDecision
                            │
                            ▼
                  ExecutionRequest
                            │
                            ▼
                        Outbox
                            │
                            ▼
                  Execution Runtime
                            │
                            ▼
                       Execution
                            │
                            ▼
                         Attempt
                            │
                            ▼
                        Executor
                            │
                            ▼
                         Target
```

avec autour :

```text
Persistence

Transactions

Concurrency

Retries

Audit

Metrics

Tracing

Claims

Leases

Fencing
```

---

# 397. Mais le premier prototype reste

```text
Clock
  │
  ▼
IntervalTrigger
  │
  ▼
Schedule
  │
  ▼
run_pending()
  │
  ▼
Callable
```

---

# 398. C’est volontaire

Le chemin d’apprentissage doit être :

```text
simple model
→
stronger guarantees
```

et non :

```text
distributed complexity
→
try to discover the domain afterward
```

---

# 399. First Commit Philosophy

Le premier commit utile ne devrait pas essayer de construire :

```text
all 35 lots
```

Il devrait permettre de dire :

> **Je sais représenter le temps et calculer la prochaine occurrence d’un intervalle de manière déterministe.**

---

# 400. First Major Milestone Philosophy

Puis :

> **Je sais transformer une règle temporelle en une exécution observable sans dépendre du temps réel.**

---

# 401. Persistent Milestone Philosophy

Puis :

> **Je peux arrêter le programme et reprendre sans perdre ce que le scheduler savait.**

---

# 402. Crash-Safe Milestone Philosophy

Puis :

> **Même un crash au pire moment ne me fait pas avancer le checkpoint sans conserver l’intention d’exécution correspondante.**

---

# 403. Distributed Milestone Philosophy

Enfin :

> **Plusieurs nœuds peuvent observer le même travail sans compromettre l’identité logique ni les invariants du scheduler.**

---

# 404. Definition finale de la roadmap

> **La roadmap PyScheduleKit construit d’abord la signification correcte du scheduling, puis ajoute progressivement les mécanismes nécessaires pour préserver cette signification face au temps réel, aux pannes, à la persistance et enfin à la concurrence distribuée.**

---

# 405. Recommandation de démarrage effective

Le premier lot d’implémentation à ouvrir après cette documentation devrait être :

```text
LOT-00 — Repository & Packaging Foundation
```

puis immédiatement :

```text
LOT-01 — Time Model
```

et :

```text
LOT-02/03 — Trigger Foundations + IntervalTrigger
```

avant tout travail sur :

```text
Cron

PostgreSQL

Outbox

Leases

Leader Election
```

---

# 406. Premier objectif exécutable

La toute première cible concrète est :

```text
MutableClock
    │
    ▼
IntervalTrigger(10m)
    │
    ▼
Schedule
    │
    ▼
advance clock
    │
    ▼
run_pending()
    │
    ▼
exactly one successful local Execution
```

---

# 407. Ce scénario devient le premier fil rouge

Toutes les phases futures doivent préserver le même comportement :

```text
InMemory

SQLite

PostgreSQL

single node

multi node
```

---

# 408. Le backend change

Mais :

```text
la signification de l'Occurrence
```

ne change pas.

---

# 409. Le runtime change

Mais :

```text
le Trigger
```

ne change pas.

---

# 410. La coordination change

Mais :

```text
OccurrenceKey
```

reste la même identité logique.

---

# 411. C’est le critère ultime de réussite architecturale

> **Pouvoir renforcer les garanties opérationnelles sans réécrire la signification métier du scheduling.**

---

# Conclusion

Cette roadmap transforme les documents précédents en chemin de réalisation concret.

Le projet passe progressivement de :

```text
concepts
```

à :

```text
pure domain
```

puis :

```text
functional scheduler
```

puis :

```text
persistent scheduler
```

puis :

```text
crash-safe scheduler
```

et enfin :

```text
distributed scheduler
```

La trajectoire recommandée est :

```text
Time
  ↓
Trigger
  ↓
Schedule
  ↓
Occurrence
  ↓
SchedulerEngine
  ↓
Execution
  ↓
run_pending
  ↓
Runtime
  ↓
Policies
  ↓
Public API
  ↓
Persistence
  ↓
Outbox
  ↓
Recovery
  ↓
Distribution
```

Le principe final reste :

> **Commencer par prouver la sémantique la plus simple possible, puis ajouter une seule nouvelle classe de difficulté à la fois.**

Ainsi, PyScheduleKit peut atteindre très tôt une première version réellement exécutable sans sacrifier l’ambition long terme définie dans les documents d’architecture.

Le meilleur prochain mouvement n’est donc plus de produire une nouvelle couche théorique majeure.

Il est de commencer :

```text
LOT-00
↓
LOT-01
↓
LOT-02
↓
LOT-03
```

puis d’atteindre le plus vite possible :

```text
M1 — IN-MEMORY SCHEDULER
```

avec comme première preuve :

```text
virtual time
+
IntervalTrigger
+
Schedule
+
Occurrence
+
Execution
+
run_pending()
=
green end-to-end test
```