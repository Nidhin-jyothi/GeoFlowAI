import os
import sys

# Add QGIS Python dirs to sys.path
QGIS_INSTALL_PATH = r"C:\Program Files\QGIS 3.40.8\apps\qgis-ltr"
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python"))
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python", "plugins"))

from qgis.core import QgsApplication, QgsRasterLayer

qgs = QgsApplication([], False)
qgs.setPrefixPath(QGIS_INSTALL_PATH, True)
qgs.initQgis()

file_path = r"C:\Users\nj825\OneDrive\Desktop\GeoFlowAI\data\India_PVOUT_poster-map_1000x1000mm-300dpi_v20191017.tif"
layer = QgsRasterLayer(file_path, "test")

if not layer.isValid():
    print("Layer is INVALID")
else:
    print(f"Layer Name: {layer.name()}")
    print(f"CRS: {layer.crs().authid()}")
    print(f"Extent: {layer.extent().toString()}")
    print(f"Width: {layer.width()}, Height: {layer.height()}")
    if layer.crs().isValid():
        print("CRS is VALID")
    else:
        print("CRS is INVALID - This file is not georeferenced!")

qgs.exitQgis()
