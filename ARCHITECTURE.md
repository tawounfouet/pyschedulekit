# Architecture — PyScheduleKit

> Document de référence technique : comment le système est construit et comment les données circulent. Les jugements de valeur sont dans [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md) ; les faits d'exécution dans [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md).

---

## 1. Vue système

```
   Application hôte (processus du consommateur)
   ┌────────────────────────────────────────────────────────────────────┐
   │  import pyschedulekit as psk                                       │
   │  scheduler = psk.Scheduler(clock=..., uow_factory=...)             │
   │  scheduler.add_schedule(target=..., trigger=...)                   │
   │  scheduler.run_pending()  — ou —  scheduler.run_forever()          │
   └──────────────┬─────────────────────────────────────────────────────┘
                  │ api/  (surface stable, manifeste _manifest.py)
   ┌──────────────▼─────────────────────────────────────────────────────┐
   │ application/                                                       │
   │  SchedulerEngine.evaluate ──► RunPendingService.run_pending        │
   │       │ matéria.          │ admissions        │ claims             │
   │       ▼                   ▼                   ▼                    │
   │  MaterializationLease  AdmissionLock    ExecutionClaim (fencing)   │
   │  Coordinator           Coordinator       Coordinator + Heartbeat   │
   │                                                │                   │
   │                                    ExecutionRunner ──► Executor    │
   │                                    (retry, cancellation)    │      │
   │  Recovery · Reconciliation · Outbox · Retention · WakeUp · Runtime │
   └───────┬───────────────────────────────┬───────────────────┬────────┘
           │ ports/ (Protocoles)           │                   │
   ┌───────▼──────────────┐  ┌─────────────▼──────────┐  ┌─────▼──────────┐
   │ UnitOfWorkFactory    │  │ Clock                  │  │ Executor       │
   │  ├ SQLite (2 018 LOC)│  │  SystemClock /         │  │  Local (py)    │
   │  └ InMemory (1 441)  │  │  MutableClock (tests)  │  │  HTTP          │
   │ Persistence/Outbox/  │  │ CancellationController │  │  Routing       │
   │ Observability ports  │  │ ObservationSink        │  └────────────────┘
   └───────┬──────────────┘  └────────────────────────┘
           │
   ┌───────▼───────────────────┐   ┌────────────────────────────────────┐
   │ fichier SQLite            │   │ Registres de confiance (process)  │
   │ 8 tables + pyschedulekit_ │   │  PythonTargetRegistry (callables) │
   │ schema (version 8)        │   │  HttpTargetRegistry (HttpRequest) │
   │ PRAGMA foreign_keys=ON    │   └────────────────────────────────────┘
   └───────────────────────────┘
```

**Topologie de déploiement réelle :**

| Composant | Hébergement | Particularité |
|---|---|---|
| Paquet `pyschedulekit` | PyPI (Trusted Publishing OIDC), version `0.1.0a3` | Wheel/sdist, **0 dépendance runtime**, Python ≥ 3.11 |
| Processus d'exécution | **chez le consommateur** (aucun serveur fourni) | Un ou N travailleurs ouvrant le même fichier SQLite |
| CI qualité | GitHub Actions `ci.yml` (push/PR), matrice 3.11-3.13 | `ruff check → ruff format --check → mypy src → pytest --cov` |
| Qualification | `distribution.yml` : wheel+sdist, clean-install, smoke hors arbre | Empêche de tester l'arbre source par accident |
| Release | tag `v*` → qualification → PyPI Trusted Publishing → vérification → GitHub Release/provenance | `v0.1.0a3` est publié en prerelease immutable ; TestPyPI n'est pas obligatoire dans le chemin de go-live final |

---

## 2. `pyschedulekit` (package principal)

### 2.1 Organisation

Couches strictes, imports uniquement vers le bas (`domain → application → ports → infrastructure → api`), **verrouillées par test** : `tests/architecture/test_domain_boundaries.py:55-84` fait échouer la CI si `domain/` importe une couche supérieure, appelle `datetime.now`/`date.today`/`time.sleep` ou lit `os.getenv`. L'heure n'entre que par injection `Clock`.

```text
src/pyschedulekit/
├── domain/           pur : time, trigger(s), schedule, occurrence,
│                     execution, retry, claim, concurrency, misfire, outbox
├── application/      orchestration : scheduler_engine, run_pending, execution_runner,
│                     execution_service, claims, concurrency, recovery,
│                     reconciliation, outbox, retention, wakeup, runtime, shutdown
├── ports/            Protocoles : persistence, executor, time, cancellation,
│                     observability, outbox, runtime
├── infrastructure/   sqlite, sqlite_schema, memory, local_executor, http_executor,
│                     routing_executor, time (SystemClock), cancellation (token), …
├── api/              Scheduler (façade), _manifest (STABLE_PUBLIC_NAMES)
├── experimental/     claims, admission tokens, lateness — sans promesse avant 1.0
└── testing/          MutableClock, FixedClock, triggers de test
```

Conventions de câblage réelles :

- La façade `api/scheduler.py::Scheduler` compose tout : `Clock`, `UnitOfWorkFactory`, registres d'exécuteurs, coordinators de claims/admission/matérialisation, `Runtime` (`run_forever`), `CancellationController`. Ligne de vie : construire une fois, `run_pending`/`run_forever` appeler par la suite.
- Chaque mutation d'agrégat domaine passe par des assertions d'invariants (`Execution._assert_invariants`, `domain/execution.py:598-628`) — un état illégal lève `ValueError` avant persistance.
- **Deux adaptateurs de persistance qualifiés par un contrat observable partagé** (SQLite + InMemory) implémentent le même protocole `UnitOfWork` : identity map + write set + validation de version + rollback. Les tests de parité forcent désormais les mêmes sémantiques de référentiel, staged state, conflits et rollback.
- `InvalidExecutionTransitionError` reste distinct de `PersistenceConflictError`, mais `run_pending` traite explicitement une transition devenue invalide par concurrence : claim non démarré libéré, erreur structurée `execution.transition`, cycle conservé.

### 2.2 Cycle de vie d'un cycle — `RunPendingService.run_pending()`

```text
scheduler.run_pending(limit)
 │
 ├─ 0. shutdown demandé ? ──────────────► résultat vide (run_pending.py:127)
 ├─ 1. recovery distribué incomplet ? ──► CrashRecoveryIncompleteError (:141)
 ├─ 2. SchedulerEngine.evaluate(now) ───► découvre les schedules dus
 │      ├─ matérialisation sous lease (MaterializationLeaseCoordinator)      (:107)
 │      ├─ déclenchement : trigger.next + misfire policy
 │      ├─ création des ExecutionRequest (dédoublonnée par OccurrenceKey)
 │      └─ pause/cancel/conflict des schedules → schedule_conflicts
 ├─ 3. admissions (ConcurrencyCoordinator.admit) ──► WAITING_ADMISSION→QUEUED
 │      └─ sous ScheduleAdmissionLock ; conflit → RunPendingError, pas de crash
 ├─ 4. list_runnable (QUEUED + RETRY_WAIT échu)
 │      └─ pour chacune : ExecutionClaimCoordinator.acquire (fencing generation)
 │            ├─ refusé → claim_denied
 │            └─ acquis → ExecutionRunner.run
 │                  ├─ shutdown.try_enter / _load_execution / executor.prepare
 │                  ├─ start_attempt (transaction) ──⚠ InvalidExecutionTransitionError
 │                  ├─ heartbeat de lease pendant l'exécution
 │                  ├─ executor.execute(timeout, token, fencing, idempotency_key)
 │                  └─ succeed / cancel / timeout|fail (+ RetryEvaluator → RETRY_WAIT)
 └─ 5. RunPendingResult{executions, admissions, errors, claim_denied, …}
       + observer.record("…")  ──  aucun sleep : la boucle appartient à runtime
```

`runtime.run_forever` boucle : `run_pending` → `WakeupPlanner.next_delay(max_sleep)` → `EventLoopWaiter.wait(wake_event)`. Une boundary de supervision entoure chaque cycle : une exception isolée produit `runtime.cycle.error`, applique un backoff borné par `max_sleep`, puis le runtime poursuit tant qu'aucun stop n'est demandé.

### 2.3 Flux métier clés

**(a) Occurrence → exécution (le flux nominal)**

```text
Scheduler.add_schedule ─► registre local compensable ─► UoW.schedules.add + commit
   └─ si création/commit échoue : unregister exact du callable ajouté
clock avance ─► evaluate ─► ExecutionRequest(PENDING) ─► admit ─► QUEUED
run_pending ─► claim(worker, generation) ─► start_attempt(RUNNING)
   ─► Executor.execute ─► Attempt terminal ─► Execution SUCCESS/FAILED/…
   ─► outbox_messages (attempt.completed) ─► dispatch_outbox() côté utilisateur
```

**(b) Annulation / retry — LOT-17 « cancellation always wins »**

```text
cancel_execution ─► domain: request_cancellation(RUNNING) + token posé (process-local)
   ├─ exécuteur coopératif ─► outcome CANCELLED ─► cancel_attempt ─► CANCELLED
   └─ timeout / non coopératif
          ├─ LocalExecutor normalise cancellation si le token est déjà annulé
          └─ Execution.finish_attempt interdit RETRY_WAIT si cancellation demandée
                 ↓
              état terminal, aucune relance
```

La protection existe à deux niveaux : normalisation infrastructure et backstop durable
dans l'agrégat `Execution`.

**(c) Multi-travailleurs — claims et fencing**

```text
Worker A                                Worker B
list_runnable ─► claim(exec, gen=3)     list_runnable ─► claim(exec)
   │  INSERT … ON CONFLICT refusé ────────► claim_denied            (course gagnée)
   ├─ heartbeat toutes les ttl/3
   ├─ génération portée en header/fencing token sur toute écriture
   └─ lease perdue (heartbeat.lost) ─► ClaimOwnershipError ─► abandon, pas d'écriture
```

⚠️ L'annulation, elle, **n'est pas** coordonnée entre workers : le token est process-local (`api/scheduler.py:379`) et `list_runnable` ne filtre pas `cancellation_requested_at` (`sqlite.py:785`) — voir [ANALYSE_CRITIQUE.md §3.2](./ANALYSE_CRITIQUE.md).

**(d) Recovery après crash**

```text
worker stoppe net ─► leases expirées, exécutions bloquées en RUNNING
recover() ─► ReconciliationService : RUNNING sans claim actif → re-queued / fail
recovery distribué en tête de chaque cycle (run_pending.py:138-141)
```

---

## 3. Modèle de données

```text
schedules ─1:N─► execution_requests ─1:1─► executions ─1:N─► attempts
   │  (:49 RESTRICT)      (get_by_request)   (79 RESTRICT)     (115 RESTRICT)
   │
   ├──1:1── schedule_admission_locks      (215, CASCADE)   verrou d'admission/worker
   ├──1:1── schedule_materialization_leases (241, CASCADE) lease de matérialisation
   └──     executions ─1:1── execution_claims (190, CASCADE) claim actif/released + fencing
              │
              └──1:N── outbox_messages   (table indépendante, payload JSON
                                          enrichi des relations ; publié par
                                          dispatch_outbox hors transaction)
```

Points clés :

- **Types d'identifiants** : `ScheduleId`, `RequestId`, `ExecutionId`, `AttemptId` — wrapper `str` auto-incrémentés, uuid4 générés par `add_schedule` si absent (`api/scheduler.py:270`).
- **Horodatages** : `Instant` domaine sérialisés en ISO-8601 UTC ; l'heure système n'est lue que par `SystemClock` (`infrastructure/time.py:14`), injectée partout ailleurs.
- **Versionnement optimiste** : colonne `version` sur les entités + `PersistenceVersion` avant `apply` → `PersistenceConflictError` en cas d'écriture perdue ; `BEGIN IMMEDIATE` sur toute écriture SQLite (`sqlite.py:1951`).
- **Snapshot & dénormalisation** : `policy_snapshot`/`target`/`occurrence_key` copiés dans `execution_requests`/`executions` — une exécution reste exécutable même si le schedule change ou disparaît (`ON DELETE RESTRICT` sur `schedules→requests`).
- **Aucun champ sensible** : pas de secret, pas de donnée personnelle, pas d'env var lue (`os.getenv` interdit dans `domain/`). Le `.env` local observé pendant l'audit n'est pas tracké et ne fait pas partie du contrat runtime.
- **Intégrité référentielle** : SQLite active ses contraintes FK et l'adaptateur InMemory reproduit les mêmes effets observables via la contract suite de persistance.

---

## 4. Interface / surface consommateur

Pas d'UI ni de CLI : l'interface est l'API publique.

- **Façade stable** : `api/scheduler.py::Scheduler` — ciblage (`register_target`, `register_http_target`, `add_schedule`), pilotage (`pause/resume/cancel_schedule`, `cancel_execution`), exécution (`run_pending`, `run_forever`, `stop`, `shutdown`), opérations (`recover`, `reconcile`, `dispatch_outbox`, `cleanup`), observation (`inspect_*`, `health`, `readiness`, `last_*`, `cycles_completed`). L'ensemble des noms exportés est gelé par `api/_manifest.STABLE_PUBLIC_NAMES` + test `tests/unit/api/test_public_api_contract.py`.
- **Erreurs** : arbre unique dans `errors.py` + exceptions métier par couche (`DuplicateScheduleError`, `PersistenceConflictError`, `InvalidExecutionTransitionError`, `ClaimOwnershipError`, …) ; les anciens noms racine émettent `DeprecationWarning` et redirigent (`__init__.py:105-119`).
- **`experimental/`** : claims/admission/`LatenessStatus` — imports explicites, **aucune promesse de compatibilité** avant 1.0.
- **`testing/`** : `MutableClock`, `FixedClock`, triggers de test — les consommateurs doivent piloter le temps avec ces helpers plutôt que de monkeypatcher `datetime`.
- **Persistance côté utilisateur** : aucun localStorage/cookie ; seule la config du constructeur `Scheduler(...)` et le fichier SQLite (chemin choisi par l'appelant) persistent.

---

## 5. Conventions transverses à connaître

| Sujet | Convention |
|---|---|
| Temps | Jamais `datetime.now` dans `domain/` ni `application/` : toujours l'`Clock` injectée ; tests avec `MutableClock` |
| Écritures | Une mutation = une UnitOfWork : `validate → apply → commit()`, rollback systématique en sortie de contexte |
| Conflits | `PersistenceConflictError` = rejeu possible ; `InvalidExecutionTransitionError` = état illégal (à ne pas confondre, B2) |
| Identité des exécutions | `OccurrenceKey(schedule_id, schedule_revision, scheduled_at)` = clé de déduplication des matérialisations |
| Multi-workers | Toute écriture d'exécution porte la `generation` de claim (fencing) ; expiration = rejeu, jamais de reprise silencieuse |
| Cibles exécutées | Registres **opt-in manuels** uniquement — jamais d'exécution d'un callable/URL non enregistré |
| Observabilité | `Observer.record(...)` sur chaque étape (cycle, attempt, claim) — pas de logging obligatoire, pas d'`os.getenv` |
| pre-commit | Hooks `language: system` : les dev deps doivent être installées dans l'environnement actif |
| Version | Source unique `src/pyschedulekit/_version.py` ; `tests/test_package.py:11` la compare **au mot près** aux métadonnées installées |
| Tests release | Chemins `.github/workflows/...` **relatifs** → pytest uniquement depuis la racine |

---

## 6. Limites structurelles actuelles

Les findings B1–B12 de l'audit ont été remédiés ; leur historique reste dans les documents
snapshot et leur disposition dans
[POST-00 Remediation Status](./docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md).

Les limites encore structurelles sont différentes :

1. **Cancellation inter-processus** — le token de coopération reste process-local. L'intention
   d'annulation est durable, mais un callable déjà exécuté dans un autre processus ne reçoit
   pas magiquement le token du processus appelant.
2. **Arrêt forcé d'un callable Python** — le runtime synchrone utilise un worker thread pour
   reprendre le contrôle au timeout ; Python ne fournit pas de terminaison sûre d'un thread
   arbitraire. Les workloads doivent donc être idempotents et, si possible, coopératifs.
3. **Persistance durable** — SQLite est le backend durable qualifié actuel. PostgreSQL n'est
   pas encore implémenté ; le contrat de parité créé pendant POST-00 doit servir de porte
   d'entrée au futur adapter.
4. **Exécution asynchrone** — les callables `async def` sont encore explicitement rejetés par
   le LocalExecutor synchrone.
5. **Registres de cibles process-local** — Python/HTTP targets restent des objets de confiance
   enregistrés dans le processus hôte ; seule leur référence déclarative est persistée.
6. **Surface alpha** — `0.1.x` reste une série alpha. La stabilité `1.0` (migrations,
   compatibility policy, long-term SemVer guarantees) n'est pas encore promise.

Ces limites appartiennent à la Phase II / trajectoire vers `1.0`, pas au périmètre de
correction de `0.1.0a4`.
