# INDEX — Documentation du projet

Point d'entrée de toute la documentation. Ce dépôt contient **8 documents Markdown à la racine** : cette page sert de sommaire et de guide de navigation.

---

## 1. Les documents

| Document | Rôle | Contenu en une ligne | À lire quand… |
|---|---|---|---|
| [README.md](./README.md) | Présentation | Vue produit : principes, fondations, API publique, développement, licence | on découvre le projet ou on cherche une notion (triggers, retry, claims…) |
| [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) | État des lieux | Faits vérifiés : métriques, architecture, surfaces, sécurité (🟡), **12 bugs B1-B12**, dette, forces | on veut les faits, chiffres et `fichier:ligne` sans opinion |
| [ANALYSE_CRITIQUE.md](./ANALYSE_CRITIQUE.md) | Opinion | Notes /10, pattern systémique (chaîne de suppositions), critiques d'architecture/sécurité/processus, « réparer ou réécrire ? » | on veut juger la qualité globale et comprendre *pourquoi* les bugs existent |
| [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) | Action | Plan Phases 0-5 avec correctifs prêts à l'emploi, tests de non-régression, critères d'acceptation, roadmap | on va corriger quelque chose — c'est le seul document à suivre |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Référence | Vue système, cycle de vie d'un cycle `run_pending`, flux métier, modèle de données, conventions | on modifie le code et on a besoin du câblage réel |
| [INDEX.md](./INDEX.md) | Sommaire | Cette page : navigation par tâche, carte du code, repères chiffrés | on ne sait pas par où commencer |
| [AGENTS.md](./AGENTS.md) | Instructions | Commandes exactes, gotchas (manifeste API, version, chemins), workflow LOT | on exécute des commandes dans ce dépôt (humain ou agent) |
| [CHANGELOG.md](./CHANGELOG.md) | Historique | Versions `0.1.0a1` → `0.1.0a3` datées | on cherche ce qui a changé depuis une version |

**Ordre de lecture suggéré** : [CODEBASE_ANALYSIS](./CODEBASE_ANALYSIS.md) (les faits) → [ANALYSE_CRITIQUE](./ANALYSE_CRITIQUE.md) (le verdict) → [RECOMMANDATIONS](./RECOMMANDATIONS.md) (le plan) → [ARCHITECTURE](./ARCHITECTURE.md) au besoin avant de coder, [AGENTS.md](./AGENTS.md) avant toute commande.

---

## 2. Navigation par tâche

| Je veux… | Aller à |
|---|---|
| Lancer la suite de tests / les hooks | [AGENTS.md](./AGENTS.md) §Commands |
| Comprendre un cycle complet `run_pending()` | [ARCHITECTURE.md](./ARCHITECTURE.md) §2.2 |
| Comprendre l'annulation vs retry (ou un autre flux) | [ARCHITECTURE.md](./ARCHITECTURE.md) §2.3 |
| Retrouver un bug précis avec sa ligne | [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) §5 (table B1-B12) |
| Connaître les failles de sécurité | [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) §4 + [ANALYSE_CRITIQUE.md](./ANALYSE_CRITIQUE.md) §4 |
| Commencer à corriger (par quoi commencer ?) | [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) §Phase 0 |
| Écrire un test de non-régression | [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) §Filet de sécurité + [AGENTS.md](./AGENTS.md) |
| Savoir si je dois réécrire ou réparer | [ANALYSE_CRITIQUE.md](./ANALYSE_CRITIQUE.md) §8 |
| Moderniser (actions, pins, couverture) | [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) §Phase 5 |
| Gérer une release (qualification, publication, rollback) | [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) §Phase 0.2 + `docs/release/06_RELEASE_RUNBOOK_AND_ROLLBACK.md` |
| Voir la surface d'API stable vs expérimentale | [ARCHITECTURE.md](./ARCHITECTURE.md) §4 + [README.md](./README.md) §Public API stability |
| Les limites de conception, sans détails | [ARCHITECTURE.md](./ARCHITECTURE.md) §6 |

---

## 3. Carte rapide du code source

| Package | Point d'entrée | Cœur du système |
|---|---|---|
| `src/pyschedulekit/api/` | `Scheduler` (`scheduler.py`) | `_manifest.py` — contrat des noms publics |
| `src/pyschedulekit/domain/` | `time.py`, `trigger.py` | `execution.py` — machine à états + invariants |
| `src/pyschedulekit/application/` | `run_pending.py` | `scheduler_engine.py` (évaluation) + `execution_runner.py` (exécution) |
| `src/pyschedulekit/ports/` | `persistence.py` (`UnitOfWork`) | `executor.py`, `time.py` — les frontières injectées |
| `src/pyschedulekit/infrastructure/` | `sqlite.py` + `sqlite_schema.py` | `memory.py` (jumeau), `local_executor.py`/`http_executor.py` |
| `src/pyschedulekit/testing/` | `time.py` (`MutableClock`) | pilotage du temps dans les tests |
| `scripts/` | `release_preflight.py` | `verify_distribution.py`, `smoke_installed_package.py` |

Fichiers à connaître absolument avant toute modification :

- **`src/pyschedulekit/api/_manifest.py`** — ajouter/renommer un export public = ce fichier + `api/__init__.py` + racine + `test_public_api_contract.py` (règle non négociable).
- **`src/pyschedulekit/_version.py`** — source unique de la version ; `tests/test_package.py:11` la compare au mot près.
- **`src/pyschedulekit/domain/execution.py`** — `start_attempt`/`finish_attempt`/`cancel` : toute transition y est validée (`InvalidExecutionTransitionError`).
- **`src/pyschedulekit/infrastructure/sqlite_schema.py`** — toute règle d'intégrité y est déclarée **et** doit être répliquée dans `memory.py`.
- **`.github/workflows/release-candidate.yml`** — ses tests lisent le YAML en chemins relatifs (`tests/unit/release/`) : ne le modifier qu'à la racine.

---

## 4. Repères chiffrés

- **8 documents Markdown à la racine** (76 au total dans le dépôt, dont **26 fichiers `docs/specs/` non versionnés** — B12).
- **Source** : 64 fichiers Python, 13 740 LOC — `domain` 3 023 · `application` 3 407 · `infrastructure` 5 390 · `api` 1 464 · `ports` ~550.
- **Tests** : 453 tests (1,63 s), 77 fichiers — 32 unit · 25 integration · 18 e2e · 1 architecture — **couverture 86 %**, aucun `fail_under`.
- **Qualité** : `ruff check` ✅ · `mypy --strict` ✅ · `pytest` ✅ · `ruff format --check` ❌ (B3, `scripts/release_preflight.py:27`).
- **Dépendances runtime** : **0** · Python ≥ 3.11 · CI sur 3.11/3.12/3.13.
- **Bugs confirmés** : **12** (B1-B12 : 1 critique, 3 élevés, 5 moyens, 3 faibles) — tous avec `fichier:ligne`.
- **Vulnérabilités** : **0 🔴 · 0 🟠 · 2 🟡** (`.env` orphelin, redirections HTTP non contrôlées) — aucun secret dans le code ni dans l'historique.
- **État des livraisons** : `0.1.0a3` publié sur PyPI ; GitHub Release absente (B4) ; CI rouge sur `main` (B3).

---

*Dernière mise à jour : 2026-10-08 — documents générés lors d'un audit complet de la codebase.*
