# PyScheduleKit — Distributed Coordination, Leases & Leader Election

**Document :** `20_DISTRIBUTED_COORDINATION_LEASES_AND_LEADER_ELECTION.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle distribué de référence  
**Nature :** Distributed Runtime Model — Coordination / Lease / Ownership / Leader Election / Fencing / Failover  
**Prérequis :**
- `14_CONCURRENCY_AND_OVERLAP_MODEL.md`
- `16_EXECUTION_LIFECYCLE_AND_STATE_MACHINE.md`
- `17_SCHEDULER_ENGINE_AND_EVALUATION_LOOP.md`
- `18_SCHEDULER_RUNTIME_AND_WAKEUP_MODEL.md`
- `19_PERSISTENCE_REPOSITORIES_AND_TRANSACTION_MODEL.md`

---

# 1. Objectif

Jusqu'ici, PyScheduleKit pouvait fonctionner avec :

```text
1 SchedulerRuntime
1 SchedulerEngine
1 persistence store
```

Le problème change lorsqu'on déploie :

```text
Scheduler Node A

Scheduler Node B

Scheduler Node C
```

sur :

```text
la même base

les mêmes Schedules

les mêmes ExecutionRequests
```

La question devient :

> **Comment plusieurs instances de PyScheduleKit peuvent-elles coopérer sans matérialiser ou exécuter incorrectement le même travail ?**

---

# 2. Le problème distribué fondamental

Supposons :

```text
Schedule S1
next_run_time = 10:00
```

À 10:00 :

```text
Node A reads S1

Node B reads S1
```

Les deux concluent :

```text
Occurrence 10:00 is due
```

Sans coordination :

```text
A → Request RA

B → Request RB
```

pour la même occurrence.

---

# 3. Heureusement, la déduplication existe déjà

Le document 19 a défini :

```text
OccurrenceKey
=
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

avec une contrainte d'unicité.

Donc même si :

```text
A
et
B
```

tentent la même matérialisation :

```text
une seule transaction
```

doit pouvoir créer la Request primaire.

---

# 4. Mais la déduplication ne résout pas tout

Elle évite principalement :

```text
duplicate durable logical occurrence
```

Elle n'empêche pas automatiquement :

```text
travail redondant

contention DB

double ownership temporaire

double executor claim

violation d'une concurrency policy

stale workers

split brain
```

---

# 5. Plusieurs niveaux de coordination

PyScheduleKit doit distinguer au moins :

```text
Schedule Coordination

Execution Coordination

Concurrency Coordination

Runtime Leadership
```

---

# 6. Schedule Coordination

Question :

> Quel nœud a le droit d'évaluer ce Schedule maintenant ?

---

# 7. Execution Coordination

Question :

> Quel worker a le droit de démarrer cette Execution ou cette Attempt ?

---

# 8. Concurrency Coordination

Question :

> Peut-on créer une nouvelle Execution pour cette ConcurrencyKey ?

---

# 9. Runtime Leadership

Question :

> Existe-t-il une responsabilité globale qui doit être exercée par un seul nœud ?

---

# 10. Ces problèmes sont différents

Très important :

```text
Schedule Lease
≠
Execution Lease
≠
Concurrency Slot
≠
Leader Election
```

---

# 11. Première architecture possible

Une architecture simple peut utiliser :

```text
plusieurs Scheduler nodes
+
même DB
+
row claiming
+
unique constraints
```

sans leader global.

---

# 12. Exemple

```text
Node A claims Schedule 1

Node B claims Schedule 2

Node C claims Schedule 3
```

Chaque nœud peut travailler en parallèle.

---

# 13. Leader global non obligatoire

Un scheduler distribué n'a pas nécessairement besoin :

```text
d'un unique master
```

si les Schedules peuvent être :

```text
partitionnés
ou
claimés individuellement
```

---

# 14. Pourquoi éviter un leader global inutile ?

Parce qu'un leader unique peut devenir :

```text
bottleneck

single point of coordination

failover complexity
```

---

# 15. Leader Election reste utile

Elle devient pertinente pour certaines responsabilités globales :

```text
cleanup

global reconciliation

maintenance

partition assignment

metadata compaction

exclusive migrations
```

---

# 16. Donc

PyScheduleKit doit supporter conceptuellement :

```text
leaderless schedule processing
```

et éventuellement :

```text
leader-only global duties
```

---

# 17. Ownership

`Ownership` signifie :

> **Un nœud est actuellement reconnu comme responsable d'une ressource coordonnée.**

Exemples :

```text
Schedule ownership

Execution ownership

Partition ownership

Leadership ownership
```

---

# 18. Ownership n'est pas éternel

Dans un système distribué, le propriétaire peut :

```text
crash

être partitionné du réseau

être suspendu

perdre sa lease
```

---

# 19. Lease

Une `Lease` représente :

> **Un droit temporaire d'agir sur une ressource jusqu'à une échéance explicite.**

---

# 20. Différence Lock versus Lease

Un lock classique signifie conceptuellement :

```text
locked until released
```

Une lease signifie :

```text
owned until expiration
unless renewed
```

---

# 21. Pourquoi les leases sont utiles en distribué

Si Node A meurt :

```text
sans release
```

la lease finit quand même par :

```text
expirer
```

---

# 22. Lease model

Une lease peut être représentée par :

```text
Lease
│
├── ResourceKey
├── OwnerId
├── AcquiredAt
├── ExpiresAt
├── LeaseVersion
└── FencingToken
```

---

# 23. Lease comme Entity

Une Lease possède :

```text
une identité liée à la ressource
```

et un lifecycle.

Classification raisonnable :

```text
Infrastructure Coordination Entity
```

---

# 24. ResourceKey

Exemples :

```text
schedule:42

execution:exec-123

leader:global-maintenance

concurrency:customer-refresh
```

---

# 25. OwnerId

Représente :

```text
SchedulerNodeId
```

ou :

```text
WorkerNodeId
```

selon le contexte.

---

# 26. Lease expiration

```text
now >= expires_at
```

signifie :

```text
lease no longer valid
```

---

# 27. Renewal

Un owner vivant peut renouveler :

```text
expires_at
```

avant expiration.

---

# 28. LeaseDuration

Exemple :

```text
lease duration = 30s
```

Node doit renouveler avant :

```text
30s
```

---

# 29. Heartbeat versus Lease Renewal

Souvent liés, mais conceptuellement :

```text
Heartbeat
→ proves liveness

Lease Renewal
→ extends ownership
```

---

# 30. Ils peuvent être le même appel infrastructure

Mais la sémantique reste distincte.

---

# 31. Danger fondamental

Supposons :

```text
Node A owns lease
```

puis A subit une longue pause GC.

La lease expire.

Node B acquiert la ressource.

Puis A se réveille.

---

# 32. Stale owner

A peut encore croire :

```text
"I am owner"
```

alors que :

```text
B is current owner
```

---

# 33. Ceci crée le problème du stale writer

Si A continue à écrire :

```text
les données peuvent être corrompues
```

---

# 34. Une lease seule n'est pas suffisante

C'est l'un des points les plus importants du document.

---

# 35. Fencing Token

Un `FencingToken` est un compteur monotone généré à chaque nouvelle acquisition.

Exemple :

```text
Node A lease token = 41

lease expires

Node B lease token = 42
```

---

# 36. Si A se réveille

Il tente une écriture avec :

```text
token = 41
```

Le système doit refuser car :

```text
41 < current token 42
```

---

# 37. Fencing provides stale-owner protection

Il ne suffit donc pas de demander :

```text
"is lease apparently still mine?"
```

Il faut aussi empêcher techniquement :

```text
old owner writes after new owner
```

---

# 38. FencingToken comme Value Object

```text
FencingToken
=
monotonic integer
```

avec invariant :

```text
new token > previous token
```

---

# 39. Fencing requires cooperation

Le composant qui reçoit l'écriture doit vérifier le token.

Sinon :

```text
token exists
but provides no protection
```

---

# 40. Example persistence

```text
UPDATE schedule
SET ...
WHERE schedule_id = ?
AND fencing_token <= supplied_token
```

La forme exacte dépend de l'architecture.

---

# 41. Alternative avec version transactionnelle

Dans certains designs DB-centric :

```text
row lock
+
transaction
+
PersistenceVersion
```

peut rendre le fencing de Schedule moins nécessaire.

---

# 42. Mais pour ressources externes

Le fencing devient très important.

Exemple :

```text
distributed storage

external worker

shared file

remote singleton resource
```

---

# 43. Schedule Claim

Un `ScheduleClaim` représente :

> Le droit temporaire d'évaluer un Schedule.

---

# 44. V1 distributed option

Avec PostgreSQL :

```text
SELECT ...
FOR UPDATE SKIP LOCKED
```

peut servir de mécanisme de claim.

---

# 45. Dans ce modèle

Le lock ne survit que :

```text
pendant la transaction
```

---

# 46. Avantage

Pas de Lease persistée complexe.

---

# 47. Pattern

```text
BEGIN

select due schedules
FOR UPDATE SKIP LOCKED

evaluate

materialize requests

advance next_run_time

COMMIT
```

---

# 48. Les autres nodes

Ignorent les lignes déjà verrouillées.

---

# 49. Ce modèle est excellent si

L'évaluation de Schedule est :

```text
courte

transactionnelle

DB-local
```

---

# 50. Pas besoin de lease longue

Si :

```text
read → evaluate → write
```

reste suffisamment court.

---

# 51. Attention

Le calcul de recurrence peut être coûteux.

Un long Catch-Up peut maintenir le lock trop longtemps.

---

# 52. Plan/Apply peut améliorer

```text
READ

PLAN

BEGIN

validate version

claim/apply

COMMIT
```

---

# 53. Mais une autre node peut planifier en parallèle

Ce n'est pas grave si :

```text
apply
```

vérifie version + occurrence uniqueness.

---

# 54. Optimistic distributed scheduling

On peut donc fonctionner avec :

```text
no long-lived schedule lease

optimistic evaluation

unique OccurrenceKey

PersistenceVersion
```

---

# 55. C'est une architecture valide

Et souvent plus simple.

---

# 56. Quand utiliser des Schedule Leases ?

Si :

```text
évaluation longue

state partitioning

non-SQL coordination

timer ownership

expensive planning

in-memory schedule shards
```

---

# 57. Donc Lease n'est pas obligatoire partout

PyScheduleKit ne doit pas devenir :

```text
lease-driven by default
```

simplement parce qu'il est distribué.

---

# 58. CoordinationPolicy

Une architecture future peut choisir :

```text
DATABASE_CLAIM

OPTIMISTIC

LEASED

PARTITIONED
```

au niveau runtime.

---

# 59. Pas une SchedulePolicy métier

C'est :

```text
Runtime Coordination Strategy
```

---

# 60. Execution Claim

Nous avons également :

```text
Execution QUEUED
```

Plusieurs workers peuvent la voir.

---

# 61. Même problème

```text
Worker A
Worker B
```

tentent tous deux :

```text
Attempt #1
```

---

# 62. Protection minimale

```text
UNIQUE(
    execution_id,
    attempt_number
)
```

empêche deux `Attempt #1`.

---

# 63. Mais encore une fois

Cela ne suffit pas à empêcher :

```text
double remote side effect
```

si les deux workers exécutent avant la contrainte durable.

---

# 64. Correct order

Worker doit :

```text
claim Execution

persist Attempt RUNNING

COMMIT
```

avant :

```text
external target invocation
```

---

# 65. Execution claim transaction

```text
BEGIN

select Execution QUEUED

claim atomically

create Attempt #1 RUNNING

COMMIT

invoke Executor
```

---

# 66. DB claim possible

Encore :

```text
FOR UPDATE SKIP LOCKED
```

est un excellent mécanisme SQL.

---

# 67. Worker lease

Pour des Attempts longues :

```text
Execution claim
```

peut être accompagné d'une :

```text
WorkerLease
```

---

# 68. Pourquoi ?

Après COMMIT, le DB row lock n'existe plus.

L'Attempt peut courir pendant :

```text
30 minutes
```

---

# 69. Ownership de l'Attempt

On peut stocker :

```text
worker_id

lease_expires_at

fencing_token
```

---

# 70. Worker heartbeat

Le worker renouvelle :

```text
lease_expires_at
```

pendant le travail.

---

# 71. Worker crash

Lease expire.

RuntimeReconciler peut conclure :

```text
worker lost
```

---

# 72. Mais attention aux faux positifs

Une pause réseau peut faire expirer la lease alors que le worker continue réellement.

---

# 73. Fencing again

Le nouveau worker doit obtenir un token supérieur.

Les side effects partagés devraient rejeter l'ancien token si possible.

---

# 74. Mais tous les Targets ne supportent pas fencing

Exemple :

```text
send email
```

ne permet pas facilement :

```text
reject stale fencing token
```

---

# 75. Donc

Une lease ne garantit jamais universellement :

```text
exactly-once external effects
```

---

# 76. IdempotencyKey reste essentielle

Pour les Targets supportant l'idempotence :

```text
same Execution
→ same IdempotencyKey
```

---

# 77. Coordination + Idempotence

Deux outils complémentaires :

```text
Coordination
→ reduce concurrent duplicates

Idempotence
→ tolerate residual duplicate attempts
```

---

# 78. Très important

Ne jamais considérer :

```text
distributed lock
```

comme substitut complet à :

```text
idempotency
```

---

# 79. ConcurrencyPolicy distributed

Le document 14 définissait :

```text
ConcurrencyPolicy
```

au niveau métier.

En multi-node, le problème devient :

```text
atomic admission
```

---

# 80. Exemple

```text
max_instances = 1
```

Node A voit :

```text
0 active
```

Node B voit :

```text
0 active
```

---

# 81. Both admit

Violation :

```text
2 active
```

---

# 82. ActiveExecutionSnapshot alone is insufficient

Il aide le domaine à décider :

```text
SHOULD admit
```

mais pas à garantir :

```text
CAN atomically admit
```

---

# 83. ConcurrencyCoordinator

Port déjà évoqué :

```text
ConcurrencyCoordinator
```

---

# 84. Possible API

```text
try_acquire(
    concurrency_key,
    max_instances,
    execution_id,
)
```

---

# 85. Result

```text
ACQUIRED

CAPACITY_EXHAUSTED

CONFLICT
```

---

# 86. Release

Lorsque Execution devient terminale :

```text
release
```

conceptuellement.

---

# 87. Better DB-derived model

Si capacité est dérivée des `ExecutionState` :

```text
release
```

peut être implicite.

---

# 88. Need atomic admission transaction

```text
lock concurrency key

count active

insert Execution

commit
```

---

# 89. ConcurrencyKey coordination row

Une table infrastructure peut être :

```text
concurrency_slots
```

ou :

```text
concurrency_keys
```

---

# 90. Example

```text
concurrency_key
version
```

La row sert de :

```text
serialization point
```

---

# 91. Advisory lock alternative

PostgreSQL :

```text
advisory lock(hash(concurrency_key))
```

peut sérialiser l'admission.

---

# 92. Portability trade-off

Advisory locks sont :

```text
powerful

database-specific
```

---

# 93. V1 distributed recommendation

Pour préserver la portabilité :

```text
row-backed concurrency key
```

est plus générique.

---

# 94. Concurrency slot lease?

Possible si capacité doit survivre hors transaction.

Mais si active state est dans DB :

```text
Execution lifecycle
```

peut être le slot logique durable.

---

# 95. Simpler

```text
Execution active
=
slot occupied
```

---

# 96. Leader Election

Passons maintenant au leadership global.

---

# 97. Leader

Un `Leader` est un nœud temporairement désigné pour exécuter :

```text
une responsabilité globale exclusive
```

---

# 98. Leader Election

Mécanisme permettant de choisir :

```text
one active leader
```

parmi plusieurs candidats.

---

# 99. Important

Leader Election n'est pas :

```text
Schedule claiming
```

---

# 100. Un scheduler peut être distribué sans leader global

avec :

```text
per-Schedule claims
```

---

# 101. Leader responsibilities possibles

```text
global cleanup

outbox compaction

retention job

partition ownership assignment

global runtime reconciliation

single maintenance task
```

---

# 102. Avoid routing all scheduling through leader

Sinon :

```text
all nodes
```

deviennent inutiles pour le scheduling.

---

# 103. Leader Lease

Le leadership peut lui-même être représenté par :

```text
Lease(
  resource="scheduler-leader",
  owner=node-A
)
```

---

# 104. Election via DB

Pattern possible :

```text
leader_leases
```

table.

---

# 105. Node attempts

```text
INSERT/UPDATE if expired
```

atomically.

---

# 106. Winner

Obtient :

```text
LeaderLease
```

avec :

```text
FencingToken
```

---

# 107. Renewal

Leader renouvelle périodiquement.

---

# 108. Failure

Si plus de renewal :

```text
lease expires
```

autre node peut gagner.

---

# 109. Failover

```text
Leader A fails
↓
lease expires
↓
Node B acquires
↓
B becomes Leader
```

---

# 110. Failover delay

Au minimum proche de :

```text
lease duration
```

ou expiry detection interval.

---

# 111. Trade-off lease duration

Lease courte :

```text
fast failover
high renewal pressure
sensitive to pauses
```

Lease longue :

```text
slow failover
more tolerant of transient pauses
```

---

# 112. No universally correct duration

Infrastructure/configuration concern.

---

# 113. Lease Renewal Margin

Il faut renouveler avant expiration.

Exemple :

```text
duration = 30s

renew every 10s
```

---

# 114. Do not renew at last millisecond

---

# 115. Clock source question

Lease expiration pose un problème important :

> **Quelle horloge est autoritative ?**

---

# 116. Danger des clocks locales

Node A :

```text
12:00:00
```

Node B :

```text
12:00:07
```

---

# 117. Clock skew

Les nœuds ne voient pas exactement le même temps.

---

# 118. Si chaque node décide l'expiration avec son propre Clock

On peut produire :

```text
overlap ownership
```

---

# 119. Better

Pour les leases DB-backed :

```text
database server time
```

peut servir de source d'expiration.

---

# 120. Exemple

```text
CURRENT_TIMESTAMP
```

dans la transaction DB.

---

# 121. Pourquoi ?

Tous les nodes consultent alors :

```text
same coordination time authority
```

---

# 122. Important separation

Pour le scheduling métier :

```text
Clock abstraction
```

reste nécessaire.

Pour les leases :

```text
coordination clock
```

peut être différent.

---

# 123. CoordinationClock

Concept possible :

```text
CoordinationClock
```

---

# 124. Mais éviter une abstraction inutile en V1

Un adapter DB peut gérer directement :

```text
lease expiry using DB time
```

---

# 125. Fencing token more robust than clocks alone

Même avec horloges imparfaites, le token monotone empêche un ancien owner de reprendre autorité.

---

# 126. Split Brain

`Split brain` signifie :

> Plusieurs nœuds se croient simultanément propriétaires d'une responsabilité exclusive.

---

# 127. Causes possibles

```text
network partition

long GC pause

clock skew

lease renewal ambiguity

database failover

stale cache
```

---

# 128. Example

```text
A believes lease valid

B believes lease expired
```

Les deux agissent.

---

# 129. Protection

```text
atomic lease acquisition

fencing tokens

idempotent operations

unique constraints
```

---

# 130. Leader election alone does not eliminate split brain

Elle réduit sa probabilité.

La sécurité réelle vient de :

```text
fenced resource access
```

---

# 131. Golden rule

> **Do not trust ownership claims that cannot be enforced at the resource boundary.**

---

# 132. NodeIdentity

Chaque runtime distribué doit avoir :

```text
NodeId
```

stable pour la durée du process.

---

# 133. Example

```text
scheduler-7f9d...
```

---

# 134. NodeId should not be hostname alone

Containers/pods may reuse names or addresses.

---

# 135. Better

```text
instance UUID
```

generated at startup.

---

# 136. NodeId lifecycle

New process:

```text
new NodeId
```

unless infrastructure guarantees stronger identity.

---

# 137. Persisted NodeId

May be stored with leases.

---

# 138. Node metadata

Could include:

```text
started_at

host

process id

version
```

for diagnostics.

---

# 139. Not part of domain identity

---

# 140. Lease lifecycle

```text
AVAILABLE
   │
   ▼
ACQUIRED
   │
   ├── renew
   │     └── ACQUIRED
   │
   ├── release
   ▼
AVAILABLE
```

Expiration behaves as:

```text
ACQUIRED
→ AVAILABLE
```

conceptually.

---

# 141. Actual DB may not mutate on expiry

Lease may remain row:

```text
owner=A
expires_at=past
```

and be considered logically available.

---

# 142. This is fine.

---

# 143. Lease acquire operation

Must be:

```text
atomic
```

---

# 144. Not

```text
read expired
then update
```

in two unprotected operations.

---

# 145. Compare-and-swap

Pattern:

```text
UPDATE lease
SET owner=?, token=token+1, expires_at=...
WHERE expires_at <= coordination_now
```

---

# 146. If affected rows = 1

Acquired.

---

# 147. If 0

Someone else owns.

---

# 148. Lease renew

Only owner and token holder should renew.

```text
WHERE owner_id=?
AND fencing_token=?
```

---

# 149. Prevent old process from renewing new lease

Very important.

---

# 150. Lease release

Same guard.

---

# 151. Stale release

Node A with token 41 must not clear B's token 42 lease.

---

# 152. Release condition

```text
owner=A
AND token=41
```

---

# 153. Lease acquisition result

```text
LeaseAcquired

LeaseBusy
```

---

# 154. Renewal result

```text
LeaseRenewed

LeaseLost
```

---

# 155. LeaseLost

If renewal fails:

```text
owner must immediately stop acting
as authoritative owner
```

---

# 156. But "immediately" has limits

Running external operation may not stop instantly.

---

# 157. Therefore fencing/idempotence still needed.

---

# 158. Schedule Lease loss

If Node loses Schedule lease during planning:

```text
do not apply plan
```

unless final transaction independently proves correctness.

---

# 159. Execution Lease loss

Worker should:

```text
stop issuing new side effects
```

when possible.

---

# 160. But current remote call may already be in flight.

Again:

```text
cannot guarantee rollback
```

---

# 161. LeaseManager Port

Possible abstraction:

```text
LeaseManager
```

---

# 162. API

```text
try_acquire(resource_key, owner_id, duration)

renew(lease)

release(lease)
```

---

# 163. Returned Lease

Contains:

```text
owner_id

expires_at

fencing_token
```

---

# 164. Infrastructure responsibility

LeaseManager belongs to:

```text
ports/infrastructure
```

not domain scheduling policy.

---

# 165. Lease acquisition should not depend on ScheduleDefinition

---

# 166. Distributed Scheduler Strategy A

## Row Claiming

```text
DB query
FOR UPDATE SKIP LOCKED
```

Best when:

```text
evaluation short

SQL central store
```

---

# 167. Strategy B

## Optimistic Competition

All nodes may evaluate.

Only one wins:

```text
version check
+
OccurrenceKey uniqueness
```

Best when planning outside transaction is useful.

---

# 168. Strategy C

## Schedule Leases

Nodes acquire temporal ownership.

Best when:

```text
state held longer

local timer shards

expensive planning
```

---

# 169. Strategy D

## Static Partitioning

Schedules assigned by:

```text
hash(schedule_id) mod N
```

---

# 170. Challenge

Membership changes.

---

# 171. Consistent hashing

Can reduce movement.

But complexity increases.

---

# 172. PyScheduleKit V1 distributed recommendation

Start with:

```text
central SQL persistence

bounded row claiming
or optimistic competition

unique OccurrenceKey

optimistic versions
```

---

# 173. Why?

It uses infrastructure guarantees already required by the persistence model.

---

# 174. Do not begin with leader election everywhere

---

# 175. Multi-node evaluation flow

```text
Node A          Database          Node B
  │                │                │
  ├─ find due ────►│◄──── find due ┤
  │                │                │
  ├─ claim S1 ────►│                │
  │                │◄──── claim S1 ┤
  │   success      │      conflict  │
  │                │                │
  ▼                │                ▼
evaluate            │             continue
```

---

# 176. Claim scope

Prefer claim of:

```text
Schedule ID
```

not entire table.

---

# 177. Batch claims

Can claim:

```text
N schedules
```

but transaction lock duration must remain bounded.

---

# 178. Per-schedule transaction remains attractive

---

# 179. Node crash during Schedule transaction

DB rollback releases locks.

Another node can retry.

---

# 180. Node crash after commit

Request is durable.

Other nodes see advanced next_run_time.

---

# 181. Perfect with Outbox

Dispatch can continue independently.

---

# 182. Node crash while holding Lease

Lease eventually expires.

---

# 183. But durable Request may already exist

Unique identity prevents rematerialization.

---

# 184. Distributed Retry Processing

Executions in:

```text
RETRY_WAIT
```

can be discovered by multiple workers.

---

# 185. Need same claim semantics

Only one can transition:

```text
RETRY_WAIT
→ RUNNING
```

and create:

```text
Attempt N+1
```

---

# 186. Protect using

```text
ExecutionVersion

transactional claim

UNIQUE(execution_id, attempt_number)
```

---

# 187. Atomic transition

Critical.

---

# 188. Retry timer does not imply owner

The node waking at retry time must still:

```text
claim execution
```

---

# 189. Timer heap in multiple nodes

Each node may have stale local timers.

That's okay.

---

# 190. Wake-up is only hint

Same principle as document 18.

---

# 191. Distributed Wake-Up

One node creates a new Schedule.

Other nodes may need waking.

---

# 192. Options

```text
polling

DB notification

message bus

shared timer service
```

---

# 193. Correctness should not depend on signal delivery

Polling fallback remains valuable.

---

# 194. Multiple nodes may all wake

No problem if claims are atomic.

---

# 195. Thundering Herd

However, all nodes polling same due instant can create contention.

---

# 196. Example

```text
100 nodes
10,000 schedules due at midnight
```

---

# 197. Solutions

```text
SKIP LOCKED

jittered polling

partitioning

bounded claiming

sharding
```

---

# 198. Runtime Poll Jitter

Can be used to desynchronise scheduler nodes.

---

# 199. This jitter is yet another distinct concept

```text
Schedule Jitter

Retry Jitter

Runtime Poll Jitter
```

---

# 200. Names must remain explicit.

---

# 201. Distributed backpressure

Nodes should claim only:

```text
what they can process
```

---

# 202. Avoid claiming 10,000 schedules

then holding ownership while slowly processing.

---

# 203. Claim batch should be bounded

---

# 204. Claim timeout

With locks:

```text
transaction duration
```

is bound.

With leases:

```text
lease duration
```

is bound.

---

# 205. Distributed fairness

A fast node may repeatedly claim all work.

---

# 206. Is this wrong?

Not necessarily.

If all work is processed correctly:

```text
fairness between scheduler nodes
```

is operational, not business.

---

# 207. Tenant fairness

Different concern.

May matter later.

---

# 208. Node-specific caches

Any local cache must be considered:

```text
staleable
```

---

# 209. Cache never authoritative

---

# 210. Schedule change propagation

If Node A has cached Schedule rev 4 and user creates rev 5:

```text
version check
```

must prevent stale write.

---

# 211. Good distributed property

The DB becomes:

```text
authoritative coordination boundary
```

for V1/V2.

---

# 212. CAP-style reality

During network partition from DB:

A node cannot safely mutate authoritative scheduler state.

---

# 213. Fail closed

If node cannot reach persistence:

```text
do not dispatch new durable work
```

---

# 214. Why?

Without persistence, it cannot prove:

```text
ownership

deduplication

checkpoint
```

---

# 215. Existing external worker

May continue its current Attempt if execution already committed.

---

# 216. Scheduler availability and worker availability are distinct.

---

# 217. Node isolation

Scheduler node DB-disconnected:

```text
stop evaluating new schedules
```

---

# 218. Worker DB-disconnected

Harder.

It may be executing.

---

# 219. It should not fabricate completion locally as durable truth.

Result must eventually be reconciled/persisted.

---

# 220. Worker lease renewal failure

May signal:

```text
ownership uncertainty
```

---

# 221. Conservative behavior

If possible:

```text
stop new side effects
```

and terminate/abort.

---

# 222. But not always feasible.

---

# 223. Failure Detector

A distributed system never knows with perfect certainty:

```text
node dead
```

It usually knows:

```text
node has not renewed within expected time
```

---

# 224. Lease expiry is a suspicion mechanism

Not metaphysical proof of death.

---

# 225. This explains fencing necessity.

---

# 226. Leader responsibilities must be idempotent too

Suppose leader A performs cleanup and loses lease.

Leader B continues.

Operations should ideally tolerate:

```text
partial previous leadership work
```

---

# 227. Leadership epoch

A fencing token can also be called:

```text
LeadershipEpoch
```

---

# 228. Example

```text
Epoch 21 → Node A

Epoch 22 → Node B
```

---

# 229. Global events can include epoch

Useful for diagnostics.

---

# 230. Leader state

Could expose:

```text
FOLLOWER

LEADER
```

as runtime role.

---

# 231. But not part of SchedulerRuntimeState

Better separate:

```text
RuntimeState = RUNNING

LeadershipRole = FOLLOWER
```

---

# 232. LeadershipRole

```text
FOLLOWER

LEADER
```

and optionally:

```text
CANDIDATE
```

if algorithm requires.

---

# 233. DB lease election does not need complex Candidate state

It is mostly:

```text
try acquire
→ leader or follower
```

---

# 234. No need to implement Raft

Important.

---

# 235. PyScheduleKit should not invent consensus protocol

If global distributed consensus becomes necessary, use:

```text
database

etcd

Consul

Kubernetes leases
```

through an adapter.

---

# 236. Core only needs a LeaderElectionPort

---

# 237. LeaderElectionPort

Possible:

```text
try_acquire_leadership()

renew_leadership()

release_leadership()
```

---

# 238. But only introduce it if leader-only work exists.

---

# 239. YAGNI

If Schedules are handled by row claims:

```text
no leader election required for scheduling
```

---

# 240. This is a crucial design decision

Avoid needless centralization.

---

# 241. Split-brain scenario with leader

```text
A = leader token 100

network pause

lease expires

B = leader token 101

A resumes
```

---

# 242. Without fencing

Both may run:

```text
global cleanup
```

---

# 243. With fencing

Any protected write from token 100 is rejected after token 101 exists.

---

# 244. Fencing at DB transaction level

If all leader duties mutate same DB:

```text
epoch check
```

can protect them.

---

# 245. External services may not support epoch

Again:

```text
idempotence
```

needed.

---

# 246. Distributed Concurrency Example

Two schedules:

```text
S1
S2
```

share:

```text
ConcurrencyKey = "customer-refresh"
```

limit:

```text
1
```

---

# 247. Node A handles S1

Node B handles S2.

Both need same:

```text
coordination point
```

---

# 248. Per-Schedule lease cannot enforce this

Because they own different Schedules.

---

# 249. Need coordination by ConcurrencyKey

This clearly proves:

```text
Schedule ownership
≠
Concurrency ownership
```

---

# 250. Atomic admission transaction

```text
lock concurrency key "customer-refresh"

count active

if 0:
    create Execution
else:
    WAIT/DROP
```

---

# 251. Distributed recovery

Node A may crash after creating Execution but before processing next work.

No issue:

```text
Execution persisted
```

---

# 252. Another worker can find:

```text
QUEUED Execution
```

---

# 253. Worker affinity not required

Unless Target demands it.

---

# 254. Retry worker affinity

Same Execution retry can be handled by:

```text
different worker
```

provided context is durable.

---

# 255. Strong architectural benefit

No in-memory owner should be required for recovery.

---

# 256. Sticky ownership future

May improve locality.

Not correctness requirement.

---

# 257. Lease state persistence

Possible table:

```text
leases
──────────────
resource_key PK
owner_id
fencing_token
expires_at
updated_at
```

---

# 258. Leader lease

Same table can use:

```text
resource_key = "leader:scheduler"
```

---

# 259. Schedule leases

```text
resource_key = "schedule:<id>"
```

---

# 260. Worker leases

```text
resource_key = "attempt:<id>"
```

---

# 261. Generic Lease table benefit

Simple reusable infrastructure.

---

# 262. Downside

Can become contention hotspot.

---

# 263. Specialized coordination

May scale better.

But V1/V2 can remain generic.

---

# 264. Lease fencing constraint

`fencing_token` must increase atomically.

---

# 265. Never reset token on release

If reset:

```text
stale token may appear current again
```

---

# 266. Token must be monotone over resource lifetime

---

# 267. Token wraparound

Use sufficiently large integer.

Practically:

```text
64-bit
```

is enough for this use.

---

# 268. Lease expiry storage

Use:

```text
absolute Instant
```

under coordination clock.

---

# 269. Renewal transaction

Atomic:

```text
verify owner/token

set new expires_at
```

---

# 270. Cannot renew expired lease automatically?

Two models.

---

# 271. Strict model

If expired:

```text
renew fails
```

owner must reacquire.

---

# 272. Recommended

Strict.

---

# 273. Why?

Once expired, another node may already have acquired a newer token.

---

# 274. Do not "resurrect" old lease.

---

# 275. Release not mandatory

Lease correctness must survive:

```text
owner crash
```

without explicit release.

---

# 276. Release is optimization

It improves failover speed.

---

# 277. Good principle

```text
release helps

expiry guarantees eventual availability
```

---

# 278. Lease renewal failure

Owner transitions to:

```text
LOST_OWNERSHIP
```

conceptually.

---

# 279. Should this be persisted?

Usually operational, not necessary.

---

# 280. Metrics are enough.

---

# 281. Lease metrics

```text
lease_acquire_success

lease_acquire_conflict

lease_renew_success

lease_renew_failure

lease_expiration_count

lease_ownership_duration
```

---

# 282. Leader metrics

```text
is_leader

leadership_epoch

leadership_changes

leader_lease_renew_failures
```

---

# 283. Scheduler node metrics

```text
claimed_schedules

claim_conflicts

duplicate_occurrence_conflicts

stale_plan_conflicts
```

---

# 284. Execution worker metrics

```text
claimed_executions

attempt_claim_conflicts

worker_lease_losses
```

---

# 285. Distributed diagnostics

For each claim/lease:

```text
resource

owner

token

acquired_at

expires_at
```

should be observable.

---

# 286. Avoid high-cardinality metrics for every resource

Use logs/traces for individual IDs.

---

# 287. Lease events

Possible operational events:

```text
LeaseAcquired

LeaseRenewed

LeaseLost

LeaseReleased

LeadershipAcquired

LeadershipLost
```

---

# 288. Not necessarily domain events

They are:

```text
coordination/runtime events
```

---

# 289. Security

Node identity must not be trusted solely from user-supplied input.

---

# 290. Lease operations require authenticated DB/service access

Infrastructure concern.

---

# 291. Multi-tenant lease key

If tenants exist later:

```text
tenant_id
```

should be part of resource namespace.

---

# 292. Example

```text
tenant:42:concurrency:refresh
```

---

# 293. Prevent accidental cross-tenant coordination

Unless explicitly global.

---

# 294. Lease GC

Expired lease rows may accumulate.

---

# 295. If row reused by ResourceKey

No unbounded growth for stable resources.

---

# 296. Temporary resources

Attempt leases may require cleanup.

---

# 297. Retention/cleanup can be leader-only maintenance

---

# 298. Again cleanup must not impact correctness

Expired rows can remain temporarily.

---

# 299. Testing distributed coordination

Must go beyond unit tests.

---

# 300. Test — two nodes same Schedule

Both attempt occurrence 10:00.

Expected:

```text
one primary ExecutionRequest
```

---

# 301. Test — optimistic stale version

Node A commits.

Node B fails version check.

Expected:

```text
reload/re-evaluate
```

---

# 302. Test — duplicate OccurrenceKey

Expected:

```text
idempotent already-materialized result
```

---

# 303. Test — two workers same Execution

Expected:

```text
one Attempt #1
```

---

# 304. Test — Retry race

Two workers see RETRY_WAIT due.

Expected:

```text
one Attempt #N
```

---

# 305. Test — Lease expiry

A owns.

Clock advances past expiry.

B acquires.

Expected:

```text
B token > A token
```

---

# 306. Test — stale renewal

A tries renewal with old token.

Expected:

```text
LeaseLost
```

---

# 307. Test — stale release

A tries release after B acquired.

Expected:

```text
B lease remains intact
```

---

# 308. Test — fencing

A token 41.

B token 42.

A tries protected write.

Expected:

```text
rejected
```

---

# 309. Test — leader failover

A leader disappears.

After expiry B acquires.

Expected:

```text
one current valid leader lease
```

---

# 310. Test — split brain simulation

A resumes after B takeover.

Expected:

```text
A cannot perform fenced mutation
```

---

# 311. Test — DB unavailable

Scheduler node cannot acquire coordination.

Expected:

```text
no new durable work dispatched
```

---

# 312. Test — network pause

Lease renewal fails.

Owner stops authoritative operations.

---

# 313. Test — concurrency across schedules

S1 and S2 same ConcurrencyKey.

Two nodes evaluate simultaneously.

Expected:

```text
max_instances respected
```

---

# 314. Test — terminal release

Execution reaches SUCCESS.

Waiting request can later acquire slot.

---

# 315. Test — node crash after request commit

Another node continues normally.

No duplicate logical occurrence.

---

# 316. Test — node crash before commit

Rollback.

Occurrence can be processed by another node.

---

# 317. Test — node crash while Attempt RUNNING

Lease expires.

Reconciler applies configured recovery.

---

# 318. Test — old worker late success

If newer Attempt exists, result handling must follow lifecycle/fencing rules.

---

# 319. Late result complexity

Suppose:

```text
Attempt #1 deemed lost

Attempt #2 starts

Attempt #1 later reports SUCCESS
```

---

# 320. V1 safety

A terminal/stale Attempt result must not silently overwrite newer Execution state.

---

# 321. Attempt identity/version needed

Result application verifies:

```text
attempt_id

execution state/version
```

---

# 322. If Attempt #1 no longer current

Treat as:

```text
LateAttemptResult
```

---

# 323. External side effect may still have occurred

Again requires idempotence/reconciliation.

---

# 324. Distributed state machine rule

> **State ownership may transfer; state history may not be rewritten.**

---

# 325. Anti-pattern — global mutex for whole scheduler

Destroys scalability.

---

# 326. Anti-pattern — one leader executes every Schedule

Unless system intentionally single-active.

---

# 327. Anti-pattern — lease without expiry

That's just a lock that may never recover.

---

# 328. Anti-pattern — expiry without fencing

Stale owners remain dangerous.

---

# 329. Anti-pattern — fencing token not checked by protected resource

Provides false confidence.

---

# 330. Anti-pattern — local clock determines distributed lease expiry independently

Clock skew can create inconsistent ownership.

---

# 331. Anti-pattern — release lease without token check

Can release another owner's lease.

---

# 332. Anti-pattern — auto-renew expired lease

May resurrect stale ownership.

---

# 333. Anti-pattern — assume network timeout means remote node dead

It only means:

```text
cannot currently confirm
```

---

# 334. Anti-pattern — use ScheduleId as all coordination keys

Concurrency can span several Schedules.

---

# 335. Anti-pattern — use ConcurrencyKey as Schedule ownership key

Different semantics.

---

# 336. Anti-pattern — distributed lock replaces unique OccurrenceKey

Keep both.

---

# 337. Anti-pattern — unique OccurrenceKey replaces atomic admission

It protects occurrence materialization, not cross-Schedule concurrency capacity.

---

# 338. Anti-pattern — leader election used as idempotency

Leadership does not guarantee external exactly-once.

---

# 339. Anti-pattern — keep owner only in memory

Crash destroys proof.

---

# 340. Anti-pattern — claim work then execute externally before durable claim commit

Can create double work.

---

# 341. Anti-pattern — worker lock held as SQL transaction for entire long-running task

Locks become pathological.

---

# 342. Use short claim transaction + durable ownership metadata

---

# 343. Anti-pattern — ignore stale worker results

They should at least be recorded diagnostically.

---

# 344. Anti-pattern — lease duration treated as execution timeout

Different concepts.

---

# 345. LeaseDuration

Controls:

```text
ownership validity
```

---

# 346. AttemptTimeout

Controls:

```text
attempt runtime budget
```

---

# 347. ExecutionDeadline

Controls:

```text
logical execution temporal budget
```

---

# 348. Three different timers

Never merge them.

---

# 349. Anti-pattern — SchedulerRuntime leader state mixed with ScheduleState

A Schedule is not:

```text
LEADER
```

---

# 350. Anti-pattern — hard-code PostgreSQL locks in domain

Use adapter seams.

---

# 351. Distributed coordination objects

Recommended concepts:

```text
NodeId [VO]

ResourceKey [VO]

Lease [Coordination Entity]

LeaseDuration [VO]

FencingToken [VO]

LeaseManager [Port]

ConcurrencyCoordinator [Port]

LeadershipRole [Runtime VO/Enum]

LeaderElectionPort [optional Port]
```

---

# 352. Existing protection concepts

Still required:

```text
OccurrenceKey

RequestId

ExecutionId

AttemptId

PersistenceVersion
```

---

# 353. Defense-in-depth stack

```text
Layer 1
Stable IDs

Layer 2
Unique constraints

Layer 3
Optimistic versions

Layer 4
Transactional claims

Layer 5
Leases where needed

Layer 6
Fencing tokens

Layer 7
Target idempotency
```

---

# 354. No single layer is enough everywhere

That is one of the key lessons of distributed scheduling.

---

# 355. Distributed scheduling flow

```text
Node A
  │
  ▼
Find due candidate
  │
  ▼
Acquire/claim
  │
  ▼
Reload authoritative Schedule
  │
  ▼
Plan occurrence
  │
  ▼
Create Request
  │
  ▼
Advance next_run_time
  │
  ▼
COMMIT
  │
  ▼
Release claim automatically / explicitly
```

---

# 356. Another node

Can then process:

```text
next due Schedule
```

---

# 357. Execution distributed flow

```text
Worker A
  │
  ▼
Find QUEUED Execution
  │
  ▼
Claim atomically
  │
  ▼
Create Attempt RUNNING
  │
  ▼
COMMIT
  │
  ▼
Invoke target
  │
  ▼
Persist AttemptResult
```

---

# 358. Worker lease flow

For long tasks:

```text
claim
↓
lease token
↓
run
↓
heartbeat / renew
↓
complete
↓
release
```

---

# 359. Leadership flow

```text
Node A ──try acquire──► LeaseStore
                         │
                         ├── success → token 81
                         │
                         └── busy

Node A becomes LEADER

renew...

if renewal fails
→ leadership lost
```

---

# 360. Failover flow

```text
Leader A
   │
   X crash
   │
lease expires
   │
   ▼
Node B acquires
token incremented
   │
   ▼
Leader B
```

---

# 361. State after failover

No Schedule semantics should change.

---

# 362. Very important

```text
Leadership is runtime ownership

not business state
```

---

# 363. Scheduler correctness without leader

The core SchedulerEngine remains:

```text
stateless enough
```

to run on any node given:

```text
durable Schedule state
```

---

# 364. This is desirable

It makes failover cheap.

---

# 365. Sticky in-memory scheduler ownership would weaken this

Unless carefully checkpointed.

---

# 366. Recommended evolution

## Phase 1 — Single Node

```text
single SchedulerRuntime
single worker runtime
```

---

# 367. Phase 2 — Multi-worker

```text
single scheduler
multiple execution workers
```

Focus on:

```text
Execution claiming
Attempt ownership
```

---

# 368. Phase 3 — Multi-scheduler SQL

```text
multiple SchedulerRuntime nodes
```

Use:

```text
row claiming
optimistic locking
unique OccurrenceKey
```

---

# 369. Phase 4 — Lease-enabled

Add:

```text
long-lived ownership
worker leases
fencing
```

where needed.

---

# 370. Phase 5 — Leader-only maintenance

Introduce:

```text
LeaderElectionPort
```

only for truly global duties.

---

# 371. Phase 6 — Partitioned Scale

Potential:

```text
sharding

consistent hashing

dynamic partition assignment
```

---

# 372. Do not jump directly to Phase 6

The learning objective favors progressive complexity.

---

# 373. Persistence tables extension

Possible table:

```text
leases
```

with:

```text
resource_key PK

owner_id

fencing_token

expires_at

updated_at
```

---

# 374. Optional node registry

```text
runtime_nodes
```

could store:

```text
node_id

started_at

last_seen_at

runtime_version
```

---

# 375. Is node registry required?

No.

Lease rows can be enough.

---

# 376. Node registry useful for observability

Not correctness necessarily.

---

# 377. Leader lease can reuse same table

```text
resource_key = "leader:maintenance"
```

---

# 378. Concurrency coordination may use separate table

Because its semantics differ.

---

# 379. Do not force every coordination primitive into generic Lease

A semaphore with:

```text
max_instances = 5
```

is not naturally a single-owner lease.

---

# 380. Distributed Semaphore

`ConcurrencyCoordinator` may conceptually behave like:

```text
distributed bounded semaphore
```

---

# 381. But durable Execution rows may already implement the count

Prefer simpler truth.

---

# 382. Leaderless Outbox Publishing

Multiple outbox publishers can also use:

```text
row claim / SKIP LOCKED
```

No leader required.

---

# 383. Another important pattern

Use per-record claiming instead of global leadership whenever possible.

---

# 384. Why?

Horizontal scalability.

---

# 385. Cleanup may also be sharded

Even global maintenance doesn't always need one leader.

---

# 386. Leader should be last resort for exclusivity

Not default.

---

# 387. Coordination and transaction boundaries

Lease acquire should usually be separate from long business execution transaction.

---

# 388. Never keep SQL transaction open for lease lifetime

Lease itself is persistent state.

---

# 389. Claim transactions stay short.

---

# 390. Distributed transaction?

PyScheduleKit should not rely on:

```text
two-phase commit
```

across DB + external Executor for V1/V2.

---

# 391. Use

```text
local transaction
+
outbox
+
idempotence
```

instead.

---

# 392. Exactly-once execution claim

Even with distributed coordination, external exactly-once remains impossible generally.

---

# 393. Honest guarantee

PyScheduleKit can target:

```text
single durable logical occurrence

single active authoritative attempt where enforceable

recoverable ownership

duplicate-tolerant message delivery
```

---

# 394. Failure classification

Distributed failures introduce:

```text
LeaseLost

ClaimConflict

LeadershipLost

FencingRejected

CoordinationUnavailable
```

---

# 395. These are not target failures

Do not feed them blindly into:

```text
RetryPolicy
```

for business execution.

---

# 396. Coordination retry

A failed claim may simply mean:

```text
another node owns it
```

No error.

---

# 397. Example

```text
ClaimConflict
→ skip item
```

---

# 398. CoordinationUnavailable

DB/lease service unavailable.

Runtime infrastructure error.

---

# 399. FencingRejected

Strong signal:

```text
this owner is stale
```

---

# 400. Owner should stop acting.

---

# 401. LeadershipLost

Not necessarily Runtime FAILED.

Node may remain:

```text
RUNNING as follower
```

---

# 402. Important

```text
RuntimeState RUNNING

LeadershipRole FOLLOWER
```

is normal.

---

# 403. Lease ownership loss during execution

Execution may continue if policy allows?

Dangerous.

---

# 404. V1 distributed recommendation

If an Attempt requires lease ownership:

```text
lease loss
```

should make worker stop/abort when possible.

---

# 405. The attempt may be marked

```text
FAILED(WORKER_OWNERSHIP_LOST)
```

after reconciliation.

---

# 406. Do not create next Attempt immediately until ownership transition is durable.

---

# 407. RetryEvaluator may decide if retryable.

---

# 408. WorkerLost as FailureCategory future

Could map into:

```text
TRANSIENT
```

depending target semantics.

---

# 409. Unknown outcome problem

Worker may lose lease after side effect but before result persistence.

---

# 410. New Attempt could duplicate side effect.

Again:

```text
IdempotencyKey
```

is mandatory for safe retryable external Targets.

---

# 411. Distributed systems keep returning to identity

This is intentional.

---

# 412. Correlation IDs

Distributed traces should propagate:

```text
ScheduleId

OccurrenceKey

RequestId

ExecutionId

AttemptId

NodeId
```

---

# 413. Lease/Fencing diagnostics can add:

```text
ResourceKey

FencingToken
```

---

# 414. Observability example

```text
schedule_id=sched-42
node_id=node-A
claim=acquired
occurrence=2026-10-04T10:00Z
persistence_version=18
```

---

# 415. Worker example

```text
execution_id=exec-7
attempt=2
worker=node-C
lease_token=94
```

---

# 416. Leader example

```text
node=node-B
role=leader
epoch=31
```

---

# 417. Testability

Lease logic should be testable with:

```text
FakeCoordinationClock

InMemoryLeaseStore
```

---

# 418. But concurrency correctness needs real DB integration tests

Same lesson as persistence.

---

# 419. InMemory lease store must emulate atomic CAS semantics

Not simple dict mutation without locking.

---

# 420. Property tests

Useful invariants:

```text
at most one valid lease owner per ResourceKey

fencing token strictly increases

stale owner cannot renew

stale owner cannot release current lease
```

---

# 421. Distributed simulation

A deterministic simulator could model:

```text
Node A pause

Clock advance

Lease expiry

Node B takeover

Node A resume
```

Excellent educational exercise.

---

# 422. Chaos tests later

```text
kill node

pause node

delay DB

duplicate messages

drop notifications
```

---

# 423. Acceptance principle

Correctness should survive:

```text
process death

restarts

duplicate wake-ups

duplicate messages

stale nodes

lease expiry
```

within documented guarantees.

---

# 424. Core distributed invariants

```text
1.
OccurrenceKey remains the canonical automatic
scheduling deduplication identity.

2.
Schedule ownership and ConcurrencyKey ownership
are separate concerns.

3.
Execution ownership and Schedule ownership
are separate concerns.

4.
A claim must be acquired atomically.

5.
A Lease always has a finite expiry.

6.
A stale Lease cannot be renewed after a newer
ownership epoch exists.

7.
FencingToken strictly increases per protected resource.

8.
A stale owner cannot release a newer owner's Lease.

9.
Leader election is not required for ordinary
per-Schedule processing.

10.
Leadership is runtime state, not Schedule state.

11.
Distributed coordination never replaces
database uniqueness.

12.
Database uniqueness never replaces
atomic concurrency admission.

13.
Locks/leases never replace target idempotence.

14.
External dispatch still occurs only after
durable commit.

15.
A node without authoritative persistence access
must fail closed for new scheduling decisions.

16.
Lease expiry is evidence of lost ownership,
not proof that previous side effects never happened.

17.
Retries remain attached to the same Execution
regardless of worker ownership changes.

18.
A new worker may continue durable work
without preserving previous in-memory state.

19.
All critical ownership transfers are observable.

20.
The system never promises universal
exactly-once external side effects.
```

---

# 425. V1/V2 distributed decisions

Recommended first distributed line:

```text
1.
Central SQL database remains authoritative.

2.
Multiple Scheduler nodes are allowed.

3.
Due Schedules are processed using either
row claiming or optimistic competition.

4.
OccurrenceKey uniqueness remains mandatory.

5.
PersistenceVersion protects stale Schedule writes.

6.
Multiple workers claim Executions atomically.

7.
AttemptNumber uniqueness protects retry races.

8.
ConcurrencyKey admission uses a shared
transactional coordination point.

9.
Long-running worker ownership may later use Leases.

10.
Leases use finite expiration.

11.
Lease acquire/renew/release operations are atomic.

12.
Leases use FencingToken when stale ownership
could cause unsafe writes.

13.
Leader election is optional and restricted
to global maintenance responsibilities.

14.
Ordinary Schedule processing remains leaderless
whenever possible.

15.
Polling/signals may wake multiple nodes;
claims determine who performs work.

16.
Lost wake-up signals do not break correctness.

17.
Failed coordination does not become a business retry.

18.
DB/coordination outages stop new authoritative
scheduling mutations.

19.
Node identity is explicit and observable.

20.
Distributed state remains reconstructible
from durable persistence.
```

---

# 426. Recommended coordination stack

For the first serious distributed implementation:

```text
PostgreSQL
│
├── schedules
│     └── PersistenceVersion
│
├── execution_requests
│     └── UNIQUE OccurrenceKey
│
├── executions
│     └── UNIQUE RequestId
│
├── attempts
│     └── UNIQUE ExecutionId + AttemptNumber
│
├── concurrency coordination
│
├── optional leases
│
└── outbox
```

---

# 427. Scheduling claim

Preferred first implementation:

```text
FOR UPDATE SKIP LOCKED
```

or equivalent adapter strategy.

---

# 428. Why?

Because it gives:

```text
short ownership

automatic release on rollback/crash

simple failover

good SQL scalability
```

---

# 429. Worker ownership

For starting Attempts:

```text
short transactional claim
```

first.

Lease only if needed for:

```text
long-running liveness/reconciliation
```

---

# 430. Leadership

Do not introduce until a real leader-only use case appears.

---

# 431. Architecture diagram

```text
                   ┌─────────────────────┐
                   │   Shared Database   │
                   │                     │
                   │ Schedules           │
                   │ Requests            │
                   │ Executions          │
                   │ Attempts            │
                   │ Leases              │
                   │ Outbox              │
                   └──────────┬──────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
      Scheduler A        Scheduler B        Scheduler C
           │                  │                  │
           └─────── claims / versions / uniqueness ──────┘
                              │
                              ▼
                    Durable Requests
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
           Worker A         Worker B         Worker C
              │               │               │
              └──── execution claims / leases ────┘
```

---

# 432. Lease/fencing model

```text
Resource X
   │
   ▼
Node A acquires
token = 41
expires = 10:00:30
   │
   X
lease expires
   │
   ▼
Node B acquires
token = 42
   │
   ▼
Node A wakes
tries token 41
   │
   ▼
REJECTED AS STALE
```

---

# 433. Leader model

```text
Nodes
 A   B   C
 │   │   │
 └───┼───┘
     ▼
Leader Lease
     │
     ├── A token 7 → expires
     │
     └── B token 8 → current leader
```

---

# 434. Distributed concurrency model

```text
Schedule S1 ──┐
              │
              ▼
      ConcurrencyKey K
              │
              │ limit = 1
              │
              ▼
       Atomic Coordinator
          │         │
          ▼         ▼
        ADMIT      WAIT
          │
          ▼
      Execution
```

---

# 435. Complete distributed flow

```text
TIME
 │
 ▼
Multiple Scheduler Nodes
 │
 ▼
Candidate discovery
 │
 ▼
Claim / Version Check
 │
 ▼
Occurrence Planning
 │
 ▼
OccurrenceKey uniqueness
 │
 ▼
Concurrency coordination
 │
 ▼
ExecutionRequest
 │
 ▼
COMMIT + Outbox
 │
 ▼
Multiple Workers
 │
 ▼
Execution Claim
 │
 ▼
Attempt
 │
 ▼
Optional Worker Lease
 │
 ▼
Target
```

---

# 436. Mental model

The system should not ask:

```text
"Which server owns the scheduler?"
```

as its first question.

It should ask:

```text
"Which durable resource is currently being acted on,
and what mechanism prevents incompatible actors
from acting authoritatively at the same time?"
```

---

# 437. Core lesson

Distributed scheduling correctness comes from combining:

```text
Durable identity

Atomic persistence

Deduplication

Short claims

Leases where necessary

Fencing where stale owners matter

Idempotency at side-effect boundaries
```

---

# 438. What Leader Election does not solve

It does not automatically solve:

```text
duplicate messages

worker retries

cross-Schedule concurrency

external side effects

request deduplication

transaction atomicity
```

---

# 439. What Lease does not solve

It does not automatically solve:

```text
stale external writes

duplicate side effects

business idempotence
```

without fencing/idempotency.

---

# 440. What unique keys do not solve

They do not automatically solve:

```text
ownership

capacity admission

worker liveness
```

---

# 441. Therefore

The architecture must use the right primitive for the right invariant.

---

# 442. Definition — Distributed Coordinator

> **A distributed coordination mechanism is infrastructure that allows independent runtime nodes to establish temporary, enforceable ownership or admission decisions over shared durable resources.**

---

# 443. Definition — Lease

> **A Lease is a time-bounded ownership grant that becomes invalid when it expires or is superseded.**

---

# 444. Definition — FencingToken

> **A FencingToken is a monotonically increasing ownership epoch used by protected resources to reject actions from stale owners.**

---

# 445. Definition — Leader Election

> **Leader Election selects one temporary owner for a global exclusive runtime responsibility; it is not required for ordinary work that can instead be claimed independently.**

---

# 446. Acceptance criteria

Le modèle distribué est suffisamment défini si l'on peut répondre précisément à :

```text
Pourquoi plusieurs scheduler nodes peuvent-ils
voir la même occurrence ?

Quelle protection empêche sa double matérialisation ?

Quelle différence entre row claim et Lease ?

Pourquoi une Lease doit-elle expirer ?

Pourquoi une Lease seule n'est-elle pas toujours sûre ?

Qu'est-ce qu'un FencingToken ?

Comment protège-t-il d'un stale owner ?

Pourquoi Schedule ownership et ConcurrencyKey
sont-ils deux problèmes différents ?

Comment deux workers évitent-ils de démarrer
le même Attempt ?

Que se passe-t-il si un worker crash
pendant une longue Attempt ?

Pourquoi une Lease ne garantit-elle pas
exactly-once side effects ?

Quand Leader Election est-elle nécessaire ?

Pourquoi ne faut-il pas forcément un leader
pour traiter les Schedules ?

Que se passe-t-il après la perte du leader ?

Quelle horloge doit piloter l'expiration
d'une Lease distribuée ?

Comment gérer le clock skew ?

Qu'est-ce qu'un split brain ?

Comment empêcher un ancien leader de continuer
à écrire après failover ?

Pourquoi les claims doivent-ils être courts ?

Pourquoi faut-il continuer à utiliser
OccurrenceKey et RequestId en présence de locks ?

Que fait un node qui perd l'accès
au store autoritatif ?
```

---

# 447. Roadmap d'implémentation distribuée

## Étape 1 — Baseline locale

```text
single scheduler
single worker
```

---

## Étape 2 — Multi-worker

```text
atomic Execution claiming
Attempt uniqueness
```

---

## Étape 3 — Multi-scheduler

```text
Schedule row claiming
PersistenceVersion
OccurrenceKey uniqueness
```

---

## Étape 4 — Distributed concurrency

```text
ConcurrencyKey serialization
atomic admission
```

---

## Étape 5 — Worker leases

```text
long-running Attempt ownership
heartbeat
expiry
```

---

## Étape 6 — Fencing

```text
stale owner protection
```

pour ressources compatibles.

---

## Étape 7 — Leader-only maintenance

```text
LeaderElectionPort
LeadershipEpoch
```

---

## Étape 8 — Partitioning / Sharding

```text
large-scale distribution
```

seulement si réellement nécessaire.

---

# 448. Conclusion

PyScheduleKit peut être distribué sans transformer tout le framework en système de consensus.

La clé est de distinguer correctement :

```text
Occurrence deduplication

Schedule claiming

Execution claiming

Concurrency admission

Lease ownership

Leader election

Target idempotency
```

La chaîne de protection devient :

```text
Stable Identity
      │
      ▼
Database Uniqueness
      │
      ▼
Optimistic Version / Claim
      │
      ▼
Lease when ownership outlives transaction
      │
      ▼
Fencing when stale owners are dangerous
      │
      ▼
Idempotency at external side effects
```

Le principe architectural essentiel est :

> **Utiliser la coordination distribuée la plus petite possible pour l'invariant à protéger.**

Ainsi :

```text
un Schedule
```

n'a pas besoin d'un leader global ;

```text
une Execution
```

n'a pas besoin d'un lock SQL pendant toute sa durée ;

```text
une Lease
```

n'a pas besoin de remplacer les unique constraints ;

et :

```text
Leader Election
```

ne doit pas devenir une solution générique à tous les problèmes de concurrence.

Le modèle recommandé privilégie donc :

```text
short transactional claims

durable identities

idempotent state transitions

leases only when necessary

fencing for stale ownership

leaderless parallelism whenever possible
```

Cette approche permet de passer progressivement de :

```text
1 Scheduler Node
```

à :

```text
N Scheduler Nodes

+

N Workers
```

sans modifier la signification métier de :

```text
Schedule

Occurrence

ExecutionRequest

Execution

Attempt
```

---

# Suite documentaire

La prochaine étape logique est :

```text
21_OBSERVABILITY_AUDIT_EVENTS_AND_DIAGNOSTICS_MODEL.md
```

Elle pourra consolider :

```text
Domain Events

Runtime Events

Audit Trail

SchedulingDecision evidence

Execution history

CorrelationId

TraceId

metrics

structured logs

diagnostics

distributed ownership evidence

failure diagnostics

SLO / lag indicators
```

et répondre à la question :

> **Comment expliquer précisément ce que PyScheduleKit a décidé, quand, pourquoi, sur quel nœud, et avec quelles preuves ?**

Puis :

```text
22_PUBLIC_API_AND_CONFIGURATION_MODEL.md
```

pour transformer progressivement tout ce domaine en contrats utilisables par les développeurs.