# Étape 5 — Audit de déduplication

## Objectif

Mesurer et tracer les doublons avant toute exclusion dans la base préparée.
La table `public.annonces` reste intacte.

## Deux niveaux de décision

### Doublons certains

Une annonce est regroupée automatiquement lorsque l'une des conditions suivantes
est satisfaite :

- même URL après retrait des paramètres de suivi ;
- même texte après normalisation de la casse, des accents et de la ponctuation.

Dans chaque groupe, l'annonce ayant la `derniere_maj` la plus récente est conservée.
La complétude puis l'identifiant servent à départager les égalités.

### Candidats à contrôler

Deux annonces ayant le même quartier, le même prix et la même superficie sont
signalées, mais ne sont pas automatiquement regroupées. Ces caractéristiques
peuvent correspondre à deux biens distincts.

## Rapports produits

- `deduplication-audit.json` : bilan global, écarts avec les volumes historiques et
  groupes candidats ;
- `deduplication-trace.csv` : identifiant conservé, identifiant écarté en simulation,
  motif et empreinte non réversible du groupe.

Le texte des annonces et les contacts WhatsApp ne sont jamais écrits dans les
rapports.

## Référence historique

| Indicateur | Valeur |
| --- | ---: |
| Observations avant | 11 245 |
| Observations supprimées | 6 694 |
| Observations restantes | 4 551 |

Ces nombres servent de point de comparaison. Ils ne sont pas codés comme une
condition de réussite, car Neon continue de recevoir de nouvelles annonces.

## Exécution

Dans GitHub Actions, lancer manuellement **Audit déduplication**. Le workflow est en
lecture seule et publie un artefact `audit-deduplication` pendant sept jours.
