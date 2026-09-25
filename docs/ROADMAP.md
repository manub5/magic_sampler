# Feuille de route — une étape à la fois, validée avant la suivante

1. Squelette : `pyproject.toml`, arborescence, `uv run choppeur` ouvre une
   fenêtre vide. Tests qui passent.
2. Moteur rythme : `core/rhythm.py` sur un fichier donné → tempo, temps,
   premiers temps. Test sur 3 morceaux réels choisis par l'utilisateur.
3. Moteur candidats boucles + export d'un WAV nommé (sans interface).
4. Moteur one-shots.
5. Cache SQLite.
6. Interface : navigation bibliothèque.
7. Interface : forme d'onde + marqueurs.
8. Interface : liste des candidats, préécoute (boucle répétée), export.
9. Paramètres (fichier TOML + fenêtre).
10. Analyse d'un album entier en arrière-plan avec barre de progression.
11. Paquet distribuable pour le prêt (à décider à ce moment-là).
Plus tard : fiche d'analyse « avant » (passages sans voix, etc.).
