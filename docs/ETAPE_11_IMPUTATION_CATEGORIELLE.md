# Étape 11 — Imputation des variables catégorielles

## Objectif

Garantir qu'aucune variable catégorielle du futur jeu de données ne soit vide, sans
inventer une catégorie métier et sans supprimer d'annonce.

Cette étape est exécutée après le filtrage des annonces sans prix ou superficie observés et ne modifie pas Neon.

La base reçue par cette phase contient donc uniquement les annonces numériquement complètes.\n\n## Variables concernées

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

- `valeurs_manquantes_avant` : les valeurs nulles ou vides détectées ;
- `valeurs_converties_en_manquante` : les remplacements effectués ;
- `valeurs_vides_apres` : les vrais champs encore vides, normalement zéro ;
- `categories_manquante_apres` : les observations portant désormais la modalité
  explicite `manquante` ;
- les distributions des principales variables.

La modalité textuelle `manquante` est donc une valeur renseignée. Elle n'est pas
comptée comme un champ techniquement vide.

Aucune ligne n'est supprimée.

## Confidentialité

Le workflow manuel **Audit imputation catégorielle** utilise une transaction Neon en
lecture seule. La trace détaillée contenant les identifiants reste dans le dossier
temporaire du runner. L'artefact publié ne contient que des statistiques agrégées,
sans texte, contact, URL ou identifiant.
