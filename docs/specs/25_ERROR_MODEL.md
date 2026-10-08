# PyScheduleKit — Error Model

**Document :** `25_ERROR_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Spécification du modèle d’erreurs V1  
**Nature :** Error Model — Exceptions / Failures / Validation / Conflicts / Normalization / Retryability  
**Langue :** Français

**Documents de référence :**
- `15_RETRY_BACKOFF_AND_FAILURE_MODEL.md`
- `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`
- `19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md`
- `20_DISTRIBUTED_COORDINATION_LEASES_AND_LEADER_ELECTION.md`
- `21_OBSERVABILITY_AUDIT_EVENTS_AND_DIAGNOSTICS_MODEL.md`
- `23_TARGET_ARCHITECTURE.md`
- `24_PUBLIC_API_SPEC.md`

---

# 1. Objectif

PyScheduleKit doit distinguer plusieurs phénomènes souvent regroupés abusivement sous le mot :

```text
error
```

Par exemple :

```text
Cron expression invalide

Schedule introuvable

Transition PAUSED → COMPLETED interdite

Conflit de version en base

Base PostgreSQL inaccessible

Target HTTP répond 503

Tentative dépasse son timeout

Lease perdue

Execution arrive au bout de ses retries
```

Ces situations ne doivent pas être traitées de la même manière.

La question centrale devient :

> **Comment représenter, classifier, propager et exposer une erreur sans confondre une erreur de programmation, un conflit métier, une panne d’infrastructure et un échec normal d’exécution ?**

---

# 2. Principe fondamental

PyScheduleKit distingue quatre notions :

```text
Exception

Domain/Application Error

Failure

Decision
```

---

# 3. Exception

Une `Exception` est un mécanisme de contrôle Python indiquant qu’une opération n’a pas pu satisfaire son contrat.

Exemples :

```text
InvalidCronExpressionError

ScheduleNotFoundError

PersistenceUnavailableError
```

---

# 4. Failure

Un `Failure` est un objet de domaine/runtime décrivant :

> **Le résultat négatif normalisé d’une tentative réelle d’exécution.**

Exemple :

```text
Attempt
↓
HTTP request
↓
503 Service Unavailable
↓
Failure(
    category=TRANSIENT,
    code="http_503",
    retryable=True,
)
```

---

# 5. Decision

Une `Decision` représente ce que le framework décide à partir de faits.

Exemples :

```text
RetryDecision.RETRY

RetryDecision.STOP

AdmissionDecision.DEFER

SchedulingDecision.SKIP
```

---

# 6. Très important

```text
Exception
≠
Failure
≠
RetryDecision
```

---

# 7. Exemple complet

```text
requests.Timeout
        │
        ▼
HttpExecutorAdapter
        │
        ▼
Failure(
    category=TIMEOUT,
    code="http_timeout"
)
        │
        ▼
RetryEvaluator
        │
        ▼
RetryDecision.RETRY
```

Le `requests.Timeout` :

```text
ne doit pas remonter brut
```

jusqu’au domaine.

---

# 8. Deux grandes familles

Le modèle distingue :

```text
Control-Plane Errors

Workload Failures
```

---

# 9. Control-Plane Error

Concerne le fonctionnement de PyScheduleKit lui-même.

Exemples :

```text
Schedule invalide

Repository inaccessible

Conflit optimiste

Runtime déjà démarré

Lease perdue
```

---

# 10. Workload Failure

Concerne le travail que PyScheduleKit était réellement chargé d’exécuter.

Exemples :

```text
API cible indisponible

fonction Python lève une exception

timeout du Target

workflow externe échoue
```

---

# 11. Pourquoi cette distinction ?

Une erreur de persistance du scheduler :

```text
ne doit pas devenir
Failure(category=TRANSIENT)
sur l’Execution métier
```

si aucune Attempt métier n’a commencé.

---

# 12. Exemple

Database down avant création de l’ExecutionRequest :

```text
PersistenceUnavailableError
```

Pas :

```text
Execution FAILED
```

car aucune Execution n’existe encore.

---

# 13. Hiérarchie publique racine

Toutes les exceptions publiques PyScheduleKit doivent dériver de :

```python
class PyScheduleKitError(Exception): ...
```

---

# 14. Pourquoi ?

L’utilisateur peut écrire :

```python
try:
    ...
except PyScheduleKitError:
    ...
```

sans dépendre des bibliothèques internes.

---

# 15. Hiérarchie recommandée

```text
PyScheduleKitError
│
├── ValidationError
│
├── ConfigurationError
│
├── DomainError
│
├── NotFoundError
│
├── ConflictError
│
├── PersistenceError
│
├── CoordinationError
│
├── ExecutorError
└── RuntimeError
```

---

# 16. Attention au nom `RuntimeError`

Python possède déjà :

```python
RuntimeError
```

---

# 17. Recommandation

Utiliser plutôt :

```text
SchedulerRuntimeError
```

pour éviter toute ambiguïté.

---

# 18. Hiérarchie V1 proposée

```text
PyScheduleKitError
│
├── ValidationError
│   ├── InvalidTriggerError
│   ├── InvalidCronExpressionError
│   ├── InvalidDurationError
│   ├── InvalidTimezoneError
│   └── InvalidPolicyError
│
├── ConfigurationError
│   ├── InvalidSchedulerConfigurationError
│   ├── UnsupportedConfigurationError
│   └── MissingAdapterError
│
├── DomainError
│   ├── InvalidScheduleTransitionError
│   ├── InvalidExecutionTransitionError
│   ├── InvalidAttemptTransitionError
│   └── InvariantViolationError
│
├── NotFoundError
│   ├── ScheduleNotFoundError
│   ├── ExecutionNotFoundError
│   └── RequestNotFoundError
│
├── ConflictError
│   ├── OptimisticConcurrencyError
│   ├── DuplicateOccurrenceError
│   ├── DuplicateRequestError
│   └── OperationConflictError
│
├── PersistenceError
│   ├── PersistenceUnavailableError
│   ├── PersistenceSerializationError
│   ├── PersistenceCorruptionError
│   └── TransactionError
│
├── CoordinationError
│   ├── ClaimConflictError
│   ├── LeaseLostError
│   ├── FencingRejectedError
│   └── CoordinationUnavailableError
│
├── ExecutorError
│   ├── TargetResolutionError
│   ├── ExecutorUnavailableError
│   └── UnsupportedTargetError
│
└── SchedulerRuntimeError
    ├── RuntimeAlreadyRunningError
    ├── RuntimeNotRunningError
    ├── RuntimeStartError
    └── RuntimeFailedError
```

---

# 19. Ne pas créer une hiérarchie infinie

L’objectif n’est pas d’avoir :

```text
150 classes d’exception
```

---

# 20. Critère d’ajout d’une exception

Une classe distincte se justifie si elle possède au moins une différence utile en termes de :

```text
gestion

contrat public

observabilité

remédiation
```

---

# 21. Exemple

`ScheduleNotFoundError` est utile car l’utilisateur peut :

```python
except ScheduleNotFoundError:
    ...
```

---

# 22. En revanche

Des exceptions comme :

```text
DateTriggerMinuteTooLargeError
```

seraient inutilement spécifiques.

---

# 23. ValidationError

`ValidationError` signifie :

> **Une valeur reçue ne satisfait pas le contrat sémantique attendu.**

---

# 24. Exemples

```python
IntervalTrigger(seconds=0)
```

→

```text
InvalidTriggerError
```

---

# 25. Cron invalide

```python
CronTrigger("99 48 * * *")
```

→

```text
InvalidCronExpressionError
```

---

# 26. Naive datetime

```python
DateTrigger(at=datetime(2026, 1, 1))
```

→

```text
ValidationError
```

avec code plus précis :

```text
NAIVE_DATETIME_NOT_ALLOWED
```

---

# 27. Policy invalide

```python
RetryPolicy.fixed(
    max_attempts=0,
    delay="10s",
)
```

→

```text
InvalidPolicyError
```

---

# 28. Fail Fast

La validation doit échouer :

```text
le plus tôt possible
```

---

# 29. Préférence

```text
construction
```

plutôt que :

```text
runtime plusieurs heures plus tard
```

---

# 30. Validation Error Structure

Toute exception publique importante devrait exposer :

```text
code

message

details
```

---

# 31. Base Error

Conceptuellement :

```python
class PyScheduleKitError(Exception):
    code: str
    details: Mapping[str, object]
```

---

# 32. ErrorCode

Le `code` est une valeur :

```text
machine-readable
```

stable.

---

# 33. Exemple

```text
INVALID_CRON_EXPRESSION
```

---

# 34. Message

Le message est destiné :

```text
aux humains
```

---

# 35. Details

Données structurées :

```text
field

provided_value

expected
```

---

# 36. Exemple

```text
code = "INVALID_CONCURRENCY_LIMIT"

message =
"max_instances must be greater than or equal to 1."

details = {
    "max_instances": 0
}
```

---

# 37. Ne pas parser les messages

Un appelant ne doit jamais devoir écrire :

```python
if "not found" in str(exc):
```

---

# 38. Il utilise

```python
isinstance(exc, ScheduleNotFoundError)
```

ou :

```python
exc.code
```

---

# 39. ErrorCode stabilité

Les codes exposés publiquement deviennent :

```text
un contrat
```

---

# 40. Naming convention

Recommandation :

```text
UPPER_SNAKE_CASE
```

---

# 41. Quelques codes publics V1

```text
INVALID_TRIGGER

INVALID_CRON_EXPRESSION

INVALID_DURATION

INVALID_TIMEZONE

INVALID_POLICY

SCHEDULE_NOT_FOUND

EXECUTION_NOT_FOUND

INVALID_SCHEDULE_TRANSITION

INVALID_EXECUTION_TRANSITION

OPTIMISTIC_CONCURRENCY_CONFLICT

PERSISTENCE_UNAVAILABLE

PERSISTENCE_CORRUPTION

TARGET_RESOLUTION_FAILED

EXECUTOR_UNAVAILABLE

RUNTIME_ALREADY_RUNNING

RUNTIME_START_FAILED
```

---

# 42. ConfigurationError

Différent d'une valeur métier invalide.

Il concerne le wiring de l'application.

---

# 43. Exemple

```text
persistent TargetRef configured
but no executor registered
for target kind "workflow"
```

→

```text
MissingAdapterError
```

---

# 44. Autre exemple

```text
distributed mode
+
InMemoryRepository
```

peut être :

```text
UnsupportedConfigurationError
```

---

# 45. DomainError

Une erreur de domaine signifie :

> **La commande demandée est compréhensible, mais incompatible avec l’état ou les invariants du domaine.**

---

# 46. Exemple

```text
ScheduleState = CANCELLED
```

puis :

```python
schedule.resume()
```

→

```text
InvalidScheduleTransitionError
```

---

# 47. Pas ValidationError

La commande :

```text
resume
```

est syntaxiquement valide.

C’est :

```text
l’état actuel
```

qui la rend interdite.

---

# 48. Execution transition

```text
Execution SUCCESS
→ RUNNING
```

interdit.

---

# 49. Terminal means terminal

Erreur :

```text
InvalidExecutionTransitionError
```

---

# 50. InvariantViolationError

À utiliser avec prudence.

Il représente :

```text
un état interne impossible
```

---

# 51. Exemple

```text
ExecutionState = RETRY_WAIT
next_attempt_at = None
```

---

# 52. Ce cas indique probablement

```text
bug

corrupted persisted state
```

---

# 53. Public ou interne ?

`InvariantViolationError` peut être visible publiquement comme base, mais il signale essentiellement :

```text
une situation anormale du framework
```

---

# 54. NotFoundError

Utilisé lorsqu'un identifiant demandé ne correspond pas à une ressource.

---

# 55. Exemple

```python
scheduler.get_schedule("missing")
```

→

```text
ScheduleNotFoundError
```

---

# 56. `get_*` contract

Les méthodes `get_*` lèvent :

```text
NotFoundError
```

---

# 57. List methods

Retour :

```text
[]
```

si aucun résultat.

---

# 58. Ne pas mélanger

Éviter que :

```python
get_schedule()
```

retourne parfois :

```text
None
```

et parfois lève.

---

# 59. ConflictError

Un conflit signifie :

> **L’opération était potentiellement valide, mais l’état concurrent ou une identité existante empêche son application telle quelle.**

---

# 60. OptimisticConcurrencyError

Cas :

```text
expected PersistenceVersion = 41
actual = 42
```

---

# 61. Qui doit voir cette erreur ?

En général :

```text
Application Layer
```

peut la gérer automatiquement par :

```text
reload
re-evaluate
```

---

# 62. API publique

Un conflit interne récupérable ne doit pas forcément atteindre l'utilisateur.

---

# 63. Exemple

SchedulerEngine :

```text
version conflict
→ re-evaluate
→ success
```

Utilisateur :

```text
ne voit rien
```

---

# 64. Si conflit persiste

L'API peut exposer :

```text
OperationConflictError
```

---

# 65. DuplicateOccurrenceError

Très particulier.

Deux Scheduler nodes tentent :

```text
same OccurrenceKey
```

---

# 66. Ce n'est souvent pas une vraie erreur

Cela peut signifier :

```text
another node already materialized it
```

---

# 67. Recommandation

Dans les flows normaux distribués :

```text
DuplicateOccurrence
```

doit devenir un :

```text
idempotence outcome
```

plutôt qu’une exception fatale.

---

# 68. Repository API

Peut retourner :

```text
CREATED

ALREADY_EXISTS
```

---

# 69. Exception uniquement si

Le duplicate révèle une incohérence réelle.

---

# 70. Même chose pour RequestId

---

# 71. PersistenceError

Regroupe les erreurs du stockage autoritatif.

---

# 72. PersistenceUnavailableError

Exemples :

```text
database connection refused

connection pool exhausted

temporary network failure
```

---

# 73. Scheduler behavior

Si l’état durable ne peut être garanti :

```text
fail closed
```

---

# 74. Donc

```text
No commit
→ no external dispatch
```

---

# 75. PersistenceSerializationError

Le framework n’a pas pu :

```text
serialize
or
deserialize
```

un objet persistant.

---

# 76. Example

Unknown Trigger codec.

---

# 77. PersistenceCorruptionError

Plus grave.

Signifie :

```text
data exists
but violates expected persisted invariants
```

---

# 78. Exemple

```text
Execution RETRY_WAIT
next_attempt_at NULL
```

---

# 79. Behavior

Ne jamais :

```text
guess
```

l’état correct.

---

# 80. Fail safely

Produire :

```text
diagnostic

error

no unsafe execution
```

---

# 81. TransactionError

Réservée aux problèmes génériques de transaction ne correspondant pas à une sous-classe plus précise.

---

# 82. DB exception leakage interdit

L’utilisateur public ne doit pas voir directement :

```text
sqlalchemy.exc.OperationalError

sqlite3.IntegrityError

psycopg.OperationalError
```

---

# 83. Adapter normalization

```text
SQL exception
      │
      ▼
Persistence Adapter
      │
      ▼
PyScheduleKit PersistenceError
```

---

# 84. Preserve cause

Utiliser Python exception chaining :

```python
raise PersistenceUnavailableError(...) from exc
```

---

# 85. Pourquoi ?

La Public API reste stable, mais le debugging garde :

```text
la cause technique originale
```

---

# 86. `__cause__`

Doit rester disponible pour :

```text
developers

logs

debugging
```

---

# 87. Mais message public

Ne doit pas exposer :

```text
password

connection string

internal hostnames
```

---

# 88. CoordinationError

Concerne :

```text
claims

leases

fencing

leader election
```

---

# 89. ClaimConflictError

Une tentative de claim échoue car une autre instance possède déjà le travail.

---

# 90. Très souvent

Ce n'est pas un incident.

---

# 91. Scheduler loop behavior

```text
ClaimConflict
→ skip
→ continue
```

---

# 92. Ne pas log ERROR

Probablement :

```text
DEBUG
```

voire aucune log individuelle.

---

# 93. LeaseLostError

Signifie :

```text
this node is no longer authoritative owner
```

---

# 94. Action

Arrêter :

```text
new authoritative actions
```

sur cette ressource.

---

# 95. FencingRejectedError

Signifie :

```text
a newer ownership epoch exists
```

---

# 96. Très fort signal

Le nœud est :

```text
stale
```

---

# 97. Ce n'est pas retryable aveuglément

Il faut :

```text
reload ownership state
```

---

# 98. CoordinationUnavailableError

Exemple :

```text
lease store unavailable
```

---

# 99. C'est un control-plane transient error potentiel.

---

# 100. Mais pas un Workload Failure

Ne doit pas incrémenter :

```text
AttemptNumber
```

---

# 101. ExecutorError

Cette catégorie nécessite une grande prudence.

---

# 102. `ExecutorError`

Représente :

> **L'impossibilité technique de soumettre ou d'interpréter une exécution avant ou autour de l'Attempt.**

---

# 103. Exemple

Target kind inconnu :

```text
TargetRef(kind="workflow")
```

mais aucun executor workflow.

→

```text
UnsupportedTargetError
```

---

# 104. TargetResolutionError

Exemple :

```text
python target
"app.tasks:missing_function"
```

impossible à résoudre.

---

# 105. Ce type d’erreur peut devenir Failure ?

Cela dépend du moment.

---

# 106. Avant création d’Attempt

Si la résolution est effectuée avant Attempt :

```text
control-plane ExecutorError
```

---

# 107. Après démarrage d’Attempt

Si l’Attempt représente explicitement cette tentative d’exécution, la résolution peut produire :

```text
Failure(
    category=PERMANENT,
    code="target_resolution_failed"
)
```

---

# 108. Recommandation V1

Une fois :

```text
Attempt RUNNING
```

créée, tout échec normalisé du target/executor devient :

```text
AttemptResult
```

plutôt qu’une exception publique.

---

# 109. C’est une frontière essentielle

```text
Before Attempt
→ control-plane errors may raise

During Attempt
→ normalize into AttemptResult/Failure
```

---

# 110. ExecutorUnavailableError

Exemple :

```text
worker broker unavailable
```

avant soumission réelle.

---

# 111. Peut appartenir au dispatch layer

Ne pas confondre avec :

```text
Target dependency unavailable
```

pendant l’Attempt.

---

# 112. SchedulerRuntimeError

Concerne le lifecycle du Runtime.

---

# 113. RuntimeAlreadyRunningError

Exemple :

```python
scheduler.run_pending()
```

alors que :

```text
background runtime is already evaluating
```

---

# 114. Pourquoi erreur ?

Pour préserver l’invariant :

```text
one active evaluation cycle
per SchedulerRuntime instance
```

---

# 115. RuntimeNotRunningError

À utiliser seulement pour des méthodes qui exigent Runtime actif.

---

# 116. `shutdown()` exception

`shutdown()` sur STOPPED devrait rester :

```text
idempotent
```

et ne pas lever.

---

# 117. RuntimeStartError

Échec pendant :

```text
STARTING
```

---

# 118. Peut encapsuler :

```text
PersistenceUnavailable

invalid storage schema

missing critical adapter
```

---

# 119. Cause chaining

Exemple :

```text
RuntimeStartError
caused by
PersistenceUnavailableError
caused by
psycopg.OperationalError
```

---

# 120. Les trois niveaux sont utiles

```text
Public context

PyScheduleKit normalized cause

Vendor cause
```

---

# 121. RuntimeFailedError

Utilisé quand Runtime est déjà :

```text
FAILED
```

et qu’une opération impossible est demandée.

---

# 122. Workload Failure Model

Passons maintenant au modèle `Failure`.

---

# 123. Failure

Proposition :

```text
Failure
│
├── category
├── code
├── message
├── retryable_hint
├── occurred_at
├── details
└── cause_type?
```

---

# 124. Failure immutable

Doit être un :

```text
Value Object
```

---

# 125. FailureCategory V1

Comme décidé précédemment :

```text
TRANSIENT

PERMANENT

TIMEOUT

CANCELLED

UNKNOWN
```

---

# 126. TRANSIENT

Échec potentiellement temporaire.

Exemples :

```text
503

429

temporary connection reset

dependency unavailable
```

---

# 127. PERMANENT

Exemple :

```text
invalid business input

target not found

authentication configuration invalid

unsupported payload
```

---

# 128. TIMEOUT

L’Attempt a dépassé son budget local.

---

# 129. CANCELLED

L’Attempt s’est arrêtée suite à une annulation.

---

# 130. UNKNOWN

Impossible à classifier de façon sûre.

---

# 131. Default UNKNOWN

Recommandation :

```text
not retryable by default
```

---

# 132. Pourquoi ?

Un retry aveugle peut répéter :

```text
des effets de bord inconnus
```

---

# 133. Retryability

Le champ :

```text
retryable_hint
```

ne doit pas être l’unique décision.

---

# 134. Le RetryEvaluator considère

```text
Failure

RetryPolicy

AttemptNumber

ExecutionDeadline

current time
```

---

# 135. Donc

```text
Failure says what happened

RetryPolicy says what we are allowed to do
```

---

# 136. Example

```text
Failure category = TRANSIENT
```

mais :

```text
RetryPolicy.none()
```

→

```text
STOP
```

---

# 137. Another example

```text
Failure category = TIMEOUT
```

Policy may say :

```text
retry timeout once
```

ou :

```text
never retry timeouts
```

---

# 138. FailureCode

Doit être plus spécifique que category.

Examples :

```text
http_429

http_503

connection_timeout

target_resolution_failed

worker_lost

external_workflow_failed
```

---

# 139. Namespace

Pour éviter collisions :

```text
http.503

executor.target_resolution_failed

worker.lost
```

peut être préférable.

---

# 140. Public convention

Recommended :

```text
lowercase.dot.separated
```

pour `Failure.code`.

---

# 141. Différent d’ErrorCode

On peut avoir :

```text
Exception ErrorCode
→ UPPER_SNAKE_CASE
```

et :

```text
FailureCode
→ namespaced.lowercase
```

---

# 142. Pourquoi distinguer ?

Ils appartiennent à :

```text
deux modèles différents
```

---

# 143. Failure.message

Safe human-readable description.

---

# 144. Ne jamais faire de ce message

la base de :

```text
retry classification
```

---

# 145. Failure.details

Petit dictionnaire contrôlé.

Exemple :

```text
{
    "status_code": 503,
    "service": "orders-api"
}
```

---

# 146. Secrets interdits

Ne pas stocker :

```text
Authorization header

token

password

full connection string
```

---

# 147. Raw exceptions

Ne jamais sérialiser :

```text
exception object
```

dans Failure.

---

# 148. Cause type

On peut conserver :

```text
exception_type
```

comme diagnostic :

```text
"TimeoutError"
```

---

# 149. Mais pas dépendre dessus pour le contrat métier.

---

# 150. AttemptResult

L’Executor retourne conceptuellement :

```text
AttemptResult
```

---

# 151. Success

```text
AttemptResult.success(...)
```

---

# 152. Failure

```text
AttemptResult.failure(
    Failure(...)
)
```

---

# 153. Exception boundary

Un Executor adapter doit encapsuler :

```text
vendor exception
```

en :

```text
AttemptResult.failure
```

lorsque l’Attempt a réellement eu lieu.

---

# 154. Example

```python
try:
    response = client.send(...)
except TimeoutError as exc:
    return AttemptResult.failed(
        Failure(
            category=FailureCategory.TIMEOUT,
            code="http.timeout",
            ...
        )
    )
```

---

# 155. Executor adapter bugs

Si l'adapter lui-même viole son contrat :

```text
programming bug
```

peut encore lever une exception.

---

# 156. Ne pas convertir `BaseException`

en Failure.

---

# 157. Très important

Ne jamais écrire :

```python
except BaseException:
    ...
```

---

# 158. Pourquoi ?

Cela capture :

```text
KeyboardInterrupt

SystemExit
```

et peut empêcher un shutdown correct.

---

# 159. Même `except Exception`

doit être réfléchi.

---

# 160. Boundary Catch

À une frontière d'Executor, capturer :

```text
exceptions attendues
```

d’abord.

---

# 161. Unknown exception

Une exception inattendue peut être :

```text
normalized to UNKNOWN Failure
```

si elle provient bien du Target.

---

# 162. Mais si elle provient du framework

Elle doit :

```text
remonter comme framework error
```

---

# 163. Distinction difficile

D’où l’intérêt d’une frontière claire :

```text
ExecutorAdapter
```

---

# 164. CallableExecutor

Pour une fonction utilisateur :

```python
def target():
    raise ValueError("bad data")
```

Cette exception provient du Target.

---

# 165. Donc

`CallableExecutor` peut normaliser :

```text
ValueError
```

en :

```text
Failure(
    category=UNKNOWN or PERMANENT,
    code="python.target_exception",
)
```

---

# 166. Comment savoir retryable ?

Impossible universellement.

---

# 167. V1

Unknown target exceptions :

```text
UNKNOWN
not retryable by default
```

---

# 168. Advanced mapping

User may register :

```text
FailureClassifier
```

later.

---

# 169. FailureClassifier

Contract :

```text
Exception / external result
→ Failure
```

---

# 170. Location

Infrastructure/application boundary.

---

# 171. Not in RetryPolicy

RetryPolicy ne doit pas connaître :

```text
requests.ConnectionError
```

---

# 172. Built-in classifiers

Possible future :

```text
HttpFailureClassifier

PythonExceptionClassifier

WorkflowFailureClassifier
```

---

# 173. Cancellation errors

Cancellation is nuanced.

---

# 174. User requests cancellation

If accepted:

```text
not an error
```

---

# 175. Attempt ends as CANCELLED

Produces:

```text
FailureCategory.CANCELLED
```

or specialized AttemptResult cancellation.

---

# 176. Recommendation

`AttemptResult` should support distinct:

```text
SUCCESS

FAILURE

CANCELLED

TIMED_OUT
```

rather than encoding everything as generic Failure.

---

# 177. But Timeout may still carry Failure metadata

Useful.

---

# 178. Execution cancellation

`cancel_execution()` success is not an exception.

---

# 179. Cancellation impossible

Example terminal Execution:

```text
SUCCESS
```

then cancel.

Can either:

```text
idempotent no-op
```

or error.

---

# 180. Recommendation

Cancel on terminal Execution:

```text
no-op returning current snapshot
```

unless strict mode introduced later.

---

# 181. Why?

Cancellation commands are naturally idempotent.

---

# 182. Timeout versus Exception

Attempt timeout is a modeled lifecycle outcome.

Not merely :

```text
TimeoutError bubbling upward
```

---

# 183. Infrastructure may use timeout exception internally

but must normalize it.

---

# 184. ExecutionDeadline exceeded

Not an exception public by default.

It becomes :

```text
ExecutionState.TIMED_OUT
```

---

# 185. Critical distinction

```text
Expected negative state transition
≠
exceptional API failure
```

---

# 186. Example

Target fails all retries.

Public caller querying later sees:

```text
ExecutionSnapshot.state == FAILED
```

not an exception thrown asynchronously into its thread.

---

# 187. Scheduler background Runtime

Cannot reasonably throw target exceptions to the thread that called :

```python
scheduler.start()
```

---

# 188. Therefore

Workload failures are observed through :

```text
Execution state

events

audit

diagnostics
```

not public synchronous exceptions.

---

# 189. `run_pending()` nuance

Even in manual mode, should a Target exception be raised ?

---

# 190. Recommendation

No by default.

It remains :

```text
AttemptResult → Execution state
```

---

# 191. Why?

Same semantics in:

```text
background

manual

distributed
```

---

# 192. Great consistency

`run_pending()` reports :

```text
executions failed
```

in its result, rather than throwing Target exception.

---

# 193. Strict testing mode

`SchedulerHarness` may expose helper :

```python
harness.assert_no_failed_executions()
```

rather than changing runtime semantics.

---

# 194. Error propagation boundaries

Four important boundaries :

```text
Public API Boundary

Persistence Boundary

Executor Boundary

Distributed Coordination Boundary
```

---

# 195. Public API Boundary

Normalizes internal exceptions into public PyScheduleKit exceptions.

---

# 196. Persistence Boundary

Normalizes DB exceptions into :

```text
PersistenceError
```

---

# 197. Executor Boundary

Normalizes workload exceptions into :

```text
AttemptResult / Failure
```

---

# 198. Coordination Boundary

Normalizes DB/etcd/etc. errors into :

```text
CoordinationError
```

---

# 199. Error normalization diagram

```text
External technology
       │
       ▼
Adapter-specific error
       │
       ▼
Boundary normalization
       │
       ├── PyScheduleKit Exception
       │
       └── Failure
```

---

# 200. Question de choix

Quand produire :

```text
Exception
```

ou :

```text
Failure
```

?

---

# 201. Rule

Si l’échec concerne :

```text
l'exécution du Target
après qu'une Attempt existe
```

→ `Failure`.

---

# 202. Si l’échec concerne :

```text
la capacité du framework à effectuer son propre use case
```

→ Exception.

---

# 203. Examples

| Situation | Representation |
|---|---|
| Cron invalide | ValidationError |
| Schedule absent | ScheduleNotFoundError |
| DB indisponible | PersistenceUnavailableError |
| Target HTTP 503 | Failure TRANSIENT |
| Target Python raises | Failure UNKNOWN/PERMANENT |
| Retry épuisé | Execution FAILED + RetryDecision STOP |
| Lease perdue | LeaseLostError |
| Attempt timeout | Attempt TIMED_OUT + Failure/metadata |
| Runtime déjà actif | RuntimeAlreadyRunningError |

---

# 204. Error Retryability

Une exception de framework peut également être :

```text
retryable operationally
```

sans devenir `Failure`.

---

# 205. Exemple

```text
PersistenceUnavailableError
```

peut déclencher :

```text
SchedulerRuntime backoff
```

---

# 206. Cela reste différent de :

```text
RetryPolicy
```

---

# 207. Trois retry domains

```text
Runtime retry
Transaction retry
Execution retry
```

---

# 208. Runtime retry

Exemple :

```text
DB temporarily unavailable
```

SchedulerRuntime attend puis retente son cycle.

---

# 209. Transaction retry

Exemple :

```text
deadlock
optimistic conflict
serialization failure
```

L’application recharge et réévalue.

---

# 210. Execution retry

Exemple :

```text
Target HTTP 503
```

RetryPolicy décide d’une nouvelle Attempt.

---

# 211. Ils ne doivent jamais partager un compteur

---

# 212. Runtime Error Classification

Une fonction interne peut classifier :

```text
TRANSIENT_RUNTIME

FATAL_RUNTIME
```

---

# 213. Transient examples

```text
temporary DB outage

temporary broker outage
```

---

# 214. Fatal examples

```text
incompatible DB schema

corrupted mandatory configuration

unsupported persistence format
```

---

# 215. Runtime behavior

Transient :

```text
backoff
retry
health=DEGRADED
```

Fatal :

```text
RuntimeState=FAILED
```

---

# 216. Transaction retryability

Optimistic conflict :

```text
usually retry/re-evaluate
```

---

# 217. Unique conflict

May mean:

```text
idempotent success elsewhere
```

---

# 218. Deadlock

Usually:

```text
retry transaction
```

with bounded attempts.

---

# 219. Unknown commit outcome

Special case.

---

# 220. Example

```text
COMMIT sent
connection drops
```

---

# 221. Do not assume rollback

Could have committed.

---

# 222. Recovery

Use stable identities :

```text
OccurrenceKey

RequestId
```

to check durable outcome.

---

# 223. Error class

Potential internal :

```text
UnknownCommitOutcomeError
```

---

# 224. Public exposure ?

Probably not V1.

Application should reconcile.

---

# 225. Duplicate-after-retry

Not fatal if natural identity proves success.

---

# 226. Error Cause Chain

All normalization should preserve causal chain when safe.

---

# 227. Example

```text
RuntimeStartError
    caused by
PersistenceUnavailableError
    caused by
psycopg.OperationalError
```

---

# 228. Public serialization of error

If REST/CLI future :

```text
code

message

details
```

---

# 229. Do not serialize stack trace by default.

---

# 230. ErrorResponse

Future representation :

```json
{
  "code": "SCHEDULE_NOT_FOUND",
  "message": "Schedule 'daily-report' was not found.",
  "details": {
    "schedule_id": "daily-report"
  }
}
```

---

# 231. Stable across adapters

Python exception, CLI and REST can share :

```text
ErrorCode
```

---

# 232. HTTP mapping future

Possible :

```text
ValidationError → 400

NotFoundError → 404

ConflictError → 409
```

---

# 233. But not part of core domain

REST adapter decides mapping.

---

# 234. CLI mapping

Potential exit codes later.

---

# 235. Again adapter concern.

---

# 236. Safe messages

Error messages can contain :

```text
schedule_id

field names

policy value
```

---

# 237. Must not contain :

```text
DB password

API token

authorization header

secret environment variables
```

---

# 238. Redaction

Infrastructure adapter should sanitize exceptions before wrapping.

---

# 239. Example bad

```text
Could not connect using
postgres://user:password@host/db
```

---

# 240. Better

```text
Persistence backend is unavailable.
```

details :

```text
backend="postgresql"
host_alias="primary"
```

if safe.

---

# 241. `repr(exception)`

Do not rely on vendor repr in public messages.

---

# 242. Diagnostics may keep technical cause type

But secret-safe.

---

# 243. Error Observability

Every error should have contextual information available to logs/traces.

---

# 244. Useful context

```text
schedule_id

execution_id

attempt_id

request_id

correlation_id

node_id

error_code
```

---

# 245. But not every exception object needs all fields.

Context can come from logging scope.

---

# 246. Public exception fields

Keep small :

```text
code

message

details
```

---

# 247. Audit of errors

Not every thrown ValidationError needs durable audit.

---

# 248. Examples not requiring audit

```text
user typo in Cron before persistence
```

---

# 249. Examples worth auditing

```text
manual command rejected due lifecycle conflict?

persistent scheduling decision failure?

critical storage corruption?
```

depending policy.

---

# 250. Runtime diagnostics

An error can generate:

```text
Diagnostic
```

without becoming :

```text
Domain Event
```

---

# 251. Example

```text
PersistenceCorruptionError
→ Diagnostic(
    code=PERSISTENCE_CORRUPTION,
    severity=CRITICAL
)
```

---

# 252. Event versus Error

An event records :

```text
what happened
```

An error says :

```text
an operation could not fulfill its contract
```

---

# 253. Example

```text
ExecutionCompleted(outcome=FAILED)
```

is an Event.

The target's network timeout is represented in :

```text
Failure
```

No public exception is required.

---

# 254. Error Aggregation

Batch operations may encounter :

```text
Schedule A success

Schedule B failure

Schedule C success
```

---

# 255. Scheduler loop must not abort all work

Per-Schedule errors should be isolated.

---

# 256. Batch Result

Can include :

```text
errors[]
```

---

# 257. `run_pending()`

Potential :

```text
RunPendingResult
│
├── evaluated
├── requests_created
├── execution_outcomes
└── errors
```

---

# 258. Should it throw if one Schedule evaluation failed?

Recommendation :

```text
no
```

for isolated Schedule errors.

---

# 259. Should it throw if DB is globally unavailable?

Yes.

Because cycle itself cannot be executed safely.

---

# 260. Distinction

```text
item-level error
→ result/diagnostic

cycle-level fatal error
→ exception
```

---

# 261. This is crucial for runtime robustness.

---

# 262. ExceptionGroup

Python 3.11 provides :

```python
ExceptionGroup
```

---

# 263. Should PyScheduleKit expose it ?

Not V1.

---

# 264. Why?

Would couple public API to batch implementation semantics unnecessarily.

---

# 265. Prefer typed batch result.

---

# 266. Multi-error diagnostics

Can expose :

```text
tuple[EvaluationErrorRecord, ...]
```

inside result objects.

---

# 267. ErrorRecord

Possible read-only DTO :

```text
code

subject_type

subject_id

message
```

---

# 268. No full exception objects in persistent state.

---

# 269. Failure serialization

Failures *are* persisted as runtime facts.

---

# 270. Schema example

```json
{
  "category": "transient",
  "code": "http.503",
  "message": "Remote service unavailable.",
  "retryable_hint": true,
  "details": {
    "status_code": 503
  }
}
```

---

# 271. Version it

Persistence representation should include :

```text
schema_version
```

---

# 272. Failure evolution

Future categories may appear.

---

# 273. Unknown category from newer version

Old runtime must :

```text
fail safely
```

rather than guess retryability.

---

# 274. Public Failure class

Should `Failure` be exported publicly ?

---

# 275. Recommendation

Yes, as read-only execution result concept.

---

# 276. Why?

Users inspecting :

```text
ExecutionSnapshot
```

need access to normalized failure information.

---

# 277. Public namespace

Possibly :

```python
from pyschedulekit.execution import (
    Failure,
    FailureCategory,
)
```

---

# 278. Not necessarily root namespace

Keep root small.

---

# 279. Failure does not derive Exception

Critical.

---

# 280. Example

```python
isinstance(failure, Exception)
```

must be :

```text
False
```

---

# 281. ErrorCode type

Could be :

```text
Enum
```

or constants.

---

# 282. Public extensibility concern

Enums make third-party custom error codes harder.

---

# 283. Recommendation

Built-in exceptions use stable strings :

```text
ErrorCode = str
```

conceptually.

---

# 284. Typed constants optional.

---

# 285. FailureCategory

Finite semantic enum is appropriate.

---

# 286. FailureCode

String is better because Executors may define namespaces.

---

# 287. Example custom executor

```text
sap.rate_limit

snowflake.query_timeout
```

---

# 288. Public exception custom subclasses

Third-party adapters may subclass :

```text
ExecutorError
```

if needed.

---

# 289. But they should prefer normalized generic public error codes.

---

# 290. Adapter failure contract

Every adapter should document :

```text
which PyScheduleKit exceptions it can raise
```

---

# 291. Repository contract errors

Expected classes:

```text
PersistenceUnavailableError

OptimisticConcurrencyError

PersistenceSerializationError

PersistenceCorruptionError
```

---

# 292. Executor contract

Before Attempt :

```text
TargetResolutionError

ExecutorUnavailableError
```

During Attempt :

```text
AttemptResult
```

---

# 293. Clock contract

Could fail ?

SystemClock generally not.

Custom Clock adapter error could become :

```text
SchedulerRuntimeError
```

---

# 294. CalendarProvider

External business calendar unavailable.

Which category ?

---

# 295. Important question

Occurrence planning cannot safely continue.

---

# 296. Could introduce :

```text
CalendarUnavailableError
```

under :

```text
DomainDependencyError
```

---

# 297. But hierarchy bloat.

---

# 298. Better V1

Use :

```text
SchedulerEvaluationError
```

or `ConfigurationError` depending source.

---

# 299. Missing static calendar

```text
ConfigurationError
```

---

# 300. Remote CalendarProvider temporarily unavailable

```text
SchedulerEvaluationError
```

with transient runtime classification.

---

# 301. Add application-level base

We therefore need :

```text
SchedulerEvaluationError
```

under `PyScheduleKitError`.

---

# 302. Revised high-level hierarchy

```text
PyScheduleKitError
│
├── ValidationError
├── ConfigurationError
├── DomainError
├── NotFoundError
├── ConflictError
├── SchedulerEvaluationError
├── PersistenceError
├── CoordinationError
├── ExecutorError
└── SchedulerRuntimeError
```

---

# 303. SchedulerEvaluationError

Concerne l’incapacité à évaluer correctement un Schedule spécifique.

---

# 304. Examples

```text
Calendar unavailable

Trigger planner exceeded search horizon

invalid persisted schedule definition

unsupported trigger configuration
```

---

# 305. One broken Schedule

Should not stop all others.

---

# 306. Runtime records diagnostic then continues.

---

# 307. Poison Schedule

Repeated evaluation failure can produce hot loop.

---

# 308. Error model provides :

```text
SchedulerEvaluationError
```

plus operational suppression/backoff.

---

# 309. It does not automatically :

```text
PAUSE Schedule
```

---

# 310. No hidden lifecycle mutation.

---

# 311. TriggerExhausted

Is this an error?

No.

---

# 312. It is a normal result :

```text
next_after() -> None
```

---

# 313. Then :

```text
Schedule → COMPLETED
```

---

# 314. Calendar rejects date

Not an error.

Planner searches next candidate.

---

# 315. Search horizon exhausted

Potential :

```text
SchedulerEvaluationError
```

if unable to prove Trigger exhausted.

---

# 316. This distinction matters.

---

# 317. Misfire

Not an error.

---

# 318. Catch-up

Not an error.

---

# 319. Concurrency limit reached

Not an error.

---

# 320. Request WAITING_ADMISSION

Not an error.

---

# 321. Retry scheduled

Not an error.

---

# 322. Retry exhausted

Not an exception.

It is :

```text
Execution terminal outcome
```

---

# 323. Execution FAILED

Not necessarily scheduler malfunction.

---

# 324. This is perhaps the most important operational distinction

```text
Failed workload
≠
failed scheduler
```

---

# 325. Health metrics must reflect this

100 failed Targets should not automatically make :

```text
SchedulerRuntime = UNHEALTHY
```

---

# 326. Scheduler health asks :

```text
Did scheduler process them correctly?
```

---

# 327. Workload health asks :

```text
Did user work succeed?
```

---

# 328. Error messages and IDs

Example :

```text
Schedule 'daily-report' cannot be resumed
because it is CANCELLED.
```

Useful.

---

# 329. Details:

```text
{
    "schedule_id": "daily-report",
    "current_state": "cancelled",
    "requested_operation": "resume"
}
```

---

# 330. This supports API/CLI later.

---

# 331. Public exceptions immutable?

Exceptions themselves need not be dataclasses.

---

# 332. But fields should not mutate after construction.

---

# 333. Base constructor

Conceptually :

```python
PyScheduleKitError(
    message,
    *,
    code,
    details=None,
)
```

---

# 334. Subclasses supply default code.

---

# 335. Example

```python
class ScheduleNotFoundError(NotFoundError):
    code = "SCHEDULE_NOT_FOUND"
```

---

# 336. Message generation

Can be subclass-controlled.

---

# 337. Localization

Do not make English/French message part of machine contract.

---

# 338. `code` is stable.

---

# 339. Cause exposure

Public `.cause` property unnecessary.

Python already provides :

```text
__cause__
```

---

# 340. Avoid duplicating.

---

# 341. Tracebacks

Logs may record traceback for unexpected framework exceptions.

---

# 342. Expected conflicts

Do not spam traceback for :

```text
ClaimConflict

Optimistic conflict
```

---

# 343. Error severity guideline

```text
Expected validation issue
→ no internal ERROR log necessarily

Expected claim conflict
→ DEBUG

Transient infrastructure issue
→ WARNING/ERROR depending duration

Persistence corruption
→ ERROR/CRITICAL

Unexpected framework bug
→ ERROR with traceback
```

---

# 344. Failure severity

A workload failure is not automatically ERROR-level scheduler log.

---

# 345. Could log :

```text
INFO/WARNING
```

and expose metric/event.

---

# 346. Retry failure

Attempt #1 failed but retry planned.

Likely :

```text
WARNING
```

---

# 347. Terminal failed execution

Could be :

```text
ERROR
```

operationally, but configurable.

---

# 348. Domain should not decide log level.

---

# 349. Retry Policy and ErrorCode

RetryPolicy should never say :

```text
retry on PersistenceUnavailableError
```

---

# 350. Because that is not Execution retry domain.

---

# 351. RetryPolicy works on :

```text
Failure
```

only.

---

# 352. Good API boundary

```python
RetryPolicy.should_retry(
    failure: Failure,
    ...
)
```

not :

```python
RetryPolicy.should_retry(
    exc: Exception
)
```

---

# 353. Excellent semantic separation.

---

# 354. FailureClassifier is the only place that may inspect concrete exceptions.

---

# 355. Public retry configuration

Future custom classifier may be registered on Executor.

Not on Schedule itself.

---

# 356. Why?

Classification depends on target technology.

Retry policy depends on business execution semantics.

---

# 357. Example

HTTP adapter knows :

```text
429
```

means rate limit.

Schedule policy knows :

```text
up to 3 attempts
```

---

# 358. Clean separation.

---

# 359. Distributed late result

Attempt #1 declared lost.

Attempt #2 begins.

Attempt #1 later reports success.

---

# 360. Is this an exception?

No.

It's a :

```text
late result conflict
```

---

# 361. Application handling

Reject state transition and emit :

```text
LateAttemptResult diagnostic
```

---

# 362. Could raise internally :

```text
OperationConflictError
```

to caller applying result.

---

# 363. But it must not overwrite newer state.

---

# 364. Fencing rejection

Similarly is a coordination conflict, not workload Failure.

---

# 365. Public worker adapter may receive it

and should terminate stale ownership.

---

# 366. Error Recovery Matrix

| Error type | Default behavior |
|---|---|
| ValidationError | Reject command immediately |
| ConfigurationError | Reject startup/configuration |
| DomainError | Reject invalid transition |
| NotFoundError | Return explicit public error |
| OptimisticConcurrencyError | Reload/re-evaluate when safe |
| DuplicateOccurrence | Treat idempotently when expected |
| PersistenceUnavailableError | Runtime backoff / fail closed |
| PersistenceCorruptionError | Stop unsafe processing / diagnostic |
| ClaimConflict | Skip; another node owns work |
| LeaseLostError | Stop authoritative action |
| FencingRejectedError | Treat owner as stale |
| Executor pre-attempt error | Normalize/raise at control plane |
| Workload Failure | Persist AttemptResult; apply RetryPolicy |
| Runtime fatal error | Runtime → FAILED |

---

# 367. Public API behavior matrix

### `add_schedule()`

Can raise :

```text
ValidationError

ConfigurationError

PersistenceError

ConflictError
```

---

# 368. `pause_schedule()`

Can raise :

```text
ScheduleNotFoundError

InvalidScheduleTransitionError

PersistenceError

ConflictError
```

---

# 369. `resume_schedule()`

Same family.

---

# 370. `reschedule_schedule()`

Adds :

```text
ValidationError
```

for new definition.

---

# 371. `cancel_schedule()`

Idempotent for already cancelled.

Can still raise :

```text
ScheduleNotFoundError

PersistenceError
```

---

# 372. `run_pending()`

May raise :

```text
RuntimeAlreadyRunningError

PersistenceUnavailableError

fatal SchedulerRuntimeError
```

---

# 373. Individual Schedule errors

Should be returned in cycle result/diagnostics rather than abort whole call when possible.

---

# 374. `start()`

Can raise :

```text
RuntimeAlreadyRunningError?
RuntimeStartError
ConfigurationError
PersistenceError
```

---

# 375. Earlier we considered idempotent `start()`

Need final consistency.

---

# 376. Recommendation

`start()` on already running :

```text
idempotent no-op
```

---

# 377. Therefore

`RuntimeAlreadyRunningError` primarily applies to :

```text
run_pending()

run_forever()
```

when background Runtime already owns the cycle.

---

# 378. This is more ergonomic.

---

# 379. `shutdown()`

Idempotent.

---

# 380. `get_schedule()`

Can raise :

```text
ScheduleNotFoundError

PersistenceError
```

---

# 381. `get_execution()`

```text
ExecutionNotFoundError

PersistenceError
```

---

# 382. Query methods should not surface domain transition errors.

---

# 383. Validation aggregation

Should constructors report first invalid field or all?

---

# 384. V1 recommendation

Fail fast on first semantic violation.

---

# 385. Why?

Simpler exception model.

---

# 386. Config-file validation later

May benefit from aggregate validation report.

---

# 387. Separate :

```text
ConfigValidationReport
```

future.

---

# 388. Don't overload runtime exceptions with multiple field errors.

---

# 389. Programmer Errors

Some failures indicate misuse of Python API itself.

Example :

```python
IntervalTrigger(minutes="abc")
```

---

# 390. Should this raise built-in `TypeError` or ValidationError?

---

# 391. Recommendation

Use normal Python conventions :

```text
wrong Python type
→ TypeError
```

when naturally enforced.

---

# 392. Semantic invalid value

```text
correct type, invalid meaning
→ ValidationError
```

---

# 393. Example

```python
IntervalTrigger(minutes=-1)
```

→ `ValidationError`.

---

# 394. Example

```python
IntervalTrigger(minutes=object())
```

→ `TypeError`.

---

# 395. Why?

Makes API feel Pythonic.

---

# 396. Should built-in `ValueError` be used?

For public consistency, semantic domain values should prefer :

```text
PyScheduleKit ValidationError
```

---

# 397. But subclassing ValueError ?

Potentially:

```python
class ValidationError(PyScheduleKitError, ValueError): ...
```

---

# 398. Is multiple inheritance worthwhile?

Probably not V1.

---

# 399. Recommendation

Single clear hierarchy under :

```text
PyScheduleKitError
```

---

# 400. Python protocol errors

Still allowed to be normal :

```text
TypeError
```

for impossible function signatures.

---

# 401. Internal AssertionError

Assertions should represent :

```text
developer assumptions
```

not user-facing validation.

---

# 402. Never catch AssertionError and convert into workload Failure.

---

# 403. Assertion failure likely framework bug.

---

# 404. Error testing

Public exception contracts need unit tests.

---

# 405. Test invalid Cron

Expected :

```text
InvalidCronExpressionError
```

with stable code.

---

# 406. Test naive datetime

Expected :

```text
ValidationError
code=NAIVE_DATETIME_NOT_ALLOWED
```

---

# 407. Test resume cancelled schedule

Expected :

```text
InvalidScheduleTransitionError
```

---

# 408. Test missing schedule

Expected :

```text
ScheduleNotFoundError
```

---

# 409. Test persistence vendor error

Vendor exception must be chained but not exposed as public type.

---

# 410. Test DB password redaction

Message/details must not contain secret.

---

# 411. Test optimistic conflict

Automatic SchedulerEngine path retries/re-evaluates correctly.

---

# 412. Test duplicate occurrence

Distributed race produces one logical Request and no fatal runtime failure.

---

# 413. Test claim conflict

No ERROR-level failure path.

---

# 414. Test lease lost

Owner stops further authoritative transitions.

---

# 415. Test target exception

Stored as Failure, not raised through Scheduler Runtime.

---

# 416. Test unknown target exception

Category :

```text
UNKNOWN
```

and not retryable by default.

---

# 417. Test HTTP 503 classifier

Category :

```text
TRANSIENT
```

---

# 418. Test timeout

Attempt state :

```text
TIMED_OUT
```

with normalized metadata.

---

# 419. Test retries exhausted

No public exception; Execution becomes FAILED.

---

# 420. Test fatal runtime error

Runtime enters :

```text
FAILED
```

and health reflects issue.

---

# 421. Test error code stability

Public exceptions expose expected stable codes.

---

# 422. Test cause chaining

```text
exc.__cause__
```

preserved where useful.

---

# 423. Test Failure persistence round-trip

```text
Failure
→ serialize
→ deserialize
```

semantically equivalent.

---

# 424. Test Failure redaction

No credentials persisted.

---

# 425. Error package structure

Target :

```text
pyschedulekit/
├── errors/
│   ├── base.py
│   ├── validation.py
│   ├── domain.py
│   ├── persistence.py
│   ├── coordination.py
│   ├── execution.py
│   └── runtime.py
```

---

# 426. But initial implementation

Can begin with :

```text
errors.py
```

until size justifies extraction.

---

# 427. Failure belongs elsewhere

Do not put `Failure` inside :

```text
errors.py
```

---

# 428. Better :

```text
domain/execution/failure.py
```

---

# 429. Why?

`Failure` is :

```text
domain/runtime data
```

not an exception.

---

# 430. Public imports

Potential :

```python
from pyschedulekit.errors import (
    PyScheduleKitError,
    ValidationError,
    ScheduleNotFoundError,
    InvalidScheduleTransitionError,
    PersistenceUnavailableError,
)
```

---

# 431. Root namespace

Should not export every exception.

---

# 432. Maybe only :

```text
PyScheduleKitError
```

at root.

---

# 433. Recommended

```python
from pyschedulekit import PyScheduleKitError
```

and detailed errors from :

```python
pyschedulekit.errors
```

---

# 434. Failure imports

```python
from pyschedulekit.execution import (
    Failure,
    FailureCategory,
)
```

---

# 435. Error compatibility policy

Once public :

```text
exception class

error code
```

becomes compatibility surface.

---

# 436. Therefore don't expose internal exception classes casually.

---

# 437. Internal exceptions

Can exist under :

```text
pyschedulekit._internal
```

or remain unexported.

---

# 438. Examples

```text
PlannerIterationLimitReached

InternalCodecLookupError
```

can be normalized before public boundary.

---

# 439. Public `SchedulerEvaluationError`

Can wrap internal planner-specific cause.

---

# 440. Architecture rule

> **Catch low, normalize at boundaries, expose high-level stable contracts.**

---

# 441. But don't catch too broadly

Another rule :

> **Never normalize an error before you know which semantic boundary it belongs to.**

---

# 442. Example

Catching all exceptions in SchedulerEngine and returning :

```text
SchedulerError
```

would destroy useful classification.

---

# 443. Preserve semantic specificity.

---

# 444. Fail Open versus Fail Closed

Scheduling correctness generally prefers :

```text
fail closed
```

for uncertainty.

---

# 445. Examples

Unknown ScheduleDefinition :

```text
do not execute
```

---

# 446. Unknown RetryPolicy :

```text
do not guess retry
```

---

# 447. Lost Lease :

```text
stop authoritative work
```

---

# 448. DB unavailable :

```text
do not dispatch new work
```

---

# 449. Unknown FailureCategory :

```text
do not automatically retry
```

---

# 450. This is a consistent safety philosophy.

---

# 451. Cases where continue is correct

ClaimConflict :

```text
another node owns work
→ continue
```

---

# 452. Single Schedule evaluation error :

```text
isolate
→ continue others
```

---

# 453. One Target failure :

```text
record
→ continue scheduler
```

---

# 454. Error isolation scopes

```text
Target scope

Execution scope

Schedule scope

Cycle scope

Runtime scope
```

---

# 455. Target Scope

A failed Target should usually affect :

```text
one Attempt/Execution
```

---

# 456. Schedule Scope

Broken persisted ScheduleDefinition affects :

```text
one Schedule
```

---

# 457. Cycle Scope

Global persistence failure may invalidate :

```text
whole evaluation cycle
```

---

# 458. Runtime Scope

Fatal storage schema incompatibility may invalidate :

```text
entire Runtime
```

---

# 459. Error escalation

Only escalate to broader scope when required.

---

# 460. Great resilience principle

```text
smallest valid blast radius
```

---

# 461. ErrorContext

Should there be a generic ErrorContext object?

Could easily become dumping ground.

---

# 462. Recommendation

No generic public ErrorContext V1.

Use:

```text
details
```

plus structured logging context.

---

# 463. Error identifiers

Do we need an `error_id` UUID?

---

# 464. Public exceptions

Not necessary.

---

# 465. Diagnostics/tracing

Can attach :

```text
trace_id
correlation_id
```

outside exception object.

---

# 466. If support use cases require

future diagnostic incident IDs can be added.

---

# 467. Retry exhaustion as Failure?

The final ExecutionResult may contain :

```text
last_failure
```

plus :

```text
attempt_count
```

---

# 468. Do not manufacture :

```text
Failure(code="retries_exhausted")
```

as if that were the Target failure.

---

# 469. Better

ExecutionCompletionReason :

```text
RETRIES_EXHAUSTED
```

and preserve :

```text
last_failure
```

---

# 470. Because

```text
retries exhausted
```

is not what originally failed.

It is why the Execution stopped retrying.

---

# 471. Similarly

```text
deadline exceeded
```

may be completion reason distinct from last Attempt failure.

---

# 472. ExecutionResult target model

```text
ExecutionResult
│
├── outcome
├── completion_reason
├── final_failure?
├── attempts_count
└── output?
```

---

# 473. CompletionReason examples

```text
SUCCESS

NON_RETRYABLE_FAILURE

RETRIES_EXHAUSTED

EXECUTION_DEADLINE_EXCEEDED

CANCELLED
```

---

# 474. This improves diagnostics.

---

# 475. AttemptResult model

```text
AttemptResult
│
├── outcome
├── output?
├── failure?
└── finished_at
```

---

# 476. Attempt outcome

```text
SUCCESS

FAILED

TIMED_OUT

CANCELLED
```

---

# 477. Invariant

SUCCESS :

```text
failure is None
```

---

# 478. FAILED :

```text
failure is not None
```

---

# 479. TIMED_OUT

May carry timeout Failure.

---

# 480. CANCELLED

May carry cancellation metadata but not ordinary Failure required.

---

# 481. Error Serialization

Public exceptions generally are not persisted.

---

# 482. Failures are persisted.

---

# 483. Diagnostics may be persisted.

---

# 484. Important separation

```text
Exception history
```

is not the source of runtime state.

---

# 485. No pickled exceptions

Ever.

---

# 486. Failure output size

Bound `details`.

---

# 487. Why?

An exception might include:

```text
multi-megabyte response body
```

---

# 488. Adapter should truncate/sanitize.

---

# 489. Diagnostic technical detail

Full traceback may go to logs, not Failure persistence.

---

# 490. Error codes versus Diagnostic codes

Could overlap, but conceptual separation remains.

---

# 491. Example

Exception :

```text
PERSISTENCE_UNAVAILABLE
```

Diagnostic :

```text
RUNTIME_PERSISTENCE_DEGRADED
```

---

# 492. Failure :

```text
http.503
```

---

# 493. Three different vocabularies

Useful because they describe :

```text
API problem

system diagnostic

workload failure
```

---

# 494. Do not force one universal error code catalogue.

---

# 495. Public Error Model Summary

```text
PyScheduleKit API
      │
      ├── invalid input
      │      └── ValidationError
      │
      ├── invalid state
      │      └── DomainError
      │
      ├── missing resource
      │      └── NotFoundError
      │
      ├── concurrent state
      │      └── ConflictError
      │
      ├── storage problem
      │      └── PersistenceError
      │
      ├── distributed ownership problem
      │      └── CoordinationError
      │
      └── runtime lifecycle problem
             └── SchedulerRuntimeError
```

---

# 496. Workload Failure Summary

```text
Attempt
   │
   ▼
Executor
   │
   ├── success
   │      └── AttemptResult.SUCCESS
   │
   └── target failure
          │
          ▼
       Failure
          │
          ▼
    RetryEvaluator
       │       │
       ▼       ▼
     RETRY    STOP
```

---

# 497. Boundary model

```text
VENDOR EXCEPTION
      │
      ▼
   ADAPTER
      │
      ├──────────────┐
      │              │
      ▼              ▼
Framework Error    Failure
      │              │
      ▼              ▼
Public Exception  Retry Decision
```

---

# 498. V1 Decisions

```text
1.
All public framework exceptions derive from
PyScheduleKitError.

2.
Failure does not derive from Exception.

3.
Workload failures are represented as Failure objects.

4.
RetryPolicy operates on Failure, not Python exceptions.

5.
Vendor-specific exceptions do not escape
public adapter boundaries.

6.
Exception chaining preserves original technical causes
when safe.

7.
Public exceptions expose stable machine-readable codes.

8.
Human-readable messages are not machine contracts.

9.
Validation fails as early as possible.

10.
Invalid lifecycle transitions use DomainError.

11.
Missing resources use explicit NotFoundError subclasses.

12.
Optimistic conflicts are retried/re-evaluated internally
when safe.

13.
Expected duplicate occurrence races are treated
idempotently rather than as fatal failures.

14.
Persistence uncertainty fails closed.

15.
Lease/fencing failures are coordination errors,
not workload failures.

16.
Target exceptions occurring within an Attempt
are normalized into AttemptResult/Failure.

17.
UNKNOWN workload failures are not retryable by default.

18.
Retry exhaustion is an Execution completion reason,
not a new target Failure.

19.
Background Target failures do not propagate
synchronously from Scheduler.start().

20.
run_pending() preserves the same execution semantics
as background runtime.

21.
One broken Schedule should not terminate
the entire SchedulerRuntime.

22.
Fatal control-plane failures may transition Runtime
to FAILED.

23.
Secrets are redacted from public errors and Failure data.

24.
Exceptions are never persisted using pickle.

25.
The smallest valid error blast radius is preferred.
```

---

# 499. Public hierarchy V1 candidate

```text
PyScheduleKitError

├── ValidationError
│   ├── InvalidTriggerError
│   ├── InvalidCronExpressionError
│   ├── InvalidDurationError
│   ├── InvalidTimezoneError
│   └── InvalidPolicyError
│
├── ConfigurationError
│
├── DomainError
│   ├── InvalidScheduleTransitionError
│   └── InvalidExecutionTransitionError
│
├── NotFoundError
│   ├── ScheduleNotFoundError
│   └── ExecutionNotFoundError
│
├── ConflictError
│   ├── OptimisticConcurrencyError
│   └── OperationConflictError
│
├── SchedulerEvaluationError
│
├── PersistenceError
│   ├── PersistenceUnavailableError
│   ├── PersistenceSerializationError
│   └── PersistenceCorruptionError
│
├── CoordinationError
│   ├── LeaseLostError
│   ├── FencingRejectedError
│   └── CoordinationUnavailableError
│
├── ExecutorError
│   ├── TargetResolutionError
│   └── ExecutorUnavailableError
│
└── SchedulerRuntimeError
    ├── RuntimeAlreadyRunningError
    ├── RuntimeStartError
    └── RuntimeFailedError
```

---

# 500. Acceptance criteria

Le modèle est suffisamment défini lorsque l'on peut répondre sans ambiguïté à :

```text
Quelle différence entre Exception et Failure ?

Pourquoi Failure ne dérive-t-il pas d'Exception ?

Quand une exception d'un Target devient-elle un Failure ?

Quand doit-elle au contraire rester une framework exception ?

Quelle exception expose un Cron invalide ?

Quelle exception expose un Schedule introuvable ?

Quelle exception expose une transition interdite ?

Que devient une exception SQLAlchemy ?

Que devient une erreur HTTP 503 du Target ?

Comment décide-t-on qu'un Failure est retryable ?

Pourquoi UNKNOWN n'est-il pas retryable par défaut ?

Pourquoi PersistenceUnavailable n'utilise-t-il pas RetryPolicy ?

Quelle différence entre Runtime retry,
Transaction retry et Execution retry ?

Que se passe-t-il lors d'un OptimisticConcurrencyError ?

Un DuplicateOccurrence est-il nécessairement une erreur ?

Que se passe-t-il lorsqu'une Lease est perdue ?

Que signifie FencingRejected ?

Un Target FAILED rend-il le SchedulerRuntime FAILED ?

Comment une cause technique originale reste-t-elle disponible ?

Comment empêcher la fuite de secrets dans les erreurs ?

Que retourne run_pending() si une Execution métier échoue ?

Comment représenter proprement Retry exhaustion ?

Quel est le blast radius d'une erreur sur un seul Schedule ?
```

---

# 501. Modèle mental final

```text
                       USER / RUNTIME
                            │
                            ▼
                       OPERATION
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
        CONTROL PLANE                 WORKLOAD
              │                           │
              ▼                           ▼
          Exception                    Attempt
              │                           │
              │                           ▼
              │                        Failure
              │                           │
              │                           ▼
              │                     RetryDecision
              │                           │
              ▼                           ▼
       caller/runtime handles       Execution evolves
```

---

# 502. Erreur de contrôle versus échec métier

```text
Database unavailable
        │
        ▼
PersistenceUnavailableError
        │
        ▼
Runtime backoff
```

contre :

```text
Orders API returns 503
        │
        ▼
Failure TRANSIENT
        │
        ▼
RetryPolicy
        │
        ▼
Attempt #2
```

---

# 503. Principe central

> **Une exception dit que PyScheduleKit n’a pas pu honorer une opération ; un Failure dit que le travail effectivement tenté n’a pas réussi.**

---

# 504. Deuxième principe

> **La retryabilité n’est pas une propriété universelle des exceptions : elle résulte de la combinaison entre un Failure normalisé et une RetryPolicy explicite.**

---

# 505. Troisième principe

> **Les erreurs techniques des adapters doivent perdre leur dépendance technologique lorsqu’elles franchissent la frontière vers le cœur du framework, tout en conservant leur cause pour le diagnostic.**

---

# Conclusion

Avec ce modèle, PyScheduleKit évite plusieurs anti-patterns fréquents :

```text
catch Exception → retry

SQL exception → Execution FAILED

Target failure → Scheduler crash

Retry exhausted → raise exception everywhere

Lease lost → treat as target failure

raw vendor exception exposed publicly
```

La chaîne correcte devient :

```text
                     CONTROL PLANE
Technology Error
      │
      ▼
Adapter Normalization
      │
      ▼
PyScheduleKit Exception
      │
      ▼
Application / Runtime handling
```

ou, pour le travail réellement exécuté :

```text
                       WORKLOAD
Target Error
    │
    ▼
Executor Adapter
    │
    ▼
Failure
    │
    ▼
AttemptResult
    │
    ▼
RetryEvaluator
    │
 ┌──┴───────┐
 ▼          ▼
RETRY       STOP
 │          │
 ▼          ▼
Attempt    Execution
 N+1       terminal
```

Cette séparation permet au framework d’être :

```text
prévisible

observable

retriable correctement

portable entre adapters

sûr face aux erreurs distribuées
```

tout en conservant des contrats publics stables.

---

# Suite documentaire

La prochaine étape est :

```text
26_SECURITY_AND_CONFIGURATION_POLICY.md
```

Elle devra fixer notamment :

```text
TargetRef safety

callable resolution

module allowlists

safe serialization

pickle prohibition

configuration sources

environment variables

secret references

redaction

HTTP targets

executor registration

plugin registration

filesystem boundaries

untrusted persisted configuration

multi-tenant considerations

security defaults
```

et répondre à :

> **Quelles données PyScheduleKit peut-il accepter, persister, résoudre et exécuter sans transformer un scheduler en mécanisme d’exécution arbitraire non sécurisé ?**

Puis :

```text
27_TEST_MATRIX_AND_ACCEPTANCE_CRITERIA.md
```

transformera l’ensemble du domaine et de l’API en matrice de preuves, avant :

```text
28_IMPLEMENTATION_ROADMAP.md
```

qui pourra découper la réalisation en lots concrets et progressifs.