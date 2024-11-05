import sys
import os
from pathlib import Path

# Sett opp prosjektstrukturen
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Sett arbeidskatalog
os.chdir(project_root)

# Opprett logs-mappe
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Importer hovedapplikasjonen
from data.src.snofokk.app import main

# Kjør applikasjonen
if __name__ == "__main__":
    main()