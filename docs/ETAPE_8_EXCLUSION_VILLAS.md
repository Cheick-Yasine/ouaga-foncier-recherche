# Étape 8 — Exclusion du type villa

## Objectif

Retirer les villas du futur jeu de données de recherche après les phases déjà
validées, sans modifier la table source Neon.

## Règle métier

- une annonce dont le type structuré est `villa` ou `villas` est exclue ;
- une annonce non typée ou classée `autre` qui décrit clairement une villa est
  également exclue ;
- une villa n'est jamais transformée en `maison` ;
- les catégories conservées sont `terrain`, `parcelle` et `maison` ;
- un type encore incertain mais ne signalant pas une villa est conservé et
  comptabilisé dans `types_a_confirmer_conserves` ;
- une parcelle ou un terrain explicitement typé reste conservé même si son texte
  évoque la construction future d'une villa.

Cette dernière règle évite d'exclure par erreur une parcelle à vendre simplement
parce que l'annonce explique qu'elle convient à une villa.

## Ordre d'exécution

1. chargement de `public.annonces` ;
2. déduplication par URL ou texte normalisé ;
3. normalisation et restriction géographique ;
4. contrôle des prix observés ;
5. exclusion des villas.

## Audit et confidentialité

Le workflow manuel **Audit exclusion des villas** ouvre une transaction Neon en
lecture seule. La trace détaillée contenant les identifiants reste dans le
répertoire temporaire du runner. Seul le rapport JSON agrégé est publié pendant
sept jours.

L'artefact ne contient ni texte d'annonce, ni contact, ni URL, ni identifiant, ni
valeur individuelle.

## Référence historique

| Indicateur | Valeur |
| --- | ---: |
| Observations avant | 2 441 |
| Villas exclues | 135 |
| Observations restantes | 2 306 |

La référence sert uniquement à expliquer l'ancien traitement. Les résultats
actuels peuvent être différents puisque la base Neon évolue et que la règle de
déduplication a été corrigée.
