# PyScheduleKit — Public API Specification

**Document :** `24_PUBLIC_API_SPEC.md`  
**Projet :** PyScheduleKit  
**Statut :** Spécification de l’API publique V1  
**Nature :** Public API Contract — Scheduler / Triggers / Policies / Handles / Runtime  
**Langue :** Français

**Document de référence principal :**
- `23_TARGET_ARCHITECTURE.md`

**Documents métier associés :**
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

Cette spécification définit la surface Python publique de PyScheduleKit.

Elle répond à :

> **À quoi doit ressembler l’utilisation de PyScheduleKit pour un développeur qui veut planifier du travail sans manipuler l’infrastructure interne du framework ?**

La Public API doit rendre simples les opérations suivantes :

```text
Créer un Scheduler

Enregistrer un Target

Créer un Schedule

Utiliser DateTrigger

Utiliser IntervalTrigger

Utiliser CronTrigger

Configurer les policies

Lister les Schedules

Inspecter un Schedule

Pause

Resume

Reschedule

Cancel

Démarrer le Runtime

Arrêter le Runtime

Tester avec du temps simulé
```

---

# 2. Philosophie de l’API

L’API publique suit cinq principes :

```text
Simple by default

Explicit when advanced

Typed

Safe

Stable
```

---

# 3. Progressive Disclosure

Le cas simple doit rester simple.

Exemple :

```python
from pyschedulekit import Scheduler, IntervalTrigger

scheduler = Scheduler()

scheduler.add_schedule(
    target=my_function,
    trigger=IntervalTrigger(minutes=10),
)

scheduler.start()
```

Un utilisateur débutant ne doit pas avoir à comprendre :

```text
UnitOfWork

OccurrenceKey

PersistenceVersion

Outbox

Lease

FencingToken
```

---

# 4. Cas avancé

Le même framework doit permettre :

```python
scheduler.add_schedule(
    target=TargetRef.python("app.tasks:refresh_customers"),
    trigger=CronTrigger(
        "0 6 * * *",
        timezone="Europe/Paris",
    ),
    misfire=MisfirePolicy.catch_up(max_occurrences=3),
    concurrency=ConcurrencyPolicy.limit(
        max_instances=1,
        overflow="queue",
    ),
    retry=RetryPolicy.exponential(
        max_attempts=4,
        initial_delay="10s",
        multiplier=2,
        max_delay="5m",
    ),
)
```

---

# 5. Namespace public racine

Le namespace principal :

```python
import pyschedulekit
```

doit rester compact.

---

# 6. Imports racine recommandés

```python
from pyschedulekit import (
    Scheduler,
    ScheduleHandle,
    DateTrigger,
    IntervalTrigger,
    CronTrigger,
    TargetRef,
)
```

---

# 7. Policies

Les policies peuvent être exposées depuis :

```python
from pyschedulekit.policies import (
    MisfirePolicy,
    CatchUpPolicy,
    ConcurrencyPolicy,
    RetryPolicy,
)
```

---

# 8. Runtime avancé

Pour les utilisateurs avancés :

```python
from pyschedulekit.runtime import (
    SchedulerRuntime,
    RuntimeConfig,
)
```

---

# 9. Testing

```python
from pyschedulekit.testing import (
    FixedClock,
    MutableClock,
    SchedulerHarness,
)
```

---

# 10. API publique versus interne

Le namespace racine ne doit pas exposer :

```text
SchedulerEngine

OccurrencePlanner

UnitOfWork

SQLAlchemyScheduleRepository

LeaseManager

OutboxRepository
```

par défaut.

---

# 11. Scheduler

`Scheduler` est la façade principale du framework.

Responsabilités :

```text
Créer et administrer les Schedules

Démarrer/arrêter le runtime

Donner accès aux vues publiques

Masquer le wiring interne
```

---

# 12. Construction simple

```python
scheduler = Scheduler()
```

---

# 13. Defaults attendus

`Scheduler()` peut utiliser :

```text
SystemClock

InMemory persistence

Local execution runtime

CallableExecutor

Fixed polling
```

---

# 14. Important

Ces defaults servent :

```text
learning

scripts

tests

small applications
```

et ne constituent pas automatiquement une configuration de production.

---

# 15. Construction configurée

Une API possible :

```python
scheduler = Scheduler.create(
    persistence=...,
    executor=...,
    runtime=...,
)
```

---

# 16. Signature conceptuelle

```python
Scheduler.create(
    *,
    persistence=None,
    executor=None,
    runtime=None,
    clock=None,
    observability=None,
) -> Scheduler
```

---

# 17. Pas de constructeur géant

Éviter :

```python
Scheduler(
    database_url=...,
    pool_size=...,
    broker_url=...,
    poll_interval=...,
    otel_endpoint=...,
    ...
)
```

---

# 18. Composition

Les configurations avancées doivent passer par :

```text
config objects

adapters

composition root
```

---

# 19. `add_schedule()`

Méthode principale.

Signature cible :

```python
scheduler.add_schedule(
    *,
    target,
    trigger,
    id=None,
    name=None,
    misfire=None,
    catch_up=None,
    concurrency=None,
    retry=None,
    timeout=None,
    metadata=None,
) -> ScheduleHandle
```

---

# 20. `target`

Formats acceptés V1 :

```text
Python callable

TargetRef
```

---

# 21. Callable

Exemple :

```python
def cleanup(): ...


scheduler.add_schedule(
    target=cleanup,
    trigger=IntervalTrigger(hours=1),
)
```

---

# 22. Conversion interne

Un callable local peut être transformé en :

```text
local callable target registration
```

par le Scheduler.

---

# 23. Limitation

Un callable Python arbitraire n’est pas forcément :

```text
persistent

serializable

portable across processes
```

---

# 24. API doit documenter cela clairement

Pour persistence/distributed mode, recommander :

```python
TargetRef.python("myapp.tasks:cleanup")
```

---

# 25. TargetRef

`TargetRef` est la référence déclarative publique vers une cible d’exécution.

---

# 26. Constructeurs

```python
TargetRef.python("app.tasks:refresh")
```

```python
TargetRef.workflow("daily-orders")
```

```python
TargetRef.http("customer-api-refresh")
```

selon adapters installés.

---

# 27. TargetRef est immutable

Il doit être :

```text
serializable

comparable

safe
```

---

# 28. Pas de credentials dedans

Interdit :

```text
username/password

API token

secret key
```

---

# 29. `trigger`

Doit être une implémentation publique du contrat :

```text
Trigger
```

---

# 30. Built-ins V1

```text
DateTrigger

IntervalTrigger

CronTrigger
```

---

# 31. DateTrigger

Usage :

```python
DateTrigger(at="2026-10-10T14:00:00+02:00")
```

---

# 32. Alternative datetime

```python
DateTrigger(at=datetime(..., tzinfo=...))
```

---

# 33. Naive datetime

Doit être rejeté.

---

# 34. Relative convenience API

Une helper publique pourrait exister :

```python
DateTrigger.in_(minutes=30)
```

---

# 35. Mais attention

Le résultat doit être résolu à la création en :

```text
absolute Instant
```

---

# 36. Recommandation V1

Ne pas mettre `in_()` directement sur `DateTrigger` tant que son comportement avec Clock n’est pas figé.

Préférer :

```python
scheduler.add_schedule(
    target=...,
    trigger=scheduler.after(minutes=30),
)
```

ou helper dédiée ultérieurement.

---

# 37. IntervalTrigger

Usage :

```python
IntervalTrigger(minutes=10)
```

---

# 38. Autres exemples

```python
IntervalTrigger(seconds=30)
IntervalTrigger(hours=1)
IntervalTrigger(days=2)
```

---

# 39. Interval strictement positif

Invalid :

```python
IntervalTrigger(seconds=0)
```

---

# 40. Anchor

API possible :

```python
IntervalTrigger(
    minutes=10,
    anchor=start_at,
)
```

---

# 41. Sans anchor

Le Scheduler peut définir l’anchor lors de l’activation.

---

# 42. Semantic contract

`IntervalTrigger` signifie :

```text
fixed-rate elapsed duration
```

---

# 43. Pas fixed-delay

Ne pas introduire :

```text
wait 10 minutes after completion
```

dans `IntervalTrigger`.

---

# 44. CronTrigger

Usage :

```python
CronTrigger(
    "0 6 * * *",
    timezone="Europe/Paris",
)
```

---

# 45. Dialect V1

Cinq champs :

```text
minute

hour

day of month

month

day of week
```

---

# 46. Pas de secondes V1

---

# 47. Timezone explicite

Si timezone non fournie :

Deux options possibles :

```text
UTC default

Scheduler default timezone
```

---

# 48. Recommandation

Le Scheduler peut avoir :

```text
default_timezone="UTC"
```

mais `CronTrigger` doit toujours être capable d’exposer la timezone effective.

---

# 49. Pas de timezone système implicite

Éviter :

```text
whatever timezone this machine happens to use
```

---

# 50. CronExpression

Peut rester type interne ou public avancé.

---

# 51. V1

L’utilisateur fournit simplement :

```text
str
```

---

# 52. Trigger inspection

Tous les triggers publics devraient fournir :

```python
trigger.kind
```

et représentation lisible :

```python
repr(trigger)
```

---

# 53. Pas d’API de mutation

Éviter :

```python
trigger.interval = ...
```

---

# 54. Pour modifier

Créer un nouveau Trigger puis :

```python
schedule.reschedule(trigger=new_trigger)
```

---

# 55. Schedule ID

`add_schedule()` accepte optionnellement :

```python
id = "daily-report"
```

---

# 56. ID utilisateur

Doit respecter un format documenté.

Par exemple :

```text
non-empty string

bounded length
```

---

# 57. Generated IDs

Si absent :

```text
UUID-backed ScheduleId
```

---

# 58. Human-readable name

```python
name = "Daily customer refresh"
```

distinct de l’identité.

---

# 59. Metadata

```python
metadata = {
    "team": "finance",
    "environment": "prod",
}
```

---

# 60. Metadata constraints

Doit rester :

```text
JSON-like

small

non-sensitive
```

---

# 61. Metadata ne doit pas porter les policies

---

# 62. ScheduleHandle

`add_schedule()` retourne :

```text
ScheduleHandle
```

---

# 63. Pourquoi pas Schedule Aggregate ?

Pour empêcher la mutation directe et préserver :

```text
application service boundary
```

---

# 64. ScheduleHandle propriétés

```python
handle.id
handle.name
```

---

# 65. Méthodes

```python
handle.pause()
handle.resume()
handle.cancel()
handle.reschedule(...)
handle.inspect()
```

---

# 66. ScheduleHandle n’est pas forcément stateful localement

Chaque opération doit relire :

```text
current durable state
```

si nécessaire.

---

# 67. Stale Handle

Un handle peut survivre à un reschedule.

Ce n’est pas un snapshot complet.

---

# 68. `get_schedule()`

```python
scheduler.get_schedule(schedule_id)
```

retourne préférentiellement :

```text
ScheduleView
```

ou `ScheduleHandle`.

---

# 69. Recommandation

Séparer :

```python
scheduler.get_schedule(id) -> ScheduleView
```

et :

```python
scheduler.schedule(id) -> ScheduleHandle
```

pour éviter ambiguïté.

---

# 70. Mais V1 peut rester simple

```python
scheduler.get_schedule(id) -> ScheduleHandle
```

avec `.snapshot()` si besoin.

---

# 71. Public snapshot

`ScheduleSnapshot` :

```text
id

name

state

revision

trigger summary

next_run_time

target

policies
```

---

# 72. Immutable

Un snapshot ne doit jamais modifier le Schedule.

---

# 73. `list_schedules()`

Signature :

```python
scheduler.list_schedules(
    *,
    state=None,
    limit=None,
) -> list[ScheduleSnapshot]
```

---

# 74. Pagination future

Pour persistence scale :

```text
cursor
```

sera probablement nécessaire.

---

# 75. V1

Une liste bornée suffit.

---

# 76. Pause

```python
scheduler.pause_schedule(schedule_id)
```

ou :

```python
handle.pause()
```

---

# 77. Semantics

Transition :

```text
ACTIVE → PAUSED
```

---

# 78. Idempotency

Pause d’un Schedule déjà PAUSED :

Deux choix :

```text
no-op

error
```

---

# 79. Recommandation

API publique :

```text
idempotent no-op
```

pour pause/resume/cancel lorsque sémantiquement sûr.

---

# 80. Mais état terminal

`resume()` sur :

```text
CANCELLED
```

doit échouer.

---

# 81. Resume

```python
handle.resume()
```

---

# 82. V1 pause semantics

Comme défini :

```text
occurrences during pause are suppressed
```

---

# 83. Resume recalculates future occurrence

Pas implicitement catch-up.

---

# 84. Cancel Schedule

```python
handle.cancel()
```

---

# 85. Semantics

```text
Schedule → CANCELLED
```

terminal.

---

# 86. Ne cancel pas automatiquement les Executions déjà actives

---

# 87. Important

API doit expliquer :

```text
cancel schedule
≠
cancel execution
```

---

# 88. Reschedule

Exemple :

```python
handle.reschedule(trigger=CronTrigger("0 7 * * *", timezone="Europe/Paris"))
```

---

# 89. Peut aussi changer policies

```python
handle.reschedule(
    trigger=...,
    misfire=...,
    concurrency=...,
)
```

---

# 90. ScheduleRevision

Chaque modification de définition :

```text
revision += 1
```

---

# 91. Existing Executions

Ne sont pas modifiées.

---

# 92. Partial update API

Attention au pattern :

```python
reschedule(trigger=None)
```

ambigu.

---

# 93. Recommendation

Utiliser sentinelle interne :

```text
UNSET
```

---

# 94. Public semantics

Champ absent :

```text
keep existing
```

Champ fourni :

```text
replace
```

---

# 95. `remove_schedule()`

Ne devrait pas être API métier principale.

---

# 96. Public method préférée

```python
cancel_schedule()
```

---

# 97. Physical deletion

Future admin API :

```text
purge_schedule()
```

hors V1 publique normale.

---

# 98. Scheduler lifecycle

Méthodes :

```python
scheduler.start()
scheduler.shutdown()
```

---

# 99. `start()`

Démarre le runtime configuré.

---

# 100. Blocking or non-blocking?

C’est une décision importante.

---

# 101. Recommendation V1

```python
scheduler.start()
```

non-blocking.

Le runtime utilise thread local.

---

# 102. Méthode blocking séparée

```python
scheduler.run_forever()
```

---

# 103. Pourquoi ?

Le sens de `start()` est généralement attendu comme :

```text
start background runtime
```

---

# 104. Example

```python
scheduler.start()

app.run()
```

---

# 105. CLI/service mode

```python
scheduler.run_forever()
```

---

# 106. `shutdown()`

```python
scheduler.shutdown(
    *,
    wait=True,
)
```

---

# 107. `wait=True`

Effectue graceful shutdown selon runtime.

---

# 108. `wait=False`

Demande arrêt sans bloquer jusqu’à completion complète.

---

# 109. `start()` idempotence

Si déjà running :

```text
no-op
```

ou public error clair.

---

# 110. Recommendation

No-op + return current status peut être confortable.

---

# 111. `run_pending()`

Très utile pour usage pédagogique et embarqué.

---

# 112. Signature

```python
scheduler.run_pending()
```

---

# 113. Semantics

Effectue :

```text
one evaluation cycle
```

sans boucle continue.

---

# 114. Great for tests

Exemple :

```python
scheduler.run_pending()
```

---

# 115. No sleep

`run_pending()` ne doit jamais :

```text
sleep
```

---

# 116. Return value

Peut retourner :

```text
RunPendingResult
```

---

# 117. RunPendingResult

```text
evaluated_schedules

created_requests

started_executions

errors
```

---

# 118. Attention

Si execution worker est séparé, `run_pending()` ne garantit pas forcément :

```text
target finished
```

---

# 119. Documentation must distinguish

```text
scheduling processed
```

et :

```text
execution completed
```

---

# 120. `tick()`

Alternative name.

---

# 121. Recommendation

Public :

```python
run_pending()
```

Internal :

```text
run_cycle()
```

---

# 122. Runtime status

```python
scheduler.status
```

peut retourner :

```text
RuntimeStatus
```

---

# 123. RuntimeStatus

```text
STOPPED

STARTING

RUNNING

STOPPING

FAILED
```

---

# 124. Read-only.

---

# 125. Health

```python
scheduler.health()
```

retourne :

```text
RuntimeHealthSnapshot
```

---

# 126. Pas juste bool

Inclure :

```text
status

last_successful_cycle_at

next_wakeup_at

lag

reasons
```

---

# 127. `inspect_schedule()`

Possible :

```python
scheduler.inspect_schedule(schedule_id)
```

---

# 128. Return

```text
ScheduleDiagnosticSnapshot
```

---

# 129. `explain_occurrence()`

Future advanced API :

```python
scheduler.explain_occurrence(
    schedule_id,
    scheduled_at,
)
```

---

# 130. V1

Peut rester sous :

```python
scheduler.inspect
```

ou ne pas être publique initialement.

---

# 131. Execution API

PyScheduleKit peut exposer lecture des Executions.

---

# 132. `get_execution()`

```python
scheduler.get_execution(execution_id)
```

retourne :

```text
ExecutionSnapshot
```

---

# 133. ExecutionSnapshot

```text
execution_id

request_id

state

scheduled_at

queued_at

started_at

finished_at

attempts

result
```

---

# 134. Public mutation

Possiblement :

```python
scheduler.cancel_execution(execution_id)
```

---

# 135. Retry manuel

Ne pas appeler :

```python
retry_execution()
```

si cela réouvre le même Execution.

---

# 136. Better

```python
scheduler.rerun_execution(execution_id)
```

---

# 137. Semantics

Crée :

```text
new Execution
```

avec identité différente.

---

# 138. V1

Manual rerun peut être hors scope initial.

---

# 139. Execution listing

```python
scheduler.list_executions(
    *,
    schedule_id=None,
    state=None,
    limit=100,
)
```

---

# 140. Query API separation

À grande échelle :

```text
QueryService
```

sous-jacent.

---

# 141. MisfirePolicy API

Builder-style classmethods.

---

# 142. Examples

```python
MisfirePolicy.skip()
```

```python
MisfirePolicy.run_now()
```

```python
MisfirePolicy.catch_up(max_occurrences=3)
```

---

# 143. GracePeriod

Possible :

```python
MisfirePolicy.skip(grace_period="5m")
```

---

# 144. Better separation

Grace period could be direct Schedule parameter :

```python
scheduler.add_schedule(
    ...,
    grace_period="5m",
    misfire=MisfirePolicy.skip(),
)
```

---

# 145. Which is clearer?

Policy should own semantics of:

```text
what to do after grace exceeded
```

Grace period itself is part of late classification.

---

# 146. Recommendation

Expose:

```python
misfire = MisfirePolicy.skip(grace_period="5m")
```

for ergonomic V1.

---

# 147. Internal model may still separate

```text
GracePeriod
```

VO.

---

# 148. CatchUpPolicy

If MisfirePolicy.catch_up already exists, separate CatchUpPolicy public API may be redundant.

---

# 149. Recommendation V1

Expose combined convenience :

```python
MisfirePolicy.catch_up(
    max_occurrences=10,
)
```

---

# 150. Internally

May create :

```text
MisfirePolicy

CatchUpPolicy
```

separately.

---

# 151. Coalescing

Example :

```python
MisfirePolicy.catch_up(
    max_occurrences=10,
    coalesce="latest",
)
```

---

# 152. Supported V1

```text
none

latest
```

---

# 153. ConcurrencyPolicy

Public constructors :

```python
ConcurrencyPolicy.allow()
```

```python
ConcurrencyPolicy.limit(
    max_instances=1,
    overflow="drop",
)
```

---

# 154. Overflow values

V1 :

```text
drop

queue
```

---

# 155. Maybe enum

```python
OverflowPolicy.DROP
```

---

# 156. Ergonomics

Strings are easy, enums safer.

---

# 157. Recommendation

Public enum :

```python
ConcurrencyOverflow.DROP
ConcurrencyOverflow.QUEUE
```

mais accepter strings peut être considered later.

---

# 158. Default

Recommended default :

```text
max_instances = 1
overflow = queue?
```

---

# 159. Important decision

Default `ALLOW` can surprise users with overlapping runs.

Default `LIMIT(1)` can surprise users expecting parallelism.

---

# 160. Recommendation V1

Use explicit conservative default :

```text
max_instances = 1
overflow = queue
```

for scheduled tasks.

---

# 161. But document clearly

This is an API philosophy decision.

---

# 162. RetryPolicy

Public constructors :

```python
RetryPolicy.none()
```

```python
RetryPolicy.fixed(
    max_attempts=3,
    delay="10s",
)
```

```python
RetryPolicy.exponential(
    max_attempts=5,
    initial_delay="5s",
    multiplier=2,
    max_delay="5m",
)
```

---

# 163. `max_attempts`

Includes initial attempt.

---

# 164. Important

Never expose ambiguous :

```text
max_retries
```

unless semantics clearly separate.

---

# 165. Default RetryPolicy

Recommended :

```python
RetryPolicy.none()
```

---

# 166. Why?

Automatic retries can duplicate side effects.

---

# 167. Users opt in explicitly.

---

# 168. Timeout API

Possible :

```python
timeout = ExecutionTimeout(
    attempt="30s",
    execution="5m",
)
```

---

# 169. V1 simpler

```python
scheduler.add_schedule(
    ...,
    attempt_timeout="30s",
    execution_timeout="5m",
)
```

---

# 170. But too many kwargs

Better :

```python
execution_policy = ExecutionPolicy(
    retry=...,
    attempt_timeout="30s",
    deadline="5m",
)
```

---

# 171. Public ergonomics trade-off

---

# 172. Recommendation

V1 simple kwargs for common cases :

```python
retry = ...
attempt_timeout = ...
```

ExecutionDeadline advanced later.

---

# 173. Duration input

Public API should accept :

```text
timedelta

Duration

compact duration string
```

---

# 174. Compact strings

Examples :

```text
"30s"

"5m"

"2h"

"1d"
```

---

# 175. Need precise grammar

No ambiguous :

```text
"1 month"
```

because calendar period ≠ Duration.

---

# 176. Supported V1 units

```text
ms?

s

m

h

d
```

---

# 177. Recommendation

V1 :

```text
s

m

h

d
```

where `d = 24 hours`.

---

# 178. Calendar days

Use Cron/calendar rules, not Duration parser.

---

# 179. Timezone strings

Accept IANA names :

```text
Europe/Paris
UTC
America/New_York
```

---

# 180. Reject ambiguous abbreviations

Avoid :

```text
CET

EST
```

when ambiguous.

---

# 181. Trigger validation timing

Construction should fail early.

Example :

```python
CronTrigger("99 99 * * *")
```

raises immediately.

---

# 182. Better than failure at runtime.

---

# 183. Public exceptions

All public validation/runtime exceptions should derive from :

```python
PyScheduleKitError
```

---

# 184. Initial hierarchy

```text
PyScheduleKitError
│
├── ConfigurationError
├── ValidationError
├── ScheduleError
├── ExecutionError
├── PersistenceError
└── RuntimeError
```

---

# 185. But detailed error model is document 25

This document only defines public behavior.

---

# 186. User should not catch SQLAlchemy exceptions

---

# 187. Example

Instead of :

```python
except sqlalchemy.exc.OperationalError:
```

public user sees :

```python
except PersistenceUnavailableError:
```

---

# 188. Public identifiers

Types :

```text
ScheduleId

ExecutionId

RequestId
```

can be public read-only VOs.

---

# 189. Ergonomics

Methods should accept either :

```text
ScheduleId

str
```

where reasonable.

---

# 190. Internally normalize.

---

# 191. Public state enums

Expose :

```text
ScheduleState

ExecutionState

AttemptState
```

---

# 192. Stable string values

Example :

```text
active

paused

cancelled

completed
```

---

# 193. Scheduler context manager

Possible:

```python
with Scheduler() as scheduler:
    scheduler.add_schedule(...)
```

---

# 194. Semantics

`__enter__` :

```text
start()
```

`__exit__` :

```text
shutdown(wait=True)
```

---

# 195. Is auto-start desirable?

Could surprise.

---

# 196. Recommendation

Context manager does auto-start because that is conventional resource behavior.

Document explicitly.

---

# 197. Alternative

```python
with scheduler.running():
    ...
```

more explicit.

---

# 198. V1 recommendation

Do not add context manager until lifecycle API is proven.

---

# 199. Avoid API surface explosion.

---

# 200. Default timezone

Scheduler construction :

```python
Scheduler(
    default_timezone="UTC",
)
```

may be reasonable.

---

# 201. But earlier constructor minimality

Could use :

```python
RuntimeConfig(default_timezone="UTC")
```

---

# 202. Timezone is more schedule semantic than runtime infrastructure.

---

# 203. Recommendation

`Scheduler` accepts :

```python
default_timezone = "UTC"
```

as one ergonomic top-level setting.

---

# 204. Cron trigger without timezone

Uses Scheduler default timezone at Schedule creation.

---

# 205. Important

Effective timezone must then be persisted into ScheduleDefinition.

---

# 206. Never depend later on changed Scheduler default.

---

# 207. Default policy values

Need explicit V1 defaults.

Recommended :

```text
MisfirePolicy = SKIP
GracePeriod = 0?
Concurrency = LIMIT 1 + QUEUE
Retry = NONE
Timezone = UTC
```

---

# 208. GracePeriod = 0 issue

Any small scheduling delay becomes misfire.

---

# 209. Better default

A practical default like :

```text
60 seconds
```

would be opinionated.

---

# 210. Learning framework recommendation

Do not hide this.

Require explicit misfire behavior for persistent schedules?

---

# 211. Too verbose.

---

# 212. Proposed V1 default

```text
MisfirePolicy.run_now(grace_period=None)
```

could mean late occurrences remain eligible without immediate misfire.

---

# 213. But unbounded lateness is dangerous.

---

# 214. Better architectural decision

Separate :

```text
late occurrence
```

from :

```text
misfire
```

using default grace.

---

# 215. Recommendation V1

Set documented default :

```text
grace_period = 60s
misfire = SKIP
```

for standard schedules.

---

# 216. But configuration must expose it.

---

# 217. This decision should be validated during implementation spikes.

---

# 218. Public scheduling method aliases

Avoid too many aliases.

Example avoid simultaneously:

```text
add_job

schedule

schedule_job

add_task

add_schedule
```

---

# 219. Canonical term

Use :

```python
add_schedule()
```

because ubiquitous language says Schedule.

---

# 220. Avoid `add_job()` V1

Since Job is optional/non-core.

---

# 221. Cron convenience API

Could offer :

```python
scheduler.cron(
    target=...,
    expression="0 6 * * *",
)
```

---

# 222. Avoid V1

It duplicates `add_schedule()`.

---

# 223. Interval convenience

Same.

Keep constructors composable.

---

# 224. Explicit > magical

---

# 225. Schedule constructor public?

Should users instantiate :

```python
Schedule(...)
```

directly?

---

# 226. Recommendation

No for normal API.

---

# 227. Why?

Schedule creation needs :

```text
ID allocation

activation time

next_run_time initialization

validation

persistence
```

---

# 228. Use Scheduler/Service.

---

# 229. Public Schedule class

Can remain internal domain concept initially.

Expose :

```text
ScheduleHandle

ScheduleSnapshot
```

instead.

---

# 230. Trigger objects are public VOs

Safe to instantiate directly.

---

# 231. Policy objects public VOs

Safe to instantiate directly.

---

# 232. Execution entity not directly user-constructed

---

# 233. ScheduleSnapshot

Proposed fields :

```python
@dataclass(frozen=True)
class ScheduleSnapshot:
    id: ScheduleId
    name: str | None
    state: ScheduleState
    revision: int
    target: TargetRef
    trigger: TriggerSnapshot
    next_run_time: datetime | None
    created_at: datetime
    updated_at: datetime
```

---

# 234. TriggerSnapshot

May expose :

```text
kind

summary

configuration
```

---

# 235. Avoid leaking concrete persistence JSON.

---

# 236. ExecutionSnapshot

Proposed :

```text
id

schedule_id

scheduled_at

state

attempt_count

next_attempt_at

started_at

finished_at

result
```

---

# 237. AttemptSnapshot

```text
attempt_number

state

started_at

finished_at

failure
```

---

# 238. Public result objects

Should be immutable.

---

# 239. `ExecutionResult`

Can be public normalized object.

---

# 240. It must not expose raw ORM records.

---

# 241. Async API

Out of V1.

---

# 242. No methods like :

```python
await scheduler.add_schedule(...)
```

initially.

---

# 243. Future package

Could provide :

```python
from pyschedulekit.asyncio import AsyncScheduler
```

---

# 244. Important

Do not make sync API internally call :

```text
asyncio.run()
```

for every operation.

---

# 245. CLI use

The same Public/Application contracts should support future :

```text
pyschedule add

pyschedule pause

pyschedule inspect
```

---

# 246. Public API remains Python-first

CLI is adapter.

---

# 247. Scheduler startup with no schedules

Valid.

---

# 248. Runtime simply waits/polls.

---

# 249. Add Schedule after start

Must be supported.

---

# 250. Example

```python
scheduler.start()

scheduler.add_schedule(...)
```

---

# 251. Runtime should be notified after commit.

---

# 252. Remove/cancel while running

Also supported.

---

# 253. Thread safety

Public Scheduler methods may be called while runtime thread is active.

---

# 254. Therefore API must be thread-safe at service/persistence boundary.

---

# 255. But domain objects themselves need not be globally thread-safe.

---

# 256. Scheduler facade serializes/coordinates as required.

---

# 257. Public method timeout

Should API calls accept operation timeouts?

Not V1.

Use infrastructure defaults.

---

# 258. Persistence errors propagate normalized public exceptions.

---

# 259. Scheduler `start()` failure

If persistence unavailable :

```text
RuntimeStartError
```

or wrapped public runtime error.

Detailed in doc 25.

---

# 260. `shutdown()` during failed runtime

Should remain safe/idempotent.

---

# 261. `run_pending()` while background runtime running

Potential race.

---

# 262. Recommendation

Reject with :

```text
RuntimeAlreadyRunningError
```

or make it a no-op.

---

# 263. Better

Reject.

It avoids two simultaneous cycles in same Scheduler instance.

---

# 264. Similarly

```python
run_forever()
```

when already running should error.

---

# 265. Scheduler ownership

One Scheduler facade owns one SchedulerRuntime instance.

---

# 266. Multiple Scheduler instances

Allowed.

---

# 267. Same database

Possible, becomes distributed coordination case.

---

# 268. In-memory callable targets

Cannot be shared across instances/processes.

Document.

---

# 269. Public serialization

Users may need export/import of Schedule definitions.

---

# 270. Future API

```python
scheduler.export_schedule(id)
```

---

# 271. Not V1 required.

---

# 272. But config objects should be serializable internally.

---

# 273. Declarative configuration

Future YAML:

```yaml
id: daily-report
target:
  kind: python
  ref: app.tasks:report
trigger:
  kind: cron
  expression: "0 6 * * *"
  timezone: Europe/Paris
```

---

# 274. But no YAML loader in core V1.

---

# 275. Public config model can come later.

---

# 276. Custom Trigger public extension

Potential protocol :

```python
class Trigger(Protocol):
    def next_after(self, reference: Instant) -> Instant | None: ...
```

---

# 277. But persistence needs codec registration.

---

# 278. Therefore custom Trigger support in V1 local mode only may be acceptable.

---

# 279. Persistent custom Trigger

Requires :

```text
TriggerCodec
```

registration.

---

# 280. Public registration future

```python
scheduler.register_trigger(
    kind="business_day",
    trigger_type=BusinessDayTrigger,
    codec=BusinessDayTriggerCodec,
)
```

---

# 281. Not V1 core.

---

# 282. Custom Executor registration

More important.

---

# 283. Possible API

```python
scheduler.register_executor(
    "workflow",
    workflow_executor,
)
```

---

# 284. TargetRef routing

```python
TargetRef.workflow(...)
```

uses `"workflow"` executor kind.

---

# 285. Better composition

Advanced users may inject prebuilt:

```text
ExecutorRouter
```

instead.

---

# 286. Public registration can be convenience.

---

# 287. V1 built-in local executor

For callable targets.

---

# 288. Public `executor=` parameter

Schedule-specific executor selection?

Avoid initially.

---

# 289. TargetRef kind determines executor.

---

# 290. Prevent contradictory config

Avoid :

```python
target = TargetRef.http(...)
executor = "python"
```

---

# 291. `TargetRef` is enough routing information.

---

# 292. Scheduler introspection

Potential :

```python
scheduler.capabilities()
```

---

# 293. Could report :

```text
persistence

distributed coordination

supported target kinds

supported trigger kinds
```

---

# 294. Not V1 necessary.

---

# 295. Public repr

Objects should have useful `repr()`.

---

# 296. Example

```text
CronTrigger("0 6 * * *", timezone="Europe/Paris")
```

---

# 297. ScheduleHandle repr

```text
<ScheduleHandle id='daily-report'>
```

---

# 298. Avoid huge payload reprs.

---

# 299. Equality

Triggers and Policies are VOs.

Structural equality desirable.

---

# 300. ScheduleHandle equality

By :

```text
ScheduleId
```

likely.

---

# 301. Snapshot equality

Structural.

---

# 302. Public hashing

Immutable VOs may be hashable.

---

# 303. Scheduler itself not hashable requirement.

---

# 304. Type hints

Public API must be fully typed.

---

# 305. No pervasive `Any`

except adapter boundaries where unavoidable.

---

# 306. Protocols

Public extension interfaces should use :

```text
typing.Protocol
```

where appropriate.

---

# 307. Python type aliases

Use intentionally.

---

# 308. DurationLike

Possible alias :

```python
DurationLike = Duration | timedelta | str
```

---

# 309. InstantLike

```python
InstantLike = Instant | datetime | str
```

---

# 310. But do not over-export utility aliases unnecessarily.

---

# 311. Input normalization

Happens at API boundary.

---

# 312. Output normalization

Public snapshots expose stable types.

---

# 313. No dict soup

Avoid methods returning :

```python
dict[str, Any]
```

for major concepts.

---

# 314. Use dataclasses.

---

# 315. Public API versioning

Before 1.0 :

```text
breaking changes allowed
```

under semver pre-1.0 rules.

---

# 316. But still document deprecated APIs.

---

# 317. After 1.0

Public contracts need compatibility guarantees.

---

# 318. Internal modules

Can evolve without compatibility.

---

# 319. Public namespace allowlist

The project should maintain explicit list of public symbols.

---

# 320. Avoid accidental exports

---

# 321. `__all__`

Can help.

---

# 322. Proposed root `__all__`

```text
Scheduler

ScheduleHandle

ScheduleSnapshot

DateTrigger

IntervalTrigger

CronTrigger

TargetRef

ScheduleState
```

---

# 323. Policies package `__all__`

```text
MisfirePolicy

ConcurrencyPolicy

RetryPolicy

ConcurrencyOverflow
```

---

# 324. Testing package public symbols

```text
FixedClock

MutableClock

SchedulerHarness

FakeExecutor
```

---

# 325. Example — one-shot

```python
from datetime import datetime, timezone

from pyschedulekit import Scheduler, DateTrigger

scheduler = Scheduler()

scheduler.add_schedule(
    id="send-reminder",
    target=send_reminder,
    trigger=DateTrigger(
        at=datetime(
            2026,
            10,
            10,
            8,
            0,
            tzinfo=timezone.utc,
        )
    ),
)

scheduler.start()
```

---

# 326. Example — interval

```python
from pyschedulekit import Scheduler, IntervalTrigger

scheduler = Scheduler()

scheduler.add_schedule(
    id="heartbeat",
    target=heartbeat,
    trigger=IntervalTrigger(seconds=30),
)

scheduler.start()
```

---

# 327. Example — cron

```python
from pyschedulekit import Scheduler, CronTrigger

scheduler = Scheduler(
    default_timezone="Europe/Paris",
)

scheduler.add_schedule(
    id="daily-report",
    target=build_daily_report,
    trigger=CronTrigger("0 6 * * *"),
)

scheduler.start()
```

---

# 328. Effective timezone

At add time :

```text
Europe/Paris
```

is copied into durable ScheduleDefinition.

---

# 329. Example — policies

```python
from pyschedulekit import Scheduler, CronTrigger
from pyschedulekit.policies import (
    MisfirePolicy,
    ConcurrencyPolicy,
    RetryPolicy,
)

scheduler.add_schedule(
    id="refresh-customers",
    target=refresh_customers,
    trigger=CronTrigger(
        "*/10 * * * *",
        timezone="Europe/Paris",
    ),
    misfire=MisfirePolicy.catch_up(
        max_occurrences=2,
        coalesce="latest",
    ),
    concurrency=ConcurrencyPolicy.limit(
        max_instances=1,
        overflow="queue",
    ),
    retry=RetryPolicy.exponential(
        max_attempts=3,
        initial_delay="10s",
        multiplier=2,
        max_delay="2m",
    ),
)
```

---

# 330. Example — pause

```python
schedule = scheduler.get_schedule("daily-report")

schedule.pause()
```

---

# 331. Example — resume

```python
schedule.resume()
```

---

# 332. Example — reschedule

```python
schedule.reschedule(
    trigger=CronTrigger(
        "0 7 * * *",
        timezone="Europe/Paris",
    )
)
```

---

# 333. Example — cancel

```python
schedule.cancel()
```

---

# 334. Example — manual tick

```python
scheduler.run_pending()
```

---

# 335. Example — virtual time test

```python
from pyschedulekit.testing import SchedulerHarness

harness = SchedulerHarness(
    start_at="2026-01-01T10:00:00Z",
)

harness.add_schedule(
    target=my_task,
    trigger=IntervalTrigger(minutes=10),
)

harness.advance("10m")

assert harness.executions_count() == 1
```

---

# 336. Harness API

Potential convenience :

```python
harness.advance("10m")
```

does :

```text
advance clock

run scheduler

optionally drain local execution
```

---

# 337. Need explicit behavior

Could provide :

```python
harness.advance("10m", run=True)
```

---

# 338. Better V1

```python
harness.advance("10m")
harness.run_pending()
```

separates time change from scheduling.

---

# 339. This mirrors architecture

Excellent for learning.

---

# 340. Testing method

```python
harness.run_until_idle()
```

could process :

```text
all immediately due runtime work
```

without advancing time.

---

# 341. Useful for retries with zero/same-time work.

---

# 342. Avoid infinite loops

`run_until_idle()` must have :

```text
max_cycles
```

guard.

---

# 343. ScheduleHandle API proposal

```python
class ScheduleHandle:
    @property
    def id(self) -> ScheduleId: ...

    def snapshot(self) -> ScheduleSnapshot: ...

    def pause(self) -> ScheduleSnapshot: ...

    def resume(self) -> ScheduleSnapshot: ...

    def reschedule(...) -> ScheduleSnapshot: ...

    def cancel(self) -> ScheduleSnapshot: ...
```

---

# 344. Why return Snapshot after mutation?

Convenient and avoids second query.

---

# 345. Mutation methods return updated durable state.

---

# 346. Scheduler method equivalents

Also expose :

```python
scheduler.pause_schedule(id)
scheduler.resume_schedule(id)
scheduler.reschedule_schedule(id, ...)
scheduler.cancel_schedule(id)
```

---

# 347. Is duplication necessary?

Maybe not.

---

# 348. Recommendation

Keep Scheduler methods canonical.

ScheduleHandle delegates to them as convenience.

---

# 349. Example

```text
handle.pause()
```

internally calls :

```text
Scheduler.pause_schedule(handle.id)
```

---

# 350. Avoid two implementations of logic.

---

# 351. Public API and transactions

User does not manually call :

```text
commit()
```

for standard operations.

---

# 352. Each public mutating operation

is one application transaction.

---

# 353. Advanced UnitOfWork not part of normal public API.

---

# 354. Bulk operations

Future :

```python
with scheduler.batch():
    ...
```

could share transaction.

---

# 355. Not V1.

---

# 356. Why?

Complex interaction with notifications and IDs.

---

# 357. Public atomicity promise

Each command like :

```text
add_schedule

pause_schedule

reschedule_schedule
```

is atomic from application perspective.

---

# 358. `add_schedule()` success means

Schedule has been durably created in persistent mode.

---

# 359. It does not mean

First execution has completed.

---

# 360. `cancel_schedule()` success means

Schedule is CANCELLED.

Not :

```text
all executions have stopped
```

---

# 361. `shutdown()` success means

Runtime lifecycle completed according to configured shutdown semantics.

---

# 362. Public method docs must distinguish these.

---

# 363. API and observability

Mutation methods may optionally return:

```text
correlation_id
```

but not necessary.

---

# 364. Public advanced method :

```python
scheduler.events(...)
```

not V1.

---

# 365. Diagnostics via snapshots sufficient.

---

# 366. Public default errors

Validation errors should occur before persistence when possible.

---

# 367. Example

```python
IntervalTrigger(seconds=-5)
```

fails at construction.

---

# 368. Example

```python
CronTrigger("invalid")
```

fails at construction.

---

# 369. Example

```python
ConcurrencyPolicy.limit(max_instances=0)
```

fails at construction.

---

# 370. Schedule lifecycle invalid transition

Fails when command applied.

---

# 371. Missing schedule

```python
scheduler.get_schedule("missing")
```

raises :

```text
ScheduleNotFoundError
```

rather than returning `None`?

---

# 372. Recommendation

`get_schedule()` raises.

---

# 373. Optional lookup

Provide :

```python
scheduler.find_schedule(id)
```

returns :

```text
ScheduleHandle | None
```

---

# 374. Is that API bloat?

Possibly.

---

# 375. V1

Only `get_schedule()` raising explicit error.

---

# 376. Lists naturally return empty list.

---

# 377. Start schedule immediately?

A Schedule's first occurrence follows Trigger semantics.

No implicit execution on add.

---

# 378. If user wants run now

Need explicit :

```python
DateTrigger(at=now)
```

or manual execution API later.

---

# 379. Avoid `run_on_start=True`

initially.

---

# 380. Manual immediate execution

Potential future :

```python
scheduler.run_now(schedule_id)
```

---

# 381. Semantics question

Would this create :

```text
synthetic occurrence

manual rerun

new execution
```

---

# 382. Needs separate design.

Not V1.

---

# 383. Backfill API

Also future.

---

# 384. API boundaries should reflect domain maturity.

---

# 385. Trigger and policy repr

Should be deterministic enough for debugging.

---

# 386. But repr not serialization contract.

---

# 387. Public `to_dict()`

Should we expose?

---

# 388. Recommendation

Not on every domain VO V1.

Use future config/export layer.

---

# 389. Avoid coupling API to persistence representation.

---

# 390. Deprecation strategy

A deprecated public symbol should emit :

```text
DeprecationWarning
```

with replacement path.

---

# 391. No silent semantic change.

---

# 392. Public API changelog

Required before stable releases.

---

# 393. Type-checking compatibility

Aim to work with :

```text
mypy

pyright
```

---

# 394. `.pyi` stubs unnecessary if package typed directly.

---

# 395. Add :

```text
py.typed
```

when package distributed.

---

# 396. Public docstring quality

Every public class/method must document :

```text
semantics

parameters

returns

raises

timing behavior
```

---

# 397. Particularly

```text
start

shutdown

pause

resume

reschedule
```

need semantic contracts.

---

# 398. Thread-safety documentation

Public docs should state:

```text
Scheduler facade methods are safe to invoke while
the SchedulerRuntime is active.
```

if implementation guarantees it.

---

# 399. If not yet guaranteed

Do not claim it.

---

# 400. V1 target

Yes, facade mutating methods should be runtime-safe.

---

# 401. Public API non-goals

V1 will not expose :

```text
distributed lease manipulation

fencing tokens

database sessions

outbox records

worker heartbeats

leader election controls

raw ORM entities
```

---

# 402. These belong to advanced/internal infrastructure.

---

# 403. V1 canonical surface

```text
Scheduler

ScheduleHandle

ScheduleSnapshot

TargetRef

DateTrigger

IntervalTrigger

CronTrigger

MisfirePolicy

ConcurrencyPolicy

RetryPolicy

ScheduleState

ExecutionState
```

---

# 404. Optional testing surface

```text
FixedClock

MutableClock

SchedulerHarness

FakeExecutor
```

---

# 405. Canonical Scheduler methods V1

```text
add_schedule()

get_schedule()

list_schedules()

pause_schedule()

resume_schedule()

reschedule_schedule()

cancel_schedule()

get_execution()

list_executions()

cancel_execution()

run_pending()

start()

run_forever()

shutdown()

health()
```

---

# 406. Maybe too many?

Still manageable.

---

# 407. Minimal V1 core

Could first implement:

```text
add_schedule

get_schedule

pause

resume

reschedule

cancel

run_pending

start

shutdown
```

---

# 408. Execution querying can follow.

---

# 409. Public trigger contract V1

```text
DateTrigger

IntervalTrigger

CronTrigger
```

immutable and serializable.

---

# 410. Public policy contract V1

```text
MisfirePolicy

ConcurrencyPolicy

RetryPolicy
```

immutable.

---

# 411. Default semantics must never depend on host environment

Especially:

```text
timezone

clock

locale
```

---

# 412. UTC is safe universal default.

---

# 413. Public API lifecycle example

```text
Scheduler()
   │
   ▼
add_schedule()
   │
   ▼
ScheduleHandle
   │
   ▼
start()
   │
   ▼
RUNNING
   │
   ├── pause/resume/reschedule
   │
   └── executions
   │
   ▼
shutdown()
```

---

# 414. Public scheduling flow

```text
Target
  +
Trigger
  +
Policies
  │
  ▼
add_schedule()
  │
  ▼
ScheduleHandle
  │
  ▼
SchedulerRuntime
  │
  ▼
Execution
```

---

# 415. Public/internal boundary

```text
PUBLIC
──────────────────────────────
Scheduler
ScheduleHandle
Triggers
Policies
Snapshots
──────────────────────────────
INTERNAL
SchedulerEngine
OccurrencePlanner
UnitOfWork
Repositories
Outbox
LeaseManager
```

---

# 416. API invariants

```text
1.
A public Schedule mutation always goes through
an application service.

2.
Public handles never mutate Aggregate state directly.

3.
Triggers and Policies are immutable.

4.
Naive datetime values are rejected.

5.
Persistent Schedules store effective timezone explicitly.

6.
RetryPolicy defaults to no retry.

7.
Manual Schedule cancellation does not imply
active Execution cancellation.

8.
Reschedule increments ScheduleRevision.

9.
Existing Executions retain their policy snapshots.

10.
run_pending() never sleeps.

11.
start() and run_pending() do not run concurrently
within one Scheduler instance.

12.
Public API never exposes ORM models.

13.
Public methods surface normalized exceptions.

14.
Callable targets are documented as local/non-portable
unless resolvable declaratively.

15.
TargetRef never stores secrets.

16.
Public state snapshots are immutable.

17.
Root namespace remains intentionally small.

18.
Advanced infrastructure concepts remain optional.

19.
Every public behavior maps to an explicit domain concept.

20.
No convenience API silently changes scheduling semantics.
```

---

# 417. V1 API decisions

```text
1.
Scheduler is the primary facade.

2.
add_schedule() is the canonical creation method.

3.
No add_job() alias in V1.

4.
Job is not mandatory in the public API.

5.
ScheduleHandle is returned instead of exposing
the Schedule Aggregate.

6.
DateTrigger, IntervalTrigger and CronTrigger
are public immutable Value Objects.

7.
Cron V1 uses five fields.

8.
UTC is the framework default timezone.

9.
Timezone becomes explicit in persisted ScheduleDefinition.

10.
Retry defaults to NONE.

11.
Concurrency defaults will be conservative
and explicitly documented.

12.
Public mutating operations are atomic.

13.
start() is non-blocking.

14.
run_forever() is blocking.

15.
run_pending() performs one immediate cycle without sleep.

16.
shutdown() provides graceful runtime stop.

17.
Persistent/distributed infrastructure is configured
through adapters/configuration objects.

18.
Public APIs do not expose UnitOfWork or repositories.

19.
Public snapshots and result objects are typed dataclasses.

20.
Async API is deferred.
```

---

# 418. Open decisions before implementation freeze

Quelques points doivent être confirmés par prototypes :

```text
Default MisfirePolicy

Default GracePeriod

Default ConcurrencyPolicy

Exact Scheduler constructor

ScheduleHandle versus direct Scheduler commands

Duration string grammar

Callable target persistence behavior

Cron parser implementation

start() idempotence behavior
```

---

# 419. These are implementation-validation questions

Pas des trous majeurs dans le domaine.

---

# 420. Acceptance criteria

La Public API est prête lorsque l'on peut réaliser proprement :

```text
Créer un Schedule one-shot

Créer un Schedule interval

Créer un Schedule cron

Configurer timezone

Configurer misfire

Configurer concurrency

Configurer retry

Pause

Resume

Reschedule

Cancel

Faire un tick manuel

Démarrer en background

Démarrer en blocking mode

Arrêter proprement

Inspecter un Schedule

Observer son next_run_time

Tester avec FixedClock

Changer persistence adapter
sans changer le code métier utilisateur
```

---

# 421. Example — API complète V1

```python
from pyschedulekit import (
    Scheduler,
    CronTrigger,
    TargetRef,
)
from pyschedulekit.policies import (
    MisfirePolicy,
    ConcurrencyPolicy,
    RetryPolicy,
)

scheduler = Scheduler(
    default_timezone="Europe/Paris",
)

daily_orders = scheduler.add_schedule(
    id="daily-orders",
    name="Daily Orders Pipeline",
    target=TargetRef.workflow("daily-orders"),
    trigger=CronTrigger("0 6 * * *"),
    misfire=MisfirePolicy.catch_up(
        max_occurrences=2,
        coalesce="latest",
    ),
    concurrency=ConcurrencyPolicy.limit(
        max_instances=1,
        overflow="queue",
    ),
    retry=RetryPolicy.exponential(
        max_attempts=3,
        initial_delay="10s",
        multiplier=2,
        max_delay="2m",
    ),
)

scheduler.start()

snapshot = daily_orders.snapshot()

print(snapshot.state)
print(snapshot.next_run_time)
```

---

# 422. Exemple — contrôle du Schedule

```python
daily_orders.pause()

daily_orders.resume()

daily_orders.reschedule(
    trigger=CronTrigger(
        "30 6 * * *",
        timezone="Europe/Paris",
    )
)

daily_orders.cancel()
```

---

# 423. Exemple — test déterministe

```python
from pyschedulekit import IntervalTrigger
from pyschedulekit.testing import SchedulerHarness

harness = SchedulerHarness(
    start_at="2026-01-01T10:00:00Z",
)

handle = harness.add_schedule(
    id="refresh",
    target=lambda: None,
    trigger=IntervalTrigger(minutes=10),
)

harness.advance("9m")
harness.run_pending()

assert harness.executions_count() == 0

harness.advance("1m")
harness.run_pending()

assert harness.executions_count() == 1
```

---

# 424. Experience Developer cible

PyScheduleKit doit permettre à l’utilisateur de penser :

```text
"When should this run?"
```

avant de devoir penser :

```text
"Which transaction strategy,
lease provider,
repository implementation,
outbox publisher,
or fencing token do I need?"
```

---

# 425. Mais sans cacher la sémantique métier

Les notions importantes restent explicites :

```text
Trigger

Timezone

Misfire

Concurrency

Retry
```

---

# 426. C'est la frontière recherchée

Masquer :

```text
plomberie technique
```

mais pas :

```text
décisions métier importantes
```

---

# 427. Modèle mental final de l’API

```text
                 USER CODE
                    │
                    ▼
               Scheduler
                    │
        ┌───────────┼────────────┐
        │           │            │
        ▼           ▼            ▼
     Target       Trigger      Policies
        │           │            │
        └───────────┼────────────┘
                    ▼
              ScheduleHandle
                    │
                    ▼
             Application Layer
                    │
                    ▼
                Runtime
```

---

# 428. API/Public contract boundary

```text
Developer sees:

Scheduler
TargetRef
Triggers
Policies
Handles
Snapshots

Developer does NOT need to see:

SchedulerEngine
OccurrencePlanner
Repositories
UnitOfWork
Outbox
Claims
Leases
Fencing
```

---

# 429. Définition finale

> **L’API publique de PyScheduleKit expose les concepts nécessaires pour exprimer une intention temporelle et administrer son cycle de vie, tout en masquant la mécanique interne de persistance, d’exécution et de coordination.**

---

# Conclusion

Le domaine complet de PyScheduleKit peut être riche :

```text
Occurrence

Misfire

Catch-Up

Concurrency

Retry

Persistence

Outbox

Leases

Fencing
```

mais l’utilisateur standard doit surtout manipuler :

```text
Scheduler

Target

Trigger

Policies

ScheduleHandle
```

La philosophie finale est :

> **Simple à utiliser ne doit pas signifier simpliste dans ses garanties.**

Ainsi :

```python
scheduler.add_schedule(
    target=my_task,
    trigger=CronTrigger(
        "0 6 * * *",
        timezone="Europe/Paris",
    ),
)
```

doit rester une opération concise, tout en s’appuyant en interne sur :

```text
ScheduleDefinition

Occurrence planning

Misfire semantics

Concurrency control

Durable requests

Execution lifecycle

Retry lifecycle

Persistence

Observability
```

Le **24** établit donc la frontière entre :

```text
la richesse interne du framework
```

et :

```text
l'expérience développeur
```

qui doit rester claire, cohérente et Pythonique.

---

# Suite documentaire

Le prochain document logique est :

```text
25_ERROR_MODEL.md
```

Il devra figer :

```text
exception hierarchy

domain errors

validation errors

lifecycle conflicts

persistence failures

runtime failures

executor failures

retryable versus non-retryable errors

public exception normalization

error codes

safe messages

cause chaining
```

et répondre à :

> **Quelles erreurs PyScheduleKit expose-t-il à l’utilisateur, lesquelles deviennent des Failure métier, lesquelles doivent être retriées, et lesquelles doivent rester purement techniques ?**

Puis :

```text
26_SECURITY_AND_CONFIGURATION_POLICY.md
```

pour sécuriser `TargetRef`, la sérialisation, les secrets, les imports et les configurations,

```text
27_TEST_MATRIX_AND_ACCEPTANCE_CRITERIA.md
```

pour transformer les contrats publics et internes en preuves exécutables,

et enfin :

```text
28_IMPLEMENTATION_ROADMAP.md
```

pour construire le framework lot par lot.