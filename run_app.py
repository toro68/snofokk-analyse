import streamlit as st
import sys
import os
from pathlib import Path

# Legg til prosjektets rotkatalog i Python-stien
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Sett arbeidskatalog til prosjektets rot
os.chdir(project_root)

# Opprett logs-mappe hvis den ikke finnes
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Importer applikasjonen
from data.src.snofokk.app import main

if __name__ == "__main__":
    main()
