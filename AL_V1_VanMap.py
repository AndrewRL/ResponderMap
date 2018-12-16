import model_test
import sys
import os
import pulp
import qgis
from pyspatialopt.models import covering, utilities
from pyspatialopt.analysis import pyqgis_analysis
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QVariant
import model_utils

# Path to shp_file directory
SHP_FILE_DIR = "/Users/andrewlaird/PycharmProjects/Van_Mapping_Test/shp_files/"
PATH_TO_VAN_MAP = SHP_FILE_DIR + "local_area_boundary.shp"
PATH_TO_BLOCK_OUTLINES = SHP_FILE_DIR + "block_outlines.shp"
PATH_TO_ROADS_SHP = SHP_FILE_DIR + "public_streets.shp"

# Name of the attribute you will use to isolate the area to be modeled
SELECTION_ATTRIBUTE = "MAPID"
# Value of the attribute used to isolate the modeling area
SELECTION_VALUE = "KERR"
# Use CRS of NAD83
GRID_CELL_SIZE = 250
# Speed of a responder in KPH
RESPONDER_SPEED = 5
# Time in seconds to add to each response
BUFFER_TIME = 180
# Target response time in seconds
RESPONSE_TIME = 300
# Path to output Vancouver map cropped to target area
LOCAL_AREA_SHP = SHP_FILE_DIR + SELECTION_VALUE + "_local_area_layer.shp"
# Block outline shp output
BLOCK_OUTLINE_SHP = SHP_FILE_DIR + SELECTION_VALUE + "_block_outline_layer.shp"
# Path to output grid layer
GRID_LAYER_SHP = SHP_FILE_DIR + SELECTION_VALUE + "_grid_layer.shp"
# Path to output response area layer
RESPONSE_AREA_LAYER_SHP = SHP_FILE_DIR + SELECTION_VALUE + "_response_area_layer.shp"
ROADS_SHP = SHP_FILE_DIR + SELECTION_VALUE + "_roads_layer.shp"
ROAD_POINTS_SHP = SHP_FILE_DIR + SELECTION_VALUE + "_road_points_layer.shp"
# Path to output final model result
MODEL_RESULT_PATH = SHP_FILE_DIR + SELECTION_VALUE + "_model_output_15.shp"



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

    # Get the map of Vancouver
    van_map_layer = QgsVectorLayer(PATH_TO_VAN_MAP, "van_map", "ogr")
    # Isolate the target area
    local_area_layer = model_utils.isolate_feature(van_map_layer, SELECTION_ATTRIBUTE, SELECTION_VALUE)
    local_area_layer.setCrs(van_map_layer.crs())
    QgsVectorFileWriter.writeAsVectorFormat(local_area_layer, LOCAL_AREA_SHP, "System", local_area_layer.crs(), "ESRI Shapefile")
    # Get the block polygons which are within the target area
    block_polygon_layer = QgsVectorLayer(PATH_TO_BLOCK_OUTLINES, "block_outlines", "ogr")
    target_blocks_layer = model_utils.isolate_blocks(block_polygon_layer, local_area_layer)
    target_blocks_layer.setCrs(local_area_layer.crs())
    QgsVectorFileWriter.writeAsVectorFormat(target_blocks_layer, BLOCK_OUTLINE_SHP, "System", target_blocks_layer.crs(), "ESRI Shapefile")

    county_bounds = model_utils.find_polygon_bounds(list(local_area_layer.getFeatures())[0])

    # make a grid layer
    grid_layer = model_utils.make_point_grid(local_area_layer, county_bounds, GRID_CELL_SIZE)
    # Apply same coord system as local
    grid_layer.setCrs(local_area_layer.crs())
    print(len(list(grid_layer.getFeatures())))
    grid_layer = model_utils.delete_points_outside_polygon(grid_layer, local_area_layer)
    QgsVectorFileWriter.writeAsVectorFormat(grid_layer, GRID_LAYER_SHP, "System", grid_layer.crs(), "ESRI Shapefile")

    # run_example()

    # Make roads layer
    roads_layer = QgsVectorLayer(PATH_TO_ROADS_SHP, "roads_layer", "ogr")
    print("Roads layer loaded. Found {} features.".format(len(list(roads_layer.getFeatures()))))
    target_roads_layer = model_utils.isolate_roads(roads_layer, local_area_layer)
    target_roads_layer.setCrs(local_area_layer.crs())
    QgsVectorFileWriter.writeAsVectorFormat(target_roads_layer, ROADS_SHP, "System", target_roads_layer.crs(), "ESRI Shapefile")

    road_points_layer = model_utils.create_road_points_layer(target_roads_layer)
    road_points_layer.setCrs(local_area_layer.crs())
    print("Writing road point layer with {} features.".format(len(list(road_points_layer.getFeatures()))))
    QgsVectorFileWriter.writeAsVectorFormat(road_points_layer, ROAD_POINTS_SHP, "System", road_points_layer.crs(), "ESRI Shapefile")

    # make a service area layer
    response_radius_km = model_utils.calc_response_radius_km(RESPONSE_TIME, RESPONDER_SPEED, BUFFER_TIME)
    print(response_radius_km)
    print(model_utils.calc_response_radius_NAD83(response_radius_km))
    response_area_layer = model_utils.make_service_area_layer(road_points_layer, response_radius_km)
    response_area_layer.setCrs(local_area_layer.crs())

    print(len(list(response_area_layer.getFeatures())))
    QgsVectorFileWriter.writeAsVectorFormat(response_area_layer, RESPONSE_AREA_LAYER_SHP, "System",
                                            response_area_layer.crs(),
                                            "ESRI Shapefile")

    block_layer = QgsVectorLayer(BLOCK_OUTLINE_SHP, "block_layer", "ogr")
    response_area_layer = QgsVectorLayer(RESPONSE_AREA_LAYER_SHP, "response_area_layer", "ogr")

    binary_coverage_polygon = pyqgis_analysis.generate_partial_coverage(block_layer, response_area_layer,
                                                                        "demand", "point_id", "area_id")

    print(binary_coverage_polygon)
    # Create the mclp model
    logger.info("Creating MCLP model...")
    mclp = covering.create_cc_threshold_model(binary_coverage_polygon, 80)
    # Solve the model using GLPK
    logger.info("Solving MCLP...")
    mclp.solve(pulp.GLPK(options=['--mipgap', '.1']))
    logger.info("Extracting results")
    ids = utilities.get_ids(mclp, "{}_response_area_layer".format(SELECTION_VALUE))
    print(ids)
    # Generate a query that could be used as a definition query or selection in arcpy
    select_query = pyqgis_analysis.generate_query(ids, unique_field_name="area_id")
    logger.info("Output query to use to generate maps is: {}".format(select_query))
    # Determine how much demand is covered by the results
    response_area_layer.setSubsetString(select_query)
    total_coverage = pyqgis_analysis.get_covered_demand(block_layer, "demand", "partial",
                                                        response_area_layer)
    logger.info("{0:.2f}% of demand is covered".format((100 * total_coverage) / binary_coverage_polygon["totalDemand"]))
    logger.info("{} responders".format(len(ids)))
    QgsVectorFileWriter.writeAsVectorFormat(response_area_layer, MODEL_RESULT_PATH, "System",
                                            response_area_layer.crs(),
                                            "ESRI Shapefile")

    QgsApplication.exitQgis()