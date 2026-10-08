# PyScheduleKit — Execution Lifecycle & State Machine

**Document :** `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle métier de référence  
**Nature :** Domain Model — Execution Lifecycle / State Machines  
**Prérequis :**
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`
- `11_DATE_INTERVAL_AND_CRON_TRIGGERS.md`
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`
- `14_CONCURRENCY_AND_OVERLAP_MODEL.md`
- `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`

---

# 1. Objectif

Les documents précédents ont progressivement séparé :

```text
Occurrence
ExecutionRequest
Execution
Attempt
ExecutionResult
```

Ils ont également introduit :

```text
Misfire
Catch-Up
Concurrency
Admission
Retry
Backoff
Timeout
Cancellation
```

Il faut maintenant répondre à une question centrale :

> **Comment une intention d'exécution évolue-t-elle depuis sa création jusqu'à son état terminal ?**

Le but de ce document est de définir :

```text
les objets runtime

leurs états

leurs transitions

leurs invariants

leurs responsabilités

les événements produits

les frontières transactionnelles
```

sans transformer PyScheduleKit en moteur d'orchestration généraliste.

---

# 2. Chaîne conceptuelle

Le modèle complet est :

```text
Schedule
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
AdmissionDecision
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

---

# 3. Trois lifecycles distincts

Le premier principe est :

```text
ExecutionRequest lifecycle
≠
Execution lifecycle
≠
Attempt lifecycle
```

Ces trois objets n'ont pas les mêmes responsabilités.

---

# 4. ExecutionRequest

Une `ExecutionRequest` représente :

> **Une demande durable d'exécuter une occurrence.**

Elle constitue la frontière entre :

```text
Scheduling
```

et :

```text
Execution Runtime
```

---

# 5. Execution

Une `Execution` représente :

> **Le run logique d'une ExecutionRequest.**

Elle peut contenir :

```text
0..N Attempts
```

et se termine par :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 6. Attempt

Une `Attempt` représente :

> **Une tentative concrète de réaliser une Execution.**

Elle peut :

```text
réussir

échouer

expirer

être annulée
```

---

# 7. Modèle global

```text
Occurrence
    │
    ▼
ExecutionRequest
    │
    ▼
Execution
    │
    ├── Attempt #1
    │
    ├── Attempt #2
    │
    └── Attempt #3
```

---

# 8. Cardinalités

```text
Occurrence
   0..1
ExecutionRequest
   0..1
Execution
   1..N
Attempt
```

Le modèle V1 suppose généralement :

```text
1 ExecutionRequest
→ 0..1 Execution
```

---

# 9. Pourquoi 0..1 Execution ?

Une request peut être :

```text
rejetée

annulée

expirée

déférée
```

avant la création réelle de son Execution.

---

# 10. ExecutionRequest comme Command Entity

La classification proposée est :

```text
ExecutionRequest
=
immutable command-like Entity
```

Elle possède :

```text
RequestId
```

et transporte une intention déjà décidée.

---

# 11. ExecutionRequest ne recalcule rien

Une request ne doit plus décider :

```text
si l'occurrence était due

si elle était misfired

si elle devait être coalescée

quel Trigger l'a produite
```

Ces décisions ont déjà été prises.

---

# 12. Request snapshot

L'ExecutionRequest peut contenir :

```text
request_id

schedule_id

schedule_revision

occurrence_key

scheduled_at

target_ref

execution_context

policy_snapshot

correlation_id

metadata
```

---

# 13. Why snapshot?

Parce que le Schedule peut évoluer après la création de la request.

La request doit rester interprétable indépendamment de cette évolution.

---

# 14. ExecutionRequest lifecycle

Un modèle initial raisonnable :

```text
PENDING
QUEUED
DISPATCHED
CANCELLED
EXPIRED
```

---

# 15. Variante encore plus simple

Pour V1 :

```text
CREATED
QUEUED
DISPATCHED
CANCELLED
```

peut suffire.

---

# 16. PENDING

`PENDING` signifie :

```text
la request existe
mais n'a pas encore été admise/dispatchée
```

---

# 17. QUEUED

`QUEUED` signifie :

```text
la request est conservée
mais attend une capacité ou admission
```

---

# 18. DISPATCHED

`DISPATCHED` signifie :

```text
la request a été remise à l'Execution Runtime
```

et peut donner naissance à une `Execution`.

---

# 19. CANCELLED

`CANCELLED` signifie :

```text
la request ne doit plus produire d'Execution
```

---

# 20. EXPIRED

`EXPIRED` signifie :

```text
la request a dépassé une limite temporelle
avant d'être exécutée
```

Cet état peut rester hors V1 si nécessaire.

---

# 21. Request state machine

```text
CREATED
   │
   ├── queue
   ▼
QUEUED
   │
   ├── dispatch
   ▼
DISPATCHED
```

Transitions terminales possibles :

```text
CREATED ─────→ CANCELLED

QUEUED ──────→ CANCELLED

CREATED ─────→ EXPIRED

QUEUED ──────→ EXPIRED
```

---

# 22. DISPATCHED est terminal pour la Request

Une fois la request dispatchée :

```text
son lifecycle propre
```

peut être considéré comme terminé.

La suite appartient à :

```text
Execution
```

---

# 23. Important

```text
ExecutionRequest.DISPATCHED
```

ne signifie pas :

```text
Execution.SUCCESS
```

Cela signifie seulement :

```text
la demande a franchi la frontière d'exécution
```

---

# 24. Execution lifecycle

Le lifecycle principal proposé est :

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

---

# 25. Execution state machine

```text
              ┌─────────┐
              │ CREATED │
              └────┬────┘
                   │
                   ▼
              ┌────────┐
              │ QUEUED │
              └────┬───┘
                   │
                   ▼
              ┌─────────┐
              │ RUNNING │
              └────┬────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
    SUCCESS     FAILED     TIMED_OUT
                   ▲
                   │
             ┌─────┴─────┐
             │ RETRY_WAIT│
             └─────┬─────┘
                   │
                   ▼
                RUNNING
```

avec `CANCELLED` accessible depuis certains états actifs.

---

# 26. CREATED

`CREATED` signifie :

```text
l'Execution existe logiquement
mais aucune tentative n'a encore commencé
```

---

# 27. QUEUED

`QUEUED` signifie :

```text
l'Execution attend une capacité runtime
avant le premier Attempt
```

---

# 28. RUNNING

`RUNNING` signifie :

```text
au moins une Attempt est actuellement active
```

dans V1 :

```text
exactement une Attempt active maximum
```

---

# 29. RETRY_WAIT

`RETRY_WAIT` signifie :

```text
la dernière Attempt a échoué
mais la RetryPolicy a décidé
qu'une nouvelle Attempt devait être créée plus tard
```

---

# 30. SUCCESS

État terminal :

```text
une Attempt a réussi
```

et l'Execution est terminée avec succès.

---

# 31. FAILED

État terminal :

```text
la dernière Attempt a échoué
et aucun retry supplémentaire n'est autorisé
```

---

# 32. TIMED_OUT

État terminal :

```text
une deadline ou limite globale
de l'Execution a été dépassée
```

---

# 33. CANCELLED

État terminal :

```text
une cancellation explicite
a arrêté le lifecycle
```

---

# 34. Terminal states

La liste V1 recommandée :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 35. Invariant terminal

Une fois dans un état terminal :

```text
aucune transition normale
vers un état actif n'est autorisée
```

---

# 36. No resurrection

Ainsi :

```text
FAILED
→ RUNNING
```

est interdit.

```text
CANCELLED
→ RETRY_WAIT
```

est interdit.

```text
SUCCESS
→ RUNNING
```

est interdit.

---

# 37. Manual rerun

Si l'utilisateur veut relancer :

```text
une nouvelle Execution
```

doit être créée.

On ne rouvre pas l'ancienne.

---

# 38. Attempt lifecycle

La machine d'état d'une Attempt peut rester très simple :

```text
PENDING
RUNNING
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

---

# 39. Attempt state machine

```text
PENDING
   │
   ▼
RUNNING
   │
   ├── SUCCESS
   ├── FAILED
   ├── TIMED_OUT
   └── CANCELLED
```

---

# 40. Attempt terminal states

```text
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

Toutes sont terminales.

---

# 41. Une Attempt ne retry jamais

Un retry crée :

```text
une nouvelle Attempt
```

Il ne remet pas :

```text
Attempt #1
```

en `RUNNING`.

---

# 42. Exemple

```text
Attempt #1
FAILED

RetryDecision = RETRY

↓
Attempt #2
PENDING → RUNNING
```

---

# 43. Un seul Attempt actif

Invariant V1 :

```text
At most one active Attempt
per Execution.
```

---

# 44. Pourquoi ?

Cela simplifie :

```text
résultats

retry

cancellation

idempotence

state transitions
```

---

# 45. Hedged Attempts

Les modèles où :

```text
Attempt #1
et
Attempt #2
```

courent en parallèle sont hors scope V1.

---

# 46. Relation Execution ↔ Attempt

L'Execution est le parent logique.

Elle protège les invariants :

```text
attempt_number progression

one active Attempt

terminal transition

retry eligibility
```

---

# 47. Execution comme Aggregate Root ?

Deux choix sont possibles.

---

# 48. Option A

```text
Execution
=
Aggregate Root
```

et `Attempt` appartient à son Aggregate.

---

# 49. Option B

`Attempt` est persistée séparément mais reste contrôlée par les règles de l'Execution.

---

# 50. Recommandation

Conceptuellement :

```text
Execution
=
Aggregate Root
```

est un bon modèle.

---

# 51. Pourquoi ?

Parce que les invariants suivants portent naturellement sur l'ensemble :

```text
une seule Attempt active

attempt_number unique

Execution terminale
→ aucune nouvelle Attempt

success d'une Attempt
→ Execution success
```

---

# 52. Mais attention à la taille

L'historique d'Attempts peut devenir important.

Pour V1 :

```text
quelques Attempts
```

restent raisonnables.

À grande échelle :

```text
Attempt
```

peut être persistée séparément avec une projection adaptée.

---

# 53. Execution aggregate

```text
Execution [AR]
│
├── ExecutionId
├── RequestId
├── OccurrenceKey
├── ExecutionState
├── AttemptCount
├── CurrentAttemptRef?
├── NextAttemptAt?
├── ExecutionPolicySnapshot
└── ExecutionResult?
```

---

# 54. ExecutionId

```text
ExecutionId
=
Value Object
```

stable pendant tout le lifecycle.

---

# 55. AttemptId

```text
AttemptId
=
Value Object
```

unique par tentative.

---

# 56. AttemptNumber

```text
AttemptNumber
=
Value Object
```

et :

```text
>= 1
```

---

# 57. State transitions as behavior

Éviter :

```python
execution.status = "running"
```

Préférer :

```text
execution.mark_queued(...)

execution.start_attempt(...)

execution.schedule_retry(...)

execution.complete_success(...)

execution.complete_failure(...)

execution.cancel(...)
```

---

# 58. Why?

Chaque transition peut alors vérifier :

```text
état actuel

invariants

timestamps

domain events
```

---

# 59. Execution creation

L'Execution peut être créée après :

```text
AdmissionDecision = ADMIT
```

---

# 60. Creation invariant

Elle doit avoir :

```text
ExecutionId

RequestId

OccurrenceKey

PolicySnapshot

Target execution data
```

---

# 61. Initial state

Deux choix :

```text
CREATED
```

ou directement :

```text
QUEUED
```

---

# 62. Recommendation

Garder :

```text
CREATED
```

comme état technique très court peut être utile.

Mais V1 pourrait simplifier en :

```text
QUEUED
```

immédiatement après création.

---

# 63. Minimal V1 states

Une version compacte pourrait être :

```text
QUEUED
RUNNING
RETRY_WAIT
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 64. Should CREATED exist?

Si aucune logique ne se produit entre :

```text
Execution creation
```

et :

```text
queueing
```

alors `CREATED` peut être inutile.

---

# 65. Recommendation

Documenter `CREATED` conceptuellement, mais ne pas obliger l'implémentation V1 à le persister longtemps.

---

# 66. StartAttempt command

Une opération conceptuelle :

```text
start_attempt()
```

doit vérifier :

```text
Execution not terminal

no active Attempt

state in QUEUED or RETRY_WAIT
```

---

# 67. Attempt number calculation

```text
next_attempt_number
=
attempt_count + 1
```

---

# 68. Transition

Pour première Attempt :

```text
QUEUED
→
RUNNING
```

---

# 69. Retry Attempt

Pour retry :

```text
RETRY_WAIT
→
RUNNING
```

---

# 70. AttemptStarted event

Peut contenir :

```text
execution_id
attempt_id
attempt_number
started_at
```

---

# 71. Attempt success

Lorsque l'Attempt réussit :

```text
Attempt
RUNNING → SUCCESS
```

puis :

```text
Execution
RUNNING → SUCCESS
```

---

# 72. Atomicity

Ces deux transitions doivent idéalement être enregistrées ensemble.

Sinon :

```text
Attempt SUCCESS
Execution RUNNING
```

crée un état incohérent.

---

# 73. Success result

L'Execution peut recevoir :

```text
ExecutionResult.success(...)
```

---

# 74. Attempt failure

Lorsque l'Attempt échoue :

```text
Attempt
RUNNING → FAILED
```

puis :

```text
RetryPolicy
```

est évaluée.

---

# 75. Two branches

```text
FAILED Attempt
   │
   ▼
RetryPolicy
   │
   ├── RETRY
   │      ▼
   │  Execution RETRY_WAIT
   │
   └── STOP
          ▼
      Execution FAILED
```

---

# 76. Retry schedule

En cas de retry :

```text
next_attempt_at
```

doit être défini.

---

# 77. Invariant RETRY_WAIT

```text
ExecutionState = RETRY_WAIT
```

implique :

```text
next_attempt_at != None
```

---

# 78. Invariant RUNNING

```text
ExecutionState = RUNNING
```

implique :

```text
exactly one active Attempt
```

dans V1.

---

# 79. Invariant SUCCESS

```text
ExecutionState = SUCCESS
```

implique :

```text
at least one Attempt SUCCESS
```

et :

```text
ExecutionResult success
```

---

# 80. Invariant FAILED

```text
ExecutionState = FAILED
```

implique :

```text
no retry remaining
```

et :

```text
latest terminal Attempt unsuccessful
```

---

# 81. TIMED_OUT

Deux timeout levels possibles :

```text
AttemptTimeout
ExecutionDeadline
```

---

# 82. Attempt timeout

Une Attempt dépasse :

```text
AttemptTimeout
```

Elle devient :

```text
TIMED_OUT
```

Puis la RetryPolicy peut éventuellement décider :

```text
RETRY
```

---

# 83. Important

```text
Attempt TIMED_OUT
```

ne signifie pas obligatoirement :

```text
Execution TIMED_OUT
```

---

# 84. Example

```text
Attempt #1 TIMED_OUT
RetryPolicy → RETRY

Attempt #2 SUCCESS

Execution → SUCCESS
```

---

# 85. Execution timeout

En revanche, si :

```text
ExecutionDeadline
```

est dépassée :

```text
Execution → TIMED_OUT
```

et aucun nouvel Attempt ne doit être créé.

---

# 86. Attempt timeout versus Execution timeout

```text
Attempt timeout
→ local failure

Execution timeout
→ terminal lifecycle condition
```

---

# 87. Cancellation

La cancellation mérite un modèle précis.

---

# 88. Cancellation request

Une commande :

```text
CancelExecution
```

peut être reçue dans :

```text
QUEUED
RUNNING
RETRY_WAIT
```

---

# 89. Queued cancellation

Si aucune Attempt n'est active :

```text
QUEUED → CANCELLED
```

peut être immédiat.

---

# 90. Retry-wait cancellation

Même logique :

```text
RETRY_WAIT → CANCELLED
```

et :

```text
next_attempt_at = None
```

---

# 91. Running cancellation

Plus complexe :

```text
RUNNING
```

implique une Attempt active.

Il faut demander à l'Executor :

```text
cancel attempt
```

---

# 92. CANCELLING state?

Une machine plus précise pourrait introduire :

```text
CANCELLING
```

---

# 93. Example

```text
RUNNING
   │
cancel requested
   ▼
CANCELLING
   │
   ├── executor confirms
   ▼
CANCELLED
```

---

# 94. Is CANCELLING needed in V1?

Pas nécessairement.

Si le runtime local peut annuler synchroniquement :

```text
RUNNING → CANCELLED
```

peut suffire.

---

# 95. Distributed runtime

Dans un runtime distant, `CANCELLING` devient plus utile.

---

# 96. Recommendation

Définir le concept mais garder :

```text
CANCELLING
```

optionnel hors V1.

---

# 97. Cancellation is best effort

Un Executor externe peut ne pas pouvoir stopper immédiatement un travail déjà lancé.

---

# 98. Therefore

```text
Cancel requested
```

et :

```text
Execution cancelled
```

ne sont pas toujours le même instant.

---

# 99. CancellationReason

Un Value Object/enum possible :

```text
USER_REQUEST

SCHEDULE_CANCELLED_CASCADE

TIMEOUT

SHUTDOWN

REPLACED
```

---

# 100. V1

Peut rester :

```text
USER_REQUEST
SYSTEM_REQUEST
```

si nécessaire.

---

# 101. Cancel Schedule versus Cancel Execution

Rappel :

```text
Cancel Schedule
≠
Cancel Execution
```

Le premier empêche :

```text
future occurrences
```

Le second arrête :

```text
one logical run
```

---

# 102. Cascading cancellation

Une future commande applicative peut :

```text
cancel schedule
+
cancel active executions
```

mais ce sont deux actions distinctes.

---

# 103. ExecutionRequest cancellation

Une Request peut être annulée avant l'Execution.

Après la création d'une Execution :

```text
CancelExecution
```

devient le concept pertinent.

---

# 104. Request cancellation invariant

```text
ExecutionRequest CANCELLED
```

ne doit jamais produire ensuite une nouvelle Execution.

---

# 105. Dispatch race

Cas difficile :

```text
request cancel
```

et :

```text
dispatch
```

arrivent simultanément.

---

# 106. Atomic transition

La transition :

```text
QUEUED → DISPATCHED
```

ou :

```text
QUEUED → CANCELLED
```

doit être protégée atomiquement.

---

# 107. Same pattern everywhere

Le runtime possède de nombreuses races :

```text
dispatch vs cancel

retry vs cancel

success vs timeout

retry vs deadline

two workers starting same Attempt
```

---

# 108. Domain state machine + atomic persistence

Encore une fois :

```text
Domain
→ transitions autorisées

Infrastructure
→ garantit transition unique
```

---

# 109. Optimistic locking

Une `ExecutionVersion` peut protéger :

```text
lost updates
```

Exemple :

```text
version = 5
```

et update :

```text
WHERE version = 5
```

---

# 110. ExecutionVersion

Ne pas confondre avec :

```text
ScheduleRevision
```

L'ExecutionVersion est généralement :

```text
persistence concurrency control
```

---

# 111. Attempt completion race

Un timeout peut être décidé au même moment qu'un résultat success arrive.

---

# 112. Need authoritative transition

Une seule transition terminale doit gagner.

---

# 113. Example

```text
Attempt RUNNING
```

Node A :

```text
mark SUCCESS
```

Node B :

```text
mark TIMED_OUT
```

---

# 114. Optimistic/transactional guard

Le store doit garantir :

```text
RUNNING → one terminal state
```

une seule fois.

---

# 115. Late result

Si `TIMED_OUT` a gagné puis un success arrive :

```text
late result
```

doit être :

```text
ignored
recorded diagnostically
```

mais ne doit pas ressusciter l'Attempt.

---

# 116. LateAttemptResult

Concept de diagnostic possible :

```text
LateAttemptResult
```

hors lifecycle principal.

---

# 117. Idempotent transitions

Recevoir deux fois :

```text
AttemptSucceeded
```

ne devrait pas doubler les effets.

---

# 118. Idempotence requirement

Les commands/events runtime doivent avoir :

```text
stable identifiers
```

permettant la déduplication.

---

# 119. Transition table — ExecutionRequest

| Current | Action | Next |
|---|---|---|
| CREATED | queue | QUEUED |
| CREATED | dispatch | DISPATCHED |
| CREATED | cancel | CANCELLED |
| QUEUED | dispatch | DISPATCHED |
| QUEUED | cancel | CANCELLED |
| QUEUED | expire | EXPIRED |

---

# 120. Invalid Request transitions

Exemples :

```text
DISPATCHED → QUEUED
```

interdit.

```text
CANCELLED → DISPATCHED
```

interdit.

---

# 121. Transition table — Execution

| Current | Action | Next |
|---|---|---|
| CREATED | queue | QUEUED |
| QUEUED | start attempt | RUNNING |
| RUNNING | attempt succeeds | SUCCESS |
| RUNNING | attempt fails + retry | RETRY_WAIT |
| RUNNING | attempt fails + stop | FAILED |
| RUNNING | execution deadline | TIMED_OUT |
| RETRY_WAIT | retry due | RUNNING |
| RETRY_WAIT | cancel | CANCELLED |
| QUEUED | cancel | CANCELLED |
| RUNNING | cancel confirmed | CANCELLED |

---

# 122. Terminal rows

À partir de :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

aucune transition métier normale.

---

# 123. Transition table — Attempt

| Current | Action | Next |
|---|---|---|
| PENDING | start | RUNNING |
| RUNNING | succeed | SUCCESS |
| RUNNING | fail | FAILED |
| RUNNING | timeout | TIMED_OUT |
| RUNNING | cancel | CANCELLED |

---

# 124. Invalid Attempt transitions

```text
SUCCESS → RUNNING
```

interdit.

```text
FAILED → RUNNING
```

interdit.

Retry = nouvelle Attempt.

---

# 125. ExecutionResult

À l'état terminal, l'Execution doit pouvoir produire :

```text
ExecutionResult
```

---

# 126. Success result

```text
ExecutionResult
│
├── status = SUCCESS
├── completed_at
├── output?
└── artifacts?
```

---

# 127. Failed result

```text
ExecutionResult
│
├── status = FAILED
├── completed_at
├── failure
└── attempts_summary
```

---

# 128. Cancelled result

Peut contenir :

```text
cancellation_reason
cancelled_at
```

---

# 129. Timed out result

Peut contenir :

```text
deadline
timed_out_at
last_attempt
```

---

# 130. ExecutionResult as Value Object

Classification :

```text
ExecutionResult
=
Value Object
```

immutable une fois l'Execution terminale.

---

# 131. Result appears once

Invariant :

```text
terminal Execution
→ exactly one ExecutionResult
```

---

# 132. Non-terminal Execution

```text
ExecutionResult = None
```

---

# 133. ArtifactRef

Si une execution produit :

```text
file
dataset
report
workflow_run
```

le résultat peut conserver :

```text
ArtifactRef
```

---

# 134. Avoid embedding heavy payloads

L'ExecutionResult ne doit pas devenir :

```text
un stockage de fichiers volumineux
```

Préférer :

```text
references
```

---

# 135. ExecutionContext

Une `ExecutionContext` peut transporter :

```text
schedule_id

schedule_revision

occurrence_key

scheduled_at

correlation_id

trace_id

metadata
```

---

# 136. Immutable context

Ce contexte doit rester stable pendant toute l'Execution.

---

# 137. Same context across Attempts

Toutes les Attempts partagent :

```text
ExecutionContext
```

mais peuvent ajouter :

```text
AttemptNumber
AttemptId
```

---

# 138. Correlation

Cela permet :

```text
Schedule
→ Occurrence
→ Request
→ Execution
→ Attempts
```

d'être suivis dans les logs/traces.

---

# 139. Execution policy snapshot

Comme défini précédemment :

```text
ExecutionPolicySnapshot
```

peut contenir :

```text
RetryPolicy
AttemptTimeout
ExecutionDeadline
Idempotency information
```

---

# 140. Snapshot immutability

Modifier le Schedule après lancement ne modifie pas :

```text
ExecutionPolicySnapshot
```

---

# 141. Important invariant

```text
runtime semantics of an existing Execution
must not depend on future Schedule mutations
```

---

# 142. Scheduling state versus runtime state

Une Schedule peut devenir :

```text
PAUSED
```

pendant qu'une Execution est :

```text
RUNNING
```

Ce n'est pas incohérent.

---

# 143. Example

```text
Schedule PAUSED

Execution #42 RUNNING
```

La pause arrête :

```text
future scheduling
```

pas :

```text
current execution
```

---

# 144. Same with CANCELLED Schedule

```text
Schedule CANCELLED

Execution #42 RETRY_WAIT
```

peut continuer par défaut.

---

# 145. Independent aggregates

Cela confirme la séparation :

```text
Schedule Aggregate
```

et :

```text
Execution Aggregate
```

---

# 146. Eventual consistency

Leurs lifecycles ne sont pas synchrones.

C'est attendu.

---

# 147. ExecutionRequest aggregate?

La Request peut être :

```text
Entity
```

mais pas nécessairement Aggregate Root complexe.

---

# 148. Simpler model

Le système peut traiter :

```text
ExecutionRequest
```

comme un command record immutable.

Puis `Execution` devient le véritable runtime Aggregate Root.

---

# 149. Recommendation

Pour V1 :

```text
ExecutionRequest
=
immutable command record/entity
```

```text
Execution
=
Aggregate Root
```

```text
Attempt
=
child Entity
```

---

# 150. Admission to Execution creation

Une request `ADMIT` peut produire :

```text
Execution.create_from(request)
```

---

# 151. Queue model question

Si ConcurrencyPolicy retourne :

```text
QUEUE
```

faut-il créer immédiatement l'Execution ?

---

# 152. Option A

Créer :

```text
Execution QUEUED
```

immédiatement.

---

# 153. Option B

Garder :

```text
ExecutionRequest QUEUED
```

et créer l'Execution seulement à admission effective.

---

# 154. Trade-off

### A

Plus simple pour :

```text
tracking
concurrency state
queue observability
```

### B

Plus strict conceptuellement :

```text
Execution = actual admitted run
```

---

# 155. Recommendation

Pour PyScheduleKit :

```text
Execution
```

peut être créée dès que la request est retenue comme run logique, même si elle attend.

Ainsi :

```text
QUEUED
```

est un véritable état de l'Execution.

---

# 156. Consequence

La relation devient :

```text
ExecutionRequest
→ Execution
```

dès l'admission logique.

Puis :

```text
Execution QUEUED
```

attend le lancement.

---

# 157. Rejected occurrence

Si ConcurrencyPolicy = DROP :

```text
aucune Execution
```

n'est créée.

---

# 158. Coalesced occurrence

Plusieurs occurrences peuvent conduire à :

```text
une seule ExecutionRequest
```

puis une seule `Execution`.

---

# 159. Execution provenance

L'Execution doit donc pouvoir référencer :

```text
one OccurrenceKey
```

ou :

```text
OccurrenceGroup
```

pour les cas coalescés.

---

# 160. ExecutionSource

Une abstraction possible :

```text
ExecutionSource
```

avec :

```text
SingleOccurrence
```

ou :

```text
OccurrenceGroup
```

---

# 161. V1 simplification

Supporter :

```text
primary_occurrence_key
```

et éventuellement :

```text
coalesced_occurrence_keys
```

dans le contexte.

---

# 162. Execution start timestamp

Il faut distinguer :

```text
created_at

queued_at

started_at

finished_at
```

---

# 163. started_at

Pour l'Execution, deux sémantiques possibles :

```text
first Attempt starts
```

ou :

```text
Execution object created
```

---

# 164. Recommendation

```text
Execution.started_at
=
first Attempt.started_at
```

---

# 165. finished_at

```text
Execution.finished_at
```

est renseigné lors du passage dans un état terminal.

---

# 166. Attempt timestamps

```text
started_at
finished_at
```

par Attempt.

---

# 167. Retry wait duration

Peut être calculée via :

```text
next_attempt_at
```

et les timestamps des Attempts.

---

# 168. Queue duration

```text
first_attempt.started_at - queued_at
```

---

# 169. Total elapsed

```text
finished_at - started_at
```

pour une Execution démarrée.

---

# 170. End-to-end lag

Depuis l'intention :

```text
finished_at - scheduled_at
```

---

# 171. Distinguish metrics

```text
scheduling lag

queue delay

attempt duration

retry wait

execution duration

end-to-end duration
```

sont différentes.

---

# 172. Execution state derivation

Certaines propriétés peuvent être dérivées.

Exemple :

```text
attempt_count
```

peut être :

```text
len(attempts)
```

---

# 173. But persisted projections are useful

Pour performance :

```text
attempt_count
current_attempt_id
next_attempt_at
```

peuvent être persistés.

---

# 174. Source of truth

La source logique reste :

```text
Execution lifecycle + Attempt records
```

---

# 175. State transition events

Événements candidats :

```text
ExecutionCreated

ExecutionQueued

AttemptStarted

AttemptSucceeded

AttemptFailed

RetryScheduled

ExecutionSucceeded

ExecutionFailed

ExecutionCancelled

ExecutionTimedOut
```

---

# 176. Do we need ExecutionStarted?

Oui, éventuellement lorsque :

```text
first Attempt starts
```

---

# 177. Avoid duplicated events

Si :

```text
AttemptStarted #1
```

implique déjà :

```text
ExecutionStarted
```

les deux ne sont pas forcément nécessaires.

---

# 178. Recommendation

Utiliser les events nécessaires pour :

```text
audit
integration
observability
```

sans dupliquer chaque mutation.

---

# 179. Suggested event set V1

```text
ExecutionCreated

AttemptStarted

AttemptCompleted

RetryScheduled

ExecutionCompleted
```

avec payloads typés.

---

# 180. AttemptCompleted outcome

```text
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

---

# 181. ExecutionCompleted outcome

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 182. More compact event model

Cela peut être préférable pour V1.

---

# 183. Event ordering

Les events d'une même Execution doivent avoir :

```text
logical ordering
```

---

# 184. Sequence number

On peut ajouter :

```text
event_sequence
```

ou utiliser :

```text
ExecutionVersion
```

pour ordonner.

---

# 185. Why timestamps are not enough

Deux events peuvent partager :

```text
le même timestamp
```

ou arriver hors ordre dans un système distribué.

---

# 186. Versioned events

Une stratégie :

```text
execution_version
```

dans chaque event.

---

# 187. ExecutionVersion monotonic

```text
1
2
3
...
```

à chaque mutation persistée.

---

# 188. Difference from AttemptNumber

```text
AttemptNumber
```

compte les tentatives.

```text
ExecutionVersion
```

compte les mutations de l'Aggregate.

---

# 189. Command model

Commands possibles :

```text
CreateExecution

QueueExecution

StartAttempt

CompleteAttempt

ScheduleRetry

CancelExecution

TimeoutExecution
```

---

# 190. But commands are application intentions

Le domaine n'a pas besoin de classes Command pour toutes les opérations dès V1.

Les méthodes de l'Aggregate peuvent suffire.

---

# 191. Domain methods example

```text
execution.start_attempt(...)

execution.complete_attempt(...)

execution.schedule_retry(...)

execution.cancel(...)

execution.timeout(...)
```

---

# 192. CompleteAttempt orchestration

L'opération :

```text
complete_attempt(result)
```

peut nécessiter la RetryPolicy.

Deux options :

```text
Execution owns policy logic
```

ou :

```text
RetryEvaluator service
```

---

# 193. Recommendation

L'Execution protège le state transition.

Le `RetryEvaluator` produit la décision.

---

# 194. Flow

```text
AttemptResult
   │
   ▼
RetryEvaluator
   │
   ▼
RetryDecision
   │
   ▼
Execution.apply(...)
```

---

# 195. Why?

Cela garde :

```text
Execution
```

centrée sur ses invariants sans lui faire connaître toute la logique de classification des erreurs.

---

# 196. Success bypasses RetryEvaluator

Si :

```text
AttemptResult = SUCCESS
```

l'Execution se termine directement.

---

# 197. Failure branch

```text
AttemptResult = FAILURE/TIMEOUT
```

→ RetryEvaluator.

---

# 198. Cancel branch

```text
AttemptResult = CANCELLED
```

ne passe généralement pas par RetryPolicy.

Execution → CANCELLED.

---

# 199. Timeout branch nuance

`Attempt TIMED_OUT` peut être retryable.

Donc :

```text
RetryEvaluator
```

peut être utilisé.

---

# 200. Global execution deadline

Avant de créer une nouvelle Attempt :

```text
now < execution_deadline
```

doit être vérifié.

---

# 201. Retry transition sequence

```text
Attempt RUNNING
   ↓
Attempt FAILED
   ↓
RetryDecision(RETRY)
   ↓
Execution RETRY_WAIT
   ↓
now reaches retry_at
   ↓
Attempt N+1 RUNNING
```

---

# 202. No hidden state

Il faut éviter un état :

```text
FAILED_BUT_RETRYING
```

mal défini.

`RETRY_WAIT` exprime clairement la situation.

---

# 203. Execution QUEUED vs RETRY_WAIT

```text
QUEUED
```

= aucune Attempt initiale n'a encore commencé.

```text
RETRY_WAIT
```

= au moins une Attempt a déjà été exécutée et a échoué.

---

# 204. Important distinction for metrics

Cela permet de distinguer :

```text
startup queue latency
```

de :

```text
retry backoff latency
```

---

# 205. Concurrency semantics

Comme décidé dans le document 14 :

```text
QUEUED
RUNNING
RETRY_WAIT
```

comptent comme actifs pour la concurrence logique V1.

---

# 206. CREATED?

Si persistant :

```text
CREATED
```

peut également compter comme actif après admission.

---

# 207. Terminal states release slot

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

libèrent la capacité logique.

---

# 208. Attempt PENDING

Si utilisé, une Attempt `PENDING` peut exister très brièvement avant `RUNNING`.

---

# 209. Recommendation

Ne pas persister `PENDING` longtemps.

Créer l'Attempt au moment où le worker peut réellement démarrer.

---

# 210. Why?

Sinon une Attempt en `PENDING` pourrait :

```text
mourir avec le scheduler
```

et nécessiter un recovery spécifique.

---

# 211. Attempt claim

Dans un runtime distribué, un worker peut :

```text
claim execution
```

avant de créer/start l'Attempt.

---

# 212. Claim/Lease

Ce mécanisme appartient :

```text
infrastructure/runtime
```

et non à la state machine métier principale.

---

# 213. Worker ownership

Un `Attempt` peut néanmoins enregistrer :

```text
worker_id
```

comme metadata opérationnelle.

---

# 214. Not identity

`worker_id` ne fait pas partie de l'identité métier de l'Attempt.

---

# 215. Heartbeat

Même logique :

```text
heartbeat_at
```

est du runtime opérationnel.

---

# 216. Reconciliation

Un service peut détecter :

```text
RUNNING Attempt
without heartbeat
```

et la déclarer :

```text
TIMED_OUT
```

ou :

```text
FAILED(WORKER_LOST)
```

---

# 217. Reconciliation is external

La state machine accepte la transition.

Le service de reconciliation décide quand l'appliquer.

---

# 218. Scheduler shutdown

Lors d'un shutdown gracieux :

```text
QUEUED executions
```

peuvent rester persistées.

```text
RUNNING executions
```

peuvent continuer sur workers externes ou être annulées.

---

# 219. Local in-process runtime

Si workers locaux meurent avec le scheduler :

```text
RUNNING
```

doit être reconcilié au restart.

---

# 220. Restart recovery

Au redémarrage, le runtime peut trouver :

```text
Execution RUNNING
Attempt RUNNING
```

mais aucun worker vivant.

---

# 221. Possible recovery

```text
Attempt
→ FAILED(WORKER_LOST)
```

puis :

```text
RetryPolicy
```

peut décider.

---

# 222. Why not silently restart Attempt?

Parce qu'il faut préserver :

```text
Attempt history
```

Une nouvelle tentative doit avoir :

```text
AttemptNumber + 1
```

---

# 223. Execution recovery

Cas :

```text
Execution RETRY_WAIT
next_attempt_at < now
```

Au restart :

```text
retry becomes due
```

mais il s'agit toujours de la même Execution.

---

# 224. Retry due is not misfire

Important :

```text
Retry timer delayed
```

ne doit pas être traité avec :

```text
MisfirePolicy
```

---

# 225. Separate runtime timer semantics

Retry timers ont leur propre recovery.

---

# 226. Possible RetryLatePolicy?

Probablement inutile en V1.

Si le scheduler revient tard :

```text
start retry now
```

sous réserve de la Deadline.

---

# 227. Recommendation

Pour V1 :

```text
if RETRY_WAIT
and now >= next_attempt_at
and execution_deadline not exceeded
→ attempt retry now
```

---

# 228. Retry catch-up is not needed

On ne crée pas :

```text
plusieurs retries manqués
```

si le scheduler a raté plusieurs instants théoriques.

Il n'existe qu'un :

```text
next_attempt_at
```

à la fois.

---

# 229. This is another distinction

```text
Schedule recurrence
→ sequence of occurrences
```

```text
Retry backoff
→ next single retry deadline
```

---

# 230. Execution deadline recovery

Au restart :

```text
now > execution_deadline
```

→ `Execution TIMED_OUT`.

---

# 231. Cancellation recovery

Une future `CANCELLING` state nécessiterait reconciliation.

Hors V1.

---

# 232. Failure normalization

L'Attempt doit recevoir un :

```text
AttemptResult
```

normalisé.

Pas une exception brute de library.

---

# 233. AttemptResult model

```text
AttemptResult
│
├── status
├── output?
├── failure?
├── started_at
└── finished_at
```

---

# 234. AttemptResult invariants

Si :

```text
status = SUCCESS
```

alors :

```text
failure = None
```

---

# 235. Failure result invariant

Si :

```text
status = FAILED
```

alors :

```text
failure != None
```

---

# 236. Timeout result

```text
status = TIMED_OUT
```

peut avoir :

```text
FailureCategory.TIMEOUT
```

---

# 237. Cancelled result

Peut porter :

```text
CancellationReason
```

plutôt qu'un Failure normal.

---

# 238. Result immutability

Une fois l'Attempt terminale :

```text
AttemptResult
```

ne doit plus changer.

---

# 239. Execution result aggregation

L'ExecutionResult est construit depuis :

```text
final lifecycle outcome
```

pas nécessairement en copiant tout l'historique.

---

# 240. Example success

```text
Attempt 1 FAILED
Attempt 2 SUCCESS

ExecutionResult:
SUCCESS
```

---

# 241. Example failure

```text
Attempt 1 FAILED
Attempt 2 FAILED
Attempt 3 FAILED

ExecutionResult:
FAILED
final_failure = Attempt3.failure
attempt_count = 3
```

---

# 242. Execution history

L'historique complet reste consultable séparément.

---

# 243. State transition timestamps

On pourrait stocker :

```text
created_at
queued_at
started_at
finished_at
next_attempt_at
```

---

# 244. No `retry_started_at`

Chaque Attempt possède déjà :

```text
started_at
```

---

# 245. Cancellation timestamp

Optionnel :

```text
cancelled_at
```

peut être dérivé de `finished_at` si status `CANCELLED`.

---

# 246. State enum simplicity

Éviter :

```text
FAILED_RETRYABLE
FAILED_NON_RETRYABLE
WAITING_BACKOFF
WAITING_QUEUE
WAITING_WORKER
```

si des objets/contextes séparés peuvent exprimer ces nuances.

---

# 247. Recommended ExecutionState V1

```text
QUEUED
RUNNING
RETRY_WAIT
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 248. Seven states only

Ce modèle est suffisamment riche pour couvrir :

```text
initial waiting
active execution
retry delay
four terminal outcomes
```

---

# 249. ExecutionRequestState V1

```text
CREATED
QUEUED
DISPATCHED
CANCELLED
```

`EXPIRED` peut être ajouté plus tard.

---

# 250. AttemptState V1

```text
RUNNING
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

`PENDING` peut rester implicite.

---

# 251. Why omit Attempt PENDING

Une Attempt n'existe qu'au moment où elle démarre.

C'est probablement plus propre pour V1.

---

# 252. Revised Attempt machine

```text
RUNNING
   │
   ├── SUCCESS
   ├── FAILED
   ├── TIMED_OUT
   └── CANCELLED
```

Très simple.

---

# 253. Attempt creation semantics

```text
create Attempt
=
start Attempt
```

dans V1.

---

# 254. Future distributed runtime

Pourra introduire :

```text
CLAIMED
PENDING
```

si nécessaire.

---

# 255. ExecutionRequest and Concurrency

Si policy = QUEUE :

```text
ExecutionRequest
→ QUEUED
```

puis lorsqu'un slot devient libre :

```text
→ DISPATCHED
→ Execution QUEUED
```

---

# 256. Alternative simplified path

On peut aussi créer directement :

```text
Execution QUEUED
```

et considérer la Request immédiatement dispatchée.

---

# 257. Recommendation for V1

Pour limiter les doublons de state machines :

```text
ExecutionRequest
```

devrait avoir un lifecycle minimal.

Une fois l'Execution créée :

```text
la queue runtime
```

est représentée par `Execution.QUEUED`.

---

# 258. Thus

```text
ExecutionRequest
CREATED
→ DISPATCHED
```

dans le chemin nominal.

---

# 259. Queued due to concurrency

Deux choix restent possibles.

V1 peut traiter :

```text
ConcurrencyDecision = QUEUE
```

comme :

```text
create Execution in QUEUED state
```

---

# 260. Why good

Cela centralise :

```text
queueing
retry
running
terminal states
```

dans un seul Aggregate runtime.

---

# 261. Then Request states can be reduced

```text
CREATED
DISPATCHED
CANCELLED
```

---

# 262. Very clean V1 model

```text
ExecutionRequest
=
immutable intent
```

sans véritable state machine complexe.

Puis :

```text
Execution
=
runtime state machine
```

---

# 263. Recommendation strengthened

Pour PyScheduleKit V1 :

```text
ExecutionRequest
```

devrait être **quasi immutable**.

Elle possède surtout :

```text
CREATED
DISPATCHED
CANCELLED
```

éventuellement.

---

# 264. Execution owns queue state

Le véritable état :

```text
QUEUED
```

appartient à `Execution`.

---

# 265. This avoids duplication

Sinon on pourrait avoir :

```text
Request QUEUED
Execution QUEUED
```

avec des sémantiques floues.

---

# 266. Final recommended object roles

```text
ExecutionRequest
→ immutable command/intention

Execution
→ lifecycle Aggregate Root

Attempt
→ concrete execution attempt
```

---

# 267. Execution creation before capacity?

Si ConcurrencyPolicy = QUEUE :

```text
Execution
```

peut être créée et attendre.

Cela représente bien :

```text
run logique accepté
mais pas encore démarré
```

---

# 268. DROP

Si policy = DROP :

```text
aucune Execution
```

n'est créée.

L'occurrence reçoit simplement un résultat de scheduling/admission.

---

# 269. Coalescing

Le coalescing se produit avant la création de l'Execution.

---

# 270. Execution remains one logical run

Même si :

```text
5 occurrences
```

ont été coalescées.

---

# 271. State transition diagram final

```text
                     ┌────────┐
                     │ QUEUED │
                     └───┬────┘
                         │ start attempt
                         ▼
                    ┌─────────┐
                    │ RUNNING │
                    └────┬────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
    SUCCESS        Attempt failure      CANCELLED
                         │
                         ▼
                    RetryPolicy
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
           RETRY                  STOP
              │                     │
              ▼                     ▼
        ┌────────────┐             FAILED
        │ RETRY_WAIT │
        └──────┬─────┘
               │ retry_at reached
               ▼
            RUNNING
```

Global deadline may also cause:

```text
QUEUED
RUNNING
RETRY_WAIT
→ TIMED_OUT
```

selon policy.

---

# 272. Should QUEUED timeout globally?

Si ExecutionDeadline commence :

```text
à la création
```

alors oui.

Si elle commence :

```text
au first Attempt
```

alors non.

---

# 273. Need explicit deadline origin

Deux modèles :

```text
deadline_from_request
```

ou :

```text
deadline_from_execution_start
```

---

# 274. V1 recommendation

Pour `ExecutionDeadline`, utiliser :

```text
deadline absolute Instant
```

déjà résolue au moment de la création.

Cela supprime l'ambiguïté.

---

# 275. Then

Même en `QUEUED` :

```text
now >= deadline
→ TIMED_OUT
```

si le contrat le veut.

---

# 276. Queue timeout nuance

Cela peut être plus justement appelé :

```text
ExecutionDeadline
```

car elle limite tout le lifecycle.

---

# 277. AttemptTimeout separately

Chaque Attempt peut posséder :

```text
timeout_duration
```

---

# 278. ExecutionDeadline and AttemptTimeout compose

```text
effective attempt limit
=
min(
  attempt_timeout,
  remaining_execution_time
)
```

conceptuellement.

---

# 279. Example

```text
Attempt timeout = 5m
Execution deadline in 2m
```

L'Attempt ne doit pas courir 5 minutes.

---

# 280. EffectiveDeadline

Une abstraction interne peut calculer :

```text
min(
    attempt_started_at + attempt_timeout,
    execution_deadline
)
```

---

# 281. No need new public VO

Un helper/domain service suffit.

---

# 282. Execution cancellation and deadline races

Si :

```text
cancel
```

et :

```text
deadline
```

arrivent simultanément, une seule transition terminale gagne.

---

# 283. Which terminal state wins?

Cela dépend de l'ordre atomiquement accepté.

Le domaine n'a pas besoin d'imposer une priorité absolue si le store garantit une transition unique.

---

# 284. But audit must show cause

L'événement accepté doit expliquer :

```text
CANCELLED
```

ou :

```text
TIMED_OUT
```

---

# 285. Strict transition guards

Chaque mutation doit vérifier :

```text
current_state
```

avant application.

---

# 286. Example

```text
execution.complete_success(...)
```

autorisé uniquement depuis :

```text
RUNNING
```

---

# 287. `schedule_retry(...)`

autorisé uniquement si :

```text
current_state = RUNNING
latest Attempt terminal failed/timed_out
retry decision = RETRY
```

---

# 288. `start_retry_attempt(...)`

autorisé uniquement depuis :

```text
RETRY_WAIT
```

et :

```text
now >= next_attempt_at
```

---

# 289. `cancel(...)`

autorisé depuis :

```text
QUEUED
RUNNING
RETRY_WAIT
```

---

# 290. `timeout(...)`

autorisé depuis tout état non-terminal soumis à une deadline.

---

# 291. Domain exceptions

Transitions invalides peuvent produire :

```text
InvalidExecutionTransition

InvalidAttemptTransition

ExecutionAlreadyTerminal

AttemptAlreadyCompleted

RetryNotDue

ExecutionDeadlineExceeded
```

---

# 292. But normal terminal result is not exception

Recevoir un Failure et décider STOP :

```text
normal domain outcome
```

pas une exception.

---

# 293. Concurrency slot ownership

L'Execution acquiert conceptuellement :

```text
un logical concurrency slot
```

lorsqu'elle est créée/admitted.

---

# 294. Slot lifetime

Le slot est conservé pendant :

```text
QUEUED
RUNNING
RETRY_WAIT
```

---

# 295. Slot release

Lors du passage à :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 296. Important

Une Attempt n'acquiert pas un nouveau slot.

---

# 297. Retry remains inside same slot

Cela garantit :

```text
no self-conflict
```

entre retries.

---

# 298. Execution queue and slot

Question :

Si une Execution est `QUEUED` parce que le slot n'est justement pas encore disponible, peut-elle déjà « posséder » un slot ?

Non.

---

# 299. Need nuance

Deux types de queue apparaissent :

```text
waiting for concurrency admission
```

et :

```text
admitted but waiting for worker
```

---

# 300. To avoid confusion

Nous pouvons distinguer :

```text
PENDING_ADMISSION
```

de :

```text
QUEUED
```

---

# 301. But complexity

Cela réintroduit un état supplémentaire.

---

# 302. Better separation

La ConcurrencyPolicy peut conserver les demandes en attente **avant** création de l'Execution.

Ainsi :

```text
Execution
```

n'est créée qu'une fois admise.

---

# 303. This aligns conceptually

```text
ExecutionRequest QUEUED
```

= attend un slot logique.

Puis :

```text
Execution created
```

= slot acquis.

Puis :

```text
Execution QUEUED
```

= attend un worker physique.

---

# 304. But duplicate `QUEUED` terminology

Pour plus de précision :

```text
ExecutionRequest WAITING_ADMISSION
```

et :

```text
Execution QUEUED
```

---

# 305. V1 model option

Request states :

```text
PENDING
WAITING_ADMISSION
DISPATCHED
CANCELLED
```

Execution states :

```text
QUEUED
RUNNING
RETRY_WAIT
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 306. Recommendation

C'est probablement le modèle le plus sémantiquement propre.

---

# 307. Request WAITING_ADMISSION

Signifie :

```text
Occurrence accepted for eventual execution
but currently blocked by ConcurrencyPolicy
```

---

# 308. Once slot available

```text
WAITING_ADMISSION
→ DISPATCHED
```

et :

```text
Execution created in QUEUED
```

---

# 309. Then Executor capacity

```text
Execution QUEUED
```

attend un worker.

---

# 310. Separation achieved

```text
WAITING_ADMISSION
→ logical concurrency wait

QUEUED
→ physical/runtime execution wait
```

---

# 311. This is powerful

Cela sépare enfin clairement :

```text
Concurrency queue
```

de :

```text
Executor queue
```

---

# 312. Recommended Request machine V1

```text
PENDING
   │
   ├── blocked by concurrency
   ▼
WAITING_ADMISSION
   │
   ├── capacity available
   ▼
DISPATCHED
```

avec :

```text
PENDING → DISPATCHED
```

si capacité immédiate.

Cancellation :

```text
PENDING → CANCELLED

WAITING_ADMISSION → CANCELLED
```

---

# 313. DISPATCHED terminal for Request

Oui.

---

# 314. Execution initial state

```text
QUEUED
```

après création.

---

# 315. Why not CREATED?

On peut désormais supprimer `CREATED`.

L'Execution naît directement :

```text
QUEUED
```

---

# 316. Final Execution states V1

```text
QUEUED
RUNNING
RETRY_WAIT
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

---

# 317. Final Request states V1

```text
PENDING
WAITING_ADMISSION
DISPATCHED
CANCELLED
```

---

# 318. Final Attempt states V1

```text
RUNNING
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

---

# 319. Three state machines together

```text
ExecutionRequest
────────────────────────
PENDING
   │
   ├── wait for concurrency
   ▼
WAITING_ADMISSION
   │
   ▼
DISPATCHED


Execution
────────────────────────
QUEUED
   │
   ▼
RUNNING
   │
   ├── SUCCESS
   ├── FAILED
   ├── TIMED_OUT
   ├── CANCELLED
   │
   └── RETRY_WAIT
          │
          ▼
       RUNNING


Attempt
────────────────────────
RUNNING
   │
   ├── SUCCESS
   ├── FAILED
   ├── TIMED_OUT
   └── CANCELLED
```

---

# 320. Mapping events across lifecycles

Example nominal:

```text
Occurrence due
↓
Request PENDING
↓
Request DISPATCHED
↓
Execution QUEUED
↓
Attempt #1 RUNNING
↓
Attempt #1 SUCCESS
↓
Execution SUCCESS
```

---

# 321. With concurrency wait

```text
Request PENDING
↓
WAITING_ADMISSION
↓
slot available
↓
DISPATCHED
↓
Execution QUEUED
```

---

# 322. With retry

```text
Execution RUNNING
↓
Attempt #1 FAILED
↓
Execution RETRY_WAIT
↓
retry_at
↓
Attempt #2 RUNNING
↓
Attempt #2 SUCCESS
↓
Execution SUCCESS
```

---

# 323. With cancellation before dispatch

```text
Request WAITING_ADMISSION
↓
CANCELLED
```

No Execution ever exists.

---

# 324. With cancellation while queued

```text
Execution QUEUED
↓
CANCELLED
```

No Attempt necessarily exists.

---

# 325. With cancellation while running

```text
Execution RUNNING
↓
Attempt CANCELLED
↓
Execution CANCELLED
```

---

# 326. With global timeout before first attempt

```text
Execution QUEUED
↓
deadline exceeded
↓
TIMED_OUT
```

No Attempt necessarily exists.

---

# 327. With Attempt timeout and retry

```text
Attempt #1 TIMED_OUT
↓
RetryPolicy = RETRY
↓
Execution RETRY_WAIT
↓
Attempt #2
```

---

# 328. With Attempt timeout terminal

```text
Attempt #N TIMED_OUT
↓
RetryPolicy = STOP
↓
Execution FAILED
```

ou :

```text
Execution TIMED_OUT
```

selon la cause.

---

# 329. Recommendation

Si :

```text
AttemptTimeout
```

est dépassé mais l'Execution peut retry :

```text
Attempt TIMED_OUT
Execution RETRY_WAIT
```

Si :

```text
ExecutionDeadline
```

est dépassée :

```text
Execution TIMED_OUT
```

---

# 330. This distinction must be strict

Sinon les dashboards deviennent incompréhensibles.

---

# 331. Execution FAILED meaning

```text
work could not be completed
under retry policy
```

---

# 332. Execution TIMED_OUT meaning

```text
global temporal budget exhausted
```

---

# 333. Cancellation meaning

```text
execution intentionally stopped
```

---

# 334. Success meaning

```text
work completed according to target contract
```

---

# 335. Result source

L'Executor ou adapter doit traduire son résultat concret en :

```text
AttemptResult
```

---

# 336. Executor contract

Conceptuellement :

```text
execute(request, attempt_context)
→ AttemptResult
```

ou async equivalent.

---

# 337. But Executor does not mutate domain directly

L'application reçoit le résultat puis demande à :

```text
Execution Aggregate
```

d'appliquer la transition.

---

# 338. Separation

```text
Executor
→ produces technical result

Application
→ normalizes

Domain
→ validates transition
```

---

# 339. No hidden state machine inside Executor

Éviter que l'Executor gère silencieusement :

```text
retry
execution state
cancellation state
```

sans visibilité du domaine.

---

# 340. Retry ownership exception

Un Target framework comme PyWorkflowKit peut avoir son propre runtime interne.

Dans ce cas, PyScheduleKit peut considérer :

```text
WorkflowRun
```

comme une execution opaque externe.

---

# 341. External execution adapter

Une `Execution` PyScheduleKit peut alors représenter :

```text
submission / tracking
```

plutôt que chaque step interne.

---

# 342. Important bounded context

PyScheduleKit n'a pas besoin de reproduire :

```text
WorkflowRunStateMachine
```

à l'intérieur.

---

# 343. ExternalExecutionRef

On peut conserver :

```text
external_execution_ref
```

dans l'Execution.

---

# 344. Example

```text
ExecutionId = exec-42
ExternalExecutionRef = workflow-run-991
```

---

# 345. Status synchronization

L'adapter peut traduire :

```text
workflow status
```

vers :

```text
ExecutionState
```

de haut niveau.

---

# 346. But semantics should stay coarse

```text
RUNNING
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

suffisent généralement.

---

# 347. Persistence tables

Conceptuellement :

```text
EXECUTION_REQUEST

EXECUTION

ATTEMPT
```

restent séparées.

---

# 348. EXECUTION_REQUEST fields

```text
request_id
schedule_id
schedule_revision
occurrence_key
target_ref
state
scheduled_at
created_at
correlation_id
context
```

---

# 349. EXECUTION fields

```text
execution_id
request_id
state
queued_at
started_at
finished_at
next_attempt_at
attempt_count
deadline
policy_snapshot
result
version
```

---

# 350. ATTEMPT fields

```text
attempt_id
execution_id
attempt_number
state
started_at
finished_at
failure
result
worker_ref?
```

---

# 351. Unique constraints

```text
UNIQUE(request_id)
```

si une request ne produit qu'une Execution.

---

# 352. Attempts

```text
UNIQUE(
    execution_id,
    attempt_number
)
```

---

# 353. Active Attempt uniqueness

Une contrainte DB directe peut être difficile.

L'atomicité applicative/transactionnelle doit protéger :

```text
one active Attempt
```

---

# 354. Partial indexes possible

Certaines DB permettent :

```text
unique active attempt per execution
```

via index conditionnel.

C'est infrastructure spécifique.

---

# 355. State persistence as enum/string

La DB peut stocker :

```text
"running"
```

mais le domaine doit utiliser :

```text
ExecutionState
```

typé.

---

# 356. No arbitrary state string

Refuser :

```text
status = "almost_done"
```

non prévu.

---

# 357. State machine migration

Ajouter un nouvel état dans une future version est une modification importante de compatibilité.

---

# 358. Persistent state compatibility

Les anciennes valeurs doivent rester :

```text
lisibles
migrables
```

---

# 359. Serialization contract

Un state peut être sérialisé sous forme :

```text
snake_case stable
```

par exemple :

```text
retry_wait
```

---

# 360. State names are public persistence contract

Ne pas les renommer légèrement sans migration.

---

# 361. Domain event persistence

Si events append-only :

```text
ExecutionCreated
AttemptCompleted
ExecutionCompleted
```

peuvent fournir un audit.

---

# 362. Event sourcing not required

L'état courant peut rester stocké directement.

---

# 363. Current state + audit events

Modèle recommandé :

```text
state tables
+
append-only lifecycle events
```

---

# 364. Recovery from current state

Le runtime doit pouvoir scanner :

```text
Execution QUEUED

Execution RETRY_WAIT

Execution RUNNING stale
```

au démarrage.

---

# 365. Recovery categories

```text
QUEUED
→ resume dispatch

RETRY_WAIT
→ wait or retry if due

RUNNING
→ reconcile worker ownership
```

---

# 366. Terminal states

Aucune recovery active nécessaire.

---

# 367. Stale running

Le plus difficile.

---

# 368. V1 local runtime approach

Si le process redémarre :

```text
all RUNNING Attempts
```

peuvent être considérées comme :

```text
FAILED(WORKER_LOST)
```

puis RetryPolicy appliquée.

---

# 369. Distributed worker approach

Le scheduler doit d'abord vérifier :

```text
worker still alive?
```

avant d'échouer l'Attempt.

---

# 370. Thus runtime-specific reconciliation

Le domaine expose les transitions possibles.

L'infrastructure décide sur quelles observations elles reposent.

---

# 371. Reconciliation events

Possible :

```text
AttemptLost

ExecutionReconciled
```

mais pas nécessaires en V1.

---

# 372. State machine and idempotence

Chaque transition command peut inclure :

```text
command_id
```

ou :

```text
event_id
```

pour déduplication.

---

# 373. Example duplicate completion

Worker renvoie deux fois :

```text
Attempt #1 SUCCESS
```

Le second message doit être :

```text
idempotently ignored
```

ou reconnu comme déjà appliqué.

---

# 374. Optimistic locking helps

Execution version :

```text
v3 RUNNING
```

first success writes :

```text
v4 SUCCESS
```

second success based on v3 :

```text
conflict
```

---

# 375. Application handles conflict

Reload.

If already same terminal state:

```text
treat as idempotent success
```

Sinon :

```text
investigate inconsistent result
```

---

# 376. Conflicting terminal results

Example :

```text
SUCCESS
```

already stored, then:

```text
FAILED
```

arrives.

Do not overwrite.

---

# 377. Late conflicting result

Record diagnostically.

---

# 378. State transition timestamps source

Le domaine doit utiliser :

```text
explicit now
```

fourni par Clock/application.

---

# 379. No hidden datetime.now()

Même règle que tout PyScheduleKit.

---

# 380. Example

```text
execution.start_attempt(
    at=evaluation_now
)
```

---

# 381. Deterministic transition tests

Avec :

```text
FixedClock
```

les timestamps deviennent reproductibles.

---

# 382. Transition history

Un event log peut reconstruire :

```text
when queued

when started

when retry scheduled

when completed
```

---

# 383. Example timeline

```text
09:55 scheduled_at

10:00 request created

10:01 execution queued

10:03 attempt #1 started

10:04 attempt #1 failed

10:04 retry scheduled for 10:09

10:09 attempt #2 started

10:12 attempt #2 succeeded

10:12 execution success
```

---

# 384. Derived metrics

```text
scheduling_to_request
=
request.created_at - scheduled_at
```

```text
queue_wait
=
execution.started_at - execution.queued_at
```

```text
retry_wait
=
attempt2.started_at - attempt1.finished_at
```

```text
execution_elapsed
=
execution.finished_at - execution.started_at
```

---

# 385. Operational diagnostics

Le runtime doit pouvoir répondre :

```text
Pourquoi l'Execution est-elle encore active ?

Attend-elle un worker ?

Attend-elle un retry ?

Est-elle en cours ?

Quelle Attempt ?

Depuis combien de temps ?

Quelle deadline reste ?
```

---

# 386. State should be explanatory

C'est pourquoi :

```text
RETRY_WAIT
```

est préférable à un simple :

```text
RUNNING
```

pendant le backoff.

---

# 387. State should not be too granular

Mais éviter :

```text
WAITING_RETRY_FIXED_BACKOFF
WAITING_RETRY_EXPONENTIAL_BACKOFF
```

La policy fournit ce détail.

---

# 388. Cancellation during RETRY_WAIT

Transition directe :

```text
RETRY_WAIT
→ CANCELLED
```

et annuler :

```text
next_attempt_at
```

---

# 389. Cancellation during QUEUED

```text
QUEUED
→ CANCELLED
```

aucune Attempt créée.

---

# 390. Cancellation during RUNNING

Requiert :

```text
Attempt cancellation
```

puis terminalisation de l'Execution.

---

# 391. Cancellation failure

Que faire si l'Executor ne peut pas arrêter ?

Future model :

```text
CANCELLING
```

plus adapté.

V1 peut considérer la cancellation uniquement pour les executors qui la supportent.

---

# 392. CancellationCapability

Un adapter peut exposer :

```text
supports_cancellation
```

mais cela appartient à l'Execution Port contract.

---

# 393. Runtime capability negotiation

À approfondir plus tard.

---

# 394. Execution timeout while RUNNING

Le runtime doit tenter d'annuler l'Attempt.

Mais l'état métier peut devenir :

```text
TIMED_OUT
```

même si le worker met du temps à s'arrêter.

---

# 395. Zombie side effects

Cela rappelle qu'un état local :

```text
TIMED_OUT
```

ne garantit pas :

```text
remote work instantly stopped
```

---

# 396. Honest semantics

La documentation doit préciser les limites.

---

# 397. Execution state versus remote reality

Pour des executors distants :

```text
ExecutionState
```

représente :

```text
la connaissance/decision du runtime
```

pas une garantie physique absolue.

---

# 398. Reconciliation may later correct

Par exemple :

```text
CANCELLED requested
but remote success observed
```

est un cas avancé à gérer explicitement.

---

# 399. V1 avoid impossible guarantees

Ne pas promettre :

```text
hard kill
exactly once
instant cancellation
```

si l'adapter ne peut pas les fournir.

---

# 400. Lifecycle and idempotency key

L'IdempotencyKey doit rester stable pendant :

```text
toutes les Attempts
```

d'une même Execution.

---

# 401. Manual rerun

Nouvelle Execution :

```text
new ExecutionId
```

et généralement :

```text
new IdempotencyKey
```

sauf contrat spécifique.

---

# 402. Execution lineage

Un rerun peut conserver :

```text
parent_execution_id
```

ou :

```text
rerun_of
```

comme référence.

---

# 403. Out of scope V1

Mais l'architecture doit permettre ce futur lien.

---

# 404. Execution relation to Occurrence

Normalement :

```text
Occurrence
→ one primary Execution
```

en automatique.

---

# 405. Manual reruns complicate cardinality

Une même Occurrence peut avoir :

```text
multiple Executions
```

si l'utilisateur demande un rerun.

---

# 406. Therefore

Le modèle conceptuel long terme devrait être :

```text
Occurrence
1
│
└── 0..N Executions
```

avec une distinction :

```text
automatic primary execution
manual reruns
```

---

# 407. But V1 automatic scheduler

Peut conserver :

```text
0..1 automatic Execution
```

par occurrence.

---

# 408. ExecutionKind

Un futur Value Object :

```text
PRIMARY
RERUN
BACKFILL
```

peut clarifier.

---

# 409. Not needed yet

Mais utile à garder en tête.

---

# 410. Domain service map

```text
RetryEvaluator

ConcurrencyEvaluator

OccurrencePlanner
```

collaborent avec :

```text
Execution Aggregate
```

mais aucun ne doit modifier directement la base.

---

# 411. Application service orchestration

Exemple :

```text
load Execution
receive AttemptResult
normalize Failure
evaluate Retry
apply domain transition
save Execution
publish events
```

---

# 412. Executor orchestration

Pour démarrer :

```text
load due queued/retry execution
claim atomically
start Attempt
save transition
invoke Executor
```

---

# 413. Async result

Si l'Executor est async :

```text
callback/event
```

ramène le résultat plus tard.

---

# 414. State machine remains same

Que l'Executor soit :

```text
local sync

thread pool

process

Celery

remote HTTP

PyWorkflowKit
```

ne change pas les états métier principaux.

---

# 415. That's the value of the model

Le lifecycle reste stable malgré le backend.

---

# 416. ExecutorPort

Un futur contrat peut inclure :

```text
submit

cancel

inspect
```

selon besoin.

---

# 417. But no concrete API yet

Ce sera défini dans les documents architecture/runtime.

---

# 418. Invariants globaux

```text
1.
ExecutionRequest ≠ Execution ≠ Attempt.

2.
Une Execution possède une identité stable.

3.
Une Attempt appartient à exactement une Execution.

4.
Une seule Attempt active par Execution en V1.

5.
AttemptNumber est strictement croissant.

6.
Une Attempt terminale ne redémarre jamais.

7.
Un retry crée une nouvelle Attempt.

8.
Une Execution terminale ne reçoit plus de retry.

9.
SUCCESS, FAILED, CANCELLED et TIMED_OUT
sont terminaux.

10.
RETRY_WAIT possède un next_attempt_at.

11.
RUNNING implique une Attempt active.

12.
SUCCESS implique une Attempt réussie.

13.
Une Execution conserve le même OccurrenceContext.

14.
Les Schedule mutations futures ne changent pas
une Execution existante.

15.
Cancellation du Schedule n'implique pas
cancellation de l'Execution.

16.
Attempt timeout ≠ Execution timeout.

17.
Concurrency queue ≠ retry wait.

18.
Manual rerun ≠ automatic retry.

19.
Le domaine contrôle les transitions.

20.
L'infrastructure garantit l'atomicité.
```

---

# 419. Anti-pattern — one giant status

Éviter :

```text
Job.status
```

qui essaie de représenter :

```text
schedule
request
execution
attempt
```

simultanément.

---

# 420. Anti-pattern — retry by resetting Attempt

Ne jamais faire :

```text
Attempt FAILED
→ RUNNING
```

---

# 421. Anti-pattern — reopen Execution

Ne jamais faire :

```text
Execution FAILED
→ RUNNING
```

pour un manual rerun.

---

# 422. Anti-pattern — state mutation without guard

Éviter :

```python
execution.state = new_state
```

sans validation.

---

# 423. Anti-pattern — Schedule controls running Execution

Éviter :

```text
schedule.pause()
```

qui muterait automatiquement tous les runs actifs.

---

# 424. Anti-pattern — failure directly marks Execution failed

Une Attempt failure doit d'abord passer par :

```text
RetryPolicy
```

si retry supporté.

---

# 425. Anti-pattern — Attempt timeout always terminalizes Execution

Un Attempt timeout peut être retryable.

---

# 426. Anti-pattern — request and execution queue conflated

Distinguer :

```text
WAITING_ADMISSION
```

de :

```text
Execution QUEUED
```

---

# 427. Anti-pattern — queued means worker running

`QUEUED` signifie exactement l'inverse :

```text
pas encore started
```

---

# 428. Anti-pattern — timestamps overwritten

Ne pas réécrire :

```text
started_at
```

au second retry.

`Execution.started_at` reste le premier démarrage.

---

# 429. Attempt own timestamps

Chaque retry possède ses propres :

```text
Attempt.started_at
Attempt.finished_at
```

---

# 430. Anti-pattern — result mutable

Une fois terminal :

```text
ExecutionResult
```

est immutable.

---

# 431. Anti-pattern — remote exception persisted raw

Normaliser et redacter.

---

# 432. Anti-pattern — same ID for rerun

Un rerun manuel crée une nouvelle Execution identity.

---

# 433. Anti-pattern — retry queue uses Trigger recurrence

Les retries n'utilisent pas :

```text
Trigger.next_after()
```

---

# 434. Anti-pattern — stale RUNNING ignored forever

Le runtime doit prévoir une reconciliation.

---

# 435. Testing strategy

La machine à états doit être testée exhaustivement.

---

# 436. Transition tests

Pour chaque état :

```text
valid transitions

invalid transitions
```

---

# 437. Example QUEUED

Valid :

```text
→ RUNNING
→ CANCELLED
→ TIMED_OUT
```

Invalid :

```text
→ SUCCESS
→ RETRY_WAIT
```

---

# 438. Example RUNNING

Valid :

```text
→ SUCCESS
→ FAILED
→ RETRY_WAIT
→ CANCELLED
→ TIMED_OUT
```

selon contexte.

---

# 439. Example RETRY_WAIT

Valid :

```text
→ RUNNING
→ CANCELLED
→ TIMED_OUT
```

Invalid :

```text
→ SUCCESS directly
```

---

# 440. Terminal state tests

Pour chacun :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

toutes les mutations supplémentaires doivent être refusées ou idempotemment ignorées lorsqu'identiques.

---

# 441. Attempt number tests

```text
1
2
3
```

sans doublon ni saut inexpliqué.

---

# 442. One active Attempt property

Impossible de démarrer Attempt #2 pendant Attempt #1 RUNNING.

---

# 443. Retry due test

```text
now < next_attempt_at
```

→ `RetryNotDue`.

---

# 444. Retry deadline test

```text
now >= execution_deadline
```

→ `TIMED_OUT`, pas nouvelle Attempt.

---

# 445. Cancellation tests

Depuis :

```text
QUEUED
RETRY_WAIT
RUNNING
```

avec comportements adaptés.

---

# 446. Reschedule test

Modifier ScheduleDefinition ne change pas l'ExecutionPolicySnapshot.

---

# 447. Schedule cancellation test

Cancel Schedule ne change pas automatiquement Execution RUNNING.

---

# 448. Persistence round-trip

```text
Execution
→ persist
→ rehydrate
→ same lifecycle state
```

---

# 449. Attempt history round-trip

Les Attempts doivent garder :

```text
number
state
timestamps
failure
```

---

# 450. Duplicate completion test

Deux fois même completion :

```text
idempotent
```

---

# 451. Conflicting completion test

```text
SUCCESS
```

puis :

```text
FAILED
```

doit être refusé.

---

# 452. Concurrency active-state tests

```text
QUEUED
RUNNING
RETRY_WAIT
```

comptent selon la policy V1.

Terminal states non.

---

# 453. State invariant property tests

Par exemple :

```text
if state == RETRY_WAIT:
    next_attempt_at is not None
```

---

# 454. Another property

```text
if state is terminal:
    finished_at is not None
```

---

# 455. Another

```text
if started_at is not None:
    queued_at <= started_at
```

---

# 456. Another

```text
if finished_at is not None:
    started_at is None
    OR
    started_at <= finished_at
```

---

# 457. Attempt timestamps

```text
attempt.started_at <= attempt.finished_at
```

pour terminal Attempt.

---

# 458. Execution result property

```text
terminal state
↔
ExecutionResult exists
```

---

# 459. V1 recommended objects

```text
ExecutionRequest [Entity / immutable command]

Execution [Aggregate Root]

Attempt [Entity]

ExecutionState [Enum]

AttemptState [Enum]

ExecutionResult [VO]

AttemptResult [VO]

Failure [VO]

ExecutionPolicySnapshot [VO]
```

---

# 460. Recommended domain services

```text
RetryEvaluator

ConcurrencyEvaluator

OccurrencePlanner

CatchUpPlanner
```

---

# 461. Runtime ports

```text
ExecutionRepository

Attempt persistence through Execution repository
or dedicated store

Executor

Clock

ExecutionQueryPort

ConcurrencyCoordinator
```

selon l'architecture finale.

---

# 462. Model package sketch

Sans figer le code :

```text
pyschedulekit/
└── domain/
    ├── execution/
    │   ├── execution.py
    │   ├── attempt.py
    │   ├── states.py
    │   ├── results.py
    │   ├── failure.py
    │   └── policies.py
    │
    ├── scheduling/
    │   ├── schedule.py
    │   ├── occurrence.py
    │   └── trigger.py
    │
    └── services/
        ├── retry_evaluator.py
        ├── concurrency_evaluator.py
        └── occurrence_planner.py
```

Structure illustrative uniquement.

---

# 463. Final lifecycle overview

```text
TIME
 │
 ▼
Schedule
 │
 ▼
Occurrence
 │
 ▼
ExecutionRequest
 │
 ├── PENDING
 ├── WAITING_ADMISSION
 ├── DISPATCHED
 └── CANCELLED
        │
        ▼
Execution
 │
 ├── QUEUED
 ├── RUNNING
 ├── RETRY_WAIT
 ├── SUCCESS
 ├── FAILED
 ├── CANCELLED
 └── TIMED_OUT
        │
        ▼
Attempt(s)
 │
 ├── RUNNING
 ├── SUCCESS
 ├── FAILED
 ├── TIMED_OUT
 └── CANCELLED
```

---

# 464. Full happy path

```text
Schedule ACTIVE
      │
      ▼
Occurrence due
      │
      ▼
ExecutionRequest PENDING
      │
      ▼
Admission granted
      │
      ▼
ExecutionRequest DISPATCHED
      │
      ▼
Execution QUEUED
      │
      ▼
Attempt #1 RUNNING
      │
      ▼
Attempt #1 SUCCESS
      │
      ▼
Execution SUCCESS
```

---

# 465. Full retry path

```text
Occurrence
   │
   ▼
Request
   │
   ▼
Execution QUEUED
   │
   ▼
Attempt #1 RUNNING
   │
   ▼
FAILED
   │
   ▼
RetryDecision
   │
   ▼
Execution RETRY_WAIT
   │
   ▼
retry_at
   │
   ▼
Attempt #2 RUNNING
   │
   ▼
SUCCESS
   │
   ▼
Execution SUCCESS
```

---

# 466. Full concurrency wait path

```text
Occurrence
   │
   ▼
Request PENDING
   │
   ▼
Concurrency limit reached
   │
   ▼
WAITING_ADMISSION
   │
   ▼
slot released
   │
   ▼
DISPATCHED
   │
   ▼
Execution QUEUED
```

---

# 467. Full cancellation path

```text
Execution RUNNING
   │
   ▼
Cancel requested
   │
   ▼
Attempt cancellation
   │
   ▼
Attempt CANCELLED
   │
   ▼
Execution CANCELLED
```

---

# 468. Full timeout path

```text
Execution RUNNING
   │
   ▼
ExecutionDeadline reached
   │
   ▼
Attempt stop/cancel requested
   │
   ▼
Execution TIMED_OUT
```

---

# 469. Full failure path

```text
Attempt #1 FAILED
   │
   ▼
RETRY
   │
   ▼
Attempt #2 FAILED
   │
   ▼
RETRY
   │
   ▼
Attempt #3 FAILED
   │
   ▼
STOP
   │
   ▼
Execution FAILED
```

---

# 470. Core V1 state model

```text
ExecutionRequestState
─────────────────────
PENDING
WAITING_ADMISSION
DISPATCHED
CANCELLED


ExecutionState
─────────────────────
QUEUED
RUNNING
RETRY_WAIT
SUCCESS
FAILED
CANCELLED
TIMED_OUT


AttemptState
─────────────────────
RUNNING
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

---

# 471. Why this is sufficient

Ce modèle couvre :

```text
waiting for logical admission

waiting for runtime capacity

actual execution

retry backoff

success

terminal failure

cancellation

global timeout
```

sans exploser le nombre d'états.

---

# 472. Decisions proposed for V1

```text
1.
ExecutionRequest est une intention durable,
quasi immutable.

2.
Execution est l'Aggregate Root runtime.

3.
Attempt est une Entity enfant logique.

4.
Une Execution possède au maximum
une Attempt active.

5.
ExecutionRequestState V1 :
PENDING,
WAITING_ADMISSION,
DISPATCHED,
CANCELLED.

6.
ExecutionState V1 :
QUEUED,
RUNNING,
RETRY_WAIT,
SUCCESS,
FAILED,
CANCELLED,
TIMED_OUT.

7.
AttemptState V1 :
RUNNING,
SUCCESS,
FAILED,
TIMED_OUT,
CANCELLED.

8.
Retry crée toujours une nouvelle Attempt.

9.
Execution RETRY_WAIT possède next_attempt_at.

10.
Les quatre états Execution terminaux sont :
SUCCESS,
FAILED,
CANCELLED,
TIMED_OUT.

11.
Une Execution terminale ne peut être rouverte.

12.
Manual rerun crée une nouvelle Execution.

13.
AttemptTimeout peut conduire à retry.

14.
ExecutionDeadline conduit à TIMED_OUT.

15.
Schedule cancel/reschedule n'altère pas
les Executions existantes par défaut.

16.
Les mutations utilisent des transitions métier,
pas des assignments de state arbitraires.

17.
Les transitions critiques sont persistées
atomiquement.

18.
Les résultats tardifs ne réouvrent jamais
un état terminal.

19.
QUEUED, RUNNING et RETRY_WAIT
peuvent compter comme actifs
pour la concurrence logique.

20.
La state machine reste indépendante
du backend Executor.
```

---

# 473. Acceptance criteria

Le modèle est suffisamment défini si l'on peut répondre sans ambiguïté à :

```text
Quelle différence entre Request, Execution et Attempt ?

Quand une Execution est-elle créée ?

Que signifie WAITING_ADMISSION ?

Quelle différence entre WAITING_ADMISSION et QUEUED ?

Quand une Attempt existe-t-elle ?

Comment fonctionne un retry ?

Quand Execution devient-elle FAILED ?

Quelle différence entre Attempt timeout
et Execution timeout ?

Quels états sont terminaux ?

Comment fonctionne cancellation ?

Une Schedule annulée arrête-t-elle un run actif ?

Une Execution terminale peut-elle être relancée ?

Quand le slot de concurrence est-il libéré ?

Que se passe-t-il au restart avec RETRY_WAIT ?

Comment éviter deux Attempt #2 simultanées ?

Comment traiter un résultat tardif ?

Comment préserver le contexte historique
après reschedule ?
```

---

# 474. Mental model

```text
        SCHEDULING WORLD
────────────────────────────────
Schedule
   ↓
Occurrence
   ↓
ExecutionRequest
   ↓
Admission


         RUNTIME WORLD
────────────────────────────────
Execution
   ↓
Attempt
   ↓
Result
   ↓
Retry?
   ↓
Terminal ExecutionResult
```

---

# 475. The key boundary

La frontière essentielle est :

```text
ExecutionRequest
```

qui transforme :

```text
une décision de scheduling
```

en :

```text
une intention d'exécution durable
```

---

# 476. The key runtime identity

L'`ExecutionId` représente :

```text
le run logique
```

et survit à plusieurs :

```text
AttemptId
```

---

# 477. The key retry invariant

```text
Retry
=
same ExecutionId
+
new AttemptId
+
same Occurrence context
```

---

# 478. The key rerun invariant

```text
Manual Rerun
=
new ExecutionId
```

---

# 479. The key terminal invariant

```text
terminal means terminal
```

Pas de résurrection silencieuse.

---

# Conclusion

Le lifecycle d'exécution de PyScheduleKit repose désormais sur trois objets clairement séparés :

```text
ExecutionRequest
→ intention d'exécution

Execution
→ run logique

Attempt
→ tentative concrète
```

La machine à états principale devient :

```text
ExecutionRequest
PENDING
→ WAITING_ADMISSION
→ DISPATCHED
```

puis :

```text
Execution
QUEUED
→ RUNNING
→ SUCCESS
```

ou :

```text
RUNNING
→ RETRY_WAIT
→ RUNNING
```

ou vers :

```text
FAILED
CANCELLED
TIMED_OUT
```

Les `Attempt` restent volontairement simples :

```text
RUNNING
→ SUCCESS | FAILED | TIMED_OUT | CANCELLED
```

Ce découpage résout une grande partie des ambiguïtés possibles du scheduler.

Il permet notamment de conserver les distinctions suivantes :

```text
waiting for admission
≠
waiting for worker

retry wait
≠
concurrency queue

attempt failure
≠
execution failure

attempt timeout
≠
execution timeout

automatic retry
≠
manual rerun

schedule cancellation
≠
execution cancellation
```

Le principe fondamental est :

> **Une Execution est un run logique durable dont le lifecycle peut traverser plusieurs Attempts, mais dont l'identité, le contexte temporel et l'état terminal restent stables.**

---

# Suite documentaire

La prochaine étape naturelle est :

```text
17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md
```

Elle permettra enfin d'assembler le moteur complet :

```text
Clock

ScheduleRepository

NextRunTime

Schedule selection

Trigger

OccurrencePlanner

MisfirePolicy

CatchUpPlanner

ConcurrencyEvaluator

ExecutionRequest

Execution lifecycle

Retry timers
```

dans une boucle opérationnelle cohérente.

Cette étape commencera à transformer tout le **modèle métier étudié jusqu'ici** en véritable comportement de scheduler sans encore tomber dans une implémentation infrastructure trop précoce.