# PyScheduleKit — Job & Schedule Model

**Document :** `09_JOB_AND_SCHEDULE_MODEL.md`  
**Projet :** PyScheduleKit  
**Statut :** Modèle métier de référence  
**Nature :** Domain Model — Job / Target / Schedule  
**Prérequis :**
- `00_PYSCHEDULEKIT_EXPRESSION_DU_BESOIN.md`
- `01_SCHEDULING_DOMAIN_INTRODUCTION.md`
- `02_SCHEDULING_HISTORY_AND_FUNDAMENTAL_CONCEPTS.md`
- `03_SCHEDULING_DOMAIN_VOCABULARY.md`
- `04_SCHEDULING_BUSINESS_OBJECTS.md`
- `05_SCHEDULING_ENTITIES_AND_VALUE_OBJECTS.md`
- `07_SCHEDULING_ERD.md`
- `08_TIME_CLOCK_TIMEZONE_AND_CALENDAR_MODEL.md`

---

# 1. Objectif

Le scheduling repose sur deux questions différentes :

```text
WHAT?
→ Quel travail voulons-nous pouvoir déclencher ?

WHEN?
→ Selon quelle règle ce travail doit-il devenir exigible ?
```

Ces questions conduisent naturellement à distinguer :

```text
Job / Target
```

et :

```text
Schedule
```

Cette distinction est essentielle.

Un même travail peut être exécuté :

```text
tous les jours à 06:00

chaque lundi à 08:00

une seule fois demain

dans plusieurs fuseaux horaires
```

sans que sa nature métier change.

Le présent document définit donc :

```text
Target
Job
Schedule
ScheduleId
ScheduleState
ScheduleRevision
ScheduleWindow
TargetRef
JobRef
```

ainsi que leurs relations, comportements, invariants et cycles de vie.

---

# 2. Principe fondamental

Le modèle doit toujours préserver :

```text
WHAT
≠
WHEN
```

ou plus précisément :

```text
Job / Target
≠
Schedule
```

Un travail ne doit pas devenir responsable de sa propre temporalité.

Une planification ne doit pas devenir responsable de l'implémentation du travail.

---

# 3. Modèle conceptuel minimal

```text
              ┌──────────────────┐
              │    Job/Target    │
              │                  │
              │ WHAT?            │
              └────────┬─────────┘
                       │
                       │ referenced by
                       ▼
              ┌──────────────────┐
              │     Schedule     │
              │                  │
              │ WHEN?            │
              │ + policies       │
              └────────┬─────────┘
                       │
                       ▼
                    Trigger
                       │
                       ▼
                  Occurrences
```

---

# 4. Target

## Définition

Un `Target` représente **la destination logique du déclenchement**.

Il ne décrit pas nécessairement comment cette destination sera exécutée.

Exemples :

```text
python:generate_report

workflow:daily_orders

ingestion:customers

transform:monthly_metrics

http:https://example/api/run

command:backup-database
```

---

# 5. Target comme concept abstrait

Le scheduler doit pouvoir fonctionner sans comprendre la structure interne du target.

Ainsi :

```text
Target
```

peut représenter :

```text
fonction
commande
workflow
message
opération
endpoint
job distant
```

sans que `Schedule` change de modèle.

---

# 6. TargetRef

Dans le domaine, il est utile d'utiliser :

```text
TargetRef
```

plutôt qu'un callable Python brut.

Exemple :

```text
TargetRef("workflow:daily-orders")
```

ou :

```text
TargetRef("python:reports.generate_daily")
```

---

# 7. Pourquoi TargetRef ?

Une référence logique apporte plusieurs avantages :

```text
sérialisation
persistance
portabilité
résolution tardive
découplage
remote execution
```

Un callable Python n'est pas toujours facilement sérialisable.

---

# 8. Classification

```text
TargetRef
=
Value Object
```

Il doit être :

```text
immutable
validé
comparable par valeur
```

---

# 9. TargetType

Une future abstraction peut permettre de distinguer :

```text
PYTHON
COMMAND
WORKFLOW
INGESTION
TRANSFORMATION
HTTP
EVENT
```

Mais il faut éviter que PyScheduleKit devienne dépendant de tous ces domaines.

Une chaîne de référence bien structurée peut suffire.

---

# 10. TargetResolver

La résolution concrète d'un target doit appartenir à une frontière d'exécution.

Conceptuellement :

```text
TargetRef
   │
   ▼
TargetResolver / Executor
   │
   ▼
Concrete Runtime
```

`Schedule` n'effectue pas cette résolution lui-même.

---

# 11. Job

## Définition

Un `Job` représente une définition logique nommée d'un travail réutilisable.

Il peut porter :

```text
JobId
name
TargetRef
arguments
metadata
```

Exemple :

```text
Job
──────────────────────
id       = daily-report
target   = python:generate_report
args     = {...}
metadata = {...}
```

---

# 12. Job versus Target

Un target répond :

> Où / vers quoi envoyer la demande ?

Un job répond :

> Quelle définition logique de travail voulons-nous réutiliser ?

Exemple :

```text
Target
python:reports.generate
```

peut être utilisé par :

```text
Job
daily-sales-report
```

avec certains paramètres.

---

# 13. Pourquoi Job est optionnel

Une architecture très légère pourrait fonctionner avec :

```text
Schedule
   │
   ▼
TargetRef
```

sans `Job`.

Cela réduit la complexité.

---

# 14. Quand Job devient utile

`Job` apporte de la valeur lorsque l'on souhaite :

```text
réutiliser un même travail dans plusieurs schedules

centraliser ses paramètres

donner une identité métier au travail

désactiver ou modifier le travail indépendamment du schedule

attacher des métadonnées
```

---

# 15. Exemple — un Job, plusieurs Schedules

```text
                     Job
              generate_report
                     │
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
      Schedule A Schedule B Schedule C

      06:00      Monday     New York
      Paris      08:00      08:00
```

Le travail reste identique.

Les temporalités changent.

---

# 16. Cardinalité

Le modèle général est :

```text
Job 1
  │
  └────────── N Schedule
```

mais :

```text
Schedule
```

doit pouvoir fonctionner directement avec un `TargetRef` si le Job n'est pas activé comme abstraction publique.

---

# 17. Classification du Job

Si conservé :

```text
Job
=
Entity
```

car il possède une identité :

```text
JobId
```

qui persiste même si :

```text
name
arguments
metadata
target
```

évoluent.

---

# 18. JobId

```text
JobId
=
Value Object
```

Exemple :

```text
JobId("daily-report")
```

ou identité opaque :

```text
JobId("01K...")
```

---

# 19. Job arguments

Les arguments doivent être distingués des informations de scheduling.

Exemple :

```text
Job
generate_report(
    format="pdf",
    locale="fr"
)
```

ne doit pas contenir :

```text
every day at 06:00
```

---

# 20. Schedule

## Définition

Un `Schedule` représente une **planification durable**.

Il associe :

```text
une cible
+
une règle temporelle
+
un contexte temporel
+
des politiques
+
un cycle de vie
```

---

# 21. Question métier

`Schedule` répond :

> **Quand et dans quelles conditions ce travail doit-il devenir exigible ?**

---

# 22. Modèle conceptuel

```text
Schedule
│
├── ScheduleId
├── TargetRef / JobRef
├── Trigger
├── Timezone
├── CalendarRef
├── ScheduleWindow
├── Policies
├── ScheduleState
├── ScheduleRevision
├── NextRunTime
└── Metadata
```

---

# 23. Schedule comme Aggregate Root

La classification recommandée reste :

```text
Schedule
=
Entity
+
Aggregate Root
```

Il protège les invariants liés à la définition et au lifecycle de la planification.

---

# 24. ScheduleId

```text
ScheduleId
=
Value Object
```

L'identité doit rester stable pendant toute la durée de vie du Schedule.

Exemple :

```text
ScheduleId("daily-orders")
```

---

# 25. Identité versus configuration

Supposons :

```text
ScheduleId = daily-orders

v1:
06:00

v2:
07:00

v3:
08:00
```

Il s'agit toujours du même Schedule.

Donc :

```text
Schedule identity
≠
Schedule configuration
```

---

# 26. ScheduleRevision

Chaque modification significative peut incrémenter :

```text
ScheduleRevision
```

Exemple :

```text
revision 1
revision 2
revision 3
```

---

# 27. Pourquoi une révision ?

Elle permet de répondre à :

```text
Sous quelle configuration
cette occurrence a-t-elle été calculée ?
```

Exemple :

```text
Occurrence
scheduled_at = 06:00
schedule_revision = 4
```

même si le Schedule est aujourd'hui en :

```text
revision = 7
```

---

# 28. Classification

```text
ScheduleRevision
=
Value Object
```

Invariant :

```text
revision >= 1
```

---

# 29. Revision versus version produit

Ne pas confondre :

```text
ScheduleRevision
```

avec :

```text
PyScheduleKit version
```

ou une version métier globale.

La revision appartient à une instance précise de Schedule.

---

# 30. Composition du Schedule

Une configuration complète pourrait conceptuellement ressembler à :

```text
Schedule(
    id,
    target,
    trigger,
    timezone,
    calendar,
    window,
    policies,
    state,
    revision
)
```

---

# 31. Trigger

Le `Trigger` appartient à la configuration du Schedule mais conserve sa propre responsabilité :

```text
Schedule
→ possède/configure

Trigger
→ calcule
```

Le prochain document détaillera cette partie.

---

# 32. Timezone

Une Timezone appartient à l'intention temporelle du Schedule lorsque la règle est calendaire.

Exemple :

```text
06:00 Europe/Paris
```

La timezone ne doit pas être recalculée à partir d'une occurrence historique.

---

# 33. CalendarRef

Le Schedule peut éventuellement référencer :

```text
CalendarRef
```

Exemple :

```text
CalendarRef("fr-business-days")
```

Le calendrier lui-même peut être résolu via un provider.

---

# 34. ScheduleWindow

Un Schedule peut être actif uniquement dans une période donnée.

Exemple :

```text
start_at = 2026-11-01
end_at   = 2026-11-30
```

Cela représente :

```text
ScheduleWindow
```

---

# 35. ScheduleWindow versus ScheduleState

Un schedule peut être :

```text
ACTIVE
```

mais se trouver :

```text
avant start_at
```

ou :

```text
après end_at
```

Ainsi :

```text
lifecycle state
≠
temporal window
```

---

# 36. Exemple

```text
ScheduleState = ACTIVE

ScheduleWindow:
2026-11-01 → 2026-11-30

Current date:
2026-10-20
```

Le schedule existe et est actif, mais aucune occurrence ne doit encore être produite.

---

# 37. ScheduleState

Le Schedule possède son propre lifecycle.

Un modèle initial peut être :

```text
ACTIVE
PAUSED
CANCELLED
COMPLETED
```

Éventuellement :

```text
DRAFT
```

si une phase de préparation est utile.

---

# 38. ACTIVE

Signification :

```text
le Schedule peut produire
de nouvelles occurrences
selon son Trigger
```

sous réserve :

```text
ScheduleWindow
Calendar
Policies
```

---

# 39. PAUSED

Signification :

```text
la planification est temporairement suspendue
```

La définition existe toujours.

---

# 40. CANCELLED

Signification :

```text
la planification a été arrêtée définitivement
```

Il s'agit normalement d'un état terminal.

---

# 41. COMPLETED

Signification :

```text
le Schedule ne peut plus produire
aucune occurrence
```

par exemple :

```text
DateTrigger déjà consommé
```

ou :

```text
end_at dépassé
```

---

# 42. DRAFT

Un éventuel état :

```text
DRAFT
```

pourrait représenter un Schedule défini mais non encore activé.

Il n'est pas indispensable pour V1.

---

# 43. Machine à états

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

et éventuellement :

```text
ACTIVE
  │
  │ recurrence exhausted
  ▼
COMPLETED
```

---

# 44. Transitions autorisées

Exemple de matrice :

| From | Action | To |
|---|---|---|
| ACTIVE | pause | PAUSED |
| ACTIVE | cancel | CANCELLED |
| ACTIVE | complete | COMPLETED |
| PAUSED | resume | ACTIVE |
| PAUSED | cancel | CANCELLED |

Les autres transitions doivent être rejetées.

---

# 45. Transition invalide

Exemple :

```text
CANCELLED
   │
   └── resume()
```

doit produire :

```text
InvalidScheduleTransition
```

---

# 46. Pause

`pause()` modifie :

```text
ScheduleState
```

mais pose immédiatement une question :

> Que faire des occurrences qui auraient dû avoir lieu pendant la pause ?

---

# 47. Deux sémantiques possibles

Après reprise :

```text
PAUSE
08:00 → 12:00
```

on peut :

### A

```text
ignorer les occurrences
de la période
```

### B

```text
les considérer comme occurrences manquées
et appliquer catch-up / misfire
```

---

# 48. Recommandation

Le lifecycle du Schedule ne doit pas décider seul.

La reprise doit interagir avec une :

```text
ResumePolicy
```

ou avec les policies de misfire/catch-up déjà existantes.

---

# 49. Resume

`resume()` remet :

```text
PAUSED
→
ACTIVE
```

mais ne doit pas automatiquement :

```text
rejouer tout l'historique
```

sans règle explicite.

---

# 50. Cancel

`cancel()` signifie :

```text
ne plus produire
de nouvelles occurrences
```

Il ne signifie pas automatiquement :

```text
annuler toutes les executions déjà créées
```

---

# 51. Distinction fondamentale

```text
Cancel Schedule
≠
Cancel Execution
```

Un run déjà en cours appartient à son propre lifecycle.

---

# 52. Delete

Supprimer physiquement un Schedule est encore différent.

```text
DELETE
```

est une opération administrative/persistante.

```text
CANCEL
```

est une opération métier.

---

# 53. Reschedule

`reschedule()` modifie la définition temporelle d'un Schedule existant.

Exemple :

```text
avant:
06:00

après:
08:00
```

---

# 54. Identité conservée

Après reschedule :

```text
ScheduleId
```

reste le même.

Mais :

```text
ScheduleRevision
```

augmente.

---

# 55. Exemple

```text
Schedule
id = daily-orders
revision = 7
cron = 0 6 * * *
```

puis :

```text
reschedule(0 8 * * *)
```

devient :

```text
Schedule
id = daily-orders
revision = 8
cron = 0 8 * * *
```

---

# 56. Que devient NextRunTime ?

Il doit être recalculé à partir :

```text
du nouveau Trigger
+
du contexte temporel
```

et non conservé aveuglément.

---

# 57. Que deviennent les anciennes occurrences ?

Une occurrence déjà matérialisée doit rester attachée à :

```text
schedule_revision précédente
```

Elle ne doit pas être rétroactivement transformée.

---

# 58. Scheduled history immutability

Principe :

> Une modification du Schedule influence les occurrences futures, pas la signification historique des occurrences déjà produites.

---

# 59. Exemple

Avant modification :

```text
Revision 4
Occurrence:
06:00
```

Après modification :

```text
Revision 5
Next occurrence:
08:00
```

L'occurrence 06:00 reste :

```text
revision = 4
```

---

# 60. Disable versus Pause

Le terme :

```text
DISABLED
```

est souvent utilisé dans les schedulers.

Mais si :

```text
PAUSED
```

exprime déjà « existe mais ne produit rien », les deux peuvent être redondants.

---

# 61. Recommandation

Pour le modèle initial :

```text
ACTIVE
PAUSED
CANCELLED
COMPLETED
```

suffisent.

Ne pas introduire `DISABLED` sans sémantique supplémentaire.

---

# 62. Schedule activation

Si `DRAFT` existe :

```text
DRAFT
  │
activate
  ▼
ACTIVE
```

Sinon, un Schedule correctement créé peut être directement :

```text
ACTIVE
```

---

# 63. Schedule creation

La création doit valider plusieurs invariants.

Exemple :

```text
target exists logically
trigger valid
timezone valid
window valid
policies valid
```

---

# 64. Invariants principaux du Schedule

```text
1.
ScheduleId est obligatoire.

2.
TargetRef ou JobRef est obligatoire.

3.
Trigger est obligatoire.

4.
ScheduleWindow doit être cohérente.

5.
GracePeriod ne peut pas être négative.

6.
ScheduleRevision >= 1.

7.
CANCELLED est terminal.

8.
COMPLETED ne produit plus d'occurrences.

9.
PAUSED ne produit pas normalement
de nouvelles ExecutionRequests.

10.
Un reschedule incrémente la revision.
```

---

# 65. Invariant Target

Un Schedule ne doit pas être créé avec :

```text
target = None
```

Même si le Target n'est résolu techniquement qu'au runtime.

---

# 66. Target existence

Question subtile :

> Faut-il vérifier que le Target existe réellement à la création ?

Deux approches.

---

# 67. Validation forte

```text
CreateSchedule
   ↓
resolve target
   ↓
must exist
```

Avantage :

```text
erreurs détectées tôt
```

Inconvénient :

```text
couplage
external dependency
```

---

# 68. Validation faible

```text
TargetRef
```

est syntaxiquement valide.

La résolution est reportée au runtime.

Avantage :

```text
découplage
```

Inconvénient :

```text
target cassé possible
```

---

# 69. Recommandation

Le domaine pur valide :

```text
la structure de TargetRef
```

La couche application/intégration peut effectuer :

```text
une validation de resolvability
```

optionnelle.

---

# 70. Schedule name

Le champ :

```text
name
```

ne doit pas nécessairement être l'identité.

Exemple :

```text
ScheduleId = 01ABC...
name = Daily orders
```

Plusieurs Schedules peuvent éventuellement partager un nom.

---

# 71. Metadata

`metadata` peut permettre :

```text
tags
owner
domain
team
description
custom attributes
```

Mais elle ne doit pas devenir une poubelle contenant des règles métier importantes.

---

# 72. Anti-pattern Metadata

Éviter :

```json
{
  "cron": "...",
  "misfire": "...",
  "timezone": "..."
}
```

si ces concepts sont de vrais attributs métier.

Ils doivent être typés explicitement.

---

# 73. Policies du Schedule

Un Schedule peut référencer :

```text
MisfirePolicy
ConcurrencyPolicy
JitterPolicy
```

et éventuellement d'autres politiques.

---

# 74. Pourquoi les policies appartiennent au Schedule

Parce que deux schedules du même Job peuvent avoir des comportements différents.

Exemple :

```text
Job = refresh_cache
```

Schedule A :

```text
every minute
ALLOW overlap
```

Schedule B :

```text
daily
FORBID overlap
```

Le comportement dépend donc de la planification.

---

# 75. RetryPolicy

Son placement est plus délicat.

Le retry peut concerner :

```text
dispatch
execution
workflow step
HTTP call
```

Il ne faut donc pas ajouter un `RetryPolicy` générique au Schedule sans préciser sa portée.

---

# 76. Recommandation

Si PyScheduleKit supporte un retry propre :

```text
DispatchRetryPolicy
```

est plus clair que :

```text
RetryPolicy
```

universel.

---

# 77. NextRunTime

`next_run_time` représente :

```text
la prochaine occurrence actuellement connue
```

Il est dérivé du Trigger.

---

# 78. NextRunTime appartient-il au Schedule ?

Conceptuellement :

```text
non essentiel à l'identité
```

mais opérationnellement :

```text
très utile
```

Il peut donc être considéré comme :

```text
derived operational state
```

du Schedule.

---

# 79. Exemple

```text
Schedule
trigger = every day 06:00
next_run_time = 2026-10-05 06:00
```

Après traitement :

```text
next_run_time = 2026-10-06 06:00
```

---

# 80. Source of truth

Principe :

```text
Trigger + Schedule configuration
=
logical source of truth

NextRunTime
=
materialized derived state
```

---

# 81. Reconstruction

Après corruption ou migration :

```text
next_run_time
```

doit idéalement pouvoir être recalculé.

---

# 82. Schedule evaluation

Un Schedule ne doit pas nécessairement lui-même décider :

```text
am I due?
```

car cela dépend aussi de :

```text
Clock
active executions
calendar data
leases
```

Cette décision peut appartenir au :

```text
SchedulingEvaluator
```

---

# 83. Responsabilité interne du Schedule

Le Schedule peut néanmoins répondre à :

```text
is_active?

is_within_window(instant)?

can_transition_to(state)?

current_revision
```

Ces questions relèvent de son propre état.

---

# 84. Exemple de comportement riche

Conceptuellement :

```python
schedule.pause(at=now)
schedule.resume(at=now)
schedule.cancel(at=now)
schedule.reschedule(trigger=new_trigger, at=now)
```

---

# 85. Domain events

Ces opérations peuvent produire :

```text
SchedulePaused
ScheduleResumed
ScheduleCancelled
ScheduleRescheduled
```

---

# 86. ScheduleCreated

Lors de création :

```text
ScheduleCreated
```

peut porter :

```text
schedule_id
revision
created_at
target_ref
```

---

# 87. ScheduleRescheduled

Peut porter :

```text
old_revision
new_revision
changed_at
```

et éventuellement :

```text
old trigger fingerprint
new trigger fingerprint
```

---

# 88. Immutabilité historique

Ces events permettent d'expliquer :

```text
quand
pourquoi
et comment
```

la planification a évolué.

---

# 89. Job lifecycle

Si `Job` est conservé comme Entity, son lifecycle peut être plus simple.

Exemple :

```text
ACTIVE
DISABLED
ARCHIVED
```

Mais il faut éviter de dupliquer le lifecycle de Schedule.

---

# 90. Question fondamentale

Que signifie :

```text
Job DISABLED
```

pour ses Schedules ?

Possibilités :

```text
tous deviennent inéligibles
```

ou :

```text
aucun impact
```

Cette complexité est une raison supplémentaire de garder `Job` optionnel.

---

# 91. Recommandation pour V1

Pour la première version :

```text
Schedule
→ TargetRef directement
```

est probablement plus simple.

Puis :

```text
Job Registry
```

peut être ajouté ultérieurement comme fonctionnalité optionnelle.

---

# 92. Modèle V1

```text
Schedule
│
├── ScheduleId
├── TargetRef
├── Trigger
├── Timezone
├── CalendarRef?
├── ScheduleWindow?
├── Policies
├── ScheduleState
├── Revision
├── NextRunTime?
└── Metadata
```

---

# 93. Modèle V2 possible

```text
Job
│
├── JobId
├── TargetRef
├── Parameters
└── Metadata

        │
        │ 1:N
        ▼

Schedule
```

---

# 94. Direct target versus JobRef

Le Schedule pourrait conceptuellement supporter un discriminant :

```text
TargetBinding
```

avec :

```text
DirectTarget(TargetRef)
```

ou :

```text
JobBinding(JobId)
```

Mais ce niveau d'abstraction est probablement inutile en V1.

---

# 95. Parameter binding

Les paramètres peuvent appartenir :

```text
au Job
au Schedule
à l'ExecutionRequest
```

selon leur nature.

---

# 96. Job-level parameters

Exemple :

```text
format = pdf
report_type = sales
```

Ils définissent le travail.

---

# 97. Schedule-level parameters

Exemple :

```text
region = France
```

si deux schedules déclenchent le même Job avec des variantes.

---

# 98. Occurrence-level parameters

Exemple :

```text
scheduled_at
calendar_date
```

sont construits au moment du déclenchement.

---

# 99. ExecutionRequest parameters

Le scheduler peut matérialiser les paramètres finaux dans :

```text
ExecutionRequest
```

pour garantir que l'exécution sait exactement ce qu'elle doit lancer.

---

# 100. Snapshot des paramètres

Cela améliore la reproductibilité.

Même si le Job ou Schedule change après création de la request :

```text
ExecutionRequest
```

conserve le contexte résolu au moment de la décision.

---

# 101. ScheduleRevision et Request

Une ExecutionRequest doit idéalement contenir :

```text
schedule_id
schedule_revision
```

afin de préserver cette relation historique.

---

# 102. ScheduleRevision et Occurrence

Même logique :

```text
OccurrenceKey
=
ScheduleId
+
ScheduledAt
+
ScheduleRevision
```

---

# 103. Concurrency scope

La ConcurrencyPolicy d'un Schedule doit savoir :

```text
sur quoi porte la concurrence ?
```

Par défaut :

```text
ScheduleId
```

peut servir de scope.

---

# 104. Mais parfois

Deux Schedules différents peuvent cibler la même ressource.

On peut alors utiliser :

```text
ConcurrencyKey
```

spécifique.

Exemple :

```text
database:customer-refresh
```

---

# 105. ConcurrencyKey dans Schedule

```text
Schedule
├── concurrency_policy
└── concurrency_key
```

permet une sémantique explicite.

---

# 106. Exemple

Schedule A :

```text
daily_customer_refresh
```

Schedule B :

```text
manual_customer_refresh
```

Les deux utilisent :

```text
ConcurrencyKey("customer-refresh")
```

et ne peuvent pas s'exécuter simultanément.

---

# 107. Schedule ownership

Un Schedule peut porter une notion fonctionnelle de :

```text
owner
team
namespace
tenant
```

mais ces propriétés ne doivent pas être ajoutées sans besoin.

---

# 108. Namespace

Une abstraction utile peut être :

```text
ScheduleNamespace
```

pour éviter les collisions d'identifiants.

Exemple :

```text
finance/daily-close

data/daily-orders
```

À introduire uniquement si le framework devient multi-domaines.

---

# 109. Multi-tenancy

Même principe pour :

```text
TenantId
```

Il ne faut pas faire du multi-tenancy un invariant de base si PyScheduleKit doit rester léger.

---

# 110. Schedule equality

Deux Schedules ayant :

```text
même trigger
même target
mêmes policies
```

ne sont pas nécessairement identiques.

Ils peuvent avoir deux :

```text
ScheduleId
```

différents.

Donc :

```text
Schedule equality
=
identity-based
```

---

# 111. Trigger equality

À l'inverse :

```text
CronTrigger("0 6 * * *")
```

et :

```text
CronTrigger("0 6 * * *")
```

peuvent être égaux par valeur.

Cette distinction reflète bien :

```text
Entity
vs
Value Object
```

---

# 112. Duplicate schedules

Le domaine doit-il empêcher :

```text
deux schedules identiques
```

?

Pas nécessairement.

Exemple :

```text
Schedule A
target X at 06:00

Schedule B
target X at 06:00
```

peut être intentionnel.

---

# 113. Deduplication

La déduplication doit donc se faire :

```text
au niveau de l'Occurrence / ExecutionRequest
```

plutôt qu'en interdisant arbitrairement les configurations semblables.

---

# 114. Schedule fingerprint

Un fingerprint peut néanmoins être utile pour :

```text
diagnostic
change detection
cache
```

Exemple :

```text
hash(
 target
 trigger
 timezone
 policies
)
```

Mais il ne remplace pas `ScheduleId`.

---

# 115. Schedule lifecycle timestamps

Des timestamps peuvent être conservés :

```text
created_at
updated_at
paused_at
cancelled_at
completed_at
```

Mais il faut éviter de multiplier des colonnes si des events suffisent.

---

# 116. Minimal lifecycle timestamps

Pour V1 :

```text
created_at
updated_at
```

peuvent suffire.

Les événements donnent le reste de l'historique.

---

# 117. Activation boundaries

Un Schedule peut avoir :

```text
start_at
end_at
```

qui limitent le Trigger.

Exemple :

```text
CronTrigger every day 06:00

start_at = Nov 1
end_at   = Nov 30
```

---

# 118. Trigger exhausted

Un Trigger peut retourner :

```text
None
```

pour signifier :

```text
aucune occurrence future
```

Le Schedule peut alors devenir :

```text
COMPLETED
```

---

# 119. Completion rule

Conceptuellement :

```text
if trigger.next_after(last_occurrence) is None:
    schedule.complete()
```

La responsabilité exacte de l'appel appartient au moteur d'application.

---

# 120. Completed versus Cancelled

```text
COMPLETED
=
fin naturelle

CANCELLED
=
arrêt demandé
```

Cette distinction est importante pour l'audit.

---

# 121. Pause versus Completed

Un Schedule `PAUSED` :

```text
pourrait reprendre
```

Un Schedule `COMPLETED` :

```text
ne possède plus de futur naturel
```

---

# 122. Reschedule d'un Completed

Question de domaine :

Peut-on rescheduler un schedule `COMPLETED` ?

Deux options :

```text
NON
→ créer un nouveau Schedule
```

ou :

```text
OUI
→ nouvelle revision et ACTIVE
```

---

# 123. Recommandation

Pour garder le lifecycle clair :

```text
COMPLETED
```

devrait être terminal.

Une nouvelle planification significative peut créer :

```text
un nouveau Schedule
```

ou une opération explicite de réactivation future si le besoin apparaît.

---

# 124. Reschedule d'un Cancelled

Même logique :

```text
CANCELLED
```

doit rester terminal.

Ne pas ressusciter silencieusement les objets annulés.

---

# 125. Clone Schedule

Si l'utilisateur souhaite repartir d'une configuration annulée :

```text
clone()
```

peut créer un :

```text
new ScheduleId
```

avec une configuration dérivée.

---

# 126. Schedule factory

Une :

```text
ScheduleFactory
```

pourrait être utile si la création nécessite :

```text
ID generation
Clock
default policies
normalization
```

Mais le domaine ne doit pas introduire une Factory sans nécessité.

---

# 127. Schedule constructor

Une construction directe peut suffire si tous les invariants sont locaux :

```text
Schedule.create(...)
```

est probablement plus lisible.

---

# 128. Exemple conceptuel

```python
schedule = Schedule.create(
    id=ScheduleId("daily-orders"),
    target=TargetRef("workflow:daily-orders"),
    trigger=CronTrigger("0 6 * * *"),
    timezone=Timezone("Europe/Paris"),
    misfire_policy=RunNow(),
    concurrency_policy=ForbidOverlap(),
)
```

API illustrative uniquement.

---

# 129. Schedule creation result

Une création peut produire :

```text
Schedule
+
ScheduleCreated
```

plutôt qu'un objet mutable incomplet.

---

# 130. Invalid schedule construction

Exemples :

```text
missing target

invalid trigger

negative grace period

start_at > end_at

invalid timezone
```

doivent être refusés immédiatement.

---

# 131. No invalid intermediate state

Principe :

> Un Schedule ne doit pas pouvoir exister dans un état structurellement invalide.

Cela implique de valider à la construction.

---

# 132. Persistence mapping

Le modèle relationnel peut stocker :

```text
schedule_id
target_ref
trigger_type
trigger_config
timezone
calendar_ref
start_at
end_at
policies
state
revision
next_run_time
metadata
```

sans faire de chaque Value Object une table.

---

# 133. Reconstitution

Le repository doit pouvoir reconstruire :

```text
Schedule Entity
```

à partir de la représentation persistée.

---

# 134. Repository

Le port :

```text
ScheduleRepository
```

peut exposer :

```text
save(schedule)

get(schedule_id)

remove(schedule_id)
```

et éventuellement :

```text
list_candidates(before=instant)
```

---

# 135. Repository ne décide pas du métier

Éviter :

```text
repository.execute_due_schedules()
```

Le repository persiste et recherche.

Le moteur de scheduling décide.

---

# 136. Query optimization

Une opération comme :

```text
find schedules with next_run_time <= now
```

est acceptable comme requête de sélection de candidats.

Mais :

```text
due
```

au sens métier final reste évalué par le domaine.

---

# 137. Schedule Candidate

Un repository peut retourner :

```text
due candidates
```

qui restent à vérifier.

Cela permet :

```text
DB filtering
+
domain decision
```

sans confondre les niveaux.

---

# 138. Optimistic concurrency

`ScheduleRevision` peut également servir à éviter les lost updates.

Exemple :

```text
client A loads revision 5
client B loads revision 5

A saves revision 6

B tries to save based on 5
→ conflict
```

---

# 139. ScheduleConflict

Une erreur :

```text
ScheduleRevisionConflict
```

peut signaler cette situation.

---

# 140. Domain events

Le Schedule peut produire :

```text
ScheduleCreated
SchedulePaused
ScheduleResumed
ScheduleRescheduled
ScheduleCancelled
ScheduleCompleted
```

---

# 141. Event payload

Les events ne doivent pas nécessairement embarquer toute l'Entity.

Ils peuvent transporter :

```text
ScheduleId
Revision
occurred_at
change summary
```

---

# 142. Audit

Grâce à :

```text
ScheduleRevision
+
Domain Events
```

on peut reconstruire l'évolution fonctionnelle du Schedule sans rendre l'Aggregate énorme.

---

# 143. Example — Daily Orders

Besoin :

> Tous les jours à 06:00 Europe/Paris, lancer `daily_orders_pipeline`, sans overlap.

Modèle :

```text
Schedule
─────────────────────────

ScheduleId
daily-orders

TargetRef
workflow:daily-orders

Trigger
CronTrigger("0 6 * * *")

Timezone
Europe/Paris

ConcurrencyPolicy
ForbidOverlap

State
ACTIVE

Revision
1
```

---

# 144. Exécution conceptuelle

```text
Schedule
   │
   ▼
Trigger
   │
   ▼
Occurrence
2026-10-05 06:00 Europe/Paris
   │
   ▼
SchedulingDecision
   │
   ▼
ExecutionRequest
```

Le Schedule n'exécute rien lui-même.

---

# 145. Example — multiple schedules

```text
Target
workflow:daily-orders
        │
        ├── Schedule Paris
        │      06:00 Europe/Paris
        │
        └── Schedule New York
               06:00 America/New_York
```

Cela montre pourquoi :

```text
Target
≠
Schedule
```

---

# 146. Example — paused Schedule

```text
Schedule state = PAUSED

Trigger next candidate = 06:00
```

Le candidat temporel peut exister conceptuellement, mais aucune nouvelle execution request ne doit être créée normalement.

---

# 147. Example — Schedule Window

```text
Schedule
every day 06:00

Window
Oct 1 → Oct 7
```

Occurrences :

```text
Oct 1 06:00
Oct 2 06:00
...
Oct 7 06:00
```

puis :

```text
COMPLETED
```

si aucune occurrence future n'est possible.

---

# 148. Example — reschedule

```text
Revision 3
06:00
```

modification :

```text
08:00
```

devient :

```text
Revision 4
08:00
```

Les anciennes occurrences conservent :

```text
revision = 3
```

---

# 149. Example — cancellation

```text
ACTIVE
  │
 cancel()
  ▼
CANCELLED
```

Une Execution déjà `RUNNING` :

```text
continue
```

sauf demande distincte au runtime.

---

# 150. Job model final recommandé

Pour V1 :

```text
TargetRef
```

est obligatoire.

`Job` reste :

```text
optionnel
```

et pourra être ajouté si un véritable besoin de registre réutilisable apparaît.

---

# 151. Schedule model final recommandé

```text
Schedule
│
├── ScheduleId
├── TargetRef
├── Trigger
├── Timezone?
├── CalendarRef?
├── ScheduleWindow?
├── MisfirePolicy
├── ConcurrencyPolicy
├── JitterPolicy?
├── ConcurrencyKey?
├── ScheduleState
├── ScheduleRevision
├── NextRunTime?
└── Metadata
```

---

# 152. Required versus optional

## Obligatoire

```text
ScheduleId
TargetRef
Trigger
State
Revision
```

## Selon le trigger / besoin

```text
Timezone
CalendarRef
ScheduleWindow
GracePeriod
Policies spécialisées
```

---

# 153. Defaults

Les valeurs par défaut doivent être prudentes.

Exemple :

```text
misfire policy
```

ne doit pas forcément être :

```text
RUN_NOW
```

si cela peut produire des effets inattendus.

Les defaults feront partie d'une spécification ultérieure.

---

# 154. Null versus explicit policy

Éviter :

```text
misfire_policy = None
```

si cela signifie implicitement un comportement caché.

Préférer :

```text
DefaultMisfirePolicy
```

ou une policy explicite au moment de la construction.

---

# 155. Null timezone

Pour un :

```text
DateTrigger(absolute Instant)
```

une timezone métier peut être inutile.

Pour :

```text
CronTrigger(local rule)
```

elle est généralement indispensable.

L'invariant dépend donc du Trigger.

---

# 156. Cross-object validation

Exemple :

```text
CronTrigger
+
timezone = None
```

peut être invalide.

Cette validation concerne la composition du Schedule.

---

# 157. Schedule validation service ?

Si ces validations deviennent nombreuses, un :

```text
ScheduleSpecification
```

ou :

```text
ScheduleValidator
```

pourrait apparaître.

Mais il vaut mieux garder les invariants proches du Schedule lorsque possible.

---

# 158. Business invariants versus infrastructure

Exemple métier :

```text
start_at <= end_at
```

Exemple infrastructure :

```text
JSON column size <= X
```

Le second ne doit pas polluer le domaine.

---

# 159. Public API future

On pourrait viser :

```python
schedule = Schedule.daily(
    id="daily-orders",
    target="workflow:daily-orders",
    at="06:00",
    timezone="Europe/Paris",
)
```

ou une API générique :

```python
Schedule(...)
```

Mais cette ergonomie viendra après le modèle.

---

# 160. Declarative Schedule Definition

Une future API déclarative pourrait permettre :

```yaml
schedule:
  id: daily-orders
  target: workflow:daily-orders

  trigger:
    cron: "0 6 * * *"

  timezone: Europe/Paris

  concurrency:
    mode: forbid
```

Ce YAML n'est qu'une représentation du `Schedule`, pas le domaine lui-même.

---

# 161. Serialization boundary

La conversion :

```text
YAML / JSON
     ↓
ScheduleDefinition DTO
     ↓
Domain Schedule
```

doit préserver la séparation entre :

```text
transport
```

et :

```text
domain
```

---

# 162. ScheduleDefinition

Il peut devenir utile d'introduire :

```text
ScheduleDefinition
```

comme Value Object immutable représentant la configuration.

Puis :

```text
Schedule Entity
=
identity
+
definition
+
lifecycle
+
revision
```

---

# 163. Variante intéressante

```text
Schedule
│
├── ScheduleId
├── ScheduleDefinition
├── ScheduleState
├── Revision
└── NextRunTime
```

et :

```text
ScheduleDefinition
│
├── TargetRef
├── Trigger
├── Timezone
├── CalendarRef
├── Window
└── Policies
```

---

# 164. Avantage

Un reschedule devient conceptuellement :

```text
old definition
→
new definition
```

sans mutation dispersée de nombreux champs.

---

# 165. ScheduleDefinition comme Value Object

Cela permet :

```text
immutable definition snapshots
```

et facilite :

```text
revisioning
comparison
audit
testing
```

---

# 166. Recommandation architecturale

Cette variante mérite d'être privilégiée.

Modèle :

```text
Schedule [Entity]
│
├── ScheduleId
├── ScheduleDefinition [Value Object]
├── ScheduleState
├── ScheduleRevision
├── NextRunTime
└── lifecycle metadata
```

---

# 167. ScheduleDefinition

```text
ScheduleDefinition
│
├── TargetRef
├── Trigger
├── Timezone
├── CalendarRef
├── ScheduleWindow
├── MisfirePolicy
├── ConcurrencyPolicy
├── JitterPolicy
├── ConcurrencyKey
└── Metadata
```

---

# 168. Reschedule avec Definition

```text
Schedule.reschedule(
    new_definition
)
```

puis :

```text
revision += 1
next_run_time = recompute()
```

Le modèle devient très propre.

---

# 169. Configuration identity

Deux `ScheduleDefinition` identiques sont :

```text
equal by value
```

mais deux `Schedule` utilisant cette même définition restent :

```text
different Entities
```

---

# 170. Modèle final recommandé

```text
                        Schedule
                   [Aggregate Root]
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ScheduleId      ScheduleState     ScheduleRevision
                         │
                         │
                         ▼
                 ScheduleDefinition
                    [Value Object]
                         │
       ┌─────────────────┼─────────────────────┐
       │                 │                     │
       ▼                 ▼                     ▼
   TargetRef          Trigger               Policies
                         │
                 ┌───────┼────────┐
                 ▼       ▼        ▼
             Timezone Calendar  Window
```

---

# 171. Flux vers l'exécution

```text
Schedule
   │
   ▼
ScheduleDefinition
   │
   ▼
Trigger
   │
   ▼
Occurrence
   │
   ▼
SchedulingEvaluator
   │
   ▼
SchedulingDecision
   │
   ▼
ExecutionRequest
```

---

# 172. Ce que Schedule ne fait PAS

Un Schedule ne doit pas :

```text
lancer des threads

exécuter directement le target

gérer une queue

connaître les étapes d'un workflow

transformer des données

faire des requêtes HTTP métier

gérer un pool de workers

stocker son historique complet d'execution
```

---

# 173. Ce que Job ne fait PAS

Si Job existe :

```text
ne calcule pas les occurrences

ne connaît pas next_run_time

ne porte pas les policies temporelles

ne décide pas du misfire
```

---

# 174. Ce que TargetRef ne fait PAS

```text
ne résout pas forcément lui-même le target

ne l'exécute pas

ne possède pas de lifecycle
```

---

# 175. Anti-pattern — Job = Schedule

Éviter un objet :

```text
Job(
    callable,
    cron,
    timezone,
    retries,
    next_run,
    status
)
```

qui fusionne toutes les responsabilités.

---

# 176. Anti-pattern — mutable trigger fields everywhere

Éviter :

```text
schedule.cron_expression = ...
schedule.interval = ...
schedule.date = ...
```

simultanément.

Le Trigger doit encapsuler la variante temporelle.

---

# 177. Anti-pattern — state string mutable

Éviter :

```python
schedule.state = "anything"
```

Préférer des transitions métier contrôlées.

---

# 178. Anti-pattern — silent reschedule

Modifier directement :

```text
trigger
```

sans :

```text
revision increment
next run recomputation
audit event
```

crée une incohérence historique.

---

# 179. Anti-pattern — target callable persisted directly

Persister des objets Python arbitraires rend :

```text
migration
portabilité
sécurité
versioning
```

beaucoup plus difficiles.

Préférer une référence logique résolue par adapter.

---

# 180. Anti-pattern — Schedule owns executions

Ne jamais faire :

```text
Schedule.executions = [...]
```

comme aggregate complet.

Le volume et le lifecycle sont indépendants.

---

# 181. Exemple Python conceptuel

Sans figer encore l'API :

```python
schedule = Schedule.create(
    schedule_id=ScheduleId("daily-orders"),
    definition=ScheduleDefinition(
        target=TargetRef("workflow:daily-orders"),
        trigger=CronTrigger("0 6 * * *"),
        timezone=Timezone("Europe/Paris"),
        concurrency_policy=ForbidOverlap(),
    ),
)
```

Puis :

```python
schedule.pause(at=now)
```

ou :

```python
schedule.reschedule(
    new_definition,
    at=now,
)
```

---

# 182. Exemple de revision

```text
Initial
────────────────
revision = 1
cron = 06:00

pause
────────────────
state changes
revision ? 
```

Il faut préciser si les changements de lifecycle incrémentent la revision.

---

# 183. Deux types de revision possibles

### Definition Revision

Change uniquement quand la configuration temporelle change.

### Entity Version

Change à chaque mutation, pour optimistic locking.

---

# 184. Recommandation

Distinguer conceptuellement :

```text
ScheduleRevision
```

pour la définition métier

et éventuellement :

```text
PersistenceVersion
```

pour l'optimistic locking technique.

Cela évite de mélanger les usages.

---

# 185. ScheduleRevision augmente lorsque

```text
Trigger change

Timezone change

Calendar change

ScheduleWindow change

Target change

Policy change
```

---

# 186. ScheduleRevision ne doit pas nécessairement augmenter pour

```text
pause

resume

last evaluated timestamp

next run cache
```

si elle représente uniquement la définition.

Cette distinction devra être figée dans la spécification technique.

---

# 187. Occurrence identity

Avec ce modèle :

```text
OccurrenceKey
=
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

reste cohérente.

---

# 188. Schedule state history

Pause/resume peuvent être tracés via :

```text
Domain Events
```

sans modifier la revision de définition.

---

# 189. NextRunTime et pause

Lors d'une pause, plusieurs stratégies :

### Conserver

```text
next_run_time
```

pour diagnostic.

### Vider

```text
next_run_time = None
```

pour ne plus être sélectionné.

---

# 190. Recommandation

Conceptuellement conserver :

```text
calculated_next_occurrence
```

mais opérationnellement exclure les schedules non ACTIVE des requêtes.

Cela préserve l'information.

---

# 191. NextRunTime après resume

Doit être recalculé en fonction :

```text
de now
de la dernière occurrence connue
de la Resume/MisfirePolicy
```

et non simplement reprendre aveuglément une date dépassée.

---

# 192. Completion automatique

Un Schedule peut devenir `COMPLETED` lorsque :

```text
Trigger exhausted
```

ou :

```text
ScheduleWindow ended
and no future occurrence remains
```

---

# 193. Completion timestamp

Un event :

```text
ScheduleCompleted
```

suffit probablement pour l'historique.

---

# 194. Search model

Les recherches peuvent porter sur :

```text
state
target_ref
next_run_time
tags
calendar_ref
```

mais cela relève du query model, pas nécessairement de l'Aggregate.

---

# 195. CQRS léger possible

À terme :

```text
Command model
→ Schedule Aggregate

Query model
→ optimized projections
```

peut être utile sans adopter un CQRS lourd.

---

# 196. Scheduling API boundary

Les opérations principales deviennent :

```text
create schedule

get schedule

pause schedule

resume schedule

cancel schedule

reschedule

list schedules

inspect next occurrence
```

---

# 197. Domain commands

On peut représenter :

```text
CreateSchedule
PauseSchedule
ResumeSchedule
CancelSchedule
Reschedule
```

mais le cœur reste l'Entity `Schedule`.

---

# 198. Domain events

```text
ScheduleCreated
SchedulePaused
ScheduleResumed
ScheduleCancelled
ScheduleRescheduled
ScheduleCompleted
```

---

# 199. Critères d'acceptation du modèle

Le modèle Job/Schedule doit permettre de répondre clairement à :

```text
Qu'est-ce que le travail ?

Qu'est-ce que la planification ?

Peut-on planifier plusieurs fois le même travail ?

Quelle identité survit à un reschedule ?

Quelle configuration a produit une occurrence historique ?

Que signifie PAUSED ?

Que signifie CANCELLED ?

Que signifie COMPLETED ?

Que devient une execution déjà active après cancel ?

Comment les policies sont-elles associées au schedule ?

Comment le target est-il référencé sans coupler le domaine au runtime ?

Comment next_run_time est-il calculé et stocké ?
```

---

# 200. Décisions proposées

Pour la première version de PyScheduleKit :

```text
1.
Schedule est l'Aggregate Root principal.

2.
ScheduleDefinition est un Value Object immutable.

3.
Schedule référence directement TargetRef.

4.
Job est optionnel et hors du noyau minimal.

5.
ScheduleState contient :
ACTIVE
PAUSED
CANCELLED
COMPLETED.

6.
CANCELLED et COMPLETED sont terminaux.

7.
Reschedule conserve ScheduleId.

8.
Reschedule crée une nouvelle ScheduleRevision.

9.
Les occurrences historiques conservent leur revision.

10.
TargetRef est résolu hors du domaine.

11.
NextRunTime est un état opérationnel dérivé.

12.
Le Schedule ne possède pas l'historique des executions.
```

---

# 201. Modèle final

```text
                    ┌────────────────────┐
                    │      Schedule      │
                    │  Aggregate Root    │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
        ScheduleId       ScheduleState   ScheduleRevision
                              │
                              ▼
                    ScheduleDefinition
                       Value Object
                              │
       ┌──────────────────────┼────────────────────────┐
       │                      │                        │
       ▼                      ▼                        ▼
   TargetRef               Trigger                  Policies
                              │
                     ┌────────┼─────────┐
                     ▼        ▼         ▼
                 Timezone  Calendar   Window
                              │
                              ▼
                         Occurrence
                              │
                              ▼
                    SchedulingDecision
                              │
                              ▼
                     ExecutionRequest
```

---

# Conclusion

Le modèle Job/Schedule doit préserver une séparation simple mais fondamentale :

```text
Target / Job
=
WHAT

Schedule
=
WHEN + CONDITIONS
```

Le modèle recommandé pour PyScheduleKit est centré sur :

```text
Schedule
=
Entity + Aggregate Root

ScheduleDefinition
=
Value Object immutable

TargetRef
=
Value Object

Trigger
=
Value Object comportemental

ScheduleState
=
Lifecycle

ScheduleRevision
=
Version de la définition
```

Cette séparation permet :

```text
plusieurs schedules pour un même travail

rescheduling traçable

historique reproductible

faible couplage au runtime

persistance claire

meilleure testabilité
```

Le point essentiel est que :

> **Le Schedule ne représente pas le travail exécuté ; il représente l'intention durable selon laquelle ce travail doit devenir exigible dans le temps.**

---

# Suite documentaire

La prochaine étape est :

```text
10_TRIGGER_MODEL.md
```

Elle devra approfondir :

```text
Trigger
Trigger contract
next occurrence
candidate occurrence
finite / infinite triggers
stateful / stateless triggers
composition
exhaustion
trigger fingerprint
determinism
timezone interaction
calendar interaction
```

puis :

```text
11_DATE_INTERVAL_AND_CRON_TRIGGERS.md
```

pour étudier concrètement les trois grandes familles de règles :

```text
DateTrigger
IntervalTrigger
CronTrigger
```

et leurs différences sémantiques.