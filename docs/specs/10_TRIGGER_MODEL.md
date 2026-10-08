# PyScheduleKit — Trigger Model

**Document :** `10_TRIGGER_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle métier de référence  
**Nature :** Domain Model — Trigger / Occurrence Generation  
**Prérequis :**
- `03_SCHEDULING_DOMAIN_VOCABULARY.md`
- `04_SCHEDULING_BUSINESS_OBJECTS.md`
- `05_SCHEDULING_ENTITIES_AND_VALUE_OBJECTS.md`
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`
- `09_JOB_AND_SCHEDULE_MODEL.md`

---

# 1. Objectif

Un `Schedule` exprime qu'un travail doit devenir exigible selon une règle temporelle.

Mais il faut encore répondre à :

> **Comment transformer cette règle temporelle en une suite d'occurrences concrètes ?**

Cette responsabilité appartient au :

```text
Trigger
```

Le Trigger est donc le composant qui transforme :

```text
Temporal Rule
+
Temporal Context
        ↓
Candidate Occurrence
```

Il constitue l'un des objets métier les plus importants de PyScheduleKit.

---

# 2. Responsabilité fondamentale

Le contrat conceptuel du Trigger est simple :

> **Calculer la prochaine occurrence temporelle valide selon sa propre règle.**

On peut l'exprimer comme :

```text
Trigger.next_after(reference)
        ↓
OccurrenceCandidate | None
```

`None` signifie :

```text
aucune occurrence future
```

et donc potentiellement :

```text
trigger exhausted
```

---

# 3. Ce qu'un Trigger n'est pas

Un Trigger n'est pas :

```text
un Scheduler

un Executor

une Queue

une Policy de misfire

une RetryPolicy

un Workflow

une Execution

une horloge
```

Il ne décide pas :

```text
"dois-je réellement exécuter maintenant ?"
```

Il calcule :

```text
"quelle est la prochaine échéance prévue ?"
```

---

# 4. Position dans le domaine

```text
Schedule
   │
   ▼
Trigger
   │
   ▼
Candidate Occurrence
   │
   ▼
Calendar / Window Validation
   │
   ▼
Occurrence
   │
   ▼
SchedulingEvaluator
   │
   ▼
SchedulingDecision
```

---

# 5. Trigger versus Schedule

Le `Schedule` possède :

```text
identité
lifecycle
target
policies
revision
```

Le `Trigger` possède :

```text
règle temporelle
algorithme de prochaine occurrence
```

Ainsi :

```text
Schedule
≠
Trigger
```

---

# 6. Trigger versus Occurrence

Le Trigger représente :

```text
la règle
```

L'Occurrence représente :

```text
un résultat concret de cette règle
```

Exemple :

```text
CronTrigger
0 6 * * *
```

peut produire :

```text
2026-10-05 06:00
2026-10-06 06:00
2026-10-07 06:00
```

---

# 7. Trigger comme Value Object comportemental

La classification recommandée reste :

```text
Trigger
=
Value Object
+
Strategy
```

Il est défini par :

```text
son type
sa configuration
ses paramètres temporels
```

Deux triggers de même type et même configuration peuvent être égaux par valeur.

---

# 8. Pas de TriggerId

Le cœur du domaine ne devrait normalement pas introduire :

```text
TriggerId
```

car le Trigger n'a pas d'identité métier indépendante.

Il appartient à la `ScheduleDefinition`.

---

# 9. Immutabilité

Un Trigger doit idéalement être immutable.

Modifier :

```text
CronTrigger("0 6 * * *")
```

en :

```text
CronTrigger("0 8 * * *")
```

ne devrait pas muter silencieusement le même objet.

Il s'agit d'un :

```text
new Trigger
```

et donc potentiellement d'une :

```text
new ScheduleRevision
```

---

# 10. Contrat minimal

Conceptuellement :

```python
class Trigger:
    def next_after(self, reference): ...
```

Mais le vrai contrat devra définir précisément :

```text
le type du reference
le caractère inclusif/exclusif
la timezone
l'exhaustion
les bornes
le déterminisme
```

---

# 11. Question fondamentale : `after` inclusif ou exclusif ?

Supposons :

```text
reference = 08:00
```

et une occurrence prévue exactement à :

```text
08:00
```

Que signifie :

```text
next_after(08:00)
```

?

Deux possibilités :

```text
08:00
```

ou :

```text
la prochaine après 08:00
```

---

# 12. Recommandation

Le contrat doit être strictement :

```text
next_after(reference)
→ prochaine occurrence STRICTEMENT > reference
```

Cela donne :

```text
next > reference
```

et évite les boucles infinies.

---

# 13. Besoin éventuel de `next_at_or_after`

Si l'on veut une sémantique inclusive :

```text
next_at_or_after(reference)
```

doit être une opération distincte.

Ne pas cacher cette différence.

---

# 14. Invariant de progression

Pour un trigger récurrent normal :

```text
next_occurrence > previous_occurrence
```

doit toujours être vrai.

Sinon :

```text
scheduler loop
```

peut devenir infinie.

---

# 15. Trigger exhaustion

Un Trigger peut être :

```text
finite
```

ou :

```text
infinite
```

---

# 16. Trigger fini

Exemple :

```text
DateTrigger
```

produit généralement :

```text
1 occurrence
```

puis :

```text
None
```

---

# 17. Trigger infini

Exemple :

```text
CronTrigger("0 6 * * *")
```

sans `end_at`.

Conceptuellement, il peut produire des occurrences indéfiniment.

---

# 18. FiniteTrigger

Une abstraction formelle :

```text
FiniteTrigger
```

n'est pas forcément nécessaire.

La propriété peut être simplement émergente de :

```text
next_after(...) is None
```

---

# 19. Trigger stateful versus stateless

Autre distinction importante :

```text
Stateless Trigger
```

versus :

```text
Stateful Trigger
```

---

# 20. Stateless Trigger

Un Trigger stateless calcule la prochaine occurrence uniquement à partir :

```text
de sa configuration
+
du reference time
```

Exemple :

```text
CronTrigger
```

peut souvent fonctionner ainsi.

---

# 21. Exemple

```text
CronTrigger("0 6 * * *")

next_after(2026-10-04 07:00)
→ 2026-10-05 06:00
```

Aucun état interne mutable n'est nécessaire.

---

# 22. IntervalTrigger stateless

Un `IntervalTrigger` peut également être stateless si l'on conserve :

```text
anchor
+
interval
```

et que l'on calcule mathématiquement la prochaine échéance.

---

# 23. Stateful Trigger

Un trigger deviendrait stateful s'il conservait :

```text
last_occurrence
counter
cursor
```

en interne.

Cette approche complique :

```text
persistence
concurrency
replay
testing
```

---

# 24. Recommandation

Privilégier :

```text
stateless immutable triggers
```

chaque fois que possible.

L'état opérationnel doit rester dans :

```text
Schedule
Occurrence
runtime state
```

plutôt que dans le Trigger.

---

# 25. Pourquoi ?

Un même Trigger peut alors être évalué :

```text
sur plusieurs nodes

dans des tests

pendant un replay

pour des simulations
```

sans coordination particulière.

---

# 26. Trigger input

Le Trigger devrait idéalement recevoir :

```text
un reference point
```

et éventuellement :

```text
un temporal context
```

minimal.

---

# 27. TriggerContext

Une abstraction potentielle :

```text
TriggerContext
```

pourrait contenir :

```text
reference
timezone
schedule_window
calendar?
```

Mais il faut éviter de rendre le Trigger dépendant de tout le domaine.

---

# 28. Recommandation de séparation

Le Trigger doit connaître uniquement ce qui est indispensable au calcul de **sa règle**.

Par exemple :

```text
CronTrigger
→ local rule + timezone

IntervalTrigger
→ anchor + duration

DateTrigger
→ absolute instant
```

Le Calendar métier peut rester séparé.

---

# 29. CandidateOccurrence

Il peut être utile de distinguer :

```text
CandidateOccurrence
```

de :

```text
Occurrence
```

---

# 30. Pourquoi ?

Le Trigger peut produire :

```text
Saturday 08:00
```

mais un `BusinessCalendar` peut ensuite l'exclure.

Le résultat du Trigger n'est donc pas encore forcément une occurrence valide du Schedule.

---

# 31. Modèle

```text
Trigger
   │
   ▼
CandidateOccurrence
   │
   ▼
Calendar / ScheduleWindow
   │
   ▼
Occurrence
```

---

# 32. CandidateOccurrence comme Value Object

Il pourrait contenir :

```text
scheduled_at
local_datetime?
timezone_resolution?
trigger_metadata?
```

Mais une classe distincte n'est pas obligatoire en V1.

---

# 33. Simplicité V1

Pour V1, le Trigger peut simplement retourner :

```text
Instant | None
```

et le moteur peut construire :

```text
Occurrence
```

ensuite.

---

# 34. Trigger et Timezone

La timezone ne joue pas le même rôle selon le Trigger.

---

# 35. DateTrigger absolu

Si la date est déjà exprimée comme :

```text
Instant
```

aucune timezone supplémentaire n'est nécessaire pour le calcul.

---

# 36. DateTrigger local

Si l'utilisateur fournit :

```text
2026-10-05 08:00
Europe/Paris
```

la résolution timezone doit avoir lieu avant ou dans le Trigger selon l'API retenue.

---

# 37. CronTrigger

Une timezone est généralement indispensable car :

```text
0 8 * * *
```

exprime une règle civile locale.

---

# 38. IntervalTrigger

Un intervalle fixe basé sur :

```text
Duration
```

peut fonctionner entièrement en Instants.

La timezone peut ne pas intervenir.

---

# 39. CalendarTrigger

Une règle métier calendaire dépend fortement :

```text
LocalDate
LocalTime
Timezone
Calendar
```

---

# 40. Trigger et DST

Pour un trigger calendaire :

```text
Every day at 02:30 Europe/Paris
```

le changement d'heure peut produire :

```text
NonexistentLocalTime
```

ou :

```text
AmbiguousLocalTime
```

---

# 41. Responsabilité DST

La résolution DST doit être explicite.

Deux modèles sont possibles.

---

# 42. Modèle A — Trigger owns DST policy

```text
CronTrigger
├── rule
├── timezone
└── dst_policy
```

Avantage :

```text
trigger self-contained
```

---

# 43. Modèle B — Schedule owns DST policy

```text
ScheduleDefinition
├── Trigger
├── Timezone
└── DSTResolutionPolicy
```

Avantage :

```text
politique temporelle partagée
```

---

# 44. Recommandation

Le Trigger devrait utiliser un :

```text
TemporalResolutionContext
```

ou une policy fournie par `ScheduleDefinition`.

Ainsi :

```text
la règle
```

reste distincte de :

```text
la stratégie de résolution des anomalies civiles
```

---

# 45. Trigger et Calendar

Le Trigger ne doit pas devenir un BusinessCalendar.

Exemple :

```text
CronTrigger
```

ne devrait pas contenir :

```text
jours fériés France
fermetures entreprise
jour bancaire
```

---

# 46. Séparation recommandée

```text
Trigger
→ produit des candidats

Calendar
→ valide / déplace selon règles métier
```

---

# 47. Mais attention

Pour une règle intrinsèquement calendaire comme :

```text
first working day of month
```

le Calendar fait partie de la définition même de l'occurrence.

Dans ce cas :

```text
CalendarTrigger
```

peut collaborer explicitement avec un `Calendar`.

---

# 48. Deux familles de triggers

On peut donc distinguer :

```text
Pure Temporal Trigger
```

et :

```text
Calendar-Aware Trigger
```

---

# 49. Pure Temporal Trigger

Exemples :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

---

# 50. Calendar-Aware Trigger

Exemples :

```text
BusinessDayTrigger
MonthEndBusinessTrigger
CalendarTrigger
```

Ces derniers peuvent dépendre d'un :

```text
CalendarRef
```

ou d'un Calendar résolu.

---

# 51. Trigger et ScheduleWindow

Le Schedule peut avoir :

```text
start_at
end_at
```

La question est :

> Le Trigger doit-il connaître ces bornes ?

---

# 52. Option A

Le Trigger produit librement :

```text
next candidate
```

puis le moteur applique :

```text
ScheduleWindow
```

---

# 53. Option B

Les bornes sont fournies au Trigger pour éviter des calculs inutiles.

---

# 54. Recommandation

La logique de validité appartient au Schedule.

Mais le Trigger peut recevoir une borne technique :

```text
upper_bound
```

comme optimisation.

La sémantique métier ne doit pas dépendre de cette optimisation.

---

# 55. Start boundary

Si :

```text
Schedule.start_at = 2026-11-01
```

le moteur peut rechercher :

```text
trigger.next_at_or_after(start_at)
```

ou utiliser une référence juste avant la borne.

---

# 56. End boundary

Si :

```text
candidate > end_at
```

alors le Schedule peut être considéré comme :

```text
COMPLETED
```

si aucune occurrence valide future n'est possible.

---

# 57. Trigger contract recommandé

Conceptuellement :

```text
next_after(reference: Instant) -> Instant | None
```

pour les triggers absolus.

Pour les triggers civils, une couche de résolution peut être nécessaire.

---

# 58. Alternative générique

```text
next_occurrence(
    reference: Instant,
    context: TriggerEvaluationContext
) -> OccurrenceCandidate | None
```

Plus extensible, mais plus lourd.

---

# 59. Recommandation V1

Préférer un contrat simple.

```text
Trigger
→ next_after(reference)
```

Les paramètres structurels nécessaires sont portés par le Trigger immutable lui-même.

---

# 60. Trigger types

Le modèle initial doit supporter conceptuellement :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

puis éventuellement :

```text
CalendarTrigger
CompositeTrigger
```

---

# 61. DateTrigger

Question :

> Existe-t-il une occurrence unique située après la référence ?

---

# 62. IntervalTrigger

Question :

> Quelle échéance de la série `anchor + n × interval` vient après la référence ?

---

# 63. CronTrigger

Question :

> Quelle prochaine combinaison calendaire satisfait l'expression ?

---

# 64. CalendarTrigger

Question :

> Quelle prochaine date satisfait une règle calendaire métier ?

---

# 65. TriggerKind

Une représentation persistante pourra utiliser :

```text
DATE
INTERVAL
CRON
CALENDAR
```

mais :

```text
TriggerKind
```

ne doit pas remplacer les objets polymorphes dans le domaine.

---

# 66. Polymorphisme

Préférer :

```text
trigger.next_after(...)
```

à :

```python
if trigger.type == "cron":
    ...
elif trigger.type == "interval":
    ...
```

dans le moteur principal.

---

# 67. Persistence representation

En base :

```text
trigger_type
trigger_config
```

reste raisonnable.

Exemple :

```json
{
  "type": "cron",
  "expression": "0 6 * * *"
}
```

---

# 68. Rehydration

Le repository doit reconstruire le bon objet :

```text
CRON
→ CronTrigger

INTERVAL
→ IntervalTrigger

DATE
→ DateTrigger
```

---

# 69. Trigger serialization

Chaque Trigger doit idéalement pouvoir être :

```text
serialized
deserialized
compared
fingerprinted
```

de façon déterministe.

---

# 70. Trigger fingerprint

Un `TriggerFingerprint` peut représenter :

```text
hash(
  normalized trigger configuration
)
```

utile pour :

```text
audit
cache
change detection
diagnostics
```

---

# 71. Fingerprint n'est pas une identité

```text
TriggerFingerprint
≠
TriggerId
```

Deux triggers identiques peuvent partager le même fingerprint.

C'est souhaité.

---

# 72. Canonical representation

Pour obtenir un fingerprint stable, la représentation doit être :

```text
normalisée
ordonnée
stable
indépendante des détails runtime
```

---

# 73. Trigger equality

Deux triggers :

```text
CronTrigger("0 6 * * *")
```

sont égaux si leur configuration métier normalisée est égale.

---

# 74. Trigger determinism

Un invariant central :

```text
same trigger
+
same reference
+
same relevant temporal context
=
same next occurrence
```

---

# 75. Sources de non-déterminisme interdites

Un Trigger ne doit pas utiliser directement :

```text
datetime.now()

random()

database mutable state

network
```

pour déterminer la prochaine occurrence.

---

# 76. Jitter

C'est important :

```text
Jitter
```

ne devrait pas modifier la sortie logique du Trigger.

---

# 77. Pourquoi ?

Le Trigger représente :

```text
l'intention temporelle
```

Le jitter représente :

```text
une variation de dispatch
```

---

# 78. Exemple

```text
Trigger occurrence:
08:00:00
```

Jitter :

```text
+17 seconds
```

Alors :

```text
scheduled_at = 08:00:00
dispatch_not_before = 08:00:17
```

et non :

```text
scheduled_at = 08:00:17
```

---

# 79. Trigger et misfire

Un Trigger ne gère pas les misfires.

Supposons :

```text
next occurrence = 08:00
now = 08:30
```

La décision :

```text
run now?
skip?
catch-up?
```

appartient à :

```text
MisfirePolicy
```

---

# 80. Trigger et catch-up

Le Trigger peut toutefois être utilisé pour **énumérer** les occurrences manquées.

Exemple :

```text
08:00
09:00
10:00
```

mais il ne décide pas :

```text
qu'elles doivent être exécutées
```

---

# 81. Occurrence enumeration

Une opération potentielle :

```text
occurrences_between(start, end)
```

peut être utile pour :

```text
catch-up
backfill
preview
calendar inspection
```

---

# 82. Doit-elle faire partie du contrat Trigger ?

Deux possibilités :

```text
oui
```

ou :

```text
helper basé sur next_after()
```

---

# 83. Recommandation

Conserver un contrat minimal :

```text
next_after()
```

et construire :

```text
iter_between()
```

comme utilitaire générique.

---

# 84. Exemple

```text
cursor = start

while True:
    next = trigger.next_after(cursor)

    if next is None or next > end:
        break

    yield next
    cursor = next
```

---

# 85. Protection contre les triggers invalides

Le moteur doit détecter un Trigger qui retournerait :

```text
next <= reference
```

et produire une erreur de domaine/runtime claire.

---

# 86. InvalidTriggerProgression

Une erreur possible :

```text
InvalidTriggerProgression
```

indique qu'un trigger viole son contrat monotone.

---

# 87. Max iteration guard

Lors d'une énumération ou d'un catch-up :

```text
max_occurrences
```

doit pouvoir limiter le calcul.

Cela protège contre :

```text
règles très fréquentes
bugs
très longues indisponibilités
```

---

# 88. Backfill

Un backfill demande :

```text
quelles occurrences auraient existé
entre T1 et T2 ?
```

Le Trigger est naturellement utile pour cela.

Mais :

```text
exécuter ces occurrences
```

reste une décision d'orchestration/policy.

---

# 89. Preview

Une fonctionnalité ergonomique utile :

```text
preview next 10 occurrences
```

peut être construite uniquement à partir du Trigger.

---

# 90. Exemple

```text
CronTrigger("0 6 * * *")

preview(3)
→
Oct 5 06:00
Oct 6 06:00
Oct 7 06:00
```

---

# 91. Trigger inspection

Une représentation introspectable peut fournir :

```text
kind
description
normalized configuration
finite?
timezone mode
```

sans exposer les détails internes de calcul.

---

# 92. Human-readable description

Exemple :

```text
CronTrigger("0 6 * * *")
```

peut être décrit :

```text
Every day at 06:00
```

mais cette traduction est une fonctionnalité de présentation, pas le contrat principal.

---

# 93. DateTrigger model

Structure conceptuelle :

```text
DateTrigger
│
└── scheduled_at: Instant
```

---

# 94. DateTrigger invariant

```text
scheduled_at
```

est obligatoire.

Aucun autre état n'est nécessaire.

---

# 95. DateTrigger behavior

```text
if scheduled_at > reference:
    return scheduled_at

return None
```

---

# 96. IntervalTrigger model

Structure :

```text
IntervalTrigger
│
├── anchor
├── interval
└── mode?
```

---

# 97. Interval invariant

```text
interval > 0
```

Un intervalle :

```text
0
```

ou négatif doit être invalide.

---

# 98. Interval anchor

L'anchor définit :

```text
le point d'origine
```

de la série.

Exemple :

```text
anchor = 10:00
interval = 5m
```

produit :

```text
10:00
10:05
10:10
...
```

---

# 99. Pourquoi l'anchor est nécessaire

Sans anchor :

```text
every 5 minutes
```

peut être interprété différemment selon :

```text
l'heure de création
le restart
le premier run
```

La sémantique doit être explicite.

---

# 100. Fixed Rate

Le modèle classique d'IntervalTrigger est :

```text
anchor + N × interval
```

Il s'agit d'un :

```text
fixed-rate schedule
```

---

# 101. Fixed Delay

Le fixed delay dépend de :

```text
previous_execution_finished_at
```

et non seulement du temps planifié.

Il constitue donc une abstraction différente.

---

# 102. Recommandation

Ne pas mettre :

```text
FIXED_DELAY
```

dans `IntervalTrigger` V1.

Introduire ultérieurement un concept séparé, par exemple :

```text
DelayAfterCompletionSchedule
```

si nécessaire.

---

# 103. Pourquoi ?

Sinon le Trigger cesse d'être une pure règle temporelle et dépend du runtime d'exécution.

---

# 104. CronTrigger model

Structure :

```text
CronTrigger
│
├── CronExpression
├── local timezone context
└── DST resolution semantics
```

selon le partage de responsabilités retenu.

---

# 105. Cron expression

Elle exprime :

```text
minute
hour
day-of-month
month
day-of-week
```

dans le modèle cron classique.

Les extensions devront être explicitement documentées.

---

# 106. Cron dialect

Tous les moteurs cron n'utilisent pas exactement le même dialecte.

PyScheduleKit doit définir :

```text
son dialecte supporté
```

avant d'accepter des expressions arbitraires.

---

# 107. Questions futures

Supportera-t-on :

```text
seconds field?
year field?
L?
W?
#?
names?
ranges?
steps?
```

Ces choix appartiendront au document détaillé du CronTrigger.

---

# 108. Cron normalization

Deux syntaxes équivalentes pourraient être normalisées vers une représentation canonique.

Cela facilite :

```text
equality
fingerprint
serialization
```

---

# 109. Cron and timezone

La timezone ne doit pas être perdue lors de la normalisation.

```text
cron="0 8 * * *"
timezone="Europe/Paris"
```

est différent de :

```text
cron="0 8 * * *"
timezone="UTC"
```

---

# 110. CalendarTrigger model

Structure conceptuelle :

```text
CalendarTrigger
│
├── recurrence rule
├── CalendarRef
├── LocalTime
└── Timezone
```

---

# 111. Exemple

```text
First business day of each month
at 07:00 Europe/Paris
```

---

# 112. Calendar dependency

Si `CalendarRef` doit être résolu via infrastructure, un Trigger immutable ne doit pas effectuer directement :

```text
calendar_provider.load()
```

---

# 113. Solution

Le moteur peut fournir :

```text
resolved Calendar
```

au calculateur spécialisé.

Ou un service :

```text
CalendarOccurrencePlanner
```

peut collaborer avec le Trigger.

---

# 114. Trigger purity

Idéalement :

```text
Trigger evaluation
```

doit être :

```text
pure
```

ou aussi proche que possible d'une fonction pure.

---

# 115. Pourquoi ?

Cela facilite :

```text
property-based tests
replay
cache
parallel evaluation
distributed scheduling
```

---

# 116. Composite Trigger

À terme, il peut être utile de combiner plusieurs triggers.

Exemples :

```text
OR
AND
EXCEPT
```

---

# 117. OrTrigger

```text
Trigger A
OR
Trigger B
```

produit la prochaine occurrence la plus proche issue des deux.

---

# 118. Exemple

```text
Every Monday 08:00
OR
Every Friday 17:00
```

---

# 119. IntersectionTrigger

Une intersection :

```text
A AND B
```

est beaucoup plus délicate.

Elle ne doit pas être introduite sans définition mathématique claire.

---

# 120. ExclusionTrigger

Exemple :

```text
Daily 08:00
EXCEPT holidays
```

Mais cela peut souvent être mieux modélisé par :

```text
Trigger
+
Calendar
```

---

# 121. Recommandation

Ne pas introduire `CompositeTrigger` dans V1.

Les trois triggers fondamentaux suffisent :

```text
Date
Interval
Cron
```

---

# 122. Trigger lifecycle

Un Trigger lui-même n'a pas vraiment de lifecycle.

Il peut être :

```text
usable
```

ou :

```text
exhausted relative to a reference
```

mais il reste immutable.

---

# 123. Trigger exhausted ≠ Trigger state mutation

Un `DateTrigger` dont la date est passée ne doit pas muter vers :

```text
USED
```

Il retourne simplement :

```text
None
```

pour une référence future.

---

# 124. Avantage

On peut toujours demander :

```text
DateTrigger.next_after(yesterday)
```

et retrouver la date.

Le Trigger reste une règle pure.

---

# 125. Schedule completion

C'est le `Schedule` ou le moteur qui peut devenir :

```text
COMPLETED
```

lorsque :

```text
trigger.next_after(reference) is None
```

---

# 126. Trigger persistence

Le Trigger étant immutable, sa persistance peut être simplement sa configuration.

Exemple :

```json
{
  "kind": "interval",
  "anchor": "2026-10-04T06:00:00Z",
  "seconds": 300
}
```

---

# 127. Schema version

Les configurations persistées devraient prévoir :

```text
trigger_schema_version
```

ou une version globale du format sérialisé.

Pourquoi ?

Pour permettre l'évolution future des formats.

---

# 128. Exemple

```json
{
  "schema_version": 1,
  "kind": "cron",
  "expression": "0 6 * * *"
}
```

---

# 129. Trigger compatibility

Une nouvelle version de PyScheduleKit doit pouvoir :

```text
relire
```

les triggers persistés par les versions antérieures compatibles.

---

# 130. Unknown trigger kind

Si une configuration contient :

```text
kind = "quantum_trigger"
```

non supporté, la reconstruction doit échouer explicitement.

---

# 131. UnsupportedTriggerKind

Erreur proposée :

```text
UnsupportedTriggerKind
```

---

# 132. InvalidTriggerConfiguration

Autre erreur :

```text
InvalidTriggerConfiguration
```

pour une configuration structurellement incorrecte.

---

# 133. InvalidCronExpression

Spécifique au cron :

```text
InvalidCronExpression
```

---

# 134. InvalidInterval

Pour :

```text
interval <= 0
```

---

# 135. Nonexistent local occurrence

Pour les triggers civils :

```text
NonexistentLocalTime
```

peut être résolu via policy ou exposé comme erreur.

---

# 136. Trigger output metadata

Une occurrence calculée peut éventuellement conserver :

```text
local datetime
timezone offset
DST fold
trigger kind
```

pour audit.

Mais ces données ne doivent pas forcément faire partie du contrat minimal.

---

# 137. Occurrence provenance

Il peut être intéressant de conserver :

```text
trigger_fingerprint
```

dans :

```text
Occurrence
```

ou dans l'evidence d'audit.

---

# 138. Pourquoi ?

Pour expliquer :

```text
quelle configuration exacte
a produit cette occurrence ?
```

Cela complète :

```text
ScheduleRevision
```

---

# 139. ScheduleRevision suffit souvent

Si chaque revision conserve une définition immutable :

```text
ScheduleRevision
```

permet déjà de retrouver le Trigger.

Le fingerprint reste donc facultatif.

---

# 140. Trigger evaluation time

Le calcul d'une occurrence ne doit pas dépendre du vrai `Clock.now()`.

Le moteur fournit explicitement :

```text
reference
```

---

# 141. Mauvais modèle

```python
trigger.next()
```

qui appelle implicitement :

```python
datetime.now()
```

---

# 142. Bon modèle

```python
trigger.next_after(reference)
```

Le temps est explicite.

---

# 143. Pourquoi c'est crucial

Pour :

```text
backfill

preview

replay

tests

recovery
```

on doit pouvoir évaluer le Trigger à partir de n'importe quelle référence.

---

# 144. Trigger preview example

```text
reference
2026-10-04 12:00

CronTrigger
0 6 * * *
```

résultats :

```text
Oct 5 06:00
Oct 6 06:00
Oct 7 06:00
```

---

# 145. Trigger and recovery

Après restart :

```text
last known occurrence
+
Trigger
```

permet de reconstruire :

```text
future occurrences
```

---

# 146. Mais attention à la source de référence

On peut calculer depuis :

```text
last_processed_occurrence
```

ou :

```text
now
```

selon :

```text
misfire/catch-up policy
```

Le Trigger ne choisit pas.

---

# 147. Exemple

```text
last occurrence = 08:00
now = 12:30
```

Trigger hourly produit :

```text
09:00
10:00
11:00
12:00
13:00
```

Le moteur/policy décide lesquelles traiter.

---

# 148. Trigger and coalescing

Le Trigger ne fusionne pas les occurrences.

Il produit :

```text
09:00
10:00
11:00
```

Le `CoalescingPolicy` décide :

```text
1 request
```

ou non.

---

# 149. Trigger and concurrency

Même séparation :

```text
Trigger
```

ne sait pas qu'un run précédent est encore actif.

---

# 150. Trigger and retry

Un retry n'est pas une nouvelle occurrence du Trigger.

```text
08:00 occurrence
├── attempt 1
├── retry 1
└── retry 2
```

Le Trigger n'est pas impliqué.

---

# 151. Trigger and execution duration

Un Trigger fixed-rate ne doit pas adapter ses dates selon :

```text
run duration
```

Sinon il devient fixed-delay.

---

# 152. Trigger and queue delay

Une queue longue ne modifie pas :

```text
future recurrence
```

pour un Trigger fixed-rate.

---

# 153. Trigger and local calendar day

Un Trigger basé sur :

```text
Every day
```

doit préciser si `day` signifie :

```text
24h duration
```

ou :

```text
next local calendar date
```

---

# 154. Recommandation de vocabulaire

```text
IntervalTrigger
→ Duration-based recurrence

CronTrigger
→ Calendar-based recurrence
```

Cette distinction doit être visible dans l'API et la documentation.

---

# 155. Trigger categories

On peut organiser :

```text
Trigger
│
├── Absolute
│   └── DateTrigger
│
├── Duration-based
│   └── IntervalTrigger
│
└── Calendar-based
    ├── CronTrigger
    └── CalendarTrigger
```

---

# 156. Trigger contract and timezone

Un `IntervalTrigger` absolu peut produire directement des `Instant`.

Un `CronTrigger` peut suivre :

```text
Local candidate
→ timezone resolution
→ Instant
```

mais son API publique peut malgré tout retourner un `Instant`.

---

# 157. Uniformité

C'est souhaitable que tous les Triggers retournent finalement :

```text
Instant | None
```

afin que le moteur n'ait pas à connaître leur mécanique interne.

---

# 158. Internal processing can differ

```text
DateTrigger
→ Instant

IntervalTrigger
→ arithmetic on Instant

CronTrigger
→ LocalDateTime → Timezone → Instant
```

mais :

```text
public result
→ Instant
```

---

# 159. Trigger dependency direction

Le cœur doit ressembler à :

```text
Scheduler
   ↓
Trigger abstraction
```

et non :

```text
Trigger
   ↓
Scheduler
```

---

# 160. Extensibility

Un utilisateur pourrait ajouter :

```text
SolarTrigger

MarketOpenTrigger

NthBusinessDayTrigger
```

sans modifier `SchedulerEngine`.

---

# 161. Trigger protocol

Conceptuellement :

```python
class Trigger(Protocol):
    def next_after(self, reference: Instant) -> Instant | None: ...
```

Ceci est illustratif, pas encore l'API finale.

---

# 162. Optional description contract

Une interface séparée pourrait fournir :

```text
describe()
serialize()
```

mais ces méthodes n'appartiennent pas forcément au contrat métier minimal.

---

# 163. Separation of concerns

On peut avoir :

```text
Trigger
```

pour le domaine.

```text
TriggerCodec
```

pour la sérialisation.

```text
TriggerFormatter
```

pour l'affichage.

---

# 164. Pourquoi ?

Éviter que le Trigger accumule :

```text
business logic
JSON serialization
human translation
database mapping
```

dans une seule classe.

---

# 165. TriggerCodec

Responsable de :

```text
Trigger
↔
serialized representation
```

---

# 166. TriggerRegistry

Pour les extensions :

```text
kind
→ decoder/factory
```

peut être géré par :

```text
TriggerRegistry
```

dans l'application/infrastructure.

---

# 167. Registry ≠ domain dependency

Le Domain Trigger ne doit pas dépendre du Registry.

Le Registry sert à :

```text
construction
deserialization
plugin extension
```

---

# 168. Security

Les configurations de Trigger ne doivent pas permettre d'exécuter du code arbitraire.

Exemple dangereux :

```text
trigger_config =
"eval(this Python)"
```

À éviter absolument.

---

# 169. Safe declarative configuration

Préférer :

```json
{
  "kind": "interval",
  "seconds": 300
}
```

à une représentation exécutable arbitraire.

---

# 170. Parsing limits

Les expressions complexes peuvent provoquer :

```text
CPU excessive
infinite search
memory use
```

Le moteur doit pouvoir imposer :

```text
search horizon
iteration limit
validation
```

---

# 171. Search horizon

Un Trigger qui ne trouve aucune occurrence avant très longtemps peut nécessiter :

```text
max_search_horizon
```

pour protéger le runtime.

---

# 172. Exemple

Une règle invalide ou extrêmement rare pourrait théoriquement demander :

```text
des millions d'itérations
```

si l'algorithme est naïf.

---

# 173. Performance contract

Un Trigger ne doit pas seulement être correct.

Il doit être raisonnablement :

```text
bounded
predictable
```

pour les règles supportées.

---

# 174. Caching

Des résultats peuvent éventuellement être mis en cache.

Mais comme les Triggers sont purs :

```text
cache
```

reste une optimisation externe.

---

# 175. Trigger does not cache mutable state

Éviter que :

```text
trigger._last_result
```

devienne nécessaire à sa correction.

---

# 176. Testing strategy

Chaque Trigger doit pouvoir être testé avec :

```text
table-driven tests
boundary tests
property-based tests
```

---

# 177. Properties communes

Pour tout Trigger :

```text
result is None
OR
result > reference
```

---

# 178. Determinism property

```text
next_after(r)
==
next_after(r)
```

pour la même configuration.

---

# 179. Monotonic property

Si :

```text
t1 = next_after(r)
t2 = next_after(t1)
```

alors :

```text
t2 > t1
```

ou :

```text
t2 is None
```

---

# 180. Serialization round-trip

```text
Trigger
→ serialize
→ deserialize
→ equal Trigger
```

doit être vérifié.

---

# 181. DateTrigger tests

Cas :

```text
reference before date
reference equal date
reference after date
```

---

# 182. IntervalTrigger tests

Cas :

```text
before anchor
at anchor
between ticks
exact tick
large offset
```

---

# 183. CronTrigger tests

Cas :

```text
minute boundary
day boundary
month boundary
leap year
DST
timezone
```

---

# 184. CalendarTrigger tests

Cas :

```text
weekend
holiday
month end
first business day
no valid date within horizon
```

---

# 185. Trigger error semantics

Les erreurs de configuration doivent apparaître :

```text
à la construction
```

autant que possible.

---

# 186. Exemple

```text
IntervalTrigger(interval=0)
```

doit être rejeté immédiatement.

Pas lors du premier `next_after()`.

---

# 187. Runtime calculation errors

Des erreurs comme :

```text
timezone data unavailable
calendar provider unavailable
```

ne sont pas forcément des erreurs du Trigger lui-même.

Elles appartiennent aux dépendances ou adapters.

---

# 188. Trigger and CalendarProvider availability

C'est une raison supplémentaire de ne pas laisser un Trigger pur appeler directement un Provider externe.

---

# 189. Trigger metrics

Des métriques internes possibles :

```text
trigger_evaluation_duration

trigger_evaluation_failures

trigger_exhaustions
```

mais elles appartiennent à l'observabilité du moteur, pas au Trigger métier.

---

# 190. Trigger tracing

On peut tracer :

```text
trigger kind
reference
result
schedule_id
revision
```

sans modifier le Trigger.

---

# 191. Trigger diagnostics

Un diagnostic utile pourrait expliquer :

```text
Reference:
2026-10-04T06:01Z

Trigger:
Cron 0 6 * * *

Timezone:
Europe/Paris

Next local candidate:
2026-10-05 06:00

Resolved instant:
...
```

---

# 192. Explainability

À terme, un :

```text
TriggerEvaluationTrace
```

pourrait être produit en mode diagnostic.

Mais il ne doit pas alourdir le chemin nominal du domaine.

---

# 193. Trigger and `NextRunTime`

Le `NextRunTime` du Schedule provient directement :

```text
Trigger.next_after(reference)
```

après prise en compte des contraintes du Schedule.

---

# 194. Attention

Il peut exister une différence entre :

```text
next trigger candidate
```

et :

```text
next valid schedule occurrence
```

si un Calendar exclut certaines dates.

---

# 195. Exemple

Trigger :

```text
daily 08:00
```

produit :

```text
Saturday 08:00
```

Calendar l'exclut.

Le véritable :

```text
NextRunTime
```

peut alors devenir :

```text
Monday 08:00
```

---

# 196. Conséquence

`NextRunTime` ne devrait probablement pas être calculé par le Trigger seul.

Il appartient au :

```text
Schedule occurrence planning
```

qui combine :

```text
Trigger
+
Calendar
+
Window
```

---

# 197. OccurrencePlanner

Cela suggère un service :

```text
OccurrencePlanner
```

responsable de :

```text
Trigger candidate generation
+
Calendar validation
+
Window boundaries
```

---

# 198. OccurrencePlanner versus Trigger

```text
Trigger
→ prochaine candidate selon la règle

OccurrencePlanner
→ prochaine occurrence valide du Schedule
```

Cette distinction est très utile.

---

# 199. Modèle conceptuel proposé

```text
ScheduleDefinition
       │
       ├── Trigger
       ├── Calendar
       ├── Window
       └── Timezone context
              │
              ▼
       OccurrencePlanner
              │
              ▼
          Occurrence
```

---

# 200. OccurrencePlanner classification

```text
OccurrencePlanner
=
Domain Service
```

car il combine plusieurs objets du domaine.

---

# 201. Trigger remains small

Cette architecture permet de maintenir :

```text
Trigger
```

simple, pur et réutilisable.

---

# 202. Planning algorithm

Conceptuellement :

```text
candidate = trigger.next_after(reference)

while candidate is not None:

    if outside schedule window:
        return None / continue

    if calendar allows candidate:
        return Occurrence(candidate)

    candidate = trigger.next_after(candidate)
```

---

# 203. Guardrails

Cette boucle doit posséder :

```text
max_iterations
search_horizon
```

afin de rester bornée.

---

# 204. `NextOccurrence`

Une API de haut niveau peut être :

```text
OccurrencePlanner.next_occurrence(schedule, after)
```

---

# 205. Trigger does not know ScheduleId

Un Trigger ne devrait pas avoir besoin de :

```text
ScheduleId
```

Il représente une règle réutilisable.

---

# 206. Occurrence does know Schedule context

Une fois l'occurrence construite :

```text
OccurrenceKey
=
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

---

# 207. Trigger reuse

Deux Schedules peuvent contenir deux triggers équivalents :

```text
CronTrigger("0 6 * * *")
```

sans partager d'identité.

---

# 208. Trigger instance sharing

Comme ils sont immutables, une implémentation peut techniquement partager les mêmes instances.

Mais cela doit rester un détail d'optimisation.

---

# 209. Trigger and ScheduleDefinition immutability

Puisque `ScheduleDefinition` est immutable :

```text
Trigger
```

l'est naturellement aussi.

Changer le Trigger signifie créer :

```text
new ScheduleDefinition
```

---

# 210. Reschedule flow

```text
Schedule
revision 4
Trigger A
   │
reschedule
   ▼
Schedule
revision 5
Trigger B
```

---

# 211. Historical occurrence

Une occurrence créée sous :

```text
revision 4
```

reste associée à :

```text
Trigger A
```

conceptuellement.

---

# 212. Trigger migration

Si le format de Trigger évolue entre versions du framework, les anciens schedules doivent pouvoir être migrés sans changer leur intention temporelle.

---

# 213. Semantic compatibility

La migration ne doit pas seulement être syntaxique.

Elle doit préserver :

```text
les mêmes occurrences
```

dans la mesure du possible.

---

# 214. Conformance tests

Chaque migration de trigger devrait pouvoir comparer :

```text
old next occurrences
```

et :

```text
new next occurrences
```

sur une série de références.

---

# 215. Trigger specification

Un futur document technique devra préciser :

```text
public protocol

serialization format

normalization

errors

timezone semantics

performance bounds
```

---

# 216. Modèle V1 recommandé

```text
Trigger
│
├── DateTrigger
├── IntervalTrigger
└── CronTrigger
```

Tous :

```text
immutable
value-based
deterministic
stateless
serializable
```

et exposant conceptuellement :

```text
next_after(reference) -> Instant | None
```

---

# 217. Ce qui reste hors de V1

```text
CompositeTrigger
SolarTrigger
EventTrigger
FixedDelayTrigger
complex business calendar triggers
randomized triggers
stateful triggers
```

Ils pourront être étudiés plus tard.

---

# 218. Pourquoi EventTrigger est hors scope

Un événement :

```text
message received
file arrived
API callback
```

n'est pas fondamentalement une règle temporelle.

Il appartient davantage à :

```text
event-driven triggering
```

qu'au scheduling temporel.

---

# 219. Timer after event

En revanche :

```text
30 minutes after event X
```

peut créer dynamiquement :

```text
DateTrigger(event_time + 30m)
```

Le Trigger reste temporel.

---

# 220. Trigger boundaries with PyWorkflowKit

PyWorkflowKit ne doit pas fournir au Trigger :

```text
step states
DAG dependencies
```

Le Trigger ne connaît que le temps.

---

# 221. Trigger boundaries with PyIngestKit

Il ne connaît pas :

```text
watermarks
API cursors
source checkpoints
```

sauf si ceux-ci servent à créer dynamiquement un nouveau Schedule en dehors du Trigger.

---

# 222. Trigger boundaries with PyTransformKit

Il ne connaît pas :

```text
dataset state
schemas
transform expressions
```

---

# 223. Core invariant

La règle la plus importante peut être résumée ainsi :

> **Un Trigger calcule le temps ; il ne décide pas de l'effet.**

---

# 224. Deuxième invariant

> **Un Trigger produit une prochaine échéance logique, pas une exécution.**

---

# 225. Troisième invariant

> **Un Trigger immutable évalué avec le même contexte doit toujours produire le même résultat.**

---

# 226. Quatrième invariant

> **La prochaine occurrence doit progresser strictement dans le temps.**

---

# 227. Cinquième invariant

> **Les erreurs de configuration doivent être rejetées avant l'exécution normale du scheduler.**

---

# 228. Anti-pattern — Trigger exécuteur

Éviter :

```python
trigger.run()
```

si cela signifie exécuter le target.

---

# 229. Anti-pattern — Trigger avec `now()` implicite

Éviter :

```python
trigger.next()
```

fondé sur l'heure système courante.

---

# 230. Anti-pattern — Trigger mutable

Éviter :

```text
trigger.last_run = ...
trigger.next_run = ...
```

si ces valeurs sont nécessaires au calcul.

---

# 231. Anti-pattern — Trigger persistant comme Entity

Éviter :

```text
TriggerId
TriggerState
TriggerHistory
```

sans justification métier.

---

# 232. Anti-pattern — Misfire dans Trigger

Éviter :

```text
CronTrigger.run_missed_occurrences()
```

Le Trigger peut les calculer, pas décider de les exécuter.

---

# 233. Anti-pattern — Calendar universel dans CronTrigger

Éviter de transformer `CronTrigger` en moteur :

```text
holidays
business calendars
company exceptions
```

---

# 234. Anti-pattern — FixedDelay déguisé en interval

Éviter :

```text
IntervalTrigger
```

dont la prochaine occurrence dépend silencieusement de la fin de l'exécution.

---

# 235. Anti-pattern — Random Trigger

Une variation aléatoire dans la date logique détruit :

```text
determinism
replay
audit
```

Le jitter doit rester une policy séparée.

---

# 236. Exemple complet — DateTrigger

```text
Schedule
│
├── TargetRef("ingestion:import")
└── DateTrigger
      2026-10-15T08:00Z
```

Evaluation :

```text
reference = Oct 14
→ Oct 15 08:00

reference = Oct 15 08:00
→ None
```

avec sémantique strictement `>`.

---

# 237. Exemple complet — IntervalTrigger

```text
anchor = 10:00
interval = 5m
```

Occurrences :

```text
10:00
10:05
10:10
10:15
...
```

---

# 238. Exemple complet — CronTrigger

```text
cron = 0 6 * * *
timezone = Europe/Paris
```

Produit les instants correspondant à :

```text
06:00 heure locale
```

chaque jour.

---

# 239. Exemple Calendar exclusion

Trigger :

```text
daily @ 08:00
```

Calendar :

```text
weekdays only
```

Calcul :

```text
Saturday 08:00
→ rejected

Sunday 08:00
→ rejected

Monday 08:00
→ accepted
```

---

# 240. Exemple recovery

Scheduler indisponible :

```text
08:00 → 12:30
```

Trigger hourly permet de calculer :

```text
09:00
10:00
11:00
12:00
13:00
```

MisfirePolicy choisit ensuite :

```text
SKIP
RUN_NOW
CATCH_UP
COALESCE
```

---

# 241. Example preview

```text
trigger.preview(
    after=Oct 4,
    count=5
)
```

est une API applicative qui peut être construite au-dessus de `next_after()`.

---

# 242. Example schedule planning

```text
ScheduleDefinition
      │
      ▼
Trigger.next_after(reference)
      │
      ▼
Candidate Instant
      │
      ▼
Calendar
      │
      ▼
ScheduleWindow
      │
      ▼
Occurrence
      │
      ▼
NextRunTime
```

---

# 243. Critères d'acceptation

Le Trigger Model sera considéré comme suffisamment défini lorsqu'on pourra répondre sans ambiguïté à :

```text
Qu'est-ce qu'un Trigger ?

Que reçoit-il en entrée ?

Que retourne-t-il ?

Est-il stateful ?

Qui gère la timezone ?

Qui gère DST ?

Qui gère le calendrier métier ?

Qui gère les misfires ?

Qui gère le catch-up ?

Qui gère le jitter ?

Comment détecter l'exhaustion ?

Comment énumérer les occurrences ?

Comment sérialiser un Trigger ?

Comment assurer son déterminisme ?

Comment ajouter un nouveau type de Trigger ?
```

---

# 244. Décisions proposées pour V1

```text
1.
Trigger est un Value Object comportemental.

2.
Trigger est immutable.

3.
Trigger est stateless.

4.
Trigger ne lit jamais l'horloge système.

5.
Le contrat conceptuel est :
next_after(reference) -> Instant | None.

6.
Le résultat doit être strictement supérieur
à la référence.

7.
V1 supporte :
DateTrigger
IntervalTrigger
CronTrigger.

8.
IntervalTrigger utilise fixed-rate.

9.
Fixed-delay est hors du Trigger V1.

10.
Misfire, catch-up, concurrency et retry
restent hors du Trigger.

11.
Jitter ne modifie pas scheduled_at.

12.
Calendar et Trigger restent séparés
sauf triggers calendaires spécialisés.

13.
ScheduleWindow est une contrainte du Schedule,
pas l'identité du Trigger.

14.
Les Triggers sont sérialisables
par configuration déclarative.

15.
Un Trigger peut retourner None
pour signaler l'exhaustion.
```

---

# 245. Modèle final

```text
                     ScheduleDefinition
                             │
                             ▼
                          Trigger
                 [Value Object / Strategy]
                             │
               next_after(reference)
                             │
                             ▼
                  Candidate Occurrence
                             │
             ┌───────────────┼────────────────┐
             │               │                │
             ▼               ▼                ▼
          Calendar      ScheduleWindow    Timezone/DST
             │               │                │
             └───────────────┼────────────────┘
                             │
                             ▼
                       Occurrence
                             │
                             ▼
                       NextRunTime
                             │
                             ▼
                  SchedulingEvaluator
                             │
                             ▼
                  SchedulingDecision
```

---

# 246. Séparation des responsabilités

```text
Trigger
→ WHEN is the next candidate?

Calendar
→ Is this date/time allowed?

ScheduleWindow
→ Is this candidate inside the schedule lifetime?

MisfirePolicy
→ What if this occurrence is late?

ConcurrencyPolicy
→ What if another execution is active?

Executor
→ How should the work be submitted?
```

---

# Conclusion

Le `Trigger` constitue le **générateur temporel** de PyScheduleKit.

Il ne représente ni le Schedule, ni l'Occurrence, ni l'Execution.

Son rôle reste volontairement étroit :

> **À partir d'une règle temporelle et d'une référence explicite, calculer de manière déterministe la prochaine échéance candidate.**

Le modèle recommandé repose donc sur :

```text
Trigger
=
immutable
+
stateless
+
deterministic
+
value-based
+
side-effect free
```

avec comme contrat conceptuel central :

```text
next_after(reference)
        ↓
Instant | None
```

Cette discipline permet ensuite au reste du domaine de traiter séparément :

```text
Calendar
ScheduleWindow
DST policies
Misfire
CatchUp
Coalescing
Concurrency
Execution
```

sans transformer le Trigger en un scheduler universel.

---

# Suite documentaire

La prochaine étape est :

```text
11_DATE_INTERVAL_AND_CRON_TRIGGERS.md
```

Elle devra comparer en profondeur :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

notamment sur :

```text
sémantique temporelle
anchor
récurrence
timezone
DST
exhaustion
fixed-rate
calendar time
serialization
algorithmes de next occurrence
edge cases
tests
```

L'objectif sera de comprendre pourquoi **« dans une heure »**, **« toutes les heures »** et **« chaque jour à 08:00 »** sont trois problèmes temporels différents malgré leur apparente proximité.