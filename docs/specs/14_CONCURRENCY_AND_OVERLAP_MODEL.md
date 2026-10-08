# PyScheduleKit — Concurrency & Overlap Model

**Document :** `14_CONCURRENCY_AND_OVERLAP_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle métier de référence  
**Nature :** Domain Model — Concurrency / Overlap / Admission  
**Prérequis :**
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`
- `11_DATE_INTERVAL_AND_CRON_TRIGGERS.md`
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`

---

# 1. Objectif

Le scheduling ne consiste pas seulement à déterminer :

```text
quand une occurrence devient exigible
```

Il faut aussi décider :

> **Que faire lorsqu'une nouvelle occurrence doit être exécutée alors qu'une exécution précédente est encore active ?**

Exemple :

```text
Schedule
every 5 minutes

Execution 10:00
duration = 8 minutes
```

Timeline :

```text
10:00          10:05          10:08          10:10
  │              │              │              │
  ▼              ▼              ▼              ▼
Run A starts   occurrence B   Run A ends    occurrence C
```

À :

```text
10:05
```

une nouvelle occurrence devient due alors que :

```text
Run A
```

est toujours active.

C'est un :

```text
OVERLAP
```

potentiel.

PyScheduleKit doit déterminer explicitement :

```text
ALLOW
FORBID
QUEUE
REPLACE
COALESCE
```

ou toute autre stratégie définie.

---

# 2. Concept central

Le problème peut se résumer ainsi :

```text
Occurrence
   │
   ▼
ExecutionRequest candidate
   │
   ▼
Are conflicting executions active?
   │
   ├── No
   │    ↓
   │  ADMIT
   │
   └── Yes
        ↓
   ConcurrencyPolicy
        ↓
   AdmissionDecision
```

---

# 3. Concurrency versus Parallelism

Deux concepts doivent être distingués.

```text
Concurrency
=
plusieurs unités de travail existent
dans des périodes temporelles qui se chevauchent
```

```text
Parallelism
=
plusieurs unités de travail
s'exécutent réellement simultanément
```

Un scheduler peut autoriser plusieurs executions concurrentes sans garantir qu'elles seront physiquement parallèles.

---

# 4. Overlap

Un `Overlap` apparaît lorsque :

```text
une nouvelle occurrence
```

devient exécutable alors qu'une execution incompatible est encore dans un état actif.

Exemple :

```text
Execution A
RUNNING

Occurrence B
DUE
```

---

# 5. Overlap n'est pas toujours un problème

Pour certaines tâches :

```text
ALLOW
```

est parfaitement valide.

Exemple :

```text
HTTP health check
```

Une exécution lente ne doit pas nécessairement empêcher la suivante.

---

# 6. Mais parfois l'Overlap est dangereux

Exemples :

```text
database maintenance

monthly accounting close

file compaction

single-writer ETL

stateful synchronization

deployment
```

Deux executions simultanées peuvent produire :

```text
race conditions
duplicates
deadlocks
corrupted state
double billing
```

---

# 7. ConcurrencyPolicy

`ConcurrencyPolicy` répond à :

> **Combien d'exécutions incompatibles peuvent être actives simultanément, et que faire lorsqu'une nouvelle execution dépasse cette limite ?**

Classification :

```text
ConcurrencyPolicy
=
Policy / Value Object comportemental
```

---

# 8. ConcurrencyPolicy appartient au ScheduleDefinition

Deux Schedules pointant vers le même Target peuvent avoir :

```text
des règles de concurrence différentes
```

Exemple :

```text
Schedule A
hourly-refresh
ALLOW

Schedule B
daily-close
FORBID
```

Donc la policy appartient naturellement à :

```text
ScheduleDefinition
```

---

# 9. ConcurrencyKey

Pour décider quelles executions entrent en conflit, il faut répondre :

> **Quelles executions appartiennent au même domaine de concurrence ?**

Cette responsabilité peut être représentée par :

```text
ConcurrencyKey
```

---

# 10. Exemple

```text
Schedule A
daily-customer-refresh

Schedule B
manual-customer-refresh
```

Les deux pourraient utiliser :

```text
ConcurrencyKey("customer-refresh")
```

Ainsi, même s'ils ont deux `ScheduleId` différents :

```text
ils sont considérés comme concurrents
```

---

# 11. Classification

```text
ConcurrencyKey
=
Value Object
```

Il doit être :

```text
immutable
stable
comparable by value
serializable
```

---

# 12. Scope par défaut

Pour un modèle simple :

```text
ConcurrencyKey
=
ScheduleId
```

peut être le comportement par défaut.

Cela signifie :

> Un Schedule ne se concurrence qu'avec lui-même.

---

# 13. Scope partagé

Une configuration avancée peut utiliser :

```text
ConcurrencyKey("warehouse-refresh")
```

pour plusieurs Schedules.

Cela permet :

```text
cross-Schedule concurrency
```

---

# 14. Scope par TargetRef

On pourrait être tenté d'utiliser automatiquement :

```text
TargetRef
```

comme ConcurrencyKey.

Mais ce n'est pas toujours correct.

Deux schedules visant le même Target peuvent parfois s'exécuter ensemble.

La clé doit donc rester explicite.

---

# 15. MaxInstances

Un concept central est :

```text
MaxInstances
```

ou :

```text
ConcurrencyLimit
```

Exemple :

```text
max_instances = 1
```

signifie :

```text
au maximum une execution active
pour cette ConcurrencyKey
```

---

# 16. Classification

```text
ConcurrencyLimit
=
Value Object
```

Invariant :

```text
limit >= 1
```

---

# 17. Active Execution

Il faut définir ce que signifie :

```text
active
```

Une execution peut être :

```text
CREATED
QUEUED
RUNNING
RETRY_WAIT
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

Toutes ne comptent pas nécessairement contre la limite.

---

# 18. ActiveExecutionState

Le modèle doit définir explicitement les états comptabilisés.

Une première proposition :

```text
QUEUED
RUNNING
```

sont actifs.

Selon le runtime :

```text
RETRY_WAIT
```

peut également être compté.

---

# 19. Question importante

Une execution en attente de retry bloque-t-elle une nouvelle occurrence ?

Deux modèles :

```text
YES
```

si elle représente encore un run logique actif.

```text
NO
```

si seules les tentatives physiquement actives comptent.

---

# 20. Recommandation conceptuelle

La concurrence doit s'appliquer à :

```text
Execution
```

et non directement à :

```text
Attempt
```

Une Execution en attente de retry peut donc rester :

```text
logically active
```

selon la policy.

---

# 21. ActiveExecutionSnapshot

Le `SchedulingEvaluator` ne doit pas aller interroger directement la base ou les workers.

Il peut recevoir :

```text
ActiveExecutionSnapshot
```

---

# 22. Structure

```text
ActiveExecutionSnapshot
│
├── concurrency_key
├── active_count
├── execution_refs
├── captured_at
└── maybe states
```

Classification :

```text
Value Object
```

---

# 23. Pourquoi un Snapshot ?

Cela permet au domaine de rester :

```text
deterministic
testable
side-effect free
```

Le calcul devient :

```text
same occurrence
+
same concurrency policy
+
same active snapshot
=
same admission decision
```

---

# 24. Source du Snapshot

Un port applicatif peut fournir :

```text
ExecutionQueryPort
```

capable de répondre :

```text
find_active(concurrency_key)
```

---

# 25. ExecutionQueryPort

Classification :

```text
Port
```

Son implémentation peut utiliser :

```text
SQL
Redis
queue runtime
distributed registry
```

sans que le domaine le sache.

---

# 26. Admission

La nouvelle question devient :

> **Cette ExecutionRequest candidate peut-elle être admise maintenant ?**

Le résultat peut être :

```text
AdmissionDecision
```

---

# 27. AdmissionDecision

Possible structure :

```text
AdmissionDecision
│
├── decision
├── reason
├── concurrency_key
├── active_count
├── limit
└── conflicting_executions
```

Classification :

```text
Value Object
```

---

# 28. AdmissionDecisionType

Une première taxonomie :

```text
ADMIT

REJECT

DEFER

REPLACE

COALESCE
```

---

# 29. ALLOW Policy

`ALLOW` signifie :

```text
aucune restriction d'overlap
```

Conceptuellement :

```text
ADMIT
```

indépendamment du nombre d'executions actives.

---

# 30. Exemple ALLOW

```text
Execution A
10:00 → 10:08

Occurrence B
10:05
```

Avec :

```text
ALLOW
```

on obtient :

```text
Execution A
10:00 ───────────── 10:08

Execution B
      10:05 ───────────── ...
```

Chevauchement autorisé.

---

# 31. FORBID

`FORBID` signifie :

> Ne pas admettre une nouvelle execution lorsqu'une execution incompatible est déjà active.

Avec :

```text
max_instances = 1
```

et :

```text
active_count = 1
```

alors :

```text
REJECT
```

ou :

```text
SKIP
```

selon la sémantique métier retenue.

---

# 32. FORBID pose une question supplémentaire

Une occurrence refusée pour overlap doit-elle :

```text
être perdue
```

ou :

```text
être rejouée plus tard
```

?

Cela distingue :

```text
DROP / SKIP
```

de :

```text
QUEUE / DEFER
```

---

# 33. Donc FORBID seul peut être insuffisant

Il faut souvent distinguer :

```text
OverlapDetection
```

de :

```text
OverflowAction
```

---

# 34. Modèle plus riche

Une policy peut être décrite par :

```text
ConcurrencyPolicy
│
├── limit
└── when_limit_reached
```

avec :

```text
DROP
QUEUE
REPLACE
COALESCE
```

---

# 35. Exemple

```text
ConcurrencyPolicy(
    limit=1,
    overflow=DROP
)
```

signifie :

```text
si une execution est active,
la nouvelle occurrence est ignorée
```

---

# 36. QUEUE

`QUEUE` signifie :

> La demande doit attendre qu'une capacité soit libérée.

Exemple :

```text
10:00 Run A starts
10:05 occurrence B
10:08 Run A ends
10:08 Run B may start
```

---

# 37. Question importante

Une occurrence `QUEUED` conserve :

```text
scheduled_at = 10:05
```

même si elle commence :

```text
10:08
```

---

# 38. QUEUE ne modifie jamais l'occurrence

Il ajoute seulement une attente entre :

```text
ExecutionRequest
```

et :

```text
Execution start
```

---

# 39. Où vit la queue ?

Deux architectures :

```text
scheduler-side pending queue
```

ou :

```text
external executor/worker queue
```

PyScheduleKit ne devrait pas imposer l'implémentation physique.

---

# 40. ConcurrencyPolicy QUEUE

Le domaine décide :

```text
DEFER
```

La couche runtime décide :

```text
comment stocker et réveiller
la request différée
```

---

# 41. REPLACE

`REPLACE` signifie :

> Une nouvelle occurrence remplace une execution incompatible déjà active.

Cela implique potentiellement :

```text
cancel previous
+
admit new
```

---

# 42. REPLACE est beaucoup plus complexe

Il faut savoir :

```text
l'ancienne execution est-elle cancellable ?

la cancellation est-elle synchrone ?

que se passe-t-il si elle refuse ?

quand la nouvelle commence-t-elle ?
```

---

# 43. Recommandation

`REPLACE` ne devrait pas faire partie de V1 tant que le modèle de cancellation d'Execution n'est pas solide.

---

# 44. COALESCE pour overlap

Le mot `COALESCE` peut également apparaître dans la concurrence.

Exemple :

```text
Execution A running

Occurrence B due
Occurrence C due
Occurrence D due
```

On souhaite :

```text
une seule future execution
```

après A.

---

# 45. Attention au vocabulaire

Nous avons déjà défini `Coalescing` pour les misfires.

Ici, il s'agit d'une situation légèrement différente :

```text
overlap coalescing
```

---

# 46. Principe commun

Dans les deux cas :

```text
plusieurs occurrences
→ moins de requests
```

Mais la cause diffère :

```text
Misfire Coalescing
→ scheduler absent / retard

Overlap Coalescing
→ capacity/concurrency saturation
```

---

# 47. Recommendation

Réutiliser éventuellement le même objet générique :

```text
OccurrenceCoalescingPolicy
```

mais conserver des :

```text
DecisionReason
```

différents.

---

# 48. QUEUE_ALL

Une policy possible :

```text
QUEUE_ALL
```

conserve chaque occurrence.

Exemple :

```text
10:05
10:10
10:15
```

attendent toutes.

---

# 49. COALESCE_LATEST

Une autre policy :

```text
COALESCE_LATEST
```

conserve uniquement l'occurrence la plus récente en attente.

---

# 50. Exemple cache refresh

```text
refresh cache every minute
```

Si un refresh dure cinq minutes :

```text
rejouer quatre refreshs intermédiaires
```

peut être inutile.

Une policy :

```text
COALESCE_LATEST
```

est pertinente.

---

# 51. Exemple partition processing

À l'inverse :

```text
process hourly partition
```

chaque occurrence peut être nécessaire.

Une policy :

```text
QUEUE_ALL
```

est plus appropriée.

---

# 52. Concurrency n'est donc pas seulement technique

Le choix dépend de :

```text
la sémantique du travail
```

PyScheduleKit doit exposer la policy, pas imposer une réponse universelle.

---

# 53. MaxInstances > 1

La concurrence ne se limite pas à :

```text
0 ou 1
```

Exemple :

```text
max_instances = 3
```

permet trois executions actives simultanément.

---

# 54. Exemple

```text
active_count = 2
limit = 3
```

Nouvelle request :

```text
ADMIT
```

---

# 55. Puis

```text
active_count = 3
limit = 3
```

Nouvelle request :

```text
overflow policy
```

s'applique.

---

# 56. ConcurrencyPolicy générale

On peut donc modéliser :

```text
ConcurrencyPolicy
│
├── limit
├── key
└── overflow_strategy
```

---

# 57. Mais key peut rester dans ScheduleDefinition

Alternative :

```text
ScheduleDefinition
├── ConcurrencyKey
└── ConcurrencyPolicy
```

avec :

```text
ConcurrencyPolicy
├── limit
└── overflow
```

Cette séparation est probablement plus propre.

---

# 58. V1 recommandé

```text
ConcurrencyPolicy
├── Allow
└── Limit(
      max_instances,
      overflow
   )
```

---

# 59. OverflowStrategy

```text
DROP
QUEUE
COALESCE_LATEST
```

pour V1.

`REPLACE` peut attendre.

---

# 60. DROP

La nouvelle occurrence n'est pas exécutée.

Mais il faut conserver :

```text
evidence
```

du rejet.

---

# 61. Event possible

```text
OccurrenceRejectedForConcurrency
```

avec :

```text
OccurrenceKey
ConcurrencyKey
active_count
limit
```

---

# 62. DROP versus Misfire SKIP

Ils produisent tous deux :

```text
aucune execution
```

mais les raisons diffèrent.

```text
MISFIRE_SKIP
```

versus :

```text
CONCURRENCY_DROP
```

Cette distinction doit être observable.

---

# 63. QUEUE

Une request est conservée pour admission ultérieure.

Elle doit avoir :

```text
scheduled_at
created_at
queued_at
```

distincts.

---

# 64. Queue delay

```text
queue_delay
=
started_at - queued_at
```

---

# 65. Scheduling delay

```text
total_start_lag
=
started_at - scheduled_at
```

Les deux métriques sont différentes.

---

# 66. DeferredAdmission

Il peut être utile d'avoir :

```text
AdmissionDecision.DEFER
```

plutôt que de dire :

```text
ADMIT into queue
```

selon le modèle.

---

# 67. Deux couches possibles

```text
Schedule admission
```

puis :

```text
Executor queue admission
```

La terminologie devra rester claire.

---

# 68. Recommendation

Dans PyScheduleKit :

```text
Admission
```

signifie :

> La policy autorise-t-elle la création ou la conservation d'une execution logique ?

L'Executor peut ensuite avoir sa propre queue technique.

---

# 69. Scheduler queue versus executor queue

```text
Scheduler queue
→ attente due à la policy de scheduling

Executor queue
→ attente due à la capacité runtime
```

À ne pas confondre.

---

# 70. Active count

La valeur :

```text
active_count
```

doit être évaluée au moment d'une décision.

---

# 71. Same-now principle

Le snapshot de concurrence doit appartenir au même :

```text
SchedulingEvaluationContext
```

que :

```text
now
```

autant que possible.

---

# 72. SchedulingEvaluationContext

Il peut contenir :

```text
now
Occurrence
ActiveExecutionSnapshot
ScheduleRevision
```

et autres données nécessaires.

---

# 73. Determinism

Pour :

```text
same occurrence
same policy
same active snapshot
```

on doit obtenir :

```text
same AdmissionDecision
```

---

# 74. Mais le monde peut changer après la décision

Entre :

```text
evaluate
```

et :

```text
persist
```

une autre execution peut être admise.

C'est une race condition.

---

# 75. Exemple

Node A :

```text
active_count = 0
→ ADMIT
```

Node B au même moment :

```text
active_count = 0
→ ADMIT
```

Avec :

```text
limit = 1
```

les deux pensent être autorisés.

---

# 76. Donc le Domain Snapshot ne suffit pas

Il faut également une :

```text
atomic admission mechanism
```

au niveau infrastructure/persistence.

---

# 77. Separation

```text
Domain
→ should this request be admissible?

Infrastructure
→ ensure the admission is serialized atomically
```

---

# 78. Local process

Dans un scheduler mono-process :

```text
mutex
```

peut suffire.

---

# 79. Multi-process

On peut utiliser :

```text
database transaction
row locking
advisory lock
```

selon l'architecture.

---

# 80. Distributed scheduler

On peut utiliser :

```text
Lease
Distributed Lock
Atomic Counter
Database constraint
```

ou combinaison.

---

# 81. Lease

Une `Lease` peut représenter :

```text
temporary ownership
```

d'une ressource de concurrence.

---

# 82. Exemple

```text
resource_key:
concurrency:customer-refresh

owner:
scheduler-node-2

expires_at:
...
```

---

# 83. Mais Lease ≠ ConcurrencyPolicy

La Lease répond :

```text
qui possède le droit temporaire ?
```

La ConcurrencyPolicy répond :

```text
combien d'executions peuvent coexister ?
```

---

# 84. Pour max_instances=1

Une Lease peut implémenter efficacement :

```text
FORBID_OVERLAP
```

mais ce n'est qu'une stratégie infrastructure.

---

# 85. Pour max_instances > 1

Une simple Lease unique ne suffit plus nécessairement.

On peut utiliser :

```text
semaphore
counter
slots
```

---

# 86. Concurrency Slot

Une abstraction infrastructure possible :

```text
ConcurrencySlot
```

avec :

```text
N slots
```

par `ConcurrencyKey`.

---

# 87. Domain should not require slots

Le domaine ne doit connaître que :

```text
limit
active_count
```

L'implémentation peut utiliser des slots ou autre chose.

---

# 88. Atomic admission

Pseudo-flow :

```text
BEGIN

lock concurrency key

count active executions

apply policy

if admitted:
    create execution/request

COMMIT
```

---

# 89. Pourquoi transaction

Pour garantir :

```text
check + create
```

comme une seule opération logique.

---

# 90. Alternative optimistic model

On peut aussi :

```text
attempt insert
```

avec contrainte/lock puis gérer :

```text
conflict
```

Mais la stratégie dépend de la persistance.

---

# 91. Concurrency invariant cross-aggregate

`Schedule` ne peut pas protéger seul :

```text
max active executions <= limit
```

car les executions sont dans un autre aggregate/store.

---

# 92. C'est donc un invariant cross-aggregate

Il nécessite :

```text
Policy
+
Query/Snapshot
+
Atomic application service/infrastructure
```

---

# 93. Important DDD insight

Tous les invariants métier ne peuvent pas être protégés par une seule Aggregate Root.

Il faut parfois :

```text
Domain Service
+
transactional coordination
```

---

# 94. ConcurrencyEvaluator

Un service possible :

```text
ConcurrencyEvaluator
```

Classification :

```text
Domain Service
```

---

# 95. Input

```text
Occurrence
ConcurrencyPolicy
ActiveExecutionSnapshot
```

---

# 96. Output

```text
AdmissionDecision
```

---

# 97. Application service

La couche application peut :

```text
load active snapshot
evaluate
attempt atomic admission
persist request/execution
publish event
```

---

# 98. Admission race handling

Si l'état change après le snapshot :

```text
AdmissionConflict
```

peut provoquer :

```text
re-evaluate
```

---

# 99. Retry of admission

Attention :

```text
retry admission
```

n'est pas le même concept que :

```text
retry failed execution
```

---

# 100. Vocabulaire recommandé

Utiliser :

```text
AdmissionRetry
```

ou simplement :

```text
re-evaluation
```

pour éviter la confusion.

---

# 101. Overlap detection

L'Overlap est détecté si :

```text
active_count >= limit
```

pour la clé concernée.

---

# 102. Avec ALLOW

Il n'y a conceptuellement pas de limite utile.

On peut représenter :

```text
Unlimited
```

au lieu d'un grand nombre arbitraire.

---

# 103. UnlimitedConcurrency

Un Value Object ou policy spécifique :

```text
AllowConcurrency
```

est plus clair que :

```text
limit = 999999
```

---

# 104. Queue semantics

Une occurrence mise en queue peut attendre longtemps.

Question :

> Peut-elle expirer ?

---

# 105. Queue deadline

Une `ExecutionRequest` peut avoir :

```text
deadline
```

ou :

```text
admission_deadline
```

au-delà de laquelle elle est abandonnée.

---

# 106. Exemple

```text
Occurrence 10:00

blocked until 12:00
```

Si le travail n'est plus pertinent après :

```text
10:30
```

la request doit probablement expirer.

---

# 107. Concurrency + GracePeriod

La GracePeriod initiale s'applique-t-elle seulement au déclenchement ou aussi à l'attente de concurrence ?

Question importante.

---

# 108. Deux modèles

### Model A

```text
grace period
```

sert uniquement à détecter un misfire avant admission.

Une fois admise/queued, la request peut attendre.

### Model B

La deadline continue de s'appliquer :

```text
si elle n'a pas démarré avant deadline
→ expire
```

---

# 109. Recommandation

Distinguer :

```text
SchedulingDeadline
```

de :

```text
ExecutionStartDeadline
```

si les deux besoins apparaissent.

Ne pas surcharger `GracePeriod`.

---

# 110. V1 simplification

La GracePeriod peut rester liée à :

```text
scheduling eligibility
```

et QUEUE peut avoir sa propre policy d'expiration future.

---

# 111. Queue starvation

Une request ancienne peut être continuellement repoussée par de nouvelles requests.

Il faut donc définir :

```text
queue ordering
```

---

# 112. FIFO

Ordre naturel :

```text
oldest scheduled_at first
```

préserve la chronologie.

---

# 113. Latest wins

Pour certains jobs :

```text
latest state only
```

on peut préférer remplacer/coalescer les anciennes requests.

---

# 114. Priority

Un futur modèle peut introduire :

```text
Priority
```

mais cela augmente fortement la complexité.

À repousser hors V1.

---

# 115. Queue ordering recommended V1

```text
FIFO by scheduled_at
```

pour les requests conservées.

---

# 116. Concurrency + Catch-Up

Après une panne :

```text
09:00
10:00
11:00
```

peuvent être planifiées en catch-up.

Avec :

```text
max_instances = 1
```

elles ne doivent pas nécessairement démarrer simultanément.

---

# 117. Recommended flow

```text
CatchUpPlanner
→ identifies requests

ConcurrencyEvaluator
→ controls admission

Executor
→ runs admitted work
```

---

# 118. Catch-up can produce queue

Exemple :

```text
3 recovery requests
```

puis :

```text
1 running
2 queued
```

---

# 119. Concurrency + Coalescing

Le coalescing peut être appliqué :

```text
avant l'admission
```

afin de réduire la pression.

---

# 120. Exemple

```text
10 pending occurrences
```

avec :

```text
COALESCE_LATEST
```

deviennent :

```text
1 request
```

avant la concurrence.

---

# 121. Normal scheduling versus catch-up

La même `ConcurrencyPolicy` devrait idéalement s'appliquer aux deux.

Sinon le système devient difficile à expliquer.

---

# 122. Exception possible

Une future policy peut distinguer :

```text
normal_limit
recovery_limit
```

mais seulement si un besoin concret existe.

---

# 123. Concurrency + Retry

Supposons :

```text
Execution A
FAILED
waiting for retry
```

Nouvelle occurrence B arrive.

Est-ce qu'A compte comme active ?

---

# 124. Cette question dépend du modèle Execution

Si A est toujours :

```text
ExecutionStatus = RETRY_WAIT
```

on peut considérer qu'elle occupe toujours son slot logique.

---

# 125. Pourquoi ?

Sinon :

```text
A retry pending
B starts
```

puis :

```text
A retry starts
```

créant finalement deux executions logiquement concurrentes.

---

# 126. Recommandation

Pour un modèle `max_instances` portant sur des Executions logiques :

```text
RETRY_WAIT
```

compte comme active.

---

# 127. Alternative

Si la concurrence porte uniquement sur l'utilisation physique des workers :

```text
RETRY_WAIT
```

ne devrait pas compter.

Mais ce serait alors plutôt une policy de runtime capacity qu'une policy de scheduling.

---

# 128. PyScheduleKit doit viser la concurrence logique

C'est-à-dire :

```text
combien de runs métier
de cette clé peuvent être ouverts ?
```

pas :

```text
combien de CPU threads ?
```

---

# 129. Resource capacity

La capacité physique appartient à :

```text
Executor
Worker Pool
Infrastructure
```

---

# 130. ConcurrencyPolicy ≠ ResourceScheduler

PyScheduleKit ne doit pas devenir :

```text
Kubernetes scheduler
CPU scheduler
worker autoscaler
```

---

# 131. Completion and slot release

Un slot logique est libéré lorsque l'Execution atteint un état terminal :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

selon le modèle.

---

# 132. Failed with retry available

Si un retry est encore prévu :

```text
Execution
```

n'est probablement pas terminale.

Donc le slot reste occupé.

---

# 133. Attempt failure

Un `Attempt` qui échoue ne libère pas nécessairement le slot.

Encore une raison de définir la concurrence au niveau :

```text
Execution
```

---

# 134. Cancellation

Lorsqu'une Execution est :

```text
CANCELLING
```

compte-t-elle encore comme active ?

Recommandation :

```text
oui
```

jusqu'à état réellement terminal.

---

# 135. Zombie execution

Un worker peut disparaître sans marquer l'Execution terminale.

Le scheduler peut alors croire :

```text
slot occupied forever
```

---

# 136. Il faut donc une stratégie de liveness

Par exemple :

```text
execution heartbeat
lease
timeout
reconciliation
```

---

# 137. Mais ce problème est runtime

La ConcurrencyPolicy peut seulement consommer :

```text
ActiveExecutionSnapshot
```

La qualité de ce snapshot dépend du runtime/reconciliation.

---

# 138. Execution stale detection

Une future policy/runtime peut marquer :

```text
stale execution
```

et libérer le slot.

À traiter dans un document runtime/recovery.

---

# 139. Schedule cancellation

Si un Schedule est annulé pendant qu'une Execution est active :

```text
Cancel Schedule
≠
Cancel Execution
```

La concurrence de cette execution reste active tant qu'elle n'est pas terminale.

---

# 140. New occurrences after cancellation

Il n'y en a plus.

Donc aucune nouvelle admission ne devrait être évaluée.

---

# 141. Reschedule

Si un Schedule est reschedulé pendant qu'une Execution de l'ancienne revision est active :

```text
compte-t-elle contre la même ConcurrencyKey ?
```

---

# 142. Par défaut oui

Si la clé reste :

```text
identique
```

l'ancienne execution compte toujours.

La concurrence doit porter sur :

```text
ConcurrencyKey
```

et non uniquement sur :

```text
ScheduleRevision
```

---

# 143. Si la clé change

Un reschedule pourrait introduire une nouvelle :

```text
ConcurrencyKey
```

Alors les nouvelles occurrences ne seraient plus en conflit avec les anciennes selon le modèle.

Cela doit être considéré comme un changement métier significatif.

---

# 144. ScheduleRevision

Modifier :

```text
ConcurrencyPolicy
```

ou :

```text
ConcurrencyKey
```

doit donc :

```text
ScheduleRevision += 1
```

---

# 145. Cross-Schedule example

```text
Schedule A
daily-import
ConcurrencyKey = data-import

Schedule B
manual-import
ConcurrencyKey = data-import
```

Si A est running :

```text
B
```

est soumis à la même policy de concurrence.

---

# 146. Qui porte la policy en cas de deux Schedules ?

Question subtile.

Schedule A peut dire :

```text
limit = 1
```

et B :

```text
limit = 3
```

pour la même clé.

C'est incohérent.

---

# 147. ConcurrencyKey shared configuration problem

Une clé partagée devrait idéalement avoir :

```text
une policy cohérente
```

---

# 148. Deux modèles possibles

### Model A

Policy portée par chaque Schedule mais validation exige cohérence.

### Model B

Créer un objet partagé :

```text
ConcurrencyProfile
```

référencé par plusieurs schedules.

---

# 149. V1 recommendation

Éviter les clés partagées complexes au début.

Définir :

```text
default scope = ScheduleId
```

et permettre `ConcurrencyKey` custom comme fonctionnalité avancée, avec exigence documentaire de cohérence.

---

# 150. Future ConcurrencyProfile

À terme :

```text
ConcurrencyProfile
│
├── ConcurrencyKey
├── limit
└── overflow
```

pourrait être référencé par plusieurs schedules.

---

# 151. But don't over-model V1

Pour l'apprentissage initial :

```text
ScheduleDefinition
├── concurrency_key?
└── concurrency_policy
```

suffit.

---

# 152. Per-target mutex

Un cas pratique :

```text
ConcurrencyKey(TargetRef)
```

peut être proposé via helper :

```text
forbid_overlap_per_target()
```

sans devenir le default implicite.

---

# 153. AdmissionDecision example

```text
Occurrence:
10:05

ConcurrencyKey:
daily-orders

Policy:
limit=1
overflow=DROP

Snapshot:
active_count=1

Decision:
REJECT

Reason:
CONCURRENCY_LIMIT_REACHED
```

---

# 154. QUEUE example

Même contexte :

```text
overflow=QUEUE
```

Decision :

```text
DEFER
```

---

# 155. ALLOW example

Policy :

```text
AllowConcurrency
```

Decision :

```text
ADMIT
```

---

# 156. COALESCE example

Pending :

```text
10:05
10:10
10:15
```

avec :

```text
COALESCE_LATEST
```

résultat :

```text
keep 10:15
```

avec evidence des deux précédentes.

---

# 157. AdmissionReason enum

Possibles :

```text
NO_CONFLICT

BELOW_LIMIT

LIMIT_REACHED_DROP

LIMIT_REACHED_QUEUE

LIMIT_REACHED_COALESCE

REPLACEMENT_REQUIRED
```

---

# 158. Rejection is not failure

Une occurrence rejetée par ConcurrencyPolicy :

```text
n'est pas une execution échouée
```

Aucune execution n'a forcément été créée.

---

# 159. Therefore

```text
Concurrency rejection
≠
Execution failure
```

---

# 160. Concurrency rejection ≠ Misfire

Au moment de l'évaluation, l'occurrence peut être parfaitement à l'heure.

Elle est rejetée à cause :

```text
d'une execution concurrente
```

---

# 161. Mais elle peut devenir misfire plus tard

Si elle est `QUEUED` ou `DEFERRED` longtemps, une autre policy temporelle peut éventuellement s'appliquer.

Cela doit être explicite.

---

# 162. Recommended V1

Une occurrence :

```text
DROP
```

est définitivement ignorée.

Une occurrence :

```text
QUEUE
```

est conservée comme ExecutionRequest et n'est plus reclassifiée comme misfire.

Cela simplifie fortement le modèle.

---

# 163. Why?

La décision de scheduling a déjà été prise.

Le problème devient :

```text
queue latency
```

plutôt que :

```text
missed scheduling occurrence
```

---

# 164. Request lifecycle

Une request peut donc avoir :

```text
CREATED
QUEUED
ADMITTED
DISPATCHED
CANCELLED
EXPIRED
```

selon le niveau de détail retenu.

---

# 165. Avoid too many states

V1 peut rester :

```text
PENDING
QUEUED
DISPATCHED
CANCELLED
```

ou déléguer davantage à Execution.

---

# 166. ExecutionRequest versus Execution

Si une request est queued mais qu'aucun worker n'a commencé :

```text
Execution
```

existe-t-elle déjà ?

Deux modèles sont possibles.

---

# 167. Model A

```text
Execution created at admission
```

même avant démarrage.

Alors :

```text
QUEUED
```

est un ExecutionStatus.

---

# 168. Model B

```text
ExecutionRequest queued
```

et `Execution` n'est créée qu'au démarrage.

---

# 169. Recommendation

Le choix doit rester cohérent avec le futur document Execution Model.

Pour la concurrence, seule compte la définition claire de :

```text
quelles unités occupent un slot logique
```

---

# 170. Concurrency and queue depth

Une policy QUEUE sans limite peut produire :

```text
un backlog infini
```

---

# 171. Queue limit

On peut ajouter :

```text
max_pending
```

ou :

```text
queue_capacity
```

---

# 172. Example

```text
max_instances = 1
max_pending = 10
```

La 11e occurrence peut :

```text
DROP
COALESCE
FAIL
```

selon policy.

---

# 173. V1 simplification

Ne pas introduire `max_pending` immédiatement.

Utiliser :

```text
QUEUE
```

avec un hard safety limit runtime.

---

# 174. Runtime safety limit

Comme pour catch-up :

```text
domain policy
```

et :

```text
runtime protection
```

doivent rester distincts.

---

# 175. Queue storm

Schedule :

```text
every second
```

Task duration :

```text
10 minutes
```

Policy :

```text
max_instances = 1
QUEUE_ALL
```

Produit :

```text
600 pending requests
```

en dix minutes.

---

# 176. Therefore

`QUEUE_ALL` n'est pas toujours sûr.

Les docs doivent rendre visible cette conséquence.

---

# 177. Coalescing can protect

Pour un job latest-state :

```text
COALESCE_LATEST
```

évite cette croissance.

---

# 178. Backpressure

Une autre stratégie runtime peut :

```text
pause schedule evaluation
```

temporairement.

Mais cela modifie la sémantique temporelle et peut créer des misfires.

À traiter séparément.

---

# 179. Concurrency metrics

Métriques utiles :

```text
active_execution_count

concurrency_limit

overlap_detected_count

admission_rejected_count

admission_deferred_count

coalesced_due_to_concurrency_count

concurrency_queue_depth

concurrency_wait_seconds
```

---

# 180. Scheduling observability

Chaque décision doit pouvoir expliquer :

```text
OccurrenceKey

ConcurrencyKey

Policy

Limit

Active count

Conflicting executions

Decision

Reason
```

---

# 181. Example diagnostic

```text
Schedule:
daily-orders

Occurrence:
2026-10-04T10:05Z

ConcurrencyKey:
daily-orders

Policy:
limit=1
overflow=QUEUE

Active executions:
1

Decision:
DEFER

Conflicting Execution:
exec-123
```

---

# 182. Domain events possibles

```text
OverlapDetected

ExecutionAdmissionGranted

ExecutionAdmissionRejected

ExecutionAdmissionDeferred

OccurrencesCoalescedForConcurrency
```

---

# 183. Avoid noisy events

Si une tâche très fréquente est bloquée pendant longtemps :

```text
des milliers d'OverlapDetected
```

peuvent produire trop de bruit.

On peut agréger certaines observations.

---

# 184. Audit event versus metric

```text
business-significant decision
→ event/log
```

```text
high-volume count
→ metric
```

---

# 185. Distributed race event

Si une admission échoue parce qu'un autre node a gagné la course :

```text
AdmissionConflict
```

peut être un événement technique, pas nécessairement métier.

---

# 186. Property tests

Pour `Allow` :

```text
any active_count
→ ADMIT
```

---

# 187. Limit tests

Pour :

```text
limit = N
```

si :

```text
active_count < N
```

alors :

```text
ADMIT
```

---

# 188. At limit

Si :

```text
active_count >= N
```

alors l'overflow strategy s'applique.

---

# 189. Determinism test

```text
same policy
same snapshot
same occurrence
→ same decision
```

---

# 190. Invalid limit

```text
max_instances = 0
```

doit être rejeté.

---

# 191. Invalid concurrency key

Une clé vide ou non valide doit être rejetée à la construction.

---

# 192. Queue ordering test

Pour :

```text
09:00
10:00
11:00
```

en FIFO :

```text
09:00
```

doit être admise avant les autres.

---

# 193. Coalescing test

Input :

```text
09:00
10:00
11:00
```

Strategy :

```text
LATEST
```

Output :

```text
11:00
```

avec evidence des trois.

---

# 194. Cross-Schedule test

Deux schedules avec la même `ConcurrencyKey` doivent partager le même active count.

---

# 195. Revision test

Une ancienne execution de revision 1 compte toujours si :

```text
ConcurrencyKey
```

est identique à celle de revision 2.

---

# 196. Retry-wait test

Si V1 considère :

```text
RETRY_WAIT
```

actif, il doit compter dans le snapshot.

---

# 197. Cancellation test

Une execution `CANCELLING` doit rester active jusqu'à confirmation terminale.

---

# 198. Stale snapshot test

Si l'admission atomique détecte que :

```text
active count changed
```

depuis le snapshot, la décision doit être recalculée ou rejetée proprement.

---

# 199. Anti-pattern — concurrency via Trigger

Éviter :

```text
Trigger.next_after()
```

qui dépend de la présence d'une execution active.

Le Trigger doit rester temporel.

---

# 200. Anti-pattern — skip hidden in executor

L'Executor ne doit pas décider silencieusement :

```text
job already running → ignore
```

sans que le scheduling domain puisse l'observer.

---

# 201. Anti-pattern — global mutex

Un verrou global :

```text
one execution in entire scheduler
```

est rarement la bonne abstraction.

Utiliser une clé de concurrence explicite.

---

# 202. Anti-pattern — ConcurrencyKey = mutable name

Éviter une clé basée sur :

```text
display name
```

modifiable.

Préférer une valeur stable.

---

# 203. Anti-pattern — using worker count as concurrency policy

```text
workers = 4
```

ne signifie pas :

```text
max_instances = 4 for this Schedule
```

Ce sont deux domaines différents.

---

# 204. Anti-pattern — DB query only, no atomic admission

```text
SELECT active_count
if 0:
   INSERT execution
```

sans transaction/lock est race-prone.

---

# 205. Anti-pattern — max_instances checked per node

Dans un système distribué :

```text
Node A active_count=0 locally
Node B active_count=0 locally
```

n'est pas une vue globale correcte.

---

# 206. Anti-pattern — REPLACE without cancellation semantics

Ne pas introduire :

```text
REPLACE
```

avant d'avoir défini précisément :

```text
cancel
termination
timeout
acknowledgement
```

---

# 207. Anti-pattern — queued occurrence loses scheduled_at

Une request mise en attente ne devient pas une nouvelle occurrence.

---

# 208. Anti-pattern — queued request considered retry

Elle n'a pas échoué.

Elle attend une admission/capacité.

---

# 209. Anti-pattern — coalescing without evidence

Comme pour misfire coalescing, conserver la provenance.

---

# 210. Anti-pattern — shared ConcurrencyKey with inconsistent policies

Deux schedules ne doivent pas interpréter la même clé de façon contradictoire.

---

# 211. Recommended Domain Objects

```text
ConcurrencyKey [VO]

ConcurrencyLimit [VO]

ConcurrencyPolicy [Policy]

OverflowStrategy [VO/Enum]

ActiveExecutionSnapshot [VO]

AdmissionDecision [VO]

ConcurrencyEvaluator [Domain Service]
```

---

# 212. Ports

```text
ExecutionQueryPort
```

pour obtenir l'état actif.

Éventuellement :

```text
ConcurrencyCoordinator
```

comme port application/infrastructure pour l'admission atomique.

---

# 213. ConcurrencyCoordinator

Responsabilité possible :

```text
attempt_admission(
    concurrency_key,
    limit,
    request
)
```

avec résultat :

```text
ADMITTED / CONFLICT
```

---

# 214. Mais ne pas dupliquer la Policy

Le Coordinator garantit :

```text
atomicité
```

Il ne doit pas réinventer :

```text
la décision métier
```

---

# 215. Application flow proposé

```text
Occurrence
   │
   ▼
SchedulingDecision
   │
   ▼
ExecutionRequest candidate
   │
   ▼
ExecutionQueryPort
   │
   ▼
ActiveExecutionSnapshot
   │
   ▼
ConcurrencyEvaluator
   │
   ▼
AdmissionDecision
   │
   ├── ADMIT
   ├── DROP
   ├── QUEUE
   └── COALESCE
```

---

# 216. Distributed finalization

Pour `ADMIT` :

```text
ConcurrencyCoordinator
   │
   ▼
atomic slot acquisition
   │
   ▼
persist request/execution
```

---

# 217. Possible two-step decision

```text
Domain Decision
=
ADMIT_IF_SLOT_AVAILABLE
```

puis :

```text
Infrastructure result
=
slot acquired / lost race
```

---

# 218. Race lost

Si slot perdu :

```text
re-evaluate overflow strategy
```

ou :

```text
DEFER
```

selon architecture.

---

# 219. Simpler V1

En mono-process / SQLite / local runtime :

```text
single transactional scheduler loop
```

peut éviter une grande partie de cette complexité.

Mais le modèle ne doit pas empêcher une évolution distribuée.

---

# 220. Learning progression

PyScheduleKit peut implémenter la concurrence par étapes.

---

# 221. Phase 1

```text
single process

ConcurrencyKey = ScheduleId

ALLOW
FORBID/DROP
```

---

# 222. Phase 2

```text
QUEUE
max_instances > 1
ActiveExecutionSnapshot
```

---

# 223. Phase 3

```text
shared keys
coalescing
distributed atomic admission
leases/semaphores
```

---

# 224. Phase 4

```text
REPLACE
advanced cancellation
distributed reconciliation
```

---

# 225. V1 recommendation

Pour la première implémentation réelle :

```text
ConcurrencyPolicy
│
├── Allow
└── Limit
      ├── max_instances
      └── overflow:
            DROP
            QUEUE
```

Puis ajouter :

```text
COALESCE_LATEST
```

si besoin.

---

# 226. Why not only Boolean allow_overlap?

Un simple :

```text
allow_overlap: bool
```

ne permet pas de représenter :

```text
max_instances = 3

queue when full

coalesce latest
```

---

# 227. But API sugar may expose it

Une API simple :

```python
forbid_overlap = True
```

peut être transformée en interne en :

```text
ConcurrencyPolicy(
    max_instances=1,
    overflow=DROP
)
```

---

# 228. Domain remains richer

Le sucre API ne doit pas limiter le modèle.

---

# 229. Example — one-at-a-time

```text
Target:
daily-close

Schedule:
every hour

Concurrency:
max_instances = 1
overflow = QUEUE
```

Si un run dure 90 minutes :

```text
10:00 starts
11:00 queued
11:30 first ends
11:30 second starts
12:00 queued
```

---

# 230. Example — drop overlap

Même cas :

```text
overflow = DROP
```

Résultat :

```text
10:00 runs
11:00 dropped
12:00 maybe admitted
```

si 10:00 est terminée avant 12:00.

---

# 231. Example — allow

```text
10:00 starts
11:00 starts
12:00 starts
```

sans restriction.

---

# 232. Example — max 3

```text
limit = 3
```

peut autoriser :

```text
Run A
Run B
Run C
```

mais la prochaine request subit l'overflow strategy.

---

# 233. Example — cross Schedule

```text
Schedule A:
automatic export

Schedule B:
manual export

ConcurrencyKey:
exports/customer-42

limit=1
```

Un export manuel peut attendre la fin de l'automatique.

---

# 234. Example — coalesce latest

Schedule :

```text
refresh dashboard every minute
```

Refresh prend :

```text
5 minutes
```

Pendant son exécution :

```text
10:01
10:02
10:03
10:04
```

arrivent.

Policy :

```text
COALESCE_LATEST
```

Après completion :

```text
seule 10:04
```

est conservée.

---

# 235. scheduled_at remains 10:04

Elle ne devient pas :

```text
10:05
```

simplement parce qu'elle commence après le run courant.

---

# 236. Queue + catch-up example

Scheduler restart avec :

```text
3 missed occurrences
```

Catch-up crée :

```text
09:00
10:00
11:00
```

Concurrency limit=1.

Le système peut :

```text
run 09:00
queue 10:00
queue 11:00
```

---

# 237. Coalescing interaction

Avec `COALESCE_LATEST` :

```text
09:00
10:00
11:00
```

peuvent devenir :

```text
11:00
```

avant même l'admission.

---

# 238. Ordering of policies

Une chaîne recommandée :

```text
Trigger
   ↓
Occurrence
   ↓
Misfire/Catch-Up
   ↓
Coalescing
   ↓
Concurrency
   ↓
Admission
   ↓
Execution
```

---

# 239. Why concurrency after misfire recovery?

Parce que le recovery détermine :

```text
quelles requests devraient exister
```

puis la concurrence détermine :

```text
lesquelles peuvent être actives
```

---

# 240. Current occurrence versus backlog

Un backlog peut être en attente lorsqu'une occurrence fraîche arrive.

Question :

> Qui passe en premier ?

---

# 241. Default recommendation

Pour le même Schedule :

```text
oldest scheduled_at first
```

préserve la progression temporelle.

---

# 242. But latest-state jobs

Ils peuvent préférer coalescing plutôt qu'un backlog FIFO.

La policy doit refléter ce choix.

---

# 243. Fairness

Avec plusieurs Schedules sur une même clé :

```text
un schedule très fréquent
```

peut monopoliser la capacité.

---

# 244. Fairness policy

Des concepts comme :

```text
round-robin
weighted fairness
priority
```

sont possibles mais hors scope V1.

---

# 245. Why outside V1?

Ils rapprocheraient PyScheduleKit d'un :

```text
general resource scheduler
```

ce qui n'est pas son objectif initial.

---

# 246. Deadlocks

Si une execution devait acquérir plusieurs ConcurrencyKeys :

```text
A then B
```

et une autre :

```text
B then A
```

on pourrait créer un deadlock.

---

# 247. V1 recommendation

Une ExecutionRequest ne possède qu'une :

```text
ConcurrencyKey
```

principale.

Les multi-resource locks sont hors scope.

---

# 248. Hierarchical keys

Des clés :

```text
tenant:1
tenant:1:dataset:42
```

peuvent sembler utiles.

Mais les règles hiérarchiques de conflit deviennent complexes.

À différer.

---

# 249. Key normalization

Une ConcurrencyKey doit avoir une représentation canonique.

Exemple :

```text
customer-refresh
```

et non des variantes incohérentes :

```text
CustomerRefresh
customer_refresh
customer-refresh
```

si elles représentent le même scope.

---

# 250. But framework shouldn't infer semantics

La normalisation syntaxique est acceptable.

La fusion sémantique automatique ne l'est pas.

---

# 251. Serialization

Exemple `Allow` :

```json
{
  "kind": "allow"
}
```

---

# 252. Serialization limit/drop

```json
{
  "kind": "limit",
  "max_instances": 1,
  "overflow": "drop"
}
```

---

# 253. Serialization queue

```json
{
  "kind": "limit",
  "max_instances": 1,
  "overflow": "queue"
}
```

---

# 254. ConcurrencyKey serialized separately

```json
{
  "concurrency_key": "daily-orders"
}
```

dans la `ScheduleDefinition`.

---

# 255. Validation

Refuser :

```text
max_instances < 1
```

---

# 256. Unknown overflow

Refuser :

```text
overflow = "teleport"
```

avec :

```text
UnsupportedOverflowStrategy
```

---

# 257. Error model

Possibles :

```text
InvalidConcurrencyPolicy

InvalidConcurrencyLimit

InvalidConcurrencyKey

UnsupportedOverflowStrategy

AdmissionConflict

ConcurrencySnapshotUnavailable
```

---

# 258. Query failure

Si `ExecutionQueryPort` est indisponible :

> Faut-il admettre ou refuser ?

---

# 259. Fail-open versus fail-closed

Deux stratégies :

```text
FAIL_OPEN
```

admet quand l'état de concurrence est inconnu.

```text
FAIL_CLOSED
```

refuse/diffère par sécurité.

---

# 260. Recommendation

Pour une policy restrictive :

```text
fail closed
```

est généralement plus cohérent.

Sinon une panne du store pourrait violer l'invariant d'overlap.

---

# 261. But policy should be explicit

Une future :

```text
ConcurrencyEvaluationFailurePolicy
```

peut définir le comportement.

V1 peut simplement retourner une erreur et ne pas exécuter.

---

# 262. Safety V1

Si l'état actif ne peut pas être déterminé :

```text
do not admit
```

est un comportement conservateur.

---

# 263. Snapshot freshness

Un snapshot vieux de plusieurs secondes peut être obsolète.

Pour une décision locale simple :

```text
captured_at
```

peut être tracé.

---

# 264. But correctness comes from atomic admission

Pas de confiance excessive dans la fraîcheur du snapshot.

---

# 265. Domain events and revision

Une modification de ConcurrencyPolicy peut produire :

```text
ScheduleRescheduled
```

puisque la `ScheduleDefinition` change.

Pas besoin d'un event spécialisé sauf besoin.

---

# 266. Observability example

```text
Occurrence:
10:05

Policy:
max=1 / queue

Active:
exec-A

Decision:
defer

Wait:
3m12s

Admitted:
10:08:12
```

---

# 267. Metrics on wait

```text
concurrency_wait_seconds
```

permet de savoir si :

```text
la fréquence du Schedule
```

est incompatible avec :

```text
la durée réelle du travail
```

---

# 268. Capacity insight

Si :

```text
interval = 5m
```

et :

```text
average runtime = 20m
```

avec :

```text
max_instances = 1
```

un backlog structurel apparaît.

---

# 269. Important operational insight

Le scheduler ne peut pas « réparer » mathématiquement une configuration impossible.

Il peut seulement :

```text
queue
drop
coalesce
allow more concurrency
```

---

# 270. Concurrency pressure

Une métrique possible :

```text
runtime / recurrence interval
```

donne une intuition de saturation.

Mais ce n'est pas un invariant métier.

---

# 271. Example

```text
runtime 20m
interval 5m
ratio = 4
```

Pour rester sans backlog avec executions parfaitement parallélisables :

```text
~4 instances
```

seraient nécessaires en moyenne.

---

# 272. But do not auto-adjust policy

PyScheduleKit ne doit pas modifier automatiquement :

```text
max_instances
```

à partir de cette métrique.

Il peut seulement fournir un diagnostic.

---

# 273. Concurrency preview

Une future commande d'inspection peut expliquer :

```text
Given 3 active executions
Policy max=2
New occurrence would be rejected
```

utile pour le debug.

---

# 274. Simulation

Avec un Fake runtime snapshot :

```text
active_count = 0
1
2
```

on peut tester facilement toutes les branches.

---

# 275. No real threads needed

Le domaine de concurrence doit être testable sans lancer :

```text
threads
processes
workers
```

---

# 276. This validates architecture

La logique de policy doit rester indépendante du mécanisme physique de parallélisme.

---

# 277. Test matrix minimale

```text
ALLOW with 0 active

ALLOW with many active

limit=1 with 0 active

limit=1 with 1 active + DROP

limit=1 with 1 active + QUEUE

limit=3 with 2 active

limit=3 with 3 active

cross-Schedule shared key

retry-wait counts active

terminal executions don't count

coalesce latest

snapshot unavailable

distributed admission conflict
```

---

# 278. Conformance property

Pour `Limit(N)` :

```text
active_count < N
→ ADMIT
```

quelle que soit l'overflow strategy.

---

# 279. Overflow only matters at saturation

```text
active_count >= N
```

→ appliquer :

```text
DROP / QUEUE / COALESCE
```

---

# 280. Terminal states property

Les executions terminales ne doivent pas compter dans :

```text
active_count
```

---

# 281. Stable key property

Deux requests avec des clés différentes ne doivent pas se bloquer mutuellement.

---

# 282. Shared key property

Deux schedules avec la même clé doivent voir la même population active.

---

# 283. Domain model final

```text
ScheduleDefinition
│
├── ConcurrencyKey
└── ConcurrencyPolicy
       │
       ├── Allow
       └── Limit
            ├── max_instances
            └── overflow_strategy
```

Runtime input :

```text
ActiveExecutionSnapshot
```

Decision :

```text
AdmissionDecision
```

Service :

```text
ConcurrencyEvaluator
```

---

# 284. Full decision flow

```text
                    Occurrence
                        │
                        ▼
               ExecutionRequest candidate
                        │
                        ▼
                 ConcurrencyKey
                        │
                        ▼
               ExecutionQueryPort
                        │
                        ▼
            ActiveExecutionSnapshot
                        │
                        ▼
               ConcurrencyPolicy
                        │
                        ▼
              ConcurrencyEvaluator
                        │
                        ▼
                AdmissionDecision
           ┌────────────┼──────────────┐
           │            │              │
           ▼            ▼              ▼
         ADMIT         DROP           DEFER
                                         │
                                         ▼
                                       QUEUE
```

Option future :

```text
COALESCE
REPLACE
```

---

# 285. Position in PyScheduleKit pipeline

```text
Time
 ↓
Trigger
 ↓
Occurrence
 ↓
Misfire / Catch-Up
 ↓
Concurrency / Overlap
 ↓
AdmissionDecision
 ↓
ExecutionRequest
 ↓
Executor
 ↓
Execution
 ↓
Attempt
```

---

# 286. Distinctions fondamentales

```text
Recurrence
≠
Concurrency

Misfire
≠
Overlap

Overlap
≠
Execution Failure

Queue
≠
Retry

Concurrency Limit
≠
Worker Pool Size

ConcurrencyKey
≠
ScheduleId necessarily
```

---

# 287. V1 policy recommendation

Supporter officiellement :

```text
ALLOW
```

et :

```text
LIMIT
  max_instances >= 1

  overflow:
  DROP
  QUEUE
```

---

# 288. V1 optional extension

Ajouter :

```text
COALESCE_LATEST
```

si le modèle d'OccurrenceGroup du document 13 est déjà en place.

---

# 289. Hors scope V1

```text
REPLACE

priority scheduling

fairness algorithms

multiple resource keys

hierarchical concurrency

distributed semaphore algorithms

dynamic auto-scaling

preemption
```

---

# 290. Why REPLACE later

Parce qu'il implique :

```text
Execution Cancellation Model
```

qui mérite un contrat autonome.

---

# 291. Core invariants

```text
1.
ConcurrencyPolicy ne modifie jamais scheduled_at.

2.
Le Trigger ne connaît pas la concurrence.

3.
ConcurrencyKey définit le scope du conflit.

4.
ConcurrencyLimit est strictement positif.

5.
Les executions terminales ne comptent pas.

6.
La décision métier utilise un snapshot explicite.

7.
L'admission distribuée doit être atomique.

8.
Une rejection de concurrence n'est pas un échec d'execution.

9.
QUEUE ne transforme pas l'occurrence en retry.

10.
Catch-Up et Concurrency restent des politiques séparées.

11.
Worker capacity et logical concurrency sont distinctes.

12.
Une execution en retry peut rester active
selon le modèle logique choisi.

13.
Une occurrence coalescée conserve son evidence.

14.
Une ConcurrencyPolicy partagée doit avoir une sémantique cohérente.

15.
Le domaine décide quoi faire ;
l'infrastructure garantit l'atomicité.
```

---

# 292. Décisions proposées pour PyScheduleKit V1

```text
1.
ConcurrencyKey est un Value Object explicite.

2.
Par défaut :
ConcurrencyKey = ScheduleId.

3.
ConcurrencyPolicy appartient à ScheduleDefinition.

4.
V1 supporte :
ALLOW
LIMIT(max_instances, overflow).

5.
overflow V1 :
DROP
QUEUE.

6.
max_instances >= 1.

7.
La concurrence porte sur les Executions logiques.

8.
QUEUED, RUNNING et RETRY_WAIT
peuvent compter comme actifs
selon l'Execution state model retenu.

9.
Les états terminaux ne comptent pas.

10.
ActiveExecutionSnapshot est fourni
au domaine par ExecutionQueryPort.

11.
ConcurrencyEvaluator produit
une AdmissionDecision pure.

12.
L'admission atomique appartient
à l'application/infrastructure.

13.
Le système échoue de manière conservative
si l'état de concurrence est inconnu.

14.
QUEUE conserve le scheduled_at d'origine.

15.
Les requests queued sont FIFO par scheduled_at
dans la sémantique V1.

16.
COALESCE_LATEST reste une extension possible.

17.
REPLACE est hors scope V1.
```

---

# 293. Critères d'acceptation

Le modèle doit permettre de répondre clairement à :

```text
Qu'est-ce qu'un overlap ?

Quelle différence entre concurrence et parallélisme ?

Quelles executions entrent en conflit ?

Qu'est-ce qu'une ConcurrencyKey ?

Que signifie max_instances ?

Que se passe-t-il lorsque la limite est atteinte ?

Quelle différence entre DROP et QUEUE ?

Une occurrence queued conserve-t-elle son scheduled_at ?

Une execution en retry compte-t-elle comme active ?

Comment gérer plusieurs Schedules partageant une ressource ?

Comment éviter deux admissions simultanées en distribué ?

Pourquoi un snapshot métier ne suffit-il pas à assurer l'atomicité ?

Comment Catch-Up et Concurrency interagissent-ils ?

Pourquoi Worker Pool Size n'est-il pas ConcurrencyLimit ?

Quand une Execution libère-t-elle son slot ?
```

---

# 294. Modèle mental final

```text
             NEW OCCURRENCE
                    │
                    ▼
              ConcurrencyKey
                    │
                    ▼
           Active Executions?
                    │
        ┌───────────┴────────────┐
        │                        │
        ▼                        ▼
       NO                       YES
        │                        │
        ▼                        ▼
      ADMIT              ConcurrencyPolicy
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
                 ▼               ▼               ▼
               DROP            QUEUE          COALESCE
                                 │
                                 ▼
                          wait for capacity
```

---

# 295. Synthèse

La concurrence répond à une question très différente de celle du Trigger :

```text
Trigger
→ Quand une occurrence existe-t-elle ?
```

```text
MisfirePolicy
→ Que faire si elle est en retard ?
```

```text
ConcurrencyPolicy
→ Que faire si une execution incompatible est déjà active ?
```

```text
RetryPolicy
→ Que faire si une execution tentée échoue ?
```

Ces quatre questions doivent rester séparées.

---

# Conclusion

Le modèle de concurrence de PyScheduleKit doit gérer **l'admission logique des executions**, pas la gestion physique des CPU, threads ou workers.

Le cœur du modèle devient :

```text
Occurrence
      │
      ▼
ConcurrencyKey
      │
      ▼
ActiveExecutionSnapshot
      │
      ▼
ConcurrencyPolicy
      │
      ▼
AdmissionDecision
```

La policy détermine :

```text
ALLOW
DROP
QUEUE
COALESCE
```

tandis que l'infrastructure assure :

```text
locks
transactions
leases
distributed coordination
```

Le principe le plus important est :

> **La décision de concurrence doit être explicite, déterministe et observable, mais sa garantie atomique appartient à la coordination runtime.**

Autrement dit :

```text
Domain
→ SHOULD this execution be admitted?

Infrastructure
→ CAN we atomically secure that admission?
```

Cette séparation prépare PyScheduleKit à évoluer d'un scheduler local simple vers un système distribué sans polluer son domaine avec des mécanismes de lock spécifiques.

---

# Suite documentaire

La prochaine étape logique est :

```text
15_RETRY_BACKOFF_AND_FAILURE_MODEL.md
```

Elle devra clarifier :

```text
Execution Failure

Attempt

Retry

RetryPolicy

MaxAttempts

Backoff

FixedBackoff

ExponentialBackoff

Jitter

Retryable / NonRetryable Failure

Timeout

Deadline

Terminal Failure
```

et surtout verrouiller définitivement la distinction :

```text
Recurrence
≠
Catch-Up
≠
Concurrency Queueing
≠
Retry
```

avant d'aborder les couches runtime et persistence avancées.