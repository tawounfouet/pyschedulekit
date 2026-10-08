# Scheduling — Entities, Value Objects et classification DDD

**Document :** `05_SCHEDULING_ENTITIES_AND_VALUE_OBJECTS.md`  
**Projet :** PyScheduleKit  
**Statut :** Modélisation DDD  
**Nature :** Entities / Value Objects / Aggregates / Domain Services / Policies / Ports  
**Prérequis :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
- `01_SCHEDULING_DOMAIN_INTRODUCTION.md`
- `02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md`
- `03_SCHEDULING_DOMAIN_VOCABULARY.md`
- `04_SCHEDULING_BUSINESS_OBJECTS.md`

---

# 1. Objectif

Le document précédent a identifié les principaux objets manipulés dans le domaine du scheduling.

Il faut maintenant les classifier selon leur nature métier.

La question n'est plus simplement :

```text
Quel objet existe ?
```

mais :

```text
Cet objet possède-t-il une identité ?

Est-il défini uniquement par sa valeur ?

Peut-il changer tout en restant le même objet ?

Protège-t-il des invariants ?

Possède-t-il un cycle de vie ?

Est-il un service du domaine ?

Est-il une stratégie ?

Est-il un port vers l'infrastructure ?
```

Cette classification est fondamentale pour éviter de transformer PyScheduleKit en un ensemble de simples dataclasses sans modèle métier explicite.

---

# 2. Les catégories DDD utilisées

Le modèle de PyScheduleKit distinguera au minimum :

```text
Entity
Value Object
Aggregate Root
Aggregate
Domain Service
Policy
Specification
Command
Event
Port
Infrastructure Adapter
```

Ces catégories ne correspondent pas nécessairement à une hiérarchie de classes Python.

Elles représentent avant tout des rôles dans le modèle.

---

# 3. Entity

Une `Entity` est un objet dont l'identité compte dans le temps.

Deux entities peuvent avoir les mêmes attributs tout en restant deux objets différents.

Exemple :

```text
Schedule #A

name = daily-report
cron = 0 6 * * *
```

et :

```text
Schedule #B

name = daily-report
cron = 0 6 * * *
```

peuvent être deux schedules différents.

Ce qui compte est :

```text
ScheduleId
```

et non seulement leurs propriétés.

---

# 4. Propriétés d'une Entity

Une Entity possède généralement :

```text
identity
lifecycle
state transitions
history
invariants
```

Elle peut évoluer :

```text
ACTIVE
  ↓
PAUSED
  ↓
ACTIVE
  ↓
CANCELLED
```

tout en restant la même entity.

---

# 5. Value Object

Un `Value Object` est défini par sa valeur.

Deux value objects ayant la même valeur sont conceptuellement équivalents.

Exemple :

```text
Duration(5 minutes)
```

et :

```text
Duration(5 minutes)
```

représentent la même valeur métier.

Ils n'ont pas besoin d'identifiant.

---

# 6. Propriétés d'un Value Object

Un Value Object devrait idéalement être :

```text
immutable
validé à la construction
comparé par valeur
sans identité métier
```

Il peut malgré tout porter du comportement.

Exemple :

```text
GracePeriod(5 minutes)

deadline_for(08:00)
→ 08:05
```

Un Value Object n'est donc pas nécessairement un simple conteneur de données.

---

# 7. Aggregate

Un `Aggregate` est un groupe cohérent d'objets métier dont les invariants doivent être protégés ensemble.

L'accès aux objets internes se fait normalement via une racine :

```text
Aggregate Root
```

Exemple conceptuel :

```text
Schedule Aggregate
│
├── Schedule
├── Trigger
├── Timezone
├── CalendarRef
├── Policies
└── Lifecycle State
```

---

# 8. Aggregate Root

L'`Aggregate Root` est l'Entity principale par laquelle toutes les modifications cohérentes de l'aggregate doivent passer.

Pour PyScheduleKit, la première hypothèse forte est :

```text
Schedule
=
Aggregate Root principal
```

Cette hypothèse sera détaillée dans la suite.

---

# 9. Domain Service

Un `Domain Service` porte une opération métier qui :

```text
ne correspond naturellement à aucune Entity

ou

nécessite plusieurs objets du domaine
```

Exemple potentiel :

```text
SchedulingEvaluator
```

qui combine :

```text
Schedule
Occurrence
Clock
ExecutionSnapshot
Policies
```

pour produire :

```text
SchedulingDecision
```

---

# 10. Policy

Une `Policy` est une stratégie métier exprimant :

> Que faire dans une situation donnée ?

Exemples :

```text
MisfirePolicy
ConcurrencyPolicy
RetryPolicy
CoalescingPolicy
```

Une Policy est généralement :

```text
sans identité
immutable
behavior-oriented
```

Elle ressemble donc structurellement à un Value Object ou à une stratégie.

---

# 11. Port

Un `Port` définit un contrat vers un système externe ou une infrastructure.

Exemples :

```text
Clock
Executor
ScheduleRepository
ExecutionRepository
LeaseManager
EventPublisher
```

Le domaine dépend de l'abstraction.

L'infrastructure fournit l'implémentation.

---

# 12. Vue générale de classification

Une première classification peut être proposée :

| Objet | Classification principale |
|---|---|
| `Schedule` | Entity / Aggregate Root |
| `Job` | Entity |
| `Occurrence` | Entity ou Value Object identifié |
| `ExecutionRequest` | Entity légère / Command Object |
| `Execution` | Entity |
| `Attempt` | Entity |
| `Lease` | Entity |
| `Trigger` | Value Object / Strategy |
| `Timezone` | Value Object |
| `Duration` | Value Object |
| `GracePeriod` | Value Object |
| `Deadline` | Value Object |
| `TimeWindow` | Value Object |
| `ConcurrencyKey` | Value Object |
| `CronExpression` | Value Object |
| `SchedulingDecision` | Value Object |
| `ExecutionResult` | Value Object |
| `MisfirePolicy` | Policy |
| `ConcurrencyPolicy` | Policy |
| `RetryPolicy` | Policy |
| `Calendar` | Domain Object / Policy |
| `Clock` | Port / Domain Service |
| `SchedulerEngine` | Domain/Application Service |
| `Executor` | Port |
| `ScheduleRepository` | Port |
| `ExecutionRepository` | Port |

Cette classification reste à affiner objet par objet.

---

# 13. Schedule — classification

## Classification retenue

```text
Schedule
=
Entity
+
Aggregate Root
```

C'est l'objet le plus naturel pour porter l'identité durable de la planification.

---

# 14. Pourquoi Schedule est une Entity

Un Schedule conserve son identité lorsque ses propriétés changent.

Exemple :

```text
ScheduleId = daily-orders
```

Version initiale :

```text
Every day @ 06:00
```

Puis :

```text
Every day @ 08:00
```

Il s'agit toujours du même schedule.

Ainsi :

```text
identity
>
attribute equality
```

---

# 15. Identité du Schedule

```text
ScheduleId
```

doit être explicite.

Exemple :

```text
ScheduleId("daily-orders")
```

La valeur technique pourrait être :

```text
UUID
ULID
string contrôlée
```

mais le domaine doit utiliser un type dédié.

---

# 16. État du Schedule

Le Schedule peut posséder un lifecycle.

```text
DRAFT ?
   ↓
ACTIVE
   ↓
PAUSED
   ↓
ACTIVE
   ↓
CANCELLED
```

ou éventuellement :

```text
COMPLETED
```

pour un trigger fini.

Le modèle exact sera défini ultérieurement.

---

# 17. Invariants du Schedule

Quelques invariants potentiels :

```text
un schedule doit avoir un target

un schedule doit avoir un trigger

start_at <= end_at

un schedule CANCELLED ne peut pas être resumed

un schedule COMPLETED ne produit plus d'occurrence

une timezone doit être compatible avec le trigger

une grace period ne peut pas être négative
```

Ces règles doivent être protégées par l'aggregate.

---

# 18. Aggregate Schedule

Une première composition possible :

```text
Schedule
│
├── ScheduleId
├── TargetRef
├── Trigger
├── Timezone
├── CalendarRef
├── ScheduleWindow
├── MisfirePolicy
├── ConcurrencyPolicy
├── JitterPolicy
├── ScheduleState
├── ScheduleRevision
└── Metadata
```

Tous ces objets ne doivent pas nécessairement être persistés dans une seule table.

L'Aggregate est une frontière de cohérence métier, pas une structure SQL.

---

# 19. Ce que Schedule ne doit pas contenir

Éviter :

```text
Schedule
├── executions[]
├── attempts[]
├── workflow steps[]
├── logs[]
├── metrics[]
└── artifacts[]
```

Un schedule peut générer des milliers ou millions d'exécutions.

Les inclure dans son aggregate rendrait celui-ci gigantesque.

---

# 20. Job — classification

## Hypothèse

```text
Job
=
Entity
```

si PyScheduleKit conserve réellement ce concept.

---

# 21. Pourquoi Job peut être une Entity

Un job peut conserver une identité durable indépendamment de ses schedules.

Exemple :

```text
JobId("generate-report")
```

avec :

```text
Schedule A
→ every day @ 06:00

Schedule B
→ every Monday @ 10:00
```

Les deux schedules référencent la même définition logique.

---

# 22. Alternative : supprimer Job du cœur

Une autre architecture serait :

```text
Schedule
   │
   ▼
TargetRef
```

sans Entity `Job`.

Cela simplifierait le modèle.

Il faudra donc décider ultérieurement si :

```text
Job
```

apporte suffisamment de valeur par rapport à :

```text
Target
```

Le modèle DDD ne doit pas conserver un objet uniquement parce que d'autres schedulers utilisent ce terme.

---

# 23. TargetRef — classification

```text
TargetRef
=
Value Object
```

Un TargetRef est défini par sa valeur.

Exemple :

```text
TargetRef("workflow:daily-orders")
```

Deux références identiques représentent le même target logique.

---

# 24. Trigger — classification

```text
Trigger
=
Value Object / Strategy
```

dans la majorité des cas.

Il n'a normalement pas besoin d'identité.

---

# 25. Pourquoi Trigger ressemble à un Value Object

Deux triggers identiques :

```text
CronTrigger(
    expression="0 6 * * *",
    timezone="Europe/Paris"
)
```

sont conceptuellement équivalents.

Il est inutile de leur donner :

```text
trigger_id
```

dans le cœur du domaine.

---

# 26. Trigger comme objet comportemental

Le trigger ne doit pas être passif.

Il porte le comportement :

```text
next_occurrence(...)
```

Exemple conceptuel :

```text
trigger.next_after(reference_time)
```

Il reste donc un Value Object riche.

---

# 27. DateTrigger

Classification :

```text
Value Object
```

Valeurs possibles :

```text
scheduled_instant
```

Invariant :

```text
scheduled_instant must be valid
```

---

# 28. IntervalTrigger

Classification :

```text
Value Object
```

Il peut contenir :

```text
interval
mode
start_at
```

avec :

```text
mode = FIXED_RATE
```

ou :

```text
mode = FIXED_DELAY
```

si les deux sont supportés.

---

# 29. CronTrigger

Classification :

```text
Value Object
```

Composition possible :

```text
CronExpression
Timezone
StartBoundary
EndBoundary
```

---

# 30. CronExpression

```text
CronExpression
=
Value Object
```

Il doit :

```text
valider sa syntaxe
normaliser éventuellement la représentation
refuser les expressions invalides
```

Exemple :

```text
CronExpression("0 6 * * *")
```

---

# 31. CalendarTrigger

Classification :

```text
Value Object / Strategy
```

Il peut référencer :

```text
CalendarId
```

plutôt que contenir un calendrier complet.

---

# 32. Occurrence — le cas le plus subtil

La classification d'`Occurrence` est moins évidente.

Deux modèles sont plausibles.

---

# 33. Modèle A — Occurrence comme Value Object

Une occurrence pourrait être définie uniquement par :

```text
ScheduleId
ScheduledAt
ScheduleRevision
```

Ainsi :

```text
Occurrence(
    schedule_id=A,
    scheduled_at=T
)
```

serait naturellement identifiable par sa valeur.

Cela convient si l'occurrence :

```text
n'est pas persistée séparément

n'a pas de lifecycle autonome

n'est qu'un résultat de calcul
```

---

# 34. Modèle B — Occurrence comme Entity

Une occurrence pourrait recevoir :

```text
OccurrenceId
```

et posséder un lifecycle :

```text
PLANNED
DUE
MISSED
SKIPPED
MATERIALIZED
```

Cela devient intéressant si elle est :

```text
persistée
auditable
dédupliquée
claimée par plusieurs scheduler nodes
référencée par des executions
```

---

# 35. Décision recommandée pour Occurrence

Pour le cœur initial de PyScheduleKit :

```text
Occurrence
=
Value Object identifié naturellement
```

avec identité logique :

```text
(ScheduleId, ScheduledAt, ScheduleRevision)
```

On évite ainsi de créer trop tôt une Entity persistante.

Si les besoins distribués l'exigent ultérieurement, une matérialisation pourra devenir :

```text
MaterializedOccurrence
```

avec :

```text
OccurrenceId
```

---

# 36. Séparation utile

```text
Occurrence
=
fait temporel calculé

MaterializedOccurrence
=
occurrence persistée avec identité
```

Cette séparation évite de complexifier le modèle local pour les besoins du scheduling distribué.

---

# 37. NextRunTime — classification

```text
NextRunTime
=
Value Object / Derived State
```

Il représente une valeur temporelle.

Exemple :

```text
NextRunTime(2026-09-30T06:00...)
```

Il n'a pas d'identité propre.

---

# 38. Instant — classification

```text
Instant
=
Value Object
```

Il représente un point temporel absolu.

Il doit être immutable.

---

# 39. LocalDateTime

```text
LocalDateTime
=
Value Object
```

Il doit rester distinct d'Instant.

---

# 40. Timezone

```text
Timezone
=
Value Object
```

Exemple :

```text
Timezone("Europe/Paris")
```

La valeur doit référencer une timezone valide, pas simplement un offset.

---

# 41. Duration

```text
Duration
=
Value Object
```

Invariant :

```text
duration >= 0
```

sauf rares cas métier où une durée signée serait explicitement souhaitée.

---

# 42. GracePeriod

```text
GracePeriod
=
Value Object
```

Composition :

```text
Duration
```

Comportement potentiel :

```text
deadline_for(scheduled_at)
```

---

# 43. Deadline

```text
Deadline
=
Value Object
```

défini par un `Instant`.

Il peut proposer :

```text
is_expired(now)
```

---

# 44. TimeWindow

```text
TimeWindow
=
Value Object
```

Composition :

```text
start
end
```

Invariant :

```text
start <= end
```

Comportements :

```text
contains()
overlaps()
duration()
```

---

# 45. ScheduleWindow

Un Value Object spécifique peut représenter :

```text
start_at
end_at
```

d'un schedule.

```text
ScheduleWindow
=
Value Object
```

Il protège notamment :

```text
start_at <= end_at
```

---

# 46. Calendar — classification

`Calendar` est plus subtil.

Il peut être vu comme :

```text
Domain Object
+
Policy
```

ou comme :

```text
Domain Service
```

selon son implémentation.

---

# 47. Calendar statique

Un calendrier embarquant :

```text
jours ouvrés
jours fériés
exceptions
```

peut être représenté comme un Value Object riche.

Exemple :

```text
BusinessCalendar
```

---

# 48. Calendar externe

Si les jours fériés sont récupérés depuis :

```text
API
database
service réglementaire
```

alors le domaine devrait dépendre d'un port :

```text
CalendarProvider
```

et non de l'infrastructure directement.

---

# 49. Proposition de séparation

```text
CalendarRule
=
Value Object / Policy

CalendarProvider
=
Port
```

Le premier contient la logique métier.

Le second fournit les données externes.

---

# 50. Clock — classification

```text
Clock
=
Port
```

Le domaine ne doit pas connaître :

```text
datetime.now()
time.time()
system clock
```

directement.

---

# 51. Implémentations de Clock

Infrastructure :

```text
SystemClock
```

Tests :

```text
FixedClock
MutableClock
```

Le port reste :

```text
Clock.now() -> Instant
```

---

# 52. SchedulingDecision — classification

```text
SchedulingDecision
=
Value Object
```

Il représente le résultat immutable d'une évaluation.

Exemple :

```text
SchedulingDecision(
    type=EXECUTE,
    reason=ELIGIBLE
)
```

---

# 53. Pourquoi SchedulingDecision est un Value Object

Il n'a normalement pas :

```text
identity
lifecycle
state mutation
```

Deux décisions identiques dans le même contexte sont équivalentes par valeur.

---

# 54. DecisionType

```text
DecisionType
=
Enum / Value Object
```

Valeurs potentielles :

```text
WAIT
EXECUTE
SKIP
COALESCE
CATCH_UP
```

---

# 55. DecisionReason

```text
DecisionReason
=
Value Object / Enum
```

Exemples :

```text
ELIGIBLE
SCHEDULE_PAUSED
MISFIRE_EXPIRED
OVERLAP_FORBIDDEN
OUTSIDE_WINDOW
DEADLINE_EXCEEDED
```

---

# 56. Eligibility

Deux possibilités :

```text
bool
```

ou objet explicite :

```text
EligibilityResult
```

La seconde est préférable si l'on souhaite conserver :

```text
eligible
reasons
blocking_rules
```

Classification :

```text
Value Object
```

---

# 57. MisfirePolicy

```text
MisfirePolicy
=
Policy
```

Elle ne possède pas d'identité.

Deux policies configurées de manière identique sont équivalentes.

Exemples :

```text
SkipMisfire
RunNowMisfire
CatchUpMisfire
CoalesceMisfire
```

---

# 58. Policy versus enum

On pourrait représenter :

```text
misfire_policy = "SKIP"
```

mais une vraie Policy devient intéressante lorsque la logique dépasse un simple choix.

Exemple :

```text
CatchUpPolicy(
    max_occurrences=10,
    lookback=24h
)
```

La Policy devient alors un objet riche.

---

# 59. ConcurrencyPolicy

```text
ConcurrencyPolicy
=
Policy
```

Exemples :

```text
AllowOverlap
ForbidOverlap
QueueOverlap
ReplaceActive
```

---

# 60. ConcurrencyKey

```text
ConcurrencyKey
=
Value Object
```

Exemples :

```text
ConcurrencyKey("schedule:daily-orders")
```

ou :

```text
ConcurrencyKey("tenant:123:report")
```

Elle définit le scope de concurrence.

---

# 61. ConcurrencyLimit

```text
ConcurrencyLimit
=
Value Object
```

Invariant :

```text
limit >= 1
```

Exemple :

```text
ConcurrencyLimit(1)
```

---

# 62. RetryPolicy

```text
RetryPolicy
=
Policy
```

Mais son ownership doit rester explicite.

On peut distinguer :

```text
DispatchRetryPolicy
```

de :

```text
ExecutionRetryPolicy
```

et éviter un objet trop générique.

---

# 63. BackoffStrategy

```text
BackoffStrategy
=
Policy / Strategy
```

Exemples :

```text
ConstantBackoff
LinearBackoff
ExponentialBackoff
```

Il peut être composé dans RetryPolicy.

---

# 64. JitterPolicy

```text
JitterPolicy
=
Policy
```

Elle calcule une variation autorisée.

Attention :

```text
scheduled_at
```

doit rester l'intention originale.

On peut introduire :

```text
effective_dispatch_at
```

pour la valeur affectée par le jitter.

---

# 65. ExecutionRequest — classification

`ExecutionRequest` est lui aussi subtil.

Il ressemble à :

```text
Command
```

mais peut posséder une identité propre :

```text
RequestId
```

---

# 66. Classification recommandée

```text
ExecutionRequest
=
immutable Entity-like Command Object
```

Elle possède :

```text
request_id
```

car il peut être nécessaire de :

```text
dédupliquer
auditer
tracer
relier à une submission
```

Mais une fois créée, elle devrait idéalement être immutable.

---

# 67. ExecutionRequest comme frontière

```text
Scheduling
      │
      ▼
ExecutionRequest
      │
      ▼
Runtime
```

Cela en fait un objet de boundary particulièrement important.

---

# 68. RequestId

```text
RequestId
=
Value Object
```

Même logique pour :

```text
ScheduleId
JobId
ExecutionId
AttemptId
```

Les IDs sont des Value Objects même lorsqu'ils identifient des Entities.

---

# 69. Execution — classification

Si PyScheduleKit conserve le suivi runtime :

```text
Execution
=
Entity
```

Elle possède :

```text
ExecutionId
lifecycle
status
timestamps
result
```

---

# 70. Lifecycle de l'Execution

Exemple :

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

Elle change d'état tout en restant la même execution.

C'est donc clairement une Entity.

---

# 71. Frontière possible

Il reste néanmoins possible que :

```text
Execution
```

appartienne à un bounded context :

```text
Execution Runtime
```

séparé du cœur Scheduling.

PyScheduleKit pourrait alors ne stocker que :

```text
ExecutionRef
ExecutionStatusSnapshot
```

---

# 72. ExecutionRef

```text
ExecutionRef
=
Value Object
```

Il permet de référencer une execution sans embarquer tout son modèle.

---

# 73. Attempt — classification

```text
Attempt
=
Entity
```

car :

```text
Attempt #1
Attempt #2
```

sont distincts même s'ils portent les mêmes paramètres.

Ils possèdent également un lifecycle.

---

# 74. AttemptNumber

```text
AttemptNumber
=
Value Object
```

Invariant :

```text
number >= 1
```

---

# 75. ExecutionResult

```text
ExecutionResult
=
Value Object
```

Il représente le résultat final observé.

Exemple :

```text
status
finished_at
artifact_refs
error_ref
```

Il devrait être immutable.

---

# 76. ArtifactRef

```text
ArtifactRef
=
Value Object
```

La donnée lourde reste hors de PyScheduleKit.

---

# 77. ExecutionContext

```text
ExecutionContext
=
Value Object
```

Idéalement immutable.

Composition possible :

```text
correlation_id
trace_id
schedule_id
occurrence_key
scheduled_at
metadata
```

---

# 78. CorrelationId

```text
CorrelationId
=
Value Object
```

Même chose pour :

```text
TraceId
```

---

# 79. ScheduleRevision

```text
ScheduleRevision
=
Value Object
```

Exemple :

```text
Revision(7)
```

Invariant :

```text
revision >= 1
```

Elle permet de relier une occurrence à la configuration qui l'a produite.

---

# 80. ScheduleState

```text
ScheduleState
=
Value Object / Enum
```

Les transitions, elles, appartiennent à :

```text
Schedule Entity
```

L'enum ne doit pas porter tout le lifecycle.

---

# 81. ExecutionState

Même principe :

```text
ExecutionState
=
Value Object / Enum
```

Les transitions appartiennent à :

```text
Execution Entity
```

---

# 82. SchedulerEngine — classification

```text
SchedulerEngine
=
Domain Service
```

ou éventuellement Application Service selon le niveau de responsabilité.

---

# 83. Quand le SchedulerEngine est un Domain Service

S'il fait principalement :

```text
evaluate
determine_due
apply_policies
produce_decision
```

sans :

```text
database transaction
thread management
network calls
```

alors il peut être considéré comme un Domain Service.

---

# 84. Quand il devient Application Service

S'il coordonne :

```text
repository
transaction
executor
event publisher
lease manager
```

il se rapproche d'un Application Service.

Une séparation saine serait :

```text
SchedulingEvaluator
=
Domain Service

SchedulerApplicationService
=
Application Service
```

---

# 85. SchedulingEvaluator

Proposition :

```text
SchedulingEvaluator
```

entrée :

```text
Schedule
Occurrence
Instant now
ExecutionSnapshot
```

sortie :

```text
SchedulingDecision
```

Il n'effectue aucun side effect.

---

# 86. SchedulerApplicationService

Responsabilités :

```text
charger les schedules
acquérir éventuellement une lease
demander une évaluation
persister les changements
publier les requests
publier les events
```

Il orchestre mais ne contient pas les règles métier profondes.

---

# 87. Executor — classification

```text
Executor
=
Port
```

Il définit un contrat :

```text
submit(request)
```

Le domaine ne doit pas dépendre de :

```text
ThreadPoolExecutor
Celery
Kafka
PyWorkflowKit
```

---

# 88. Adaptateurs Executor

Exemples :

```text
InlineExecutorAdapter
ThreadExecutorAdapter
ProcessExecutorAdapter
QueueExecutorAdapter
WorkflowExecutorAdapter
```

Ils appartiennent à l'infrastructure ou l'intégration.

---

# 89. ScheduleRepository

```text
ScheduleRepository
=
Port
```

Il manipule l'Aggregate Root :

```text
Schedule
```

Exemple conceptuel :

```text
save(schedule)
get(schedule_id)
remove(schedule_id)
```

---

# 90. Repository versus Store

Le langage recommandé devient :

```text
Domain/Application Layer
→ ScheduleRepository

Infrastructure Layer
→ SQLScheduleStore
```

Cela évite de mélanger abstraction métier et technologie.

---

# 91. ExecutionRepository

Si `Execution` appartient au même bounded context :

```text
ExecutionRepository
=
Port
```

Sinon, le scheduler peut simplement utiliser :

```text
ExecutionQueryPort
```

pour connaître les exécutions actives.

---

# 92. ActiveExecutionQuery

Une abstraction plus étroite peut être préférable :

```text
ActiveExecutionQuery
```

question :

```text
what executions are currently active for this concurrency key?
```

Cela évite d'importer tout le repository d'execution dans le domaine.

---

# 93. Lease — classification

Une `Lease` possède :

```text
LeaseId
OwnerId
ResourceKey
AcquiredAt
ExpiresAt
```

Elle évolue :

```text
ACTIVE
EXPIRED
RELEASED
```

Donc :

```text
Lease
=
Entity
```

---

# 94. LeaseManager

```text
LeaseManager
=
Port
```

Il fournit :

```text
acquire
renew
release
```

Une implémentation peut utiliser :

```text
PostgreSQL
Redis
etcd
database locks
```

---

# 95. SchedulerNodeId

```text
SchedulerNodeId
=
Value Object
```

utile dans le scheduling distribué.

---

# 96. DeduplicationKey

```text
DeduplicationKey
=
Value Object
```

Exemple :

```text
ScheduleId
+
ScheduledAt
+
ScheduleRevision
```

Elle peut être dérivée de l'Occurrence.

---

# 97. OccurrenceKey

Une abstraction claire peut être introduite :

```text
OccurrenceKey
```

Composition :

```text
ScheduleId
ScheduledAt
ScheduleRevision
```

Classification :

```text
Value Object
```

Elle représente l'identité naturelle d'une occurrence.

---

# 98. Cela simplifie le modèle

Ainsi :

```text
Occurrence
=
Value Object
```

portant :

```text
OccurrenceKey
```

sans devenir immédiatement une Entity persistante.

---

# 99. Commands

Les commandes représentent des intentions.

Exemples :

```text
CreateSchedule
PauseSchedule
ResumeSchedule
CancelSchedule
Reschedule
```

Classification :

```text
Command Object
```

Ils sont généralement immutables.

---

# 100. Events

Les Events représentent des faits passés.

Exemples :

```text
ScheduleCreated
SchedulePaused
OccurrenceDue
OccurrenceSkipped
ExecutionRequested
```

Classification :

```text
Domain Event
```

Ils sont immutables.

---

# 101. Entity versus Event

```text
Schedule
=
objet vivant

SchedulePaused
=
fait historique
```

Il ne faut pas confondre les deux.

---

# 102. Policy versus Specification

Une `Policy` dit :

```text
quoi faire
```

Une `Specification` répond plutôt :

```text
est-ce que cette condition est satisfaite ?
```

Exemple :

```text
IsOccurrenceDue
```

pourrait être une specification.

---

# 103. Doit-on introduire des Specifications ?

Pas nécessairement dès la première version.

Trop de classes comme :

```text
IsDueSpecification
IsWithinWindowSpecification
IsCalendarAllowedSpecification
```

peuvent fragmenter inutilement le domaine.

On ne les introduira que si elles apportent une réelle composabilité.

---

# 104. Aggregate principal proposé

Le cœur pourrait donc être :

```text
Schedule Aggregate
────────────────────────────

Schedule [Aggregate Root]
│
├── ScheduleId
├── TargetRef
├── Trigger
├── Timezone
├── ScheduleWindow
├── CalendarRef
├── MisfirePolicy
├── ConcurrencyPolicy
├── JitterPolicy
├── ScheduleState
├── ScheduleRevision
└── Metadata
```

---

# 105. Ce qui reste hors de cet Aggregate

```text
Occurrence history
Execution history
Attempts
Logs
Metrics
Leases
Workflow state
Artifacts
```

Ces objets doivent être référencés, pas encapsulés.

---

# 106. Aggregate Execution potentiel

Si le runtime appartient à PyScheduleKit :

```text
Execution Aggregate
────────────────────────

Execution [Aggregate Root]
│
├── ExecutionId
├── RequestId
├── OccurrenceKey
├── ExecutionState
├── Attempts
└── ExecutionResult
```

`Attempt` pourrait alors être une Entity interne à l'aggregate.

---

# 107. Avantage de cette structure

L'invariant :

```text
Attempt numbers are sequential
```

peut être protégé par Execution.

De même :

```text
SUCCESS execution cannot create new attempt
```

---

# 108. Mais attention à la taille de l'aggregate

Si une execution peut générer énormément de tentatives, même ce modèle peut devenir lourd.

Cependant, en pratique :

```text
attempt_count
```

reste généralement faible.

Ce modèle paraît donc raisonnable.

---

# 109. Deux Aggregates principaux possibles

Le bounded context pourrait contenir :

```text
Schedule Aggregate
```

et :

```text
Execution Aggregate
```

reliés uniquement par :

```text
ScheduleId
OccurrenceKey
RequestId
```

et non par références objet directes.

---

# 110. Pourquoi éviter les références objet fortes

Éviter :

```python
execution.schedule = schedule_object
```

dans un modèle persistant distribué.

Préférer :

```text
execution.schedule_id
```

Cela réduit :

```text
coupling
aggregate loading
transactional scope
```

---

# 111. Aggregate Occurrence ?

A priori :

```text
NON
```

dans la première version.

L'occurrence reste une valeur calculée.

Un aggregate dédié ne se justifierait que pour :

```text
massive backfill management
distributed claiming
durable occurrence lifecycle
```

---

# 112. Domain Service pour les occurrences

Un service éventuel :

```text
OccurrencePlanner
```

pourrait produire :

```text
next occurrence
occurrences in a window
catch-up occurrences
```

Mais il ne faut pas dupliquer la responsabilité des triggers.

Le trigger doit rester le calculateur principal.

---

# 113. CatchUpPlanner

Le catch-up, en revanche, peut justifier un service :

```text
CatchUpPlanner
```

entrée :

```text
Schedule
last_processed_occurrence
now
policy
```

sortie :

```text
OccurrenceSet
```

---

# 114. OccurrenceSet

```text
OccurrenceSet
=
Value Object / Collection Object
```

Il peut représenter plusieurs occurrences calculées.

Exemple :

```text
08:00
09:00
10:00
```

---

# 115. CoalescedOccurrenceSet

Un coalescing pourrait produire :

```text
CoalescedOccurrence
```

ou conserver :

```text
OccurrenceSet
```

dans la SchedulingDecision.

Éviter d'introduire trop tôt une nouvelle Entity.

---

# 116. Error objects

Les erreurs métier peuvent aussi être structurées.

Exemples :

```text
InvalidScheduleTransition
InvalidCronExpression
InvalidScheduleWindow
OccurrenceExpired
ConcurrencyViolation
```

Ces erreurs expriment des violations de domaine.

---

# 117. Validation syntaxique versus invariant métier

Exemple :

```text
CronExpression("foo")
```

est une erreur de valeur.

Alors que :

```text
Resume(CANCELLED schedule)
```

est une violation de lifecycle.

Les deux catégories doivent être distinguées.

---

# 118. Immutabilité

Les Value Objects devraient être immutables.

Exemples :

```text
Timezone
Duration
CronExpression
GracePeriod
ScheduleId
OccurrenceKey
SchedulingDecision
```

---

# 119. Mutation contrôlée des Entities

Les Entities peuvent changer, mais via des méthodes métier.

Préférer :

```python
schedule.pause(at=now)
```

à :

```python
schedule.state = "PAUSED"
```

La première approche protège les transitions.

---

# 120. Exemple de Schedule riche

Conceptuellement :

```python
schedule.pause(at=now)
schedule.resume(at=now)
schedule.cancel(at=now)
schedule.reschedule(new_trigger, at=now)
```

Ces méthodes peuvent :

```text
valider l'état
incrementer revision
produire un Domain Event
```

---

# 121. Exemple de Value Object riche

```python
grace_period.deadline_for(occurrence.scheduled_at)
```

ou :

```python
window.contains(now)
```

ou :

```python
cron.next_after(now)
```

L'objet porte le comportement correspondant à sa valeur.

---

# 122. Exemple d'Execution Entity riche

```python
execution.mark_queued(...)
execution.start(...)
execution.fail(...)
execution.succeed(...)
```

avec vérification de transitions.

---

# 123. Domain Events et Aggregates

Un aggregate peut accumuler des Domain Events.

Exemple :

```text
schedule.pause()
    ↓
SchedulePaused
```

Puis l'application publie l'event après persistance.

---

# 124. Eventual consistency

Les interactions entre Aggregates ne doivent pas nécessairement être transactionnelles.

Exemple :

```text
Schedule
   ↓
ExecutionRequest
   ↓
Execution
```

peut fonctionner avec une cohérence éventuelle.

Cela facilite les architectures distribuées.

---

# 125. Invariant intra-aggregate

Exemple :

```text
Schedule cannot be ACTIVE and CANCELLED simultaneously
```

doit être garanti immédiatement.

---

# 126. Invariant inter-aggregate

Exemple :

```text
max one active execution for a concurrency key
```

peut nécessiter :

```text
repository query
lock
lease
database constraint
```

et ne peut pas toujours être garanti uniquement par l'Entity Schedule.

---

# 127. DDD et concurrence distribuée

Certaines règles dépassent l'aggregate.

Par exemple :

```text
ForbidOverlap
```

nécessite de savoir si une autre execution est active.

Le Schedule seul ne peut pas le savoir.

Il faut donc :

```text
ConcurrencyPolicy
+
ActiveExecutionQuery
```

ou une abstraction équivalente.

---

# 128. Modèle de décision

```text
Schedule
Occurrence
CurrentTime
ActiveExecutionSnapshot
        │
        ▼
SchedulingEvaluator
        │
        ▼
SchedulingDecision
```

Cela permet de garder le modèle pur.

---

# 129. ActiveExecutionSnapshot

```text
ActiveExecutionSnapshot
=
Value Object
```

Il peut contenir :

```text
count
execution_refs
concurrency_key
observed_at
```

Cela évite de donner au Domain Service un repository brut.

---

# 130. Pourquoi utiliser un Snapshot

Le domaine raisonne alors sur :

```text
des faits observés
```

plutôt que sur :

```text
une infrastructure mutable
```

Cela améliore :

```text
testability
determinism
simulation
```

---

# 131. Ports principaux

Une première liste de ports pourrait être :

```text
Clock
ScheduleRepository
ExecutionQueryPort
Executor
LeaseManager
EventPublisher
CalendarProvider
```

Potentiellement :

```text
ExecutionRepository
```

si PyScheduleKit gère les executions.

---

# 132. Infrastructure adapters

Exemples :

```text
SystemClock
SQLScheduleRepository
InMemoryScheduleRepository
RedisLeaseManager
ThreadExecutorAdapter
PyWorkflowKitExecutorAdapter
```

Ils ne doivent pas polluer le domaine.

---

# 133. PyWorkflowKit integration

Un adapter pourrait être :

```text
WorkflowExecutor
```

qui traduit :

```text
ExecutionRequest
```

vers :

```text
PyWorkflowKit.WorkflowRunRequest
```

PyScheduleKit ne dépend ainsi pas du modèle interne de PyWorkflowKit.

---

# 134. PyIngestKit integration

Même logique :

```text
IngestionExecutorAdapter
```

ou un target générique pouvant invoquer PyIngestKit.

---

# 135. PyTransformKit integration

Même principe :

```text
TransformationExecutorAdapter
```

Les integrations sont extérieures au cœur métier.

---

# 136. Modèle de dépendances souhaité

```text
Domain
  ↑
Application
  ↑
Infrastructure
```

et non :

```text
Domain
  ↓
SQLAlchemy
Celery
APScheduler
PyWorkflowKit
```

---

# 137. Arbre de classification proposé

```text
Scheduling Domain
│
├── Aggregates
│   ├── Schedule
│   └── Execution ?
│
├── Entities
│   ├── Schedule
│   ├── Job ?
│   ├── Execution ?
│   ├── Attempt ?
│   └── Lease
│
├── Value Objects
│   ├── ScheduleId
│   ├── JobId
│   ├── TargetRef
│   ├── Trigger
│   ├── CronExpression
│   ├── Instant
│   ├── Duration
│   ├── Timezone
│   ├── TimeWindow
│   ├── GracePeriod
│   ├── Deadline
│   ├── Occurrence
│   ├── OccurrenceKey
│   ├── SchedulingDecision
│   ├── DecisionReason
│   ├── ConcurrencyKey
│   ├── ExecutionContext
│   └── ExecutionResult
│
├── Policies
│   ├── MisfirePolicy
│   ├── ConcurrencyPolicy
│   ├── RetryPolicy
│   ├── JitterPolicy
│   └── BackoffStrategy
│
├── Domain Services
│   ├── SchedulingEvaluator
│   └── CatchUpPlanner
│
└── Ports
    ├── Clock
    ├── ScheduleRepository
    ├── ExecutionQueryPort
    ├── Executor
    ├── LeaseManager
    ├── CalendarProvider
    └── EventPublisher
```

---

# 138. Classification résumée

| Objet | Entity | Value Object | Policy | Service | Port |
|---|---:|---:|---:|---:|---:|
| Schedule | ✓ | | | | |
| Job | ✓? | | | | |
| Trigger | | ✓ | | | |
| Occurrence | | ✓ | | | |
| ExecutionRequest | ✓* | | | | |
| Execution | ✓ | | | | |
| Attempt | ✓ | | | | |
| Lease | ✓ | | | | |
| Instant | | ✓ | | | |
| Duration | | ✓ | | | |
| Timezone | | ✓ | | | |
| GracePeriod | | ✓ | | | |
| TimeWindow | | ✓ | | | |
| SchedulingDecision | | ✓ | | | |
| ExecutionResult | | ✓ | | | |
| MisfirePolicy | | | ✓ | | |
| ConcurrencyPolicy | | | ✓ | | |
| RetryPolicy | | | ✓ | | |
| SchedulingEvaluator | | | | ✓ | |
| Clock | | | | | ✓ |
| Executor | | | | | ✓ |
| ScheduleRepository | | | | | ✓ |

`* ExecutionRequest` est traitée comme un command object doté d'une identité technique.

---

# 139. Décisions provisoires

À ce stade :

```text
Schedule
→ Entity + Aggregate Root

Trigger
→ Value Object / Strategy

Occurrence
→ Value Object avec identité naturelle

ExecutionRequest
→ immutable command object avec RequestId

Execution
→ Entity si gérée par PyScheduleKit

Attempt
→ Entity interne à Execution

SchedulingDecision
→ Value Object

Clock
→ Port

Calendar
→ Domain Object + éventuel Provider Port

Policies
→ objets métier comportementaux sans identité

Executor
→ Port

Repositories
→ Ports
```

---

# 140. Décisions à repousser

Les points suivants ne doivent pas encore être figés définitivement :

```text
Job est-il nécessaire ?

Execution appartient-elle au bounded context principal ?

Occurrence doit-elle devenir Entity en mode distribué ?

Calendar doit-il être Value Object ou abstraction composite ?

RetryPolicy appartient-elle réellement au scheduler ?

ScheduleDefinition doit-elle être distincte de Schedule ?

ExecutionRequest mérite-t-elle réellement un lifecycle ?
```

---

# 141. Invariants architecturaux

## Invariant 1

```text
Entities are identified by explicit IDs.
```

---

## Invariant 2

```text
Value Objects are immutable.
```

---

## Invariant 3

```text
Aggregate boundaries remain small.
```

---

## Invariant 4

```text
Schedule does not own execution history.
```

---

## Invariant 5

```text
Triggers do not perform side effects.
```

---

## Invariant 6

```text
Policies decide; adapters execute.
```

---

## Invariant 7

```text
Domain services do not depend on concrete infrastructure.
```

---

# 142. Anti-pattern : tout mettre en Entity

Il serait incorrect de donner un ID à chaque objet :

```text
DurationId
TimezoneId
CronExpressionId
GracePeriodId
```

si leur identité n'a aucun sens métier.

Cela crée :

```text
complexity
persistence overhead
coupling
```

sans bénéfice.

---

# 143. Anti-pattern : tout mettre en Value Object

À l'inverse :

```text
Schedule
```

ne doit pas être un simple record immutable comparé par valeur.

Son identité persiste malgré les modifications.

---

# 144. Anti-pattern : Aggregate gigantesque

Éviter :

```text
Schedule
├── occurrences
├── executions
├── attempts
├── events
├── logs
└── artifacts
```

Cela rendrait chaque modification coûteuse et fragile.

---

# 145. Anti-pattern : Domain Service omniscient

Éviter :

```text
SchedulingService
```

qui ferait :

```text
create
update
calculate
execute
retry
persist
publish
lock
transform
```

Le service deviendrait un God Object.

---

# 146. Anti-pattern : Value Objects sans comportement

Un Value Object ne doit pas nécessairement être :

```text
@dataclass
value: str
```

sans règles.

Exemple :

```text
CronExpression
```

devrait garantir sa validité.

---

# 147. Exemple conceptuel complet

Besoin :

> Tous les jours à 06:00 Europe/Paris, lancer `daily_orders_pipeline`, sans chevauchement, avec cinq minutes de tolérance.

Modèle :

```text
Schedule [Entity / Aggregate Root]
│
├── ScheduleId("daily-orders")
├── TargetRef("workflow:daily-orders")
├── CronTrigger [Value Object]
│      └── CronExpression("0 6 * * *")
├── Timezone("Europe/Paris")
├── GracePeriod(5 minutes)
├── ForbidOverlap [Policy]
├── ScheduleState.ACTIVE
└── Revision(3)
```

Le trigger produit :

```text
Occurrence [Value Object]

OccurrenceKey(
    schedule_id="daily-orders",
    scheduled_at="2026-09-29T06:00+02:00",
    revision=3
)
```

Puis :

```text
SchedulingEvaluator [Domain Service]
```

produit :

```text
SchedulingDecision(
    EXECUTE,
    reason=ELIGIBLE
)
```

Puis l'application crée :

```text
ExecutionRequest
```

soumise au :

```text
Executor Port
```

---

# 148. Exemple avec misfire

```text
Occurrence
scheduled_at = 08:00

Clock.now()
= 08:15

GracePeriod
= 5 min
```

Le domaine utilise :

```text
MisfirePolicy
```

et produit :

```text
SchedulingDecision(SKIP)
```

ou :

```text
SchedulingDecision(EXECUTE)
```

selon la Policy.

Aucune infrastructure n'est nécessaire pour tester cette décision.

---

# 149. Exemple avec concurrence

Entrées :

```text
Occurrence
ConcurrencyKey
ActiveExecutionSnapshot(count=1)
ForbidOverlap
```

Le Domain Service produit :

```text
SchedulingDecision(SKIP)
reason = OVERLAP_FORBIDDEN
```

Le domaine n'a pas besoin de savoir si l'execution active est stockée dans :

```text
PostgreSQL
Redis
memory
```

---

# 150. Testabilité du modèle

Grâce à cette classification, un test peut construire :

```text
FixedClock
Schedule
Occurrence
Policy
ActiveExecutionSnapshot
```

et appeler :

```text
SchedulingEvaluator
```

sans :

```text
database
threads
network
real time
```

C'est une propriété architecturale importante.

---

# 151. Projection Python future

Sans figer encore l'API :

```python
@dataclass(frozen=True)
class ScheduleId:
    value: str
```

```python
@dataclass(frozen=True)
class GracePeriod:
    duration: timedelta
```

et :

```python
class Schedule: ...
```

avec :

```text
identity
state
behavior
```

Cette différence de représentation doit refléter la différence conceptuelle Entity / Value Object.

---

# 152. Value Objects comme types métier

L'objectif est d'éviter :

```python
schedule_id: str
timezone: str
grace_period: int
cron: str
```

partout.

Préférer :

```text
ScheduleId
Timezone
GracePeriod
CronExpression
```

Cela rend le domaine plus explicite.

---

# 153. Mais éviter la surmodélisation

Il ne faut pas créer un Value Object pour chaque champ trivial.

Exemple :

```text
ScheduleDescription
ScheduleDisplayName
MetadataKey
MetadataValue
```

peuvent rester des types simples si aucune règle métier spécifique ne les justifie.

---

# 154. Critère de création d'un Value Object

Créer un Value Object lorsque :

```text
la valeur possède des invariants

elle apparaît dans plusieurs signatures

elle porte un comportement

elle doit être distinguée d'un type primitif

une confusion serait dangereuse
```

---

# 155. Critère de création d'une Entity

Créer une Entity lorsque :

```text
l'identité compte

l'objet possède un lifecycle

son histoire compte

ses attributs peuvent changer

il doit être référencé indépendamment de ses valeurs
```

---

# 156. Critère de création d'un Domain Service

Créer un Domain Service lorsque :

```text
la logique est réellement métier

elle ne tient naturellement dans aucune Entity ou Value Object

elle combine plusieurs concepts
```

Pas simplement parce que :

```text
"nous avons besoin d'une classe service"
```

---

# 157. Critère de création d'une Policy

Créer une Policy lorsque :

```text
plusieurs comportements sont valides

le comportement est configurable

le choix porte une sémantique métier
```

Exemple parfait :

```text
MisfirePolicy
```

---

# 158. Frontière finale proposée

```text
                 SCHEDULING DOMAIN
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
   Aggregates       Value Objects     Policies
        │               │                │
        │               │                │
     Schedule       Trigger         MisfirePolicy
     Execution?     Occurrence      ConcurrencyPolicy
                   Timezone        RetryPolicy
                   Duration
                   Decision
        │
        └────────────────┬────────────────┘
                         │
                         ▼
                Domain Services
                         │
                 SchedulingEvaluator
                         │
                         ▼
                      Ports
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
      Clock       ScheduleRepository     Executor
```

---

# 159. Modèle de référence retenu

La première version du modèle DDD cible donc :

```text
Schedule
=
Aggregate Root

Trigger
=
Value Object / Strategy

Occurrence
=
Value Object

SchedulingDecision
=
Value Object

MisfirePolicy
=
Policy

ConcurrencyPolicy
=
Policy

SchedulingEvaluator
=
Domain Service

Clock
=
Port

ScheduleRepository
=
Port

Executor
=
Port
```

avec :

```text
Execution
```

maintenue provisoirement comme Entity de frontière dont l'ownership exact sera confirmé plus tard.

---

# 160. Conséquence pour la suite

Nous disposons maintenant de trois niveaux distincts :

```text
VOCABULARY
    ↓
BUSINESS OBJECTS
    ↓
DDD CLASSIFICATION
```

La prochaine étape consiste à relier tous ces objets dans un **Domain Model cohérent**.

---

# Conclusion

La modélisation DDD permet de comprendre que tous les objets du scheduling n'ont pas la même nature.

Les principaux résultats sont :

```text
Schedule
→ Entity + Aggregate Root

Trigger
→ Value Object comportemental

Occurrence
→ Value Object temporel

SchedulingDecision
→ Value Object

Policies
→ stratégies métier

SchedulerEvaluator
→ Domain Service

Clock / Executor / Repository
→ Ports

Execution / Attempt
→ Entities lorsque le runtime appartient au périmètre
```

Cette distinction protège plusieurs qualités fondamentales :

```text
clarté du modèle
testabilité
faible couplage
immutabilité
cohérence des invariants
compatibilité avec le distribué
évolutivité
```

La question centrale n'est donc plus :

> Quelle classe Python dois-je écrire ?

mais :

> Quelle nature possède réellement cet objet dans le domaine ?

C'est cette distinction qui permettra à PyScheduleKit de rester un modèle de scheduling cohérent plutôt qu'un simple ensemble de classes techniques.

---

# Suite documentaire

Le prochain document est :

```text
06_SCHEDULING_DOMAIN_MODEL.md
```

Il devra assembler :

```text
Entities
Value Objects
Aggregates
Policies
Domain Services
Ports
Events
```

dans un modèle cohérent, avec :

```text
relations
cardinalités
flux de décision
frontières d'aggregate
invariants
ownership
dependency directions
```

La question centrale deviendra :

> **Comment tous les objets identifiés jusqu'ici coopèrent-ils pour transformer une règle temporelle en une demande d'exécution contrôlée ?**