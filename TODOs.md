# UI :

A tester sur question M1 :
- le raisonnement s'affiche comme du texte standard, pas de séparation avec la réponse finale
- pour la dernière réponse du LLM, c'est affiché ainsi
- pour les réponse précédente, ce n'est plus inclu

-> on voudrait :
- que ce soit affiché dans la petite box déplié lors de la génération
- que la box soit replié une fois la réponse finie
- que ce soit toujours accessible dans les réponses précédentes
- (other fix) : la box affiche toujours 'generating answer...' même quand elle a fini


# AGENT TEST :
voir `learning_must_read.md` -> Question M1 - détournement
sénario où l'agent injecte de la connaissance propre, on a forcé le prompt pour transparence du modèle, mais ce serait bien d'avoir un test dédié

## sur la même question:
 - on a corrigé le join `products → product_category_name_translation` dans le modèle sémantique
 - ce serait bien de même en place des tests de non regression de nos modèles (des questions auquels le LLM doit savoir répondre + ce qui est testé en description)
- mais c'est des tests du modèle sémantiques plus que des tests de l'agent
