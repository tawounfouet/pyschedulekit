# PyScheduleKit — Scheduler Engine & Evaluation Loop

**Document :** `17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle métier et runtime de référence  
**Nature :** Scheduler Engine — Evaluation Loop / Planning / Dispatch  
**Prérequis :**
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`
- `11_DATE_INTERVAL_AND_CRON_TRIGGERS.md`
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`
- `14_CONCURRENCY_AND_OVERLAP_MODEL.md`
- `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`
- `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`

---

# 1. Objectif

Les documents précédents ont défini séparément :

```text
Time
Clock
Schedule
Trigger
Occurrence
Misfire
Catch-Up
Concurrency
ExecutionRequest
Execution
Attempt
Retry
```

Il faut maintenant les assembler.

La question centrale devient :

> **Comment un scheduler passe-t-il continuellement du temps qui s'écoule à des décisions d'exécution durables, sans perdre ni dupliquer les occurrences ?**

Ce document définit donc :

```text
SchedulerEngine

SchedulerRuntime

EvaluationLoop

Schedule selection

Occurrence planning

Recovery planning

Concurrency evaluation

ExecutionRequest materialization

NextRunTime progression

Retry wake-up

Persistence boundaries

Failure isolation

Distributed execution seams
```

---

# 2. Le scheduler n'est pas une grosse boucle `while`

Un scheduler naïf pourrait ressembler à :

```python
while True:
    for job in jobs:
        if should_run(job):
            run(job)

    sleep(1)
```

Ce modèle cache presque tout le domaine réel :

```text
timezone
DST
misfires
recovery
concurrency
retries
persistence
crash recovery
distributed ownership
atomicity
```

PyScheduleKit doit utiliser un modèle plus explicite.

---

# 3. Question fondamentale du moteur

À chaque cycle d'évaluation, le moteur doit essentiellement répondre à :

```text
1. Quels Schedules méritent d'être examinés ?

2. Quelles occurrences sont réellement dues ?

3. Certaines occurrences ont-elles été manquées ?

4. Que faut-il faire de ces occurrences ?

5. Peuvent-elles être admises ?

6. Quelles ExecutionRequests faut-il matérialiser ?

7. Quelle sera la prochaine échéance du Schedule ?

8. Quels retries d'Executions deviennent également dus ?
```

---

# 4. Architecture conceptuelle

```text
                         Clock
                           │
                           ▼
                  Scheduler Runtime
                           │
                           ▼
                     Evaluation Loop
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
 Schedule candidates   Retry candidates   Recovery
          │                │
          ▼                ▼
 Scheduler Engine      Execution Runtime
          │
          ▼
 Occurrence Planner
          │
          ▼
 Misfire / Catch-Up
          │
          ▼
 Concurrency Evaluator
          │
          ▼
 ExecutionRequest
          │
          ▼
 Persistence / Outbox
          │
          ▼
 Executor
```

---

# 5. SchedulerEngine

`SchedulerEngine` représente :

> **Le cœur applicatif qui évalue les Schedules et produit des décisions de scheduling.**

Il ne doit pas être confondu avec :

```text
SchedulerRuntime
```

qui gère :

```text
boucle
sleep/wake-up
process lifecycle
threads
locks
shutdown
```

---

# 6. Classification

Le `SchedulerEngine` est principalement :

```text
Application Service
```

Il coordonne plusieurs objets de domaine.

---

# 7. Pourquoi pas Domain Service pur ?

Parce qu'il a besoin de :

```text
repositories
transactions
ports
persistence
```

et potentiellement :

```text
outbox
distributed coordination
```

Ces responsabilités dépassent le domaine pur.

---

# 8. Domain Services utilisés par l'Engine

Le moteur peut déléguer à :

```text
OccurrencePlanner

CatchUpPlanner

ConcurrencyEvaluator

RetryEvaluator
```

chacun restant plus pur.

---

# 9. SchedulerRuntime

`SchedulerRuntime` représente :

> **Le processus opérationnel qui fait vivre le SchedulerEngine dans le temps.**

Il gère notamment :

```text
start

stop

sleep

wake-up

shutdown

loop frequency

exception containment

health
```

---

# 10. Runtime versus Engine

```text
SchedulerRuntime
→ quand appeler le moteur ?

SchedulerEngine
→ que décider lorsque le moteur est appelé ?
```

---

# 11. Clock

Le Runtime ne doit pas appeler arbitrairement :

```python
datetime.now()
```

partout.

Il dépend de :

```text
Clock
```

---

# 12. EvaluationNow

À chaque cycle :

```text
evaluation_now = Clock.now()
```

est capturé une seule fois.

---

# 13. Same-now principle

Toute l'évaluation d'un batch doit idéalement utiliser :

```text
le même evaluation_now
```

pour éviter :

```text
Schedule A évalué à 10:00:00.001

Schedule B évalué à 10:00:00.970
```

avec des frontières incohérentes.

---

# 14. EvaluationCycle

Une abstraction utile peut être :

```text
EvaluationCycle
│
├── cycle_id
├── evaluation_now
├── started_at
└── maybe node_id
```

Classification :

```text
runtime/application Value Object
```

---

# 15. CycleId

Utile pour :

```text
logs
traces
metrics
diagnostics
```

mais pas essentiel au domaine V1.

---

# 16. Deux familles d'échéances

PyScheduleKit doit désormais gérer au moins deux types de timers :

```text
Schedule.next_run_time
```

et :

```text
Execution.next_attempt_at
```

---

# 17. Important

Ces deux timers utilisent potentiellement le même mécanisme technique :

```text
priority queue
database query
wake-up calculation
```

mais restent :

```text
deux concepts métier différents
```

---

# 18. Timeline globale

```text
Schedule Timer
     │
     ▼
Occurrence
     │
     ▼
Execution
     │
     ├── Attempt #1
     │
     └── retry timer
             │
             ▼
        Attempt #2
```

---

# 19. EvaluationLoop

Le Runtime peut conceptuellement fonctionner ainsi :

```text
while running:

    now = clock.now()

    process_due_schedules(now)

    process_due_retries(now)

    compute_next_wakeup()

    sleep_until(next_wakeup)
```

---

# 20. Mais ce pseudo-code reste incomplet

Il faut également traiter :

```text
waiting admissions

reconciliation

expired leases

cancellation

shutdown
```

à terme.

---

# 21. V1 Evaluation Loop

Pour une première version pédagogique :

```text
1. Capture now

2. Evaluate due schedules

3. Evaluate waiting admissions

4. Evaluate due retries

5. Determine next wake-up

6. Sleep
```

---

# 22. Schedule selection

Le moteur ne doit pas charger :

```text
tous les Schedules
```

à chaque cycle si leur nombre devient important.

Il doit sélectionner des :

```text
candidate schedules
```

---

# 23. ScheduleRepository

Port conceptuel :

```text
ScheduleRepository
```

avec une query comme :

```text
find_due_candidates(
    before_or_at=now,
    limit=N
)
```

---

# 24. Candidate ≠ Due

Important :

```text
database candidate
≠
domain-confirmed due Schedule
```

La requête SQL ne fait qu'un premier filtrage.

---

# 25. Exemple

La DB peut sélectionner :

```text
state = ACTIVE
AND next_run_time <= now
```

Mais le domaine doit encore prendre en compte :

```text
revision

Calendar

ScheduleWindow

policy

ownership
```

---

# 26. next_run_time

`next_run_time` devient ici extrêmement important.

Il permet d'éviter de recalculer en permanence tous les Triggers.

---

# 27. Nature du NextRunTime

Rappel :

```text
Trigger + ScheduleDefinition
=
source logique

NextRunTime
=
projection opérationnelle dérivée
```

---

# 28. Invariant important

Un `next_run_time` incorrect ne doit jamais être considéré comme la définition du Schedule.

Il doit pouvoir être :

```text
reconstruit
```

---

# 29. next_run_time meaning

Il doit être défini précisément comme :

> **La prochaine occurrence valide connue du Schedule qui n'a pas encore été traitée par le scheduler.**

---

# 30. Pas simplement next Trigger candidate

Car :

```text
Calendar
ScheduleWindow
```

peuvent modifier la prochaine occurrence valide.

---

# 31. OccurrencePlanner

Ainsi :

```text
OccurrencePlanner.next_occurrence(
    definition,
    after
)
```

est responsable du vrai `NextRunTime`.

---

# 32. Planning chain

```text
Trigger
   ↓
candidate
   ↓
Timezone/DST
   ↓
Calendar
   ↓
ScheduleWindow
   ↓
Occurrence
```

---

# 33. Reference cursor

Pour calculer l'occurrence suivante, il faut un :

```text
cursor
```

---

# 34. Possible cursor

```text
last_materialized_occurrence.scheduled_at
```

ou :

```text
previous next_run_time
```

selon architecture.

---

# 35. next_run_time driven loop

Une approche très pratique :

```text
Schedule.next_run_time
```

représente directement le prochain cursor à traiter.

---

# 36. Exemple

```text
next_run_time = 10:00
now = 09:58
```

Pas due.

À :

```text
now = 10:00
```

elle devient candidate.

---

# 37. Processing nominal

Pour une occurrence à l'heure :

```text
next_run_time = 10:00
now = 10:00
```

le moteur :

```text
1. materialise 10:00
2. calcule la suivante
3. met next_run_time = 11:00
```

---

# 38. Mais attention à l'ordre transactionnel

Si on fait :

```text
next_run_time = 11:00
COMMIT
```

avant de créer l'Occurrence/Request 10:00 :

```text
crash
```

→ 10:00 peut être perdue.

---

# 39. Inversement

Si on crée :

```text
Occurrence 10:00
```

puis crash avant d'avancer `next_run_time` :

au restart :

```text
10:00
```

sera revue.

---

# 40. Préférence

Il vaut mieux accepter la possibilité de :

```text
re-évaluer
```

une occurrence que de la perdre.

Puis utiliser :

```text
OccurrenceKey
```

pour la déduplication.

---

# 41. Core robustness principle

```text
duplicates can be detected

lost occurrences cannot easily be recovered
```

Donc la conception doit privilégier :

```text
at-least-once evaluation
+
idempotent materialization
```

---

# 42. Atomic schedule advancement

Idéalement :

```text
materialize occurrence/request
+
advance next_run_time
```

se produisent dans une même transaction.

---

# 43. Transaction boundary nominale

```text
BEGIN

load Schedule for update

validate revision/state

materialize occurrence

create ExecutionRequest or decision evidence

compute next valid occurrence

update next_run_time

save events/outbox

COMMIT
```

---

# 44. No network before commit

L'Executor ne doit pas être appelé :

```text
avant COMMIT
```

---

# 45. Pourquoi ?

Si :

```text
remote execution starts
```

puis transaction DB rollback :

```text
scheduler has no durable record
```

du travail déjà déclenché.

---

# 46. Transactional Outbox

Une architecture robuste peut utiliser :

```text
DB transaction
├── ExecutionRequest
└── OutboxMessage
```

puis un publisher séparé.

---

# 47. PyScheduleKit et Outbox

L'Outbox n'est pas nécessairement un objet métier du scheduler.

C'est un :

```text
infrastructure consistency pattern
```

---

# 48. Mais le modèle doit le permettre

D'où la règle :

```text
create durable intent
before external side effect
```

---

# 49. Nominal processing flow

```text
Schedule candidate
       │
       ▼
load + lock
       │
       ▼
verify state/revision
       │
       ▼
Occurrence due
       │
       ▼
Misfire evaluation
       │
       ▼
Concurrency evaluation
       │
       ▼
ExecutionRequest
       │
       ▼
persist + advance Schedule
       │
       ▼
COMMIT
       │
       ▼
dispatch later
```

---

# 50. Evaluation of one Schedule

Une méthode applicative conceptuelle :

```text
evaluate_schedule(
    schedule_id,
    evaluation_now
)
```

---

# 51. First step — load

```text
schedule = repository.get(schedule_id)
```

---

# 52. Verify current state

Si :

```text
ScheduleState != ACTIVE
```

le Schedule ne doit normalement pas produire de nouvelles occurrences.

---

# 53. PAUSED

Si un candidat DB stale remonte un `PAUSED` Schedule :

```text
skip safely
```

---

# 54. CANCELLED / COMPLETED

Même comportement :

```text
no occurrence
```

et éventuellement correction du `next_run_time`.

---

# 55. Second step — inspect next_run_time

Si :

```text
next_run_time is None
```

plusieurs cas :

```text
new schedule not initialized

trigger exhausted

projection missing/corrupt
```

---

# 56. Initialize NextRunTime

Pour un nouveau Schedule :

```text
OccurrencePlanner.next_occurrence(
    schedule,
    after=appropriate_reference
)
```

---

# 57. Appropriate reference

Cela dépend du contrat de création.

Un Schedule créé à :

```text
10:03
```

avec Cron :

```text
10:00 hourly
```

ne doit pas forcément produire rétroactivement :

```text
10:00
```

sauf policy explicite.

---

# 58. Schedule activation anchor

La création doit donc avoir une référence :

```text
activated_at
```

ou :

```text
start_at
```

---

# 59. Initial occurrence rule

Recommandation V1 :

> À l'activation, calculer la première occurrence strictement après `activation_reference`, sauf DateTrigger explicitement future.

---

# 60. Historical catch-up on creation

Ne doit pas arriver implicitement.

Pour cela :

```text
manual backfill
```

ou une policy explicite est préférable.

---

# 61. Third step — compare to now

Si :

```text
next_run_time > evaluation_now
```

le Schedule n'est plus due.

Cela peut arriver à cause :

```text
d'une race
d'une autre node
d'une projection mise à jour
```

---

# 62. If due

```text
next_run_time <= evaluation_now
```

il faut déterminer :

```text
une occurrence ou plusieurs occurrences historiques
```

---

# 63. Single nominal occurrence

Si :

```text
next_run_time ~= now
```

une occurrence nominale peut être évaluée.

---

# 64. Historical backlog

Si :

```text
next_run_time << now
```

on peut avoir :

```text
misfire / catch-up
```

---

# 65. Important

Le moteur ne doit pas faire :

```text
next_run_time = now
```

pour « rattraper ».

Il doit reconstruire les occurrences réelles.

---

# 66. CatchUpPlanner

```text
CatchUpPlanner.plan(
    schedule,
    from_occurrence=next_run_time,
    until=evaluation_now
)
```

peut produire :

```text
RecoveryPlan
```

---

# 67. RecoveryPlan output

```text
selected occurrences

skipped occurrences

coalesced groups

next future occurrence
```

---

# 68. Possible simplification

Le CatchUpPlanner peut aussi laisser l'OccurrencePlanner calculer la séquence et uniquement appliquer les policies.

---

# 69. Policy order

Pour chaque occurrence valide :

```text
1. Determine lateness

2. Apply MisfirePolicy

3. Apply catch-up/coalescing

4. Apply concurrency
```

---

# 70. Important

`ConcurrencyPolicy` s'applique après que l'on sait quelles occurrences méritent effectivement une Execution.

---

# 71. Multiple selected occurrences

Un recovery peut générer :

```text
O1
O2
O3
```

Il faut les traiter dans un ordre déterministe.

---

# 72. V1 order

```text
oldest scheduled_at first
```

---

# 73. Materialization limit

Ne jamais traiter un backlog sans limite dans une transaction géante.

---

# 74. Evaluation batch

Le moteur peut imposer :

```text
max_occurrences_per_schedule_evaluation
```

---

# 75. Example

```text
1000 missed occurrences
limit = 100
```

Cycle actuel :

```text
100
```

puis le Schedule reste immédiatement due pour un prochain cycle.

---

# 76. Pourquoi ?

Pour limiter :

```text
transaction duration
memory
lock time
latency
```

---

# 77. But CatchUpPolicy limit is different

Il existe :

```text
business recovery limit
```

et :

```text
technical batch size
```

Ne pas les confondre.

---

# 78. Example

Policy :

```text
Replay 10 000
```

Runtime batch :

```text
100 at a time
```

Les 10 000 restent sémantiquement sélectionnées, mais traitées progressivement.

---

# 79. Admission evaluation

Pour une occurrence sélectionnée :

```text
ConcurrencyKey
```

est déterminée.

Puis :

```text
ExecutionQueryPort
```

fournit un snapshot.

---

# 80. ConcurrencyEvaluator

```text
AdmissionDecision
=
evaluate(
    policy,
    active_snapshot,
    occurrence
)
```

---

# 81. Possible decisions

```text
ADMIT

DROP

WAIT
```

et éventuellement :

```text
COALESCE
```

---

# 82. ADMIT

Le moteur crée :

```text
ExecutionRequest
```

durable.

---

# 83. DROP

Le moteur ne crée pas d'Execution.

Mais il doit conserver :

```text
DecisionEvidence
```

au moins via événement/log/audit.

---

# 84. WAIT

La request peut devenir :

```text
WAITING_ADMISSION
```

comme établi dans le document 16.

---

# 85. Important

`WAITING_ADMISSION` demande une boucle de réévaluation indépendante.

---

# 86. Waiting admission query

Un repository/queue peut permettre :

```text
find_waiting_admissions(
    limit=N
)
```

---

# 87. EvaluationLoop phase 2

Donc le loop V1 devient :

```text
A. evaluate schedules
B. re-evaluate waiting admissions
C. process due retries
```

---

# 88. Waiting admission evaluation

Pour chaque request :

```text
reload current active count

apply admission again
```

---

# 89. But do not redo Misfire

Une request en `WAITING_ADMISSION` a déjà franchi la décision temporelle.

Elle ne redevient pas :

```text
Misfire
```

---

# 90. It may expire

Une future :

```text
AdmissionDeadline
```

peut annuler une request trop ancienne.

Hors V1 initial.

---

# 91. Atomic admission

Même si le domaine dit :

```text
ADMIT
```

il faut ensuite sécuriser réellement le slot.

---

# 92. ConcurrencyCoordinator

Port possible :

```text
try_acquire_slot(
    concurrency_key,
    limit,
    request_id
)
```

---

# 93. Result

```text
ACQUIRED

CONFLICT
```

---

# 94. If conflict

Le snapshot était obsolète.

Le moteur peut :

```text
move/request remain WAITING_ADMISSION
```

ou recalculer.

---

# 95. Never violate limit silently

La race ne doit pas transformer :

```text
max_instances=1
```

en deux Executions actives.

---

# 96. Execution creation

Après admission atomique :

```text
Execution.create_from(request)
```

peut être persistée en :

```text
QUEUED
```

---

# 97. Request transition

```text
ExecutionRequest
WAITING_ADMISSION/PENDING
→ DISPATCHED
```

---

# 98. Transaction

Idéalement :

```text
acquire logical slot
create Execution
mark Request DISPATCHED
```

se fait de manière atomique ou fortement coordonnée.

---

# 99. Executor queue

Après commit, l'Execution `QUEUED` devient candidate pour :

```text
Executor
```

---

# 100. Scheduler vs Executor Worker

Le SchedulerEngine ne doit pas obligatoirement démarrer lui-même les work units.

---

# 101. Separation

```text
Scheduler Engine
→ crée durablement le travail

Execution Worker
→ réalise le travail
```

---

# 102. Local runtime exception

Pour une petite V1 locale :

```text
same process
```

peut gérer les deux.

Mais les couches doivent rester conceptuellement séparées.

---

# 103. Worker loop

Une boucle d'exécution distincte peut ressembler à :

```text
find queued executions

claim one

create/start Attempt

invoke Executor

record result
```

---

# 104. Important

Cette boucle n'est pas la :

```text
Schedule evaluation loop
```

---

# 105. Two loops

On distingue donc :

```text
Scheduling Loop
```

et :

```text
Execution Loop
```

---

# 106. Scheduling Loop

Responsable de :

```text
Schedules
Occurrences
Policies
Requests
```

---

# 107. Execution Loop

Responsable de :

```text
Executions
Attempts
Results
Retries
```

---

# 108. Retry timer processing

Le Scheduling Runtime peut néanmoins avoir une phase :

```text
find executions
where state = RETRY_WAIT
and next_attempt_at <= now
```

---

# 109. Retry candidate

Encore une fois :

```text
candidate
≠
guaranteed runnable
```

Il faut :

```text
reload
validate state/version/deadline
```

---

# 110. Retry processing

```text
Execution RETRY_WAIT
      │
      ▼
next_attempt_at <= now
      │
      ▼
deadline still valid?
      │
   ┌──┴──┐
   │     │
  yes    no
   │     │
   ▼     ▼
Attempt  TIMED_OUT
 N+1
```

---

# 111. Retry processing does not use Trigger

Aucun :

```text
Schedule Trigger
```

dans ce chemin.

---

# 112. Retry does not re-run Concurrency admission

Si l'Execution conserve son slot logique pendant `RETRY_WAIT` :

```text
retry remains inside same admitted Execution
```

---

# 113. This is V1 policy

Comme décidé précédemment.

---

# 114. Retry wake-up

La prochaine échéance globale du Runtime doit donc prendre en compte :

```text
minimum Schedule.next_run_time

minimum Execution.next_attempt_at
```

---

# 115. Plus waiting admission?

Une request `WAITING_ADMISSION` n'a pas forcément un timestamp exact.

Elle peut être réévaluée :

```text
après completion d'une Execution
```

ou :

```text
à intervalle régulier
```

---

# 116. Event-driven wake-up

L'idéal :

```text
Execution terminal
→ signal
→ re-evaluate waiting admissions
```

---

# 117. Polling fallback

V1 peut simplement les rescanner :

```text
à chaque cycle
```

---

# 118. Global next wake-up

Conceptuellement :

```text
next_wakeup =
min(
    next_schedule_due,
    next_retry_due,
    runtime_poll_deadline
)
```

---

# 119. Runtime poll deadline

Même si aucune échéance n'est proche, le Runtime peut se réveiller périodiquement pour :

```text
health
shutdown
reconciliation
new schedule discovery
```

---

# 120. Poll interval

Exemple :

```text
30 seconds
```

mais cette valeur est infrastructure/configuration, pas domaine.

---

# 121. SleepUntil

Une abstraction runtime :

```text
Sleeper.sleep_until(instant)
```

peut améliorer les tests.

---

# 122. Monotonic time

Le document 08 a distingué :

```text
Wall Clock
Monotonic Clock
```

---

# 123. Scheduler semantics

Les deadlines métier utilisent :

```text
Wall Clock Instants
```

---

# 124. Sleep mechanics

La durée réelle de sleep peut utiliser :

```text
Monotonic Clock
```

pour résister aux ajustements système.

---

# 125. Example

```text
target wakeup wall time = 10:05
```

Runtime calcule :

```text
duration until target
```

puis attend avec timer monotonic.

---

# 126. Wall clock jump

Si l'horloge système avance brutalement :

```text
10:00 → 10:10
```

le prochain cycle détecte les occurrences manquées.

---

# 127. Misfire model handles this

Le Runtime ne doit pas essayer de masquer le saut en modifiant les timestamps.

---

# 128. Clock backward jump

Plus délicat :

```text
10:10 → 10:00
```

---

# 129. OccurrenceKey prevents duplicates

Une occurrence déjà matérialisée à :

```text
10:05
```

ne doit pas être recréée simplement parce que l'horloge repasse avant puis revient.

---

# 130. Durable checkpointing

D'où l'importance de :

```text
next_run_time
last materialized evidence
OccurrenceKey
```

---

# 131. Schedule claiming

Avec plusieurs scheduler nodes :

```text
Node A
Node B
```

peuvent sélectionner le même Schedule due.

---

# 132. Distributed problem

Il faut éviter qu'ils fassent simultanément :

```text
materialize same occurrence
```

---

# 133. Solution families

```text
row locking

SKIP LOCKED

lease

compare-and-swap

optimistic concurrency

unique OccurrenceKey
```

---

# 134. Best architecture

Utiliser plusieurs protections complémentaires :

```text
ownership/locking
+
unique occurrence identity
```

---

# 135. Why both?

Le lock réduit les courses.

La contrainte unique protège contre :

```text
bugs
lease expiry
network partitions
replays
```

---

# 136. ScheduleLease

Port possible :

```text
ScheduleLeaseManager
```

---

# 137. Lease semantics

```text
acquire(schedule_id)

renew(schedule_id)

release(schedule_id)
```

---

# 138. But V1 local scheduler

Peut ne pas utiliser de Lease.

---

# 139. Architecture seam

L'Engine doit simplement éviter d'être conçu comme si :

```text
il serait éternellement mono-process
```

---

# 140. Per-Schedule transaction

Une bonne granularité consiste à traiter chaque Schedule dans sa propre transaction.

---

# 141. Why?

Une erreur sur :

```text
Schedule A
```

ne doit pas rollback :

```text
Schedule B
C
D
```

---

# 142. Batch query + individual transactions

Pattern :

```text
select candidate IDs

for each schedule_id:
    transaction:
        evaluate schedule
```

---

# 143. Error isolation

Si un Schedule possède une configuration corrompue :

```text
log error
mark diagnostic
continue others
```

---

# 144. Do not crash whole scheduler

Un Schedule invalide ne doit pas nécessairement tuer le Runtime.

---

# 145. Fatal errors

Certaines erreurs peuvent néanmoins justifier l'arrêt :

```text
database unavailable globally

schema incompatible

critical configuration invalid

clock unavailable
```

---

# 146. Error taxonomy Runtime

```text
ScheduleEvaluationError

TransientInfrastructureError

FatalSchedulerError
```

peut être utile.

---

# 147. ScheduleEvaluationError

Local à :

```text
un Schedule
```

---

# 148. InfrastructureError

Peut nécessiter :

```text
loop-level backoff
```

---

# 149. Scheduler loop backoff

Attention :

```text
SchedulerRuntime retry/backoff
```

est encore différent de :

```text
Execution RetryPolicy
```

---

# 150. Example

DB indisponible :

```text
Runtime waits 5s before retrying loop
```

Cela n'appartient à aucune Execution.

---

# 151. Three backoff layers

Nous avons maintenant :

```text
SchedulerRuntime backoff

Dispatch/Execution retry backoff

Target internal backoff
```

Les noms doivent rester explicites.

---

# 152. Runtime failure loop

Conceptuellement :

```text
try:
    run evaluation cycle
except transient infrastructure error:
    runtime_backoff()
except fatal error:
    stop
```

---

# 153. Runtime backoff bounded

Même ici, éviter les hot loops.

---

# 154. Evaluation batch size

Config runtime :

```text
schedule_batch_size
```

---

# 155. Retry batch size

```text
retry_batch_size
```

---

# 156. Waiting admission batch size

```text
admission_batch_size
```

---

# 157. Fairness

Si des milliers de retries existent, ils ne doivent pas empêcher indéfiniment l'évaluation des nouveaux Schedules.

---

# 158. Phase fairness

V1 peut traiter :

```text
N schedules

N admissions

N retries
```

par cycle.

---

# 159. Or fixed order

```text
Schedules
Admissions
Retries
```

puis sleep minimal.

---

# 160. Starvation risk

Un flux infini dans la première phase peut empêcher les suivantes.

Donc :

```text
bounded work per phase
```

est important.

---

# 161. Evaluation budget

Une future abstraction :

```text
EvaluationBudget
```

peut limiter :

```text
items
time
```

par cycle.

Hors V1.

---

# 162. Runtime heartbeat

SchedulerRuntime peut exposer :

```text
last_cycle_started_at

last_cycle_completed_at

last_successful_cycle_at
```

---

# 163. Health

Un health endpoint peut déterminer :

```text
is scheduler loop alive?
```

---

# 164. Lag metrics

Une métrique essentielle :

```text
scheduler_lag
```

---

# 165. Schedule lag

Pour un Schedule due :

```text
now - next_run_time
```

---

# 166. Global lag

On peut mesurer :

```text
oldest due schedule age
```

---

# 167. Useful metrics

```text
evaluation_cycle_duration

candidate_schedules_count

evaluated_schedules_count

occurrences_materialized

occurrences_skipped

misfire_count

waiting_admission_count

retry_due_count

execution_requests_created

schedule_evaluation_errors
```

---

# 168. next_wakeup metric

Utile pour debug :

```text
scheduler_next_wakeup_timestamp
```

---

# 169. High-cardinality caution

Comme auparavant :

```text
ScheduleId
```

ne doit pas forcément devenir label Prometheus partout.

---

# 170. Logs/traces

Les identifiants fins appartiennent mieux aux :

```text
structured logs
traces
```

---

# 171. Cycle trace

Un trace peut contenir :

```text
cycle_id
evaluation_now
candidate_count
duration
```

---

# 172. Schedule evaluation trace

Peut contenir :

```text
schedule_id
revision
next_run_time_before
occurrences_selected
decisions
next_run_time_after
```

---

# 173. Explainability

Pour une occurrence, il doit être possible de répondre :

```text
Pourquoi a-t-elle été créée ?

Pourquoi maintenant ?

Pourquoi a-t-elle été skipped ?

Pourquoi attend-elle ?

Pourquoi le next_run_time vaut cette valeur ?
```

---

# 174. EvaluationResult

Un Domain/Application result utile :

```text
ScheduleEvaluationResult
```

---

# 175. Possible content

```text
schedule_id
revision
evaluated_at
occurrences_seen
requests_created
occurrences_skipped
next_run_time
completion_state
```

---

# 176. Why useful

Pour :

```text
testing
logging
diagnostics
```

sans inspecter directement la DB.

---

# 177. Pure evaluation versus mutation

Une architecture encore plus propre pourrait séparer :

```text
Plan
```

et :

```text
Apply
```

---

# 178. SchedulingPlan

Concept :

```text
SchedulingPlan
│
├── schedule_id
├── expected_revision
├── occurrence decisions
├── requests to create
├── next_run_time
└── schedule state changes
```

---

# 179. Then Application applies plan

```text
compute plan
→ validate revision
→ persist atomically
```

---

# 180. Advantages

```text
determinism
testability
dry-run
diagnostics
```

---

# 181. Disadvantage

Plus de modèles intermédiaires.

---

# 182. Recommendation

Le concept est très intéressant pour PyScheduleKit, même si V1 l'implémente simplement.

---

# 183. EvaluationPlan

Nom possible :

```text
ScheduleEvaluationPlan
```

---

# 184. Domain input

```text
Schedule

evaluation_now

ActiveExecutionSnapshot(s)

calendar data
```

---

# 185. Output

```text
occurrence decisions

request intents

next occurrence

state transition
```

---

# 186. Side-effect free planning

Le calcul du plan pourrait être presque entièrement pur.

---

# 187. Then transaction layer

Se charge de :

```text
deduplication
locks
insert
update
outbox
```

---

# 188. Very strong architecture

Cela donne :

```text
READ
 ↓
PLAN
 ↓
VALIDATE
 ↓
COMMIT
 ↓
DISPATCH
```

---

# 189. Plan staleness

Entre `READ` et `COMMIT`, l'état peut changer.

---

# 190. expected revision

Le plan doit porter :

```text
ScheduleRevision
PersistenceVersion
```

attendues.

---

# 191. If stale

```text
ScheduleEvaluationPlanStale
```

→ relecture/recalcul.

---

# 192. Same with concurrency snapshot

L'admission doit encore être finalisée atomiquement.

---

# 193. Therefore pure plan may contain

```text
ADMIT_IF_CAPACITY_AVAILABLE
```

plutôt qu'une garantie absolue.

---

# 194. Domain plan and infrastructure result

Encore :

```text
should
vs
can atomically
```

---

# 195. Schedule completion

Le moteur peut détecter :

```text
no next occurrence
```

---

# 196. If Trigger exhausted

```text
Schedule
ACTIVE → COMPLETED
```

---

# 197. Example DateTrigger

Une fois son unique occurrence traitée :

```text
next_occurrence = None
```

→ `COMPLETED`.

---

# 198. ScheduleWindow ended

Même résultat si :

```text
aucune occurrence future valide
```

---

# 199. Important

`COMPLETED` signifie :

```text
natural end
```

pas erreur.

---

# 200. Completion transaction

La création de la dernière occurrence et :

```text
Schedule → COMPLETED
```

peuvent être enregistrées dans la même transaction.

---

# 201. next_run_time after completion

Doit devenir :

```text
None
```

---

# 202. Pause interaction

Un `PAUSED` Schedule :

```text
next_run_time
```

peut être conservé pour diagnostic, mais ne doit pas être sélectionné.

---

# 203. Resume

À la reprise, comme décidé :

```text
les occurrences de pause sont supprimées en V1
```

Donc le moteur recalcule depuis :

```text
resume_at
```

---

# 204. Resume operation

L'application peut directement recalculer :

```text
next_run_time
```

lors du `resume()`.

---

# 205. Better than waiting for loop

Ainsi le repository possède immédiatement une projection correcte.

---

# 206. Reschedule

Même principe :

```text
ScheduleDefinition changes
```

→ recalcul immédiat de :

```text
next_run_time
```

---

# 207. Old occurrence safety

Les requests déjà créées sous l'ancienne revision continuent.

---

# 208. Candidate stale revision

Si un worker de scheduling avait chargé revision 4 puis qu'un reschedule produit revision 5 :

```text
commit based on revision 4
```

doit échouer.

---

# 209. Optimistic concurrency

Très important pour :

```text
pause
resume
reschedule
scheduler evaluation
```

concurrents.

---

# 210. Schedule persistence version

À distinguer de :

```text
ScheduleRevision
```

comme vu précédemment.

---

# 211. Example

Definition revision :

```text
7
```

Persistence version :

```text
42
```

Une simple mise à jour `next_run_time` peut faire :

```text
version 43
```

sans changer revision 7.

---

# 212. Exactly the right distinction

```text
ScheduleRevision
→ métier/configuration

PersistenceVersion
→ concurrency control
```

---

# 213. Processing concurrency between scheduler nodes

Query pattern possible :

```text
SELECT ...
FOR UPDATE SKIP LOCKED
```

dans une implementation SQL.

---

# 214. But domain independent

Le port n'expose pas forcément SQL semantics.

---

# 215. Repository method

Conceptuellement :

```text
claim_due_schedules(now, limit)
```

peut encapsuler ce mécanisme.

---

# 216. But careful

Un Repository métier ne devrait pas devenir trop infrastructure-specific.

Un :

```text
ScheduleClaimPort
```

séparé peut être préférable dans distributed mode.

---

# 217. V1

Simple `ScheduleRepository.find_due_candidates()` suffit.

---

# 218. Scheduler node identity

En distributed mode :

```text
SchedulerNodeId
```

peut être tracé.

---

# 219. Node ID use

```text
lease owner

logs

diagnostics
```

pas identité du Schedule.

---

# 220. Shutdown

Le Runtime doit soutenir :

```text
graceful stop
```

---

# 221. Stop new cycles

À shutdown :

```text
do not begin new scheduling batch
```

---

# 222. Finish current transaction

Une transaction en cours doit idéalement :

```text
commit
or rollback
```

proprement.

---

# 223. Do not leave half-applied plans

---

# 224. Execution workers

Peuvent avoir leur propre politique de shutdown :

```text
finish active

cancel

wait N seconds
```

séparée du SchedulerRuntime.

---

# 225. Runtime state

Possible :

```text
STOPPED
STARTING
RUNNING
STOPPING
FAILED
```

---

# 226. Do we need domain model?

Pas nécessairement.

C'est un lifecycle infrastructure/runtime.

---

# 227. Health state

Peut rester un enum opérationnel.

---

# 228. Initialization

Au démarrage, le Runtime doit :

```text
validate storage

load config

reconcile state

initialize next wake-up
```

---

# 229. Reconciliation before normal loop

Particulièrement :

```text
stale RUNNING attempts

overdue RETRY_WAIT

inconsistent next_run_time
```

---

# 230. V1 startup reconciliation

Minimum :

```text
find overdue retries

find due schedules
```

---

# 231. Local worker loss

Si executions locales RUNNING ont survécu en DB mais process a crash :

```text
mark attempts WORKER_LOST
```

puis retry evaluation.

---

# 232. This may be separate phase

```text
RuntimeReconciler
```

---

# 233. RuntimeReconciler

Responsabilité :

```text
repair operational state
after crashes/restarts
```

---

# 234. Not same as CatchUpPlanner

```text
CatchUpPlanner
→ missing Schedule occurrences
```

```text
RuntimeReconciler
→ inconsistent Execution runtime state
```

---

# 235. Important distinction

Un scheduler restart peut nécessiter les deux :

```text
Schedule catch-up

Execution reconciliation
```

---

# 236. Example

Pendant outage :

```text
Schedule missed 10:00

Execution from 09:00 was RUNNING
```

Au restart :

```text
CatchUpPlanner handles 10:00

RuntimeReconciler handles stale 09:00 Execution
```

---

# 237. Scheduler iteration model

Une architecture complète peut avoir :

```text
Cycle
├── reconcile runtime
├── evaluate due schedules
├── process waiting admissions
├── process due retries
└── compute next wake-up
```

---

# 238. Reconciliation frequency

Pas forcément à chaque cycle.

V1 peut faire :

```text
startup only
```

puis étendre.

---

# 239. No recursion

Le moteur ne doit pas appeler :

```text
evaluate_schedule()
```

récursivement lorsqu'une nouvelle occurrence est immédiatement due.

---

# 240. Why?

Une fréquence très courte ou un backlog important pourrait provoquer :

```text
deep recursion
long transaction
```

---

# 241. Iterative bounded processing

Toujours préférer :

```text
loops with explicit bounds
```

---

# 242. Zero-delay schedule problem

Un Trigger invalide pourrait produire :

```text
next == previous
```

---

# 243. Trigger contract prevents it

```text
next_after(reference) > reference
```

---

# 244. Safety assertion

Le SchedulerEngine doit quand même vérifier :

```text
next_run_time_after > current_occurrence
```

ou `None`.

---

# 245. Invalid progression

Sinon :

```text
InvalidTriggerProgression
```

---

# 246. Calendar infinite rejection

Un Calendar pourrait rejeter des milliers de Trigger candidates.

---

# 247. OccurrencePlanner guards

Utiliser :

```text
max_iterations
search_horizon
```

---

# 248. Scheduler Engine must respect planner failure

Ne pas boucler sans fin.

---

# 249. Misconfigured Schedule

Si aucune occurrence ne peut être trouvée dans les limites supportées :

```text
ScheduleEvaluationError
```

ou potentiellement :

```text
ScheduleBlocked
```

---

# 250. Avoid new state prematurely

V1 peut seulement enregistrer l'erreur et réessayer/alerter.

---

# 251. Poison Schedule

Un Schedule invalide peut être sélectionné à chaque cycle et générer constamment une erreur.

---

# 252. Error throttling

Runtime peut :

```text
temporarily suppress repeated evaluation
```

ou log rate limit.

---

# 253. But hidden pause is dangerous

Ne pas changer automatiquement :

```text
ACTIVE → PAUSED
```

sans policy explicite.

---

# 254. Operational quarantine future

Une future :

```text
SUSPENDED
```

pour erreur runtime répétée peut exister, mais hors modèle métier V1.

---

# 255. Evaluation error event

```text
ScheduleEvaluationFailed
```

peut être observé.

---

# 256. Retry evaluation of broken schedule

Runtime peut utiliser un :

```text
operational retry delay
```

pour éviter hot loop.

---

# 257. Again distinct from Schedule recurrence

---

# 258. Executor dispatch

Après request durable :

```text
publisher/worker
```

peut la transmettre au bon Executor.

---

# 259. Executor routing

Selon :

```text
TargetRef
```

un router peut choisir :

```text
PythonExecutor

WorkflowExecutorAdapter

IngestionExecutorAdapter

TransformExecutorAdapter
```

---

# 260. SchedulerEngine does not know concrete executor

Il connaît :

```text
TargetRef
```

et une abstraction.

---

# 261. TargetResolver

Possible :

```text
TargetRef
   ↓
ExecutorRouter
   ↓
Executor
```

---

# 262. But scheduling decision already complete

Le routing ne doit pas recalculer :

```text
due
misfire
concurrency
```

---

# 263. Dispatch failure

Si le publisher ne peut pas envoyer la request :

```text
request remains durable
```

---

# 264. Retry dispatch

Peut être géré par :

```text
Outbox Publisher
```

ou un `DispatchRetryPolicy`.

---

# 265. Do not recreate occurrence

Même après 100 dispatch retries :

```text
same ExecutionRequest
```

---

# 266. Important separation

```text
Occurrence materialization
≠
message delivery
```

---

# 267. Message deduplication

Le consumer peut utiliser :

```text
RequestId
```

pour éviter double Execution creation.

---

# 268. Unique Execution by Request

```text
UNIQUE(request_id)
```

est une protection forte.

---

# 269. Then outbox can deliver at-least-once

Sans créer plusieurs Executions.

---

# 270. Core consistency chain

```text
OccurrenceKey
→ deduplicates scheduling intent

RequestId
→ deduplicates execution command

ExecutionId
→ identifies logical run

AttemptId
→ identifies concrete attempt
```

---

# 271. Four identity layers

Très important pour comprendre le runtime.

---

# 272. Example

```text
OccurrenceKey:
schedule-42/rev7/10:00

RequestId:
req-ABC

ExecutionId:
exec-XYZ

AttemptId:
attempt-1
```

---

# 273. SchedulerLoop and new schedules

Un Schedule peut être créé pendant que le Runtime dort.

---

# 274. Problem

Si le Runtime dort jusqu'à :

```text
18:00
```

et un nouveau Schedule à :

```text
17:00
```

est créé à 16:30, il faut le réveiller.

---

# 275. Wake-up signal

Une architecture peut utiliser :

```text
condition variable

event

database notification

message bus
```

---

# 276. V1 polling fallback

Un maximum :

```text
max_sleep_interval
```

garantit qu'un nouveau Schedule sera vu assez vite.

---

# 277. Example

```text
next known due = 18:00
max sleep = 30s
```

Le runtime dort au plus :

```text
30s
```

---

# 278. Trade-off

Petit intervalle :

```text
responsive
more wake-ups
```

Grand intervalle :

```text
efficient
less responsive
```

---

# 279. Scheduler precision

La précision garantie dépend aussi :

```text
loop latency
DB latency
OS timer
executor latency
```

---

# 280. Do not claim hard real-time

PyScheduleKit est un :

```text
application scheduler
```

pas un hard real-time scheduler.

---

# 281. Due semantics

Une occurrence due à :

```text
10:00
```

peut être détectée à :

```text
10:00:00.150
```

sans être considérée comme défaillante si la GracePeriod le permet.

---

# 282. Granularity

Cron V1 peut être minute-level.

Runtime peut néanmoins tick plus finement.

---

# 283. Polling versus wake-up scheduler

Deux modèles :

```text
fixed polling
```

ou :

```text
sleep until nearest deadline
```

---

# 284. Fixed polling

```text
every second:
    query due items
```

Simple.

---

# 285. Dynamic wake-up

```text
compute earliest known timer
sleep until then
```

Plus efficace.

---

# 286. V1 recommendation

Commencer par :

```text
bounded polling
```

pour comprendre le domaine.

Puis évoluer vers :

```text
dynamic next wake-up
```

---

# 287. Why?

L'optimisation de wake-up ne doit pas masquer la logique métier.

---

# 288. Local prototype loop

Pseudo-code pédagogique :

```python
while runtime.running:
    now = clock.now()

    engine.evaluate_due_schedules(now)
    engine.evaluate_waiting_admissions(now)
    engine.evaluate_due_retries(now)

    sleeper.sleep(poll_interval)
```

---

# 289. Production evolution

```text
next_wakeup = min(
    repository.next_schedule_time(),
    execution_store.next_retry_time(),
    now + max_poll_interval,
)
```

---

# 290. Query next timer

Ports peuvent fournir :

```text
ScheduleRepository.get_earliest_next_run_time()
```

et :

```text
ExecutionRepository.get_earliest_retry_time()
```

---

# 291. But beware stale values

Ils sont des optimisations de wake-up.

Un wake-up un peu trop tôt est acceptable.

Un wake-up trop tard sera traité par misfire/retry recovery.

---

# 292. Time safety

Ne jamais considérer le wake-up mechanism comme garant de la sémantique.

La sémantique vient des :

```text
persisted timestamps
+
policies
```

---

# 293. Exactly right principle

```text
timer wakes the scheduler

stored temporal state tells the scheduler what is true
```

---

# 294. Scheduler engine API candidate

Conceptuellement :

```text
evaluate_due_schedules(
    now,
    limit
) -> EvaluationBatchResult
```

---

# 295. Single Schedule API

```text
evaluate_schedule(
    schedule_id,
    now
) -> ScheduleEvaluationResult
```

---

# 296. Waiting admission API

```text
evaluate_waiting_admissions(
    now,
    limit
)
```

---

# 297. Retry API

```text
evaluate_due_retries(
    now,
    limit
)
```

---

# 298. Runtime facade

```text
run_cycle()
```

peut appeler les trois.

---

# 299. But keep methods separable

Pour :

```text
tests
manual admin tools
recovery
```

---

# 300. Dry-run evaluation

Une fonctionnalité extrêmement utile :

```text
evaluate_schedule(..., dry_run=True)
```

---

# 301. Better architecture

Encore mieux :

```text
planner.plan(...)
```

toujours pur,

puis :

```text
engine.apply(plan)
```

---

# 302. Dry-run then free

On peut afficher le plan sans mutation.

---

# 303. Example diagnostic

```text
Schedule: daily-orders
Now: 12:37
Previous next run: 09:00

Detected occurrences:
09:00
10:00
11:00
12:00

Policy:
CatchUp(max=2, latest)

Selected:
11:00
12:00

Next future:
13:00
```

---

# 304. Operational CLI future

```text
pyschedule inspect schedule daily-orders
```

pourrait afficher :

```text
state
revision
next_run_time
next 5 occurrences
current lag
waiting executions
```

---

# 305. Evaluation simulation

```text
pyschedule simulate daily-orders \
  --from ... \
  --to ...
```

peut réutiliser :

```text
OccurrencePlanner
CatchUpPlanner
Concurrency mocks
```

---

# 306. Pedagogical value

C'est particulièrement utile pour PyScheduleKit dont l'objectif initial est l'apprentissage du domaine.

---

# 307. Testing the engine

Le SchedulerEngine doit être testable avec :

```text
FixedClock

InMemoryScheduleRepository

FakeExecutionQueryPort

FakeConcurrencyCoordinator

InMemoryRequestStore
```

sans sleep réel.

---

# 308. Never test business logic with real `time.sleep`

Les tests deviennent :

```text
lents
flaky
non déterministes
```

---

# 309. FixedClock example

```text
clock = FixedClock(10:00)

run_cycle()

clock.advance(1h)

run_cycle()
```

---

# 310. Test nominal

Schedule :

```text
hourly
next_run_time = 10:00
```

Now :

```text
10:00
```

Expected :

```text
Occurrence 10:00

Request created

next_run_time 11:00
```

---

# 311. Test early cycle

Now :

```text
09:59
```

Expected :

```text
no request
next_run_time unchanged
```

---

# 312. Test crash-safe duplicate

Simuler :

```text
Occurrence already exists
next_run_time stale
```

Evaluation must :

```text
not create duplicate
advance safely
```

---

# 313. Test catch-up

```text
next_run_time = 09:00
now = 12:30
```

Expected according to policy.

---

# 314. Test coalescing

Backlog :

```text
09
10
11
12
```

Policy latest.

Expected:

```text
1 request
```

with provenance.

---

# 315. Test concurrency DROP

Active count at limit.

Expected :

```text
no ExecutionRequest/Execution
decision evidence persisted
```

depending exact model.

---

# 316. Test WAITING_ADMISSION

Active count at limit + QUEUE.

Expected :

```text
Request WAITING_ADMISSION
```

---

# 317. Later slot free

Expected :

```text
Request DISPATCHED
Execution QUEUED
```

---

# 318. Retry due test

Execution :

```text
RETRY_WAIT
next_attempt_at = 10:00
```

Now :

```text
10:00
```

Expected :

```text
new Attempt allowed
```

---

# 319. Retry early

Now :

```text
09:59
```

Expected :

```text
unchanged
```

---

# 320. Retry deadline exceeded

Expected :

```text
Execution TIMED_OUT
```

---

# 321. Schedule reschedule race

Engine reads revision 4.

User reschedules to revision 5.

Engine commit must not apply old plan.

---

# 322. Pause race

Engine reads ACTIVE.

User pauses.

Old evaluation must fail version check or lock sequencing.

---

# 323. Multi-node same occurrence test

Two engine instances attempt same Schedule.

Expected :

```text
one durable occurrence/request
```

---

# 324. Outbox duplicate delivery test

Same Request delivered twice.

Expected :

```text
one Execution
```

---

# 325. Wall clock jump forward test

Clock from 10:00 to 13:00.

Expected :

```text
CatchUp/MisfirePolicy applied
```

---

# 326. Clock backward test

Already processed occurrences not duplicated.

---

# 327. Trigger exhaustion test

DateTrigger occurrence processed.

Expected :

```text
Schedule COMPLETED
next_run_time=None
```

---

# 328. Calendar exclusion test

Trigger candidate excluded.

Expected next_run_time jumps to next valid occurrence.

---

# 329. Planner iteration limit test

Pathological calendar/trigger combination must fail boundedly.

---

# 330. Batch fairness test

Huge Schedule backlog must not prevent due retries from ever being processed.

---

# 331. Restart test

Persist:

```text
Schedule due

Execution RETRY_WAIT
```

Restart Runtime.

Both should resume correctly.

---

# 332. Runtime state recovery

No ephemeral in-memory state should be required for correctness.

---

# 333. Strong invariant

> **A process restart may delay work, but must not erase the durable knowledge needed to decide what should happen next.**

---

# 334. What must be durable

At minimum :

```text
Schedule definition

Schedule state

Schedule revision

next_run_time / scheduling checkpoint

ExecutionRequests

Executions

Attempts

next_attempt_at

terminal results
```

---

# 335. What can remain ephemeral

```text
current loop iteration

temporary cache

in-process heap

sleep timer

local batch objects
```

---

# 336. Rebuildability

Any ephemeral optimization should be reconstructible from durable state.

---

# 337. Priority queue optimization

Le runtime peut charger :

```text
next timers
```

dans un heap mémoire.

---

# 338. But heap is not source of truth

Après restart :

```text
rebuild from DB
```

---

# 339. In-memory scheduler prototype

Pour apprentissage :

```text
ScheduleRepository
=
dict
```

et :

```text
priority queue
```

est parfait.

---

# 340. Production adapter

Plus tard :

```text
SQL
Redis
distributed store
```

peut remplacer sans modifier le domaine.

---

# 341. Avoid premature distributed complexity

Le document définit les seams.

L'implémentation initiale peut rester :

```text
single-process
single-node
```

---

# 342. Learning sequence recommended

```text
V0:
in-memory schedules
fixed polling

V1:
persistent local scheduler

V2:
crash recovery
outbox

V3:
multi-process claiming

V4:
distributed leases
```

---

# 343. Engine responsibility map

```text
SchedulerEngine owns:
─────────────────────
schedule evaluation
occurrence materialization
misfire recovery decisions
concurrency admission orchestration
next_run_time progression

SchedulerRuntime owns:
─────────────────────
loop lifecycle
sleep/wakeup
batching
runtime error backoff
health

ExecutionRuntime owns:
─────────────────────
execution queue
attempt lifecycle
executor integration
retry wakeup
result application
```

---

# 344. Domain services responsibility map

```text
OccurrencePlanner
→ next valid occurrence

CatchUpPlanner
→ recovery set

ConcurrencyEvaluator
→ logical admission decision

RetryEvaluator
→ post-failure retry decision
```

---

# 345. Infrastructure responsibility map

```text
Repositories
→ durable state

ConcurrencyCoordinator
→ atomic slot control

LeaseManager
→ distributed ownership

Outbox
→ reliable publication

ExecutorAdapter
→ concrete work execution
```

---

# 346. Anti-pattern — one god Scheduler class

Éviter :

```text
Scheduler
├── parses cron
├── opens SQL connections
├── runs HTTP
├── starts threads
├── retries
├── catches all exceptions
├── serializes YAML
└── owns every state machine
```

---

# 347. Anti-pattern — query every Schedule every second

Cela fonctionne pour un prototype, mais ne doit pas devenir la seule architecture possible.

---

# 348. Anti-pattern — DB determines domain due logic

Éviter de mettre toute la logique dans :

```text
WHERE ...
```

Le DB sélectionne des candidats.

Le domaine confirme.

---

# 349. Anti-pattern — execute before commit

Très important.

---

# 350. Anti-pattern — advance checkpoint before materialization

Risque de perte.

---

# 351. Anti-pattern — ignore duplicate occurrence errors

Un conflit sur `OccurrenceKey` peut être une situation normale de concurrence.

Il doit être interprété correctement.

---

# 352. Anti-pattern — duplicate is always fatal

Dans distributed scheduling :

```text
duplicate occurrence insert
```

peut simplement signifier :

```text
another node already processed it
```

---

# 353. Anti-pattern — recalculate scheduled_at as now

Jamais pour recovery.

---

# 354. Anti-pattern — process unlimited backlog in one transaction

---

# 355. Anti-pattern — retry via Trigger

---

# 356. Anti-pattern — waiting admission re-runs MisfirePolicy

La décision temporelle est déjà figée.

---

# 357. Anti-pattern — runtime sleep controls semantics

Si le scheduler se réveille tard :

```text
policies
```

doivent traiter ce retard.

---

# 358. Anti-pattern — in-memory timer as source of truth

---

# 359. Anti-pattern — one transaction for all schedules

---

# 360. Anti-pattern — one broken Schedule stops Runtime

Sauf erreur infrastructure réellement globale.

---

# 361. Anti-pattern — hidden automatic pause on errors

---

# 362. Anti-pattern — distributed execution without stable identities

Il faut :

```text
OccurrenceKey

RequestId

ExecutionId

AttemptId
```

---

# 363. Anti-pattern — scheduler node local active count

Pour distributed concurrency, cela ne suffit pas.

---

# 364. Anti-pattern — no optimistic versioning

Les opérations :

```text
reschedule
pause
evaluate
```

peuvent alors s'écraser.

---

# 365. Anti-pattern — mixed wall and monotonic timestamps

Les timestamps métier doivent rester des Instants muraux cohérents.

---

# 366. Anti-pattern — `sleep(interval)` forever

Cela accumule potentiellement du drift.

---

# 367. Better

À chaque cycle :

```text
recompute next temporal truth
```

depuis le Clock et l'état durable.

---

# 368. Fixed polling drift

Même avec polling :

```text
run cycle
sleep N
```

peut dériver si cycle prend du temps.

---

# 369. Better fixed cadence

Utiliser un timer monotonic pour :

```text
target next poll
```

si précision nécessaire.

---

# 370. But domain remains unaffected

---

# 371. Evaluation ordering

Pour une seule Schedule :

```text
1. Lock/load

2. Validate lifecycle

3. Determine overdue occurrence set

4. Apply Calendar/Window

5. Apply Misfire/Catch-Up

6. Apply Coalescing

7. Determine admission

8. Materialize decisions

9. Calculate next occurrence

10. Persist atomically
```

---

# 372. Why calculate next occurrence near end?

Parce que le traitement actuel peut affecter le curseur opérationnel.

---

# 373. But pure plan may compute it earlier

C'est acceptable tant que :

```text
plan is validated atomically
```

---

# 374. Complete Schedule algorithm

Conceptuellement :

```text
evaluate(schedule, now):

    if not ACTIVE:
        return

    cursor = schedule.next_run_time

    if cursor is None:
        cursor = initialize_next_occurrence()

    if cursor > now:
        return

    occurrences = reconstruct_due_occurrences(
        from=cursor,
        until=now,
    )

    recovery_plan = apply_misfire_policy(occurrences)

    execution_intents = apply_coalescing(recovery_plan)

    for intent in execution_intents:
        admission = evaluate_concurrency(intent)

        materialize(admission)

    next_time = find_next_future_occurrence(after=last_cursor)

    persist(schedule, next_time, decisions)
```

---

# 375. Important simplification

Ce pseudo-code omet :

```text
transaction races
batching
distributed ownership
```

qui doivent entourer l'algorithme.

---

# 376. Retry algorithm

```text
evaluate_retry(execution, now):

    if execution.state != RETRY_WAIT:
        return

    if now < next_attempt_at:
        return

    if deadline exceeded:
        timeout execution
        return

    atomically start next Attempt
```

---

# 377. Waiting admission algorithm

```text
evaluate_waiting_request(request, now):

    if request.state != WAITING_ADMISSION:
        return

    snapshot = query active executions

    decision = evaluate concurrency

    if capacity:
        atomically acquire slot
        create Execution
        mark request DISPATCHED
```

---

# 378. Engine return values

Éviter des méthodes :

```text
void
```

partout.

Des résultats explicites améliorent l'observabilité.

---

# 379. BatchResult

```text
EvaluationBatchResult
│
├── candidates
├── processed
├── created_requests
├── skipped
├── errors
└── duration
```

---

# 380. ScheduleResult

```text
ScheduleEvaluationResult
│
├── schedule_id
├── previous_next_run
├── new_next_run
├── decisions
└── state_after
```

---

# 381. RetryBatchResult

Même idée.

---

# 382. Not all public API

Ces objets peuvent rester internes.

---

# 383. Scheduler engine idempotence

Appeler :

```text
evaluate_schedule(schedule, same now)
```

deux fois doit idéalement produire :

```text
pas de nouvelle ExecutionRequest dupliquée
```

---

# 384. How?

Grâce à :

```text
OccurrenceKey
Request deduplication
Schedule checkpoint
```

---

# 385. Strong test

```text
run_cycle(now)
run_cycle(now)
```

Expected :

```text
same durable result
```

---

# 386. Event publication idempotence

Outbox records doivent avoir des identifiants stables.

---

# 387. Possible EventId

Dérivé de :

```text
RequestId
```

ou généré lors du commit.

---

# 388. Publisher retries

Ne changent pas le state métier.

---

# 389. Execution consumer idempotence

Consumer reçoit deux fois :

```text
RequestId=req42
```

→ same Execution.

---

# 390. This closes reliability chain

```text
scheduler evaluation at least once
+
DB deduplication
+
outbox at least once
+
consumer deduplication
=
robust practical semantics
```

---

# 391. Not exactly-once

Le système ne doit pas appeler cela :

```text
exactly once execution
```

sans coopération complète du Target.

---

# 392. Better terminology

```text
exactly-once materialization of logical occurrence
```

peut être approché par contrainte DB.

Mais les side effects restent autre chose.

---

# 393. SchedulerEngine and PyWorkflowKit

Pour :

```text
TargetRef("workflow:daily-orders")
```

le moteur ne connaît pas :

```text
DAG
steps
dependencies
```

---

# 394. It creates request

Puis :

```text
WorkflowExecutorAdapter
```

soumet le Workflow.

---

# 395. Same with PyIngestKit

```text
TargetRef("ingestion:orders")
```

---

# 396. Same with PyTransformKit

```text
TargetRef("transform:daily-metrics")
```

---

# 397. Shared ExecutionContext

Le request peut contenir :

```text
scheduled_at

OccurrenceKey

CorrelationId

ScheduleId
```

que le framework cible propage.

---

# 398. This enables ecosystem tracing

```text
PyScheduleKit
      │
      ▼
PyWorkflowKit
      │
      ├── PyIngestKit
      └── PyTransformKit
```

avec la même :

```text
CorrelationId
```

---

# 399. But no shared mega-domain

Seuls des contrats légers sont partagés.

---

# 400. Runtime scalability

À terme, la capacité peut être étendue horizontalement :

```text
multiple Scheduler nodes

multiple Execution workers
```

---

# 401. Scheduler scaling problem

Nécessite :

```text
claiming
leases
deduplication
```

---

# 402. Worker scaling problem

Nécessite :

```text
queue
claiming
Attempt coordination
```

---

# 403. Different problems

Ne pas les confondre.

---

# 404. Scheduler sharding future

Les Schedules pourraient être répartis par :

```text
hash(schedule_id)
```

ou tenant/namespace.

---

# 405. Not V1

Mais le modèle `ScheduleId` stable le permet.

---

# 406. Runtime partitioning

Les retries peuvent être traités par un pool différent.

---

# 407. Recovery traffic

Peut également avoir une capacité dédiée.

---

# 408. Again future concerns

Le moteur métier n'a pas à connaître ces détails.

---

# 409. Security

Les Schedules persistés sont des entrées potentiellement non sûres.

---

# 410. Trigger decoding

Doit utiliser :

```text
safe declarative codecs
```

---

# 411. TargetRef

Ne doit pas permettre implicitement :

```text
arbitrary eval/import
```

---

# 412. Execution payload

Doit être validé avant dispatch.

---

# 413. Metadata

Ne doit pas permettre de contourner :

```text
typed policy fields
```

---

# 414. Multi-tenant future

Si PyScheduleKit devient multi-tenant :

```text
ScheduleRepository queries
```

devront être tenant-scoped.

---

# 415. ConcurrencyKey

Pourra également être tenant-scoped.

---

# 416. But not core V1

---

# 417. Audit model

Le scheduler doit pouvoir conserver au minimum :

```text
ScheduleCreated

ScheduleRescheduled

Occurrence decision

ExecutionRequest created

Execution terminal result
```

selon le niveau choisi.

---

# 418. SchedulingDecision evidence

Une occurrence skipped doit également être explicable.

---

# 419. No execution does not mean no history

Si policy :

```text
SKIP
```

une trace métier est utile.

---

# 420. Decision persistence options

```text
Occurrence record

DecisionEvent

AuditLog
```

---

# 421. V1 recommendation

Pas nécessairement matérialiser chaque candidate occurrence rejetée comme Entity.

Un événement/audit structuré peut suffire.

---

# 422. Important for huge schedules

Sinon un Schedule every second qui skip souvent produit une quantité massive d'objets.

---

# 423. MaterializedOccurrence

Peut être réservé aux occurrences ayant :

```text
un intérêt durable
```

par exemple request créée ou décision importante.

---

# 424. Natural occurrence identity remains available

Même sans table occurrence dédiée.

---

# 425. Scheduler checkpoints

Une architecture sans table `Occurrence` peut fonctionner avec :

```text
Schedule.next_run_time
+
ExecutionRequest.occurrence_key
```

---

# 426. ERD implication

Le document 07 pourra éventuellement être ajusté plus tard selon ce choix.

---

# 427. Learning recommendation

Pour la première implémentation :

```text
persist Schedule
persist ExecutionRequest
persist Execution
persist Attempt
```

et garder `Occurrence` comme VO.

---

# 428. Exactly aligned with earlier DDD choice

---

# 429. SchedulerEngine dependencies

Proposition :

```text
SchedulerEngine
│
├── Clock
├── ScheduleRepository
├── ExecutionRequestRepository
├── ExecutionQueryPort
├── ConcurrencyCoordinator
├── OccurrencePlanner
├── CatchUpPlanner
└── Event/Outbox Port
```

---

# 430. ExecutionRuntime dependencies

```text
ExecutionRuntime
│
├── Clock
├── ExecutionRepository
├── Executor
├── RetryEvaluator
└── Event/Outbox Port
```

---

# 431. SchedulerRuntime dependencies

```text
SchedulerRuntime
│
├── Clock
├── Sleeper
├── SchedulerEngine
├── ExecutionRuntime
└── RuntimeConfiguration
```

---

# 432. Could be separate processes

Yes.

These interfaces allow:

```text
scheduler process
worker process
```

separation later.

---

# 433. V1 can instantiate together

```text
Application
├── SchedulerRuntime
└── ExecutionRuntime
```

in one process.

---

# 434. Package sketch

```text
pyschedulekit/
│
├── domain/
│   ├── schedule/
│   ├── occurrence/
│   ├── execution/
│   └── policies/
│
├── application/
│   ├── scheduler_engine.py
│   ├── execution_runtime.py
│   ├── occurrence_planner.py
│   ├── catchup_planner.py
│   ├── concurrency_evaluator.py
│   └── retry_evaluator.py
│
├── ports/
│   ├── clock.py
│   ├── schedule_repository.py
│   ├── execution_repository.py
│   ├── executor.py
│   └── event_publisher.py
│
└── infrastructure/
    ├── persistence/
    ├── executors/
    └── runtime/
```

Illustratif uniquement.

---

# 435. SchedulerEngine must not import infrastructure

Domain/application direction :

```text
Infrastructure
      ↓
implements Ports
      ↓
Application
      ↓
Domain
```

---

# 436. Hexagonal architecture fit

PyScheduleKit se prête naturellement à :

```text
Ports & Adapters
```

---

# 437. Why?

Le scheduler dépend fortement de :

```text
Clock

Storage

Execution

Coordination
```

mais son modèle métier ne doit pas dépendre des technologies concrètes.

---

# 438. Evaluation phases final proposal

```text
PHASE 0
capture evaluation_now

PHASE 1
evaluate due Schedules

PHASE 2
evaluate waiting admissions

PHASE 3
evaluate due retries

PHASE 4
optional reconciliation

PHASE 5
compute next wake-up
```

---

# 439. Phase ordering is not semantic truth

Une implémentation distributed peut exécuter ces phases séparément.

---

# 440. Semantic contracts matter more

Chaque phase doit respecter ses propres invariants.

---

# 441. Schedule evaluation invariant

```text
same logical occurrence
→ at most one durable automatic request
```

---

# 442. Admission invariant

```text
logical concurrency limit
is not exceeded
```

---

# 443. Retry invariant

```text
at most one active Attempt per Execution
```

---

# 444. Terminal invariant

```text
terminal remains terminal
```

---

# 445. Restart invariant

```text
durable state is sufficient
to resume decision-making
```

---

# 446. Time invariant

```text
all temporal decisions
use explicit Clock/context
```

---

# 447. No hidden scheduling state

Critical state must not live only inside :

```text
Python objects
threads
timers
```

---

# 448. Evaluation loop state diagram

```text
                  ┌─────────────────┐
                  │  Capture `now`  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Due Schedules   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Waiting         │
                  │ Admissions      │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Due Retries     │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Reconciliation  │
                  │ optional        │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Next Wake-up    │
                  └────────┬────────┘
                           │
                           ▼
                         SLEEP
                           │
                           └───────────────┐
                                           │
                                           ▼
                                      next cycle
```

---

# 449. Full scheduling flow

```text
Clock
  │
  ▼
evaluation_now
  │
  ▼
ScheduleRepository
  │
  ▼
Candidate Schedule
  │
  ▼
OccurrencePlanner
  │
  ▼
Due / Historical Occurrences
  │
  ▼
Misfire + Catch-Up
  │
  ▼
Coalescing
  │
  ▼
ConcurrencyEvaluator
  │
  ├── DROP
  │
  ├── WAIT
  │
  └── ADMIT
          │
          ▼
   ExecutionRequest
          │
          ▼
     Persistence
          │
          ▼
        COMMIT
          │
          ▼
       Dispatch
```

---

# 450. Full execution flow

```text
ExecutionRequest
      │
      ▼
Execution QUEUED
      │
      ▼
Attempt RUNNING
      │
 ┌────┴────────┐
 │             │
 ▼             ▼
SUCCESS       FAILURE
 │             │
 ▼             ▼
Execution   RetryEvaluator
SUCCESS         │
          ┌─────┴─────┐
          │           │
         STOP       RETRY
          │           │
          ▼           ▼
       FAILED     RETRY_WAIT
                      │
                      ▼
                 next_attempt_at
                      │
                      ▼
                  Attempt N+1
```

---

# 451. Full temporal model

PyScheduleKit gère donc plusieurs instants distincts :

```text
scheduled_at

detected_at

request_created_at

admitted_at

execution_queued_at

execution_started_at

attempt_started_at

attempt_finished_at

next_attempt_at

execution_finished_at
```

---

# 452. Never collapse them

Sinon impossible de mesurer correctement :

```text
scheduler lag

admission wait

executor queue latency

attempt duration

retry backoff

end-to-end time
```

---

# 453. Production qualification questions

Avant de considérer l'Engine robuste :

```text
Que se passe-t-il si le process crash après chaque étape ?

Que se passe-t-il si deux nodes évaluent le même Schedule ?

Que se passe-t-il si la DB commit mais le dispatch échoue ?

Que se passe-t-il si le dispatch réussit deux fois ?

Que se passe-t-il si l'horloge saute ?

Que se passe-t-il si un Schedule est reschedulé pendant l'évaluation ?

Que se passe-t-il si un worker disparaît ?

Que se passe-t-il si un retry devient due pendant un restart ?
```

---

# 454. Crash-point analysis

Une méthode pédagogique importante consiste à tester :

```text
crash before transaction

crash during transaction

crash after commit

crash before dispatch

crash after dispatch

crash before ack
```

---

# 455. Desired property

À chaque crash point :

```text
no logical work silently disappears
```

et :

```text
duplicates remain identifiable
```

---

# 456. Scheduler semantics statement

PyScheduleKit devrait pouvoir annoncer quelque chose comme :

> Le scheduler maintient durablement l'intention des occurrences, peut réévaluer après interruption et utilise des identités stables pour rendre les répétitions de traitement détectables.

---

# 457. Better than claiming exactly-once

---

# 458. V1 implementation recommendation

La première vraie version du moteur devrait volontairement rester :

```text
single process

single scheduler node

persistent or in-memory repository

fixed polling loop

Date/Interval/Cron triggers

OccurrencePlanner

Misfire policies

Concurrency limit

Execution state machine

bounded retries
```

---

# 459. V1.1

Ajouter :

```text
SQL persistence

restart recovery

optimistic locking
```

---

# 460. V1.2

Ajouter :

```text
transactional outbox

separate worker loop

idempotent dispatch
```

---

# 461. V2

Ajouter :

```text
distributed claiming

leases

multiple scheduler nodes
```

---

# 462. Do not begin with V2

L'objectif est de comprendre :

```text
les objets
leurs invariants
leurs interactions
```

avant la coordination distribuée avancée.

---

# 463. Core Engine pseudo-contract

```text
SchedulerEngine.evaluate(now)
```

ne devrait pas signifier :

```text
execute everything
```

mais :

```text
evaluate durable scheduling state
and materialize appropriate runtime intent
```

---

# 464. This is the key abstraction

Le moteur transforme :

```text
Time
+
Schedule State
+
Runtime Evidence
```

en :

```text
Durable Scheduling Decisions
```

---

# 465. Formal view

On peut presque représenter :

```text
Evaluation(
    Schedule,
    TimeContext,
    RuntimeSnapshot
)
→
SchedulingPlan
```

---

# 466. Then

```text
Apply(
    SchedulingPlan,
    DurableState
)
→
NewDurableState
```

---

# 467. This decomposition is powerful

Elle sépare :

```text
reasoning
```

de :

```text
side effects
```

---

# 468. Recommended long-term architecture

```text
                  READ MODEL
                      │
                      ▼
             Scheduling Planner
              [mostly pure]
                      │
                      ▼
               SchedulingPlan
                      │
                      ▼
            Transactional Applier
                      │
                      ▼
                 DURABLE STATE
                      │
                      ▼
                   OUTBOX
                      │
                      ▼
                  EXECUTOR
```

---

# 469. Why this matters for AI-generated code

Une architecture explicite permet de vérifier plus facilement :

```text
where time is read

where DB is mutated

where network calls happen

where policies are evaluated
```

et évite les fonctions monolithiques impossibles à auditer.

---

# 470. Core anti-responsibilities of SchedulerEngine

Il ne doit pas :

```text
exécuter directement du code métier

implémenter Cron parsing lui-même dans la loop

gérer les étapes internes d'un workflow

contenir des credentials

réaliser des transformations de données

devenir un message broker

devenir un worker autoscaler

gérer des ressources CPU
```

---

# 471. What SchedulerEngine owns

```text
temporal evaluation

occurrence recovery

scheduling policy application

request materialization

schedule progression
```

---

# 472. What ExecutionRuntime owns

```text
attempt lifecycle

executor interaction

retry timers

execution completion
```

---

# 473. What SchedulerRuntime owns

```text
continuous operation

wake-up

batch cadence

lifecycle

health
```

---

# 474. Core invariants

```text
1.
The Runtime captures one explicit `now`
per evaluation cycle.

2.
Database candidate selection does not replace
domain evaluation.

3.
Trigger candidates are not automatically
valid Schedule occurrences.

4.
`next_run_time` is derived operational state.

5.
Occurrence identity is stable.

6.
Materialization is idempotent.

7.
A Schedule checkpoint is never advanced
in a way that can silently lose work.

8.
External side effects occur only after
durable scheduling intent exists.

9.
Misfire, concurrency and retry remain
separate decision layers.

10.
Waiting admission does not re-run
the temporal scheduling decision.

11.
Retries do not use the Schedule Trigger.

12.
Schedule revisions are checked
before applying an evaluation plan.

13.
Persistent versions protect concurrent mutations.

14.
A single broken Schedule should not stop
all other Schedule evaluations.

15.
Processing is bounded per cycle.

16.
Ephemeral timers are never the sole source
of scheduling truth.

17.
A restart can reconstruct the next decisions
from durable state.

18.
Distributed coordination may change,
but domain semantics remain stable.

19.
Exactly-once side effects are not promised
by the scheduler alone.

20.
All critical runtime transitions are observable.
```

---

# 475. V1 decisions

```text
1.
SchedulerEngine is an Application Service.

2.
SchedulerRuntime owns the continuous loop.

3.
OccurrencePlanner remains a Domain Service.

4.
CatchUpPlanner handles historical recovery.

5.
ConcurrencyEvaluator handles logical admission.

6.
RetryEvaluator handles post-attempt retries.

7.
The main runtime loop processes:
   due schedules,
   waiting admissions,
   due retries.

8.
A single `evaluation_now` is used per cycle.

9.
`next_run_time` is persisted as an operational projection.

10.
OccurrenceKey protects against duplicate
logical occurrence materialization.

11.
RequestId protects execution command identity.

12.
External execution occurs only after commit.

13.
V1 can use fixed polling.

14.
Polling interval is infrastructure configuration.

15.
Per-Schedule evaluation is bounded and isolated.

16.
Each Schedule is preferably evaluated
inside its own transaction.

17.
ScheduleRevision and PersistenceVersion
remain separate concepts.

18.
V1 is single-node but leaves explicit seams
for leases/claiming.

19.
Retry timers use `next_attempt_at`,
not Trigger.

20.
Runtime state must be restartable
from durable data.
```

---

# 476. Acceptance criteria

Le moteur est suffisamment défini lorsque l'on peut répondre sans ambiguïté à :

```text
Comment le scheduler choisit-il les Schedules à examiner ?

Que signifie next_run_time ?

Comment calcule-t-il une vraie occurrence ?

Comment récupère-t-il plusieurs occurrences manquées ?

Quand la MisfirePolicy intervient-elle ?

Quand la ConcurrencyPolicy intervient-elle ?

Que devient une occurrence blocked by concurrency ?

Quand l'Execution est-elle créée ?

Quand le Schedule avance-t-il son next_run_time ?

Comment éviter de perdre une occurrence lors d'un crash ?

Comment éviter de créer deux fois la même occurrence ?

Pourquoi l'Executor n'est-il appelé qu'après commit ?

Comment les retries sont-ils réveillés ?

Pourquoi les retries n'utilisent-ils pas Trigger ?

Comment calculer le prochain wake-up global ?

Que se passe-t-il après restart ?

Comment deux scheduler nodes pourraient-ils coopérer ?

Comment une modification concurrente du Schedule est-elle détectée ?

Comment isoler l'échec d'un seul Schedule ?

Quelles données doivent être durables ?

Quelles optimisations peuvent rester en mémoire ?
```

---

# 477. Modèle mental final

```text
                         CLOCK
                           │
                           ▼
                    EVALUATION CYCLE
                           │
              ┌────────────┼─────────────┐
              │            │             │
              ▼            ▼             ▼
        Due Schedules  Waiting       Due Retries
                       Admissions
              │            │             │
              ▼            ▼             ▼
        Occurrence     Concurrency    Retry Timer
         Planning        Recheck
              │            │             │
              ▼            ▼             ▼
        Misfire /       Admission      Attempt
         Catch-Up        Decision       Start
              │
              ▼
         Concurrency
              │
              ▼
       ExecutionRequest
              │
              ▼
          PERSIST
              │
              ▼
            COMMIT
              │
              ▼
          EXECUTION
```

---

# 478. Vue architecture finale

```text
┌─────────────────────────────────────────────────────────┐
│                    SchedulerRuntime                     │
│                                                         │
│  start · stop · loop · wake-up · health · batching     │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     SchedulerEngine                     │
│                                                         │
│  select → evaluate → plan → persist                    │
└────────────┬────────────┬────────────┬─────────────────┘
             │            │            │
             ▼            ▼            ▼
     OccurrencePlanner CatchUpPlanner ConcurrencyEvaluator
             │
             └────────────┬────────────┘
                          ▼
                 ExecutionRequest
                          │
                          ▼
                    Durable Store
                          │
                          ▼
                        Outbox
                          │
                          ▼
                  ExecutionRuntime
                          │
                          ▼
                       Executor
                          │
                          ▼
                       Attempt
                          │
                          ▼
                    RetryEvaluator
```

---

# 479. La transformation complète du domaine

Nous sommes partis de :

```text
"Exécuter quelque chose tous les jours à 06:00"
```

pour arriver à :

```text
Time Rule
   ↓
Trigger
   ↓
Occurrence
   ↓
Occurrence validation
   ↓
Misfire / Catch-Up
   ↓
Concurrency
   ↓
SchedulingDecision
   ↓
ExecutionRequest
   ↓
Durable commit
   ↓
Execution
   ↓
Attempt
   ↓
Retry / Result
```

---

# 480. Définition finale du SchedulerEngine

> **Le SchedulerEngine est le composant applicatif qui transforme, à partir d'un instant explicite et d'un état durable, les Schedules éligibles en décisions d'exécution durables, tout en faisant progresser de manière cohérente leur état temporel.**

---

# Conclusion

Le `SchedulerEngine` n'est pas le composant qui « lance des fonctions à une heure donnée ».

Il est le composant qui maintient une correspondance cohérente entre :

```text
le temps qui passe

la définition des Schedules

les occurrences théoriques

les politiques de recovery

l'état runtime

les décisions d'admission

et les intentions d'exécution durables
```

Le cœur de PyScheduleKit peut désormais être résumé ainsi :

```text
Clock
  ↓
Schedule candidates
  ↓
OccurrencePlanner
  ↓
Misfire / Catch-Up
  ↓
ConcurrencyEvaluator
  ↓
SchedulingPlan
  ↓
Transactional persistence
  ↓
ExecutionRequest
  ↓
ExecutionRuntime
  ↓
Attempt / Retry
```

La distinction architecturale centrale devient :

```text
SchedulerRuntime
→ fait vivre la boucle

SchedulerEngine
→ orchestre l'évaluation

Domain Services
→ prennent les décisions spécialisées

Repositories / Coordinators
→ garantissent la durabilité et l'atomicité

Executor
→ réalise effectivement le travail
```

Et le principe le plus important est :

> **Le temps réveille le scheduler, mais c'est l'état durable — et non le timer lui-même — qui détermine ce qui doit réellement se produire.**

Cette propriété rend possible :

```text
le restart

le catch-up

la déduplication

la persistence

les retries

la concurrence

et, plus tard, la distribution multi-node
```

sans changer la signification fondamentale du modèle métier.

---

# Suite documentaire

La prochaine étape logique est :

```text
18_SCHEDULER_RUNTIME_AND_WAKEUP_MODEL.md
```

Elle pourra approfondir spécifiquement :

```text
Runtime lifecycle

polling

dynamic wake-up

sleep strategy

wall clock vs monotonic clock

runtime backoff

shutdown

health

wake-up notifications

new Schedule signaling

timer heap

restart behavior
```

puis :

```text
19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md
```

pour figer :

```text
ScheduleRepository

ExecutionRepository

transaction boundaries

optimistic locking

OccurrenceKey uniqueness

RequestId deduplication

outbox

atomic schedule advancement
```

avant d'aborder ensuite la coordination distribuée.