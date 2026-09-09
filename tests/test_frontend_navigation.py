"""Vérifie les réponses concurrentes et la navigation avec le moteur JavaScript."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_conversation_navigation():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js nécessaire pour les tests de navigation')
    subprocess.run([node, '--test', 'tests/frontend/navigation.cjs'],
                   cwd=Path(__file__).resolve().parents[1], check=True)
