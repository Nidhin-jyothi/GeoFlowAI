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
    # Define input and output paths relative to the project root
    input_layer_path = os.path.abspath('data/gadm41_IND_1.shp')
    output_layer_path = os.path.abspath('outputs/kerala_boundary.shp')
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_layer_path), exist_ok=True)
    
    # Define the parameters for the native:extractbyattribute algorithm
    params = {
        'INPUT': input_layer_path,
        'FIELD': 'NAME_1',
        'OPERATOR': 0,  # 0 corresponds to '='
        'VALUE': 'Kerala',
        'OUTPUT': output_layer_path
    }
    
    # Run the processing algorithm
    result = processing.run("native:extractbyattribute", params, feedback=feedback)
    
    # Check if the output file was created successfully
    if os.path.exists(output_layer_path):
        print("SUCCESS")
    else:
        # This part is not explicitly requested but good for debugging if needed
        print(f"Error: Output file not found at {output_layer_path}")
        if 'OUTPUT' in result and result['OUTPUT'] is None:
            print("Algorithm returned None for OUTPUT.")
        # More detailed error logging can be added if result contains error messages
        # For example, by checking feedback.messages() or result.get('ERRORS')
finally:
    qgs.exitQgis()
