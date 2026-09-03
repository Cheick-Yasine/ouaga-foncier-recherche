# Étape 10 révisée — Filtrage du double manque numérique

## Décision

L'imputation des prix et superficies reste supprimée.

Une annonce quitte la base préparée uniquement lorsque le prix et la superficie
sont tous les deux manquants. Si une seule de ces informations manque, l'annonce
reste disponible pour la recherche.

## Pourquoi conserver les annonces partiellement renseignées

Une annonce sans prix peut encore correspondre au quartier, à la superficie, au
type de bien, au document, à la proximité et à la viabilité recherchés.

Une annonce sans superficie peut encore correspondre au quartier, au prix et aux
autres caractéristiques. Les supprimer ferait perdre des résultats potentiellement
utiles.

## Règle de classement future

Le moteur calculera le score uniquement avec les critères disponibles pour chaque
annonce :

- prix absent : le critère prix ne rapporte aucun point ;
- superficie absente : le critère superficie ne rapporte aucun point ;
- la couverture du résultat diminue lorsqu'une information demandée manque ;
- l'interface signale clairement toute information indisponible ;
- une annonce ne reçoit jamais un avantage parce qu'une valeur manque.

Les règles strictes demandées par l'utilisateur restent prioritaires. Par exemple,
si l'utilisateur rend le prix obligatoire, une annonce sans prix est écartée de
cette recherche particulière, même si elle reste dans la base préparée.

## Motifs suivis dans l'audit

Les annonces sont réparties entre :

- `complete` ;
- `prix_manquant`, conservée ;
- `superficie_manquante`, conservée ;
- `prix_et_superficie_manquants`, exclue ;
- `superficie_non_positive`, conservée par cette règle et signalée séparément.

## Conservation de la base brute

L'exclusion concerne uniquement le jeu de données préparé. Aucune ligne originale
n'est supprimée de `public.annonces` dans Neon.

## Résultat attendu

D'après le dernier audit :

- 3 401 annonces sont disponibles avant ce filtre ;
- 113 ont simultanément le prix et la superficie manquants ;
- 3 288 annonces devraient rester ;
- aucune valeur numérique ne sera imputée.

## Confidentialité

Le workflow **Audit complétude numérique** utilise Neon en lecture seule. La trace
détaillée reste temporaire dans le runner. L'artefact publié contient uniquement
des statistiques agrégées.
