# Hugging Face Spaces entry point -- just runs Introduction.py
import subprocess
import sys
sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", "Introduction.py", "--server.port=7860", "--server.address=0.0.0.0"]))
