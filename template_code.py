
import os
import sys
from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProcessingFeedback,
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    QgsGeometry
)

# Initialize QGIS in headless mode
qgs = QgsApplication([], False)
qgs.setPrefixPath("C:/Program Files/QGIS 3.40.8/apps/qgis-ltr", True)
qgs.initQgis()

# Add necessary paths to sys.path
sys.path.append("C:/Program Files/QGIS 3.40.8/apps/qgis-ltr/python/plugins")

from qgis.analysis import QgsNativeAlgorithms
import processing

# Register processing providers
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
processing.core.Processing.Processing.initialize()

# Input data paths
data_root = "C:/QGIS_Auto/data"
raster_path = os.path.join(data_root, "kerala_dem.tif")
vector_path = os.path.join(data_root, "gadm41_IND_1.shp")
output_path = os.path.join(data_root, "clipped_dem.tif")

# Check if input files exist
if not os.path.exists(raster_path) or not os.path.exists(vector_path):
    print("Error: Input files not found.")
    qgs.exitQgis()
    sys.exit(1)


try:
    # Load raster layer
    raster_layer = QgsRasterLayer(raster_path, "Kerala DEM")
    if not raster_layer.isValid():
        print("Error: Could not load raster layer.")
        qgs.exitQgis()
        sys.exit(1)

    # Load vector layer and filter for Kerala
    vector_layer = QgsVectorLayer(vector_path, "India Admin Level 1", "ogr")
    if not vector_layer.isValid():
        print("Error: Could not load vector layer.")
        qgs.exitQgis()
        sys.exit(1)

    if "NAME_1" in vector_layer.fields().names():
        vector_layer.setSubsetString("NAME_1 = 'Kerala'")

    # Check if any features are selected after filtering.
    if vector_layer.featureCount() == 0:
        print("Error: No features found for Kerala.")
        qgs.exitQgis()
        sys.exit(1)

    # Ensure output directory exists
    os.makedirs(data_root, exist_ok=True)


    # Match CRS
    raster_crs = raster_layer.crs()
    vector_layer.setCrs(raster_crs)

    # Clip the raster
    feedback = QgsProcessingFeedback()
    params = {
        'INPUT': raster_path,
        'MASK': vector_layer,
        'OUTPUT': output_path
    }

    try:
      processing.run("gdal:cliprasterbymasklayer", params, feedback=feedback)
      print(f"Clipped raster saved to: {output_path}")
    except Exception as e:
      try:
        processing.run("qgis:cliprasterbymasklayer", params, feedback=feedback)
        print(f"Clipped raster saved to: {output_path}")
      except Exception as e2:
        print(f"Error during clipping: {e2}")
        qgs.exitQgis()
        sys.exit(1)


except Exception as e:
    print(f"An error occurred: {e}")
    qgs.exitQgis()
    sys.exit(1)

qgs.exitQgis()
