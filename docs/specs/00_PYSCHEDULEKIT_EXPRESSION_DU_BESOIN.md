# PyScheduleKit — Expression du besoin

**Document :** `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`  
**Projet :** PyScheduleKit  
**Statut :** Document fondateur  
**Nature :** Expression du besoin  
**Orientation :** apprentissage du domaine métier du scheduling avant implémentation

---

# 1. Contexte

De nombreux systèmes logiciels ont besoin d’exécuter une action :

- à une date précise ;
- à une heure donnée ;
- périodiquement ;
- selon un calendrier ;
- après un certain délai ;
- selon une règle de récurrence ;
- ou lorsqu’une prochaine échéance temporelle devient exigible.

Quelques exemples :

```text
Tous les jours à 06:00
→ récupérer les commandes d'une API.

Toutes les 5 minutes
→ vérifier l'arrivée de nouvelles données.

Chaque lundi à 08:00
→ générer un rapport.

Le 31 décembre à 23:59
→ lancer un traitement annuel.

Toutes les heures
→ recalculer certains indicateurs.

10 minutes après un événement
→ lancer une action différée.
```

Ces besoins relèvent du **scheduling**.

À première vue, le problème peut sembler simple :

```python
if now >= scheduled_time:
    execute()
```

Mais cette représentation devient rapidement insuffisante dès que l'on introduit :

- plusieurs tâches ;
- des récurrences ;
- des calendriers ;
- des fuseaux horaires ;
- des redémarrages ;
- des exécutions manquées ;
- des chevauchements ;
- des erreurs ;
- de la persistance ;
- de la concurrence ;
- plusieurs instances du scheduler ;
- de l'observabilité ;
- ou des systèmes distribués.

Le scheduling constitue donc un véritable **domaine métier technique**, avec ses propres objets, invariants, politiques et cycles de vie.

PyScheduleKit a pour ambition d'explorer et de formaliser ce domaine.

---

# 2. Intention principale du projet

PyScheduleKit n'est pas initialement conçu comme une tentative de remplacer :

- `cron` ;
- APScheduler ;
- Celery Beat ;
- Airflow ;
- Prefect ;
- Dagster ;
- Temporal ;
- ou d'autres moteurs existants.

Le projet doit d'abord servir de support à une compréhension approfondie du domaine du scheduling.

L'objectif principal est donc :

> **Comprendre le scheduling en modélisant explicitement les objets métier, les règles temporelles, les politiques d'exécution et leurs interactions, puis construire progressivement un framework Python cohérent à partir de cette compréhension.**

L'implémentation devient ainsi un moyen d'apprentissage du domaine et non une fin en soi.

---

# 3. Problématique fondamentale

La question fondamentale du scheduling peut être formulée ainsi :

> **Comment déterminer de manière fiable quand une action doit être exécutée, puis transformer cette décision temporelle en une demande d'exécution contrôlée, observable et reproductible ?**

Cette question peut être décomposée en plusieurs sous-questions.

```text
Quoi exécuter ?
        ↓
Quand faut-il l'exécuter ?
        ↓
Comment calculer la prochaine occurrence ?
        ↓
Comment détecter qu'une occurrence est due ?
        ↓
Que faire si elle a été manquée ?
        ↓
Que faire si l'exécution précédente tourne encore ?
        ↓
Que faire si l'exécution échoue ?
        ↓
Comment conserver l'état du scheduler ?
        ↓
Comment reprendre après un redémarrage ?
        ↓
Comment observer ce qui s'est réellement passé ?
```

PyScheduleKit doit permettre d'étudier chacune de ces questions séparément.

---

# 4. Vision conceptuelle

Le modèle mental de départ est :

```text
                         SCHEDULING
                              │
              ┌───────────────┼───────────────┐
              │               │               │
             WHAT            WHEN             HOW
              │               │               │
              ▼               ▼               ▼
             Job           Trigger         Policies
                              │
                         next_run_time
                              │
                              ▼
                           Schedule
                              │
                              ▼
                          Scheduler
                              │
                       detect due work
                              │
                              ▼
                           Executor
                              │
                              ▼
                          Execution
                              │
                   ┌──────────┴──────────┐
                   ▼                     ▼
                SUCCESS                FAILURE
```

Le scheduler n'est donc pas simplement une boucle temporelle.

Il met en relation plusieurs objets métier distincts.

---

# 5. Premier principe : séparer ce qui est planifié de son exécution

Une distinction essentielle doit être introduite dès le début.

## 5.1 Job

Un `Job` représente quelque chose qui peut être exécuté.

Exemple :

```text
Job
────────────────────────
id
name
callable
arguments
metadata
```

Conceptuellement :

```text
generate_daily_report
```

est un job.

---

## 5.2 Execution

Une `Execution` représente une occurrence concrète de ce job.

```text
Job
generate_daily_report
        │
        ├── Execution #001
        │      scheduled_at = Monday 08:00
        │      status = SUCCESS
        │
        ├── Execution #002
        │      scheduled_at = Tuesday 08:00
        │      status = SUCCESS
        │
        └── Execution #003
               scheduled_at = Wednesday 08:00
               status = FAILED
```

Par conséquent :

```text
Job ≠ Execution
```

Un job est une définition.

Une exécution est un événement concret dans le temps.

Cette distinction doit être structurante dans le domaine PyScheduleKit.

---

# 6. Deuxième principe : distinguer Job, Schedule et Trigger

Le projet doit également éviter de confondre trois objets fréquemment mélangés.

## Job

Répond à :

> **Quoi exécuter ?**

---

## Trigger

Répond à :

> **Comment déterminer les prochaines occurrences temporelles ?**

Exemples :

```text
DateTrigger
IntervalTrigger
CronTrigger
CalendarTrigger
```

---

## Schedule

Associe une action planifiable à une règle temporelle et à ses politiques.

Conceptuellement :

```text
Schedule
────────────────────────
job
trigger
timezone
misfire_policy
concurrency_policy
calendar
enabled
```

On obtient donc :

```text
Job
  +
Trigger
  +
Policies
  =
Schedule
```

---

# 7. Le temps comme objet métier

Dans PyScheduleKit, le temps ne doit pas être traité uniquement comme un `datetime`.

Le domaine implique plusieurs notions distinctes :

```text
Instant
Duration
Interval
Timezone
Calendar
LocalTime
Deadline
Recurrence
Occurrence
NextRunTime
ScheduledTime
ActualStartTime
CompletionTime
```

Exemple :

```text
"08:00"
```

ne veut pas nécessairement dire la même chose selon :

```text
Europe/Paris
America/New_York
UTC
Asia/Tokyo
```

De même :

```text
Every day at 02:30
```

peut devenir problématique lors d'un changement d'heure.

Le framework doit donc considérer les problématiques temporelles comme des préoccupations de premier ordre.

---

# 8. Les premiers objets métier à étudier

L'étude du domaine doit au minimum couvrir les objets suivants.

## 8.1 Job

Décrit une opération exécutable.

---

## 8.2 Schedule

Décrit la planification d'une opération.

---

## 8.3 Trigger

Calcule les occurrences futures.

---

## 8.4 DateTrigger

Déclenche une seule occurrence.

```text
2026-10-01 08:00
```

---

## 8.5 IntervalTrigger

Produit des occurrences à intervalle régulier.

```text
every 5 minutes
```

---

## 8.6 CronTrigger

Produit des occurrences à partir d'une expression calendaire.

```text
0 6 * * *
```

---

## 8.7 Calendar

Définit les périodes autorisées ou interdites.

Exemple :

```text
WorkingDaysCalendar
BusinessHoursCalendar
HolidayCalendar
ExcludedDatesCalendar
```

---

## 8.8 Scheduler

Détermine les schedules qui sont arrivés à échéance.

---

## 8.9 Executor

Prend en charge l'exécution technique d'une action.

Exemples :

```text
InlineExecutor
ThreadExecutor
ProcessExecutor
AsyncExecutor
RemoteExecutor
```

---

## 8.10 Execution

Représente une occurrence concrète.

---

## 8.11 ExecutionResult

Représente le résultat d'une exécution.

---

## 8.12 JobStore / ScheduleStore

Persiste les définitions et états nécessaires au scheduler.

---

## 8.13 MisfirePolicy

Détermine le comportement lorsqu'une occurrence prévue a été manquée.

---

## 8.14 ConcurrencyPolicy

Détermine le comportement lorsqu'une nouvelle occurrence apparaît alors qu'une précédente est encore active.

---

## 8.15 RetryPolicy

Détermine certaines règles de répétition après échec.

Cette notion devra cependant être strictement délimitée afin de ne pas empiéter sur les retries propres aux opérations exécutées.

---

# 9. Le problème des misfires

Un scheduler peut être indisponible au moment où une exécution devait commencer.

Exemple :

```text
07:55                  08:00                  08:15
  │                      │                      │
  │                      │                      │
scheduler OFF       run attendu         scheduler restart
```

À son redémarrage, plusieurs politiques sont possibles.

```text
SKIP
    ↓
L'occurrence est ignorée.

RUN_NOW
    ↓
L'occurrence est exécutée immédiatement.

RESCHEDULE
    ↓
L'occurrence est abandonnée et la prochaine est calculée.

CATCH_UP
    ↓
Les occurrences manquées sont rejouées.

COALESCE
    ↓
Plusieurs occurrences sont fusionnées.
```

Le comportement adopté ne doit pas être un détail technique caché.

Il constitue une véritable **politique métier du scheduler**.

---

# 10. Le problème de concurrence

Considérons :

```text
Schedule
every 5 minutes

Duration
8 minutes
```

On obtient potentiellement :

```text
10:00 ───────── Run #1 ─────────────── 10:08

10:05 ───────── Run #2 ─────────────── 10:13

10:10 ───────── Run #3 ─────────────── 10:18
```

Plusieurs politiques sont possibles :

```text
ALLOW
FORBID
QUEUE
REPLACE
COALESCE
```

PyScheduleKit doit permettre de formaliser ces choix explicitement.

---

# 11. Cycle de vie d'une exécution

Un modèle initial pourrait être :

```text
             ┌─────────────┐
             │  SCHEDULED  │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │    DUE      │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │   QUEUED    │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │   RUNNING   │
             └──────┬──────┘
                    │
            ┌───────┼────────┐
            │       │        │
            ▼       ▼        ▼
         SUCCESS  FAILED  CANCELLED
```

D'autres états pourront être nécessaires :

```text
MISSED
SKIPPED
RETRYING
TIMED_OUT
REJECTED
```

Ce modèle devra être étudié avant d'être figé.

---

# 12. Relation entre définition et occurrence

Le modèle doit distinguer :

```text
Schedule
    │
    ├── occurrence 1
    │
    ├── occurrence 2
    │
    ├── occurrence 3
    │
    └── occurrence N
```

Puis :

```text
Occurrence
    │
    ▼
ExecutionRequest
    │
    ▼
Execution
```

Il faudra déterminer si ces trois concepts doivent être :

- trois objets distincts ;
- deux objets ;
- ou différentes étapes d'un même cycle de vie.

Cette question fera partie de l'analyse du domaine.

---

# 13. PyScheduleKit et l'écosystème Py*Kit

PyScheduleKit doit être conçu pour cohabiter avec les autres frameworks spécialisés.

La séparation de responsabilités cible est :

```text
PyScheduleKit
    WHEN?

PyWorkflowKit
    WHAT NEXT?

PyIngestKit
    HOW TO ACQUIRE DATA?

PyTransformKit
    HOW TO TRANSFORM DATA?
```

---

# 14. PyScheduleKit et PyWorkflowKit

La relation principale est :

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
  ├── step
  ├── step
  ├── step
  └── step
```

PyScheduleKit détermine :

```text
quand
```

PyWorkflowKit détermine :

```text
quoi ensuite
```

Exemple :

```text
Every day @ 06:00
        │
        ▼
PyScheduleKit
        │
        ▼
daily_orders_pipeline
        │
        ▼
PyWorkflowKit
        │
        ├── ingest
        ├── validate
        ├── transform
        └── publish
```

---

# 15. PyScheduleKit ne doit pas devenir un moteur de workflow

PyScheduleKit ne doit pas être propriétaire de :

```text
DAG
task dependency
branching
workflow state machine
workflow compensation
step dependency
workflow graph
```

Ces concepts appartiennent à PyWorkflowKit.

PyScheduleKit peut déclencher un workflow.

Il ne doit pas l'orchestrer.

---

# 16. PyScheduleKit peut déclencher directement une opération

PyWorkflowKit ne doit pas être obligatoire.

Pour une opération simple :

```text
Every 5 minutes
       │
       ▼
PyScheduleKit
       │
       ▼
PyIngestKit
```

Cela doit rester possible.

Même chose pour :

```text
Every night @ 02:00
       │
       ▼
PyScheduleKit
       │
       ▼
PyTransformKit
```

L'introduction d'un workflow ne se justifie que lorsqu'il existe une véritable orchestration.

---

# 17. Exemple de composition complète

```text
                            TIME
                              │
                     Every day @ 06:00
                              │
                              ▼
                 ┌────────────────────────┐
                 │     PyScheduleKit      │
                 │                        │
                 │ CronTrigger            │
                 │ 0 6 * * *              │
                 └───────────┬────────────┘
                             │
                             │ creates
                             │ execution request
                             ▼
                 ┌────────────────────────┐
                 │     PyWorkflowKit      │
                 │                        │
                 │ daily_orders_pipeline  │
                 └───────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼

           STEP 1          STEP 2          STEP 3

        PyIngestKit   PyTransformKit      publish()
             │              │
             ▼              ▼
        API Orders      Raw Dataset
             │              │
             ▼              ▼
        Raw Dataset     Clean Dataset
```

Cette composition constitue un cas d'usage de référence du projet.

---

# 18. Retry : attention aux frontières

Le terme `retry` peut exister à plusieurs niveaux.

Il ne faut pas les confondre.

```text
PyScheduleKit retry
───────────────────
Impossible de soumettre une exécution.

PyWorkflowKit retry
───────────────────
Une étape du workflow a échoué.

PyIngestKit retry
─────────────────
Une requête API a retourné HTTP 503.

PyTransformKit retry
────────────────────
Une opération technique de transformation a échoué.
```

Ainsi :

```text
Scheduling Retry
≠
Workflow Retry
≠
Operation Retry
```

Les responsabilités devront être précisément documentées.

---

# 19. Contexte d'exécution partagé

Les différents frameworks devront pouvoir coopérer sans devenir dépendants les uns des autres.

Une notion légère de contexte partagé pourra être étudiée.

Exemple :

```text
ExecutionContext
────────────────────────
execution_id
correlation_id
trace_id
scheduled_at
triggered_at
metadata
```

Puis :

```text
PyScheduleKit
ScheduleExecution
       │
       │ correlation_id = ABC
       ▼

PyWorkflowKit
WorkflowRun
       │
       │ correlation_id = ABC
       ▼

PyIngestKit
IngestionRun
       │
       │ correlation_id = ABC
       ▼

PyTransformKit
TransformationRun
```

Cette propagation facilitera :

```text
logging
metrics
tracing
audit
lineage
debugging
observability
```

sans imposer un modèle métier unique à tous les frameworks.

---

# 20. Pas de super-classe universelle `Job`

PyScheduleKit ne doit pas imposer à l'ensemble de l'écosystème une abstraction universelle appelée `Job`.

Le terme est historiquement ambigu.

Selon les systèmes :

```text
cron
Job = commande planifiée

APScheduler
Job = élément planifié

Celery
Task = fonction distribuée

Airflow
Task = nœud de DAG

Spark
Job = exécution distribuée

CI/CD
Job = unité d'un pipeline
```

L'écosystème Py*Kit doit donc préférer des concepts métier explicites.

```text
Schedule
Workflow
Step
IngestionRun
TransformationRun
Execution
Operation
Artifact
Dataset
```

Les relations doivent être établies par contrats plutôt que par héritage artificiel.

---

# 21. Architecture conceptuelle cible

```text
                         ┌──────────────────────┐
                         │    PyScheduleKit     │
                         │                      │
                         │       WHEN ?         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    PyWorkflowKit     │
                         │                      │
                         │    WHAT NEXT ?       │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                         ▼                     ▼
                ┌────────────────┐    ┌────────────────┐
                │  PyIngestKit   │    │ PyTransformKit │
                │                │    │                │
                │ HOW TO ACQUIRE │    │ HOW TO CHANGE  │
                │     DATA?      │    │     DATA?      │
                └────────────────┘    └────────────────┘
```

Cette organisation n'impose cependant pas PyWorkflowKit entre PyScheduleKit et une opération.

Le chemin suivant reste valide :

```text
PyScheduleKit
      │
      ▼
PyIngestKit
```

comme :

```text
PyScheduleKit
      │
      ▼
PyTransformKit
```

---

# 22. Besoin fonctionnel principal

PyScheduleKit devra permettre à terme de :

1. définir une action planifiable ;
2. définir une règle temporelle ;
3. calculer la prochaine occurrence ;
4. associer cette règle à une action ;
5. détecter les occurrences arrivées à échéance ;
6. produire une demande d'exécution ;
7. soumettre cette exécution à un executor ;
8. suivre son état ;
9. appliquer des politiques de concurrence ;
10. gérer les exécutions manquées ;
11. gérer les calendriers et fuseaux horaires ;
12. suspendre et reprendre un schedule ;
13. persister les schedules ;
14. reconstruire l'état après redémarrage ;
15. enregistrer l'historique d'exécution ;
16. publier des événements d'observabilité ;
17. permettre l'intégration avec d'autres frameworks sans couplage fort.

---

# 23. Besoins pédagogiques

Le projet poursuit également explicitement des objectifs d'apprentissage.

Chaque objet majeur devra être étudié selon une grille commune.

```text
1. Qu'est-ce que cet objet ?

2. Pourquoi existe-t-il ?

3. Quel problème résout-il ?

4. Quelle est son identité ?

5. Quel est son cycle de vie ?

6. Est-il une Entity ou un Value Object ?

7. Quelles données porte-t-il ?

8. Quels invariants protège-t-il ?

9. Avec quels objets interagit-il ?

10. Quelles erreurs conceptuelles sont fréquentes ?

11. Comment les frameworks existants le représentent-ils ?

12. Comment pourrait-on le modéliser en Python ?
```

Cette méthode doit permettre de comprendre le domaine avant de choisir une architecture logicielle.

---

# 24. Besoins non fonctionnels

PyScheduleKit devra progressivement rechercher :

## 24.1 Déterminisme

À contexte temporel identique, le calcul des prochaines occurrences doit être reproductible.

---

## 24.2 Testabilité

Les composants temporels devront être testables sans dépendre directement de l'horloge système.

Cela suggère l'introduction future d'une abstraction :

```text
Clock
```

---

## 24.3 Extensibilité

Il devra être possible d'ajouter :

```text
Trigger
Executor
Store
Calendar
Policy
```

sans modifier le cœur du domaine.

---

## 24.4 Observabilité

Chaque décision importante doit pouvoir être expliquée.

Exemple :

```text
Why did this execution happen?

Why was it skipped?

Why was it delayed?

Why was it coalesced?

Why did the scheduler choose this next run time?
```

---

## 24.5 Persistance

Le redémarrage du scheduler ne doit pas nécessairement entraîner la perte des schedules ou de leur état.

---

## 24.6 Portabilité

Le cœur du framework ne doit pas dépendre d'une plateforme spécifique.

---

## 24.7 Faible couplage

PyScheduleKit ne doit pas obliger l'utilisateur à installer :

```text
PyWorkflowKit
PyIngestKit
PyTransformKit
```

pour utiliser le scheduler.

Les intégrations doivent rester optionnelles.

---

# 25. Principe d'architecture

Une séparation devra être maintenue entre :

```text
Domain
Application
Infrastructure
Integration
```

Conceptuellement :

```text
┌─────────────────────────────┐
│          Domain             │
│                             │
│ Schedule                    │
│ Trigger                     │
│ Occurrence                  │
│ Policies                    │
│ Execution concepts          │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│        Application          │
│                             │
│ SchedulerEngine             │
│ execution submission        │
│ lifecycle coordination      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       Infrastructure        │
│                             │
│ Clock                       │
│ Store                       │
│ Executor                    │
│ Persistence                 │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│        Integrations         │
│                             │
│ PyWorkflowKit               │
│ PyIngestKit                 │
│ PyTransformKit              │
└─────────────────────────────┘
```

---

# 26. Ce que PyScheduleKit ne doit pas devenir

PyScheduleKit ne doit pas progressivement absorber tous les problèmes d'exécution.

Il ne doit pas devenir :

```text
un moteur de workflow généraliste ;
un système ETL ;
un framework de transformation ;
un framework d'ingestion ;
un message broker ;
un moteur de tâches distribuées complet ;
une plateforme de data engineering ;
un remplacement automatique d'Airflow ;
un framework universel de jobs.
```

Le domaine doit rester clairement centré sur :

> **la décision temporelle et la production contrôlée d'occurrences d'exécution.**

---

# 27. Question centrale de frontière

Une règle simple doit permettre de déterminer si une fonctionnalité appartient à PyScheduleKit.

Si la question principale est :

> **Quand cette action doit-elle devenir exécutable ?**

elle appartient probablement à PyScheduleKit.

Si elle est :

> **Quelles étapes doivent être exécutées ensuite ?**

elle appartient probablement à PyWorkflowKit.

Si elle est :

> **Comment acquérir ces données ?**

elle appartient probablement à PyIngestKit.

Si elle est :

> **Comment transformer ces données ?**

elle appartient probablement à PyTransformKit.

---

# 28. Première taxonomie du domaine

```text
Scheduling
│
├── Time
│   ├── Instant
│   ├── Duration
│   ├── Timezone
│   ├── Calendar
│   └── Clock
│
├── Planning
│   ├── Job
│   ├── Schedule
│   ├── Trigger
│   └── Occurrence
│
├── Triggering
│   ├── DateTrigger
│   ├── IntervalTrigger
│   ├── CronTrigger
│   └── CalendarTrigger
│
├── Execution
│   ├── ExecutionRequest
│   ├── Execution
│   ├── ExecutionResult
│   └── Executor
│
├── Policies
│   ├── MisfirePolicy
│   ├── ConcurrencyPolicy
│   ├── RetryPolicy
│   ├── TimeoutPolicy
│   └── JitterPolicy
│
├── Lifecycle
│   ├── Pause
│   ├── Resume
│   ├── Cancel
│   └── Reschedule
│
├── Persistence
│   ├── ScheduleStore
│   ├── ExecutionStore
│   └── History
│
└── Distributed Scheduling
    ├── Lock
    ├── Lease
    ├── Ownership
    └── Leader Election
```

Cette taxonomie est volontairement préliminaire.

Elle devra évoluer avec l'analyse du domaine.

---

# 29. Questions ouvertes

Plusieurs questions doivent rester ouvertes à ce stade.

### Modèle métier

- `Job` doit-il être une Entity ?
- `Schedule` doit-il être l'Aggregate Root principal ?
- `Trigger` est-il un Value Object ?
- `Occurrence` mérite-t-elle une identité ?
- `ExecutionRequest` et `Execution` doivent-ils être distincts ?

### Temps

- comment représenter les timezones ?
- comment traiter DST ?
- comment modéliser les calendriers d'exclusion ?
- faut-il un objet `Clock` dès le cœur du domaine ?

### Exécution

- qui crée l'`Execution` ?
- le scheduler ou l'executor ?
- quand une occurrence devient-elle officiellement une execution ?

### Persistance

- que faut-il réellement persister ?
- comment recalculer `next_run_time` ?
- quelle information constitue la source de vérité ?

### Concurrence

- les politiques appartiennent-elles au `Schedule` ou au `Job` ?
- la concurrence se contrôle-t-elle par job, schedule ou target ?

### Distribution

- plusieurs schedulers peuvent-ils partager le même store ?
- comment éviter les doubles exécutions ?
- faut-il des leases ?
- faut-il un leader ?

Ces questions seront étudiées dans les documents suivants.

---

# 30. Stratégie d'apprentissage

L'implémentation ne doit pas précéder la compréhension.

La démarche retenue est :

```text
Vocabulaire
    ↓
Objets métier
    ↓
Entités / Value Objects
    ↓
Relations
    ↓
Invariants
    ↓
Cycles de vie
    ↓
Politiques
    ↓
Domain Model
    ↓
Architecture
    ↓
Dataclasses / Protocols
    ↓
Prototype
    ↓
Framework
```

Cette démarche doit éviter de construire trop tôt des abstractions dictées uniquement par Python ou par l'API de frameworks existants.

---

# 31. Ordre documentaire envisagé

```text
00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md

01_SCHEDULING_DOMAIN_INTRODUCTION.md
02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md
03_SCHEDULING_DOMAIN_VOCABULARY.md

04_SCHEDULING_BUSINESS_OBJECTS.md
05_SCHEDULING_ENTITIES_AND_VALUE_OBJECTS.md
06_SCHEDULING_DOMAIN_MODEL.md
07_SCHEDULING_ERD.md

08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md

09_JOB_AND_SCHEDULE_MODEL.md
10_TRIGGER_MODEL.md
11_DATE_INTERVAL_AND_CRON_TRIGGERS.md

12_EXECUTION_AND_JOB_RUN_MODEL.md

13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md
14_CONCURRENCY_AND_OVERLAP_MODEL.md
15_RETRY_BACKOFF_AND_FAILURE_MODEL.md

16_JOB_STORE_AND_PERSISTENCE_MODEL.md
17_EXECUTOR_AND_EXECUTION_RUNTIME_MODEL.md
18_SCHEDULER_ENGINE_AND_TICK_MODEL.md

19_PAUSE_RESUME_CANCEL_AND_LIFECYCLE_MODEL.md
20_EVENTS_OBSERVABILITY_AND_EXECUTION_HISTORY.md

21_DISTRIBUTED_SCHEDULING_AND_LOCKING_MODEL.md

22_SCHEDULING_VS_WORKFLOW_VS_QUEUE_MODEL.md
23_PYSCHEDULEKIT_DOMAIN_BOUNDARIES.md

24_PYSCHEDULEKIT_PYTHON_DATACLASSES.md

25_PYSCHEDULEKIT_ARCHITECTURE.md

26_PYSCHEDULEKIT_IMPLEMENTATION_PLAN.md
27_PYSCHEDULEKIT_REPOSITORY_BOOTSTRAP_AND_PROJECT_STRUCTURE.md
28_PYSCHEDULEKIT_INITIAL_DOMAIN_IMPLEMENTATION_SPEC.md
```

---

# 32. Critères de réussite

PyScheduleKit pourra être considéré comme conceptuellement réussi lorsque l'on pourra expliquer clairement :

```text
ce qu'est un Job ;

ce qu'est un Schedule ;

ce qu'est un Trigger ;

ce qu'est une Occurrence ;

ce qu'est une Execution ;

comment une occurrence devient due ;

comment next_run_time est calculé ;

ce qui se passe lorsqu'une occurrence est manquée ;

ce qui se passe lorsque deux exécutions se chevauchent ;

comment les timezones influencent la planification ;

comment un scheduler reprend après redémarrage ;

où se situe la frontière avec un workflow engine ;

où se situe la frontière avec un task queue ;

comment PyScheduleKit interagit avec les autres Py*Kit.
```

La réussite ne sera donc pas seulement mesurée au nombre de fonctionnalités implémentées.

Elle sera mesurée par la **qualité du modèle mental et du modèle métier produits**.

---

# 33. Vision cible

À terme, PyScheduleKit pourrait permettre d'exprimer :

```python
schedule = Schedule(
    id="daily-orders",
    target="daily_orders_pipeline",
    trigger=CronTrigger("0 6 * * *"),
    timezone="Europe/Paris",
    misfire_policy=RunNow(),
    concurrency_policy=ForbidOverlap(),
)

scheduler.add(schedule)
```

Mais cette API ne doit pas être considérée comme acquise.

Elle devra émerger du modèle métier.

L'objectif n'est donc pas de commencer par écrire cette API puis d'inventer les concepts nécessaires pour la justifier.

L'objectif est l'inverse :

```text
UNDERSTAND
    ↓
MODEL
    ↓
VALIDATE
    ↓
IMPLEMENT
```

---

# Conclusion

PyScheduleKit est avant tout un projet d'exploration du domaine du scheduling.

Son objectif est de comprendre comment le temps, les règles de récurrence, les schedules, les triggers, les occurrences, les politiques et les exécutions s'articulent pour produire un système de planification fiable.

La question fondatrice du projet reste :

> **Comment transformer une règle temporelle en une décision d'exécution explicite, déterministe, contrôlable, persistable et observable ?**

PyScheduleKit devra répondre à cette question sans absorber les responsabilités des autres frameworks de l'écosystème.

La séparation cible reste :

```text
PyScheduleKit
    ↓
WHEN?

PyWorkflowKit
    ↓
WHAT NEXT?

PyIngestKit
    ↓
HOW TO ACQUIRE DATA?

PyTransformKit
    ↓
HOW TO TRANSFORM DATA?
```

Cette frontière constituera l'un des invariants architecturaux majeurs du projet.