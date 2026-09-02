# Étape 6 — Préparation géographique

## Objectif

Simuler la normalisation des quartiers puis la restriction à Ouagadougou et aux
zones périphériques du référentiel validé. Cette étape intervient après la
déduplication certaine et ne modifie pas Neon.

## Règle de sélection du quartier

1. rechercher les 102 zones canoniques et leurs variantes dans `texte_nettoye` ;
2. si une seule zone est détectée, l'utiliser comme `quartier_final` ;
3. si aucune ou plusieurs zones sont détectées, utiliser `quartier_zone` comme repli ;
4. si le repli n'appartient pas au référentiel, marquer l'annonce hors périmètre.

Les noms longs sont prioritaires. Par exemple, `Dapoya 2` n'est pas réduit à
`Dapoya`. Les annonces hors périmètre ne sont pas supprimées de `public.annonces` :
elles sont uniquement absentes du futur jeu de recherche.

## Traçabilité

Le rapport JSON contient les volumes de chaque phase et les répartitions par source,
type de zone et niveau de précision. Le CSV associe chaque identifiant à :

- son quartier final ;
- la source utilisée ;
- le nombre de zones détectées dans le texte ;
- le niveau de précision ;
- la décision de conservation ou d'exclusion.

Aucun texte d'annonce et aucun contact WhatsApp ne sont exportés.

## Référence historique

| Indicateur | Valeur |
| --- | ---: |
| Observations avant restriction | 4 551 |
| Observations hors périmètre | 2 109 |
| Observations restantes | 2 442 |

Ces nombres restent une référence historique. Le rapport affiche les écarts sans
forcer artificiellement les résultats actuels.
