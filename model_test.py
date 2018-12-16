import sys
import os
import logging
import pulp
import qgis
from pyspatialopt.models import covering, utilities
from pyspatialopt.analysis import pyqgis_analysis
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QVariant


def isolate_county(us_counties_shp, state_code, county_code):
    #Create an empty layer
    county_layer = QgsVectorLayer("Polygon", "county_layer", "memory")
    #Get the feature which matches county code
    counties = QgsVectorLayer(us_counties_shp, "us_counties", "ogr")
    for county in counties.getFeatures():
        if county['COUNTYFP'] == county_code and county['STATEFP'] == state_code:
            county_layer.startEditing()
            cl_prov = county_layer.dataProvider()
            cl_prov.addFeatures([county])
            county_layer.commitChanges()
            break
    return county_layer


def find_polygon_bounds(polygon):
    multipolygon_vertices = polygon.geometry().asMultiPolygon()

    x_coords = []
    y_coords = []
    for polygon_part in multipolygon_vertices:
        for next_layer in polygon_part:
            for point in next_layer:
                x_coords.append(point.x())
                y_coords.append(point.y())

    return [min(x_coords), max(x_coords), min(y_coords), max(y_coords)]


def make_point_grid(source_layer, county_bounds, cell_size):
    #make new layer of same shape and crs as source layer
    grid_layer = QgsVectorLayer("Point", "coverage_grid", "memory")
    print(grid_layer.isValid())
    #add attributes to layer
    provider = grid_layer.dataProvider()
    provider.addAttributes([QgsField("point_id", QVariant.Int), QgsField("demand", QVariant.Int)])
    #add points to layer  and set default attribute values
    grid_points = make_points(county_bounds, cell_size, cell_size)
    #add points to grid layer
    provider.addFeatures(grid_points)
    return grid_layer


def make_points(county_bounds, x_step, y_step):
    print(county_bounds)
    x_min, x_max, y_min, y_max = county_bounds
    #create a point
    curr_x = x_min
    curr_y = y_max
    curr_id = 0
    default_demand = 1
    grid_points = []
    while curr_x < x_max:
        while curr_y > y_min:
            ft = QgsFeature()
            ft.setAttributes([curr_id, default_demand])
            ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(curr_x, curr_y)))
            grid_points.append(ft)
            print("Added point {}, {}".format(curr_x, curr_y))
            curr_id += 1
            curr_y -= y_step

        curr_x += x_step
        curr_y = y_max
    return grid_points


def delete_points_outside_polygon(points_layer, polygon_layer):
    points = list(points_layer.getFeatures())
    n_points = len(points)
    polygon = list(polygon_layer.getFeatures())[0]
    points_layer.startEditing()
    for point in points:
        if not point.geometry().intersects(polygon.geometry()):
            points_layer.deleteFeature(point.id())
    points_layer.commitChanges()
    print("Deleted {} points".format(n_points - len(list(points_layer.getFeatures()))))
    return points_layer


def make_service_area_layer(points_layer):
    sa_layer = QgsVectorLayer("Polygon", "sa_layer", "memory")
    sa_layer_prov = sa_layer.dataProvider()
    sa_layer.startEditing()
    sa_layer_prov.addAttributes([QgsField("area_id", QVariant.Int)])
    circles = []
    current_id = 0
    for point in points_layer.getFeatures():
        ft = QgsFeature()
        ft.setGeometry(QgsGeometry.fromPointXY(point.geometry().asPoint()).buffer(.01, 10))
        ft.setAttributes([current_id])
        circles.append(ft)
        current_id += 1

    sa_layer_prov.addFeatures(circles)
    sa_layer.commitChanges()
    return sa_layer


def run_example():
    providers = QgsProviderRegistry.instance().providerList()
    for provider in providers:
        print(provider)
    print(QgsApplication.showSettings())
    demand_points = QgsVectorLayer("/Users/andrewlaird/Desktop/QGIS Mapping/points_2.shp", "demand_points", "ogr")
    print(demand_points.isValid())
    service_areas = QgsVectorLayer("/Users/andrewlaird/Desktop/QGIS Mapping/zones.shp", "service_areas", "ogr")
    print(service_areas.isValid())

    binary_coverage_polygon = pyqgis_analysis.generate_binary_coverage(demand_points, service_areas,
                                                                       "od_rate", "point_id", "zone_id")

    print(binary_coverage_polygon)
    # Create the mclp model
    # Maximize the total coverage (binary polygon) using at most 5 out of 8 facilities
    logger.info("Creating MCLP model...")
    mclp = covering.create_threshold_model(binary_coverage_polygon, 100.0)
    # Solve the model using GLPK
    logger.info("Solving MCLP...")
    mclp.solve(pulp.GLPK())
    # Get the unique ids of the 5 facilities chosen
    logger.info("Extracting results")
    ids = utilities.get_ids(mclp, "zones")
    # Generate a query that could be used as a definition query or selection in arcpy
    select_query = pyqgis_analysis.generate_query(ids, unique_field_name="zone_id")
    logger.info("Output query to use to generate maps is: {}".format(select_query))
    # Determine how much demand is covered by the results
    service_areas.setSubsetString(select_query)
    total_coverage = pyqgis_analysis.get_covered_demand(demand_points, "od_rate", "binary",
                                                        service_areas)
    logger.info("{0:.2f}% of demand is covered".format((100 * total_coverage) / binary_coverage_polygon["totalDemand"]))


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    # setup stream handler to console output
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    print(sys.argv)
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

    PATH_TO_US_COUNTIES_SHP = "/Users/andrewlaird/PycharmProjects/Van_Mapping_Test/shp_files/tl_2018_us_county.shp"
    TARGET_STATE_CODE = "39"
    TARGET_COUNTY_CODE = "049"
    GRID_CELL_SIZE = 300
    COUNTY_LAYER_SHP = "/Users/andrewlaird/PycharmProjects/Van_Mapping_Test/shp_files/county_" + TARGET_COUNTY_CODE + ".shp"
    GRID_LAYER_SHP = "/Users/andrewlaird/PycharmProjects/Van_Mapping_Test/shp_files/county_" + TARGET_COUNTY_CODE + "_grid.shp"
    SERVICE_AREA_SHP = "/Users/andrewlaird/PycharmProjects/Van_Mapping_Test/shp_files/county_" + TARGET_COUNTY_CODE + "_sas.shp"
    '''
    county_layer = isolate_county(PATH_TO_US_COUNTIES_SHP, TARGET_STATE_CODE, TARGET_COUNTY_CODE)
    QgsVectorFileWriter.writeAsVectorFormat(county_layer, COUNTY_LAYER_SHP, "System", county_layer.crs(), "ESRI Shapefile")

    print(len(list(county_layer.getFeatures())))
    '''
    kerrisdale_layer = QgsVectorLayer("/Users/andrewlaird/Desktop/QGIS Mapping/kerrisdale_map.shp", "kd_layer", "ogr")
    county_bounds = find_polygon_bounds(list(kerrisdale_layer.getFeatures())[0])

    #make a grid layer
    grid_layer = make_point_grid(kerrisdale_layer, county_bounds, GRID_CELL_SIZE)
    print(len(list(grid_layer.getFeatures())))
    grid_layer = delete_points_outside_polygon(grid_layer, kerrisdale_layer)
    QgsVectorFileWriter.writeAsVectorFormat(grid_layer, GRID_LAYER_SHP, "System", grid_layer.crs(), "ESRI Shapefile")

    #make a service area layer
    service_area_layer = make_service_area_layer(grid_layer)
    print(len(list(service_area_layer.getFeatures())))
    QgsVectorFileWriter.writeAsVectorFormat(service_area_layer, SERVICE_AREA_SHP, "System", service_area_layer.crs(), "ESRI Shapefile")

    run_example()
    grid_layer = QgsVectorLayer(GRID_LAYER_SHP, "grid_layer", "ogr")
    service_area_layer = QgsVectorLayer(SERVICE_AREA_SHP, "service_area_layer", "ogr")

    binary_coverage_polygon = pyqgis_analysis.generate_binary_coverage(grid_layer, service_area_layer,
                                                                       "demand", "point_id", "area_id")
    
    print(binary_coverage_polygon)
    # Create the mclp model
    logger.info("Creating MCLP model...")
    mclp = covering.create_threshold_model(binary_coverage_polygon, 100.0)
    # Solve the model using GLPK
    logger.info("Solving MCLP...")
    mclp.solve(pulp.GLPK())
    logger.info("Extracting results")
    ids = utilities.get_ids(mclp, "areas")
    # Generate a query that could be used as a definition query or selection in arcpy
    select_query = pyqgis_analysis.generate_query(ids, unique_field_name="area_id")
    logger.info("Output query to use to generate maps is: {}".format(select_query))
    # Determine how much demand is covered by the results
    service_area_layer.setSubsetString(select_query)
    total_coverage = pyqgis_analysis.get_covered_demand(grid_layer, "demand", "binary",
                                                        service_area_layer)
    logger.info("{0:.2f}% of demand is covered".format((100 * total_coverage) / binary_coverage_polygon["totalDemand"]))

    QgsApplication.exitQgis()