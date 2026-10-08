# PyScheduleKit — Security & Configuration Policy

**Document :** `26_SECURITY_AND_CONFIGURATION_POLICY.md`  
**Projet :** PyScheduleKit  
**Statut :** Politique de sécurité et de configuration V1  
**Nature :** Security Model — Configuration / Target Resolution / Serialization / Secrets / Plugins / Trust Boundaries  
**Langue :** Français

**Documents de référence :**
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`
- `19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md`
- `20_DISTRIBUTED_COORDINATION_LEASES_AND_LEADER_ELECTION.md`
- `21_OBSERVABILITY_AUDIT_EVENTS_AND_DIAGNOSTICS_MODEL.md`
- `23_TARGET_ARCHITECTURE.md`
- `24_PUBLIC_API_SPEC.md`
- `25_ERROR_MODEL.md`

---

# 1. Objectif

PyScheduleKit manipule plusieurs catégories de données potentiellement sensibles ou dangereuses :

```text
TargetRef

ScheduleDefinition

Trigger configuration

Executor configuration

database configuration

HTTP endpoints

plugin registrations

secret references

environment variables

serialized schedules
```

Certaines d’entre elles peuvent indirectement provoquer :

```text
une exécution Python

un appel HTTP

le lancement d’un workflow

une connexion à une base

un accès filesystem
```

La question principale est donc :

> **Comment autoriser une configuration riche sans transformer toute donnée persistée ou fournie par un utilisateur en code implicitement exécutable ?**

---

# 2. Principe central

La politique de sécurité repose sur :

> **Data is not code.**

Une configuration doit rester :

```text
déclarative

validée

bornée

résolue explicitement
```

et non :

```text
évaluée dynamiquement
```

---

# 3. Deux frontières principales

PyScheduleKit distingue :

```text
Control Plane

Workload Plane
```

---

# 4. Control Plane

Le Control Plane manipule :

```text
Schedules

Triggers

Policies

Configuration

Persistence

Coordination

Executors

Target resolution
```

---

# 5. Workload Plane

Le Workload Plane exécute :

```text
le travail demandé par l’utilisateur
```

Exemples :

```text
fonction Python

workflow

appel HTTP

commande distante via adapter
```

---

# 6. Règle

Le Control Plane doit être :

```text
plus strict
```

que le Workload Plane.

Une mauvaise configuration ne doit jamais devenir silencieusement :

```text
du code exécuté
```

---

# 7. Threat Model V1

Le modèle V1 considère notamment :

```text
configuration malformée

configuration hostile

TargetRef falsifié

module Python inattendu

pickle malveillant

secret persisté en clair

URL dangereuse

plugin arbitraire

path traversal

config override par environnement

ScheduleDefinition corrompue

event payload non fiable

mauvaise isolation multi-tenant
```

---

# 8. Hors modèle V1

PyScheduleKit n’a pas vocation à protéger contre :

```text
un administrateur OS root hostile

une base totalement compromise

un interpréteur Python compromis
```

---

# 9. Defense in Depth

La sécurité doit reposer sur plusieurs couches :

```text
Input Validation
       │
       ▼
Declarative Models
       │
       ▼
Allowlisted Resolution
       │
       ▼
Safe Serialization
       │
       ▼
Secret References
       │
       ▼
Runtime Authorization
       │
       ▼
Audit / Diagnostics
```

---

# 10. Configuration is not authority

Le simple fait qu’une configuration existe ne signifie pas :

```text
qu’elle est autorisée
```

---

# 11. Exemple

Un Schedule persisté contient :

```text
TargetRef.python("os:system")
```

Le Scheduler ne doit pas conclure automatiquement :

```text
"la base le contient donc j'exécute"
```

---

# 12. Resolution Policy

Il doit passer par :

```text
TargetResolutionPolicy
```

ou équivalent.

---

# 13. TargetRef

`TargetRef` reste une Value Object déclarative.

Exemple :

```text
kind = "python"

reference = "myapp.tasks:refresh"
```

---

# 14. TargetRef ne contient pas

```text
callable sérialisé

bytecode

pickle

lambda sérialisée

code source à evaluer
```

---

# 15. Règle majeure

> **TargetRef identifies executable capability; it does not carry executable code.**

---

# 16. Python Target Resolution

La résolution :

```text
myapp.tasks:refresh
```

doit suivre un mécanisme explicitement contrôlé.

---

# 17. Naive implementation interdite

Éviter :

```python
eval(reference)
```

---

# 18. Interdit également

```python
exec(source)
```

pour reconstruire un Target.

---

# 19. Import dynamique

Même :

```python
importlib.import_module(...)
```

doit être encadré.

---

# 20. Pourquoi ?

Un TargetRef pourrait sinon référencer :

```text
n'importe quel module importable du process
```

---

# 21. PythonTargetPolicy

Concept possible :

```text
PythonTargetPolicy
│
├── allowed_modules
├── denied_modules
├── allowed_prefixes
└── require_registered_targets
```

---

# 22. Modes de résolution

Trois stratégies possibles :

```text
REGISTERED_ONLY

ALLOWLISTED_IMPORT

UNRESTRICTED_IMPORT
```

---

# 23. REGISTERED_ONLY

Seuls les Targets enregistrés explicitement peuvent être utilisés.

Exemple :

```python
scheduler.register_target(
    "daily-report",
    build_daily_report,
)
```

---

# 24. Puis

```text
TargetRef.python("daily-report")
```

---

# 25. Avantage

Le contenu persistant ne peut pas choisir :

```text
un callable arbitraire
```

---

# 26. Recommandation V1

Pour les environnements persistants ou multi-utilisateurs :

```text
REGISTERED_ONLY
```

est le mode recommandé.

---

# 27. ALLOWLISTED_IMPORT

Exemple :

```text
allowed prefixes:

myapp.tasks
myapp.jobs
```

---

# 28. Référence autorisée

```text
myapp.tasks:refresh
```

---

# 29. Référence refusée

```text
subprocess:run
```

---

# 30. UNRESTRICTED_IMPORT

Peut être acceptable uniquement dans :

```text
local trusted developer mode
```

---

# 31. Default Security Principle

Le mode le moins sûr ne doit pas être :

```text
le default implicite
```

en production.

---

# 32. Callable targets

L’API V1 permet :

```python
scheduler.add_schedule(
    target=my_function,
    ...
)
```

---

# 33. Important

Un callable direct est :

```text
process-local
```

---

# 34. Il n’est pas nécessairement

```text
persistable

distribuable

rechargeable après restart
```

---

# 35. Security consideration

Un callable fourni directement par le code Python du processus est considéré comme :

```text
trusted application code
```

---

# 36. Mais

Il ne doit pas être automatiquement transformé en :

```text
module path persisté arbitraire
```

sans règle explicite.

---

# 37. V1 recommendation

Deux modes :

```text
Ephemeral Callable Target

Declarative Persistent TargetRef
```

---

# 38. Ephemeral Callable

Valable pour :

```text
InMemory Scheduler
```

---

# 39. Persistent mode

Doit exiger :

```text
registered or declarative TargetRef
```

---

# 40. Reject unsafe persistence

Exemple :

```text
SQLite persistence enabled
+
lambda target
```

→

```text
ConfigurationError
```

plutôt que tentative de sérialisation magique.

---

# 41. Pickle Policy

Règle V1 :

```text
PICKLE IS FORBIDDEN
```

pour toute donnée persistée ou reçue depuis une frontière externe.

---

# 42. Pourquoi ?

`pickle.loads()` peut :

```text
exécuter du code arbitraire
```

---

# 43. Interdictions

Ne pas utiliser pickle pour :

```text
ScheduleDefinition

Trigger

Policies

TargetRef

ExecutionContext

Events

Failures

Plugin configuration
```

---

# 44. Même trusted DB ?

Toujours éviter.

Une base aujourd’hui “trusted” peut demain devenir :

```text
import/export source

admin-edited

restored backup

shared environment
```

---

# 45. Serialization V1

Formats recommandés :

```text
JSON-compatible primitives
```

---

# 46. Types autorisés

```text
string

number

boolean

null

list

object/dict
```

---

# 47. Temporal values

Persistés sous forme explicite :

```text
ISO 8601

IANA timezone names

duration contract
```

---

# 48. No arbitrary object reconstruction

La désérialisation doit reconstruire uniquement :

```text
known explicit types
```

---

# 49. Type discriminator

Exemple :

```json
{
  "schema_version": 1,
  "kind": "cron",
  "expression": "0 6 * * *",
  "timezone": "Europe/Paris"
}
```

---

# 50. Codec Registry

Le `kind` est résolu par :

```text
TriggerCodecRegistry
```

---

# 51. Registry explicite

```text
cron → CronTriggerCodec

date → DateTriggerCodec

interval → IntervalTriggerCodec
```

---

# 52. Interdit

```text
kind = "my.module.MyTrigger"
→ import dynamically
```

---

# 53. Pourquoi ?

Le format de données deviendrait :

```text
un import statement déguisé
```

---

# 54. Safe Codec Principle

> **Serialized type identifiers map to pre-registered codecs, not arbitrary Python classes.**

---

# 55. Codec Registration

Doit se faire au :

```text
Composition Root
```

---

# 56. Pas via donnée persistée

La base ne doit pas pouvoir dire :

```text
load plugin X from path Y
```

---

# 57. Plugin Security

Les plugins sont du :

```text
code exécutable
```

---

# 58. Donc

Installer/enregistrer un plugin est une opération :

```text
administrative / deployment-time
```

pas une simple donnée Schedule.

---

# 59. Plugin registration future

```python
scheduler.register_executor(...)
scheduler.register_trigger_codec(...)
```

---

# 60. Source

Le code doit provenir :

```text
du processus/app package
```

ou d’un plugin installé volontairement.

---

# 61. No remote plugin loading

V1 ne doit pas :

```text
download code from URL
```

puis l'exécuter.

---

# 62. No plugin path from Schedule metadata

---

# 63. Target Kinds

Exemples :

```text
python

workflow

http
```

---

# 64. ExecutorRegistry

Un Target kind doit être enregistré explicitement.

---

# 65. Unknown kind

```text
TargetRef(kind="shell", ...)
```

sans adapter :

→

```text
UnsupportedTargetError
```

---

# 66. No fallback execution

Ne jamais dire :

```text
unknown kind → try shell
```

---

# 67. Shell Execution

Si un jour ajouté :

```text
shell
```

doit être :

```text
adapter optionnel explicitement activé
```

---

# 68. V1 recommendation

Pas de built-in arbitrary shell executor.

---

# 69. Pourquoi ?

Il transformerait tout TargetRef en :

```text
remote command execution primitive
```

---

# 70. HTTP Targets

Un HTTP Executor peut sembler plus sûr, mais introduit :

```text
SSRF
```

comme risque.

---

# 71. SSRF

Server-Side Request Forgery :

```text
user configures URL
→ scheduler calls internal/private service
```

---

# 72. Exemple dangereux

```text
http://169.254.169.254/
```

---

# 73. HTTP security recommendation

Ne pas persister une URL libre comme Target dans les environnements sensibles.

---

# 74. Better model

```text
HttpTargetRef
→ connection profile / endpoint alias
```

---

# 75. Example

```text
TargetRef.http("orders-api.refresh")
```

---

# 76. Registry

```text
orders-api.refresh
→ https://api.example.com/internal/refresh
```

configuré par l’application.

---

# 77. Advantage

Le Schedule ne choisit pas directement :

```text
host

scheme

port
```

---

# 78. Direct URL mode

Peut exister en local/developer mode.

---

# 79. Production policy

Support possible :

```text
allowed schemes

allowed hosts

allowed ports

deny private ranges
```

---

# 80. Redirects

HTTP Executor doit être prudent avec :

```text
redirects
```

car une URL autorisée peut rediriger vers :

```text
destination interdite
```

---

# 81. Recommendation

V1 HTTP adapter, s'il existe :

```text
direct URL support is opt-in
```

---

# 82. Credentials

Jamais dans :

```text
TargetRef
```

---

# 83. Mauvais

```text
https://user:password@example.com
```

---

# 84. Mauvais

```json
{
  "authorization": "Bearer secret-token"
}
```

dans ScheduleDefinition.

---

# 85. SecretRef

Préférer :

```text
SecretRef("orders-api-token")
```

---

# 86. SecretProvider

Port future :

```text
SecretProvider
```

résout :

```text
SecretRef
→ secret at execution time
```

---

# 87. Important

Les secrets doivent être résolus :

```text
le plus tard possible
```

---

# 88. Pourquoi ?

Limiter leur présence dans :

```text
persistence

logs

events

snapshots

diagnostics
```

---

# 89. Secret storage

PyScheduleKit ne doit pas devenir :

```text
secret manager
```

---

# 90. External secret systems

Possible adapters :

```text
environment variables

Vault

AWS Secrets Manager

Azure Key Vault

Kubernetes Secrets
```

plus tard.

---

# 91. Environment variables

Elles appartiennent à :

```text
configuration bootstrap
```

---

# 92. Domain rule

Le domaine n'appelle jamais :

```python
os.getenv(...)
```

---

# 93. Why?

Sinon :

```text
same object
+
same input
```

pourrait changer de comportement selon l’environnement.

---

# 94. Config Sources

Sources possibles :

```text
Defaults

Config File

Environment

Explicit Python Configuration
```

---

# 95. Precedence

Une politique explicite est nécessaire.

Recommandation :

```text
Explicit Python Arguments
        >
Environment Overrides
        >
Config File
        >
Framework Defaults
```

---

# 96. Important

La precedence doit être :

```text
stable

documented

testable
```

---

# 97. No hidden sources

Éviter :

```text
current working directory magic config

implicit ~/.pyschedule

host timezone
```

sans opt-in.

---

# 98. Configuration Object Families

Comme défini dans l’architecture :

```text
RuntimeConfig

PersistenceConfig

ExecutorConfig

ObservabilityConfig

SecurityConfig
```

---

# 99. Schedule configuration

Reste séparée :

```text
ScheduleDefinition
```

---

# 100. Why?

Une variable comme :

```text
database_pool_size
```

ne doit pas se retrouver dans :

```text
ScheduleDefinition
```

---

# 101. SecurityConfig

Possible :

```text
SecurityConfig
│
├── python_target_policy
├── allow_direct_http_urls
├── allowed_http_hosts
├── allow_custom_codecs
├── redact_sensitive_values
└── max_config_size
```

---

# 102. Keep defaults conservative

Exemple :

```text
allow_direct_http_urls = False
```

en production profile.

---

# 103. Profiles

Doit-on avoir :

```text
dev

production
```

profiles ?

---

# 104. Risk

Un profil magique peut cacher de nombreux changements.

---

# 105. Recommendation

Pas de profil implicite V1.

Utiliser :

```text
explicit config presets
```

si besoin.

---

# 106. Example

```python
SecurityConfig.local_development()
```

peut être clair.

---

# 107. Mais

Production config doit rester explicitement construite.

---

# 108. Configuration validation

Avant Runtime start :

```text
validate everything that can be validated
```

---

# 109. Startup validation examples

```text
database configuration valid

executor kinds available

codec registry complete

security policy coherent

default timezone valid
```

---

# 110. Fail before Runtime

Éviter de découvrir après 4 heures :

```text
workflow target adapter missing
```

si les persisted Schedules peuvent être vérifiés au démarrage.

---

# 111. Mais

Un Target ajouté après startup doit encore être validé au moment de :

```text
add_schedule()
```

---

# 112. Validation scopes

```text
Static Config Validation

Schedule Validation

Runtime Resolution Validation
```

---

# 113. Static

Exemple :

```text
invalid database URL
```

---

# 114. Schedule

Exemple :

```text
unsupported Target kind
```

---

# 115. Runtime

Exemple :

```text
registered external workflow deleted after schedule creation
```

---

# 116. Validation cannot eliminate all runtime failures

Correct.

---

# 117. Persisted configuration trust

Donnée issue de DB doit toujours être :

```text
revalidated during deserialization
```

---

# 118. Why?

DB record may be :

```text
corrupted

manually edited

written by older version

hostile
```

---

# 119. Do not trust because "we wrote it"

---

# 120. Rehydration rule

```text
deserialize
↓
validate schema
↓
validate version
↓
construct domain object
↓
enforce invariants
```

---

# 121. Invalid persisted config

Produces :

```text
PersistenceSerializationError
```

ou :

```text
PersistenceCorruptionError
```

---

# 122. Fail closed

Ne pas exécuter le Schedule concerné.

---

# 123. Schema Versions

Tous les formats durables importants doivent avoir :

```text
schema_version
```

---

# 124. Unsupported future schema

```text
runtime supports v1
DB record is v3
```

→ refuse.

---

# 125. No downgrade guess

---

# 126. Older schema

May be :

```text
migrated
```

through known codecs.

---

# 127. Configuration migration must be code-controlled

Pas :

```text
eval arbitrary migration expression
```

---

# 128. JSON size limits

Une configuration peut elle-même devenir DoS.

Exemple :

```text
500 MB metadata payload
```

---

# 129. Therefore

Set reasonable limits for :

```text
metadata

ExecutionContext

event payloads

serialized policy configs
```

---

# 130. `metadata`

Doit rester :

```text
small
```

---

# 131. V1

Configurer une limite globale raisonnable côté adapter/API.

Exact threshold :

```text
deployment-specific
```

---

# 132. Depth limits

JSON très profondément imbriqué peut être problématique.

---

# 133. Recommendation

Configuration structures should be :

```text
shallow and schema-defined
```

---

# 134. Unknown fields

Que faire ?

---

# 135. Persisted configuration

Recommendation :

```text
reject unknown fields
```

pour le core V1.

---

# 136. Why?

Un typo :

```text
max_attemps
```

ne doit pas être silencieusement ignoré.

---

# 137. Forward compatibility

Handled through :

```text
schema versions
```

pas en acceptant tout.

---

# 138. Public Python kwargs

Python signature already rejects unknown kwargs.

---

# 139. Good.

---

# 140. Metadata exception

`metadata` can remain user-defined JSON-like mapping.

---

# 141. But metadata must not influence security-sensitive behavior

---

# 142. Never do

```text
metadata["executor"] = "shell"
```

and route execution based on it.

---

# 143. Semantic config must live in typed fields.

---

# 144. Filesystem Security

If future adapters access files:

```text
path traversal
```

must be considered.

---

# 145. Example dangerous path

```text
../../etc/passwd
```

---

# 146. Core scheduling V1

Should not expose arbitrary filesystem execution targets.

---

# 147. If future FileTarget exists

Must use:

```text
configured roots

canonicalized paths

path boundary checks
```

---

# 148. Current recommendation

Keep filesystem outside core TargetRef kinds.

---

# 149. Command/Shell Target

Also out of V1.

---

# 150. If later added

Use :

```text
pre-registered commands
```

rather than free shell strings.

---

# 151. Good

```text
TargetRef.command("refresh-search-index")
```

with registry :

```text
refresh-search-index
→ fixed executable + fixed argv template
```

---

# 152. Bad

```text
TargetRef.command("rm -rf ...")
```

as raw string.

---

# 153. Python import allowlist

If `ALLOWLISTED_IMPORT` exists :

```text
mycompany.jobs
```

must mean prefix-boundary aware.

---

# 154. Bad prefix check

```python
module.startswith("mycompany.jobs")
```

would also allow:

```text
mycompany.jobs_evil
```

---

# 155. Need segment-aware matching

```text
module == prefix
or
module.startswith(prefix + ".")
```

---

# 156. Denylist

A denylist alone is insufficient.

---

# 157. Prefer allowlist

Because impossible to enumerate every dangerous module.

---

# 158. Builtin callables

Should not be resolvable by default.

Examples :

```text
builtins:eval

builtins:exec
```

---

# 159. Subprocess

Not allowlisted by default.

---

# 160. Dynamic attributes

Avoid resolving chains like :

```text
module:object.attr.method
```

unless explicitly supported and validated.

---

# 161. V1 Python ref syntax

Prefer exactly :

```text
module.path:function_name
```

---

# 162. Why?

Simple parser.

Small attack surface.

Predictable resolution.

---

# 163. Function visibility

Could require :

```text
module-level callable
```

---

# 164. No class construction from TargetRef V1

Avoid :

```text
module:Class(...)
```

---

# 165. No argument expressions

TargetRef is not :

```text
Python expression
```

---

# 166. Target arguments

Where stored?

Potential :

```text
ExecutionContext
```

or Schedule input config.

---

# 167. Security concern

Arguments may contain :

```text
secrets

PII

large payloads
```

---

# 168. Recommendation

Persistent target arguments :

```text
small declarative JSON-like values
```

---

# 169. Large inputs

Use references :

```text
ArtifactRef

DatasetRef

ObjectRef
```

---

# 170. Secrets

Use `SecretRef`.

---

# 171. Do not persist arbitrary Python objects as args.

---

# 172. Argument schema

Executors may provide :

```text
TargetSchema
```

future.

---

# 173. V1

Basic JSON-like validation sufficient.

---

# 174. ExecutionContext

Must not become :

```text
bag of everything
```

---

# 175. Recommended contents

```text
CorrelationId

TraceId

IdempotencyKey

safe metadata
```

---

# 176. Security principle

Do not put credentials inside ExecutionContext unless reference-only.

---

# 177. Observability Redaction

Security policy and observability must align.

---

# 178. Secret values

Must be filtered from :

```text
logs

audit

events

diagnostics

repr()
```

---

# 179. Redaction by key

Useful but insufficient alone.

---

# 180. Why?

A secret can be under innocuous key :

```text
"value"
```

---

# 181. Better

Use typed SecretRef/SecretValue wrappers where possible.

---

# 182. SecretValue

If raw secret must temporarily exist :

```text
SecretValue
```

could override :

```text
repr
str
```

to redact.

---

# 183. But Python memory remains readable by process

No illusion of secure enclave.

---

# 184. Primary goal

Prevent accidental disclosure.

---

# 185. Logging exception causes

Vendor exceptions may contain secrets.

---

# 186. Adapter must sanitize before :

```text
public message
```

---

# 187. Full traceback

Can still contain sensitive local state.

Use restricted logging sinks.

---

# 188. Public Error.details

Must be :

```text
secret-safe
```

---

# 189. Configuration File Security

Potential future formats :

```text
JSON

TOML

YAML
```

---

# 190. YAML caution

If YAML is supported :

```text
safe_load only
```

---

# 191. Never

```text
yaml.load with arbitrary constructors
```

---

# 192. V1 recommendation

Core does not need YAML.

---

# 193. TOML/JSON safer default

They do not encode arbitrary object constructors.

---

# 194. Configuration file path

Explicitly provided.

Avoid automatically searching arbitrary parent directories unless documented.

---

# 195. File permissions

Deployment concern, but docs should recommend restricted permissions for files containing :

```text
database URLs

secret references
```

---

# 196. Environment Configuration

Environment variables may contain secrets.

---

# 197. Never dump complete environment

in diagnostics.

---

# 198. Config inspection

If `scheduler.inspect_config()` exists later :

```text
secrets redacted
```

---

# 199. Config source tracing

Useful to know :

```text
poll_interval came from ENV
```

---

# 200. But avoid displaying raw secret values.

---

# 201. Configuration Provenance

Future VO :

```text
ConfigSource
```

possible values :

```text
DEFAULT

FILE

ENV

EXPLICIT
```

---

# 202. Useful for diagnostics

Not domain state.

---

# 203. Configuration mutability

V1 runtime config should be :

```text
immutable after Scheduler start
```

---

# 204. Why?

Dynamic mutation of :

```text
DB adapter

security policy

target registry
```

while running creates race/security complexity.

---

# 205. Schedule configuration

Can change through explicit :

```text
reschedule
```

---

# 206. Runtime configuration

Requires restart V1.

---

# 207. Registry configuration

Requires restart V1.

---

# 208. Security configuration

Requires restart V1.

---

# 209. This makes reasoning simpler.

---

# 210. Hot Reload

Deferred.

---

# 211. If future hot reload

Must be explicit and audited.

---

# 212. External config changes

Do not silently mutate ScheduleDefinitions.

---

# 213. Default Timezone Security?

Timezone itself isn't secret, but implicit host timezone causes non-determinism.

---

# 214. Therefore

Default :

```text
UTC
```

---

# 215. Effective timezone persists into ScheduleDefinition.

---

# 216. Locale

Cron semantics must not depend on :

```text
process locale
```

---

# 217. Month/day names

If textual Cron fields supported later, use explicit language/standard rules.

---

# 218. V1 numeric Cron preferred.

---

# 219. Regex / parser DoS

Cron/config parsers should avoid catastrophic backtracking.

---

# 220. Inputs must be bounded in length.

---

# 221. Cron expression length

Apply reasonable maximum.

---

# 222. Trigger computational DoS

A malicious Trigger config might force :

```text
huge search
```

---

# 223. Search Horizon

Already defined.

Security use :

```text
bounded evaluation
```

---

# 224. Max iterations

Protect scheduler from pathological expressions.

---

# 225. Catch-Up DoS

Scheduler down for months + high-frequency Schedule could generate :

```text
millions of missed occurrences
```

---

# 226. Therefore

Catch-Up must have :

```text
max_occurrences

search horizon

batch limits
```

---

# 227. Security and resilience intersect here.

---

# 228. Retry DoS

Unbounded retry is forbidden V1.

---

# 229. Why?

Could cause :

```text
infinite resource consumption
```

---

# 230. `max_attempts`

Must be finite.

---

# 231. Minimum :

```text
>= 1
```

---

# 232. Maximum

Deployment may impose cap.

---

# 233. Concurrency Safety

User config should not be able to request :

```text
max_instances = unlimited
```

without explicit support.

---

# 234. V1

Integer finite positive limit.

---

# 235. `ConcurrencyPolicy.allow()`

If kept, it means framework imposes no domain limit.

But Executor capacity remains independent.

---

# 236. Production deployments may restrict this policy.

---

# 237. Policy Authorization

A future multi-user API may need :

```text
some users cannot create unlimited concurrency schedules
```

---

# 238. This is authorization, not validation.

---

# 239. Important distinction

```text
Valid
≠
Authorized
```

---

# 240. Example

```text
CronTrigger every minute
```

is valid.

But tenant policy may forbid:

```text
more than one run per hour
```

---

# 241. Authorization Port future

Potential :

```text
ScheduleAuthorizationPolicy
```

---

# 242. V1 embedded library

Does not require user identity/ACL model.

---

# 243. But

Architecture must leave authorization to :

```text
host application
```

rather than pretending all callers equal in future server mode.

---

# 244. Multi-tenancy

Not V1 core, but security implications must be documented.

---

# 245. If TenantId is introduced later

It must scope :

```text
Schedule queries

Execution queries

Concurrency keys

audit queries

Target registries

secret references
```

---

# 246. Tenant leak

A tenant must never be able to reference another tenant’s :

```text
ScheduleId

ExecutionId

SecretRef

Target registration
```

---

# 247. Resource keys

Distributed coordination should include tenant namespace where appropriate.

Example :

```text
tenant:T1:concurrency:refresh
```

---

# 248. Global concurrency

Must be explicitly marked global.

---

# 249. ID enumeration

If server mode exposes IDs externally :

```text
UUID-like identifiers
```

reduce trivial guessing, but are not authorization.

---

# 250. Never rely on unguessable ID as access control.

---

# 251. Persistence Security

Database role used by Scheduler should follow :

```text
least privilege
```

---

# 252. Example

Scheduler process likely needs :

```text
SELECT

INSERT

UPDATE
```

on its own tables.

---

# 253. It may not need :

```text
CREATE DATABASE

superuser
```

---

# 254. Migration user

Could be separate from runtime DB user.

---

# 255. Good production pattern

```text
migration credentials
≠
runtime credentials
```

---

# 256. SQL Injection

Repositories must use :

```text
parameterized queries / ORM bindings
```

---

# 257. Never concatenate :

```text
ScheduleId
```

into raw SQL.

---

# 258. Dynamic ordering fields

Must use allowlisted column mapping.

---

# 259. Serialization injection

JSON values are data.

Never transform them into code snippets.

---

# 260. Event Security

Events may cross trust boundaries.

---

# 261. Published Integration Events

Need :

```text
safe schema

minimal payload

no secrets
```

---

# 262. Consumers should treat event payloads as untrusted input.

---

# 263. EventId duplication

Deduplication protects correctness but not authorization.

---

# 264. Message authenticity

If external brokers cross security boundaries, authentication/TLS belong to adapter/deployment.

---

# 265. Core V1

Does not implement cryptographic event signatures.

---

# 266. But events should support immutable identifiers for future verification.

---

# 267. Audit Security

Audit records may reveal :

```text
Schedule names

target names

user IDs

failure info
```

---

# 268. Access to audit should be restricted by host application.

---

# 269. Audit is not automatically public.

---

# 270. Redaction applies to audit too.

---

# 271. Logs

Do not log full :

```text
ScheduleDefinition
```

at INFO by default.

---

# 272. Why?

It may contain :

```text
business metadata

endpoint refs
```

---

# 273. Log identifiers and summaries.

---

# 274. Debug mode

Can expose more, but still not raw secrets.

---

# 275. `repr()`

Public objects should avoid leaking sensitive configuration.

---

# 276. TargetRef repr

Safe if it contains no secrets by contract.

---

# 277. SecretRef repr

Can show :

```text
SecretRef("orders-api-token")
```

because alias itself may be acceptable.

---

# 278. But even secret alias can be sensitive in some deployments.

---

# 279. Configurable redaction possible later.

---

# 280. Default error behavior

Security failures should :

```text
fail closed
```

---

# 281. Examples

Target not authorized :

```text
do not execute
```

---

# 282. Unknown codec :

```text
do not deserialize using generic import
```

---

# 283. Unknown plugin :

```text
do not auto-install
```

---

# 284. Invalid secret reference :

```text
do not fallback to plaintext credential
```

---

# 285. HTTP host denied :

```text
do not call anyway
```

---

# 286. Fail closed does not mean crash everything

A single unsafe Schedule should usually be isolated.

---

# 287. Scope

```text
Schedule-specific security issue
→ block Schedule operation

global security configuration invalid
→ fail Scheduler startup
```

---

# 288. Security Error Types

Potential V1 errors :

```text
UnsafeTargetError

TargetNotAllowedError

UnsafeSerializationError

SecretResolutionError
```

---

# 289. Do we need new hierarchy?

Could add :

```text
SecurityError
```

under `PyScheduleKitError`.

---

# 290. Recommendation

Yes.

---

# 291. Updated public hierarchy concept

```text
PyScheduleKitError
│
├── ValidationError
├── ConfigurationError
├── SecurityError
├── DomainError
├── NotFoundError
├── ConflictError
├── PersistenceError
├── CoordinationError
├── ExecutorError
└── SchedulerRuntimeError
```

---

# 292. SecurityError subclasses

Potential :

```text
TargetNotAllowedError

UnsafeConfigurationError

SecretResolutionError
```

---

# 293. Keep small V1

Probably :

```text
SecurityPolicyError

TargetNotAllowedError
```

suffisent.

---

# 294. Secret missing

Could remain :

```text
ConfigurationError
```

rather than separate class initially.

---

# 295. Security event logging

Rejected target should emit :

```text
structured warning/security diagnostic
```

---

# 296. Do not log secret payload.

---

# 297. Security audit

Manual changes to :

```text
TargetRef

security-sensitive executor config
```

may deserve durable audit.

---

# 298. Host Application Responsibilities

PyScheduleKit embedded library cannot enforce everything.

Host application owns :

```text
authentication

user authorization

network policies

container isolation

OS permissions

TLS

database credential management
```

---

# 299. PyScheduleKit owns

```text
safe internal defaults

safe serialization

explicit target resolution

secret minimization

config validation

safe extension points
```

---

# 300. Executor Isolation

A Python callable executes :

```text
inside scheduler/worker process
```

unless isolated runtime is used.

---

# 301. Consequence

A hostile callable can :

```text
read process memory

read files

make network calls

exit process
```

---

# 302. Therefore

PyScheduleKit cannot sandbox arbitrary Python callables in-process.

---

# 303. Explicit documentation

> **Python Target execution is trusted-code execution.**

---

# 304. Need untrusted code?

Use :

```text
external isolated worker / sandbox
```

outside core V1.

---

# 305. ProcessExecutor

A separate process improves fault isolation.

---

# 306. But not a security sandbox by itself.

---

# 307. Containers

Can provide stronger isolation if configured appropriately.

Infrastructure concern.

---

# 308. Workflow Executor

PyWorkflowKit integration should receive :

```text
TargetRef.workflow(workflow_name)
```

---

# 309. PyScheduleKit does not inject :

```text
arbitrary workflow code
```

---

# 310. Workflow system owns its own authorization.

---

# 311. ExecutionContext propagation

Only safe fields should cross framework boundaries.

---

# 312. Example allowed

```text
CorrelationId

TraceId

IdempotencyKey
```

---

# 313. Avoid forwarding every Schedule metadata field automatically.

---

# 314. Explicit context mapping

Executor adapter chooses what to send.

---

# 315. Principle of Least Data

> **Send downstream only what the target needs.**

---

# 316. Configuration object immutability

Recommended :

```text
frozen dataclasses
```

for:

```text
SecurityConfig

RuntimeConfig

ExecutorConfig
```

where practical.

---

# 317. Why?

Prevent unnoticed mutation after validation.

---

# 318. Copy-on-build

Composition Root validates then freezes config.

---

# 319. Configuration Validation Result

Errors must be :

```text
structured
```

---

# 320. Example

```text
TARGET_KIND_NOT_REGISTERED

UNSAFE_PYTHON_TARGET_POLICY

INVALID_HTTP_HOST_ALLOWLIST
```

---

# 321. Unknown env vars

Framework should ignore variables outside documented namespace.

---

# 322. Prefix

Future convention :

```text
PYSCHEDULEKIT_
```

---

# 323. Example

```text
PYSCHEDULEKIT_DEFAULT_TIMEZONE
```

---

# 324. But secrets

Prefer external config mechanisms/SecretRefs.

---

# 325. Env var string parsing

Strict.

Example :

```text
PYSCHEDULEKIT_POLL_INTERVAL=banana
```

must fail startup.

---

# 326. Boolean parsing

Avoid accepting arbitrary truthy strings.

Use documented :

```text
true / false
```

---

# 327. Numeric bounds

Always validate.

---

# 328. Config merging

Nested structures should merge deliberately.

---

# 329. Avoid surprising deep merge semantics V1.

---

# 330. Better

Explicit config object replacement.

---

# 331. Config Export

If future :

```python
scheduler.config_snapshot()
```

must redact :

```text
secret-bearing values
```

---

# 332. Security configuration itself may reveal policy

Usually safe, but could aid attackers.

Host decides exposure.

---

# 333. Supply Chain

Third-party executor plugins run code.

---

# 334. PyScheduleKit cannot guarantee plugin safety.

---

# 335. Recommendation

Plugins are trusted dependencies.

---

# 336. Version pinning

Deployment should pin plugin versions.

---

# 337. Plugin compatibility

Plugin metadata may declare :

```text
supported PyScheduleKit versions
```

future.

---

# 338. No runtime pip install

V1 explicitly forbids:

```text
pip install from Schedule configuration
```

---

# 339. No code fetching

No :

```text
git clone plugin URL
```

from Schedule.

---

# 340. No user-controlled `sys.path`

---

# 341. Codec Security

Codec decoders must :

```text
validate before construction
```

---

# 342. Do not call constructors with unrestricted `**payload`

unless payload schema is controlled.

---

# 343. Example safe flow

```text
payload
→ schema parser
→ validated primitive fields
→ explicit constructor
```

---

# 344. Bad

```python
CronTrigger(**payload)
```

on arbitrary unknown JSON without field filtering.

---

# 345. Object Injection

Avoid generic object factories:

```text
{
  "class": "...",
  "args": [...]
}
```

---

# 346. This is effectively unsafe deserialization.

---

# 347. Persistence record tampering

If DB may be modified outside application :

```text
audit / integrity controls
```

can help.

---

# 348. Cryptographic signatures

Not V1.

---

# 349. But schedule revision/history aids detection.

---

# 350. UpdatedAt/Actor metadata

Useful for investigation.

---

# 351. Migration Security

Database migrations should not execute arbitrary data-driven code.

---

# 352. Migration scripts are deployment-trusted code.

---

# 353. Runtime process should not auto-run unknown migrations from DB.

---

# 354. Startup

If DB schema incompatible :

```text
RuntimeStartError
```

---

# 355. No auto destructive migrations.

---

# 356. Destructive configuration migration

Should require explicit deployment process.

---

# 357. Backup Import

Imported Schedule definitions must be treated as :

```text
untrusted configuration
```

---

# 358. Revalidate all TargetRefs and policies.

---

# 359. Never trust export origin blindly.

---

# 360. Duplicate IDs

Import must handle conflict explicitly.

---

# 361. No overwrite by default.

---

# 362. Secure Defaults Matrix

| Concern | V1 Default |
|---|---|
| Serialization | JSON-like declarative only |
| Pickle | Forbidden |
| Dynamic `eval`/`exec` | Forbidden |
| Python target persistence | Registered/allowlisted |
| Arbitrary shell execution | Not built-in |
| Direct HTTP URLs | Opt-in / restricted |
| Secrets in ScheduleDefinition | Forbidden |
| Secret resolution | Via references/adapters |
| Unknown config fields | Rejected |
| Unknown codec kind | Rejected |
| Unknown target kind | Rejected |
| Runtime config hot reload | Disabled |
| Retry | None by default |
| Timezone | UTC |
| Unsafe unknown failure retry | Disabled |
| Plugin remote loading | Forbidden |

---

# 363. Security Invariants

```text
1.
Persisted data never selects an arbitrary Python class.

2.
Persisted TargetRef never carries executable code.

3.
Pickle is not used for persisted scheduler data.

4.
eval() and exec() are not used for configuration resolution.

5.
Unknown target kinds are rejected.

6.
Unknown codec kinds are rejected.

7.
Python imports are registered or allowlisted
for persistent environments.

8.
Raw secrets are not stored in ScheduleDefinition.

9.
Raw secrets are not intentionally emitted
to logs, audit, metrics or diagnostics.

10.
Runtime configuration is validated before start.

11.
Persisted configuration is revalidated on load.

12.
Unsupported schema versions fail closed.

13.
Configuration does not implicitly alter
authorization boundaries.

14.
Metadata cannot select an Executor or security policy.

15.
Custom plugins are trusted deployment-time code.

16.
Plugins cannot be installed from Schedule data.

17.
HTTP execution cannot silently bypass configured
network restrictions.

18.
Catch-up, retry and trigger evaluation are bounded.

19.
Untrusted code is not considered safely sandboxed
inside the PyScheduleKit process.

20.
Security-sensitive configuration changes are explicit.
```

---

# 364. Configuration Invariants

```text
1.
Explicit configuration precedence is deterministic.

2.
Schedule configuration and Runtime configuration
remain separate.

3.
Environment variables are read only at configuration
boundaries.

4.
Domain objects never query environment variables.

5.
Effective Schedule timezone is persisted.

6.
Runtime/Security config is immutable while running
in V1.

7.
Schedule definition changes use reschedule semantics
and increment ScheduleRevision.

8.
Unknown configuration fields are rejected.

9.
Configuration values have explicit bounds.

10.
Configuration serialization is versioned.
```

---

# 365. Example — Safe local mode

```python
scheduler = Scheduler()

scheduler.add_schedule(
    target=local_function,
    trigger=IntervalTrigger(minutes=10),
)
```

Assumption :

```text
application code is trusted
```

Persistence :

```text
InMemory
```

---

# 366. Example — Persistent safe mode

```python
scheduler = Scheduler.create(
    persistence=postgres,
    executor=executor_router,
    security=SecurityConfig(
        python_targets=PythonTargetPolicy.registered_only(),
    ),
)

scheduler.register_target(
    "refresh-customers",
    refresh_customers,
)

scheduler.add_schedule(
    target=TargetRef.python("refresh-customers"),
    trigger=CronTrigger(
        "0 6 * * *",
        timezone="Europe/Paris",
    ),
)
```

---

# 367. Persisted value

Only :

```text
python:refresh-customers
```

---

# 368. On restart

Application re-registers :

```text
refresh-customers
```

---

# 369. If registration missing

Schedule execution fails closed with :

```text
TargetResolutionError
```

---

# 370. Example — Allowlisted import

```python
PythonTargetPolicy.allow_modules(
    "myapp.jobs",
    "myapp.tasks",
)
```

---

# 371. Allowed

```text
myapp.jobs:refresh
```

---

# 372. Denied

```text
subprocess:run
```

---

# 373. Example — SecretRef

```python
TargetRef.http("orders.refresh")
```

Executor configuration :

```text
endpoint = orders API

credential = SecretRef("orders-api-token")
```

---

# 374. Schedule DB

Contains :

```text
orders.refresh
```

not :

```text
actual bearer token
```

---

# 375. Example — Unsafe config rejection

Serialized trigger :

```json
{
  "kind": "python_class",
  "class": "evil.module:Trigger"
}
```

Result :

```text
PersistenceSerializationError
```

---

# 376. No dynamic fallback.

---

# 377. Example — Malicious metadata

```json
{
  "metadata": {
    "executor": "shell",
    "command": "..."
  }
}
```

Result :

```text
treated as inert metadata
```

---

# 378. It cannot alter execution routing.

---

# 379. Example — Unknown field

```json
{
  "kind": "cron",
  "expression": "0 6 * * *",
  "eval": "..."
}
```

Strict codec :

```text
rejects unknown field
```

---

# 380. Good.

---

# 381. Security diagnostics

Potential codes :

```text
TARGET_NOT_ALLOWED

UNKNOWN_TARGET_KIND

UNSAFE_SERIALIZATION_FORMAT

SECRET_REFERENCE_UNRESOLVED

HTTP_TARGET_DENIED

CONFIG_SCHEMA_UNSUPPORTED
```

---

# 382. Security metrics

Low-cardinality only :

```text
security_rejections_total{
  reason="target_not_allowed"
}
```

---

# 383. Do not label with

```text
full target ref
```

if unbounded/sensitive.

---

# 384. Audit

A rejection may record :

```text
Target kind

safe reference identifier

reason code

actor/correlation
```

---

# 385. No secret values.

---

# 386. Security vs Usability

Strict security can make local experimentation harder.

---

# 387. Therefore

PyScheduleKit should support :

```text
explicit trusted local mode
```

---

# 388. But naming must make trust obvious.

Good :

```text
PythonTargetPolicy.trusted_local_imports()
```

---

# 389. Bad

```text
unsafe=False
```

with confusing polarity.

---

# 390. Prefer positive semantic configuration.

---

# 391. Production Documentation

Should clearly mark which features are intended only for :

```text
trusted local applications
```

---

# 392. Security review gates

Before supporting a new Target kind, ask :

```text
What can it access?

What data controls it?

Can config select arbitrary resources?

Where are credentials stored?

Can it cross network boundaries?

Can it execute code?

How is it audited?
```

---

# 393. New Trigger review

Ask :

```text
Can it perform I/O?

Can it loop forever?

Can persisted data load code?

Is evaluation bounded?
```

---

# 394. Rule

A Trigger should not perform :

```text
network I/O

filesystem I/O

arbitrary imports
```

during `next_after()`.

---

# 395. CalendarProvider exception

External calendars may require I/O.

But that's a separate Port.

---

# 396. Excellent separation

Trigger remains pure.

---

# 397. New Executor review

Ask :

```text
How are failures normalized?

How are secrets resolved?

Can TargetRef cause SSRF/RCE?

Does it support idempotency?

How does cancellation work?
```

---

# 398. New Persistence Adapter review

Ask :

```text
Are queries parameterized?

Does it preserve uniqueness?

Does it leak connection strings?

Does it deserialize safely?
```

---

# 399. New Plugin review

Ask :

```text
How is it installed?

How is it registered?

Can persisted data select implementation classes?
```

---

# 400. Security test matrix V1

Tests should include :

```text
pickle payload rejected

unknown codec rejected

unknown target kind rejected

non-allowlisted Python module rejected

registered Python target accepted

lambda rejected in persistent mode

secret absent from serialized Schedule

secret absent from repr/log/error

unknown JSON field rejected

unsupported schema version rejected

invalid HTTP host rejected

Target metadata cannot override executor

oversized config rejected

catch-up bounded

retry bounded

runtime config immutable after start
```

---

# 401. Test import boundary

Persist :

```text
subprocess:run
```

Expected :

```text
TargetNotAllowedError
```

under allowlist policy.

---

# 402. Test `builtins:eval`

Rejected.

---

# 403. Test arbitrary class codec

Rejected.

---

# 404. Test bad SecretRef

Fails safely before side effect.

---

# 405. Test DB corrupted config

No Target execution occurs.

---

# 406. Test logs

Search output for known test secret.

Expected :

```text
0 occurrences
```

---

# 407. Test error chain

Vendor error cause preserved internally without secret leakage.

---

# 408. Test HTTP redirect

If host policy used, redirects must be revalidated or disabled.

---

# 409. Test metadata inertness

Changing metadata cannot change :

```text
TargetRef

Executor kind

SecurityConfig
```

---

# 410. Test immutable config

Changing original config dict after Scheduler creation must not alter effective config unexpectedly.

---

# 411. Test config precedence

```text
explicit
>
env
>
file
>
default
```

exactly as documented.

---

# 412. Test malformed env

Startup fails.

---

# 413. Test hidden host timezone

With no timezone specified, effective timezone remains :

```text
UTC
```

regardless of host.

---

# 414. Test cron parser bounds

Pathological expression cannot lock Runtime indefinitely.

---

# 415. Test catch-up flood

Millions of theoretical occurrences are constrained by :

```text
CatchUpPolicy.max_occurrences
```

and planning bounds.

---

# 416. Security Acceptance Criteria

Le modèle est suffisamment défini si l’on peut répondre précisément à :

```text
Une ScheduleDefinition peut-elle contenir du code ?

Peut-on utiliser pickle ?

Comment un Target Python est-il résolu ?

Un Schedule peut-il importer n’importe quel module ?

Quelle différence entre callable local
et TargetRef persistant ?

Comment enregistrer un Target de façon sûre ?

Une configuration persistée peut-elle choisir un plugin ?

Comment sont résolus les secrets ?

Les secrets sont-ils persistés dans ScheduleDefinition ?

Comment empêcher un HTTP Target d’appeler n’importe quelle URL ?

Comment réagit le système à un codec inconnu ?

Comment réagit-il à un schema_version inconnu ?

Les données de DB sont-elles revalidées ?

Comment éviter qu’un metadata field change l’Executor ?

Quelles configurations sont immuables après start ?

Quel est l’ordre de priorité des sources de configuration ?

Quelles opérations sont bornées contre les boucles
ou volumes excessifs ?

PyScheduleKit peut-il sandboxer un callable Python hostile ?

Quelle responsabilité reste au host application ?
```

---

# 417. Configuration Architecture

```text
                  Configuration Sources
                          │
          ┌───────────────┼──────────────┐
          │               │              │
       Defaults         File           Env
          │               │              │
          └───────────────┼──────────────┘
                          │
                    Explicit Python
                          │
                          ▼
                  Configuration Loader
                          │
                          ▼
                      Validation
                          │
                          ▼
                     Frozen Config
                          │
                          ▼
                    Composition Root
```

---

# 418. Target Resolution Architecture

```text
                   TargetRef
                      │
                      ▼
              Security Policy
                      │
             ┌────────┴────────┐
             │                 │
          ALLOWED            DENIED
             │                 │
             ▼                 ▼
       ExecutorRouter      SecurityError
             │
             ▼
       Registered Executor
             │
             ▼
            Target
```

---

# 419. Serialization Architecture

```text
Persisted JSON
     │
     ▼
Schema Version Check
     │
     ▼
Known Kind Registry
     │
     ▼
Strict Codec Validation
     │
     ▼
Domain Value Object
```

Never :

```text
JSON
 ↓
class path
 ↓
dynamic import
 ↓
arbitrary constructor
```

---

# 420. Secret Architecture

```text
ScheduleDefinition
      │
      ▼
   SecretRef
      │
      ▼
Execution Boundary
      │
      ▼
 SecretProvider
      │
      ▼
   SecretValue
      │
      ▼
Target Adapter
```

---

# 421. Main Trust Boundaries

```text
User/Application Input
        │
        ▼
Public API Validation
        │
        ▼
Domain Configuration
        │
        ▼
Persistence
        │
        ▼
Revalidation
        │
        ▼
Target Resolution
        │
        ▼
Executor Boundary
        │
        ▼
External System
```

Chaque frontière :

```text
validates

normalizes

minimizes trust
```

---

# 422. Recommended V1 Security Decisions

```text
1.
No pickle.

2.
No eval.

3.
No exec.

4.
No arbitrary class-path deserialization.

5.
Persistent TargetRefs are declarative.

6.
Python persistent Targets use registered
or allowlisted resolution.

7.
Direct callables are local/trusted-mode only.

8.
No built-in arbitrary shell Target V1.

9.
HTTP direct URLs are restricted/opt-in.

10.
Credentials are referenced, not persisted
inside ScheduleDefinition.

11.
Unknown target kinds fail closed.

12.
Unknown codecs fail closed.

13.
Unknown config fields are rejected.

14.
Serialized schemas are versioned.

15.
Persisted records are revalidated on load.

16.
Runtime/Security config is immutable after start.

17.
Environment access occurs only at bootstrap.

18.
UTC is the deterministic default timezone.

19.
Catch-up, retry and trigger searches are bounded.

20.
Plugins are trusted deployment-time code,
not Schedule-controlled code.

21.
Metadata cannot influence executable routing.

22.
Security-sensitive failures use structured errors
and diagnostics.

23.
Observability redacts secret-bearing values.

24.
Untrusted Python callables are not considered sandboxed.

25.
Host application remains responsible for authentication,
authorization and infrastructure isolation.
```

---

# 423. Security Non-Goals V1

PyScheduleKit does not attempt to provide :

```text
Python code sandboxing

container security

OS privilege separation

TLS certificate management

secret vault implementation

user authentication

full RBAC

network firewalling

malware scanning

plugin signature verification
```

---

# 424. It provides safe seams for them

Through :

```text
Target registries

SecretProvider

Adapters

Host authorization

Runtime isolation
```

---

# 425. Modèle mental final

```text
                   UNTRUSTED / CONFIG DATA
                            │
                            ▼
                       VALIDATION
                            │
                            ▼
                   DECLARATIVE MODEL
                            │
                            ▼
                    SECURITY POLICY
                            │
                            ▼
                  EXPLICIT RESOLUTION
                            │
                            ▼
                      EXECUTOR
                            │
                            ▼
                       WORKLOAD
```

---

# 426. Principe clé

> **Une valeur configurée n’obtient jamais implicitement le droit de devenir du code.**

---

# 427. Deuxième principe

> **Une donnée persistée est revalidée comme si elle pouvait avoir été modifiée depuis son écriture.**

---

# 428. Troisième principe

> **Les secrets sont référencés dans le Control Plane et résolus uniquement à la frontière où ils deviennent réellement nécessaires.**

---

# 429. Quatrième principe

> **Les fonctionnalités qui augmentent fortement le pouvoir d’exécution — imports dynamiques, URLs libres, commandes shell, plugins — sont opt-in, bornées ou exclues de la V1.**

---

# Conclusion

PyScheduleKit doit être capable de transformer :

```text
une intention temporelle
```

en :

```text
une exécution contrôlée
```

sans faire de la configuration un canal caché d’exécution arbitraire.

La chaîne sûre devient :

```text
Input
  │
  ▼
Validation
  │
  ▼
ScheduleDefinition
  │
  ▼
Safe Serialization
  │
  ▼
Persistence
  │
  ▼
Revalidation
  │
  ▼
TargetRef
  │
  ▼
Security Policy
  │
  ▼
Registered Executor
  │
  ▼
Target
```

et non :

```text
Persisted String
      │
      ▼
eval / import arbitrary code
      │
      ▼
Execution
```

La philosophie générale est donc :

```text
explicit over magical

allowlist over denylist

references over secrets

schemas over arbitrary objects

bounded computation over unbounded behavior

fail closed over unsafe guessing
```

Le résultat recherché n’est pas de transformer PyScheduleKit en framework de cybersécurité.

Il s’agit de garantir que son architecture de scheduling ne crée pas elle-même des mécanismes inutiles de :

```text
RCE

secret leakage

unsafe deserialization

SSRF

configuration injection
```

alors que ces risques peuvent être évités par conception.

---

# Suite documentaire

La prochaine étape logique est :

```text
27_TEST_MATRIX_AND_ACCEPTANCE_CRITERIA.md
```

Ce document devra transformer tout ce qui a été défini depuis le début en preuves exécutables :

```text
Trigger tests

Timezone / DST tests

Schedule lifecycle

Misfire

Catch-Up

Concurrency

Retry

Execution state machine

Persistence

Crash consistency

Outbox

Distributed claims

Leases / fencing

Observability

Public API

Error model

Security
```

et répondre à :

> **Quelles preuves concrètes doivent être vertes avant que PyScheduleKit puisse considérer chacune de ses garanties comme réellement implémentée ?**

Puis :

```text
28_IMPLEMENTATION_ROADMAP.md
```

pour convertir cette matrice en lots de réalisation ordonnés, depuis le premier vertical slice en mémoire jusqu’au runtime persistant et distribué.