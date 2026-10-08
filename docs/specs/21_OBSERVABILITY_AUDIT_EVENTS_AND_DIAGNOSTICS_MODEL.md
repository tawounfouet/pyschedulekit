# PyScheduleKit — Observability, Audit, Events & Diagnostics Model

**Document :** `21_OBSERVABILITY_AUDIT_EVENTS_AND_DIAGNOSTICS_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle d’observabilité de référence  
**Nature :** Observability Model — Events / Audit / Logs / Metrics / Traces / Diagnostics  
**Prérequis :**
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`
- `14_CONCURRENCY_AND_OVERLAP_MODEL.md`
- `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`
- `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`
- `17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md`
- `18_SCHEDULER_RUNTIME_AND_WAKEUP_MODEL.md`
- `19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md`
- `20_DISTRIBUTED_COORDINATION_LEASES_AND_LEADER_ELECTION.md`

---

# 1. Objectif

PyScheduleKit sait désormais :

```text
calculer des occurrences

prendre des décisions de misfire

faire du catch-up

gérer la concurrence

créer des ExecutionRequests

exécuter plusieurs Attempts

faire des retries

persister les états

fonctionner sur plusieurs nœuds
```

Il reste une question fondamentale :

> **Comment expliquer exactement ce que le scheduler a fait, pourquoi il l’a fait, quand il l’a fait et avec quelles preuves ?**

---

# 2. Un scheduler inexplicable est difficilement exploitable

Supposons qu'un utilisateur demande :

```text
Pourquoi mon job de 10:00
n'a-t-il pas été exécuté ?
```

Le système doit pouvoir répondre autre chose que :

```text
"aucune idée"
```

---

# 3. Les réponses possibles sont nombreuses

```text
Schedule PAUSED

Occurrence skipped by MisfirePolicy

Occurrence coalesced

Concurrency limit reached

Request waiting admission

Execution failed

Retries exhausted

Execution cancelled

Runtime unavailable

Node lost lease

Trigger exhausted

Schedule completed
```

---

# 4. Observability comme capacité métier

L'observabilité ne concerne pas seulement :

```text
CPU

RAM

logs
```

Elle doit permettre de reconstruire :

```text
la décision métier du scheduler
```

---

# 5. Question centrale

Pour toute occurrence potentielle, PyScheduleKit devrait pouvoir répondre à :

```text
What happened?

When?

Why?

Under which Schedule revision?

Which policy made the decision?

Was an ExecutionRequest created?

Which Execution resulted?

Which Attempts occurred?

Which node handled it?

What failed?

What happens next?
```

---

# 6. Six familles à distinguer

Le modèle d'observabilité contient :

```text
Domain Events

Audit Records

Structured Logs

Metrics

Distributed Traces

Diagnostics
```

---

# 7. Important

Ces six concepts ne sont pas interchangeables.

---

# 8. Domain Event

Un `DomainEvent` représente :

> **Un fait significatif ayant eu lieu dans le domaine.**

Exemple :

```text
SchedulePaused
```

---

# 9. Audit Record

Un `AuditRecord` représente :

> **Une preuve durable destinée à expliquer une action ou une décision passée.**

---

# 10. Structured Log

Un log structuré représente :

> **Une observation technique ou contextuelle produite pendant l'exécution.**

---

# 11. Metric

Une métrique représente :

> **Une valeur numérique agrégable permettant d'observer le comportement d'un système dans le temps.**

---

# 12. Trace

Une trace représente :

> **Le chemin causal d'une opération distribuée à travers plusieurs composants.**

---

# 13. Diagnostic

Un diagnostic représente :

> **Une explication structurée d'un état, d'une décision, d'une anomalie ou d'un problème.**

---

# 14. Distinction fondamentale

```text
Event
≠
Audit Record
≠
Log
≠
Metric
≠
Trace
≠
Diagnostic
```

---

# 15. Pourquoi cette séparation ?

Parce que chacun répond à une question différente.

| Concept | Question principale |
|---|---|
| Event | Qu'est-il arrivé ? |
| Audit | Quelle preuve durable avons-nous ? |
| Log | Que faisait le système à ce moment ? |
| Metric | Combien / à quelle fréquence / avec quelle latence ? |
| Trace | Quel chemin a suivi l'opération ? |
| Diagnostic | Pourquoi et que faut-il comprendre ? |

---

# 16. Observability Architecture

```text
Domain
  │
  ├── Domain Events
  │
  ▼
Application
  │
  ├── Audit Records
  ├── Diagnostics
  ├── Structured Logs
  │
  ▼
Observability Adapters
  │
  ├── Metrics
  ├── Traces
  ├── Log Sink
  └── Audit Sink
```

---

# 17. Source de vérité

L'état courant reste :

```text
Persistence Store
```

et non :

```text
logs
metrics
traces
```

---

# 18. Observability is evidence, not state authority

Un log disant :

```text
Execution succeeded
```

ne remplace pas :

```text
ExecutionState = SUCCESS
```

persisté.

---

# 19. Event sourcing non requis

PyScheduleKit n'a pas besoin d'être :

```text
event sourced
```

pour publier des événements.

---

# 20. Modèle recommandé

```text
Current State
+
Append-only Events/Audit
```

---

# 21. Événement et état courant

Exemple :

```text
ScheduleState = PAUSED
```

et historique :

```text
ScheduleCreated
ScheduleRescheduled
SchedulePaused
```

---

# 22. Domain Event Envelope

Un format générique peut contenir :

```text
EventEnvelope
│
├── event_id
├── event_type
├── schema_version
├── occurred_at
├── aggregate_type
├── aggregate_id
├── aggregate_version
├── correlation_id
├── causation_id
├── node_id?
└── payload
```

---

# 23. EventId

```text
EventId
```

doit être stable et unique.

---

# 24. EventType

Exemples :

```text
schedule.created

schedule.paused

occurrence.skipped

execution.requested

attempt.failed

execution.completed
```

---

# 25. Event type naming

Recommandation :

```text
<domain>.<past_tense_fact>
```

---

# 26. Exemples

```text
schedule.created

schedule.rescheduled

execution.retry_scheduled

lease.acquired
```

---

# 27. SchemaVersion

Chaque event doit pouvoir évoluer.

```text
schema_version = 1
```

---

# 28. occurred_at

Doit être un :

```text
Instant
```

timezone-aware.

---

# 29. aggregate_type

Exemple :

```text
Schedule

Execution

ExecutionRequest
```

---

# 30. aggregate_id

Exemple :

```text
sched-42

exec-123
```

---

# 31. aggregate_version

Permet :

```text
ordering

diagnostics

optimistic consistency
```

---

# 32. Event ordering

Les timestamps seuls ne suffisent pas.

---

# 33. Pourquoi ?

Deux événements peuvent avoir :

```text
same timestamp
```

---

# 34. Per-aggregate ordering

Utiliser :

```text
aggregate_version
```

ou :

```text
event_sequence
```

---

# 35. Pas de global total order garanti

Dans un système distribué :

```text
Schedule event

Execution event

Worker event
```

peuvent arriver dans différents ordres.

---

# 36. CorrelationId

Le `CorrelationId` relie une même opération métier distribuée.

---

# 37. Example

```text
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

peuvent partager :

```text
CorrelationId
```

---

# 38. CausationId

Le `CausationId` répond :

> Quel événement ou command a causé celui-ci ?

---

# 39. Example

```text
AttemptFailed
```

cause :

```text
RetryScheduled
```

---

# 40. Graph causal

```text
AttemptFailed
   │
   ▼
RetryScheduled
   │
   ▼
AttemptStarted
```

---

# 41. Correlation versus Causation

```text
CorrelationId
→ même conversation globale

CausationId
→ relation parent/enfant directe
```

---

# 42. TraceId

Un `TraceId` est principalement technique.

---

# 43. CorrelationId versus TraceId

Ils peuvent être identiques V1, mais conceptuellement :

```text
CorrelationId
→ business/runtime correlation

TraceId
→ distributed tracing implementation
```

---

# 44. Recommendation

Conserver les concepts séparés.

---

# 45. ExecutionContext

Peut porter :

```text
CorrelationId

TraceId

ScheduleId

OccurrenceKey

ExecutionId
```

---

# 46. Propagation

Cet `ExecutionContext` doit pouvoir traverser :

```text
PyScheduleKit
→ PyWorkflowKit
→ PyIngestKit
→ PyTransformKit
```

---

# 47. Pas de mega-context

Ne transmettre que les informations nécessaires.

---

# 48. Schedule lifecycle events

Catalogue initial :

```text
ScheduleCreated

ScheduleActivated

SchedulePaused

ScheduleResumed

ScheduleRescheduled

ScheduleCancelled

ScheduleCompleted
```

---

# 49. ScheduleCreated

Peut contenir :

```text
schedule_id

revision

target_ref

next_run_time
```

---

# 50. ScheduleRescheduled

Peut contenir :

```text
old_revision

new_revision

previous_next_run_time

new_next_run_time
```

---

# 51. SchedulePaused

```text
paused_at

reason?
```

---

# 52. ScheduleResumed

```text
resumed_at

new_next_run_time
```

---

# 53. ScheduleCompleted

Indique :

```text
Trigger exhausted
```

ou :

```text
no future valid occurrence
```

---

# 54. Occurrence decision events

Les occurrences constituent la partie la plus importante pour l'explicabilité.

---

# 55. Événements possibles

```text
OccurrenceDetected

OccurrenceEligible

OccurrenceMisfired

OccurrenceSkipped

OccurrenceSelectedForCatchUp

OccurrencesCoalesced

OccurrenceAdmissionDeferred

OccurrenceAdmissionRejected
```

---

# 56. Faut-il tout publier ?

Non.

---

# 57. Event volume

Un Schedule à haute fréquence peut générer énormément d'événements.

---

# 58. Recommendation

Publier durablement surtout les :

```text
business-significant decisions
```

---

# 59. SchedulingDecision

Le modèle a déjà introduit :

```text
SchedulingDecision
```

Il devient central pour l'audit.

---

# 60. SchedulingDecision Evidence

Une décision peut capturer :

```text
schedule_id

schedule_revision

occurrence_key

scheduled_at

evaluated_at

decision

reason

policy

policy_parameters

lateness

grace_period

concurrency_key?

active_count?

node_id?
```

---

# 61. DecisionType

Exemples :

```text
EXECUTE

SKIP

DEFER

COALESCE

DROP
```

---

# 62. DecisionReason

Exemples :

```text
ON_TIME

MISFIRE_SKIP

CATCH_UP_SELECTED

COALESCED_TO_LATEST

CONCURRENCY_LIMIT_REACHED

SCHEDULE_PAUSED

SCHEDULE_CANCELLED
```

---

# 63. Why reason codes matter

Ne pas dépendre de :

```text
free-form message parsing
```

---

# 64. Machine-readable reason

Utiliser :

```text
reason_code
```

plus :

```text
human_message
```

---

# 65. Example

```text
reason_code =
CONCURRENCY_LIMIT_REACHED
```

message :

```text
Execution deferred because active_count=1 and limit=1.
```

---

# 66. DecisionSnapshot

Une abstraction possible :

```text
DecisionEvidence [VO]
```

---

# 67. Immutabilité

Une décision passée ne doit pas être réinterprétée après modification du Schedule.

---

# 68. Policy snapshot

Audit peut conserver :

```text
policy kind

relevant parameters

schedule revision
```

---

# 69. Pas forcément configuration entière

Conserver seulement ce qui est utile.

---

# 70. Misfire evidence

Exemple :

```text
scheduled_at = 10:00

evaluated_at = 10:12

lateness = 12m

grace_period = 5m

decision = SKIP

reason = MISFIRE_GRACE_EXCEEDED
```

---

# 71. Catch-Up evidence

```text
missed_occurrences = 10

selected = 3

skipped = 7

policy = CATCH_UP_LIMITED

max_occurrences = 3
```

---

# 72. Coalescing evidence

```text
source_occurrences =
09:00
10:00
11:00

strategy = LATEST

selected_occurrence = 11:00
```

---

# 73. Concurrency evidence

```text
ConcurrencyKey = customer-refresh

active_count = 1

limit = 1

overflow = QUEUE

decision = DEFER
```

---

# 74. Why this is useful

Un opérateur peut répondre précisément :

```text
Why is my job waiting?
```

---

# 75. ExecutionRequest events

Exemples :

```text
ExecutionRequestCreated

ExecutionRequestWaitingAdmission

ExecutionRequestDispatched

ExecutionRequestCancelled
```

---

# 76. Execution events

```text
ExecutionCreated

ExecutionQueued

ExecutionStarted

ExecutionCompleted

ExecutionCancelled

ExecutionTimedOut
```

---

# 77. Attempt events

```text
AttemptStarted

AttemptSucceeded

AttemptFailed

AttemptTimedOut

AttemptCancelled
```

---

# 78. Retry events

```text
RetryScheduled

RetriesExhausted
```

---

# 79. RetryScheduled evidence

```text
execution_id

previous_attempt

next_attempt_number

retry_at

backoff

failure_category

reason
```

---

# 80. Retry exhaustion evidence

```text
attempt_count

max_attempts

final_failure

stop_reason
```

---

# 81. Distributed coordination events

Operational events can include :

```text
ScheduleClaimAcquired

ScheduleClaimConflict

ExecutionClaimAcquired

LeaseAcquired

LeaseRenewed

LeaseLost

LeadershipAcquired

LeadershipLost

FencingRejected
```

---

# 82. Ces événements ne sont pas nécessairement métier

Classification :

```text
Runtime / Coordination Events
```

---

# 83. Runtime events

```text
SchedulerRuntimeStarted

SchedulerRuntimeStopping

SchedulerRuntimeStopped

SchedulerRuntimeFailed

EvaluationCycleStarted

EvaluationCycleCompleted

EvaluationCycleFailed
```

---

# 84. Event taxonomy

Recommandation :

```text
Domain Events

Application Events

Runtime Events

Coordination Events
```

---

# 85. Ne pas tout appeler DomainEvent

Cela évite de brouiller les bounded contexts.

---

# 86. Audit Trail

L'Audit Trail doit répondre à :

> **Que s'est-il réellement passé sur cet objet au fil du temps ?**

---

# 87. AuditRecord

Proposition :

```text
AuditRecord
│
├── audit_id
├── occurred_at
├── category
├── action
├── subject_type
├── subject_id
├── actor
├── reason_code
├── correlation_id
├── metadata
└── source_event_id?
```

---

# 88. Actor

Peut être :

```text
USER

SCHEDULER

WORKER

SYSTEM

NODE
```

---

# 89. Human actor

Pour les opérations manuelles :

```text
pause

resume

reschedule

cancel

rerun
```

---

# 90. System actor

Pour :

```text
automatic schedule evaluation

misfire decision

retry

timeout
```

---

# 91. Audit is append-only

Recommandation forte :

```text
never update historical AuditRecord
```

---

# 92. Correction

Si une information doit être corrigée :

```text
append a correction record
```

plutôt que réécrire silencieusement.

---

# 93. Audit versus Events

Un AuditRecord peut être généré depuis un Event.

Mais :

```text
not every Event
must become audit
```

---

# 94. Exemple

```text
LeaseRenewed
```

toutes les 10 secondes n'a probablement pas besoin d'un audit durable métier.

---

# 95. Audit focus

Audit durable prioritaire :

```text
Schedule lifecycle changes

Scheduling decisions

Execution lifecycle

Manual interventions

Security-sensitive actions
```

---

# 96. Logs

Les logs sont utiles pour :

```text
debug

operations

incident investigation
```

---

# 97. Structured logging

Éviter uniquement :

```text
"something failed"
```

---

# 98. LogRecord fields

Exemple :

```text
timestamp

level

logger

message

event_code

schedule_id

request_id

execution_id

attempt_id

correlation_id

trace_id

node_id
```

---

# 99. Structured logs as JSON

Une infrastructure peut produire :

```json
{
  "level": "INFO",
  "event_code": "execution.retry_scheduled",
  "execution_id": "exec-42",
  "attempt_number": 2,
  "retry_at": "2026-10-04T10:05:00Z"
}
```

---

# 100. Human-readable logs still useful

Console dev peut rendre :

```text
[INFO] exec-42 retry #2 scheduled at 10:05
```

---

# 101. Same underlying structure

Renderer différent.

---

# 102. Log Levels

Recommandation :

```text
DEBUG

INFO

WARNING

ERROR

CRITICAL
```

---

# 103. DEBUG

Pour :

```text
candidate selection

planner details

state snapshots
```

---

# 104. INFO

Pour :

```text
major lifecycle transitions
```

---

# 105. WARNING

Pour :

```text
misfire spikes

late execution

retry

lease loss

degraded runtime
```

selon importance.

---

# 106. ERROR

Pour :

```text
Schedule evaluation failure

persistence error

terminal unexpected failure
```

---

# 107. CRITICAL

Pour :

```text
runtime unable to continue safely
```

---

# 108. Avoid log-level semantics as domain state

`ERROR` log does not mean :

```text
Execution FAILED
```

automatically.

---

# 109. Logging context propagation

Une scope de logging peut porter automatiquement :

```text
schedule_id

execution_id

correlation_id
```

---

# 110. No global mutable logging context

En async/concurrent environment, préférer :

```text
context-local / explicit context
```

---

# 111. Secret redaction

Logs, audit and diagnostics doivent protéger :

```text
passwords

tokens

authorization headers

private keys

connection strings
```

---

# 112. RedactionPolicy

Une abstraction possible :

```text
RedactionPolicy
```

---

# 113. Sensitive keys

Exemples :

```text
password

secret

token

authorization

api_key
```

---

# 114. Never persist raw traceback blindly

Les tracebacks peuvent contenir :

```text
arguments

paths

secrets

payload snippets
```

---

# 115. Failure object normalized first

Puis détails techniques contrôlés séparément.

---

# 116. PII

Execution metadata peut contenir :

```text
user IDs

emails

business data
```

---

# 117. Principle

> **Observe enough to explain the scheduler, not enough to recreate every sensitive payload.**

---

# 118. Metrics

Les métriques doivent être :

```text
aggregable

low-cardinality

cheap
```

---

# 119. Cardinality danger

Éviter comme metric label :

```text
schedule_id

execution_id

request_id

correlation_id
```

à grande échelle.

---

# 120. Pourquoi ?

Cela produit :

```text
unbounded time series
```

---

# 121. Good labels

Exemples :

```text
trigger_type

decision

failure_category

execution_state

runtime_state

policy_kind
```

si cardinalité maîtrisée.

---

# 122. Scheduling Metrics

```text
schedules_active

schedules_due

schedules_evaluated_total

schedule_evaluation_errors_total

occurrences_detected_total

occurrences_materialized_total

occurrences_skipped_total

misfires_total

catchup_occurrences_total

coalesced_occurrences_total
```

---

# 123. Schedule Lag

```text
schedule_lag_seconds
```

mesure :

```text
evaluation_now - scheduled_at
```

pour une occurrence traitée.

---

# 124. Global scheduler lag

```text
oldest_due_schedule_age_seconds
```

---

# 125. Admission metrics

```text
admission_admitted_total

admission_deferred_total

admission_rejected_total

waiting_admission_count

concurrency_limit_reached_total
```

---

# 126. Execution metrics

```text
executions_created_total

executions_completed_total

executions_active

executions_success_total

executions_failed_total

executions_cancelled_total

executions_timed_out_total
```

---

# 127. Attempt metrics

```text
attempts_started_total

attempts_success_total

attempts_failed_total

attempts_timed_out_total
```

---

# 128. Retry metrics

```text
retries_scheduled_total

retries_exhausted_total

retry_wait_seconds

execution_success_after_retry_total
```

---

# 129. Runtime metrics

```text
scheduler_runtime_up

evaluation_cycle_total

evaluation_cycle_errors_total

evaluation_cycle_duration_seconds

wakeups_total

runtime_backoff_total

scheduler_next_wakeup_timestamp
```

---

# 130. Persistence metrics

```text
transaction_commits_total

transaction_rollbacks_total

optimistic_conflicts_total

duplicate_occurrence_conflicts_total

repository_latency_seconds
```

---

# 131. Outbox metrics

```text
outbox_pending_count

outbox_oldest_pending_age_seconds

outbox_publish_total

outbox_publish_failures_total
```

---

# 132. Distributed metrics

```text
schedule_claim_success_total

schedule_claim_conflict_total

execution_claim_success_total

lease_acquire_success_total

lease_acquire_conflict_total

lease_renew_failure_total

leadership_changes_total

fencing_rejections_total
```

---

# 133. Gauge versus Counter

Exemple :

```text
executions_active
```

→ Gauge.

```text
attempts_failed_total
```

→ Counter.

---

# 134. Histogram

Bon pour :

```text
cycle_duration

schedule_lag

execution_duration

retry_wait
```

---

# 135. SLO-related metrics

PyScheduleKit peut mesurer :

```text
scheduling latency

decision latency

execution start latency
```

---

# 136. Scheduling latency

```text
request_created_at - scheduled_at
```

---

# 137. Admission latency

```text
execution_created_at - request_created_at
```

pour les requests en attente.

---

# 138. Queue latency

```text
first_attempt.started_at - execution.queued_at
```

---

# 139. Execution latency

```text
finished_at - started_at
```

---

# 140. End-to-end latency

```text
execution.finished_at - occurrence.scheduled_at
```

---

# 141. Important

Ces latences racontent des choses différentes.

---

# 142. Tracing

Le distributed tracing doit suivre :

```text
Evaluation Cycle

Schedule Evaluation

Occurrence Decision

Request Materialization

Execution

Attempt

External Target
```

---

# 143. Trace hierarchy example

```text
SchedulerCycle
│
├── EvaluateSchedule sched-1
│   ├── PlanOccurrences
│   ├── ApplyMisfirePolicy
│   ├── EvaluateConcurrency
│   └── PersistRequest
│
└── EvaluateSchedule sched-2
```

---

# 144. Execution trace

```text
Execution exec-42
│
├── Attempt #1
│   └── TargetCall
│
└── Attempt #2
    └── TargetCall
```

---

# 145. Span names

Stable names preferred:

```text
scheduler.cycle

schedule.evaluate

occurrence.plan

concurrency.evaluate

execution.start

attempt.execute
```

---

# 146. Span attributes

Examples :

```text
trigger.type

schedule.revision

decision

failure.category

attempt.number
```

---

# 147. High-cardinality attributes

Trace attributes can usually tolerate IDs better than metrics.

Exemples :

```text
schedule.id

execution.id

request.id
```

---

# 148. Propagate trace context

Vers :

```text
PyWorkflowKit

HTTP targets

message broker

workers
```

---

# 149. Async propagation

ExecutionRequest doit pouvoir porter le contexte de trace nécessaire.

---

# 150. But tracing vendor-neutral

Core PyScheduleKit ne dépend pas directement de :

```text
Datadog

Jaeger

Zipkin
```

---

# 151. OpenTelemetry adapter possible

Très naturel.

---

# 152. ObservabilityPort ?

Éviter un énorme :

```text
ObservabilityPort
```

qui mélange tout.

---

# 153. Better separation

```text
EventSink

AuditSink

MetricsRecorder

Tracer

Logger
```

ou utilisation des abstractions Python existantes.

---

# 154. Domain must not know MetricsRecorder

Le domaine peut produire :

```text
DomainEvents

Decision objects
```

L'application/infrastructure transforme cela en métriques.

---

# 155. Good dependency direction

```text
Domain
→ facts

Application
→ interpretation

Infrastructure
→ telemetry export
```

---

# 156. Diagnostics

Le diagnostic est différent des logs.

---

# 157. Diagnostic object

```text
Diagnostic
│
├── code
├── severity
├── summary
├── details
├── subject_type
├── subject_id
├── occurred_at
├── evidence
├── remediation?
└── correlation_id
```

---

# 158. DiagnosticCode

Exemples :

```text
SCHEDULE_LATE

TRIGGER_EXHAUSTED

MISFIRE_SKIPPED

CONCURRENCY_BLOCKED

RETRY_EXHAUSTED

STALE_ATTEMPT

LEASE_LOST

PERSISTENCE_CONFLICT

OUTBOX_BACKLOG
```

---

# 159. DiagnosticSeverity

```text
INFO

WARNING

ERROR

CRITICAL
```

---

# 160. Diagnostics should be machine-readable

Ne pas utiliser seulement :

```text
long prose message
```

---

# 161. Diagnostic evidence

Peut contenir :

```text
expected

observed

threshold

policy

relevant IDs
```

---

# 162. Example — concurrency blocked

```text
code:
CONCURRENCY_BLOCKED

key:
customer-refresh

active:
1

limit:
1

decision:
WAIT
```

---

# 163. Example — retry exhausted

```text
code:
RETRY_EXHAUSTED

attempts:
3

max_attempts:
3

final_failure:
DEPENDENCY_UNAVAILABLE
```

---

# 164. Diagnostic remediation

Optionnel.

Exemple :

```text
"Inspect dependency availability
or adjust RetryPolicy."
```

---

# 165. Avoid automated prescriptive remediation in core

Diagnostic peut suggérer, pas modifier automatiquement le système.

---

# 166. DiagnosticSnapshot

Pour support/admin tools, on peut produire :

```text
ScheduleDiagnosticSnapshot
```

---

# 167. Contents

```text
ScheduleState

Revision

NextRunTime

Current Lag

Recent Decisions

Active Executions

Waiting Requests

Recent Failures
```

---

# 168. ExecutionDiagnosticSnapshot

```text
ExecutionState

OccurrenceKey

Attempts

RetryPolicy

next_attempt_at

deadline

final result
```

---

# 169. RuntimeDiagnosticSnapshot

```text
RuntimeState

HealthStatus

NodeId

last cycle

next wake-up

lag

backlogs

leadership role
```

---

# 170. Why snapshots matter

Ils rendent possible une commande :

```text
pyschedule inspect ...
```

---

# 171. CLI future

Exemple :

```text
pyschedule inspect schedule daily-orders
```

---

# 172. Output possible

```text
State: ACTIVE
Revision: 7
Next run: 06:00 tomorrow
Last decision: EXECUTE
Active executions: 0
Recent misfires: 1
```

---

# 173. Explain command

Une fonction particulièrement intéressante :

```text
pyschedule explain occurrence ...
```

---

# 174. Goal

Répondre :

```text
Why did this occurrence not execute?
```

---

# 175. ExplainResult

Possible :

```text
ExplainResult
│
├── subject
├── outcome
├── reason_chain
├── evidence
└── related_entities
```

---

# 176. Example chain

```text
Occurrence 10:00
↓
Detected 10:12
↓
GracePeriod = 5m
↓
MISFIRED
↓
MisfirePolicy = SKIP
↓
No ExecutionRequest created
```

---

# 177. This is extremely valuable

Pour :

```text
debug

support

learning

operations
```

---

# 178. SchedulingDecision chain

Chaque decision devrait pouvoir produire une explication compacte.

---

# 179. DecisionReasonChain

Une abstraction possible :

```text
ReasonStep[]
```

---

# 180. Example

```text
1. Trigger produced 10:00
2. Calendar accepted date
3. Occurrence detected 12m late
4. GracePeriod exceeded
5. MisfirePolicy selected SKIP
```

---

# 181. Does this need persistence?

Pas forcément intégralement.

---

# 182. V1

Persist:

```text
decision type

reason code

key evidence
```

Puis reconstruct detail when possible.

---

# 183. Historical reconstruction limitation

Si policy config n'est pas historique :

```text
cannot fully reconstruct later
```

---

# 184. Therefore snapshot important facts

Especially:

```text
ScheduleRevision

policy type

critical policy parameters
```

---

# 185. Failure diagnostics

Failure normalized:

```text
FailureCategory

FailureCode

retryable

message
```

---

# 186. Technical cause

May include:

```text
exception_type

stack fingerprint
```

---

# 187. Stack fingerprint

Useful to aggregate similar failures without storing full traceback.

---

# 188. Example

```text
failure_fingerprint =
hash(exception_type + normalized_frame_pattern)
```

---

# 189. Not business identity

Pure diagnostic identifier.

---

# 190. Error grouping

Metrics/log tooling can group by:

```text
failure.category

failure.code

fingerprint
```

---

# 191. Failure message cardinality

Do not use free-form failure message as metric label.

---

# 192. Attempt diagnostics

Should answer:

```text
which worker?

how long?

which failure?

was it retryable?

what retry decision followed?
```

---

# 193. Distributed ownership diagnostics

For Schedule claim:

```text
node_id

claim strategy

claim acquired?

persistence_version
```

---

# 194. Lease diagnostics

```text
resource_key

owner_id

fencing_token

expires_at

renew status
```

---

# 195. Fencing rejection diagnostic

Important security/correctness signal.

---

# 196. Example

```text
current_token = 42

provided_token = 41

owner = node-A

result = STALE_OWNER
```

---

# 197. Leader diagnostics

```text
role

epoch

lease expiry

leadership acquired_at
```

---

# 198. Do not expose excessive distributed detail to ordinary users

Separate :

```text
developer diagnostics

operator diagnostics

end-user explanation
```

---

# 199. Diagnostic audience

Could classify:

```text
USER

OPERATOR

DEVELOPER
```

---

# 200. V1

Not necessary as public object.

But useful principle.

---

# 201. Audit storage

Could use table:

```text
audit_records
```

---

# 202. Fields

```text
audit_id

occurred_at

category

action

subject_type

subject_id

actor_type

actor_id?

reason_code

correlation_id

payload_json
```

---

# 203. Indexes

Potential :

```text
(subject_type, subject_id, occurred_at)

(correlation_id, occurred_at)

(category, occurred_at)
```

---

# 204. Event Store?

Not full event sourcing.

A simple:

```text
scheduler_events
```

append-only table may suffice.

---

# 205. Should audit and event tables be same?

Could be, but conceptually distinct.

---

# 206. V1 simplification

Use one append-only:

```text
event_records
```

with:

```text
event_category
```

then expose audit projection.

---

# 207. Trade-off

Simpler persistence, slightly less semantic separation.

---

# 208. Long-term recommendation

Keep conceptual separation even if physical storage is shared.

---

# 209. Outbox relation

Important events can be inserted into:

```text
outbox
```

inside same transaction as state mutation.

---

# 210. Event publication consistency

Example:

```text
Execution → SUCCESS
+
ExecutionCompleted event
```

must be committed atomically.

---

# 211. Transaction

```text
BEGIN

update Execution

insert audit/event

insert OutboxMessage

COMMIT
```

---

# 212. Crash after commit

Evidence remains durable.

---

# 213. Consumer may receive duplicate event

EventId must allow deduplication.

---

# 214. AuditSink may consume duplicates

Should deduplicate using:

```text
event_id
```

---

# 215. Event delivery semantics

Likely:

```text
at-least-once
```

---

# 216. Event handling must be idempotent

---

# 217. Internal synchronous events

Some events may be handled in-process before commit?

Danger.

---

# 218. Rule

Side effects requiring durability should occur:

```text
after committed event/outbox
```

---

# 219. Pure in-memory reactions

Can exist if non-critical.

---

# 220. But no external alert before durable state if avoidable.

---

# 221. Alerting

Observability may lead to alerts.

---

# 222. Examples

```text
scheduler lag too high

runtime unhealthy

outbox backlog

retries exhausted spike

lease renewal failures

evaluation errors
```

---

# 223. Alert != Event

Alert is:

```text
operational interpretation of telemetry
```

---

# 224. Alert policies outside core domain

---

# 225. SLO

Possible future SLOs:

```text
99.9% of due occurrences evaluated within 5s

99.9% of requests dispatched within 10s

scheduler runtime available 99.95%
```

---

# 226. But SLO values are deployment-specific

Core exposes metrics, not universal thresholds.

---

# 227. Useful SLI

```text
schedule_evaluation_latency
```

---

# 228. Another SLI

```text
request_to_execution_start_latency
```

---

# 229. Another

```text
successful_execution_ratio
```

But note:

```text
target failures
```

may not reflect scheduler reliability.

---

# 230. Scheduler SLI versus workload SLI

Important distinction.

---

# 231. Scheduler health

Should measure:

```text
could scheduler evaluate and persist correctly?
```

---

# 232. Target health

Measures:

```text
did user workloads succeed?
```

---

# 233. Do not blame scheduler for all target failures

---

# 234. Dashboard layers

Potential dashboards:

```text
Scheduler Runtime

Scheduling Decisions

Execution Runtime

Retry/Failure

Distributed Coordination

Persistence/Outbox
```

---

# 235. Runtime dashboard

```text
cycle duration

scheduler lag

runtime state

next wake-up

evaluation errors
```

---

# 236. Scheduling dashboard

```text
due occurrences

misfires

skips

catch-up

coalescing

admission waits
```

---

# 237. Execution dashboard

```text
active executions

queue depth

success/failure rates

durations
```

---

# 238. Retry dashboard

```text
retry volume

success after retry

retries exhausted

retry delays
```

---

# 239. Distributed dashboard

```text
claim conflicts

lease losses

leader changes

fencing rejections
```

---

# 240. Persistence dashboard

```text
DB latency

transaction conflicts

outbox backlog
```

---

# 241. Event retention

Not all telemetry needs same retention.

---

# 242. Example

```text
metrics → weeks/months

logs → days/weeks

traces → sampled days

audit → months/years
```

---

# 243. RetentionPolicy

Deployment concern.

---

# 244. Audit retention may have compliance requirements

Framework should not hard-code them.

---

# 245. Data minimization

Long retention increases privacy/security exposure.

---

# 246. Audit payload must be intentionally minimal.

---

# 247. Event schema evolution

Events can live long.

Need:

```text
schema_version
```

---

# 248. Backward compatibility

Consumers should tolerate older compatible event versions.

---

# 249. EventType version versus schema version

Prefer stable event type:

```text
execution.completed
```

plus:

```text
schema_version
```

---

# 250. Avoid

```text
execution.completed.v2
```

unless necessary.

---

# 251. Unknown event version

Consumer must:

```text
fail safely
```

or ignore if non-critical.

---

# 252. Audit parser

Should not guess fields from future schema.

---

# 253. Observability availability

Metrics backend can fail.

Should scheduler stop?

---

# 254. Usually no

Failure to emit:

```text
metric
trace
debug log
```

should not break scheduling correctness.

---

# 255. Audit may be different

If durable audit is a hard compliance requirement, mutation might require:

```text
audit record in same DB transaction
```

---

# 256. Distinguish telemetry criticality

```text
Best-effort telemetry

Durable required evidence
```

---

# 257. Best-effort

Examples:

```text
metrics

traces

debug logs
```

---

# 258. Durable evidence

Examples:

```text
critical scheduling decision audit

manual admin action audit
```

depending requirements.

---

# 259. V1 recommendation

Persist key decision evidence in same DB context when cheap.

Export metrics/traces best-effort.

---

# 260. Observability should never mutate domain decisions

Example:

```text
metrics exporter unavailable
```

must not turn:

```text
ADMIT
```

into:

```text
DROP
```

---

# 261. No feedback loop accidentally

Unless an explicit future policy uses telemetry.

---

# 262. Logging failures

Logging sink failure should be isolated.

---

# 263. Avoid recursive logging failure

Classic anti-pattern.

---

# 264. Trace sampling

High-volume scheduling may require sampling.

---

# 265. Never sample required audit evidence

---

# 266. Head sampling

Could sample ordinary successful traces.

---

# 267. Keep failed traces

Often useful.

---

# 268. Tail sampling

Infrastructure-specific.

---

# 269. Event sampling

Domain/audit events generally should not be randomly sampled if relied on for history.

---

# 270. Metrics derived from sampled traces are unreliable

Use native metric recording.

---

# 271. Decision audit volume

High-frequency schedules can create huge audit volume.

---

# 272. Possible batching

Example:

```text
100 occurrences skipped
```

could produce:

```text
one batch audit record
```

---

# 273. But preserve enough identity

For strict audit use cases, individual records may still be required.

---

# 274. Configurable audit verbosity

Future option:

```text
MINIMAL

STANDARD

VERBOSE
```

---

# 275. Not a domain policy

Operational configuration.

---

# 276. V1

Use `STANDARD`.

Persist:

```text
major Schedule lifecycle

request creation

execution completion

misfire skip

retry exhausted

manual commands
```

---

# 277. Logs fill the rest

---

# 278. Event correlation across Py*Kit

Example:

```text
PyScheduleKit
Occurrence 06:00
CorrelationId C123
```

then:

```text
PyWorkflowKit
WorkflowRun W42
CorrelationId C123
```

then:

```text
PyIngestKit
Ingestion I9
CorrelationId C123
```

---

# 279. End-to-end tracing

Possible without shared database.

---

# 280. This is the right integration boundary

```text
identifiers + context
```

not:

```text
cross-framework foreign keys
```

---

# 281. ExternalExecutionRef

Audit can relate:

```text
ExecutionId
→ ExternalExecutionRef
```

---

# 282. Example

```text
exec-42
→ workflow-run-918
```

---

# 283. Diagnostics across frameworks

PyScheduleKit can say:

```text
"Execution submitted successfully to workflow-run-918"
```

Then deeper step diagnostics belong to PyWorkflowKit.

---

# 284. Respect bounded contexts

Do not duplicate downstream internals.

---

# 285. Failure boundaries

If WorkflowRun fails:

PyScheduleKit may see:

```text
ExternalExecution FAILED
```

with reference.

---

# 286. Detailed step failure

Remains downstream responsibility.

---

# 287. `Explain` API future

Potential public application service:

```text
explain_schedule(schedule_id)

explain_occurrence(occurrence_key)

explain_execution(execution_id)
```

---

# 288. ExplainSchedule

Could summarize:

```text
definition

state

next run

recent decisions

recent failures
```

---

# 289. ExplainOccurrence

Could show:

```text
Trigger candidate

calendar validation

misfire classification

concurrency decision

request/execution relationship
```

---

# 290. ExplainExecution

Could show:

```text
request source

attempts

retry chain

terminal result
```

---

# 291. This is highly aligned with PyScheduleKit's learning goal

The framework becomes not only executable but:

```text
inspectable
```

---

# 292. Explainability as first-class design goal

Recommended.

---

# 293. Observability interfaces

Possible package:

```text
pyschedulekit/
├── domain/
│   └── events/
├── application/
│   ├── diagnostics/
│   └── explain/
├── ports/
│   ├── audit_sink.py
│   ├── event_sink.py
│   └── telemetry.py
└── infrastructure/
    └── observability/
        ├── logging/
        ├── metrics/
        ├── tracing/
        └── audit/
```

---

# 294. Avoid direct dependency on Prometheus

Metrics adapter handles it.

---

# 295. Avoid direct dependency on OpenTelemetry in domain

Tracing adapter handles it.

---

# 296. Python logging

Can be default structured logging backend.

---

# 297. AuditStore

Port possible:

```text
AuditRepository
```

if audit is queryable durable data.

---

# 298. EventStore naming caution

Don't call it EventStore if not event-sourcing to avoid confusion.

---

# 299. Better

```text
EventRecordRepository
```

or:

```text
AuditRepository
```

---

# 300. Diagnostics may be computed

Not all Diagnostics need persistence.

---

# 301. Persistent diagnostics

Useful for:

```text
terminal failures

corruption

critical distributed conflicts
```

---

# 302. Ephemeral diagnostics

Useful for:

```text
inspect command

health check
```

---

# 303. Diagnostic source

Can combine:

```text
current state

recent audit

runtime metrics
```

---

# 304. State snapshots should not be events by default

Avoid storing full state repeatedly unless required.

---

# 305. DecisionEvidence versus StateSnapshot

```text
DecisionEvidence
→ why a decision happened

StateSnapshot
→ what state exists now
```

---

# 306. Both useful.

---

# 307. Audit immutability

If storage supports it, audit rows should be:

```text
append-only
```

---

# 308. No normal UPDATE

---

# 309. Deletion

Only retention/administrative policy.

---

# 310. Manual action auditing

Commands:

```text
pause

resume

reschedule

cancel

rerun
```

should capture:

```text
actor

timestamp

reason?
```

---

# 311. Reason for manual action

Optional but useful.

---

# 312. Example

```text
SchedulePaused
actor=user:42
reason="maintenance window"
```

---

# 313. Security-sensitive event

Changes to:

```text
TargetRef

credentials references

execution permissions
```

may need stronger audit.

---

# 314. Not core V1 security model

But audit supports future controls.

---

# 315. Event consistency

A domain event should correspond to:

```text
committed state
```

before external publication.

---

# 316. Outbox again

```text
state mutation
+
event/outbox
```

same transaction.

---

# 317. Logs can happen before commit

But should make transaction outcome clear.

---

# 318. Example bad log

```text
"Execution completed successfully"
```

before commit.

If commit fails, log lies.

---

# 319. Better

Before commit:

```text
"Attempt result received"
```

After commit:

```text
"Execution state committed: SUCCESS"
```

---

# 320. Commit-aware observability

Very important for distributed systems.

---

# 321. Audit only after/with durable state

---

# 322. Metrics before commit?

A counter can be slightly approximate.

But for critical numbers:

```text
prefer post-commit
```

---

# 323. Metrics are not accounting ledger

Small telemetry inaccuracies can be tolerable.

---

# 324. Audit cannot tolerate same looseness.

---

# 325. NodeId propagation

Distributed events should include:

```text
node_id
```

when relevant.

---

# 326. WorkerId

Attempt events may include:

```text
worker_id
```

---

# 327. SchedulerNodeId

Schedule evaluation events may include:

```text
scheduler_node_id
```

---

# 328. Don't use NodeId as domain identity

Operational metadata only.

---

# 329. Leadership epoch

Coordination diagnostics may include:

```text
fencing_token

leadership_epoch
```

---

# 330. Audit answer example

Question:

```text
Why didn't schedule S execute at 10:00?
```

Possible answer:

```text
Schedule S revision 7 produced occurrence 10:00.

Scheduler node B evaluated it at 10:12.

The occurrence was 12 minutes late.

GracePeriod was 5 minutes.

MisfirePolicy was SKIP.

Decision: MISFIRE_SKIP.

No ExecutionRequest was created.
```

---

# 331. Another example

```text
Why hasn't execution started?
```

Answer:

```text
Request req-10 exists.

ConcurrencyKey = billing-close.

Limit = 1.

Execution exec-9 is still active.

Request state = WAITING_ADMISSION.
```

---

# 332. Another example

```text
Why did execution fail?
```

Answer:

```text
3 Attempts were performed.

Attempt #1: timeout.

Attempt #2: dependency unavailable.

Attempt #3: dependency unavailable.

MaxAttempts = 3.

RetryDecision = STOP.

Execution state = FAILED.
```

---

# 333. Another example

```text
Why did node B process this schedule?
```

Answer:

```text
Node B acquired Schedule claim after node A released/expired ownership.
```

---

# 334. Observability enables trust

A scheduling framework is much easier to operate when it can:

```text
explain itself
```

---

# 335. Deterministic decision codes

Every policy outcome should ideally have:

```text
stable reason codes
```

---

# 336. Why stable?

They become:

```text
API contracts

audit values

metrics dimensions

tests
```

---

# 337. ReasonCode taxonomy

Could be namespaced:

```text
MISFIRE_GRACE_EXCEEDED

CATCHUP_LIMIT_REACHED

CONCURRENCY_LIMIT_REACHED

RETRY_MAX_ATTEMPTS

EXECUTION_DEADLINE_EXCEEDED
```

---

# 338. Do not over-generalize one giant enum

Better separate:

```text
SchedulingDecisionReason

AdmissionReason

RetryReason

ExecutionCompletionReason
```

---

# 339. Strong typing

Improves clarity.

---

# 340. Human message should not be persisted as sole evidence

Messages may change with localization/version.

---

# 341. Persist reason codes and structured fields.

---

# 342. Internationalization

Future UIs can translate messages from reason codes.

---

# 343. Event payload minimization

Only include needed fields.

Avoid embedding entire Aggregate state.

---

# 344. Why?

```text
event bloat

sensitive data

coupling
```

---

# 345. Reference over duplication

Use IDs/keys plus critical snapshot data.

---

# 346. When snapshot is required

If future state changes would make event uninterpretable.

Example:

```text
ScheduleRevision
```

must be included.

---

# 347. Failure payload

Store normalized failure, not giant exception object.

---

# 348. Metrics cardinality test

V1 acceptance should review every metric label.

---

# 349. Rule

If label values grow with:

```text
users

schedules

executions

requests
```

it is probably unsuitable as a metric label.

---

# 350. Use logs/traces for IDs

---

# 351. Observability failure isolation

If metrics export blocks for 30s, scheduler must not block 30s.

---

# 352. Async/buffered telemetry adapters

Recommended for production.

---

# 353. Backpressure

Telemetry system may be overloaded.

---

# 354. Best-effort telemetry can drop data

With counters:

```text
exporter may aggregate
```

---

# 355. Durable audit must not silently drop

---

# 356. Audit failure handling

If audit is mandatory:

```text
transaction should fail
```

or:

```text
audit should be persisted in same authoritative DB
```

---

# 357. V1 recommendation

Use same DB for critical audit/event evidence.

Export externally later.

---

# 358. This avoids distributed dual-write.

---

# 359. Event dispatcher

After commit:

```text
OutboxPublisher
```

can send event to:

```text
Kafka

NATS

Webhook

other systems
```

future.

---

# 360. Core doesn't care which.

---

# 361. Trace/Event correlation

Published events can include:

```text
traceparent
```

or generic trace context.

---

# 362. But do not make W3C trace headers domain fields

Keep in telemetry/context metadata.

---

# 363. Runtime health diagnostics

Health check can produce:

```text
HEALTHY

DEGRADED

UNHEALTHY
```

---

# 364. Example degraded

```text
runtime running

but oldest due schedule lag = 120s
```

---

# 365. Example unhealthy

```text
no successful evaluation cycle for 5 minutes
```

threshold deployment-specific.

---

# 366. Health reason codes

```text
SCHEDULER_LAG_HIGH

PERSISTENCE_UNAVAILABLE

OUTBOX_STALLED

LEASE_RENEWAL_FAILURES
```

---

# 367. HealthStatus should contain reasons

Not only boolean.

---

# 368. RuntimeHealth

Possible:

```text
RuntimeHealth
│
├── status
├── checked_at
├── reasons[]
├── last_successful_cycle_at
└── lag
```

---

# 369. Health is a snapshot

Not durable domain history by default.

---

# 370. Alert evidence

When alert fires, operator should be able to navigate to:

```text
diagnostic context
```

---

# 371. Observability navigation model

From:

```text
ScheduleId
```

navigate to:

```text
Occurrences
Requests
Executions
Attempts
Events
```

---

# 372. From ExecutionId

Navigate to:

```text
source occurrence

attempt history

audit records

trace
```

---

# 373. This informs future UI/CLI API design.

---

# 374. Indexing for audit

Query by:

```text
subject_id

correlation_id

occurred_at
```

should be efficient.

---

# 375. High-volume retention partitions

Future DB may partition:

```text
event/audit table by time
```

---

# 376. Not V1.

---

# 377. Clock correctness in observability

Use explicit:

```text
occurred_at
```

from Clock/context.

---

# 378. `logged_at`

Can differ from:

```text
occurred_at
```

---

# 379. Example delayed event publication

```text
occurred_at = 10:00

published_at = 10:05
```

---

# 380. Both useful.

---

# 381. Event timing fields

Potential:

```text
occurred_at

recorded_at

published_at
```

---

# 382. Do not collapse them.

---

# 383. Event duplication

Consumer may see same event twice.

Use:

```text
event_id
```

deduplication.

---

# 384. Event ordering across retry

Use:

```text
aggregate_version
```

for Execution history.

---

# 385. Example

```text
v1 ExecutionCreated

v2 AttemptStarted

v3 RetryScheduled

v4 AttemptStarted

v5 ExecutionCompleted
```

---

# 386. Missing event detection

If version jumps:

```text
3 → 5
```

consumer may know it missed something.

---

# 387. But not all consumers require complete stream.

---

# 388. Audit ingestion should prefer completeness.

---

# 389. Diagnostics and event version

Diagnostic derived today from old events must understand old schemas.

---

# 390. This motivates stable reason codes.

---

# 391. Testing events

Every domain transition should test:

```text
expected event emitted
```

when event is part of contract.

---

# 392. Test SchedulePaused

Expected event:

```text
SchedulePaused
```

with correct ScheduleId and revision.

---

# 393. Test misfire

Expected:

```text
decision evidence
```

contains lateness and reason.

---

# 394. Test retry

Expected:

```text
RetryScheduled
```

with correct next_attempt_at.

---

# 395. Test terminal failure

Expected:

```text
ExecutionCompleted
outcome=FAILED
```

---

# 396. Test duplicate result

Should not emit two terminal events.

---

# 397. Test optimistic conflict

Failed transaction should not publish committed event.

---

# 398. Test rollback

Audit/outbox inserted in rolled-back transaction must disappear.

---

# 399. Test Outbox duplicate publish

Consumer deduplicates EventId.

---

# 400. Test redaction

Sensitive fields removed.

---

# 401. Test metric cardinality

Ensure IDs not used as labels in default metrics.

---

# 402. Test correlation propagation

Request → Execution → Attempt share expected CorrelationId.

---

# 403. Test Trace propagation

Executor receives trace context.

---

# 404. Test node evidence

Distributed claim event includes NodeId.

---

# 405. Test fencing diagnostic

Stale token produces:

```text
FENCING_REJECTED
```

diagnostic.

---

# 406. Test explain occurrence

Given stored decision evidence, explanation must be deterministic.

---

# 407. Test explain execution

Attempts ordered and retry chain correct.

---

# 408. Test clock values

Audit timestamps timezone-aware.

---

# 409. Observability contract tests

Adapters:

```text
InMemoryEventSink

InMemoryAuditStore

FakeMetricsRecorder

FakeTracer
```

can support deterministic testing.

---

# 410. Production adapters

Potential:

```text
Python logging

OpenTelemetry

Prometheus-compatible metrics

SQL audit store
```

---

# 411. No mandatory external telemetry stack

Framework remains lightweight.

---

# 412. Default local observability

V1 can provide:

```text
structured Python logs

in-memory metrics

SQL audit/events

simple diagnostics
```

---

# 413. JSON logging optional.

---

# 414. Developer mode

Can expose verbose planner details.

---

# 415. Production mode

Can reduce noise.

---

# 416. Audit always separate from debug verbosity.

---

# 417. Event severity?

Domain events generally should not have:

```text
log severity
```

intrinsically.

---

# 418. Why?

`ExecutionFailed` is a fact.

Whether it is:

```text
WARNING
or ERROR
```

depends on operational policy.

---

# 419. Keep event semantics clean.

---

# 420. Diagnostic severity may vary

Diagnostic is interpretation, so severity belongs there.

---

# 421. Event naming past tense

Because event records:

```text
something already happened
```

---

# 422. Commands remain imperative

```text
PauseSchedule

CancelExecution
```

---

# 423. Events

```text
SchedulePaused

ExecutionCancelled
```

---

# 424. CommandId future

Can be useful for manual operations.

---

# 425. Command-to-event chain

```text
CommandId
↓
CausationId
↓
EventId
```

---

# 426. Manual command audit

Could record:

```text
command_id

actor

reason
```

---

# 427. Future API benefit

Users can ask:

```text
What happened to command C42?
```

---

# 428. Not required V1.

---

# 429. Event consistency with state machine

No event should imply an impossible transition.

---

# 430. Example

Never publish:

```text
ExecutionSucceeded
```

if persisted state is:

```text
FAILED
```

---

# 431. State and event commit together.

---

# 432. Audit reconstruction

Given one Execution, history may look:

```text
ExecutionCreated
AttemptStarted #1
AttemptFailed #1
RetryScheduled
AttemptStarted #2
AttemptSucceeded #2
ExecutionCompleted SUCCESS
```

---

# 433. This history is intuitive and useful.

---

# 434. Schedule history example

```text
ScheduleCreated rev1
ScheduleRescheduled rev2
SchedulePaused
ScheduleResumed
ScheduleCancelled
```

---

# 435. Scheduling decision history example

```text
10:00 EXECUTE
11:00 EXECUTE
12:00 MISFIRE_SKIP
13:00 EXECUTE
```

---

# 436. Excellent for timeline UI

Future web UI can render this naturally.

---

# 437. Event payload and UI

Do not design event payload solely for UI.

Use stable semantic facts.

---

# 438. UI can build view models.

---

# 439. Diagnostic query performance

Avoid joining entire history for ordinary health check.

Use projections.

---

# 440. Read models

Future:

```text
ScheduleStatusView

ExecutionSummaryView

RuntimeHealthView
```

---

# 441. These are query models, not domain aggregates.

---

# 442. Observability and CQRS

A lightweight read-model architecture fits naturally.

---

# 443. But V1 can query normalized tables directly.

---

# 444. Observability data as integration surface

External platforms may consume:

```text
ExecutionCompleted
```

---

# 445. Therefore events should be versioned carefully.

---

# 446. Public versus internal events

Important distinction.

---

# 447. Internal event

Can evolve faster.

---

# 448. Public integration event

Requires compatibility guarantees.

---

# 449. Example

```text
ExecutionCompleted
```

may become public.

---

# 450. `ScheduleClaimAcquired`

probably internal.

---

# 451. Event visibility

Possible:

```text
INTERNAL

PUBLIC
```

metadata.

---

# 452. V1

Document classification rather than implementing field.

---

# 453. Audit immutability and user deletion

If future privacy law requires deletion/anonymization, append-only audit may need:

```text
pseudonymized actor references
```

---

# 454. Framework should avoid storing unnecessary personal details.

---

# 455. Secret-safe Event payloads

Same rule as logs.

---

# 456. Exception representation

Failure details can include:

```text
exception_class

safe_message

fingerprint
```

not raw object.

---

# 457. Technical traceback storage

Optional debug sink with restricted access.

---

# 458. V1 recommended event catalogue

## Schedule

```text
ScheduleCreated
SchedulePaused
ScheduleResumed
ScheduleRescheduled
ScheduleCancelled
ScheduleCompleted
```

---

# 459. Scheduling

```text
OccurrenceSkipped
OccurrencesCoalesced
ExecutionRequestCreated
ExecutionRequestDeferred
ExecutionRequestCancelled
```

---

# 460. Execution

```text
ExecutionCreated
AttemptStarted
AttemptCompleted
RetryScheduled
ExecutionCompleted
```

---

# 461. Runtime

```text
SchedulerRuntimeStarted
SchedulerRuntimeStopped
EvaluationCycleFailed
```

---

# 462. Coordination

```text
LeaseLost
LeadershipChanged
FencingRejected
```

only when distributed mode used.

---

# 463. Why compact catalogue?

Avoid event explosion.

---

# 464. `AttemptCompleted`

Can carry outcome:

```text
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

rather than four event classes if desired.

---

# 465. Same for `ExecutionCompleted`

---

# 466. Trade-off

Specific event classes:

```text
more explicit
```

generic completion:

```text
smaller catalogue
```

---

# 467. V1 recommendation

Use:

```text
AttemptCompleted(outcome)
ExecutionCompleted(outcome)
```

---

# 468. Schedule events remain specific

Because lifecycle changes carry distinct semantics.

---

# 469. Decision event recommendation

Use:

```text
SchedulingDecisionRecorded
```

with typed:

```text
decision
reason
```

instead of dozens of occurrence-specific events.

---

# 470. This keeps model manageable.

---

# 471. Example V1 event set

```text
ScheduleCreated
ScheduleChanged
ScheduleStateChanged
SchedulingDecisionRecorded
ExecutionRequestCreated
ExecutionCreated
AttemptStarted
AttemptCompleted
RetryScheduled
ExecutionCompleted
RuntimeStateChanged
CoordinationEvent
```

---

# 472. Internal typed subcategories can refine later.

---

# 473. Event granularity must match useful questions.

---

# 474. V1 AuditRecord categories

```text
SCHEDULE

SCHEDULING_DECISION

EXECUTION

ATTEMPT

ADMIN

RUNTIME

COORDINATION
```

---

# 475. Observability V1 decisions

```text
1.
Current persisted state remains the authoritative truth.

2.
PyScheduleKit does not require Event Sourcing.

3.
Domain Events, Audit, Logs, Metrics, Traces
and Diagnostics remain separate concepts.

4.
Events use stable EventId and schema_version.

5.
CorrelationId connects Schedule → Request → Execution → Attempt.

6.
CausationId represents direct causal relationships.

7.
TraceId remains distinct from CorrelationId.

8.
SchedulingDecision evidence is first-class.

9.
Reason codes are machine-readable and stable.

10.
Important Schedule lifecycle changes are auditable.

11.
Misfire skips and terminal retry exhaustion
are auditable by default.

12.
Execution lifecycle history is observable.

13.
Audit records are append-only.

14.
Structured logging is preferred.

15.
Sensitive data is redacted.

16.
Metrics avoid high-cardinality identifiers.

17.
Traces may include high-cardinality IDs as attributes.

18.
Critical audit evidence is persisted transactionally
with related state where necessary.

19.
Metrics, traces and ordinary logs are best-effort.

20.
Outbox provides reliable external event publication.

21.
Duplicate event delivery is tolerated through EventId.

22.
Runtime, coordination and domain events are classified separately.

23.
Diagnostics use structured codes and evidence.

24.
Explain APIs are a first-class long-term goal.

25.
Observability failures must not silently alter
scheduling semantics.
```

---

# 476. Core invariants

```text
1.
An event never replaces persisted domain state.

2.
A committed domain transition never publishes
a contradictory event.

3.
Audit history is append-only.

4.
Every public/durable event has a stable EventId.

5.
Event schemas are versioned.

6.
Reason codes are not inferred from human text.

7.
Correlation identity is propagated across runtime boundaries.

8.
Secrets are never intentionally persisted
inside ordinary observability payloads.

9.
Metrics do not use unbounded IDs as default labels.

10.
A failed telemetry exporter does not invalidate
a committed scheduling decision.

11.
Required audit evidence must not be silently dropped.

12.
SchedulingDecision evidence retains enough context
to explain its outcome later.

13.
Timestamps are timezone-aware Instants.

14.
occurred_at and published_at are distinct when needed.

15.
Distributed ownership evidence includes NodeId
and fencing/epoch information where relevant.

16.
Terminal Execution history cannot be rewritten
by late results.

17.
Observability data follows the same bounded-context
boundaries as the domain.

18.
Downstream framework internals are referenced,
not duplicated.

19.
Explainability uses structured evidence,
not log-message parsing.

20.
Observability remains portable across telemetry vendors.
```

---

# 477. Acceptance criteria

Le modèle d'observabilité est suffisamment défini si PyScheduleKit peut répondre précisément à :

```text
Pourquoi cette occurrence n'a-t-elle pas été exécutée ?

Quelle policy a pris la décision ?

Quelle ScheduleRevision était active ?

L'occurrence était-elle en retard ?

Était-elle misfired ?

A-t-elle été coalescée ?

A-t-elle attendu un slot de concurrence ?

Une ExecutionRequest a-t-elle été créée ?

Quelle Execution correspond à cette occurrence ?

Combien d'Attempts ont été effectuées ?

Pourquoi un retry a-t-il été planifié ?

Pourquoi les retries se sont-ils arrêtés ?

Quelle erreur finale a été observée ?

Quel nœud scheduler a traité la décision ?

Quel worker a réalisé l'Attempt ?

Une Lease a-t-elle été perdue ?

Y a-t-il eu un fencing rejection ?

Quel est le lag actuel du scheduler ?

Le Runtime est-il sain ?

Quand a eu lieu le dernier cycle réussi ?

Quel est le backlog Outbox ?

Comment suivre une exécution à travers plusieurs Py*Kit ?

Comment reconstruire la timeline complète
sans parser des strings de logs ?
```

---

# 478. Modèle mental final

```text
                       DOMAIN STATE
                            │
                            ▼
                     Domain Decision
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
           Event          Audit       Diagnostic
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                       Application
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
       Logs              Metrics             Traces
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
                    OPERABILITY / EXPLAIN
```

---

# 479. Vue d'une occurrence expliquée

```text
Trigger
  │
  ▼
Occurrence 10:00
  │
  ▼
Evaluation at 10:12
  │
  ▼
lateness = 12m
  │
  ▼
GracePeriod = 5m
  │
  ▼
MisfirePolicy = SKIP
  │
  ▼
SchedulingDecision
  │
  ├── decision = SKIP
  ├── reason = MISFIRE_GRACE_EXCEEDED
  └── no ExecutionRequest
         │
         ▼
      Audit/Event
```

---

# 480. Vue d'une Execution expliquée

```text
Occurrence
    │
    ▼
ExecutionRequest
    │
    ▼
Execution
    │
    ├── Attempt #1 FAILED
    │       │
    │       ▼
    │   RetryScheduled
    │
    ├── Attempt #2 FAILED
    │       │
    │       ▼
    │   RetryScheduled
    │
    └── Attempt #3 SUCCESS
            │
            ▼
      ExecutionCompleted
            │
            ▼
           Audit
```

---

# 481. Vue distribuée

```text
Scheduler Node A
      │
      │ Trace / Correlation
      ▼
ExecutionRequest
      │
      ▼
Worker Node C
      │
      ▼
Attempt
      │
      ▼
External Target
```

avec propagation de :

```text
CorrelationId

TraceId

ExecutionId

AttemptId
```

---

# 482. Vue observabilité complète

```text
                              PyScheduleKit
                                   │
                 ┌─────────────────┼─────────────────┐
                 │                 │                 │
                 ▼                 ▼                 ▼
             Durable            Runtime          Decisions
              State              State
                 │                 │                 │
                 ▼                 ▼                 ▼
              Audit              Logs            Diagnostics
                 │                 │                 │
                 └────────┬────────┴────────┬────────┘
                          │                 │
                          ▼                 ▼
                       Metrics            Traces
                          │                 │
                          └────────┬────────┘
                                   ▼
                              OPERABILITY
```

---

# 483. Définition finale

> **Le modèle d’observabilité de PyScheduleKit transforme les décisions, transitions et anomalies du scheduler en preuves structurées permettant de comprendre, mesurer, corréler et diagnostiquer son comportement sans faire de la télémétrie une nouvelle source de vérité métier.**

---

# Conclusion

PyScheduleKit ne doit pas seulement savoir :

```text
quoi exécuter

et quand
```

Il doit aussi pouvoir répondre à :

```text
pourquoi

comment

par qui

avec quelle policy

avec quel résultat

et avec quelle preuve
```

La chaîne complète devient :

```text
Schedule
   │
   ▼
Occurrence
   │
   ▼
SchedulingDecision
   │
   ├── ReasonCode
   ├── DecisionEvidence
   └── Audit
   │
   ▼
ExecutionRequest
   │
   ▼
Execution
   │
   ▼
Attempt
   │
   ▼
Result / Failure
```

et tout au long de cette chaîne :

```text
CorrelationId
Events
Audit
Logs
Metrics
Traces
Diagnostics
```

rendent le comportement explicable.

Le principe central est :

> **L’état durable dit ce qui est vrai ; l’observabilité explique comment et pourquoi cet état est devenu vrai.**

Cette distinction permet d'éviter deux extrêmes :

```text
un scheduler opaque
```

et :

```text
un scheduler où la vérité métier dépend des logs
```

La cible de PyScheduleKit devient donc un moteur :

```text
observable

auditable

diagnosticable

corrélable

expliquable
```

sans sacrifier la séparation des responsabilités.

---

# Suite documentaire

La prochaine étape logique est :

```text
22_PUBLIC_API_AND_CONFIGURATION_MODEL.md
```

Elle devra transformer les concepts désormais stabilisés en expérience développeur :

```text
Scheduler API

ScheduleBuilder

TargetRef API

Trigger construction

DateTrigger

IntervalTrigger

CronTrigger

policies

runtime configuration

persistence configuration

executor registration

serialization

validation

exceptions

sync API

future async API
```

et répondre à :

> **À quoi doit réellement ressembler l'utilisation de PyScheduleKit par un développeur sans lui exposer toute la complexité interne que nous venons de modéliser ?**

Après le **22**, la documentation pourra naturellement entrer dans une nouvelle phase :

```text
23_TARGET_ARCHITECTURE.md

24_PUBLIC_API_SPEC.md

25_ERROR_MODEL.md

26_SECURITY_AND_CONFIGURATION_POLICY.md

27_TEST_MATRIX_AND_ACCEPTANCE_CRITERIA.md

28_IMPLEMENTATION_ROADMAP.md
```

c'est-à-dire le passage progressif du **modèle métier appris** à la **spécification concrète du framework**.