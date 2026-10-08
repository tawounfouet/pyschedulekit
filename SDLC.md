# SDLC — PyScheduleKit

> Guide du cycle de vie de développement : les 7 phases, les outils OpenCode associés, et où en est le projet. Ce document complète [`INDEX.md`](./INDEX.md) (sommaire) et [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md) (plan de remédiation).

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
- **Critère de sortie** : plus d'issue bloquante ; faits consignés dans [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md) / [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md).

### 3.5 Release
- **Outils** : `/release` · `@release-prep` · skill `release-prep` · `diff-summary`.
- **Commande projet** : `python -m scripts.release_preflight` · `python -m scripts.verify_distribution dist` · `python scripts/smoke_installed_package.py`.
- **Critère de sortie** : tag + GitHub Release alignés avec PyPI (voir bug **B4**).

### 3.6 Déploiement
- **Outils** : `/commit` · skill `git-hygiene` · `check-ci` · plugin `env-protection`.
- **Commande projet** : la porte qualité complète (voir §6), puis `git push`.
- **Critère de sortie** : commits atomiques poussés, CI verte sur `main`.

### 3.7 Maintenance
- **Outils** : `/docs` · `@docs-writer` · `find-todos` · skill `git-hygiene` · `/archive`.
- **Commande projet** : `ruff format --check .` sur le repo entier (les artefacts d'agent type `session-ses_*.md` doivent être ignorés).
- **Critère de sortie** : docs à jour, dette tracée et priorisée.

---

## 4. Où en est le projet (2026-10-08)

```text
 1 Plan ──► 2 Build ──► 3 Test ──► 4 Review ──► 5 Release ──► 6 Deploy ──► 7 Maintain
   ✅        ✅          ✅          ✅           ⚠️            ⏳           🟡
 specs     B1/B3/B12   4 tests      audit       a3 sur PyPI  3 commits   docs d'audit
 LOTs      committés   +457 pass   + sécurité  GH Rel KO    non push    non commitées
```

- **Courant** : phase **6 (Déploiement)**, en transition vers **7 (Maintenance)**, avec un résidu **phase 5** (B4).
- **Portes qualité** : `ruff check` ✅ · `ruff format --check` ❌ (artefact non suivi) · `mypy src` ✅ · `pytest` ✅ 457.
- **Dernier tag** : `v0.1.0a3`.

---

## 5. Backlog par phase

| Bug | Phase cible | État | Réf. |
|---|---|---|---|
| B1 — annulation vs retry | 2/3 | ✅ corrigé (`c0601e9`) | CODEBASE §5 |
| B3 — CI format rouge | 2/6 | ✅ corrigé (`394c246`) | CODEBASE §5 |
| B12 — `docs/specs/` non versionné | 7 | ✅ corrigé (`0d09e34`) | CODEBASE §5 |
| B4 — GitHub Release manquante | 5 | ⬜ ouvert | RECOMMANDATIONS §Phase 0.2 |
| B2 — `run_pending` casse la boucle | 2/3 | ⬜ ouvert | RECOMMANDATIONS §2.2 |
| B7 — registre cible avant commit | 2 | ⬜ ouvert | RECOMMANDATIONS §2.3 |
| B9 — `has_pending` ignore le staged | 2 | ⬜ ouvert | RECOMMANDATIONS §2.4 |
| B5 — init schéma non atomique | 3 | ⬜ ouvert | RECOMMANDATIONS §3.2 |
| B6 — verrou d'admission non libéré | 3 | ⬜ ouvert | RECOMMANDATIONS §3.3 |
| B8 — FK manquantes en mémoire | 3 | ⬜ ouvert | RECOMMANDATIONS §3.4 |
| B10 — fuite HTTPError | 4 | ⬜ ouvert | RECOMMANDATIONS §4.1 |
| B11 — version README obsolète | 7 | ⬜ ouvert (dans `README.md` modifié) | CODEBASE §5 |

### Prochaine étape recommandée
1. **7 — Maintenance** : assainir (`.gitignore` pour `temp/` et `session-ses_*.md`), puis committer les 6 livrables d'audit + `README.md` + `.gitignore` (`/commit`).
2. **6 — Déploiement** : `git push` après porte qualité verte.
3. **5 — Release** : corriger B4 (`actions/checkout` dans `create-github-release`) et rattraper la release `v0.1.0a3`.
4. **2/3 — Build/Test** : enchaîner B2, puis B5/B6/B8 (voir [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md)).

---

## 6. Porte qualité du projet (référence)

À exécuter depuis la racine du dépôt, dans cet ordre (identique à la CI) :

```bash
pip install -e ".[dev]"          # une fois : hooks pre-commit en language: system
ruff check .                     # lint
ruff format --check .            # format (ruff format . pour corriger)
mypy src                         # typage strict (src uniquement)
pytest -q --cov=pyschedulekit    # suite + couverture (457 tests, 86 %)
```

Raccourci outil : `check-ci`. Pièges connus : `pytest` doit tourner depuis la racine (chemins relatifs des tests release) ; `rg`/`find-todos` pour la dette.

---

## 7. Voir aussi

- [`INDEX.md`](./INDEX.md) — sommaire de toute la documentation.
- [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md) — plan de remédiation (Phases 0-5, correctifs prêts à l'emploi).
- [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md) — faits vérifiés et bugs B1-B12.
- [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md) — verdict et notes /10.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — référence technique.
- [`AGENTS.md`](./AGENTS.md) — commandes et gotchas pour les agents.

---

*Dernière mise à jour : 2026-10-08.*
