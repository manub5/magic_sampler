# Choppeur

Extraction automatique de samples (boucles calées sur la mesure et one-shots)
depuis sa bibliothèque d'albums, avec préécoute et export nommé.

## Prérequis
- Linux, Python 3.12, `uv`, `ffmpeg` (lecture MP3/AAC), `libportaudio2`.
- GPU NVIDIA facultatif (accélère l'analyse).

## Installation
    uv sync
    uv run choppeur

Documentation : `docs/SPEC.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`.
