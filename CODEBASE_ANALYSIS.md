# Analyse de la codebase — PyScheduleKit

> **AUDIT SNAPSHOT — 2026-10-08.** Ce document conserve volontairement les faits,
> métriques et findings tels qu'ils ont été observés pendant l'audit. Il n'est pas
> réécrit après chaque correction. Pour l'état courant et la disposition B1–B12, voir
> [POST-00 Remediation Status](./docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md).

> Analyse réalisée le 2026-10-08. Périmètre : `src/pyschedulekit` (64 fichiers Python, 13 740 LOC), `scripts/`, `tests/`, `.github/workflows/`, `docs/` ; la sécurité, les bugs confirmés et la dette technique.

---

## 1. Vue d'ensemble

PyScheduleKit est une **bibliothèque Python de planification** (aucun serveur, aucune dépendance runtime) conçue comme projet d'apprentissage rigoureux d'un domaine de scheduling : temps, triggers, schedules, occurrences, exécutions, retries, persistance, récupération et coordination multi-travailleurs. Le code est structuré en couches DDD (`domain` → `application` → `ports` → `infrastructure` → `api`).

| Package | Stack | LOC | Rôle |
|---|---|---|---|
| `src/pyschedulekit/domain/` | Python 3.11+ pur | 3 023 | Modèle pur : temps, triggers, schedules, exécutions, politiques. Aucune I/O. |
| `src/pyschedulekit/application/` | Python pur | 3 407 | Orchestration : moteur de planification, run_pending, claims, recovery, outbox. |
| `src/pyschedulekit/infrastructure/` | Python + `sqlite3` stdlib | 5 390 | Adaptateurs : SQLite (2 018 LOC), mémoire (1 441), exécuteurs local/HTTP/routing. |
| `src/pyschedulekit/ports/` | Protocoles | ~550 | Interfaces persistence, executor, clock, observabilité, runtime. |
| `src/pyschedulekit/api/` | Python | 1 464 | Surface publique stable : façade `Scheduler`, `_manifest.STABLE_PUBLIC_NAMES`. |
| `src/pyschedulekit/testing/` | Python | ~150 | Helpers livrés (`MutableClock`, `FixedClock`, triggers de test). |
| `scripts/` | Python | 331 | Outils release : preflight, verify_distribution, verify_release_candidate, smoke. |
| `tests/` | pytest | 11 420 | 453 tests : 32 fichiers unit, 25 integration, 18 e2e, 1 architecture. |

**Caractéristiques générales :**

- **Single-package**, pas de monorepo : racine = le projet, `src/` = seul paquet (`pyproject.toml:49`).
- **Dépendances runtime : 0** (`pyproject.toml:28` `dependencies = []`). Dev : mypy, pre-commit, pytest, pytest-cov, ruff. Release : build, twine.
- **Type-check strict** : `mypy --strict` sur `src/` uniquement (`pyproject.toml:95`), PEP 561 (`py.typed`).
- **Lint/format** : ruff (règles E,F,I,UP,B,SIM,RUF, ligne 100) — `pyproject.toml:73-91`.
- **CI** : 4 workflows (ci, distribution, release-candidate, release-readiness), matrice Python 3.11/3.12/3.13 (`.github/workflows/ci.yml:27-31`).
- **Couverture** : 86 % mesurés (`pytest --cov=pyschedulekit`, TOTAL 6 238 instructions / 636 manquantes), **sans seuil `fail_under`** (`pyproject.toml:65-71`).
- **Vérifications exécutées pour cet audit** : `ruff check .` ✅ · `mypy src` ✅ · `pytest` ✅ 453 tests en 1,63 s · `ruff format --check .` ❌ **échec** (voir B3).
- **État CI (GitHub, vérifié par `gh run list`)** : workflow *CI* sur `main` **en échec** (run 37791859372), *Release Candidate Gate* **en échec** sur `v0.1.0a3` (run 37792035140) et sur `v0.1.0a2`.
- **200 fichiers trackés** ; `docs/implementation/` (35 fichiers LOT) + `docs/release/` (7 fichiers REL) versionnés, **`docs/specs/` (26 fichiers) NON versionnés** (voir B12).
- **Histoire git** : 0 secret codé en dur détecté (scan `git rev-list --all` sur motifs `api_key|secret|password|token`, aucun fichier concerné).

---

## 2. Architecture

```
                      ┌──────────────────────────────────────────────┐
   Consommateur       │  pyschedulekit.api  (surface stable,         │
   applicative ───────┼─► manifeste _manifest.STABLE_PUBLIC_NAMES)   │
                      │      Scheduler  (façade, api/scheduler.py)  │
                      └───────┬──────────────────────────────────────┘
                              │ appels
   ┌──────────────────────────▼──────────────────────────────────────┐
   │ application/   SchedulerEngine · RunPendingService ·           │
   │                ExecutionRunner · Claims/Admission/Materialization│
   │                · Recovery · Reconciliation · Outbox · Runtime   │
   └───────┬──────────────────────────────────────┬─────────────────┘
           │ ports (Protocoles)                   │ injection Clock
   ┌───────▼───────────────┐        ┌─────────────▼──────────────────┐
   │ ports/persistence     │        │ ports/time (Clock)             │
   │ ports/executor        │        │ ports/cancellation, observability│
   └───────┬───────────────┘        └─────────────┬──────────────────┘
           │ impl.                                 │ impl.
   ┌───────▼────────────────────┐    ┌─────────────▼──────────────────┐
   │ infrastructure/            │    │ SystemClock (datetime.now(UTC))│
   │  SqliteUnitOfWorkFactory   │    │ EventLoopWaiter, Observers     │
   │  InMemoryUnitOfWorkFactory │    └────────────────────────────────┘
   │  LocalExecutor · HttpExecutor · RoutingExecutor                 │
   └───────┬────────────────────┘
           │
   ┌───────▼───────────┐   ┌──────────────────────┐
   │ fichier SQLite    │   │ registres de cibles  │
   │ (8 tables +       │   │ PythonTargetRegistry │
   │  schema version)  │   │ HttpTargetRegistry   │
   └───────────────────┘   └──────────────────────┘
```

Aucune topologie de déploiement serveur : le produit est un **paquet wheel/sdist publié sur PyPI** (`.github/workflows/distribution.yml`, `release-candidate.yml`), exécuté **dans le processus** de l'application consommatrice.

### 2.1 `src/pyschedulekit/domain/` — particularité structurante

Domaine **pur et vérifié par test d'architecture** : `tests/architecture/test_domain_boundaries.py:55-65` interdit tout import `application|infrastructure|ports|api|runtime`, et `:68-84` interdit `datetime.now`/`date.today`/`time.sleep`/`os.getenv`. L'heure n'entre que par injection `Clock`. Toute mutation d'agrégat passe par des assertions d'invariants (`_assert_invariants`, ex. `domain/execution.py`).

### 2.2 `src/pyschedulekit/infrastructure/` — particularité structurante

Deux adaptateurs de persistance **à parité contractuelle manuelle** (in-mémoire `memory.py` 1 441 LOC vs SQLite `sqlite.py` 2 018 LOC) : les mêmes sémantiques (identity map, write set, validation version `PersistenceVersion` avant apply) sont réimplémentées deux fois — source des bugs B8/B9. SQLite utilise `BEGIN IMMEDIATE` + « validate puis apply » (`sqlite.py:1951-1967`) et des contraintes FK déclarées (`sqlite_schema.py:49,79,115`).

### 2.3 Topologie de déploiement réelle

| Composant | Hébergement | Particularité |
|---|---|---|
| Paquet `pyschedulekit` | PyPI (Trusted Publishing OIDC) | Version unique `0.1.0a3` (`src/pyschedulekit/_version.py`) |
| CI qualité | GitHub Actions, push `main` + PR | Échoue actuellement (B3) |
| Qualification distribution | GitHub Actions (`distribution.yml`) | wheel+sdist, matrice clean-install, smoke hors arbre source |
| Release | GitHub Actions (`release-candidate.yml`) | job `create-github-release` cassé (B4) |

---

## 3. Inventaire des surfaces publiques / routes

Équivalent « endpoints » d'une bibliothèque = la surface exportée et les points d'extension confiants. Modèle de confiance vérifié : **aucune authentification réseau** ; la sécurité repose sur des **registres de cibles explicites** (le code exécuté doit être enregistré à la main) et sur la validation en entrée du domaine.

| Surface | Entrées notables | Modèle de confiance |
|---|---|---|
| `pyschedulekit.api` (façade `Scheduler`) | `add_schedule`, `run_pending`, `run_forever`, `cancel_execution`, `recover`, `reconcile`, `dispatch_outbox`, `cleanup`, `health`, `pause/resume/cancel_schedule` (`api/scheduler.py`) | Stable et contractuel (manifeste) ; exceptions typées propagées à l'appelant |
| **`Scheduler.run_forever`** | boucle continue, aucune garde d'exception (`application/runtime.py:103-104`) | **Voir B2** — une exception non rattrapée tue la boucle |
| **`Scheduler.add_schedule`** | enregistre la cible avant commit (`api/scheduler.py:271`, `:630` vs commit `:302`) | **Voir B7** |
| Registre Python `PythonTargetRegistry` | callables enregistrés à la main (`infrastructure/local_executor.py:39-82`) | Confiance explicite : signature validée, async rejeté |
| Registre HTTP `HttpTargetRegistry` | `HttpRequestSpec` validées : scheme http(s), pas d'identifiants URL, anti-CRLF (`infrastructure/http_executor.py:52-76`) | Confiance explicite + validation ; **voir §4 (redirections)** |
| Exécuteurs (routing) | `python`, `http`, extensible (`infrastructure/routing_executor.py`) | Le routing dépend du `TargetRef.kind` persisté |
| Ports `UnitOfWorkFactory`, `Clock`, `ObservationSink` | injection par le consommateur (`api/_manifest.py:87,92`) | Contractuel (manifeste), testable (`testing/` fournit les clocks) |
| `pyschedulekit.experimental` | claims, admission locks, `LatenessStatus` (`experimental/__init__.py:1-31`) | **Sans promesse de compatibilité** avant 1.0 ; anciens noms racine redirigés avec dépréciation (`__init__.py:105-119`) |
| `pyschedulekit.testing` | `MutableClock`, `FixedClock`, triggers (`testing/time.py`) | Helpers livrés pour le consommateur |

---

## 4. Sécurité — vulnérabilités

### 🔴 Critiques

Aucune. Vérifié : aucun secret en clair dans le code ni dans l'historique git (scan complet), aucune surface réseau exposée par défaut (bibliothèque intégrée au processus hôte), aucune dépendance runtime, domaine interdit `os.getenv` (test d'architecture).

### 🟠 Élevées

Aucune confirmée. Le modèle de confiance est explicite et testé (validation URL/entêtes, registres opt-in, fencing des claims).

### 🟡 Moyennes

- **Fichier `.env` orphelin à la racine** : contient une clé `API_TOKEN` mais **aucun code du projet ne lit l'environnement** (`grep getenv|environ` vide dans `src/`, `scripts/`, `tests/`). Il est bien ignoré par `.gitignore:49-52` (règle `.env` à la ligne 50) et non tracké — néanmoins sa présence est une source d'accident (commit accidentel si la règle d'ignore change, confusion sur un secret « qui existe » alors qu'il est inexploité). Risque : exposition future d'un jeton si un contributeur le committe « pour dépanner ». *(Aucune valeur n'est reprise dans ce document.)*
- **Suivi de redirections HTTP sans contrôle** : `HttpExecutor` délègue à `urllib.request.urlopen` (`infrastructure/http_executor.py:161`) qui suit les redirections par défaut, sans limite ni blocage d'hôte interne. Si un `HttpRequestSpec` enregistré est redirigé vers `169.254.169.254`/réseau local, la requête suit. La cible doit être enregistrée manuellement (modèle de confiance) — durcissement manquant, pas exploitable anonymement.

---

## 5. Bugs confirmés (reproductibles par lecture du code)

| # | Fichier:ligne | Bug |
|---|---|---|
| B1 | `domain/execution.py:520-527` + `application/execution_runner.py:166-191` + `infrastructure/local_executor.py:186-187` | **Une annulation pendant l'exécution ne gagne pas face au retry**, contre la garantie documentée « Cancellation always wins over retry » (`docs/implementation/LOT-17_CANCELLATION_REFINEMENTS.md:115`). Chaîne vérifiée : (a) le chemin timeout du `LocalExecutor` renvoie `_timeout_outcome()` **sans tester le token** (`local_executor.py:186-187`, alors que `:153-154` et `:193-194` le font) ; (b) le runner passe alors au branchement retry sans jamais consulter `execution.cancellation_requested` (`execution_runner.py:167-191`) ; (c) `finish_attempt(retry_at=...)` place l'exécution en `RETRY_WAIT` sans regarder `_cancellation_requested_at` (`execution.py:520-527`) ; (d) le `finally` **libère le token** (`execution_runner.py:216` → `infrastructure/cancellation.py:54-56` le supprime) ; (e) `list_runnable` ne filtre pas sur la cancellation (`infrastructure/sqlite.py:785-790`, `memory.py:603-631`), `start_attempt` non plus (`execution.py:467-482`), et `token_for` minte un **token neuf non annulé** (`cancellation.py:38-44`). Effet réel : sur un schedule avec `RetryPolicy(max_attempts>1)` (config normale), l'exécution annulée **relance le travail avec effets de bord dupliqués** et peut finir `SUCCESS`. Aucun test ne couvre ce scénario (les 3 tests de `tests/integration/application/test_cancellation_control.py:54,71,125` et `tests/e2e/test_cancellation_e2e.py:30` testent l'annulation coopérative ou l'annulation depuis `RETRY_WAIT`). |
| B2 | `application/run_pending.py:194-224` + `application/runtime.py:103-104` | **`InvalidExecutionTransitionError` n'est pas rattrapée dans `run_pending`** alors qu'une annulation concurrente peut faire passer une exécution listée comme `QUEUED` en `CANCELLED` entre la sélection (`run_pending.py:172`) et `start_attempt` (`execution.py:467-471` lève l'exception). `InvalidExecutionTransitionError(ValueError)` (`domain/execution.py:19`) n'est **pas** une sous-classe de `PersistenceConflictError(RuntimeError)` (`ports/persistence.py:20`) : aucun des `except` de `run_pending.py:194,196,199,208,217` ne l'attrape. L'exception remonte dans la boucle `run_forever` qui n'a **aucune garde** (`runtime.py:103-104`) : la boucle meurt définitivement (`finally` à `:135-138`), le claim acquis n'est jamais libéré. Effet réel : une annulation parallèle (usage prévu, cf. `tests/e2e/test_cancellation_e2e.py:64-68`) peut **arrêter silencieusement toute planification** jusqu'au redémarrage du processus. |
| B3 | `scripts/release_preflight.py:26-28` (+ `.github/workflows/ci.yml:42-43`) | **La CI de `main` est rouge.** `ruff format --check .` échoue sur ce fichier (confirmé localement : `unformatted: scripts/release_preflight.py:27`, exit 1 ; et dans les logs GitHub Actions du run 37791859372, identique sur Python 3.11 et 3.12). Le fichier a été commité non formaté par `ad4a494` (HEAD). Effet réel : **toute la grille de qualité (lint→format→mypy→pytest) est bloquée sur le premier pas**, aucune PR ne peut passer. |
| B4 | `.github/workflows/release-candidate.yml:201-234` | **Le job `create-github-release` n'exécute aucun `actions/checkout`** (les seuls checkout du workflow sont `:32` et `:163`, dans d'autres jobs). `gh release create ... --verify-tag` (étape `:234`) échoue avec `failed to run git: fatal: not a git repository` — vérifié dans les logs du run 37792035140. Effet réel sur `v0.1.0a3` : **PyPI reçoit bien le paquet** (jobs Qualify/Publish/Verify ✅) mais **le GitHub Release n'est jamais créé** et `verify-github-release` est skippé ; le pipeline de release est à moitié exécuté. Le même workflow a déjà échoué sur `v0.1.0a2` (échange Trusted Publishing TestPyPI). |
| B5 | `infrastructure/sqlite_schema.py:274` puis `:328` | **Initialisation de schéma non atomique au premier boot.** `_schema_metadata_exists()` est testé **hors transaction** (`:274`) et `CREATE TABLE pyschedulekit_schema` se fait **sans `IF NOT EXISTS`** (`:328`) — la transaction `BEGIN IMMEDIATE` n'est ouverte qu'ensuite (`:327`). Deux processus démarrant simultanément sur une base vierge (scénario multi-processus assumé : `tests/integration/sqlite/test_multi_worker_admission.py`) : le perdant attend le verrou, puis tente le `CREATE` contre un schéma déjà committé → `sqlite3.OperationalError: table pyschedulekit_schema already exists` qui s'échappe du constructeur `Scheduler(...)`. Même TOCTOU sur la lecture de `version` (`:278-282`). Effet réel : crash au démarrage concurrent, non reproductible en test unitaire mono-processus. |
| B6 | `application/concurrency.py:99-100` | **Le verrou d'admission n'est pas libéré en cas de `PersistenceConflictError`** alors que la branche générique voisine le fait (`:101-106`). Le handle est valide : sans libération, `ScheduleAdmissionLockCoordinator.acquire` refuse toute admission suivante du schedule tant que `lock.is_active(now)` (`application/admission_lock.py:66-71`), c'est-à-dire jusqu'à l'expiration du TTL (5 s par défaut, `api/scheduler.py:138-140`). Effet réel : après un simple conflit d'écriture transitoire, **les admissions du schedule sont bloquées pendant tout le TTL** et remontées `lock_denied` (`concurrency.py:268-277`). Ce chemin est **non testé** : les lignes 99-106 sont hors couverture. |
| B7 | `api/scheduler.py:271-274` → `:630`, commit `:302` | **`add_schedule` enregistre la cible `local:{id}` dans le registre AVANT le commit.** Si le commit échoue (ex. `DuplicateScheduleError` pour un id existant), l'entrée reste enregistrée à jamais : la nouvelle tentative lève alors `DuplicateTargetRegistrationError` (`local_executor.py:42-45`) au lieu de l'erreur de schedule attendue (`docs/implementation/LOT-22_TRANSACTIONS_DB_CONSTRAINTS.md` contracte `DuplicateScheduleError`). Effet réel : état du registre corrompu par un échec transitoire + **mauvaise classe d'erreur au retry** ; aucun test ne couvre `add_schedule` avec id dupliqué. |
| B8 | `infrastructure/memory.py:464-486`, `:717-730`, `:825-840` vs `infrastructure/sqlite_schema.py:49,79,115` | **Le dépôt en mémoire n'applique pas les clés étrangères que SQLite enforce.** `_validate_commit_locked` des requests/executions/attempts ne vérifie que doublons+versions, jamais l'existence du parent ; SQLite déclare `FOREIGN KEY ... REFERENCES` sur les 3 mêmes relations (et `tests/integration/sqlite/test_sqlite_constraints.py` les exige). Effet réel : la même opération est **acceptée en mémoire et rejetée en SQLite** (`ReferentialIntegrityError`) — le double de test du projet valide donc des graphs que la production refuse. |
| B9 | `infrastructure/memory.py:440-445` vs `:383-389` | **`has_pending()` ignore les lignes staged** alors que `list_pending()` et `list_admission_candidates()` les incluent (`candidate_ids.update(self._tracked)` `:389`, `:415`). Effet réel : dans un même `UnitOfWork` mémoire, `has_pending()` peut renvoyer `False` pendant que `list_pending(limit=1)` renvoie la request staged correspondante — deux méthodes du même port qui se contredisent ; le chemin SQLite inclut toujours `self._tracked`. Latent aujourd'hui (`WakeUpPlanner` utilise un UoW frais) mais exposé publiquement via `UnitOfWorkFactory`. |
| B10 | `infrastructure/http_executor.py:163-164` | **La réponse d'erreur HTTP n'est jamais fermée.** `HTTPError` *est* l'objet response ouvert (`exc.fp`) ; le branchement `except HTTPError` ne lit que `exc.code` et retourne, sans `exc.close()` (le chemin succès ferme via `with urlopen(...)`, `:161`). Effet réel : sous charge soutenue de réponses 4xx/5xx, **fuite de descripteurs de fichiers/socket** jusqu'au passage du GC. |
| B11 | `README.md:849` vs `src/pyschedulekit/_version.py` | **README obsolète** : il affirme « Version `0.1.0a1` » alors que la version réelle est `0.1.0a3` (confirmé par `tests/test_package.py:11`, CHANGELOG `[0.1.0a3] - 2026-10-08`). Effet réel : un lecteur (ou un agent) copie une version fausse. |
| B12 | `docs/specs/` (26 fichiers, non trackés) + `ruff format --check .` | **La totalité de `docs/specs/` (≈ 100 kLOC Markdown) n'est pas versionnée** (`git status` → `?? docs/specs/`) alors que `AGENTS.md` et le README s'y réfèrent comme source de spécification. Par ailleurs, 11 de ces fichiers `.md` **feraient échouer `ruff format --check .`** (constaté localement : 11 fichiers `docs/specs/*.md` non conformes) — les commiter tel quel casserait la CI. Effet réel : travail de spécification **non sauvegardé dans le dépôt** (perte au nettoyage du poste) + piège piège formatage au premier `git add`. |

---

## 6. Dette technique & risques environnementaux

### 6.1 Code

- **Double implémentation persistante** : `memory.py` (1 441 LOC) et `sqlite.py` (2 018 LOC) réimplémentent la même sémantique UoW ; la parité est maintenue à la main, sans test croisé automatique → origine directe de B8, B9.
- **Chemin timeout du `LocalExecutor` abandonne un thread daemon** (`local_executor.py:179-187`) : limitation **documentée** (`docs/implementation/LOT-16_EXECUTION_TIMEOUT.md:64-76`) — pas un bug, mais consigne à rappeler aux utilisateurs (effets de bord non réversibles).
- **`except Exception` très larges** : `application/operations.py:202` (health probe, volontaire), `application/concurrency.py:101` (relance, correct), `infrastructure/sqlite.py:1960` (rollback+re-raise, correct) — tous relus et jugés défendables, sauf l'incohérence B6.
- **Tests de release liés au répertoire courant** : `tests/unit/release/*.py` ouvrent `Path(".github/workflows/...")` en chemin **relatif** (ex. `test_pypi_workflow.py:5`) → `pytest` lancé depuis un autre répertoire échoue sur cette suite.

### 6.2 Obsolescence

- `actions/checkout@v4` dans `ci.yml:26` alors que les 3 autres workflows utilisent `@v6` ; dépréciations Node 20 remontées par GitHub sur `setup-python@v5`, `upload-artifact@v4`/`download-artifact@v5` (annotations du run 37792035140).
- `ruff>=0.8` non plafonné (`pyproject.toml:36`) : la version installée (0.16.1) a changé ses règles de formatage → **cause racine de B3** ; la CI n'est pas figée.
- Épinglage SHA partiel : `pypa/gh-action-pypi-publish` et `actions/attest` sont épinglés par SHA (`release-candidate.yml:186,199`) mais pas `checkout`/`setup-python` — politique incohérente.

### 6.3 Configuration bloquante

- **`.env` orphelin** (clé `API_TOKEN`, non lu par le code) — voir §4 🟡.
- **`docs/specs/` non versionné** — voir B12.
- **Pas de seuil de couverture** : `fail_under` absent de `pyproject.toml` → 86 % peut régresser sans bloquer.
- **Tags de release non réutilisables** : `release-readiness.yml` refuse explicitement un tag déjà existant — après B4, la correction ne pourra pas re-pousser `v0.1.0a3` (voir [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) Phase 0).
- **pre-commit config en `language: system`** (`.pre-commit-config.yaml:13`) : exige les deps dev installées dans l'environnement actif, sinon tous les hooks échouent (signalé dans `AGENTS.md`).

---

## 7. Points forts

- **Pureté du domaine réellement exécutable** : les tests d'architecture (`tests/architecture/test_domain_boundaries.py`) interdisent imports transverses, heure murale et `os.getenv` — vérifié, vert.
- **Contrat d'API publique verrouillé** : `_manifest.STABLE_PUBLIC_NAMES` trié+unique, test `tests/unit/api/test_public_api_contract.py` (identité des objets, redirections de dépréciation, signature de `Scheduler`, version installée == version runtime).
- **Transactions correctes** : `BEGIN IMMEDIATE`, validate-then-apply, rollback systématique en sortie d'UoW (`sqlite.py:1946-1975`), clés étrangères activées, CAS sur `PersistenceVersion`.
- **Coordination multi-travailleurs soignée** : claims avec fencing par `generation`, heartbeat de lease, verrous d'admission et baux de matérialisation durables — avec tests dédiés (`tests/integration/sqlite/test_multi_worker_admission.py`, `test_lease_fencing.py`).
- **Déterminisme des tests** : 453 tests sans sleep de horloge (helpers `MutableClock` livrés), durée totale 1,63 s ; suite e2e réelle (18 fichiers).
- **Discipline de release avancée** : qualification de distribution, matrice clean-install, Trusted Publishing OIDC, provenance/attestations, runbook (`docs/release/`), preflight exécutable — même si l'exécution réelle est cassée (B4).
- **Documentation de spécification dense** : 35 LOTs implémentés, 68 fichiers Markdown, chaque garantie associée à un test (règle de projet).

---

## 8. Recommandations priorisées

1. **P0 —** Remettre la CI au vert : `ruff format scripts/release_preflight.py` (B3) ; traiter le GitHub Release inachevé de `v0.1.0a3` (B4) ; versionner `docs/specs/` après formatage (B12).
2. **P1 —** Bloquants de contrat : annulation qui gagne sur le retry (B1) et boucle `run_forever` qui survit aux transitions concurrentes (B2), avec tests de non-régression.
3. **P2 —** Robustesse persistante : initialisation de schéma atomique (B5), libération du verrou d'admission sur conflit (B6), enregistrement de cible post-commit (B7).
4. **P3 —** Parité et hygiène des adaptateurs : FK mémoire (B9/B8), staged lus partout (B9), fermeture des réponses HTTP d'erreur (B10), README à jour (B11).
5. **P4 —** Filets : seuil de couverture, versions d'actions cohérentes, pin de ruff, tests de parité mémoire/SQLite automatiques.

Le plan détaillé, les correctifs prêts à l'emploi et les critères d'acceptation sont dans [RECOMMANDATIONS.md](./RECOMMANDATIONS.md).

---

*Méthodologie : lecture intégrale de `src/pyschedulekit/{domain,application,ports,infrastructure,api}` sur les flux critiques (run_pending, run_forever, cancellation/retry, claims/fencing, unités de travail SQLite/mémoire) ; vérification croisée `pyproject`/workflows/`.gitignore`/pre-commit ; exécution réelle de la suite CI locale (ruff, mypy, pytest, coverage) et lecture des logs GitHub Actions via `gh run view` pour B3/B4 ; scan d'historique git pour secrets. Chaque bug listé au §5 est justifié par une ligne de code précise.*
