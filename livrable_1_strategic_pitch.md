# Strategic Pitch — Sujet 5 : Chasse aux navires de guerre

## Angle choisi

Nous voulons construire un prototype capable de repérer des navires militaires visibles sur des images satellites ouvertes, puis de les replacer dans leur contexte géographique.

L'idée n'est pas seulement de dire : "il y a un bateau sur l'image".  
L'objectif est de transformer une image satellite brute en signal utile :

- où se trouve le navire ;
- quel type de navire il pourrait être ;
- s'il est proche d'une zone militaire ou stratégique ;
- si cette présence mérite une attention particulière.

## Problème traité

La Marine Nationale doit surveiller de vastes zones maritimes, souvent avec beaucoup d'incertitude. Les images satellites ouvertes donnent déjà accès à une partie de cette information, mais elles restent difficiles à exploiter rapidement à grande échelle.

Le problème concret est donc le suivant :

**comment détecter et prioriser automatiquement des navires militaires à partir de sources ouvertes, sans dépendre uniquement d'une analyse humaine image par image à cause du volume de données ?**

## Objectif

Notre objectif est de créer une première chaîne OSINT capable de :

- analyser des images satellites ;
- détecter les navires visibles ;
- distinguer autant que possible les navires civils des navires militaires ;
- croiser les détections avec des zones sensibles comme Toulon, Ormuz, Malacca, Suez ou Pearl Harbor ;
- générer un score simple de priorité pour aider à décider quelles observations méritent une analyse humaine.

Le livrable final ne sera pas seulement un modèle de vision.  
Ce sera une méthode complète : données, détection, classification, contexte géospatial et restitution exploitable.

## Pertinence pour la Marine Nationale

Ce sujet répond à un besoin évident : gagner du temps dans l'exploitation d'informations ouvertes.

Une image satellite seule ne suffit pas. Elle devient utile lorsqu'elle est liée à une zone, une date, un type de navire, un niveau de risque et une confiance de détection.

Pour la Marine Nationale, l'intérêt est de disposer d'un outil qui peut aider à :

- repérer plus vite des présences navales dans des zones sensibles ;
- enrichir une veille maritime à partir de sources publiques ;
- tester la valeur opérationnelle de l'IA sur des données non classifiées ;
- préparer le travail d'un analyste, sans chercher à le remplacer ;
- identifier les limites réelles des données ouvertes.

Ce point est important : notre prototype doit rester honnête.  
Il ne dira pas "voici la vérité". Il dira plutôt : **"voici les observations les plus intéressantes à vérifier en priorité."**

## Pourquoi maintenant ?

La quantité d'images satellites disponibles augmente fortement. En parallèle, les modèles de computer vision deviennent plus accessibles et plus rapides à tester.

Cela crée une opportunité : utiliser des outils simples, peu coûteux et reproductibles pour produire une première couche de renseignement maritime à partir de données ouvertes.

Attendre six mois, c'est laisser passer une fenêtre utile :

- les sources OSINT sont déjà disponibles ;
- les modèles de détection sont déjà assez matures pour un MVP ;
- les tensions maritimes rendent la surveillance des zones stratégiques plus critique ;
- les méthodes testées ici peuvent être réutilisées sur d'autres sujets : ports, infrastructures, activité anormale, évolution temporelle.

## Ce qui changerait si le prototype fonctionne

Si notre approche fonctionne, la Marine Nationale pourrait disposer d'un outil d'aide au tri.

Concrètement, cela permettrait de :

- réduire le temps passé à parcourir manuellement des images ;
- concentrer l'attention humaine sur les cas les plus prometteurs ;
- produire une cartographie rapide des navires détectés ;
- comparer différentes zones militaires ou stratégiques ;
- documenter les incertitudes plutôt que les cacher.

Les métriques importantes seraient :

- nombre de navires détectés ;
- taux de faux positifs ;
- précision de la classification civil / militaire ;
- temps de traitement par image ;
- nombre de zones sensibles couvertes ;
- qualité du score de priorité produit.

## Positionnement

Notre proposition n'est pas de remplacer l'expertise militaire.  
Elle consiste à créer un filtre intelligent entre la masse d'images disponibles et l'analyste humain.

Le cerveau humain reste essentiel pour :

- interpréter le contexte géopolitique ;
- juger si une détection est réellement intéressante ;
- reconnaître les limites d'un modèle ;
- choisir les zones à surveiller ;
- formuler les bonnes hypothèses opérationnelles.

L'IA apporte la vitesse.  
L'humain apporte le jugement.

Notre ambition est de combiner les deux pour produire une veille maritime plus rapide, plus structurée et plus défendable.
