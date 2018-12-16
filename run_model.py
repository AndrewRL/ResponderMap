import model_utils
import os
import sys
from model_utils import ConfigReader
from batch_handler import BatchHandler

if __name__ == "__main__":

    logger = model_utils.init_logger()

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

    # Load config file passed as sys arg
    config_rdr = ConfigReader()
    config_rdr.load(sys.argv[1])
    '''
    for batch in range(30):
        config_rdr.config['name'] = "n_darts_highT_test_{}".format(batch)
        config_rdr.config['batch_root'] = "Results/" + config_rdr.config['name'] + "/"
    '''
    batch = BatchHandler(config_rdr, config_rdr.generate_batch(), logger)
    print(batch.batch)
    print(batch.batch_config)
    batch.run(logger=logger)

    '''
    # Get the map of Vancouver
    van_map_layer = QgsVectorLayer(PATH_TO_VAN_MAP, "van_map", "ogr")
    # Isolate the target area
    local_area_layer = model_utils.isolate_feature(van_map_layer, SELECTION_ATTRIBUTE, SELECTION_VALUE)
    local_area_layer.setCrs(van_map_layer.crs())
    QgsVectorFileWriter.writeAsVectorFormat(local_area_layer, LOCAL_AREA_SHP, "System", local_area_layer.crs(), "ESRI Shapefile")

    county_bounds = model_utils.find_polygon_bounds(list(local_area_layer.getFeatures())[0])

    # make a grid layer
    grid_layer = model_utils.make_point_grid(local_area_layer, county_bounds, GRID_CELL_SIZE)
    # Apply same coord system as local
    grid_layer.setCrs(local_area_layer.crs())
    print(len(list(grid_layer.getFeatures())))
    grid_layer = model_utils.delete_points_outside_polygon(grid_layer, local_area_layer)
    QgsVectorFileWriter.writeAsVectorFormat(grid_layer, GRID_LAYER_SHP, "System", grid_layer.crs(), "ESRI Shapefile")

    # make a service area layer
    response_radius_km = model_utils.calc_response_radius_km(RESPONSE_TIME, RESPONDER_SPEED, BUFFER_TIME)
    print(response_radius_km)
    print(model_utils.calc_response_radius_NAD83(response_radius_km))
    response_area_layer = model_utils.make_service_area_layer(grid_layer, response_radius_km)
    response_area_layer.setCrs(local_area_layer.crs())

    print(len(list(response_area_layer.getFeatures())))
    QgsVectorFileWriter.writeAsVectorFormat(response_area_layer, RESPONSE_AREA_LAYER_SHP, "System", response_area_layer.crs(),
                                            "ESRI Shapefile")

    # run_example()
    grid_layer = QgsVectorLayer(GRID_LAYER_SHP, "grid_layer", "ogr")
    response_area_layer = QgsVectorLayer(RESPONSE_AREA_LAYER_SHP, "response_area_layer", "ogr")

    binary_coverage_polygon = pyqgis_analysis.generate_binary_coverage(grid_layer, response_area_layer,
                                                                       "demand", "point_id", "area_id")

    print(binary_coverage_polygon)
    # Create the mclp model
    logger.info("Creating MCLP model...")
    mclp = covering.create_threshold_model(binary_coverage_polygon, 100.0)
    # Solve the model using GLPK
    logger.info("Solving MCLP...")
    mclp.solve(pulp.GLPK())
    logger.info("Extracting results")
    ids = utilities.get_ids(mclp, "KERR_response_area_layer")
    print(ids)
    # Generate a query that could be used as a definition query or selection in arcpy
    select_query = pyqgis_analysis.generate_query(ids, unique_field_name="area_id")
    logger.info("Output query to use to generate maps is: {}".format(select_query))
    # Determine how much demand is covered by the results
    response_area_layer.setSubsetString(select_query)
    total_coverage = pyqgis_analysis.get_covered_demand(grid_layer, "demand", "binary",
                                                        response_area_layer)
    logger.info("{0:.2f}% of demand is covered".format((100 * total_coverage) / binary_coverage_polygon["totalDemand"]))

    QgsVectorFileWriter.writeAsVectorFormat(response_area_layer, MODEL_RESULT_PATH, "System",
                                            response_area_layer.crs(),
                                            "ESRI Shapefile")

    QgsApplication.exitQgis()

'''
