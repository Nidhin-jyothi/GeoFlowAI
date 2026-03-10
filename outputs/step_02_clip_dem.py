import sys
import os

QGIS_INSTALL_PATH = r"C:\Program Files\QGIS 3.40.8\apps\qgis-ltr"

# Add QGIS Python dirs to sys.path (must be done before any qgis imports)
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python"))
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python", "plugins"))

from qgis.core import QgsApplication, QgsProcessingFeedback

# Initialize QGIS (headless mode)
qgs = QgsApplication([], False)
qgs.setPrefixPath(QGIS_INSTALL_PATH, True)
qgs.initQgis()

# Import processing AFTER initQgis and path setup
import processing
from processing.core.Processing import Processing
Processing.initialize()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

# Custom feedback class to capture internal QGIS C++ errors
class LoggingFeedback(QgsProcessingFeedback):
    def reportError(self, error, fatalError=False):
        print(f"QGIS_ERROR: {error}", flush=True)
    def pushWarning(self, warning):
        print(f"QGIS_WARNING: {warning}", flush=True)
    def pushInfo(self, info):
        print(f"QGIS_INFO: {info}", flush=True)
    def pushDebugInfo(self, info):
        pass  # Suppress debug noise

feedback = LoggingFeedback()

try:
    # Ensure the output directory exists
    output_dir = os.path.abspath('outputs')
    os.makedirs(output_dir, exist_ok=True)
    
    params = {
        "INPUT": os.path.abspath('data/kerala_dem.tif'),
        "MASK": os.path.abspath('outputs/kerala_boundary.shp'),
        "SOURCE_CRS": "EPSG:4326",
        "TARGET_CRS": "EPSG:4326",
        "TARGET_EXTENT": None,
        "NODATA": -9999,
        "ALPHA_BAND": False,
        "CROP_TO_CUTLINE": True,
        "KEEP_RESOLUTION": False,
        "SET_RESOLUTION": False,
        "X_RESOLUTION": None,
        "Y_RESOLUTION": None,
        "MULTITHREADING": False,
        "OPTIONS": "",
        "OUTPUT": os.path.abspath('outputs/kerala_clipped_dem.tif')
    }
    
    processing.run("gdal:cliprasterbymasklayer", params, feedback=feedback)
    
    print("SUCCESS")
finally:
    qgs.exitQgis()
