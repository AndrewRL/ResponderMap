import model_utils
import pulp
import itertools
from pulp import solvers
import os
from pyspatialopt.analysis import pyqgis_analysis
from pyspatialopt.models import covering, utilities
from model_utils import MetadataHandler
from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsProject
from PyQt5.QtCore import QFileInfo


class ModelCore:

    def __init__(self, batch_config, model_run_config, logger=None):
        self.batch_config = batch_config
        self.model_run_config = model_run_config
        self.paths = self._generate_paths(self.batch_config, self.model_run_config)
        self.problem = None
        self.vars = None
        self.status = None
        self.results = MetadataHandler()
        self.point_ids = None
        self.area_ids = None
        self.selected_points = None
        self.selected_areas = None
        self.area = None
        self.blocks = None
        self.roads = None
        self.road_points = None
        self.grid = None
        self.response_areas = None
        self.existing_coverage = None
        self.coverage_mask = None
        self.logger = logger

    def model(self):
        # Run a threshold model on a provided demand and response_area layer

        '''
        if self.batch_config.config['preload_coverage']:
            if self.batch_config.config['existing_coverage']:
                self.existing_coverage = _load_shp_file(self.batch_config.config['existing_coverage'])
            else:
                print("Generating sample existing_coverage layer.")
                # Make a sparse road points layer
                # Make a response area layer
                # self.existing_coverage = ec_response_area_layer

            # find the "anti-intersection" between each block and the ec_response_area_layer dissolved_geom
            # self.blocks = anti_intersection_layer
        '''
        self._create_run_dirs()
        self._save_shp_files()

        # TODO: Figure out why it is necessary to reload here rather than just using the layer.
        block_layer = QgsVectorLayer(self.paths['block_shp_output'], "block_layer", "ogr")
        response_area_layer = QgsVectorLayer(self.paths['responder_shp_output'], "response_area_layer", "ogr")
        if self.logger:
            self.logger.info("Reloaded layers from file. Found {} blocks and {} response areas."
                             .format(len(list(block_layer.getFeatures())),
                              len(list(response_area_layer.getFeatures()))))

        binary_coverage_polygon = pyqgis_analysis.generate_partial_coverage(block_layer, response_area_layer,
                                                                            "demand", "point_id", "area_id")

        # Create the mclp model
        if self.logger:
            self.logger.info("Creating MCLP model...")
        mclp = covering.create_cc_threshold_model(binary_coverage_polygon, self.model_run_config['thresholds'])
        # Solve the model using GLPK
        if self.logger:
            self.logger.info("Solving MCLP...")

        mclp.solve(solvers.PULP_CBC_CMD())
        self.problem = mclp
        if pulp.LpStatus[mclp.status] == "Infeasible":
            print(pulp.LpStatus[mclp.status])
            print("Model run {} deemed infeasible. Skipping...".format(self.model_run_config['run_name']))
            self.results.parse_model_output(self)
            return
            # TODO: Update model results to reflect infeasibility.

        if self.logger:
            self.logger.info("Extracting results")
        ids = utilities.get_ids(mclp, "responder_layer")
        self.area_ids = ids
        point_ids = [str(ft['from_point']) for ft in list(response_area_layer.getFeatures()) if str(ft['area_id']) in ids]
        self.point_ids = point_ids
        # Generate a query that could be used as a definition query or selection in arcpy
        select_query = pyqgis_analysis.generate_query(ids, unique_field_name="area_id")
        point_select_query = pyqgis_analysis.generate_query(point_ids, unique_field_name="point_id")
        if self.logger:
            self.logger.info("Output query to use to generate response area maps is: {}".format(select_query))
            self.logger.info("Output query to use to generate response point maps is: {}".format(point_select_query))
        # Determine how much demand is covered by the results
        self.response_areas.setSubsetString(select_query)
        self.road_points.setSubsetString(point_select_query)
        self.results.parse_model_output(self)
        #total_coverage = pyqgis_analysis.get_covered_demand(block_layer, "demand", "partial",
        #                                                    response_area_layer)
        if self.logger:
            # self.logger.info(
            # "{0:.2f}% of demand is covered".format((100 * total_coverage) / binary_coverage_polygon["totalDemand"]))
            self.logger.info("{} responders".format(len(ids)))
        _write_shp_file(self.response_areas, self.paths['model_result_shp_output'])
        _write_shp_file(self.road_points, self.paths['selected_points_shp_output'])
        self._write_qgs_project()

        return self

    def _test_serviceable_area(self):
        dissolved_geom = None
        for ft in self.response_areas.getFeatures():
            if not dissolved_geom:
                dissolved_geom = ft.geometry()
            dissolved_geom = dissolved_geom.combine(ft.geometry())
        local_area_geom = next(self.area.getFeatures()).geometry()
        intersection = dissolved_geom.intersection(local_area_geom)
        if intersection.area() >= local_area_geom.area() * (self.model_run_config['thresholds'] / 100):
            return True
        else:
            return False

    def _make_roads_layer(self):

        roads_layer = _load_shp_file(self.paths['roads'], "roads_layer")
        target_roads_layer = model_utils.isolate_roads(roads_layer, self.area)
        target_roads_layer.setCrs(self.area.crs())

        return target_roads_layer

    def _make_road_points_layer(self):

        road_points_layer = model_utils.create_road_points_layer(self.area, self.roads)
        road_points_layer.setCrs(self.roads.crs())

        return road_points_layer

    def _make_block_layer(self):
        block_polygon_layer = _load_shp_file(self.paths['block_outlines'], "block_outlines")
        target_blocks_layer = model_utils.isolate_blocks(block_polygon_layer, self.area)
        target_blocks_layer.setCrs(self.area.crs())

        return target_blocks_layer

    def _make_area_layer(self):
        # Load map to select modeling area from
        area_boundaries = _load_shp_file(self.paths['area_boundaries'], "area_boundaries")
        # Isolate the polygon for the area to be modeled
        local_area_layer = model_utils.isolate_feature(area_boundaries,
                                                       self.batch_config.config['area_select_key'],
                                                       self.model_run_config['areas'])
        local_area_layer.setCrs(area_boundaries.crs())
        return local_area_layer

    def _make_service_area_layer(self):
        config = self.model_run_config
        response_radius_km = model_utils.calc_response_radius_km(config['response_time'], config['responder_speed'], config['responder_buffer'])
        response_area_layer = model_utils.make_service_area_layer(self.road_points, response_radius_km)
        response_area_layer.setCrs(self.road_points.crs())

        return response_area_layer

    def _create_run_dirs(self):

        run_path = self.batch_config.config['batch_root'] + "Model Runs/" + str(self.model_run_config['run_name']) + "/"
        if not os.path.isdir(run_path):
            os.mkdir(run_path)
        run_shp_files_path = run_path + "shp_files/"
        if not os.path.isdir(run_shp_files_path):
            os.mkdir(run_shp_files_path)

    def _save_shp_files(self):
        _write_shp_file(self.area, self.paths['area_shp_output'])
        _write_shp_file(self.blocks, self.paths['block_shp_output'])
        _write_shp_file(self.roads, self.paths['road_shp_output'])
        _write_shp_file(self.road_points, self.paths['road_points_shp_output'])
        _write_shp_file(self.response_areas, self.paths['responder_shp_output'])

    def _generate_paths(self, batch_config, model_run_config):
        batch_config = batch_config.config
        paths = {}
        model_runs_dir = batch_config['batch_root'] + "Model Runs/"
        run_name = str(model_run_config['run_name'])
        paths['area_boundaries'] = batch_config['map_path']
        paths['block_outlines'] = batch_config['block_path']
        paths['roads'] = batch_config['road_path']
        paths['area_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "area_layer.shp"
        paths['grid_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "grid_layer.shp"
        paths['road_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "roads_layer.shp"
        paths['road_points_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "road_points_layer.shp"
        paths['block_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "block_layer.shp"
        paths['responder_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "responder_layer.shp"
        paths['model_result_shp_output'] = model_runs_dir + run_name + "/shp_files/selected_areas.shp"
        paths['selected_points_shp_output'] = model_runs_dir + run_name + "/shp_files/selected_points.shp"
        paths['csv_output'] = model_runs_dir + run_name + "/" + batch_config['name'] + "_summary.csv"
        return paths

    def _update_results(self):
        # Add the relevant metadata to self.results for the run
        pass

    def _write_qgs_project(self):
        # TODO: This function probably doesn't need to reload the shp files
        project = QgsProject().instance()
        config = self.batch_config.config
        project_path = config['batch_root'] + config['name'] + str(self.model_run_config['run_name']) + '.qgs'

        # add files to the project and register them

        project.addMapLayer(_load_shp_file(self.paths['area_shp_output']))
        project.addMapLayer(_load_shp_file(self.paths['block_shp_output']))
        project.addMapLayer(_load_shp_file(self.paths['road_shp_output']))
        project.addMapLayer(_load_shp_file(self.paths['model_result_shp_output']))
        project.addMapLayer(_load_shp_file(self.paths['selected_points_shp_output']))

        # write the project file
        project.write(project_path)
        project.clear()

    def load_layers(self, layer_handler):

        for layer_name, layer in vars(layer_handler).items():
            setattr(self, layer_name, layer)


class LayerBuilder:

    # Load and create layers for modeling
    def __init__(self, batch_config):
        self.config = batch_config
        self.layers = {
            "areas": {},
            "blocks": {},
            "roads": {},
            "road_points": {},
            "pre_coverage": {},
            "response_areas": {}
        }

    def make_all(self):

        self.make_area_layers()
        self.make_block_layers()
        self.make_road_layers()
        self.make_road_point_layers()
        self.make_response_area_layers()

    def make_area_layers(self):
        # Iterate the areas in batch_config
        print(self.config)
        print(self.config.config)
        for area in self.config.config['settings']['areas']:
            area_bounds = _load_shp_file(self.config.config['map_path'], 'area_boundaries')
            area_layer = model_utils.isolate_feature(area_bounds, self.config.config['area_select_key'], area)
            area_layer.setCrs(area_bounds.crs())
            self.layers['areas'][area] = area_layer

    def make_block_layers(self):

        for area in self.config.config['settings']['areas']:
            blocks = _load_shp_file(self.config.config['block_path'], "block_outlines")
            target_blocks = model_utils.isolate_blocks(blocks, self.layers['areas'][area])
            target_blocks.setCrs(self.layers['areas'][area].crs())
            print("Blocks found: {}".format(len(list(target_blocks.getFeatures()))))
            self.layers['blocks'][area] = target_blocks

    def make_road_layers(self):

        for area in self.config.config['settings']['areas']:
            roads = _load_shp_file(self.config.config['road_path'], "roads_layer")
            print("Original roads found: {}".format(len(list(roads.getFeatures()))))
            print(len(list(self.layers['areas'][area].getFeatures())))
            target_roads = model_utils.isolate_roads(roads, self.layers['areas'][area])
            target_roads.setCrs(self.layers['areas'][area].crs())
            print("Roads found: {}".format(len(list(target_roads.getFeatures()))))
            self.layers['roads'][area] = target_roads

    def make_road_point_layers(self):
        print(self.layers)
        for area in self.config.config['settings']['areas']:
            road_points_layer = model_utils.create_road_points_layer(self.layers['areas'][area], self.layers['roads'][area])
            road_points_layer.setCrs(self.layers['roads'][area].crs())
            self.layers['road_points'][area] = road_points_layer

    def make_response_area_layers(self):
        config = self.config.config['settings']

        for area in config['areas']:
            service_area_combinations = list(itertools.product(*[config['response_time'], config['responder_speed'], config['responder_buffer']]))
            print(service_area_combinations)
            for response_time, responder_speed, responder_buffer in service_area_combinations:
            
                response_radius_km = model_utils.calc_response_radius_km(response_time, responder_speed,
                                                                         responder_buffer)
                response_area_layer = model_utils.make_service_area_layer(self.layers['road_points'][area], response_radius_km)
                response_area_layer.setCrs(self.layers['road_points'][area].crs())
                run_settings = {
                    'areas': area,
                    'response_time': response_time,
                    'responder_speed': responder_speed,
                    'responder_buffer': responder_buffer
                }
                self.layers['response_areas'][_get_service_area_layer_key(run_settings)] = response_area_layer

    def get_run_layers(self, run_settings):
        layers = LayerHandler()
        layers.add("area", self.layers['areas'][run_settings['areas']])
        layers.add("blocks", self.layers['blocks'][run_settings['areas']])
        layers.add("roads", self.layers['roads'][run_settings['areas']])
        layers.add("road_points", self.layers['road_points'][run_settings['areas']])
        layers.add("response_areas", self.layers['response_areas'][_get_service_area_layer_key(run_settings)])

        return layers


def _get_service_area_layer_key(run_vals):
    return "{}_{}_{}_{}".format(run_vals['areas'], run_vals['response_time'], run_vals['responder_speed'],
                                run_vals['responder_buffer'])


class LayerHandler:
    def __init__(self):
        self.area = None
        self.blocks = None
        self.roads = None
        self.road_points = None
        self.response_areas = None

    def add(self, layer_type, layer):
        setattr(self, layer_type, layer)


def _load_shp_file(path, name="new_layer"):
    return QgsVectorLayer(path, name, "ogr")


def _write_shp_file(layer, path):
    QgsVectorFileWriter.writeAsVectorFormat(layer, path, "System", layer.crs(),
                                            "ESRI Shapefile")
