# Recentrage de la solution - Sujet 5

## Décision importante

La base principale du projet n'est pas Hugging Face.

La base principale est le dossier `Sujet5`, surtout :

- `Sujet5/MiseEnJambe`
- `Sujet5/Généralisation`

Ces fichiers ne sont pas seulement des exemples administratifs. Ils représentent déjà une chaîne de computer vision simulée ou préparée :

- métadonnées d'images satellites ;
- annotations COCO ;
- résultats de détection ;
- catégories de navires ;
- distinction civil / militaire ;
- zones sensibles ;
- niveaux de risque.

Le problème principal n'est donc pas de refaire toute la détection d'image. Le vrai enjeu court terme est de transformer ces résultats en renseignement exploitable.

## Ce qu'on garde comme hypothèse

Les images ne sont pas accessibles via les URLs, car les liens pointent vers `example.com`.

Mais ce n'est pas bloquant pour un MVP, car les résultats de vision sont déjà fournis :

- `annotations_large.json` donne une vérité terrain structurée ;
- `detection_results.csv` donne des objets détectés ;
- `images_metadata_large.csv` donne les zones, coordonnées, sources et conditions ;
- `military_zones.csv` donne des points de zones militaires ou sensibles.

On doit donc exploiter la sortie de la computer vision, pas forcément refaire la computer vision immédiatement.

## Rôle de Hugging Face

Le dataset Hugging Face reste utile, mais comme source secondaire.

Il peut servir à :

- montrer de vraies images satellites ;
- comprendre un vrai format image + label YOLO ;
- illustrer ce que seraient des patches annotés ;
- éventuellement entraîner une brique `boat / background`.

Mais il ne répond pas directement au sujet militaire, car les classes sont principalement :

- `boat`
- `background`
- `porte-conteneur`
- `inconnu`

Il ne permet donc pas, seul, de distinguer frégate, destroyer, porte-avions ou navire civil/militaire.

## Nouvelle formulation du MVP

Le MVP devient :

> À partir de résultats de computer vision déjà disponibles, construire une couche géospatiale et métier qui priorise les navires militaires détectés dans des zones sensibles.

La valeur du projet est donc dans la chaîne :

```text
detection image -> catégorie navire -> zone géographique -> niveau de risque -> score de priorité -> carte / briefing
```

## Ce qu'on doit produire en priorité

1. Comprendre les datasets fournis.
2. Nettoyer les coordonnées.
3. Fusionner métadonnées, détections et zones.
4. Calculer un score de priorité.
5. Produire une carte lisible.
6. Identifier les zones et détections les plus intéressantes.
7. Expliquer les limites : pas d'image directe, coordonnées au niveau zone, pas au niveau pixel géolocalisé.

## Limite géospatiale importante

Les détections n'ont pas de coordonnées GPS individuelles.

Elles ont :

- une bounding box dans l'image ;
- une zone associée ;
- les coordonnées de l'image / zone.

Donc la carte ne localise pas précisément chaque navire au mètre près. Elle localise les observations au niveau de la zone satellite.

Ce n'est pas une faiblesse si on l'explique clairement. Pour un outil de priorisation stratégique, une localisation par zone est déjà utile.

## Score recommandé

Un premier score simple peut suffire :

- +40 si le navire est militaire ;
- +25 si la zone est critique ;
- +15 si la zone est à risque élevé ;
- +15 si la confiance est supérieure ou égale à 0.85 ;
- +20 si le type est stratégique : porte-avions, sous-marin, destroyer, croiseur ;
- +10 si la zone correspond à une zone militaire active.

Ce score n'est pas une vérité opérationnelle. C'est une règle transparente pour trier les observations.

## Positionnement final

Le projet ne doit pas être présenté comme :

> Nous avons entraîné un modèle parfait de détection de navires militaires.

Il doit être présenté comme :

> Nous avons construit une chaîne de priorisation OSINT à partir de résultats de computer vision, pour aider un analyste à repérer rapidement les observations navales les plus sensibles.

L'humain reste au centre : il valide, interprète et décide. L'IA sert à accélérer le tri.
