# PyScheduleKit — Misfire, Coalescing & Catch-Up Model

**Document :** `13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle métier de référence  
**Nature :** Domain Model — Misfire / Catch-Up / Coalescing  
**Prérequis :**
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`
- `11_DATE_INTERVAL_AND_CRON_TRIGGERS.md`

---

# 1. Objectif

Dans un monde idéal, toute occurrence planifiée serait détectée exactement au bon moment :

```text
scheduled_at
     │
     ▼
scheduler wakes up
     │
     ▼
ExecutionRequest
```

Mais un scheduler réel peut :

```text
être arrêté

redémarrer en retard

être indisponible

être saturé

perdre temporairement son accès à la base

subir une panne réseau

être suspendu

être victime d'un failover

être bloqué par une lease concurrente
```

On peut alors découvrir, à un instant donné, qu'une ou plusieurs échéances prévues sont déjà dans le passé.

Exemple :

```text
Schedule:
every hour

Occurrences prévues:
08:00
09:00
10:00
11:00

Scheduler restart:
11:37
```

La question n'est plus seulement :

> Quelle est la prochaine occurrence ?

mais :

> **Que faire des occurrences qui auraient dû être traitées pendant l'absence du scheduler ?**

C'est le domaine de :

```text
Misfire
Catch-Up
Coalescing
```

---

# 2. Trois concepts différents

Il est crucial de ne pas les confondre.

```text
Misfire
=
constat qu'une occurrence est en retard
ou n'a pas été traitée dans sa fenêtre normale

Catch-Up
=
stratégie consistant à récupérer
une ou plusieurs occurrences manquées

Coalescing
=
stratégie consistant à regrouper
plusieurs occurrences en une seule demande
```

---

# 3. Modèle mental

```text
Occurrences théoriques
     │
     ▼
08:00  09:00  10:00  11:00
  X      X      X       ?
     scheduler absent
              │
              ▼
           now=11:37
              │
              ▼
       Missed Occurrences
              │
      ┌───────┼─────────┐
      │       │         │
      ▼       ▼         ▼
     SKIP   CATCH-UP  COALESCE
```

---

# 4. Misfire — définition

Une occurrence est en situation de `Misfire` lorsque :

```text
elle aurait dû devenir exigible
```

mais qu'elle est examinée après son instant planifié.

Formellement :

```text
now > scheduled_at
```

ne suffit toutefois pas toujours.

Il faut également tenir compte de :

```text
GracePeriod
Deadline
```

---

# 5. Misfire avec GracePeriod

Supposons :

```text
scheduled_at = 08:00

grace_period = 5 minutes
```

Alors :

```text
deadline = 08:05
```

À :

```text
08:03
```

l'occurrence est en retard chronologiquement, mais peut encore être considérée comme admissible.

À :

```text
08:10
```

elle a dépassé sa fenêtre normale.

---

# 6. Distinction entre Late et Misfired

Il peut être utile de distinguer :

```text
LATE
```

de :

```text
MISFIRED
```

Par exemple :

```text
scheduled_at < now <= deadline
→ LATE BUT ELIGIBLE
```

et :

```text
now > deadline
→ MISFIRED
```

---

# 7. Modèle recommandé

```text
scheduled_at
     │
     ├──────────── GracePeriod ────────────┐
     │                                     │
     ▼                                     ▼
   08:00                                 08:05
     │                                     │
     │ Normal / Late but acceptable        │
     │                                     │
     └─────────────────────────────────────┘
                                           │
                                           ▼
                                      MISFIRE ZONE
```

---

# 8. Misfire n'est pas un échec d'exécution

Cette distinction est fondamentale.

```text
Misfire
```

concerne :

```text
une occurrence qui n'a pas été dispatchée
à temps
```

Alors que :

```text
Execution Failure
```

concerne :

```text
une execution réellement lancée
qui a échoué
```

Donc :

```text
Misfire
≠
Execution Failure
```

---

# 9. Misfire n'est pas un Retry

Un retry concerne :

```text
la même Execution
ou le même travail déjà tenté
```

Un misfire concerne :

```text
une occurrence temporelle
qui n'a jamais été traitée normalement
```

Donc :

```text
Retry
≠
Misfire
```

---

# 10. Misfire n'est pas un Trigger concept

Le Trigger peut reconstruire :

```text
les occurrences théoriques
```

mais il ne doit pas décider :

```text
que faire de celles qui sont en retard
```

Cette décision appartient à :

```text
MisfirePolicy
```

---

# 11. Chaîne conceptuelle

```text
Trigger
   │
   ▼
Expected Occurrences
   │
   ▼
Compare with now
   │
   ▼
Missed / Late Occurrences
   │
   ▼
MisfirePolicy
   │
   ▼
SchedulingDecision
```

---

# 12. MissedOccurrence

Il peut être utile d'introduire :

```text
MissedOccurrence
```

comme représentation explicite d'une occurrence théorique qui n'a pas été normalement traitée.

Elle peut contenir :

```text
OccurrenceKey
scheduled_at
lateness
deadline
schedule_revision
```

---

# 13. Classification

```text
MissedOccurrence
=
Value Object
```

car elle est définie par :

```text
l'occurrence
+
le contexte temporel de son constat
```

---

# 14. Lateness

On peut définir :

```text
Lateness
=
now - scheduled_at
```

Exemple :

```text
scheduled_at = 08:00
now = 08:17

lateness = 17 minutes
```

---

# 15. GracePeriod

Si :

```text
lateness <= grace_period
```

alors l'occurrence peut rester :

```text
eligible
```

sans être considérée comme un véritable misfire.

---

# 16. MisfireDetection

Un service ou comportement peut répondre :

```text
classify_occurrence(
    scheduled_at,
    now,
    grace_period
)
```

et produire par exemple :

```text
ON_TIME
LATE
MISFIRED
```

---

# 17. MisfireStatus

Une classification possible :

```text
ON_TIME

LATE_BUT_ELIGIBLE

MISFIRED
```

Éviter de multiplier inutilement les états si une simple `SchedulingDecision` suffit.

---

# 18. MisfirePolicy

`MisfirePolicy` répond :

> **Que devons-nous faire lorsqu'une occurrence a dépassé sa fenêtre normale ?**

Elle est donc une :

```text
Policy
```

DDD.

---

# 19. Politiques fondamentales

Une première taxonomie peut être :

```text
SKIP

RUN_NOW

CATCH_UP

COALESCE
```

Éventuellement :

```text
FAIL
```

pour certaines configurations strictes.

---

# 20. SKIP

`SKIP` signifie :

> L'occurrence manquée est abandonnée.

Exemple :

```text
scheduled_at = 08:00
now = 10:00

policy = SKIP
```

Résultat :

```text
Occurrence 08:00
→ SKIPPED
```

Aucune execution n'est créée.

---

# 21. Pourquoi SKIP ?

Certains travaux n'ont plus de valeur s'ils arrivent trop tard.

Exemple :

```text
send "good morning" notification at 07:00
```

À :

```text
15:00
```

l'exécution n'a probablement plus de sens.

---

# 22. RUN_NOW

`RUN_NOW` signifie :

> L'occurrence manquée produit immédiatement une demande d'exécution.

Mais son :

```text
scheduled_at
```

reste l'heure originale.

---

# 23. Exemple RUN_NOW

```text
scheduled_at = 08:00
now = 10:17
```

On crée :

```text
ExecutionRequest
scheduled_at = 08:00
created_at   = 10:17
```

et non :

```text
scheduled_at = 10:17
```

---

# 24. Pourquoi conserver scheduled_at

Parce que l'occurrence reste :

```text
celle de 08:00
```

même si elle est traitée à :

```text
10:17
```

Cela est essentiel pour :

```text
audit
partitions
idempotence
metrics
correlation
```

---

# 25. CATCH_UP

`CATCH_UP` signifie :

> Reconstituer et traiter plusieurs occurrences manquées individuellement.

Exemple :

```text
hourly schedule

scheduler down:
08:30 → 12:15
```

Occurrences manquées :

```text
09:00
10:00
11:00
12:00
```

Catch-up peut générer :

```text
ExecutionRequest #1 → 09:00
ExecutionRequest #2 → 10:00
ExecutionRequest #3 → 11:00
ExecutionRequest #4 → 12:00
```

---

# 26. Catch-Up ne change pas le Trigger

Le Trigger est simplement utilisé pour reconstruire :

```text
les occurrences théoriques
```

La policy décide :

```text
qu'elles doivent être matérialisées
```

---

# 27. COALESCE

`COALESCE` signifie :

> Regrouper plusieurs occurrences manquées dans une seule demande d'exécution.

Exemple :

```text
09:00
10:00
11:00
12:00
```

deviennent :

```text
1 ExecutionRequest
```

---

# 28. Question majeure du Coalescing

À quelle occurrence cette request appartient-elle ?

Plusieurs possibilités :

```text
FIRST

LATEST

RANGE

GROUP
```

Cette sémantique doit être explicite.

---

# 29. Coalescing par dernière occurrence

Une approche simple :

```text
09:00
10:00
11:00
12:00
```

→ une request associée à :

```text
12:00
```

et portant éventuellement :

```text
coalesced_count = 4
```

---

# 30. Limite de cette approche

On perd l'identité détaillée des occurrences précédentes si elles ne sont pas enregistrées ailleurs.

Pour un audit riche, il vaut mieux conserver :

```text
OccurrenceGroup
```

ou une collection de `OccurrenceKey`.

---

# 31. OccurrenceGroup

Une abstraction possible :

```text
OccurrenceGroup
│
├── first_scheduled_at
├── last_scheduled_at
├── count
└── occurrence_keys
```

Classification :

```text
Value Object
```

---

# 32. CoalescedExecutionRequest

On peut conceptuellement avoir :

```text
ExecutionRequest
│
├── request_id
├── schedule_id
├── primary_occurrence
└── occurrence_group?
```

---

# 33. Coalescing et ERD

Si chaque `ExecutionRequest` peut représenter plusieurs occurrences :

```text
Occurrence N
   │
   ▼
ExecutionRequest 1
```

la relation devient :

```text
N:1
```

et peut nécessiter une table d'association.

---

# 34. Recommandation V1

Ne pas imposer immédiatement un modèle N:N complexe.

On peut représenter le coalescing via :

```text
ExecutionRequest
+
OccurrenceBatch / OccurrenceRange
```

tout en conservant les clés sources dans un payload structuré.

---

# 35. Catch-Up versus Coalescing

```text
Catch-Up
=
rejouer plusieurs occurrences

Coalescing
=
réduire plusieurs occurrences
à un plus petit nombre d'executions
```

Le coalescing peut donc être considéré comme une **stratégie de catch-up**.

---

# 36. Taxonomie recommandée

```text
MisfirePolicy
│
├── Skip
├── RunNow
└── CatchUpPolicy
      │
      ├── ReplayAll
      ├── ReplayLimited
      └── Coalesce
```

Cette structure est conceptuellement plus précise.

---

# 37. CatchUpPolicy

Une `CatchUpPolicy` peut définir :

```text
enabled
max_occurrences
lookback_window
coalescing_strategy
ordering
```

---

# 38. Pourquoi limiter le catch-up

Supposons :

```text
schedule every second
```

et scheduler arrêté pendant :

```text
24 hours
```

Cela représente :

```text
86 400 occurrences
```

Un replay sans limite peut saturer immédiatement le système.

---

# 39. max_occurrences

Une policy peut imposer :

```text
max_occurrences = 100
```

---

# 40. Que faire si la limite est dépassée ?

Plusieurs stratégies possibles :

```text
KEEP_LATEST

KEEP_OLDEST

COALESCE_REMAINDER

FAIL

TRUNCATE
```

Elles doivent être explicites.

---

# 41. LookbackWindow

On peut aussi limiter temporellement :

```text
catch up only last 24 hours
```

via :

```text
LookbackWindow
```

---

# 42. Exemple

```text
now = Oct 10 12:00

lookback = 24h
```

On ignore les occurrences antérieures à :

```text
Oct 9 12:00
```

---

# 43. Catch-Up ordering

Si plusieurs occurrences sont rejouées :

```text
09:00
10:00
11:00
```

l'ordre recommandé est :

```text
oldest first
```

par défaut.

---

# 44. Pourquoi oldest first ?

Pour préserver :

```text
causalité temporelle
séquentialité métier
progression de partitions
```

---

# 45. Mais pas toujours

Certains cas peuvent préférer :

```text
latest first
```

si seule l'information la plus récente a de la valeur.

Cette stratégie ressemble cependant souvent davantage à du coalescing.

---

# 46. ReplayAll

```text
ReplayAll
```

signifie :

```text
toutes les occurrences manquées admissibles
→ une request chacune
```

sous réserve de limites de sécurité.

---

# 47. ReplayLatest

Une stratégie :

```text
ReplayLatest
```

peut choisir uniquement :

```text
la dernière occurrence manquée
```

Cela ressemble à :

```text
CoalesceLatest
```

---

# 48. CoalescingStrategy

On peut définir :

```text
LATEST

EARLIEST

RANGE

BATCH
```

---

# 49. LATEST

Toutes les occurrences sont représentées par la plus récente.

```text
09:00
10:00
11:00
→ 11:00
```

---

# 50. EARLIEST

Toutes sont représentées par la première.

```text
09:00
10:00
11:00
→ 09:00
```

Plus rare, mais possible.

---

# 51. RANGE

La request porte :

```text
from = 09:00
to   = 11:00
```

Cela est utile pour un target capable de traiter une plage.

---

# 52. Exemple data processing

Un job de traitement peut accepter :

```text
start_partition
end_partition
```

Coalescer :

```text
2026-10-01
2026-10-02
2026-10-03
```

en :

```text
range:
2026-10-01 → 2026-10-03
```

peut être très efficace.

---

# 53. Mais attention

PyScheduleKit ne doit pas deviner que le Target sait traiter une plage.

Cela doit être explicite dans :

```text
CoalescingPolicy
```

ou dans un adapter applicatif.

---

# 54. BATCH

Une autre stratégie :

```text
OccurrenceBatch
[
  09:00,
  10:00,
  11:00
]
```

est transmise au Target.

Cela nécessite un contrat clair côté execution.

---

# 55. Coalescing n'est donc pas purement temporel

Le choix de regrouper peut dépendre :

```text
des capacités du Target
```

C'est une frontière importante.

---

# 56. Recommandation architecturale

Le domaine de scheduling peut décider :

```text
quelles occurrences sont regroupées
```

mais la traduction vers les paramètres spécifiques du Target doit appartenir à :

```text
ExecutionRequestFactory
```

ou à l'adapter d'exécution.

---

# 57. MisfirePolicy minimale

Pour V1, une politique simple peut être :

```text
MisfirePolicy
│
├── Skip
├── RunNow
├── CatchUp
└── CoalesceLatest
```

---

# 58. Mais modèle interne plus riche

À terme :

```text
MisfirePolicy
│
├── Detection threshold
│
└── Recovery strategy
```

peut être plus propre.

---

# 59. Séparer détection et réaction

Deux concepts :

```text
MisfireDetectionPolicy
```

et :

```text
MisfireRecoveryPolicy
```

pourraient être distingués.

---

# 60. Exemple

```text
Detection:
grace_period = 5m

Recovery:
ReplayAll(max=10)
```

---

# 61. Pourquoi cette séparation est intéressante

La question :

```text
"est-ce un misfire ?"
```

est différente de :

```text
"que faire de ce misfire ?"
```

---

# 62. Cependant

Pour V1, un seul objet :

```text
MisfirePolicy
```

peut encapsuler les deux afin de garder le modèle simple.

---

# 63. Misfire evaluation input

Une évaluation peut recevoir :

```text
Occurrence
now
GracePeriod
MisfirePolicy
```

---

# 64. Misfire evaluation output

Elle peut produire :

```text
SchedulingDecision
```

avec :

```text
EXECUTE
SKIP
CATCH_UP
COALESCE
```

et une raison.

---

# 65. DecisionReason

Exemples :

```text
ON_TIME

WITHIN_GRACE_PERIOD

MISFIRE_SKIPPED

MISFIRE_RUN_NOW

MISFIRE_CATCH_UP

MISFIRE_COALESCED
```

---

# 66. Auditability

Une décision de misfire doit pouvoir expliquer :

```text
scheduled_at
now
lateness
grace_period
policy
decision
```

---

# 67. Exemple d'audit

```text
Schedule:
hourly-report

Occurrence:
10:00

Detected at:
10:17

Grace period:
5 minutes

Lateness:
17 minutes

Policy:
SKIP

Decision:
MISFIRE_SKIPPED
```

---

# 68. Scheduler downtime scenario

Considérons :

```text
Schedule:
every 15 minutes

Last processed occurrence:
10:00

Scheduler restarts:
11:02
```

Le Trigger peut reconstruire :

```text
10:15
10:30
10:45
11:00
11:15
```

---

# 69. Occurrences passées

À :

```text
11:02
```

sont passées :

```text
10:15
10:30
10:45
11:00
```

La suivante :

```text
11:15
```

est future.

---

# 70. Recovery planner

Un composant peut donc calculer :

```text
missed_occurrences
+
next_future_occurrence
```

---

# 71. RecoveryPlan

Une abstraction possible :

```text
RecoveryPlan
│
├── missed_occurrences
├── selected_occurrences
├── skipped_occurrences
├── coalesced_groups
└── next_run_time
```

---

# 72. Classification

```text
RecoveryPlan
=
Value Object
```

ou résultat de `CatchUpPlanner`.

---

# 73. CatchUpPlanner

Un :

```text
CatchUpPlanner
```

peut être un :

```text
Domain Service
```

responsable de combiner :

```text
Trigger
last_checkpoint
now
ScheduleWindow
Calendar
MisfirePolicy
```

---

# 74. Pourquoi un Domain Service

Parce que cette logique combine plusieurs objets :

```text
Trigger
Schedule
Occurrence
Policies
Time
```

sans appartenir naturellement à une seule Entity.

---

# 75. OccurrencePlanner versus CatchUpPlanner

```text
OccurrencePlanner
→ prochaine occurrence valide

CatchUpPlanner
→ ensemble des occurrences historiques
à traiter après interruption
```

---

# 76. Exemple architectural

```text
Trigger
   │
   ▼
OccurrencePlanner
   │
   ├── next future occurrence
   │
   └── candidate sequence
           │
           ▼
     CatchUpPlanner
           │
           ▼
      RecoveryPlan
```

---

# 77. Recovery checkpoint

Pour savoir quelles occurrences sont manquées, il faut une référence historique.

Possibilités :

```text
last_processed_occurrence

last_evaluated_at

next_run_time

scheduler checkpoint
```

---

# 78. LastProcessedOccurrence

Une stratégie robuste consiste à connaître :

```text
le dernier scheduled_at réellement traité
```

---

# 79. Exemple

```text
last_processed = 08:00

trigger = hourly

now = 11:37
```

On reconstruit :

```text
09:00
10:00
11:00
12:00
```

Puis :

```text
09:00
10:00
11:00
```

sont historiques.

---

# 80. next_run_time comme checkpoint

Si `next_run_time` persisté vaut :

```text
09:00
```

et que :

```text
now = 11:37
```

on peut également repartir de :

```text
09:00
```

et dérouler jusqu'à maintenant.

---

# 81. Attention aux crashs

Supposons :

```text
Occurrence 09:00
materialized
```

mais le process crash avant d'avancer le checkpoint.

Au restart, il pourrait rematérialiser :

```text
09:00
```

---

# 82. Déduplication indispensable

Il faut donc une clé stable :

```text
OccurrenceKey
=
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

pour rendre la matérialisation idempotente.

---

# 83. Unique constraint

Conceptuellement :

```text
UNIQUE(
  schedule_id,
  revision,
  scheduled_at
)
```

permet d'éviter le double traitement de la même occurrence logique.

---

# 84. At-least-once reality

Dans un système distribué, il est souvent plus réaliste de viser :

```text
at-least-once scheduling intent
+
deduplication
```

que de promettre :

```text
exactly once execution
```

---

# 85. Misfire et delivery semantics

Une occurrence peut être :

```text
planned
materialized once
dispatched twice
executed once or twice
```

selon les pannes.

Le Misfire model ne doit donc pas être présenté comme une garantie globale d'exactly-once.

---

# 86. Catch-Up et idempotence

Le catch-up augmente le besoin d'idempotence.

Exemple :

```text
daily partition processing
```

si :

```text
Oct 1
Oct 2
Oct 3
```

sont rejoués, le Target doit pouvoir distinguer les partitions.

---

# 87. ExecutionContext

Une ExecutionRequest de catch-up devrait transporter :

```text
scheduled_at
OccurrenceKey
correlation_id
recovery_reason
```

---

# 88. Possible RecoveryMetadata

```text
RecoveryMetadata
│
├── is_catch_up
├── detected_at
├── lateness
├── batch_id?
└── policy
```

peut enrichir l'observabilité.

---

# 89. Mais attention à ne pas contaminer le domaine

Toutes ces données ne doivent pas nécessairement être des propriétés permanentes de `Execution`.

Certaines peuvent rester :

```text
metadata
events
diagnostics
```

---

# 90. Misfire d'un DateTrigger

Cas :

```text
DateTrigger at 08:00

scheduler starts at 10:00
```

La policy peut :

```text
SKIP
```

ou :

```text
RUN_NOW
```

Catch-up multi-occurrence n'a pas de sens car il n'y a qu'une seule occurrence.

---

# 91. Misfire d'un IntervalTrigger

Exemple :

```text
every 5 minutes
```

scheduler indisponible pendant une heure.

Il peut y avoir de nombreuses occurrences manquées.

C'est un cas classique pour :

```text
CatchUpLimit
Coalescing
```

---

# 92. Misfire d'un CronTrigger

Exemple :

```text
every day at 06:00
```

scheduler arrêté pendant trois jours.

Occurrences manquées :

```text
Monday 06:00
Tuesday 06:00
Wednesday 06:00
```

---

# 93. Catch-Up et Timezone

Le Trigger reconstruit correctement les occurrences selon :

```text
Timezone
DST rules
ScheduleRevision
```

Le catch-up ne doit pas approximer :

```text
3 days = 72 hours
```

pour un CronTrigger.

---

# 94. Catch-Up et ScheduleRevision

Supposons :

```text
revision 1
hourly until 10:30

revision 2
every 30 minutes after 10:30
```

Le recovery devient plus complexe.

---

# 95. Principe

Une occurrence historique doit être calculée selon :

```text
la ScheduleRevision
qui était active à cette date
```

si le système conserve un historique de définitions.

---

# 96. V1 simplification

Pour V1, on peut définir :

> Le catch-up ne couvre que la révision courante depuis son activation ou dernier checkpoint.

Les cas multi-révisions peuvent être différés.

---

# 97. Mais l'architecture doit laisser la porte ouverte

Conserver :

```text
ScheduleRevision
```

dans `OccurrenceKey` reste donc essentiel.

---

# 98. Pause et Misfire

Supposons :

```text
Schedule paused:
08:00 → 12:00
```

Les occurrences pendant cette période sont-elles :

```text
misfires
```

?

Pas nécessairement.

---

# 99. Pause semantics

Deux politiques possibles :

```text
PAUSE_SUPPRESSES_OCCURRENCES
```

ou :

```text
PAUSE_CREATES_MISSED_OCCURRENCES
```

---

# 100. Recommandation

En V1 :

```text
PAUSE_SUPPRESSES_OCCURRENCES
```

est plus simple.

Cela signifie :

```text
les occurrences ne sont pas dues
pendant l'état PAUSED
```

donc elles ne sont pas des misfires.

---

# 101. Resume

Lors de `resume()` :

```text
next occurrence
```

est recalculée à partir du contexte de reprise.

Pas de replay automatique de la période de pause.

---

# 102. Variante future

Une :

```text
ResumeCatchUpPolicy
```

pourrait permettre explicitement de rejouer la période de pause.

---

# 103. Cancelled Schedule

Un Schedule `CANCELLED` ne crée jamais de catch-up futur.

Toutes les occurrences non matérialisées restantes sont abandonnées.

---

# 104. Completed Schedule

Même logique :

```text
COMPLETED
```

ne produit pas de nouvelle recovery.

---

# 105. ScheduleWindow et catch-up

Une occurrence historique hors de la fenêtre du Schedule ne doit pas être rejouée.

---

# 106. Exemple

```text
ScheduleWindow:
Oct 1 → Oct 3

now:
Oct 10
```

Même si le Trigger pourrait générer :

```text
Oct 4
Oct 5
...
```

elles ne font pas partie du Schedule.

---

# 107. Calendar et catch-up

Le `BusinessCalendar` doit être appliqué lors de la reconstruction.

Exemple :

```text
daily trigger
weekdays only
```

Le week-end ne doit pas devenir du catch-up si aucune occurrence valide n'existait.

---

# 108. Trigger candidates versus missed occurrences

```text
Trigger candidate
```

n'est un `MissedOccurrence` que s'il passe :

```text
Calendar
ScheduleWindow
Schedule lifecycle
```

---

# 109. Pipeline correct

```text
Trigger
   ↓
Candidate
   ↓
Calendar
   ↓
ScheduleWindow
   ↓
Valid historical Occurrence
   ↓
Misfire classification
```

---

# 110. Pas l'inverse

Éviter :

```text
Trigger candidates
→ catch-up all
→ calendar filter later
```

si cela crée des requêtes pour des échéances qui n'ont jamais été valides.

---

# 111. GracePeriod et catch-up

Chaque occurrence possède conceptuellement sa propre deadline :

```text
deadline
=
scheduled_at + grace_period
```

---

# 112. Exemple

```text
09:00 occurrence
grace = 10m

now = 09:08
```

Elle n'est pas nécessairement un misfire.

---

# 113. Multiple occurrences, mixed states

Avec un intervalle de 5 minutes :

```text
09:00
09:05
09:10
09:15
```

à :

```text
09:17
```

et grace :

```text
10 minutes
```

on peut avoir :

```text
09:00 → misfired
09:05 → misfired
09:10 → within grace
09:15 → within grace
```

selon la convention de frontière.

---

# 114. Policy may apply individually

Chaque occurrence doit être classifiée individuellement avant la consolidation.

---

# 115. Coalescing candidates

Le coalescing peut ensuite prendre uniquement :

```text
les occurrences sélectionnées pour recovery
```

---

# 116. Coalescing et GracePeriod

Il faut éviter qu'une occurrence encore normalement admissible soit fusionnée arbitrairement avec des misfires anciens si la policy ne le prévoit pas.

---

# 117. Recommended processing order

```text
1. Reconstruct valid occurrences

2. Classify lateness/misfire

3. Apply recovery policy

4. Apply coalescing

5. Apply concurrency policy

6. Create ExecutionRequest(s)
```

---

# 118. Concurrency vient après

Supposons catch-up :

```text
09:00
10:00
11:00
```

et :

```text
ConcurrencyPolicy = FORBID_OVERLAP
```

On ne peut pas nécessairement lancer les trois simultanément.

---

# 119. Catch-Up ≠ parallel execution

Le catch-up dit :

```text
quelles occurrences doivent être récupérées
```

La concurrence dit :

```text
combien peuvent être actives simultanément
```

---

# 120. Séparation essentielle

```text
CatchUpPolicy
≠
ConcurrencyPolicy
```

---

# 121. Exemple séquentiel

RecoveryPlan :

```text
09:00
10:00
11:00
```

Concurrency :

```text
max_instances = 1
```

Le scheduler peut :

```text
queue 3 requests
```

tout en n'exécutant :

```text
qu'une à la fois
```

---

# 122. Coalescing avant concurrence

Si :

```text
09:00
10:00
11:00
```

sont coalescées en :

```text
1 request
```

la concurrence s'applique ensuite à cette request.

---

# 123. Jitter et misfire

Le `JitterPolicy` ne doit pas transformer artificiellement une occurrence en misfire.

Il faut distinguer :

```text
scheduled_at
```

et :

```text
dispatch_not_before
```

---

# 124. Exemple

```text
scheduled_at = 10:00
jitter       = +30s
dispatch_not_before = 10:00:30
```

À :

```text
10:00:20
```

l'occurrence n'est pas en retard.

---

# 125. Deadline liée au scheduled_at

La deadline peut rester :

```text
scheduled_at + grace
```

ou éventuellement tenir compte du jitter selon le contrat.

Ce choix devra être explicitement spécifié.

---

# 126. Recommandation

Conserver :

```text
scheduled_at
```

comme base de la GracePeriod.

Le jitter est une variation volontaire du dispatch.

Il ne modifie pas l'intention temporelle.

---

# 127. Retry et catch-up

Supposons une occurrence catch-up :

```text
09:00
```

est exécutée à :

```text
12:00
```

puis échoue.

Ses retries restent attachés à :

```text
Occurrence 09:00
```

---

# 128. Ils ne deviennent pas de nouvelles occurrences

```text
09:00 occurrence
   └── Execution
         ├── Attempt 1
         ├── Attempt 2
         └── Attempt 3
```

---

# 129. Catch-up et latest state jobs

Certains jobs sont naturellement :

```text
state reconciliation
```

Exemple :

```text
refresh cache
```

Rejouer :

```text
09:00
10:00
11:00
```

n'a peut-être aucun intérêt.

---

# 130. Dans ce cas

Une policy :

```text
COALESCE_LATEST
```

est probablement meilleure.

---

# 131. Catch-up et incremental jobs

À l'inverse, pour :

```text
process daily partition
```

chaque occurrence peut être essentielle.

```text
Oct 1
Oct 2
Oct 3
```

doivent toutes être traitées.

---

# 132. Dans ce cas

```text
ReplayAll
```

est probablement la bonne stratégie.

---

# 133. La policy dépend donc de la sémantique métier

PyScheduleKit ne peut pas choisir universellement entre :

```text
SKIP
RUN_NOW
REPLAY_ALL
COALESCE
```

Le framework doit rendre ce choix explicite.

---

# 134. Policy defaults

Un default trop agressif est dangereux.

Par exemple :

```text
ReplayAll
```

par défaut peut créer une tempête d'exécutions après une longue panne.

---

# 135. Recommandation V1

Le default devrait être conservateur.

Par exemple :

```text
SKIP
```

ou une policy explicitement configurée.

L'important est de ne pas cacher un catch-up massif.

---

# 136. Safety limits

Même avec :

```text
ReplayAll
```

le runtime devrait imposer des garde-fous.

Exemples :

```text
max_catch_up_occurrences

max_catch_up_age

max_recovery_batch_size
```

---

# 137. Hard limit versus policy limit

Il faut distinguer :

```text
business limit
```

de :

```text
runtime safety limit
```

---

# 138. Exemple

Policy :

```text
max_occurrences = 1000
```

Runtime hard limit :

```text
10000
```

Le second protège le système contre une mauvaise configuration.

---

# 139. Catch-up pagination

Pour un très grand backlog, on peut générer les occurrences par pages :

```text
batch 1
batch 2
batch 3
```

plutôt que charger tout en mémoire.

---

# 140. Mais V1 peut rester simple

Une limite raisonnable suffit pour commencer.

---

# 141. Recovery burst

Après restart, plusieurs schedules peuvent tous avoir du backlog.

Exemple :

```text
100 schedules
×
100 missed occurrences
=
10 000 requests
```

---

# 142. Recovery throttling

Le runtime peut donc nécessiter :

```text
recovery throttling
```

mais cette logique appartient davantage au scheduler runtime qu'à la MisfirePolicy pure.

---

# 143. Domain versus runtime

```text
Domain
→ quelles occurrences doivent être récupérées ?

Runtime
→ à quelle vitesse les soumettre ?
```

---

# 144. Backpressure

Si le queue/executor est saturé, le scheduler peut retarder le dispatch.

Cela ne doit pas recalculer les occurrences.

---

# 145. Recovery queue

Une architecture avancée peut différencier :

```text
normal scheduling queue
```

et :

```text
catch-up queue
```

pour limiter l'impact sur le trafic courant.

---

# 146. Priorité

Une occurrence normale récente peut être prioritaire par rapport à un backlog historique.

Ou l'inverse selon le métier.

C'est une policy/runtime concern distincte.

---

# 147. Catch-up et ordering global

Avec plusieurs schedules, il peut être impossible de préserver un ordre temporel global strict.

Ce n'est généralement pas nécessaire.

L'ordre doit surtout être défini :

```text
par Schedule
```

ou par `ConcurrencyKey`.

---

# 148. Schedule-local ordering

Par défaut :

```text
Occurrence A at 09:00
before
Occurrence B at 10:00
```

pour le même Schedule lors d'un replay séquentiel.

---

# 149. Coalescing et audit

Même si plusieurs occurrences donnent une seule request, l'audit devrait pouvoir répondre :

```text
quelles occurrences ont été absorbées ?
```

---

# 150. Example audit event

```text
OccurrencesCoalesced
│
├── schedule_id
├── occurrence_keys
├── selected_primary
├── policy
└── occurred_at
```

---

# 151. Domain events possibles

```text
OccurrenceMisfired

OccurrenceSkipped

CatchUpPlanned

OccurrencesCoalesced

RecoveryExecutionRequested
```

---

# 152. Faut-il créer un event pour chaque occurrence ?

Pas nécessairement.

Pour un backlog massif :

```text
10000 skipped occurrences
```

un event agrégé peut être préférable.

---

# 153. Aggregate event

Exemple :

```text
MisfireBatchProcessed
count = 10000
from = ...
to = ...
policy = SKIP
```

---

# 154. Observabilité

Les métriques utiles incluent :

```text
misfire_count

misfire_lateness_seconds

catchup_occurrences_planned

catchup_occurrences_skipped

coalesced_occurrences_count

recovery_batch_size

recovery_duration
```

---

# 155. Metric cardinality

Éviter de mettre :

```text
schedule_id
```

comme label de métrique non contrôlé si le nombre de schedules est très grand.

Préférer :

```text
logs/traces
```

pour les identifiants fins.

---

# 156. Scheduling lag

Un misfire peut être vu comme un lag important.

```text
scheduling_lag
=
detected_at - scheduled_at
```

---

# 157. Mais threshold métier

Le passage de :

```text
late
```

à :

```text
misfire
```

dépend de la GracePeriod.

---

# 158. Exemple de timeline

```text
08:00                08:05                  08:30
  │--------------------│----------------------│
  │                    │                      │
scheduled            deadline                detected
  │                    │                      │
  └── eligible ────────┘                      │
                                              ▼
                                           MISFIRE
```

---

# 159. MisfireDecision

On peut représenter :

```text
MisfireDecision
│
├── occurrence
├── classification
├── action
├── lateness
└── reason
```

Classification :

```text
Value Object
```

---

# 160. RecoveryAction

Enum possible :

```text
SKIP

EXECUTE_NOW

REPLAY

COALESCE
```

---

# 161. Mais éviter deux taxonomies concurrentes

Si `SchedulingDecision` existe déjà, `MisfireDecision` peut rester un sous-résultat interne.

---

# 162. Cohérence recommandée

```text
MisfirePolicy
      │
      ▼
SchedulingDecision
```

avec un :

```text
DecisionReason
```

suffisamment riche.

---

# 163. API conceptuelle

Sans figer l'implémentation :

```python
decision = misfire_policy.evaluate(
    occurrence=occurrence,
    now=now,
    grace_period=grace_period,
)
```

---

# 164. Catch-up API conceptuelle

```python
plan = catch_up_planner.plan(
    schedule=schedule,
    after=last_checkpoint,
    until=now,
)
```

---

# 165. Coalescing API conceptuelle

```python
grouped = coalescing_policy.coalesce(occurrences)
```

---

# 166. Purity

Ces calculs doivent idéalement rester :

```text
déterministes
sans effet de bord
```

pour les mêmes inputs.

---

# 167. Catch-up planner must not dispatch

Il ne doit pas :

```text
call executor
publish network message
commit transaction
```

Il produit uniquement un plan.

---

# 168. Application service

Le flow applicatif devient :

```text
load Schedule
load checkpoint
build RecoveryPlan
persist occurrences/requests
advance checkpoint
commit
dispatch asynchronously
```

selon l'architecture retenue.

---

# 169. Atomicité

Un point important apparaît :

```text
materialize occurrence
+
create ExecutionRequest
+
advance checkpoint
```

devra éventuellement être atomique.

---

# 170. Pourquoi ?

Sinon un crash entre les étapes peut provoquer :

```text
lost occurrence
```

ou :

```text
duplicate occurrence
```

---

# 171. Exemple dangereux

```text
1. advance checkpoint to 10:00
2. crash
3. request 10:00 never created
```

Occurrence perdue.

---

# 172. Autre ordre dangereux

```text
1. create request 10:00
2. crash
3. checkpoint still 09:00
```

Au restart :

```text
10:00
```

peut être recréée.

---

# 173. Solution

Une combinaison de :

```text
transaction locale
+
unique OccurrenceKey
+
outbox éventuellement
```

peut rendre le processus robuste.

---

# 174. Mais cela appartient à l'architecture persistence/runtime

Le modèle métier fournit surtout :

```text
OccurrenceKey
RecoveryPlan
idempotent intent
```

---

# 175. Distributed scheduler

Avec plusieurs nodes :

```text
Node A
Node B
```

peuvent détecter le même backlog.

---

# 176. Lease

Une `Lease` ou autre mécanisme d'ownership doit empêcher ou rendre idempotente la double matérialisation.

---

# 177. Le MisfirePolicy n'est pas responsable de la coordination

Encore une séparation :

```text
MisfirePolicy
→ what should happen

Lease / persistence
→ who may perform it
```

---

# 178. Coalescing et distributed race

Deux nodes ne doivent pas produire deux groupes différents pour les mêmes occurrences.

La coordination doit donc se faire avant ou pendant la matérialisation transactionnelle.

---

# 179. Recovery snapshot

Un contexte de récupération peut capturer :

```text
now
ScheduleRevision
calendar version
last checkpoint
```

pour garantir une décision cohérente.

---

# 180. Same-now principle

Comme ailleurs dans PyScheduleKit :

```text
toute la recovery evaluation
```

doit utiliser le même :

```text
now
```

capturé au début.

---

# 181. Pourquoi ?

Éviter qu'une occurrence change de classification en plein calcul parce que quelques millisecondes passent.

---

# 182. Example

```text
evaluation_now = 12:00:00
```

Toutes les occurrences du batch sont évaluées contre cette valeur.

---

# 183. Schedule rescheduled during recovery

Si le Schedule change pendant le calcul :

```text
revision 4
→ revision 5
```

le plan fondé sur revision 4 peut devenir obsolète.

---

# 184. Optimistic concurrency

Le commit peut vérifier :

```text
ScheduleRevision still == 4
```

avant de matérialiser le plan.

---

# 185. Sinon

```text
RecoveryPlanStale
```

et recalcul.

---

# 186. Policy immutability

Une MisfirePolicy doit être :

```text
Value Object / Policy
immutable
```

comme le reste de `ScheduleDefinition`.

---

# 187. Rescheduling a policy

Modifier :

```text
SKIP
```

en :

```text
ReplayAll
```

est un changement de définition.

Donc :

```text
ScheduleRevision += 1
```

---

# 188. Historical semantics

Les occurrences historiques devraient idéalement conserver :

```text
la policy effective
```

via `ScheduleRevision`.

---

# 189. MisfirePolicy serialization

Exemple :

```json
{
  "kind": "skip"
}
```

---

# 190. RunNow serialization

```json
{
  "kind": "run_now"
}
```

---

# 191. CatchUp serialization

```json
{
  "kind": "catch_up",
  "max_occurrences": 100,
  "lookback_seconds": 86400
}
```

---

# 192. Coalescing serialization

```json
{
  "kind": "coalesce",
  "strategy": "latest",
  "max_occurrences": 1000
}
```

---

# 193. Configuration validation

Refuser :

```text
max_occurrences <= 0
```

si la policy exige une limite positive.

---

# 194. Lookback validation

Refuser :

```text
negative lookback
```

---

# 195. Unsupported strategy

Une stratégie inconnue doit produire :

```text
UnsupportedCoalescingStrategy
```

---

# 196. Error model

Erreurs possibles :

```text
InvalidMisfirePolicy

InvalidCatchUpLimit

CatchUpSearchLimitExceeded

RecoveryPlanStale

InvalidCoalescingConfiguration
```

---

# 197. CatchUpSearchLimitExceeded

Cette erreur est importante lorsqu'un Trigger génère trop d'occurrences avant la limite technique.

---

# 198. Policy versus hard failure

Une limite business peut conduire à :

```text
truncate/coalesce
```

Une limite technique dépassée peut conduire à :

```text
error
```

pour éviter une décision silencieuse incorrecte.

---

# 199. Example — SKIP

Schedule :

```text
every hour
```

Downtime :

```text
09:00 → 12:20
```

Missed :

```text
10:00
11:00
12:00
```

Policy :

```text
SKIP
```

Résultat :

```text
10:00 → skipped
11:00 → skipped
12:00 → skipped

next future:
13:00
```

---

# 200. Example — RUN_NOW

Même contexte.

Policy :

```text
RUN_NOW
```

Question :

faut-il produire :

```text
3 executions immédiates
```

ou :

```text
1 seule
```

?

---

# 201. Ambiguïté importante

`RUN_NOW` appliqué à plusieurs missed occurrences doit être défini.

Deux variantes :

```text
RUN_EACH_NOW
```

ou :

```text
RUN_LATEST_NOW
```

---

# 202. Recommandation

Éviter un `RUN_NOW` ambigu.

Pour une seule occurrence :

```text
RUN_NOW
```

Pour plusieurs :

```text
CatchUpPolicy
```

doit décider explicitement.

---

# 203. Taxonomie améliorée

Ainsi :

```text
SingleMisfireAction
│
├── SKIP
└── EXECUTE_NOW
```

et :

```text
MultipleMisfireRecovery
│
├── REPLAY_ALL
├── REPLAY_LIMITED
├── COALESCE_LATEST
└── SKIP_ALL
```

---

# 204. Mais API publique simple possible

L'API peut masquer cette sophistication derrière :

```text
MisfirePolicy
```

avec des implémentations spécialisées.

---

# 205. Example — ReplayAll

Missed :

```text
10:00
11:00
12:00
```

Output :

```text
Request 10:00
Request 11:00
Request 12:00
```

---

# 206. Example — CoalesceLatest

Missed :

```text
10:00
11:00
12:00
```

Output :

```text
Request representing 12:00
coalesced_from = [10:00,11:00,12:00]
```

---

# 207. Example — Range

Missed daily partitions :

```text
Oct 1
Oct 2
Oct 3
```

Output :

```text
Request
range_start = Oct 1
range_end   = Oct 3
```

---

# 208. Example — Limited catch-up

Missed :

```text
100 occurrences
```

Policy :

```text
max_occurrences = 10
KEEP_LATEST
```

Output :

```text
latest 10 occurrences
```

---

# 209. Truncation audit

Le système doit signaler :

```text
90 occurrences omitted
```

et ne pas les perdre silencieusement.

---

# 210. Backlog age

Une métrique utile :

```text
oldest_missed_occurrence_age
```

indique la profondeur temporelle du backlog.

---

# 211. Backlog count

```text
missed_occurrence_count
```

permet d'estimer :

```text
recovery pressure
```

---

# 212. Recovery dry-run

Une API très utile pédagogiquement et opérationnellement :

```text
plan catch-up without executing
```

pour afficher :

```text
occurrences found
ones selected
ones skipped
coalescing result
```

---

# 213. Exemple de preview

```text
Missed: 125
Within lookback: 48
Policy limit: 20
Selected: latest 20
Coalesced into: 1 request
```

---

# 214. Explainability

Une recovery doit pouvoir être expliquée comme :

```text
Pourquoi cette occurrence est-elle rejouée ?

Pourquoi celle-ci a-t-elle été ignorée ?

Pourquoi trois occurrences sont-elles devenues une seule request ?
```

---

# 215. RecoveryReason

Value Object ou enum possible :

```text
SCHEDULER_DOWNTIME

PROCESS_RESTART

MANUAL_CATCH_UP

LEASE_DELAY

QUEUE_BACKLOG
```

---

# 216. Attention

Le scheduler ne connaît pas toujours la cause exacte.

Il peut utiliser :

```text
MISFIRE_DETECTED
```

plutôt que d'inventer une raison.

---

# 217. Manual backfill versus automatic catch-up

Ils se ressemblent mais sont différents.

```text
Automatic Catch-Up
```

répare une interruption opérationnelle.

```text
Manual Backfill
```

demande explicitement de rejouer une période historique.

---

# 218. Backfill

Exemple :

```text
reprocess Oct 1 → Oct 31
```

même si ces occurrences avaient déjà été traitées.

---

# 219. Catch-up

Exemple :

```text
process Oct 4 → Oct 6
because scheduler was down
```

et uniquement si elles n'ont pas été matérialisées.

---

# 220. Distinction fondamentale

```text
Catch-Up
≠
Backfill
```

Même si tous deux utilisent le Trigger pour reconstruire des occurrences.

---

# 221. Backfill should be separate command

Par exemple :

```text
CreateBackfill
```

avec ses propres règles de déduplication.

---

# 222. Catch-up is automatic recovery

Il est lié à :

```text
scheduler continuity
```

et non à un besoin fonctionnel de retraitement volontaire.

---

# 223. Replay already processed occurrence

Le catch-up automatique ne doit normalement pas recréer une occurrence déjà matérialisée.

Un backfill explicite peut le faire selon contrat.

---

# 224. Deduplication therefore differs

Catch-up :

```text
deduplicate strongly
```

Backfill :

```text
may intentionally create new execution
for same historical scheduled_at
```

---

# 225. Backfill identity

Un futur modèle peut utiliser :

```text
BackfillId
```

pour distinguer plusieurs retraitements d'une même occurrence.

---

# 226. Hors scope actuel

Ce document ne définit pas encore le Backfill complet.

Il clarifie uniquement la frontière.

---

# 227. Misfire and one-shot completion

Pour un DateTrigger avec policy `SKIP` :

```text
occurrence skipped
```

puis :

```text
Trigger exhausted
```

Le Schedule devient :

```text
COMPLETED
```

---

# 228. DateTrigger + RUN_NOW

Après execution request :

```text
Trigger exhausted
```

Le Schedule peut également devenir `COMPLETED`.

---

# 229. Cron and next_run_time after catch-up

Après recovery :

```text
next_run_time
```

doit pointer vers :

```text
la première occurrence future valide
```

et non vers une occurrence historique encore présente dans le backlog traité.

---

# 230. Interval and next_run_time

Même logique.

Exemple :

```text
now = 12:17
```

après replay de :

```text
10:00
11:00
12:00
```

la prochaine peut être :

```text
13:00
```

---

# 231. Transaction boundary

La progression du :

```text
next_run_time
```

doit rester cohérente avec les requests matérialisées.

---

# 232. Catch-up checkpoint versus next_run_time

Ces deux valeurs peuvent être distinctes.

```text
last_processed_occurrence
```

historique.

```text
next_run_time
```

future.

---

# 233. Recommended conceptual state

```text
Schedule Operational State
│
├── last_materialized_occurrence?
└── next_run_time?
```

sans nécessairement faire de ces champs des propriétés métier centrales.

---

# 234. Avoid storing full backlog in Schedule

Ne pas faire :

```text
Schedule.missed_occurrences = [...]
```

Le backlog peut être massif.

---

# 235. Compute or query separately

Les occurrences matérialisées ou historiques appartiennent :

```text
à un store séparé
```

ou sont reconstruites via le Trigger.

---

# 236. Misfire policy belongs to ScheduleDefinition

Deux Schedules du même Target peuvent avoir :

```text
des policies différentes
```

---

# 237. Exemple

Schedule A :

```text
daily report
policy = SKIP
```

Schedule B :

```text
daily accounting close
policy = REPLAY_ALL
```

Même heure, criticité différente.

---

# 238. Default policy is part of public contract

Changer le default entre versions peut modifier radicalement le comportement.

Il faut donc :

```text
documenter
versionner
tester
```

ce default.

---

# 239. Recommended V1 default

Une option prudente :

```text
SkipMisfirePolicy
```

avec :

```text
explicit GracePeriod
```

évite une tempête de recovery surprise.

---

# 240. Alternative

On pourrait exiger que la MisfirePolicy soit toujours explicite.

C'est plus strict mais plus verbeux.

---

# 241. Pédagogiquement

Exiger une policy explicite est très intéressant pour comprendre le domaine.

Pour une API ergonomique publique, un default pourra être ajouté ensuite.

---

# 242. Determinism

Pour :

```text
same missed occurrences
same now
same policy
same limits
```

le :

```text
RecoveryPlan
```

doit être identique.

---

# 243. No randomness

Le coalescing ne doit pas choisir arbitrairement un sous-ensemble.

---

# 244. Stable ordering

Les occurrences doivent être triées selon :

```text
scheduled_at
```

avant application de la policy.

---

# 245. Occurrence equality

Une occurrence historique est identifiée par :

```text
OccurrenceKey
```

pas seulement par son timestamp si plusieurs schedules ou revisions existent.

---

# 246. Calendar version issue

Si un BusinessCalendar a changé depuis les occurrences historiques, un catch-up exact peut nécessiter :

```text
CalendarRevision
```

ou snapshot.

---

# 247. V1 simplification

Utiliser :

```text
current calendar
```

peut suffire au début.

Mais il faut documenter que le replay historique parfait n'est alors pas garanti.

---

# 248. Same issue with timezone database changes

Rare mais conceptuellement similaire.

Une reproduction historique parfaite nécessite davantage d'evidence.

---

# 249. Domain purity versus forensic reproducibility

PyScheduleKit V1 doit privilégier :

```text
correct scheduling semantics
```

sans prétendre résoudre immédiatement toute la reproductibilité temporelle historique mondiale.

---

# 250. Tests — single misfire

```text
scheduled_at = 08:00
grace = 5m
now = 08:10
policy = SKIP
```

Résultat :

```text
SKIP
```

---

# 251. Test — within grace

```text
scheduled_at = 08:00
grace = 5m
now = 08:03
```

Résultat :

```text
eligible normally
```

---

# 252. Test — catch-up enumeration

Trigger :

```text
hourly
```

Last checkpoint :

```text
08:00
```

Now :

```text
11:30
```

Expected missed :

```text
09:00
10:00
11:00
```

---

# 253. Test — coalesce latest

Input :

```text
09:00
10:00
11:00
```

Expected selected:

```text
11:00
```

avec evidence des trois occurrences.

---

# 254. Test — max occurrences

Input count :

```text
100
```

Limit :

```text
10
```

Expected :

```text
10 selected
90 explicitly omitted/truncated
```

selon la policy.

---

# 255. Test — ScheduleWindow

Window :

```text
09:00 → 11:00
```

Candidates :

```text
08:00
09:00
10:00
11:00
12:00
```

Seulement les occurrences autorisées par la convention de frontière doivent entrer dans le recovery.

---

# 256. Test — Calendar

Calendar :

```text
weekdays
```

Recovery period contient :

```text
Friday
Saturday
Sunday
Monday
```

Le backlog valide doit contenir uniquement les jours autorisés.

---

# 257. Test — duplicate recovery

Exécuter deux fois le même planning de catch-up doit produire les mêmes `OccurrenceKey`.

La couche de persistance doit pouvoir éviter les doubles matérialisations.

---

# 258. Test — policy determinism

Même input :

```text
same policy
same now
```

→ même plan.

---

# 259. Test — boundary deadline

Définir explicitement :

```text
now == deadline
```

comme :

```text
still eligible
```

ou :

```text
misfired
```

et tester ce contrat.

---

# 260. Test — DateTrigger missed

Une seule occurrence doit être considérée.

Jamais plusieurs.

---

# 261. Test — Interval massive backlog

Vérifier :

```text
search limit
max occurrences
```

afin d'éviter une boucle ou allocation incontrôlée.

---

# 262. Test — DST catch-up

Pour CronTrigger :

```text
02:30 Europe/Paris
```

sur une période comprenant un changement d'heure.

Le recovery doit respecter la policy DST du Schedule.

---

# 263. Test — schedule revision

Une recovery planifiée avec revision X doit échouer ou être recalculée si le Schedule est passé à revision Y avant commit.

---

# 264. Anti-pattern — `now` devient `scheduled_at`

Ne jamais transformer une occurrence manquée :

```text
08:00
```

en :

```text
scheduled_at = 10:00
```

simplement parce qu'on l'exécute maintenant.

---

# 265. Anti-pattern — replay tout sans limite

Très dangereux.

Un simple :

```text
while candidate < now:
    create_request()
```

sans garde-fou peut faire tomber le scheduler.

---

# 266. Anti-pattern — catch-up dans Trigger

Le Trigger ne doit pas connaître :

```text
misfire policy
recovery limits
coalescing
```

---

# 267. Anti-pattern — coalescing invisible

Regrouper :

```text
100 occurrences
```

en une execution sans conserver aucune evidence détruit l'auditabilité.

---

# 268. Anti-pattern — Skip silencieux

Une occurrence ignorée à cause d'une policy devrait laisser :

```text
event
log
metric
```

approprié.

---

# 269. Anti-pattern — Pause = downtime

Une pause volontaire ne doit pas forcément être traitée comme une panne de scheduler.

---

# 270. Anti-pattern — catch-up = backfill

Ne pas utiliser le même concept pour :

```text
automatic recovery
```

et :

```text
manual historical reprocessing
```

---

# 271. Anti-pattern — coalescing target-aware dans le domaine

Le domaine scheduling ne doit pas contenir :

```text
if target == "sales":
    merge partitions this way
```

La traduction spécifique appartient aux adapters.

---

# 272. Anti-pattern — execution result influences historical occurrence selection

La présence d'un échec d'exécution ne doit pas transformer automatiquement l'occurrence en misfire.

Elle a déjà été matérialisée.

---

# 273. Anti-pattern — duplicate request as catch-up

Si une occurrence possède déjà une ExecutionRequest, le catch-up automatique ne doit pas en créer une seconde sans raison explicite.

---

# 274. Domain model proposé

```text
MissedOccurrence [VO]

MisfirePolicy [Policy]

CatchUpPolicy [Policy]

CoalescingPolicy [Policy]

OccurrenceGroup [VO]

RecoveryPlan [VO]

CatchUpPlanner [Domain Service]
```

---

# 275. Relations

```text
ScheduleDefinition
      │
      └── MisfirePolicy
               │
               ▼
        CatchUpPlanner
               │
      ┌────────┼─────────┐
      │        │         │
      ▼        ▼         ▼
   Trigger   Calendar   Window
      │
      ▼
Historical Occurrences
      │
      ▼
RecoveryPlan
      │
      ▼
ExecutionRequest(s)
```

---

# 276. Modèle de décision complet

```text
                 LAST CHECKPOINT
                       │
                       ▼
                    Trigger
                       │
                       ▼
              Historical Candidates
                       │
              ┌────────┴─────────┐
              ▼                  ▼
          Calendar          ScheduleWindow
              │                  │
              └────────┬─────────┘
                       ▼
              Valid Occurrences
                       │
                       ▼
                     now
                       │
                       ▼
             Misfire Classification
                       │
                       ▼
                 MisfirePolicy
                       │
             ┌─────────┼─────────┐
             │         │         │
             ▼         ▼         ▼
           SKIP     CATCH-UP   COALESCE
                       │
                       ▼
                  RecoveryPlan
                       │
                       ▼
             ExecutionRequest(s)
```

---

# 277. Relation avec Concurrency

Après :

```text
RecoveryPlan
```

le scheduler doit encore appliquer :

```text
ConcurrencyPolicy
```

avant ou pendant l'admission des requests.

---

# 278. Relation avec Retry

Une fois une Execution créée, ses éventuels retries ne concernent plus :

```text
MisfirePolicy
```

---

# 279. Relation avec Executor

L'Executor reçoit des requests déjà décidées.

Il ne doit pas recalculer :

```text
misfire
catch-up
coalescing
```

---

# 280. Relation avec PyWorkflowKit

PyWorkflowKit peut recevoir :

```text
scheduled_at
catch_up metadata
coalesced occurrence information
```

mais ne décide pas de la politique temporelle du Schedule.

---

# 281. Relation avec PyIngestKit

Un cas très pertinent :

```text
hourly ingestion
```

Après downtime :

```text
replay each ingestion window
```

ou :

```text
coalesce into a larger interval
```

peut être configuré.

La stratégie de découpage spécifique des données appartient cependant à PyIngestKit.

---

# 282. Relation avec PyTransformKit

Même principe pour :

```text
daily partitions
```

Le scheduling fournit les occurrences ou plages à traiter.

La transformation comprend la signification du dataset.

---

# 283. Recommended V1 model

Pour rester pédagogique mais réaliste :

```text
MisfirePolicy
│
├── SkipMisfire
├── ExecuteLatestNow
└── CatchUp
      ├── max_occurrences
      └── coalescing
```

avec :

```text
Coalescing
=
NONE
or
LATEST
```

pour commencer.

---

# 284. Pourquoi limiter V1

Des stratégies comme :

```text
RANGE
BATCH
custom merger
```

créent rapidement des dépendances avec la sémantique du Target.

Elles peuvent attendre.

---

# 285. V1 — SkipMisfire

Comportement :

```text
all misfired occurrences
→ skipped
```

---

# 286. V1 — ExecuteLatestNow

Comportement :

```text
select latest missed occurrence
→ one ExecutionRequest now
```

tout en conservant son :

```text
scheduled_at original
```

---

# 287. V1 — CatchUp

Comportement :

```text
replay selected missed occurrences
oldest first
```

avec :

```text
max_occurrences
```

obligatoire ou default strict.

---

# 288. V1 — CoalesceLatest

Comme option du CatchUp :

```text
many missed
→ latest only
```

---

# 289. State model

Une occurrence matérialisée peut éventuellement avoir :

```text
PLANNED
DUE
MISSED
SKIPPED
REQUESTED
COALESCED
```

Mais il faut éviter une machine d'états trop détaillée avant besoin.

---

# 290. Alternative

Conserver les états simples et exprimer les décisions via :

```text
events
```

peut être plus propre.

---

# 291. Exemple

Occurrence :

```text
scheduled_at = 09:00
```

Event :

```text
OccurrenceSkipped(
  reason=MISFIRE_POLICY
)
```

Pas nécessaire d'ajouter :

```text
state=SKIPPED_MISFIRE_EXPIRED
```

---

# 292. Domain events recommended

```text
OccurrenceSkipped

CatchUpRequested

OccurrencesCoalesced

RecoveryPlanCreated
```

en gardant le nombre d'events raisonnable.

---

# 293. Public API future

Exemple possible :

```python
Schedule(
    ...,
    misfire_policy=SkipMisfires(),
)
```

---

# 294. Catch-up API

```python
Schedule(
    ...,
    misfire_policy=CatchUp(
        max_occurrences=24,
    ),
)
```

---

# 295. Coalescing API

```python
Schedule(
    ...,
    misfire_policy=CatchUp(
        max_occurrences=24,
        coalesce="latest",
    ),
)
```

---

# 296. API declarative

```yaml
misfire:
  strategy: catch_up
  max_occurrences: 24
  coalesce: latest
```

---

# 297. Dry-run API

```text
pyschedule inspect catch-up <schedule>
```

pourrait plus tard afficher :

```text
missed occurrences
selected occurrences
skipped occurrences
resulting requests
```

---

# 298. CLI future

Exemple :

```text
pyschedule schedule recovery-plan daily-orders
```

Ce n'est pas nécessaire au domaine, mais très utile opérationnellement.

---

# 299. Invariants principaux

```text
1.
scheduled_at d'une occurrence est immutable.

2.
Misfire ≠ ExecutionFailure.

3.
Misfire ≠ Retry.

4.
Catch-Up ne modifie pas le Trigger.

5.
Coalescing conserve l'evidence
des occurrences regroupées.

6.
Catch-Up est borné.

7.
Une occurrence déjà matérialisée
n'est pas recréée automatiquement.

8.
Les occurrences sont traitées
dans un ordre déterministe.

9.
Calendar et ScheduleWindow
sont appliqués avant le recovery.

10.
Concurrency est distincte du catch-up.

11.
Pause volontaire n'est pas forcément misfire.

12.
Catch-Up ≠ Manual Backfill.
```

---

# 300. Critères d'acceptation

Le modèle est suffisamment défini si l'on peut répondre clairement à :

```text
Qu'est-ce qu'un misfire ?

Quand une occurrence devient-elle réellement misfired ?

Quelle différence entre lateness et misfire ?

Qu'est-ce que SKIP ?

Qu'est-ce que RUN_NOW ?

Qu'est-ce que CATCH_UP ?

Qu'est-ce que COALESCE ?

Comment éviter un catch-up massif ?

Comment représenter plusieurs occurrences coalescées ?

Comment le scheduler reprend-il après une panne ?

Pourquoi scheduled_at ne change pas ?

Comment dédupliquer les occurrences ?

Quelle différence entre catch-up et retry ?

Quelle différence entre catch-up et backfill ?

Comment concurrency interagit-elle avec recovery ?
```

---

# 301. Décisions proposées pour PyScheduleKit V1

```text
1.
Une occurrence est évaluée contre un `now`
capturé une fois.

2.
GracePeriod détermine sa fenêtre normale.

3.
Après Deadline, elle peut devenir MISFIRED.

4.
MisfirePolicy appartient à ScheduleDefinition.

5.
V1 supporte au minimum :
SKIP
EXECUTE_LATEST_NOW
CATCH_UP.

6.
Catch-Up travaille oldest-first par défaut.

7.
Catch-Up possède une limite explicite
de nombre d'occurrences.

8.
Coalescing V1 supporte :
NONE
LATEST.

9.
scheduled_at reste l'instant original.

10.
OccurrenceKey garantit une identité stable.

11.
Le recovery automatique ne rematérialise pas
une occurrence déjà connue.

12.
Pause supprime les occurrences pendant la pause
dans la sémantique V1.

13.
Manual Backfill reste un concept séparé.

14.
CatchUpPlanner est un Domain Service
qui produit un RecoveryPlan pur.

15.
Concurrency et Retry sont appliqués
dans des étapes séparées.
```

---

# 302. Modèle mental final

```text
                      TIME PASSES
                           │
                           ▼
                   Expected Occurrences
                           │
                           ▼
                    Scheduler absent
                           │
                           ▼
                  Missed Occurrences
                           │
                           ▼
                     MisfirePolicy
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
        SKIP            CATCH-UP         COALESCE
                           │                │
                           ▼                ▼
                    many requests       fewer requests
                           │                │
                           └────────┬───────┘
                                    ▼
                             Concurrency
                                    │
                                    ▼
                              Execution
```

---

# 303. Synthèse conceptuelle

```text
Trigger
→ Quelles occurrences étaient prévues ?

Calendar / Window
→ Lesquelles étaient réellement valides ?

Misfire Detection
→ Lesquelles sont trop tardives ?

MisfirePolicy
→ Lesquelles faut-il récupérer ?

Coalescing
→ Combien de requests faut-il produire ?

ConcurrencyPolicy
→ Combien peuvent être actives ?

Executor
→ Comment les lancer ?
```

---

# Conclusion

`Misfire`, `Catch-Up` et `Coalescing` ne sont pas des détails d'implémentation.

Ils définissent la manière dont un scheduler conserve sa **continuité temporelle** face aux interruptions.

La distinction essentielle est :

```text
Misfire
→ détecter un retard

Catch-Up
→ récupérer des occurrences

Coalescing
→ compresser plusieurs occurrences
```

Le modèle doit surtout éviter deux erreurs opposées :

```text
perdre silencieusement
des occurrences importantes
```

et :

```text
déclencher une tempête
de milliers d'executions
après un redémarrage
```

PyScheduleKit doit donc traiter le recovery comme une décision explicite, bornée, observable et déterministe.

Le cœur du modèle devient :

```text
Trigger
    ↓
Historical Occurrences
    ↓
Misfire Classification
    ↓
MisfirePolicy
    ↓
CatchUpPlanner
    ↓
RecoveryPlan
    ↓
Coalescing
    ↓
ExecutionRequest(s)
```

tout en préservant l'invariant le plus important :

> **Une occurrence reste l'occurrence de son instant d'origine, même lorsqu'elle est détectée, récupérée ou exécutée bien plus tard.**

---

# Suite documentaire

La suite logique est :

```text
14_CONCURRENCY_AND_OVERLAP_MODEL.md
```

Elle devra répondre à une autre question fondamentale :

> **Que faire lorsqu'une nouvelle occurrence devient exigible alors qu'une execution précédente est toujours active ?**

On y approfondira :

```text
Overlap

ConcurrencyKey

ALLOW

FORBID

QUEUE

REPLACE

MaxInstances

AdmissionDecision

ActiveExecutionSnapshot

cross-Schedule concurrency

distributed coordination
```

avant de traiter ensuite :

```text
15_RETRY_BACKOFF_AND_FAILURE_MODEL.md
```

pour séparer définitivement :

```text
récurrence temporelle
misfire recovery
concurrence
retry technique
```