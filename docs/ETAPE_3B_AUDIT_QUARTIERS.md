# Étape 3B — Audit des quartiers

## Objectif

Avant toute normalisation, inventorier les valeurs de `quartier_zone` et repérer :

- les différences de majuscules et minuscules ;
- les accents et apostrophes différents ;
- les espaces manquants ;
- les variantes connues ;
- les valeurs composées ou ambiguës à examiner.

## Principe de prudence

L'audit ne transforme pas automatiquement toutes les chaînes en noms de quartiers. Il propose une valeur canonique uniquement lorsqu'une correspondance connue a été définie.

Exemples initiaux :

| Variante | Proposition |
|---|---|
| OUAGA2000 | Ouaga 2000 |
| Ouaga 2000 | Ouaga 2000 |
| RIMKIETA | Rimkiéta |
| boassa | Boassa |

Les formulations inconnues restent marquées `review_required`.

## Données produites

Le rapport JSON contient :

- le nombre total de lignes ;
- les quartiers manquants ;
- toutes les valeurs distinctes et leurs effectifs ;
- les groupes de variantes équivalentes ;
- les propositions connues ;
- les valeurs nécessitant une validation.

L'audit est en lecture seule et ne contient ni texte d'annonce, ni numéro WhatsApp.

## Exécution

```powershell
python -m scripts.audit_neighborhoods --output reports/quartiers-audit.json
```
