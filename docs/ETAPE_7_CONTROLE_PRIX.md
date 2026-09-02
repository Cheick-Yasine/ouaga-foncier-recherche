# Étape 7 — Contrôle des prix observés

## Objectif

Contrôler `prix_fcfa` après la déduplication et la restriction géographique, sans
fabriquer de prix et sans modifier la table source Neon.

## Règles

- prix manquant : conserver l'annonce et mémoriser que le prix est absent ;
- prix inférieur à 10 000 FCFA : exclure du résultat préparé ;
- prix égal ou supérieur à 10 000 FCFA : conserver ;
- valeur techniquement invalide : exclure et signaler séparément.

Aucune limite supérieure n'est ajoutée à cette étape. Le seuil inférieur correspond
à la règle métier validée.

## Ordre d'exécution

1. chargement de `public.annonces` ;
2. déduplication par URL ou texte normalisé ;
3. normalisation et restriction géographique ;
4. contrôle des prix observés.

## Traçabilité et confidentialité

Le workflow crée une trace détaillée dans le répertoire temporaire du runner, mais
publie uniquement un rapport JSON agrégé. L'artefact ne contient aucun identifiant,
texte, contact, URL ou prix individuel.

## Référence historique

| Indicateur | Valeur |
| --- | ---: |
| Observations avant | 2 442 |
| Observations exclues | 1 |
| Observations restantes | 2 441 |

Ces valeurs servent de comparaison et ne sont pas imposées artificiellement, car la
base Neon continue d'évoluer.
