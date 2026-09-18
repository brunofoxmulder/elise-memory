# Élise Memory

Mémoire locale déterministe pour le projet Maison Cognitive.

## Statut

Prototype isolé — aucune écriture dans Home Assistant.

## Principes

- une seule application, deux espaces logiques : `house` et `temporal`;
- persistance locale SQLite sous `/data`;
- API HTTP locale et minimale;
- aucune dépendance à un LLM;
- aucune commande ni modification Home Assistant;
- provenance et horodatage conservés pour chaque souvenir.

Le raccordement à Élise Live et le déploiement Home Assistant sont des étapes séparées, soumises à validation.
