# Scheduling — Introduction au domaine

**Document :** `01_SCHEDULING_DOMAIN_INTRODUCTION.md`  
**Projet :** PyScheduleKit  
**Statut :** Document de fondation pédagogique  
**Nature :** Introduction au domaine métier  
**Prérequis :** `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`

---

# 1. Introduction

Le **scheduling** désigne l'ensemble des mécanismes permettant de décider :

> **quand une action doit devenir exécutable.**

Cette définition paraît simple.

Pourtant, dès qu'un système doit fonctionner durablement, survivre aux redémarrages, gérer plusieurs tâches, plusieurs fuseaux horaires, des exécutions manquées ou des chevauchements, le scheduling devient un véritable domaine technique.

Le problème n'est plus simplement :

```text
Attendre jusqu'à 08:00
        ↓
Exécuter une fonction
```

Il devient :

```text
Quelle heure est-il réellement ?
        ↓
Quelle règle temporelle s'applique ?
        ↓
Quelle occurrence est attendue ?
        ↓
Est-elle déjà passée ?
        ↓
Est-elle encore valide ?
        ↓
Une autre exécution est-elle active ?
        ↓
L'exécution doit-elle être créée ?
        ↓
À qui doit-elle être soumise ?
        ↓
Comment conserver l'historique ?
        ↓
Quelle est la prochaine occurrence ?
```

Le scheduling se situe donc à l'intersection de plusieurs problématiques :

```text
temps
récurrence
calendrier
état
exécution
concurrence
persistance
résilience
observabilité
distribution
```

---

# 2. Le besoin fondamental

Dans un système logiciel, certaines actions ne doivent pas nécessairement être exécutées immédiatement.

Elles peuvent être déclenchées :

```text
à une date donnée
à une heure précise
après un délai
à intervalles réguliers
selon une règle calendaire
selon des jours ouvrés
selon une fenêtre temporelle
```

Exemples :

```text
2026-10-01 à 09:00
→ envoyer un rappel

toutes les 30 secondes
→ sonder une ressource

tous les jours à 06:00
→ lancer une ingestion

chaque lundi à 08:00
→ produire un reporting hebdomadaire

le premier jour ouvré du mois
→ clôturer une période

toutes les 5 minutes entre 08:00 et 18:00
→ synchroniser un système
```

Le scheduling transforme donc une règle exprimée sur le temps en une ou plusieurs **occurrences d'exécution**.

---

# 3. Le scheduling comme fonction de transformation

On peut représenter le cœur du domaine par :

```text
Temporal Rule
     │
     ▼
Occurrence Calculation
     │
     ▼
Execution Decision
     │
     ▼
Execution Request
```

Mathématiquement, on pourrait simplifier l'idée ainsi :

```text
Schedule + Time Context
        ↓
Next Occurrence
```

Puis :

```text
Current Time >= Next Occurrence
        ↓
Execution becomes due
```

Cette vision permet immédiatement de séparer deux responsabilités.

## Calcul

```text
Quand la prochaine occurrence doit-elle avoir lieu ?
```

## Décision

```text
Cette occurrence doit-elle maintenant produire une exécution ?
```

Ces deux questions sont liées, mais elles ne sont pas identiques.

---

# 4. Scheduling versus simple attente

Un mécanisme élémentaire peut être écrit comme :

```python
sleep(60)
execute()
```

Cela permet de différer une action.

Mais ce n'est pas encore un véritable système de scheduling.

Le simple `sleep` exprime :

```text
attendre une durée
```

alors qu'un scheduler doit être capable de raisonner sur :

```text
une date absolue
une récurrence
un calendrier
un fuseau horaire
un état persistant
une exécution passée
une exécution manquée
une future occurrence
```

Comparaison :

```text
sleep(3600)

"attends une heure"
```

contre :

```text
CronTrigger("0 8 * * MON")
```

qui signifie conceptuellement :

```text
trouve chaque lundi
calcule 08:00
applique le fuseau horaire
détermine la prochaine occurrence valide
```

---

# 5. Les trois questions fondamentales

Le scheduling peut être étudié autour de trois questions.

```text
WHAT?
WHEN?
WHAT IF?
```

---

## 5.1 WHAT?

> Que souhaite-t-on exécuter ?

Cela peut être :

```text
une fonction
une commande
un workflow
une requête
une ingestion
une transformation
une tâche distante
un message
```

On peut représenter cela par un `Job`, une `Operation` ou un `Target`.

---

## 5.2 WHEN?

> À quel moment l'action doit-elle être déclenchée ?

Cela implique :

```text
dates
durées
récurrences
calendriers
timezones
triggers
```

---

## 5.3 WHAT IF?

> Que faire lorsque la réalité ne correspond pas au scénario nominal ?

Exemples :

```text
scheduler arrêté
run précédent encore actif
machine surchargée
heure d'été
heure d'hiver
exécution trop tardive
erreur d'exécution
redémarrage
plusieurs schedulers concurrents
```

Le scheduling est précisément intéressant parce qu'un bon moteur doit répondre à ce troisième groupe de questions.

---

# 6. Les notions centrales du domaine

Une première carte du domaine peut être construite ainsi :

```text
                         Scheduling
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
       Time                Planning              Execution
        │                     │                     │
    Instant                  Job                 Execution
    Duration               Schedule              Result
    Timezone               Trigger              Executor
    Calendar              Occurrence
        │                     │
        └──────────┬──────────┘
                   │
                 Policy
                   │
         ┌─────────┼──────────┐
         │         │          │
      Misfire  Concurrency   Retry
```

Ces concepts ne sont pas indépendants.

Ils forment ensemble un modèle cohérent.

---

# 7. Le temps n'est pas seulement une date

En Python, un développeur pourrait être tenté de réduire le temps à :

```python
datetime
```

Mais le domaine du scheduling nécessite plusieurs concepts.

---

## 7.1 Instant

Un point précis sur la ligne du temps.

```text
2026-09-28T06:00:00Z
```

---

## 7.2 LocalDateTime

Une date et une heure exprimées localement.

```text
2026-09-28 08:00
```

Cette valeur seule ne précise pas nécessairement le fuseau horaire.

---

## 7.3 Timezone

Permet d'interpréter une heure locale dans un contexte géographique ou réglementaire.

```text
Europe/Paris
America/New_York
Asia/Tokyo
UTC
```

---

## 7.4 Duration

Une quantité de temps.

```text
5 minutes
2 hours
3 days
```

---

## 7.5 Interval

Une période comprise entre deux instants.

```text
[start, end]
```

---

## 7.6 Calendar

Définit les jours ou périodes considérés comme valides.

Exemples :

```text
jours ouvrés
jours fériés
heures de bureau
fenêtres de maintenance
jours exclus
```

---

## 7.7 Clock

Abstraction fournissant le temps courant.

```text
Clock.now()
```

Cette abstraction paraît simple mais sera importante pour la testabilité et la simulation.

---

# 8. La notion de règle temporelle

Une règle temporelle décrit comment produire des occurrences.

Exemples :

```text
une seule fois le 1er octobre
toutes les 5 minutes
tous les jours à 06:00
chaque lundi
le dernier jour du mois
```

Cette règle ne constitue pas encore nécessairement un `Schedule`.

Elle peut être représentée par un objet :

```text
Trigger
```

dont la responsabilité essentielle serait :

> calculer une prochaine occurrence à partir d'un contexte temporel.

Conceptuellement :

```text
Trigger.next(after)
        ↓
Occurrence
```

---

# 9. Le Trigger

Un `Trigger` est une abstraction centrale du domaine.

Il ne doit pas exécuter une tâche.

Il ne doit pas nécessairement persister quoi que ce soit.

Sa responsabilité fondamentale est de répondre à une question :

> Quelle est la prochaine occurrence temporelle valide ?

Exemple :

```text
IntervalTrigger(5 minutes)
```

peut produire :

```text
10:00
10:05
10:10
10:15
...
```

---

## 9.1 Trigger à date fixe

```text
DateTrigger
```

Produit généralement une seule occurrence.

```text
2026-10-10 14:30
```

---

## 9.2 Trigger par intervalle

```text
IntervalTrigger
```

Produit des occurrences espacées par une durée.

```text
every 5 minutes
```

---

## 9.3 Trigger calendaire

```text
CronTrigger
```

Produit des occurrences basées sur des règles calendaires.

```text
0 6 * * *
```

---

# 10. Le Job

Le `Job` représente ce que le système peut exécuter.

Conceptuellement :

```text
Job
│
├── identity
├── name
├── callable / target
├── arguments
└── metadata
```

Exemple :

```text
generate_invoice_report
```

Le job ne répond pas nécessairement à la question :

```text
quand ?
```

Il répond principalement à :

```text
quoi ?
```

---

# 11. Le Schedule

Le `Schedule` crée le lien entre :

```text
quoi
+
quand
+
selon quelles règles
```

Une représentation simplifiée :

```text
Schedule
│
├── Job
├── Trigger
├── Timezone
├── Calendar
├── MisfirePolicy
├── ConcurrencyPolicy
└── LifecycleState
```

Conceptuellement :

```text
Job
generate_daily_report

+

Trigger
Every day @ 08:00

=

Schedule
daily_report_schedule
```

---

# 12. Schedule versus Job

Cette distinction est importante.

Un même job peut être utilisé par plusieurs schedules.

Exemple :

```text
              generate_report
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
Schedule Europe          Schedule America
08:00 Europe/Paris       08:00 New York
```

Ainsi :

```text
1 Job
N Schedules
```

peut être parfaitement valide.

Le métier exécuté reste identique.

La planification diffère.

---

# 13. La notion d'Occurrence

Une `Occurrence` représente un moment calculé par une règle de scheduling.

Exemple :

```text
Schedule
Every day at 06:00
```

produit conceptuellement :

```text
2026-09-28 06:00
2026-09-29 06:00
2026-09-30 06:00
2026-10-01 06:00
...
```

Chaque valeur constitue une occurrence potentielle.

Une occurrence n'est pas nécessairement encore une exécution.

---

# 14. Occurrence versus Execution

Cette séparation est fondamentale.

```text
Occurrence
    │
    │ décision
    ▼
Execution
```

Une occurrence peut :

```text
être exécutée
être ignorée
être coalescée
être considérée trop ancienne
être annulée
être rejetée
```

Donc :

```text
Occurrence ≠ Execution
```

L'occurrence appartient davantage à la dimension temporelle.

L'exécution appartient au runtime.

---

# 15. Le moment « due »

Une occurrence devient **due** lorsque les conditions temporelles indiquent qu'elle peut ou doit être traitée.

On peut simplifier :

```text
now >= scheduled_at
```

Mais la réalité est plus complexe.

Il faut éventuellement prendre en compte :

```text
grace period
deadline
misfire policy
calendar validity
scheduler ownership
concurrency
execution state
```

Le passage :

```text
SCHEDULED
    ↓
DUE
```

constitue donc une décision importante du moteur.

---

# 16. Le Scheduler

Le scheduler est le composant qui coordonne la dimension temporelle.

Conceptuellement :

```text
Scheduler
    │
    ├── observe time
    ├── load schedules
    ├── calculate due occurrences
    ├── apply policies
    ├── create execution requests
    └── calculate future occurrences
```

Il ne faut pas nécessairement le confondre avec l'executor.

---

# 17. Scheduler versus Executor

Le scheduler répond à :

> **Est-il temps d'exécuter ?**

L'executor répond à :

> **Comment exécuter ?**

```text
Scheduler
   │
   │ submit
   ▼
Executor
   │
   ▼
Execution
```

Exemples d'executors :

```text
InlineExecutor
ThreadExecutor
ProcessExecutor
AsyncExecutor
RemoteExecutor
```

Cette séparation permet de conserver le moteur temporel indépendant du mécanisme d'exécution.

---

# 18. La notion d'Execution

Une `Execution` représente un run concret.

Exemple :

```text
Execution
────────────────────────
execution_id
schedule_id
job_id
scheduled_at
created_at
started_at
finished_at
status
result
error
```

Un schedule récurrent génère donc potentiellement :

```text
Schedule
   │
   ├── Execution 001
   ├── Execution 002
   ├── Execution 003
   └── Execution ...
```

---

# 19. Le cycle de vie nominal

Le scénario idéal peut être représenté ainsi :

```text
Schedule
   │
   ▼
Occurrence calculated
   │
   ▼
Wait
   │
   ▼
Occurrence due
   │
   ▼
Execution requested
   │
   ▼
Queued
   │
   ▼
Running
   │
   ▼
Success
```

Mais ce chemin nominal n'est qu'une partie du problème.

---

# 20. Le monde réel introduit des branches

En pratique :

```text
                 SCHEDULED
                     │
                     ▼
                    DUE
                     │
         ┌───────────┼────────────┐
         │           │            │
         ▼           ▼            ▼
       QUEUED      SKIPPED       MISSED
         │
         ▼
       RUNNING
         │
    ┌────┼─────┐
    │    │     │
    ▼    ▼     ▼
 SUCCESS FAILED CANCELLED
```

Le scheduling est donc également un problème de **gestion d'état**.

---

# 21. Les misfires

Un `misfire` apparaît lorsqu'une occurrence n'a pas pu être traitée au moment prévu.

Exemple :

```text
08:00
execution prévue

08:00 → 08:15
scheduler indisponible

08:15
scheduler redémarre
```

Le système doit décider quoi faire.

Possibilités :

```text
SKIP
RUN_NOW
RESCHEDULE
CATCH_UP
COALESCE
```

Cette décision est une politique explicite.

---

# 22. Catch-up

Supposons :

```text
toutes les heures
```

et un scheduler arrêté pendant 4 heures.

Il peut manquer :

```text
08:00
09:00
10:00
11:00
```

Avec un mécanisme de `catch-up`, le scheduler peut décider de produire plusieurs exécutions.

```text
restart 11:30

↓
08:00 execution
09:00 execution
10:00 execution
11:00 execution
```

Ce comportement peut être souhaitable dans certains domaines et catastrophique dans d'autres.

---

# 23. Coalescing

Le `coalescing` permet de fusionner plusieurs occurrences manquées.

```text
08:00
09:00
10:00
11:00
```

peut devenir :

```text
1 execution at restart
```

On remplace donc :

```text
N missed occurrences
```

par :

```text
1 execution
```

Le coalescing exprime une sémantique métier différente du catch-up.

---

# 24. Le problème des chevauchements

Supposons :

```text
interval = 5 minutes
execution duration = 8 minutes
```

Chronologie :

```text
10:00 ───────── Run #1 ─────────────── 10:08
10:05 ───────── Run #2 ─────────────── 10:13
10:10 ───────── Run #3 ─────────────── 10:18
```

Le système doit décider si ces chevauchements sont acceptables.

---

# 25. Les politiques de concurrence

Quelques possibilités :

```text
ALLOW
    plusieurs runs simultanés

FORBID
    rejeter une nouvelle exécution

QUEUE
    attendre

COALESCE
    fusionner

REPLACE
    remplacer l'exécution active
```

Cette politique ne doit pas être cachée dans l'implémentation.

Elle fait partie du contrat du schedule.

---

# 26. Idempotence et scheduling

Le scheduling pose naturellement la question de l'idempotence.

Supposons qu'un scheduler ignore si une exécution a réellement été lancée avant un crash.

Il peut produire une exécution une seconde fois.

```text
Execution A
   │
   ├── request sent
   │
   └── scheduler crashes

restart
   │
   ▼
Was A executed?
```

Dans les systèmes distribués, garantir exactement une exécution est extrêmement difficile.

Une approche robuste consiste souvent à combiner :

```text
deduplication
idempotence
execution identity
leases
persistence
reconciliation
```

Le scheduler ne peut donc pas être étudié indépendamment de la sémantique d'exécution.

---

# 27. Exactly-once, at-least-once, at-most-once

Ces notions sont importantes pour comprendre les garanties possibles.

## At-most-once

```text
0 ou 1 exécution
```

On préfère perdre une occurrence plutôt que la dupliquer.

---

## At-least-once

```text
1 ou plusieurs exécutions
```

On préfère potentiellement dupliquer plutôt que perdre.

---

## Exactly-once

```text
exactement 1 effet observable
```

Il s'agit généralement d'une garantie beaucoup plus complexe que simplement :

```text
executor called once
```

Cette distinction deviendra importante dans l'étude du scheduling distribué.

---

# 28. Le rôle de la persistance

Un scheduler purement en mémoire peut perdre son état au redémarrage.

Exemple :

```text
Memory

Schedule A
Schedule B
Schedule C

        ↓ crash

∅
```

Un scheduler persistant doit être capable de reconstruire son état.

```text
Persistent Store
       │
       ▼
Schedule A
Schedule B
Schedule C
       │
       ▼
Scheduler Restart
```

La persistance pose alors plusieurs questions :

```text
Que sauvegarder ?

Le trigger ?

La prochaine occurrence ?

L'historique ?

L'état d'exécution ?

Les politiques ?

Les leases ?
```

---

# 29. Source de vérité temporelle

Une question essentielle est :

> `next_run_time` est-il une donnée primaire ou une donnée dérivée ?

Deux approches sont envisageables.

## Approche calculée

```text
Trigger + previous occurrence
        ↓
next_run_time
```

---

## Approche persistée

```text
Store
  ↓
next_run_time
```

En pratique, des architectures hybrides sont fréquentes.

Le choix a des conséquences importantes sur :

```text
consistency
recovery
concurrency
distributed scheduling
```

---

# 30. La boucle du scheduler

Une architecture simple peut fonctionner selon un cycle appelé parfois :

```text
tick
```

Exemple :

```text
while running:

    now = clock.now()

    schedules = store.get_due(now)

    for schedule in schedules:
        process(schedule)

    sleep(...)
```

Conceptuellement :

```text
        ┌───────────────┐
        │     TICK      │
        └───────┬───────┘
                │
                ▼
           Read Clock
                │
                ▼
        Find Due Schedules
                │
                ▼
         Apply Policies
                │
                ▼
        Create Executions
                │
                ▼
       Compute Next Runs
                │
                ▼
             WAIT
                │
                └─────────────→ next tick
```

Cette boucle apparemment simple cache de nombreuses décisions métier.

---

# 31. Polling versus wake-up précis

Deux grandes stratégies peuvent exister.

## Polling

```text
check every second
```

Le scheduler inspecte régulièrement les schedules.

---

## Next-wakeup

```text
next run = 10:05:00
sleep until 10:05:00
```

Le scheduler calcule la prochaine échéance et attend jusqu'à celle-ci.

La deuxième approche peut être plus efficace, mais doit gérer :

```text
new schedules
cancellations
clock changes
external wake-ups
shutdown
```

---

# 32. Monotonic clock versus wall clock

Il faut distinguer deux notions.

## Wall clock

```text
2026-09-28 18:00 Europe/Paris
```

Utilisée pour les règles calendaires.

---

## Monotonic clock

Mesure la progression du temps sans être affectée par certains changements de l'horloge système.

Elle est utile pour :

```text
timeouts
durations
elapsed time
```

Un scheduler sérieux peut avoir besoin des deux.

---

# 33. Fuseaux horaires

Le scheduling calendaire implique inévitablement les timezones.

Exemple :

```text
Every day at 08:00
```

doit préciser :

```text
08:00 where?
```

La réponse pourrait être :

```text
Europe/Paris
```

La différence entre :

```text
08:00 UTC
```

et :

```text
08:00 Europe/Paris
```

n'est pas constante sur toute l'année.

---

# 34. DST — changement d'heure

Le passage heure d'été / heure d'hiver introduit des cas complexes.

Une heure locale peut :

```text
ne jamais exister
```

ou :

```text
exister deux fois
```

Exemple conceptuel :

```text
02:30
```

peut devenir ambigu selon le jour et le fuseau.

Il faut alors définir :

```text
skip?
shift?
first occurrence?
second occurrence?
error?
```

Le scheduling impose donc une compréhension précise de la représentation du temps.

---

# 35. Calendriers métier

Toutes les règles ne peuvent pas être exprimées uniquement par cron.

Exemples :

```text
premier jour ouvré du mois

dernier jour bancaire

tous les jours sauf jours fériés

uniquement pendant une fenêtre de maintenance

chaque vendredi sauf clôture trimestrielle
```

Cela introduit la notion de :

```text
Business Calendar
```

qui peut participer au calcul des occurrences.

---

# 36. Jitter

Lorsqu'un grand nombre de tâches sont planifiées exactement au même instant :

```text
00:00:00
```

une surcharge peut apparaître.

Un `jitter` permet d'ajouter une petite variation.

```text
00:00:00
+
random delay within 30 seconds
```

Résultat potentiel :

```text
Job A → 00:00:03
Job B → 00:00:14
Job C → 00:00:22
```

Cette technique permet de répartir la charge.

---

# 37. Deadline et grace period

Une occurrence peut ne plus avoir de sens après un certain délai.

Exemple :

```text
scheduled_at = 08:00
grace_period = 5 minutes
```

À :

```text
08:03
```

elle peut encore être exécutée.

À :

```text
08:20
```

elle peut être considérée comme trop tardive.

Cela introduit la notion de :

```text
execution window
```

---

# 38. Timeout

Un scheduler peut également avoir besoin de distinguer :

```text
quand lancer une exécution
```

de :

```text
combien de temps elle peut durer
```

Le timeout appartient davantage au runtime d'exécution, mais peut être attaché au contrat du schedule.

Exemple :

```text
Schedule
every hour

TimeoutPolicy
max_duration = 20 minutes
```

---

# 39. Pause et Resume

Un schedule possède généralement un cycle de vie.

```text
ACTIVE
   │
   ▼
PAUSED
   │
   ▼
ACTIVE
```

La pause soulève une question importante :

> Que faire des occurrences qui auraient eu lieu pendant la pause ?

Exemples :

```text
ignore
catch-up
coalesce
resume from next future occurrence
```

Le lifecycle interagit donc avec les politiques temporelles.

---

# 40. Reschedule

Modifier un schedule ne consiste pas simplement à éditer une propriété.

Exemple :

```text
avant
every day @ 06:00

après
every day @ 08:00
```

Questions :

```text
Que devient next_run_time ?

Que faire d'une occurrence déjà due ?

Que faire d'une execution queued ?

À partir de quand la nouvelle règle s'applique-t-elle ?
```

Le rescheduling mérite donc une sémantique explicite.

---

# 41. Cancellation

Annuler un schedule peut vouloir dire différentes choses.

```text
ne plus produire de nouvelles occurrences
```

mais qu'en est-il des exécutions déjà :

```text
queued
running
retrying
```

Il faut distinguer :

```text
cancel schedule
cancel occurrence
cancel execution
```

---

# 42. Scheduling et file d'attente

Le scheduling et la queue résolvent deux problèmes différents.

```text
Scheduler
    WHEN?
```

contre :

```text
Queue
    WAIT UNTIL A WORKER CAN PROCESS THIS
```

Exemple :

```text
PyScheduleKit
    │
    │ 08:00
    ▼
Execution Request
    │
    ▼
Queue
    │
    ▼
Worker
```

Le scheduler détermine **quand la tâche devient éligible**.

La queue détermine **comment cette tâche attend une capacité d'exécution**.

---

# 43. Scheduling et workflow

Le scheduling répond :

```text
WHEN?
```

Le workflow répond :

```text
WHAT NEXT?
```

Exemple :

```text
06:00
  │
  ▼
Scheduler
  │
  ▼
Workflow
  │
  ├── ingest
  ├── validate
  ├── transform
  └── publish
```

Les deux domaines sont complémentaires mais distincts.

---

# 44. Scheduling et event-driven

Dans un système événementiel :

```text
Event
  ↓
Action
```

Dans un scheduler :

```text
Time Condition
  ↓
Action
```

Mais les deux modèles peuvent être combinés.

```text
Event received
     │
     ▼
Schedule delayed action
     │
     ▼
30 minutes later
     │
     ▼
Action
```

Le temps lui-même peut donc être considéré comme une source de déclenchement.

---

# 45. Scheduling et orchestration

Le scheduler ne doit pas nécessairement orchestrer le détail d'un traitement.

Il peut simplement demander :

```text
Start Workflow X
```

Ainsi :

```text
PyScheduleKit
      │
      ▼
ExecutionRequest
      │
      ▼
PyWorkflowKit
```

Les responsabilités restent séparées.

---

# 46. Scheduling local versus distribué

Un scheduler local peut fonctionner avec :

```text
1 process
1 clock
1 store
1 executor
```

Un scheduler distribué introduit :

```text
multiple processes
multiple machines
shared state
locks
leases
leader election
duplicate prevention
clock skew
failover
```

La complexité augmente fortement.

---

# 47. Le problème de double déclenchement

Supposons deux schedulers :

```text
Scheduler A
Scheduler B
```

qui voient tous les deux :

```text
Schedule X due at 08:00
```

Sans coordination :

```text
Scheduler A → execute X
Scheduler B → execute X
```

On obtient deux exécutions.

Il faut introduire une forme de :

```text
claim
lock
lease
compare-and-swap
ownership
```

---

# 48. Lease

Une `Lease` peut permettre à une instance de déclarer temporairement :

```text
"I own this scheduling decision."
```

Exemple :

```text
Schedule X
   │
   ▼
Lease acquired by Scheduler A
   │
   ├── Scheduler A → process
   │
   └── Scheduler B → ignore
```

La lease doit généralement expirer afin d'éviter un blocage permanent après crash.

---

# 49. Leader election

Une autre stratégie consiste à désigner une seule instance active.

```text
Scheduler A → LEADER
Scheduler B → STANDBY
Scheduler C → STANDBY
```

Si A échoue :

```text
B becomes LEADER
```

Cette approche simplifie certaines décisions mais introduit d'autres mécanismes de coordination.

---

# 50. Observabilité

Un bon scheduler doit pouvoir expliquer ses décisions.

Questions essentielles :

```text
Pourquoi ce job a-t-il été exécuté ?

Pourquoi n'a-t-il pas été exécuté ?

Quelle occurrence était attendue ?

Quelle occurrence est la prochaine ?

Pourquoi une occurrence a-t-elle été ignorée ?

Pourquoi deux runs ont-ils été fusionnés ?

Combien de retard avait l'exécution ?

Quelle instance du scheduler a pris la décision ?
```

Cela suppose de produire :

```text
logs
events
metrics
history
trace context
```

---

# 51. Événements métier possibles

Exemples d'événements :

```text
ScheduleCreated
ScheduleUpdated
SchedulePaused
ScheduleResumed
ScheduleRemoved

OccurrenceCalculated
OccurrenceDue
OccurrenceMissed
OccurrenceSkipped
OccurrenceCoalesced

ExecutionRequested
ExecutionQueued
ExecutionStarted
ExecutionSucceeded
ExecutionFailed
ExecutionCancelled
```

Ces événements permettent de rendre le système observable.

---

# 52. Métriques possibles

Le scheduling peut exposer des métriques comme :

```text
number_of_active_schedules

due_occurrences_total

misfires_total

execution_delay_seconds

schedule_lag_seconds

executions_started_total

executions_failed_total

coalesced_occurrences_total

scheduler_tick_duration

next_wakeup_delay
```

Ces métriques sont particulièrement importantes dans les systèmes de production.

---

# 53. Le scheduling comme machine à décisions temporelles

Une manière puissante de résumer le domaine consiste à considérer le scheduler comme une machine à décisions.

Entrées :

```text
current time
schedule state
trigger
previous occurrence
policies
execution state
calendar
```

Décision :

```text
DO NOTHING

WAIT

EXECUTE

SKIP

COALESCE

CATCH UP

RESCHEDULE

PAUSE
```

Sorties :

```text
execution requests
state changes
events
next run time
```

---

# 54. Modèle général

```text
                           Clock
                             │
                             ▼
                        Current Time
                             │
                             ▼
┌──────────────┐       ┌──────────────┐
│   Schedule   │──────▶│   Scheduler  │
└──────┬───────┘       │    Engine    │
       │               └──────┬───────┘
       │                      │
       ▼                      ▼
┌──────────────┐       ┌──────────────┐
│   Trigger    │       │   Policies   │
└──────┬───────┘       └──────┬───────┘
       │                      │
       └──────────┬───────────┘
                  │
                  ▼
             Decision
                  │
          ┌───────┼────────┐
          │       │        │
          ▼       ▼        ▼
        WAIT     SKIP    EXECUTE
                           │
                           ▼
                  Execution Request
                           │
                           ▼
                       Executor
                           │
                           ▼
                       Execution
```

---

# 55. Une responsabilité essentielle : séparer calcul et effet

Le moteur peut être plus facile à tester si l'on distingue :

```text
decision
```

de :

```text
side effect
```

Par exemple :

```text
SchedulerDecision(
    action=EXECUTE,
    occurrence=...,
)
```

puis seulement ensuite :

```text
executor.submit(...)
```

Cette approche permettrait potentiellement de tester la logique temporelle sans réellement exécuter les jobs.

---

# 56. Scheduling déterministe

Un objectif important du modèle est de permettre :

```text
same input
    ↓
same scheduling decision
```

Par exemple :

```text
Clock = fixed at 2026-09-28 08:00

Schedule = ...

Execution state = ...

Policies = ...
```

doit produire une décision reproductible.

Cela facilitera :

```text
testing
simulation
debugging
replay
```

---

# 57. Simulation temporelle

Une fois le temps abstrait par un `Clock`, il devient possible de simuler :

```text
advance 5 minutes
advance 1 day
jump across DST
simulate scheduler outage
simulate restart
```

Exemple :

```text
FakeClock
   │
   ├── now = 08:00
   │
   ├── advance(1 hour)
   │
   └── now = 09:00
```

La simulation est particulièrement adaptée à l'apprentissage du domaine.

---

# 58. Pourquoi ce domaine est intéressant à étudier

Le scheduling semble simple tant que l'on ignore :

```text
failure
concurrency
timezones
persistence
distribution
```

Puis il devient un excellent domaine pour comprendre :

```text
Domain-Driven Design
state machines
distributed systems
time semantics
concurrency control
resilience
event modeling
observability
```

Il constitue donc un excellent terrain pédagogique.

---

# 59. Les erreurs conceptuelles fréquentes

Plusieurs confusions devront être évitées.

---

## Erreur 1

```text
Job = Schedule
```

Non.

```text
Job → quoi
Schedule → quoi + quand + politiques
```

---

## Erreur 2

```text
Occurrence = Execution
```

Non.

Une occurrence peut ne jamais être exécutée.

---

## Erreur 3

```text
Scheduler = Executor
```

Non.

```text
Scheduler → décide
Executor → exécute
```

---

## Erreur 4

```text
Retry = Scheduling
```

Non.

Le retry est une politique possible parmi d'autres.

---

## Erreur 5

```text
cron = scheduling
```

Cron constitue une forme historique importante de scheduling, mais le domaine est beaucoup plus large.

---

## Erreur 6

```text
workflow = schedule
```

Non.

```text
schedule → temps
workflow → ordre et dépendances
```

---

# 60. Une première frontière métier

Le domaine PyScheduleKit peut être résumé par :

```text
IN SCOPE
────────────────────────

time
calendar
trigger
schedule
occurrence
next run
misfire
coalescing
concurrency
schedule lifecycle
scheduler decision
execution request
scheduling history
distributed scheduling coordination
```

et :

```text
OUT OF SCOPE
────────────────────────

workflow DAG semantics
data ingestion logic
data transformation logic
business process modeling
message broker implementation
distributed task runtime complet
```

---

# 61. Relation avec PyWorkflowKit

```text
PyScheduleKit
    │
    │ "Start at 06:00"
    ▼
PyWorkflowKit
    │
    │ "First ingest,
    │  then transform,
    │  then publish"
    ▼
Workflow Execution
```

Le premier décide du moment.

Le second décide de l'enchaînement.

---

# 62. Relation avec PyIngestKit

Pour une opération simple :

```text
PyScheduleKit
    │
    │ every 5 min
    ▼
PyIngestKit
    │
    ▼
API → Dataset
```

Aucun workflow n'est nécessaire.

---

# 63. Relation avec PyTransformKit

De même :

```text
PyScheduleKit
    │
    │ every night
    ▼
PyTransformKit
    │
    ▼
Dataset → Dataset
```

Le scheduler ne connaît pas les opérations internes de transformation.

---

# 64. Composition complète

```text
                            TIME
                              │
                              ▼
                      PyScheduleKit
                              │
                              │ trigger
                              ▼
                      PyWorkflowKit
                              │
                   ┌──────────┼───────────┐
                   │          │           │
                   ▼          ▼           ▼
             PyIngestKit PyTransformKit publish()
```

Cette composition sert de référence pour comprendre la frontière des domaines.

---

# 65. Le scheduling vu comme contrat

Un `Schedule` peut être interprété comme un contrat disant :

> Tant que ce schedule est actif, cette règle temporelle doit être évaluée et chaque occurrence doit être traitée selon ces politiques.

Exemple :

```text
Schedule:
    every day at 06:00
    Europe/Paris
    no overlap
    grace period = 5 min
    misfire = RUN_NOW
```

Ce contrat exprime beaucoup plus qu'une simple date.

---

# 66. Questions que le modèle devra pouvoir répondre

Un modèle de scheduling solide doit permettre de répondre explicitement à :

```text
Quelle est la prochaine occurrence ?

Pourquoi est-ce cette occurrence ?

Est-elle due ?

Est-elle trop tardive ?

A-t-elle déjà été exécutée ?

Une exécution est-elle déjà active ?

Peut-on créer une nouvelle exécution ?

Que faire des occurrences précédentes ?

Quelle règle calculera la suivante ?

Que se passe-t-il après redémarrage ?
```

Si ces réponses sont implicites ou dispersées dans du code technique, le modèle métier est probablement insuffisant.

---

# 67. Première représentation du bounded context

```text
┌─────────────────────────────────────────────────────┐
│             SCHEDULING BOUNDED CONTEXT              │
│                                                     │
│   Time                                              │
│    │                                                │
│    ▼                                                │
│  Trigger ────→ Occurrence                           │
│                    │                                │
│                    ▼                                │
│ Job ─────────→ Schedule                             │
│                    │                                │
│                    ▼                                │
│               Scheduler                             │
│                    │                                │
│                    ▼                                │
│            ExecutionRequest                         │
│                    │                                │
└────────────────────┼────────────────────────────────┘
                     │
                     ▼
             External Execution Runtime
```

Cette frontière sera affinée ultérieurement.

---

# 68. Première hypothèse d'agrégat

Sans encore figer le modèle DDD, une hypothèse naturelle est :

```text
Schedule
```

comme agrégat principal.

Il pourrait être propriétaire de :

```text
Trigger
Policies
Timezone
CalendarRef
LifecycleState
```

Mais pas nécessairement :

```text
Execution
```

qui pourrait appartenir à un contexte différent ou à un autre agrégat.

Cette question devra être analysée dans les documents consacrés aux entités et au domain model.

---

# 69. Pourquoi ne pas commencer immédiatement par le code

Si l'on commence directement par :

```python
class Scheduler: ...
```

on risque de reproduire les choix d'une bibliothèque existante sans comprendre pourquoi ils existent.

L'approche PyScheduleKit cherche plutôt à suivre :

```text
Domain
  ↓
Vocabulary
  ↓
Objects
  ↓
Relationships
  ↓
Invariants
  ↓
Policies
  ↓
Architecture
  ↓
Python
```

Le langage Python vient après le modèle conceptuel.

---

# 70. La question centrale du domaine

À ce stade, le scheduling peut être résumé par une question :

> **Comment convertir une règle temporelle en une suite d'occurrences, puis transformer chacune de ces occurrences en une décision d'exécution fiable ?**

Cette question contient déjà les principales dimensions du domaine :

```text
Rule
 ↓
Time
 ↓
Occurrence
 ↓
Decision
 ↓
Execution
```

---

# 71. Modèle mental final

Le modèle mental de base à conserver pour la suite est :

```text
                         TIME
                           │
                           ▼
                       Trigger
                           │
                           ▼
                      Occurrence
                           │
                           ▼
                        Schedule
                           │
                           ▼
                       Scheduler
                           │
                    Scheduling Decision
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
        WAIT              SKIP           EXECUTE
                                             │
                                             ▼
                                      ExecutionRequest
                                             │
                                             ▼
                                          Executor
                                             │
                                             ▼
                                         Execution
```

---

# Conclusion

Le scheduling n'est pas simplement l'action d'attendre puis d'exécuter une fonction.

C'est un domaine composé de règles temporelles, de calendriers, de schedules, de triggers, d'occurrences, de politiques et de décisions d'exécution.

Les principales distinctions à retenir sont :

```text
Job ≠ Schedule

Trigger ≠ Scheduler

Occurrence ≠ Execution

Scheduler ≠ Executor

Scheduling ≠ Workflow

Scheduling ≠ Queue
```

Le scheduler peut être compris comme une **machine à décisions temporelles**.

Il observe le temps, interprète des règles, calcule des occurrences, applique des politiques et transforme certaines occurrences en demandes d'exécution.

Cette compréhension constitue la base nécessaire pour étudier ensuite l'origine, l'évolution et les concepts fondamentaux du scheduling.

---

# Suite documentaire

Le prochain document est :

```text
02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md
```

Il étudiera notamment :

```text
batch processing
time-sharing
cron
Unix scheduling
enterprise schedulers
distributed task schedulers
workflow orchestrators
modern application schedulers
```

afin de comprendre comment le domaine s'est progressivement structuré et pourquoi les abstractions actuelles existent.