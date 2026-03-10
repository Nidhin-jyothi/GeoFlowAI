import sys
import os
from qgis.core import QgsApplication, QgsVectorLayer

QGIS_INSTALL_PATH = r"C:\Program Files\QGIS 3.40.8\apps\qgis-ltr"
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python"))
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python", "plugins"))

qgs = QgsApplication([], False)
qgs.setPrefixPath(QGIS_INSTALL_PATH, True)
qgs.initQgis()

try:
    path = os.path.join("data", "gadm41_IND_1.shp")
    layer = QgsVectorLayer(path, "Test Layer", "ogr")
    
    if layer.isValid():
        print(f"SUCCESS: Layer loaded! Feature count: {layer.featureCount()}")
        print(f"Extent: {layer.extent().toString()}")
    else:
        print(f"ERROR: Layer at '{path}' is INVALID.")
        if not os.path.exists(path):
            print(f"Verified: File physically MISSING at {os.path.abspath(path)}")
        else:
            print(f"Verified: File EXISTS at {os.path.abspath(path)} but QGIS cannot load it.")
finally:
    qgs.exitQgis()
