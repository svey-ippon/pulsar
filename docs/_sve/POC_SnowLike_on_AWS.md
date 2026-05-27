
A déterminer très rapidement :

Ce que l'on cherche comme gestion des droits :
- une fois connecté à l'appli, tous les utilisateurs ont les mêmes droits -> facile
- les droits dépendent de l'utilisateur, c'est un chantier

# Phase 1

Mise en place d'une infrastructure basique :
- interface graphique Streamlit
- première version simple de l'agent, avec outils pour interrogation de la couche sémantique
- mise en place d'une couche sémantique via cube-core

## Chat UI

Une interface simple pour la première version du POC = application développé en python / streamlit.  

Intéret : 
- une UI développé de manière rapide, pour valider le fonctionnement du reste de la stack
- éprouver les interactions entre UI / agent (affichage des données structurés tableau / graphique)

### SCOPE
- utilise l'agent via API
- streaming des réponses
- définition du format d'échanges des données structurées (tableaux) et la manière de les intégrer naturellement dans l'interface
- authentification simple (à définir, soit via cognito, soit in-app)
- pas de mémoire entre les sessions (mémoire interne à l'application)


## Agent 

Première version simple de l'agent, application python développé sous LangGraph + FastAPI

Intérêt :
- développer les première briques de l'agent

### SCOPE
- mémoire interne (redémarrage de l'instance -> perte de la mémoire de l'agent)
- client LLM branché à Bedrock
- prompt standard, sans injection de contexte, pas de context store
- utilisation des outils modèles sémantiques développés
- agent ReAct standard (c'est le LLM qui gère la réflexion de manière autonome) pas de boucle plan -> act -> observe -> reflect

### Itérations suivantes
- mémoire externe (redis ou autre)
- fonctionnement serverless (lambda + API Gateway)
- injection d'un context via context store
- développement d'un graph agent pour plus d'intelligence

## Modèle sémantique

Modèle sémantique sur données tests développé avec cube-core:
- le modèle est défini sous forme de YAML, via IaC, c'est un format 'cube'
- maintenance à charge des développeurs (l'outil cube_dbt peut faciliter le développement)

- mise à disposition du modèle sémantique via API (différents entrypoint: description du modèle, réalisation de requêtes...)
- /!\ cube ne fourni pas de MCP (outil tout fait mis à disposition pour les agents)
- cube-core est branché sur Snowflake, un user + role, il réalise les requêtes et renvoi 


- pas de notion de droits sur les entités du modèles

## Outil de l'agent

Les outils qu'utilise l'agent pour interroger le modèle sémantique n'est pas fourni pas cube-core. Il faut un wrapper

### Quoi
les outils que doit avoir l'agent :
- `list_cubes`
- `get_cube_schema`
- `query_cube`
- `validate_query`
- `get_query_sql`

### Comment
Version minimale :
- développement des outils au coeur de l'agent (module python de l'agent)
- -> n'ajoute pas de couche supplémentaire

Version MCP :
- développement d'un MCP qui met à disposition ces outils
- -> pourra être réutilisé par d'autres projets qui souhaite intégrer l'interrogation d'une couche sémantique à un agent



## Authentification

Version très simple:
- une authentification via login / mdp ou Cognito
- accès tout ou rien. Une fois authentifié, l'agent (aka. l'utilisateur) a accès à l'ensemble du modèle sémantique en lecture seule


## Observabilité
