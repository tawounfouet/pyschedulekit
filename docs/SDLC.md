# SDLC — PyScheduleKit

> Guide du cycle de vie de développement : les 7 phases, les outils OpenCode associés, et où en est le projet. Ce document complète [`docs/README.md`](./README.md) (sommaire) et [`RECOMMANDATIONS.md`](./audit/2026-10-08/RECOMMANDATIONS.md) (plan de remédiation).

---

## 1. Comment utiliser ce document

- Pour **savoir où on en est** : §4 (position courante) + §5 (backlog par phase).
- Pour **savoir quoi faire ensuite** : §3 (outils par phase) + §6 (porte qualité).
- L'orchestrateur est invocable à tout moment via `/sdlc` (ou `/sdlc <phase>` pour se placer sur une phase : `plan`, `build`, `test`, `review`, `release`, `deploy`, `maintain`).

---

## 2. Le cycle

```text
 1 Plan ──► 2 Build ──► 3 Test ──► 4 Review ──► 5 Release ──► 6 Deploy ──► 7 Maintain
   ▲                                                                          │
   └──────────────────────────────── feedback / nouvelle dette ───────────────┘

  Planifier  →  Coder  →  Vérifier  →  Contrôler  →  Versionner  →  Publier  →  Entretenir
```

Règle de bouclage : un échec de test renvoie en **Build** ; une CI rouge renvoie en **Build** ; un bug de release renvoie en **Release**.

---

## 3. Les 7 phases

| # | Phase | Objectif | Aiguillage (indicateurs) |
|---|---|---|---|
| 1 | **Planification** | Comprendre, concevoir, spécifier | Pas de code, exploration d'architecture, rédaction de specs |
| 2 | **Développement** | Implémenter, corriger, refactorer | Fichiers modifiés, features/bugs en cours |
| 3 | **Testing** | Vérifier, couvrir, valider | Code écrit, tests manquants ou à ajouter |
| 4 | **Review** | Qualité, sécurité, préparation de merge | Code terminé, pas encore relu |
| 5 | **Release** | Version, changelog, tag | Revue passée, prêt à versionner |
| 6 | **Déploiement** | Commit propre, push, publication | Commit local, push en attente |
| 7 | **Maintenance** | Docs, dette technique, support | Après release, consolidation |

### 3.1 Planification
- **Outils** : mode `architect` (`ctrl+a`) · agent `plan` · `@docs-writer` · skill `docs-writer`.
- **Commande projet** : lecture de `docs/specs/` et `docs/implementation/LOT-*.md`.
- **Critère de sortie** : une spec/garantie écrite pour chaque comportement attendu.

### 3.2 Développement
- **Outils** : agent `build` · `/refactor` · `@refactor-assistant` · skill `git-hygiene`.
- **Commande projet** : `ruff check .` · `ruff format .` · `mypy src`.
- **Critère de sortie** : le comportement est implémenté et lint/type passent.

### 3.3 Testing
- **Outils** : `/test` · `@test-scaffolder` · skill `test-scaffolder` · `check-ci`.
- **Commande projet** : `pytest` · `pytest -q --cov=pyschedulekit` · un seul test : `pytest tests/...::test_...`.
- **Critère de sortie** : nouvelle garantie couverte par un test exécutable (rouge → vert), suite verte.

### 3.4 Review
- **Outils** : `/review` · `/pr-review` · `@code-reviewer` · mode `security-audit` (`ctrl+s`) · mode `debug` (`ctrl+d`).
- **Critère de sortie** : plus d'issue bloquante ; comportement courant reflété dans les tests et, si nécessaire, dans [`ARCHITECTURE.md`](./ARCHITECTURE.md) ou le registre de statut concerné. Les snapshots d'audit datés ne sont jamais réécrits.

### 3.5 Release
- **Outils** : `/release` · `@release-prep` · skill `release-prep` · `diff-summary`.
- **Commande projet** : `python -m scripts.verify_distribution dist` · `python scripts/smoke_installed_package.py`; `release_preflight` seulement pour une vraie publication.
- **Critère de sortie** : avant `1.0.0`, version interne + gates vertes suffisent. À partir de la première stable `1.0.0`, tag, PyPI, GitHub Release et provenance redeviennent obligatoires.

### 3.6 Déploiement
- **Outils** : `/commit` · skill `git-hygiene` · `check-ci` · plugin `env-protection`.
- **Commande projet** : la porte qualité complète (voir §6), puis `git push`.
- **Critère de sortie** : commits atomiques poussés, CI verte sur `main`.

### 3.7 Maintenance
- **Outils** : `/docs` · `@docs-writer` · `find-todos` · skill `git-hygiene` · `/archive`.
- **Commande projet** : `ruff format --check .` sur le repo entier ; les transcripts bruts archivés sous `docs/audit/**/sessions/**` sont explicitement hors surface Ruff.
- **Critère de sortie** : docs à jour, dette tracée et priorisée.

---

## 4. État courant — 0.2.x PostgreSQL / PG-05

Le snapshot détaillé de l'audit du 2026-10-08 est archivé sous
[`docs/audit/2026-10-08/`](./audit/2026-10-08/README.md). Le statut faisant foi des
findings est [POST-00 Remediation Status](./audit/2026-10-08/POST_00_REMEDIATION_STATUS.md).

```text
Initial LOT roadmap                     ✅ LOT-00 → LOT-34
POST-00 Audit Remediation               ✅
Pre-1.0 PyPI publication guard          ✅
POST-01 Documentation Cleanup           ✅
POST-02 Examples / Cookbook             ✅
POST-03 API Documentation               ✅
POST-04 Dogfooding                      ✅
POST-05 Benchmarks                      ✅
POST-06 Chaos / Fault Injection         ✅
0.2.x PostgreSQL / PG-00                ✅
0.2.x PostgreSQL / PG-01                ✅
0.2.x PostgreSQL / PG-02                ✅
0.2.x PostgreSQL / PG-03                ✅
0.2.x PostgreSQL / PG-04                ✅
0.2.x PostgreSQL / PG-05                🚧 current
```

- **Dernière version publique PyPI** : `0.1.0a3`.
- **Version de développement** : `0.1.0a4`.
- **Politique de publication** : aucun nouveau package PyPI avant une version stable
  `>=1.0.0`; alpha/beta/rc restent non publiables.
- **Quality gates** : Ruff ✅ · mypy strict ✅ · pytest ✅ · coverage ≥85 ✅.
- **Distribution Qualification** : wheel/sdist ✅ sur Python 3.11 / 3.12 / 3.13.
- **Findings B1–B12** : aucun finding ouvert.
- **PG-03 qualifié** : contrat partagé InMemory/SQLite/PostgreSQL, 130 tests PostgreSQL live, couverture PostgreSQL 87,88% avec floor 85%.
- **PG-04 qualifié** : 138 tests PostgreSQL live, Scheduler/run_pending, retry, outbox, reconciliation, crash recovery et contention multi-worker; couverture PostgreSQL 88,59%.
- **Étape active** : durcir isolation, lock ordering, retry transactionnel, lifecycle connexions, migrations et support matrix avant exposition publique du factory.

---

## 5. Backlog de remédiation — disposition

| Finding | État | Preuve principale |
|---|---|---|
| B1 — cancellation vs retry | ✅ FIXED | `c0601e9` |
| B2 — transition race / runtime | ✅ FIXED | PR #44 / `0a5455b` |
| B3 — Ruff release preflight | ✅ FIXED | `394c246` |
| B4 — GitHub Release | ✅ HISTORICAL / RESOLVED | `v0.1.0a3` publiée |
| B5 — SQLite bootstrap | ✅ FIXED | PR #45 / `f310994` |
| B6 — admission lock conflict | ✅ FIXED | PR #46 / `0fe4d8a` |
| B7 — target registry before commit | ✅ FIXED | PR #51 / `1c3e31c` |
| B8/B9 — persistence parity | ✅ FIXED | PR #48 / `cbf3904` |
| B10 — HTTP cleanup / redirects | ✅ FIXED | PR #49 / `c1c85e3` |
| B11 — README status | ✅ FIXED | README courant |
| B12 — specs non versionnées | ✅ FIXED | `0d09e34` |

### Suite

1. PG-00 — fondation PostgreSQL / CI / bootstrap ;
2. PG-01 — core repositories + UnitOfWork ;
3. PG-02 — coordination / outbox / retention ;
4. PG-03/PG-04 — parité et E2E multi-worker ;
5. PG-05 — hardening, puis Async Executor et executor plugin registry.

Aucune publication PyPI intermédiaire n'est nécessaire pour franchir ces étapes.

---

## 6. Porte qualité du projet (référence)

À exécuter depuis la racine du dépôt, dans cet ordre (identique à la CI) :

```bash
pip install -e ".[dev]"          # une fois : hooks pre-commit en language: system
ruff check .                     # lint
ruff format --check .            # format (ruff format . pour corriger)
mypy src                         # typage strict (src uniquement)
pytest -q --cov=pyschedulekit    # suite + couverture ; fail_under = 85
```

Raccourci outil : `check-ci`. Pièges connus : `pytest` doit tourner depuis la racine (chemins relatifs des tests release) ; `rg`/`find-todos` pour la dette.

---

## 7. Voir aussi

- [`docs/README.md`](./README.md) — sommaire de toute la documentation.
- [`POST-00 Remediation Status`](./audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) — état courant et preuves.
- [`RECOMMANDATIONS.md`](./audit/2026-10-08/RECOMMANDATIONS.md) — plan de remédiation historique issu de l'audit.
- [`CODEBASE_ANALYSIS.md`](./audit/2026-10-08/CODEBASE_ANALYSIS.md) — faits vérifiés et bugs B1-B12.
- [`ANALYSE_CRITIQUE.md`](./audit/2026-10-08/ANALYSE_CRITIQUE.md) — verdict et notes /10.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — référence technique.
- [`AGENTS.md`](../AGENTS.md) — commandes et gotchas pour les agents.

---

*Dernière mise à jour : 2026-10-09 — PostgreSQL PG-05.*
