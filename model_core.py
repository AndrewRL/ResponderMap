import model_utils
import pulp
from pulp import solvers
import os
from pyspatialopt.analysis import pyqgis_analysis
from pyspatialopt.models import covering, utilities
from model_utils import MetadataHandler
from layers import *


class ModelCore:
    # TODO: ModelCore shouldn't need batch_config in addition to run_config. Model config could include paths.
    def __init__(self, batch_config, model_run_config, paths, logger=None):
        # TODO: ModelCore should use layers object rather than importing layers to it's own variables
        self.batch_config = batch_config
        self.model_run_config = model_run_config
        self.paths = paths
        # TODO: Get data from pulp model object to populate these fields
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

        self._create_run_dirs()

        # TODO: Figure out why it is necessary to reload here rather than just using the layer.
        block_layer = QgsVectorLayer(self.paths['block_shp_output'], "block_layer", "ogr")
        response_area_layer = QgsVectorLayer(self.paths['responder_shp_output'], "response_area_layer", "ogr")
        if self.logger:
            self.logger.info("Reloaded layers from file. Found {} blocks and {} response areas."
                             .format(len(list(block_layer.getFeatures())),
                              len(list(response_area_layer.getFeatures()))))

        binary_coverage_polygon = pyqgis_analysis.generate_partial_coverage(block_layer, response_area_layer,
                                                                            "demand", "point_id", "area_id")
        # TODO: Build a handler which selects the proper model based on config
        # TODO: Move this code into a function (class?) for partial_coverage_threshold
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

        # TODO: Move result extraction into it's own function (or tie to partial_coverage_model object)
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
        self.selected_points = SelectedPointsLayer().copy(RoadPointLayer(layer=self.road_points))
        self.selected_points.layer.setSubsetString(point_select_query)
        self.selected_areas = SelectedAreasLayer().copy(ResponderLayer(layer=self.response_areas))
        self.selected_areas.layer.setSubsetString(select_query)
        self.results.parse_model_output(self)
        # TODO: Fix calculation of covered demand and add to output
        #total_coverage = pyqgis_analysis.get_covered_demand(block_layer, "demand", "partial",
        #                                                    response_area_layer)
        if self.logger:
            # self.logger.info(
            # "{0:.2f}% of demand is covered".format((100 * total_coverage) / binary_coverage_polygon["totalDemand"]))
            self.logger.info("{} responders".format(len(ids)))
        _write_shp_file(self.selected_areas.layer, self.paths['model_result_shp_output'])
        _write_shp_file(self.selected_points.layer, self.paths['selected_points_shp_output'])
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

    # TODO: Create a class to handle batch and model paths
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

    # TODO: Move this function to layers.py as QgsProjectWriter
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

        for layer_name, layer in layer_handler.items():
            setattr(self, layer_name, layer.layer)


class ModelEngine:
    # Parent class for all the different model types (threshold, partial / binary coverage)
    pass


class Preprocessor:
    # Parent class for model layer preprocessors (preexisting coverage)
    pass


class CoveragePreprocessor:
    # Adapts batchhandler to produce pre-existing.
    def __init__(self, batch_handler):
        self.batch_handler = batch_handler
        self.layers = batch_handler.layers
        self.config = batch_handler.batch_config

    def run(self):
        # Load existing coverage
        self.layers.layers['existing'] = CoverageLayer().load("coverage_layer",
                                                              self.config.config['existing_coverage_path'])

        self.layers.clone_layers("blocks", "original_block", "original_block_layer")
        print(self.layers)
        # Create coverage layers
        self.create_coverage_layers()

        # Save coverage layers
        LayerWriter(self.batch_handler, self.layers).write_all()
        # Reoutput original block layer?
        return self.layers

    def create_coverage_layers(self):
        layers = self.layers.layers
        for tag, layer in layers['blocks'].items():
            # Get intersection between block layer and existing coverage layer
            print("Clipping layer: {}".format(tag))
            print("Area before clip: {}".format(sum([feature.geometry().area() for feature in layer.layer.getFeatures()])))
            layer.clip(layers['existing'])
            print("Area after clip: {}".format(sum([feature.geometry().area() for feature in layer.layer.getFeatures()])))


# TODO: Remove these once they are no longer needed by _write_qgs_method etc
def _load_shp_file(path, name="new_layer"):
    return QgsVectorLayer(path, name, "ogr")


def _write_shp_file(layer, path):
    QgsVectorFileWriter.writeAsVectorFormat(layer, path, "System", layer.crs(),
                                            "ESRI Shapefile")
