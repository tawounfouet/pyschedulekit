# PyScheduleKit — Persistence, Repositories & Transaction Model

**Document :** `19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle de persistance de référence  
**Nature :** Persistence Model — Repositories / Unit of Work / Transactions / Idempotence / Crash Consistency  
**Prérequis :**
- `07_SCHEDULING_ERD.md`
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`
- `14_CONCURRENCY_AND_OVERLAP_MODEL.md`
- `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`
- `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`
- `17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md`
- `18_SCHEDULER_RUNTIME_AND_WAKEUP_MODEL.md`

---

# 1. Objectif

Le modèle PyScheduleKit possède désormais :

```text
Schedule

ScheduleDefinition

Trigger

Occurrence

ExecutionRequest

Execution

Attempt

Retry

NextRunTime

Concurrency

Misfire

Catch-Up
```

Mais ces objets ne sont fiables que si le système sait répondre à :

> **Que se passe-t-il si le process s'arrête exactement entre deux mutations critiques ?**

Exemples :

```text
Occurrence calculée
↓
process crash
↓
request jamais créée
```

ou :

```text
Request créée
↓
process crash
↓
next_run_time jamais avancé
```

ou encore :

```text
Execution envoyée au worker
↓
process crash
↓
transaction locale rollback
```

Le modèle de persistance doit rendre ces scénarios :

```text
récupérables

détectables

idempotents

auditables
```

---

# 2. Principe directeur

Le principe fondamental est :

> **La persistance doit rendre durable l'intention avant tout effet externe irréversible.**

Ainsi :

```text
Decide
↓
Persist
↓
Commit
↓
Publish / Execute
```

et jamais :

```text
Decide
↓
Execute externally
↓
Persist later
```

---

# 3. Source of Truth

Le système possède plusieurs formes d'état :

```text
Domain State

Operational Projection

Audit History

Ephemeral Runtime State
```

Il faut les distinguer.

---

# 4. Domain State

Exemples :

```text
ScheduleDefinition

ScheduleState

ScheduleRevision

ExecutionState

AttemptState
```

Ils représentent la réalité métier/runtime durable.

---

# 5. Operational Projection

Exemples :

```text
next_run_time

next_attempt_at

attempt_count

active_execution_count cache
```

Ces données optimisent le runtime.

Certaines peuvent être :

```text
recalculables
```

---

# 6. Audit History

Exemples :

```text
Schedule events

Execution lifecycle events

Misfire decisions

Retry decisions
```

Ils expliquent :

```text
pourquoi l'état actuel existe
```

---

# 7. Ephemeral Runtime State

Exemples :

```text
timer heap

current batch

thread wake-up signal

in-memory cache

current EvaluationCycle
```

Ils ne sont jamais la source de vérité.

---

# 8. Durability Rule

Tout ce qui est nécessaire pour reconstruire :

```text
la prochaine décision correcte
```

après restart doit être durable.

---

# 9. Données minimales durables

PyScheduleKit doit au minimum préserver :

```text
Schedule

ScheduleDefinition

ScheduleState

ScheduleRevision

PersistenceVersion

next_run_time

ExecutionRequest

Execution

Attempt

next_attempt_at

ExecutionResult
```

---

# 10. Occurrence persistence

Comme vu précédemment, `Occurrence` peut rester :

```text
Value Object
```

et ne pas avoir sa propre table V1.

---

# 11. OccurrenceKey

Même sans table `Occurrence`, son identité naturelle reste :

```text
OccurrenceKey
=
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

---

# 12. Rôle d'OccurrenceKey

Il sert à :

```text
dédupliquer

auditer

corréler

reconstruire le contexte
```

---

# 13. Contrainte essentielle

Pour les ExecutionRequests automatiques :

```text
UNIQUE(
    schedule_id,
    schedule_revision,
    scheduled_at
)
```

ou l'équivalent dérivé de `OccurrenceKey`.

---

# 14. Pourquoi ?

Deux scheduler nodes peuvent tenter simultanément de matérialiser :

```text
la même occurrence
```

La base doit pouvoir dire :

```text
une seule gagne
```

---

# 15. Application-level deduplication ne suffit pas

Ce code :

```text
if not exists:
    insert
```

n'est pas sûr en concurrence.

Deux transactions peuvent lire :

```text
not exists
```

simultanément.

---

# 16. Database uniqueness

Il faut donc préférer :

```text
unique constraint
```

comme dernière ligne de défense.

---

# 17. Stable IDs

Les identités principales sont :

```text
ScheduleId

RequestId

ExecutionId

AttemptId
```

---

# 18. Identity hierarchy

```text
OccurrenceKey
    ↓
ExecutionRequest.RequestId
    ↓
Execution.ExecutionId
    ↓
Attempt.AttemptId
```

---

# 19. Chaque niveau répond à une question différente

```text
OccurrenceKey
→ quelle intention temporelle ?

RequestId
→ quelle commande d'exécution ?

ExecutionId
→ quel run logique ?

AttemptId
→ quelle tentative concrète ?
```

---

# 20. Repository Pattern

Le domaine ne doit pas connaître :

```text
SQLAlchemy

PostgreSQL

SQLite

Redis

DynamoDB
```

Il dépend de :

```text
Repositories
```

---

# 21. Repository

Un Repository représente :

> **Une abstraction de collection persistante d'Aggregates ou Entities majeures.**

---

# 22. Repositories principaux V1

```text
ScheduleRepository

ExecutionRequestRepository

ExecutionRepository
```

---

# 23. AttemptRepository ?

Deux stratégies.

---

# 24. Option A

`Attempt` est enfant de l'Aggregate `Execution`.

Donc :

```text
ExecutionRepository
```

persiste l'Execution et ses Attempts.

---

# 25. Option B

Les Attempts sont nombreuses ou volumineuses.

Donc :

```text
AttemptRepository
```

séparé.

---

# 26. Recommandation V1

Conceptuellement :

```text
Execution = Aggregate Root
Attempt = child Entity
```

Donc :

```text
ExecutionRepository
```

est suffisant.

---

# 27. Mais stockage physique séparé

On peut tout à fait avoir :

```text
executions table

attempts table
```

sans créer deux Repositories métier publics.

---

# 28. Important distinction

```text
Repository boundary
≠
database table boundary
```

---

# 29. ScheduleRepository responsabilités

Il doit permettre notamment :

```text
get

save

find_due_candidates

find_by_id
```

---

# 30. Example conceptual API

```text
get(schedule_id)

save(schedule)

find_due_candidates(now, limit)
```

---

# 31. ScheduleRepository ne doit pas parser Trigger

La sérialisation est une responsabilité :

```text
mapper / codec
```

---

# 32. ExecutionRequestRepository

Responsabilités possibles :

```text
save request

get request

find waiting admissions

find by occurrence key

deduplicate request
```

---

# 33. ExecutionRepository

Responsabilités :

```text
get Execution

save Execution

find queued Executions

find due retries

find active by ConcurrencyKey
```

---

# 34. Query ports versus repositories

Toutes les lectures ne doivent pas nécessairement passer par un Repository d'Aggregate.

---

# 35. Exemple

Pour la concurrence :

```text
ExecutionQueryPort
```

peut être plus adapté que :

```text
ExecutionRepository.find_everything()
```

---

# 36. Pourquoi ?

Le Query Port peut retourner :

```text
projection légère
```

comme :

```text
ActiveExecutionSnapshot
```

---

# 37. CQRS léger

Le modèle peut donc utiliser :

```text
Repositories
→ Aggregate persistence

Query Ports
→ optimized read models
```

sans adopter un CQRS complet.

---

# 38. ScheduleTimerQueryPort

Pour le Runtime :

```text
earliest_next_run_time
```

peut être une query optimisée.

---

# 39. RetryTimerQueryPort

Même chose pour :

```text
earliest_next_attempt_at
```

---

# 40. Unit of Work

Une `UnitOfWork` représente :

> **Une frontière transactionnelle autour d'un ensemble cohérent de mutations.**

---

# 41. Pourquoi nécessaire ?

Le SchedulerEngine peut modifier ensemble :

```text
Schedule

ExecutionRequest

OutboxMessage
```

---

# 42. Ces mutations doivent parfois être atomiques

Exemple :

```text
Occurrence 10:00
→ create request
→ advance next_run_time to 11:00
```

Ces deux opérations doivent rester cohérentes.

---

# 43. UnitOfWork conceptuelle

```text
BEGIN
    load aggregates
    mutate
    persist
    add outbox
COMMIT
```

---

# 44. UnitOfWork responsibilities

```text
begin transaction

provide repositories

commit

rollback
```

---

# 45. Possible API

```python
with unit_of_work as uow:
    schedule = uow.schedules.get(...)
    ...
    uow.commit()
```

Architecture indicative seulement.

---

# 46. No hidden commits

Un Repository ne doit jamais faire :

```text
commit()
```

silencieusement.

---

# 47. Pourquoi ?

Sinon :

```text
schedule.save()
```

pourrait commit avant :

```text
request.save()
```

et casser l'atomicité.

---

# 48. Critical invariant

> **Repositories participate in the caller's transaction.**

---

# 49. No auto-commit Repository

Très important.

---

# 50. One operation = one transaction boundary

Le transaction boundary appartient à :

```text
Application Service / UnitOfWork
```

pas au Repository individuel.

---

# 51. Atomic Schedule Evaluation

Le cas nominal :

```text
Schedule due
```

doit idéalement produire dans une même transaction :

```text
request creation

decision evidence

next_run_time advancement

Schedule persistence version increment

outbox entry
```

---

# 52. Transaction flow

```text
BEGIN

load Schedule

verify current state/version

materialize ExecutionRequest

advance next_run_time

insert audit/outbox

COMMIT
```

---

# 53. Crash before BEGIN

Aucun effet.

---

# 54. Crash during transaction

La DB rollback.

---

# 55. Crash immediately before COMMIT

Rollback.

---

# 56. Crash immediately after COMMIT

L'état est durable.

Le système pourra reprendre.

---

# 57. This is the desired property

---

# 58. Crash consistency

La persistance doit garantir :

> Après un crash, l'état visible correspond à un état cohérent complet, pas à la moitié d'une décision.

---

# 59. Scenario A — checkpoint first

Mauvais ordre :

```text
next_run_time = 11:00
COMMIT

create request for 10:00
```

Crash entre les deux :

```text
10:00 lost
```

---

# 60. Scenario B — request first separate transaction

```text
create request 10:00
COMMIT

advance next_run_time
```

Crash entre les deux :

```text
10:00 request exists
next_run_time still 10:00
```

---

# 61. Scenario B is safer

Parce que la seconde évaluation peut détecter :

```text
request already exists
```

puis avancer le checkpoint.

---

# 62. General rule

Si l'atomicité parfaite n'est pas possible :

```text
prefer duplicates/re-evaluation
over silent loss
```

---

# 63. But ideal remains one transaction

---

# 64. Atomicity scope

La transaction locale peut inclure uniquement :

```text
une même base de données
```

---

# 65. Network calls cannot be part of SQL transaction safely

Exemple :

```text
HTTP call
Kafka publish
Celery send
```

ne doivent pas être considérés comme atomiques avec le commit DB normal.

---

# 66. Dual Write Problem

Supposons :

```text
DB commit
+
Kafka publish
```

---

# 67. Order A

```text
publish
↓
crash
↓
DB rollback
```

Message existe sans état durable.

---

# 68. Order B

```text
DB commit
↓
crash
↓
publish never happens
```

État durable existe mais message absent.

---

# 69. Transactional Outbox

Le pattern Outbox résout cette incohérence pratique.

---

# 70. Principle

Dans la transaction DB :

```text
business state

+

outbox message
```

sont persistés ensemble.

---

# 71. Then

Un publisher séparé lit :

```text
outbox
```

et publie les messages.

---

# 72. Outbox flow

```text
BEGIN
│
├── create ExecutionRequest
├── update Schedule
└── insert OutboxMessage
│
COMMIT
   │
   ▼
OutboxPublisher
   │
   ▼
Executor / Message Broker
```

---

# 73. Crash after commit

L'OutboxMessage reste en DB.

Le publisher pourra l'envoyer plus tard.

---

# 74. Publisher crash after send

Cas :

```text
message delivered
publisher crashes before marking sent
```

---

# 75. On restart

Il peut republier.

---

# 76. Therefore Outbox delivery is usually

```text
at-least-once
```

---

# 77. Consumer deduplication required

Le consumer utilise :

```text
RequestId
```

pour éviter une seconde Execution.

---

# 78. Reliable chain

```text
OccurrenceKey uniqueness

+

Outbox

+

RequestId deduplication
```

forme une chaîne robuste.

---

# 79. OutboxMessage

Infrastructure Entity possible :

```text
message_id

topic/type

payload

created_at

published_at

attempt_count
```

---

# 80. Est-ce un Domain Object ?

Non.

---

# 81. Classification

```text
Infrastructure Persistence Record
```

---

# 82. Outbox belongs outside core domain

---

# 83. Domain Event versus OutboxMessage

Un Domain Event peut devenir :

```text
OutboxMessage
```

mais ce sont deux concepts distincts.

---

# 84. Example

```text
ExecutionRequested [Domain/Application Event]
```

peut être sérialisé comme :

```text
OutboxMessage
```

---

# 85. PersistenceVersion

Nous avons déjà distingué :

```text
ScheduleRevision
```

de :

```text
PersistenceVersion
```

---

# 86. ScheduleRevision

Change lorsque :

```text
ScheduleDefinition
```

change.

---

# 87. PersistenceVersion

Change lors de toute mutation persistée pertinente :

```text
next_run_time advancement

pause

resume

reschedule

operational state update
```

---

# 88. Example

```text
ScheduleRevision = 4
PersistenceVersion = 127
```

---

# 89. Evaluation cycle

Updating only:

```text
next_run_time
```

may produce:

```text
PersistenceVersion = 128
```

while:

```text
ScheduleRevision = 4
```

remains.

---

# 90. Why two versions?

Because they solve different problems.

---

# 91. ScheduleRevision solves

```text
historical scheduling semantics
```

---

# 92. PersistenceVersion solves

```text
concurrent writes
```

---

# 93. Optimistic Locking

Pattern:

```text
UPDATE schedule
SET ...
    version = version + 1
WHERE schedule_id = ?
AND version = expected_version
```

---

# 94. Result

If rows updated:

```text
1
```

success.

If:

```text
0
```

someone changed the Schedule.

---

# 95. Then

Raise or return:

```text
OptimisticConcurrencyConflict
```

---

# 96. Application response

```text
reload

re-evaluate

retry operation if appropriate
```

---

# 97. Important

Optimistic retry here is not:

```text
Execution Retry
```

---

# 98. Better vocabulary

Use:

```text
transaction retry
```

or:

```text
operation re-evaluation
```

---

# 99. Reschedule race

Node A loads:

```text
version 10
revision 3
```

User reschedules.

Now:

```text
version 11
revision 4
```

Node A tries commit with:

```text
expected version 10
```

---

# 100. Commit fails

Correctly.

---

# 101. Without optimistic locking

Node A might overwrite:

```text
new definition / next_run_time
```

with stale data.

---

# 102. Pause race

Same protection.

---

# 103. Concurrent scheduler nodes

Both load version 10.

A commits version 11.

B fails.

---

# 104. Unique OccurrenceKey

Even if lock/version logic fails somehow, duplicate request creation remains protected.

---

# 105. Defense in depth

Recommended:

```text
optimistic locking

+

unique business keys

+

transaction boundaries
```

---

# 106. Pessimistic locking

Alternative:

```text
SELECT FOR UPDATE
```

---

# 107. Advantages

```text
simple serialisation

strong local coordination
```

---

# 108. Disadvantages

```text
lock contention

long waits

DB-specific behavior
```

---

# 109. V1 recommendation

For single-node:

```text
optimistic locking
```

may be enough.

---

# 110. Distributed SQL implementation

Could combine:

```text
FOR UPDATE SKIP LOCKED
```

with uniqueness.

---

# 111. But not domain contract

---

# 112. Repository semantics must remain abstract

For example:

```text
claim_due_schedules()
```

could hide DB-specific locking.

---

# 113. Or separate Claim Port

As discussed earlier.

---

# 114. Persistence mapping

Domain objects should not become ORM models by default.

---

# 115. Why?

An ORM entity often has concerns like:

```text
lazy loading

session lifecycle

DB column nullability

foreign-key navigation
```

that should not define domain semantics.

---

# 116. Recommended separation

```text
Domain Model

Persistence Model

Mapper
```

---

# 117. Example

```text
Schedule
```

domain object mapped to:

```text
ScheduleRecord
```

---

# 118. ScheduleRecord fields

Possible:

```text
schedule_id

state

revision

persistence_version

definition_json

next_run_time

created_at

updated_at
```

---

# 119. Embedded ScheduleDefinition

For V1:

```text
definition_json
```

is reasonable.

---

# 120. Why?

ScheduleDefinition contains:

```text
Trigger

Timezone

CalendarRef

MisfirePolicy

ConcurrencyPolicy

JitterPolicy

TargetRef
```

which are mostly immutable VOs.

---

# 121. Alternative normalized schema

Separate tables for:

```text
trigger

policy

calendar
```

would add complexity without much benefit V1.

---

# 122. Recommendation

Serialize immutable configuration as:

```text
structured JSON
```

with explicit schemas/versioning.

---

# 123. But searchable fields may be extracted

For performance:

```text
state

next_run_time

target_kind

concurrency_key
```

can have dedicated columns.

---

# 124. Hybrid model

```text
typed operational columns
+
definition_json
```

---

# 125. Definition schema version

Example:

```json
{
  "schema_version": 1,
  "target": {...},
  "trigger": {...},
  "timezone": "Europe/Paris",
  "misfire": {...},
  "concurrency": {...}
}
```

---

# 126. Persistence serialization contract

Must be:

```text
stable

versioned

validated

round-trippable
```

---

# 127. Round-trip invariant

```text
DomainObject
→ serialize
→ deserialize
→ semantically equivalent DomainObject
```

---

# 128. Trigger codecs

As defined earlier:

```text
TriggerCodec
```

should own Trigger persistence representation.

---

# 129. Policy codecs

Same idea:

```text
MisfirePolicyCodec

ConcurrencyPolicyCodec

RetryPolicyCodec
```

if needed.

---

# 130. No pickle

Never use:

```text
pickle
```

as durable public persistence format for scheduler definitions.

---

# 131. Why?

Security and compatibility.

---

# 132. No arbitrary Python callable serialization

TargetRef should remain:

```text
declarative
```

---

# 133. TargetRef storage

Example:

```text
kind = "python"

value = "myapp.tasks:daily_report"
```

or:

```text
workflow:daily-orders
```

---

# 134. Executor resolves it later

---

# 135. Request persistence

ExecutionRequest should store a snapshot sufficient to survive Schedule changes.

---

# 136. Candidate fields

```text
request_id

schedule_id

schedule_revision

occurrence_scheduled_at

target_ref

state

execution_context

policy_snapshot

created_at

correlation_id
```

---

# 137. Why store schedule revision?

To explain:

```text
which definition produced this request
```

---

# 138. Why snapshot TargetRef?

Because Schedule may later point elsewhere.

Existing request should not silently change.

---

# 139. Why snapshot policy?

For policies whose semantics continue into Execution:

```text
RetryPolicy

ExecutionDeadline

AttemptTimeout
```

---

# 140. But avoid duplicating unnecessary scheduling policy

Once occurrence is materialized, things like:

```text
CronTrigger
```

need not travel into Execution.

---

# 141. Snapshot only runtime-required semantics

---

# 142. Execution persistence

Possible fields:

```text
execution_id

request_id

state

queued_at

started_at

finished_at

next_attempt_at

deadline

attempt_count

policy_snapshot

result_json

version
```

---

# 143. ExecutionVersion

Can be its own optimistic concurrency counter.

---

# 144. Why separate from Schedule version?

Execution has independent lifecycle.

---

# 145. Attempt persistence

Possible fields:

```text
attempt_id

execution_id

attempt_number

state

started_at

finished_at

failure_json

result_json
```

---

# 146. Unique constraint

```text
UNIQUE(
    execution_id,
    attempt_number
)
```

---

# 147. Request → Execution uniqueness

If one automatic request yields at most one execution:

```text
UNIQUE(request_id)
```

on executions.

---

# 148. Coalescing provenance

ExecutionRequest may store:

```text
primary_occurrence

coalesced_occurrence_keys
```

---

# 149. Serialization format

JSON array may suffice V1.

---

# 150. Historical audit

For large groups, a separate association table may later be preferable.

---

# 151. Waiting admission persistence

Request state:

```text
WAITING_ADMISSION
```

must be durable.

---

# 152. Why?

If process crashes while waiting:

```text
the queue must survive
```

---

# 153. Queue order fields

Store:

```text
scheduled_at

created_at
```

for deterministic FIFO selection.

---

# 154. Query

```text
find_waiting_admissions(
    order_by=scheduled_at,
    limit=N
)
```

---

# 155. Execution queued persistence

Same principle.

---

# 156. Execution QUEUED must survive crash

Otherwise admitted work could disappear.

---

# 157. RetryWait persistence

Must preserve:

```text
next_attempt_at
```

durably.

---

# 158. On restart

Query:

```text
state = RETRY_WAIT
AND next_attempt_at <= now
```

---

# 159. Attempt RUNNING persistence

Important for crash recovery.

---

# 160. Why?

At restart, runtime needs to know:

```text
which attempts may have been interrupted
```

---

# 161. Local process model

RUNNING attempt surviving DB but process gone:

```text
stale
```

---

# 162. Distributed model

Not necessarily stale.

---

# 163. Worker ownership fields future

Could include:

```text
worker_id

lease_id

heartbeat_at
```

---

# 164. But those are operational columns

Not domain identity.

---

# 165. Audit timestamps

All persisted timestamps should be:

```text
timezone-aware Instants
```

---

# 166. Recommended storage

UTC.

---

# 167. But Schedule timezone remains separately stored

For civil-time rules.

---

# 168. Never use naive datetime

---

# 169. Database timezone

Do not rely solely on server session timezone.

---

# 170. Canonical serialization

Prefer:

```text
UTC Instant
```

for operational timestamps.

---

# 171. CalendarRef persistence

Store:

```text
stable reference
```

not a transient object.

---

# 172. Calendar revision future

Could include:

```text
calendar_version
```

if historical reproducibility needed.

---

# 173. Transaction — nominal occurrence

Detailed example.

Initial state:

```text
Schedule
next_run_time = 10:00
version = 42
```

Now:

```text
10:00
```

---

# 174. Transaction steps

```text
BEGIN

load Schedule v42

verify ACTIVE

build OccurrenceKey
(schedule, rev, 10:00)

insert Request
unique occurrence key

calculate next occurrence = 11:00

update Schedule
next_run_time=11:00
version=43
WHERE version=42

insert outbox event

COMMIT
```

---

# 175. Crash before insert

No state change.

---

# 176. Crash after insert before commit

Rollback.

---

# 177. Crash after Schedule update before commit

Rollback all.

---

# 178. Crash after commit before dispatch

Outbox survives.

---

# 179. This is ideal.

---

# 180. Duplicate evaluation

Another node tries same 10:00 occurrence.

---

# 181. Possible outcomes

It sees Schedule already at:

```text
11:00
```

and does nothing.

---

# 182. Or stale race

It attempts same OccurrenceKey.

DB uniqueness rejects duplicate.

---

# 183. Application interpretation

Duplicate occurrence should generally mean:

```text
already materialized
```

not fatal corruption.

---

# 184. Then Schedule advancement?

Careful.

If duplicate request exists but Schedule checkpoint is stale, transaction should reconcile.

---

# 185. Example

Request 10:00 exists.

Schedule still next_run_time=10:00 due to earlier unusual partial system.

---

# 186. Evaluation can

```text
detect request exists

compute next = 11:00

advance Schedule
```

without creating another request.

---

# 187. This is idempotent recovery

---

# 188. Important design

Request repository should support:

```text
find_by_occurrence_key
```

or insert conflict detection.

---

# 189. Upsert?

Could use:

```text
INSERT ... ON CONFLICT DO NOTHING
```

---

# 190. But domain must know whether inserted

Because behavior may differ.

---

# 191. Result

```text
CREATED

ALREADY_EXISTS
```

can be useful.

---

# 192. Repository save semantics

Avoid vague:

```text
save()
```

when create/dedup semantics matter.

---

# 193. Possible explicit method

```text
add_if_absent(request)
```

---

# 194. But avoid infrastructure terms in domain API if possible

---

# 195. Transaction — waiting admission

State:

```text
Request WAITING_ADMISSION
```

Slot available.

---

# 196. Needed atomicity

```text
acquire logical slot

create Execution

mark Request DISPATCHED
```

must be coordinated.

---

# 197. If these live in same DB

Can be transactional.

---

# 198. If concurrency slot lives in external Redis

Atomicity becomes harder.

---

# 199. V1 recommendation

For persistence model:

```text
derive logical concurrency
from durable executions in same DB
```

where possible.

---

# 200. This enables transaction-level correctness

---

# 201. Example

Transaction:

```text
BEGIN

lock concurrency scope

count active executions

if below limit:
    insert Execution QUEUED
    update Request DISPATCHED

COMMIT
```

---

# 202. Cross-Schedule concurrency

Need a lockable resource representing:

```text
ConcurrencyKey
```

---

# 203. ConcurrencyLockRow

Infrastructure pattern possible:

```text
concurrency_key table
```

---

# 204. Or database advisory locks

Implementation-specific.

---

# 205. Domain should not require either

---

# 206. max_instances > 1

Counting active executions within same transaction must be consistent.

---

# 207. Isolation level matters

A simple:

```text
COUNT active
```

under weak isolation may race.

---

# 208. Solutions

```text
lock row for concurrency key

serializable transaction

atomic counter/semaphore
```

---

# 209. V1 single-process

Simpler.

---

# 210. Still model the seam

---

# 211. Transaction — attempt result

Attempt #1 fails.

Need to atomically:

```text
mark Attempt FAILED

update Execution state

set next_attempt_at
```

---

# 212. If retry

Transaction:

```text
BEGIN

load Execution

verify RUNNING/version

mark Attempt failed

set Execution RETRY_WAIT

set next_attempt_at

increment version

insert RetryScheduled event

COMMIT
```

---

# 213. If terminal

```text
mark Attempt FAILED

Execution → FAILED

finished_at

ExecutionResult
```

same transaction.

---

# 214. Why?

Avoid state:

```text
Attempt FAILED

Execution RUNNING
```

after crash.

---

# 215. Transaction — Attempt success

Atomically:

```text
Attempt → SUCCESS

Execution → SUCCESS

result

finished_at

release logical concurrency slot representation
```

---

# 216. Slot release

If active state is derived from ExecutionState:

```text
setting terminal state
```

automatically means it no longer counts.

---

# 217. This is elegant

No separate slot record necessary V1.

---

# 218. Then waiting admissions can query active executions.

---

# 219. Cancellation transaction

Queued Execution:

```text
QUEUED → CANCELLED
```

simple.

---

# 220. Running cancellation

More difficult because external worker exists.

---

# 221. Pattern

Persist:

```text
cancellation requested
```

then send cancel command via Outbox.

---

# 222. This suggests future CANCELLING state

As discussed.

---

# 223. V1 local cancellation

May remain synchronous.

---

# 224. Persistent commands

For external Executors:

```text
ExecutionCommand
```

could be materialized/outboxed.

---

# 225. But not required now.

---

# 226. UnitOfWork and events

Domain objects may accumulate:

```text
domain_events
```

---

# 227. On commit

Application can:

```text
persist aggregates

persist events/outbox

commit
```

---

# 228. Clear events after successful commit

Not before.

---

# 229. Why?

If commit fails, events must not disappear from in-memory retry context unexpectedly.

---

# 230. Event publication after rollback forbidden

---

# 231. UnitOfWork responsibilities may include

```text
collect domain events

serialize them to outbox
```

---

# 232. Or application service explicitly does this

Both possible.

---

# 233. Keep magic limited

For learning-oriented PyScheduleKit:

```text
explicit application flow
```

may be clearer than invisible UoW event collection.

---

# 234. Recommended V1

Use explicit:

```text
uow.outbox.add(...)
```

or application event writer.

---

# 235. Persistence errors

Taxonomy may include:

```text
EntityNotFound

OptimisticConcurrencyConflict

DuplicateOccurrence

DuplicateRequest

PersistenceUnavailable

SerializationError
```

---

# 236. Domain errors versus persistence errors

`DuplicateOccurrence` can be:

```text
expected idempotence outcome
```

rather than exception in some paths.

---

# 237. PersistenceUnavailable

Infrastructure failure.

---

# 238. SerializationError

Could indicate:

```text
corrupted definition

unsupported schema version
```

---

# 239. Fail closed

If ScheduleDefinition cannot be safely deserialized:

```text
do not execute
```

---

# 240. Never guess old configuration

---

# 241. Migration model

Persistent schedules can outlive application versions.

Therefore:

```text
schema migrations
```

are unavoidable.

---

# 242. Two migration layers

```text
Database Schema Migration

Serialized Domain Configuration Migration
```

---

# 243. Example

DB migration:

```text
add next_attempt_at column
```

---

# 244. Domain config migration

```text
trigger schema_version 1
→ version 2
```

---

# 245. Keep distinct

---

# 246. Codec migration

A decoder may support:

```text
v1
v2
```

and normalize to current domain object.

---

# 247. Write current version only

A good policy:

```text
read old compatible versions

write latest version
```

---

# 248. Unsupported future version

If DB contains:

```text
schema_version = 7
```

but runtime supports up to 5:

```text
fail safely
```

---

# 249. No silent downgrade

---

# 250. Persistence-level timestamps

Recommended:

```text
created_at

updated_at
```

for major records.

---

# 251. Are they domain concepts?

Usually not.

They are persistence/audit metadata.

---

# 252. Don't confuse

```text
created_at
```

with:

```text
scheduled_at
```

---

# 253. Important temporal distinction

```text
scheduled_at
→ temporal intent

created_at
→ when DB record was created
```

---

# 254. Request example

```text
scheduled_at = 10:00

created_at = 10:17
```

during catch-up.

---

# 255. Both must be preserved.

---

# 256. Soft delete?

Schedules should generally use lifecycle:

```text
CANCELLED
```

instead of deletion for semantic operations.

---

# 257. Physical deletion

Administrative maintenance only.

---

# 258. Why?

Deleting a Schedule can destroy references used by:

```text
historical executions

audit
```

---

# 259. Foreign key strategy

Should ExecutionRequest have FK to Schedule?

---

# 260. Within same bounded context

Reasonable.

---

# 261. But if historical schedules can be physically deleted

FK may complicate retention.

---

# 262. V1 recommendation

Use FKs where useful, but preserve:

```text
schedule_id
schedule_revision
snapshot
```

in historical records.

---

# 263. Cross-framework foreign keys

Avoid.

---

# 264. Example

Do not create DB FK from:

```text
PyScheduleKit Execution
```

to:

```text
PyWorkflowKit internal table
```

---

# 265. Use

```text
ExternalExecutionRef

TargetRef
```

instead.

---

# 266. Retention

Execution history may grow indefinitely.

---

# 267. Need future RetentionPolicy

Examples:

```text
keep attempts 90 days

keep audit 1 year

archive old executions
```

---

# 268. Not V1 core

But schema should not assume infinite hot storage.

---

# 269. Purging

Must not remove data still needed for:

```text
deduplication
```

too early.

---

# 270. Important

If automatic occurrence uniqueness depends only on historical request rows, deleting them may allow duplicate replay later.

---

# 271. Solutions

```text
retain dedup key longer

separate tombstone table

advance checkpoints safely

retention horizon
```

---

# 272. V1

Do not purge automatic ExecutionRequests.

Simpler.

---

# 273. Archival later

---

# 274. OccurrenceDedupRecord future

Could preserve:

```text
OccurrenceKey
```

without full historical payload.

---

# 275. Data integrity constraints

Useful constraints include:

```text
state valid enum

revision >= 1

version >= 1

attempt_number >= 1

next_attempt_at nullable only when appropriate

scheduled_at not null

request_id unique
```

---

# 276. But DB cannot express every domain invariant

Example:

```text
RETRY_WAIT requires next_attempt_at
```

can be DB CHECK in some systems.

---

# 277. Domain remains primary

Database constraints are defense in depth.

---

# 278. Useful DB CHECK

Example:

```text
if state = RETRY_WAIT
then next_attempt_at is not null
```

---

# 279. Execution terminal result check

Could enforce:

```text
terminal → finished_at NOT NULL
```

---

# 280. But cross-column complexity grows

Use judiciously.

---

# 281. Repository hydration

When loading an Aggregate, invalid persisted state must not be silently accepted.

---

# 282. Example

```text
Execution state = RETRY_WAIT
next_attempt_at = NULL
```

---

# 283. Hydration should fail

With:

```text
CorruptPersistenceState
```

or equivalent.

---

# 284. Never "repair" silently

Unless explicit reconciliation logic exists.

---

# 285. Rehydration path

Two approaches.

---

# 286. Constructor validation

Rebuild object through normal constructor.

---

# 287. Dedicated rehydrate()

Useful for persisted lifecycle state.

---

# 288. Recommendation

Have explicit:

```text
Execution.rehydrate(...)
```

with invariants still checked.

---

# 289. Same for Schedule

---

# 290. Persistence Mapper

Responsibilities:

```text
record → domain

domain → record
```

---

# 291. Mapper does not decide business transitions

---

# 292. Repository does not mutate Aggregate state

It persists what the domain decided.

---

# 293. Query consistency

Do reads need:

```text
strong consistency
```

?

For critical admission/scheduling:

```text
yes, effectively
```

at transaction boundary.

---

# 294. Eventually consistent replicas

May be unsafe for:

```text
concurrency admission

next_run_time mutation
```

---

# 295. Read replicas

Can be used for:

```text
dashboards

analytics

history queries
```

---

# 296. But not authoritative mutation decisions

unless architecture explicitly accounts for lag.

---

# 297. Transaction isolation

V1 need not prescribe a single SQL isolation level.

But it must demand:

```text
correctness under concurrent writers
```

---

# 298. Tools include

```text
optimistic versions

unique constraints

row locks

serializable sections
```

---

# 299. No magical isolation assumption

---

# 300. Connection failures after COMMIT ambiguity

A classic case:

```text
COMMIT sent
connection drops
```

Application may not know whether commit succeeded.

---

# 301. Unknown commit outcome

If it retries blindly:

```text
duplicates possible
```

---

# 302. Stable identifiers help

Retrying same operation with:

```text
same RequestId
same OccurrenceKey
```

makes outcome detectable.

---

# 303. Idempotent transaction commands

This is critical.

---

# 304. Example

If Schedule evaluation operation has stable:

```text
OccurrenceKey
```

then uncertain commit can be resolved by querying:

```text
does request exist?
```

---

# 305. Similarly

Outbox message can have stable:

```text
message_id
```

---

# 306. Transaction idempotency

Important principle:

> **Every transaction that may be retried after an uncertain outcome should have stable business keys allowing the system to determine whether it already succeeded.**

---

# 307. RequestId generation

When?

---

# 308. If generated randomly before transaction

Retry should reuse same value.

---

# 309. But after process crash

Random RequestId may be lost.

---

# 310. OccurrenceKey remains durable natural identity

Therefore request can be rediscovered by OccurrenceKey.

---

# 311. Could RequestId be deterministic?

Possibly derive from:

```text
OccurrenceKey
```

for automatic primary requests.

---

# 312. Example

UUIDv5-like deterministic ID.

---

# 313. Advantage

Natural idempotence.

---

# 314. Disadvantage

Manual reruns/coalescing/backfill complicate derivation.

---

# 315. Recommendation

Keep:

```text
RequestId opaque
```

but enforce unique OccurrenceKey for automatic request.

---

# 316. Manual reruns

Need distinct RequestId even if same OccurrenceKey.

---

# 317. Therefore uniqueness may need scope

For example:

```text
automatic_primary = true
```

unique by OccurrenceKey.

---

# 318. Future ExecutionKind

Could help distinguish:

```text
PRIMARY

RERUN

BACKFILL
```

---

# 319. V1 automatic scheduler

Simple unique OccurrenceKey constraint sufficient.

---

# 320. Coalesced request uniqueness

A request representing several occurrences needs a canonical identity.

---

# 321. Possible primary occurrence

Use:

```text
latest occurrence
```

as primary key plus provenance.

---

# 322. But then skipped/coalesced occurrences may not have their own request rows.

---

# 323. Dedup strategy

CatchUpPlanner should produce deterministic group composition.

---

# 324. Then repeated evaluation creates same coalesced group.

---

# 325. Group fingerprint

Future:

```text
OccurrenceGroupFingerprint
```

could protect coalesced deduplication.

---

# 326. V1

`COALESCE_LATEST` can use latest OccurrenceKey as request natural key.

---

# 327. Skipped occurrences

If no table Occurrence exists, how remember they were skipped?

---

# 328. Options

```text
audit event

advance next_run_time past them

decision log
```

---

# 329. Minimum correctness

Advancing Schedule checkpoint means:

```text
they won't be re-evaluated
```

---

# 330. Auditability

Store:

```text
MisfireBatchProcessed
```

or similar.

---

# 331. Transaction must include

```text
checkpoint advancement
+
skip evidence
```

if audit required.

---

# 332. Otherwise a crash could lose evidence but not semantics.

---

# 333. Acceptable depending audit requirements.

---

# 334. Persistence of ScheduleDefinition history

Do we keep every revision?

---

# 335. V1 options

A. Only current definition.

B. Separate historical revisions.

---

# 336. Current-only

Simpler.

But old ExecutionRequest should snapshot required context.

---

# 337. Historical revision store

Allows:

```text
forensic reconstruction

exact historical catch-up

audit
```

---

# 338. Recommendation

V1 can store current Schedule plus snapshots in requests.

Future:

```text
ScheduleRevisionHistory
```

---

# 339. If exact historical recovery across reschedules required

Revision history becomes important.

---

# 340. For initial learning framework

Not mandatory.

---

# 341. ScheduleRevisionRecord future

```text
schedule_id

revision

definition_json

effective_from

effective_to
```

---

# 342. But this introduces temporal versioning complexity.

---

# 343. Repository boundaries final

```text
ScheduleRepository
→ Schedule Aggregate

ExecutionRequestRepository
→ durable execution intents

ExecutionRepository
→ Execution Aggregate + Attempts
```

---

# 344. Query Ports

```text
ScheduleQueryPort

ExecutionQueryPort

TimerQueryPort
```

can optimize reads.

---

# 345. UnitOfWork final

```text
UnitOfWork
│
├── schedules
├── requests
├── executions
├── outbox
├── commit()
└── rollback()
```

---

# 346. Maybe events/audit

Optional:

```text
audit
```

---

# 347. Repository implementations

Possible:

```text
InMemory

SQLite

PostgreSQL
```

---

# 348. Why InMemory first?

Excellent for:

```text
domain tests

learning

prototype
```

---

# 349. But InMemory must emulate key constraints

Very important.

---

# 350. Example

InMemory request repository should reject duplicate:

```text
OccurrenceKey
```

just like SQL adapter.

---

# 351. Otherwise tests pass but production breaks.

---

# 352. InMemory optimistic locking

Should also model:

```text
PersistenceVersion
```

if concurrency tests rely on it.

---

# 353. Contract tests

Every Repository adapter should pass the same:

```text
Repository Contract Test Suite
```

---

# 354. Example ScheduleRepository contract

```text
save/load round-trip

version conflict

due query ordering

state filtering

next_run_time null handling
```

---

# 355. RequestRepository contract

```text
OccurrenceKey uniqueness

RequestId uniqueness

waiting admission ordering

round-trip
```

---

# 356. ExecutionRepository contract

```text
RequestId uniqueness

Attempt number uniqueness

active query

retry due query

terminal filtering

version conflict
```

---

# 357. Database indexes

Important for runtime performance.

---

# 358. Schedule indexes

```text
(state, next_run_time)
```

---

# 359. Request indexes

```text
(state, scheduled_at)
```

for waiting admissions.

---

# 360. Execution indexes

```text
(state, next_attempt_at)
```

---

# 361. Active concurrency queries

Potential:

```text
(concurrency_key, state)
```

---

# 362. Attempts

```text
(execution_id, attempt_number)
```

unique.

---

# 363. Outbox

```text
(published_at, created_at)
```

---

# 364. Indexes are infrastructure design

But critical enough to document.

---

# 365. Query order determinism

Due schedules:

```text
ORDER BY next_run_time, schedule_id
```

---

# 366. Due retries:

```text
ORDER BY next_attempt_at, execution_id
```

---

# 367. Waiting admission:

```text
ORDER BY scheduled_at, request_id
```

---

# 368. Stable tie-breaker

Always include deterministic secondary key.

---

# 369. Pagination

Offset pagination can be unstable under mutation.

---

# 370. Cursor pagination

May be preferable later.

---

# 371. V1 bounded repeated query

Simpler.

---

# 372. Transaction duration

Keep transactions short.

---

# 373. No Trigger-heavy calculation under long lock?

Interesting trade-off.

---

# 374. Approach A

Lock Schedule then calculate.

Strong consistency but longer locks.

---

# 375. Approach B

Read Schedule.

Compute plan outside transaction.

Re-open transaction.

Check version.

Apply if unchanged.

---

# 376. This matches Plan/Apply architecture

---

# 377. Recommended long-term

```text
READ
↓
PLAN outside transaction
↓
BEGIN
↓
reload/version check
↓
APPLY
↓
COMMIT
```

---

# 378. Benefit

Short transactions.

---

# 379. Risk

Plan becomes stale.

---

# 380. Solved by

```text
expected ScheduleRevision

expected PersistenceVersion
```

---

# 381. Concurrency snapshot also stale

Atomic admission still needs transactional recheck.

---

# 382. So plan may say

```text
request intent requires admission
```

then transaction finalizes capacity.

---

# 383. V1 simpler path

Compute inside transaction if small/local.

---

# 384. But architecture should allow Plan/Apply later.

---

# 385. Transaction Retry

Deadlocks or serialization conflicts can happen.

---

# 386. Application may retry transaction

But must recompute state.

---

# 387. Do not simply re-submit stale mutations

---

# 388. Safe transaction retry

```text
reload

re-plan

re-apply
```

---

# 389. Bounded retries

Runtime transaction retries themselves should be bounded.

---

# 390. Again not Execution RetryPolicy

---

# 391. Database unavailable

Do not create in-memory requests pretending persistence succeeded.

---

# 392. Fail closed

If durable intent cannot be stored:

```text
do not dispatch
```

---

# 393. This is fundamental.

---

# 394. Persistence before execution invariant

```text
No durable request
→ no external dispatch
```

---

# 395. Outbox publisher

Should read committed records only.

---

# 396. Publisher claim

Multiple publishers may run.

Need:

```text
claiming / locking
```

on Outbox rows.

---

# 397. Publisher duplication remains acceptable

Consumer dedup required.

---

# 398. Mark sent after successful publish

---

# 399. Delete immediately?

Better to retain for some audit/retention period or mark published.

---

# 400. V1 outbox state

```text
PENDING

PUBLISHED
```

---

# 401. Outbox retry

Publisher may use its own technical retry/backoff.

---

# 402. Again separate from Execution retry.

---

# 403. Crash consistency matrix

| Crash point | Expected result |
|---|---|
| Before transaction | No change |
| During transaction | Rollback |
| After commit before publish | Outbox recovers |
| After publish before ack | Possible duplicate publish |
| Duplicate publish | Consumer deduplicates |
| After Request insert before next-run update, same TX | Rollback both |
| Version conflict | Re-evaluate |
| Duplicate OccurrenceKey | Treat as already materialized |

---

# 404. This matrix is central

---

# 405. Persistence invariants

```text
1.
Automatic logical occurrence is materialized at most once.

2.
Request identity is unique.

3.
One automatic Request creates at most one Execution.

4.
Attempt numbers are unique within an Execution.

5.
Schedule next_run_time progression and request materialization
remain transactionally coherent.

6.
External dispatch never precedes durable commit.

7.
Repository methods never hide commits.

8.
PersistenceVersion detects stale writes.

9.
ScheduleRevision represents business definition changes only.

10.
Terminal Execution state is persisted atomically
with its final result.

11.
Retry state is persisted atomically
with next_attempt_at.

12.
Durable state is sufficient for restart.

13.
In-memory state can always be discarded.

14.
Unknown commit outcomes are resolvable via stable identities.

15.
Persistence serialization is explicit and versioned.
```

---

# 406. V1 database model recommendation

A compact physical model:

```text
schedules

execution_requests

executions

attempts

outbox_messages
```

---

# 407. `schedules`

```text
schedule_id PK

state

revision

version

definition_json

next_run_time

created_at

updated_at
```

---

# 408. `execution_requests`

```text
request_id PK

schedule_id

schedule_revision

scheduled_at

state

target_ref

context_json

policy_snapshot_json

created_at
```

Constraint:

```text
UNIQUE(
    schedule_id,
    schedule_revision,
    scheduled_at
)
```

for primary automatic requests.

---

# 409. `executions`

```text
execution_id PK

request_id UNIQUE

state

queued_at

started_at

finished_at

next_attempt_at

deadline

attempt_count

policy_snapshot_json

result_json

version
```

---

# 410. `attempts`

```text
attempt_id PK

execution_id

attempt_number

state

started_at

finished_at

failure_json

result_json
```

Constraint:

```text
UNIQUE(
    execution_id,
    attempt_number
)
```

---

# 411. `outbox_messages`

```text
message_id PK

message_type

aggregate_type

aggregate_id

payload_json

created_at

published_at
```

---

# 412. Optional audit table

Future:

```text
scheduler_events
```

---

# 413. Not mandatory for correctness V1.

---

# 414. Database portability

Initial domain should not rely on:

```text
PostgreSQL-specific types
```

unless adapter-specific.

---

# 415. JSON portability

Use codec abstraction.

---

# 416. SQLite value

SQLite is ideal for:

```text
learning

local persistence

single-node tests
```

---

# 417. PostgreSQL value

PostgreSQL becomes more attractive for:

```text
concurrent scheduler nodes

row locking

SKIP LOCKED

JSONB

advisory locks
```

---

# 418. But PyScheduleKit core stays independent.

---

# 419. Persistence Adapter capability

An adapter could expose:

```text
supports_skip_locked

supports_advisory_lock

supports_partial_index
```

if advanced runtime needs it.

---

# 420. Avoid branching domain logic on DB vendor

Capabilities belong application/infrastructure layer.

---

# 421. Isolation testing

Concurrency tests should run against:

```text
real SQL adapter
```

not only InMemory.

---

# 422. Why?

Race conditions are often invisible in fake repositories.

---

# 423. Contract tests + integration tests

Both needed.

---

# 424. Crash tests

Can simulate process interruption between:

```text
commit

publish

ack
```

---

# 425. Especially important for Outbox

---

# 426. Fault injection

A useful test adapter can raise:

```text
before_commit

after_commit

before_publish

after_publish
```

---

# 427. Educational value

Excellent for understanding transaction semantics.

---

# 428. Repository transaction visibility

A Repository should only see records from:

```text
its UnitOfWork transaction
```

plus committed state.

---

# 429. InMemory UoW should model rollback

Not simply mutate shared dict immediately.

---

# 430. Why?

Otherwise transaction tests are meaningless.

---

# 431. InMemory UnitOfWork

Can use:

```text
copy-on-write
```

or staged mutations.

---

# 432. Commit applies changes.

Rollback discards.

---

# 433. Valuable learning exercise.

---

# 434. Repository save semantics

For Aggregates with versioning:

```text
save(schedule, expected_version)
```

or version embedded in aggregate.

---

# 435. Mapper updates

Repository compares:

```text
loaded_version
```

against DB.

---

# 436. On successful save

Domain object may receive:

```text
new PersistenceVersion
```

---

# 437. But beware mutation after commit

Could return new instance or update version.

---

# 438. V1 can update aggregate version explicitly after save.

---

# 439. Transaction object identity

UnitOfWork may keep identity map to avoid loading same Aggregate twice.

---

# 440. Not required V1.

---

# 441. Lazy loading

Avoid in domain.

---

# 442. Why?

Hidden DB access inside domain methods makes reasoning difficult.

---

# 443. Repositories should hydrate enough state needed by Aggregate.

---

# 444. Attempt history loading

If many attempts later:

```text
lazy/paged history
```

may be needed.

---

# 445. But MaxAttempts bounded means V1 histories remain small.

---

# 446. Excellent reason for bounded retries.

---

# 447. Deletion semantics

Repository `delete(schedule)` should not be primary business API.

---

# 448. Use:

```text
schedule.cancel()
```

for business cancellation.

---

# 449. Physical delete only through admin/retention path.

---

# 450. Transactional event ordering

Events generated in same transaction should have deterministic order.

---

# 451. Event sequence

Could use:

```text
aggregate_version
```

or insertion sequence.

---

# 452. Outbox order across aggregates

No strict global order should be promised.

---

# 453. Per aggregate order

More realistic.

---

# 454. Execution outbox

Possible events:

```text
ExecutionRequested

ExecutionCompleted
```

---

# 455. Publisher ordering

May need per aggregate ordering if consumers care.

---

# 456. V1

Single publisher can simplify.

---

# 457. But consumers must still tolerate duplicates.

---

# 458. Persistence and observability

DB failures should not be hidden behind generic scheduler errors.

---

# 459. Useful metrics

```text
transaction_commit_count

transaction_rollback_count

optimistic_conflict_count

duplicate_occurrence_count

outbox_pending_count

outbox_publish_retry_count

repository_latency
```

---

# 460. Outbox age

```text
oldest_pending_outbox_age
```

is important.

---

# 461. Why?

DB may be healthy while publisher is stuck.

---

# 462. Request backlog

```text
waiting_admission_count
```

---

# 463. Retry backlog

```text
due_retry_count
```

---

# 464. Storage corruption diagnostics

Deserializer errors must identify:

```text
record ID

schema version

field category
```

without exposing secrets.

---

# 465. Sensitive data

Execution context and failure metadata may contain:

```text
tokens

credentials

PII
```

---

# 466. Persistence model should favor references

Not full secret payloads.

---

# 467. Secret references

Store:

```text
SecretRef
```

rather than secret itself where possible.

---

# 468. Encryption at rest

Infrastructure concern.

---

# 469. But framework should not encourage plaintext credentials.

---

# 470. Target arguments

Need careful policy.

---

# 471. If arbitrary args are persisted

They must be:

```text
serializable

validated

redacted
```

---

# 472. ExecutionContext should be intentionally bounded.

---

# 473. No Python object graphs

Persist declarative values.

---

# 474. Schema evolution of contexts

Can be versioned similarly.

---

# 475. Recovery invariant

At restart, a fresh process should be able to answer:

```text
Which Schedules are due?

Which Requests await admission?

Which Executions are queued?

Which Retries are due?

Which Attempts are stale?
```

using only persistence.

---

# 476. If answer requires lost in-memory state

Persistence model is incomplete.

---

# 477. This is a strong acceptance test.

---

# 478. Complete restart model

```text
PROCESS CRASH
     │
     ▼
memory disappears
     │
     ▼
new process
     │
     ▼
load durable state
     │
     ├── due schedules
     ├── waiting requests
     ├── queued executions
     ├── retry waits
     └── stale attempts
     │
     ▼
resume safely
```

---

# 479. Data model hierarchy

```text
Schedule
│
├── current ScheduleDefinition
├── next_run_time
└── version
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

---

# 480. Transaction boundaries summary

### Schedule evaluation transaction

```text
Schedule
+
ExecutionRequest
+
next_run_time
+
Outbox
```

### Execution admission transaction

```text
Request state
+
Execution creation
+
Concurrency coordination
```

### Attempt completion transaction

```text
Attempt result
+
Execution state
+
retry timer / final result
+
Outbox
```

---

# 481. These are the three most important transactions

---

# 482. Transaction 1 — Scheduling

Transforms:

```text
temporal intent
```

into:

```text
durable ExecutionRequest
```

---

# 483. Transaction 2 — Admission

Transforms:

```text
durable request
```

into:

```text
logical Execution
```

---

# 484. Transaction 3 — Completion

Transforms:

```text
AttemptResult
```

into:

```text
retry wait
or
terminal ExecutionResult
```

---

# 485. Beautiful separation

Each transaction corresponds to one major semantic boundary.

---

# 486. No transaction spans actual task duration

Critical.

---

# 487. Never keep SQL transaction open while Attempt runs

---

# 488. Instead

Persist:

```text
RUNNING
```

commit.

Then execute.

Then new transaction records result.

---

# 489. Why?

A task may run:

```text
seconds

minutes

hours
```

---

# 490. Holding DB locks that long would be disastrous.

---

# 491. Consequence

There is always a possibility:

```text
RUNNING persisted

worker crashes before result
```

---

# 492. Therefore RuntimeReconciler exists.

---

# 493. Persistence model accepts uncertainty

Rather than pretending one giant transaction can cover execution.

---

# 494. Distributed system principle

Local transactions provide:

```text
atomic state transitions
```

but not:

```text
atomic external side effects
```

---

# 495. Honest guarantees

PyScheduleKit should clearly state:

```text
durable logical intent

idempotent materialization

recoverable runtime state

at-least-once publication possibility
```

---

# 496. Not:

```text
exactly once business effect
```

---

# 497. Persistence state machine enforcement

Repositories should not expose generic:

```text
update_status(anything)
```

---

# 498. Application changes Aggregate via domain methods

Repository persists resulting state.

---

# 499. Why?

Otherwise DB layer can bypass:

```text
state machine invariants
```

---

# 500. Admin repair tools exception

May update persistence directly under explicit maintenance procedures.

---

# 501. But not normal runtime.

---

# 502. Database triggers?

Possible for constraints, but domain rules should remain in code.

---

# 503. Avoid business logic split across:

```text
Python

DB triggers

ORM callbacks
```

without clear reason.

---

# 504. V1 keep transparent.

---

# 505. Persistence module boundaries

Suggested:

```text
pyschedulekit/
├── domain/
├── application/
├── ports/
│   ├── schedule_repository.py
│   ├── execution_request_repository.py
│   ├── execution_repository.py
│   └── unit_of_work.py
└── infrastructure/
    └── persistence/
        ├── memory/
        ├── sqlalchemy/
        ├── mappings/
        ├── codecs/
        └── migrations/
```

---

# 506. SQLAlchemy

A likely adapter later.

But core must not import it.

---

# 507. UnitOfWork port

Example conceptual protocol:

```text
UnitOfWork

.schedules
.requests
.executions

.commit()
.rollback()
```

---

# 508. Context manager semantics

Useful, but implementation detail.

---

# 509. Automatic rollback on exception

Recommended.

---

# 510. Explicit commit

Recommended.

---

# 511. Why explicit commit?

Makes transaction boundaries visible.

---

# 512. Example

```text
with uow:
    ...
    uow.commit()
```

If commit absent:

```text
rollback
```

---

# 513. Very educational model.

---

# 514. Transaction event hooks

After successful commit:

```text
notify runtime
```

can occur.

---

# 515. Example

Create Schedule:

```text
BEGIN

save Schedule

COMMIT

runtime.notify()
```

---

# 516. If notify fails

Schedule still durable.

Polling fallback.

---

# 517. Exactly the desired semantics.

---

# 518. Execution completion notification

Same:

```text
COMMIT terminal Execution

notify SchedulerRuntime
```

to wake waiting admissions.

---

# 519. Signal loss harmless.

---

# 520. Persistence and wake-up are loosely coupled

Good architecture.

---

# 521. Transactional notifications via DB

Future Postgres adapter could use:

```text
LISTEN / NOTIFY
```

---

# 522. But not required.

---

# 523. Migration safety

Before runtime starts, migrations must be:

```text
compatible
```

---

# 524. Runtime should not discover missing critical columns mid-cycle.

---

# 525. SchemaVersion table

Infrastructure can track DB schema version.

---

# 526. On incompatible schema

Runtime:

```text
FAILED
```

during STARTING.

---

# 527. No automatic destructive migration in scheduler process V1.

---

# 528. Backup/restore

After DB restore to earlier point:

```text
external side effects may already have occurred
```

---

# 529. Important limitation

Restoring scheduler DB does not rewind external world.

---

# 530. Therefore disaster recovery requires:

```text
idempotency

external reconciliation
```

---

# 531. This is beyond V1 but worth documenting.

---

# 532. Persistence guarantees cannot erase external history.

---

# 533. Multi-region replication

Future concern.

---

# 534. Strong single-writer semantics preferred initially.

---

# 535. Clock persistence

Do not persist:

```text
monotonic timestamps
```

across process restart.

---

# 536. Only wall-clock Instants have durable meaning.

---

# 537. Sleep deadlines need recomputation after restart.

---

# 538. Query model could derive backlog counts

No need to persist them.

---

# 539. Derived values

Examples:

```text
active_count

waiting_count

retry_due_count
```

should generally be queried/derived.

---

# 540. Avoid mutable counters unless needed for scale

Counters introduce consistency issues.

---

# 541. V1 favor truth from rows.

---

# 542. Performance later

Materialized counters possible with clear ownership.

---

# 543. Persistence contract tests

Recommended shared suite:

```text
Schedule round-trip

Schedule optimistic conflict

Request occurrence dedup

Request state query

Execution request uniqueness

Attempt number uniqueness

Retry due ordering

Active execution filtering

Transaction rollback

Transaction commit

Outbox atomicity
```

---

# 544. Crash consistency tests

Also:

```text
rollback after request creation

rollback after next_run update

commit before simulated process crash

outbox republish duplicate

consumer dedup
```

---

# 545. Concurrency tests

Two transactions trying:

```text
same OccurrenceKey
```

---

# 546. Expected

Exactly one logical request.

---

# 547. Two transactions rescheduling same Schedule

Expected:

```text
one succeeds

one conflict
```

---

# 548. Two workers starting same retry

Expected:

```text
one Attempt N+1
```

---

# 549. Duplicate result submission

Expected:

```text
idempotent or conflict-safe
```

---

# 550. Terminal overwrite

Must fail.

---

# 551. Persistence quality is part of domain correctness

This is important.

A perfect Trigger with a bad transaction model still creates:

```text
lost

duplicated

corrupted
```

scheduling behavior.

---

# 552. Therefore

Persistence is not merely:

```text
"infrastructure plumbing"
```

It supports domain invariants.

---

# 553. But domain must remain storage-agnostic

This is the balance.

---

# 554. Persistence terminology

Use:

```text
Store

Repository

UnitOfWork

Transaction

Projection

Outbox

Optimistic Lock
```

precisely.

---

# 555. Avoid calling DB row a Domain Entity automatically.

---

# 556. Repository ≠ DAO

A DAO is often table-oriented.

Repository is aggregate/domain-oriented.

---

# 557. Query Port ≈ read-oriented abstraction

Can be projection-oriented.

---

# 558. Mapper ≠ Repository

Mapper transforms representations.

Repository exposes collection semantics.

---

# 559. UnitOfWork ≠ Repository

UoW controls transaction boundary across repositories.

---

# 560. Outbox ≠ event bus

It is durable staging for messages/events.

---

# 561. Final persistence architecture

```text
                   Application Service
                           │
                           ▼
                      UnitOfWork
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
 ScheduleRepository  RequestRepository ExecutionRepository
          │                │                 │
          └────────────────┼─────────────────┘
                           ▼
                     Persistence Mapper
                           │
                           ▼
                        Database
                           │
                           ├── Domain State
                           ├── Runtime State
                           └── Outbox
```

---

# 562. Scheduling transaction diagram

```text
Schedule due
    │
    ▼
BEGIN TRANSACTION
    │
    ├── validate version
    │
    ├── create Request
    │
    ├── advance next_run_time
    │
    ├── increment version
    │
    └── write Outbox
    │
    ▼
COMMIT
    │
    ▼
Outbox Publisher
    │
    ▼
Execution Runtime
```

---

# 563. Execution transaction diagram

```text
AttemptResult
     │
     ▼
BEGIN TRANSACTION
     │
     ├── load Execution
     ├── validate version/state
     ├── finalize Attempt
     │
     ├── Retry?
     │     ├── yes → RETRY_WAIT + next_attempt_at
     │     └── no  → terminal ExecutionResult
     │
     └── write Outbox/Event
     │
     ▼
COMMIT
```

---

# 564. Idempotence hierarchy final

```text
OccurrenceKey
→ scheduling deduplication

RequestId
→ dispatch deduplication

ExecutionId
→ logical run identity

AttemptNumber / AttemptId
→ retry attempt identity

MessageId
→ publication deduplication
```

---

# 565. Persistence V1 decisions

```text
1.
Use Repository abstractions around domain aggregates.

2.
Use UnitOfWork for transaction boundaries.

3.
Repositories never commit implicitly.

4.
ScheduleRepository, ExecutionRequestRepository
and ExecutionRepository form the V1 persistence core.

5.
Attempt is persisted as part of the Execution aggregate
even if physically stored in its own table.

6.
Occurrence remains a Value Object in V1.

7.
OccurrenceKey is persisted on ExecutionRequest.

8.
Automatic primary requests are unique by OccurrenceKey.

9.
Execution is unique by RequestId.

10.
AttemptNumber is unique per Execution.

11.
ScheduleRevision and PersistenceVersion are separate.

12.
Optimistic locking is supported.

13.
Schedule evaluation materialization and next_run advancement
are transactionally coherent.

14.
Attempt completion and Execution transition
are transactionally coherent.

15.
External dispatch occurs after commit.

16.
Transactional Outbox is the recommended reliable
publication pattern.

17.
Outbox delivery may be at-least-once.

18.
Consumers must deduplicate using stable identities.

19.
Serialized configuration is explicit, safe and versioned.

20.
All durable Instants are timezone-aware.

21.
In-memory persistence adapters emulate
transaction and uniqueness semantics.

22.
The runtime can reconstruct its work after restart
using only durable state.

23.
Physical deletion is not normal lifecycle behavior.

24.
Cross-framework DB foreign keys are avoided.

25.
Exactly-once external side effects are not promised.
```

---

# 566. Acceptance criteria

Le modèle est suffisamment défini lorsque l'on peut répondre précisément à :

```text
Quel objet possède quel Repository ?

Pourquoi Attempt n'a-t-elle pas forcément besoin
d'un Repository public séparé ?

Qu'est-ce qu'une UnitOfWork ?

Qui décide du commit ?

Pourquoi un Repository ne doit-il jamais commit silencieusement ?

Quelles mutations doivent être atomiques
avec next_run_time ?

Comment éviter de perdre une occurrence ?

Comment éviter de créer la même occurrence deux fois ?

Pourquoi ScheduleRevision et PersistenceVersion
sont-elles différentes ?

Comment deux scheduler nodes détectent-ils
une mutation concurrente ?

Comment survivre à un crash après COMMIT
mais avant dispatch ?

Pourquoi utiliser un Outbox ?

Pourquoi l'Outbox implique-t-elle encore
de la déduplication côté consumer ?

Comment représenter un Retry durablement ?

Quelles données permettent la reprise après restart ?

Quelles données peuvent rester en mémoire ?

Comment les policies et Triggers sont-ils sérialisés ?

Comment gérer les migrations de formats ?

Que faire si une transaction a un résultat de commit inconnu ?

Pourquoi exactement-once business effect
n'est-il pas garanti par une transaction SQL locale ?
```

---

# 567. Modèle mental final

```text
                   DOMAIN DECISION
                         │
                         ▼
                 APPLICATION SERVICE
                         │
                         ▼
                     UnitOfWork
                         │
                         ▼
              ┌────────────────────┐
              │   DB TRANSACTION   │
              │                    │
              │ Schedule           │
              │ Request            │
              │ Execution          │
              │ Attempt            │
              │ Outbox             │
              └─────────┬──────────┘
                        │
                      COMMIT
                        │
                        ▼
                 DURABLE INTENT
                        │
                        ▼
                 OUTBOX PUBLISHER
                        │
                        ▼
                     EXECUTOR
```

---

# 568. Principe central

Le stockage n'est pas seulement chargé de sauvegarder des objets.

Il doit préserver :

```text
identity

ordering

atomicity

idempotence

lifecycle invariants

restartability
```

---

# 569. Définition finale

> **Le modèle de persistance de PyScheduleKit transforme les décisions du scheduler en état durable, transactionnel et réévaluable, de sorte qu'un crash, une concurrence d'écriture ou une livraison dupliquée ne puisse pas silencieusement transformer l'intention temporelle du système.**

---

# Conclusion

À ce stade, PyScheduleKit possède désormais toute la chaîne conceptuelle fondamentale :

```text
Time
↓
Trigger
↓
Occurrence
↓
Misfire / Catch-Up
↓
Concurrency
↓
ExecutionRequest
↓
Execution
↓
Attempt
↓
Retry
↓
Persistence
```

Le document **19** ajoute la garantie qui manquait à cette chaîne :

```text
les décisions importantes
ne vivent plus uniquement
dans la mémoire du process
```

Elles deviennent :

```text
durables

transactionnelles

versionnées

dédupliquées

récupérables
```

Le principe le plus important est :

> **Il vaut mieux être capable de détecter et éliminer un traitement répété que de risquer de perdre silencieusement une intention d'exécution.**

C'est pourquoi l'architecture privilégie :

```text
at-least-once evaluation

+

stable identities

+

unique constraints

+

transactional persistence

+

idempotent consumers
```

plutôt qu'une promesse artificielle d'`exactly once`.

---

# Suite documentaire

La suite logique est désormais :

```text
20_DISTRIBUTED_COORDINATION_LEASES_AND_LEADER_ELECTION.md
```

Ce document pourra traiter :

```text
multi-node schedulers

Schedule claiming

Lease

Lease expiry

Lease renewal

node ownership

leader election

split brain

clock skew

distributed concurrency

fencing tokens

failover

reconciliation
```

et répondre à la question suivante :

> **Comment plusieurs instances de PyScheduleKit peuvent-elles partager la même base et le même ensemble de Schedules sans exécuter le même travail simultanément ?**

Après cela, une suite très naturelle sera :

```text
21_OBSERVABILITY_AUDIT_EVENTS_AND_DIAGNOSTICS_MODEL.md
```

puis :

```text
22_PUBLIC_API_AND_CONFIGURATION_MODEL.md
```

avant d'entrer dans les premières spécifications d'implémentation concrètes.