# UI FIX

Bug, reasoning box also as the last message appended. Duplicate

Quand l'agent s'emballe (question difficile, essaye des query mais se prend un mur), pas moyen de l'arrêter depuis l'UI ...

# PROMPT FIX

après 4 requêtes qui sortent des erreurs "Cube rejected the query." ne pass s'acharner, exposer le raisonnement et les limites

# QUESTIONS EVALUATION
-> j'en suis à M2

# AGENT TEST :
voir `learning_must_read.md` -> Question M1 - détournement
sénario où l'agent injecte de la connaissance propre, on a forcé le prompt pour transparence du modèle, mais ce serait bien d'avoir un test dédié

## sur la même question:
 - on a corrigé le join `products → product_category_name_translation` dans le modèle sémantique
 - ce serait bien de mettre en place des tests de non regression de nos modèles (des questions auquels le LLM doit savoir répondre + ce qui est testé en description)
- mais c'est des tests du modèle sémantiques plus que des tests de l'agent
