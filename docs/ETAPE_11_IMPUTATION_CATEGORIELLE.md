# Étape 11 — Imputation des variables catégorielles

## Objectif

Garantir qu'aucune variable catégorielle du futur jeu de données ne soit vide, sans
inventer une catégorie métier et sans supprimer d'annonce.

Cette étape est exécutée après l'imputation numérique et ne modifie pas Neon.

## Variables concernées

- `quartier_final` ;
- `type_bien_normalise` ;
- `proximite` ;
- `viabilite` ;
- `statut_document`.

## Règle appliquée

Une valeur devient `manquante` uniquement lorsqu'elle est :

- nulle ;
- vide ;
- composée uniquement d'espaces.

Une catégorie déjà renseignée reste inchangée.

## Différence entre « non précisée » et « manquante »

Les valeurs `non_precisee` et `non_precise` signifient que l'annonce a été
analysée, mais qu'aucun signal suffisamment clair n'a été trouvé dans son texte.
Elles restent donc distinctes de `manquante`, qui représente une absence technique
de catégorie à l'issue du pipeline.

Cette distinction permet de savoir si l'information n'était pas annoncée ou si la
catégorie n'a pas pu être construite.

## Cas du type de bien

Les catégories utilisables restent :

- `terrain` ;
- `parcelle` ;
- `maison`.

Les villas ont déjà été exclues à l'étape précédente. Un type encore ambigu devient
`manquante` et l'annonce reste dans la base, afin d'éviter une suppression
irréversible.

## Contrôle

Le rapport agrégé indique pour chaque variable :

- le nombre de valeurs absentes avant l'imputation ;
- le nombre converti en `manquante` ;
- le nombre restant après l'imputation ;
- les distributions des principales variables.

Aucune ligne n'est supprimée.

## Confidentialité

Le workflow manuel **Audit imputation catégorielle** utilise une transaction Neon en
lecture seule. La trace détaillée contenant les identifiants reste dans le dossier
temporaire du runner. L'artefact publié ne contient que des statistiques agrégées,
sans texte, contact, URL ou identifiant.
