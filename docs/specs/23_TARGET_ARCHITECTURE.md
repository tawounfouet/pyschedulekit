# PyScheduleKit — Target Architecture

**Document :** `23_TARGET_ARCHITECTURE.md`  
**Projet :** PyScheduleKit  
**Statut :** Architecture cible de référence  
**Nature :** Software Architecture — Domain / Application / Ports / Runtime / Infrastructure  
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

---

# 1. Objectif

Ce document définit l’architecture cible de PyScheduleKit.

Nous avons déjà étudié :

```text
le domaine

les objets

les règles temporelles

les occurrences

les politiques de recovery

la concurrence

les retries

le lifecycle d'exécution

le runtime

la persistance

la coordination distribuée

l'observabilité
```

Il faut maintenant répondre à :

> **Comment organiser le code et les dépendances afin que ces concepts restent cohérents, testables, extensibles et indépendants des choix d’infrastructure ?**

---

# 2. Principe architectural principal

PyScheduleKit doit être conçu selon une architecture :

```text
Domain-Centric
+
Ports & Adapters
+
Application Services
+
Explicit Runtime
```

On peut la représenter ainsi :

```text
┌────────────────────────────────────────────┐
│               PUBLIC API                   │
│                                            │
│ Scheduler · Schedule · Trigger · Policies │
└───────────────────┬────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────┐
│            APPLICATION LAYER               │
│                                            │
│ SchedulerEngine                            │
│ ScheduleService                            │
│ ExecutionService                           │
│ OccurrencePlanner                          │
│ CatchUpPlanner                             │
│ RetryEvaluator                             │
└───────────────────┬────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────┐
│               DOMAIN CORE                  │
│                                            │
│ Schedule · Trigger · Occurrence            │
│ Execution · Attempt                        │
│ Policies · Value Objects · Events          │
└───────────────────┬────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────┐
│                  PORTS                     │
│                                            │
│ Clock · Repositories · Executor            │
│ LeaseManager · Outbox · Telemetry          │
└───────────────────┬────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────┐
│             INFRASTRUCTURE                 │
│                                            │
│ Memory · SQLite · PostgreSQL               │
│ Threading · AsyncIO · OpenTelemetry        │
└────────────────────────────────────────────┘
```

---

# 3. Objectif de séparation

L’architecture doit garantir que :

```text
Cron parsing
```

ne dépende pas de :

```text
PostgreSQL
```

que :

```text
RetryPolicy
```

ne dépende pas de :

```text
Celery
```

et que :

```text
Execution
```

ne dépende pas de :

```text
SQLAlchemy
```

---

# 4. Dependency Rule

La règle principale :

```text
Infrastructure
    ↓
Application
    ↓
Domain
```

Le domaine ne dépend jamais de l’infrastructure.

---

# 5. Direction autorisée

```text
infrastructure
→ ports
→ application
→ domain
```

---

# 6. Direction interdite

```text
domain
→ sqlalchemy
```

interdit.

```text
domain
→ redis
```

interdit.

```text
trigger
→ celery
```

interdit.

---

# 7. Architecture hexagonale

PyScheduleKit se prête naturellement à :

```text
Ports & Adapters
```

car il doit pouvoir changer :

```text
Clock

Storage

Executor

Coordination

Telemetry
```

sans modifier le cœur métier.

---

# 8. Les quatre couches principales

L’architecture cible possède :

```text
domain

application

ports

infrastructure
```

avec une couche supplémentaire :

```text
api
```

pour l’expérience développeur.

---

# 9. Layer — Domain

Le package :

```text
pyschedulekit.domain
```

contient :

```text
Entities

Value Objects

Aggregates

Policies

Domain Services

Domain Events

Domain Errors
```

---

# 10. Ce que Domain ne contient pas

Jamais :

```text
SQL

HTTP

threads

asyncio

logging vendor

filesystem

environment variables
```

---

# 11. Domaine principal

Organisation possible :

```text
domain/
├── scheduling/
├── execution/
├── time/
├── policies/
├── events/
└── errors/
```

---

# 12. `domain/time`

Contient :

```text
Instant

Duration

Timezone

TimeWindow

GracePeriod
```

éventuellement :

```text
CalendarRef
```

---

# 13. `Clock` n'est pas nécessairement dans domain

`Clock` est plutôt :

```text
Port
```

car il représente une dépendance vers le monde extérieur.

---

# 14. `domain/scheduling`

Contient :

```text
Schedule

ScheduleDefinition

ScheduleId

ScheduleRevision

ScheduleState

TargetRef

Occurrence

OccurrenceKey

NextRunTime
```

---

# 15. Trigger package

```text
domain/scheduling/triggers/
```

avec :

```text
Trigger

DateTrigger

IntervalTrigger

CronTrigger

CronExpression
```

---

# 16. Trigger comme Behavioral Value Object

Les Triggers restent :

```text
immutable

stateless

deterministic
```

---

# 17. Trigger interface conceptuelle

```python
class Trigger(Protocol):
    def next_after(self, reference: Instant) -> Instant | None: ...
```

---

# 18. But timezone context

Pour Cron, une signature plus riche peut être nécessaire.

---

# 19. Final Trigger contract

Une option robuste :

```text
Trigger.next_after(
    reference,
    temporal_context
)
```

---

# 20. TemporalContext

Peut contenir :

```text
Timezone

DSTResolutionPolicy
```

---

# 21. Mais éviter context object énorme

Si Trigger spécifique connaît déjà ses paramètres, il peut rester simple.

---

# 22. Recommandation

V1 :

```text
DateTrigger
```

et :

```text
IntervalTrigger
```

retournent directement des Instants.

`CronTrigger` contient :

```text
CronExpression
Timezone
DST policy
```

dans sa configuration immuable.

---

# 23. `domain/policies`

Contient :

```text
MisfirePolicy

CatchUpPolicy

CoalescingPolicy

ConcurrencyPolicy

RetryPolicy

BackoffPolicy

TimeoutPolicy
```

---

# 24. Policies must stay pure

Une Policy ne doit pas appeler :

```text
database

HTTP

Clock.now()
```

implicitement.

---

# 25. Inputs explicit

Exemple :

```text
RetryPolicy
+
Failure
+
AttemptNumber
+
now
→ RetryDecision
```

---

# 26. `domain/execution`

Contient :

```text
ExecutionRequest

Execution

Attempt

ExecutionState

AttemptState

ExecutionResult

AttemptResult

Failure
```

---

# 27. Aggregate Root

Architecture cible :

```text
Schedule
=
Aggregate Root
```

et :

```text
Execution
=
Aggregate Root
```

---

# 28. ExecutionRequest

Reste :

```text
durable command-like Entity
```

entre :

```text
Scheduling
```

et :

```text
Execution Runtime
```

---

# 29. Domain services

Certains calculs n’appartiennent à aucune Entity seule.

---

# 30. OccurrencePlanner

Responsable de :

```text
Trigger
+
Calendar
+
ScheduleWindow
→ valid occurrence
```

---

# 31. CatchUpPlanner

Responsable de :

```text
historical occurrences
+
MisfirePolicy
+
CatchUpPolicy
→ RecoveryPlan
```

---

# 32. ConcurrencyEvaluator

Responsable de :

```text
ConcurrencyPolicy
+
ActiveExecutionSnapshot
→ AdmissionDecision
```

---

# 33. RetryEvaluator

Responsable de :

```text
RetryPolicy
+
Failure
+
Attempt history
→ RetryDecision
```

---

# 34. Ces services doivent être presque purs

Idéalement :

```text
same input
→ same output
```

---

# 35. Layer — Application

Le package :

```text
pyschedulekit.application
```

orchestre les use cases.

---

# 36. Application services possibles

```text
ScheduleService

SchedulerEngine

ExecutionService

RuntimeReconciler

InspectionService
```

---

# 37. ScheduleService

Use cases :

```text
create schedule

pause schedule

resume schedule

reschedule schedule

cancel schedule
```

---

# 38. SchedulerEngine

Use cases :

```text
evaluate due schedules

materialize requests

advance schedule
```

---

# 39. ExecutionService

Use cases :

```text
admit request

create execution

start attempt

complete attempt

schedule retry

cancel execution
```

---

# 40. RuntimeReconciler

Use cases :

```text
reconcile stale attempts

recover overdue retries

repair known operational inconsistencies
```

---

# 41. InspectionService

Future :

```text
inspect schedule

explain occurrence

inspect execution

runtime diagnostics
```

---

# 42. Application Layer knows Ports

Il dépend de contrats comme :

```text
ScheduleRepository

ExecutionRepository

Clock

Executor

UnitOfWork
```

---

# 43. Application does not know implementations

Exemple :

```text
ExecutionService
```

connaît :

```text
Executor
```

pas :

```text
CeleryExecutor
```

---

# 44. Layer — Ports

Le package :

```text
pyschedulekit.ports
```

définit les dépendances externes.

---

# 45. Time Ports

```text
Clock

MonotonicClock
```

---

# 46. Persistence Ports

```text
ScheduleRepository

ExecutionRequestRepository

ExecutionRepository

UnitOfWork
```

---

# 47. Query Ports

```text
ExecutionQueryPort

TimerQueryPort
```

---

# 48. Execution Ports

```text
Executor

ExecutorRouter
```

---

# 49. Coordination Ports

```text
ConcurrencyCoordinator

LeaseManager

LeaderElectionPort
```

---

# 50. Messaging Ports

```text
OutboxRepository

EventPublisher
```

---

# 51. Observability Ports

Potentiellement :

```text
AuditSink

Tracer
```

mais à utiliser avec parcimonie.

---

# 52. Logger

Peut utiliser directement :

```text
Python logging API
```

au niveau infrastructure/application.

Pas forcément besoin de Port personnalisé.

---

# 53. MetricsRecorder

Un petit port peut être utile.

---

# 54. Mais éviter `ObservabilityService`

qui deviendrait :

```text
god abstraction
```

---

# 55. Layer — Infrastructure

Le package :

```text
pyschedulekit.infrastructure
```

contient les adapters.

---

# 56. Persistence adapters

```text
Memory

SQLite

PostgreSQL
```

---

# 57. SQLAlchemy

Peut servir d’implémentation :

```text
SQLAlchemyScheduleRepository

SQLAlchemyExecutionRepository

SQLAlchemyUnitOfWork
```

---

# 58. Domain does not import SQLAlchemy

---

# 59. Time adapters

```text
SystemClock

SystemMonotonicClock

FixedClock

MutableClock
```

---

# 60. FixedClock

Peut être placé dans :

```text
testing
```

plutôt que infrastructure production.

---

# 61. Executor adapters

Exemples :

```text
CallableExecutor

ThreadPoolExecutorAdapter

ProcessExecutor

HttpExecutor

WorkflowExecutorAdapter
```

---

# 62. Py*Kit adapters

Exemples :

```text
PyWorkflowKitExecutor

PyIngestKitExecutor

PyTransformKitExecutor
```

---

# 63. Important

Ils restent dans :

```text
integration adapters
```

pas dans Domain.

---

# 64. Coordination adapters

```text
InMemoryConcurrencyCoordinator

SqlConcurrencyCoordinator

SqlLeaseManager
```

---

# 65. Leader adapters

Future :

```text
PostgresLeaderElection

KubernetesLeaseLeaderElection
```

---

# 66. Observability adapters

```text
LoggingAuditSink

SqlAuditRepository

OpenTelemetryTracer

PrometheusMetricsAdapter
```

---

# 67. Runtime infrastructure

```text
ThreadedSchedulerRuntime

AsyncSchedulerRuntime
```

future.

---

# 68. Public API Layer

Le package public :

```text
pyschedulekit
```

doit masquer le maximum de complexité interne.

---

# 69. Public Developer Experience

Un développeur devrait pouvoir écrire :

```python
scheduler = Scheduler()

scheduler.add_schedule(
    target=my_task,
    trigger=CronTrigger("0 6 * * *"),
)

scheduler.start()
```

---

# 70. Et ne pas devoir manipuler

```text
OccurrencePlanner

UnitOfWork

Outbox

PersistenceVersion

FencingToken
```

pour un usage simple.

---

# 71. Progressive Disclosure

Principe essentiel :

```text
simple use case
→ simple API

advanced use case
→ advanced controls
```

---

# 72. Example simple API

```python
scheduler.add_schedule(
    target=send_report,
    trigger=CronTrigger("0 6 * * *"),
)
```

---

# 73. Advanced API

```python
scheduler.add_schedule(
    target=TargetRef.python("app.tasks:send_report"),
    trigger=CronTrigger(
        expression="0 6 * * *",
        timezone="Europe/Paris",
    ),
    misfire_policy=MisfirePolicy.catch_up(max_occurrences=2),
    concurrency_policy=ConcurrencyPolicy.limit(
        max_instances=1,
        overflow="queue",
    ),
    retry_policy=RetryPolicy.exponential(
        max_attempts=3,
        initial_delay="5s",
    ),
)
```

---

# 74. Public API must not expose persistence details by default

A user should not need:

```text
ScheduleRecord

ExecutionRecord
```

---

# 75. Schedule Handle

`add_schedule()` may return :

```text
Schedule
```

ou :

```text
ScheduleHandle
```

---

# 76. Trade-off

Returning Aggregate directly can expose too much.

---

# 77. Recommendation

Public API can return immutable:

```text
ScheduleHandle
```

with:

```text
id
pause()
resume()
cancel()
reschedule()
```

---

# 78. Internally

Commands passent par :

```text
ScheduleService
```

---

# 79. Scheduler facade

La classe :

```text
Scheduler
```

agit comme :

```text
Facade
```

---

# 80. SchedulerFacade responsibilities

```text
configuration

dependency wiring

public commands

runtime lifecycle
```

---

# 81. Scheduler is not Domain SchedulerEngine

Important.

---

# 82. Naming collision

On a :

```text
Scheduler
```

public facade.

Et :

```text
SchedulerEngine
```

application service.

---

# 83. Clear distinction

```text
Scheduler
→ developer-facing facade

SchedulerEngine
→ internal evaluation engine
```

---

# 84. Dependency Injection

PyScheduleKit doit permettre :

```text
inject Clock

inject repositories

inject Executor

inject Runtime
```

---

# 85. Mais offrir des defaults

Pour usage local :

```text
Scheduler()
```

peut créer :

```text
SystemClock

InMemoryStore

CallableExecutor

ThreadedRuntime
```

---

# 86. Local default mode

Excellent pour :

```text
learning

tests

scripts

small applications
```

---

# 87. Persistent local mode

Possible :

```python
Scheduler.sqlite("scheduler.db")
```

ou config équivalente.

---

# 88. Production mode

Composition explicite :

```text
PostgreSQL persistence

Outbox

distributed worker executor

telemetry
```

---

# 89. Composition Root

Toute création d'implémentations concrètes doit être centralisée.

---

# 90. Composition Root possible

```text
pyschedulekit.bootstrap
```

---

# 91. Responsibilities

```text
load config

instantiate adapters

wire services

construct Scheduler facade
```

---

# 92. Domain must never build adapters

---

# 93. Configuration model

Une architecture cible doit distinguer :

```text
Schedule Configuration

Runtime Configuration

Infrastructure Configuration
```

---

# 94. Schedule Configuration

Fait partie du modèle métier :

```text
Trigger

Timezone

Policies

TargetRef
```

---

# 95. Runtime Configuration

```text
poll interval

batch sizes

runtime backoff

shutdown timeout
```

---

# 96. Infrastructure Configuration

```text
database URL

pool size

broker endpoint

telemetry endpoint
```

---

# 97. Do not mix

Éviter un objet :

```text
SchedulerConfig
```

de 200 paramètres non structurés.

---

# 98. Better

```text
RuntimeConfig

PersistenceConfig

ObservabilityConfig

ExecutorConfig
```

---

# 99. Secrets

Infrastructure config may reference:

```text
SecretRef
```

but core objects do not store raw secrets.

---

# 100. Environment Variables

Read only in:

```text
bootstrap/config adapter
```

---

# 101. Domain does not call `os.getenv`

---

# 102. Runtime Architecture

Target runtime should separate:

```text
Scheduling Runtime

Execution Runtime
```

---

# 103. Scheduling Runtime

```text
SchedulerRuntime
      │
      ▼
SchedulerEngine
```

---

# 104. Execution Runtime

```text
ExecutionWorkerRuntime
      │
      ▼
ExecutionService
      │
      ▼
Executor
```

---

# 105. Single-process mode

Both can live in:

```text
same process
```

---

# 106. Distributed mode

They can become:

```text
separate processes
```

without modifying domain concepts.

---

# 107. This is a major architectural goal

---

# 108. Single-process architecture

```text
Application Process
│
├── SchedulerRuntime
│   └── SchedulerEngine
│
└── ExecutionRuntime
    └── Executor
```

---

# 109. Distributed architecture

```text
Scheduler Process(es)
│
└── SchedulerEngine
        │
        ▼
      DB/Outbox
        │
        ▼
Broker / Queue
        │
        ▼
Worker Process(es)
│
└── ExecutionRuntime
```

---

# 110. Domain unchanged

This is the point.

---

# 111. SchedulerEngine interfaces

Possible dependencies:

```text
Clock

UnitOfWorkFactory

OccurrencePlanner

CatchUpPlanner

ConcurrencyEvaluator

ConcurrencyCoordinator

EventRecorder
```

---

# 112. Keep constructor explicit

Avoid global service locator.

---

# 113. No singleton dependency registry

---

# 114. ExecutionService dependencies

```text
Clock

UnitOfWorkFactory

RetryEvaluator

ExecutorRouter

EventRecorder
```

---

# 115. Executor invocation placement

ExecutionService may orchestrate:

```text
claim

persist Attempt RUNNING

commit

invoke Executor
```

---

# 116. But long-running target call should not occur under UoW transaction

---

# 117. Therefore application flow may split

```text
prepare_attempt()

execute()

complete_attempt()
```

---

# 118. `prepare_attempt()`

Transaction:

```text
claim execution
create Attempt RUNNING
commit
```

---

# 119. `execute()`

Outside transaction.

---

# 120. `complete_attempt()`

New transaction.

---

# 121. Excellent architecture for workers

---

# 122. Request Dispatch

Similarly :

```text
materialize request
commit
```

then :

```text
publish
```

---

# 123. Via Outbox

Prefer:

```text
materialize request + outbox
```

same transaction.

---

# 124. OutboxPublisher separate component

---

# 125. OutboxPublisher architecture

```text
OutboxPublisher
│
├── OutboxRepository
├── MessagePublisher
└── Runtime Backoff
```

---

# 126. Not SchedulerEngine responsibility

---

# 127. Runtime components

Target architecture may include :

```text
SchedulerRuntime

ExecutionWorkerRuntime

OutboxPublisherRuntime

ReconciliationRuntime
```

---

# 128. Must we run four processes?

No.

These are :

```text
logical components
```

---

# 129. In local mode

Can be grouped.

---

# 130. In production

Can scale independently.

---

# 131. ReconciliationRuntime

Potential separate runtime for:

```text
stale Attempts

expired leases

broken ownership
```

---

# 132. V1

Can run reconciliation inside startup or scheduler loop.

---

# 133. Keep abstraction future-friendly.

---

# 134. Internal Commands

Application use cases can use commands:

```text
CreateSchedule

PauseSchedule

ResumeSchedule

RescheduleSchedule

CancelSchedule

CancelExecution
```

---

# 135. Do we need full CQRS command bus?

No.

---

# 136. Recommendation

Plain application methods initially.

---

# 137. Command objects only where useful for:

```text
validation

audit

external API
```

---

# 138. Query Side

Read models can expose:

```text
ScheduleView

ExecutionView

AttemptView

RuntimeHealthView
```

---

# 139. Domain aggregates should not be used as UI DTOs

---

# 140. Why?

UI needs differ:

```text
joined data

formatted timestamps

history

diagnostics
```

---

# 141. Application Query Services

Possible:

```text
ScheduleQueryService

ExecutionQueryService

DiagnosticQueryService
```

---

# 142. V1

Can stay small.

---

# 143. Event architecture

Domain events originate from:

```text
Aggregate transitions
```

---

# 144. Application events can represent:

```text
scheduling decisions

runtime events
```

---

# 145. Outbox turns them into integration events

---

# 146. Three levels

```text
Domain Event

Application/Internal Event

Integration Event
```

---

# 147. Do not conflate them

---

# 148. Example

Domain:

```text
ExecutionCompleted
```

---

# 149. Application may transform to integration:

```text
pyschedule.execution.completed.v1
```

---

# 150. External consumers do not need full internal Aggregate representation.

---

# 151. Event Mapper

Can transform:

```text
DomainEvent
→ IntegrationEvent
```

---

# 152. Security boundary

Critical before external publication.

---

# 153. Serialization architecture

Need dedicated:

```text
Codecs
```

for:

```text
Trigger

Policies

TargetRef

Events

ExecutionContext
```

---

# 154. Codecs location

```text
infrastructure/serialization
```

or:

```text
serialization/
```

near Ports.

---

# 155. Domain serialization independence

Domain objects should not implement giant:

```text
to_json()
```

knowing persistence schema.

---

# 156. But small semantic serialization may be acceptable

Example:

```text
CronExpression.value
```

---

# 157. PersistenceCodec

Maps :

```text
Domain VO
↔
serialized contract
```

---

# 158. Versioned codecs

Required.

---

# 159. Trigger Registry

A registry can map:

```text
"date" → DateTriggerCodec

"interval" → IntervalTriggerCodec

"cron" → CronTriggerCodec
```

---

# 160. Registry must be safe

No arbitrary dynamic import from persisted strings.

---

# 161. Plugin Architecture

Future PyScheduleKit may allow :

```text
custom Trigger

custom Executor

custom Calendar
```

---

# 162. But not arbitrary plugin loading V1

---

# 163. Extension points

Explicit registration:

```text
register_trigger_codec()

register_executor()

register_calendar_provider()
```

---

# 164. Extension points must be narrow

Avoid:

```text
hook_everything()
```

---

# 165. Stable extension boundaries

Most important:

```text
Trigger

Executor

CalendarProvider

PersistenceAdapter

TelemetryAdapter
```

---

# 166. Custom Trigger risk

A Trigger must obey invariants:

```text
deterministic

strict progression

serializable

bounded evaluation
```

---

# 167. Trigger Conformance Tests

Future extension API should require:

```text
next_after > reference

round-trip serialization

no hidden Clock

finite search guarantees
```

---

# 168. Executor Conformance Tests

Should verify:

```text
TargetRef resolution

AttemptResult normalization

idempotency propagation

cancellation capabilities
```

---

# 169. Persistence Adapter Conformance

As document 19:

```text
transactions

uniqueness

optimistic locking

round-trip
```

---

# 170. Ports should be minimal

Bad:

```text
ScheduleRepository
with 37 methods
```

---

# 171. Better

Split:

```text
ScheduleRepository

ScheduleQueryPort
```

---

# 172. Command/query separation without full CQRS

---

# 173. Domain package dependencies

Target dependency graph:

```text
domain.time
      │
      ▼
domain.scheduling
      │
      ├──────────┐
      ▼          ▼
domain.policies domain.execution
```

---

# 174. Avoid cycles

For example :

```text
execution
→ scheduling
→ execution
```

would be undesirable.

---

# 175. Use lightweight refs

Execution can contain:

```text
OccurrenceKey
```

rather than whole Schedule object.

---

# 176. Schedule does not contain Executions

Important Aggregate boundary.

---

# 177. Schedule Aggregate

Owns:

```text
its definition

lifecycle

next_run_time
```

---

# 178. Execution Aggregate

Owns:

```text
attempt lifecycle

retry state

terminal result
```

---

# 179. Communication through IDs/events/application

Not direct object graph.

---

# 180. ScheduleDefinition

Architecture:

```text
Schedule
│
├── ScheduleId
├── ScheduleDefinition
├── ScheduleState
├── ScheduleRevision
├── PersistenceVersion
└── NextRunTime
```

---

# 181. ScheduleDefinition

Immutable VO containing:

```text
TargetRef

Trigger

CalendarRef

ScheduleWindow

MisfirePolicy

ConcurrencyPolicy

RetryPolicy?

JitterPolicy
```

---

# 182. RetryPolicy placement question

Retry operates after Execution starts.

---

# 183. Recommended

ScheduleDefinition may define the default :

```text
ExecutionPolicy
```

snapshot into ExecutionRequest.

---

# 184. Better model

Split:

```text
SchedulingPolicySet
```

and:

```text
ExecutionPolicySet
```

---

# 185. SchedulingPolicySet

Contains:

```text
MisfirePolicy

CatchUpPolicy

ConcurrencyPolicy

ScheduleJitterPolicy
```

---

# 186. ExecutionPolicySet

Contains:

```text
RetryPolicy

AttemptTimeout

ExecutionDeadlinePolicy
```

---

# 187. This separation improves architecture

---

# 188. ScheduleDefinition becomes

```text
ScheduleDefinition
│
├── TargetRef
├── Trigger
├── Timezone
├── CalendarRef
├── ScheduleWindow
├── SchedulingPolicySet
└── ExecutionPolicySet
```

---

# 189. ExecutionRequest snapshots

Only:

```text
ExecutionPolicySet
```

plus required execution context.

---

# 190. Excellent boundary

Scheduling-only policies remain behind.

---

# 191. ExecutionRequest

Target architecture:

```text
ExecutionRequest
│
├── RequestId
├── OccurrenceSource
├── TargetRef
├── ExecutionPolicySnapshot
├── ExecutionContext
├── State
└── CreatedAt
```

---

# 192. OccurrenceSource

Could be:

```text
SingleOccurrence

CoalescedOccurrences
```

---

# 193. V1

Use:

```text
primary OccurrenceKey

optional coalesced keys
```

---

# 194. Execution Aggregate

```text
Execution
│
├── ExecutionId
├── RequestId
├── State
├── ExecutionPolicySnapshot
├── Attempts
├── NextAttemptAt
├── Result
├── Deadline
└── PersistenceVersion
```

---

# 195. Attempt

```text
Attempt
│
├── AttemptId
├── AttemptNumber
├── State
├── StartedAt
├── FinishedAt
└── AttemptResult
```

---

# 196. Value Objects should be frozen

Where possible:

```text
@dataclass(frozen=True)
```

---

# 197. Entities mutable through methods

Example:

```text
Schedule.pause()

Execution.schedule_retry()
```

---

# 198. No generic setters

---

# 199. Error architecture

Three broad categories :

```text
Domain Errors

Application Errors

Infrastructure Errors
```

---

# 200. Domain Errors

Examples :

```text
InvalidScheduleTransition

InvalidTrigger

InvalidRetryPolicy

RetryNotDue
```

---

# 201. Application Errors

```text
ScheduleNotFound

ExecutionNotFound

OperationConflict
```

---

# 202. Infrastructure Errors

```text
PersistenceUnavailable

CoordinationUnavailable

ExecutorUnavailable
```

---

# 203. No giant exception hierarchy initially

Keep meaningful.

---

# 204. Failure ≠ Exception

Important.

---

# 205. `Failure`

Is a domain/runtime value representing:

```text
work failure outcome
```

---

# 206. Exception

Represents:

```text
program/control failure
```

---

# 207. Example

HTTP 500 from target can become:

```text
Failure(
    category=DEPENDENCY,
    retryable=True
)
```

not necessarily propagate raw exception.

---

# 208. Boundary normalization

Infrastructure adapter catches concrete exception and returns:

```text
AttemptResult
```

or normalized Failure.

---

# 209. Security architecture

Target architecture must avoid :

```text
arbitrary code deserialization

pickle

unsafe dynamic imports

secret persistence
```

---

# 210. `TargetRef`

Should use explicit schemas.

---

# 211. Python Target example

```text
python://myapp.tasks/send_report
```

or structured equivalent.

---

# 212. Resolution allowlist

A Python executor may restrict:

```text
permitted modules
```

in secure environments.

---

# 213. Remote Targets

HTTP target should reference:

```text
connection profile
```

rather than storing raw credentials.

---

# 214. SecretProvider

Future port:

```text
SecretProvider
```

if needed.

---

# 215. But not essential to scheduling domain.

---

# 216. Calendar architecture

`CalendarProvider` port resolves:

```text
CalendarRef
→ Calendar
```

---

# 217. Calendar objects may be:

```text
static

versioned

external
```

---

# 218. V1 built-in

Possible:

```text
AlwaysCalendar

WeekdayCalendar

CompositeCalendar
```

---

# 219. Business calendars later.

---

# 220. Timezone architecture

Use standard :

```text
zoneinfo.ZoneInfo
```

through domain wrapper where useful.

---

# 221. Do not invent timezone database.

---

# 222. Cron architecture

Cron parser can be:

```text
internal
```

or use library adapter.

---

# 223. But public semantics must be PyScheduleKit semantics

Do not let a dependency silently determine:

```text
DOM/DOW behavior

DST policy

field count
```

---

# 224. Wrap dependency

If a third-party cron parser is used:

```text
CronExpression
→ parser adapter
```

with explicit tests.

---

# 225. Runtime architecture — V1

Recommended first concrete implementation:

```text
single process

synchronous scheduler loop

threaded worker executor

in-memory repository

fixed polling
```

---

# 226. Why?

Maximum learning value.

---

# 227. V1.1

Add:

```text
SQLite persistence

restart recovery

structured logs
```

---

# 228. V1.2

Add:

```text
SQLAlchemy persistence abstraction

PostgreSQL adapter

Outbox
```

---

# 229. V1.3

Add:

```text
multi-worker execution

atomic claims
```

---

# 230. V2

Add:

```text
multi-scheduler nodes

distributed concurrency

leases

fencing
```

---

# 231. Async support

Should not be foundational V1.

---

# 232. Why?

Async adds:

```text
event loop

cancellation semantics

async DB

async executor
```

before the domain needs it.

---

# 233. Target architecture should allow it

Through ports that can later have async counterparts.

---

# 234. Sync/Async strategy

Possible future:

```text
pyschedulekit
```

sync.

Then:

```text
pyschedulekit.asyncio
```

for async runtime.

---

# 235. Avoid mixing sync and async methods in same Protocol initially

---

# 236. Public API remains conceptually aligned

---

# 237. Threading model

Scheduler loop itself:

```text
one thread
```

V1.

---

# 238. Workers

Can use:

```text
ThreadPoolExecutor
```

for basic concurrent execution.

---

# 239. CPU-bound targets

Users may choose:

```text
ProcessPoolExecutorAdapter
```

later.

---

# 240. Distributed executors

Can bypass local pool.

---

# 241. Scheduler remains executor-agnostic.

---

# 242. Resource scheduling

Out of scope.

PyScheduleKit does not choose:

```text
CPU allocation

GPU scheduling

memory allocation
```

---

# 243. Worker count

Infrastructure setting.

---

# 244. ConcurrencyPolicy

Business logical setting.

---

# 245. Keep distinction.

---

# 246. Architecture around `Job`

Earlier documents kept `Job` optional.

---

# 247. Target architecture recommendation

Do not require `Job` as core V1 Entity.

---

# 248. Why?

Most use cases can use:

```text
TargetRef
+
Schedule
```

directly.

---

# 249. Job can later become

```text
reusable Target configuration
```

if real needs appear.

---

# 250. Thus core chain V1

```text
TargetRef
   ↓
Schedule
   ↓
Occurrence
   ↓
ExecutionRequest
   ↓
Execution
   ↓
Attempt
```

---

# 251. Job optional layer

Future:

```text
Job
→ reusable TargetRef + default ExecutionPolicy
```

---

# 252. Avoid premature abstraction.

---

# 253. Package target overview

```text
src/
└── pyschedulekit/
    ├── __init__.py
    │
    ├── api/
    │   ├── scheduler.py
    │   ├── handles.py
    │   └── builders.py
    │
    ├── domain/
    │   ├── time/
    │   ├── scheduling/
    │   │   ├── schedule.py
    │   │   ├── occurrence.py
    │   │   └── triggers/
    │   ├── execution/
    │   ├── policies/
    │   ├── events/
    │   └── errors/
    │
    ├── application/
    │   ├── schedule_service.py
    │   ├── scheduler_engine.py
    │   ├── execution_service.py
    │   ├── planners/
    │   ├── reconciliation/
    │   └── diagnostics/
    │
    ├── ports/
    │   ├── time.py
    │   ├── persistence.py
    │   ├── execution.py
    │   ├── coordination.py
    │   └── observability.py
    │
    ├── runtime/
    │   ├── scheduler_runtime.py
    │   ├── execution_runtime.py
    │   ├── wakeup.py
    │   └── health.py
    │
    ├── infrastructure/
    │   ├── persistence/
    │   │   ├── memory/
    │   │   ├── sqlite/
    │   │   └── sqlalchemy/
    │   ├── executors/
    │   ├── coordination/
    │   ├── observability/
    │   └── time/
    │
    ├── serialization/
    │   ├── triggers.py
    │   ├── policies.py
    │   └── events.py
    │
    ├── config/
    │
    └── testing/
```

---

# 254. Is this final filesystem layout?

Non.

C'est :

```text
target module topology
```

---

# 255. Important

Architecture should be driven by responsibilities, not desire to create many directories.

---

# 256. Early implementation may collapse packages

Example:

```text
domain/time.py
```

instead of directory.

---

# 257. Promote modules only when size justifies.

---

# 258. Dependency rules

Target static rule:

```text
domain
```

can depend only on :

```text
Python stdlib

small pure dependencies
```

---

# 259. `application`

depends on:

```text
domain

ports
```

---

# 260. `runtime`

depends on:

```text
application

ports

runtime primitives
```

---

# 261. `infrastructure`

depends on:

```text
domain

ports

application contracts when needed
```

---

# 262. `api`

depends on:

```text
application

domain public types
runtime facade
```

---

# 263. Forbidden dependency

```text
domain → application
```

---

# 264. Forbidden dependency

```text
domain → infrastructure
```

---

# 265. Forbidden dependency

```text
application → infrastructure concrete module
```

except composition/bootstrap.

---

# 266. Bootstrap

May import everything.

That's its purpose.

---

# 267. Architecture tests

Use a dependency checker later.

Could verify:

```text
domain cannot import sqlalchemy
```

---

# 268. Package boundary tests

Very useful.

---

# 269. No circular dependencies

Particularly:

```text
policies

execution

scheduling
```

---

# 270. Shared kernel

Need minimal shared primitives.

Possible:

```text
domain.common
```

with:

```text
IDs

Result helpers?

DomainEvent base?
```

---

# 271. Avoid `common.py` dumping ground

---

# 272. Better

Specific modules:

```text
identifiers.py

events.py
```

---

# 273. IDs

Could use generic:

```text
UUID-backed Value Objects
```

---

# 274. Example

```text
ScheduleId

RequestId

ExecutionId

AttemptId
```

---

# 275. Do not use raw strings everywhere

Strong types reduce mixing.

---

# 276. But runtime overhead minimal.

---

# 277. Persistence adapters map them to:

```text
UUID

TEXT
```

---

# 278. Dataclasses

Good fit for many VOs.

---

# 279. Entities

Can use regular classes/dataclasses with methods.

---

# 280. Pydantic?

Possible at API/config boundaries.

---

# 281. But avoid making Pydantic core domain dependency unless useful.

---

# 282. Recommendation

```text
dataclasses
```

for domain.

```text
Pydantic optional
```

for public config/API serialization later.

---

# 283. Why?

Domain invariants should not be hidden in framework magic.

---

# 284. Type system

Heavy use of:

```text
Protocol

Enum

dataclass

NewType/value wrappers
```

is suitable.

---

# 285. Python versions

Target likely:

```text
Python 3.11+
```

or a later supported baseline.

---

# 286. Exact version should be decided at implementation/release planning.

---

# 287. No hard dependency decisions yet

Target architecture should not lock:

```text
SQLAlchemy

Pydantic

APScheduler-like cron parser
```

before implementation spike.

---

# 288. Dependency evaluation criteria

Each external library must be evaluated on:

```text
semantic fit

maintenance

compatibility

dependency weight

security

escape hatch
```

---

# 289. Framework philosophy

PyScheduleKit should remain:

```text
small core

optional adapters
```

---

# 290. Installation extras

Future:

```text
pyschedulekit[sqlalchemy]

pyschedulekit[postgres]

pyschedulekit[otel]
```

---

# 291. Core install

Should not pull:

```text
database drivers

telemetry stacks
```

unnecessarily.

---

# 292. Minimal Core

Potential built-in dependencies:

```text
stdlib only
```

at first.

---

# 293. Cron parser exception

Could eventually justify dependency.

---

# 294. But a learning framework may benefit from implementing a constrained parser.

---

# 295. Scope V1 Cron

Five fields:

```text
minute

hour

day-of-month

month

day-of-week
```

---

# 296. No seconds V1

unless intentionally chosen later.

---

# 297. Runtime state stores

In-memory adapter should support same logical contracts as SQL.

---

# 298. Testing architecture

Dedicated package:

```text
pyschedulekit.testing
```

may expose:

```text
FixedClock

MutableClock

InMemorySchedulerHarness

FakeExecutor
```

---

# 299. SchedulerHarness

Very useful pedagogically.

---

# 300. Example

```python
harness = SchedulerHarness(start_at="2026-01-01T08:00:00Z")

harness.add_schedule(...)

harness.advance("1h")

assert harness.executions(...)
```

---

# 301. No real time passing

Excellent learning/testing API.

---

# 302. This could become a flagship feature

Because scheduling is difficult mainly due to:

```text
time
```

---

# 303. Deterministic Simulation

Potential subsystem:

```text
SimulationClock

InMemoryPersistence

FakeExecutor
```

---

# 304. Not part of production runtime

But same core application/domain.

---

# 305. This validates architecture

If same SchedulerEngine works with:

```text
real time
```

and:

```text
simulated time
```

then Clock boundary is healthy.

---

# 306. SchedulerEngine should not know `sleep`

Exactly.

---

# 307. Runtime should not know Cron semantics

Exactly.

---

# 308. Executor should not know MisfirePolicy

Exactly.

---

# 309. Repository should not know Retry decisions

Exactly.

---

# 310. Architecture ownership table

| Concern | Owner |
|---|---|
| Temporal recurrence | Trigger |
| Valid occurrence search | OccurrencePlanner |
| Misfire recovery | CatchUpPlanner / policy |
| Logical concurrency decision | ConcurrencyEvaluator |
| Atomic admission | ConcurrencyCoordinator |
| Schedule lifecycle | Schedule Aggregate |
| Execution lifecycle | Execution Aggregate |
| Retry decision | RetryEvaluator |
| Continuous wake-up | SchedulerRuntime |
| Durable transaction | UnitOfWork |
| External work | Executor |
| Distributed ownership | Lease/claim adapter |
| Explanation | Diagnostic/Inspection services |

---

# 311. This table should guide code reviews

---

# 312. No business logic in CLI

Future CLI should call:

```text
Application Services
```

---

# 313. No business logic in REST API

Same.

---

# 314. No business logic in database adapters

---

# 315. No policy logic in worker queue adapter

---

# 316. API adapters

Future:

```text
CLI

REST

Python API
```

all call same Application Layer.

---

# 317. Primary adapter

The Python API is the main primary adapter.

---

# 318. Secondary adapters

```text
Persistence

Executor

Clock

Telemetry

Coordination
```

---

# 319. Hexagonal view

```text
                    Primary Adapters
                ┌─────────────────────┐
                │ Python API          │
                │ CLI                 │
                │ REST future         │
                └──────────┬──────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Application    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │     Domain      │
                  └────────┬────────┘
                           │
               Secondary Ports
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
      Persistence       Executor        Coordination
```

---

# 320. Public API design principle

Public API should expose concepts users understand:

```text
Schedule

Trigger

Policy

Scheduler
```

not infrastructure internals.

---

# 321. Advanced users can import lower-level components

But default docs should not start there.

---

# 322. Stable public namespace

Potential:

```python
from pyschedulekit import (
    Scheduler,
    DateTrigger,
    IntervalTrigger,
    CronTrigger,
)
```

---

# 323. Policies

Potential:

```python
from pyschedulekit.policies import (
    MisfirePolicy,
    ConcurrencyPolicy,
    RetryPolicy,
)
```

---

# 324. Advanced runtime

```python
from pyschedulekit.runtime import SchedulerRuntime
```

---

# 325. Internal modules

May be prefixed/documented as internal.

---

# 326. No accidental public API

Avoid exposing every class from root `__init__.py`.

---

# 327. Public API freeze later

Will need explicit compatibility policy.

---

# 328. Architecture around versioning

There are multiple versions:

```text
PackageVersion

ScheduleRevision

PersistenceVersion

EventSchemaVersion

SerializationSchemaVersion
```

---

# 329. Keep names explicit

Never use generic:

```text
version
```

without context in domain code.

---

# 330. PackageVersion

Semantic versioning of library.

---

# 331. ScheduleRevision

Version of ScheduleDefinition.

---

# 332. PersistenceVersion

Optimistic concurrency.

---

# 333. EventSchemaVersion

Event payload format.

---

# 334. CodecSchemaVersion

Persisted configuration format.

---

# 335. Very important distinction

---

# 336. Architecture around Backfill

Manual backfill was kept separate.

---

# 337. Target architecture should eventually introduce:

```text
BackfillService
```

not misuse CatchUpPlanner.

---

# 338. BackfillService

Could generate explicit :

```text
ExecutionRequests
```

for historical occurrence range.

---

# 339. Future ExecutionKind

```text
PRIMARY

RERUN

BACKFILL
```

---

# 340. Not V1 core.

---

# 341. Architecture around Rerun

Manual rerun:

```text
new ExecutionRequest
```

or:

```text
new Execution
```

depending final command model.

---

# 342. Recommendation future

Create explicit:

```text
RerunRequest
```

that results in new Execution identity.

---

# 343. Do not mutate terminal Execution.

---

# 344. Multi-tenancy

Not core V1.

---

# 345. But architecture should allow future:

```text
TenantId
```

on:

```text
Schedule

ExecutionRequest

Execution
```

---

# 346. Avoid global repositories assuming single tenant forever.

---

# 347. But do not add TenantId prematurely without a requirement.

---

# 348. Namespace

A lighter future concept could be:

```text
Namespace
```

for grouping schedules.

---

# 349. Not needed yet.

---

# 350. Architecture around plugins

Potential extension registry should be constructed at bootstrap.

---

# 351. No hidden global registry mutation at import time.

---

# 352. Why?

Global registries hurt:

```text
tests

isolation

multiple Scheduler instances
```

---

# 353. Registry ownership

Each Scheduler instance/composition root can own:

```text
ExecutorRegistry

CodecRegistry
```

---

# 354. This allows separate configurations in same process.

---

# 355. ExecutorRouter

Possible architecture:

```text
TargetRef
   │
   ▼
ExecutorRouter
   │
   ├── python → CallableExecutor
   ├── workflow → PyWorkflowKitAdapter
   └── http → HttpExecutor
```

---

# 356. Router belongs application/infrastructure boundary

---

# 357. Domain only knows TargetRef.

---

# 358. Executor capability model

Future executor may advertise:

```text
supports_cancellation

supports_idempotency_key

supports_external_status
```

---

# 359. Capability VO

Could help avoid assuming all Executors equal.

---

# 360. V1

Keep minimal interface.

---

# 361. Capability expansion later.

---

# 362. Error normalization boundary

Executor adapter returns normalized:

```text
AttemptResult
```

---

# 363. Scheduler core never understands:

```text
requests.Timeout

psycopg.Error

Celery exception
```

directly.

---

# 364. Great boundary.

---

# 365. Persistence mapping architecture

```text
Domain Aggregate
      │
      ▼
Mapper
      │
      ▼
Persistence Record
      │
      ▼
ORM
      │
      ▼
Database
```

---

# 366. ORM model should not leak upward.

---

# 367. UnitOfWorkFactory

Scheduler services usually need new UoW per operation.

---

# 368. Port:

```text
UnitOfWorkFactory
```

can return:

```text
UnitOfWork
```

---

# 369. Why factory?

Avoid one long-lived transaction/session.

---

# 370. Each use case creates short UoW.

---

# 371. Outbox architecture

Persistence adapter may expose:

```text
OutboxRepository
```

inside same UnitOfWork.

---

# 372. Application can stage event.

---

# 373. Publisher separate.

---

# 374. Observability architecture

Critical events:

```text
state + audit/outbox
```

transactional.

---

# 375. Telemetry:

```text
metrics/traces/logs
```

best-effort around application operations.

---

# 376. Architecture and logging

Domain should ideally not log.

---

# 377. Why?

Domain should return:

```text
decisions

events

errors
```

---

# 378. Application logs those outcomes.

---

# 379. Exception

Pure library diagnostics during parsing may still be surfaced through errors, not logging.

---

# 380. Avoid library configuring global logging.

---

# 381. Testing layers

Target test pyramid:

```text
Domain Unit Tests

Application Tests

Port Contract Tests

Infrastructure Integration Tests

Runtime Tests

End-to-End Tests
```

---

# 382. Domain tests

No DB.

No sleeps.

No network.

---

# 383. Application tests

Use:

```text
InMemory UoW

FakeClock

Fake Executor
```

---

# 384. Contract tests

Ensure:

```text
Memory adapter
SQLite adapter
PostgreSQL adapter
```

behave consistently.

---

# 385. Integration tests

Validate:

```text
transactions

locks

concurrency

Outbox
```

---

# 386. Runtime tests

Use virtual time where possible.

---

# 387. E2E tests

Actual scheduler process:

```text
Schedule
→ Occurrence
→ Execution
```

---

# 388. Distributed E2E

Later:

```text
2 schedulers
2 workers
same DB
```

---

# 389. Architecture Fitness Functions

Possible CI checks:

```text
domain has no infrastructure imports

no SQLAlchemy imports outside infrastructure

no datetime.now outside Clock adapters

no time.sleep outside runtime adapters
```

---

# 390. Excellent guards

---

# 391. Search rule

In source:

```text
datetime.now(
```

should appear only in:

```text
SystemClock
```

or controlled infrastructure.

---

# 392. Same for:

```text
time.sleep
```

---

# 393. Same for:

```text
os.getenv
```

only config/bootstrap.

---

# 394. Same for network clients

Only infrastructure adapters.

---

# 395. This architecture is highly auditable

---

# 396. Performance architecture

Optimization should happen mainly in:

```text
Query Ports

Persistence Adapters

Runtime batching
```

---

# 397. Avoid contaminating Domain with cache logic.

---

# 398. Example

Domain computes next occurrence.

Repository query optimizes candidate Schedule selection.

---

# 399. Bulk scheduling

Later :

```text
evaluate 100 schedules
```

can still call pure planners.

---

# 400. Batch persistence

Can be optimized infrastructure-side if semantics maintained.

---

# 401. Caching Triggers

Cron parsing can be cached.

---

# 402. But cached object immutable.

---

# 403. Cache loss harmless.

---

# 404. Availability architecture

Single-node V1:

```text
restart recovery
```

provides durability.

---

# 405. Multi-node later:

```text
claims
leases
```

provide high availability.

---

# 406. Same domain.

---

# 407. Deployment topologies

Architecture should support at least three.

---

# 408. Topology A — Embedded

```text
Application
│
└── PyScheduleKit
    ├── SchedulerRuntime
    └── Local Executor
```

---

# 409. Great for

```text
scripts

desktop apps

small services
```

---

# 410. Topology B — Persistent Service

```text
Application
│
├── PyScheduleKit SchedulerRuntime
├── SQL DB
└── Worker Pool
```

---

# 411. Topology C — Distributed

```text
Scheduler Nodes
      │
      ▼
Shared DB / Outbox
      │
      ▼
Workers
```

---

# 412. Public API should not assume topology.

---

# 413. Architecture around shutdown

Runtime owns:

```text
start

stop
```

---

# 414. Scheduler facade delegates.

---

# 415. Context Manager

Public API could support:

```python
with Scheduler() as scheduler:
    ...
```

---

# 416. But lifecycle semantics must be clear.

---

# 417. `start()` should not silently spawn unbounded threads.

---

# 418. Configuration should expose runtime mode.

---

# 419. Builder versus constructor

Could use:

```text
SchedulerBuilder
```

for advanced wiring.

---

# 420. Example

```python
scheduler = SchedulerBuilder().with_postgres(...).with_executor(...).with_metrics(...).build()
```

---

# 421. But avoid Java-style verbosity for simple use.

---

# 422. Recommended

Simple:

```python
Scheduler()
```

Advanced:

```python
Scheduler.create(
    persistence=...,
    executor=...,
    runtime=...,
)
```

---

# 423. `ScheduleBuilder`

May be useful for complex definitions.

---

# 424. But keyword API may already be readable.

---

# 425. Public API document will decide later.

---

# 426. Architecture around validation

Validation happens at several layers.

---

# 427. Domain validation

Example:

```text
interval > 0
```

---

# 428. API validation

Example:

```text
string timezone parses correctly
```

---

# 429. Persistence validation

Example:

```text
schema_version supported
```

---

# 430. Infrastructure validation

Example:

```text
DB connection works
```

---

# 431. Do not duplicate domain rules inconsistently.

---

# 432. Domain remains final semantic authority.

---

# 433. Architecture around time parsing

Public API may accept:

```text
datetime

timedelta

str
```

---

# 434. Normalize immediately

Into:

```text
Instant

Duration

Timezone
```

---

# 435. Domain internals should not juggle many representations.

---

# 436. `datetime` policy

All Instants:

```text
timezone-aware
```

---

# 437. Naive datetime

Reject by default.

---

# 438. This should be enforced at public boundary.

---

# 439. Architecture around enums

Public enums can expose stable semantic values.

---

# 440. Persisted strings should be independent of enum class name where possible.

---

# 441. Example

```text
ExecutionState.RETRY_WAIT
```

serialized as:

```text
"retry_wait"
```

---

# 442. Compatibility manageable.

---

# 443. Architecture around event schemas

Integration events should use DTOs distinct from domain event objects if public.

---

# 444. Prevent domain refactor breaking external event consumer.

---

# 445. Architecture around version evolution

A major guiding rule:

> **The internal architecture may evolve faster than persisted and public contracts.**

---

# 446. Therefore freeze slowly.

---

# 447. Internal classes

Can remain private until semantics mature.

---

# 448. Root package only exports intentional public concepts.

---

# 449. Architecture maturity stages

```text
Stage 1
Domain model

Stage 2
Application services

Stage 3
In-memory runtime

Stage 4
Persistent runtime

Stage 5
Distributed runtime

Stage 6
Public compatibility freeze
```

---

# 450. We are currently conceptually between Stage 1 and Stage 2

The documentation has mapped the domain; implementation can now begin carefully.

---

# 451. Architecture non-goals

PyScheduleKit target architecture does not aim to become:

```text
workflow engine

distributed message broker

resource scheduler

Kubernetes replacement

data pipeline engine

cron daemon replacement at OS level

full Celery replacement
```

---

# 452. It focuses on:

```text
temporal scheduling

durable execution intent

execution lifecycle integration
```

---

# 453. PyWorkflowKit boundary

```text
PyScheduleKit
→ WHEN
```

---

# 454. PyWorkflowKit

```text
→ WHAT NEXT
```

---

# 455. PyIngestKit

```text
→ HOW TO ACQUIRE
```

---

# 456. PyTransformKit

```text
→ HOW TO TRANSFORM
```

---

# 457. Integration

Through:

```text
TargetRef

ExecutionContext

CorrelationId

Executor Adapters
```

---

# 458. No direct domain imports across kits

Prefer stable adapters.

---

# 459. Shared tiny kernel future

Potentially:

```text
CorrelationId

ExecutionContext primitives

ArtifactRef
```

but only if real duplication appears.

---

# 460. Avoid PyCoreKit mega-package prematurely.

---

# 461. Architectural Decision — Domain Purity

**Decision:**

```text
Domain remains infrastructure-free.
```

**Reason:**

```text
testability

portability

clarity

learning value
```

---

# 462. Architectural Decision — Schedule & Execution Separate Aggregates

**Decision:**

```text
Schedule
and
Execution
```

remain separate.

**Reason:**

Different lifecycles and consistency boundaries.

---

# 463. Architectural Decision — Occurrence as VO

**Decision V1:**

```text
Occurrence
```

remains a Value Object.

---

# 464. Persistent identity via:

```text
OccurrenceKey
```

---

# 465. Architectural Decision — Job Optional

**Decision V1:**

No mandatory `Job` aggregate.

---

# 466. Architectural Decision — Explicit Clock

All time-dependent evaluation receives explicit Clock/time input.

---

# 467. Architectural Decision — Runtime Separate from Engine

```text
SchedulerRuntime
≠
SchedulerEngine
```

---

# 468. Architectural Decision — Execution Runtime Separate

Long-running work is outside scheduling loop.

---

# 469. Architectural Decision — UnitOfWork

Transactions are explicit at application layer.

---

# 470. Architectural Decision — Outbox

Reliable external dispatch uses transactional Outbox when persistence adapter supports production durability.

---

# 471. Architectural Decision — Distributed Leaderless First

Multi-node scheduling uses:

```text
claims
versions
uniqueness
```

before introducing global leader election.

---

# 472. Architectural Decision — Observability Derived from Facts

Domain returns decisions/events.

Infrastructure records logs/metrics/traces.

---

# 473. Architectural Decision — Safe Declarative Serialization

No pickle or arbitrary import-based deserialization.

---

# 474. Architectural Decision — Progressive Disclosure

Simple public API hides advanced machinery.

---

# 475. Architectural Decision — Single Sync Core First

V1 synchronous.

Async support later through adapted runtime.

---

# 476. Architecture quality attributes

The target should optimize for:

```text
Correctness

Determinism

Testability

Recoverability

Explainability

Extensibility

Portability
```

---

# 477. Correctness

A Schedule must not silently lose its due occurrence.

---

# 478. Determinism

Same state + same time context should yield same decision.

---

# 479. Testability

Core can be tested without:

```text
real clock

real DB

real network
```

---

# 480. Recoverability

Restart reconstructs state from durable storage.

---

# 481. Explainability

Major decisions have structured evidence.

---

# 482. Extensibility

New adapters do not require rewriting domain.

---

# 483. Portability

Core is not tied to one:

```text
DB

broker

telemetry vendor

execution backend
```

---

# 484. Architecture risks

Main risks:

```text
over-engineering before first prototype

too many abstractions

policy explosion

premature distributed design

public API leaking internals
```

---

# 485. Mitigation

Implement in vertical increments.

---

# 486. First vertical slice

Recommended:

```text
IntervalTrigger

Schedule

InMemoryRepository

SchedulerEngine

FixedClock

CallableExecutor
```

---

# 487. Example behavior

```text
every 10 minutes
→ due occurrence
→ request
→ execution
→ successful attempt
```

---

# 488. Second vertical slice

Add:

```text
DateTrigger

CronTrigger

Timezone
```

---

# 489. Third vertical slice

Add:

```text
Misfire

Catch-Up
```

---

# 490. Fourth

```text
Concurrency
```

---

# 491. Fifth

```text
Retry
```

---

# 492. Sixth

```text
SQLite persistence
```

---

# 493. Seventh

```text
PostgreSQL + Outbox
```

---

# 494. Eighth

```text
multi-worker
```

---

# 495. Ninth

```text
multi-scheduler
```

---

# 496. This is safer than implementing all layers horizontally.

---

# 497. Architecture acceptance criteria

L'architecture cible est cohérente si :

```text
Domain tests need no infrastructure.

SchedulerEngine can use InMemory or SQL persistence
without code changes.

SystemClock can be replaced by FixedClock.

Executor can be replaced without changing Schedule.

SchedulerRuntime can be replaced without changing Trigger.

Persistence can restart without losing semantic state.

Multi-node coordination can be added without rewriting
domain policies.

Logs/metrics/traces can change vendor without changing
domain entities.

PyWorkflowKit can be scheduled through an adapter
without PyScheduleKit knowing workflow internals.

An Execution retry does not require re-evaluating Trigger.

A Schedule reschedule does not mutate existing Execution.

A transaction can fail without external task having been
launched before durable commit.
```

---

# 498. Architecture dependency diagram

```text
                            ┌──────────────┐
                            │  Public API  │
                            └──────┬───────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │   Application    │
                         └───────┬──────────┘
                                 │
                                 ▼
                         ┌──────────────────┐
                         │      Domain      │
                         └──────────────────┘

Application also depends on:

               ┌──────────────────────────────┐
               │            Ports             │
               └──────────────┬───────────────┘
                              ▲
                              │ implements
                              │
               ┌──────────────┴───────────────┐
               │       Infrastructure         │
               └──────────────────────────────┘
```

---

# 499. Runtime topology diagram

```text
                    SchedulerRuntime
                           │
                           ▼
                    SchedulerEngine
                           │
                    ┌──────┴──────┐
                    │             │
                    ▼             ▼
                 Domain          Ports
                                  │
                                  ▼
                            Persistence
                                  │
                                  ▼
                             ExecutionRequest
                                  │
                                  ▼
                              Outbox
                                  │
                                  ▼
                         ExecutionRuntime
                                  │
                                  ▼
                               Executor
```

---

# 500. Distributed target diagram

```text
             ┌───────────────┐
             │ Scheduler A   │
             └───────┬───────┘
                     │
             ┌───────┴───────┐
             │ Scheduler B   │
             └───────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ Shared Store │
              │              │
              │ Schedules    │
              │ Requests     │
              │ Executions   │
              │ Attempts     │
              │ Outbox       │
              └──────┬───────┘
                     │
                     ▼
               Message/Claim
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Worker A       Worker B      Worker C
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                  Targets
```

---

# 501. Hexagonal target diagram

```text
                         PRIMARY SIDE

                    Python API / CLI
                           │
                           ▼
                     ┌──────────┐
                     │   API    │
                     └────┬─────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   APPLICATION   │
                 └───────┬─────────┘
                         │
                         ▼
                 ┌─────────────────┐
                 │     DOMAIN      │
                 └─────────────────┘
                         ▲
                         │
                 ┌───────┴─────────┐
                 │      PORTS      │
                 └───────┬─────────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
   Persistence         Executor       Coordination
       │                 │                 │
       ▼                 ▼                 ▼
 SQLite/Postgres     Local/Remote      DB/Lease
```

---

# 502. Architectural invariant summary

```text
1.
Domain depends on no infrastructure.

2.
Schedule and Execution are separate Aggregates.

3.
Occurrence remains lightweight.

4.
SchedulerEngine never sleeps.

5.
SchedulerRuntime never interprets Cron.

6.
Executor never decides Misfire.

7.
Repositories never commit implicitly.

8.
External execution never occurs before durable intent.

9.
Retry never creates a new Schedule occurrence.

10.
Concurrency decision and atomic concurrency admission
remain distinct.

11.
Distributed ownership remains infrastructure concern.

12.
Telemetry never becomes domain truth.

13.
Public API does not expose persistence records.

14.
Persisted configuration is declarative and safe.

15.
Testing can replace time, persistence and execution.

16.
In-memory optimizations are rebuildable.

17.
Simple use cases remain simple.

18.
Advanced distributed features remain optional.

19.
Py*Kit integration happens through adapters and context.

20.
Architecture evolves by vertical slices.
```

---

# 503. Recommended initial module set

Pour commencer l’implémentation, il n’est pas nécessaire de créer immédiatement toute l’arborescence cible.

Un premier noyau peut être :

```text
pyschedulekit/
├── domain/
│   ├── time.py
│   ├── schedule.py
│   ├── occurrence.py
│   ├── triggers.py
│   ├── policies.py
│   └── execution.py
│
├── application/
│   ├── scheduler_engine.py
│   └── execution_service.py
│
├── ports/
│   ├── clock.py
│   ├── persistence.py
│   └── executor.py
│
├── infrastructure/
│   ├── memory.py
│   ├── system_clock.py
│   └── callable_executor.py
│
├── runtime.py
└── scheduler.py
```

---

# 504. Puis extraire progressivement

Quand un module grossit :

```text
triggers.py
```

devient :

```text
triggers/
├── base.py
├── date.py
├── interval.py
└── cron.py
```

---

# 505. Architecture before folder ceremony

Très important.

---

# 506. Target Architecture versus Initial Architecture

```text
Target Architecture
→ destination structurante

Initial Architecture
→ minimum nécessaire pour apprendre et livrer
```

---

# 507. Les deux ne doivent pas être confondues

Sinon PyScheduleKit pourrait commencer avec :

```text
60 fichiers vides
```

avant le premier Schedule fonctionnel.

---

# 508. Architecture target evolution

```text
Domain Model
   ↓
In-Memory Vertical Slice
   ↓
Persistent Vertical Slice
   ↓
Reliable Dispatch
   ↓
Distributed Execution
   ↓
Distributed Scheduling
```

---

# 509. First architectural milestone

Le premier milestone doit pouvoir exécuter :

```text
FixedClock
   ↓
IntervalTrigger
   ↓
Schedule
   ↓
Occurrence
   ↓
ExecutionRequest
   ↓
Execution
   ↓
Fake/Callable Executor
```

de manière entièrement déterministe.

---

# 510. Second milestone

Même scénario après :

```text
process restart
```

avec persistance.

---

# 511. Third milestone

Même scénario avec :

```text
2 workers
```

sans double Attempt.

---

# 512. Fourth milestone

Même scénario avec :

```text
2 Scheduler nodes
```

sans double occurrence.

---

# 513. Si ces quatre milestones fonctionnent

L’architecture aura démontré :

```text
domain correctness

persistence correctness

execution coordination

distributed scheduling correctness
```

---

# 514. Definition finale de l'architecture cible

> **PyScheduleKit est organisé autour d'un domaine temporel pur, orchestré par des services applicatifs, connecté au monde extérieur par des ports explicites et exécuté par des runtimes remplaçables, de façon à préserver les mêmes invariants du prototype en mémoire jusqu'au déploiement distribué.**

---

# Conclusion

L’architecture cible de PyScheduleKit n’est pas :

```text
une grosse classe Scheduler
```

entourée de callbacks.

Elle repose sur plusieurs responsabilités distinctes :

```text
Domain
→ définit le sens

Application
→ orchestre les use cases

Ports
→ définissent les dépendances externes

Infrastructure
→ implémente les technologies

Runtime
→ maintient les processus vivants

Public API
→ simplifie l'expérience développeur
```

La chaîne principale reste :

```text
Schedule
   │
   ▼
Trigger
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
Execution
   │
   ▼
Attempt
```

mais l’architecture garantit désormais que :

```text
le temps

la persistance

l'exécution

la coordination

l'observabilité
```

restent substituables autour de cette chaîne.

Le principe central est :

> **Les mécanismes techniques peuvent changer ; les invariants métier du scheduling ne doivent pas changer avec eux.**

Ainsi PyScheduleKit peut commencer comme :

```text
un scheduler Python local et pédagogique
```

puis évoluer vers :

```text
un runtime persistant

multi-worker

multi-node

observable

distribué
```

sans abandonner le modèle appris depuis les premiers documents.

---

# Suite documentaire recommandée

Le prochain document naturel est :

```text
24_PUBLIC_API_SPEC.md
```

Il devra figer concrètement :

```text
imports publics

Scheduler facade

add_schedule()

get_schedule()

pause()

resume()

reschedule()

cancel()

run_pending()

start()

shutdown()

DateTrigger API

IntervalTrigger API

CronTrigger API

Policy APIs

TargetRef API

return types

type hints

sync contracts

exceptions publiques
```

Puis :

```text
25_ERROR_MODEL.md
```

pour fixer le contrat d'erreurs public,

```text
26_SECURITY_AND_CONFIGURATION_POLICY.md
```

pour sécuriser TargetRef, sérialisation, configuration et secrets,

```text
27_TEST_MATRIX_AND_ACCEPTANCE_CRITERIA.md
```

pour transformer toute la documentation en preuves exécutables,

et enfin :

```text
28_IMPLEMENTATION_ROADMAP.md
```

pour découper l'implémentation en lots progressifs depuis le premier vertical slice jusqu'au runtime distribué.