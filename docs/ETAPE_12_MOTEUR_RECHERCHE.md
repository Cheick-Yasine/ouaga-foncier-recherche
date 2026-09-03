# Étape 12 — Moteur de recherche hybride

## Objectif

Classer les annonces les plus proches d'une description libre, tout en respectant
les contraintes explicites de l'utilisateur.

Cette première version construit le cœur testable du classement. Le branchement à
Neon sera réalisé à l'étape suivante.

## Interprétation de la description

L'API `POST /search/interpret` reconnaît notamment :

- le type de bien : terrain, parcelle ou maison ;
- le quartier ou la zone ;
- le prix exprimé en FCFA, millions ou milliards ;
- la superficie en m² ;
- la notion de budget maximum ;
- la proximité ;
- la viabilité ;
- le statut documentaire.

Exemple :

```json
{
  "description": "Parcelle à Saaba de 400 m², budget maximum 8 millions, avec PUH",
  "required_fields": ["quartier", "prix"],
  "max_age_days": 7
}
```

## Similarité textuelle

Le texte de la demande et celui de l'annonce sont normalisés puis représentés par
leurs mots et groupes de deux mots. La similarité cosinus mesure leur orientation :

- 100 % : vocabulaire identique ;
- proche de 0 % : vocabulaire très différent.

Cette méthode constitue une base locale, explicable et sans coût d'API. Une
représentation sémantique avec `pgvector` pourra ensuite améliorer la compréhension
des synonymes et formulations différentes.

## Score hybride initial

| Composante | Poids |
| --- | ---: |
| Similarité du texte | 35 % |
| Quartier | 20 % |
| Prix | 15 % |
| Superficie | 15 % |
| Type de bien | 8 % |
| Document | 3 % |
| Proximité | 2 % |
| Viabilité | 2 % |

Les poids sont centralisés et pourront être ajustés à partir de cas réels validés.

## Valeurs absentes

Une annonce sans prix ou sans superficie reste candidate, conformément à la règle
validée. Toutefois, une information absente :

- ne reçoit aucun point ;
- réduit le taux de couverture du résultat ;
- est indiquée dans l'explication ;
- élimine l'annonce si le champ a été déclaré obligatoire.

Ainsi, une valeur manquante ne donne aucun avantage artificiel.

## Contraintes strictes

- une annonce dépassant un budget maximum est exclue ;
- une catégorie obligatoire absente ou différente est exclue ;
- une annonce âgée de plus de sept jours est exclue ;
- les préférences non obligatoires influencent le score sans bloquer le résultat.

## Explications fournies

Chaque résultat contient :

- le score final sur 100 ;
- la couverture des critères sur 100 ;
- les composantes détaillées ;
- des raisons lisibles, par exemple « même quartier », « même type de bien »,
  « respecte le budget maximum » ou « information absente : prix ».

## Prochaine étape

La prochaine étape construira le dépôt de lecture Neon, assemblera les 3 288
annonces préparées, appliquera la limite des sept jours et exposera le véritable
endpoint `POST /search`.
