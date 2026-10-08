# Scheduling — Histoire et concepts fondamentaux

**Document :** `02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md`  
**Projet :** PyScheduleKit  
**Statut :** Document pédagogique  
**Nature :** Histoire du domaine et concepts fondamentaux  
**Prérequis :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
- `01_SCHEDULING_DOMAIN_INTRODUCTION.md`

---

# 1. Introduction

Le scheduling informatique n'est pas apparu comme une abstraction unique et parfaitement définie.

Il est le résultat de plusieurs évolutions historiques liées à des problèmes différents :

```text
Comment partager une machine entre plusieurs programmes ?

Comment lancer automatiquement des traitements la nuit ?

Comment exécuter une commande chaque jour ?

Comment différer une tâche ?

Comment distribuer du travail entre plusieurs machines ?

Comment enchaîner plusieurs traitements dépendants ?

Comment garantir qu'une exécution prévue ne soit pas perdue ?

Comment reprendre après une panne ?
```

Ces problèmes ont progressivement fait émerger plusieurs familles de systèmes :

```text
Batch Processing
        ↓
Operating-System Scheduling
        ↓
Time-based Job Scheduling
        ↓
Task Queues
        ↓
Workflow Scheduling
        ↓
Distributed Scheduling
        ↓
Modern Orchestration Platforms
```

Ces familles partagent parfois du vocabulaire, mais elles ne répondent pas exactement aux mêmes questions.

L'objectif de ce document est donc double :

1. comprendre l'évolution historique du scheduling ;
2. dégager les concepts fondamentaux qui structurent encore les systèmes modernes.

---

# 2. Avant le scheduling applicatif : le batch processing

Aux débuts de l'informatique, les machines exécutaient souvent des traitements par lots.

Un utilisateur préparait un ensemble d'instructions et de données.

Le système exécutait ensuite ces travaux successivement.

Conceptuellement :

```text
Input
  │
  ▼
Job #1
  │
  ▼
Job #2
  │
  ▼
Job #3
  │
  ▼
Output
```

Cette approche est appelée :

```text
Batch Processing
```

Le traitement n'était pas nécessairement interactif.

On soumettait du travail.

Le système l'exécutait lorsque les ressources devenaient disponibles.

---

# 3. Le concept historique de « job »

Le mot `job` précède largement les frameworks modernes.

Historiquement, il désigne approximativement :

> une unité de travail soumise à un système informatique pour exécution.

Un job peut contenir :

```text
programme
données
paramètres
instructions d'exécution
besoins en ressources
```

Cette notion restera extrêmement importante.

Aujourd'hui encore, on retrouve `Job` dans :

```text
cron jobs
batch jobs
Spark jobs
Kubernetes Jobs
CI/CD jobs
scheduler jobs
```

Mais le sens précis varie selon le système.

C'est pourquoi PyScheduleKit devra définir explicitement ce qu'il entend par `Job`.

---

# 4. Job scheduling et resource scheduling

Une distinction historique fondamentale doit immédiatement être faite.

Le terme **scheduler** désigne au moins deux grands domaines.

---

## 4.1 Resource Scheduling

Le système décide :

> quel processus peut utiliser une ressource maintenant ?

Exemple :

```text
CPU

Process A
Process B
Process C
    │
    ▼
CPU Scheduler
    │
    ▼
Who runs next?
```

Ce type de scheduling concerne :

```text
CPU scheduling
thread scheduling
process scheduling
resource allocation
```

---

## 4.2 Job Scheduling

Le système décide :

> quand un travail doit être lancé ?

Exemple :

```text
Job A
Every day @ 06:00
        │
        ▼
Job Scheduler
        │
        ▼
Execution
```

PyScheduleKit appartient principalement à cette seconde famille.

---

# 5. Une distinction essentielle

On peut donc déjà séparer :

```text
RESOURCE SCHEDULING
───────────────────
Who gets the CPU?

versus

TEMPORAL / JOB SCHEDULING
─────────────────────────
When should this work start?
```

Ce document se concentre essentiellement sur le second.

---

# 6. Multiprogrammation et time-sharing

Lorsque plusieurs programmes ont commencé à partager une même machine, les systèmes d'exploitation ont dû arbitrer l'accès au CPU.

Cela a donné naissance à des concepts comme :

```text
priority
quantum
preemption
waiting
ready state
running state
```

Exemple :

```text
          ┌─────────┐
          │  READY  │
          └────┬────┘
               │
               ▼
          ┌─────────┐
          │ RUNNING │
          └────┬────┘
               │
        ┌──────┼──────┐
        │             │
        ▼             ▼
     WAITING       FINISHED
```

Ces concepts appartiennent au scheduler du système d'exploitation.

Ils influencent néanmoins certains modèles modernes de scheduling applicatif.

---

# 7. Pourquoi l'histoire du CPU scheduling est intéressante ici

Même si PyScheduleKit ne doit pas gérer le CPU, plusieurs idées sont analogues :

```text
ready queue
priority
fairness
starvation
preemption
resource contention
```

Par exemple :

```text
Scheduled execution
        ↓
Queued execution
        ↓
Running execution
```

ressemble partiellement à :

```text
Ready
 ↓
Running
```

Mais il ne faut pas confondre analogie et identité conceptuelle.

PyScheduleKit ne doit pas devenir un CPU scheduler.

---

# 8. Le besoin d'automatisation temporelle

Avec la généralisation des systèmes multi-utilisateurs et des serveurs, un autre besoin apparaît :

> exécuter automatiquement certaines commandes à des moments déterminés.

Exemples :

```text
nettoyage nocturne
sauvegarde
rotation de logs
génération de rapports
maintenance
synchronisation
```

Cela conduit progressivement à des mécanismes dédiés à la planification temporelle.

---

# 9. Unix et la philosophie des petits outils

Les systèmes Unix ont historiquement favorisé des outils :

```text
simples
composables
centrés sur une responsabilité
```

Le scheduling temporel y apparaît notamment à travers plusieurs mécanismes.

Parmi les plus connus :

```text
at
cron
```

Ces deux outils représentent deux besoins fondamentalement différents.

---

# 10. `at` — planification ponctuelle

Le mécanisme `at` représente une idée simple :

> exécuter une commande une seule fois dans le futur.

Conceptuellement :

```text
NOW
 │
 │
 ├─────────────── Future Time
 │                     │
 │                     ▼
 │                  Command
```

Exemple conceptuel :

```text
execute backup at 23:00
```

Cela correspond approximativement à ce que nous appellerions aujourd'hui :

```text
DateTrigger
```

---

# 11. Une première abstraction fondamentale

Le besoin exprimé par `at` est :

```text
ONE-SHOT SCHEDULING
```

Il comporte :

```text
target
+
future instant
```

Conceptuellement :

```text
ScheduledAction(
    target,
    execute_at
)
```

Ce modèle reste aujourd'hui extrêmement important.

---

# 12. Cron — scheduling récurrent

`cron` représente une évolution majeure.

Le besoin devient :

> exécuter automatiquement une commande selon une règle calendaire récurrente.

Exemple :

```text
0 6 * * *
```

peut représenter :

```text
Every day @ 06:00
```

Conceptuellement :

```text
Cron Expression
      │
      ▼
Calendar Rule
      │
      ▼
Occurrences
```

---

# 13. Pourquoi cron est fondamental

Cron introduit une idée extrêmement puissante :

> représenter une infinité potentielle d'occurrences à partir d'une règle compacte.

Au lieu de stocker :

```text
2026-09-28 06:00
2026-09-29 06:00
2026-09-30 06:00
2026-10-01 06:00
...
```

on stocke :

```text
0 6 * * *
```

La règle permet ensuite de calculer les occurrences.

C'est exactement le principe du :

```text
Trigger
```

---

# 14. Cron comme générateur d'occurrences

Une expression cron peut être comprise comme une fonction :

```text
CronRule
  +
ReferenceTime
  ↓
NextOccurrence
```

Puis :

```text
NextOccurrence
  +
CronRule
  ↓
FollowingOccurrence
```

Ainsi :

```text
Trigger.next(after)
```

est une abstraction générale de ce principe.

---

# 15. Cron n'est pas tout le scheduling

Cron répond très bien à certaines questions.

Mais il ne modélise pas directement :

```text
retry
misfire
execution history
distributed locking
workflow dependencies
task queues
rich calendars
execution result
concurrency policy
catch-up semantics
```

Cron constitue donc une **forme historique majeure du scheduling temporel**, mais pas le domaine complet.

---

# 16. La notion de daemon

Pour qu'un scheduler temporel fonctionne continuellement, il faut généralement un processus actif.

Conceptuellement :

```text
Scheduler Daemon
      │
      ├── observe clock
      ├── inspect schedules
      ├── find due entries
      └── start commands
```

Cela introduit la notion de :

```text
long-running scheduling process
```

Cette idée reste présente dans les schedulers modernes.

---

# 17. Scheduling par polling

Une approche naturelle consiste à vérifier périodiquement :

```text
Is something due?
```

Exemple :

```text
tick
 ↓
check schedules
 ↓
wait
 ↓
tick
 ↓
check schedules
```

Cette approche est appelée :

```text
polling
```

---

# 18. La notion de tick

On peut définir un `tick` comme :

> une itération du moteur durant laquelle il observe l'état temporel et détermine les actions à effectuer.

Conceptuellement :

```text
TICK
 │
 ├── now()
 ├── find_due()
 ├── apply_policies()
 ├── create_requests()
 └── compute_next()
```

Le `tick` sera probablement un concept important pour PyScheduleKit.

---

# 19. Scheduling par prochaine échéance

Une approche plus efficace peut consister à calculer :

```text
earliest_next_run
```

puis attendre jusqu'à cet instant.

Exemple :

```text
Schedule A → 10:15
Schedule B → 10:07
Schedule C → 10:40
```

Le scheduler détermine :

```text
next wake-up = 10:07
```

Puis :

```text
sleep until 10:07
```

---

# 20. Timer wheels et structures temporelles

Lorsque des systèmes doivent gérer énormément de timers, des structures spécialisées peuvent être utilisées.

Exemples conceptuels :

```text
priority queue
min-heap
timer wheel
calendar queue
```

L'idée commune est d'éviter de parcourir systématiquement toutes les tâches.

---

# 21. Priority queue temporelle

Une représentation simple consiste à utiliser :

```text
(next_run_time, schedule)
```

ordonné par date.

Exemple :

```text
Heap
────────────────────────
10:00 → Schedule A
10:03 → Schedule D
10:07 → Schedule B
11:00 → Schedule C
```

Le premier élément représente l'échéance la plus proche.

---

# 22. L'émergence des schedulers d'entreprise

Avec le développement des systèmes d'information, les entreprises ont eu besoin de planifier des traitements plus complexes.

Exemples :

```text
batch bancaire
clôture comptable
traitement de paie
ETL nocturnes
transferts de fichiers
reporting
mainframe jobs
```

Le besoin ne se limite plus à :

```text
run command at 06:00
```

Il devient :

```text
run A

when A succeeds
run B

when B and C succeed
run D

only on business days
```

Le scheduling commence alors à se rapprocher de l'orchestration.

---

# 23. Job dependency

On introduit des dépendances comme :

```text
Job A
  │
  ▼
Job B
  │
  ▼
Job C
```

ou :

```text
      A
     / \
    B   C
     \ /
      D
```

Ce modèle conduit naturellement à la notion de :

```text
DAG
```

---

# 24. Une divergence historique importante

À partir de là, deux questions apparaissent :

```text
WHEN should a process start?

et

WHAT should run after what?
```

Ces questions sont liées, mais différentes.

Elles donneront progressivement naissance à deux domaines :

```text
Scheduling
    WHEN?

Workflow Orchestration
    WHAT NEXT?
```

---

# 25. Scheduling versus orchestration

Exemple :

```text
Every day @ 06:00
        │
        ▼
    Scheduler
        │
        ▼
   Start Workflow
        │
        ▼
A → B → C → D
```

Le scheduler décide du démarrage.

Le workflow engine décide de l'enchaînement.

---

# 26. L'émergence des files de tâches

Un autre besoin apparaît avec les applications distribuées :

> exécuter une tâche ailleurs, parfois plus tard, lorsque des workers sont disponibles.

Cela conduit à la notion de :

```text
Task Queue
```

Architecture typique :

```text
Producer
   │
   ▼
Queue
   │
   ▼
Worker
   │
   ▼
Execution
```

---

# 27. La queue répond à une autre question

Le scheduler répond :

```text
WHEN does this work become due?
```

La queue répond :

```text
WHERE / WHEN CAPACITY IS AVAILABLE
should the work be processed?
```

La différence est subtile mais fondamentale.

---

# 28. Scheduler et queue ensemble

Les deux peuvent parfaitement être combinés.

```text
Time
 │
 ▼
Scheduler
 │
 ▼
Task
 │
 ▼
Queue
 │
 ▼
Worker
```

Par exemple :

```text
08:00
  ↓
schedule due
  ↓
enqueue task
  ↓
worker processes task
```

---

# 29. Delayed queue versus scheduler

Certaines queues permettent également :

```text
execute this message after 10 minutes
```

Cela peut sembler équivalent au scheduling.

Mais les modèles ne sont pas nécessairement identiques.

Une delayed queue est souvent centrée sur :

```text
delivery delay
```

alors qu'un scheduler riche peut gérer :

```text
recurrence
calendar
timezone
misfire
catch-up
pause/resume
next occurrence
```

---

# 30. L'apparition des task schedulers applicatifs

Dans les applications modernes, il devient courant d'intégrer directement un scheduler dans le processus applicatif.

Architecture :

```text
Application
   │
   ├── API
   ├── Business Logic
   └── Scheduler
```

Le scheduler peut alors lancer :

```text
Python functions
methods
coroutines
jobs
```

---

# 31. L'intérêt des schedulers applicatifs

Ils permettent :

```text
configuration en code
intégration avec le domaine applicatif
persistance personnalisée
exécuteurs multiples
événements
logging
runtime control
```

Le scheduling devient alors une abstraction logicielle explicite.

---

# 32. Trigger comme abstraction générale

Une évolution importante consiste à séparer :

```text
Schedule
```

de :

```text
Trigger
```

Le trigger devient la stratégie responsable de :

```text
calculer les occurrences
```

Exemples :

```text
DateTrigger
IntervalTrigger
CronTrigger
CalendarTrigger
```

---

# 33. Pourquoi cette séparation est importante

Sans cette abstraction, le scheduler pourrait devenir :

```python
if type == "cron":
    ...
elif type == "interval":
    ...
elif type == "date":
    ...
```

Avec un trigger :

```text
Scheduler
   │
   ▼
Trigger.next(...)
```

Le moteur n'a plus besoin de connaître chaque règle spécifique.

---

# 34. Strategy Pattern et scheduling

Conceptuellement, `Trigger` ressemble à une stratégie.

```text
             Trigger
                │
      ┌─────────┼─────────┐
      │         │         │
     Date    Interval    Cron
```

Chaque implémentation répond à la même question :

```text
What is the next valid occurrence?
```

---

# 35. Scheduler state versus trigger state

Certaines règles peuvent être stateless.

Exemple :

```text
CronTrigger
```

peut souvent calculer la prochaine occurrence à partir d'une date.

D'autres peuvent nécessiter davantage d'état.

La distinction :

```text
trigger state
scheduler state
execution state
```

devra être étudiée avec attention.

---

# 36. Évolution vers les workflows de données

Avec la montée du data engineering, le scheduling est devenu central.

Exemple :

```text
02:00 ingest
02:15 transform
03:00 aggregate
04:00 publish
```

Mais l'approche strictement temporelle pose un problème.

Que se passe-t-il si l'ingestion dure plus longtemps ?

---

# 37. Time-based dependency versus data dependency

Approche naïve :

```text
02:00 ingest
02:30 transform
```

Mais :

```text
ingest duration = 45 min
```

alors :

```text
transform starts too early
```

Une approche plus robuste devient :

```text
ingest
  │ success
  ▼
transform
```

On passe ainsi :

```text
time-based scheduling
```

à :

```text
dependency-based orchestration
```

---

# 38. Pourquoi les workflow engines ont émergé

Parce que de nombreux systèmes ont besoin de représenter :

```text
dependencies
branching
retries
state
artifacts
compensation
backfills
```

Le scheduler temporel seul ne suffit plus.

D'où :

```text
Scheduler
    +
Workflow Engine
```

ou parfois une plateforme intégrant les deux.

---

# 39. Le risque de confusion moderne

Aujourd'hui, certaines plateformes sont appelées :

```text
scheduler
orchestrator
workflow engine
task platform
```

parfois de manière interchangeable.

Pour PyScheduleKit, il faudra au contraire maintenir une définition précise.

---

# 40. Distributed scheduling

Lorsque l'application devient distribuée, plusieurs instances du scheduler peuvent exister.

Exemple :

```text
Scheduler A
Scheduler B
Scheduler C
```

avec un store partagé :

```text
        Shared Store
       /     |      \
      A      B       C
```

Cela introduit un problème :

```text
Who owns a due occurrence?
```

---

# 41. Duplicate execution

Sans coordination :

```text
Schedule X due @ 08:00
```

peut être vu simultanément par :

```text
Scheduler A
Scheduler B
```

et produire :

```text
Execution X1
Execution X2
```

Cette duplication peut être indésirable.

---

# 42. Locks

Une solution classique consiste à utiliser :

```text
lock(schedule)
```

Conceptuellement :

```text
A acquires lock
B fails to acquire lock
        ↓
A processes occurrence
```

Mais les locks introduisent leurs propres problèmes.

---

# 43. Pourquoi un lock permanent est dangereux

Supposons :

```text
A acquires lock
A crashes
```

Si le lock n'expire jamais :

```text
Schedule X remains blocked forever
```

Cela conduit à la notion de :

```text
Lease
```

---

# 44. Lease

Une lease représente un droit temporaire.

```text
owner = scheduler-A
expires_at = 08:00:30
```

Si A disparaît :

```text
08:00:30
lease expires
```

Une autre instance peut alors reprendre.

---

# 45. Leader election

Une stratégie différente consiste à désigner une seule instance responsable du scheduling.

```text
A = leader
B = standby
C = standby
```

Seul A prend les décisions temporelles.

En cas d'échec :

```text
B becomes leader
```

---

# 46. Clock skew

Dans un système distribué, deux machines peuvent avoir des horloges légèrement différentes.

Exemple :

```text
Scheduler A → 08:00:01
Scheduler B → 07:59:58
```

Cela peut affecter :

```text
due detection
lease expiration
timeouts
ordering
```

Le temps devient donc une problématique distribuée.

---

# 47. Wall clock

Une `wall clock` représente l'heure civile.

Exemple :

```text
2026-09-28 08:00 Europe/Paris
```

Elle est nécessaire pour :

```text
calendar scheduling
cron
human schedules
business rules
```

---

# 48. Monotonic clock

Une horloge monotone permet de mesurer :

```text
elapsed time
```

sans dépendre directement des ajustements de l'heure civile.

Elle est adaptée à :

```text
timeouts
delays
durations
leases
```

Conceptuellement :

```text
elapsed = monotonic_now - monotonic_start
```

---

# 49. Pourquoi il faut distinguer les deux

Une règle :

```text
Every day at 08:00
```

utilise une horloge civile.

Un timeout :

```text
cancel after 30 seconds
```

est généralement mieux représenté par une durée monotone.

Ainsi :

```text
calendar time
≠
elapsed time
```

---

# 50. Le problème des fuseaux horaires

Le scheduling moderne doit gérer :

```text
08:00 Europe/Paris
```

différemment de :

```text
08:00 UTC
```

Une règle temporelle comporte donc potentiellement :

```text
local time
+
timezone
```

---

# 51. UTC ne résout pas tout

Il peut être tentant de tout convertir en UTC.

Cela fonctionne bien pour représenter un instant.

Mais une règle comme :

```text
every day at 08:00 Paris time
```

ne correspond pas toute l'année à la même heure UTC.

À cause des changements d'heure :

```text
08:00 Paris
→ parfois 06:00 UTC
→ parfois 07:00 UTC
```

Une règle récurrente locale doit donc conserver son intention locale.

---

# 52. DST

Le changement d'heure introduit deux situations importantes.

---

## 52.1 Heure inexistante

Certaines heures peuvent être sautées.

Exemple conceptuel :

```text
01:59
 ↓
03:00
```

Une planification à :

```text
02:30
```

pose alors problème.

---

## 52.2 Heure ambiguë

Lors du retour à l'heure précédente :

```text
02:30
```

peut se produire deux fois.

Le scheduler doit définir une politique.

---

# 53. Calendriers métier

Les besoins d'entreprise introduisent des règles plus riches que cron.

Exemples :

```text
premier jour ouvré
dernier jour bancaire
jour ouvré précédent
jours fériés exclus
fenêtre de maintenance
jour de clôture
```

Cela conduit à des objets de type :

```text
Calendar
BusinessCalendar
HolidayCalendar
```

---

# 54. Fundamental concept — Recurrence

Une récurrence est une règle produisant plusieurs occurrences.

```text
R = {t1, t2, t3, ...}
```

Exemple :

```text
Every Monday @ 08:00
```

produit une suite temporelle.

Le scheduler n'a donc pas nécessairement besoin de connaître à l'avance toutes les occurrences.

---

# 55. Fundamental concept — Occurrence

Une occurrence représente :

> un instant candidat produit par une règle temporelle.

Exemple :

```text
Schedule:
Every day @ 06:00

Occurrences:
2026-09-28 06:00
2026-09-29 06:00
2026-09-30 06:00
```

---

# 56. Occurrence versus scheduled execution

Une occurrence peut exister conceptuellement sans devenir une exécution.

Exemple :

```text
Occurrence @ 08:00
        │
        ▼
MisfirePolicy = SKIP
        │
        ▼
No Execution
```

Donc :

```text
Occurrence ≠ Execution
```

---

# 57. Fundamental concept — Due

Une occurrence est `due` lorsqu'elle atteint le moment où le scheduler doit prendre une décision.

Version simplifiée :

```text
now >= occurrence.time
```

Version plus réaliste :

```text
now
+
schedule state
+
grace period
+
calendar
+
execution state
+
policies
```

déterminent la décision.

---

# 58. Fundamental concept — Misfire

Une occurrence est dite manquée lorsqu'elle n'a pas été traitée comme prévu au moment attendu.

Exemple :

```text
scheduled_at = 08:00
scheduler restart = 08:15
```

Le scheduler doit décider :

```text
skip
run now
catch up
coalesce
reschedule
```

---

# 59. Fundamental concept — Catch-up

Catch-up signifie :

> tenter de rejouer les occurrences passées qui auraient dû être exécutées.

Exemple :

```text
08:00 missed
09:00 missed
10:00 missed
```

restart :

```text
10:30
```

catch-up :

```text
run 08:00
run 09:00
run 10:00
```

---

# 60. Fundamental concept — Coalescing

Le coalescing consiste à fusionner plusieurs occurrences.

```text
08:00
09:00
10:00
```

devient :

```text
1 execution
```

Cela peut être utile lorsque :

```text
latest state matters
```

plutôt que :

```text
every historical occurrence matters
```

---

# 61. Fundamental concept — Overlap

Une exécution peut durer plus longtemps que la fréquence du schedule.

Exemple :

```text
interval = 5 min
duration = 8 min
```

Cela crée des overlaps.

---

# 62. Fundamental concept — Concurrency policy

Le scheduler doit alors définir :

```text
ALLOW
FORBID
QUEUE
COALESCE
REPLACE
```

Ces politiques décrivent une sémantique métier et pas seulement une optimisation technique.

---

# 63. Fundamental concept — Jitter

Un grand nombre de jobs peuvent être programmés exactement au même moment.

Exemple :

```text
00:00
├── Job A
├── Job B
├── Job C
├── Job D
└── Job E
```

Cela peut produire un pic de charge.

Un jitter permet :

```text
00:00:04
00:00:11
00:00:18
00:00:22
00:00:28
```

---

# 64. Fundamental concept — Grace period

Une occurrence peut rester acceptable pendant un délai limité.

```text
scheduled_at = 08:00
grace_period = 5 minutes
```

Alors :

```text
08:03 → valid
08:20 → expired
```

---

# 65. Fundamental concept — Deadline

Une deadline définit un instant après lequel l'exécution n'a plus de sens.

```text
Occurrence
    │
    ├──── valid window ────┐
    │                      │
    ▼                      ▼
scheduled_at            deadline
```

---

# 66. Fundamental concept — Retry

Un retry consiste à tenter de nouveau une opération après un échec.

Mais son niveau doit être clairement identifié.

Exemples :

```text
schedule submission retry
execution retry
workflow step retry
HTTP request retry
```

Ils ne sont pas équivalents.

---

# 67. Retry versus recurrence

Très important :

```text
RETRY
```

et :

```text
RECURRENCE
```

ne représentent pas le même phénomène.

---

## Recurrence

```text
08:00
09:00
10:00
```

Ce sont des occurrences prévues indépendamment.

---

## Retry

```text
08:00 execution failed
08:00:30 retry #1
08:01:30 retry #2
```

Les tentatives dérivent d'une même occurrence.

---

# 68. Modèle conceptuel

```text
Schedule
   │
   ├── Occurrence #1
   │       │
   │       ├── Attempt #1 FAILED
   │       ├── Attempt #2 FAILED
   │       └── Attempt #3 SUCCESS
   │
   └── Occurrence #2
           │
           └── Attempt #1 SUCCESS
```

Cette distinction est très importante pour le futur domain model.

---

# 69. Fundamental concept — Backoff

Lors de retries, le délai peut évoluer.

Exemple :

```text
retry #1 → 5 s
retry #2 → 10 s
retry #3 → 20 s
retry #4 → 40 s
```

On parle souvent de :

```text
exponential backoff
```

---

# 70. Fundamental concept — Idempotence

Si une même exécution peut être déclenchée plusieurs fois, l'opération devrait idéalement être capable de tolérer les doublons.

Exemple :

```text
charge_credit_card()
```

n'est pas naturellement idempotent.

Alors que :

```text
set_user_status("active")
```

peut l'être davantage.

Le scheduling distribué rend cette question importante.

---

# 71. At-most-once

Cette sémantique signifie :

```text
0 or 1 execution
```

On préfère éventuellement perdre une exécution plutôt que la dupliquer.

---

# 72. At-least-once

Cette sémantique signifie :

```text
1 or more attempts
```

On préfère rejouer plutôt que perdre.

Cela nécessite souvent des opérations idempotentes.

---

# 73. Exactly-once

Le terme est délicat.

Il faut distinguer :

```text
exactly one scheduler decision
```

de :

```text
exactly one execution attempt
```

et :

```text
exactly one externally observable effect
```

Ces trois propriétés ne sont pas automatiquement équivalentes.

---

# 74. Fundamental concept — Persistence

Un scheduler durable doit pouvoir conserver :

```text
schedules
trigger state
next run time
lifecycle state
execution history
ownership information
```

selon son architecture.

---

# 75. Fundamental concept — Recovery

Après redémarrage :

```text
scheduler starts
      │
      ▼
load state
      │
      ▼
reconcile missed occurrences
      │
      ▼
compute next occurrences
      │
      ▼
resume operation
```

La reprise fait donc partie intégrante du scheduling.

---

# 76. Fundamental concept — Reconciliation

Un système peut devoir comparer :

```text
expected state
```

à :

```text
actual state
```

Exemple :

```text
Occurrence expected @ 08:00

Store says:
no execution exists

Current time:
08:15
```

Le scheduler doit réconcilier cette situation.

---

# 77. Scheduling comme système de contrôle

On peut voir un scheduler comme un petit système de contrôle.

Entrées :

```text
time
schedule definitions
execution state
policies
```

Décision :

```text
wait
execute
skip
catch up
coalesce
```

Sorties :

```text
execution requests
state updates
events
```

---

# 78. Modèle abstrait

```text
State(t)
   +
Clock(t)
   +
Rules
   ↓
Decision
   ↓
State(t+1)
```

Ce modèle rapproche le scheduling d'une machine à états.

---

# 79. Scheduling et state machines

Un schedule possède souvent un état :

```text
ACTIVE
PAUSED
DISABLED
COMPLETED
CANCELLED
```

Une exécution possède également un état :

```text
SCHEDULED
QUEUED
RUNNING
SUCCESS
FAILED
CANCELLED
```

Ces deux machines à états ne doivent pas être confondues.

---

# 80. Lifecycle du schedule

Exemple :

```text
        ┌─────────┐
        │ ACTIVE  │
        └────┬────┘
             │ pause
             ▼
        ┌─────────┐
        │ PAUSED  │
        └────┬────┘
             │ resume
             ▼
        ┌─────────┐
        │ ACTIVE  │
        └────┬────┘
             │ cancel
             ▼
        ┌───────────┐
        │ CANCELLED │
        └───────────┘
```

---

# 81. Lifecycle de l'exécution

```text
SCHEDULED
    │
    ▼
QUEUED
    │
    ▼
RUNNING
    │
 ┌──┼────┐
 ▼  ▼    ▼
OK FAIL CANCELLED
```

Les deux lifecycles interagissent mais ne représentent pas la même chose.

---

# 82. Évolution vers l'observabilité

Les schedulers modernes doivent expliquer :

```text
what ran?
when?
why?
how late?
where?
which scheduler?
what result?
```

Cela mène à :

```text
events
metrics
logs
execution history
tracing
```

---

# 83. Le concept de scheduling lag

On peut mesurer :

```text
actual_start - scheduled_time
```

Exemple :

```text
scheduled_at = 08:00:00
started_at   = 08:00:07

lag = 7 seconds
```

Cette métrique est importante pour savoir si le scheduler respecte ses engagements temporels.

---

# 84. Scheduling accuracy

Tous les schedulers ne visent pas la même précision.

Certains travaillent à la :

```text
minute
```

d'autres à :

```text
second
```

voire moins.

La précision dépend :

```text
du domaine
de l'architecture
du système d'exploitation
du runtime
des garanties attendues
```

---

# 85. Scheduling n'est pas du temps réel dur

Un scheduler applicatif classique ne garantit généralement pas :

```text
execute exactly at 08:00:00.000000
```

Il garantit plutôt quelque chose comme :

```text
execution becomes due around this time
```

avec une certaine tolérance.

Il faut distinguer :

```text
application scheduling
```

de :

```text
hard real-time scheduling
```

---

# 86. Hard real-time

Dans un système temps réel dur :

```text
missing a deadline
```

peut être considéré comme une défaillance du système.

Exemples possibles :

```text
contrôle industriel
avionique
systèmes embarqués critiques
```

PyScheduleKit ne vise pas ce domaine.

---

# 87. Soft real-time

Certains systèmes tolèrent un léger retard.

Exemple :

```text
planned = 08:00:00
actual  = 08:00:03
```

Cela peut rester acceptable.

Les schedulers applicatifs appartiennent généralement davantage à cette famille.

---

# 88. Modern scheduling landscape

Aujourd'hui, plusieurs catégories coexistent.

```text
OS Scheduler
Cron Scheduler
Application Scheduler
Task Queue Scheduler
Workflow Scheduler
Data Orchestrator
Distributed Scheduler
Cloud Scheduler
Container Scheduler
```

Elles utilisent parfois des termes identiques pour des objets différents.

---

# 89. Container scheduling

Kubernetes utilise également le terme scheduler.

Mais sa question principale est :

```text
On which node should this Pod run?
```

Cela correspond davantage à :

```text
placement scheduling
```

qu'au scheduling temporel.

Même vocabulaire, autre domaine.

---

# 90. Cloud schedulers

Les plateformes cloud proposent souvent :

```text
cron-like schedules
event rules
delayed triggers
serverless invocations
```

Le modèle devient :

```text
Time Rule
  ↓
Cloud Scheduler
  ↓
Function / HTTP endpoint / Event
```

Il s'agit d'une forme moderne du scheduling temporel.

---

# 91. Le scheduling comme producteur d'événements

Une autre manière de voir le scheduler est :

```text
Time
 ↓
Scheduler
 ↓
Event
 ↓
Consumer
```

Exemple :

```text
"DailyReportDue"
```

Le scheduler ne lance pas nécessairement directement le code.

Il peut publier un événement.

---

# 92. Scheduled command versus scheduled event

Deux modèles peuvent donc exister.

### Modèle direct

```text
Schedule
  ↓
Callable
```

### Modèle event-driven

```text
Schedule
  ↓
Event
  ↓
Consumer
```

PyScheduleKit pourra potentiellement supporter les deux via des adapters.

---

# 93. Convergence avec les architectures modernes

Dans une architecture modulaire :

```text
PyScheduleKit
      │
      ▼
ExecutionRequest
      │
      ├── local executor
      ├── task queue
      ├── event bus
      └── PyWorkflowKit
```

Le scheduler reste propriétaire uniquement de la décision temporelle.

---

# 94. Une chronologie conceptuelle simplifiée

```text
1950s–1960s
Batch Processing
       │
       ▼
1960s–1970s
OS / Time-sharing Schedulers
       │
       ▼
1970s+
Unix Automated Job Scheduling
       │
       ▼
cron / at
       │
       ▼
Enterprise Batch Scheduling
       │
       ▼
Job Dependencies
       │
       ▼
Task Queues
       │
       ▼
Workflow Engines
       │
       ▼
Distributed Schedulers
       │
       ▼
Cloud / Application Scheduling
       │
       ▼
Modern Orchestration Platforms
```

Cette chronologie est conceptuelle : plusieurs familles ont évolué parallèlement et continuent de coexister.

---

# 95. Ce que l'histoire nous apprend

L'évolution historique montre que plusieurs besoins ont progressivement été séparés.

```text
WHEN?
    ↓
Scheduling

WHERE / ON WHAT RESOURCE?
    ↓
Placement / Resource Scheduling

WHO CAN PROCESS THIS?
    ↓
Queue / Worker System

WHAT NEXT?
    ↓
Workflow

WHAT HAPPENS IF IT FAILS?
    ↓
Resilience / Retry Policies

HOW DO WE RECOVER?
    ↓
Persistence / Reconciliation
```

---

# 96. Le scheduling moderne est une composition

Un système réel peut aujourd'hui combiner :

```text
Time Rule
   │
   ▼
Scheduler
   │
   ▼
Workflow Engine
   │
   ▼
Task Queue
   │
   ▼
Worker
   │
   ▼
Domain Operation
```

Ces composants ne doivent pas nécessairement être fusionnés dans une seule abstraction.

---

# 97. Application à PyScheduleKit

PyScheduleKit doit tirer parti de cette histoire.

Il doit notamment éviter de recréer simultanément :

```text
cron
Celery
Airflow
Kubernetes scheduler
Temporal
```

dans un seul package.

Sa responsabilité doit rester centrée sur :

```text
temporal scheduling
```

---

# 98. Domaine cible de PyScheduleKit

```text
                   PyScheduleKit
                        │
          ┌─────────────┼─────────────┐
          │             │             │
         Time         Rules        Decisions
          │             │             │
          ▼             ▼             ▼
        Clock        Trigger        Due?
      Timezone       Schedule       Skip?
      Calendar      Recurrence      Execute?
                                   Catch-up?
                                   Coalesce?
```

---

# 99. Frontières historiques utiles

Les distinctions historiques conduisent à cette matrice.

| Domaine | Question principale |
|---|---|
| OS Scheduling | Quel processus utilise la ressource ? |
| Job Scheduling | Quand le job doit-il démarrer ? |
| Queueing | Quel travail attend un worker ? |
| Workflow | Quelle étape vient ensuite ? |
| Placement Scheduling | Où exécuter le workload ? |
| Orchestration | Comment coordonner plusieurs opérations ? |
| PyScheduleKit | Quand produire une demande d'exécution ? |

---

# 100. Les concepts fondamentaux retenus

À l'issue de cette analyse historique, les concepts suivants doivent être conservés comme vocabulaire de base.

```text
Time
Clock
Instant
Duration
Timezone
Calendar

Job
Target

Schedule
Trigger
Recurrence
Occurrence
NextRunTime

Due
Misfire
GracePeriod
Deadline
CatchUp
Coalescing
Jitter

Concurrency
Overlap

ExecutionRequest
Execution
Attempt
Result

Retry
Backoff

Scheduler
Tick
WakeUp

Store
Persistence
Recovery
Reconciliation

Lock
Lease
Ownership
LeaderElection

Event
Metric
History
```

---

# 101. Première classification conceptuelle

```text
Scheduling Domain
│
├── Temporal Model
│   ├── Clock
│   ├── Instant
│   ├── Duration
│   ├── Timezone
│   └── Calendar
│
├── Planning Model
│   ├── Job
│   ├── Schedule
│   ├── Trigger
│   ├── Recurrence
│   └── Occurrence
│
├── Decision Model
│   ├── Due
│   ├── Misfire
│   ├── CatchUp
│   ├── Coalescing
│   └── ConcurrencyPolicy
│
├── Execution Boundary
│   ├── ExecutionRequest
│   ├── Execution
│   └── Attempt
│
├── Runtime
│   ├── Scheduler
│   ├── Tick
│   ├── WakeUp
│   └── Executor
│
├── Durability
│   ├── Store
│   ├── Recovery
│   └── Reconciliation
│
└── Distribution
    ├── Lock
    ├── Lease
    ├── Ownership
    └── LeaderElection
```

---

# 102. Concepts à ne pas confondre

## Job vs Schedule

```text
Job
= what

Schedule
= what + when + policies
```

---

## Trigger vs Scheduler

```text
Trigger
= calculates occurrences

Scheduler
= coordinates decisions
```

---

## Occurrence vs Execution

```text
Occurrence
= temporal expectation

Execution
= concrete runtime activity
```

---

## Recurrence vs Retry

```text
Recurrence
= expected future occurrence

Retry
= new attempt of failed work
```

---

## Scheduler vs Queue

```text
Scheduler
= when work becomes due

Queue
= where work waits
```

---

## Scheduler vs Workflow

```text
Scheduler
= when

Workflow
= what next
```

---

## Scheduler vs OS Scheduler

```text
PyScheduleKit
= temporal execution eligibility

OS Scheduler
= CPU/process resource allocation
```

---

# 103. Invariant conceptuel majeur

Une règle importante peut être retenue pour toute la suite du projet :

> **Le scheduling ne doit pas être défini par le mécanisme qui exécute le travail, mais par la logique qui détermine quand ce travail devient exigible.**

Autrement dit :

```text
Scheduling
≠
Execution mechanism
```

Le scheduler peut soumettre à :

```text
thread
process
async runtime
queue
workflow engine
remote worker
HTTP endpoint
event bus
```

sans changer de responsabilité fondamentale.

---

# 104. Deuxième invariant conceptuel

> **Une règle temporelle produit des occurrences ; elle ne produit pas directement des effets métier.**

Ainsi :

```text
Trigger
   ↓
Occurrence
   ↓
Decision
   ↓
ExecutionRequest
   ↓
Effect
```

Cette séparation aidera à garder le domaine testable et déterministe.

---

# 105. Troisième invariant conceptuel

> **Une occurrence passée ne doit jamais implicitement déterminer son propre traitement.**

Son traitement doit être défini par une politique explicite.

Exemple :

```text
Occurrence missed
       │
       ▼
MisfirePolicy
       │
 ┌─────┼──────────────┐
 ▼     ▼              ▼
SKIP RUN_NOW       CATCH_UP
```

---

# 106. Quatrième invariant conceptuel

> **Les garanties d'exécution ne doivent pas être déduites uniquement du scheduler.**

Même si PyScheduleKit crée exactement une `ExecutionRequest`, l'effet réel peut être dupliqué plus loin.

```text
Scheduler
   ↓
Queue
   ↓
Worker
   ↓
Database
```

Les garanties end-to-end nécessitent une coopération de plusieurs composants.

---

# 107. Cinquième invariant conceptuel

> **Le temps lui-même doit être une dépendance explicite.**

Au lieu de :

```python
datetime.now()
```

partout dans le domaine, un modèle plus robuste pourrait s'appuyer sur :

```text
Clock
```

Cela facilitera :

```text
tests
simulation
DST scenarios
recovery tests
deterministic decisions
```

---

# 108. PyScheduleKit dans l'écosystème Py*Kit

L'histoire du scheduling confirme la séparation suivante :

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

# 109. Composition de référence

```text
TIME
 │
 ▼
PyScheduleKit
 │
 │ ExecutionRequest
 ▼
PyWorkflowKit
 │
 ├── PyIngestKit
 │
 ├── PyTransformKit
 │
 └── Publish
```

Ou plus simplement :

```text
PyScheduleKit
      │
      ▼
PyIngestKit
```

selon le besoin.

---

# 110. Modèle historique → modèle PyScheduleKit

On peut résumer l'évolution ainsi :

```text
Batch Job
   │
   ▼
Scheduled Job
   │
   ▼
Recurring Schedule
   │
   ▼
Trigger
   │
   ▼
Occurrence
   │
   ▼
Scheduling Decision
   │
   ▼
Execution Request
```

PyScheduleKit cherche donc à rendre explicites des abstractions qui se sont construites progressivement pendant plusieurs décennies.

---

# 111. Ce qu'il faut retenir

Le scheduling moderne est le résultat de plusieurs lignées historiques.

```text
Batch
→ notion de Job

Unix cron / at
→ planification temporelle

OS schedulers
→ états, attente, priorité, ressources

Enterprise schedulers
→ persistance, calendriers, dépendances

Task queues
→ découplage execution / workers

Workflow engines
→ dépendances et orchestration

Distributed systems
→ leases, ownership, idempotence

Cloud systems
→ triggers, events, remote execution
```

PyScheduleKit ne doit pas copier tous ces systèmes.

Il doit comprendre ce qu'ils ont apporté au vocabulaire du domaine.

---

# 112. Modèle mental final

```text
                     HUMAN INTENT
                         │
                         ▼
                  Temporal Rule
                         │
                         ▼
                      Trigger
                         │
                         ▼
                    Occurrence
                         │
                         ▼
                    Scheduler
                         │
                   ┌─────┴─────┐
                   │ Decision  │
                   └─────┬─────┘
                         │
              ┌──────────┼─────────┐
              │          │         │
              ▼          ▼         ▼
             WAIT       SKIP     EXECUTE
                                   │
                                   ▼
                           ExecutionRequest
                                   │
                       ┌───────────┼────────────┐
                       │           │            │
                       ▼           ▼            ▼
                     Queue      Workflow      Executor
                       │           │            │
                       └───────────┴─────┬──────┘
                                       ▼
                                   Execution
```

---

# Conclusion

L'histoire du scheduling montre qu'il n'existe pas un unique problème appelé « scheduling ».

Plusieurs disciplines ont émergé autour de questions distinctes :

```text
quand ?
où ?
sur quelle ressource ?
dans quel ordre ?
avec quel worker ?
que faire après un échec ?
comment reprendre après une panne ?
```

Le domaine qui intéresse PyScheduleKit doit rester centré sur la première :

> **Quand une action doit-elle devenir exigible, et comment cette échéance temporelle doit-elle être transformée en décision d'exécution ?**

L'histoire fait également apparaître plusieurs concepts fondamentaux qui structureront désormais la suite :

```text
Job
Schedule
Trigger
Occurrence
Clock
Calendar
Scheduler
Misfire
CatchUp
Coalescing
Concurrency
ExecutionRequest
Execution
Retry
Store
Lease
```

Le prochain travail consiste donc à stabiliser le vocabulaire afin d'éviter que des mots comme `Job`, `Task`, `Run`, `Trigger`, `Execution` ou `Schedule` prennent plusieurs significations au sein du même framework.

---

# Suite documentaire

Le prochain document est :

```text
03_SCHEDULING_DOMAIN_VOCABULARY.md
```

Il devra définir rigoureusement le lexique du domaine, notamment :

```text
Job
Task
Operation
Target

Schedule
Trigger
Recurrence
Occurrence
NextRunTime

Due
Misfire
CatchUp
Coalescing
Overlap

ExecutionRequest
Execution
Run
Attempt

Executor
Scheduler
Worker

Calendar
Clock
Instant
Duration
Timezone

Retry
Backoff
Timeout
Deadline
GracePeriod
Jitter

Store
Lock
Lease
Ownership
```

L'objectif sera de disposer d'un **ubiquitous language** avant de commencer la modélisation des objets métier.