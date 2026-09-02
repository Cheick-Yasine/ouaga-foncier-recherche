# Étape 3A — Normalisation des types de biens

## Catégories finales

La plateforme utilise uniquement trois valeurs non nulles :

- `terrain` ;
- `parcelle` ;
- `maison`.

## Correspondances directes

| Valeur originale | Valeur normalisée |
|---|---|
| terrain | terrain |
| ferme | terrain |
| parcelle | parcelle |
| maison | maison |
| villa | valeur vide, annonce exclue |

Une villa ne devient jamais une maison. Elle ne participe pas aux futurs résultats de recherche.

La colonne d'origine `type_bien` reste intacte. La nouvelle valeur est placée dans `type_bien_normalise`.

## Traitement de `autre`

Les anciennes annonces `autre` sont analysées à partir de `resume_court` et `texte_nettoye`.

Une catégorie n'est retenue que lorsqu'une seule famille claire de mots-clés est détectée. Une annonce mentionnant une villa est exclue. Si le texte contient des signaux contradictoires ou aucun signal, `type_bien_normalise` reste vide et l'annonce est marquée comme étant à confirmer.

Cette règle évite de transformer une incertitude en fausse information.

## Sécurité de la migration

- simulation par défaut ;
- écriture uniquement avec l'option `--apply` ;
- nouvelle colonne : aucune suppression de l'ancienne ;
- contrainte PostgreSQL limitée aux trois catégories ;
- index ajouté pour accélérer les futurs filtres ;
- transaction annulée automatiquement en cas d'erreur.

## Simulation locale

```powershell
python -m scripts.migrate_property_types --output reports/type-bien-dry-run.json
```

## Application locale

À exécuter seulement après validation du rapport de simulation :

```powershell
python -m scripts.migrate_property_types --apply --output reports/type-bien-applied.json
```
