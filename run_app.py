import streamlit as st
import sys
import os

# Legg til prosjektets rotkatalog i Python-stien
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Importer applikasjonen
from data.src.snofokk.app import main

if __name__ == "__main__":
    main()
