import sys
import os
import json

# Absolute path to QGIS install
QGIS_INSTALL_PATH = r"C:\Program Files\QGIS 3.40.8\apps\qgis-ltr"

# Add QGIS Python paths
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python"))
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python", "plugins"))

from qgis.core import QgsApplication
# Initialize Headless QGIS
qgs = QgsApplication([], False)
qgs.setPrefixPath(QGIS_INSTALL_PATH, True)
qgs.initQgis()

# Import processing AFTER init
import processing
from processing.core.Processing import Processing
Processing.initialize()

# Add native provider
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

# --- Data-type classification helpers ---
RASTER_INPUT_TYPES = {
    "QgsProcessingParameterRasterLayer",
    "QgsProcessingParameterMultipleLayers",  # could be either, but often raster
}
VECTOR_INPUT_TYPES = {
    "QgsProcessingParameterFeatureSource",
    "QgsProcessingParameterVectorLayer",
}

def classify_data_type(params):
    """Determine if the algorithm primarily works on raster or vector data."""
    for p in params:
        if p["name"] == "INPUT":
            if p["type_class"] in RASTER_INPUT_TYPES:
                return "raster"
            elif p["type_class"] in VECTOR_INPUT_TYPES:
                return "vector"
    return "unknown"

algos_metadata = []

print("Extracting detailed algorithm metadata...")
for algo in QgsApplication.processingRegistry().algorithms():
    try:
        params_list = []
        for p in algo.parameterDefinitions():
            p_data = {
                "name": p.name(),
                "description": p.description(),
                "type_class": p.__class__.__name__,
                "is_optional": bool(p.flags() & 0x01),  # FlagOptional
                "is_destination": p.isDestination(),
            }

            # Default value
            default = p.defaultValue()
            if default is not None:
                # Convert to JSON-safe type
                if isinstance(default, (int, float, bool, str)):
                    p_data["default"] = default
                else:
                    p_data["default"] = str(default)

            # Enum options with integer indices
            if hasattr(p, 'options'):
                opts = list(p.options())
                p_data["options"] = {str(i): v for i, v in enumerate(opts)}

            params_list.append(p_data)

        data = {
            "id": algo.id(),
            "name": algo.displayName(),
            "short_description": algo.shortDescription() if hasattr(algo, 'shortDescription') else "",
            "group": algo.group(),
            "tags": algo.tags(),
            "input_type": classify_data_type(params_list),
            "parameters": params_list,
        }

        algos_metadata.append(data)
    except Exception as e:
        print(f"Error reading algo {algo.id()}: {e}")

output_file = "qgis_algorithms_detailed.json"
with open(output_file, "w", encoding='utf-8') as f:
    json.dump(algos_metadata, f, indent=2, ensure_ascii=False)

print(f"Successfully dumped {len(algos_metadata)} algorithms to {output_file}")
qgs.exitQgis()
