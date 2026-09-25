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

## Paquet distribuable (étape 11) : pas encore de paquet autonome
- `docs/ROADMAP.md` reporte explicitement ce choix ("à décider à ce
  moment-là"). Ce qui est fait pour l'instant : `pyproject.toml` produit un
  paquet Python standard, validé avec `uv build` (`choppeur-0.1.0.tar.gz` +
  `.whl`), avec le point d'entrée `choppeur = choppeur.app:main`.
- Installation actuelle chez la personne à qui le logiciel est prêté :
  `uv sync && uv run choppeur` (déjà documenté dans README.md), qui suppose
  `uv` installé chez elle.
- Non fait : un exécutable autonome (ex. PyInstaller) qui embarquerait
  PySide6 + PyTorch. C'est notoirement fragile à mettre au point (taille,
  compatibilité GPU/CPU selon la machine cible) ; le choix concret de l'outil
  dépend de la machine de la personne à qui le logiciel sera prêté, donc
  reporté comme prévu par la ROADMAP plutôt que décidé arbitrairement ici.

## Corrections suite au premier essai réel (Kubuntu 24.04, KDE Plasma)

### Bibliothèque : chargement dossier par dossier, pas tout l'arbre d'un coup
- Bug : `LibraryPanel` parcourait toute l'arborescence récursivement dès
  `set_root()`. Sur un NAS/dossier réseau (latence par accès, parfois des
  milliers de fichiers), ça pouvait geler l'interface durablement, voire
  tourner indéfiniment sur un lien symbolique circulaire — perçu comme
  "impossible à charger".
- Correctif : un seul niveau chargé à la fois ; un dossier reçoit un enfant
  provisoire ("…") et n'est réellement lu qu'à son ouverture (signal
  `itemExpanded`). Une entrée illisible (lien cassé, droit réseau refusé) est
  ignorée individuellement au lieu d'interrompre tout le dossier. Si le
  dossier racine choisi est lui-même illisible, `load_failed` est émis et
  affiché dans la barre de statut plutôt que de laisser un panneau vide sans
  explication.
- Incertitude restante : un partage réseau exposé uniquement via un
  protocole KIO de Dolphin (`smb://…`) sans montage FUSE/gvfs réel ne
  correspond à aucun chemin de fichier local ; un tel chemin choisi dans la
  boîte de dialogue resterait illisible pour Python. À vérifier : le dossier
  doit être monté (Dolphin propose en général de le monter automatiquement
  via gvfs, ce qui le rend accessible comme un dossier normal).

### Préécoute : erreurs remontées au lieu d'être avalées silencieusement
- Bug : une exception de `sounddevice` (ex. aucun périphérique de sortie
  disponible/configuré) était avalée silencieusement par Qt (les exceptions
  dans un slot ne remontent pas) : cliquer sur "Préécouter" ne faisait
  simplement rien, sans indice sur la cause.
- Correctif : `sd.play`/`sd.stop` sont maintenant protégés ; toute erreur est
  émise via le signal `preview_failed` et affichée dans la barre de statut.
  Cocher un candidat sans avoir cliqué dessus (sélection Qt "courante" non
  positionnée) est aussi couvert : la préécoute retombe sur le premier
  candidat coché s'il n'y a pas de ligne sélectionnée.
- Incertitude : non testable dans cet environnement de développement (aucun
  périphérique audio dans ce bac à sable — `sounddevice.query_devices()` y
  est vide). Le prochain clic sur "Préécouter" chez toi affichera le message
  d'erreur exact de PortAudio dans la barre de statut si ça échoue encore ;
  ce message précisera la vraie cause.

### Artefacts d'affichage ("zébrures") en session Wayland
- Sur KDE Plasma/Kubuntu, certaines applications Qt Widgets ont des bugs de
  rafraîchissement connus en session Wayland native (zones mal repeintes).
  `app.py` force maintenant XCB (X11 via XWayland) par défaut quand
  `XDG_SESSION_TYPE=wayland` et qu'aucun `QT_QPA_PLATFORM` n'est déjà choisi
  explicitement — XCB est le chemin le plus éprouvé pour PySide6 côté
  widgets.
- Incertitude : non vérifiable ici (pas d'affichage réel dans ce bac à
  sable). Si des zébrures persistent malgré XCB, ou si XCB pose un autre
  problème (affichage flou en cas d'écran haute résolution, par exemple),
  fixer explicitement `QT_QPA_PLATFORM=wayland` (ou une autre valeur) avant
  `uv run choppeur` annule ce choix automatique.
- Le fait que l'ancien chargement récursif de la bibliothèque provoquait
  aussi énormément de mises à jour de widgets d'un coup a pu aggraver ou
  causer ces artefacts ; le correctif de chargement paresseux ci-dessus
  devrait déjà réduire le phénomène indépendamment du choix XCB/Wayland.
