# Étape 4 — Référentiel géographique

## Objectif

Définir les quartiers et zones acceptés avant la préparation de la base de recherche.
Cette étape ne modifie pas Neon.

## Principes

- la valeur d'origine reste intacte ;
- une clé technique neutralise casse, accents, ponctuation et espaces ;
- seules les valeurs présentes dans le référentiel sont admises dans le périmètre ;
- une valeur inconnue reste `review_required` et n'est jamais inventée ;
- les zones potentiellement distinctes ne sont pas fusionnées sans validation métier.

## Variantes confirmées

| Variante | Valeur canonique |
| --- | --- |
| `Ouaga2000` | `Ouaga 2000` |
| `Ouagadougou 2000` | `Ouaga 2000` |
| `Centre-ville` | `Centre Ville` |
| `Cité An III` | `Cité An 3` |

`Baossa` et `Boassa`, ainsi que `Kamboinsé` et `Kamboinsin`, restent séparés en
attendant une validation explicite.

## Niveaux géographiques

- `quartier` : localisation exploitable directement dans le classement ;
- `commune_peripherique` : Loumbila, Saaba, Pabré, Koubri ou Komsilga ;
- `zone_administrative` ou `zone_large` : information utile mais moins précise ;
- `ville` : `Ouagadougou` confirme le périmètre sans fournir un quartier précis.

## Sécurité

Le workflow d'audit reste en lecture seule. La restriction géographique et les
écritures éventuelles dans une table préparée feront l'objet d'une autre pull
request et d'une validation distincte.
