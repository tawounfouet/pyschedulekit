# PyScheduleKit — Date, Interval & Cron Triggers

**Document :** `11_DATE_INTERVAL_AND_CRON_TRIGGERS.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle détaillé des triggers fondamentaux  
**Nature :** Domain Model — DateTrigger / IntervalTrigger / CronTrigger  
**Prérequis :**
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`
- `09_JOB_AND_SCHEDULE_MODEL.md`
- `10_TRIGGER_MODEL.md`

---

# 1. Objectif

PyScheduleKit retient trois formes fondamentales de Trigger pour sa première version :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

Ces trois objets semblent tous répondre à la même question :

> Quelle est la prochaine échéance ?

Mais ils modélisent en réalité trois intentions temporelles très différentes.

```text
DateTrigger
→ À cet instant précis.

IntervalTrigger
→ Toutes les N unités de durée.

CronTrigger
→ Lorsque le calendrier correspond à cette règle.
```

Cette distinction est essentielle.

Les expressions :

```text
dans 1 heure

toutes les heures

tous les jours à 08:00
```

ne décrivent pas la même sémantique.

---

# 2. Vue d'ensemble

```text
                     TRIGGER
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
     DateTrigger   IntervalTrigger  CronTrigger
          │             │             │
          ▼             ▼             ▼
     One-shot       Duration-based  Calendar-based
          │             │             │
          ▼             ▼             ▼
       Instant       Fixed Rate     Civil Time
```

---

# 3. Résumé comparatif

| Trigger | Question | Base temporelle | Récurrent | Timezone |
|---|---|---|---:|---:|
| `DateTrigger` | Quand exécuter une fois ? | Instant | Non | Non si Instant déjà résolu |
| `IntervalTrigger` | À quelle fréquence absolue ? | Duration | Oui | Généralement non |
| `CronTrigger` | Quand le calendrier correspond-il ? | Civil/Calendar Time | Oui | Oui |

---

# 4. Trois intentions différentes

## DateTrigger

```text
2026-10-15T08:00:00Z
```

signifie :

> Une occurrence unique à cet instant précis.

---

## IntervalTrigger

```text
anchor = 10:00
interval = 5 minutes
```

signifie :

> Produire des occurrences séparées exactement par cinq minutes.

---

## CronTrigger

```text
0 8 * * *
Europe/Paris
```

signifie :

> Produire une occurrence chaque jour lorsque l'heure civile locale atteint 08:00 à Paris.

---

# 5. Pourquoi cette distinction est fondamentale

Considérons :

```text
Every 24 hours
```

et :

```text
Every day at 08:00 Europe/Paris
```

Ils semblent similaires.

Mais autour d'un changement d'heure :

```text
Every 24 hours
```

conserve une distance temporelle absolue.

Alors que :

```text
Every day at 08:00
```

conserve l'heure civile locale.

Donc :

```text
IntervalTrigger(Duration(hours=24))
≠
CronTrigger("0 8 * * *", Europe/Paris)
```

---

# 6. DateTrigger — définition

`DateTrigger` représente une règle produisant au maximum une seule occurrence.

Conceptuellement :

```text
DateTrigger
      │
      ▼
scheduled_at
      │
      ▼
1 occurrence maximum
```

---

# 7. Intention métier du DateTrigger

Il répond à :

> À quel instant unique cette action doit-elle devenir exigible ?

Exemples :

```text
demain à 14:00

le 15 octobre 2026 à 08:00 UTC

dans dix minutes

à l'expiration d'un délai calculé
```

Une intention relative comme :

```text
dans dix minutes
```

devrait généralement être résolue lors de la création en :

```text
un Instant absolu
```

---

# 8. Modèle DateTrigger

Structure minimale :

```text
DateTrigger
│
└── scheduled_at: Instant
```

Classification :

```text
Value Object
immutable
stateless
finite
```

---

# 9. Contrat DateTrigger

Avec la convention :

```text
next_after(reference)
```

strictement exclusive :

```text
if scheduled_at > reference:
    return scheduled_at

return None
```

---

# 10. Exemple DateTrigger

```text
scheduled_at
=
2026-10-15T08:00:00Z
```

Alors :

```text
reference = Oct 14
→ Oct 15 08:00
```

mais :

```text
reference = Oct 15 08:00
→ None
```

et :

```text
reference = Oct 16
→ None
```

---

# 11. DateTrigger est naturellement fini

Il ne possède qu'une seule échéance.

On peut donc considérer :

```text
cardinality = 1
```

au maximum.

Une fois la date dépassée relativement au curseur d'évaluation :

```text
next_after(...)
→ None
```

---

# 12. DateTrigger ne devient pas « consommé »

Le Trigger lui-même reste immutable.

Il ne doit pas muter vers :

```text
USED
```

ou :

```text
COMPLETED
```

Exemple :

```text
trigger.next_after(yesterday)
```

peut toujours retourner sa date historique.

Le `Schedule`, lui, peut devenir `COMPLETED`.

---

# 13. DateTrigger absolu versus local

Deux formes d'entrée peuvent exister côté API utilisateur.

### Forme absolue

```text
2026-10-15T08:00:00Z
```

### Forme locale

```text
2026-10-15 10:00
Europe/Paris
```

Dans les deux cas, le domaine durable devrait idéalement obtenir :

```text
scheduled_at: Instant
```

---

# 14. Pourquoi résoudre l'heure locale

Parce que :

```text
2026-10-15 10:00
```

sans timezone n'est pas un instant universel.

La résolution devient :

```text
LocalDateTime
+
Timezone
↓
Instant
↓
DateTrigger
```

---

# 15. DateTrigger et DST

Une date locale peut être :

```text
ambiguous
```

ou :

```text
nonexistent
```

au moment de la création.

La `DSTResolutionPolicy` doit résoudre cette ambiguïté avant de produire l'Instant du DateTrigger.

---

# 16. DateTrigger — invariants

```text
1. scheduled_at est obligatoire.

2. scheduled_at représente un Instant valide.

3. Le Trigger est immutable.

4. next_after(r) retourne soit scheduled_at, soit None.

5. Le Trigger ne produit jamais plus d'une occurrence.

6. Le Trigger ne lit jamais Clock.now() directement.
```

---

# 17. DateTrigger — cas d'usage

```text
reminder ponctuel

exécution différée

expiration future

release planifiée

traitement unique

action calculée depuis un événement
```

---

# 18. Exemple « dans 30 minutes »

À :

```text
now = 10:00
```

l'utilisateur demande :

```text
dans 30 minutes
```

L'application résout :

```text
10:00
+
30 min
=
10:30
```

puis construit :

```text
DateTrigger(10:30)
```

---

# 19. Pourquoi ne pas conserver `delay=30m`

Après redémarrage, une valeur :

```text
delay = 30 minutes
```

pose :

> trente minutes à partir de quand ?

L'Instant résolu évite cette ambiguïté.

---

# 20. IntervalTrigger — définition

`IntervalTrigger` produit une série d'occurrences espacées par une `Duration` fixe.

Exemple :

```text
anchor = 10:00
interval = 5 min
```

donne :

```text
10:00
10:05
10:10
10:15
...
```

---

# 21. Intention métier

Il répond à :

> À quelle fréquence temporelle absolue cette occurrence doit-elle revenir ?

Le mot important est :

```text
Duration
```

---

# 22. Modèle IntervalTrigger

```text
IntervalTrigger
│
├── anchor: Instant
└── interval: Duration
```

Optionnellement :

```text
end_at
```

peut borner la série.

---

# 23. Classification

```text
IntervalTrigger
=
Value Object
immutable
stateless
duration-based
```

---

# 24. Anchor

L'`anchor` représente l'origine mathématique de la séquence.

```text
Occurrence(n)
=
anchor + n × interval
```

pour :

```text
n >= 0
```

---

# 25. Pourquoi l'anchor est indispensable

Sans anchor :

```text
every 5 minutes
```

reste ambigu.

Cela peut vouloir dire :

```text
depuis la création du Schedule
```

ou :

```text
aux minutes 00,05,10...
```

ou :

```text
depuis la dernière execution
```

Le domaine doit être explicite.

---

# 26. Invariant Interval

```text
interval > 0
```

Un intervalle :

```text
0
```

créerait une infinité d'occurrences au même instant.

Un intervalle négatif ferait régresser le temps.

Les deux sont invalides.

---

# 27. Fixed Rate

PyScheduleKit V1 retient pour `IntervalTrigger` une sémantique :

```text
FIXED RATE
```

La séquence dépend uniquement de :

```text
anchor
+
interval
```

---

# 28. Exemple Fixed Rate

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
```

Supposons que le run de 10:00 dure jusqu'à :

```text
10:08
```

L'occurrence suivante reste :

```text
10:05
```

même si elle chevauche la précédente.

La gestion de ce chevauchement appartient à :

```text
ConcurrencyPolicy
```

---

# 29. Fixed Rate ≠ Fixed Delay

En fixed delay :

```text
run starts 10:00
run finishes 10:08
delay = 5m
next = 10:13
```

La prochaine échéance dépend donc de :

```text
execution.finished_at
```

Ce n'est plus une pure règle temporelle indépendante du runtime.

---

# 30. Décision V1

```text
IntervalTrigger
=
Fixed Rate only
```

Le fixed delay reste hors scope de ce Trigger.

---

# 31. Pourquoi séparer Fixed Delay

Cela protège l'invariant :

```text
Trigger evaluation
does not depend on Execution state
```

et conserve le Trigger :

```text
stateless
pure
deterministic
```

---

# 32. Calcul mathématique

On cherche le plus petit entier `n` tel que :

```text
anchor + n × interval > reference
```

Cela permet d'éviter de parcourir toutes les occurrences intermédiaires.

---

# 33. Exemple

```text
anchor = 10:00
interval = 5m
reference = 10:12
```

La prochaine occurrence est :

```text
10:15
```

sans avoir besoin de recalculer séquentiellement :

```text
10:00
10:05
10:10
10:15
```

---

# 34. Cas reference avant anchor

```text
anchor = 10:00
reference = 09:00
```

Alors :

```text
next_after(reference)
→ 10:00
```

---

# 35. Cas reference exactement sur tick

```text
reference = 10:10
```

avec contrat strictement exclusif :

```text
next_after(10:10)
→ 10:15
```

---

# 36. Trigger borné

On peut vouloir :

```text
anchor = 10:00
interval = 5m
end_at = 11:00
```

Deux modèles sont possibles.

### Trigger owns end boundary

ou :

### ScheduleWindow owns end boundary

---

# 37. Recommandation

Préférer :

```text
ScheduleWindow
```

comme borne métier globale.

Le Trigger reste défini par :

```text
anchor
+
interval
```

---

# 38. IntervalTrigger et timezone

Un IntervalTrigger basé sur des `Instant` et une `Duration` n'a pas besoin de timezone pour progresser.

Exemple :

```text
10:00Z
+
24 hours
```

est une opération absolue.

---

# 39. Conséquence DST

Un intervalle :

```text
24h
```

ne maintient pas forcément la même heure locale.

C'est voulu.

---

# 40. Exemple

Supposons une occurrence locale :

```text
08:00 Europe/Paris
```

puis :

```text
+ 24h
```

autour d'un changement d'heure.

La prochaine représentation locale peut devenir :

```text
07:00
```

ou :

```text
09:00
```

selon le sens du changement.

C'est correct pour un `IntervalTrigger`.

---

# 41. Si l'on veut toujours 08:00 local

Il faut utiliser :

```text
CronTrigger
```

ou une autre règle calendaire.

---

# 42. IntervalTrigger — invariants

```text
1. anchor est un Instant valide.

2. interval > 0.

3. Le Trigger est immutable.

4. La séquence est strictement croissante.

5. La distance entre deux ticks consécutifs est constante.

6. Le calcul ne dépend pas des executions.

7. Le calcul ne dépend pas d'une timezone locale.
```

---

# 43. IntervalTrigger — cas d'usage

```text
polling toutes les 30 secondes

heartbeat toutes les 10 secondes

refresh toutes les 5 minutes

health check périodique

synchronisation à fréquence absolue

maintenance technique régulière
```

---

# 44. CronTrigger — définition

`CronTrigger` produit des occurrences selon une règle calendaire.

Exemple :

```text
0 6 * * *
```

peut représenter :

```text
chaque jour à 06:00
```

dans une timezone donnée.

---

# 45. Intention métier

Cron répond à :

> Quand le calendrier civil correspond-il à cette expression ?

Il manipule donc :

```text
minute
hour
day
month
weekday
```

et non simplement une durée.

---

# 46. CronTrigger est calendar-based

Contrairement à `IntervalTrigger` :

```text
CronTrigger
```

raisonne dans l'espace du :

```text
LocalDateTime
```

puis résout le résultat vers un :

```text
Instant
```

---

# 47. Modèle CronTrigger

Conceptuellement :

```text
CronTrigger
│
├── CronExpression
└── timezone context
```

La timezone peut être portée directement par le Trigger ou par `ScheduleDefinition`.

La séparation finale devra rester stable.

---

# 48. CronExpression

`CronExpression` est un Value Object.

Il doit être :

```text
immutable
validated
normalized
serializable
```

---

# 49. Modèle cron classique

Une expression Unix classique possède cinq champs :

```text
minute
hour
day_of_month
month
day_of_week
```

Exemple :

```text
0 6 * * *
```

---

# 50. Lecture

```text
minute       0
hour         6
day          *
month        *
weekday      *
```

donne :

```text
Every day at 06:00
```

---

# 51. Autres exemples

```text
*/5 * * * *
```

→ toutes les cinq minutes civiles.

```text
0 8 * * MON
```

→ chaque lundi à 08:00.

```text
0 0 1 * *
```

→ le premier jour de chaque mois à minuit.

---

# 52. Cron n'est pas un intervalle

Exemple :

```text
0 * * * *
```

signifie :

```text
à chaque changement d'heure civile, minute 0
```

Ce n'est pas conceptuellement :

```text
exactement toutes les 3600 secondes
```

autour de certains changements d'heure.

---

# 53. Cron et timezone

Une expression cron n'est complète qu'avec son contexte timezone.

```text
0 8 * * *
Europe/Paris
```

est différent de :

```text
0 8 * * *
UTC
```

---

# 54. Pipeline de calcul

```text
CronExpression
      │
      ▼
LocalDateTime candidate
      │
      +
Timezone
      │
      ▼
DST Resolution
      │
      ▼
Instant
```

---

# 55. Cron et DST — heure inexistante

Supposons :

```text
Cron:
30 2 * * *

Timezone:
Europe/Paris
```

Un jour de passage à l'heure d'été, l'heure :

```text
02:30
```

peut ne pas exister.

---

# 56. Politique nécessaire

Le framework doit savoir s'il faut :

```text
SKIP

SHIFT_FORWARD

ERROR
```

ou appliquer une autre convention.

Cette sémantique ne peut pas rester implicite.

---

# 57. Cron et DST — heure ambiguë

Lors du retour à l'heure d'hiver :

```text
02:30
```

peut exister deux fois.

Le framework doit choisir :

```text
FIRST

SECOND

EARLIER_OFFSET

LATER_OFFSET

ERROR
```

---

# 58. Scheduled intention

Même si deux instants possibles existent, l'intention reste :

```text
02:30 Europe/Paris
```

La policy choisit son interprétation.

---

# 59. Cron dialect

Un point important est de définir précisément le dialecte accepté.

Le cron « standard » n'est pas totalement universel.

Certaines variantes proposent :

```text
seconds
year
L
W
#
?
```

---

# 60. Décision V1 recommandée

Commencer par un dialecte simple et prévisible :

```text
5 champs
minute
hour
day-of-month
month
day-of-week
```

avec :

```text
*
lists
ranges
steps
```

si l'implémentation choisie les supporte correctement.

---

# 61. Extensions à repousser

Ne pas introduire immédiatement :

```text
L
W
#
?
seconds field
year field
Quartz-specific semantics
```

sans spécification formelle.

---

# 62. Noms de mois et jours

Le support de :

```text
MON
JAN
```

peut être ergonomique.

Mais la représentation normalisée pourrait devenir :

```text
1
```

ou une structure interne canonique.

---

# 63. Normalisation

Exemple :

```text
MON
```

et :

```text
1
```

peuvent être équivalents selon le dialecte.

Le Value Object peut les normaliser pour :

```text
equality
fingerprint
serialization
```

---

# 64. Day-of-month versus day-of-week

C'est l'un des sujets les plus délicats du cron.

Selon les implémentations, lorsque les deux sont renseignés, leur combinaison peut être interprétée différemment.

PyScheduleKit devra documenter précisément cette règle.

---

# 65. Pas de sémantique implicite

Une expression comme :

```text
0 8 1 * MON
```

ne doit pas dépendre d'une convention non documentée.

Le dialecte doit dire explicitement :

```text
AND
```

ou :

```text
OR
```

selon la sémantique retenue.

---

# 66. CronTrigger — calcul candidat

Conceptuellement :

```text
reference Instant
      │
      ▼
convert to local timezone
      │
      ▼
search next matching LocalDateTime
      │
      ▼
resolve timezone / DST
      │
      ▼
Instant
```

---

# 67. Pourquoi partir de la timezone locale

Parce que l'expression cron représente :

```text
civil/calendar semantics
```

pas une suite d'Instants espacés uniformément.

---

# 68. CronTrigger — invariants

```text
1. CronExpression est valide.

2. Une timezone est disponible pour
   toute règle locale.

3. Le résultat est strictement > reference.

4. Les occurrences respectent le calendrier civil.

5. Le Trigger reste immutable.

6. La même entrée et la même policy DST
   donnent le même résultat.

7. Le Trigger ne gère ni misfire ni retry.
```

---

# 69. CronTrigger — cas d'usage

```text
tous les jours à 06:00

chaque lundi à 08:00

chaque premier jour du mois

toutes les 15 minutes civiles

tous les jours ouvrables simples
si uniquement basé sur weekday
```

Mais pas nécessairement :

```text
premier jour ouvré bancaire du mois
```

qui nécessite un BusinessCalendar.

---

# 70. Comparaison Date / Interval / Cron

```text
DateTrigger
      │
      ▼
ONE POINT

IntervalTrigger
      │
      ▼
ARITHMETIC SERIES

CronTrigger
      │
      ▼
CALENDAR MATCHING
```

---

# 71. Représentation mathématique

## DateTrigger

```text
T = {t}
```

---

## IntervalTrigger

```text
T = {a + nΔ | n ∈ N}
```

où :

```text
a = anchor
Δ = interval
```

---

## CronTrigger

```text
T = {t | calendar_fields(t) satisfy expression}
```

dans une timezone donnée.

---

# 72. Nature de la distance entre occurrences

### DateTrigger

Sans objet :

```text
une seule occurrence
```

### IntervalTrigger

```text
distance absolue constante
```

### CronTrigger

```text
distance absolue potentiellement variable
```

---

# 73. Exemple Cron mensuel

```text
0 0 1 * *
```

produit :

```text
Jan 1
Feb 1
Mar 1
Apr 1
```

Les durées entre occurrences sont :

```text
31 days
28/29 days
31 days
30 days
```

Elles ne sont donc pas constantes.

---

# 74. Exemple Interval mensuel impossible

Un :

```text
IntervalTrigger(30 days)
```

n'est pas équivalent à :

```text
first day of every month
```

---

# 75. Month semantics

Si le besoin est :

> tous les mois le 1er

utiliser une règle calendaire.

Si le besoin est :

> exactement toutes les 720 heures

utiliser un intervalle.

---

# 76. Daily semantics

Même distinction :

```text
every 24h
```

versus :

```text
every day at 08:00 local
```

---

# 77. Weekly semantics

```text
every 7 days
```

n'est pas nécessairement exactement le même concept que :

```text
every Monday at 08:00
```

même si souvent les résultats coïncident.

---

# 78. Trigger selection guide

Utiliser `DateTrigger` lorsque :

```text
l'occurrence est unique
```

Utiliser `IntervalTrigger` lorsque :

```text
la distance temporelle absolue
entre occurrences doit être constante
```

Utiliser `CronTrigger` lorsque :

```text
la règle est exprimée dans le calendrier civil
```

---

# 79. Exemple décisionnel

Besoin :

> Dans 30 minutes.

```text
DateTrigger
```

---

# 80. Exemple décisionnel

Besoin :

> Toutes les 30 minutes après 10:00.

```text
IntervalTrigger
```

---

# 81. Exemple décisionnel

Besoin :

> À chaque heure pile.

```text
CronTrigger("0 * * * *")
```

peut être préférable si l'intention est calendaire.

---

# 82. Nuance

Si le besoin est :

> exactement toutes les 60 minutes à partir de maintenant

alors :

```text
IntervalTrigger
```

est plus fidèle.

---

# 83. Exemple

À :

```text
10:17
```

### Interval every 60m

```text
10:17
11:17
12:17
```

### Cron hourly

```text
11:00
12:00
13:00
```

Même fréquence apparente, sémantique différente.

---

# 84. DateTrigger et ScheduleWindow

Si le DateTrigger pointe en dehors de :

```text
ScheduleWindow
```

le `OccurrencePlanner` peut conclure :

```text
no valid occurrence
```

Le Trigger lui-même reste valide.

---

# 85. IntervalTrigger et ScheduleWindow

Le planner peut prendre :

```text
next_after(reference)
```

jusqu'à ce que :

```text
candidate > end_at
```

puis conclure :

```text
Schedule completed
```

---

# 86. CronTrigger et ScheduleWindow

Même principe :

```text
cron candidate
↓
window validation
↓
accepted / exhausted
```

---

# 87. Calendar et DateTrigger

Un DateTrigger peut être exclu par un BusinessCalendar si le Schedule l'impose.

Exemple :

```text
DateTrigger
Sunday 08:00

Calendar
Weekdays only
```

Le planner peut produire :

```text
no valid occurrence
```

ou appliquer une policy explicite de déplacement si elle existe.

---

# 88. Important : exclusion ≠ déplacement

Si un Calendar interdit :

```text
Sunday
```

il ne faut pas automatiquement déplacer vers :

```text
Monday
```

sans règle explicite.

---

# 89. Calendar et IntervalTrigger

Un intervalle peut produire :

```text
Saturday
Sunday
Monday
```

Le Calendar peut en exclure certaines.

Cela signifie alors que la distance entre **occurrences retenues** n'est plus forcément constante, même si la séquence du Trigger l'est.

---

# 90. Calendar et CronTrigger

Même logique.

Le CronTrigger produit ses candidats.

Le Calendar applique une sémantique supplémentaire.

---

# 91. Candidate sequence versus accepted sequence

```text
Trigger sequence
T1 T2 T3 T4 T5
```

Calendar exclut :

```text
T2 T4
```

Occurrences du Schedule :

```text
T1 T3 T5
```

---

# 92. Importance

Le Trigger doit rester responsable de :

```text
sa propre série
```

Le Schedule/Planner est responsable de :

```text
la série réellement admissible
```

---

# 93. `next_after` commun

Les trois Triggers doivent respecter :

```text
next_after(reference)
→ Instant | None
```

---

# 94. Tableau comportemental

| Cas | Date | Interval | Cron |
|---|---|---|---|
| Unique | Oui | Non | Non |
| Récurrent | Non | Oui | Oui |
| Basé Duration | Non | Oui | Non |
| Basé calendrier | Non | Non | Oui |
| Nécessite anchor | Date elle-même | Oui | Non de même manière |
| Timezone requise | Si entrée locale seulement | Non généralement | Oui |
| DST | À la résolution initiale | Effet local indirect | Central |
| Peut retourner None | Oui | Si borné/window externe | Si borné/window externe |

---

# 95. Exhaustion DateTrigger

Naturelle :

```text
date <= reference
→ None
```

---

# 96. Exhaustion IntervalTrigger

Sans borne :

```text
never
```

conceptuellement.

Avec ScheduleWindow :

```text
planner
```

détecte l'absence d'occurrence admissible future.

---

# 97. Exhaustion CronTrigger

Sans borne et avec une expression satisfiable :

```text
généralement non
```

Avec :

```text
ScheduleWindow
```

il peut être effectivement épuisé pour le Schedule.

---

# 98. Unsatisfiable Cron

Certaines expressions ou combinaisons pourraient ne jamais trouver d'occurrence.

Le parser ou le calculateur doit idéalement détecter :

```text
impossible / no match within supported domain
```

plutôt que chercher indéfiniment.

---

# 99. Search horizon

Le CronTrigger doit avoir un calcul borné techniquement.

Exemple :

```text
maximum supported year
```

ou :

```text
search horizon
```

doit être documenté.

---

# 100. DateTrigger serialization

Exemple :

```json
{
  "schema_version": 1,
  "kind": "date",
  "scheduled_at": "2026-10-15T08:00:00Z"
}
```

---

# 101. IntervalTrigger serialization

```json
{
  "schema_version": 1,
  "kind": "interval",
  "anchor": "2026-10-04T10:00:00Z",
  "interval_seconds": 300
}
```

---

# 102. CronTrigger serialization

```json
{
  "schema_version": 1,
  "kind": "cron",
  "expression": "0 6 * * *",
  "timezone": "Europe/Paris"
}
```

si la timezone appartient au Trigger sérialisé.

---

# 103. Alternative timezone au Schedule

On peut préférer :

```json
{
  "trigger": {
    "kind": "cron",
    "expression": "0 6 * * *"
  },
  "timezone": "Europe/Paris"
}
```

au niveau `ScheduleDefinition`.

---

# 104. Recommandation architecturale

Pour garder une politique temporelle cohérente :

```text
ScheduleDefinition
├── Trigger
├── Timezone
├── DSTResolutionPolicy
└── Calendar
```

est probablement plus flexible que d'enfouir toute la timezone dans chaque Trigger.

---

# 105. Mais le Trigger doit recevoir son contexte

Cela peut être fait via :

```text
OccurrencePlanner
```

qui connaît :

```text
ScheduleDefinition
```

et utilise :

```text
Trigger
```

dans le bon contexte temporel.

---

# 106. Uniformité du Trigger

Cela renforce le modèle :

```text
Trigger
=
règle temporelle

ScheduleDefinition
=
contexte et politiques
```

---

# 107. DateTrigger equality

Deux DateTriggers sont égaux si :

```text
scheduled_at
```

est identique.

---

# 108. IntervalTrigger equality

Deux IntervalTriggers sont égaux si :

```text
anchor
interval
```

sont identiques.

---

# 109. CronTrigger equality

Deux CronTriggers sont égaux si :

```text
normalized expression
```

et le contexte inclus dans leur définition le sont.

Si timezone est externe, elle n'entre pas dans l'égalité du Trigger lui-même.

---

# 110. Trigger fingerprint

La représentation canonique permet :

```text
Date
→ hash(kind + scheduled_at)

Interval
→ hash(kind + anchor + interval)

Cron
→ hash(kind + normalized_expression)
```

ou avec timezone selon le modèle retenu.

---

# 111. Preview DateTrigger

```text
preview(count=10)
```

retournera au maximum :

```text
1 occurrence
```

---

# 112. Preview IntervalTrigger

```text
10:00
10:05
10:10
10:15
...
```

---

# 113. Preview CronTrigger

```text
Mon 08:00
Tue 08:00
Wed 08:00
...
```

selon l'expression.

---

# 114. Iteration helper

Tous peuvent être utilisés via un helper :

```text
iter_occurrences(
    trigger,
    after,
    limit
)
```

---

# 115. Importance de `limit`

Ne jamais exposer une itération non bornée par défaut sur un Trigger potentiellement infini.

---

# 116. Backfill DateTrigger

Un backfill d'une période contient :

```text
0 ou 1
```

occurrence.

---

# 117. Backfill IntervalTrigger

Peut contenir potentiellement beaucoup d'occurrences.

Exemple :

```text
every second
over 30 days
```

→ millions d'occurrences.

Des garde-fous sont indispensables.

---

# 118. Backfill CronTrigger

Même problématique.

La quantité dépend de :

```text
expression
window size
timezone
```

---

# 119. Backfill limit

Une policy/app layer doit fournir :

```text
max_occurrences
```

pour éviter une explosion accidentelle.

---

# 120. Performance DateTrigger

Complexité :

```text
O(1)
```

---

# 121. Performance IntervalTrigger

Un calcul mathématique peut viser :

```text
O(1)
```

pour `next_after()`.

Il faut éviter l'itération tick par tick depuis l'anchor.

---

# 122. Performance CronTrigger

Le calcul est plus complexe.

Il doit idéalement avancer intelligemment :

```text
mois
jour
heure
minute
```

plutôt que minute par minute sur de longues périodes.

---

# 123. Algorithme Cron conceptuel

```text
reference
   ↓
next candidate minute
   ↓
month allowed?
day allowed?
hour allowed?
minute allowed?
   ↓
resolve timezone
   ↓
return Instant
```

L'implémentation exacte dépendra de la stratégie/library choisie.

---

# 124. Bibliothèques externes

PyScheduleKit pourra potentiellement utiliser une bibliothèque existante pour :

```text
cron parsing
cron next calculation
```

mais son **contrat métier propre** doit rester indépendant de cette dépendance.

---

# 125. Pourquoi ?

Pour pouvoir :

```text
changer de backend

tester la conformité

normaliser les erreurs

stabiliser l'API
```

---

# 126. Adapter de calcul Cron

Une architecture possible :

```text
CronTrigger
      │
      ▼
CronCalculator Port/Internal Strategy
      │
      ▼
Library Adapter
```

Mais cela pourrait être excessif pour V1.

---

# 127. Priorité pédagogique

Pour PyScheduleKit, il est important de comprendre :

```text
l'algorithme conceptuel
```

avant de déléguer entièrement à une librairie.

---

# 128. Error model commun

Erreurs de construction :

```text
InvalidTriggerConfiguration
InvalidInterval
InvalidCronExpression
InvalidInstant
InvalidTimezone
```

---

# 129. Runtime calculation errors

```text
TriggerEvaluationError
TemporalResolutionError
UnsupportedTemporalRange
```

doivent rester rares après validation correcte.

---

# 130. DateTrigger invalid cases

```text
scheduled_at missing

naive datetime passed as Instant

unresolvable local datetime
```

---

# 131. IntervalTrigger invalid cases

```text
interval = 0

interval < 0

anchor invalid
```

---

# 132. CronTrigger invalid cases

```text
wrong field count

invalid numeric ranges

unknown names

impossible tokens

unsupported syntax
```

---

# 133. Cron field validation examples

Minute :

```text
0..59
```

Hour :

```text
0..23
```

Month :

```text
1..12
```

Les autres champs suivent la convention retenue.

---

# 134. Cron weekday representation

Il faudra définir précisément :

```text
0 = Sunday?
0 = Monday?
7 = Sunday?
```

selon le dialecte choisi.

PyScheduleKit doit éviter les ambiguïtés historiques.

---

# 135. Recommandation

Fournir une représentation interne canonique indépendante de la syntaxe externe.

Exemple :

```text
MONDAY
```

comme enum interne.

---

# 136. Human API

Une API future peut offrir :

```text
CronTrigger.daily_at("06:00")
```

ou :

```text
CronTrigger.weekly(...)
```

mais ces helpers doivent produire le même modèle canonique.

---

# 137. Sugar syntax versus core model

```text
daily_at("06:00")
```

est du sucre ergonomique.

Le domaine reste :

```text
CronTrigger
```

ou une règle calendaire équivalente.

---

# 138. Could daily schedule be a separate Trigger?

On pourrait créer :

```text
DailyTrigger
WeeklyTrigger
MonthlyTrigger
```

Mais cela multiplie les classes.

---

# 139. Recommandation

En V1 :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

sont suffisants.

Les helpers peuvent masquer la syntaxe cron pour les cas simples.

---

# 140. Exemple helper

```python
Schedule.daily(
    at="06:00",
    timezone="Europe/Paris",
)
```

peut produire en interne :

```text
CronTrigger("0 6 * * *")
```

---

# 141. Mais attention à l'abstraction

L'utilisateur ne doit pas être obligé de comprendre cron pour les cas les plus simples.

Le modèle interne peut rester cron tout en proposant une API plus expressive.

---

# 142. Date API ergonomique

```text
at(datetime)
```

→ `DateTrigger`

---

# 143. Interval API ergonomique

```text
every(minutes=5)
```

→ `IntervalTrigger`

---

# 144. Calendar API ergonomique

```text
daily_at("06:00")
```

→ `CronTrigger`

---

# 145. Exemple comparatif

```text
run once tomorrow at 08:00
→ DateTrigger
```

```text
run every 24 hours from tomorrow 08:00
→ IntervalTrigger
```

```text
run every day at 08:00 Europe/Paris
→ CronTrigger
```

---

# 146. Cas où les trois peuvent sembler équivalents

Supposons :

```text
start = Monday 08:00
```

Pendant quelques jours :

```text
DateTrigger successive manual dates
IntervalTrigger 24h
CronTrigger daily 08:00
```

peuvent produire les mêmes heures.

Mais leurs **intentions métier** restent différentes.

---

# 147. L'intention prime sur les résultats accidentellement identiques

C'est un principe essentiel.

Ne pas choisir un Trigger uniquement parce qu'il produit aujourd'hui les mêmes dates qu'un autre.

Choisir celui qui représente correctement la règle métier.

---

# 148. Trigger selection anti-pattern

Mauvais raisonnement :

```text
"cron et interval donnent les mêmes heures,
donc peu importe."
```

Bon raisonnement :

```text
"quelle intention temporelle
dois-je préserver lorsque le contexte change ?"
```

---

# 149. ScheduledAt

Quel que soit le Trigger :

```text
Occurrence.scheduled_at
```

doit devenir un :

```text
Instant
```

immuable.

---

# 150. DateTrigger scheduled_at

Directement :

```text
Trigger date
```

---

# 151. IntervalTrigger scheduled_at

Calculé par :

```text
anchor + n × interval
```

---

# 152. CronTrigger scheduled_at

Calculé par :

```text
calendar match
+
timezone resolution
```

---

# 153. Après matérialisation

La provenance du Trigger ne doit plus modifier cet Instant.

---

# 154. Jitter

Pour les trois Triggers :

```text
Jitter
```

doit intervenir **après** `scheduled_at`.

---

# 155. Misfire

Pour les trois :

```text
MisfirePolicy
```

intervient lorsque :

```text
now
```

est trop éloigné de :

```text
scheduled_at
```

---

# 156. Concurrency

Identique :

```text
Trigger
```

ne connaît pas les executions actives.

---

# 157. Retry

Identique :

```text
Retry
```

ne produit jamais de nouvelle occurrence du Trigger.

---

# 158. ScheduleRevision

Si le type ou la configuration du Trigger change :

```text
ScheduleRevision += 1
```

---

# 159. Exemple

Avant :

```text
IntervalTrigger(24h)
```

Après :

```text
CronTrigger(daily 08:00)
```

Même si les premières dates sont proches, il s'agit d'un changement sémantique majeur de la ScheduleDefinition.

---

# 160. Migration Trigger type

Une API de reschedule doit permettre explicitement :

```text
Date → Cron

Interval → Cron

Cron → Date
```

si le Schedule reste conceptuellement le même.

---

# 161. Historical occurrence remains stable

Une occurrence issue de l'ancien Trigger conserve :

```text
ScheduleRevision
```

et son :

```text
scheduled_at
```

---

# 162. Trigger provenance example

```text
Schedule revision 3
IntervalTrigger(24h)
Occurrence 2026-10-05T06:00Z
```

Puis :

```text
revision 4
CronTrigger("0 8 * * *")
```

L'ancienne occurrence n'est pas recalculée.

---

# 163. Observabilité

Pour chaque occurrence, on devrait pouvoir expliquer :

```text
Trigger type
Trigger configuration revision
Reference
Candidate
Timezone resolution
Final scheduled_at
```

---

# 164. Diagnostic DateTrigger

```text
Trigger: DATE
Scheduled instant: 2026-10-15T08:00Z
Reference: 2026-10-14T12:00Z
Result: 2026-10-15T08:00Z
```

---

# 165. Diagnostic IntervalTrigger

```text
Trigger: INTERVAL
Anchor: 10:00
Interval: 5m
Reference: 10:12
Result: 10:15
```

---

# 166. Diagnostic CronTrigger

```text
Trigger: CRON
Expression: 0 6 * * *
Timezone: Europe/Paris
Reference: ...
Local candidate: ...
Resolved instant: ...
```

---

# 167. Property-based tests

Les trois Trigger types se prêtent bien aux tests par propriétés.

---

# 168. Propriété universelle

```text
result is None
OR
result > reference
```

---

# 169. DateTrigger property

Il ne peut produire qu'une valeur possible :

```text
scheduled_at
```

---

# 170. IntervalTrigger property

Pour deux occurrences consécutives :

```text
t2 - t1 = interval
```

---

# 171. CronTrigger property

Chaque occurrence, convertie dans la timezone cible, doit satisfaire l'expression cron.

---

# 172. Determinism

Pour les trois :

```text
same trigger
same reference
same temporal context
→ same result
```

---

# 173. Serialization round-trip

Pour chaque trigger :

```text
trigger
↓
serialize
↓
deserialize
↓
same semantic trigger
```

---

# 174. Boundary DateTrigger tests

```text
reference < date

reference == date

reference > date
```

---

# 175. Boundary IntervalTrigger tests

```text
reference before anchor

reference == anchor

reference one micro-unit before tick

reference exactly on tick

large number of intervals
```

---

# 176. Boundary CronTrigger tests

```text
23:59 → next day

month end

year end

February 29

DST spring

DST autumn
```

---

# 177. Time precision

Les calculs doivent respecter la précision officielle choisie par PyScheduleKit.

Si l'Instant supporte :

```text
microseconds
```

le contrat strict `>` doit en tenir compte.

---

# 178. Interval precision

Un Interval peut être inférieur à une seconde si le framework le permet.

Mais les limites opérationnelles du scheduler restent distinctes.

---

# 179. Cron precision

Si V1 utilise cinq champs :

```text
minute
```

est sa granularité calendaire minimale.

Cela n'empêche pas le runtime d'avoir des timestamps plus précis.

---

# 180. Cron seconds future

Un futur :

```text
6-field CronTrigger
```

pourrait supporter les secondes.

Mais ce serait une extension explicite du dialecte.

---

# 181. Scheduler wake-up

Les trois Triggers alimentent :

```text
NextRunTime
```

qui permet au runtime de déterminer son prochain wake-up.

---

# 182. Exemple multi-schedules

```text
Schedule A
DateTrigger
next = 10:15

Schedule B
IntervalTrigger
next = 10:03

Schedule C
CronTrigger
next = 11:00
```

Le scheduler peut choisir :

```text
earliest = 10:03
```

---

# 183. Trigger ne choisit pas le wake-up global

Chaque Trigger calcule uniquement pour son Schedule.

Le Scheduler agrège ensuite les échéances.

---

# 184. Persistence JSON model

Une représentation déclarative commune pourrait suivre :

```json
{
  "kind": "...",
  "schema_version": 1,
  "config": {}
}
```

---

# 185. Date config

```json
{
  "kind": "date",
  "schema_version": 1,
  "config": {
    "scheduled_at": "2026-10-15T08:00:00Z"
  }
}
```

---

# 186. Interval config

```json
{
  "kind": "interval",
  "schema_version": 1,
  "config": {
    "anchor": "2026-10-04T10:00:00Z",
    "interval_seconds": 300
  }
}
```

---

# 187. Cron config

```json
{
  "kind": "cron",
  "schema_version": 1,
  "config": {
    "expression": "0 6 * * *"
  }
}
```

Timezone éventuellement stockée dans `ScheduleDefinition`.

---

# 188. Trigger codec

La conversion :

```text
JSON
↔
Trigger
```

appartient à :

```text
TriggerCodec
```

plutôt qu'au scheduler métier.

---

# 189. Security

Aucun Trigger sérialisé ne doit permettre :

```text
import arbitrary module
eval Python
execute code
```

Les configurations doivent rester déclaratives.

---

# 190. Allowed trigger registry

Le système peut posséder :

```text
TriggerRegistry
```

avec uniquement des kinds autorisés.

---

# 191. Unknown trigger

Un kind inconnu doit produire :

```text
UnsupportedTriggerKind
```

pas une tentative dynamique de chargement de code arbitraire.

---

# 192. Stable public contract

Les utilisateurs doivent pouvoir compter sur :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

comme primitives stables de V1.

---

# 193. Internal libraries may change

L'implémentation de :

```text
Cron next occurrence
```

peut changer sans modifier le contrat public si les résultats restent compatibles.

---

# 194. Semantic regression testing

Lors du remplacement d'une bibliothèque cron :

```text
same expression
same timezone
same references
```

doit produire les mêmes occurrences sur une suite de tests de conformité.

---

# 195. Trigger conformance suite

Chaque Trigger devrait satisfaire une suite commune :

```text
immutability

determinism

strict progression

serialization

validation

no side effects
```

---

# 196. DateTrigger conformance

En plus :

```text
maximum one occurrence
```

---

# 197. IntervalTrigger conformance

En plus :

```text
constant duration spacing
```

---

# 198. CronTrigger conformance

En plus :

```text
calendar rule satisfaction
timezone correctness
DST policy correctness
```

---

# 199. API illustrative

```python
DateTrigger(scheduled_at=...)
```

```python
IntervalTrigger(anchor=..., interval=...)
```

```python
CronTrigger(
    expression="0 6 * * *",
)
```

avec le contexte timezone éventuellement fourni par la `ScheduleDefinition`.

---

# 200. Schedule examples

## One shot

```python
ScheduleDefinition(
    target=TargetRef("workflow:release"),
    trigger=DateTrigger(release_at),
)
```

---

## Polling

```python
ScheduleDefinition(
    target=TargetRef("ingestion:orders"),
    trigger=IntervalTrigger(
        anchor=start,
        interval=Duration(minutes=5),
    ),
)
```

---

## Daily business operation

```python
ScheduleDefinition(
    target=TargetRef("workflow:daily-orders"),
    trigger=CronTrigger("0 6 * * *"),
    timezone=Timezone("Europe/Paris"),
)
```

---

# 201. Trois diagrammes mentaux

## Date

```text
──────────────●────────────────▶ TIME
              ↑
          occurrence
```

---

## Interval

```text
────●────●────●────●────●──────▶ TIME
    Δ    Δ    Δ    Δ
```

---

## Cron

```text
Calendar
Mon Tue Wed Thu Fri Sat Sun
 ↑       ↑       ↑
matches rule according to civil fields
```

---

# 202. Question de sélection

Avant de créer un Trigger, demander :

> Est-ce que mon intention est un **instant**, une **distance temporelle**, ou une **position dans le calendrier** ?

Réponse :

```text
Instant
→ DateTrigger

Distance
→ IntervalTrigger

Calendar position
→ CronTrigger
```

---

# 203. Anti-pattern — cron pour tout

Il est possible de représenter beaucoup de récurrences avec cron.

Mais :

```text
every 17 minutes from creation time
```

peut être beaucoup plus naturel avec :

```text
IntervalTrigger
```

---

# 204. Anti-pattern — interval pour calendrier

Éviter :

```text
30 days
```

pour représenter :

```text
every month
```

---

# 205. Anti-pattern — DateTrigger mutable

Ne pas modifier :

```text
scheduled_at
```

d'un DateTrigger existant.

Créer une nouvelle `ScheduleDefinition`.

---

# 206. Anti-pattern — interval depuis last run

Si l'intervalle dépend de la fin de l'exécution :

```text
ce n'est pas le modèle fixed-rate
```

Ne pas cacher cette différence.

---

# 207. Anti-pattern — cron sans timezone

Pour une règle civile :

```text
0 8 * * *
```

sans convention timezone claire est dangereuse.

---

# 208. Anti-pattern — cron converti définitivement en UTC

Une règle :

```text
08:00 Europe/Paris
```

ne doit pas devenir :

```text
07:00 UTC every day
```

comme règle durable.

---

# 209. Anti-pattern — DST implicite

Le comportement pendant les changements d'heure doit être spécifié et testé.

---

# 210. Anti-pattern — `next_after` inclusif variable

Tous les Trigger types doivent respecter la même convention.

```text
strictly > reference
```

doit être universel.

---

# 211. Anti-pattern — Trigger = Execution recurrence

Le Trigger produit des **occurrences**, pas des runs.

Une occurrence peut être :

```text
skipped
coalesced
missed
```

sans execution.

---

# 212. Anti-pattern — retry via IntervalTrigger

Un retry après cinq minutes n'est pas :

```text
IntervalTrigger(5m)
```

C'est :

```text
RetryPolicy
+
Backoff
```

sur la même Execution/Occurrence.

---

# 213. Modèle de calcul global

```text
                      ScheduleDefinition
                              │
                              ▼
                     Trigger selection
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
        DateTrigger     IntervalTrigger    CronTrigger
             │                │                │
             ▼                ▼                ▼
           Instant       Arithmetic       Calendar Match
             │                │                │
             └────────────────┼────────────────┘
                              │
                              ▼
                       Candidate Instant
                              │
                              ▼
                    Calendar / Window
                              │
                              ▼
                          Occurrence
                              │
                              ▼
                         NextRunTime
```

---

# 214. Modèle des responsabilités

```text
DateTrigger
→ ONE WHEN

IntervalTrigger
→ EVERY Δ

CronTrigger
→ WHEN CALENDAR MATCHES

OccurrencePlanner
→ WHICH CANDIDATE IS VALID

MisfirePolicy
→ WHAT IF IT IS LATE

ConcurrencyPolicy
→ WHAT IF SOMETHING IS ALREADY RUNNING

Executor
→ HOW TO RUN IT
```

---

# 215. Décisions proposées pour V1

```text
1.
DateTrigger stocke un Instant absolu.

2.
IntervalTrigger stocke :
anchor + positive Duration.

3.
IntervalTrigger utilise fixed-rate.

4.
Fixed-delay est hors scope V1.

5.
CronTrigger utilise un dialecte cron
explicitement défini.

6.
Cron représente le temps civil/calendaire.

7.
Les règles cron utilisent une Timezone
explicite via ScheduleDefinition ou Trigger.

8.
DST est traité par une policy explicite.

9.
Tous les Triggers implémentent :
next_after(reference) -> Instant | None.

10.
Le résultat est strictement > reference.

11.
Les Triggers sont immutables,
stateless et déterministes.

12.
Calendar, Misfire, Concurrency,
Jitter et Retry restent hors du Trigger.

13.
La sérialisation est déclarative
et versionnée.

14.
Date, Interval et Cron constituent
le noyau V1 des Triggers.
```

---

# 216. Critères d'acceptation

À l'issue de ce modèle, il doit être possible d'expliquer précisément :

```text
Pourquoi DateTrigger est one-shot.

Pourquoi IntervalTrigger a besoin d'un anchor.

Pourquoi IntervalTrigger 24h
n'est pas Daily 08:00.

Pourquoi CronTrigger a besoin
d'une sémantique timezone.

Pourquoi DST concerne Cron
plus directement qu'Interval.

Pourquoi fixed-delay n'est pas
un simple IntervalTrigger.

Pourquoi retry ≠ recurrence.

Pourquoi scheduled_at reste stable.

Comment les trois Trigger types
partagent le même contrat public.
```

---

# 217. Tableau final

| Dimension | DateTrigger | IntervalTrigger | CronTrigger |
|---|---|---|---|
| Intention | Une fois | Fréquence absolue | Règle civile |
| Base | Instant | Duration | Calendar |
| Occurrences | 0..1 future | Série | Série |
| Anchor | Date elle-même | Obligatoire | Référence calendaire implicite |
| Spacing absolu constant | N/A | Oui | Non garanti |
| Timezone | Résolue avant | Généralement inutile | Essentielle |
| DST | Création locale | Indirect | Fondamental |
| Stateful | Non | Non | Non |
| Fin naturelle | Oui | Non | Non généralement |
| V1 | Oui | Oui | Oui |

---

# 218. Modèle mental final

```text
                         USER INTENT
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
      "At this time"    "Every Δ time"   "When calendar
                                           matches"
            │                │                │
            ▼                ▼                ▼
      DateTrigger      IntervalTrigger    CronTrigger
            │                │                │
            └────────────────┼────────────────┘
                             │
                             ▼
                     next_after(reference)
                             │
                             ▼
                         Instant
                             │
                             ▼
                   Candidate Occurrence
                             │
                             ▼
                    OccurrencePlanner
                             │
                             ▼
                        Occurrence
```

---

# Conclusion

Les trois Triggers fondamentaux ne sont pas de simples variantes syntaxiques d'un même mécanisme.

Ils modélisent trois catégories différentes de temps :

```text
DateTrigger
→ un instant

IntervalTrigger
→ une durée répétée

CronTrigger
→ une règle calendaire
```

La distinction la plus importante est probablement :

```text
Duration-based recurrence
≠
Calendar-based recurrence
```

Ainsi :

```text
Every 24 hours
```

et :

```text
Every day at 08:00 Europe/Paris
```

doivent rester deux modèles distincts, même lorsqu'ils produisent momentanément les mêmes résultats.

PyScheduleKit peut dès lors construire son noyau V1 autour de trois primitives simples, cohérentes et complémentaires :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

toutes soumises au même contrat :

```text
next_after(reference)
        ↓
Instant | None
```

mais chacune préservant la sémantique temporelle du besoin qu'elle représente.

---

# Suite documentaire

La suite logique est :

```text
12_EXECUTION_AND_JOB_RUN_MODEL.md
```

Elle permettra de quitter progressivement le **temps planifié** pour étudier ce qui se produit après la décision :

```text
Occurrence
ExecutionRequest
Execution
Attempt
ExecutionResult
```

et surtout de stabiliser définitivement la distinction :

```text
Occurrence
≠
Execution
≠
Attempt
```

avant d'aborder ensuite :

```text
13_MISFIRE_COALESCING_AND_CATCHUP_MODEL.md
14_CONCURRENCY_AND_OVERLAP_MODEL.md
15_RETRY_BACKOFF_AND_FAILURE_MODEL.md
```