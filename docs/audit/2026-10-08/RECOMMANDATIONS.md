# Recommandations — PyScheduleKit

> **AUDIT SNAPSHOT / REMEDIATION PLAN — 2026-10-08.** Ce document conserve le plan
> d'action produit à partir de l'audit initial. Plusieurs actions décrites plus bas sont
> désormais terminées. Le statut d'exécution faisant foi est
> [POST-00 Remediation Status](./docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md).

> Document d'**action** : traduit les constats de [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md) et le verdict de [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md) en plan de remédiation concret, ordonné par priorité, avec correctifs prêts à l'emploi et critères de validation.

**Lecture rapide :** Phase 0 = aujourd'hui · Phase 1 = sécurité (bloquant) · Phase 2 = bugs cassant des features · Phase 3 = intégrité des données · Phase 4 = robustesse · Phase 5 = modernisation.

**Ordre d'exécution imposé** : le « filet de sécurité » (tests de non-régession) se construit **en premier**, phase 1 inclus ; aucun correctif des phases 2-3 n'est mergeable sans son test qui échoue avant / passe après.

---

## Phase 0 — Urgence immédiate (< 1 jour)

**Aucun secret n'est commis dans le dépôt** (scan de l'historique git : aucun fichier tracké concerné) : pas de rotation ni de purge `git filter-repo` nécessaire. L'urgence est ailleurs — la CI, la release inachevée et les specs non versionnées.

| # | Action | Détail |
|---|---|---|
| 0.1 | **Rouvrir la CI (B3)** | `ruff format scripts/release_preflight.py` puis vérifier `ruff format --check .` → exit 0. C'est **l'étape 1 de `ci.yml:42`** qui échoue sur `scripts/release_preflight.py:27` (le `return (` multi-lignes doit être réduit en une ligne). Commit `fix(ci): format release_preflight` — débloque 100 % de la grille qualité. |
| 0.2 | **Rattraper la release `v0.1.0a3` (B4)** | Deux options, jamais les deux registres désaccordés : **(a)** corriger le workflow (correctif 4.x ci-dessous), créer manuellement le release depuis une checkout locale : `gh release create v0.1.0a3 dist/* release-candidate-sha256.txt --verify-tag --prerelease --title "PyScheduleKit 0.1.0a3" --generate-notes` ; **(b)** passer à `0.1.0a4` avec le workflow corrigé (release-readiness **refuse les tags existants**, un re-run du workflow tel quel échouera à nouveau). |
| 0.3 | **Versionner `docs/specs/` (B12)** | `ruff format docs/specs` (11 fichiers non conformes, sinon la CI échouera dès le commit) puis `git add docs/specs` — 26 fichiers de spécification référencés par `AGENTS.md`/README sont aujourd'hui **non sauvegardés dans le dépôt**. |
| 0.4 | **Mettre le README à jour (B11)** | `README.md:849` affiche `0.1.0a1`, la réalité est `0.1.0a3` — corrigé dans le livrable « README » de l'audit (voir § Phase 2). |
| 0.5 | **Purger le `.env` orphelin** | Fichier local non tracké contenant `API_TOKEN`, **jamais lu par le code**. Le supprimer (ou confirmer qu'il s'agit d'un jeton mort et le révoquer côté fournisseur). Règle : aucun fichier de configuration non consommé dans la racine. |

---

## Phase 1 — Sécurité (bloquante)

### 1.1 Correctif structurant : contrôle des redirections HTTP (🟡 CODEBASE §4)

Le seul point d'entrée réseau du paquet est `HttpExecutor`. L'URL d'origine est déjà validée (`http_executor.py:52-76` : scheme http(s), pas d'identifiants, anti-CRLF) mais **la destination après redirection ne l'est jamais**. Ajouter un opener dédié qui re-valide chaque saut :

```python
# src/pyschedulekit/infrastructure/http_executor.py
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

_MAX_REDIRECTS = 3


class _ControlledRedirectHandler(HTTPRedirectHandler):
    """Re-validate every redirect hop against the original target rules."""

    def __init__(self, allowed_host: str | None) -> None:
        super().__init__()
        self._allowed_host = allowed_host
        self._hops = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        self._hops += 1
        parts = urlsplit(newurl)
        if self._hops > _MAX_REDIRECTS or parts.scheme not in ("http", "https"):
            raise URLError(f"Blocked HTTP redirect to {newurl!r}")
        if self._allowed_host is not None and parts.hostname != self._allowed_host:
            raise URLError(f"Blocked cross-host HTTP redirect to {newurl!r}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# dans execute() : construire l'opener avec l'hôte de prepared.request.url
# opener = build_opener(_ControlledRedirectHandler(urlsplit(prepared.request.url).hostname))
# with opener.open(request, timeout=timeout_seconds) as response: ...
```

| Surface (§3) | État actuel | Correctif |
|---|---|---|
| `HttpExecutor.execute` redirections | `urlopen` suit toute redirection (`http_executor.py:161`) | Opener contrôlé ci-dessus : max 3 sauts, scheme revalidé, **hôte d'origine exigé** |
| `.env` orphelin | Non tracké, non lu, mais présent | Suppression (Phase 0.5) + interdiction documentée dans `AGENTS.md` |
| Registres de cibles | Opt-in manuel, signatures/URL validées | Aucun changement — c'est le bon modèle ; le documenter comme tel dans `ARCHITECTURE.md` §conventions |
| Chaîne d'approvisionnement Actions | SHA épinglées pour `pypa/gh-action-pypi-publish` + `attest` ; tags flottants pour `checkout`/`setup-python` | Uniformiser en Phase 5 |

### 1.2 Durcissement transversal (~1 h)

- **Tests** : ajouter un cas « cible HTTP redirigée vers hôte interne » (mock `urlopen`) qui exige `URLError`.
- **Aucune lib supplémentaire nécessaire** : tout est dans la stdlib (`urllib.request`, `urllib.parse`) — respecte la règle « zéro dépendance runtime » (`pyproject.toml:28`).
- **Documentation** : une section « Threat model » courte dans la doc de sécurité (le modèle de confiance = registres explicites, le risque résiduel = effet de bord dupliqué, voir [ANALYSE_CRITIQUE.md](./ANALYSE_CRITIQUE.md) §4).

---

## Phase 2 — Bugs fonctionnels (~2 jours)

Classement par impact utilisateur décroissant. Chaque ligne a **un test qui échoue avant** (arborescence du filet de sécurité, plus bas).

### 2.1 Correctif B1 — l'annulation gagne sur le retry (2 points d'application)

**(a) `local_executor.py:186-187` — le chemin timeout ignore le token** (reproduit en 50 ms) :

```python
# AVANT (local_executor.py, branche timeout)
if not completed.wait(timeout_seconds):
    return self._timeout_outcome()

# APRÈS — miroir du contrôle déjà présent à :153 et :193
if not completed.wait(timeout_seconds):
    if cancellation_token is not None and cancellation_token.is_cancelled:
        return self._cancelled_outcome()
    return self._timeout_outcome()
```

**(b) `domain/execution.py:520-527` — filet défensif unique dans `finish_attempt`** (état frais, lu dans la transaction du service) :

```python
# AVANT (execution.py, dans finish_attempt)
if retry_at is not None:
    if result.state not in (AttemptState.FAILED, AttemptState.TIMED_OUT):
        raise InvalidExecutionTransitionError(...)

# APRÈS
if retry_at is not None and self._cancellation_requested_at is None:
    if result.state not in (AttemptState.FAILED, AttemptState.TIMED_OUT):
        raise InvalidExecutionTransitionError(...)
    ...  # bloc RETRY_WAIT inchangé
# si une cancellation est déjà demandée : on tombe dans le mapping terminal
# → l'exécution devient FAILED/TIMED_OUT, JAMAIS RETRY_WAIT (LOT-17:115 respecté)
```

> Note de conception : quand l'exécuteur rapporte `CANCELLED`, le branchement existant (`execution_runner.py:155-161`) produit déjà l'état `CANCELLED` canonique de LOT-17. Le filet (b) couvre les cas **non coopératifs** (timeout, cible qui ignore le token, worker distant) — l'état terminal est alors `FAILED`/`TIMED_OUT` (l'attempt a réellement échoué) mais **aucune relance n'a lieu**, ce qui est la garantie de safety réelle. Laisser `RETRY_WAIT` avec `_cancellation_requested_at` posé reste interdit.

**Critère d'acceptation** : `test_cancellation_retry_regression.py` — schedule avec `RetryPolicy(max_attempts=3)`, cible non coopérative qui dépasse le timeout, `cancel_execution` pendant l'exécution → état final terminal **et** `retry_scheduled == 0` **et** la cible n'est jamais rappelée après la cancellation.

### 2.2 Correctif B2 — `run_pending` survit aux transitions concurrentes

```python
# AVANT (application/run_pending.py, boucle d'exécution, après except TargetResolutionError:)
except PersistenceConflictError:          # ligne 208 — n'attrape PAS
    ...                                  # InvalidExecutionTransitionError(ValueError)

# APRÈS — ajouter le branchement (mirroir de TargetResolutionError, ligne 194)
except InvalidExecutionTransitionError:
    self._release_unstarted_claim(claim_handle)
    errors.append(
        RunPendingError(
            request_id=execution.request_id,
            code="execution.transition",
            message="Execution state changed concurrently; skipped this cycle.",
        )
    )
```

- Import à compléter : `from pyschedulekit.domain.execution import Execution, ExecutionId, InvalidExecutionTransitionError` (`run_pending.py:22`).
- **Défense en profondeur (Phase 4)** : envelopper l'appel de `run_pending` dans `runtime.py:103` d'un `try/except Exception` qui enregistre `runtime.cycle.error` via `ObservationObserver`, attend `max_sleep`, et continue — une boucle de longue haleine ne doit jamais mourir sur une erreur de cycle (avec compteur de pannes consécutives pour éviter une boucle serrée infinie).

**Critère d'acceptation** : test qui force une exécution listée `QUEUED` puis annulée avant `start_attempt` (monkeypatch de `_list_runnable_executions`) → `run_pending()` **retourne** avec `errors[0].code == "execution.transition"` au lieu de lever.

### 2.3 Correctif B7 — enregistrer la cible **après** le commit

```python
# AVANT (api/scheduler.py)
target_ref = self._normalize_target(
    target=target, schedule_id=schedule_id
)  # :271 → registry.register
...
with self._uow_factory() as uow:
    uow.schedules.add(schedule)
    uow.commit()  # :302


# APRÈS
def _normalize_target(self, *, target, schedule_id) -> TargetRef:
    if isinstance(target, TargetRef):
        return target
    return TargetRef.python(f"local:{schedule_id.value}")  # ne modifie PLUS le registre


# dans add_schedule :
target_ref = self._normalize_target(target=target, schedule_id=schedule_id)
...
with self._uow_factory() as uow:
    uow.schedules.add(schedule)
    uow.commit()
if not isinstance(target, TargetRef):
    self._registry.register(
        target_ref.reference, target
    )  # état process-local dérivé du commit réussi
self._runtime.wake()
```

**Critère d'acceptation** : `add_schedule(id=<existant>, target=callable)` lève `DuplicateScheduleError` (et pas `DuplicateTargetRegistrationError`) ; une tentative qui échoue ne laisse **aucune entrée orpheline** dans le registre (réessai possible).

### 2.4 Correctif B9 — `has_pending` doit voir les staged

```python
# AVANT (infrastructure/memory.py:440)
def has_pending(self) -> bool:
    with self._store._lock:
        return any(
            request.state is ExecutionRequestState.PENDING
            for request in self._store._execution_requests.values()
        )


# APRÈS — mirroir exact de list_pending (memory.py:383-389)
def has_pending(self) -> bool:
    with self._store._lock:
        candidate_ids = set(self._store._execution_requests)
    candidate_ids.update(self._tracked)
    for request_id in candidate_ids:
        request = self._tracked.get(request_id)
        if request is None:
            request = self.get(request_id)
        if request is not None and request.state is ExecutionRequestState.PENDING:
            return True
    return False
```

Vérifier au passage `next_runnable_at` (`memory.py:663`) contre la même omission.

**Critère d'acceptation** : dans un même UoW mémoire, ajouter une request `PENDING` sans commit → `has_pending() is True` et `len(list_pending(limit=1)) == 1` (les deux ne peuvent plus diverger).

| Bug | Fichier:ligne | Correctif (résumé) |
|---|---|---|
| B1 | `local_executor.py:186` + `execution.py:520` | Token testé sur timeout ; jamais de `RETRY_WAIT` quand cancellation demandée |
| B2 | `run_pending.py:194-224` (+ `runtime.py:103` optionnel) | `except InvalidExecutionTransitionError` + libération du claim |
| B7 | `api/scheduler.py:271` vs `:302`, `:630` | `registry.register` déplacé après `uow.commit()` |
| B9 | `memory.py:440` (+ `:663`) | `has_pending`/`next_runnable_at` incluent `self._tracked` |

---

## Phase 3 — Intégrité des données (~1 jour)

### 3.1 Règles repo-wide (énoncées comme telles)

1. **Jamais d'initialisation de schéma hors transaction** — tout `CREATE`/`ALTER` se fait sous `BEGIN IMMEDIATE`, avec re-vérification de l'état **à l'intérieur** de la transaction (B5).
2. **Jamais de ressource acquise non libérée sur le chemin d'erreur** — tout `except` qui retourne doit passer par la libération (B6) ; toute réponse réseau ouverte est fermée dans un `finally`/`with` (B10).
3. **Toujours la parité des deux adaptateurs** — toute règle appliquée par `sqlite_schema.py` a un équivalent testé dans `memory.py` (B8), via un test paramétré unique (ci-dessous).

### 3.2 Correctif B5 — bootstrap atomique

```python
# AVANT (infrastructure/sqlite_schema.py:327-329, dans _create_v8_schema)
connection.execute("BEGIN IMMEDIATE")
try:
    connection.execute(
        "CREATE TABLE pyschedulekit_schema (version INTEGER NOT NULL CHECK(version >= 1))"
    )

# APRÈS
connection.execute("BEGIN IMMEDIATE")
try:
    if _schema_metadata_exists(connection):      # re-check SOUS verrou
        connection.execute("ROLLBACK")            # un concurrent a initialisé
        return False                              # ← signaler « non créé »
    connection.execute(
        "CREATE TABLE IF NOT EXISTS pyschedulekit_schema "
        "(version INTEGER NOT NULL CHECK(version >= 1))"
    )
```

Et dans `initialize_sqlite_schema` (`:271`), boucler : si `_create_v8_schema` renvoie « non créé », reprendre la lecture de `version` (la version concurrente est identique — même code — mais la relecture évite toute supposition). Le check initial hors transaction (`:274`) devient un simple chemin rapide, plus une garantie.

**Critère d'acceptation** : `test_concurrent_schema_init.py` — 8 threads initialisent simultanément 1 base vierge sous `tmp_path`, 20 exécutions consécutives sans `sqlite3.OperationalError`.

### 3.3 Correctif B6 — libérer le verrou sur conflit

```python
# AVANT (application/concurrency.py:99-100)
except (AdmissionLockOwnershipError, PersistenceConflictError):
    return self._lock_denied_result(request_id)          # verrou laissé actif → TTL bloqué

# APRÈS
except PersistenceConflictError:
    try:
        self._admission_lock_coordinator.release(         # miroir de :101-106
            handle=acquisition.handle,
            released_at=self._now(created_at),
        )
    except PersistenceConflictError:
        pass                                              # échec de release → expiration TTL
    return self._lock_denied_result(request_id)
except AdmissionLockOwnershipError:
    return self._lock_denied_result(request_id)           # plus notre verrou : rien à libérer
```

**Critère d'acceptation** : simuler un `PersistenceConflictError` dans `_admit_locked` → le retour est `lock_denied` **et** une admission immédiate suivante du même schedule est acceptée (aujourd'hui : refusée pendant 5 s).

### 3.4 Correctif B8 — FK dans le validateur mémoire

```python
# AVANT (infrastructure/memory.py, _validate_commit_locked : contrôle doublon+version)
# APRÈS — ajouter, pour les executions et les attempts :
parent = self._execution_requests.get(...)  # requests doivent exister…
if parent is None:
    raise ReferentialIntegrityError(...)
# executions → requests ; attempts → executions (miroir de sqlite_schema.py:49,79,115)
```

Plutôt que trois patchs recopiés : **un test paramétré de parité** (Phase 4) exécutant la même séquence d'opérations sur les deux adaptateurs et exigeant le même couple (succès, `ReferentialIntegrityError`).

---

## Phase 4 — Robustesse & qualité (~1 jour)

| # | Item | Fichier:ligne | Correctif |
|---|---|---|---|
| 4.1 | B10 — fuite de descripteurs HTTP | `http_executor.py:163-164` | `except HTTPError as exc:` → `try: status = int(exc.code) finally: exc.close()` (un `HTTPError` **est** la response ouverte) |
| 4.2 | Seuil de couverture | `pyproject.toml:65-71` | ajouter `[tool.coverage.report] fail_under = 85` (86 % actuels ; la valeur 85 laisse la marge des nouveaux tests) |
| 4.3 | Tests de release liés au cwd | `tests/unit/release/*.py:5` | remplacer `Path(".github/workflows/...")` par `Path(__file__).resolve().parents[3] / ".github/..."` — `pytest` devient portable hors racine |
| 4.4 | Claim non libéré sur conflit | `run_pending.py:208` | libérer le claim dans le branchement `PersistenceConflictError` (mirroir `_release_unstarted_claim`) avant d'appender l'erreur |
| 4.5 | Garde de boucle runtime | `runtime.py:103` | défense en profondeur de B2 : `try/except` + `runtime.cycle.error` + backoff (voir §2.2) |
| 4.6 | Exécution en cours / threads daemon | doc | ajouter au README l'avertissement LOT-16 (timeout local abandonne un thread) au même endroit que la section retry |

**Validation Phase 4** : `ruff check . && ruff format --check . && mypy src && pytest --cov=pyschedulekit` — les **4 commandes** vertes, 0 warning, couverture ≥ 85 %.

---

## Phase 5 — Modernisation (opportun, après stabilisation)

| Sujet | Migration | Bénéfice |
|---|---|---|
| Actions GitHub flottantes | `actions/checkout@v4` → `@v6` (`ci.yml:26`) + épinglage SHA de `checkout`/`setup-python` comme `pypa/gh-action-pypi-publish` (`release-candidate.yml:186`) | Chaîne d'approvisionnement homogène, fin des dépréciations Node 20 |
| ruff non plafonné | `ruff>=0.8` (`pyproject.toml:36`) → `ruff==0.16.1` (version réellement utilisée) | Le format ne re-dérape plus au prochain upgrade (cause racine de B3) |
| Parité adaptateurs manuelle | test paramétré `test_adapter_parity.py` branché sur les 8 opérations du port | Régression B8/B9 impossible à reintroduire en silence |
| `AGENTS.md` / README manuels | dériver la ligne de version du README (`python -c "import pyschedulekit…"`) | Fin de B11 (version fausse recopiée) |
| pre-commit `language: system` | le documenter comme contrat d'env (déjà fait) ou basculer en hooks CI uniquement | Fin du piège « hooks verts seulement avec deps installées » |

---

## Filet de sécurité : suite de tests minimale (à faire EN PREMIER de la phase 1)

```
tests/
├── integration/
│   ├── application/
│   │   ├── test_cancellation_retry_regression.py   # B1 : timeout non coopératif + cancel + RetryPolicy
│   │   └── test_run_pending_transition_race.py     # B2 : transition concurrente rattrapée, cycle survit
│   ├── infrastructure/
│   │   └── test_adapter_parity.py                  # B8/B9 : même scénario → mémoire == SQLite
│   └── sqlite/
│       └── test_concurrent_schema_init.py          # B5 : N threads, base vierge, zéro OperationalError
├── unit/
│   ├── application/
│   │   └── test_admission_lock_release.py          # B6 : conflit → verrou libéré immédiatement
│   ├── api/
│   │   └── test_add_schedule_duplicate_id.py       # B7 : DuplicateScheduleError + registre propre
│   ├── infrastructure/
│   │   └── test_http_executor_error_paths.py       # B10 : 4xx/5xx fermés + redirect bloqué (Phase 1)
│   └── release/
│       └── test_github_release_workflow.py         # B4 : + test_t_github_release_006 exigeant
│                                                    #   "actions/checkout" dans la section create-
│                                                    #   github-release (la lacune non détectée)
```

- **Stack** : pytest + pytest-cov + mypy (inchangé, `pyproject.toml`), `MutableClock`/`InMemoryUnitOfWorkFactory` de `pyschedulekit.testing` + `tmp_path` pour SQLite — **aucune nouvelle dépendance**.
- **Lancement** : `pytest` depuis la racine (règle du projet) ; chaque nouveau test doit **échouer sur le code actuel** et passer après son correctif.

**Critère d'acceptation global de la phase 1 :** `ruff check . && ruff format --check . && mypy src && pytest --cov=pyschedulekit --cov-fail-under=85` vert **avec les nouveaux tests de non-régression inclus**, et le run GitHub Actions correspondant vert sur `main`.

---

## Récapitulatif de la roadmap

| Phase | Contenu | Effort | Jalons de sortie |
|---|---|---|---|
| 0 | CI verte (B3), release a3 rattrapée (B4), specs versionnées (B12), README (B11), `.env` purgé | < 1 jour | CI verte sur `main` **et** GitHub Release `v0.1.0a3` (ou tag `a4`) présent |
| 1 | Filet de tests (B1, B2, B4-test) + redirections HTTP contrôlées | 0,5–1 jour | Nouveaux tests rouges avant fix, verts après ; `fail_under` actif |
| 2 | B1 (2 points), B2, B7, B9 | ~1 jour | Aucun `RETRY_WAIT` possible avec cancellation ; `run_pending` ne lève plus sur race |
| 3 | B5, B6, B8 (+ parité mémoire/SQLite) | ~1 jour | Bootstrap concurrent × 20 OK ; conflit d'admission ne bloque plus le TTL |
| 4 | B10, cwd des tests release, claim sur conflit, garde runtime | ~1 jour | 4 commandes CI vertes, 0 warning, couverture ≥ 85 % |
| 5 | Pins d'actions, pin ruff, tests de parité pérennes, dérivation de version | ~1 jour | Aucun tag flottant critique ; upgrade ruff sans surprise |

> **Principe directeur** : *« toute garantie supportée mappe à un test exécutable »* — un fix n'existe pas tant que son test n'a pas échoué d'abord ; et **réparer, pas réécrire** : les 12 bugs sont localisés et indépendants, le socle (domaine, transactions, fencing, contrat d'API) est sain.
