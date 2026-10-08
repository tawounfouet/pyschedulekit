# Scheduling — Objets métier du domaine

**Document :** `04_SCHEDULING_BUSINESS_OBJECTS.md`  
**Projet :** PyScheduleKit  
**Statut :** Document de modélisation métier  
**Nature :** Business Objects / Domain Objects  
**Prérequis :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
- `01_SCHEDULING_DOMAIN_INTRODUCTION.md`
- `02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md`
- `03_SCHEDULING_DOMAIN_VOCABULARY.md`

---

# 1. Objectif

Le vocabulaire du domaine a permis d'identifier des concepts comme :

```text
Schedule
Trigger
Occurrence
ExecutionRequest
Execution
Clock
Calendar
Policy
```

Mais connaître les mots ne suffit pas.

Il faut maintenant répondre à une question plus profonde :

> **Quels sont les véritables objets métier manipulés par un système de scheduling ?**

Pour chacun d'eux, il faut comprendre :

```text
Pourquoi existe-t-il ?

Quelle question représente-t-il ?

Quelle donnée possède-t-il ?

Quel comportement porte-t-il ?

Quelle identité possède-t-il ?

Quels invariants doit-il protéger ?

Avec quels autres objets interagit-il ?

Que ne doit-il surtout pas faire ?
```

L'objectif de ce document est donc de construire une première cartographie explicite des objets métier avant de décider lesquels seront :

```text
Entities
Value Objects
Aggregates
Domain Services
Policies
Ports
Infrastructure Objects
```

Cette classification DDD précise sera réalisée dans le document suivant.

---

# 2. Principe fondamental

Un objet métier ne doit pas exister simplement parce qu'il est pratique d'avoir une classe Python.

Il doit exister parce qu'il représente une distinction utile dans le domaine.

Ainsi :

```text
class Schedule:
    ...
```

n'est pertinent que si `Schedule` représente réellement quelque chose de distinct de :

```text
Job
Trigger
Occurrence
Execution
```

La modélisation doit donc partir du domaine :

```text
DOMAIN CONCEPT
      ↓
BUSINESS RESPONSIBILITY
      ↓
OBJECT
      ↓
PYTHON REPRESENTATION
```

et non l'inverse.

---

# 3. Carte générale des objets

Une première cartographie peut être organisée en six familles.

```text
Scheduling Domain
│
├── 1. Temporal Objects
│   ├── Instant
│   ├── Duration
│   ├── Timezone
│   ├── TimeWindow
│   ├── Clock
│   └── Calendar
│
├── 2. Planning Objects
│   ├── Target
│   ├── Job
│   ├── Schedule
│   ├── Trigger
│   ├── Recurrence
│   └── Occurrence
│
├── 3. Decision Objects
│   ├── SchedulingDecision
│   ├── Eligibility
│   ├── MisfireDecision
│   └── ConcurrencyDecision
│
├── 4. Policy Objects
│   ├── MisfirePolicy
│   ├── ConcurrencyPolicy
│   ├── RetryPolicy
│   ├── TimeoutPolicy
│   └── JitterPolicy
│
├── 5. Execution Boundary
│   ├── ExecutionRequest
│   ├── Execution
│   ├── Attempt
│   └── ExecutionResult
│
└── 6. Runtime / Coordination
    ├── Scheduler
    ├── SchedulerEngine
    ├── Executor
    ├── ScheduleStore
    └── Lease
```

Ces objets n'ont pas tous le même statut.

Certains seront probablement des objets métier purs.

D'autres sont davantage des services ou des abstractions d'infrastructure.

---

# 4. Première grande séparation

Le domaine peut être lu selon cette chaîne :

```text
        DEFINITION
            │
            ▼
         Schedule
            │
            ▼
         Trigger
            │
            ▼
        Occurrence
            │
            ▼
         Decision
            │
            ▼
    ExecutionRequest
            │
            ▼
        Execution
```

Cela permet de distinguer :

```text
ce qui est défini
ce qui est calculé
ce qui est décidé
ce qui est exécuté
```

Ces quatre dimensions ne doivent pas être fusionnées.

---

# 5. Objet métier : Target

## 5.1 Définition

Un `Target` représente **ce qui devra être déclenché** lorsqu'une occurrence produit une décision d'exécution.

Exemples :

```text
fonction Python
workflow
commande
endpoint HTTP
message
ingestion
transformation
```

Le scheduler ne doit pas nécessairement connaître la nature interne du target.

---

## 5.2 Question métier

> Quel travail logique doit être demandé lorsque le schedule devient exigible ?

---

## 5.3 Données potentielles

```text
target_ref
target_type
metadata
```

Exemple :

```text
TargetRef("daily_orders_pipeline")
```

---

## 5.4 Responsabilités

Le `Target` peut :

```text
identifier une destination d'exécution
porter une référence logique
indiquer éventuellement son type
```

---

## 5.5 Anti-responsabilités

Le `Target` ne doit pas :

```text
calculer une occurrence
gérer les retries
connaître les horaires
exécuter lui-même le travail
```

---

# 6. Objet métier : Job

## 6.1 Définition

Un `Job` représente une définition logique nommée de travail.

Il répond principalement à :

> **Quoi exécuter ?**

Exemple :

```text
Job
────────────────
id = daily_report
target = generate_report
arguments = ...
metadata = ...
```

---

## 6.2 Pourquoi avoir Job en plus de Target ?

Un `Target` peut être une simple référence.

Un `Job` peut enrichir cette référence avec :

```text
identité
nom
arguments
métadonnées
configuration logique
```

On peut donc imaginer :

```text
Job
  └── TargetRef
```

---

## 6.3 Responsabilités

Un job peut :

```text
identifier une unité logique de travail
porter ses paramètres
définir son target
porter des métadonnées
```

---

## 6.4 Anti-responsabilités

Un job ne doit pas :

```text
déterminer quand il s'exécute
calculer next_run_time
gérer les calendriers
être une occurrence
```

---

# 7. Objet métier : Schedule

## 7.1 Définition

Le `Schedule` est l'objet qui représente la planification durable d'un travail.

Il associe :

```text
quoi
+
quand
+
selon quelles politiques
```

Conceptuellement :

```text
Schedule
│
├── identity
├── job / target
├── trigger
├── timezone
├── calendar
├── policies
└── lifecycle state
```

---

## 7.2 Question métier

> Selon quelle règle temporelle et quelles contraintes ce travail doit-il devenir exigible ?

---

## 7.3 Données potentielles

```text
schedule_id
name
job_ref
trigger
timezone
calendar
misfire_policy
concurrency_policy
start_at
end_at
state
metadata
revision
```

---

## 7.4 Responsabilités

Le schedule peut être responsable de :

```text
porter la configuration temporelle
porter les politiques
porter son état de cycle de vie
définir les bornes temporelles
associer un target à un trigger
```

---

## 7.5 Invariants potentiels

```text
start_at <= end_at

un schedule annulé ne produit plus de nouvelles occurrences

un schedule doit avoir un trigger

un schedule doit référencer un target

une timezone doit être explicite pour certaines règles calendaires
```

---

## 7.6 Anti-responsabilités

Le schedule ne doit pas :

```text
exécuter directement son target
gérer un pool de threads
connaître la topologie d'un workflow
réaliser une ingestion
faire une transformation
```

---

# 8. Schedule comme candidat Aggregate Root

À ce stade, `Schedule` est un bon candidat pour devenir un agrégat principal.

Pourquoi ?

Parce qu'il concentre :

```text
identité
configuration
politiques
cycle de vie
règles de modification
```

Cependant, cette hypothèse reste à confirmer.

Notamment :

```text
Occurrence
Execution
```

ne doivent probablement pas être embarquées naïvement dans le même agrégat.

---

# 9. Objet métier : Trigger

## 9.1 Définition

Un `Trigger` est un objet chargé de calculer des occurrences temporelles.

Sa responsabilité centrale est :

```text
Trigger + temporal context
        ↓
Occurrence
```

---

## 9.2 Question métier

> Quelle est la prochaine échéance valide ?

---

## 9.3 Interface conceptuelle

```text
next(after)
```

ou :

```text
next_occurrence(context)
```

---

## 9.4 Responsabilités

Un trigger peut :

```text
interpréter une règle temporelle
calculer une prochaine occurrence
déterminer qu'il n'y aura plus d'occurrence
```

---

## 9.5 Anti-responsabilités

Il ne doit pas :

```text
lancer un job
persister des executions
appliquer une policy de concurrence
gérer des workers
```

---

# 10. Objet métier : DateTrigger

## Définition

Produit une occurrence unique.

Exemple :

```text
2026-10-01 09:00
```

---

## Responsabilité

Répondre :

```text
Cette occurrence a-t-elle déjà été consommée ?

Si non :
    retourner cette date

Sinon :
    None
```

---

# 11. Objet métier : IntervalTrigger

## Définition

Produit des occurrences selon un intervalle.

Exemple :

```text
every 5 minutes
```

---

## Question métier importante

L'intervalle peut suivre deux modèles.

### Fixed Rate

```text
10:00
10:05
10:10
10:15
```

indépendamment de la durée des runs.

### Fixed Delay

```text
run end
   +
5 minutes
   =
next run
```

Ces deux modèles ne doivent pas être confondus.

---

# 12. Objet métier : CronTrigger

## Définition

Produit des occurrences selon une règle calendaire.

Exemple :

```text
0 6 * * *
```

---

## Responsabilité

Le trigger doit interpréter :

```text
minute
hour
day
month
weekday
timezone
```

pour produire une prochaine occurrence.

---

## Anti-responsabilité

`CronTrigger` ne doit pas gérer :

```text
catch-up
retry
execution
overlap
```

Ces notions appartiennent à d'autres objets.

---

# 13. Objet métier : CalendarTrigger

## Définition

Un `CalendarTrigger` représente une récurrence dépendant d'un calendrier métier.

Exemple :

```text
first working day of each month
```

Il peut utiliser un :

```text
BusinessCalendar
```

pour déterminer la prochaine date valide.

---

# 14. Objet métier : Recurrence

## Définition

Une `Recurrence` représente conceptuellement une suite d'occurrences.

```text
R = {t1, t2, t3, ...}
```

Elle n'est pas nécessairement matérialisée entièrement.

---

## Question métier

> Quelle structure temporelle relie plusieurs occurrences ?

---

## Remarque

Il est possible que `Recurrence` reste un concept du modèle sans devenir une classe publique.

Elle peut être incarnée directement par certains triggers.

---

# 15. Objet métier : Occurrence

## 15.1 Définition

Une `Occurrence` représente une échéance concrète produite par une règle temporelle.

Exemple :

```text
Schedule:
daily_orders

Occurrence:
2026-09-29 06:00 Europe/Paris
```

---

## 15.2 Question métier

> Quel instant précis de cette planification sommes-nous en train de considérer ?

---

## 15.3 Données potentielles

```text
occurrence_id
schedule_id
scheduled_at
sequence
trigger_metadata
```

---

## 15.4 Responsabilités

Une occurrence peut porter :

```text
l'instant planifié
son schedule source
son identité
des informations de calcul
```

---

## 15.5 Anti-responsabilités

Une occurrence ne doit pas :

```text
exécuter le travail
décider seule si elle est en misfire
calculer la prochaine occurrence
gérer les retries
```

---

# 16. Identité d'une occurrence

Plusieurs stratégies sont possibles.

## Identité naturelle

```text
(schedule_id, scheduled_at)
```

## Identité artificielle

```text
occurrence_id
```

Exemple :

```text
occ_01J...
```

L'identité explicite facilite :

```text
audit
deduplication
distributed scheduling
replay
correlation
```

---

# 17. Occurrence versus Execution

C'est l'une des distinctions les plus importantes.

```text
Occurrence
= ce qui était prévu

Execution
= ce qui s'est réellement exécuté
```

Exemple :

```text
Occurrence 08:00
     │
     ├── skipped
     │
     └── aucune Execution
```

ou :

```text
Occurrence 08:00
     │
     ▼
Execution
started_at = 08:03
```

---

# 18. Objet métier : NextRunTime

## Définition

`NextRunTime` représente la prochaine échéance actuellement connue.

Exemple :

```text
2026-09-30T06:00:00+02:00
```

---

## Question ouverte

Est-ce :

```text
une simple valeur dérivée
```

ou :

```text
un état persistant du Schedule
```

?

Cette décision aura un impact important sur la persistance.

---

# 19. Objet métier : Clock

## Définition

Un `Clock` fournit le temps courant au domaine.

```text
Clock.now()
```

---

## Pourquoi en faire un objet explicite ?

Parce que :

```text
datetime.now()
```

introduit une dépendance cachée.

Avec un `Clock` :

```text
SchedulerEngine
      │
      ▼
    Clock
```

on peut contrôler le temps.

---

## Exemples

```text
SystemClock
FixedClock
MutableClock
```

---

# 20. Objet métier : Calendar

## Définition

Un `Calendar` détermine si une date ou un instant est valide selon certaines règles.

Exemple :

```text
Monday → allowed
Saturday → forbidden
Christmas → forbidden
```

---

## Interface conceptuelle

```text
calendar.allows(date)
```

ou :

```text
calendar.next_valid_after(date)
```

---

## Responsabilités

```text
jours ouvrés
jours fériés
heures de fonctionnement
blackout periods
exceptions
```

---

# 21. Objet métier : BusinessCalendar

## Définition

Une spécialisation de `Calendar` porte des règles métier.

Exemple :

```text
FrenchBusinessCalendar
```

avec :

```text
weekends
public holidays
company closures
```

Il peut être utilisé par :

```text
CalendarTrigger
```

ou par des règles de validation.

---

# 22. Objet métier : TimeWindow

## Définition

Une `TimeWindow` représente un intervalle temporel autorisé.

Exemple :

```text
08:00 → 18:00
```

Elle peut servir pour :

```text
execution window
maintenance window
allowed window
blackout window
```

---

# 23. Objet métier : SchedulingDecision

## 23.1 Définition

Une `SchedulingDecision` représente la décision produite par le moteur après évaluation d'une occurrence.

Exemples :

```text
WAIT
EXECUTE
SKIP
COALESCE
CATCH_UP
```

---

## 23.2 Pourquoi matérialiser une décision ?

Sans objet explicite :

```text
if ...
    executor.submit(...)
```

le moteur mélange :

```text
raisonnement
+
effet
```

Avec un objet décision :

```text
evaluate(...)
    ↓
SchedulingDecision
    ↓
apply(...)
```

on sépare les deux.

---

## 23.3 Données potentielles

```text
decision_type
occurrence
reason
policy_source
created_at
execution_requests
```

---

# 24. Objet métier : Eligibility

## Définition

`Eligibility` exprime si une occurrence peut réellement produire une exécution.

Une occurrence peut être :

```text
DUE
```

sans être :

```text
ELIGIBLE
```

Exemple :

```text
Due
+
Schedule PAUSED
=
Not Eligible
```

ou :

```text
Due
+
Max concurrency reached
=
Not Eligible
```

---

# 25. Objet métier : Misfire

## Définition

Un `Misfire` représente la situation dans laquelle une occurrence n'a pas été traitée selon la fenêtre normale attendue.

Exemple :

```text
scheduled_at = 08:00
now = 08:17
grace_period = 5 min
```

L'occurrence peut être qualifiée de misfire.

---

# 26. Objet métier : MisfirePolicy

## Définition

La `MisfirePolicy` définit comment traiter un misfire.

Exemples :

```text
SkipMisfire
RunNow
CatchUp
Coalesce
Reschedule
```

---

## Interface conceptuelle

```text
MisfirePolicy.decide(context)
```

---

## Important

Une policy ne doit pas nécessairement modifier directement le système.

Elle peut produire une décision.

```text
Policy
   ↓
Decision
```

---

# 27. Objet métier : GracePeriod

## Définition

Une `GracePeriod` représente la tolérance accordée après `scheduled_at`.

Exemple :

```text
5 minutes
```

---

## Calcul

```text
deadline =
scheduled_at + grace_period
```

---

## Nature probable

`GracePeriod` est probablement davantage un Value Object qu'une Entity.

---

# 28. Objet métier : Deadline

## Définition

Une `Deadline` représente l'instant au-delà duquel une occurrence ou exécution n'est plus acceptable.

```text
scheduled_at
     │
     ├──── validity ────┐
     │                  │
     ▼                  ▼
   08:00              08:05
                    deadline
```

---

# 29. Objet métier : ConcurrencyKey

## Définition

Avant de décider une politique de concurrence, il faut savoir **quelles exécutions sont considérées comme concurrentes entre elles**.

Exemple :

```text
schedule_id
job_id
customer_id
resource_id
```

On peut introduire :

```text
ConcurrencyKey
```

Exemple :

```text
ConcurrencyKey("daily-orders")
```

---

# 30. Pourquoi ConcurrencyKey est utile

Sans cela, une règle comme :

```text
max_instances = 1
```

reste ambiguë.

Une seule instance :

```text
du schedule ?
du job ?
du target ?
du tenant ?
```

Le scope doit être explicite.

---

# 31. Objet métier : ConcurrencyPolicy

## Définition

Une `ConcurrencyPolicy` définit le comportement lorsqu'une occurrence devient eligible mais qu'une exécution incompatible est déjà active.

Exemples :

```text
AllowOverlap
ForbidOverlap
QueueOverlap
ReplaceActive
CoalesceOverlap
```

---

# 32. Objet métier : ConcurrencyDecision

Une policy peut produire :

```text
ALLOW
REJECT
QUEUE
REPLACE
COALESCE
```

sous la forme d'un objet décision.

Cela évite de mélanger :

```text
policy
```

et :

```text
runtime action
```

---

# 33. Objet métier : CatchUpPolicy

Il peut être pertinent de distinguer :

```text
MisfirePolicy
```

de :

```text
CatchUpPolicy
```

si le domaine devient plus précis.

Exemple :

```text
max_catchup_occurrences = 10
```

ou :

```text
catchup_window = 24h
```

Ce point reste ouvert.

---

# 34. Objet métier : CoalescingPolicy

Même logique.

Un coalescing peut être plus riche que :

```text
yes/no
```

Exemples :

```text
latest only
earliest only
aggregate all metadata
bounded window
```

Il faudra déterminer si un objet spécifique est justifié.

---

# 35. Objet métier : Jitter

## Définition

Le `Jitter` représente une variation contrôlée ajoutée à une échéance.

Exemple :

```text
planned:
00:00:00

actual eligibility:
00:00:17
```

avec :

```text
jitter <= 30 s
```

---

## Question métier

Le jitter doit-il modifier :

```text
scheduled_at
```

ou seulement :

```text
dispatch_at
```

?

Il est préférable de conserver :

```text
scheduled_at
```

comme intention originale.

---

# 36. Objet métier : ExecutionRequest

## 36.1 Définition

Une `ExecutionRequest` représente une demande de lancement produite par le scheduling.

Elle matérialise le passage :

```text
Scheduling Domain
      ↓
Execution Runtime
```

---

## 36.2 Données potentielles

```text
request_id
schedule_id
occurrence_id
target
scheduled_at
created_at
context
metadata
```

---

## 36.3 Responsabilités

```text
identifier la demande
porter le target
porter le contexte
relier la demande à l'occurrence
```

---

## 36.4 Anti-responsabilités

Elle ne doit pas :

```text
exécuter le target
calculer une occurrence
gérer le worker
```

---

# 37. Pourquoi ExecutionRequest est important

Sans cet objet :

```text
Occurrence
   ↓
Executor
```

on fusionne décision et exécution.

Avec lui :

```text
Occurrence
   ↓
Decision
   ↓
ExecutionRequest
   ↓
Executor
```

on dispose d'une frontière claire.

---

# 38. Objet métier : Execution

## 38.1 Définition

Une `Execution` représente une instance concrète de travail prise en charge par le runtime.

---

## 38.2 Données potentielles

```text
execution_id
request_id
status
created_at
queued_at
started_at
finished_at
result
error
```

---

## 38.3 Cycle de vie potentiel

```text
CREATED
   ↓
QUEUED
   ↓
RUNNING
   ↓
SUCCESS
```

ou :

```text
RUNNING
   ↓
FAILED
```

---

# 39. Execution comme objet du scheduling ?

Question importante :

> L'Execution appartient-elle réellement au bounded context du scheduling ?

Deux possibilités.

## Modèle A

PyScheduleKit possède :

```text
Execution
```

et suit le runtime.

## Modèle B

PyScheduleKit s'arrête à :

```text
ExecutionRequest
```

et ne reçoit que :

```text
ExecutionStatus
ExecutionEvent
```

du runtime externe.

Le second modèle crée une frontière plus nette.

Cette décision devra être approfondie.

---

# 40. Objet métier : Attempt

## Définition

Un `Attempt` représente une tentative technique d'une execution.

```text
Execution
   │
   ├── Attempt #1
   ├── Attempt #2
   └── Attempt #3
```

---

## Distinction fondamentale

```text
Occurrence
≠
Execution
≠
Attempt
```

Une occurrence est temporelle.

Une execution est logique.

Un attempt est technique.

---

# 41. Objet métier : RetryPolicy

## Définition

Une `RetryPolicy` définit les règles de nouvelles tentatives.

Exemple :

```text
max_attempts = 3
backoff = exponential
retry_on = NetworkError
```

---

## Problème de frontière

PyScheduleKit doit probablement gérer uniquement les retries de :

```text
submission
dispatch
scheduler-owned execution
```

et non tous les retries du travail métier déclenché.

---

# 42. Objet métier : Backoff

## Définition

Le `Backoff` détermine le délai entre plusieurs attempts.

Exemples :

```text
constant
linear
exponential
```

Exemple :

```text
5s
10s
20s
40s
```

---

# 43. Objet métier : ExecutionResult

## Définition

Un `ExecutionResult` représente l'issue d'une execution.

Exemple :

```text
ExecutionResult(
    status=SUCCESS,
    finished_at=...,
    artifact_refs=[...]
)
```

---

## Anti-responsabilité

Il ne doit pas nécessairement contenir :

```text
un dataset de plusieurs Go
un fichier complet
un objet métier massif
```

Il peut préférer des références.

---

# 44. Objet métier : ArtifactRef

Dans l'écosystème Py*Kit, une execution peut produire :

```text
ArtifactRef
DatasetRef
```

Ces objets peuvent permettre une interopérabilité sans charger PyScheduleKit de la gestion des artifacts.

---

# 45. Objet métier : ExecutionContext

## Définition

Un `ExecutionContext` transporte les informations transverses liées au déclenchement.

Exemple :

```text
schedule_id
occurrence_id
execution_id
correlation_id
trace_id
scheduled_at
triggered_at
metadata
```

---

# 46. Pourquoi ExecutionContext est important

Il permet de propager :

```text
traçabilité
corrélation
observabilité
lineage
```

vers :

```text
PyWorkflowKit
PyIngestKit
PyTransformKit
```

---

# 47. Exemple de propagation

```text
PyScheduleKit
Occurrence #42
      │
      │ correlation_id = ABC
      ▼
ExecutionRequest
      │
      ▼
PyWorkflowKit
WorkflowRun
      │
      ├── PyIngestKit
      └── PyTransformKit
```

Tous peuvent partager :

```text
correlation_id = ABC
```

sans partager leurs modèles métier internes.

---

# 48. Objet métier : ScheduleState

Le schedule possède son propre état.

Exemple :

```text
ACTIVE
PAUSED
CANCELLED
COMPLETED
```

---

## Règles potentielles

```text
ACTIVE
→ peut produire des occurrences

PAUSED
→ ne produit pas normalement de nouvelles ExecutionRequests

CANCELLED
→ terminal

COMPLETED
→ trigger épuisé
```

---

# 49. Objet métier : OccurrenceState

Si l'occurrence devient persistante, elle peut avoir un état.

Exemples :

```text
PLANNED
DUE
MATERIALIZED
MISSED
SKIPPED
COALESCED
```

Il faudra cependant éviter de créer trop tôt une machine à états inutilement complexe.

---

# 50. Objet métier : ExecutionState

L'execution a son propre lifecycle.

Exemples :

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

---

# 51. Trois machines à états différentes

```text
Schedule
────────
ACTIVE
PAUSED
CANCELLED

Occurrence
──────────
PLANNED
DUE
SKIPPED
MATERIALIZED

Execution
─────────
QUEUED
RUNNING
SUCCESS
FAILED
```

Ces états ne doivent jamais être fusionnés dans un enum générique :

```text
Status
```

sans préciser l'objet.

---

# 52. Objet métier : Scheduler

## Définition

Le `Scheduler` est le service applicatif qui coordonne les objets du domaine.

Conceptuellement :

```text
Clock
  │
  ▼
Scheduler
  │
  ├── ScheduleStore
  ├── Trigger
  ├── Policies
  └── Executor
```

---

## Responsabilités

```text
trouver les schedules pertinents
évaluer les occurrences
appliquer les policies
produire des ExecutionRequests
persister l'état
```

---

## Anti-responsabilités

```text
implémenter un DAG
faire de l'ingestion
gérer un DataFrame
devenir un message broker
```

---

# 53. Objet métier : SchedulerEngine

Il peut être utile de séparer :

```text
SchedulerEngine
```

de :

```text
SchedulerRuntime
```

Le premier porte :

```text
la logique
les décisions
les transitions
```

Le second porte :

```text
la boucle
le sleep
les signaux
startup/shutdown
threads
async runtime
```

---

# 54. SchedulerEngine comme fonction conceptuelle

On peut viser quelque chose comme :

```text
SchedulerState
+
CurrentTime
+
Schedules
+
ExecutionState
      ↓
SchedulerDecisionSet
```

Cela permet une meilleure testabilité.

---

# 55. Objet technique : Executor

## Définition

L'`Executor` reçoit une `ExecutionRequest`.

Exemples :

```text
InlineExecutor
ThreadExecutor
ProcessExecutor
AsyncExecutor
QueueExecutor
WorkflowExecutor
```

---

## Question principale

> Comment cette demande est-elle soumise à un mécanisme d'exécution ?

---

# 56. Executor comme port

Il est probable que `Executor` soit davantage :

```text
un Port
```

qu'un véritable objet métier.

Par exemple :

```text
class Executor(Protocol):
    submit(request) -> SubmissionResult
```

L'implémentation appartient alors à l'infrastructure.

---

# 57. Objet technique : ScheduleStore

`ScheduleStore` permet la persistance des schedules.

Il peut exposer :

```text
save
get
remove
list_due_candidates
```

Mais attention :

```text
find_due()
```

peut contenir de la logique métier.

Il faudra décider si :

```text
Store
```

retourne seulement des candidats ou décide réellement du caractère `due`.

---

# 58. Objet technique : ExecutionStore

Peut conserver :

```text
executions
status
history
attempts
```

Il permet :

```text
audit
recovery
deduplication
observability
```

---

# 59. Objet métier / infrastructure : Lease

## Définition

Une `Lease` représente une possession temporaire.

Exemple :

```text
Lease
──────────────
resource = Schedule A
owner = Scheduler-2
expires_at = 08:00:30
```

---

## Pourquoi c'est important

Dans un système distribué :

```text
Scheduler A
Scheduler B
```

peuvent observer la même occurrence.

La lease peut permettre de déterminer :

```text
who owns the decision
```

---

# 60. Objet métier : SchedulingKey

Une clé de scheduling peut identifier un espace de coordination.

Exemple :

```text
SchedulingKey(schedule_id, occurrence_id)
```

Elle peut servir pour :

```text
deduplication
lease
idempotence
```

Ce concept reste optionnel.

---

# 61. Objet métier : DeduplicationKey

Pour éviter plusieurs demandes identiques :

```text
DeduplicationKey(
    schedule_id,
    occurrence_time
)
```

peut permettre de reconnaître la même occurrence.

Cette distinction devient importante avec :

```text
multi-node scheduling
retries
network failures
```

---

# 62. Objet métier : ScheduleRevision

Une modification du schedule peut créer une nouvelle révision.

```text
revision 1
06:00

revision 2
08:00
```

Cela permet de savoir sous quelle définition une occurrence a été produite.

---

# 63. Pourquoi la révision est intéressante

Supposons :

```text
Occurrence
scheduled_at = 06:00
```

puis le schedule est modifié à :

```text
08:00
```

avant que l'occurrence soit exécutée.

Il faut pouvoir déterminer :

```text
quelle version du schedule
a produit cette occurrence ?
```

Une révision peut répondre à cette question.

---

# 64. Objet métier : PauseCommand

Les changements de lifecycle peuvent être représentés comme des commandes :

```text
PauseSchedule
ResumeSchedule
CancelSchedule
Reschedule
```

Ces commandes expriment une intention.

---

# 65. Objet métier : ScheduleEvent

Les changements peuvent produire des événements :

```text
ScheduleCreated
SchedulePaused
ScheduleResumed
ScheduleCancelled
ScheduleRescheduled
```

Ces événements permettent :

```text
audit
observability
integration
```

---

# 66. Objet métier : OccurrenceEvent

Exemples :

```text
OccurrenceCalculated
OccurrenceDue
OccurrenceMissed
OccurrenceSkipped
OccurrenceCoalesced
OccurrenceMaterialized
```

---

# 67. Objet métier : ExecutionEvent

Exemples :

```text
ExecutionRequested
ExecutionAccepted
ExecutionStarted
ExecutionSucceeded
ExecutionFailed
ExecutionCancelled
```

Ces événements représentent ce qui s'est produit.

---

# 68. Relations principales

Une première relation générale peut être exprimée ainsi :

```text
Job
 │
 │ 1
 │
 │ N
 ▼
Schedule
 │
 │ owns/configures
 ▼
Trigger
 │
 │ produces
 ▼
Occurrence
 │
 │ evaluated by
 ▼
Scheduler
 │
 │ produces
 ▼
ExecutionRequest
 │
 │ submitted through
 ▼
Executor
 │
 │ results in
 ▼
Execution
 │
 ├── Attempt
 ├── Attempt
 └── Attempt
```

---

# 69. Job et Schedule

Un même `Job` peut avoir plusieurs schedules.

```text
                   Job
            generate_report
                  │
          ┌───────┴────────┐
          ▼                ▼
Schedule Paris      Schedule New York
08:00 Europe/Paris  08:00 America/New_York
```

La définition logique du travail reste la même.

---

# 70. Schedule et Trigger

Un schedule possède normalement une règle temporelle principale.

```text
Schedule
   │
   └── Trigger
```

Cette relation semble naturellement :

```text
1 → 1
```

mais un trigger composite pourrait permettre :

```text
OR
AND
EXCLUDE
```

plus tard.

---

# 71. Trigger et Occurrence

```text
Trigger
   │
   ├── Occurrence 1
   ├── Occurrence 2
   ├── Occurrence 3
   └── ...
```

Un trigger peut produire :

```text
0..N
```

occurrences.

---

# 72. Occurrence et ExecutionRequest

Une occurrence peut produire :

```text
0
```

demande si elle est ignorée.

Elle peut produire :

```text
1
```

demande dans le cas nominal.

Dans certains modèles de catch-up ou de fan-out, il faudra vérifier si :

```text
1 occurrence → N requests
```

est autorisé.

Par défaut, il serait préférable de conserver :

```text
Occurrence
    ↓
0..1 ExecutionRequest
```

---

# 73. ExecutionRequest et Execution

Une demande peut :

```text
être rejetée
être mise en queue
être exécutée
```

Donc :

```text
ExecutionRequest
   ↓
0..1 Execution
```

dans un modèle simple.

Mais en présence de retries techniques, une même request peut produire plusieurs attempts.

---

# 74. Execution et Attempt

```text
Execution
   │
   ├── Attempt #1
   ├── Attempt #2
   └── Attempt #3
```

Relation naturelle :

```text
1 → N
```

---

# 75. Exemple métier complet

Besoin :

> Tous les jours à 06:00, lancer `daily_orders_pipeline`, sans chevauchement et avec cinq minutes de tolérance.

On obtient :

```text
Job
daily_orders_pipeline
      │
      ▼
Schedule
daily_orders_schedule
      │
      ├── CronTrigger("0 6 * * *")
      ├── Timezone("Europe/Paris")
      ├── GracePeriod(5 min)
      └── ForbidOverlap()
```

Puis :

```text
2026-09-29 06:00
        │
        ▼
Occurrence
        │
        ▼
Eligibility Evaluation
        │
        ▼
SchedulingDecision(EXECUTE)
        │
        ▼
ExecutionRequest
        │
        ▼
WorkflowExecutor
        │
        ▼
PyWorkflowKit
        │
        ▼
WorkflowRun
```

---

# 76. Exemple avec overlap

Supposons :

```text
Schedule
every 5 min
```

et :

```text
Execution #1
RUNNING
```

à l'arrivée de l'occurrence suivante.

Le système construit :

```text
Occurrence
   │
   ▼
ConcurrencyContext
   │
   ▼
ForbidOverlap
   │
   ▼
ConcurrencyDecision
   │
   ▼
SKIP / REJECT
```

L'occurrence et la policy restent distinctes.

---

# 77. Exemple avec misfire

```text
Occurrence
scheduled_at = 08:00

now = 08:15

grace_period = 5m
```

Le moteur peut produire :

```text
MisfireContext
      │
      ▼
MisfirePolicy
      │
      ▼
SchedulingDecision(SKIP)
```

ou :

```text
SchedulingDecision(EXECUTE_NOW)
```

selon la configuration.

---

# 78. Exemple avec catch-up

Supposons :

```text
08:00
09:00
10:00
```

toutes manquées.

Un `CatchUpPlanner` pourrait produire :

```text
Occurrence 08:00
Occurrence 09:00
Occurrence 10:00
```

à traiter.

Il faut éviter de faire du `Trigger` lui-même un composant qui exécute le catch-up.

---

# 79. Exemple avec coalescing

```text
Occurrence #1
Occurrence #2
Occurrence #3
```

peuvent produire :

```text
CoalescedOccurrenceGroup
```

ou directement une :

```text
SchedulingDecision
```

référençant plusieurs occurrences.

Cette modélisation reste à arbitrer.

---

# 80. Objet métier possible : OccurrenceGroup

Pour représenter le coalescing, un objet :

```text
OccurrenceGroup
```

pourrait contenir :

```text
occurrences
first_scheduled_at
last_scheduled_at
count
```

Mais il ne doit être introduit que si l'implémentation en a réellement besoin.

---

# 81. Objet métier possible : ScheduleEvaluationContext

Pour évaluer une occurrence, plusieurs informations sont nécessaires :

```text
now
schedule
occurrence
active executions
calendar
policies
```

On pourrait regrouper cela dans :

```text
ScheduleEvaluationContext
```

afin d'éviter des signatures énormes.

---

# 82. Objet métier possible : SchedulingOutcome

Une évaluation peut produire plus qu'une simple enum.

Exemple :

```text
SchedulingOutcome
│
├── decision
├── reasons
├── requests
├── next_occurrence
└── events
```

Cela rendrait le moteur plus explicable.

---

# 83. Explicabilité des décisions

Une bonne modélisation devrait permettre :

```text
Why was this occurrence skipped?
```

Réponse :

```text
Schedule daily-orders
Occurrence 08:00
Policy ForbidOverlap
Active Execution #123
Decision SKIP
```

Cela implique que la décision conserve son contexte ou sa raison.

---

# 84. Objet métier : DecisionReason

Exemples :

```text
MISFIRE_EXPIRED
OVERLAP_FORBIDDEN
SCHEDULE_PAUSED
OUTSIDE_CALENDAR
DEADLINE_EXCEEDED
ELIGIBLE
```

Cela peut être préférable à du logging textuel arbitraire.

---

# 85. Business objects versus DTOs

Les objets métier ne doivent pas être confondus avec des DTO.

Exemple DTO :

```text
CreateScheduleRequest
```

peut contenir :

```text
name
cron
timezone
```

mais il ne constitue pas nécessairement le vrai :

```text
Schedule
```

du domaine.

---

# 86. Business objects versus persistence models

Une table SQL comme :

```text
schedules
```

ne doit pas automatiquement déterminer la structure de la classe métier.

Exemple :

```text
ScheduleRow
```

peut être distinct de :

```text
Schedule
```

---

# 87. Business objects versus API schemas

Même principe :

```text
ScheduleCreateSchema
ScheduleResponseSchema
Schedule
```

peuvent être trois objets différents.

Le domaine ne doit pas être contraint par l'API REST.

---

# 88. Business objects versus events

Un :

```text
ScheduleCreated
```

n'est pas le même objet qu'un :

```text
Schedule
```

L'événement décrit un changement déjà survenu.

---

# 89. Business objects versus commands

```text
CreateSchedule
```

exprime une intention.

```text
Schedule
```

exprime l'état métier obtenu.

---

# 90. Business objects versus services

Tous les concepts ne doivent pas devenir des classes contenant de l'état.

Exemple :

```text
SchedulerEngine
```

peut être un service du domaine ou de l'application.

De même :

```text
OccurrenceCalculator
```

peut parfois être un service si le comportement ne tient naturellement dans aucun objet.

---

# 91. Comportement riche versus anémie

Il faut éviter que les objets deviennent uniquement :

```text
data containers
```

avec toute la logique placée ailleurs.

Par exemple :

```text
Schedule.pause()
```

peut être plus cohérent que :

```text
ScheduleService.set_status(schedule, "PAUSED")
```

si la transition appartient véritablement au schedule.

---

# 92. Exemple d'objet riche

Conceptuellement :

```python
schedule.pause(at=now)
```

peut valider :

```text
ACTIVE → PAUSED
```

et interdire :

```text
CANCELLED → PAUSED
```

Le comportement protège ainsi l'invariant.

---

# 93. Exemple de Value Object riche

`GracePeriod` peut encapsuler :

```text
duration >= 0
```

au lieu de laisser circuler :

```text
-5 minutes
```

dans le système.

---

# 94. Objets qui portent probablement une identité

À ce stade, les candidats principaux sont :

```text
Job
Schedule
Occurrence
ExecutionRequest
Execution
Attempt
Lease
```

Mais cette liste doit encore être validée.

---

# 95. Objets probablement définis par leur valeur

Exemples :

```text
ScheduleId
OccurrenceId
Duration
GracePeriod
Timezone
CronExpression
ConcurrencyKey
Deadline
TimeWindow
```

---

# 96. Objets probablement comportementaux

Exemples :

```text
Trigger
MisfirePolicy
ConcurrencyPolicy
RetryPolicy
Calendar
Clock
```

Ils sont moins intéressants par leur identité que par leur comportement.

---

# 97. Objets probablement externes au domaine pur

Exemples :

```text
SQLScheduleStore
RedisLeaseStore
ThreadExecutor
ProcessExecutor
```

Ils appartiennent davantage à l'infrastructure.

---

# 98. Première matrice de classification

| Objet | Identité probable | État mutable | Comportement métier | Catégorie pressentie |
|---|---:|---:|---:|---|
| `Schedule` | Oui | Oui | Oui | Entity / Aggregate Root |
| `Job` | Oui | Faible | Oui | Entity |
| `Trigger` | Non | Faible | Oui | Value/Strategy |
| `Occurrence` | Oui ou naturelle | Faible | Faible | Entity / Value hybride |
| `Clock` | Non | Non | Oui | Domain Service / Port |
| `Calendar` | Non | Faible | Oui | Policy / Domain Object |
| `GracePeriod` | Non | Non | Faible | Value Object |
| `MisfirePolicy` | Non | Non | Oui | Policy |
| `ConcurrencyPolicy` | Non | Non | Oui | Policy |
| `SchedulingDecision` | Non | Non | Oui | Value Object |
| `ExecutionRequest` | Oui | Faible | Faible | Entity / Command-like Object |
| `Execution` | Oui | Oui | Oui | Entity |
| `Attempt` | Oui | Oui | Oui | Entity |
| `ExecutionResult` | Non | Non | Faible | Value Object |
| `Executor` | Non | N/A | Oui | Port |
| `ScheduleStore` | Non | N/A | Oui | Port / Repository |
| `Lease` | Oui | Oui | Oui | Entity / Infra-domain Object |

Cette classification reste provisoire.

---

# 99. Questions à poser pour chaque objet

Avant de conserver un objet, il faut vérifier :

```text
A-t-il une identité propre ?

Son identité compte-t-elle dans le temps ?

Peut-il changer tout en restant le même objet ?

Est-il défini uniquement par ses valeurs ?

Protège-t-il des invariants ?

Possède-t-il un lifecycle ?

Est-il seulement une stratégie ?

Est-il seulement un port technique ?

Est-il vraiment nécessaire ?
```

---

# 100. Anti-pattern : Generic Job Object

Un mauvais modèle pourrait devenir :

```text
Job
├── schedule
├── retries
├── trigger
├── workflow
├── executor
├── state
├── result
├── queue
└── metadata
```

Ce `Job` devient alors un objet universel sans frontière claire.

PyScheduleKit doit éviter cela.

---

# 101. Anti-pattern : Generic Task

Même problème avec :

```text
Task
```

utilisé pour désigner :

```text
schedule
execution
workflow step
function
queue item
```

Le vocabulaire devient alors inutilisable.

---

# 102. Anti-pattern : Generic Status

Éviter :

```text
Status
```

partagé par tous les objets.

Préférer :

```text
ScheduleState
OccurrenceState
ExecutionState
AttemptState
```

---

# 103. Anti-pattern : Trigger as Executor

Un trigger ne doit jamais devenir :

```text
CronTrigger.run()
```

ou :

```text
IntervalTrigger.execute()
```

Sa responsabilité reste :

```text
calculation
```

et non :

```text
side effect
```

---

# 104. Anti-pattern : Schedule as Workflow

Le schedule ne doit pas contenir :

```text
steps
dependencies
branching
DAG
```

Ces concepts appartiennent à PyWorkflowKit.

---

# 105. Anti-pattern : Execution contains business internals

Une `Execution` ne doit pas connaître :

```text
colonnes d'un dataset
mappings de transformation
pagination API
DAG interne
```

Elle doit rester générique vis-à-vis du target.

---

# 106. Anti-pattern : Clock hidden in global state

Éviter :

```text
datetime.now()
```

répandu partout.

Préférer :

```text
Clock
```

injecté explicitement.

Cela rend les décisions reproductibles.

---

# 107. Anti-pattern : Policy hidden in conditionals

Éviter :

```python
if lateness > 300:
    ...
```

en dur partout.

Préférer un objet explicite :

```text
MisfirePolicy
```

ou :

```text
GracePeriod
```

---

# 108. Objets dans un cas direct

Exemple :

```text
every 5 minutes
→ run ingestion
```

Objets impliqués :

```text
Job
Schedule
IntervalTrigger
Occurrence
SchedulingDecision
ExecutionRequest
Executor
```

Puis :

```text
PyIngestKit
```

prend le relais.

---

# 109. Objets dans un cas workflow

Exemple :

```text
every day @ 06:00
→ daily_orders_pipeline
```

Objets :

```text
Schedule
CronTrigger
Occurrence
ExecutionRequest
```

Puis :

```text
WorkflowExecutor
     ↓
PyWorkflowKit
```

Le scheduler n'introduit pas de :

```text
Step
DAG
Dependency
```

---

# 110. Interaction avec PyWorkflowKit

```text
PyScheduleKit
─────────────────────
Schedule
Occurrence
ExecutionRequest

       │
       ▼

PyWorkflowKit
─────────────────────
Workflow
WorkflowRun
Step
StepRun
Dependency
```

Le contrat commun peut être :

```text
ExecutionContext
TargetRef
ArtifactRef
CorrelationId
```

---

# 111. Interaction avec PyIngestKit

```text
PyScheduleKit
Occurrence
   │
   ▼
ExecutionRequest
   │
   ▼
PyIngestKit
IngestionRun
```

Le scheduler ne doit pas modéliser :

```text
Source
Connector
Checkpoint
Destination
```

---

# 112. Interaction avec PyTransformKit

Même principe :

```text
PyScheduleKit
   │
   ▼
ExecutionRequest
   │
   ▼
PyTransformKit
TransformationRun
```

PyScheduleKit ne connaît pas :

```text
Expression
Mapping
Schema
Dataset operation
```

---

# 113. Objets communs potentiels dans l'écosystème

Certains concepts pourraient devenir des contrats partagés :

```text
CorrelationId
TraceId
ExecutionContext
ArtifactRef
DatasetRef
TargetRef
```

Mais il faut éviter de centraliser :

```text
Schedule
Workflow
IngestionRun
TransformationRun
```

dans un méga-core.

---

# 114. Modèle conceptuel complet

```text
                           Clock
                             │
                             ▼
                         Scheduler
                             │
                             │ evaluates
                             ▼
┌─────────┐      ┌──────────────────────┐
│   Job   │─────▶│       Schedule       │
└─────────┘      │                      │
                 │ Trigger              │
                 │ Calendar             │
                 │ Policies             │
                 │ State                │
                 └──────────┬───────────┘
                            │
                            │ produces
                            ▼
                      ┌────────────┐
                      │ Occurrence │
                      └─────┬──────┘
                            │
                            ▼
                 ┌────────────────────┐
                 │ SchedulingDecision │
                 └─────────┬──────────┘
                           │
                ┌──────────┼───────────┐
                │          │           │
                ▼          ▼           ▼
              WAIT        SKIP       EXECUTE
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ExecutionRequest │
                              └────────┬────────┘
                                       │
                                       ▼
                                  Executor
                                       │
                                       ▼
                                  Execution
                                       │
                                   ┌───┴───┐
                                   ▼       ▼
                                Attempt  Attempt
```

---

# 115. Modèle de responsabilité

```text
Target
→ ce qui doit être lancé

Job
→ définition logique du travail

Schedule
→ planification durable

Trigger
→ calcul des occurrences

Calendar
→ validation calendaire

Occurrence
→ échéance concrète

Policy
→ décision comportementale

Scheduler
→ coordination temporelle

ExecutionRequest
→ demande de passage vers runtime

Executor
→ mécanisme de soumission

Execution
→ run concret

Attempt
→ tentative concrète

ExecutionResult
→ résultat final
```

---

# 116. Premier ordre de dépendances souhaité

Le cœur métier devrait idéalement éviter des dépendances inverses.

On peut viser :

```text
Schedule
   ↓
Trigger
   ↓
Temporal Objects
```

et :

```text
SchedulerEngine
   ↓
Schedule
Occurrence
Policies
```

puis :

```text
Application Layer
   ↓
Executor Port
Store Port
```

sans que :

```text
Trigger
```

dépende d'un executor ou d'une base SQL.

---

# 117. Objets à approfondir en priorité

Les objets les plus structurants sont :

```text
Schedule
Trigger
Occurrence
SchedulingDecision
ExecutionRequest
Execution
Clock
Calendar
MisfirePolicy
ConcurrencyPolicy
```

Ils devront faire l'objet d'une modélisation particulièrement stricte.

---

# 118. Questions encore ouvertes

## Job

```text
Job est-il réellement nécessaire
ou Target suffit-il ?
```

---

## Schedule

```text
Est-il l'Aggregate Root principal ?
```

---

## Occurrence

```text
Entity ou Value Object ?
Doit-elle être persistée ?
```

---

## NextRunTime

```text
Valeur dérivée ou état persistant ?
```

---

## Execution

```text
Fait-elle partie de PyScheduleKit
ou d'un execution runtime externe ?
```

---

## Retry

```text
Quel niveau de retry appartient réellement au scheduler ?
```

---

## Pause

```text
Que deviennent les occurrences pendant la pause ?
```

---

## Coalescing

```text
Faut-il matérialiser un OccurrenceGroup ?
```

---

# 119. Critères d'acceptation du modèle métier

La modélisation devra permettre d'expliquer sans ambiguïté :

```text
où est stockée la règle temporelle ;

qui calcule une occurrence ;

qui décide qu'elle est due ;

qui applique la politique de misfire ;

qui applique la concurrence ;

qui crée une ExecutionRequest ;

qui exécute réellement le travail ;

comment une execution est reliée à son occurrence ;

comment plusieurs attempts sont reliés à une execution ;

comment le temps est simulé ;

comment les calendriers influencent les occurrences.
```

---

# 120. Règle architecturale centrale

La chaîne suivante doit rester visible dans le modèle :

```text
Definition
   ↓
Temporal Calculation
   ↓
Occurrence
   ↓
Decision
   ↓
Execution Request
   ↓
Runtime
```

Chaque transition représente une responsabilité différente.

---

# 121. Résumé des objets principaux

| Objet | Rôle |
|---|---|
| `Target` | Référence vers ce qui devra être déclenché |
| `Job` | Définition logique d'un travail |
| `Schedule` | Planification durable |
| `Trigger` | Calcul des occurrences |
| `Occurrence` | Échéance temporelle concrète |
| `Clock` | Source du temps courant |
| `Calendar` | Règles de validité calendaire |
| `SchedulingDecision` | Résultat de l'évaluation |
| `MisfirePolicy` | Traitement des occurrences manquées |
| `ConcurrencyPolicy` | Gestion des chevauchements |
| `ExecutionRequest` | Demande de lancement |
| `Executor` | Soumission au runtime |
| `Execution` | Run concret |
| `Attempt` | Tentative technique |
| `ExecutionResult` | Résultat |
| `Lease` | Ownership temporaire distribué |

---

# 122. Vision finale

Le domaine peut désormais être lu ainsi :

```text
                     ┌───────────────┐
                     │     TIME      │
                     └───────┬───────┘
                             │
                             ▼
                           Clock
                             │
                             ▼
┌────────┐             ┌─────────────┐
│  Job   │────────────▶│  Schedule   │
└────────┘             └──────┬──────┘
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                    ▼         ▼         ▼
                 Trigger   Calendar   Policies
                    │
                    ▼
                Occurrence
                    │
                    ▼
             SchedulerEngine
                    │
                    ▼
           SchedulingDecision
                    │
        ┌───────────┼────────────┐
        │           │            │
        ▼           ▼            ▼
       WAIT        SKIP        EXECUTE
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
                            ▼             ▼
                         Attempt       Attempt
                                   │
                                   ▼
                           ExecutionResult
```

---

# Conclusion

La modélisation des objets métier révèle que le scheduling n'est pas un simple trio :

```text
Job
Cron
Executor
```

Il repose sur une chaîne beaucoup plus riche :

```text
Target
→ Job
→ Schedule
→ Trigger
→ Occurrence
→ SchedulingDecision
→ ExecutionRequest
→ Execution
→ Attempt
→ ExecutionResult
```

Autour de cette chaîne gravitent :

```text
Clock
Calendar
Timezone
GracePeriod
MisfirePolicy
ConcurrencyPolicy
RetryPolicy
Lease
ExecutionContext
```

La principale leçon est qu'il faut séparer :

```text
l'intention temporelle
le calcul temporel
l'échéance
la décision
la demande d'exécution
l'exécution réelle
```

Cette séparation constituera la base du futur modèle DDD de PyScheduleKit.

---

# Suite documentaire

Le prochain document est :

```text
05_SCHEDULING_ENTITIES_AND_VALUE_OBJECTS.md
```

Il devra classer précisément les objets étudiés ici en :

```text
Entity
Value Object
Aggregate Root
Domain Service
Policy
Port
Infrastructure Object
```

avec une attention particulière à :

```text
Schedule
Occurrence
Execution
Attempt
Trigger
Clock
Calendar
GracePeriod
Timezone
SchedulingDecision
ExecutionRequest
Lease
```

L'objectif sera de passer d'une cartographie conceptuelle à une **modélisation DDD formelle du domaine du scheduling**.