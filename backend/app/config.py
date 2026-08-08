"""Central configuration. Everything has a safe default so the app boots with zero setup."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------- Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_ANON_KEY", "").strip()
)
SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_KEY)

# ------------------------------------------------------------------- Cache ---
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
OFFLINE_CACHE = DATA_DIR / "offline_cache.json"   # low-bandwidth / offline bundle
LOCAL_DB = DATA_DIR / "agrisense_demo.db"         # SQLite mirror used when offline

# ------------------------------------------------------------------ Server ---
PORT = int(os.getenv("PORT", "8000"))
API_PREFIX = "/api"
APP_NAME = "AgriSense — Hyper-Local Climate Intelligence & Precision Agriculture DSS"
APP_VERSION = "1.0.0"

# ---------------------------------------------------------------- Agronomy ---
# Kc = FAO-56 crop coefficient by growth stage. Used for ET-based water balance.
CROP_LIBRARY = {
    "Rice": {
        "kc": {"initial": 1.05, "development": 1.10, "mid": 1.20, "late": 0.90},
        "duration_days": 135, "base_temp": 10.0,
        "n_p_k": (120, 60, 60), "potential_yield": 6.5,
        "root_depth_mm": 400, "critical_moisture": 0.32,
        "rotation": ["Blackgram", "Sesame", "Maize"],
    },
    "Banana": {
        "kc": {"initial": 0.50, "development": 0.90, "mid": 1.10, "late": 1.00},
        "duration_days": 330, "base_temp": 14.0,
        "n_p_k": (200, 100, 300), "potential_yield": 55.0,
        "root_depth_mm": 600, "critical_moisture": 0.28,
        "rotation": ["Cowpea", "Turmeric"],
    },
    "Coconut": {
        "kc": {"initial": 0.90, "development": 0.95, "mid": 1.00, "late": 0.95},
        "duration_days": 365, "base_temp": 15.0,
        "n_p_k": (500, 320, 1200), "potential_yield": 12.0,
        "root_depth_mm": 1200, "critical_moisture": 0.22,
        "rotation": ["Intercrop: Cocoa", "Intercrop: Pineapple"],
    },
    "Maize": {
        "kc": {"initial": 0.40, "development": 0.80, "mid": 1.15, "late": 0.65},
        "duration_days": 110, "base_temp": 10.0,
        "n_p_k": (135, 62, 50), "potential_yield": 8.0,
        "root_depth_mm": 700, "critical_moisture": 0.20,
        "rotation": ["Blackgram", "Groundnut", "Rice"],
    },
    "Groundnut": {
        "kc": {"initial": 0.45, "development": 0.85, "mid": 1.05, "late": 0.65},
        "duration_days": 105, "base_temp": 12.0,
        "n_p_k": (25, 50, 75), "potential_yield": 2.8,
        "root_depth_mm": 500, "critical_moisture": 0.18,
        "rotation": ["Maize", "Rice", "Sorghum"],
    },
    "Black Pepper": {
        "kc": {"initial": 0.60, "development": 0.90, "mid": 1.05, "late": 0.95},
        "duration_days": 365, "base_temp": 15.0,
        "n_p_k": (100, 40, 140), "potential_yield": 3.5,
        "root_depth_mm": 800, "critical_moisture": 0.26,
        "rotation": ["Intercrop: Ginger", "Intercrop: Coffee"],
    },
    "Tapioca": {
        "kc": {"initial": 0.40, "development": 0.80, "mid": 1.10, "late": 0.55},
        "duration_days": 270, "base_temp": 13.0,
        "n_p_k": (100, 50, 100), "potential_yield": 32.0,
        "root_depth_mm": 600, "critical_moisture": 0.17,
        "rotation": ["Cowpea", "Maize"],
    },
}

SOIL_LIBRARY = {
    "Laterite":       {"fc": 0.30, "pwp": 0.14, "infiltration": 18, "ideal_ph": (5.5, 6.5)},
    "Alluvial":       {"fc": 0.36, "pwp": 0.16, "infiltration": 12, "ideal_ph": (6.0, 7.5)},
    "Clay Loam":      {"fc": 0.40, "pwp": 0.22, "infiltration": 6,  "ideal_ph": (6.0, 7.0)},
    "Sandy Loam":     {"fc": 0.24, "pwp": 0.10, "infiltration": 25, "ideal_ph": (6.0, 7.0)},
    "Red Sandy":      {"fc": 0.22, "pwp": 0.09, "infiltration": 28, "ideal_ph": (6.5, 7.5)},
    "Coastal Sandy":  {"fc": 0.18, "pwp": 0.07, "infiltration": 35, "ideal_ph": (6.5, 8.0)},
}

# Pests keyed by crop, with the weather envelope that favours an outbreak.
PEST_LIBRARY = {
    "Rice": [
        {"name": "Brown Plant Hopper", "temp": (25, 32), "humidity": (80, 100), "stage": "mid",
         "control": "Spray Pymetrozine 50WG @ 300 g/ha; drain field for 3 days to break the humid canopy."},
        {"name": "Leaf Folder", "temp": (24, 30), "humidity": (75, 95), "stage": "development",
         "control": "Release Trichogramma japonicum 100k/ha; avoid excess nitrogen top-dress."},
    ],
    "Banana": [
        {"name": "Pseudostem Weevil", "temp": (26, 34), "humidity": (70, 92), "stage": "mid",
         "control": "Swab pseudostem with Chlorpyriphos 0.03%; remove and burn infested suckers."},
        {"name": "Sigatoka Leaf Spot", "temp": (24, 30), "humidity": (85, 100), "stage": "mid",
         "control": "Propiconazole 0.1% + mineral oil, 2 rounds 21 days apart; improve drainage."},
    ],
    "Coconut": [
        {"name": "Rhinoceros Beetle", "temp": (25, 33), "humidity": (70, 95), "stage": "mid",
         "control": "Place naphthalene balls in leaf axils; clear breeding manure pits."},
        {"name": "Root Wilt", "temp": (24, 32), "humidity": (80, 100), "stage": "late",
         "control": "Root-feed Tridemorph 2 ml + water 100 ml; apply 1 kg MgSO4 per palm."},
    ],
    "Maize": [
        {"name": "Fall Armyworm", "temp": (24, 32), "humidity": (60, 90), "stage": "development",
         "control": "Whorl application of Emamectin benzoate 0.4 g/l; install 5 pheromone traps/ha."},
    ],
    "Groundnut": [
        {"name": "Leaf Miner", "temp": (26, 34), "humidity": (55, 80), "stage": "development",
         "control": "Spray Quinalphos 25EC @ 2 ml/l at 5% leaf damage."},
        {"name": "Tikka Leaf Spot", "temp": (24, 30), "humidity": (80, 100), "stage": "mid",
         "control": "Chlorothalonil 0.2% at 45 and 60 DAS."},
    ],
    "Black Pepper": [
        {"name": "Quick Wilt (Phytophthora)", "temp": (22, 29), "humidity": (88, 100), "stage": "mid",
         "control": "Drench 0.2% Potassium phosphonate; provide crown-level drainage channels."},
    ],
    "Tapioca": [
        {"name": "Cassava Mosaic Vector (Whitefly)", "temp": (26, 35), "humidity": (55, 85), "stage": "development",
         "control": "Install yellow sticky traps 25/ha; spray Neem oil 3% at 15-day interval."},
    ],
}

LANGUAGES = ["en", "ta", "ml", "hi"]
