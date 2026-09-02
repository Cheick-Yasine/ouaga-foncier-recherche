# Étape 10 — Imputation des variables numériques

## Objectif

Compléter temporairement les prix et superficies manquants afin que la future
interface puisse comparer les annonces, sans perdre l'information sur l'origine
réelle ou imputée de chaque valeur.

Cette étape est une simulation en lecture seule. Elle ne modifie pas Neon et ne
supprime aucune annonce.

## Ordre des annonces

Avant l'imputation, les annonces sont classées par :

1. `premiere_collecte` ;
2. `id` pour départager deux annonces collectées au même moment.

Cet ordre explicite rend le résultat reproductible. Une modification arbitraire de
l'ordre des lignes ne changera donc pas silencieusement le calcul.

## Méthode d'encadrement

Pour chaque valeur manquante :

- si une valeur observée existe avant et après, leur moyenne est utilisée ;
- si seule la valeur précédente existe, elle est reprise ;
- si seule la valeur suivante existe, elle est reprise ;
- si toute la variable est manquante, la valeur reste indisponible.

Les valeurs déjà imputées ne servent jamais à en imputer d'autres. Seules les
valeurs réellement observées peuvent encadrer un manque.

## Indicateurs conservés

Chaque annonce reçoit dans la trace de préparation :

- `prix_fcfa_etait_manquant` ;
- `superficie_m2_etait_manquante` ;
- `methode_imputation_prix` ;
- `methode_imputation_superficie` ;
- `cible_prix_m2_observee`.

La dernière variable vaut vrai uniquement lorsque le prix et la superficie étaient
présents dans l'annonce originale et que la superficie était strictement positive.

## Protection de la modélisation

Un prix au m² calculé avec un prix ou une superficie imputée est une valeur utile
pour la recherche exploratoire, mais ce n'est pas une cible réellement observée.

Le futur modèle de prix devra donc être entraîné uniquement avec :

```text
cible_prix_m2_observee = true
```

Cela empêche le modèle d'apprendre des prix au m² que le système a lui-même
fabriqués.

## Limite de la méthode

La moyenne des annonces voisines est la règle demandée pour cette phase, mais elle
ne tient pas directement compte du quartier, du type de bien ou de la superficie.
Les valeurs imputées doivent donc être clairement signalées dans l'interface et ne
doivent pas être présentées comme des informations publiées par le vendeur.

## Confidentialité

Le workflow manuel **Audit imputation numérique** utilise une transaction Neon en
lecture seule. La trace détaillée reste dans le répertoire temporaire du runner.
L'artefact contient seulement des totaux agrégés, sans identifiant, texte, contact,
URL, prix ou superficie individuelle.
