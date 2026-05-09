import sys
import os

QGIS_INSTALL_PATH = r"C:\Program Files\QGIS 3.40.8\apps\qgis-ltr"

# Add QGIS Python dirs to sys.path (must be done before any qgis imports)
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python"))
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python", "plugins"))

from qgis.core import (
    QgsApplication, 
    QgsProcessingFeedback, 
    QgsVectorLayer, 
    QgsRasterLayer,
    QgsProject,
    QgsCoordinateReferenceSystem
)

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
    params = {
        'INPUT': os.path.abspath('data/gadm41_IND_1.shp'),
        'FIELD': 'NAME_1',
        'OPERATOR': 0,
        'VALUE': 'Kerala',
        'OUTPUT': os.path.abspath('outputs/kerala_boundary.shp')
    }

    processing.run("native:extractbyattribute", params, feedback=feedback)

    print("SUCCESS")
finally:
    qgs.exitQgis()
