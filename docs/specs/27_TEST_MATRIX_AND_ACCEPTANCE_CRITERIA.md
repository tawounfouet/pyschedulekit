# PyScheduleKit — Test Matrix & Acceptance Criteria

**Document :** `27_TEST_MATRIX_AND_ACCEPTANCE_CRITERIA.md`  
**Projet :** PyScheduleKit  
**Statut :** Spécification de qualification et d’acceptation V1  
**Nature :** Verification & Validation — Test Strategy / Test Matrix / Release Gates / Acceptance Criteria  
**Langue :** Français

**Documents de référence :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
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

---

# 1. Objectif

PyScheduleKit dispose désormais d’un modèle détaillé de :

```text
Time

Trigger

Schedule

Occurrence

Misfire

Catch-Up

Concurrency

ExecutionRequest

Execution

Attempt

Retry

Runtime

Persistence

Outbox

Distributed Coordination

Observability

Public API

Errors

Security
```

Mais une architecture n’est pas considérée comme correcte parce qu’elle est :

```text
bien documentée
```

Elle doit être :

```text
prouvée
```

par des tests reproductibles.

La question centrale de ce document est donc :

> **Quelles preuves concrètes doivent être vertes avant que PyScheduleKit puisse considérer chacune de ses garanties comme réellement implémentée ?**

---

# 2. Principe directeur

Le modèle de test repose sur :

> **Chaque invariant important doit avoir au moins une preuve exécutable.**

Autrement dit :

```text
Documented invariant
        │
        ▼
Test scenario
        │
        ▼
Expected observable result
        │
        ▼
Automated evidence
```

---

# 3. Un test ne valide pas uniquement du code

Il valide :

```text
une sémantique
```

Exemple :

```text
IntervalTrigger every 24h
```

ne doit pas seulement :

```text
"retourner une datetime"
```

Il doit prouver que :

```text
24h elapsed duration
≠
1 civil calendar day
```

lors d’un changement DST.

---

# 4. Testability as Architecture

La testabilité est une propriété d’architecture.

Si tester un comportement nécessite :

```text
attendre réellement 24 heures

modifier l’horloge système

démarrer PostgreSQL pour chaque test métier

faire de vraies requêtes HTTP
```

alors les frontières architecturales sont probablement mauvaises.

---

# 5. Test Pyramid cible

PyScheduleKit utilisera plusieurs niveaux :

```text
                    E2E
                     ▲
                 Runtime
                     ▲
               Integration
                     ▲
             Contract Tests
                     ▲
             Application Tests
                     ▲
               Domain Tests
```

---

# 6. Niveau 1 — Domain Unit Tests

Doivent être :

```text
très rapides

déterministes

sans I/O

sans sleep

sans DB

sans réseau
```

Ils couvrent notamment :

```text
Value Objects

Triggers

Policies

State Machines

Domain Services
```

---

# 7. Niveau 2 — Application Tests

Testent :

```text
SchedulerEngine

ScheduleService

ExecutionService

CatchUpPlanner

RuntimeReconciler
```

avec :

```text
FakeClock

InMemoryUnitOfWork

FakeExecutor
```

---

# 8. Niveau 3 — Contract Tests

Vérifient que plusieurs adapters respectent :

```text
le même contrat
```

Exemple :

```text
InMemoryScheduleRepository

SQLiteScheduleRepository

PostgreSQLScheduleRepository
```

doivent réussir :

```text
la même suite de contrats
```

---

# 9. Niveau 4 — Integration Tests

Utilisent de vraies technologies :

```text
SQLite

PostgreSQL

threads

transactions

locks
```

pour tester :

```text
atomicité

concurrence

uniqueness

crash consistency
```

---

# 10. Niveau 5 — Runtime Tests

Valident :

```text
wake-up

polling

shutdown

runtime lifecycle

backoff

recovery
```

---

# 11. Niveau 6 — End-to-End Tests

Valident une chaîne complète :

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
↓
Result
```

---

# 12. Niveau 7 — Distributed Tests

Valident :

```text
multi-scheduler

multi-worker

claim races

leases

fencing

failover
```

---

# 13. Niveau 8 — Security Tests

Valident :

```text
safe serialization

target restrictions

secret redaction

config validation

unsafe payload rejection
```

---

# 14. Test IDs

Chaque scénario important reçoit un identifiant stable.

Convention proposée :

```text
T-<DOMAIN>-<NUMBER>
```

Exemples :

```text
T-TIME-001

T-TRG-010

T-PER-005

T-DIST-014
```

---

# 15. Catégories d’IDs

```text
TIME   → temps

TRG    → triggers

SCH    → schedule

MIS    → misfire

CAT    → catch-up

CON    → concurrency

EXE    → execution

RET    → retry

RUN    → runtime

PER    → persistence

OUT    → outbox

DIST   → distributed coordination

OBS    → observability

API    → public API

ERR    → errors

SEC    → security

E2E    → end-to-end

PERF   → performance/resilience
```

---

# 16. Criticité

Chaque test peut être :

```text
P0 — invariant critique de correction

P1 — comportement fonctionnel majeur

P2 — comportement secondaire

P3 — confort / ergonomie / diagnostics
```

---

# 17. Release Gate

Tout test :

```text
P0
```

est :

```text
release-blocking
```

---

# 18. P1

Également bloquant pour une release stable.

---

# 19. P2

Peut éventuellement être :

```text
known limitation
```

sur une alpha, mais doit être documenté.

---

# 20. P3

Peut être différé selon roadmap.

---

# 21. Determinism Rule

Un test V1 ne doit pas dépendre de :

```text
l'heure réelle

la vitesse CPU

un sleep arbitraire

un hasard non seedé
```

lorsqu’une abstraction existe.

---

# 22. FixedClock

La plupart des tests temporels utiliseront :

```text
FixedClock
```

---

# 23. MutableClock

Les scénarios de progression utiliseront :

```text
MutableClock
```

---

# 24. MonotonicClock

Les tests de runtime sleep utilisent :

```text
FakeMonotonicClock
```

ou abstraction équivalente.

---

# 25. No `time.sleep()` in Domain Tests

Invariant de test :

```text
domain tests
never call real sleep
```

---

# 26. SchedulerHarness

Un outil de test de premier ordre est recommandé :

```text
SchedulerHarness
```

---

# 27. Exemple

```python
harness = SchedulerHarness(
    start_at="2026-01-01T10:00:00Z",
)

harness.add_schedule(
    target=fake_target,
    trigger=IntervalTrigger(minutes=10),
)

harness.advance("10m")
harness.run_pending()

assert harness.executions_count() == 1
```

---

# 28. Harness Scope

Le Harness peut fournir :

```text
MutableClock

InMemoryPersistence

FakeExecutor

Runtime driver

Inspection helpers
```

---

# 29. Mais

Le Harness ne doit pas :

```text
modifier les règles métier
```

---

# 30. Même SchedulerEngine

Il doit exécuter :

```text
le vrai SchedulerEngine
```

avec des adapters de test.

---

# 31. Matrice globale

| Domaine | Unit | Application | Contract | Integration | E2E |
|---|---:|---:|---:|---:|---:|
| Time | ✓ | ✓ |  |  | ✓ |
| Triggers | ✓ | ✓ | ✓ codec |  | ✓ |
| Schedule | ✓ | ✓ | ✓ repository | ✓ | ✓ |
| Misfire/Catch-Up | ✓ | ✓ |  | ✓ | ✓ |
| Concurrency | ✓ | ✓ | ✓ coordinator | ✓ | ✓ |
| Retry | ✓ | ✓ |  | ✓ | ✓ |
| Execution | ✓ | ✓ | ✓ repository | ✓ | ✓ |
| Runtime |  | ✓ | ✓ runtime ports | ✓ | ✓ |
| Persistence |  | ✓ | ✓ | ✓ | ✓ |
| Distributed | ✓ | ✓ | ✓ | ✓ | ✓ |
| Observability | ✓ | ✓ | ✓ | ✓ | ✓ |
| Security | ✓ | ✓ | ✓ | ✓ | ✓ |

---

# 32. TIME — Core Test Matrix

---

# 33. T-TIME-001 — Instant timezone-aware

**Priorité :** P0

Given :

```text
timezone-aware datetime
```

When :

```text
Instant is created
```

Then :

```text
accepted
```

---

# 34. T-TIME-002 — Naive datetime rejected

Given :

```python
datetime(2026, 1, 1, 10, 0)
```

Then :

```text
ValidationError
```

avec :

```text
NAIVE_DATETIME_NOT_ALLOWED
```

---

# 35. T-TIME-003 — Same instant, different timezone representation

```text
10:00 UTC
=
11:00 Europe/Paris
```

si offsets correspondants.

---

# 36. T-TIME-004 — Timezone does not equal fixed offset

Verifier que :

```text
Europe/Paris
```

n’est pas modélisé comme :

```text
UTC+1 forever
```

---

# 37. T-TIME-005 — Duration 24h across DST

Prouver :

```text
24 elapsed hours
```

n’est pas forcément :

```text
same local clock time next day
```

---

# 38. T-TIME-006 — Same Clock value within evaluation

Toutes les décisions d’un même evaluation context utilisent :

```text
same now
```

---

# 39. T-TIME-007 — Clock dependency explicit

Le domaine ne doit jamais appeler directement :

```python
datetime.now()
```

---

# 40. Architecture fitness check

CI peut rechercher :

```text
datetime.now(
```

hors adapters autorisés.

---

# 41. T-TIME-008 — System timezone independence

Le résultat d’un test ne change pas selon :

```text
TZ host environment
```

---

# 42. T-TIME-009 — TimeWindow boundaries

Si convention :

```text
[start, end)
```

alors :

```text
start accepted

end rejected
```

---

# 43. T-TIME-010 — DST nonexistent local time

Tester un horaire comme :

```text
02:30
```

le jour d’un saut DST.

Le comportement doit suivre :

```text
DSTResolutionPolicy
```

documentée.

---

# 44. T-TIME-011 — DST ambiguous local time

Tester heure répétée lors du retour DST.

---

# 45. T-TIME-012 — Leap year

```text
2028-02-29
```

doit être correctement traité.

---

# 46. TRIGGER — DateTrigger

---

# 47. T-TRG-001 — DateTrigger emits one occurrence

Given :

```text
at = T
```

Then :

```text
next_after(T - ε) = T
```

---

# 48. T-TRG-002 — DateTrigger exhausted

```text
next_after(T) = None
```

si contrat strictement supérieur.

---

# 49. T-TRG-003 — DateTrigger immutable

Après construction :

```text
at
```

ne peut pas être muté.

---

# 50. IntervalTrigger

---

# 51. T-TRG-010 — Positive interval required

```text
interval <= 0
```

→ ValidationError.

---

# 52. T-TRG-011 — Exact progression

Given :

```text
anchor = 10:00
interval = 10m
```

Expected :

```text
10:00
10:10
10:20
...
```

---

# 53. T-TRG-012 — Strictly increasing

Property :

```text
next_after(x) > x
```

pour tout `x`.

---

# 54. T-TRG-013 — No cumulative drift

Après 10 000 occurrences :

```text
anchor + n*interval
```

reste exact selon représentation temporelle.

---

# 55. T-TRG-014 — Interval does not use last actual execution

Une exécution détectée en retard à :

```text
10:12
```

ne décale pas le prochain fixed-rate vers :

```text
10:22
```

si plan initial :

```text
10:10
10:20
```

---

# 56. T-TRG-015 — Large reference O(1) behavior

Le calcul de prochaine occurrence ne doit pas nécessiter :

```text
itérer depuis l'anchor occurrence par occurrence
```

pour IntervalTrigger.

---

# 57. CronTrigger

---

# 58. T-TRG-020 — Basic daily cron

```text
0 6 * * *
```

produit :

```text
06:00
```

dans timezone effective.

---

# 59. T-TRG-021 — Five fields only V1

Une expression à six champs est :

```text
rejected
```

si V1 reste cinq champs.

---

# 60. T-TRG-022 — Invalid minute

```text
60 * * * *
```

rejeté.

---

# 61. T-TRG-023 — Invalid hour

```text
0 24 * * *
```

rejeté.

---

# 62. T-TRG-024 — Month boundaries

Cron traverse correctement :

```text
January → February
```

---

# 63. T-TRG-025 — Leap day

Expression ciblant :

```text
29 February
```

doit trouver la prochaine année bissextile.

---

# 64. T-TRG-026 — Search horizon

Une expression extrêmement rare ne peut pas provoquer :

```text
infinite search
```

---

# 65. T-TRG-027 — DOM/DOW semantics

Le comportement entre :

```text
day-of-month
```

et :

```text
day-of-week
```

doit correspondre exactement au dialecte documenté.

---

# 66. T-TRG-028 — Cron DST forward

Tester un cron dans une heure inexistante.

---

# 67. T-TRG-029 — Cron DST backward

Tester un cron dans une heure ambiguë.

---

# 68. T-TRG-030 — Cron deterministic serialization

```text
serialize
→ deserialize
```

produit une expression sémantiquement équivalente.

---

# 69. Trigger Property Tests

Property-based testing recommandé.

Propriétés :

```text
next_after(x) > x

sequence monotonic

serialization round-trip stable

no infinite loop within configured horizon
```

---

# 70. Custom Trigger Conformance

Toute extension future doit passer :

```text
TriggerContractSuite
```

---

# 71. Schedule Aggregate Tests

---

# 72. T-SCH-001 — Create valid Schedule

Résultat :

```text
state = ACTIVE

revision = 1

PersistenceVersion initial valid

next_run_time computed
```

---

# 73. T-SCH-002 — Pause active Schedule

```text
ACTIVE → PAUSED
```

---

# 74. T-SCH-003 — Pause paused Schedule

Doit être :

```text
idempotent
```

selon Public API V1.

---

# 75. T-SCH-004 — Resume paused Schedule

```text
PAUSED → ACTIVE
```

et :

```text
next_run_time recalculated
```

---

# 76. T-SCH-005 — Resume cancelled Schedule

Doit lever :

```text
InvalidScheduleTransitionError
```

---

# 77. T-SCH-006 — Cancel active

```text
ACTIVE → CANCELLED
```

---

# 78. T-SCH-007 — Cancel already cancelled

Idempotent.

---

# 79. T-SCH-008 — Trigger exhausted

Schedule devient :

```text
COMPLETED
```

avec :

```text
next_run_time = None
```

---

# 80. T-SCH-009 — Reschedule increments revision

```text
revision N
→
revision N+1
```

---

# 81. T-SCH-010 — Operational next-run update does not increment ScheduleRevision

Seule :

```text
PersistenceVersion
```

avance.

---

# 82. T-SCH-011 — Reschedule preserves ScheduleId

---

# 83. T-SCH-012 — Existing Execution unaffected by reschedule

Execution créée sous revision 3 conserve :

```text
revision 3 context
```

même si Schedule devient revision 4.

---

# 84. T-SCH-013 — Pause does not cancel active execution

---

# 85. T-SCH-014 — Cancel Schedule does not cancel active Execution

---

# 86. T-SCH-015 — Effective timezone frozen in definition

Changer :

```text
Scheduler.default_timezone
```

plus tard ne modifie pas Schedule existant.

---

# 87. Occurrence Tests

---

# 88. T-SCH-020 — OccurrenceKey deterministic

Même :

```text
ScheduleId
ScheduleRevision
ScheduledAt
```

→ même OccurrenceKey.

---

# 89. T-SCH-021 — Different revisions produce different keys

---

# 90. T-SCH-022 — Occurrence scheduled_at immutable

---

# 91. Misfire Tests

---

# 92. T-MIS-001 — On-time

Given :

```text
evaluation_now <= scheduled_at + grace
```

classification :

```text
eligible
```

---

# 93. T-MIS-002 — Misfire beyond grace

```text
evaluation_now > deadline
```

classification :

```text
MISFIRED
```

---

# 94. T-MIS-003 — SKIP

Misfired occurrence :

```text
no ExecutionRequest
```

---

# 95. T-MIS-004 — RUN_NOW

Request créée mais :

```text
scheduled_at remains original occurrence
```

---

# 96. T-MIS-005 — Misfire != Failure

Aucune :

```text
Attempt
```

n’est créée simplement parce qu’une occurrence est misfired.

---

# 97. T-MIS-006 — Misfire audit evidence

Doit contenir :

```text
scheduled_at

evaluated_at

lateness

grace

decision
```

---

# 98. Catch-Up Tests

---

# 99. T-CAT-001 — Reconstruct missed occurrences

Après outage :

```text
10:00
10:10
10:20
```

doivent être reconstruits selon Trigger.

---

# 100. T-CAT-002 — Oldest first

Catch-up traite :

```text
chronological order
```

---

# 101. T-CAT-003 — Max occurrences bound

```text
max_occurrences = 3
```

ne génère jamais plus de 3 Requests dans le plan courant.

---

# 102. T-CAT-004 — Catch-up does not create retries

Chaque occurrence :

```text
new logical occurrence
```

et non :

```text
retry same execution
```

---

# 103. T-CAT-005 — Coalesce latest

Missed :

```text
10:00
10:10
10:20
```

avec :

```text
LATEST
```

produit une Request principale pour :

```text
10:20
```

avec provenance des autres.

---

# 104. T-CAT-006 — Deterministic coalescing

Re-evaluation du même backlog produit :

```text
same group selection
```

---

# 105. T-CAT-007 — Catch-up bounded under huge outage

Exemple :

```text
1-second schedule
offline 30 days
```

ne doit pas allouer des millions d’objets en mémoire.

---

# 106. Concurrency Policy Tests

---

# 107. T-CON-001 — ALLOW

Active count quelconque :

```text
ADMIT
```

si politique allow.

---

# 108. T-CON-002 — LIMIT below threshold

```text
active=0
limit=1
```

→ ADMIT.

---

# 109. T-CON-003 — LIMIT reached + DROP

→ DROP.

---

# 110. T-CON-004 — LIMIT reached + QUEUE

→ WAIT/DEFER.

---

# 111. T-CON-005 — RETRY_WAIT counts active

Selon V1 :

```text
Execution RETRY_WAIT
```

occupe toujours le slot.

---

# 112. T-CON-006 — Terminal does not count active

```text
SUCCESS

FAILED

CANCELLED

TIMED_OUT
```

libèrent la capacité.

---

# 113. T-CON-007 — Different ConcurrencyKey independent

---

# 114. T-CON-008 — Same ConcurrencyKey across different Schedules

Doit être partagé.

---

# 115. T-CON-009 — Evaluation pure

Même :

```text
policy + snapshot
```

→ même AdmissionDecision.

---

# 116. Atomic Admission Tests

---

# 117. T-CON-020 — Two nodes, limit=1

Deux transactions simultanées.

Expected :

```text
one Execution admitted
one waiting/dropped
```

jamais :

```text
two active
```

---

# 118. T-CON-021 — Admission and Execution creation atomic

Crash entre :

```text
capacity acquisition
```

et :

```text
Execution creation
```

ne doit pas laisser un slot fantôme durable.

---

# 119. Retry Tests

---

# 120. T-RET-001 — NoRetry

Premier Failure :

```text
STOP
```

---

# 121. T-RET-002 — Fixed retry

```text
delay = 10s
```

calcule :

```text
retry_at = now + 10s
```

---

# 122. T-RET-003 — Exponential sequence

Exemple :

```text
5s
10s
20s
40s
```

jusqu’au cap.

---

# 123. T-RET-004 — MaxDelay cap

---

# 124. T-RET-005 — MaxAttempts includes first attempt

```text
max_attempts = 3
```

signifie :

```text
Attempt 1
Attempt 2
Attempt 3
```

pas 4.

---

# 125. T-RET-006 — Attempt numbers strictly increasing

---

# 126. T-RET-007 — Retry same Execution

ExecutionId reste identique.

---

# 127. T-RET-008 — Retry creates new Attempt

AttemptId change.

---

# 128. T-RET-009 — IdempotencyKey stable across Attempts

---

# 129. T-RET-010 — Permanent failure no retry

si policy respecte catégorie.

---

# 130. T-RET-011 — Unknown nonretryable default

---

# 131. T-RET-012 — Deadline prevents retry

Même si Failure retryable.

---

# 132. T-RET-013 — Retry does not invoke Trigger

---

# 133. T-RET-014 — RetryWait persists next_attempt_at

---

# 134. T-RET-015 — Retries exhausted completion reason

Expected :

```text
Execution FAILED

completion_reason = RETRIES_EXHAUSTED
```

avec :

```text
final_failure = last target failure
```

---

# 135. Execution State Machine Tests

---

# 136. T-EXE-001 — Request pending lifecycle

Valider transitions publiques autorisées.

---

# 137. T-EXE-002 — Execution creation

```text
Request admitted
→
Execution QUEUED
```

---

# 138. T-EXE-003 — Start

```text
QUEUED → RUNNING
```

---

# 139. T-EXE-004 — Success

```text
RUNNING → SUCCESS
```

---

# 140. T-EXE-005 — Retryable failure

```text
RUNNING → RETRY_WAIT
```

---

# 141. T-EXE-006 — Terminal failure

```text
RUNNING → FAILED
```

---

# 142. T-EXE-007 — Retry restart

```text
RETRY_WAIT → RUNNING
```

---

# 143. T-EXE-008 — Terminal state cannot resurrect

Exemples interdits :

```text
SUCCESS → RUNNING

FAILED → RETRY_WAIT
```

---

# 144. T-EXE-009 — One active Attempt maximum

---

# 145. T-EXE-010 — Attempt starts RUNNING

---

# 146. T-EXE-011 — Attempt terminal transition only

---

# 147. T-EXE-012 — Attempt cannot retry itself

---

# 148. T-EXE-013 — ExecutionResult exactly once

Terminal Execution possède :

```text
one final result
```

---

# 149. T-EXE-014 — Duplicate completion

Deux submissions de même result ne créent pas :

```text
two terminal transitions
```

---

# 150. T-EXE-015 — Late attempt result

Ancienne Attempt ne peut pas écraser une nouvelle.

---

# 151. T-EXE-016 — Manual rerun new identity

Future feature :

```text
new ExecutionId
```

---

# 152. SchedulerEngine Tests

---

# 153. T-RUN-001 — Due Schedule evaluated

---

# 154. T-RUN-002 — Future Schedule ignored

---

# 155. T-RUN-003 — Paused Schedule ignored

---

# 156. T-RUN-004 — Cancelled Schedule ignored

---

# 157. T-RUN-005 — Completed Schedule ignored

---

# 158. T-RUN-006 — same-now principle

Tous les Schedules d’un cycle utilisent :

```text
cycle_now
```

identique pour la décision.

---

# 159. T-RUN-007 — Per-Schedule error isolation

Un Schedule cassé :

```text
n'empêche pas les autres d'être traités
```

---

# 160. T-RUN-008 — Batch bounds

Au plus :

```text
configured batch size
```

dans un cycle.

---

# 161. T-RUN-009 — Deterministic candidate ordering

```text
next_run_time ASC
ScheduleId ASC
```

---

# 162. T-RUN-010 — Trigger exhaustion completes Schedule

---

# 163. T-RUN-011 — Waiting admission independent re-evaluation

Une Request déjà WAITING ne repasse pas :

```text
misfire classification
```

---

# 164. T-RUN-012 — Due retries independent of Trigger

---

# 165. Runtime Wake-Up Tests

---

# 166. T-RUN-020 — First startup cycle immediate

---

# 167. T-RUN-021 — Fixed polling wakes within configured bound

---

# 168. T-RUN-022 — Earliest timer selection

```text
min(
 schedule next due,
 retry due,
 poll deadline
)
```

---

# 169. T-RUN-023 — Signal causes early wake

---

# 170. T-RUN-024 — Duplicate signal harmless

---

# 171. T-RUN-025 — Lost signal recovered by polling

---

# 172. T-RUN-026 — Spurious wake harmless

---

# 173. T-RUN-027 — Earlier reschedule wakes runtime

---

# 174. T-RUN-028 — Later reschedule stale wake harmless

---

# 175. T-RUN-029 — Clock jumps forward

Triggers normal :

```text
misfire/catch-up
```

---

# 176. T-RUN-030 — Clock jumps backward

No duplicate logical occurrence.

---

# 177. T-RUN-031 — System suspension

Après reprise :

```text
durable state determines backlog
```

---

# 178. T-RUN-032 — No overlapping cycles

Même si cycle dépasse poll interval.

---

# 179. T-RUN-033 — Immediate next cycle when work remains

Sans busy loop infini.

---

# 180. T-RUN-034 — Runtime transient failure backoff

---

# 181. T-RUN-035 — Fatal runtime failure

```text
RuntimeState = FAILED
```

---

# 182. Runtime Lifecycle Tests

---

# 183. T-RUN-040 — STOPPED → STARTING → RUNNING

---

# 184. T-RUN-041 — RUNNING → STOPPING → STOPPED

---

# 185. T-RUN-042 — start idempotence

---

# 186. T-RUN-043 — shutdown idempotence

---

# 187. T-RUN-044 — run_pending while running rejected

---

# 188. T-RUN-045 — graceful shutdown wakes sleeper

---

# 189. T-RUN-046 — no new cycle after stop requested

---

# 190. T-RUN-047 — no transaction open during sleep

---

# 191. Persistence Contract Suite

Tous les persistence adapters doivent exécuter :

```text
PersistenceContractSuite
```

---

# 192. ScheduleRepository Contract

---

# 193. T-PER-001 — Schedule round-trip

```text
save
→ load
```

sémantiquement équivalent.

---

# 194. T-PER-002 — Trigger/policy serialization round-trip

---

# 195. T-PER-003 — next_run_time persisted

---

# 196. T-PER-004 — ScheduleRevision persisted

---

# 197. T-PER-005 — PersistenceVersion optimistic update

---

# 198. T-PER-006 — Stale version rejected

---

# 199. T-PER-007 — due query state filtering

---

# 200. T-PER-008 — due ordering deterministic

---

# 201. T-PER-009 — null next_run_time excluded

---

# 202. ExecutionRequest Contract

---

# 203. T-PER-010 — Request round-trip

---

# 204. T-PER-011 — RequestId unique

---

# 205. T-PER-012 — OccurrenceKey unique

P0.

---

# 206. T-PER-013 — Waiting admission query order

---

# 207. T-PER-014 — find by OccurrenceKey

---

# 208. ExecutionRepository Contract

---

# 209. T-PER-020 — Execution round-trip

---

# 210. T-PER-021 — RequestId → Execution unique

---

# 211. T-PER-022 — Attempt persistence

---

# 212. T-PER-023 — Attempt number uniqueness

---

# 213. T-PER-024 — due retry query

---

# 214. T-PER-025 — active Execution query

---

# 215. T-PER-026 — terminal Execution excluded from active

---

# 216. UnitOfWork Tests

---

# 217. T-PER-030 — Commit persists all changes

---

# 218. T-PER-031 — Rollback discards all changes

---

# 219. T-PER-032 — Repository does not commit implicitly

---

# 220. T-PER-033 — Exception causes rollback

---

# 221. T-PER-034 — Same transaction sees own changes

---

# 222. T-PER-035 — New UoW sees committed state only

---

# 223. InMemory UoW must pass same semantics

Très important.

---

# 224. Atomic Scheduling Transaction Tests

---

# 225. T-PER-040 — Request + next_run_time atomic

Crash before commit :

```text
neither visible
```

---

# 226. T-PER-041 — Commit exposes both

---

# 227. T-PER-042 — Duplicate Request conflict + stale checkpoint recovery

Si Request existe déjà mais next_run_time stale :

```text
reconcile safely
```

---

# 228. T-PER-043 — Skip + checkpoint advancement atomic

---

# 229. T-PER-044 — WAITING_ADMISSION + checkpoint atomic

---

# 230. Attempt Transaction Tests

---

# 231. T-PER-050 — Attempt start + Execution RUNNING atomic

---

# 232. T-PER-051 — Failure + RETRY_WAIT + next_attempt_at atomic

---

# 233. T-PER-052 — Success + Execution SUCCESS atomic

---

# 234. T-PER-053 — Terminal failure result atomic

---

# 235. T-PER-054 — cancellation terminal transition atomic

---

# 236. Unknown Commit Outcome Tests

---

# 237. T-PER-060 — Simulated commit connection loss

Le système doit pouvoir déterminer :

```text
whether Request exists
```

via stable identity.

---

# 238. T-PER-061 — Retried materialization does not duplicate

---

# 239. T-PER-062 — Same RequestId safe

---

# 240. Outbox Contract Tests

---

# 241. T-OUT-001 — State + outbox same transaction

---

# 242. T-OUT-002 — Rollback removes outbox

---

# 243. T-OUT-003 — Commit preserves pending message

---

# 244. T-OUT-004 — Publisher reads committed only

---

# 245. T-OUT-005 — Publish then crash before mark

Résultat :

```text
message may be delivered twice
```

---

# 246. T-OUT-006 — Consumer dedup by MessageId/RequestId

---

# 247. T-OUT-007 — Published status persisted

---

# 248. T-OUT-008 — Multiple publishers do not corrupt record

---

# 249. T-OUT-009 — Outbox backlog observable

---

# 250. Crash Consistency Fault Injection

Le test framework devrait pouvoir injecter :

```text
before_insert_request

after_insert_request

before_schedule_update

after_schedule_update

before_commit

after_commit

before_publish

after_publish
```

---

# 251. T-PER-070 — Failure before commit

Expected :

```text
rollback
```

---

# 252. T-PER-071 — Crash after commit before publish

Expected :

```text
outbox recovers
```

---

# 253. T-PER-072 — Crash after publish

Expected :

```text
possible redelivery
without duplicate logical Execution
```

---

# 254. Distributed Schedule Tests

---

# 255. T-DIST-001 — Two schedulers same occurrence

Expected :

```text
exactly one primary durable ExecutionRequest
```

---

# 256. Note

Cela ne promet pas :

```text
exactly-once all side effects
```

---

# 257. T-DIST-002 — Row claim conflict

One node wins.

Other :

```text
skips without failure
```

---

# 258. T-DIST-003 — Optimistic competition

Les deux peuvent planifier.

Un seul applique version.

---

# 259. T-DIST-004 — Stale ScheduleVersion rejected

---

# 260. T-DIST-005 — Node crash during transaction

Lock released/transaction rollback.

Another node recovers.

---

# 261. T-DIST-006 — Node crash after commit

Other nodes see advanced durable state.

---

# 262. Distributed Worker Tests

---

# 263. T-DIST-010 — Two workers same Execution

Expected :

```text
one Attempt #1
```

---

# 264. T-DIST-011 — Two workers same retry

Expected :

```text
one Attempt #(N+1)
```

---

# 265. T-DIST-012 — Worker crash after Attempt RUNNING persisted

RuntimeReconciler detects stale state.

---

# 266. T-DIST-013 — Different worker resumes later retry

Works without original in-memory state.

---

# 267. Lease Contract Tests

---

# 268. T-DIST-020 — Acquire free lease

---

# 269. T-DIST-021 — Second owner denied while valid

---

# 270. T-DIST-022 — Lease expiry

New owner may acquire.

---

# 271. T-DIST-023 — Fencing token increments

```text
41 → 42
```

---

# 272. T-DIST-024 — Stale owner cannot renew

---

# 273. T-DIST-025 — Stale owner cannot release

---

# 274. T-DIST-026 — Strict expired lease cannot be resurrected

---

# 275. T-DIST-027 — Node A pause, Node B takeover, A resumes

A must be treated stale.

---

# 276. Fencing Tests

---

# 277. T-DIST-030 — Stale token rejected

---

# 278. T-DIST-031 — Current token accepted

---

# 279. T-DIST-032 — Token never decreases

Property-based / concurrent test.

---

# 280. Leader Election Tests

---

# 281. T-DIST-040 — One valid leader

---

# 282. T-DIST-041 — Leader renewal

---

# 283. T-DIST-042 — Leader crash/failover

---

# 284. T-DIST-043 — Old leader stale after failover

---

# 285. T-DIST-044 — Follower stays runtime RUNNING

Leadership loss :

```text
does not necessarily Runtime FAILED
```

---

# 286. T-DIST-045 — Scheduling does not require leader

Important architectural test.

Avec leader lease indisponible pour maintenance :

```text
per-Schedule claiming
```

doit continuer si architecture l'autorise.

---

# 287. Split-Brain Simulation

---

# 288. T-DIST-050

Scenario :

```text
A token 100

A pauses

lease expires

B token 101

A resumes
```

Expected :

```text
A fenced
```

---

# 289. Observability Tests

---

# 290. T-OBS-001 — CorrelationId propagation

```text
Schedule
→ Request
→ Execution
→ Attempt
```

---

# 291. T-OBS-002 — TraceId propagation

---

# 292. T-OBS-003 — EventId unique

---

# 293. T-OBS-004 — Event schema version present

---

# 294. T-OBS-005 — Domain transition emits expected event

---

# 295. T-OBS-006 — Rolled-back transaction emits no committed integration event

---

# 296. T-OBS-007 — Audit append-only

---

# 297. T-OBS-008 — Audit reason code stable

---

# 298. T-OBS-009 — Misfire decision evidence complete

---

# 299. T-OBS-010 — RetryScheduled evidence

---

# 300. T-OBS-011 — Execution completion timeline reconstructible

---

# 301. T-OBS-012 — Claim diagnostics contain NodeId

---

# 302. T-OBS-013 — Lease diagnostics contain fencing token

---

# 303. Metrics Tests

---

# 304. T-OBS-020 — Occurrence counter increments

---

# 305. T-OBS-021 — Failure metrics separated from scheduler health

100 workload failures :

```text
do not automatically mark scheduler runtime unhealthy
```

---

# 306. T-OBS-022 — Lag calculated correctly

---

# 307. T-OBS-023 — No IDs as default metric labels

Test/inspection du registry metrics.

---

# 308. T-OBS-024 — Outbox age metric

---

# 309. T-OBS-025 — Runtime health reasons

---

# 310. Explainability Tests

---

# 311. T-OBS-030 — Explain misfire skip

Doit produire reason chain cohérente.

---

# 312. T-OBS-031 — Explain concurrency wait

---

# 313. T-OBS-032 — Explain retry exhaustion

---

# 314. T-OBS-033 — Explain successful retry chain

---

# 315. T-OBS-034 — No log parsing required

L’explication doit dériver de :

```text
structured evidence
```

---

# 316. Public API Tests

---

# 317. T-API-001 — Root imports

```python
from pyschedulekit import Scheduler
```

fonctionne.

---

# 318. T-API-002 — Root namespace limited

Les classes internes ne doivent pas être accidentellement exportées.

---

# 319. T-API-003 — add_schedule returns ScheduleHandle

---

# 320. T-API-004 — ScheduleHandle ID stable

---

# 321. T-API-005 — Snapshot immutable

---

# 322. T-API-006 — pause via handle delegates canonical service

---

# 323. T-API-007 — resume

---

# 324. T-API-008 — reschedule

---

# 325. T-API-009 — cancel

---

# 326. T-API-010 — get missing Schedule raises correct error

---

# 327. T-API-011 — list no results returns []

---

# 328. T-API-012 — start non-blocking

---

# 329. T-API-013 — run_forever blocking semantics

Test via controlled runtime/thread, jamais timer fragile.

---

# 330. T-API-014 — shutdown graceful

---

# 331. T-API-015 — run_pending no sleep

---

# 332. T-API-016 — background Target failure not raised from start()

---

# 333. T-API-017 — callable local mode works

---

# 334. T-API-018 — callable persistent unsafe mode rejected

---

# 335. T-API-019 — TargetRef persistent mode works

---

# 336. T-API-020 — default timezone deterministic

---

# 337. API Type Tests

Utiliser :

```text
mypy
pyright
```

ou équivalent.

---

# 338. T-API-030 — public API has type annotations

---

# 339. T-API-031 — package contains py.typed

à partir du packaging public.

---

# 340. T-API-032 — documented examples type-check

---

# 341. Error Model Tests

---

# 342. T-ERR-001 — All public framework errors derive PyScheduleKitError

---

# 343. T-ERR-002 — Failure is not Exception

---

# 344. T-ERR-003 — Cron invalid → InvalidCronExpressionError

---

# 345. T-ERR-004 — Schedule missing → ScheduleNotFoundError

---

# 346. T-ERR-005 — Invalid lifecycle → DomainError

---

# 347. T-ERR-006 — Vendor DB error normalized

---

# 348. T-ERR-007 — Vendor error cause chained

---

# 349. T-ERR-008 — Public message sanitized

---

# 350. T-ERR-009 — Target exception becomes Failure

si Attempt active.

---

# 351. T-ERR-010 — Target Failure does not crash Runtime

---

# 352. T-ERR-011 — UNKNOWN nonretryable by default

---

# 353. T-ERR-012 — PersistenceUnavailable triggers runtime handling, not RetryPolicy

---

# 354. T-ERR-013 — ClaimConflict not treated as ERROR

---

# 355. T-ERR-014 — FencingRejected stops stale owner

---

# 356. T-ERR-015 — Retry exhaustion is completion reason

Pas nouveau Failure artificiel.

---

# 357. Failure Serialization Tests

---

# 358. T-ERR-020 — Failure round-trip

---

# 359. T-ERR-021 — Failure code preserved

---

# 360. T-ERR-022 — Sensitive details redacted

---

# 361. Security Tests

---

# 362. T-SEC-001 — Pickle forbidden

Toute tentative de codec pickle doit échouer.

---

# 363. T-SEC-002 — eval forbidden

Architecture/static scan.

---

# 364. T-SEC-003 — exec forbidden in configuration resolution

---

# 365. T-SEC-004 — Arbitrary class-path codec rejected

---

# 366. T-SEC-005 — Unknown target kind rejected

---

# 367. T-SEC-006 — Registered Python target accepted

---

# 368. T-SEC-007 — Non-registered target rejected in REGISTERED_ONLY

---

# 369. T-SEC-008 — Allowlisted module accepted

---

# 370. T-SEC-009 — Prefix confusion rejected

Allow :

```text
myapp.jobs
```

Reject :

```text
myapp.jobs_evil
```

---

# 371. T-SEC-010 — builtins:eval rejected

---

# 372. T-SEC-011 — subprocess target rejected by default

---

# 373. T-SEC-012 — lambda persistent target rejected

---

# 374. T-SEC-013 — Secret absent from Schedule serialization

---

# 375. T-SEC-014 — Secret absent from repr

---

# 376. T-SEC-015 — Secret absent from logs

---

# 377. T-SEC-016 — Secret absent from public error details

---

# 378. T-SEC-017 — Unknown config field rejected

---

# 379. T-SEC-018 — Unsupported schema version rejected

---

# 380. T-SEC-019 — Persisted config revalidated

---

# 381. T-SEC-020 — Metadata cannot change executor routing

---

# 382. T-SEC-021 — Direct HTTP forbidden when policy says false

---

# 383. T-SEC-022 — HTTP host allowlist

---

# 384. T-SEC-023 — Redirect revalidation

si HTTP adapter V1 existe.

---

# 385. T-SEC-024 — Config size bounded

---

# 386. T-SEC-025 — Trigger evaluation bounded

---

# 387. T-SEC-026 — Catch-up bounded

---

# 388. T-SEC-027 — Retry bounded

---

# 389. T-SEC-028 — Runtime config immutable after start

---

# 390. T-SEC-029 — Environment malformed value fails startup

---

# 391. T-SEC-030 — Config precedence deterministic

```text
explicit
>
env
>
file
>
default
```

---

# 392. Static Architecture Security Checks

CI doit pouvoir détecter :

```text
pickle.loads

eval(

exec(

os.system
```

dans modules non autorisés.

---

# 393. Attention

Ces scans ne remplacent pas review/tests.

Ils servent de :

```text
fitness functions
```

---

# 394. Serialization Codec Contract Tests

Chaque codec doit passer :

```text
CodecContractSuite
```

---

# 395. T-SEC-040 — Round-trip

---

# 396. T-SEC-041 — Unknown field reject

---

# 397. T-SEC-042 — Unknown version reject

---

# 398. T-SEC-043 — Missing required field reject

---

# 399. T-SEC-044 — No arbitrary import

---

# 400. T-SEC-045 — Deterministic output

Même object :

```text
semantically same serialized representation
```

hors ordering JSON non-significatif.

---

# 401. End-to-End V1 Tests

---

# 402. T-E2E-001 — One-shot success

```text
DateTrigger
→ Request
→ Execution
→ Attempt
→ SUCCESS
→ Schedule COMPLETED
```

---

# 403. T-E2E-002 — Interval repeated executions

3 due intervals :

```text
3 logical occurrences
```

---

# 404. T-E2E-003 — Cron daily

Avec MutableClock.

---

# 405. T-E2E-004 — Pause/resume

Aucune occurrence créée pendant pause selon V1.

---

# 406. T-E2E-005 — Reschedule

Future occurrences utilisent nouvelle revision.

Existing Execution retains old revision.

---

# 407. T-E2E-006 — Misfire SKIP

---

# 408. T-E2E-007 — Catch-Up

---

# 409. T-E2E-008 — Concurrency WAIT

---

# 410. T-E2E-009 — Retry then success

```text
Attempt 1 FAILED

Attempt 2 SUCCESS

Execution SUCCESS
```

---

# 411. T-E2E-010 — Retries exhausted

---

# 412. T-E2E-011 — Persistence restart

Scenario :

```text
create Schedule
stop process
restart
advance time
```

Expected :

```text
correct future occurrence
```

---

# 413. T-E2E-012 — Restart during RETRY_WAIT

---

# 414. T-E2E-013 — Restart with WAITING_ADMISSION

---

# 415. T-E2E-014 — Crash after request commit

Outbox recovers.

---

# 416. T-E2E-015 — Two Scheduler nodes

Same DB :

```text
no duplicate primary occurrence
```

---

# 417. T-E2E-016 — Two Workers

No duplicate Attempt.

---

# 418. T-E2E-017 — Distributed concurrency

Two Schedules, same ConcurrencyKey, limit 1.

---

# 419. T-E2E-018 — Worker lease failover

Future distributed stage.

---

# 420. Deterministic Scenario Fixtures

Créer des fixtures de référence.

---

# 421. Fixture A — Simple Interval

```text
Start: 10:00 UTC
Interval: 10m
```

Expected occurrences :

```text
10:10
10:20
10:30
```

---

# 422. Fixture B — Cron Europe/Paris

```text
0 6 * * *
```

autour :

```text
DST transition
```

---

# 423. Fixture C — Outage

```text
last processed 10:00

restart 11:00
```

pour catch-up.

---

# 424. Fixture D — Retry

```text
Failure #1 transient
Failure #2 transient
Success #3
```

---

# 425. Fixture E — Concurrency

```text
S1 and S2
same key
limit 1
```

---

# 426. Fixture F — Distributed race

Deux nodes synchronisés par barrier de test.

---

# 427. Property-Based Testing

PyScheduleKit est particulièrement adapté.

---

# 428. Trigger properties

```text
monotonicity

termination within horizon

round-trip serialization
```

---

# 429. State Machine properties

Générer des séquences d’opérations :

```text
pause

resume

cancel

reschedule
```

et vérifier :

```text
no invalid terminal resurrection
```

---

# 430. Retry properties

Pour tout :

```text
max_attempts >= 1
```

nombre d’Attempts :

```text
<= max_attempts
```

---

# 431. Persistence properties

Un transaction rollback :

```text
never leaves partial visible state
```

---

# 432. Lease properties

À tout instant logique :

```text
at most one current fenced owner
```

---

# 433. Fuzz Testing

Particulièrement utile pour :

```text
Cron expressions

Duration parsing

JSON config

serialized codecs
```

---

# 434. Fuzz Security Objective

Input arbitraire ne doit pas :

```text
crash process

loop indefinitely

execute code

consume unbounded memory
```

---

# 435. Mutation Testing

Option intéressante après V1.

---

# 436. Pourquoi ?

Un coverage à 100 % ne prouve pas :

```text
quality of assertions
```

---

# 437. Mutation testing peut vérifier que les tests détectent :

```text
comparaison > changée en >=

version check removed

unique check removed

retry limit off-by-one
```

---

# 438. Coverage Policy

Ne pas fixer uniquement :

```text
X% lines
```

comme critère principal.

---

# 439. Better

Chaque :

```text
documented P0 invariant
```

doit avoir :

```text
explicit test
```

---

# 440. Néanmoins

Une baseline de couverture peut prévenir les zones totalement non testées.

---

# 441. Recommandation

Pour core modules :

```text
high branch coverage
```

plutôt qu’objectif de ligne arbitraire.

---

# 442. P0 Invariant Registry

Créer éventuellement :

```text
tests/invariants/
```

ou document de mapping.

---

# 443. Exemple

```text
INV-SCH-001
Automatic occurrence materialized at most once
→
T-PER-012
T-DIST-001
T-E2E-015
```

---

# 444. Traceability Matrix

| Invariant | Tests |
|---|---|
| Trigger progresses strictly | T-TRG-012 |
| Terminal Execution never resurrects | T-EXE-008 |
| Automatic occurrence deduped | T-PER-012, T-DIST-001 |
| Retry same Execution | T-RET-007 |
| No dispatch before durable commit | T-PER-040, T-OUT-001 |
| Lost signal harmless | T-RUN-025 |
| Stale lease owner fenced | T-DIST-030, T-DIST-050 |
| Pickle forbidden | T-SEC-001 |
| Target failures do not crash Runtime | T-ERR-010 |

---

# 445. Non-Functional Acceptance

Correction seule ne suffit pas.

---

# 446. Determinism

Même scénario simulé doit produire :

```text
same semantic result
```

sur exécutions répétées.

---

# 447. Performance Baselines

Ne pas viser benchmark absolu universel.

Mais établir des garde-fous.

---

# 448. T-PERF-001 — Trigger calculation bounded

Interval next calculation doit rester :

```text
approximately constant-time
```

---

# 449. T-PERF-002 — 10k in-memory schedules

Un cycle de sélection ne doit pas dégrader de façon catastrophique.

---

# 450. T-PERF-003 — Bounded catch-up memory

---

# 451. T-PERF-004 — No telemetry cardinality explosion

---

# 452. T-PERF-005 — Runtime idle does not busy-loop

CPU proche d’inactivité normale.

---

# 453. T-PERF-006 — Backlog fairness

Avec :

```text
schedule backlog
retry backlog
waiting admissions
```

aucune catégorie ne doit être affamée indéfiniment.

---

# 454. Load Testing

Future production qualification :

```text
large schedule count

burst at midnight

retry storm

outbox backlog
```

---

# 455. Thundering Herd Test

Multi-node :

```text
many nodes
many due schedules
same second
```

Expected :

```text
bounded contention
correctness preserved
```

---

# 456. Chaos / Fault Injection

À partir de distributed phases.

---

# 457. Faults

```text
kill scheduler

kill worker

pause process

drop DB connection

delay DB

duplicate notification

lose notification

duplicate outbox message

delay result

expire lease
```

---

# 458. Chaos invariant

Même lorsque disponibilité baisse :

```text
semantic correctness must remain
```

dans garanties documentées.

---

# 459. Exemple

DB unavailable :

```text
no new unsafe dispatch
```

---

# 460. Recovery Acceptance

Après récupération :

```text
system progresses again
```

sans intervention manuelle pour les pannes transitoires prévues.

---

# 461. Compatibility Tests

À partir des versions persistantes.

---

# 462. T-COMP-001 — Read previous Schedule schema

---

# 463. T-COMP-002 — Write current schema

---

# 464. T-COMP-003 — Unknown future schema rejected

---

# 465. T-COMP-004 — Event older version decoded

si supportée.

---

# 466. T-COMP-005 — Public import compatibility

---

# 467. Golden Files

Pour serialization :

```text
Trigger payload

Policy payload

Failure payload

Event payload
```

peuvent disposer de :

```text
golden fixtures
```

---

# 468. Attention

Golden files ne doivent pas empêcher des changements internes légitimes.

Ils protègent :

```text
public/persistent contracts
```

seulement.

---

# 469. Database Migration Tests

---

# 470. T-MIG-001 — Fresh database bootstrap

---

# 471. T-MIG-002 — Upgrade previous schema

---

# 472. T-MIG-003 — Existing Schedules preserved

---

# 473. T-MIG-004 — Existing Executions preserved

---

# 474. T-MIG-005 — Rollback/compatibility strategy documented

---

# 475. No destructive automatic migration in Runtime tests.

---

# 476. CI Test Stages

Pipeline recommandée :

```text
Stage 1
Lint / formatting / static architecture checks

Stage 2
Domain unit tests

Stage 3
Application tests

Stage 4
Contract tests

Stage 5
SQLite integration

Stage 6
PostgreSQL integration

Stage 7
E2E

Stage 8
Security / fuzz selected

Stage 9
Distributed qualification
```

---

# 477. Fast Feedback

PR standard devrait exécuter rapidement :

```text
P0/P1 unit

application

contract
```

---

# 478. Heavier Tests

PostgreSQL distributed/fault injection peuvent être :

```text
mandatory on merge/release
```

---

# 479. Release Qualification Pipeline

Avant une release stable :

```text
all P0

all P1

all adapter contracts

all migrations

all E2E

security suite

distributed suite if feature enabled
```

---

# 480. Feature-Gated Tests

Si une release ne supporte pas encore :

```text
leases
```

les tests lease peuvent être :

```text
not applicable
```

---

# 481. Important

Pas :

```text
xfail forever
```

sans raison.

---

# 482. Feature Matrix

Chaque feature a un statut :

```text
NOT_IMPLEMENTED

EXPERIMENTAL

SUPPORTED
```

---

# 483. Release test expectation

```text
SUPPORTED
→ all acceptance tests green
```

---

# 484. Experimental

Peut avoir :

```text
known limitations
```

documentées.

---

# 485. No Silent XFail

Tout xfail doit référencer :

```text
issue

reason

expected removal condition
```

---

# 486. Test Naming

Exemple :

```python
def test_retry_exhaustion_keeps_last_failure(): ...
```

---

# 487. Prefer semantic names

Pas :

```python
def test_retry_3():
```

---

# 488. Arrange / Act / Assert

Recommandé pour lisibilité.

---

# 489. Given / When / Then

Excellent pour domain scenarios.

---

# 490. Test Fixtures

Éviter huge fixture global opaque.

---

# 491. Prefer builders

Exemples :

```text
ScheduleBuilder

ExecutionBuilder

OccurrenceBuilder
```

dans testing only.

---

# 492. But

Builders ne doivent pas autoriser :

```text
invalid impossible states
```

par défaut.

---

# 493. Need invalid state?

Use explicit :

```text
unsafe_fixture()
```

for corruption tests.

---

# 494. Fake versus Mock

Préférer :

```text
small fakes
```

pour repositories/clocks.

---

# 495. Pourquoi ?

Ils testent davantage :

```text
behavior
```

et moins :

```text
call implementation details
```

---

# 496. Mocks utiles pour

```text
outbound adapter interaction
```

très ciblée.

---

# 497. Avoid Mock Everything

Sinon tests deviennent couplés à architecture interne.

---

# 498. FakeExecutor

Doit pouvoir être configuré :

```text
succeed

fail with Failure

timeout

block

record invocations
```

---

# 499. ScriptedExecutor

Très utile :

```text
Attempt 1 → transient failure

Attempt 2 → success
```

---

# 500. BarrierExecutor

Utile pour concurrency race tests.

---

# 501. FakeWakeUpCoordinator

Permet :

```text
signal

timer

shutdown
```

sans vrais sleeps.

---

# 502. FaultInjectingRepository

Permet :

```text
fail before commit

fail after operation

simulate conflict
```

---

# 503. Testing Utilities public package

Certains outils peuvent être proposés à l’utilisateur :

```text
FixedClock

MutableClock

SchedulerHarness

FakeExecutor
```

---

# 504. Internal test tools

D’autres restent :

```text
project-internal
```

comme :

```text
FaultInjectingUnitOfWork

RaceBarrier
```

---

# 505. Public Testing API itself needs tests

Parce qu’il deviendra une feature du framework.

---

# 506. Manual Exploratory Tests

L’automatisation ne couvre pas tout.

Avant release importante :

```text
small interactive examples
```

peuvent vérifier :

```text
developer experience

error readability

repr

documentation
```

---

# 507. Documentation Tests

Tous les snippets publics doivent idéalement être :

```text
executable
```

---

# 508. Doctest ?

Possible, mais pas obligatoire.

---

# 509. Better

Extraire les examples docs vers tests dédiés.

---

# 510. Example Contract

Le code :

```python
Scheduler()
```

du README doit réellement fonctionner.

---

# 511. Example Drift

Un test doit éviter que documentation et API divergent.

---

# 512. Public API Acceptance

Avant V1 :

```text
all examples in 24_PUBLIC_API_SPEC
```

doivent être soit :

```text
implemented and green
```

soit explicitement :

```text
deferred
```

---

# 513. Security Acceptance Gate

Aucune release stable si :

```text
pickle path exists

eval-based config exists

secrets appear in normal logs

unknown target types auto-resolve
```

---

# 514. Persistence Acceptance Gate

Aucune release persistante si :

```text
Request creation
and
next_run advancement
```

peuvent diverger après crash.

---

# 515. Distributed Acceptance Gate

Aucune feature multi-node déclarée stable si :

```text
two nodes
```

peuvent créer deux primary requests pour :

```text
same OccurrenceKey
```

---

# 516. Retry Acceptance Gate

Aucun retry stable si :

```text
max_attempts
```

peut être dépassé.

---

# 517. Runtime Acceptance Gate

Aucune Runtime stable si :

```text
shutdown can leave transaction open
```

ou :

```text
two cycles can overlap in same Runtime
```

---

# 518. Observability Acceptance Gate

Une Execution terminale doit être :

```text
diagnostically reconstructible
```

au minimum depuis :

```text
state

Attempts

Failure

completion reason
```

---

# 519. Core P0 Release Invariants

La release V1 ne peut être acceptée que si :

```text
1.
Trigger progression is deterministic.

2.
next_run_time cannot silently skip committed intent.

3.
Automatic occurrence is uniquely materialized.

4.
External dispatch never occurs before durable intent.

5.
Execution terminal states cannot resurrect.

6.
Retry never creates a new scheduling occurrence.

7.
Retry count cannot exceed max_attempts.

8.
Persistence rollback leaves no partial state.

9.
Restart reconstructs pending work from durable state.

10.
Unknown/unsafe configuration fails closed.

11.
Secrets are not intentionally persisted or logged.

12.
One broken workload does not crash the scheduler.

13.
One broken Schedule does not corrupt unrelated Schedules.

14.
Distributed stale owners cannot overwrite newer fenced state.

15.
Public errors never leak vendor-specific contracts by default.
```

---

# 520. V1 Functional Acceptance Matrix

| Feature | Required evidence |
|---|---|
| DateTrigger | T-TRG-001 → 003 |
| IntervalTrigger | T-TRG-010 → 015 |
| CronTrigger | T-TRG-020 → 030 |
| Schedule lifecycle | T-SCH-001 → 015 |
| Misfire | T-MIS-001 → 006 |
| Catch-Up | T-CAT-001 → 007 |
| Concurrency | T-CON-001 → 021 |
| Retry | T-RET-001 → 015 |
| Execution lifecycle | T-EXE-001 → 016 |
| Runtime | T-RUN-001 → 047 |
| Persistence | T-PER-001 → 072 |
| Outbox | T-OUT-001 → 009 |
| Observability | T-OBS-001 → 034 |
| Public API | T-API-001 → 032 |
| Errors | T-ERR-001 → 022 |
| Security | T-SEC-001 → 045 |

---

# 521. Distributed Acceptance Matrix

Pour déclarer :

```text
multi-node scheduling
```

stable, il faut au minimum :

```text
T-DIST-001
T-DIST-002
T-DIST-003
T-DIST-004
T-DIST-005
T-DIST-006
```

---

# 522. Multi-worker Acceptance

```text
T-DIST-010
T-DIST-011
T-DIST-012
T-DIST-013
```

---

# 523. Lease Support Acceptance

```text
T-DIST-020 → T-DIST-027
```

---

# 524. Fencing Support Acceptance

```text
T-DIST-030 → T-DIST-032
```

---

# 525. Leader Election Acceptance

```text
T-DIST-040 → T-DIST-045
```

---

# 526. Feature Qualification Levels

Proposition :

```text
Level 0 — Conceptual

Level 1 — Unit Qualified

Level 2 — In-Memory Qualified

Level 3 — Persistent Qualified

Level 4 — Crash Qualified

Level 5 — Distributed Qualified
```

---

# 527. Example

CronTrigger peut être :

```text
Level 1
```

avant qu’un Scheduler complet existe.

---

# 528. Schedule Engine

Peut atteindre :

```text
Level 2
```

avec InMemory.

---

# 529. SQLite release

Atteint :

```text
Level 3
```

---

# 530. Outbox/crash tests

Atteignent :

```text
Level 4
```

---

# 531. PostgreSQL multi-node

Atteint :

```text
Level 5
```

---

# 532. Cette graduation est utile pour roadmap

Elle empêche de dire :

```text
"feature done"
```

sans préciser :

```text
à quel niveau de garantie
```

---

# 533. Definition of Done — Domain Object

Une Entity/VO n’est done que si :

```text
valid construction tested

invalid construction tested

invariants tested

equality semantics tested where relevant

serialization tested if durable
```

---

# 534. Definition of Done — Application Use Case

Doit tester :

```text
happy path

domain rejection

repository failure

transaction rollback

observability evidence
```

---

# 535. Definition of Done — Adapter

Doit :

```text
pass contract suite

normalize vendor errors

pass integration tests

document capability limitations
```

---

# 536. Definition of Done — Public API

Doit avoir :

```text
typing

docstring

example

error contract

backward-compatibility decision
```

---

# 537. Definition of Done — Distributed Feature

Doit avoir :

```text
race test

node crash test

stale owner test

recovery test

observability evidence
```

---

# 538. Test Flakiness Policy

Flaky test = defect.

---

# 539. Interdit

```text
rerun 3 times until green
```

comme solution permanente.

---

# 540. Flaky time tests

Doivent être réécrits avec :

```text
virtual time

barriers

signals
```

---

# 541. Concurrency Tests

Éviter :

```python
time.sleep(0.1)
```

pour espérer provoquer une race.

---

# 542. Utiliser

```text
thread barriers

events

deterministic coordination
```

---

# 543. Distributed timing tests

Lease expiry via :

```text
controlled coordination clock
```

si adapter de test le permet.

---

# 544. Database lock tests

Peuvent nécessiter de vrais threads/connections.

Mais synchroniser :

```text
transaction start points
```

explicitement.

---

# 545. CI Environment

Tests PostgreSQL doivent utiliser :

```text
isolated database/schema
```

---

# 546. Test Isolation

Chaque test doit :

```text
own its data
```

---

# 547. Unique IDs

Utiliser fixtures générées ou namespace par test.

---

# 548. Database Cleanup

Préférer :

```text
transaction rollback
```

ou schema isolé.

---

# 549. Test Order Independence

Toute permutation raisonnable de tests :

```text
same result
```

---

# 550. Random Test Order

Peut être utilisé pour détecter état global caché.

---

# 551. Global Registry Tests

Comme architecture évite les registries globaux :

```text
two Scheduler instances
```

avec différents ExecutorRegistry doivent rester indépendants.

---

# 552. T-API-040 — Registry isolation

---

# 553. Timezone environment randomization

CI peut exécuter certains tests avec :

```text
UTC

Europe/Paris

America/New_York
```

pour détecter dépendances host.

---

# 554. Locale randomization

Même principe pour parser.

---

# 555. Python Version Matrix

Quand baseline définie :

```text
minimum supported version

latest supported version
```

au minimum.

---

# 556. Database Matrix

Selon adapters supportés :

```text
SQLite supported version

PostgreSQL supported versions
```

---

# 557. Optional Adapter Matrix

Chaque extra :

```text
postgres

otel
```

a ses tests spécifiques.

---

# 558. Regression Tests

Tout bug corrigé doit produire :

```text
a failing regression test first
```

quand reproductible.

---

# 559. Naming

```text
test_regression_<issue>_<behavior>
```

si utile.

---

# 560. Production Incident Rule

Tout incident de correction métier doit idéalement enrichir :

```text
acceptance matrix
```

---

# 561. Test Reports

CI devrait produire :

```text
tests run

failures

skips

duration

coverage

qualification level
```

---

# 562. Feature Qualification Report

Future release peut publier :

```text
DateTrigger: Level 4
CronTrigger: Level 4
Multi-node: Experimental Level 5
```

---

# 563. This is valuable

Particulièrement pour un framework pédagogique et évolutif.

---

# 564. Test Documentation Traceability

Chaque document majeur doit être relié à sa suite.

Exemple :

```text
15_RETRY_BACKOFF_AND_FAILURE_MODEL.md
→
tests/domain/test_retry_policy.py
tests/application/test_execution_retry.py
tests/e2e/test_retry_flow.py
```

---

# 565. Suggested Test Tree

```text
tests/
├── unit/
│   ├── domain/
│   │   ├── time/
│   │   ├── triggers/
│   │   ├── schedule/
│   │   ├── policies/
│   │   └── execution/
│   │
│   └── application/
│
├── contracts/
│   ├── persistence/
│   ├── executors/
│   ├── codecs/
│   └── coordination/
│
├── integration/
│   ├── sqlite/
│   ├── postgres/
│   ├── outbox/
│   └── runtime/
│
├── distributed/
│   ├── scheduler/
│   ├── workers/
│   ├── leases/
│   └── fencing/
│
├── security/
│
├── e2e/
│
├── regression/
│
└── fixtures/
```

---

# 566. Keep tree pragmatic

Ne pas créer tous les dossiers au premier commit.

---

# 567. Start with vertical slice

Premier test vertical majeur :

```text
T-E2E-001
```

---

# 568. Minimal first proof

```text
FixedClock

IntervalTrigger

Schedule

InMemoryRepository

SchedulerEngine

Callable/FakeExecutor
```

---

# 569. Scenario

```text
10:00
Schedule every 10m

advance to 10:10

run_pending
```

Expected :

```text
one occurrence

one request

one execution

one attempt

success
```

---

# 570. Second Proof

Add :

```text
Retry
```

---

# 571. Third Proof

Add :

```text
Persistence restart
```

---

# 572. Fourth Proof

Add :

```text
Distributed race
```

---

# 573. This maps directly to architecture milestones

---

# 574. Acceptance Gate — Alpha

Une première alpha peut être considérée acceptable lorsque :

```text
DateTrigger

IntervalTrigger

Schedule lifecycle

InMemory persistence

run_pending

local execution

FixedClock testing
```

ont leurs P0/P1 tests verts.

---

# 575. Acceptance Gate — Alpha Persistent

Ajouter :

```text
SQLite

restart recovery

transactions

serialization
```

---

# 576. Acceptance Gate — Beta

Ajouter :

```text
Cron

Misfire

Catch-Up

Concurrency

Retry

Outbox

PostgreSQL
```

---

# 577. Acceptance Gate — RC

Ajouter :

```text
full public API

error normalization

security suite

observability

migration tests

documentation tests
```

---

# 578. Acceptance Gate — 1.0

Toutes les features annoncées `SUPPORTED` :

```text
P0 green

P1 green

no unexplained xfail

public compatibility frozen

persistent formats versioned

security gates green
```

---

# 579. Distributed 1.x

Multi-node peut être :

```text
post-1.0
```

si souhaité.

---

# 580. Important

L’architecture cible distribuée ne force pas :

```text
V1 package release
```

à implémenter toute cette complexité immédiatement.

---

# 581. Test Matrix versus Roadmap

Ce document répond :

```text
WHAT MUST BE PROVEN?
```

---

# 582. Le document 28 répondra :

```text
IN WHAT ORDER DO WE BUILD THE PROOFS?
```

---

# 583. Acceptance Question — Time

Peut-on prouver que :

```text
time semantics remain correct
```

sans attendre le temps réel ?

Si non :

```text
not accepted
```

---

# 584. Acceptance Question — Trigger

Peut-on prouver que chaque Trigger :

```text
progresses

terminates

round-trips
```

?

---

# 585. Acceptance Question — Schedule

Peut-on prouver toutes les transitions ?

---

# 586. Acceptance Question — Occurrence

Peut-on prouver qu’une occurrence logique n’est matérialisée qu’une fois ?

---

# 587. Acceptance Question — Misfire

Peut-on expliquer pourquoi une occurrence a été :

```text
executed

skipped

caught up
```

?

---

# 588. Acceptance Question — Concurrency

Peut-on faire courir deux transactions réellement concurrentes et prouver :

```text
limit=1
```

?

---

# 589. Acceptance Question — Retry

Peut-on prouver :

```text
same Execution

new Attempt

bounded count
```

?

---

# 590. Acceptance Question — Persistence

Peut-on tuer le process au pire moment possible et récupérer ?

---

# 591. Acceptance Question — Distributed

Peut-on faire croire à deux nœuds qu’ils ont le même travail et rester correct ?

---

# 592. Acceptance Question — Security

Peut-on injecter une configuration hostile sans obtenir :

```text
code execution

secret disclosure

unsafe network access
```

?

---

# 593. Acceptance Question — Observability

Peut-on répondre :

```text
why didn't this run?
```

sans lire manuellement 500 lignes de logs ?

---

# 594. Acceptance Question — Public API

Les exemples du README sont-ils :

```text
real

typed

tested
```

?

---

# 595. Definition finale de qualification

> **Une fonctionnalité PyScheduleKit n’est considérée comme supportée que lorsque son comportement nominal, ses invariants, ses erreurs, ses scénarios de reprise et ses frontières avec les adapters disposent de preuves automatisées correspondant au niveau de garantie annoncé.**

---

# 596. Modèle mental final

```text
            REQUIREMENT / INVARIANT
                     │
                     ▼
                TEST SCENARIO
                     │
                     ▼
             CONTROLLED INPUTS
                     │
                     ▼
              SYSTEM UNDER TEST
                     │
                     ▼
          OBSERVABLE DURABLE RESULT
                     │
                     ▼
                 ASSERTION
                     │
                     ▼
             ACCEPT / REJECT
```

---

# 597. Test Architecture

```text
                      Tests
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
   Domain Tests   Application Tests   Contract Tests
        │               │                │
        └───────────────┼────────────────┘
                        ▼
                 Integration Tests
                        │
                        ▼
                    Runtime
                        │
                        ▼
                       E2E
                        │
                        ▼
                  Distributed
```

---

# 598. Reliability Model

```text
Unit Tests
   │
   ▼
prove local semantics
   │
   ▼
Contract Tests
   │
   ▼
prove interchangeable adapters
   │
   ▼
Integration Tests
   │
   ▼
prove technology guarantees
   │
   ▼
E2E / Fault Injection
   │
   ▼
prove system guarantees
```

---

# 599. Final Release Principle

> **No guarantee without a test; no distributed guarantee without a race; no persistence guarantee without a crash scenario; no security guarantee without hostile input.**

---

# Conclusion

Le test model de PyScheduleKit ne repose donc pas uniquement sur :

```text
unit testing
```

mais sur une chaîne de preuves adaptée à la nature du problème :

```text
pure domain semantics
        │
        ▼
application orchestration
        │
        ▼
adapter contracts
        │
        ▼
transaction behavior
        │
        ▼
crash recovery
        │
        ▼
distributed races
        │
        ▼
security boundaries
```

Le framework devra être capable de prouver séparément :

```text
qu'un Trigger calcule correctement

qu'un Schedule suit son lifecycle

qu'une occurrence n'est pas perdue

qu'une Request n'est pas dupliquée

qu'un retry reste dans la même Execution

qu'une transaction rollback correctement

qu'un restart reprend le travail

que deux nœuds se coordonnent

qu'un stale owner est rejeté

qu'une configuration hostile n'exécute pas du code

qu'une décision est explicable
```

La notion de :

```text
"tests verts"
```

prend donc une signification plus forte :

> **Les tests verts constituent la preuve exécutable que les invariants documentés de PyScheduleKit sont effectivement respectés par l’implémentation.**

---

# Suite documentaire

Le prochain document est naturellement :

```text
28_IMPLEMENTATION_ROADMAP.md
```

Il pourra maintenant partir de cette matrice et organiser la construction de PyScheduleKit en lots progressifs :

```text
LOT-00 — Repository & Packaging Foundation

LOT-01 — Time Model

LOT-02 — Trigger Foundations

LOT-03 — Schedule Aggregate

LOT-04 — Occurrence Planning

LOT-05 — In-Memory Persistence

LOT-06 — SchedulerEngine

LOT-07 — Execution Lifecycle

LOT-08 — Local Runtime

LOT-09 — Misfire / Catch-Up

LOT-10 — Concurrency

LOT-11 — Retry

LOT-12 — Public API

LOT-13 — SQLite Persistence

LOT-14 — Observability

LOT-15 — Error & Security Hardening

LOT-16 — PostgreSQL / Outbox

LOT-17 — Crash Recovery

LOT-18 — Multi-Worker

LOT-19 — Multi-Scheduler

LOT-20 — Leases / Fencing

LOT-21 — Production Qualification
```

et répondre à la dernière grande question avant l’implémentation :

> **Dans quel ordre construire PyScheduleKit pour obtenir très tôt un scheduler fonctionnel tout en ajoutant progressivement les garanties de persistance, de résilience et de distribution sans sur-concevoir la première version ?**