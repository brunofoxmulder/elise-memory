# Élise Memory

Paquet Python embarqué par l'App Home Assistant Élise Memory.

Cette arborescence est la **source unique** du code exécuté dans le conteneur.
Les tests CI installent directement ce paquet et construisent ensuite l'image
Home Assistant réelle.

Aucun ID de classeur Google, credential ou secret utilisateur n'est embarqué
dans ce paquet. Les coordonnées des sources sont fournies uniquement à
l'exécution par la configuration privée de l'App.
