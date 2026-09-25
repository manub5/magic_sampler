# Spécification — Choppeur

## Objectif
Extraire rapidement, depuis ses propres albums, des samples exploitables
dans une STAN (Bitwig) : boucles qui démarrent sur le premier temps de la
mesure, et one-shots propres.

## Parcours utilisateur
1. Dans le panneau bibliothèque, l'utilisateur ouvre un dossier racine
   (local ou NAS monté) et navigue : dossiers → albums → pistes.
2. Il lance l'analyse sur UNE piste ou sur UN album entier.
3. L'analyse tourne en arrière-plan ; l'interface reste utilisable.
4. Pour chaque piste analysée : forme d'onde affichée, tempo, marqueurs des
   premiers temps de mesure, et liste de plusieurs samples candidats.
5. Il préécoute chaque candidat (une boucle peut être jouée en répétition
   pour vérifier qu'elle « tourne »), coche ceux qu'il garde.
6. Il exporte : vers le dossier cible défini dans les paramètres, ou vers
   un dossier choisi au moment de l'export.

## Deux types de samples
### Boucles
- Début exactement sur un premier temps de mesure.
- Longueur : 1, 2, 4 ou 8 mesures (réglable).
- Plusieurs candidats par piste, classés par score (régularité du tempo sur
  la zone, énergie, absence de coupure brutale).

### One-shots
- Début sur une attaque nette.
- Fin : retour au silence relatif ou attaque suivante, avec court fondu.
- Durée maximale réglable.

## Nommage automatique
Format par défaut (modifiable dans les paramètres) :
`{artiste}_{album}_{piste}_{type}_{bpm}bpm_{mesures}bars_{position}.wav`
Exemple : `Burial_Untrue_03_loop_139bpm_4bars_01m12s.wav`
One-shot : `Burial_Untrue_03_shot_01m12s340.wav`
Caractères interdits nettoyés, pas d'écrasement (suffixe `_2`, `_3`…).

## Paramètres
- Dossier racine de la bibliothèque.
- Dossier cible d'export par défaut.
- Format d'export : WAV 24 bits (défaut) ou FLAC ; fréquence d'origine conservée.
- Longueurs de boucle proposées, nombre de candidats par piste.
- Durée maximale d'un one-shot.
- Utilisation du GPU : auto / forcé CPU.

## Hors périmètre (pour l'instant)
- Séparation de pistes (voix, batterie…) : projet séparé, pas de fusion prévue.
- Docker, web, serveur.
- Traitement de toute la bibliothèque en tâche de fond.

## Évolutions envisagées
- Fiche d'analyse « avant » : passages sans voix, boucles stables,
  sections percussives (voir ROADMAP, phase ultérieure).
- Détection de la tonalité, tri par tonalité.
- Glisser-déposer d'un candidat directement vers Bitwig.
