# Décisions techniques (et pourquoi)

## Détection des temps et du premier temps de mesure : beat_this, pas madmom
- madmom : dernière version PyPI 0.16.1, qui ne gère que Python < 3.10 et
  numpy < 1.20 ; installation seulement depuis GitHub. Ses modèles sont sous
  licence non commerciale (CC BY-NC-SA) — gênant pour un logiciel prêté.
- beat_this (même labo, CPJKU, ISMIR 2024) : détecte temps et premiers temps
  de mesure sans post-traitement probabiliste ; code et modèles sous MIT.
- Contrepartie : dépend de PyTorch (installation lourde). On l'appelle sans
  l'option `dbn` pour ne pas dépendre de madmom.
- Incertitude : précision non vérifiée sur ambient/musiques sans percussions.
  À tester sur des morceaux réels dès l'étape 2 de la ROADMAP.

## Attaques, séparation percussif/harmonique, tempo : librosa 0.11.0
- Version stable du 11/03/2025, bibliothèque de référence, maintenue.

## Interface : PySide6
- Qt natif, cohérent sous KDE, sans navigateur ni serveur.
- Licence LGPL (compatible avec un prêt/diffusion).
- Riche et extensible : répond au besoin d'« élaborations futures ».

## Cache SQLite
- La bibliothèque peut être très grande : on mémorise les analyses
  (clé = chemin + taille + date de modification) pour ne jamais recalculer.

## uv pour l'environnement Python
- Un seul fichier `pyproject.toml` + verrou `uv.lock` : installation
  identique chez une autre personne.

## Installation de beat_this depuis PyPI, pas depuis l'archive GitHub
- Le paquet `beat-this` (même code, mêmes auteurs CPJKU) est aussi publié sur
  PyPI depuis la version 1.1.0, en plus de l'installation `pip install
  https://github.com/CPJKU/beat_this/archive/main.zip` documentée dans leur
  README. Les deux installent le même module `beat_this`.
- On utilise la version PyPI (`beat-this>=1.1.0`) : plus stable (numéro de
  version figé, pas "main" qui peut changer), et n'exige pas d'accès à
  `github.com` au moment de l'installation.
- Les poids du modèle, eux, se téléchargent automatiquement au premier lancement
  depuis le cloud de la JKU (`cloud.cp.jku.at`), pas depuis GitHub.

## Roues CPU de PyTorch par défaut
- `torch`/`torchaudio` installés depuis l'index CPU officiel
  (`download.pytorch.org/whl/cpu`, voir `[tool.uv.index]` dans
  `pyproject.toml`) plutôt que les roues par défaut de PyPI, qui embarquent
  ~2,5 Go de bibliothèques CUDA même sans GPU NVIDIA.
- Le logiciel reste utilisable sans GPU (voir portabilité dans CLAUDE.md).
  Sur une machine avec GPU NVIDIA, réinstaller `torch`/`torchaudio` avec les
  roues CUDA correspondantes (voir pytorch.org/get-started/locally) pour
  accélérer l'analyse.
