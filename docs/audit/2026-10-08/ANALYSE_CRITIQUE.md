# Analyse critique — PyScheduleKit

> **AUDIT SNAPSHOT — 2026-10-08.** Cette analyse critique reste attachée à l'état du
> code observé lors de l'audit. Les notes et critiques ci-dessous sont conservées comme
> historique de décision. Pour l'état courant des corrections, voir
> [POST-00 Remediation Status](./POST_00_REMEDIATION_STATUS.md).

> Document d'**opinion** : évalue les choix de conception, pas seulement l'état des lieux. Les faits bruts et la liste exhaustive des bugs sont dans [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md) ; ici on répond à la question « ce code est-il bon, et pourquoi ? ».

---

## 1. Verdict global

| Dimension | Note /10 | Commentaire |
|---|---|---|
| Fonctionnel | 7 | Le cœur (triggers, matérialisation, claims, recovery) est correct et prouvé — mais deux garanties écrites sont fausses en pratique : « cancellation gagne sur retry » (B1) et la résilience de `run_forever` (B2). |
| Sécurité | 8 | Modèle de confiance explicite, zéro secret en clair dans le code ou l'historique, domaine interdit `os.getenv` par test. Reste deux durcissements manquants (redirections HTTP, `.env` orphelin) et un épingle-Actions incohérent. |
| Architecture | 9 | Couches nettes, domaine pur **vérifié par test d'architecture**, ports injectés, manifeste d'API contractuel. Le seul reproche sérieux : deux persistance-jumeaux sans filet de parité (B8/B9). |
| Qualité de code | 8 | `ruff check` + `mypy --strict` verts sur `src/`, style homogène, invariants d'agrégats assertés. Le format a dérapé sur un seul fichier — suffisant pour tuer la CI (B3). |
| Testabilité / DX | 8 | 453 tests déterministes en 1,6 s, `MutableClock` livrés, contrat d'API testé. Manquent les tests d'adversité (B6/B7 non couverts), le seuil de couverture et la parité mémoire/SQLite. |
| Production-readiness | 6 | Paquet alpha publié, qualification de distribution sérieuse — mais CI rouge sur `main` (B3), pipeline de release à moitié cassé (B4), bootstrap non atomique (B5). |

**En une phrase** : **un excellent soclo de conception dont les garanties sont déclarées dans les docs et testées sur le chemin heureux, mais défendues par personne sur les chemins de transition — et dont les filets de sécurité (CI, release) ont été laissés tomber.**

---

## 2. Le problème n'est pas les bugs, c'est la chaîne de suppositions sans propriétaire

Derrière B1, B2, B4, B6 et B7, un seul mécanisme revient : **chaque couche suppose que la couche voisine a vérifié l'invariant, et aucun test ne force l'enchaînement adverse qui révèlerait l'écart.**

- LOT-17 écrit « Cancellation always wins over retry » (`LOT-17_CANCELLATION_REFINEMENTS.md:115`) et trace le flux `Attempt RUNNING → CANCELLED → CANCELLED → no RetryEvaluator decision`. Le test d'e2e (`test_cancellation_e2e.py:30`) valide ce flux… **coopératif**, où la cible obéit au token. Le runner suppose que l'exécutor a testé le token, l'exécutor timeout ne le teste pas (`local_executor.py:186-187`), `finish_attempt` suppose que l'appelant n'arrivera pas avec `retry_at` pendant une cancellation (`execution.py:520-527`), et personne ne consulte `cancellation_requested_at` côté runnable. L'invariant n'a **aucun point d'application unique** : il est distribué sur 4 couches qui se font mutuellement confiance.
- `run_pending` suppose que `start_attempt` ne peut pas lever (`run_pending.py:194-224` liste cinq exceptions… pas celle qui est effectivement levable), et `run_forever` suppose que `run_pending` ne lève jamais (`runtime.py:103-104`, aucune garde). Deux suppositions, aucune test adverse.
- Le job `create-github-release` suppose que quelqu'un a fait le `checkout` (`release-candidate.yml:201-234` : personne ne l'a fait). Le branchement conflit du verrou d'admission suppose… que la branche voisine a raison (`concurrency.py:99-106`). `add_schedule` suppose que le commit passe (`api/scheduler.py:271` vs `:302`).

**Pourquoi corriger la liste ne suffit pas** : chaque fix isolé rendrait le symptôme vert, sans changer le principe. Tant qu'une garantie n'a pas (a) un **seul point d'application** et (b) un **test qui force l'interleaving adversaire** (annulation pendant timeout, conflit pendant admission, commit qui échoue pendant registration), la garantie suivante rééchouera au même endroit. C'est exactement ce que montre le deuxième pattern du dépôt : **la tolérance à la rupture du filet** — B3 (un fichier commité non formaté, CI rouge au moment du commit), B12 (`docs/specs/` jamais versionnés malgré la règle « toute garantie mappe à un test »), B4 re-tiré en `a3` après l'échec `a2` **sans correction du workflow**. Le processus produit du contenu plus vite qu'il ne consolide ses propres barrières.

---

## 3. Critiques d'architecture

### 3.1 Deux persistance-jumeaux, un seul contrat (choix défendable, mal appliqué)

Le choix `memory.py` + `sqlite.py` est légitime (zéro dépendance, tests sans I/O, port testable). Mais la parité est **manuelle et non testée** : SQLite enforce des FK (`sqlite_schema.py:49,79,115`) que le mémoire ignore (B8) ; le mémoire lit ses propres staged dans `list_pending` mais pas dans `has_pending` (B9). Le double test du projet valide donc des graphs que la production refuse. Un **test de parité paramétré** (même scénario d'opérations, deux adaptateurs, même résultat/erreur) coûterait ~1 journée et éliminerait toute la classe B8/B9.

### 3.2 La cancellation est un état réparti sur trois endroits sans coordinateur

`cancellation_requested_at` (durable, domaine), le `CancellationToken` (process-local, `infrastructure/cancellation.py:54-56`), et l'outcome de l'exécutor (coopératif ou non). Rien ne garantit qu'ils convergent : c'est B1 dans sa généralité, et la version multi-processus est pire encore — `Scheduler.cancel_execution` ne pose le token **que dans son propre processus** (`api/scheduler.py:379-392`), alors que `list_runnable` ne filtre jamais sur `cancellation_requested_at` (`sqlite.py:785`). Le fencing des claims est méticuleusement conçu, mais l'annulation transverses-workers n'a pas de design équivalent. Erreur de conception : une garantie de safety distribuée sans acteur central.

### 3.3 `run_forever` sans supervision (erreur, pas choix)

`runtime.py:103-104` appelle `run_pending` sans `try/except` : une seule erreur de transition (B2), un seul bug futur d'exécuteur, et la boucle **meurt silencieusement**, leacquis du claim n'étant jamais libéré (le `finally` libère l'événement, pas la lease). Toute boucle de longue haleine a besoin d'une boundary : rattraper, logger via `ObservationSink`, libérer, continuer. Le projet possède déjà tous les primitives (observabilité, recovery) — elles ne sont juste pas branchées sur la boucle elle-même.

### 3.4 État croisé registre/persistance sans point de vérité (B7)

Le registre de cibles (`local:{id}`) est de l'état **process-local mutable**, modifié dans `add_schedule` avant que la DB ne confirme la schedule (`api/scheduler.py:271` → commit `:302`). Aucun des deux états ne commande : en cas d'échec, ils divergent et le retry produit la mauvaise erreur. Le registre devrait être dérivé (register après commit) ou versionné avec la schedule.

### 3.5 Un projet qui vise le multi-processus, un bootstrap mono-processus (B5)

Toute la pile coordination (claims, fencing, verrous d'admission) est pensée pour N travailleurs, mais l'initialisation de schéma teste l'existence **hors transaction** puis `CREATE TABLE` sans `IF NOT EXISTS` (`sqlite_schema.py:274` puis `:328`). Le premier démarrage simultané de deux workers — le scénario même que les tests `test_multi_worker_admission.py` présupposent — casse. Contradiction nette entre l'ambition et le chemin du premier octet.

---

## 4. Critique sécurité (au-delà de la liste des failles)

1. **La menace réelle n'est pas l'injection, c'est l'effet de bord dupliqué.** Pour un scheduler, le scénario de compromission réaliste n'est pas un attaquant distant mais un cancel qui n'annule pas (B1) : la cible (déploiement, envoi d'e-mail, écriture métier) **re-exécute ses effets non idempotents** après annulation explicite de l'utilisateur. C'est une faille d'intégrité de safety, invisible au scan classique. Aucun threat model écrit n'a jamais envisagé « l'utilisateur annule et le système désobéit ».
2. **Le SSRF latent est assumé sans le dire.** `HttpExecutor` suit les redirections par défaut (`http_executor.py:161`) ; le registre valide l'URL d'origine (`http_executor.py:52-76`) mais pas sa réécriture à vol d'oiseau. Un `HttpRequestSpec` compromis ou mal documenté pointant vers un hôtes interne après redirection = requête serveur forgée. La défense actuelle est « la cible doit être enregistrée à la main » — correct, mais ce n'est pas une contrôle, c'est une espérance ; elle devrait être écrite dans la doc de sécurité et bloquée en code (limite de redirections + re-validation de l'hôte).
3. **Le dépôt lui-même reçoit des artefacts d'un autre workflow.** Le `.env` orphelin avec `API_TOKEN` — que **rien ne lit** (`os.getenv` interdit dans le domaine, absent du reste) — montre qu'un fichier de « web app » s'est glissé dans un projet qui n'en est pas un. Le bon réflexe (`gitignore`) existe ; le réflexe manqué est le nettoyage. La règle d'hygiène devrait être : aucun fichier de configuration non consommé par le code.
4. **La chaîne d'approvisionnement GA est inégalement épinglée.** `pypa/gh-action-pypi-publish` et `actions/attest` sont épinglés par SHA (`release-candidate.yml:186,199`), mais `checkout`/`setup-python` non, avec en prime `checkout@v4` dans `ci.yml:26` contre `@v6` ailleurs. Les tags flottants d'Actions sont la porte d'entrée standard ; avoir épinglé les deux étapes les plus sensibles (publication, provenance) est la bonne idée, l'avoir laissé le reste flotter rend le dispositif incohérent.

---

## 5. Critique du frontend / interface

Pas d'UI ni de CLI : l'« interface » est l'API publique + le README. Trois reproches :

- **Le README ment sur la version** (B11 : affiche `0.1.0a1`, réel `0.1.0a3`) — symptôme d'un README de 898 lignes maintenu par recopiage au lieu d'être dérivé (une ligne `python -c "import pyschedulekit; print(pyschedulekit.__version__)"` suffirait).
- **La frontière `experimental/` est honnête** (aucune promesse avant 1.0, redirections dépréciées testées) mais **invisible dans le README** : un lecteur ne voit pas, en surface, ce qui est stable (`api/_manifest.py`) et ce qui ne l'est pas.
- **Les erreurs sont bien façonnées mais sous-documentées** : `DuplicateScheduleError` vs `DuplicateTargetRegistrationError` (B7), `InvalidExecutionTransitionError` qui n'est pas un `PersistenceConflictError` (B2) — les noms sont bons, le contrat de propagé dans `run_pending`/`run_forever` ne l'est pas. Le consommateur d'une bibliothèque de scheduling a besoin d'un tableau « quelle exception, quelle action » ; il n'existe pas.

---

## 6. Critique du processus (DX, outillage, livrable)

- **La CI a été cassée au moment même du commit** : B3 signifie que `ad4a494` (HEAD) a été poussé sans exécuter `ruff format --check .` localement alors que la règle de projet dit explicitement « run lint and typecheck before committing ». Le filet existe, il n'a pas été honoré → coût : **100 % de la grille qualité bloquée** sur chaque push depuis.
- **Le pipeline de release a échoué deux fois de suite sans correction de cause racine** : `v0.1.0a2` (échange OIDC TestPyPI), puis `v0.1.0a3` (B4) — le workflow a été re-tiré tel quel. Résultat : PyPi et GitHub Release **divergent** (paquet public, release absente), ce qui est exactement l'incohérence qu'une release engineering sérieuse doit éviter. Et `release-readiness` refuse les tags existants → le rattrapage n'est pas un `re-run`.
- **La couverture n'est pas un filet** : 86 % mesurés, `fail_under` absent — rien n'empêche une régression vers 70 % en silence. De même, les tests les plus précieux (B6 lignes 99-106, B7) sont précisément sur les chemins non couverts.
- **`pytest` n'est portable qu'à la racine** : les tests release ouvrent `.github/workflows/...` en chemin relatif (`test_pypi_workflow.py:5`), les hooks pre-commit sont `language: system` (deps exigées dans l'env actif) — l'environnement de dev est fonctionnel mais fragile, et c'est déjà écrit dans `AGENTS.md` plutôt que corrigé.
- **Points positifs du processus** : règle « toute garantie → un test exécutable » respectée sur le domaine, docs LOT/REL structurées, preflight/qualification de distribution au-dessus de la moyenne pour une alpha.

---

## 7. Ce qui mérite d'être sauvegardé

- **Le domaine pur**, avec ses tests d'architecture interdisant imports transverses, heure murale et `os.getenv` — rarement vu appliqué aussi littéralement.
- **Le contrat d'API verrouillé** (`_manifest.STABLE_PUBLIC_NAMES` + `test_public_api_contract.py`) : identité des objets, redirections de dépréciation, version installée == version runtime. C'est ce qui rendra la 0.1 stable sûre.
- **Le modèle de transactions SQLite** : `BEGIN IMMEDIATE`, validate-then-apply, rollback systématique, CAS de version, FK activées — la base est saine (B5 est le seul trou du bootstrap).
- **La coordination multi-travailleurs** : fencing par `generation`, leases avec heartbeat, verrous d'admission durables, avec tests dédiés. Le plus difficile du domaine est déjà construit.
- **L'écosystème de test** : `MutableClock`/`FixedClock` livrés, 453 tests en 1,63 s, zéro sleep de horloge, e2e réels.
- **La discipline documentaire** : 35 LOTs, 7 RELs, runbook de release — l'inverse du « le code parle » ; ici les décisions sont écrites (ce qui rend B1 facile à prouver : la garantie violée est écrite noir sur blanc).

---

## 8. Réparer ou réécrire ?

| Option | Effort estimé | Verdict |
|---|---|---|
| **A. Corriger sur place** (Phases 0-3 de [RECOMMANDATIONS.md](./RECOMMANDATIONS.md)) | ~5 jours | **Recommandé.** Les 12 bugs sont localisés, indépendants, et prouvables par tests de non-régression. Le socle (domaine, transactions, fencing) est sain. |
| B. Réécrire la couche `application` (runner/runtime/cancellation) | 2-3 semaines | Refusé : `concurrency.py`/`claims`/`recovery` sont corrects et testés ; on réécrirait 90 % de correct pour les 10 % fautifs (B1/B2), avec risque de régression sur le fencing. |
| C. Réécrire le projet depuis zéro | 4+ semaines | Refusé : la valeur (domaine pur + contrat d'API + écosystème de test) est précisément ce qui est bon ; réécrire perd le 9/10 d'architecture pour guérir un 6/10 de production-readiness. |
| D. Renoncer au double adaptateur mémoire (SQLite seul) | 1 semaine | Refusé : le mémoire est ce qui rend la suite à 1,63 s ; la parité se règle par un **test paramétré**, pas en supprimant un adaptateur. |

**Quel que soit le chemin, trois non-négociables :**
1. **Aucun fix sans test qui reproduit le bug d'abord** (règle déjà inscrite dans `AGENTS.md` : toute garantie supportée mappe à un test exécutable).
2. **La CI revient au vert avant toute autre évolution** (B3 en P0) : tant que `ruff format --check` échoue, aucun filet ne fonctionne.
3. **La release `v0.1.0a3` est résolue proprement** (B4) : soit correctif du workflow + création manuelle du GitHub Release, soit bump `a4` — jamais les deux registres (PyPI/GitHub) en désaccord.

---

## 9. Conclusion

PyScheduleKit n'est pas un « bon projet de débutant » : ses décisions structurantes (domaine pur testé, manifeste d'API, transactions, fencing, zéro dépendance) sont celles d'ingénieurs expérimentés, et les 453 tests prouvent que le chemin heureux est réellement maîtrisé. Ce que l'audit révèle est plus subtil : **les garanties les plus visibles du projet — l'annulation gagne sur le retry, la boucle survit aux erreurs, la release sort d'un seul tenant — sont écrites, documentées, et précisément les trois qui ne tiennent pas**, parce qu'elles reposent sur des chaînes de suppositions jamais forcées par un test adverse, pendant que les filets (CI, format, versionnement des specs) se sont relâchés en silence. Les douze bugs sont tous à portée de fix local avec un test de non-régression ; aucun ne justifie une réécriture. En appliquant les phases 0-3, le projet atteint une maturité rare pour une bibliothèque de scheduling de cette taille.

> **Note finale : 7/10 en l'état — potentiel 9/10 atteignable en ~1 semaine de correctifs (Phases 0-3), à condition de rétablir la CI en P0 et de traiter B1/B2 avec des tests d'interleaving adversaire avant toute nouvelle fonctionnalité.**
