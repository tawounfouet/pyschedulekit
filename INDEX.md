# INDEX — Documentation du projet

Point d'entrée de la documentation PyScheduleKit. Depuis l'audit du 2026-10-08, la
documentation distingue explicitement **snapshot historique** et **état courant**.

---

## 1. Documents de référence

| Document | Statut | Rôle | À lire quand… |
|---|---|---|---|
| [README.md](./README.md) | **CURRENT** | Vue produit, état public, capacités, API et développement | on découvre ou utilise le projet |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | **CURRENT** | Architecture, flux, invariants et limites actuelles | on modifie le code ou le design |
| [AGENTS.md](./AGENTS.md) | **CURRENT** | Commandes, conventions et gotchas pour humains/agents | on travaille dans le dépôt |
| [POST-00 Remediation Status](./docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) | **CURRENT** | Disposition B1–B12, preuves de correction, état POST-00 | on veut savoir ce qui est encore vrai aujourd'hui |
| [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) | **SNAPSHOT 2026-10-08** | Faits et findings B1–B12 observés pendant l'audit | on veut comprendre ce que l'audit a réellement trouvé |
| [ANALYSE_CRITIQUE.md](./ANALYSE_CRITIQUE.md) | **SNAPSHOT 2026-10-08** | Opinion et scoring basés sur l'état audité | on veut comprendre le diagnostic critique initial |
| [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) | **SNAPSHOT / PLAN** | Plan de remédiation produit à partir de l'audit | on veut retrouver la logique des corrections |
| [CHANGELOG.md](./CHANGELOG.md) | **HISTORY** | Historique des versions publiques | on cherche les changements par version |

Règle de lecture :

```text
question sur ce qui était cassé le 8 octobre
    → audit snapshot

question sur ce qui est vrai maintenant
    → README / ARCHITECTURE / AGENTS / POST-00 status
```

---

## 2. Navigation par tâche

| Je veux… | Aller à |
|---|---|
| Lancer les quality gates / hooks | [AGENTS.md](./AGENTS.md) §Commands |
| Comprendre un cycle complet `run_pending()` | [ARCHITECTURE.md](./ARCHITECTURE.md) §2.2 |
| Comprendre cancellation / retry / timeout | [ARCHITECTURE.md](./ARCHITECTURE.md) §2.3 |
| Voir les findings originaux B1–B12 | [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) §5 |
| Connaître leur statut actuel | [POST-00 Remediation Status](./docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) §2 |
| Comprendre pourquoi POST-00 a été lancé | [ANALYSE_CRITIQUE.md](./ANALYSE_CRITIQUE.md) |
| Retrouver le plan de correction initial | [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) |
| Voir la parité Memory / SQLite | [POST-00 Remediation Status](./docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) §4.2 |
| Comprendre la surface stable vs expérimentale | [ARCHITECTURE.md](./ARCHITECTURE.md) §4 |
| Gérer une release | `docs/release/` + [AGENTS.md](./AGENTS.md) |
| Voir le pipeline de go-live réellement utilisé | [README.md](./README.md) §Project status |
| Préparer `0.1.0a4` | [POST-00 Remediation Status](./docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) §7–8 |

---

## 3. Carte rapide du code source

| Package | Point d'entrée | Cœur du système |
|---|---|---|
| `src/pyschedulekit/api/` | `Scheduler` | façade publique + manifeste de stabilité |
| `src/pyschedulekit/domain/` | time / triggers / schedule / execution | invariants métier et machines à états |
| `src/pyschedulekit/application/` | `run_pending.py` | orchestration, runtime, recovery, claims, admission |
| `src/pyschedulekit/ports/` | persistence / executor / time | frontières injectées |
| `src/pyschedulekit/infrastructure/` | SQLite / Memory / executors | adaptateurs qualifiés par tests |
| `src/pyschedulekit/testing/` | `MutableClock`, `FixedClock` | pilotage déterministe du temps |
| `tests/integration/infrastructure/` | adapter parity | contrat observable partagé Memory / SQLite |
| `tests/acceptance/` | qualification publique | exercice consommateur / package |
| `scripts/` | release verification | build, preflight, smoke et qualification |

Fichiers à connaître avant une modification structurante :

- **`src/pyschedulekit/api/_manifest.py`** — contrat des exports publics.
- **`src/pyschedulekit/_version.py`** — source unique de version.
- **`src/pyschedulekit/domain/execution.py`** — transitions et invariants d'exécution.
- **`src/pyschedulekit/infrastructure/sqlite_schema.py`** — intégrité durable SQLite.
- **`src/pyschedulekit/infrastructure/memory.py`** — doit respecter le même contrat observable que SQLite.
- **`.github/workflows/`** — workflows testés comme code ; actions SHA-pinnées.

---

## 4. Repères courants

État vérifié sur `main` après POST-00G et la fermeture de B7 :

- **Version publique :** `0.1.0a3`.
- **GitHub Release :** `v0.1.0a3`, prerelease immutable, wheel + sdist + checksum.
- **Runtime dependencies :** 0.
- **Python :** 3.11 / 3.12 / 3.13.
- **Source type-checkée :** 65 fichiers Python, `mypy --strict` vert.
- **Tests :** 493 passants sur Python 3.11 dans le run de consolidation.
- **Couverture :** 86.61 %, avec seuil bloquant `fail_under = 85`.
- **Qualité :** Ruff lint ✅ · Ruff format ✅ · mypy ✅ · pytest ✅.
- **Distribution :** clean-install wheel/sdist ✅ sur Python 3.11 / 3.12 / 3.13.
- **Findings B1–B12 :** aucun finding ouvert ; historique et preuves dans le registre POST-00.
- **Release cible suivante :** `0.1.0a4` — stabilization & adversarial hardening.

Les métriques présentes dans les documents d'audit racine restent celles du **snapshot
2026-10-08** et ne doivent pas être confondues avec ces repères courants.

---

*Dernière mise à jour : 2026-10-09 — POST-00H audit documentation consolidation.*
