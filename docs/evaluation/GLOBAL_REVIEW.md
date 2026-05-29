/!\ Ce document contient mes notes, en cours d'exploration, développement
/!\ Il devra être consolidé en cours ou à la fin de l'exploration
/!\ La langue française est temporaire, le document devra être en anglais

# PULSAR - CUBE

PROs :
- réponse cadré par le modèle sémantique. Mesure non dispo dans le modèle ? pas dispo -> pas de dérive
- simple à l'usage par un agent (probablement Mistral Ready au besoin, à tester)

CONs :
- le modèle sémantique est à maintenir, ce sera probablement du 1 <-> 1 avec un gold, donc automatisable. Mais ça reste à maintenir
- une gestion des droits côté cube-core, style RBAC à mettre en place. Du boulot
- pas d'exploration hors couche sémantique (pas d'exploration d'un silver)
- cube-core comme élément de la stack, à déployer, dimensionner (intermédaire Snow <-> agent)
