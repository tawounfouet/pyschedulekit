# PyScheduleKit — Time, Clock, Timezone & Calendar Model

**Document :** `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle temporel de référence  
**Nature :** Domain Model — Time / Clock / Timezone / Calendar  
**Prérequis :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
- `01_SCHEDULING_DOMAIN_INTRODUCTION.md`
- `02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md`
- `03_SCHEDULING_DOMAIN_VOCABULARY.md`
- `04_SCHEDULING_BUSINESS_OBJECTS.md`
- `05_SCHEDULING_ENTITIES_AND_VALUE_OBJECTS.md`
- `07_SCHEDULING_ERD.md`

---

# 1. Objectif

Un framework de scheduling manipule avant tout du **temps**.

Pourtant, le mot « temps » recouvre plusieurs notions différentes :

```text
2026-10-04 08:00

08:00 Europe/Paris

2026-10-04T06:00:00Z

5 minutes

08:00 → 18:00

premier jour ouvré du mois

dans 10 minutes

chaque lundi à 08:00
```

Ces expressions ne représentent pas le même type d'information.

PyScheduleKit doit donc construire un modèle temporel explicite permettant de distinguer :

```text
Instant
LocalDate
LocalTime
LocalDateTime
Timezone
UTC Offset
Duration
Period
TimeWindow
Clock
Calendar
BusinessCalendar
Deadline
GracePeriod
```

L'objectif fondamental est :

> **Éviter de réduire le domaine temporel à quelques objets `datetime` manipulés implicitement.**

---

# 2. Pourquoi le temps est un domaine à part entière

Une implémentation naïve pourrait reposer partout sur :

```python
datetime.now()
```

puis effectuer des comparaisons.

Cela fonctionne tant que l'on ignore :

```text
les fuseaux horaires
les changements d'heure
les heures inexistantes
les heures ambiguës
les calendriers métier
les jours fériés
les durées
les fenêtres d'exécution
les tests déterministes
les redémarrages
les systèmes distribués
```

Dès que ces problèmes apparaissent :

```text
datetime
```

ne suffit plus comme modèle conceptuel.

---

# 3. Principe fondamental

PyScheduleKit doit toujours chercher à savoir :

```text
Sommes-nous en train de parler :

1. d'un point absolu sur la ligne du temps ?

2. d'une représentation locale de ce point ?

3. d'une quantité de temps ?

4. d'une règle calendaire ?

5. d'une plage temporelle ?

6. de l'horloge utilisée pour observer le temps ?
```

Ces questions conduisent à des objets différents.

---

# 4. Carte générale du modèle temporel

```text
                         TIME MODEL
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
       Instant          Local Time         Duration
          │                  │                  │
          │            LocalDateTime            │
          │                  │                  │
          │                  ▼                  │
          │              Timezone               │
          │                  │                  │
          └──────────┬───────┘                  │
                     │                          │
                     ▼                          │
                Zoned Time                     │
                     │                          │
                     ├──────────────────────────┘
                     │
                     ▼
                 TimeWindow
                     │
            ┌────────┴────────┐
            ▼                 ▼
        Deadline          GracePeriod

                     +
                     │
                     ▼
                  Calendar
                     │
                     ▼
              BusinessCalendar

                     +
                     │
                     ▼
                    Clock
```

---

# 5. Instant

## Définition

Un `Instant` représente un point unique sur la ligne du temps universelle.

Exemple :

```text
2026-10-04T06:00:00Z
```

Cet instant est indépendant de la manière dont il est affiché.

---

# 6. Un même Instant, plusieurs représentations locales

Par exemple :

```text
2026-10-04T06:00:00Z
```

peut correspondre à :

```text
08:00 Europe/Paris
```

et à une autre heure locale ailleurs.

Conceptuellement :

```text
              Instant
  2026-10-04T06:00:00Z
          /         \
         /           \
        ▼             ▼
08:00 Paris       Local time elsewhere
```

Il n'existe toujours qu'un seul instant.

---

# 7. Instant comme Value Object

Dans le modèle DDD :

```text
Instant
=
Value Object
```

Il doit idéalement être :

```text
immutable
timezone-independent internally
totally ordered
comparable
```

---

# 8. Usages d'Instant

Les propriétés suivantes devraient généralement être représentées comme des instants :

```text
scheduled_at
triggered_at
created_at
queued_at
started_at
finished_at
deadline
lease_expires_at
```

Cela permet des comparaisons fiables.

---

# 9. LocalDate

`LocalDate` représente une date calendaire sans heure.

Exemple :

```text
2026-10-04
```

Elle répond à :

> Quel jour du calendrier local ?

Elle ne représente pas un instant.

---

# 10. LocalTime

`LocalTime` représente une heure locale sans date ni timezone.

Exemple :

```text
06:00
```

Cette valeur ne permet pas à elle seule de savoir quand exactement l'événement aura lieu.

---

# 11. LocalDateTime

`LocalDateTime` associe :

```text
LocalDate
+
LocalTime
```

Exemple :

```text
2026-10-04 06:00
```

Mais il manque encore :

```text
Timezone
```

pour interpréter cette valeur comme un instant absolu.

---

# 12. Distinction fondamentale

```text
LocalDateTime
≠
Instant
```

Par exemple :

```text
2026-10-04 08:00
```

ne suffit pas.

Il faut savoir :

```text
08:00 où ?
```

---

# 13. Timezone

Une `Timezone` représente un ensemble de règles permettant d'interpréter le temps civil d'une région.

Exemples :

```text
Europe/Paris
America/New_York
Asia/Tokyo
Africa/Douala
UTC
```

Une timezone ne correspond pas seulement à :

```text
UTC+2
```

---

# 14. Timezone versus UTC Offset

Cette distinction est fondamentale.

```text
Timezone
──────────────
Europe/Paris
```

possède des règles historiques et calendaires.

Alors que :

```text
UTC Offset
──────────────
+02:00
```

n'est qu'une différence numérique avec UTC.

Ainsi :

```text
Europe/Paris
≠
UTC+02:00
```

sur l'ensemble de l'année.

---

# 15. Pourquoi ?

Parce que `Europe/Paris` peut utiliser selon la période :

```text
UTC+01:00
```

ou :

```text
UTC+02:00
```

Un offset fixe ne porte pas cette logique.

---

# 16. Invariant de PyScheduleKit

Une règle calendaire locale comme :

```text
Tous les jours à 08:00 Europe/Paris
```

doit conserver :

```text
Europe/Paris
```

comme intention métier.

Elle ne doit pas être transformée définitivement en :

```text
06:00 UTC
```

ou :

```text
07:00 UTC
```

car la correspondance change dans l'année.

---

# 17. Conversion LocalDateTime → Instant

Conceptuellement :

```text
LocalDateTime
      +
Timezone
      ↓
Timezone Resolution
      ↓
Instant
```

Mais cette opération n'est pas toujours triviale.

---

# 18. DST — Daylight Saving Time

Les règles de changement d'heure créent deux situations particulièrement importantes pour un scheduler :

```text
Nonexistent Local Time

Ambiguous Local Time
```

---

# 19. Heure locale inexistante

Lors d'un passage à l'heure d'été, l'horloge peut avancer.

Conceptuellement :

```text
01:59
  │
  ▼
03:00
```

La période :

```text
02:00 → 02:59
```

n'existe alors pas localement.

Une règle :

```text
Every day @ 02:30
```

rencontre une occurrence impossible.

---

# 20. Le scheduler doit choisir une politique

Quelques possibilités :

```text
SKIP

SHIFT_FORWARD

SHIFT_BACKWARD

USE_NEXT_VALID_TIME

FAIL
```

Cette décision ne doit pas être implicite.

---

# 21. Heure locale ambiguë

Lors du retour à l'heure d'hiver, une période peut se produire deux fois.

Conceptuellement :

```text
02:30
 ↓
...
 ↓
02:30
```

La valeur :

```text
2026-XX-XX 02:30 Europe/Paris
```

peut donc correspondre à deux instants.

---

# 22. Politique d'ambiguïté

PyScheduleKit devra pouvoir définir explicitement :

```text
FIRST

SECOND

EARLIER_OFFSET

LATER_OFFSET

FAIL
```

ou une abstraction équivalente.

---

# 23. DSTResolutionPolicy

Une abstraction potentielle :

```text
DSTResolutionPolicy
```

pourrait définir :

```text
NonexistentTimePolicy
AmbiguousTimePolicy
```

Exemple :

```text
DSTResolutionPolicy(
    nonexistent=SHIFT_FORWARD,
    ambiguous=EARLIER
)
```

---

# 24. Pourquoi cette policy appartient au domaine temporel

Elle détermine directement :

```text
quel Instant correspond à une intention locale
```

Elle doit donc être définie avant l'exécution.

---

# 25. UTC

UTC joue un rôle central comme référence absolue.

Une stratégie raisonnable consiste à :

```text
exprimer les intentions calendaires
dans leur timezone métier

↓

résoudre chaque occurrence

↓

représenter l'instant obtenu
en UTC pour le runtime
```

Ainsi :

```text
Intent
Every day 08:00 Europe/Paris
```

reste locale.

Mais :

```text
Occurrence.scheduled_at
```

peut être stockée comme `Instant`.

---

# 26. Modèle recommandé

```text
Schedule
│
├── Local rule
│     08:00
│
├── Timezone
│     Europe/Paris
│
└── Trigger
      │
      ▼
Timezone Resolution
      │
      ▼
Occurrence
scheduled_at = Instant
```

---

# 27. Duration

Une `Duration` représente une quantité de temps.

Exemple :

```text
5 minutes
30 seconds
2 hours
```

Classification :

```text
Duration
=
Value Object
```

---

# 28. Duration n'est pas une date

```text
5 minutes
```

ne dit pas :

```text
quand
```

mais :

```text
combien de temps
```

C'est une distinction fondamentale.

---

# 29. Duration et arithmetic temporelle

Exemple :

```text
Instant
08:00
+
Duration
5 minutes
=
08:05
```

Cela permet de calculer :

```text
deadline
retry_at
lease expiration
```

---

# 30. Duration versus Calendar Period

Attention à :

```text
24 hours
```

et :

```text
1 calendar day
```

qui ne sont pas nécessairement équivalents autour d'un changement d'heure.

Exemple conceptuel :

```text
08:00 Monday
+ 24 hours
```

peut différer de :

```text
08:00 next local day
```

selon les règles temporelles.

---

# 31. Period

Un futur objet :

```text
Period
```

pourrait représenter des quantités calendaires comme :

```text
1 day
1 month
1 year
```

dans une logique civile.

Alors que :

```text
Duration
```

représente une quantité temporelle absolue.

---

# 32. Distinction

```text
Duration
────────────
3600 seconds

Period
────────────
1 calendar hour / day / month
```

Cette distinction devient surtout importante pour :

```text
months
years
DST
```

---

# 33. Clock

Le `Clock` est l'abstraction par laquelle le domaine obtient le temps courant.

Interface conceptuelle :

```text
Clock.now()
    ↓
Instant
```

---

# 34. Pourquoi Clock est indispensable

Sans abstraction :

```python
datetime.now()
```

peut apparaître dans :

```text
Trigger
Scheduler
Policy
Execution
Retry
Lease
```

Le temps devient alors une dépendance globale invisible.

---

# 35. Avec Clock

```text
SchedulerEngine
      │
      ▼
     Clock
      │
      ▼
    Instant
```

Le temps devient explicite et injectable.

---

# 36. Clock comme Port

Dans notre classification DDD :

```text
Clock
=
Port
```

Le domaine définit :

```text
now()
```

L'infrastructure fournit l'implémentation.

---

# 37. SystemClock

```text
SystemClock
=
Infrastructure Adapter
```

Il interroge l'horloge réelle du système.

---

# 38. FixedClock

Pour les tests :

```text
FixedClock
```

retourne toujours le même instant.

Exemple :

```text
now()
→ 2026-10-04T06:00Z
```

---

# 39. MutableClock

Pour les simulations :

```text
MutableClock
```

permet :

```text
clock.advance(5 minutes)
```

Exemple :

```text
08:00
 ↓ advance 5m
08:05
```

---

# 40. Pourquoi MutableClock est pédagogiquement puissant

On peut tester :

```text
le passage d'une occurrence à DUE
les misfires
les deadlines
les retries
les expirations de leases
```

sans réellement attendre.

---

# 41. Simulation

Exemple conceptuel :

```text
clock = MutableClock(08:00)

next occurrence = 08:05

clock.advance(4 min)
→ not due

clock.advance(1 min)
→ due
```

Cela permet de comprendre le domaine directement.

---

# 42. Wall Clock

Une `WallClock` représente l'heure civile actuelle.

Elle répond à :

> Quelle date et quelle heure sont actuellement affichées dans le monde civil ?

Elle peut être affectée par :

```text
synchronisation NTP
ajustement manuel
DST
correction système
```

---

# 43. Monotonic Clock

Une horloge monotone mesure une progression continue.

Elle répond davantage à :

> Combien de temps s'est écoulé ?

Elle est adaptée à :

```text
timeouts
durations
elapsed time
backoff
performance measurements
```

---

# 44. Distinction fondamentale

```text
Wall Clock
→ What time is it?

Monotonic Clock
→ How much time has elapsed?
```

---

# 45. Pourquoi ne pas utiliser Wall Clock pour tout

Supposons que l'horloge système soit corrigée :

```text
10:00:05
 ↓
09:59:58
```

Un calcul de durée basé naïvement dessus pourrait devenir incohérent.

Une horloge monotone évite ce problème pour les durées.

---

# 46. Usage recommandé

```text
Cron / Calendar scheduling
→ Wall Clock / Instant

Timeout
→ Monotonic time

Execution duration
→ Monotonic time preferred

Human timestamps
→ Wall Clock / Instant
```

---

# 47. Clock abstrait versus deux clocks

PyScheduleKit pourrait exposer :

```text
Clock
```

pour le domaine principal

et éventuellement :

```text
MonotonicClock
```

pour les mécanismes runtime.

Cela évite de mélanger deux sémantiques.

---

# 48. CurrentTime

Un `CurrentTime` peut simplement être :

```text
Instant
```

obtenu une seule fois au début d'une évaluation.

Exemple :

```text
now = clock.now()
```

Puis toute la décision utilise ce même `now`.

---

# 49. Pourquoi ?

Éviter :

```text
policy #1 calls now()
policy #2 calls now()
policy #3 calls now()
```

et obtienne trois valeurs différentes.

Préférer :

```text
EvaluationContext(
    now=clock.now()
)
```

---

# 50. Déterminisme

Avec cette approche :

```text
same Schedule
+
same Occurrence
+
same now
+
same runtime snapshot
=
same SchedulingDecision
```

C'est une propriété extrêmement importante.

---

# 51. Calendar

Un `Calendar` représente les règles déterminant quelles dates ou périodes sont autorisées ou exclues.

Exemple :

```text
Monday
→ allowed

Sunday
→ excluded
```

---

# 52. Calendar versus Trigger

Le Trigger répond :

> Quelle serait la prochaine occurrence selon la règle de récurrence ?

Le Calendar répond :

> Cette occurrence est-elle admissible ?

Conceptuellement :

```text
Trigger
  ↓
Candidate Occurrence
  ↓
Calendar
  ↓
Valid Occurrence
```

---

# 53. Exemple

Schedule :

```text
Every day @ 08:00
```

Calendar :

```text
Monday → Friday only
```

Le trigger produit potentiellement :

```text
Saturday 08:00
```

Le calendrier peut alors :

```text
exclude
```

cette occurrence.

---

# 54. Deux architectures possibles

## Approche A — Trigger calendar-aware

```text
Trigger
+
Calendar
→ next valid occurrence
```

## Approche B — séparation

```text
Trigger
→ candidate occurrence

Calendar
→ validates candidate
```

---

# 55. Recommandation

Pour garder les responsabilités lisibles :

```text
Trigger
→ produit des candidats temporels

Calendar
→ applique des contraintes calendaires
```

Puis un composant de planification coordonne les deux.

---

# 56. Calendar Rule

Une `CalendarRule` peut être un Value Object ou une Policy.

Exemples :

```text
WeekdayRule
ExcludedDateRule
AllowedHoursRule
HolidayRule
```

---

# 57. Composite Calendar

Un calendrier peut être composé :

```text
BusinessCalendar
│
├── MondayToFriday
├── ExcludePublicHolidays
├── ExcludeCompanyClosures
└── AllowedHours(08:00, 18:00)
```

---

# 58. Composition logique

On peut imaginer :

```text
AND

OR

NOT
```

entre règles calendaires.

Exemple :

```text
Weekday
AND
NOT Holiday
AND
BusinessHours
```

---

# 59. Calendar comme objet métier

Un calendrier ne doit pas être réduit à :

```text
list[date]
```

Il représente une logique permettant de répondre :

```text
is_allowed(date)?
```

et éventuellement :

```text
next_allowed_after(date)?
```

---

# 60. BusinessCalendar

Un `BusinessCalendar` ajoute des concepts métiers.

Exemple :

```text
FrenchBusinessCalendar
```

peut représenter :

```text
jours ouvrés
jours fériés
fermetures spécifiques
```

---

# 61. Cas d'utilisation

Exemple :

> Exécuter le traitement le premier jour ouvré du mois à 07:00.

Cela nécessite :

```text
calendar month
+
working-day rules
+
timezone
+
local time
```

Cron seul ne décrit pas naturellement toute cette sémantique.

---

# 62. CalendarId / CalendarRef

Lorsqu'un calendrier est partagé :

```text
CalendarRef("fr-business-days")
```

peut être stocké dans le Schedule.

Classification :

```text
CalendarRef
=
Value Object
```

---

# 63. CalendarProvider

Si le calendrier dépend de données externes :

```text
CalendarProvider
=
Port
```

Exemple :

```text
calendar_provider.resolve(
    CalendarRef("fr-business-days")
)
```

---

# 64. Pourquoi un Provider ?

Pour ne pas faire dépendre le domaine directement de :

```text
database
HTTP API
holiday library
external SaaS
```

---

# 65. Calendar Snapshot

Pour garantir le déterminisme, une question importante apparaît.

Supposons :

```text
Occurrence historique
2026-12-24
```

et le calendrier métier est modifié plus tard.

Comment expliquer l'ancienne décision ?

Une solution possible :

```text
CalendarVersion
```

ou :

```text
CalendarSnapshotRef
```

---

# 66. CalendarVersion

Un calendrier évolutif peut avoir :

```text
calendar_ref
calendar_revision
```

Cette notion est surtout importante pour :

```text
audit
replay
historical interpretation
```

---

# 67. Working Day

Un `WorkingDay` n'est pas simplement :

```text
Monday-Friday
```

car il peut dépendre de :

```text
pays
secteur
entreprise
marché financier
convention métier
```

Le framework ne doit pas imposer une définition universelle.

---

# 68. Holiday

Même principe.

Un jour férié est une donnée métier contextuelle.

PyScheduleKit doit fournir des abstractions permettant de l'utiliser, pas une vérité mondiale codée en dur.

---

# 69. TimeWindow

Une `TimeWindow` représente une plage temporelle.

Exemple :

```text
08:00 ───────────────── 18:00
```

Elle possède :

```text
start
end
```

---

# 70. TimeWindow comme Value Object

```text
TimeWindow
=
Value Object
```

Invariant :

```text
start <= end
```

selon la sémantique choisie.

---

# 71. Interval boundary semantics

Il faut préciser si la fenêtre est :

```text
[start, end]

[start, end)

(start, end]

(start, end)
```

La forme recommandée pour les intervalles techniques est souvent :

```text
[start, end)
```

c'est-à-dire :

```text
start inclus
end exclu
```

---

# 72. Pourquoi ?

Cela facilite la composition :

```text
08:00 → 09:00
09:00 → 10:00
```

sans chevauchement de frontière.

---

# 73. ScheduleWindow

Un `ScheduleWindow` représente les limites globales d'activité d'un schedule.

Exemple :

```text
start_at = 2026-10-01
end_at   = 2026-12-31
```

Le trigger ne doit rien produire en dehors.

---

# 74. ExecutionWindow

Une `ExecutionWindow` décrit la période durant laquelle une occurrence reste acceptable.

Par exemple :

```text
scheduled_at = 08:00
grace_period = 5m
```

donne :

```text
08:00 ───────────── 08:05
```

---

# 75. GracePeriod

Une `GracePeriod` est une durée de tolérance.

```text
GracePeriod(5 minutes)
```

---

# 76. GracePeriod versus Deadline

```text
GracePeriod
=
Duration
```

alors que :

```text
Deadline
=
Instant
```

Relation :

```text
Deadline
=
ScheduledAt
+
GracePeriod
```

---

# 77. Exemple

```text
scheduled_at = 08:00
grace_period = 5 min

deadline = 08:05
```

À :

```text
08:03
```

l'occurrence peut rester admissible.

À :

```text
08:15
```

elle peut devenir misfire.

---

# 78. Deadline

`Deadline` est un Value Object représentant un instant limite.

Comportement :

```text
deadline.has_passed(now)
```

---

# 79. Deadline inclusive ou exclusive

Le domaine devra décider :

```text
now == deadline
```

est-il :

```text
VALID
```

ou :

```text
EXPIRED
```

Une convention doit être stable.

---

# 80. Recommandation

Utiliser généralement :

```text
valid while now <= deadline
```

ou l'inverse selon le contrat documenté.

L'important est d'éviter l'ambiguïté.

---

# 81. BlackoutWindow

Une `BlackoutWindow` représente une période pendant laquelle les exécutions sont interdites.

Exemple :

```text
02:00 → 03:00
```

pour une maintenance.

---

# 82. AllowedWindow

À l'inverse :

```text
AllowedWindow
08:00 → 18:00
```

peut limiter les exécutions.

---

# 83. SchedulingWindow versus ExecutionWindow

Distinction utile :

```text
SchedulingWindow
→ quand une occurrence peut être prévue

ExecutionWindow
→ quand une occurrence prévue peut effectivement être exécutée
```

Ces concepts peuvent parfois être identiques, mais pas nécessairement.

---

# 84. Recurrence et temps

Une récurrence transforme une règle en suite d'occurrences.

Conceptuellement :

```text
R =
{
 t1,
 t2,
 t3,
 ...
}
```

Le modèle temporel doit garantir :

```text
t[n+1] > t[n]
```

pour une recurrence normale.

---

# 85. Invariant monotone des occurrences

Un trigger ne doit normalement pas produire :

```text
10:00
09:00
11:00
```

pour des appels successifs.

L'invariant est :

```text
next > previous
```

sauf modèle explicitement différent.

---

# 86. Cron et temps local

Une expression comme :

```text
0 8 * * *
```

ne suffit pas à déterminer les instants.

Il faut :

```text
CronExpression
+
Timezone
```

---

# 87. Exemple

```text
CronExpression
0 8 * * *

Timezone
Europe/Paris
```

produit des heures locales :

```text
08:00
08:00
08:00
...
```

mais les instants UTC associés peuvent varier avec DST.

---

# 88. Interval et Instant

Pour un intervalle fixe :

```text
every 5 minutes
```

on peut calculer :

```text
previous_instant
+
Duration(5m)
```

Ce modèle est très différent d'une règle calendaire.

---

# 89. Calendar recurrence versus duration recurrence

```text
Every 24 hours
```

n'est pas nécessairement identique à :

```text
Every day at 08:00 local time
```

Cette distinction doit être explicite.

---

# 90. Exemple DST

```text
Every 24 hours
```

vise une distance temporelle constante.

Alors que :

```text
Every day at 08:00 Europe/Paris
```

vise une heure civile constante.

---

# 91. Fixed Rate

En `FixedRate` :

```text
t(n+1) = t(n) + interval
```

indépendamment des executions.

---

# 92. Fixed Delay

En `FixedDelay` :

```text
next =
previous_execution_finished_at
+
delay
```

Ce comportement dépend du runtime.

---

# 93. Conséquence conceptuelle

`FixedDelay` n'est pas un pur trigger temporel autonome comme un cron.

Il dépend de :

```text
ExecutionCompletion
```

Cela devra être clairement distingué dans le modèle des triggers.

---

# 94. Temporal Anchor

Un interval trigger a besoin d'un point de référence.

On peut appeler ce concept :

```text
TemporalAnchor
```

Exemple :

```text
start_at = 10:00
interval = 5 min
```

donne :

```text
10:00
10:05
10:10
...
```

---

# 95. Anchor comme Value Object

```text
TemporalAnchor
=
Instant
```

ou abstraction plus riche si nécessaire.

Il ne faut pas introduire un nouvel objet sans besoin.

---

# 96. « Dans 10 minutes »

Cette expression représente :

```text
now
+
Duration(10 min)
```

Elle doit normalement être résolue au moment où le schedule ponctuel est créé.

Exemple :

```text
request at 08:00
→ DateTrigger(08:10)
```

---

# 97. Pourquoi ne pas stocker « in 10 minutes » indéfiniment ?

Parce qu'après redémarrage :

```text
10 minutes from when?
```

devient ambigu.

Il est préférable de transformer l'intention relative en :

```text
Instant
```

au moment approprié.

---

# 98. RelativeSchedule

Un futur modèle peut malgré tout distinguer les expressions relatives au niveau API.

Mais le domaine durable devrait généralement travailler avec l'instant résolu.

---

# 99. Date arithmetic

Les opérations temporelles doivent être explicites.

Exemples :

```text
Instant + Duration

LocalDate + Period

LocalDateTime + Timezone → Instant
```

Éviter de mélanger silencieusement ces catégories.

---

# 100. Precision

Il faut décider de la précision temporelle du framework.

Exemples :

```text
minute
second
millisecond
microsecond
```

---

# 101. Recommandation

Le domaine ne devrait pas être limité artificiellement à la minute comme cron historique.

Une représentation d'Instant suffisamment précise peut être conservée.

Les différents triggers peuvent imposer leur propre granularité.

---

# 102. Scheduler Accuracy

La précision représentable n'est pas équivalente à la précision garantie.

PyScheduleKit peut représenter :

```text
08:00:00.123456
```

sans garantir :

```text
execution starts exactly at 08:00:00.123456
```

---

# 103. Distinction

```text
Temporal precision
≠
Execution accuracy
```

Le scheduler détermine une échéance.

Le runtime introduit une latence.

---

# 104. Scheduling Lag

```text
SchedulingLag
=
triggered_at - scheduled_at
```

Il mesure la différence entre :

```text
intention temporelle
```

et :

```text
décision réelle
```

---

# 105. Clock Skew

Dans un système distribué, deux nodes peuvent avoir :

```text
Node A
08:00:01

Node B
07:59:58
```

Cela constitue un :

```text
ClockSkew
```

---

# 106. Pourquoi c'est important

Le skew peut influencer :

```text
due detection
lease expiry
deadline evaluation
event ordering
```

---

# 107. Source of Time

Dans un système distribué, il faut décider :

```text
quelle horloge fait autorité ?
```

Possibilités :

```text
local system clocks

database time

central time service

consensus-based timestamp
```

PyScheduleKit ne doit probablement pas imposer cette architecture dans son domaine pur.

---

# 108. TimeSource Port

Une abstraction avancée pourrait distinguer :

```text
Clock
```

de :

```text
AuthoritativeTimeSource
```

Mais cela serait prématuré dans les premières versions.

---

# 109. Scheduling Evaluation Context

Le temps peut être injecté dans un objet :

```text
SchedulingEvaluationContext
```

contenant :

```text
now
calendar
active executions
schedule state
```

---

# 110. Règle importante

Tous les calculs d'une même évaluation doivent utiliser :

```text
le même `now`
```

pour éviter les incohérences internes.

---

# 111. Exemple

Mauvais :

```text
check deadline at 08:04:59

...

check misfire at 08:05:01
```

avec deux lectures différentes.

Bon :

```text
evaluation_now = 08:04:59

toutes les policies utilisent cette valeur
```

---

# 112. Temporal determinism

Le domaine doit viser :

```text
Input temporel explicite
      +
État explicite
      ↓
Décision reproductible
```

C'est une propriété clé de PyScheduleKit.

---

# 113. Temporal serialization

Lors de la persistance :

```text
Instant
```

doit être sérialisé sans ambiguïté.

Une forme logique est :

```text
ISO 8601
+
timezone offset / UTC
```

Exemple :

```text
2026-10-04T06:00:00Z
```

---

# 114. Timezone serialization

Pour une timezone métier :

```text
Europe/Paris
```

doit être conservé.

Ne pas stocker uniquement :

```text
+02:00
```

---

# 115. Pourquoi conserver les deux informations

Un Schedule peut avoir :

```text
timezone = Europe/Paris
```

alors qu'une Occurrence contient :

```text
scheduled_at = absolute Instant
```

Cette séparation conserve :

```text
l'intention
+
le résultat du calcul
```

---

# 116. Exemple persistant

```text
SCHEDULE
timezone = Europe/Paris
cron = 0 8 * * *

OCCURRENCE
scheduled_at = 2026-10-04T06:00:00Z
```

On peut toujours expliquer :

```text
pourquoi cet instant correspondait à 08:00 local
```

---

# 117. Historical timezone rules

Les règles timezone peuvent évoluer historiquement.

Pour une reproductibilité parfaite à très long terme, la version de la base timezone utilisée pourrait théoriquement compter.

Mais ce niveau de complexité ne doit pas être introduit prématurément.

---

# 118. Timezone Database

L'implémentation devra s'appuyer sur une source reconnue de règles temporelles, typiquement la base IANA via les mécanismes standards disponibles en Python.

Le domaine, lui, manipule simplement :

```text
Timezone
```

---

# 119. Local schedule example

Besoin :

> Chaque lundi à 08:00 heure de Paris.

Modèle :

```text
Schedule
│
├── Trigger
│     weekly Monday @ 08:00
│
└── Timezone
      Europe/Paris
```

---

# 120. Calcul

```text
Local candidate
Monday 08:00
      │
      ▼
Timezone resolution
      │
      ▼
Instant
      │
      ▼
Occurrence
```

---

# 121. Business calendar example

Besoin :

> Chaque premier jour ouvré du mois à 07:00.

Modèle :

```text
Monthly Rule
     │
     ▼
Candidate Date
     │
     ▼
BusinessCalendar
     │
     ▼
First valid working day
     │
     +
LocalTime 07:00
     │
     +
Timezone
     │
     ▼
Instant
```

---

# 122. Blackout example

Besoin :

> Exécuter toutes les heures, sauf entre 02:00 et 04:00.

Deux options :

```text
Trigger
+
BlackoutCalendar
```

ou :

```text
Composite Trigger
```

La première maintient mieux la séparation des responsabilités.

---

# 123. Calendar inclusion versus exclusion

Un calendrier peut fonctionner en :

```text
ALLOWLIST
```

ou :

```text
DENYLIST
```

Exemple :

```text
allow Monday-Friday
```

versus :

```text
exclude Saturday-Sunday
```

Ces deux modèles ne sont pas toujours strictement équivalents lorsqu'on ajoute des exceptions.

---

# 124. Calendar precedence

Si plusieurs règles sont combinées :

```text
WorkingDay
Holiday
SpecialOpening
CompanyClosure
```

il faut définir leur priorité.

Exemple :

```text
SpecialOpening
may override Holiday
```

ou non.

Cette logique appartient au BusinessCalendar.

---

# 125. CalendarDecision

Une réponse plus expressive que `bool` peut être utile :

```text
CalendarDecision(
    allowed=False,
    reason=PUBLIC_HOLIDAY
)
```

Cela améliore :

```text
audit
debug
observability
```

---

# 126. CalendarDecision comme Value Object

```text
CalendarDecision
=
Value Object
```

Il peut contenir :

```text
allowed
reason
rule
```

---

# 127. TimezoneResolutionResult

De même, une résolution locale peut produire :

```text
RESOLVED
AMBIGUOUS
NONEXISTENT
```

au lieu de lancer immédiatement une exception opaque.

---

# 128. TemporalError

Les erreurs temporelles peuvent être structurées.

Exemples :

```text
InvalidTimezone
AmbiguousLocalTime
NonexistentLocalTime
InvalidTimeWindow
NegativeDuration
InvalidCalendarRule
```

---

# 129. Pourquoi ?

Parce que :

```text
"datetime error"
```

ne décrit pas suffisamment le problème métier.

---

# 130. Modèle DDD proposé

```text
Temporal Value Objects
────────────────────────

Instant
LocalDate
LocalTime
LocalDateTime
Timezone
UtcOffset
Duration
Period
TimeWindow
ScheduleWindow
GracePeriod
Deadline
CalendarRef
```

---

# 131. Temporal Policies

```text
DSTResolutionPolicy
CalendarPolicy
JitterPolicy
```

et éventuellement :

```text
DeadlinePolicy
```

si nécessaire.

---

# 132. Temporal Ports

```text
Clock
MonotonicClock
CalendarProvider
```

---

# 133. Temporal Domain Services

Éventuellement :

```text
TimezoneResolver
CalendarEvaluator
```

si les comportements deviennent suffisamment complexes pour ne pas tenir naturellement dans les Value Objects.

---

# 134. Mais éviter la surmodélisation

Il ne faut pas nécessairement créer :

```text
InstantService
DurationService
TimezoneService
TimeWindowService
```

Les Value Objects peuvent porter leurs comportements naturels.

---

# 135. Exemple de comportement riche

```text
TimeWindow.contains(instant)

GracePeriod.deadline_for(scheduled_at)

Deadline.is_expired(now)

Calendar.allows(local_date)

Timezone.resolve(local_datetime)
```

---

# 136. Modèle conceptuel

```text
                      Schedule
                         │
               ┌─────────┴─────────┐
               │                   │
               ▼                   ▼
            Trigger             Timezone
               │                   │
               │                   │
               ▼                   │
       Local Candidate Time ◀──────┘
               │
               ▼
       Timezone Resolution
               │
               ▼
            Instant
               │
               ▼
           Occurrence
               │
               ▼
            Calendar
               │
               ▼
         Valid Occurrence
               │
               ▼
          GracePeriod
               │
               ▼
            Deadline
               │
               ▼
      Scheduling Evaluation
```

L'ordre exact `Trigger ↔ Calendar` pourra varier selon la règle, mais les responsabilités restent séparées.

---

# 137. Variante plus précise

Pour certaines règles :

```text
Trigger Rule
    │
    ▼
Local Candidate
    │
    ▼
Calendar Rules
    │
    ▼
Valid Local Candidate
    │
    ▼
Timezone Resolution
    │
    ▼
Instant
    │
    ▼
Occurrence
```

Cette approche peut être plus naturelle pour les calendriers métier locaux.

---

# 138. Question de design importante

Le Calendar travaille-t-il sur :

```text
Instant
```

ou sur :

```text
LocalDate / LocalDateTime
```

?

Réponse :

> Cela dépend de la nature de la règle.

Un calendrier métier comme :

```text
Monday-Friday
```

est principalement local.

Une blackout window technique peut être exprimée en instants absolus.

---

# 139. Recommandation

Prévoir deux niveaux :

```text
Local Calendar Rules

Absolute Time Windows
```

au lieu de tout forcer dans une seule abstraction.

---

# 140. LocalCalendar

Responsable de :

```text
weekdays
holidays
business dates
local opening hours
```

---

# 141. AbsoluteTimeWindow

Responsable de :

```text
maintenance window
system freeze
incident blackout
```

exprimés par des instants.

---

# 142. Temporal hierarchy

```text
Temporal Model
│
├── Absolute Time
│   ├── Instant
│   ├── Duration
│   ├── Deadline
│   └── AbsoluteTimeWindow
│
├── Civil Time
│   ├── LocalDate
│   ├── LocalTime
│   ├── LocalDateTime
│   └── Timezone
│
├── Calendar
│   ├── CalendarRule
│   ├── BusinessCalendar
│   └── CalendarRef
│
└── Time Sources
    ├── Clock
    └── MonotonicClock
```

---

# 143. Python mapping envisagé

Sans figer l'API :

```text
Instant
→ aware datetime / wrapper

LocalDate
→ date / wrapper

LocalTime
→ time / wrapper

Timezone
→ ZoneInfo-backed Value Object

Duration
→ timedelta-backed Value Object

Clock
→ Protocol
```

La représentation technique doit venir après la sémantique.

---

# 144. Règle Python fondamentale

Un datetime naïf :

```python
datetime(2026, 10, 4, 8, 0)
```

ne doit pas être utilisé comme `Instant`.

Il ne possède pas d'information suffisante de timezone.

---

# 145. Principe

Dans les frontières du domaine :

```text
naive datetime
=
local/civil value only
```

et non :

```text
absolute instant
```

---

# 146. Validation des timezones

Un Schedule déclarant :

```text
timezone = "Moon/Base1"
```

doit être rejeté à la création.

La timezone est un Value Object validé.

---

# 147. Validation des Durations

Exemple :

```text
GracePeriod(-5 minutes)
```

doit être impossible.

Même chose pour :

```text
LeaseDuration(0)
```

si le domaine exige une durée strictement positive.

---

# 148. Validation des fenêtres

```text
TimeWindow(
    start=18:00,
    end=08:00
)
```

est ambigu.

Cela peut signifier :

```text
invalid
```

ou :

```text
cross-midnight window
```

Il faut donc choisir explicitement.

---

# 149. Cross-midnight window

Une plage :

```text
22:00 → 06:00
```

peut être valide dans certains domaines.

Elle ne doit pas être interprétée automatiquement sans type adapté.

On pourrait introduire :

```text
DailyLocalTimeWindow
```

qui supporte explicitement ce comportement.

---

# 150. Calendar date versus rolling duration

Même problème avec :

```text
monthly
```

Un mois ne possède pas une durée constante.

Il faut donc éviter :

```text
1 month = 30 days
```

comme convention implicite.

---

# 151. Leap years

Les règles calendaires doivent également gérer :

```text
February 29
```

Exemple :

> Exécuter tous les 29 février.

La prochaine occurrence peut être plusieurs années plus tard.

---

# 152. Month-end semantics

Besoin :

> Le dernier jour du mois.

Cela signifie :

```text
Jan 31
Feb 28/29
Mar 31
Apr 30
...
```

et non :

```text
every 30 days
```

---

# 153. Business month-end

Besoin :

> Le dernier jour ouvré du mois.

Nécessite :

```text
Calendar Month End
+
BusinessCalendar
```

Encore une fois :

```text
Trigger
+
Calendar
```

sont complémentaires.

---

# 154. Time model and Misfire

Le misfire dépend directement du modèle temporel.

Exemple :

```text
scheduled_at
+
GracePeriod
=
Deadline
```

puis :

```text
Clock.now() > Deadline
```

peut provoquer :

```text
MISFIRE
```

---

# 155. Time model and Retry

Un retry produit :

```text
retry_at
```

calculé par :

```text
now
+
BackoffDuration
```

ou éventuellement depuis :

```text
attempt_finished_at
```

---

# 156. Time model and Lease

Une lease repose sur :

```text
acquired_at
+
lease_duration
=
expires_at
```

Le choix de l'horloge utilisée est particulièrement important.

---

# 157. Time model and Jitter

Le jitter peut produire :

```text
dispatch_not_before
```

sans modifier :

```text
scheduled_at
```

C'est la séparation recommandée.

---

# 158. ScheduledAt est sacré

Une fois qu'une occurrence existe :

```text
scheduled_at
```

représente l'intention temporelle originale.

Il ne devrait pas être réécrit simplement parce que :

```text
jitter
queue delay
retry
worker delay
```

ont déplacé l'exécution réelle.

---

# 159. Plusieurs timestamps

La chaîne de référence devient :

```text
scheduled_at
     ↓
triggered_at
     ↓
dispatched_at
     ↓
queued_at
     ↓
started_at
     ↓
finished_at
```

Chacun porte une sémantique distincte.

---

# 160. Exemple complet — Daily Orders

Besoin :

> Tous les jours à 06:00 heure de Paris, lancer `daily_orders_pipeline`, avec une tolérance de cinq minutes.

Modèle :

```text
Schedule
│
├── TargetRef
│     workflow:daily-orders
│
├── CronTrigger
│     0 6 * * *
│
├── Timezone
│     Europe/Paris
│
├── GracePeriod
│     5 minutes
│
└── Clock
      injected
```

---

# 161. Calcul d'une occurrence

```text
Cron rule
   │
   ▼
2026-10-05 06:00 local
   │
   +
Europe/Paris
   │
   ▼
Timezone resolution
   │
   ▼
Instant
   │
   ▼
Occurrence.scheduled_at
```

---

# 162. Evaluation

```text
Clock.now()
=
scheduled_at + 2 minutes
```

Donc :

```text
deadline
=
scheduled_at + 5 minutes
```

L'occurrence reste :

```text
eligible
```

sous réserve des autres policies.

---

# 163. À +10 minutes

```text
now
=
scheduled_at + 10 minutes
```

Le domaine détecte :

```text
deadline exceeded
```

et transmet la situation à :

```text
MisfirePolicy
```

---

# 164. Exemple — premier jour ouvré

Besoin :

> Le premier jour ouvré de chaque mois à 08:00 Europe/Paris.

Chaîne :

```text
Next Month
   ↓
Month Start
   ↓
BusinessCalendar
   ↓
First Working Date
   ↓
LocalTime(08:00)
   ↓
Timezone(Europe/Paris)
   ↓
Instant
   ↓
Occurrence
```

---

# 165. Exemple — after 10 minutes

Besoin :

> Lancer dans dix minutes.

```text
Clock.now()
   │
   +
Duration(10m)
   │
   ▼
Instant
   │
   ▼
DateTrigger
```

Le schedule devient ensuite absolu.

---

# 166. Exemple — maintenance

Besoin :

> Aucune nouvelle exécution entre 02:00 et 04:00 heure locale.

Modèle :

```text
LocalTimeWindow
02:00 → 04:00
        │
        ▼
Blackout Calendar Rule
```

---

# 167. Temporal invariants

Le sous-domaine doit protéger au minimum :

```text
1.
Instant est timezone-aware conceptuellement.

2.
Timezone ≠ UTC offset.

3.
Duration ne représente pas un calendrier civil.

4.
scheduled_at ne doit pas être réécrit par le runtime.

5.
Value Objects temporels sont immutables.

6.
start <= end pour les fenêtres absolues normales.

7.
GracePeriod >= 0.

8.
Les occurrences d'une recurrence normale progressent dans le temps.

9.
Une règle calendaire conserve sa timezone métier.

10.
Tous les calculs d'une décision utilisent le même `now`.
```

---

# 168. Anti-pattern : UTC partout comme modèle métier

Il est bon de stocker des instants en UTC.

Mais il est mauvais de remplacer :

```text
Every day @ 08:00 Europe/Paris
```

par :

```text
Every day @ 07:00 UTC
```

comme règle permanente.

On perd l'intention métier.

---

# 169. Anti-pattern : naive datetime

Éviter :

```python
scheduled_at = datetime.now()
```

sans timezone ni abstraction Clock.

---

# 170. Anti-pattern : un timestamp unique

Éviter :

```text
execution_time
```

pour tout représenter.

Préférer :

```text
scheduled_at
triggered_at
started_at
finished_at
```

---

# 171. Anti-pattern : 1 day = 24 hours

Ce raccourci n'est pas toujours correct pour les règles civiles locales.

---

# 172. Anti-pattern : timezone = offset

Éviter :

```text
timezone = +02:00
```

lorsque l'intention est :

```text
Europe/Paris
```

---

# 173. Anti-pattern : Calendar dans CronTrigger

Éviter que `CronTrigger` accumule :

```text
jours ouvrés
jours fériés
fermetures
vacances
règles bancaires
```

jusqu'à devenir un moteur calendaire complet.

---

# 174. Anti-pattern : temps global implicite

Éviter :

```text
datetime.now()
time.time()
```

dans toutes les classes.

Le temps doit être injecté là où il constitue une dépendance.

---

# 175. Anti-pattern : Clock comme singleton global

Même avec une abstraction Clock, un singleton global rend :

```text
tests
simulation
isolation
```

plus difficiles.

Préférer l'injection explicite.

---

# 176. Anti-pattern : modifier scheduled_at au retry

Un retry à :

```text
08:05
```

ne change pas une occurrence originellement planifiée à :

```text
08:00
```

Il ajoute :

```text
retry_at
```

ou un nouvel Attempt.

---

# 177. Anti-pattern : Calendar renvoie uniquement bool

Pour les cas complexes, un résultat explicable peut être préférable :

```text
allowed = false
reason = COMPANY_HOLIDAY
```

---

# 178. Persistence model recommandé

Dans `Schedule` :

```text
timezone
trigger configuration
calendar_ref
start_at
end_at
grace period
```

Dans `Occurrence` ou `ExecutionRequest` :

```text
scheduled_at as Instant
schedule_revision
```

---

# 179. Ne pas persister inutilement

Les Value Objects comme :

```text
Deadline
```

peuvent être dérivés de :

```text
scheduled_at
+
grace_period
```

et ne nécessitent pas forcément un champ dédié.

---

# 180. Mais persister lorsque cela aide l'audit

Dans certains systèmes :

```text
resolved_deadline
resolved_timezone_offset
```

peuvent être conservés à titre d'évidence.

Il faudra distinguer :

```text
source of truth
```

de :

```text
audit snapshot
```

---

# 181. Test matrix temporelle minimale

Les tests devront couvrir :

```text
Instant comparison

timezone conversion

DST nonexistent time

DST ambiguous time

leap year

month end

business day

holiday exclusion

grace period boundary

deadline boundary

cross-midnight windows

fixed interval

calendar recurrence

clock advancement
```

---

# 182. Tests de simulation

Exemple :

```text
FixedClock
2026-10-04 05:59

Schedule
06:00

→ not due
```

Puis :

```text
clock.advance(1 minute)

→ due
```

---

# 183. Test DST

Construire explicitement un cas où :

```text
02:30 local
```

est :

```text
nonexistent
```

et vérifier la policy choisie.

---

# 184. Test calendar

```text
Saturday
+
WorkingDaysCalendar
→ excluded
```

---

# 185. Test deadline

```text
scheduled_at = 08:00
grace_period = 5m

now = 08:05
```

Le résultat doit être défini sans ambiguïté par le contrat.

---

# 186. Observabilité temporelle

Le scheduler doit pouvoir expliquer :

```text
timezone utilisée

heure locale demandée

instant résolu

règle DST appliquée

calendar rule appliquée

scheduled_at

deadline

current evaluation time

lag
```

---

# 187. Exemple d'explication

```text
Schedule: daily-orders

Rule:
Every day at 06:00

Timezone:
Europe/Paris

Resolved local time:
2026-10-05 06:00

Resolved instant:
2026-10-05T04:00:00Z

Evaluation time:
2026-10-05T04:00:03Z

Scheduling lag:
3 seconds
```

Ce niveau d'explicabilité est extrêmement utile en production.

---

# 188. Relation avec PyWorkflowKit

PyWorkflowKit ne doit pas recalculer :

```text
pourquoi le workflow devait commencer à 06:00
```

Il reçoit :

```text
scheduled_at
triggered_at
ExecutionContext
```

de PyScheduleKit.

---

# 189. Relation avec PyIngestKit

PyIngestKit peut recevoir :

```text
scheduled_at
```

pour savoir à quelle occurrence logique son ingestion correspond.

Exemple :

```text
partition_date
```

peut éventuellement être dérivée du contexte, mais la décision appartient au domaine d'ingestion.

---

# 190. Relation avec PyTransformKit

Même principe :

```text
TransformationRun
```

peut être corrélé à :

```text
OccurrenceKey
```

sans que PyTransformKit ne connaisse les règles de timezone ou de cron.

---

# 191. Time ownership

Règle d'architecture :

```text
PyScheduleKit
owns temporal scheduling semantics.
```

Les autres frameworks peuvent consommer :

```text
scheduled_at
correlation_id
```

mais ne doivent pas redéfinir la signification du schedule.

---

# 192. Première API conceptuelle

Sans figer encore Python :

```text
clock.now()
```

```text
timezone.resolve(local_datetime)
```

```text
calendar.allows(local_datetime)
```

```text
trigger.next_after(reference)
```

```text
grace_period.deadline_for(scheduled_at)
```

```text
window.contains(instant)
```

---

# 193. Value Objects envisagés

```text
Instant
LocalDate
LocalTime
LocalDateTime
Timezone
UtcOffset
Duration
Period
TimeWindow
ScheduleWindow
GracePeriod
Deadline
CalendarRef
OccurrenceKey
```

---

# 194. Policies envisagées

```text
DSTResolutionPolicy
JitterPolicy
CalendarCombinationPolicy
```

Les misfire et concurrency policies restent dans les autres sous-domaines.

---

# 195. Ports envisagés

```text
Clock
MonotonicClock
CalendarProvider
```

---

# 196. Adapters envisagés

```text
SystemClock
PythonMonotonicClock
ZoneInfoTimezoneResolver
InMemoryCalendarProvider
FileCalendarProvider
SQLCalendarProvider
```

Les noms techniques exacts seront définis lors de l'architecture.

---

# 197. Modèle simplifié à mémoriser

```text
        Human Time Intent
              │
              ▼
       LocalDate / Time
              │
              +
          Timezone
              │
              ▼
            Instant
              │
              ▼
          Occurrence
              │
              +
            Clock
              │
              ▼
      Scheduling Decision
```

et parallèlement :

```text
Candidate Date
     │
     ▼
   Calendar
     │
     ▼
Valid Date
```

---

# 198. Modèle complet à mémoriser

```text
                      TEMPORAL INTENT
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
       Recurrence Rule                Calendar Rules
             │                             │
             ▼                             ▼
        Local Candidate ───────────▶ Valid Candidate
                                           │
                                           ▼
                                        Timezone
                                           │
                                           ▼
                                         Instant
                                           │
                                           ▼
                                       Occurrence
                                           │
                       ┌───────────────────┼──────────────────┐
                       │                   │                  │
                       ▼                   ▼                  ▼
                     Clock            GracePeriod       TimeWindow
                       │                   │                  │
                       └──────────┬────────┴─────────┬────────┘
                                  │                  │
                                  ▼                  ▼
                             Evaluation          Deadline
                                  │
                                  ▼
                         SchedulingDecision
```

---

# 199. Décisions proposées pour PyScheduleKit

Pour la première ligne d'implémentation :

```text
1.
Tous les instants runtime sont timezone-aware.

2.
Les occurrences conservent un Instant absolu.

3.
Les schedules calendaires conservent une Timezone IANA.

4.
Clock est un Port obligatoire du SchedulerEngine.

5.
Les tests utilisent FixedClock / MutableClock.

6.
Les calendriers métier restent séparés des Triggers.

7.
GracePeriod est un Value Object basé sur Duration.

8.
Deadline est calculable depuis scheduled_at.

9.
scheduled_at reste immutable après matérialisation.

10.
Wall-clock scheduling et elapsed-time measurement restent distincts.
```

---

# 200. Questions ouvertes

Les points suivants devront encore être arbitrés :

```text
Le framework expose-t-il ses propres wrappers
Instant / Duration ou utilise-t-il directement
les types standards Python ?

DSTResolutionPolicy appartient-elle au Trigger
ou au Schedule ?

Calendar agit-il avant ou après la résolution timezone
selon les règles ?

Period est-il nécessaire dès V1 ?

FixedDelay appartient-il réellement au modèle Trigger ?

Les calendars doivent-ils être versionnés ?

Comment modéliser les fenêtres locales traversant minuit ?

Quelle précision temporelle minimale garantir ?

Quelle convention exacte pour les frontières de Deadline ?
```

---

# 201. Critères d'acceptation

Le modèle temporel sera considéré comme suffisamment défini lorsque PyScheduleKit pourra répondre sans ambiguïté à :

```text
Quelle différence entre Instant et LocalDateTime ?

Quelle différence entre Timezone et UTC offset ?

Que signifie "chaque jour à 08:00" ?

Que se passe-t-il pendant un changement d'heure ?

Comment simuler le temps dans un test ?

Comment représenter "dans 10 minutes" ?

Quelle différence entre 24 heures et un jour calendaire ?

Comment exclure les jours fériés ?

Comment représenter une plage d'exécution ?

Comment calculer une deadline ?

Quel timestamp représente l'intention originale ?

Quelle horloge utiliser pour un timeout ?

Quelle horloge utiliser pour une règle cron ?
```

---

# Conclusion

Le scheduling est impossible à modéliser correctement sans un langage temporel précis.

Les distinctions fondamentales sont :

```text
Instant
≠
LocalDateTime

Timezone
≠
UTC Offset

Duration
≠
Calendar Period

Wall Clock
≠
Monotonic Clock

Trigger
≠
Calendar

GracePeriod
≠
Deadline

scheduled_at
≠
started_at
```

Le modèle cible repose donc sur une idée centrale :

> **Une intention temporelle humaine ou métier doit être résolue explicitement en un instant précis avant de devenir une occurrence d'exécution.**

Le chemin principal devient :

```text
Temporal Rule
     │
     ▼
Local Candidate
     │
     +
Calendar
     │
     ▼
Valid Local Candidate
     │
     +
Timezone
     │
     ▼
Instant
     │
     ▼
Occurrence
     │
     +
Clock
Policies
Windows
     │
     ▼
SchedulingDecision
```

Cette séparation constitue le socle sur lequel pourront maintenant être modélisés précisément `Job`, `Schedule`, `Trigger` et leurs différentes formes de récurrence.

---

# Suite documentaire

La suite naturelle est :

```text
09_JOB_AND_SCHEDULE_MODEL.md
```

Ce document approfondira notamment :

```text
Job
Target
Schedule
ScheduleId
ScheduleState
ScheduleRevision
ScheduleWindow
TargetRef
Job vs Target
1 Job → N Schedules
pause / resume
cancel
reschedule
completion
```

Puis :

```text
10_TRIGGER_MODEL.md
```

pour isoler complètement la mécanique de production des occurrences temporelles.