from layers import BatchLayerHandler
from model_utils import ConfigReader, init_logger
import os, sys


def test_area_layer_load(source_path):

    config = ConfigReader()
    config.config = {
        'map_path': source_path,
        'area_select_key': 'MAPID',
        'settings': {
            'areas': ['KERR']
        }
    }

    layer_handler = BatchLayerHandler(config).make_area_layers()
    assert len(list(layer_handler.layers['areas']['KERR'].layer.getFeatures())) == 1


if __name__ == "__main__":

    logger = init_logger()

    print("Attempting to run...")
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/Applications/QGIS3.app/Contents/PlugIns'
    # os.environ['QGIS_PREFIX_PATH'] = '/Applications/QGIS3.app/Contents'
    sys.path.insert(0, '/Applications/QGIS3.app/Contents/Resources/python/')
    sys.path.insert(0, '/Applications/QGIS3.app/Contents/Resources/python/plugins')
    from qgis.core import *

    app = QgsApplication([], True)
    QgsApplication.setPrefixPath("/Applications/QGIS3.app/Contents")
    QgsApplication.setPluginPath("/Applications/QGIS3.app/Contents/PlugIns/qgis")
    QgsApplication.setPkgDataPath("/Applications/QGIS3.app/Contents/Resources")
    QgsApplication.setDefaultSvgPaths(['/Users/andrewlaird/Library/Application Support/profiles/default/svg/',
                                       '/Applications/QGIS3.app/Contents/Resources/svg/'])
    QgsApplication.setThemeName('Night Mapping')
    app.initQgis()


test_area_layer_load("shp_files/local_area_boundary.shp")