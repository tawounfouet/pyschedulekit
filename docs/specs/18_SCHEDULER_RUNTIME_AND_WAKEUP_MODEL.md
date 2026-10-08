# PyScheduleKit — Scheduler Runtime & Wake-Up Model

**Document :** `18_SCHEDULER_RUNTIME_AND_WAKEUP_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle runtime de référence  
**Nature :** Runtime Model — Wake-Up / Polling / Sleep / Lifecycle / Health  
**Prérequis :**
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`
- `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`
- `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`
- `17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md`

---

# 1. Objectif

Le `SchedulerEngine` sait désormais :

```text
quels Schedules évaluer

quelles occurrences produire

comment traiter les misfires

comment appliquer la concurrence

comment matérialiser des ExecutionRequests

comment faire progresser next_run_time
```

Mais il manque encore une question fondamentale :

> **Comment le processus de scheduling sait-il quand il doit se réveiller pour recommencer une évaluation ?**

Le `SchedulerRuntime` doit transformer :

```text
une collection d'échéances futures
```

en :

```text
une boucle fiable de sommeil et de réveil
```

tout en gérant :

```text
Clock
polling
dynamic wake-up
new Schedule notification
retries
shutdown
runtime failure
restart
health
clock jumps
```

---

# 2. Runtime versus Engine

La distinction centrale reste :

```text
SchedulerEngine
→ décide quoi faire

SchedulerRuntime
→ décide quand rappeler le moteur
```

---

# 3. SchedulerRuntime

Le `SchedulerRuntime` représente :

> **Le composant opérationnel qui maintient la boucle de scheduling active dans le temps.**

Ses responsabilités principales :

```text
start

stop

wake-up

sleep

polling

cycle orchestration

runtime backoff

health

shutdown

restart coordination
```

---

# 4. Ce que le Runtime ne doit pas faire

Il ne doit pas décider lui-même :

```text
si une occurrence est un misfire

si un Schedule doit catch-up

si une Execution peut être concurrente

si un retry est autorisé

comment interpréter Cron
```

Ces décisions appartiennent aux modèles déjà définis.

---

# 5. Vue générale

```text
                 Clock
                   │
                   ▼
           SchedulerRuntime
                   │
                   ▼
              Wake-Up Loop
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
  Schedule due   Retry due   External wake-up
        │          │          │
        └──────────┼──────────┘
                   ▼
             SchedulerEngine
                   │
                   ▼
             Runtime Result
                   │
                   ▼
          Compute Next Wake-Up
                   │
                   ▼
                 Sleep
```

---

# 6. Le Runtime est une boucle

Conceptuellement :

```python
while running:
    now = clock.now()

    run_cycle(now)

    next_wakeup = compute_next_wakeup(now)

    sleeper.sleep_until(next_wakeup)
```

Mais ce modèle est encore trop naïf.

---

# 7. Pourquoi ?

Parce qu'un événement peut arriver pendant le sommeil :

```text
new Schedule created

Schedule resumed

Schedule rescheduled earlier

Execution completed

retry scheduled earlier

shutdown requested
```

Le Runtime doit pouvoir être :

```text
réveillé avant son timer initial
```

---

# 8. Trois causes de réveil

Une architecture générale doit supporter :

```text
TIME

SIGNAL

SHUTDOWN
```

---

# 9. Time Wake-Up

Le Runtime se réveille car :

```text
une échéance temporelle connue
```

est atteinte.

Exemple :

```text
next Schedule = 10:00
```

---

# 10. Signal Wake-Up

Le Runtime se réveille parce qu'un nouvel événement modifie l'état attendu.

Exemple :

```text
new Schedule created for 09:30
```

alors que le Runtime dormait jusqu'à :

```text
10:00
```

---

# 11. Shutdown Wake-Up

Le Runtime doit également interrompre son sommeil lorsque :

```text
stop()
```

est demandé.

---

# 12. WakeUpReason

Une abstraction runtime utile :

```text
WakeUpReason
│
├── TIMER
├── SIGNAL
├── SHUTDOWN
└── SPURIOUS
```

---

# 13. Spurious wake-up

Selon le mécanisme de synchronisation, un thread peut se réveiller sans événement métier particulier.

Le Runtime doit simplement :

```text
recalculer l'état
```

plutôt que considérer cela comme une erreur.

---

# 14. Principe fondamental

> **Un wake-up n'est jamais une preuve qu'une tâche est réellement due.**

Le wake-up signifie seulement :

```text
"réévalue maintenant"
```

---

# 15. Pourquoi ?

Le monde peut avoir changé depuis le calcul du timer :

```text
Schedule paused

Schedule rescheduled

another node processed it

retry cancelled

execution completed
```

---

# 16. Donc

Après chaque réveil :

```text
reload durable state
+
re-evaluate
```

---

# 17. Wake-up ≠ due decision

Cette séparation évite beaucoup de bugs.

```text
Timer
→ hint

Durable State
→ truth
```

---

# 18. Sources d'échéances

Le Runtime possède plusieurs familles de timers.

Au minimum :

```text
Schedule.next_run_time

Execution.next_attempt_at
```

---

# 19. Plus tard

On peut ajouter :

```text
lease expiration

reconciliation deadline

admission timeout

execution deadline

maintenance timers
```

---

# 20. V1

Le modèle doit rester centré sur :

```text
Schedule next_run_time

Retry next_attempt_at

max poll interval
```

---

# 21. Global Next Wake-Up

Conceptuellement :

```text
next_wakeup =
min(
    earliest_schedule_due,
    earliest_retry_due,
    polling_deadline
)
```

---

# 22. Exemple

```text
next Schedule = 10:15

next retry = 10:07

max poll deadline = 10:05
```

Donc :

```text
next_wakeup = 10:05
```

---

# 23. Pourquoi poll deadline plus tôt ?

Parce que le Runtime doit rester capable de détecter :

```text
new schedules

external state changes
```

même sans système de notification.

---

# 24. MaxPollInterval

`MaxPollInterval` représente :

> La durée maximale pendant laquelle le Runtime accepte de dormir sans réévaluer l'état durable.

---

# 25. Exemple

```text
max_poll_interval = 30s
```

Même si la prochaine occurrence connue est dans une heure :

```text
wake at most in 30 seconds
```

---

# 26. Trade-off

Petit intervalle :

```text
plus réactif

plus de requêtes

plus de CPU/DB
```

Grand intervalle :

```text
plus efficace

plus de latence pour les changements non signalés
```

---

# 27. Polling pur

La stratégie la plus simple :

```text
sleep 1 second
run cycle
repeat
```

---

# 28. Avantages

```text
simple

prévisible

facile à tester

facile à comprendre
```

---

# 29. Inconvénients

```text
wake-ups inutiles

queries fréquentes

latence liée au poll interval
```

---

# 30. Dynamic Wake-Up

Une approche plus efficace :

```text
sleep until earliest known deadline
```

---

# 31. Exemple

```text
current time = 10:00

next Schedule = 14:00

next retry = 10:03
```

Le Runtime dort jusqu'à :

```text
10:03
```

---

# 32. Mais problème

Un nouveau Schedule peut être créé à :

```text
10:01
```

avec échéance :

```text
10:02
```

---

# 33. Il faut donc

```text
dynamic wake-up
+
notification
```

ou :

```text
dynamic wake-up
+
max polling bound
```

---

# 34. Recommandation V1

Commencer avec :

```text
bounded polling
```

puis évoluer vers :

```text
dynamic wake-up + signal
```

---

# 35. Pourquoi commencer par polling

L'objectif initial de PyScheduleKit est l'apprentissage des objets métier.

Le wake-up optimal est :

```text
une optimisation runtime
```

et ne doit pas masquer les concepts temporels fondamentaux.

---

# 36. RuntimeStrategy

Une abstraction future peut représenter :

```text
FixedPolling

DynamicDeadline

HybridWakeUp
```

---

# 37. HybridWakeUp

Probablement le meilleur modèle long terme :

```text
sleep until min(
    next_known_deadline,
    now + max_poll_interval
)
```

mais interruption possible par :

```text
wake-up signal
```

---

# 38. Exemple

```text
next_known_deadline = 15:00
max_poll = 30s
now = 10:00
```

le Runtime dort jusqu'à :

```text
10:00:30
```

sauf notification avant.

---

# 39. Event-driven optimisation

Avec un système de signal :

```text
next_known_deadline = 15:00
```

le Runtime pourrait dormir jusqu'à 15:00.

Si un Schedule plus tôt est créé :

```text
signal_runtime()
```

---

# 40. WakeUpSignal

Port possible :

```text
WakeUpSignal
```

avec :

```text
wait_until(deadline)

notify()
```

---

# 41. Alternative name

```text
WakeUpCoordinator
```

peut être plus explicite.

---

# 42. Responsibilities

```text
wait

notify

shutdown interruption
```

---

# 43. Runtime must always recompute after signal

Le signal ne transporte pas obligatoirement :

```text
le Schedule à traiter
```

---

# 44. Pourquoi ?

Plus simple et robuste :

```text
signal
→ "something changed"
```

puis :

```text
query durable state
```

---

# 45. Avoid payload-heavy wake-up bus

Un système de notification de wake-up n'a pas besoin de devenir :

```text
message broker métier
```

---

# 46. Coalescing wake-up signals

Si dix Schedules sont créés simultanément :

```text
10 notifications
```

peuvent être fusionnées en :

```text
1 wake-up
```

---

# 47. Important

Le wake-up signal n'a pas besoin d'être exactement-once.

---

# 48. Why?

Parce que le Runtime relit :

```text
durable state
```

---

# 49. Missed wake-up notification

Même si une notification est perdue :

```text
max_poll_interval
```

permet de récupérer.

---

# 50. Therefore

Le système peut viser :

```text
best-effort wake-up signal

durable scheduling state
```

---

# 51. Clock model

Deux notions temporelles sont nécessaires :

```text
Wall Clock

Monotonic Clock
```

---

# 52. Wall Clock

Utilisé pour :

```text
Instant métier

next_run_time

scheduled_at

next_attempt_at

deadline
```

---

# 53. Monotonic Clock

Utilisé pour :

```text
sleep duration

elapsed runtime measurement

timeouts internes
```

---

# 54. Pourquoi séparer

L'horloge murale peut :

```text
avancer

reculer

être corrigée par NTP

changer manuellement
```

---

# 55. L'horloge monotonic

Doit seulement :

```text
progresser
```

durant le processus.

---

# 56. Exemple problématique

Runtime :

```text
wall clock = 10:00
```

calcule :

```text
sleep until 11:00
```

Puis l'OS avance l'heure à :

```text
10:30
```

---

# 57. Si sleep basé sur timestamp absolu naïf

Le comportement peut dépendre du système.

---

# 58. Better model

Calculer :

```text
remaining_duration =
target_wall_instant - current_wall_instant
```

puis attendre cette durée avec :

```text
monotonic timer
```

---

# 59. Mais après le sleep

Toujours relire :

```text
wall Clock.now()
```

et ne jamais supposer qu'on est exactement à la deadline.

---

# 60. Clock Jump Forward

Supposons :

```text
10:00 → 11:30
```

brutalement.

---

# 61. Runtime behavior

Au prochain réveil :

```text
evaluation_now = 11:30
```

Puis :

```text
Misfire/CatchUp
```

traite les occurrences intermédiaires.

---

# 62. Runtime ne doit pas fabriquer un temps artificiel

Ne jamais faire :

```text
pretend now is 10:01
10:02
...
```

pour rattraper.

---

# 63. Clock Jump Backward

Supposons :

```text
11:00 → 10:30
```

---

# 64. Risk

Une occurrence de :

```text
10:45
```

peut sembler redevenir future alors qu'elle a déjà été traitée.

---

# 65. Protection

Les données durables :

```text
OccurrenceKey

next_run_time

request uniqueness
```

empêchent la duplication logique.

---

# 66. Runtime principle

> **Clock tells us where time appears to be; durable history tells us what was already processed.**

---

# 67. `sleep_until`

Port utile :

```text
Sleeper
```

---

# 68. Contract

Conceptuellement :

```text
sleep_until(deadline)
```

ou :

```text
sleep(duration)
```

---

# 69. Test implementation

```text
FakeSleeper
```

ne dort pas réellement.

Il peut :

```text
record requested sleep
```

ou avancer un :

```text
MutableClock
```

---

# 70. Pourquoi ?

Les tests runtime doivent être :

```text
rapides

déterministes

sans vraie attente
```

---

# 71. No `time.sleep()` in domain tests

Le `time.sleep()` réel ne doit apparaître que dans :

```text
infrastructure adapter
```

---

# 72. Wake-Up computation

Le calcul peut être externalisé dans :

```text
WakeUpPlanner
```

---

# 73. WakeUpPlanner

Input :

```text
now

earliest_schedule_due

earliest_retry_due

max_poll_interval
```

Output :

```text
WakeUpPlan
```

---

# 74. WakeUpPlan

```text
WakeUpPlan
│
├── wake_at
├── reason_hint
└── poll_deadline
```

---

# 75. Classification

```text
runtime Value Object
```

---

# 76. Pourquoi utile ?

Pour tester indépendamment :

```text
quel instant de réveil choisir
```

---

# 77. Example

Input :

```text
now = 10:00
schedule = 10:20
retry = 10:05
max_poll = 30s
```

Output :

```text
wake_at = 10:00:30
```

---

# 78. Important subtlety

Si `max_poll_interval` est plus petit que les échéances connues, le poll gagne.

---

# 79. With reliable signal mode

Une configuration peut autoriser :

```text
max_poll_interval = 5 minutes
```

ou davantage.

---

# 80. Without signal mode

Il doit rester suffisamment court.

---

# 81. RuntimeConfig

Possible :

```text
SchedulerRuntimeConfig
│
├── poll_interval
├── max_poll_interval
├── schedule_batch_size
├── retry_batch_size
├── admission_batch_size
├── runtime_error_backoff
└── graceful_shutdown_timeout
```

---

# 82. Classification

Configuration applicative/runtime.

Pas Entity métier.

---

# 83. Avoid config leaking into ScheduleDefinition

`poll_interval` n'est pas une propriété du Schedule.

---

# 84. Runtime lifecycle

Le Runtime lui-même peut avoir des états.

Proposition :

```text
STOPPED

STARTING

RUNNING

STOPPING

FAILED
```

---

# 85. SchedulerRuntimeState

Classification :

```text
runtime operational state
```

pas domaine métier.

---

# 86. STOPPED

Aucune boucle active.

---

# 87. STARTING

Initialisation en cours :

```text
validate dependencies

perform startup reconciliation

initialize metrics

prepare wake-up primitive
```

---

# 88. RUNNING

La boucle accepte de nouveaux cycles.

---

# 89. STOPPING

Le Runtime :

```text
n'entame plus de nouveau cycle

termine ou rollback le cycle courant

réveille les sleepers

ferme les ressources
```

---

# 90. FAILED

Une erreur fatale empêche la poursuite sûre.

---

# 91. Runtime state machine

```text
STOPPED
   │
   ▼
STARTING
   │
   ├── success
   ▼
RUNNING
   │
   ├── stop requested
   ▼
STOPPING
   │
   ▼
STOPPED
```

Fatal path :

```text
STARTING/RUNNING
→ FAILED
```

---

# 92. Restart after FAILED

Peut nécessiter :

```text
new Runtime instance
```

ou une action explicite.

V1 peut ne pas autoriser :

```text
FAILED → RUNNING
```

automatiquement.

---

# 93. Start idempotence

Appeler :

```text
start()
```

sur un Runtime déjà `RUNNING` doit :

```text
no-op
```

ou lever une erreur explicite.

---

# 94. Stop idempotence

Appeler :

```text
stop()
```

plusieurs fois doit être sûr.

---

# 95. Graceful shutdown

Objectif :

> Arrêter le SchedulerRuntime sans laisser une transaction de scheduling à moitié appliquée.

---

# 96. Shutdown flow

```text
stop requested
      │
      ▼
wake sleeping runtime
      │
      ▼
prevent new cycle
      │
      ▼
finish current transaction
      │
      ▼
close resources
      │
      ▼
STOPPED
```

---

# 97. Scheduler shutdown ≠ worker shutdown

Très important.

---

# 98. SchedulerRuntime

Arrête :

```text
new scheduling evaluations
```

---

# 99. ExecutionRuntime

Peut avoir une politique distincte :

```text
finish active attempts

cancel attempts

stop accepting queued work
```

---

# 100. Application-level coordinated shutdown

Un processus contenant les deux peut :

```text
stop scheduler first

then stop worker runtime
```

---

# 101. Why scheduler first?

Pour éviter de créer :

```text
new executions
```

pendant que les workers sont en train de fermer.

---

# 102. Shutdown deadline

Une configuration peut utiliser :

```text
graceful_shutdown_timeout
```

---

# 103. If timeout expires

Le process peut devoir :

```text
force stop
```

---

# 104. But durable state must remain recoverable

Toute transaction non terminée doit :

```text
rollback
```

ou être détectable au restart.

---

# 105. Runtime failure

Le Runtime peut rencontrer des erreurs sans qu'un Schedule soit fautif.

Exemples :

```text
database unavailable

network partition to persistence

system resource exhaustion

repository initialization failure
```

---

# 106. RuntimeErrorPolicy

Une abstraction possible :

```text
RuntimeFailurePolicy
```

---

# 107. Question

Après une erreur globale :

```text
retry loop ?

wait ?

fail Runtime ?
```

---

# 108. Transient runtime errors

Exemple :

```text
database unavailable for 2 seconds
```

Le Runtime peut :

```text
backoff
retry
```

---

# 109. Fatal runtime errors

Exemple :

```text
unsupported database schema version
```

Le Runtime doit probablement :

```text
FAILED
```

---

# 110. RuntimeFailureCategory

```text
TRANSIENT

FATAL
```

suffit largement pour V1.

---

# 111. RuntimeBackoff

Ne pas confondre avec :

```text
Execution Retry Backoff
```

---

# 112. RuntimeBackoff meaning

> Combien de temps attendre avant de retenter une boucle après erreur infrastructure globale.

---

# 113. Example

```text
DB error
↓
runtime waits 2s
↓
retry cycle
```

---

# 114. RuntimeBackoffStrategy

Peut être :

```text
fixed

exponential
```

mais V1 peut utiliser :

```text
fixed
```

simplement.

---

# 115. RuntimeBackoff bounded

Toujours avec :

```text
maximum
```

pour ne pas dormir des heures silencieusement.

---

# 116. Logging errors

Une erreur runtime doit fournir :

```text
cycle id

error category

last successful cycle

next retry
```

---

# 117. No hot loop

Si DB est indisponible :

```text
while True:
    query()
```

sans délai serait dangereux.

---

# 118. Failure isolation

Une erreur de Schedule individuel ne doit pas déclencher :

```text
RuntimeBackoff global
```

---

# 119. Distinction

```text
ScheduleEvaluationError
→ isolate one Schedule
```

```text
InfrastructureUnavailable
→ affect entire Runtime
```

---

# 120. Health model

Le Runtime doit pouvoir exposer son état opérationnel.

---

# 121. Health questions

```text
Le process est-il vivant ?

La boucle tourne-t-elle ?

Quand a eu lieu le dernier cycle ?

Quand a eu lieu le dernier cycle réussi ?

Quel est le lag ?

Le Runtime est-il en backoff ?

Est-il en train de s'arrêter ?
```

---

# 122. RuntimeHealth

Possible :

```text
RuntimeHealth
│
├── state
├── last_cycle_started_at
├── last_cycle_completed_at
├── last_successful_cycle_at
├── next_wakeup_at
├── last_error
└── scheduler_lag
```

---

# 123. Liveness versus Readiness

Deux concepts classiques :

```text
Liveness

Readiness
```

---

# 124. Liveness

Question :

> Le processus est-il vivant ?

---

# 125. Readiness

Question :

> Est-il capable de réaliser correctement de nouveaux cycles ?

---

# 126. Example

DB inaccessible :

```text
process alive
```

mais :

```text
not ready
```

---

# 127. V1

Même si aucune API HTTP n'existe, le modèle peut exposer :

```text
runtime.health()
```

---

# 128. Health is operational

Pas un objet métier.

---

# 129. Scheduler lag

Une métrique clé :

```text
scheduler_lag =
now - earliest_overdue_schedule
```

si Schedule en retard.

---

# 130. No lag

Si aucun Schedule due :

```text
0
```

ou `None` selon convention.

---

# 131. Retry lag

On peut aussi mesurer :

```text
retry_lag =
now - earliest_overdue_retry
```

---

# 132. Admission backlog

```text
waiting_admission_count
```

---

# 133. Runtime cycle metrics

```text
cycle_count

cycle_duration

cycle_error_count

wake_up_count

timer_wake_up_count

signal_wake_up_count

runtime_backoff_count
```

---

# 134. Sleep metrics

```text
requested_sleep_duration

actual_sleep_duration
```

peut aider à détecter :

```text
clock issues

OS scheduling delays
```

---

# 135. Wake-up lateness

```text
wake_up_lag =
actual_wakeup_at - requested_wakeup_at
```

---

# 136. But not business misfire

Important :

```text
WakeUp lag
≠
Misfire
```

Le Misfire concerne une Occurrence selon sa GracePeriod.

---

# 137. Observability layering

```text
Runtime lag

Schedule lag

Execution queue lag

Retry lag
```

sont des métriques distinctes.

---

# 138. Startup

Le démarrage du Runtime doit suivre un ordre explicite.

---

# 139. Suggested startup sequence

```text
1. Load runtime config

2. Validate dependencies

3. Validate storage compatibility

4. Initialize Clock/Sleeper

5. Perform reconciliation

6. Compute initial wake-up

7. Enter RUNNING
```

---

# 140. Storage compatibility

Exemple :

```text
schema migration version
```

doit être valide avant scheduling.

---

# 141. Clock sanity

Le Runtime peut vérifier :

```text
Clock returns aware Instant
```

---

# 142. Reconciliation

Au startup :

```text
overdue Schedules

overdue retries

stale running Attempts
```

peuvent nécessiter traitement.

---

# 143. Order

Il n'est pas nécessaire de tout corriger avant de devenir `RUNNING` si cela prend longtemps.

---

# 144. V1 recommendation

Minimum startup reconciliation :

```text
nothing destructive

simply start normal evaluation immediately
```

car :

```text
due Schedules
due retries
```

seront détectés.

---

# 145. Stale RUNNING Attempts

Nécessitent cependant une stratégie spécifique si workers locaux ont disparu.

---

# 146. Local runtime assumption

En V1 locale :

```text
process restart
→ all persisted RUNNING local Attempts are stale
```

---

# 147. Reconciliation action

```text
Attempt → FAILED(WORKER_LOST)
```

puis :

```text
RetryEvaluator
```

---

# 148. Distributed executor

Cette règle n'est plus valable si worker externe peut toujours être actif.

---

# 149. Therefore

Le `RuntimeReconciler` dépend :

```text
du type d'Executor
```

---

# 150. Wake-up after startup

Le premier cycle devrait généralement être :

```text
immédiat
```

---

# 151. Why?

Pour traiter :

```text
due schedules

overdue retries

waiting admissions
```

sans attendre le premier poll interval.

---

# 152. Initial loop

```text
STARTING
↓
RUNNING
↓
run_cycle immediately
↓
compute wake-up
```

---

# 153. Runtime cycle

Un cycle peut avoir un lifecycle conceptuel :

```text
CREATED

RUNNING

COMPLETED

FAILED
```

mais il n'est pas nécessaire de le persister.

---

# 154. EvaluationCycleResult

Objet interne :

```text
EvaluationCycleResult
│
├── cycle_id
├── started_at
├── completed_at
├── schedule_result
├── admission_result
├── retry_result
└── errors
```

---

# 155. Useful for tests

Oui.

---

# 156. Cycle must be bounded

Aucun cycle ne doit pouvoir :

```text
tourner éternellement
```

sur une énorme quantité de travail.

---

# 157. Batch limits

Comme document 17 :

```text
schedule_batch_size

admission_batch_size

retry_batch_size
```

---

# 158. More work remains

Si une phase atteint son batch limit :

```text
immediate_next_cycle = true
```

peut être utilisé.

---

# 159. Immediate next cycle

Le Runtime n'a pas besoin de dormir si :

```text
backlog is known to remain
```

---

# 160. But avoid busy loop

Même dans ce cas :

```text
yield
```

ou très petit délai peut éviter monopolisation CPU selon implémentation.

---

# 161. WorkRemainingHint

Le résultat d'un cycle peut fournir :

```text
more_due_schedules

more_waiting_admissions

more_due_retries
```

---

# 162. WakeUpPlanner

Peut alors choisir :

```text
wake_at = now
```

ou :

```text
minimal_yield_delay
```

---

# 163. Fairness

Le Runtime doit éviter qu'un backlog de :

```text
Schedules
```

empêche toujours :

```text
retries
```

---

# 164. Phase batch limits

Permettent cela.

---

# 165. Round-robin phases

Un cycle peut toujours appeler :

```text
Schedules
Admissions
Retries
```

avec un nombre limité par phase.

---

# 166. Alternative

Un dispatcher interne peut mélanger les timers par échéance globale.

Plus complexe, hors V1.

---

# 167. Unified Timer Queue

Concept future :

```text
TimerEntry
│
├── kind
├── due_at
└── reference_id
```

Kinds :

```text
SCHEDULE

RETRY
```

---

# 168. Avantage

Une seule priority queue.

---

# 169. Inconvénient

Risque de confondre les domaines.

---

# 170. Recommendation

Une infrastructure commune de timers est acceptable.

Mais les handlers restent distincts :

```text
ScheduleTimerHandler

RetryTimerHandler
```

---

# 171. Shared mechanism

```text
priority queue
```

---

# 172. Separate semantics

```text
Schedule due
≠
Retry due
```

---

# 173. TimerEntry not domain entity

C'est une structure runtime/infrastructure.

---

# 174. In-memory Timer Heap

Pour optimisation :

```text
heapq
```

peut conserver :

```text
(due_at, kind, id)
```

---

# 175. Source of truth

Toujours :

```text
durable store
```

---

# 176. Heap stale entries

Un Schedule reschedulé peut laisser une ancienne entrée heap.

---

# 177. Strategy

Lors du wake-up :

```text
load Schedule
```

et vérifier :

```text
current next_run_time
```

---

# 178. Stale timer becomes harmless

Exactement.

---

# 179. No need delete every old heap entry

On peut utiliser :

```text
lazy invalidation
```

si performance acceptable.

---

# 180. Timer identity

Une entrée peut porter :

```text
reference_version
```

pour détecter staleness rapidement.

---

# 181. Example

```text
schedule_id = 42
persistence_version = 10
due_at = 10:00
```

Schedule now :

```text
version 12
due_at = 11:00
```

ancienne timer ignorée.

---

# 182. Event-driven Schedule changes

Lors de :

```text
create

resume

reschedule
```

l'application peut appeler :

```text
runtime.notify()
```

---

# 183. Pause

Pause d'un Schedule dont timer est encore dans heap :

```text
wake-up may still happen
```

mais évaluation verra :

```text
PAUSED
```

et n'exécutera rien.

---

# 184. Good property

La correctness ne dépend pas de supprimer tous les timers obsolètes.

---

# 185. New Schedule signaling

Application flow :

```text
CreateSchedule
↓
commit
↓
notify SchedulerRuntime
```

---

# 186. Important

Signal après commit.

---

# 187. Pourquoi ?

Si on signale avant commit :

```text
Runtime wakes
```

mais ne trouve pas encore le Schedule.

---

# 188. Is that fatal?

Non, avec polling fallback.

Mais inutilement racy.

---

# 189. Better

```text
persist first

signal second
```

---

# 190. Transactional signal?

Pour une notification non durable :

```text
best effort after commit
```

suffit souvent.

---

# 191. Because fallback polling

garantit la détection ultérieure.

---

# 192. Reschedule earlier

Exemple :

```text
Runtime sleeps until 12:00

Schedule rescheduled from 12:00 to 10:05

current time 10:00
```

Il faut :

```text
wake immediately
```

---

# 193. Reschedule later

Si :

```text
10:05 → 12:00
```

un wake-up à 10:05 peut encore se produire.

---

# 194. That's acceptable

Le Runtime se réveille :

```text
too early
```

relit l'état :

```text
next_run_time = 12:00
```

puis se rendort.

---

# 195. Principle

```text
early wake-up = cheap inconvenience

late wake-up = potentially business-significant
```

---

# 196. Therefore

Optimiser surtout pour :

```text
never sleep past important newly-created deadlines
```

---

# 197. Polling guarantee

Avec :

```text
max_poll_interval = P
```

et aucune notification :

```text
new due item detection latency <= roughly P + processing latency
```

---

# 198. Not hard guarantee

OS/DB delays peuvent augmenter.

---

# 199. Document honestly

PyScheduleKit n'est pas un hard real-time system.

---

# 200. Runtime precision

Une propriété config possible :

```text
target_poll_resolution
```

mais elle ne garantit pas :

```text
exact start time
```

---

# 201. Scheduling accuracy

Dépend :

```text
wake-up latency

evaluation latency

DB latency

admission latency

executor queue latency
```

---

# 202. scheduled_at remains stable

Même si l'exécution démarre plus tard.

---

# 203. Runtime Overrun

Un cycle peut durer plus longtemps que le poll interval.

Exemple :

```text
poll interval = 1s

cycle duration = 5s
```

---

# 204. Naive loop

```text
cycle 5s
sleep 1s
```

produit une cadence :

```text
6s
```

---

# 205. Is this wrong?

Pas nécessairement.

Mais il faut le comprendre.

---

# 206. Fixed-rate polling

Alternative :

```text
target cycle start every 1s
```

mais impossible si cycle dure 5s sans overlap.

---

# 207. Runtime should not overlap cycles by default

Important V1 invariant :

```text
one active evaluation cycle per SchedulerRuntime
```

---

# 208. Why?

Évite :

```text
duplicate candidate processing

complex locking

hard-to-debug races
```

---

# 209. Distributed parallelism

Plus tard, plusieurs Runtime nodes peuvent agir.

Mais chaque instance peut rester :

```text
single-cycle sequential
```

---

# 210. No self-overlap

Le SchedulerRuntime ne doit pas lancer un second cycle avant la fin du précédent.

---

# 211. Long cycle handling

Si cycle long :

```text
next cycle starts immediately
```

si travail en retard.

---

# 212. Cycle duration metric

Permet de détecter :

```text
runtime unable to keep up
```

---

# 213. Runtime saturation

Si :

```text
cycle duration continuously > target poll interval
```

le runtime est structurellement saturé.

---

# 214. Solutions

```text
larger batches?

better queries?

multiple scheduler nodes?

reduce polling cost?
```

---

# 215. Do not silently skip work

---

# 216. Runtime Backpressure

Le SchedulerRuntime peut être saturé par :

```text
millions of due Schedules
```

---

# 217. Backpressure tools

```text
bounded batches

pagination

multi-node claiming

metrics
```

---

# 218. Not changing Schedule semantics

La pression runtime ne doit pas modifier automatiquement :

```text
MisfirePolicy

CatchUpPolicy
```

---

# 219. Sleep strategy

Un `SleepStrategy` peut être :

```text
FixedPollSleeper

DeadlineAwareSleeper

InterruptibleSleeper
```

---

# 220. InterruptibleSleeper

Important pour :

```text
new schedule signals

shutdown
```

---

# 221. Possible interface

```text
wait_until(deadline) -> WakeUpReason
```

---

# 222. This is elegant

Le Runtime reçoit directement :

```text
TIMER

SIGNAL

SHUTDOWN
```

---

# 223. Implementation options

En Python :

```text
threading.Condition

asyncio.Event

asyncio.Condition
```

selon runtime.

---

# 224. But domain must not depend on one

Le port masque le mécanisme.

---

# 225. Sync Runtime

Première version possible :

```text
threading.Condition
```

---

# 226. Async Runtime

Future :

```text
asyncio
```

---

# 227. Should PyScheduleKit support both immediately?

Non nécessaire.

---

# 228. Recommendation

V1 :

```text
synchronous runtime
```

simple et testable.

---

# 229. Later adapter

Un :

```text
AsyncSchedulerRuntime
```

peut réutiliser le même SchedulerEngine.

---

# 230. Runtime concurrency model

Même avec runtime sync :

```text
Executor
```

peut être async/distant.

---

# 231. Scheduling loop should remain lightweight

Il ne doit jamais bloquer pendant :

```text
execution métier longue
```

---

# 232. Why?

Sinon un Job de 30 minutes bloquerait :

```text
tous les autres Schedules
```

---

# 233. Therefore

SchedulerRuntime :

```text
materialise
dispatch
return
```

---

# 234. Not execute inline

Sauf prototype pédagogique ultra minimal.

---

# 235. If inline executor exists

Il doit être considéré comme :

```text
dev/testing adapter
```

pas architecture finale.

---

# 236. Wake-up after Execution completion

Pourquoi une completion peut réveiller le scheduler ?

Parce qu'elle peut libérer :

```text
ConcurrencyKey capacity
```

---

# 237. Waiting admission

Une request :

```text
WAITING_ADMISSION
```

peut maintenant devenir admissible.

---

# 238. Event path

```text
Execution terminal
↓
Concurrency slot released
↓
runtime notify()
↓
re-evaluate waiting admissions
```

---

# 239. Without signal

Le prochain poll le découvrira.

---

# 240. Best-effort notification again

Correctness remains durable.

---

# 241. Wake-up after RetryScheduled

Si un Execution failure produit :

```text
next_attempt_at earlier than current known wake-up
```

le Runtime doit être notifié.

---

# 242. Example

Runtime sleeping until :

```text
11:00
```

Retry scheduled at :

```text
10:05
```

→ notify.

---

# 243. Who sends signal?

L'application service qui persiste :

```text
Execution RETRY_WAIT
```

peut signaler le Runtime après commit.

---

# 244. Shared Runtime in one process

Simple.

---

# 245. Separate scheduler/worker processes

Le signal doit alors utiliser :

```text
IPC

DB notification

message bus
```

ou fallback polling.

---

# 246. V1 seam

`WakeUpNotifier` port permet l'évolution future.

---

# 247. But no need implementation distributed now

---

# 248. Lost notification scenario

```text
retry persisted
signal lost
```

max polling catches it.

---

# 249. Duplicate notification

```text
notify twice
```

just causes early wake-up.

No correctness issue.

---

# 250. Notification semantics

Donc :

```text
at-most-once

at-least-once
```

n'est pas critique.

---

# 251. Wake-up debouncing

Des milliers de notifications peuvent être fusionnées.

---

# 252. Coarse signal

Un simple flag :

```text
wake_requested = true
```

peut suffire.

---

# 253. Shutdown flag

Également :

```text
stop_requested = true
```

---

# 254. Runtime loop pseudo-code

```python
while not stop_requested:
    now = clock.now()

    result = run_cycle(now)

    if stop_requested:
        break

    wake_plan = wakeup_planner.plan(
        now=clock.now(),
        cycle_result=result,
        next_schedule=...,
        next_retry=...,
    )

    wake_reason = waiter.wait_until(wake_plan.wake_at)
```

---

# 255. Why recapture now before planning wake-up?

Parce que :

```text
run_cycle
```

a pris du temps.

---

# 256. Example

Cycle started :

```text
10:00
```

finished :

```text
10:00:08
```

Le wake-up doit être calculé à partir de :

```text
10:00:08
```

pas du `evaluation_now` initial.

---

# 257. Same-now principle scope

Le même `evaluation_now` est utilisé :

```text
inside one evaluation cycle
```

mais après le cycle :

```text
Clock.now()
```

peut être recapturé pour le Runtime.

---

# 258. Important distinction

```text
Domain evaluation time
```

versus :

```text
Runtime scheduling time
```

---

# 259. EvaluationNow immutable

Oui.

---

# 260. RuntimeNow recaptured

Oui.

---

# 261. Wake-up in past

Le plan peut calculer :

```text
wake_at <= now
```

si du travail reste dû.

---

# 262. Behavior

```text
do not sleep
```

ou :

```text
minimal yield
```

---

# 263. MinimalYield

Configuration technique possible :

```text
1ms
```

ou :

```text
thread yield
```

---

# 264. V1

Peut simplement :

```text
continue
```

mais attention au hot loop.

---

# 265. Work remaining guard

Si plusieurs cycles immédiats ont lieu sans progrès :

```text
runtime detects possible stuck loop
```

---

# 266. StuckLoopGuard

Future abstraction :

```text
max_consecutive_immediate_cycles
```

---

# 267. Why?

Un Schedule mal configuré peut rester :

```text
due forever
```

si checkpoint n'avance pas.

---

# 268. Trigger monotonic invariant helps

Mais bugs/infrastructure corruption restent possibles.

---

# 269. Runtime must protect itself

---

# 270. Suggested V1 guard

Si :

```text
same schedule
same next_run_time
same error
```

se répète trop rapidement :

```text
log loudly
apply runtime error delay
```

---

# 271. Do not mutate Schedule silently

No auto-pause unless explicit future policy.

---

# 272. Runtime error suppression

Can rate-limit logs.

---

# 273. Runtime scheduler precision under load

Le wake-up peut arriver à l'heure, mais :

```text
cycle backlog
```

retarde l'évaluation réelle.

---

# 274. Metrics

Distinguer :

```text
wake_up_lag

evaluation_queue_lag

schedule_lag
```

---

# 275. RuntimeHealth state example

```text
RUNNING
last_successful_cycle = 10:02:30
next_wakeup = 10:03:00
schedule_lag = 0.2s
```

---

# 276. Degraded health

```text
RUNNING
but DB failures for 30s
```

peut être :

```text
DEGRADED
```

---

# 277. Should DEGRADED be RuntimeState?

Pas nécessairement.

Mieux comme :

```text
HealthStatus
```

---

# 278. RuntimeState remains lifecycle

```text
STOPPED
STARTING
RUNNING
STOPPING
FAILED
```

---

# 279. HealthStatus

```text
HEALTHY
DEGRADED
UNHEALTHY
```

---

# 280. Separation

```text
RuntimeState
→ lifecycle

HealthStatus
→ operational quality
```

---

# 281. Example

```text
RuntimeState = RUNNING

HealthStatus = DEGRADED
```

possible.

---

# 282. Health policy

Could say degraded when:

```text
last successful cycle older than threshold
```

---

# 283. But thresholds are operational config

---

# 284. External monitoring

Metrics can integrate with :

```text
Prometheus

OpenTelemetry

logs
```

later.

---

# 285. No vendor dependency in core

---

# 286. Restart semantics

Un process restart détruit :

```text
in-memory timers

condition variables

heap

temporary caches
```

---

# 287. On startup

Il reconstruit depuis :

```text
durable state
```

---

# 288. Therefore

In-memory wake-up structures must be :

```text
rebuildable
```

---

# 289. Timer heap rebuild

Possible:

```text
load nearest N schedules

load nearest N retries
```

---

# 290. Or lazy query

No heap at all.

---

# 291. V1

Prefer:

```text
query storage each cycle
```

---

# 292. Simpler reasoning

Yes.

---

# 293. Eventual optimization

Heap later.

---

# 294. Scheduler Runtime and DB transactions

Le Runtime ne doit pas garder une transaction ouverte pendant :

```text
sleep
```

---

# 295. Obvious but important

Transactions doivent être :

```text
short-lived
```

---

# 296. Sleep is outside transactions

Toujours.

---

# 297. Lock duration

Aucun Schedule lock ne doit survivre :

```text
au cycle global
```

plus que nécessaire.

---

# 298. Wake-up query

Lire :

```text
earliest next_run_time
```

ne nécessite pas de lock long.

---

# 299. Runtime and distributed leases

Dans une version distributed :

```text
lease expiry
```

peut elle-même devenir un timer.

---

# 300. But Lease renewal is not schedule recurrence

Encore séparation.

---

# 301. Lease heartbeat

Runtime peut renouveler :

```text
node lease
```

périodiquement.

---

# 302. Not V1

---

# 303. System suspend / laptop sleep

Un cas intéressant pour un scheduler local :

```text
machine sleeps for 2 hours
```

---

# 304. On resume

Wall Clock a avancé.

Le Runtime redémarre son cycle avec :

```text
now = current time
```

---

# 305. Misfire/Catch-Up handles missed Schedule occurrences

---

# 306. RetryWait

Overdue retries :

```text
run now
```

si deadline encore valide.

---

# 307. No special "computer slept" semantics required

Exactly.

---

# 308. Long GC pause / process freeze

Même logique.

---

# 309. Runtime sees later now

Policies handle consequences.

---

# 310. Strong design property

Le runtime n'a pas besoin de distinguer :

```text
sleep

pause

CPU starvation

OS suspend
```

pour maintenir la sémantique temporelle.

---

# 311. Only durable time gap matters

---

# 312. Runtime drift

Un scheduler basé uniquement sur :

```text
sleep(interval)
```

puis :

```text
next = now + interval
```

accumule du drift.

---

# 313. PyScheduleKit avoids this

Parce que :

```text
Schedule Trigger
```

calcule depuis sa règle et ses occurrences, pas depuis la fin du cycle runtime.

---

# 314. Example

Daily 08:00.

Même si runtime détecte à :

```text
08:00:15
```

la prochaine reste :

```text
next day 08:00
```

pas :

```text
next day 08:00:15
```

---

# 315. This is fundamental

Runtime timing must never redefine Schedule semantics.

---

# 316. Retry fixed delay

Même principe :

```text
retry_at
```

est durable une fois calculé.

---

# 317. Runtime wake delay doesn't shift policy

Si retry prévu à :

```text
10:05
```

mais Runtime se réveille à :

```text
10:05:10
```

l'Attempt est :

```text
due now
```

pas recalculée pour 10:05:20.

---

# 318. Deadline check still applies

---

# 319. Runtime and precision classes

On pourrait distinguer :

```text
best_effort

high_precision
```

mais hors V1.

---

# 320. Avoid precision marketing

PyScheduleKit should state:

```text
application-level scheduler
```

---

# 321. Thread safety

Si `notify()` peut venir d'un autre thread :

```text
WakeUpCoordinator
```

doit être thread-safe.

---

# 322. SchedulerEngine itself

Peut rester non-thread-safe si :

```text
one cycle at a time
```

---

# 323. Clear concurrency boundary

Runtime serializes Engine calls.

---

# 324. Good V1 invariant

```text
One SchedulerEngine evaluation cycle
per Runtime instance at a time.
```

---

# 325. Async notifications

Can set flag safely.

---

# 326. Cancellation token

A runtime may have:

```text
CancellationToken
```

or stop flag.

---

# 327. Should domain know it?

No.

---

# 328. Runtime interruption

If shutdown requested during long Schedule evaluation:

```text
finish current atomic unit
```

then stop.

---

# 329. Per-Schedule transaction

Good shutdown boundary.

---

# 330. Example

Batch of 100 Schedules.

Stop requested after 37.

Runtime can:

```text
finish schedule 37
stop before 38
```

---

# 331. More responsive shutdown

Check stop flag between items.

---

# 332. Do not abort DB transaction mid-operation

Unless infrastructure handles rollback safely.

---

# 333. Startup/shutdown events

Possible:

```text
SchedulerRuntimeStarted

SchedulerRuntimeStopping

SchedulerRuntimeStopped

SchedulerRuntimeFailed
```

---

# 334. Are these domain events?

No.

Operational/runtime events.

---

# 335. Useful for observability

Yes.

---

# 336. Runtime configuration reload

Can poll interval change while running?

---

# 337. V1

No dynamic runtime config required.

Restart process to apply.

---

# 338. Future

Could allow hot reload.

---

# 339. But ScheduleDefinition changes remain independent.

---

# 340. Runtime wake-up planner pseudocode

```text
poll_deadline =
now + max_poll_interval

candidates = [
    poll_deadline,
    earliest_schedule_due,
    earliest_retry_due
]

wake_at =
minimum non-null candidate
```

---

# 341. If all null

Then:

```text
wake_at = poll_deadline
```

---

# 342. If candidate already past

```text
wake_at = now
```

---

# 343. If shutdown

Ignore wake_at.

---

# 344. If signal arrives

Return early.

---

# 345. Earliest schedule query may return null

If:

```text
no ACTIVE schedules
```

---

# 346. Earliest retry query may return null

If:

```text
no RETRY_WAIT executions
```

---

# 347. Runtime still wakes periodically

For:

```text
new work discovery
health
shutdown
```

---

# 348. Notification-only mode future

If system has reliable durable notifications:

```text
polling interval could be very large
```

---

# 349. But full notification-only mode is risky

Unless notifications themselves are durable.

---

# 350. Hybrid recommended

Even production:

```text
signal + periodic safety poll
```

---

# 351. Similar to cache invalidation strategy

Notification accelerates.

Polling guarantees eventual discovery.

---

# 352. RuntimePollReason

Maybe metrics classify cycles triggered by:

```text
STARTUP

TIMER

SIGNAL

BACKLOG

RECOVERY
```

---

# 353. Useful but internal.

---

# 354. SchedulerEngine result hints

Engine may return:

```text
work_remaining
earliest_new_due
```

to help Runtime.

---

# 355. But Runtime should not trust only hints

Can query durable state before sleeping.

---

# 356. Why?

Engine result may become stale due to concurrent changes.

---

# 357. Recommended wake-up calculation

After cycle:

```text
query earliest durable deadlines
```

then compute sleep.

---

# 358. Cost

Additional DB query.

---

# 359. Benefit

More correct wake-up plan.

---

# 360. Possible optimization later

Use cycle hints plus signal.

---

# 361. Runtime and Schedule priority

No priority scheduling in V1.

Due schedules can be ordered by:

```text
next_run_time ASC
```

---

# 362. Tie-breaker

```text
ScheduleId
```

for deterministic order.

---

# 363. Retry order

```text
next_attempt_at ASC
```

then:

```text
ExecutionId
```

---

# 364. Waiting admissions order

```text
scheduled_at ASC
```

then RequestId.

---

# 365. Deterministic ordering

Important for:

```text
tests

fairness reasoning

debug
```

---

# 366. Fairness across tenants

Future.

---

# 367. Scheduler Runtime memory usage

Never load all due items if large.

Use:

```text
bounded page
```

---

# 368. Query pagination

Could use:

```text
cursor-based
```

or repeated bounded query.

---

# 369. V1

Simple limit is enough.

---

# 370. Immediate backlog cycles

If query returned full batch size:

```text
possible more work
```

Runtime can schedule immediate next cycle.

---

# 371. But full batch doesn't prove more

It's only a hint.

---

# 372. Good enough for optimization.

---

# 373. Runtime testability

Must support fake:

```text
Clock

Sleeper

WakeUpCoordinator

Repositories
```

---

# 374. Test — timer wake-up

Given:

```text
wake_at = 10:05
```

Fake waiter returns:

```text
TIMER
```

Runtime invokes next cycle.

---

# 375. Test — signal early

Wait until 10:05.

Signal at logical 10:01.

Expected:

```text
cycle immediately
```

---

# 376. Test — shutdown during sleep

Expected:

```text
wait interrupted

STOPPING
```

---

# 377. Test — early wake stale timer

Schedule rescheduled later.

Runtime wakes at old time.

Expected:

```text
no execution
new wake-up later
```

---

# 378. Test — new earlier Schedule

Runtime sleeping for old 12:00.

New Schedule 10:05 committed + signal.

Expected:

```text
wake and recompute
```

---

# 379. Test — lost signal

No signal.

Expected:

```text
poll deadline discovers new schedule
```

---

# 380. Test — duplicate signals

Expected:

```text
at most extra harmless cycles
```

---

# 381. Test — clock forward jump

Expected:

```text
misfire/catch-up
```

not Runtime corruption.

---

# 382. Test — clock backward jump

Expected:

```text
no duplicate occurrence materialization
```

---

# 383. Test — system resume

Advance MutableClock 2h.

Next cycle handles backlog.

---

# 384. Test — Runtime transient DB failure

Expected:

```text
runtime backoff

state remains RUNNING/DEGRADED
```

depending model.

---

# 385. Test — Fatal startup error

Expected:

```text
FAILED
```

never enters normal loop.

---

# 386. Test — graceful shutdown

Stop requested during batch.

Expected:

```text
current item finishes
no next item
STOPPED
```

---

# 387. Test — one active cycle

Concurrent notify calls must not create concurrent engine runs.

---

# 388. Test — long cycle

Cycle > poll interval.

Expected:

```text
next cycle after completion
```

without overlap.

---

# 389. Test — due retry earlier than schedule

Wake-up chooses retry.

---

# 390. Test — poll earlier than both

Wake-up chooses poll deadline.

---

# 391. Test — no timers

Wake-up chooses max poll deadline.

---

# 392. Test — backlog remaining

Runtime does not sleep unnecessarily.

---

# 393. Test — runtime health

After successful cycle:

```text
last_successful_cycle_at
```

updated.

---

# 394. Test — failed cycle

Do not incorrectly update success timestamp.

---

# 395. Test — degraded health

Multiple transient failures can produce degraded status.

---

# 396. Test — restart

All in-memory timing structures lost.

Runtime reconstructs behavior from repositories.

---

# 397. Anti-pattern — timer executes business logic directly

Avoid:

```text
Timer callback
→ invoke target function
```

Bypass would skip:

```text
persistence
misfire
concurrency
request identity
```

---

# 398. Anti-pattern — one timer object per Schedule as source of truth

Large scale and restart become difficult.

---

# 399. Timer objects can be optimization

Not truth.

---

# 400. Anti-pattern — schedule next time from actual wake-up

Wrong:

```text
next = now + interval
```

for a fixed-rate Schedule.

---

# 401. Anti-pattern — use monotonic clock for persisted scheduled_at

Monotonic time has no durable global meaning.

---

# 402. Anti-pattern — use wall clock for duration measurement only

Clock jumps distort elapsed timings.

---

# 403. Anti-pattern — no polling fallback with lossy notifications

Can miss new schedules indefinitely.

---

# 404. Anti-pattern — process new Schedule before commit

---

# 405. Anti-pattern — long DB transaction while sleeping

---

# 406. Anti-pattern — overlapping runtime cycles

---

# 407. Anti-pattern — Runtime performs Target execution inline

---

# 408. Anti-pattern — Runtime changes Schedule state because of its own load

A slow runtime must not silently:

```text
pause schedules
```

---

# 409. Anti-pattern — Runtime failure backoff confused with Execution retry

---

# 410. Anti-pattern — shutdown kills transaction arbitrarily

---

# 411. Anti-pattern — use health status as domain state

`DEGRADED` is not a ScheduleState.

---

# 412. Anti-pattern — wake-up signal carries authoritative state

Signal may be stale.

Always re-read.

---

# 413. Anti-pattern — assume notification order

Signals can arrive:

```text
out of order
duplicated
```

and should remain harmless.

---

# 414. Anti-pattern — no upper bound on cycle work

---

# 415. Anti-pattern — all Schedules loaded into memory forever

---

# 416. Anti-pattern — sleep indefinitely when no current work

Without reliable durable notifications, new Schedules could never be detected.

---

# 417. Anti-pattern — current process time is history

History is durable data, not memory.

---

# 418. Proposed runtime objects

```text
SchedulerRuntime

SchedulerRuntimeState

SchedulerRuntimeConfig

WakeUpPlanner

WakeUpPlan

WakeUpReason

WakeUpCoordinator / Waiter

RuntimeHealth

HealthStatus

RuntimeFailurePolicy
```

---

# 419. Ports

```text
Clock

MonotonicClock

Sleeper / WakeUpCoordinator

ScheduleTimerQueryPort

RetryTimerQueryPort
```

---

# 420. Existing application collaborators

```text
SchedulerEngine

ExecutionRuntime

RuntimeReconciler
```

---

# 421. Possible timer query port

Rather than expose repository internals:

```text
TimerQueryPort
```

could provide:

```text
earliest_schedule_due()

earliest_retry_due()
```

---

# 422. Advantage

Wake-up logic doesn't need full repositories.

---

# 423. But V1

Direct repository queries are simpler.

---

# 424. Package sketch

```text
pyschedulekit/
│
├── runtime/
│   ├── scheduler_runtime.py
│   ├── wakeup.py
│   ├── health.py
│   ├── config.py
│   └── reconciliation.py
│
├── application/
│   ├── scheduler_engine.py
│   └── execution_runtime.py
│
├── ports/
│   ├── clock.py
│   ├── sleeper.py
│   └── repositories.py
│
└── infrastructure/
    ├── time/
    ├── persistence/
    └── synchronization/
```

Illustratif uniquement.

---

# 425. V1 synchronous runtime

Architecture recommandée :

```text
Single process

One SchedulerRuntime thread

One evaluation cycle at a time

Fixed polling

Interruptible shutdown

FixedClock-compatible tests
```

---

# 426. V1.1

Ajouter :

```text
DynamicWakeUpPlanner

wake-up signals

max polling fallback
```

---

# 427. V1.2

Ajouter :

```text
in-memory timer heap

lazy timer invalidation
```

si performance utile.

---

# 428. V2

Ajouter :

```text
separate scheduler process

DB notifications

distributed wake-up
```

---

# 429. V3

Ajouter :

```text
multi-node scheduler

leases

claiming

partitioning
```

---

# 430. Core runtime algorithm V1

```text
start()

while not stop_requested:

    cycle_now = clock.now()

    scheduler_engine.evaluate_due_schedules(cycle_now)

    scheduler_engine.evaluate_waiting_admissions(cycle_now)

    execution_runtime.evaluate_due_retries(cycle_now)

    if stop_requested:
        break

    wait(poll_interval)

stop()
```

---

# 431. Hybrid runtime algorithm

```text
while running:

    cycle_now = clock.now()

    result = run_cycle(cycle_now)

    runtime_now = clock.now()

    next_schedule = query_earliest_schedule()

    next_retry = query_earliest_retry()

    wake_plan = planner.plan(
        runtime_now,
        next_schedule,
        next_retry,
        max_poll_interval,
    )

    waiter.wait_until(wake_plan.wake_at)
```

Interruptions :

```text
notify

shutdown
```

---

# 432. Long-term architecture

```text
┌─────────────────────────────────────────┐
│           SchedulerRuntime              │
│                                         │
│ Lifecycle · Wake-Up · Health · Sleep    │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│            WakeUpPlanner                │
│                                         │
│ Schedule Timer · Retry Timer · Poll     │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│           WakeUpCoordinator             │
│                                         │
│ TIMER · SIGNAL · SHUTDOWN               │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│            SchedulerEngine              │
│                                         │
│ evaluate durable scheduling truth       │
└─────────────────────────────────────────┘
```

---

# 433. Full wake-up model

```text
             Earliest Schedule
                    │
                    │
             Earliest Retry
                    │
                    │
              Max Poll Time
                    │
                    ▼
              WakeUpPlanner
                    │
                    ▼
                 wake_at
                    │
                    ▼
            WakeUpCoordinator
              │      │      │
              │      │      │
              ▼      ▼      ▼
            TIMER  SIGNAL SHUTDOWN
              │      │
              └──┬───┘
                 ▼
          SchedulerRuntime
                 │
                 ▼
             run_cycle()
```

---

# 434. Runtime robustness statement

PyScheduleKit should aim for:

> **The Runtime may wake early, late, or more than once, but durable scheduling semantics remain correct because every wake-up causes a fresh evaluation of persisted temporal state.**

---

# 435. Core invariants

```text
1.
SchedulerRuntime does not decide domain scheduling policy.

2.
A wake-up is only a signal to re-evaluate.

3.
Durable state is the source of truth.

4.
One evaluation cycle is active at a time per Runtime instance.

5.
One explicit evaluation_now is used inside each cycle.

6.
Wake-up computation after a cycle may capture a new Clock.now().

7.
Schedule timers and Retry timers remain distinct concepts.

8.
Polling is bounded by MaxPollInterval.

9.
Wake-up notifications may be duplicated or lost without breaking correctness.

10.
A polling fallback exists when notifications are non-durable.

11.
Wall Clock is used for persisted business Instants.

12.
Monotonic Clock is preferred for elapsed waits.

13.
Clock jumps are handled by normal recovery semantics.

14.
In-memory timers are not sources of truth.

15.
The Runtime never sleeps with an open scheduling transaction.

16.
Runtime errors use a separate backoff from Execution retries.

17.
Shutdown interrupts sleep and prevents new cycles.

18.
Current atomic work is completed or rolled back before stop.

19.
A process restart can rebuild runtime state from persistence.

20.
Runtime load never silently rewrites Schedule semantics.
```

---

# 436. V1 decisions

```text
1.
SchedulerRuntime is an operational/application component.

2.
SchedulerRuntimeState:
STOPPED,
STARTING,
RUNNING,
STOPPING,
FAILED.

3.
One active evaluation cycle per Runtime instance.

4.
V1 uses fixed bounded polling.

5.
Polling interval is runtime configuration,
not Schedule configuration.

6.
The first cycle after startup runs immediately.

7.
Shutdown interrupts waiting.

8.
FixedClock / MutableClock are supported in tests.

9.
No real sleeps are required in unit tests.

10.
Wall Clock and Monotonic Clock remain distinct.

11.
Schedule next_run_time and Execution next_attempt_at
are the two primary timers.

12.
Runtime backoff is distinct from RetryPolicy.

13.
Each cycle performs bounded work.

14.
Runtime may perform immediate additional cycles
while known backlog remains.

15.
No Schedule/Execution semantics depend solely
on in-memory timers.

16.
Health and lifecycle state remain separate.

17.
Dynamic wake-up and notifications are follow-up optimizations.

18.
Hybrid notification + safety polling
is the recommended production direction.

19.
SchedulerRuntime does not execute business Targets directly.

20.
All wake-ups result in re-reading durable truth.
```

---

# 437. Acceptance criteria

Le modèle Runtime est suffisamment défini si l'on peut répondre clairement à :

```text
Quelle différence entre SchedulerRuntime et SchedulerEngine ?

Pourquoi un wake-up n'est-il pas une preuve qu'un Schedule est due ?

Quelles échéances déterminent le prochain réveil ?

Quelle différence entre polling et dynamic wake-up ?

Pourquoi conserver un max poll interval ?

Que se passe-t-il si un nouveau Schedule apparaît pendant le sommeil ?

Que se passe-t-il si une notification est perdue ?

Pourquoi une notification dupliquée est-elle sans danger ?

Pourquoi distinguer Wall Clock et Monotonic Clock ?

Que se passe-t-il après un saut d'horloge ?

Pourquoi les timers en mémoire ne sont-ils pas source de vérité ?

Comment le Runtime s'arrête-t-il proprement ?

Comment distingue-t-on runtime backoff et execution retry ?

Que se passe-t-il après restart ?

Pourquoi ne faut-il pas exécuter les Targets dans la boucle de scheduling ?

Comment éviter deux cycles concurrents dans la même instance ?

Comment gérer un cycle qui dure plus longtemps que le poll interval ?

Comment le runtime détecte-t-il qu'il est en retard ?

Quelles métriques permettent de surveiller sa santé ?
```

---

# 438. Modèle mental final

```text
                           TIME
                             │
                             ▼
                        Clock.now()
                             │
                             ▼
                    SchedulerRuntime
                             │
                             ▼
                        run_cycle
                             │
                             ▼
                    SchedulerEngine
                             │
                             ▼
                       Durable State
                             │
                             ▼
                    Compute next timers
                             │
                 ┌───────────┼───────────┐
                 │           │           │
                 ▼           ▼           ▼
            Schedule due   Retry due   Poll bound
                 │           │           │
                 └───────────┼───────────┘
                             ▼
                       WakeUpPlanner
                             │
                             ▼
                          SLEEP
                             │
                   ┌─────────┼─────────┐
                   │         │         │
                   ▼         ▼         ▼
                 TIMER     SIGNAL   SHUTDOWN
                   │         │
                   └────┬────┘
                        ▼
                  evaluate again
```

---

# 439. Le principe clé

Le `SchedulerRuntime` ne sert pas à garantir que :

```text
"le callback partira exactement à 10:00:00.000"
```

Il sert à garantir que :

```text
"lorsque le système se réveille, il peut déterminer correctement
ce qui aurait dû se produire et agir selon les politiques définies."
```

---

# 440. Définition finale

> **Le SchedulerRuntime est le composant opérationnel qui maintient le SchedulerEngine vivant dans le temps en orchestrant les cycles, les réveils, les périodes de sommeil, les notifications, les erreurs globales et l'arrêt, sans devenir lui-même la source de vérité temporelle.**

---

# Conclusion

Le modèle de runtime complète une distinction essentielle de PyScheduleKit :

```text
Clock
→ indique le temps

Wake-Up
→ demande une nouvelle évaluation

SchedulerRuntime
→ orchestre la boucle

SchedulerEngine
→ transforme l'état temporel en décisions

Durable Store
→ conserve la vérité nécessaire à la reprise
```

Le Runtime peut :

```text
se réveiller trop tôt

se réveiller légèrement trop tard

recevoir deux signaux

perdre un signal

être arrêté

redémarrer
```

sans remettre en cause la sémantique métier, à condition que :

```text
l'état durable soit correct

les identités soient stables

les policies soient explicites

chaque réveil relise la vérité persistée
```

Le principe architectural final est donc :

> **Le timer optimise le moment où l'on regarde ; il ne décide jamais de ce qui est vrai.**

C'est ce principe qui permet à PyScheduleKit de commencer avec un simple polling local puis d'évoluer, sans changer son domaine, vers :

```text
dynamic wake-up

signals

timer heaps

separate scheduler processes

distributed coordination
```

---

# Suite documentaire

La prochaine étape logique est :

```text
19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md
```

Elle devra formaliser :

```text
ScheduleRepository

ExecutionRequestRepository

ExecutionRepository

Attempt persistence

UnitOfWork

transaction boundaries

ScheduleRevision vs PersistenceVersion

OccurrenceKey uniqueness

RequestId uniqueness

atomic next_run_time advancement

optimistic locking

outbox

crash consistency
```

Le **19** sera donc le document qui répondra à :

> **Comment rendre durable tout ce modèle sans perdre ni dupliquer le travail lorsqu'un crash survient au pire moment possible ?**