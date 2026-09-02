# Étape 9 — Extraction des caractéristiques textuelles

## Objectif

Transformer les informations décrites dans les annonces admissibles en variables
simples utilisables par le futur moteur de recherche. Cette phase ne supprime aucune
annonce et ne modifie pas Neon.

## Sources analysées

L'extraction utilise uniquement :

- `resume_court` ;
- `mots_cles_pertinents` ;
- `texte_nettoye` ;
- `statut_document` pour compléter la classification documentaire.

Les contacts WhatsApp ne sont jamais lus par cette phase.

## Proximité

| Valeur produite | Exemples de signaux |
| --- | --- |
| `centre_sante_hopital` | hôpital, clinique, CSPS, CMA, centre de santé |
| `ecole` | école, lycée, collège, université |
| `voie_bitumee` | goudron, bitume, route bitumée |
| `voie_route` | route, voie principale, axe principal |
| `plusieurs` | plusieurs familles distinctes détectées |
| `non_precisee` | aucun signal suffisamment clair |

Une expression telle que « route bitumée » donne seulement `voie_bitumee`.

## Viabilité

| Valeur produite | Règle |
| --- | --- |
| `eau` | eau, ONEA ou forage |
| `electricite` | électricité, SONABEL ou courant |
| `eau_et_electricite` | présence des deux familles |
| `non_precisee` | aucune information détectée |

## Statut documentaire

Les catégories produites sont :

- `titre_foncier` ;
- `puh` ;
- `attestation_attribution` ;
- `apfr` ;
- `plusieurs_documents` ;
- `non_precise`.

L'absence d'information reste une absence. Aucun document n'est supposé.

## Ordre du pipeline

1. déduplication ;
2. normalisation et restriction géographique ;
3. contrôle des prix ;
4. exclusion des villas ;
5. extraction des caractéristiques textuelles.

## Contrôle et confidentialité

Le workflow manuel **Audit caractéristiques textuelles** exécute les tests puis
ouvre Neon dans une transaction en lecture seule. Une trace détaillée reste
temporairement dans le runner. L'artefact publié contient seulement les effectifs
agrégés de chaque catégorie, sans identifiant, texte, URL, contact ou valeur
individuelle.

La prochaine étape d'imputation décidera comment représenter les valeurs non
précisées dans la base finale. Elle ne doit pas être confondue avec cette extraction.
