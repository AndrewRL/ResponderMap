import logging
import sys
import csv
from qgis.core import *
from PyQt5.QtCore import QVariant
import json
import itertools
import math
import pulp
from plotly.offline import iplot, init_notebook_mode
import plotly.graph_objs as go
import plotly.io as pio
import random


class GraphBuilder:
    def __init__(self, source_batch, graph_config):
        self.source_batch = source_batch
        self.outfile = graph_config['outfile']
        self.title = graph_config['title']
        self.x_title = graph_config['x_title']
        self.y_title = graph_config['y_title']
        self.x_key = graph_config['x_key']
        self.y_key = graph_config['y_key']
        self.plot_kind = 'scatter'
        self.py_plot = None

        self._set_x_range(graph_config)
        self._set_y_range(graph_config)

        self._set_x_data()
        self._set_y_data()

    def _set_x_range(self, graph_config):
        if graph_config['x_range']:
            self.x_range = graph_config['x_range']
        else:
            self.x_range = {"min": 0, "max": None}

    def _set_y_range(self, graph_config):
        if graph_config['y_range']:
            self.y_range = graph_config['y_range']
        else:
            self.y_range = {"min": 0, "max": None}

    def _set_x_data(self):
        batch_results = self.source_batch.metadata.metadata['results']
        x_data = []
        for run in batch_results:
            print(run)
            if self.x_key == 'n_responders':
                x_data.append(run['results'][0]['n_responders'])
            else:
                x_data.append(run['results'][0]['config'][self.x_key])

        self.x_data = x_data

    def _set_y_data(self):
        batch_results = self.source_batch.metadata.metadata['results']
        y_data = []
        for run in batch_results:
            print(run)
            if self.y_key == 'n_responders':
                y_data.append(run['results'][0]['n_responders'])
            else:
                y_data.append(run['results'][0]['config'][self.y_key])

        self.y_data = y_data

    def plot(self):
        # Generate a plot based on the specified settings and source batch data

        layout = dict(
            title=self.title,
            xaxis=dict(title=self.x_title),
            yaxis=dict(title=self.y_title),
        )
        trace = go.Scatter(
            x=self.x_data,
            y=self.y_data,
            name='Below',
            mode='markers',
            marker=dict(
                size=10,
                color='rgba(255, 182, 193, .9)',
                line=dict(
                    width=2,
                )
            )
        )

        data = [trace]
        fig = dict(data=data, layout=layout)

        pio.write_image(fig, self.source_batch.batch_config.config['batch_root'] + self.outfile)

class MetadataHandler:
    # Stores model metadata and allows output of metadata files. Metadata can be produced for batches or single runs.
    def __init__(self, metadata=None):
        if metadata:
            self.metadata = metadata
        else:
            self.metadata = {
                "results": []
            }

    def parse_json(self, json_path):
        # Parse json file into MetadataHandler
        pass

    def to_json(self, path):
        # Output a json file from the metadata
        pass

    def to_csv(self, path):
        results = self.metadata['results']
        output = []
        for result in results:
            config = result['results'][0]['config']
            output.append({
                "name": config['run_name'],
                "status": result['results'][0]['status'],
                "area": config['areas'],
                "response_time": config['response_time'],
                "responder_speed": config['responder_speed'],
                "responder_buffer": config['responder_buffer'],
                "threshold": config['thresholds'],
                "responders": result['results'][0]['n_responders']
            })

        with open(path, 'w') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([key for key in output[0].keys()])
            for run in output:
                writer.writerow([value for value in run.values()])

    def parse_model_output(self, model):
        # TODO: Check that model result exists, balk if it does not
        config = model.model_run_config
        n_responders = ""
        if pulp.LpStatus[model.problem.status] != "Infeasible":
            n_responders = len(model.area_ids)
        self.metadata['results'].append({
            "config": config,
            "status": pulp.LpStatus[model.problem.status],
            "n_responders": n_responders,
            "point_ids": model.point_ids,
            "area_ids": model.area_ids
        })

        return self

    def add_config(self, config_rdr):
        # Add ConfigReader.config to the metadata
        self.metadata['config'] = config_rdr.config

    def add_locations(self, locs):
        pass


class ConfigReader:
    # Read in batch config data and allow preparation of model run data
    def __init__(self):
        self.path = ""
        self.batch = []
        self.config = {}
        self.status = "No File Loaded"

    def load(self, config_path):
        print("Loading config from {}".format(config_path))
        self.path = config_path
        with open(config_path) as config_file:
            self.config = json.load(config_file)
        return self

    def generate_batch(self):
        self.batch = []
        batch_settings = self.config['settings']
        model_configs = list(itertools.product(*list(batch_settings.values())))

        for run_number, model_run in enumerate(model_configs):
            run_vars = dict(zip(batch_settings.keys(), model_run))
            run_vars['run_name'] = run_number
            self.batch.append(run_vars)

        return self.batch

    def set_attribute(self, attribute_name, value):
        self.config[attribute_name] = value

    def _update_status(self):
        # Change self.status to reflect if data is missing, malformed, or presented
        pass

    def _test_config(self):
        # Checks that all required fields are present in the config file and validates values
        pass


def set_block_attributes(block_layer, default_demand):
    bl_prov = block_layer.dataProvider()
    for curr_id, ft in enumerate(block_layer.getFeatures()):
        block_layer.changeAttributeValue(ft.id(), bl_prov.fieldNameIndex("point_id"), curr_id)
        block_layer.changeAttributeValue(ft.id(), bl_prov.fieldNameIndex("demand"), default_demand)


def isolate_blocks(block_outlines, local_area_boundary):
    target_blocks = QgsVectorLayer("Polygon", "target_blocks", "memory")
    target_blocks_prov = target_blocks.dataProvider()
    target_blocks_prov.addAttributes([QgsField("point_id", QVariant.Int), QgsField("demand", QVariant.Int)])
    target_blocks.startEditing()
    recreate_blocks(target_blocks, block_outlines, 1)
    delete_points_outside_polygon(target_blocks, local_area_boundary)
    target_blocks.commitChanges()
    return target_blocks


def recreate_blocks(target_blocks, block_outlines, default_demand):
    tb_prov = target_blocks.dataProvider()
    for curr_id, ft in enumerate(list(block_outlines.getFeatures())):
        new_ft = QgsFeature()
        new_ft.setAttributes([curr_id, math.sqrt(ft.geometry().area())])
        new_ft.setGeometry(ft.geometry())
        tb_prov.addFeatures([new_ft])
    return target_blocks


def isolate_roads(roads, local_area_boundary):
    target_roads = QgsVectorLayer("LINESTRING", "target_roads", "memory")
    target_roads_prov = target_roads.dataProvider()
    target_roads_prov.addAttributes([QgsField("point_id", QVariant.Int)])
    target_roads.startEditing()
    recreate_roads(target_roads, roads)
    print("Were roads copied?")
    print(len(list(roads.getFeatures())))
    print(len(list(target_roads.getFeatures())))
    delete_roads_outside_target_area(target_roads, local_area_boundary)
    target_roads.commitChanges()
    return target_roads


def recreate_roads(target_roads, roads):
    for curr_id, ft in enumerate(list(roads.getFeatures())):
        new_ft = QgsFeature()
        new_ft.setAttributes([curr_id])
        new_ft.setGeometry(ft.geometry())
        target_roads.addFeatures([new_ft])
    return target_roads


def calc_response_radius_km(response_time, responder_speed, buffer_time):
    return (response_time - buffer_time) * responder_speed * 1000 / 60 / 60


def calc_response_radius_NAD83(response_radius_km):
    return response_radius_km * .01


def init_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    # setup stream handler to console output
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    return logger


# From a layer of features, returns a layer containing only the feature specified by
# attribute_name = attribute_value
def isolate_feature(containing_layer, attribute_name, attribute_value):
    # Create an empty layer
    output_layer = QgsVectorLayer("Polygon", "output_layer", "memory")
    # Get the feature which matches county code
    for county in containing_layer.getFeatures():
        if county[attribute_name] == attribute_value:
            output_layer.startEditing()
            cl_prov = output_layer.dataProvider()
            cl_prov.addFeatures([county])
            output_layer.commitChanges()
            break
    return output_layer


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
    #add attributes to layer
    provider = grid_layer.dataProvider()
    provider.addAttributes([QgsField("point_id", QVariant.Int), QgsField("demand", QVariant.Int)])
    #add points to layer  and set default attribute values
    grid_points = make_points(county_bounds, cell_size, cell_size)
    #add points to grid layer
    provider.addFeatures(grid_points)
    return grid_layer


def make_points(county_bounds, x_step, y_step):
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
            ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(curr_x, curr_y)))
            ft.setAttributes([curr_id, default_demand])
            grid_points.append(ft)
            curr_id += 1
            curr_y -= y_step

        curr_x += x_step
        curr_y = y_max
    return grid_points


def create_road_points_layer(area_layer, roads_layer, rp_model='n_darts'):
    road_points_layer = QgsVectorLayer("Point", "road_points", "memory")
    rp_prov = road_points_layer.dataProvider()
    road_points_layer.startEditing()
    rp_prov.addAttributes([QgsField("point_id", QVariant.Int)])

    if rp_model == 'n_darts':
        print("Running n_darts model to generate candidate responder locations.")
        _n_darts_road_pts_model(area_layer, roads_layer, road_points_layer, rp_prov)
        print("Confirm RPs added to layer: {}".format(len(list(road_points_layer.getFeatures()))))
    elif rp_model == 'place_and_prune':
        _place_and_prune_road_pts_model(roads_layer)

    '''
    for curr_id, road in enumerate(roads_layer.getFeatures()):
        geom = road.geometry()
        mid_point = geom.interpolate(geom.length() / 2)
        mid_point_buffer = QgsGeometry.fromPointXY(mid_point.asPoint()).buffer(150, 10)
        near_existing_point = False
        for existing_point in road_points_layer.getFeatures():
            if existing_point.geometry().intersects(mid_point_buffer):
                near_existing_point = True
                break
        if not near_existing_point:
            ft = QgsFeature()
            ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(mid_point.asPoint().x(), mid_point.asPoint().y())))
            ft.setAttributes([curr_id])
            rp_prov.addFeatures([ft])
    '''
    road_points_layer.commitChanges()
    print("Road points layer created and commited with {} features.".format(len(list(road_points_layer.getFeatures()))))
    return road_points_layer


def _n_darts_road_pts_model(area_layer, roads_layer, road_points_layer, road_pts_prov, n_darts=150, buffer=150):
    roads = list(roads_layer.getFeatures())
    print("Found {} roads for point placement.".format(len(roads)))
    for dart in range(0, n_darts):
        # Throw the dart until you hit a viable location
        dart_placed = False
        print("Throwing dart {} of {}".format(dart, n_darts))
        while not dart_placed:
            # Randomly select a road segment (possibly weighted by length)
            total_rd_length = sum([road.geometry().length() for road in roads])
            road_seg = random.choices(roads, weights=[road.geometry().length() / total_rd_length for road in roads])[0]
            # Randomly select a point along that segment
            pct_to_interpolate = random.random()
            road_length = road_seg.geometry().length()
            test_point = road_seg.geometry().interpolate(road_length * pct_to_interpolate)
            # Check if the point is in the target area
            area_polygon = next(area_layer.getFeatures())
            if not test_point.intersects(area_polygon.geometry()):
                continue

            # Test if there is a point within buffer meters
            test_point_buffer = QgsGeometry.fromPointXY(test_point.asPoint()).buffer(buffer, 10)

            if dart == 0:
                ft = QgsFeature()
                ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(test_point.asPoint().x(), test_point.asPoint().y())))
                ft.setAttributes([dart])
                road_pts_prov.addFeatures([ft])
                dart_placed = True
            else:
                near_existing_point = False
                for existing_point in road_points_layer.getFeatures():
                    if existing_point.geometry().intersects(test_point_buffer):
                        near_existing_point = True
                        break

                if not near_existing_point:
                    ft = QgsFeature()
                    ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(test_point.asPoint().x(), test_point.asPoint().y())))
                    ft.setAttributes([dart])
                    road_pts_prov.addFeatures([ft])
                    dart_placed = True

    print("Saving candidate locations to road_points_layer. Created {} points (n_darts = {}).".format(len(list(road_points_layer.getFeatures())), n_darts))


def _place_and_prune_road_pts_model(roads_layer):
    pass

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


def delete_roads_outside_target_area(roads_layer, target_area_layer):
    roads = list(roads_layer.getFeatures())
    n_roads = len(roads)
    polygon = list(target_area_layer.getFeatures())[0]
    roads_layer.startEditing()
    for road in roads:
        if not polygon.geometry().intersects(road.geometry()):
            roads_layer.deleteFeature(road.id())
    roads_layer.commitChanges()
    print("Deleted {} points".format(n_roads - len(list(roads_layer.getFeatures()))))
    return roads_layer


def make_service_area_layer(points_layer, response_radius_NAD83):
    sa_layer = QgsVectorLayer("Polygon", "sa_layer", "memory")
    sa_layer_prov = sa_layer.dataProvider()
    sa_layer.startEditing()
    sa_layer_prov.addAttributes([QgsField("area_id", QVariant.Int), QgsField("from_point", QVariant.Int)])
    circles = []
    current_id = 0
    for point in points_layer.getFeatures():
        ft = QgsFeature()
        ft.setGeometry(QgsGeometry.fromPointXY(point.geometry().asPoint()).buffer(response_radius_NAD83, 10))
        ft.setAttributes([current_id, point["point_id"]])
        circles.append(ft)
        current_id += 1

    sa_layer_prov.addFeatures(circles)
    sa_layer.commitChanges()

    print("Generated service area layer with {} service areas.".format(len(list(sa_layer.getFeatures()))))
    return sa_layer


def make_model_output_layer(ids, response_area_layer):
    print(ids)
    output_layer = QgsVectorLayer("Polygon", "output_layer", "memory")
    output_layer_prov = output_layer.dataProvider()
    output_layer.startEditing()
    output_layer_prov.addAttributes([QgsField("area_id", QVariant.Int)])
    for ft in response_area_layer.getFeatures():
        print(ft['area_id'])
        if ft['area_id'] in ids:
            output_layer.addFeature(ft)
            ids.remove(ft['area_id'])
            if not ids:
                break
    output_layer.commitChanges()
    return output_layer
