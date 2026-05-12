# Plan d'action data - Sujet 5

## Position de départ

Les fichiers fournis sont utiles pour construire un MVP, mais ils ne contiennent pas les vraies images satellites.

Les URLs des CSV pointent vers `example.com`, donc elles sont factices. On peut tout de même utiliser les métadonnées, les annotations COCO, les résultats de détection et les zones militaires pour préparer une première chaîne de traitement.

## Objectif court terme

Construire une base data propre avant de faire de la détection d'image.

Le but immédiat est de savoir :

- quelles données sont disponibles ;
- ce qu'elles décrivent exactement ;
- ce qui est exploitable pour un MVP ;
- ce qui manque pour entraîner ou tester un modèle ;
- quelles images réelles récupérer en priorité.

## Étape 1 - Comprendre les fichiers fournis

À faire maintenant :

- répondre au README de `MiseEnJambe` dans un notebook simple ;
- répondre au README de `Généralisation` dans un notebook simple ;
- documenter clairement les limites : images absentes, URLs factices, zones militaires pas encore harmonisées avec de vrais polygones.

Livrables créés :

- `Sujet5/MiseEnJambe/reponses_mise_en_jambe_detection_navires.ipynb`
- `Sujet5/Généralisation/reponses_generalisation_detection_navires.ipynb`

## Étape 2 - Garder les données fournies comme MVP data

Les fichiers les plus utiles sont :

- `images_metadata_large.csv` : contexte image, zone, pays, résolution, source, couverture nuageuse ;
- `annotations_large.json` : vérité terrain au format COCO ;
- `detection_results.csv` : détections déjà structurées ;
- `military_zones.csv` : zones sensibles ou militaires.

Ces fichiers permettent déjà de construire :

- une analyse exploratoire ;
- une table enrichie des détections ;
- un marquage civil / militaire ;
- un score de priorité ;
- un premier tableau des observations importantes.

## Étape 3 - Récupérer un petit lot d'images réelles

Ne pas chercher à télécharger un dataset massif au début.

Priorité :

1. Hugging Face `DefendIntelligence/vessel-detection-labeled-patches`
2. Kaggle `Ships in Satellite Imagery`
3. Maxar Open Data si une zone intéressante est disponible rapidement
4. xView si l'accès est simple
5. Sentinel Hub / Google Earth Engine seulement si on a le temps de gérer les APIs

À faire à la main si nécessaire :

- créer un compte Kaggle ou Hugging Face ;
- accepter les conditions d'accès aux datasets ;
- télécharger un petit échantillon d'images ;
- placer les images dans un dossier clair, par exemple `Sujet5/data/images_reelles/` ;
- noter la source et la licence dans un fichier `sources_images.md`.

## Étape 4 - Vérifier manuellement les images

Avant tout modèle :

- ouvrir 5 à 10 images ;
- vérifier si les navires sont réellement visibles ;
- noter la résolution et la difficulté ;
- repérer les cas simples et les cas ambigus ;
- comparer avec les annotations si elles existent.

Cette étape est importante car elle évite de perdre du temps sur un modèle si les images sont trop faibles ou mal adaptées.

## Étape 5 - Préparer le score de priorité

Le scoring peut être construit avant le modèle d'image.

Exemple simple :

- +40 si le navire est militaire ;
- +25 si la zone est critique ;
- +15 si la zone est à risque élevé ;
- +15 si la confiance est supérieure à 0.85 ;
- +20 si le type est stratégique : porte-avions, sous-marin, destroyer, croiseur.

Ce score servira à transformer les données en outil d'aide à la décision.

## Étape 6 - Passer seulement ensuite à l'image

Quand les images réelles sont disponibles :

- afficher les bounding boxes ;
- tester un modèle pré-entraîné ;
- comparer prédictions et annotations ;
- mesurer quelques métriques simples ;
- garder une présentation honnête des limites.

L'objectif n'est pas de vendre un modèle parfait. L'objectif est de montrer une chaîne OSINT crédible, rapide et améliorable.
