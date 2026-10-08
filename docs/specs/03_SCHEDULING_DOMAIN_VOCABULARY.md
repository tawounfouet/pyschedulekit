# Scheduling — Vocabulaire du domaine

**Document :** `03_SCHEDULING_DOMAIN_VOCABULARY.md`  
**Projet :** PyScheduleKit  
**Statut :** Référentiel terminologique  
**Nature :** Ubiquitous Language / Glossaire métier  
**Prérequis :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
- `01_SCHEDULING_DOMAIN_INTRODUCTION.md`
- `02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md`

---

# 1. Objectif

Le scheduling utilise un vocabulaire qui semble familier :

```text
Job
Task
Schedule
Trigger
Run
Execution
Retry
Queue
Worker
Scheduler
```

Le problème est que ces termes changent de sens selon les technologies.

Par exemple :

```text
cron
Job = commande planifiée

APScheduler
Job = objet représentant une planification

Celery
Task = fonction distribuable

Airflow
Task = nœud d'un workflow

Kubernetes
Job = workload fini

Spark
Job = unité de calcul distribuée

CI/CD
Job = unité d'exécution d'un pipeline
```

Cette ambiguïté devient dangereuse lorsqu'un framework tente d'intégrer plusieurs domaines.

PyScheduleKit doit donc disposer d'un **vocabulaire explicite, cohérent et stable**.

L'objectif de ce document est de fixer le sens des termes fondamentaux avant de modéliser les objets métier.

---

# 2. Principe du langage ubiquitaire

Dans une approche Domain-Driven Design, un **Ubiquitous Language** désigne un vocabulaire commun utilisé :

```text
dans la documentation
dans le code
dans les tests
dans les discussions
dans les diagrammes
dans les APIs
```

Un terme important ne doit pas changer de sens selon le contexte sans que cette variation soit explicitement documentée.

Ainsi :

```text
Schedule
```

doit désigner le même concept :

```text
dans un diagramme
dans une dataclass
dans un repository
dans une API
dans un test
```

---

# 3. Règle terminologique principale

Le vocabulaire de PyScheduleKit repose sur cette chaîne conceptuelle :

```text
Target
   │
   ▼
Schedule
   │
   ├── Trigger
   │
   ▼
Occurrence
   │
   ▼
Scheduling Decision
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
ExecutionResult
```

Cette chaîne doit rester la référence centrale.

---

# 4. Vue synthétique du vocabulaire

| Terme | Question principale | Nature |
|---|---|---|
| `Target` | Qu'est-ce qui devra être déclenché ? | Référence exécutable |
| `Job` | Quelle unité logique de travail est définie ? | Définition de travail |
| `Schedule` | Selon quelle planification ce travail devient-il exigible ? | Entité de planification |
| `Trigger` | Comment calculer les occurrences ? | Règle temporelle |
| `Occurrence` | Quel instant planifié a été produit ? | Fait temporel |
| `NextRunTime` | Quelle est la prochaine occurrence connue ? | Valeur dérivée |
| `Due` | L'occurrence doit-elle être traitée maintenant ? | État / prédicat |
| `Misfire` | L'occurrence n'a-t-elle pas été traitée à temps ? | Situation métier |
| `ExecutionRequest` | Quel travail doit maintenant être soumis au runtime ? | Commande |
| `Execution` | Quelle exécution concrète existe ? | Entité runtime |
| `Attempt` | Quelle tentative d'une exécution est en cours ? | Sous-unité d'exécution |
| `ExecutionResult` | Quel est le résultat de l'exécution ? | Valeur résultat |
| `Scheduler` | Qui prend les décisions temporelles ? | Service |
| `Executor` | Qui soumet réellement le travail au mécanisme d'exécution ? | Port / service |
| `Worker` | Qui consomme et exécute le travail ? | Runtime externe |
| `Clock` | Quelle heure le domaine considère-t-il comme courante ? | Abstraction temporelle |
| `Calendar` | Quelles périodes sont autorisées ou exclues ? | Règle métier temporelle |
| `Policy` | Que faire dans une situation particulière ? | Stratégie métier |

---

# 5. Time

## Définition

`Time` représente le domaine conceptuel du temps.

Ce n'est pas un objet métier unique.

Il regroupe :

```text
Instant
Duration
Timezone
Calendar
Clock
Interval
Deadline
```

Le terme `Time` ne doit donc pas être utilisé comme substitut approximatif de `datetime`.

---

# 6. Instant

## Définition

Un `Instant` représente un point précis sur la ligne du temps.

Exemple :

```text
2026-09-28T06:00:00Z
```

Un instant est conceptuellement indépendant de la manière dont un humain l'affiche.

Ainsi :

```text
2026-09-28T06:00:00Z
```

et :

```text
2026-09-28 08:00 Europe/Paris
```

peuvent représenter le même instant.

## Rôle

`Instant` est utile pour représenter :

```text
scheduled_at
created_at
started_at
finished_at
deadline
lease_expiration
```

---

# 7. LocalDateTime

## Définition

Une `LocalDateTime` représente une date et une heure dans un calendrier local, mais sans identifier à elle seule un instant universel.

Exemple :

```text
2026-10-25 02:30
```

Cette valeur peut être ambiguë selon le fuseau horaire.

## Distinction

```text
LocalDateTime
≠
Instant
```

Une timezone peut être nécessaire pour convertir l'une vers l'autre.

---

# 8. Timezone

## Définition

Une `Timezone` représente les règles permettant de convertir entre temps local et temps absolu.

Exemples :

```text
UTC
Europe/Paris
America/New_York
Asia/Tokyo
```

Elle inclut potentiellement :

```text
offset UTC
règles historiques
heure d'été
heure d'hiver
```

## Invariant

Une récurrence calendaire locale ne doit pas perdre sa timezone.

```text
Every day at 08:00 Europe/Paris
```

ne doit pas être remplacé naïvement par :

```text
Every day at 06:00 UTC
```

car cette équivalence n'est pas constante sur toute l'année.

---

# 9. Duration

## Définition

Une `Duration` représente une quantité de temps.

Exemples :

```text
30 seconds
5 minutes
2 hours
7 days
```

Elle est utilisée pour :

```text
interval
timeout
retry delay
grace period
jitter range
lease duration
```

## Distinction

```text
Duration
≠
DateTime
```

Une durée ne représente pas un instant.

---

# 10. Interval

## Définition

Un `Interval` représente une zone temporelle comprise entre deux bornes.

```text
[start, end]
```

Exemple :

```text
08:00 → 18:00
```

Il peut représenter :

```text
execution window
maintenance window
availability window
calendar exclusion
```

---

# 11. Clock

## Définition

Un `Clock` est l'abstraction utilisée pour obtenir le temps courant.

Conceptuellement :

```text
Clock.now()
    ↓
Instant
```

## Pourquoi ne pas appeler directement l'horloge système ?

Pour permettre :

```text
tests déterministes
simulation temporelle
replay
tests DST
tests de misfire
tests de recovery
```

## Implémentations possibles

```text
SystemClock
FixedClock
MutableClock
OffsetClock
```

---

# 12. Calendar

## Définition

Un `Calendar` détermine quelles dates ou périodes sont considérées comme admissibles.

Exemples :

```text
WorkingDaysCalendar
HolidayCalendar
BusinessHoursCalendar
MaintenanceCalendar
ExcludedDatesCalendar
```

## Question principale

> Cet instant ou cette date est-il valide selon les règles calendaires ?

Conceptuellement :

```text
Calendar.allows(instant)
```

---

# 13. Business Calendar

## Définition

Un `BusinessCalendar` est un calendrier enrichi de règles métier.

Exemple :

```text
lundi → vendredi
hors jours fériés
hors fermeture annuelle
```

Il peut servir à définir :

```text
premier jour ouvré
dernier jour ouvré
jour bancaire suivant
```

---

# 14. Target

## Définition

Un `Target` représente ce que le scheduler souhaite rendre exécutable.

Il s'agit volontairement d'un terme abstrait.

Un target peut être :

```text
fonction Python
commande
workflow
message
endpoint HTTP
operation
job distant
```

## Rôle

Le scheduler n'a pas nécessairement besoin de connaître les détails internes du target.

Il doit seulement pouvoir produire une demande permettant au runtime approprié de le déclencher.

---

# 15. Operation

## Définition

Une `Operation` représente une action logique atomique du point de vue du composant qui l'appelle.

Exemple :

```text
refresh_cache
send_report
start_ingestion
```

Une opération peut être implémentée :

```text
localement
à distance
via queue
via workflow
```

Le terme reste plus générique que `Task`.

---

# 16. Job

## Définition retenue

Dans PyScheduleKit, un `Job` représente une **définition nommée d'un travail pouvant être demandé à l'exécution**.

Il peut contenir :

```text
job_id
name
target
arguments
metadata
```

Le job décrit principalement :

> Quoi exécuter ?

Il ne décrit pas nécessairement :

> Quand ?

## Exemple

```text
Job
────────────────────
id = daily_report
target = generate_report
```

## Important

```text
Job ≠ Schedule
```

Un job peut être partagé par plusieurs schedules.

---

# 17. Task

## Position terminologique

Le terme `Task` est volontairement évité comme concept central dans PyScheduleKit.

Pourquoi ?

Parce qu'il est déjà fortement chargé dans :

```text
Celery
Airflow
asyncio
workflow engines
distributed runtimes
```

Dans PyScheduleKit, `Task` pourra éventuellement apparaître dans des adapters spécifiques, mais ne doit pas devenir un synonyme de :

```text
Job
Schedule
Execution
Occurrence
```

---

# 18. Schedule

## Définition

Un `Schedule` représente la configuration durable reliant :

```text
un travail
+
une règle temporelle
+
des politiques de scheduling
```

Conceptuellement :

```text
Schedule
────────────────────────
schedule_id
job / target
trigger
timezone
calendar
misfire_policy
concurrency_policy
lifecycle_state
```

## Question principale

> Selon quelle règle et quelles politiques ce travail devient-il exigible ?

## Exemple

```text
Schedule
daily_orders

Target:
daily_orders_pipeline

Trigger:
Every day @ 06:00

Timezone:
Europe/Paris

Concurrency:
FORBID
```

---

# 19. Schedule Definition

`ScheduleDefinition` peut être utilisé lorsque l'on souhaite distinguer la configuration déclarative du schedule de son état runtime.

Exemple :

```text
ScheduleDefinition
        +
ScheduleState
        =
effective Schedule
```

Cette distinction reste ouverte et sera analysée dans le modèle métier.

---

# 20. Trigger

## Définition

Un `Trigger` représente une règle capable de calculer des occurrences temporelles.

Question centrale :

> Quelle est la prochaine occurrence valide ?

Conceptuellement :

```text
Trigger.next(after)
```

peut retourner :

```text
Occurrence
```

ou :

```text
None
```

lorsque le trigger est épuisé.

---

# 21. DateTrigger

## Définition

Un `DateTrigger` produit normalement une occurrence unique.

Exemple :

```text
2026-10-01 09:00
```

Il modélise :

```text
one-shot scheduling
```

---

# 22. IntervalTrigger

## Définition

Un `IntervalTrigger` produit des occurrences séparées par une durée.

Exemple :

```text
every 5 minutes
```

Conceptuellement :

```text
10:00
10:05
10:10
10:15
```

Une distinction importante devra être faite ultérieurement entre :

```text
fixed rate
```

et :

```text
fixed delay
```

---

# 23. CronTrigger

## Définition

Un `CronTrigger` produit des occurrences à partir d'une règle calendaire de type cron.

Exemple :

```text
0 6 * * *
```

Il décrit une récurrence calendaire, pas une durée absolue entre chaque occurrence.

---

# 24. CalendarTrigger

## Définition

Un `CalendarTrigger` représente une règle temporelle s'appuyant explicitement sur un calendrier métier.

Exemple :

```text
first working day of every month at 08:00
```

Il peut nécessiter :

```text
Calendar
Timezone
LocalTime
```

---

# 25. Recurrence

## Définition

Une `Recurrence` représente la propriété d'une règle à produire plusieurs occurrences dans le temps.

Conceptuellement :

```text
R = {t1, t2, t3, ..., tn}
```

ou potentiellement une suite infinie.

## Distinction

```text
Recurrence
≠
Retry
```

Une recurrence produit des échéances prévues.

Un retry produit une nouvelle tentative liée à un échec.

---

# 26. Occurrence

## Définition

Une `Occurrence` représente une échéance temporelle concrète produite par un trigger.

Exemple :

```text
Schedule:
Every day @ 06:00

Occurrence:
2026-09-29 06:00
```

## Nature

Une occurrence est avant tout un fait du domaine temporel.

Elle peut porter :

```text
schedule_id
scheduled_at
sequence
metadata temporelles
```

## Important

```text
Occurrence ≠ Execution
```

Une occurrence peut :

```text
être exécutée
être ignorée
être manquée
être coalescée
être annulée
```

---

# 27. Occurrence Identity

Question ouverte :

> Une occurrence a-t-elle besoin d'un identifiant ?

Deux représentations sont possibles.

```text
(schedule_id, scheduled_at)
```

ou :

```text
occurrence_id
```

Le choix aura un impact sur :

```text
deduplication
persistence
distributed scheduling
replay
audit
```

---

# 28. NextRunTime

## Définition

`NextRunTime` représente l'instant actuellement considéré comme prochaine échéance connue d'un schedule.

Exemple :

```text
next_run_time = 2026-09-29T06:00
```

## Important

Il peut être :

```text
dérivé
persisté
mis en cache
```

selon l'architecture.

Le terme ne doit pas être confondu avec :

```text
started_at
execution_time
retry_at
```

---

# 29. ScheduledAt

## Définition

`scheduled_at` désigne l'instant auquel une occurrence était prévue.

Exemple :

```text
scheduled_at = 06:00:00
```

Même si l'exécution démarre à :

```text
06:00:07
```

le `scheduled_at` reste :

```text
06:00:00
```

---

# 30. TriggeredAt

## Définition

`triggered_at` représente l'instant auquel le scheduler a effectivement pris la décision de produire une demande d'exécution.

Exemple :

```text
scheduled_at = 06:00:00
triggered_at = 06:00:02
```

---

# 31. StartedAt

## Définition

`started_at` représente l'instant auquel l'exécution réelle commence.

Exemple :

```text
scheduled_at = 06:00:00
triggered_at = 06:00:02
started_at   = 06:00:06
```

Ces trois valeurs sont différentes et doivent rester distinctes.

---

# 32. Scheduling Lag

## Définition

Le `SchedulingLag` mesure le retard entre l'heure planifiée et une étape réelle du traitement.

Par exemple :

```text
trigger_lag = triggered_at - scheduled_at
```

ou :

```text
start_lag = started_at - scheduled_at
```

Il faut préciser la définition utilisée lorsque cette métrique est exposée.

---

# 33. Due

## Définition

Une occurrence est `Due` lorsqu'elle est arrivée au moment où le scheduler doit prendre une décision à son sujet.

Version simplifiée :

```text
now >= scheduled_at
```

Mais cela ne signifie pas automatiquement :

```text
execute now
```

Des politiques peuvent encore intervenir.

---

# 34. Eligibility

## Définition

`Eligibility` représente le fait qu'une occurrence soit non seulement arrivée à échéance, mais également autorisée à devenir une demande d'exécution.

Exemple :

```text
Due
+
Schedule ACTIVE
+
Calendar allows
+
Concurrency policy allows
+
Deadline not exceeded
        ↓
Eligible
```

Cette notion permet de distinguer :

```text
time reached
```

de :

```text
execution permitted
```

---

# 35. Misfire

## Définition

Un `Misfire` est une situation où une occurrence aurait dû être traitée précédemment mais ne l'a pas été dans le scénario nominal.

Exemple :

```text
scheduled_at = 08:00
scheduler restarted = 08:15
```

La simple existence d'un retard ne définit pas toujours un misfire.

Une politique ou une tolérance peut intervenir.

---

# 36. MisfirePolicy

## Définition

La `MisfirePolicy` détermine comment traiter une occurrence manquée.

Exemples de décisions possibles :

```text
SKIP
RUN_NOW
RESCHEDULE
CATCH_UP
COALESCE
```

Le nom exact des politiques sera figé ultérieurement.

---

# 37. GracePeriod

## Définition

Une `GracePeriod` représente une durée pendant laquelle une occurrence reste encore acceptable après son instant planifié.

Exemple :

```text
scheduled_at = 08:00
grace_period = 5 min
```

Alors :

```text
08:03 → still acceptable
08:15 → no longer acceptable
```

---

# 38. Deadline

## Définition

Une `Deadline` représente l'instant absolu après lequel une action n'est plus considérée valide ou utile.

Conceptuellement :

```text
scheduled_at
     │
     ├──── valid window ────┐
     │                      │
     ▼                      ▼
  08:00                  08:05
                       deadline
```

---

# 39. CatchUp

## Définition

Le `CatchUp` consiste à produire des traitements pour plusieurs occurrences passées.

Exemple :

```text
08:00 missed
09:00 missed
10:00 missed
```

avec redémarrage à :

```text
10:30
```

peut produire :

```text
ExecutionRequest(08:00)
ExecutionRequest(09:00)
ExecutionRequest(10:00)
```

---

# 40. Coalescing

## Définition

Le `Coalescing` consiste à regrouper plusieurs occurrences en une seule décision d'exécution.

Exemple :

```text
08:00
09:00
10:00
```

devient :

```text
1 ExecutionRequest
```

## Distinction

```text
CatchUp
→ plusieurs exécutions

Coalescing
→ une exécution représentant plusieurs échéances
```

---

# 41. Skip

## Définition

`Skip` signifie qu'une occurrence connue ne produira volontairement aucune exécution.

Le skip est une décision explicite.

Il peut résulter :

```text
d'une misfire policy
d'une calendar rule
d'une concurrency policy
d'une deadline
```

---

# 42. Missed

## Définition

`Missed` décrit une occurrence qui n'a pas pu être traitée selon le comportement attendu.

Il s'agit davantage d'une qualification factuelle.

## Distinction

```text
MISSED
= ce qui s'est produit

SKIP
= décision prise
```

Une occurrence missed peut ensuite être :

```text
skipped
replayed
coalesced
run now
```

---

# 43. Overlap

## Définition

Un `Overlap` apparaît lorsque plusieurs exécutions associées à une même contrainte de concurrence peuvent être actives simultanément.

Exemple :

```text
Run #1
10:00 ───────────── 10:08

Run #2
       10:05 ───────────── 10:13
```

La période :

```text
10:05 → 10:08
```

est un overlap.

---

# 44. Concurrency

## Définition

`Concurrency` décrit la présence potentielle de plusieurs exécutions actives simultanément.

Elle peut être évaluée :

```text
par schedule
par job
par target
par resource key
```

Le scope devra toujours être explicite.

---

# 45. ConcurrencyPolicy

## Définition

La `ConcurrencyPolicy` détermine ce qu'il faut faire lorsqu'une nouvelle occurrence devient eligible alors qu'une exécution incompatible est déjà active.

Exemples :

```text
ALLOW
FORBID
QUEUE
COALESCE
REPLACE
```

---

# 46. MaxInstances

## Définition

`MaxInstances` représente une limite quantitative de concurrence.

Exemple :

```text
max_instances = 3
```

signifie qu'un quatrième run ne pourra pas immédiatement commencer.

Il faudra déterminer si ce concept appartient au schedule, au job, au target ou à l'executor.

---

# 47. ExecutionRequest

## Définition

Une `ExecutionRequest` représente la commande créée lorsqu'une décision de scheduling conclut qu'un travail doit être soumis à l'exécution.

Elle constitue la frontière entre :

```text
Scheduling Domain
```

et :

```text
Execution Runtime
```

## Contenu potentiel

```text
request_id
schedule_id
occurrence_id
target
scheduled_at
created_at
execution_context
metadata
```

## Important

```text
ExecutionRequest
≠
Execution
```

Une demande peut :

```text
être refusée
rester en attente
échouer à la soumission
être dédupliquée
```

avant qu'une véritable exécution ne commence.

---

# 48. Execution

## Définition

Une `Execution` représente un run concret associé à une demande d'exécution.

Elle possède généralement :

```text
execution_id
request_id
status
started_at
finished_at
result
error
```

## Question principale

> Que s'est-il réellement passé au runtime ?

---

# 49. Run

## Position terminologique

`Run` est un terme pratique mais ambigu.

Dans PyScheduleKit, il pourra être utilisé dans :

```text
API conviviale
logging
documentation utilisateur
```

mais le modèle métier doit préférer :

```text
Execution
```

lorsqu'une précision conceptuelle est requise.

Ainsi :

```text
run
≈ terme informel

Execution
= terme métier formel
```

---

# 50. Attempt

## Définition

Un `Attempt` représente une tentative individuelle d'accomplissement d'une execution.

Exemple :

```text
Execution E1
    │
    ├── Attempt #1 FAILED
    ├── Attempt #2 FAILED
    └── Attempt #3 SUCCESS
```

Cette distinction permet de séparer :

```text
logical execution
```

de :

```text
technical attempts
```

---

# 51. Retry

## Définition

Un `Retry` signifie qu'une nouvelle tentative est créée après un échec ou une situation retryable.

Il se rapporte donc généralement à :

```text
Attempt
```

et non à une nouvelle occurrence temporelle.

## Distinction essentielle

```text
Occurrence #1
    ├── Attempt #1
    ├── Attempt #2
    └── Attempt #3

Occurrence #2
    └── Attempt #1
```

Ainsi :

```text
Retry ≠ Recurrence
```

---

# 52. RetryPolicy

## Définition

Une `RetryPolicy` détermine :

```text
si un retry est autorisé
combien de tentatives
quels échecs sont retryables
quel délai appliquer
quelle stratégie de backoff
```

Il faudra distinguer les retries appartenant :

```text
au scheduler
à l'executor
au workflow
à l'opération métier
```

PyScheduleKit ne doit pas absorber tous les retries des systèmes qu'il déclenche.

---

# 53. Backoff

## Définition

Le `Backoff` représente la stratégie utilisée pour déterminer le délai entre plusieurs tentatives.

Exemples :

```text
constant
linear
exponential
exponential with jitter
```

Exemple :

```text
5 s
10 s
20 s
40 s
```

---

# 54. Timeout

## Définition

Un `Timeout` représente une durée maximale accordée à une opération ou une phase avant de considérer qu'elle a dépassé son budget temporel.

Exemple :

```text
execution timeout = 30 minutes
```

## Distinction

```text
Deadline
= instant absolu

Timeout
= durée maximale
```

---

# 55. Jitter

## Définition

Un `Jitter` représente une variation volontaire ajoutée à un instant ou un délai.

Exemple :

```text
planned = 00:00:00
jitter  = ±30 s
```

Objectif :

```text
répartir les charges
éviter le thundering herd
désynchroniser les workloads
```

---

# 56. ExecutionResult

## Définition

Un `ExecutionResult` représente l'issue observable d'une execution terminée.

Il peut contenir :

```text
status
value
error
finished_at
metadata
```

Il ne doit pas nécessairement stocker des objets métiers volumineux.

Il peut référencer :

```text
ArtifactRef
DatasetRef
external result
```

---

# 57. ExecutionStatus

## Définition

`ExecutionStatus` représente l'état courant d'une execution.

Exemples potentiels :

```text
CREATED
QUEUED
RUNNING
SUCCESS
FAILED
CANCELLED
TIMED_OUT
REJECTED
```

Cette liste devra être figée lors de la définition de la machine à états.

---

# 58. OccurrenceStatus

Une occurrence peut également avoir son propre statut.

Exemples potentiels :

```text
PLANNED
DUE
MISSED
SKIPPED
COALESCED
MATERIALIZED
```

Il ne faut pas réutiliser les statuts d'execution lorsque la sémantique diffère.

---

# 59. ScheduleStatus

Le schedule possède encore un cycle de vie différent.

Exemples :

```text
ACTIVE
PAUSED
DISABLED
COMPLETED
CANCELLED
```

Ainsi :

```text
ScheduleStatus
≠
OccurrenceStatus
≠
ExecutionStatus
```

Cette séparation sera fondamentale.

---

# 60. Scheduler

## Définition

Le `Scheduler` est le service chargé de coordonner la logique temporelle.

Il peut :

```text
observer le temps
charger les schedules
identifier les occurrences dues
appliquer les politiques
créer des ExecutionRequests
calculer les prochaines occurrences
persister l'état
```

## Question centrale

> Qu'est-ce qui doit devenir exécutable maintenant ?

---

# 61. SchedulerEngine

## Définition

`SchedulerEngine` peut désigner le cœur algorithmique du scheduler, séparé de son processus runtime.

Conceptuellement :

```text
SchedulerEngine
    │
    ├── evaluate
    ├── decide
    └── produce decisions
```

alors que :

```text
SchedulerRuntime
```

pourrait gérer :

```text
loop
sleep
startup
shutdown
signals
threads
```

Cette séparation est intéressante pour la testabilité.

---

# 62. Tick

## Définition

Un `Tick` représente une itération logique du scheduler.

Conceptuellement :

```text
Tick
  ↓
read clock
  ↓
find due schedules
  ↓
apply decisions
  ↓
persist
```

Un tick n'est pas nécessairement associé à une fréquence fixe.

---

# 63. WakeUp

## Définition

Un `WakeUp` représente un réveil du runtime scheduler afin de réévaluer son état.

Il peut être provoqué par :

```text
prochaine échéance
nouveau schedule
modification
pause/resume
shutdown
signal externe
```

---

# 64. Executor

## Définition

Un `Executor` représente l'abstraction chargée de soumettre ou d'effectuer le travail concret.

Exemples :

```text
InlineExecutor
ThreadExecutor
ProcessExecutor
AsyncExecutor
QueueExecutor
RemoteExecutor
WorkflowExecutor
```

## Question centrale

> Comment soumettre ce travail au mécanisme d'exécution ?

---

# 65. Scheduler versus Executor

```text
Scheduler
→ décide QUAND

Executor
→ décide COMMENT SOUMETTRE / EXÉCUTER
```

Le scheduler ne doit pas incorporer les détails techniques de tous les runtimes possibles.

---

# 66. Worker

## Définition

Un `Worker` représente un processus ou une instance consommant du travail à exécuter.

Il apparaît surtout dans des architectures :

```text
queue-based
distributed
remote
```

Exemple :

```text
Scheduler
   ↓
Queue
   ↓
Worker
```

Le worker n'est pas nécessairement un objet interne à PyScheduleKit.

---

# 67. Queue

## Définition

Une `Queue` représente un mécanisme permettant à du travail de patienter jusqu'à ce qu'une capacité de traitement soit disponible.

## Distinction

```text
Scheduler
→ quand le travail devient disponible

Queue
→ où le travail attend
```

Une queue n'est donc pas un schedule.

---

# 68. Store

## Définition

Un `Store` est une abstraction de persistance.

Dans PyScheduleKit, plusieurs responsabilités peuvent être séparées :

```text
ScheduleStore
ExecutionStore
OccurrenceStore
LeaseStore
```

Il faudra éviter un `JobStore` universel trop vague si plusieurs concepts sont réellement persistés.

---

# 69. ScheduleStore

## Définition

Un `ScheduleStore` conserve les définitions et/ou l'état des schedules.

Il peut supporter :

```text
add
get
update
remove
find_due
```

La responsabilité exacte sera définie avec le modèle de persistance.

---

# 70. ExecutionStore

## Définition

Un `ExecutionStore` conserve les exécutions et leur état.

Il peut permettre :

```text
historique
audit
recovery
observability
deduplication
```

---

# 71. Repository

## Position terminologique

Un `Repository` représente une abstraction métier d'accès à des agrégats.

Un `Store` peut être davantage orienté infrastructure.

Cette distinction DDD devra rester consciente.

Par exemple :

```text
ScheduleRepository
```

pourrait être l'interface du domaine ou de l'application tandis qu'un :

```text
SQLScheduleStore
```

serait une implémentation infrastructure.

---

# 72. Persistence

## Définition

`Persistence` désigne la capacité à conserver l'état au-delà de la durée de vie du processus.

Elle peut concerner :

```text
schedules
next_run_time
executions
attempts
leases
events
```

---

# 73. Recovery

## Définition

`Recovery` désigne la reconstruction d'un état opérationnel valide après une interruption.

Exemple :

```text
restart
   ↓
load persisted state
   ↓
reconcile
   ↓
resume scheduling
```

---

# 74. Reconciliation

## Définition

La `Reconciliation` compare l'état attendu avec l'état observé et produit les décisions nécessaires pour rétablir la cohérence.

Exemple :

```text
Expected:
Occurrence 08:00 processed

Observed:
No execution exists

Current time:
08:15
```

Le système doit décider quoi faire.

---

# 75. Ownership

## Définition

`Ownership` indique quelle instance du scheduler est autorisée à traiter un élément donné à un instant donné.

Cette notion apparaît principalement dans les architectures distribuées.

---

# 76. Lock

## Définition

Un `Lock` représente un mécanisme d'exclusion empêchant plusieurs acteurs d'accéder simultanément à une ressource ou une décision critique.

Exemple :

```text
lock(schedule_id)
```

Il ne doit pas nécessairement être exposé comme concept métier de premier niveau si une abstraction plus adaptée existe.

---

# 77. Lease

## Définition

Une `Lease` représente un droit temporaire exclusif ou semi-exclusif sur une ressource.

Exemple :

```text
owner = scheduler-A
valid_until = 08:00:30
```

La différence avec un lock classique est notamment son caractère temporel et expirant.

---

# 78. Leader

## Définition

Un `Leader` est l'instance actuellement responsable d'une fonction de coordination dans une architecture distribuée.

Exemple :

```text
Scheduler A = LEADER
Scheduler B = STANDBY
```

---

# 79. LeaderElection

## Définition

`LeaderElection` désigne le mécanisme permettant aux instances distribuées de désigner un leader.

Il s'agit d'un problème d'infrastructure distribuée, pas d'une responsabilité fonctionnelle de chaque schedule.

---

# 80. Deduplication

## Définition

La `Deduplication` consiste à reconnaître qu'une demande ou une exécution correspond à un travail déjà traité ou en cours.

Une clé possible :

```text
(schedule_id, occurrence_time)
```

peut servir de base.

Le modèle devra cependant préciser les garanties recherchées.

---

# 81. Idempotence

## Définition

Une opération est `Idempotent` lorsque la répéter produit un effet observable équivalent à une seule application.

Conceptuellement :

```text
f(f(x)) = f(x)
```

dans la perspective de l'effet considéré.

L'idempotence appartient généralement au travail exécuté plutôt qu'au scheduler lui-même.

---

# 82. AtMostOnce

## Définition

`AtMostOnce` signifie que le système cherche à éviter toute exécution multiple.

Résultat possible :

```text
0 ou 1
```

Une exécution peut être perdue.

---

# 83. AtLeastOnce

## Définition

`AtLeastOnce` signifie que le système privilégie la non-perte du travail.

Résultat possible :

```text
1 ou plusieurs tentatives
```

Cela nécessite souvent :

```text
idempotence
deduplication
```

---

# 84. ExactlyOnce

## Définition prudente

`ExactlyOnce` ne doit jamais être utilisé sans préciser la couche concernée.

Il peut signifier :

```text
one scheduling decision
one execution request
one processing attempt
one business effect
```

Ces garanties sont différentes.

PyScheduleKit ne devra pas annoncer une garantie `exactly once` sans définir précisément son périmètre.

---

# 85. ExecutionContext

## Définition

Un `ExecutionContext` transporte les informations transverses associées à une exécution.

Exemple :

```text
correlation_id
trace_id
schedule_id
occurrence_id
execution_id
scheduled_at
metadata
```

Il peut faciliter l'intégration avec les autres Py*Kit.

---

# 86. CorrelationId

## Définition

Un `CorrelationId` permet de relier plusieurs événements ou opérations appartenant à une même chaîne logique.

Exemple :

```text
PyScheduleKit
ScheduleExecution
      │
correlation_id = ABC
      ▼
PyWorkflowKit
WorkflowRun
      │
correlation_id = ABC
      ▼
PyIngestKit
IngestionRun
```

---

# 87. TraceId

## Définition

Un `TraceId` représente un identifiant utilisé dans le tracing distribué.

Il peut coïncider ou non avec `CorrelationId`.

Les deux concepts ne doivent pas être fusionnés automatiquement.

---

# 88. Event

## Définition

Un `Event` décrit un fait qui s'est produit.

Exemples :

```text
ScheduleCreated
OccurrenceDue
OccurrenceSkipped
ExecutionRequested
ExecutionStarted
ExecutionSucceeded
```

Un event est formulé au passé ou comme un fait accompli.

---

# 89. Command

## Définition

Une `Command` représente une intention demandant qu'une action soit effectuée.

Exemple :

```text
CreateSchedule
PauseSchedule
RequestExecution
```

## Distinction

```text
Command
→ demande

Event
→ fait constaté
```

---

# 90. SchedulingDecision

## Définition

Une `SchedulingDecision` représente la conclusion obtenue par le moteur après évaluation du contexte.

Exemples :

```text
WAIT
EXECUTE
SKIP
COALESCE
CATCH_UP
```

Elle permet de séparer :

```text
decision logic
```

de :

```text
side effects
```

---

# 91. Policy

## Définition

Une `Policy` représente une règle explicitement configurable appliquée lors d'une situation particulière.

Exemples :

```text
MisfirePolicy
ConcurrencyPolicy
RetryPolicy
TimeoutPolicy
JitterPolicy
```

Une policy répond souvent à :

> Que doit faire le système lorsque cette situation survient ?

---

# 92. Rule

## Définition

Une `Rule` représente une contrainte ou une logique déterministe du domaine.

Exemple :

```text
occurrence must not precede schedule start
```

Une rule peut être intrinsèque au domaine, contrairement à une policy qui peut être sélectionnable.

---

# 93. Invariant

## Définition

Un `Invariant` représente une propriété qui doit toujours rester vraie pour préserver la cohérence du modèle.

Exemples potentiels :

```text
next occurrence > previous occurrence

finished_at >= started_at

disabled schedule does not create new executions
```

Les invariants seront formalisés dans les documents de modèle métier.

---

# 94. State

## Définition

`State` représente une situation durable ou transitoire d'un objet.

Il ne faut pas créer un état universel.

On distingue notamment :

```text
ScheduleState
OccurrenceState
ExecutionState
AttemptState
```

---

# 95. Lifecycle

## Définition

Un `Lifecycle` représente les transitions autorisées entre les états d'un objet.

Exemple :

```text
ACTIVE
  │
pause
  ▼
PAUSED
  │
resume
  ▼
ACTIVE
```

---

# 96. Pause

## Définition

`Pause` suspend la production normale de nouvelles exécutions à partir d'un schedule sans nécessairement supprimer sa définition.

Une question importante reste :

> Que deviennent les occurrences produites pendant la pause ?

Cette réponse doit dépendre d'une politique explicite.

---

# 97. Resume

## Définition

`Resume` réactive un schedule précédemment suspendu.

Le resume doit préciser sa sémantique :

```text
next future occurrence
catch-up
coalesce
```

selon la politique adoptée.

---

# 98. Disable

## Définition

`Disable` marque un schedule comme temporairement non actif.

La différence exacte entre :

```text
PAUSED
DISABLED
```

devra être justifiée si les deux concepts sont conservés.

Sinon, un seul devra rester.

---

# 99. Cancel

## Définition

`Cancel` représente l'arrêt définitif ou demandé d'un objet.

Il faut toujours préciser l'objet :

```text
cancel schedule
cancel occurrence
cancel execution
cancel attempt
```

Ces actions ne sont pas équivalentes.

---

# 100. Reschedule

## Définition

`Reschedule` modifie la règle temporelle ou certaines propriétés affectant les occurrences futures.

Exemple :

```text
06:00
→
08:00
```

Le reschedule pose des questions sur :

```text
next_run_time
occurrences déjà dues
executions queued
versioning
```

---

# 101. StartAt

## Définition

`StartAt` représente la borne à partir de laquelle un schedule peut produire des occurrences.

Exemple :

```text
start_at = 2026-10-01
```

---

# 102. EndAt

## Définition

`EndAt` représente la borne après laquelle aucune nouvelle occurrence ne doit être produite.

Exemple :

```text
end_at = 2026-12-31
```

---

# 103. Finite Schedule

Un `FiniteSchedule` produit un nombre limité d'occurrences.

Exemple :

```text
Every day
from Oct 1
to Oct 7
```

---

# 104. Infinite Schedule

Un `InfiniteSchedule` n'a pas de fin temporelle définie.

Exemple :

```text
Every Monday @ 08:00
```

jusqu'à suspension, annulation ou modification.

---

# 105. Fixed Rate

## Définition

En `FixedRate`, les occurrences sont calculées à partir d'une grille temporelle indépendante de la durée réelle des exécutions.

Exemple :

```text
10:00
10:05
10:10
10:15
```

même si un run dure huit minutes.

---

# 106. Fixed Delay

## Définition

En `FixedDelay`, le prochain déclenchement dépend de la fin d'une exécution précédente.

Exemple :

```text
Run starts 10:00
Run ends   10:08

delay = 5 min

next = 10:13
```

## Important

```text
FixedRate
≠
FixedDelay
```

Cette distinction devra probablement apparaître dans le modèle des triggers.

---

# 107. Recurrence Window

Une `RecurrenceWindow` représente une période pendant laquelle une récurrence peut produire des occurrences.

Exemple :

```text
every 5 min
between 08:00 and 18:00
```

---

# 108. Blackout Window

Une `BlackoutWindow` représente une période durant laquelle aucune nouvelle exécution ne doit être déclenchée.

Exemple :

```text
maintenance:
02:00 → 03:00
```

---

# 109. Execution Window

Une `ExecutionWindow` représente une période pendant laquelle une occurrence peut encore produire une exécution valide.

Elle peut être dérivée de :

```text
scheduled_at
+
grace period
```

---

# 110. Scheduler Runtime

## Définition

Le `SchedulerRuntime` représente le processus opérationnel qui héberge le scheduler.

Il peut gérer :

```text
startup
shutdown
loop
sleep
signals
threads
async event loop
```

Ces préoccupations doivent être séparées autant que possible du domaine pur.

---

# 111. Scheduler Node

## Définition

Un `SchedulerNode` représente une instance d'un scheduler dans un déploiement distribué.

Exemple :

```text
scheduler-node-1
scheduler-node-2
scheduler-node-3
```

Cette notion devient utile pour :

```text
ownership
leases
leader election
observability
```

---

# 112. Schedule Version

## Définition

Une `ScheduleVersion` permet de distinguer plusieurs versions successives d'une même définition.

Exemple :

```text
v1 → every day @ 06:00
v2 → every day @ 08:00
```

Cette notion peut être utile pour :

```text
audit
concurrency control
optimistic locking
historical interpretation
```

---

# 113. Revision

`Revision` peut être utilisé comme compteur technique permettant d'identifier une modification du schedule.

Exemple :

```text
revision = 7
```

Le terme peut être préféré à `version` si la version métier crée de l'ambiguïté.

---

# 114. Event Time

## Définition

`EventTime` représente le moment auquel un événement métier est considéré comme s'étant produit.

---

# 115. Processing Time

## Définition

`ProcessingTime` représente le moment auquel le système traite effectivement l'événement ou l'occurrence.

Dans le scheduling :

```text
scheduled_at
```

peut être assimilé à l'intention temporelle alors que :

```text
triggered_at
started_at
```

représentent différents temps de traitement.

---

# 116. Wall Clock

## Définition

Une `WallClock` représente l'heure civile.

Elle est utilisée pour :

```text
calendar rules
cron
business schedules
```

---

# 117. Monotonic Clock

## Définition

Une `MonotonicClock` mesure une progression temporelle qui ne revient pas en arrière.

Elle est adaptée à :

```text
timeouts
elapsed durations
backoff
lease durations
```

## Distinction

```text
Wall Clock
→ quelle heure est-il ?

Monotonic Clock
→ combien de temps s'est écoulé ?
```

---

# 118. Clock Skew

## Définition

`ClockSkew` représente la différence entre les horloges de plusieurs machines.

Exemple :

```text
Node A = 08:00:02
Node B = 07:59:59
```

Ce problème devient important pour :

```text
distributed scheduling
lease expiration
due detection
ordering
```

---

# 119. Dispatch

## Définition

`Dispatch` désigne l'action consistant à transmettre une `ExecutionRequest` vers un executor ou un runtime.

```text
SchedulingDecision
      ↓
Dispatch
      ↓
Executor
```

---

# 120. Submission

## Définition

`Submission` désigne l'acte technique par lequel une demande est acceptée par un executor.

Ainsi :

```text
dispatch attempted
```

ne garantit pas nécessairement :

```text
submission succeeded
```

---

# 121. Admission

## Définition

`Admission` représente la décision d'un runtime d'accepter ou non un travail.

Elle peut dépendre de :

```text
capacity
concurrency
rate limit
resource constraints
```

Cette notion peut rester hors du cœur PyScheduleKit si elle appartient au runtime d'exécution.

---

# 122. Rejection

## Définition

Une `Rejection` signifie qu'une demande d'exécution n'a pas été acceptée.

Elle est différente d'un échec du travail lui-même.

```text
REJECTED
→ execution did not start

FAILED
→ execution started and failed
```

---

# 123. Completion

## Définition

`Completion` représente la fin d'une execution, quel que soit son résultat.

Exemples :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 124. Success

Une execution est `SUCCESS` lorsque son contrat d'exécution est considéré comme satisfait.

Le scheduler ne doit pas inventer lui-même la sémantique métier du succès du target.

---

# 125. Failure

Une execution est `FAILED` lorsqu'elle s'est terminée sans satisfaire son contrat.

La failure peut éventuellement produire :

```text
retry
event
alert
workflow compensation
```

selon la couche responsable.

---

# 126. Terminal State

Un `TerminalState` représente un état depuis lequel aucune transition normale supplémentaire n'est attendue.

Exemples potentiels :

```text
SUCCESS
FAILED
CANCELLED
```

selon la machine à états retenue.

---

# 127. Active State

Un `ActiveState` représente un état dans lequel un objet continue de progresser.

Exemples :

```text
QUEUED
RUNNING
RETRYING
```

---

# 128. Artifact

## Définition

Un `Artifact` représente un résultat durable produit par une execution.

Exemples :

```text
file
report
model
dataset
archive
```

PyScheduleKit ne doit pas gérer leur contenu.

Il peut seulement conserver une référence.

---

# 129. ArtifactRef

`ArtifactRef` représente une référence portable vers un artifact.

Cette abstraction peut être partagée dans l'écosystème Py*Kit.

---

# 130. DatasetRef

`DatasetRef` représente une référence vers un dataset produit ou consommé.

Il appartient davantage aux contrats inter-frameworks qu'au domaine propre du scheduling.

---

# 131. PyScheduleKit vocabulary versus PyWorkflowKit vocabulary

La séparation terminologique doit rester nette.

```text
PyScheduleKit
─────────────────
Schedule
Trigger
Occurrence
Misfire
Calendar
ExecutionRequest

PyWorkflowKit
─────────────────
Workflow
Step
Dependency
Branch
DAG
WorkflowRun
StepRun
```

PyScheduleKit ne doit pas utiliser `Step` pour représenter une occurrence temporelle.

---

# 132. PyScheduleKit versus PyIngestKit

```text
PyScheduleKit
─────────────────
Occurrence
Schedule
ExecutionRequest

PyIngestKit
─────────────────
Source
Connector
Extraction
IngestionRun
Checkpoint
Destination
```

Une ingestion peut être le target d'un schedule, mais ses objets métier restent ceux de PyIngestKit.

---

# 133. PyScheduleKit versus PyTransformKit

```text
PyScheduleKit
─────────────────
Trigger
Occurrence
Schedule

PyTransformKit
─────────────────
Dataset
Transformation
Expression
Schema
Mapping
TransformationRun
```

Le scheduler ne doit pas connaître la structure des transformations.

---

# 134. Termes déconseillés comme abstractions universelles

Plusieurs termes doivent être utilisés avec prudence.

| Terme | Pourquoi il est ambigu |
|---|---|
| `Task` | Celery, asyncio, Airflow, workflow engines |
| `Job` | cron, Spark, CI/CD, Kubernetes, schedulers |
| `Run` | trop générique |
| `State` | doit préciser l'objet |
| `Retry` | peut exister à plusieurs couches |
| `Worker` | dépend fortement du runtime |
| `Queue` | ne doit pas être assimilée au scheduler |
| `Process` | ambigu entre OS et processus métier |

---

# 135. Conventions de nommage recommandées

Lorsqu'un concept est spécifique à un objet, son nom doit le refléter.

Préférer :

```text
ScheduleState
ExecutionState
OccurrenceState

ScheduleId
ExecutionId
OccurrenceId

ScheduleStore
ExecutionStore

ExecutionRetryPolicy
MisfirePolicy
ConcurrencyPolicy
```

à :

```text
State
Id
Store
Policy
```

lorsque le contexte n'est pas évident.

---

# 136. Suffixes conceptuels

Quelques conventions peuvent aider.

```text
*Id
→ identité

*Ref
→ référence externe ou légère

*Policy
→ stratégie configurable

*Rule
→ règle du domaine

*State
→ état

*Status
→ représentation d'un état observable

*Event
→ fait passé

*Command
→ intention

*Request
→ demande adressée à une frontière

*Result
→ résultat

*Store
→ persistance/infrastructure

*Repository
→ abstraction d'accès métier

*Context
→ informations transverses
```

---

# 137. Une phrase par concept central

Pour faciliter la mémorisation :

```text
Job
→ définition de ce qui peut être exécuté.

Schedule
→ association entre un travail, une règle temporelle et des politiques.

Trigger
→ mécanisme qui calcule les occurrences.

Occurrence
→ instant planifié produit par un trigger.

Due
→ occurrence arrivée à l'étape de décision.

Misfire
→ occurrence non traitée normalement à temps.

ExecutionRequest
→ demande créée par le scheduling.

Execution
→ run concret au runtime.

Attempt
→ tentative technique d'une execution.

Scheduler
→ service qui prend les décisions temporelles.

Executor
→ composant qui soumet ou exécute le travail.

Clock
→ abstraction du temps courant.

Calendar
→ règle déterminant les périodes autorisées.

Policy
→ règle configurable déterminant quoi faire dans une situation.
```

---

# 138. Chaîne conceptuelle officielle

Le modèle lexical de référence devient :

```text
                         Job / Target
                              │
                              │
                              ▼
                          Schedule
                              │
                     ┌────────┴────────┐
                     │                 │
                     ▼                 ▼
                  Trigger          Policies
                     │
                     ▼
                 Occurrence
                     │
                  becomes
                     │
                     ▼
                    Due
                     │
                     ▼
             SchedulingDecision
                     │
         ┌───────────┼────────────┐
         │           │            │
         ▼           ▼            ▼
        WAIT        SKIP       EXECUTE
                                  │
                                  ▼
                         ExecutionRequest
                                  │
                                  ▼
                               Executor
                                  │
                                  ▼
                              Execution
                                  │
                           ┌──────┴──────┐
                           │             │
                           ▼             ▼
                        Attempt       Attempt
                           │
                           ▼
                     ExecutionResult
```

---

# 139. Concepts internes et concepts de frontière

Une première séparation peut être faite.

## Cœur du domaine

```text
Schedule
Trigger
Occurrence
Clock
Calendar
SchedulingDecision
MisfirePolicy
ConcurrencyPolicy
```

## Frontière d'exécution

```text
ExecutionRequest
Executor
Execution
ExecutionResult
```

## Infrastructure

```text
Store
Repository implementation
Lease
Lock
LeaderElection
SchedulerRuntime
```

Cette classification pourra évoluer après la modélisation DDD.

---

# 140. Concepts volontairement non figés

Certains termes restent encore à arbitrer.

```text
Job vs Target

ScheduleDefinition vs Schedule

Run vs Execution

OccurrenceId

JobStore vs ScheduleStore

Pause vs Disable

Retry ownership

Occurrence status model

Executor ownership of Execution
```

Ces points devront être décidés dans les documents suivants.

---

# 141. Invariants terminologiques

Les règles suivantes doivent être considérées comme stables.

```text
Job ≠ Schedule

Schedule ≠ Trigger

Trigger ≠ Scheduler

Occurrence ≠ Execution

Execution ≠ Attempt

Recurrence ≠ Retry

Scheduler ≠ Executor

Scheduler ≠ Worker

ScheduleStatus ≠ ExecutionStatus

Misfire ≠ Failure

Skip ≠ Missed

Timeout ≠ Deadline

Duration ≠ Instant

Timezone ≠ UTC Offset
```

---

# 142. Exemple complet

Considérons :

```text
Tous les jours à 06:00,
lancer le pipeline daily_orders,
sans chevauchement.
```

Le vocabulaire correct serait :

```text
Job / Target
    daily_orders_pipeline

Schedule
    daily_orders_schedule

Trigger
    CronTrigger("0 6 * * *")

Timezone
    Europe/Paris

ConcurrencyPolicy
    FORBID

Occurrence
    2026-09-29 06:00 Europe/Paris

Due
    lorsque Clock.now() atteint l'occurrence

SchedulingDecision
    EXECUTE

ExecutionRequest
    demande de lancement de daily_orders_pipeline

Executor
    composant chargé de soumettre le workflow

Execution
    instance concrète du pipeline lancé

Attempt
    première tentative d'exécution

ExecutionResult
    SUCCESS
```

---

# 143. Exemple avec misfire

Supposons :

```text
Occurrence:
06:00

Scheduler offline:
05:55 → 06:15
```

À 06:15 :

```text
Occurrence
    ↓
MISSED
    ↓
MisfirePolicy
    ↓
RUN_NOW
    ↓
SchedulingDecision
    ↓
ExecutionRequest
```

Il ne faut pas dire :

```text
"le job a retry"
```

car aucun retry n'a nécessairement eu lieu.

Il s'agit d'une occurrence manquée traitée par une policy de misfire.

---

# 144. Exemple avec retry

Supposons maintenant :

```text
Occurrence:
06:00

Execution starts:
06:00:05

Attempt #1:
FAILED
```

Une `RetryPolicy` peut produire :

```text
Attempt #2
```

Cela reste la même :

```text
Occurrence
```

et généralement la même :

```text
Execution logique
```

selon le modèle retenu.

---

# 145. Exemple avec recurrence

```text
Occurrence #1
Monday 06:00

Occurrence #2
Tuesday 06:00

Occurrence #3
Wednesday 06:00
```

Ces occurrences ne sont pas des retries.

Elles correspondent à trois échéances prévues distinctes.

---

# 146. Exemple avec workflow

```text
PyScheduleKit

Occurrence
06:00
   │
   ▼
ExecutionRequest
target = daily_orders_pipeline
   │
   ▼
PyWorkflowKit
WorkflowRun
   │
   ├── ingest
   ├── transform
   └── publish
```

Le `WorkflowRun` appartient à PyWorkflowKit.

PyScheduleKit ne doit pas le renommer :

```text
ScheduleExecutionStep
```

ou tenter de modéliser son DAG.

---

# 147. Exemple avec ingestion directe

```text
Schedule
every 5 minutes
   │
   ▼
ExecutionRequest
target = ingest_orders
   │
   ▼
PyIngestKit
IngestionRun
```

Ici encore :

```text
Occurrence
≠
IngestionRun
```

mais les deux peuvent partager un :

```text
correlation_id
```

---

# 148. Vocabulaire de référence minimal

Le noyau terminologique indispensable pour commencer la modélisation est :

```text
Clock
Instant
Duration
Timezone
Calendar

Job
Target

Schedule
Trigger
Occurrence
NextRunTime

Due
Misfire
GracePeriod
CatchUp
Coalescing
ConcurrencyPolicy

SchedulingDecision

ExecutionRequest
Execution
Attempt
ExecutionResult

Scheduler
Executor

Store
Recovery
Reconciliation

Lease
Ownership
```

Tout autre terme devra être introduit uniquement s'il apporte une distinction réellement utile.

---

# 149. Objectif pour le code futur

Le code Python devra refléter ce vocabulaire.

À terme, on souhaite pouvoir lire quelque chose comme :

```python
schedule = Schedule(
    id=ScheduleId("daily-orders"),
    target=TargetRef("daily_orders_pipeline"),
    trigger=CronTrigger("0 6 * * *"),
    timezone=Timezone("Europe/Paris"),
    misfire_policy=RunNow(),
    concurrency_policy=ForbidOverlap(),
)
```

et comprendre immédiatement le modèle métier.

De même :

```python
occurrence = schedule.next_occurrence(...)
```

puis :

```python
decision = scheduler.evaluate(
    occurrence=occurrence,
    clock=clock,
)
```

puis éventuellement :

```python
request = decision.execution_request
```

L'API exacte n'est pas encore figée.

Le vocabulaire, en revanche, doit précéder l'API.

---

# 150. Critères de qualité du vocabulaire

Un terme est considéré comme correctement défini s'il est possible de répondre clairement à :

```text
Quelle question représente-t-il ?

Quelle responsabilité porte-t-il ?

Avec quels autres concepts peut-il être confondu ?

Est-il temporel, métier, runtime ou infrastructure ?

Possède-t-il une identité ?

Possède-t-il un cycle de vie ?

Est-il configurable ?

Est-il persistant ?

À quel bounded context appartient-il ?
```

Ces questions serviront de base au prochain document consacré aux objets métier.

---

# Conclusion

Le vocabulaire de PyScheduleKit doit permettre de parler précisément du scheduling sans importer inconsciemment les significations de cron, Celery, Airflow, Kubernetes ou d'autres outils.

La chaîne fondamentale à retenir est :

```text
Target
  ↓
Schedule
  ↓
Trigger
  ↓
Occurrence
  ↓
SchedulingDecision
  ↓
ExecutionRequest
  ↓
Execution
  ↓
Attempt
  ↓
ExecutionResult
```

Les distinctions les plus importantes restent :

```text
Schedule ≠ Job

Trigger ≠ Schedule

Occurrence ≠ Execution

Execution ≠ Attempt

Recurrence ≠ Retry

Misfire ≠ Failure

Scheduler ≠ Executor

Scheduler ≠ Workflow Engine

Scheduler ≠ Queue

Time reached ≠ execution permitted
```

Ce langage ubiquitaire constitue désormais la base sur laquelle pourront être définis les véritables objets du domaine.

---

# Suite documentaire

Le prochain document est :

```text
04_SCHEDULING_BUSINESS_OBJECTS.md
```

Il devra reprendre chacun des concepts métier principaux et analyser :

```text
son rôle ;
son identité ;
ses données ;
ses comportements ;
ses invariants ;
son cycle de vie ;
ses relations ;
ses responsabilités ;
ses anti-responsabilités ;
ses frontières ;
sa représentation conceptuelle en Python.
```

Ce document commencera donc réellement la **modélisation métier objet par objet** du domaine du scheduling.