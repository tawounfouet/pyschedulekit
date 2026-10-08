# PyScheduleKit — Retry, Backoff & Failure Model

**Document :** `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle métier de référence  
**Nature :** Domain Model — Failure / Attempt / Retry / Backoff  
**Prérequis :**
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`
- `11_DATE_INTERVAL_AND_CRON_TRIGGERS.md`
- `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`
- `14_CONCURRENCY_AND_OVERLAP_MODEL.md`

---

# 1. Objectif

Une occurrence peut être parfaitement :

```text
planifiée
valide
non misfired
admise par la ConcurrencyPolicy
```

et malgré tout échouer pendant son exécution.

Exemple :

```text
Occurrence
10:00
   │
   ▼
ExecutionRequest
   │
   ▼
Execution
   │
   ▼
Attempt #1
   │
   ▼
HTTP 503
   │
   ▼
FAILURE
```

Le scheduler doit alors répondre à une nouvelle question :

> **Que faire lorsqu'une tentative d'exécution échoue ?**

Les réponses possibles incluent :

```text
ne pas réessayer

réessayer immédiatement

réessayer après un délai fixe

réessayer avec backoff exponentiel

arrêter après N tentatives

arrêter après une deadline

ne réessayer que certaines erreurs
```

Ce domaine est celui de :

```text
Attempt
Failure
RetryPolicy
Backoff
RetryDecision
TerminalFailure
```

---

# 2. Distinction fondamentale

Un `Retry` n'est pas :

```text
une nouvelle occurrence
```

Il appartient toujours à la même exécution logique.

Modèle :

```text
Occurrence 10:00
      │
      ▼
Execution #E1
      │
      ├── Attempt #1 FAILED
      ├── Attempt #2 FAILED
      └── Attempt #3 SUCCESS
```

La totalité représente :

```text
1 occurrence
1 execution
3 attempts
```

et non :

```text
3 occurrences
```

---

# 3. La chaîne complète

```text
Schedule
   │
   ▼
Trigger
   │
   ▼
Occurrence
   │
   ▼
Misfire / Catch-Up
   │
   ▼
Concurrency
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
   │
   ▼
RetryPolicy
```

---

# 4. Les quatre questions à ne jamais confondre

```text
Recurrence
→ Quand créer une nouvelle occurrence ?

Misfire / Catch-Up
→ Que faire des occurrences ratées ?

Concurrency
→ Peut-on lancer une nouvelle execution maintenant ?

Retry
→ Que faire lorsqu'une tentative d'une execution échoue ?
```

---

# 5. Exemple comparatif

Supposons :

```text
Schedule:
every hour
```

Occurrence :

```text
10:00
```

L'exécution échoue à :

```text
10:03
```

Puis retry à :

```text
10:05
```

La prochaine occurrence du Schedule reste :

```text
11:00
```

et non :

```text
10:05
```

---

# 6. Invariant fondamental

```text
Retry
≠
Recurrence
```

Le retry ne doit jamais modifier :

```text
Trigger
NextRunTime
Occurrence.scheduled_at
```

---

# 7. Execution

Une `Execution` représente un run logique d'une occurrence.

Elle possède :

```text
ExecutionId
RequestId
OccurrenceKey
status
attempts
result
```

Une Execution peut vivre plus longtemps qu'une tentative particulière.

---

# 8. Attempt

Un `Attempt` représente :

> Une tentative concrète d'exécuter l'Execution.

Exemple :

```text
Execution E1
│
├── Attempt 1
├── Attempt 2
└── Attempt 3
```

---

# 9. Classification DDD

```text
Execution
=
Entity
```

```text
Attempt
=
Entity
```

car chacune possède une identité/lifecycle distinct.

---

# 10. AttemptNumber

Chaque Attempt peut être identifié fonctionnellement par :

```text
ExecutionId
+
AttemptNumber
```

Exemple :

```text
Execution E1
Attempt 1
```

---

# 11. Invariant

Pour une même Execution :

```text
AttemptNumber
```

doit être :

```text
1
2
3
...
```

strictement croissant.

---

# 12. Contrainte relationnelle

Conceptuellement :

```text
UNIQUE(
    execution_id,
    attempt_number
)
```

---

# 13. Attempt lifecycle

Une tentative peut suivre :

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

# 14. Execution lifecycle

L'Execution peut suivre un lifecycle plus large :

```text
CREATED
   │
   ▼
RUNNING
   │
   ├── RETRY_WAIT
   │      │
   │      ▼
   │    RUNNING
   │
   ├── SUCCESS
   ├── FAILED
   ├── CANCELLED
   └── TIMED_OUT
```

---

# 15. Attempt status ≠ Execution status

Exemple :

```text
Attempt #1
FAILED
```

mais :

```text
Execution
RETRY_WAIT
```

Donc :

```text
Attempt FAILED
≠
Execution FAILED
```

tant qu'un retry reste possible.

---

# 16. Failure

Un `Failure` représente l'échec observé d'une tentative.

Il doit pouvoir répondre à :

```text
qu'est-ce qui a échoué ?

quelle catégorie d'erreur ?

est-elle retryable ?

quelle cause ?

quand ?
```

---

# 17. Failure comme Value Object

Une représentation de Failure peut être :

```text
Failure
│
├── category
├── code
├── message
├── retryable?
├── details
└── occurred_at
```

Classification :

```text
Value Object
```

---

# 18. FailureCategory

Une taxonomie initiale pourrait être :

```text
TRANSIENT

PERMANENT

TIMEOUT

CANCELLED

RATE_LIMITED

DEPENDENCY_UNAVAILABLE

INVALID_INPUT

AUTHENTICATION

AUTHORIZATION

UNKNOWN
```

---

# 19. Pourquoi classifier les échecs

Parce que :

```text
HTTP 503
```

et :

```text
invalid credentials
```

ne doivent pas forcément recevoir la même RetryPolicy.

---

# 20. Transient Failure

Exemples :

```text
temporary network error

HTTP 503

temporary database connection failure

rate limit

short-lived dependency outage
```

Ces erreurs peuvent souvent être :

```text
retryable
```

---

# 21. Permanent Failure

Exemples :

```text
invalid configuration

schema mismatch

resource does not exist

invalid credentials

malformed request
```

Un retry identique risque de produire exactement le même échec.

---

# 22. Retryable n'est pas une propriété universelle de l'exception

La même erreur technique peut être retryable ou non selon :

```text
operation
context
business semantics
```

Il vaut donc mieux utiliser :

```text
RetryClassifier
```

ou une policy explicite.

---

# 23. RetryPolicy

`RetryPolicy` répond :

> **Après cet échec et cet historique de tentatives, doit-on essayer à nouveau ?**

Elle peut prendre en compte :

```text
attempt_number
failure
elapsed_time
deadline
max_attempts
```

---

# 24. Classification

```text
RetryPolicy
=
Policy / Strategy
```

Elle doit idéalement rester :

```text
immutable
deterministic
side-effect free
```

---

# 25. RetryPolicy input

Conceptuellement :

```text
RetryEvaluationContext
│
├── execution
├── attempt
├── failure
├── now
├── attempt_count
└── maybe deadline
```

---

# 26. RetryDecision

La policy produit :

```text
RetryDecision
```

avec par exemple :

```text
RETRY
STOP
```

et potentiellement :

```text
retry_at
reason
```

---

# 27. RetryDecision comme Value Object

```text
RetryDecision
│
├── action
├── reason
├── retry_at?
├── delay?
└── next_attempt_number?
```

---

# 28. RetryDecisionType

```text
RETRY

STOP
```

peut suffire pour V1.

---

# 29. DecisionReason

Exemples :

```text
TRANSIENT_FAILURE

MAX_ATTEMPTS_REACHED

NON_RETRYABLE_FAILURE

DEADLINE_EXCEEDED

EXECUTION_CANCELLED

RETRY_BUDGET_EXHAUSTED
```

---

# 30. MaxAttempts

La première limite naturelle est :

```text
MaxAttempts
```

Exemple :

```text
max_attempts = 3
```

signifie :

```text
Attempt 1
Attempt 2
Attempt 3
```

maximum.

---

# 31. Attention au vocabulaire

```text
max_attempts = 3
```

signifie normalement :

```text
1 initial attempt
+
2 retries
```

et non :

```text
1 initial attempt
+
3 retries
```

---

# 32. Retry count versus Attempt count

Il est préférable de parler de :

```text
MaxAttempts
```

car :

```text
max_retries
```

est souvent ambigu.

---

# 33. Exemple

```text
MaxAttempts = 3
```

Timeline :

```text
Attempt 1 FAILED
Attempt 2 FAILED
Attempt 3 FAILED
→ Execution FAILED
```

---

# 34. Invariant

```text
attempt_count <= max_attempts
```

---

# 35. NoRetry Policy

La policy la plus simple :

```text
NoRetry
```

produit :

```text
STOP
```

après le premier échec.

---

# 36. Immediate Retry

Une policy pourrait décider :

```text
retry_at = now
```

Mais les retries immédiats répétés peuvent créer :

```text
hot loops
CPU pressure
dependency overload
```

---

# 37. Backoff

Un `Backoff` définit :

> Combien de temps attendre avant la prochaine tentative ?

Il transforme :

```text
attempt history
```

en :

```text
Duration
```

---

# 38. BackoffStrategy

Classification :

```text
BackoffStrategy
=
Strategy / Value Object comportemental
```

---

# 39. Contrat conceptuel

```text
delay_for(attempt_number)
→ Duration
```

ou :

```text
delay_for(retry_number)
→ Duration
```

La convention devra être figée.

---

# 40. Recommandation

Utiliser :

```text
retry_index
```

pour éviter la confusion.

Exemple :

```text
retry_index = 1
```

correspond au délai avant Attempt #2.

---

# 41. FixedBackoff

Exemple :

```text
5 seconds
```

pour chaque retry.

Timeline :

```text
Attempt 1 fails
    │
    +5s
    ▼
Attempt 2 fails
    │
    +5s
    ▼
Attempt 3
```

---

# 42. LinearBackoff

Formule :

```text
delay(n)
=
base × n
```

Exemple :

```text
5s
10s
15s
20s
```

---

# 43. ExponentialBackoff

Formule :

```text
delay(n)
=
base × multiplier^(n-1)
```

Exemple :

```text
base = 1s
multiplier = 2
```

donne :

```text
1s
2s
4s
8s
16s
```

---

# 44. Pourquoi Exponential Backoff

Il permet de :

```text
réagir rapidement aux erreurs courtes
```

tout en :

```text
réduisant progressivement la pression
sur une dépendance indisponible
```

---

# 45. MaximumBackoff

Sans plafond :

```text
1s
2s
4s
...
```

peut devenir énorme.

Une valeur :

```text
max_delay
```

est donc utile.

---

# 46. Exemple

```text
base = 1s
multiplier = 2
max = 30s
```

donne :

```text
1
2
4
8
16
30
30
30
...
```

---

# 47. Jitter

Si des milliers d'executions échouent simultanément et utilisent le même backoff :

```text
1s
2s
4s
```

elles risquent de réessayer toutes ensemble.

C'est un :

```text
thundering herd
```

---

# 48. Retry Jitter

Le jitter ajoute une variation au délai de retry.

Exemple :

```text
base delay = 10s

actual delay
=
between 7s and 13s
```

selon la stratégie.

---

# 49. Important

Le `Retry Jitter` du présent document est différent du :

```text
Scheduling Jitter
```

appliqué éventuellement au dispatch des occurrences.

---

# 50. Distinction

```text
Scheduling Jitter
→ décale volontairement le dispatch d'une occurrence
```

```text
Retry Jitter
→ désynchronise plusieurs retries après échec
```

---

# 51. Même mot, deux contextes

Le modèle devrait donc utiliser des noms explicites :

```text
SchedulingJitterPolicy
```

et :

```text
RetryJitterPolicy
```

ou incorporer le retry jitter dans le BackoffStrategy.

---

# 52. Determinism et Jitter

Un jitter réellement aléatoire rend les décisions non reproductibles.

Pour conserver testabilité et auditabilité, plusieurs options existent.

---

# 53. Option A — random source injectée

```text
RandomSource
```

comme Port.

---

# 54. Option B — deterministic jitter

Calculer le jitter depuis :

```text
ExecutionId
AttemptNumber
```

via un hash stable.

---

# 55. Recommandation

Pour PyScheduleKit, un jitter déterministe est particulièrement intéressant :

```text
same execution
+
same attempt
+
same policy
=
same delay
```

---

# 56. RetryAt

Une décision de retry doit produire un :

```text
retry_at
```

déterministe.

```text
retry_at
=
failure_time
+
backoff
```

ou :

```text
now
+
backoff
```

selon le contrat.

---

# 57. Recommandation

Utiliser un :

```text
decision_now
```

capturé explicitement.

Alors :

```text
retry_at = decision_now + delay
```

---

# 58. Same-now principle

Comme dans les autres domaines :

```text
RetryPolicy
```

ne doit pas appeler directement :

```text
Clock.now()
```

Le `now` doit être fourni.

---

# 59. Retry waiting state

Entre deux Attempts :

```text
Execution
=
RETRY_WAIT
```

et :

```text
retry_at
```

indique la prochaine échéance de tentative.

---

# 60. Retry timer

Question architecturale :

> Qui réveille l'Execution lorsque `retry_at` arrive ?

Deux modèles sont possibles.

---

# 61. Model A — PyScheduleKit manages retry timer

Le scheduler runtime peut conserver :

```text
retry_at
```

et réveiller l'execution.

---

# 62. Model B — Executor handles retries

L'Executor peut posséder sa propre mécanique.

---

# 63. Boundary question

Cette décision dépend de la portée réelle de PyScheduleKit.

Si PyScheduleKit veut apprendre et modéliser le scheduling des retries, il peut conserver la policy et le timer.

Si le Target est un workflow PyWorkflowKit :

```text
workflow-level retries
```

peuvent appartenir à PyWorkflowKit.

---

# 64. Règle d'ownership

Le composant qui possède :

```text
Execution
```

devrait généralement posséder :

```text
Attempt
RetryPolicy
```

pour cette Execution.

---

# 65. Retry layers

Il existe potentiellement plusieurs couches de retry :

```text
Scheduler dispatch retry

Execution retry

Workflow step retry

HTTP client retry

Database driver retry
```

Il faut éviter qu'elles se superposent sans contrôle.

---

# 66. Retry amplification

Exemple :

```text
Scheduler retries 3 times
×
Workflow retries 3 times
×
HTTP client retries 3 times
```

peut entraîner jusqu'à :

```text
27 attempts techniques
```

pour une seule intention initiale.

---

# 67. Retry budget

Une architecture mature peut donc définir :

```text
RetryBudget
```

pour limiter l'amplification globale.

---

# 68. Hors scope V1

Le `RetryBudget` cross-layer peut attendre.

Mais le principe doit être documenté :

> Les retries doivent avoir un propriétaire clair.

---

# 69. Dispatch failure

Supposons que PyScheduleKit tente d'envoyer :

```text
ExecutionRequest
```

à un Executor mais échoue avant que l'Execution distante soit créée.

C'est un :

```text
DispatchFailure
```

---

# 70. Dispatch Retry

Cela peut mériter une policy distincte :

```text
DispatchRetryPolicy
```

---

# 71. Pourquoi distinguer

Un dispatch failure signifie :

```text
le travail n'a peut-être jamais commencé
```

Alors qu'un Execution Failure signifie :

```text
le travail a commencé et a échoué
```

---

# 72. Important pour l'idempotence

Si la réponse du système distant est perdue après création du travail :

```text
did dispatch fail?
```

peut être impossible à savoir.

On entre alors dans :

```text
unknown outcome
```

et les problèmes de déduplication.

---

# 73. V1 recommendation

Séparer conceptuellement :

```text
DispatchRetry
```

de :

```text
ExecutionRetry
```

même si seule la seconde est implémentée au départ.

---

# 74. Retryable Failure classification

Une policy peut reposer sur :

```text
FailureClassifier
```

---

# 75. FailureClassifier

Contrat conceptuel :

```text
classify(failure)
→ RETRYABLE | NON_RETRYABLE | UNKNOWN
```

---

# 76. Classification

```text
FailureClassifier
=
Policy / Domain Service
```

selon sa complexité.

---

# 77. UNKNOWN

Question :

> Que faire lorsqu'on ne sait pas si l'erreur est retryable ?

Deux possibilités :

```text
fail closed
→ STOP
```

ou :

```text
retry conservatively
```

---

# 78. Recommandation V1

Par défaut :

```text
UNKNOWN
→ NON_RETRYABLE
```

est plus sûr pour éviter des boucles inattendues.

Une configuration peut éventuellement changer cela.

---

# 79. Retryable examples

```text
HTTP 429

HTTP 502

HTTP 503

temporary network failure

database connection temporarily unavailable
```

---

# 80. Non-retryable examples

```text
HTTP 400

invalid input

invalid credentials

unsupported operation

schema validation failure
```

---

# 81. Attention

Ces exemples sont généraux, pas universels.

Le Target ou adapter peut enrichir la classification.

---

# 82. Error mapping boundary

Une exception technique :

```text
requests.ConnectionError
```

ne devrait pas forcément traverser directement le domaine.

L'adapter peut la convertir en :

```text
Failure(
    category=DEPENDENCY_UNAVAILABLE,
    ...
)
```

---

# 83. Failure normalization

Cela protège le domaine contre :

```text
requests
httpx
sqlalchemy
grpc
specific SDK exceptions
```

---

# 84. Raw exception

Les détails bruts peuvent être conservés dans :

```text
diagnostics
logs
telemetry
```

mais pas nécessairement dans le Value Object public.

---

# 85. Error redaction

Attention aux :

```text
passwords
tokens
headers
personal data
```

dans les messages d'erreur.

La normalisation doit permettre la redaction.

---

# 86. Timeout

Un `Timeout` représente :

> La durée maximale autorisée pour une tentative ou execution.

Il faut distinguer :

```text
AttemptTimeout
```

et :

```text
ExecutionDeadline
```

---

# 87. AttemptTimeout

Exemple :

```text
Attempt #1
must finish within 30 seconds
```

---

# 88. ExecutionDeadline

Exemple :

```text
entire execution including retries
must finish before 10:15
```

---

# 89. Distinction

```text
AttemptTimeout
→ limite chaque tentative
```

```text
ExecutionDeadline
→ limite l'ensemble du run logique
```

---

# 90. GracePeriod ≠ Timeout

Rappel :

```text
GracePeriod
```

concerne :

```text
le retard acceptable d'une occurrence
avant sa prise en charge
```

`Timeout` concerne :

```text
la durée d'une exécution en cours
```

---

# 91. Scheduled deadline ≠ Execution deadline

Le mot `Deadline` doit toujours être qualifié.

Par exemple :

```text
SchedulingDeadline

ExecutionDeadline
```

---

# 92. Retry et ExecutionDeadline

Une RetryPolicy doit vérifier :

```text
retry_at < execution_deadline
```

sinon le retry est inutile.

---

# 93. Exemple

```text
deadline = 10:15

now = 10:14
backoff = 5m
```

Alors :

```text
retry_at = 10:19
```

dépasse la deadline.

Décision :

```text
STOP
```

---

# 94. RetryDeadlineExceeded

Reason possible :

```text
NEXT_RETRY_AFTER_DEADLINE
```

---

# 95. MaxElapsedTime

Une alternative à une Deadline absolue :

```text
MaxElapsedTime
```

depuis le début de l'Execution.

---

# 96. Exemple

```text
max_elapsed = 10 minutes
```

La policy peut arrêter les retries après dix minutes totales.

---

# 97. Deadline préférable pour la décision

Une fois l'Execution créée, on peut résoudre :

```text
execution_deadline
=
started_at + max_elapsed
```

pour obtenir un Instant stable.

---

# 98. Retry stop conditions

Une RetryPolicy peut arrêter lorsque :

```text
max attempts reached

failure non-retryable

deadline exceeded

execution cancelled

backoff would exceed deadline

policy disabled
```

---

# 99. TerminalFailure

Lorsque plus aucun retry n'est possible :

```text
Execution
→ FAILED
```

et l'échec devient :

```text
TerminalFailure
```

---

# 100. TerminalFailure

Il peut représenter :

```text
final failure
last attempt
stop reason
attempt count
completed_at
```

---

# 101. Classification

```text
TerminalFailure
=
Value Object
```

ou simplement un `ExecutionResult` de type failed.

---

# 102. Recommendation

Éviter trop d'objets si :

```text
ExecutionResult.failure(...)
```

peut porter proprement cette information.

---

# 103. ExecutionResult

Le résultat final d'une Execution peut être :

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

avec :

```text
output?
failure?
```

---

# 104. AttemptResult

Chaque Attempt peut également avoir :

```text
AttemptResult
```

pour conserver son propre résultat.

---

# 105. Difference

```text
AttemptResult
```

peut être `FAILED`.

Mais :

```text
ExecutionResult
```

peut finalement être `SUCCESS`.

---

# 106. Exemple

```text
Attempt #1 → FAILED
Attempt #2 → FAILED
Attempt #3 → SUCCESS

ExecutionResult
→ SUCCESS
```

---

# 107. Retry policy example — fixed

```text
max_attempts = 3
backoff = 5 seconds
retryable = transient failures
```

Flow :

```text
Attempt 1
FAIL
  │
  +5s
  ▼
Attempt 2
FAIL
  │
  +5s
  ▼
Attempt 3
SUCCESS
```

---

# 108. Retry policy example — exponential

```text
max_attempts = 5
base = 1s
multiplier = 2
max_delay = 10s
```

Delays :

```text
1s
2s
4s
8s
```

---

# 109. Exponential with max

Avec un sixième retry théorique :

```text
10s
```

et non :

```text
16s
```

si `max_delay=10s`.

---

# 110. Jittered exponential

Exemple conceptuel :

```text
raw delay = 8s
jitter = ±20%
```

délai réel :

```text
6.4s → 9.6s
```

selon stratégie.

---

# 111. Jitter strategy types

Possibles :

```text
NONE

FULL_JITTER

EQUAL_JITTER

BOUNDED_PERCENTAGE
```

Mais V1 n'a pas besoin de toutes.

---

# 112. V1 recommendation

Supporter :

```text
NoJitter
```

et éventuellement :

```text
DeterministicPercentageJitter
```

plus tard.

---

# 113. Keep V1 deterministic

Pour l'apprentissage initial :

```text
FixedBackoff
ExponentialBackoff
```

sans jitter suffisent.

---

# 114. RetryScheduling

Lorsqu'une RetryDecision retourne :

```text
retry_at = future Instant
```

le runtime doit conserver cette attente.

---

# 115. Retry queue

Cette attente peut être représentée par :

```text
Execution.status = RETRY_WAIT
```

et :

```text
next_attempt_at
```

---

# 116. Is retry a Schedule?

Non.

Éviter de créer dynamiquement :

```text
Schedule
```

pour chaque retry.

---

# 117. Pourquoi ?

Le retry appartient au lifecycle de :

```text
Execution
```

et non au lifecycle d'une nouvelle planification métier.

---

# 118. Scheduler runtime can still wake it

Le runtime peut utiliser une structure temporelle similaire :

```text
priority queue
timer heap
database next_attempt_at
```

sans transformer le retry en Schedule.

---

# 119. Common temporal engine, distinct domain semantics

Une même infrastructure de timers peut servir :

```text
Schedule.next_run_time

Execution.next_attempt_at
```

mais ce sont deux concepts différents.

---

# 120. Important architectural distinction

```text
shared mechanism
≠
shared domain concept
```

---

# 121. Retry and Concurrency

Nous avons défini :

```text
RETRY_WAIT
```

comme potentiellement actif pour la ConcurrencyPolicy.

Cela signifie qu'une Execution attendant son prochain Attempt peut continuer à occuper un slot logique.

---

# 122. V1 recommendation

Pour une concurrence logique :

```text
CREATED
QUEUED
RUNNING
RETRY_WAIT
CANCELLING
```

peuvent être considérés comme actifs.

---

# 123. Terminal states

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

libèrent le slot.

---

# 124. Retry and Queue

Ne pas confondre :

```text
QUEUED
```

attente avant première tentative

et :

```text
RETRY_WAIT
```

attente après un Attempt échoué.

---

# 125. Retry and catch-up

Une occurrence de catch-up peut elle-même échouer.

Exemple :

```text
Occurrence 09:00
replayed at 12:00
Attempt 1 fails
```

Retry :

```text
12:05
```

reste attaché à :

```text
Occurrence 09:00
```

---

# 126. Recovery metadata stays stable

L'Execution garde :

```text
scheduled_at = 09:00
```

tout au long de ses retries.

---

# 127. Retry and coalescing

Une Execution issue de plusieurs occurrences coalescées reste :

```text
1 Execution
```

avec :

```text
N source occurrences
```

Ses retries restent des Attempts de cette même Execution.

---

# 128. No re-coalescing on retry

Le retry ne doit pas recalculer :

```text
quelles occurrences étaient coalescées
```

Le contexte de l'Execution est déjà figé.

---

# 129. Retry and reschedule

Si le Schedule est reschedulé pendant qu'une Execution retry :

```text
Execution
```

continue selon :

```text
la RetryPolicy snapshot
```

associée à sa création, idéalement.

---

# 130. Pourquoi snapshotter la RetryPolicy

Supposons :

```text
Execution E1
created under revision 4
max_attempts = 5
```

Puis le Schedule devient :

```text
revision 5
max_attempts = 1
```

Doit-on interrompre E1 ?

Probablement non.

---

# 131. Invariant

Une Execution doit généralement conserver :

```text
la configuration d'exécution
effective au moment de sa création
```

---

# 132. ExecutionPolicySnapshot

Une abstraction possible :

```text
ExecutionPolicySnapshot
│
├── retry_policy
├── timeout_policy
├── maybe target config revision
└── source schedule revision
```

---

# 133. Classification

```text
Value Object
```

---

# 134. Alternative

Stocker simplement :

```text
ScheduleRevision
```

et pouvoir retrouver la définition historique.

Mais cela nécessite un historique durable des revisions.

---

# 135. V1 recommendation

Materialiser dans `ExecutionRequest` les paramètres nécessaires au runtime.

Cela évite de dépendre d'une ScheduleDefinition mutable ultérieurement.

---

# 136. RetryPolicy ownership revisited

Question :

> La RetryPolicy doit-elle vraiment appartenir à ScheduleDefinition ?

Pas toujours.

---

# 137. Deux niveaux

### Scheduling / dispatch retry

Peut appartenir à PyScheduleKit.

### Business execution retry

Peut appartenir au Target framework.

Exemple :

```text
PyWorkflowKit
```

peut avoir son propre step retry.

---

# 138. Recommendation

PyScheduleKit ne devrait pas essayer de piloter les retries internes d'un workflow qu'il ne possède pas.

---

# 139. PyScheduleKit Retry scope

Définir clairement :

```text
Retry of the execution boundary owned by PyScheduleKit
```

et non :

```text
retry every internal operation of the target
```

---

# 140. Direct execution case

Si Target :

```text
python:function
```

et PyScheduleKit possède directement son Executor :

```text
RetryPolicy
```

peut être pleinement gérée par PyScheduleKit.

---

# 141. Workflow target case

Si Target :

```text
workflow:daily-orders
```

PyScheduleKit peut seulement gérer :

```text
submission retry
```

ou considérer le WorkflowRun lui-même comme une execution distante.

Les retries internes appartiennent à PyWorkflowKit.

---

# 142. Ingestion target case

Même séparation avec :

```text
PyIngestKit
```

---

# 143. Transform target case

Même séparation avec :

```text
PyTransformKit
```

---

# 144. Retry Ownership Matrix

| Failure | Owner probable |
|---|---|
| Scheduler cannot persist request | Application / Persistence |
| Dispatch to Executor fails | PyScheduleKit boundary |
| Python target invocation fails | PyScheduleKit Executor |
| Workflow step fails | PyWorkflowKit |
| HTTP call inside workflow fails | Workflow/HTTP adapter |
| Database driver transient retry | Driver/adapter, cautiously |

---

# 145. Layered retries

Chaque couche doit documenter :

```text
what it retries

how many times

which failures

which backoff
```

---

# 146. Avoid invisible retries

Un adapter qui retry 10 fois silencieusement fausse :

```text
latency
metrics
attempt counts
failure semantics
```

---

# 147. Recommendation

Les retries significatifs doivent être :

```text
observable
bounded
owned
```

---

# 148. Retry context

Chaque Attempt peut porter :

```text
attempt_number
started_at
finished_at
failure
```

---

# 149. Retry metadata

L'Execution peut porter :

```text
last_failure
next_attempt_at
attempt_count
```

comme état opérationnel.

---

# 150. Source of truth

L'historique des `Attempt` est la source complète.

Les champs :

```text
attempt_count
last_failure
next_attempt_at
```

peuvent être des projections pratiques.

---

# 151. Attempt creation

Une nouvelle tentative ne doit être créée que lorsqu'elle est effectivement prête à commencer ou dispatchée, selon le lifecycle retenu.

---

# 152. Avoid precreating all Attempts

Ne pas créer :

```text
Attempt 1
Attempt 2
Attempt 3
```

dès le début.

Les retries peuvent ne jamais être nécessaires.

---

# 153. RetryDecision first

Flow :

```text
Attempt fails
   │
   ▼
RetryPolicy
   │
   ├── STOP
   │
   └── RETRY at T
          │
          ▼
    Execution RETRY_WAIT
          │
          ▼
    at retry_at
          │
          ▼
      create Attempt N+1
```

---

# 154. Failure timing

Le backoff doit commencer à partir d'un instant clairement défini.

Options :

```text
Attempt.started_at

Attempt.finished_at

RetryDecision.now
```

---

# 155. Recommendation

Utiliser :

```text
failure/attempt finished_at
```

ou :

```text
decision_now
```

si décision immédiate.

V1 peut définir :

```text
retry_at = decision_now + delay
```

---

# 156. Timeout as Failure

Lorsqu'un Attempt dépasse son timeout :

```text
Attempt
→ TIMED_OUT
```

et produit :

```text
FailureCategory.TIMEOUT
```

---

# 157. Is timeout retryable?

Cela dépend de la policy.

Exemple :

```text
network read timeout
```

peut être retryable.

Un :

```text
deterministic CPU timeout due to oversized input
```

peut ne pas l'être.

---

# 158. Cancellation

Une Attempt annulée :

```text
CANCELLED
```

ne devrait généralement pas être retryée automatiquement.

---

# 159. User cancellation

Si l'Execution est annulée volontairement :

```text
RetryPolicy
```

ne doit pas ressusciter le travail.

---

# 160. Invariant

```text
Execution CANCELLED
→ no new Attempts
```

---

# 161. Terminal failure

Une Execution devient `FAILED` lorsque :

```text
latest attempt failed
AND
RetryDecision = STOP
```

---

# 162. Terminal timeout

Une Execution peut devenir :

```text
TIMED_OUT
```

si une deadline globale est dépassée.

---

# 163. Should TIMED_OUT be FAILED?

Deux modèles :

```text
FAILED with reason TIMEOUT
```

ou :

```text
TIMED_OUT
```

comme état terminal distinct.

---

# 164. Recommendation

Conserver :

```text
TIMED_OUT
```

distinct pour observabilité.

Mais `ExecutionResult` peut regrouper :

```text
unsuccessful terminal outcomes
```

si nécessaire.

---

# 165. Retry Exhausted

Un état ou event :

```text
RetriesExhausted
```

peut indiquer :

```text
max attempts reached
```

avant que :

```text
Execution
→ FAILED
```

---

# 166. Event model

Événements possibles :

```text
AttemptStarted

AttemptSucceeded

AttemptFailed

RetryScheduled

RetryStarted

RetriesExhausted

ExecutionSucceeded

ExecutionFailed

ExecutionTimedOut
```

---

# 167. Avoid event explosion

Comme toujours, le niveau d'event doit être cohérent avec :

```text
audit
observability
volume
```

---

# 168. Metrics

Métriques utiles :

```text
attempt_count

retry_count

retry_delay_seconds

retry_exhausted_count

execution_failure_count

execution_success_after_retry_count

timeout_count

failure_category_count
```

---

# 169. Success after retry

Très utile :

```text
execution_success_after_retry_count
```

permet de savoir si les retries sont réellement efficaces.

---

# 170. Retry effectiveness

On peut mesurer :

```text
retries that eventually succeed
/
executions that retry
```

sans faire de cette métrique un invariant métier.

---

# 171. Excessive retry signal

Une hausse de :

```text
average attempts per execution
```

peut signaler une dépendance instable.

---

# 172. Retry storm

Après panne d'un service :

```text
1000 executions
```

peuvent toutes passer en retry.

Sans backoff/jitter :

```text
1000 retries simultaneously
```

peuvent empirer la panne.

---

# 173. Retry throttling

Un runtime avancé peut limiter :

```text
global retry rate
```

mais cela appartient davantage à la capacité/runtime.

---

# 174. Backoff remains per-execution policy

Il ne doit pas gérer toute la régulation globale.

---

# 175. Circuit Breaker

Un `CircuitBreaker` pourrait empêcher des retries inutiles vers une dépendance malade.

Mais :

```text
CircuitBreaker
```

n'est pas une RetryPolicy.

---

# 176. Relation

```text
RetryPolicy
→ Should this execution retry?

CircuitBreaker
→ Is this dependency currently allowed to receive calls?
```

---

# 177. Hors scope V1

Le Circuit Breaker peut appartenir aux adapters ou à un futur framework de résilience.

---

# 178. Rate limiting

Même logique :

```text
RateLimiter
≠
RetryPolicy
```

---

# 179. Backoff and rate limit

Une erreur :

```text
429
```

peut fournir :

```text
Retry-After
```

---

# 180. Server-provided retry delay

La RetryPolicy peut éventuellement utiliser :

```text
failure.retry_after_hint
```

---

# 181. RetryAfterHint

Value Object possible :

```text
Duration
```

ou :

```text
Instant
```

selon la source.

---

# 182. Policy composition

La decision peut être :

```text
delay
=
max(
  backoff_delay,
  server_retry_after
)
```

selon convention.

---

# 183. V1 simplification

Ignorer ces hints au début.

Commencer avec :

```text
NoRetry

FixedBackoffRetry

ExponentialBackoffRetry
```

---

# 184. RetryPolicy model possible

```text
RetryPolicy
│
├── MaxAttempts
├── FailureClassifier
├── BackoffStrategy
└── ExecutionDeadline?
```

---

# 185. Alternative composition

```text
RetryPolicy
→ decision logic

BackoffStrategy
→ delay logic

FailureClassifier
→ error classification
```

Cette séparation est plus flexible.

---

# 186. Recommendation

Retenir :

```text
RetryPolicy
```

comme orchestration de décision utilisant :

```text
FailureClassifier
BackoffStrategy
MaxAttempts
```

---

# 187. RetryPolicy pseudo-model

```text
if execution cancelled:
    STOP

if failure not retryable:
    STOP

if attempts >= max_attempts:
    STOP

delay = backoff.delay_for(next_retry_index)

if retry_at exceeds deadline:
    STOP

return RETRY(retry_at)
```

---

# 188. RetryClassifier deterministic

Même Failure :

```text
+
same classification policy
```

doit produire le même résultat.

---

# 189. Backoff deterministic

Même retry index :

```text
+
same strategy
```

doit produire le même délai, sauf random source explicitement injectée.

---

# 190. RetryDecision deterministic

Même context :

```text
same failure
same attempt count
same now
same policy
```

→ même décision.

---

# 191. Persistence model — Execution

Exemple :

```text
EXECUTION
────────────────
execution_id
request_id
status
attempt_count
next_attempt_at
started_at
finished_at
result
failure
```

---

# 192. Persistence model — Attempt

```text
ATTEMPT
────────────────
attempt_id
execution_id
attempt_number
status
started_at
finished_at
failure
result
```

---

# 193. Do we persist RetryDecision?

Pas nécessairement.

On peut persister :

```text
next_attempt_at
```

et produire un :

```text
RetryScheduled event
```

pour audit.

---

# 194. Why event is useful

Il permet d'expliquer :

```text
why attempt 2 occurred at 10:05
```

---

# 195. RetryScheduled payload

Exemple :

```text
ExecutionId
AttemptNumber
FailureCategory
RetryAt
Backoff
Reason
```

---

# 196. Atomicity

Après un Attempt failed :

```text
record failure
+
update Execution to RETRY_WAIT
+
set next_attempt_at
```

devra idéalement être atomique.

---

# 197. Why?

Un crash entre :

```text
Attempt FAILED
```

et :

```text
Execution RETRY_WAIT
```

peut laisser un état incohérent.

---

# 198. Transaction boundary

Le repository/application service doit protéger :

```text
Attempt result
+
Execution transition
+
retry schedule
```

comme unité cohérente lorsque possible.

---

# 199. Duplicate retry scheduling

Deux workers ne doivent pas planifier :

```text
Attempt #2
```

simultanément.

---

# 200. Unique constraint

La contrainte :

```text
UNIQUE(
 execution_id,
 attempt_number
)
```

aide à protéger cette situation.

---

# 201. Distributed worker race

Deux nodes voient :

```text
next_attempt_at <= now
```

et tentent de démarrer le même retry.

Il faut une coordination atomique.

---

# 202. Retry lease

Une :

```text
Lease
```

ou transaction peut protéger :

```text
Attempt startup
```

---

# 203. RetryPolicy ≠ Retry coordination

Encore une frontière :

```text
RetryPolicy
→ should retry, and when
```

```text
Infrastructure
→ ensure only one next attempt starts
```

---

# 204. Same pattern as Concurrency

Nous retrouvons :

```text
Domain decision
+
Infrastructure atomicity
```

---

# 205. Attempt lease expiration

Si un worker meurt pendant Attempt #2 :

```text
RUNNING
```

peut rester bloqué.

Le runtime doit pouvoir détecter :

```text
stale attempt
```

---

# 206. Stale attempt recovery

Peut produire :

```text
FailureCategory.WORKER_LOST
```

et passer par la RetryPolicy.

---

# 207. Heartbeat

Une Attempt longue peut avoir :

```text
heartbeat
```

pour prouver qu'elle est encore active.

---

# 208. Hors scope du domaine retry pur

La mécanique heartbeat appartient au runtime.

Le domaine ne reçoit que :

```text
Attempt lost/timed out
```

comme résultat.

---

# 209. Idempotence

Les retries impliquent toujours le risque de :

```text
la première tentative a peut-être partiellement réussi
```

avant de sembler échouer.

---

# 210. Example

```text
POST payment
```

le serveur traite le paiement, mais la réponse réseau est perdue.

Client voit :

```text
timeout
```

et retry.

Risque :

```text
double payment
```

---

# 211. Retry safety

La RetryPolicy devrait pouvoir connaître ou supposer :

```text
is operation idempotent?
```

---

# 212. IdempotencyKey

Une `ExecutionRequest` peut fournir :

```text
IdempotencyKey
```

stable entre les Attempts.

---

# 213. Important

Tous les retries d'une même Execution doivent utiliser :

```text
la même clé d'idempotence
```

lorsque l'adapter le supporte.

---

# 214. Different Execution

Une nouvelle occurrence doit normalement utiliser :

```text
une nouvelle IdempotencyKey
```

---

# 215. Possible derivation

```text
IdempotencyKey
=
ExecutionId
```

ou :

```text
OccurrenceKey
```

selon la sémantique.

---

# 216. Retry and exactly-once

Un retry ne peut pas à lui seul garantir :

```text
exactly once side effects
```

Cela nécessite la coopération du Target ou du système distant.

---

# 217. Honest semantic guarantee

PyScheduleKit peut garantir au mieux :

```text
stable execution identity
stable attempt history
stable idempotency token
```

mais pas contrôler tous les side effects externes.

---

# 218. Retry-safe targets

La documentation devrait encourager :

```text
idempotent operations

idempotency keys

upserts

transactional consumers
```

pour les Targets retryables.

---

# 219. Non-idempotent target

Pour un Target non idempotent :

```text
RetryPolicy = NoRetry
```

peut être plus sûr.

---

# 220. Retryability and idempotence are different

Une erreur peut être temporaire, mais le retry rester dangereux.

Donc la décision peut dépendre de :

```text
failure retryability
+
operation retry safety
```

---

# 221. RetrySafety

Une future abstraction :

```text
RetrySafety
```

pourrait être :

```text
SAFE
UNSAFE
UNKNOWN
```

---

# 222. V1 simplification

Ne pas introduire cet objet immédiatement.

Documenter simplement :

> L'utilisateur ne doit activer les retries que pour des Targets compatibles avec cette sémantique.

---

# 223. Retry and target arguments

Chaque Attempt doit normalement utiliser :

```text
les mêmes arguments d'Execution
```

---

# 224. Do not mutate inputs silently

Un retry ne devrait pas modifier les paramètres métier pour « essayer autre chose » sans policy explicite.

---

# 225. Adaptive retries

Des changements comme :

```text
use another endpoint

use fallback provider
```

relèvent plutôt :

```text
resilience routing
workflow logic
```

que d'un simple RetryPolicy.

---

# 226. Retry and result

Si Attempt #1 réussit :

```text
Execution
→ SUCCESS
```

Aucun retry ne doit être créé.

---

# 227. Late duplicate result

Dans un système distribué, Attempt #1 peut être considéré timed out, Attempt #2 démarre, puis le résultat de #1 arrive tard.

Il faut une règle.

---

# 228. First terminal result wins?

Une stratégie possible :

```text
first accepted success wins
```

puis les autres résultats sont marqués :

```text
late / ignored
```

---

# 229. Complex distributed problem

Ce sujet relève d'un modèle runtime avancé.

V1 peut supposer :

```text
un Attempt à la fois par Execution
```

---

# 230. Important invariant V1

```text
At most one active Attempt per Execution
```

---

# 231. This simplifies

```text
retry scheduling

state transitions

result acceptance

concurrency
```

---

# 232. Parallel hedged attempts

Des techniques comme :

```text
hedged requests
```

où plusieurs Attempts de la même Execution courent simultanément sont hors scope V1.

---

# 233. Retry queue ordering

Si beaucoup d'Executions atteignent :

```text
retry_at
```

simultanément, l'Executor peut les ordonner.

Ce n'est pas la RetryPolicy.

---

# 234. Retry priority

Hors scope du domaine V1.

---

# 235. Retry with Schedule cancellation

Si le Schedule est annulé pendant une Execution en `RETRY_WAIT`, faut-il stopper les retries ?

---

# 236. Rappel

```text
Cancel Schedule
≠
Cancel Execution
```

Donc par défaut :

```text
Execution continues its own lifecycle
```

y compris ses retries.

---

# 237. Explicit cascade cancellation

Une option future :

```text
cancel_active_executions=True
```

pourrait modifier cela, mais elle appartient au command/application layer.

---

# 238. Reschedule

Même principe :

```text
reschedule
```

ne modifie pas une Execution déjà créée.

---

# 239. Execution policy snapshot

Encore une justification forte pour figer la policy au moment de l'ExecutionRequest.

---

# 240. Retry and Deadline from Schedule

Une Schedule peut éventuellement définir :

```text
execution_timeout
retry policy
```

mais une Execution doit les snapshotter.

---

# 241. Failure escalation

Après TerminalFailure, le système peut :

```text
emit event
send alert
move to DLQ
trigger workflow
```

---

# 242. But RetryPolicy should stop there

La RetryPolicy répond :

```text
retry or stop
```

Pas :

```text
who to notify
```

---

# 243. Dead Letter Queue

Une DLQ peut recevoir les failures terminales.

Mais elle appartient :

```text
runtime/integration
```

et non à la logique pure du retry.

---

# 244. Failure handler

Un futur :

```text
FailureSink
```

Port peut permettre :

```text
DLQ
alerting
audit
```

---

# 245. Observability

Chaque Attempt devrait permettre de répondre à :

```text
quel numéro ?

quand a-t-il commencé ?

combien de temps ?

pourquoi a-t-il échoué ?

le failure était-il retryable ?

quel délai a été choisi ?

quelle prochaine tentative ?
```

---

# 246. Example timeline

```text
10:00:00  Attempt #1 starts
10:00:03  Attempt #1 fails
10:00:03  RetryDecision → +5s

10:00:08  Attempt #2 starts
10:00:11  Attempt #2 fails
10:00:11  RetryDecision → +10s

10:00:21  Attempt #3 starts
10:00:24  Attempt #3 succeeds
```

---

# 247. Execution timeline

```text
scheduled_at:      09:55
execution started: 10:00
attempt #1:        10:00 → 10:00:03
retry wait:        10:00:03 → 10:00:08
attempt #2:        10:00:08 → 10:00:11
retry wait:        10:00:11 → 10:00:21
attempt #3:        10:00:21 → 10:00:24
execution success: 10:00:24
```

---

# 248. Execution duration

On peut définir :

```text
execution elapsed
=
finished_at - started_at
```

incluant :

```text
retry waits
```

---

# 249. Active execution time

Une autre métrique pourrait exclure les waits.

```text
sum(attempt durations)
```

Les deux sont utiles.

---

# 250. Retry wait duration

```text
total_retry_wait
```

permet de distinguer :

```text
slow work
```

de :

```text
long recovery delays
```

---

# 251. Failure reason preservation

Le résultat final doit conserver :

```text
final failure
```

mais l'historique complet des Attempts doit permettre de voir les erreurs précédentes.

---

# 252. Example

```text
Attempt 1: HTTP 503
Attempt 2: HTTP 503
Attempt 3: timeout
```

Terminal failure :

```text
timeout
```

mais l'historique montre une dépendance instable.

---

# 253. Retry reason

Une request de retry peut référencer :

```text
previous_attempt_id
```

pour chaîner clairement l'historique.

---

# 254. Attempt causality

```text
Attempt #2
caused_by_retry_of
Attempt #1
```

est implicite via `attempt_number`, mais un lien explicite peut être utile.

---

# 255. V1 simplification

`execution_id + attempt_number` suffit.

---

# 256. Retry serialization

Exemple NoRetry :

```json
{
  "kind": "none"
}
```

---

# 257. Fixed retry serialization

```json
{
  "kind": "fixed",
  "max_attempts": 3,
  "delay_seconds": 5
}
```

---

# 258. Exponential serialization

```json
{
  "kind": "exponential",
  "max_attempts": 5,
  "base_delay_seconds": 1,
  "multiplier": 2,
  "max_delay_seconds": 30
}
```

---

# 259. With classifier

```json
{
  "kind": "exponential",
  "max_attempts": 5,
  "retry_on": [
    "TRANSIENT",
    "RATE_LIMITED",
    "DEPENDENCY_UNAVAILABLE"
  ],
  "base_delay_seconds": 1,
  "multiplier": 2,
  "max_delay_seconds": 30
}
```

---

# 260. Validation

Refuser :

```text
max_attempts < 1
```

---

# 261. Fixed delay validation

Refuser :

```text
delay < 0
```

---

# 262. Exponential validation

Refuser :

```text
base_delay < 0

multiplier < 1

max_delay < base_delay
```

selon la sémantique choisie.

---

# 263. Zero delay

Un délai zéro peut être techniquement valide pour :

```text
immediate retry
```

mais doit être explicitement supporté.

---

# 264. Infinite retries

```text
max_attempts = infinite
```

est dangereux.

---

# 265. V1 recommendation

Toujours exiger :

```text
finite max_attempts
```

---

# 266. Why?

Pour garantir :

```text
bounded resource usage

eventual terminal state

simpler reasoning
```

---

# 267. Infinite retry future

Si nécessaire, il devra être accompagné de :

```text
deadline
budget
cancellation
```

et non être un simple drapeau.

---

# 268. Retry deadline validation

Une ExecutionDeadline déjà dépassée interdit la création d'une nouvelle Attempt.

---

# 269. Backoff overflow

Les calculs exponentiels doivent protéger contre :

```text
numeric overflow

unreasonably large duration
```

---

# 270. Clamp

Utiliser :

```text
max_delay
```

avant d'atteindre des valeurs extrêmes.

---

# 271. Retry search is not Trigger calculation

Aucune utilisation de :

```text
Trigger.next_after()
```

pour les retries.

Le backoff calcule directement :

```text
retry_at
```

---

# 272. Anti-pattern — retry creates new occurrence

À éviter absolument.

---

# 273. Anti-pattern — mutate scheduled_at

Le retry n'affecte jamais :

```text
Occurrence.scheduled_at
```

---

# 274. Anti-pattern — retry on every exception

Certaines erreurs ne peuvent pas être réparées par un second essai.

---

# 275. Anti-pattern — unbounded retry

Risque :

```text
infinite loops
resource leaks
hidden failures
```

---

# 276. Anti-pattern — retry with no backoff

Pour les dépendances indisponibles :

```text
retry immediately forever
```

peut aggraver la panne.

---

# 277. Anti-pattern — retry hidden in adapters

Les retries invisibles rendent :

```text
attempt count
latency
failure reporting
```

incohérents.

---

# 278. Anti-pattern — same policy for every layer

Un retry HTTP interne et un retry de workflow complet n'ont pas la même portée ni le même coût.

---

# 279. Anti-pattern — random jitter without injected source

Rend :

```text
tests flaky
replay impossible
```

---

# 280. Anti-pattern — retry changes business input

Sauf policy explicite, une tentative est une nouvelle tentative de la même execution, pas une autre opération métier.

---

# 281. Anti-pattern — failure details expose secrets

Les erreurs persistées doivent être redacted.

---

# 282. Anti-pattern — cancellation triggers retry

Une cancellation volontaire n'est pas un incident temporaire.

---

# 283. Anti-pattern — timeout equals misfire

Un misfire a lieu avant l'exécution.

Un timeout a lieu pendant l'exécution.

---

# 284. Anti-pattern — queue wait equals backoff

```text
QUEUE
```

attend pour concurrence/capacité.

```text
RETRY_WAIT
```

attend après un échec.

Deux causes différentes.

---

# 285. Domain objects recommandés

```text
Execution [Entity]

Attempt [Entity]

AttemptNumber [VO]

Failure [VO]

FailureCategory [VO/Enum]

RetryPolicy [Policy]

BackoffStrategy [Strategy]

MaxAttempts [VO]

RetryDecision [VO]

ExecutionDeadline [VO]

ExecutionResult [VO]
```

---

# 286. Ports possibles

```text
Clock
Executor
FailureMapper?
AttemptRepository?
ExecutionRepository
```

mais la forme précise sera définie dans l'architecture runtime.

---

# 287. Domain services possibles

```text
RetryEvaluator
```

si la logique n'est pas portée directement par `RetryPolicy`.

---

# 288. RetryEvaluator

Input :

```text
Execution state
latest Attempt
Failure
RetryPolicy
now
```

Output :

```text
RetryDecision
```

---

# 289. Application flow

```text
Attempt finishes
      │
      ▼
Normalize result
      │
      ├── SUCCESS
      │     │
      │     ▼
      │ Execution SUCCESS
      │
      └── FAILURE
            │
            ▼
      FailureClassifier
            │
            ▼
        RetryPolicy
            │
       ┌────┴────┐
       │         │
       ▼         ▼
     STOP      RETRY
       │         │
       ▼         ▼
 Execution    Backoff
   FAILED        │
                 ▼
              retry_at
                 │
                 ▼
        Execution RETRY_WAIT
```

---

# 290. At retry time

```text
Clock.now >= retry_at
       │
       ▼
atomic retry admission
       │
       ▼
create Attempt N+1
       │
       ▼
RUNNING
```

---

# 291. Atomic transition

Le passage :

```text
RETRY_WAIT
→
RUNNING
```

doit être protégé contre les doubles workers.

---

# 292. Distributed correctness

Comme pour les autres parties du scheduler :

```text
domain decides
infrastructure coordinates
```

---

# 293. Integration with Concurrency

Si une Execution en `RETRY_WAIT` occupe son slot :

```text
retry wake-up
```

n'a pas besoin de refaire une admission contre sa propre ConcurrencyKey.

Elle possède déjà son run logique.

---

# 294. Important distinction

```text
Concurrency admission
```

a lieu au niveau de l'Execution.

Les Attempts internes ne doivent pas se concurrencer contre leur propre parent.

---

# 295. This simplifies semantics

Une fois Execution admise :

```text
its retries remain inside that logical slot
```

jusqu'à terminal state.

---

# 296. Alternative

Si `RETRY_WAIT` libère le slot, le prochain Attempt devra potentiellement réacquérir la capacité.

C'est beaucoup plus complexe.

---

# 297. V1 recommendation

```text
RETRY_WAIT keeps the logical concurrency slot.
```

---

# 298. Retry and Executor capacity

Même si le slot logique est conservé, le worker physique n'est pas occupé pendant le backoff.

---

# 299. Good separation

```text
logical slot
≠
physical worker
```

---

# 300. Manual retry

Après une Execution terminalement FAILED, un utilisateur peut demander :

```text
retry manually
```

Question :

> Est-ce la même Execution ou une nouvelle Execution ?

---

# 301. Recommendation

Un manual retry après terminal failure devrait créer :

```text
a new Execution
```

ou un concept :

```text
Rerun
```

plutôt que rouvrir une Entity terminale.

---

# 302. Why?

Les états terminaux restent réellement terminaux.

Cela préserve :

```text
audit
identity
lifecycle clarity
```

---

# 303. Automatic Retry versus Manual Rerun

```text
Automatic Retry
→ same Execution, new Attempt
```

```text
Manual Rerun
→ new Execution, same or related Occurrence
```

---

# 304. Critical distinction

```text
Retry
≠
Rerun
```

---

# 305. Rerun and Backfill

Un rerun d'une occurrence historique peut être proche d'un backfill manuel.

Ce sujet pourra être traité ultérieurement.

---

# 306. Failure recovery hierarchy

```text
Attempt Failure
   │
   ▼
Automatic Retry?
   │
   ├── yes → next Attempt
   │
   └── no
        │
        ▼
Execution Failed
        │
        ▼
Manual Rerun / Alert / DLQ
```

---

# 307. Retry Policy examples by workload

## Stateless HTTP refresh

```text
MaxAttempts 5
ExponentialBackoff
```

pertinent.

---

## Financial posting

```text
NoRetry
```

ou retry uniquement avec idempotency guarantees.

---

## Long-running workflow

Retry probablement géré :

```text
inside PyWorkflowKit
```

---

# 308. File ingestion

Une lecture distante temporairement indisponible peut être :

```text
retryable
```

mais une erreur de format de fichier est :

```text
non-retryable
```

---

# 309. Data transformation

Un manque temporaire de ressource peut être retryable.

Un schéma invalide est probablement permanent.

---

# 310. Error semantics belong partly to adapter

Le domaine générique ne peut pas comprendre toutes les erreurs métier.

L'adapter doit fournir une classification normalisée.

---

# 311. Failure code

Un `Failure` peut porter :

```text
code
```

comme :

```text
HTTP_503
CONNECTION_RESET
INVALID_SCHEMA
AUTH_FAILED
```

sans dépendre de l'exception technique brute.

---

# 312. Machine-readable first

La policy doit raisonner sur :

```text
category / code
```

pas sur parsing du message texte.

---

# 313. Human-readable message

Le message reste utile pour :

```text
logs
diagnostic
UI
```

mais pas comme règle métier principale.

---

# 314. Failure cause chain

Une chaîne de causes complète peut être conservée dans :

```text
telemetry
```

sans forcément devenir un énorme Value Object.

---

# 315. Retry policy versioning

Changer une RetryPolicy dans un Schedule est un changement de :

```text
ScheduleDefinition
```

donc :

```text
ScheduleRevision += 1
```

si PyScheduleKit possède cette policy.

---

# 316. Running executions unaffected

Une Execution déjà créée doit conserver :

```text
old effective policy
```

---

# 317. Retry serialization version

Les policies persistées devraient être versionnées comme les triggers.

Exemple :

```json
{
  "schema_version": 1,
  "kind": "fixed",
  "max_attempts": 3,
  "delay_seconds": 5
}
```

---

# 318. Unknown policy kind

Doit produire :

```text
UnsupportedRetryPolicy
```

---

# 319. Error model possible

```text
InvalidRetryPolicy

InvalidMaxAttempts

InvalidBackoff

UnsupportedRetryPolicy

NonRetryableFailure

RetryDeadlineExceeded

RetriesExhausted

RetryAdmissionConflict
```

---

# 320. NonRetryableFailure is not necessarily an exception

Cela peut être simplement :

```text
DecisionReason
```

plutôt qu'une erreur levée.

---

# 321. Domain decisions should not use exceptions for normal outcomes

```text
STOP because max attempts reached
```

est un résultat métier attendu.

Pas nécessairement une exception technique.

---

# 322. Exception versus domain outcome

Utiliser des exceptions pour :

```text
invalid configuration
corruption
unsupported state
```

et des Value Objects pour :

```text
normal retry decisions
```

---

# 323. Test strategy

Le modèle doit être testable entièrement avec :

```text
FixedClock
fake Failure
fake Execution
```

sans réseau réel.

---

# 324. Test — NoRetry

Attempt #1 fails.

Expected :

```text
STOP
Execution FAILED
```

---

# 325. Test — FixedBackoff

```text
now = 10:00
delay = 5s
```

Expected :

```text
retry_at = 10:00:05
```

---

# 326. Test — Exponential

Retry indices :

```text
1 → 1s
2 → 2s
3 → 4s
4 → 8s
```

---

# 327. Test — MaxBackoff

Raw :

```text
32s
```

Max :

```text
10s
```

Expected :

```text
10s
```

---

# 328. Test — MaxAttempts

```text
max_attempts = 3
attempt_count = 3
```

Expected :

```text
STOP
```

---

# 329. Test — Retryable failure

```text
category = TRANSIENT
```

Expected :

```text
RETRY
```

si budget disponible.

---

# 330. Test — Permanent failure

```text
category = INVALID_INPUT
```

Expected :

```text
STOP
```

---

# 331. Test — Deadline

```text
now = 10:14
delay = 5m
deadline = 10:15
```

Expected :

```text
STOP
```

---

# 332. Test — Cancellation

Execution cancelled before retry time.

Expected :

```text
no next Attempt
```

---

# 333. Test — same scheduled_at

All Attempts must preserve:

```text
Occurrence.scheduled_at
```

indirectly through the same Execution.

---

# 334. Test — one active Attempt

Attempt #2 cannot start while Attempt #1 is still RUNNING.

---

# 335. Test — deterministic policy

Same:

```text
Failure
Attempt count
now
RetryPolicy
```

must yield same `RetryDecision`.

---

# 336. Test — serialization round-trip

```text
RetryPolicy
→ serialize
→ deserialize
→ semantically equal policy
```

---

# 337. Test — retry slot

Execution in `RETRY_WAIT` should count as active if V1 concurrency semantics say so.

---

# 338. Test — Schedule reschedule

Change retry policy on revision 5.

Execution created under revision 4 continues using revision 4's snapshot.

---

# 339. Test — duplicate attempt

Creating two Attempt #2 for same Execution must fail.

---

# 340. Test — unknown failure

V1 recommended:

```text
UNKNOWN
→ STOP
```

---

# 341. Test — zero delay

If allowed:

```text
delay=0
```

must not create an infinite same-loop inside one evaluation cycle.

The runtime should schedule the next Attempt as a separate transition.

---

# 342. Anti-hot-loop guard

Même pour :

```text
retry_at = now
```

le moteur doit éviter :

```text
while failure:
    retry instantly
```

dans une seule stack.

---

# 343. Async transition

Chaque retry doit être un nouvel événement/lifecycle step.

---

# 344. Observability example

```text
Execution:
exec-42

Occurrence:
10:00

Attempt 1:
FAILED
DEPENDENCY_UNAVAILABLE

Retry policy:
Exponential
max_attempts=4

Retry delay:
2s

Next attempt:
10:00:07
```

---

# 345. Final failure diagnostic

```text
Execution:
exec-42

Attempts:
4

Final category:
DEPENDENCY_UNAVAILABLE

Stop reason:
MAX_ATTEMPTS_REACHED

Status:
FAILED
```

---

# 346. Recommended V1 types

```text
RetryPolicy
│
├── NoRetry
├── FixedRetry
└── ExponentialRetry
```

---

# 347. FixedRetry

Configuration :

```text
max_attempts
delay
retryable_categories
```

---

# 348. ExponentialRetry

Configuration :

```text
max_attempts
base_delay
multiplier
max_delay
retryable_categories
```

---

# 349. V1 Failure categories

Une liste réduite suffit :

```text
TRANSIENT

PERMANENT

TIMEOUT

CANCELLED

UNKNOWN
```

Les adapters peuvent mapper leurs codes détaillés vers ces catégories.

---

# 350. V1 retryable defaults

Possible :

```text
TRANSIENT → yes

TIMEOUT → configurable

PERMANENT → no

CANCELLED → no

UNKNOWN → no
```

---

# 351. Why TIMEOUT configurable

Certains timeouts sont temporaires.

D'autres signalent une opération intrinsèquement trop lente.

---

# 352. V1 Backoff strategies

```text
FixedBackoff

ExponentialBackoff
```

suffisent.

---

# 353. V1 no jitter initially

Pour préserver :

```text
simplicity
determinism
learning clarity
```

Retry Jitter peut être ajouté ensuite.

---

# 354. V1 timeout model

Support conceptuel :

```text
AttemptTimeout
```

et éventuellement :

```text
ExecutionDeadline
```

sans implémenter immédiatement toutes les combinaisons.

---

# 355. Core invariants

```text
1.
Retry ne crée jamais une nouvelle Occurrence.

2.
Toutes les Attempts d'une Execution
partagent la même Occurrence.

3.
AttemptNumber est strictement croissant.

4.
Une seule Attempt active par Execution en V1.

5.
RetryPolicy est bornée.

6.
max_attempts >= 1.

7.
Une cancellation volontaire ne retry pas.

8.
Un Failure non-retryable arrête l'Execution.

9.
Backoff ne modifie jamais scheduled_at.

10.
Retry wait ≠ concurrency queue wait.

11.
Attempt failure ≠ Execution failure
tant qu'un retry reste possible.

12.
Une Execution terminale ne peut pas
recevoir de nouvelle Attempt automatique.

13.
Une Execution conserve la policy effective
au moment de sa création.

14.
Le domaine décide si/quand retry ;
l'infrastructure garantit une transition unique.

15.
Les retries significatifs doivent être observables.
```

---

# 356. Décisions proposées pour PyScheduleKit V1

```text
1.
Execution est une Entity.

2.
Attempt est une Entity enfant logique
de l'Execution.

3.
Retry reste dans le lifecycle
de la même Execution.

4.
V1 autorise au maximum
une Attempt active par Execution.

5.
RetryPolicy utilise MaxAttempts,
pas un max_retries ambigu.

6.
V1 supporte :
NoRetry,
FixedRetry,
ExponentialRetry.

7.
Les retries sont toujours bornés.

8.
RetryPolicy ne lit pas Clock directement.

9.
Le now de décision est fourni explicitement.

10.
FailureCategory V1 :
TRANSIENT,
PERMANENT,
TIMEOUT,
CANCELLED,
UNKNOWN.

11.
UNKNOWN n'est pas retryable par défaut.

12.
Backoff V1 :
FixedBackoff,
ExponentialBackoff.

13.
Retry Jitter est hors V1 initial.

14.
RETRY_WAIT compte comme Execution active
pour la concurrence logique.

15.
Les retries utilisent le même
ExecutionId et la même identité d'occurrence.

16.
Les paramètres nécessaires au retry
sont snapshotés dans l'ExecutionRequest/
Execution.

17.
Schedule cancel/reschedule ne modifie pas
automatiquement une Execution déjà créée.

18.
Manual rerun crée une nouvelle Execution
plutôt que de rouvrir une Execution terminale.
```

---

# 357. Modèle conceptuel final

```text
                        Occurrence
                            │
                            ▼
                     ExecutionRequest
                            │
                            ▼
                        Execution
                            │
                            ▼
                        Attempt #1
                            │
                      ┌─────┴─────┐
                      │           │
                      ▼           ▼
                   SUCCESS      FAILURE
                      │           │
                      ▼           ▼
               Execution      RetryPolicy
                 SUCCESS          │
                           ┌───────┴────────┐
                           │                │
                           ▼                ▼
                         STOP             RETRY
                           │                │
                           ▼                ▼
                    Execution FAILED     Backoff
                                            │
                                            ▼
                                         retry_at
                                            │
                                            ▼
                                    Execution RETRY_WAIT
                                            │
                                            ▼
                                        Attempt #2
```

---

# 358. Position dans le modèle global

```text
Trigger
→ produit des occurrences

MisfirePolicy
→ traite le retard avant execution

ConcurrencyPolicy
→ contrôle l'admission des runs

RetryPolicy
→ traite les échecs après tentative

BackoffStrategy
→ calcule quand réessayer

Executor
→ exécute concrètement les Attempts
```

---

# 359. Tableau de séparation définitif

| Concept | Question |
|---|---|
| Trigger | Quand existe la prochaine occurrence ? |
| MisfirePolicy | Que faire si l'occurrence est trop tardive ? |
| CatchUpPolicy | Quelles occurrences manquées récupérer ? |
| ConcurrencyPolicy | Peut-on admettre cette execution maintenant ? |
| RetryPolicy | Faut-il retenter cette execution après échec ? |
| BackoffStrategy | Combien de temps attendre avant la nouvelle tentative ? |
| Executor | Comment lancer concrètement la tentative ? |

---

# 360. Modèle mental essentiel

```text
Occurrence
    │
    ▼
Execution
    │
    ├──────── Attempt #1 ─────── FAIL
    │                              │
    │                           Backoff
    │                              │
    ├──────── Attempt #2 ◀────────┘
    │              │
    │              └────────── FAIL
    │                           │
    │                        Backoff
    │                           │
    └──────── Attempt #3 ◀──────┘
                   │
                   ▼
                SUCCESS
```

Tout cela reste :

```text
UNE SEULE OCCURRENCE
UNE SEULE EXECUTION
PLUSIEURS ATTEMPTS
```

---

# Conclusion

Le modèle de retry de PyScheduleKit doit préserver une distinction absolument fondamentale :

```text
Occurrence
≠
Execution
≠
Attempt
```

Une occurrence représente :

```text
une intention temporelle
```

Une Execution représente :

```text
un run logique de cette occurrence
```

Une Attempt représente :

```text
une tentative technique de réaliser ce run
```

Le retry ne doit donc jamais être modélisé comme une nouvelle occurrence ou un nouveau Trigger.

Le cœur du domaine devient :

```text
Attempt Failure
      │
      ▼
Failure Classification
      │
      ▼
RetryPolicy
      │
  ┌───┴────┐
  │        │
 STOP    RETRY
  │        │
  ▼        ▼
FAILED   Backoff
           │
           ▼
        retry_at
           │
           ▼
      Next Attempt
```

Le principe directeur est :

> **Le Trigger contrôle la répétition temporelle du travail ; la RetryPolicy contrôle la répétition technique d'une même Execution après échec.**

Ces deux répétitions peuvent employer des mécanismes temporels similaires, mais elles n'ont pas la même sémantique métier.

---

# Suite documentaire

La suite naturelle peut maintenant être :

```text
16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md
```

pour réunir définitivement :

```text
ExecutionRequest

Execution

Attempt

ExecutionResult

Cancellation

Timeout

RetryWait

Terminal states
```

dans une machine à états cohérente.

Elle pourra ensuite préparer :

```text
17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md
```

où nous assemblerons enfin :

```text
Clock
Schedule
Trigger
OccurrencePlanner
MisfirePolicy
CatchUpPlanner
ConcurrencyEvaluator
Retry timers
NextRunTime
```

dans la boucle réelle du moteur de scheduling.