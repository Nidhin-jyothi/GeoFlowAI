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
    input_raster = os.path.abspath("outputs/kerala_clipped_dem.tif")
    output_raster = os.path.abspath("outputs/kerala_slope.tif")
    
    params = {
        "INPUT": input_raster,
        "BAND": 1,
        "SCALE": 1.0,
        "AS_PERCENT": False,
        "COMPUTE_EDGES": False,
        "ZEVENBERGEN": False,
        "OPTIONS": "",
        "EXTRA": "",
        "OUTPUT": output_raster
    }
    
    result = processing.run("gdal:slope", params, feedback=feedback)
    
    if os.path.exists(output_raster):
        print("SUCCESS")
finally:
    qgs.exitQgis()
