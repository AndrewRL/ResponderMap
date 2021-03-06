import model_utils
import os
import sys
from model_utils import ConfigReader
from batch_handler import BatchHandler

if __name__ == "__main__":

    logger = model_utils.init_logger()

    logger.info("Starting QGIS...")
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

    # Load config file passed as sys arg
    config_rdr = ConfigReader()
    config_rdr.load(sys.argv[1])

    # TODO: Add support for meta-batch handling and results parsing

    batch = BatchHandler(config_rdr, config_rdr.generate_batch(), logger)
    batch.run(logger=logger)
