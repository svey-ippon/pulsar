/!\ Ce document contient mes notes, en cours d'exploration, développement
/!\ Il devra être consolidé en cours ou à la fin de l'exploration
/!\ La langue française est temporaire, le document devra être en anglais

# PULSAR-CUBE vs Snowflake Intelligence

## Point Commun aux deux

PROs :
- réponse cadré par le modèle sémantique. Bonne description -> très bonne qualité des réponses
- le modèle sémantique dans les deux cas permet une génération du SQL propre et maitrisée
- simple à l'usage par un agent (probablement Mistral Ready au besoin, à tester)
- dans les deux cas on peut cadrer l'agent avec des instructions détaillée

CONs :
- le modèle sémantique est à maintenir, c'est du 1 <-> 1 avec un gold, avec apports de détails :
  - dim / fact / measure
  - joins
  - ...
  - ->  ça reste à maintenir dans les deux cas même si avec un gold bien décrit on a 90% des infos

Voir si les questions hors jeux sont traité de la même manière par les deux. ça peut être la seule diff

## Avantages Snowflake Intelligence

- une interface abouti : SQL généré / présentation sous forme de graphiques
- rien d'autres que l'ajout d'objet (couche sémantique, description d'un agent), pas d'infra
- la gestion RBAC intégré
- génération de SQL plus avancé (eg. avec set-intersection logic). Côté cube-core, il faudrait partir sur des outils wrappers de la SQL API, faisable mais un peu de travail pour qu'il soit bien compris des LLMs

## Avantage Solution Maison Cube-core

- le cout d'une session, INFERENCE 50% plus chère côté Snowflake Intelligence
- la maitrise de la stack


## le delta cout

- les données ne sont pas volumineuses sur le POC, un warehouse XS est large
- on a pour les deux 0.50$ / 10min de compute
- snowflake intelligence : 3.75$ / 10min (les 17 questions)
- cube-core : 2.40$ / 10min

-> différence de 1.35$ / 0.17H -> ~8$/H

pour 'amortir', 150$/mois (hors développement, pur cout infra, inférence ...) -> 19H de chat actif
