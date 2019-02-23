import json
import itertools
import os
from layers import *
from model_core import ModelCore, CoveragePreprocessor
from model_utils import MetadataHandler, ConfigReader, GraphBuilder


class BatchHandler:
    def __init__(self, batch_config_rdr, batch, logger=None):
        self.logger = logger
        self.batch_config = batch_config_rdr
        # TODO: Get rid of batch import and create it within batch handler?
        self.batch = batch
        self.metadata = MetadataHandler()
        self.demand_points = None
        self.paths = PathBuilder(self).generate_paths()
        self.layers = BatchLayerHandler(self.batch_config)

    def run(self, logger=None):
        # Run all of the models presented in the batch config
        self.metadata.add_config(self.batch_config)

        # Prepare the layer files for the batch
        print(self.batch_config.config)
        self.layers = BatchLayerHandler(self.batch_config)
        self.layers.make_all()
        if self.batch_config.config['existing_coverage']:
            self.layers = CoveragePreprocessor(self).run()
        print("Full layer table:")
        print(self.layers.layers)

        # Set up area combination if needed
        if self.batch_config.config['combine_areas']:
            models = []

        if self.logger is not None:
            self.logger.info("Running {} models from batch: {}".format(len(self.batch), self.batch_config.config['name']))
            self.logger.info("Generating output dirs at {}".format(self.batch_config.config['batch_root']))
            # TODO: Update create dirs to throw error if dirs exist unless config flag overwrite=True
        self._create_dirs()
        LayerWriter(self, self.layers).write_all()
        for index, model_run_config in enumerate(self.batch):
            if self.logger is not None:
                self.logger.info("Running model {} of {} from batch: {}".format(index, len(self.batch),
                                                                                self.batch_config.config['name']))
            run_paths = self.paths.paths['runs'][str(model_run_config['run_name'])]
            model_run = ModelCore(self.batch_config, model_run_config, run_paths, logger)
            print("Running model with the following settings and layers:")
            print(model_run_config)
            for layer in self.layers.get_run_layers(model_run_config).values():
                print("{} --> {} features".format(layer.layer_type, len(list(layer.layer.getFeatures()))))
            model_run.load_layers(self.layers.get_run_layers(model_run_config))
            model_run.model()
            model_results = model_run.results.metadata['results']
            if self.logger is not None:
                self.logger.info("Run complete. Status: {} | Coverage: FIX ME | Num. Responders: {}".format(model_results[0]['status'],
                                                                                           model_results[0]['n_responders']))
            self.metadata.metadata['results'].append(model_run.results.metadata)

            # Save results for combination if combine_areas flag is True
            if self.batch_config.config['combine_areas'] and model_run.status != 'Infeasible':
                models.append(model_run)

        if self.batch_config.config['combine_areas']:
            model_utils.merge_models_by_area(self, models)

        #self._save_metadata()
        self._save_batch_csv()

        # TODO: Move graphing to it's own module and add graph config to config

        graph_config = {
            'title': "Scatter Test",
            'outfile': 'scatter_test.jpeg',
            'x_key': 'thresholds',
            'y_key': 'n_responders',
            'x_title': 'Threshold (%)',
            'y_title': 'Num. Responders',
            'x_range': None,
            'y_range': None
        }

        test_scatter = GraphBuilder(self, graph_config)
        test_scatter.plot()

    def _save_metadata(self):
        metadata_path = self.batch_config.config["batch_root"] + "{}_metadata".format(self.batch_config.config['name'])
        self.metadata.to_json(metadata_path + ".json")

    def _save_batch_csv(self):
        csv_path = self.batch_config.config["batch_root"] + "{}_summary.csv".format(self.batch_config.config['name'])
        self.metadata.to_csv(csv_path)

    def _create_dirs(self):
        # Build the directory structure for the batch files
        os.makedirs(os.getcwd() + "/" + self.batch_config.config['batch_root'], exist_ok=True)
        os.makedirs(os.getcwd() + "/" + self.batch_config.config['batch_root'] + "/Model Runs/", exist_ok=True)

        for run in range(len(self.batch)):
            run_path = self.batch_config.config['batch_root'] + "Model Runs/" + str(run) + "/"
            if not os.path.isdir(run_path):
                os.mkdir(run_path)
            run_shp_files_path = run_path + "shp_files/"
            if not os.path.isdir(run_shp_files_path):
                os.mkdir(run_shp_files_path)

    def _save_run_files(self, model_run_results):
        # Create the directory structure, metadata, and shp files related to a model run
        pass

    def _save_batch_files(self):
        # Save CSV of batch information
        pass


class PathBuilder:
    def __init__(self, batch_handler):
        self.batch_handler = batch_handler
        self.paths = {}

    def generate_paths(self):
        # Generate all paths needed based on config
        self._generate_batch_paths()
        self._generate_all_run_paths()

        return self

    def _generate_batch_paths(self):
        # Generate batch level paths
        batch_config = self.batch_handler.batch_config.config
        self.paths['area_boundaries'] = batch_config['map_path']
        self.paths['block_outlines'] = batch_config['block_path']
        self.paths['roads'] = batch_config['road_path']

    def _generate_all_run_paths(self):
        # Generate paths for all model runs
        self.paths['runs'] = {}
        for run_num, _ in enumerate(self.batch_handler.batch):
            self._generate_run_paths(run_num)

    def _generate_run_paths(self, run_name):
        # Generate all paths for a given model run
        config = self.batch_handler.batch_config.config
        model_runs_dir = config['batch_root'] + "Model Runs/"
        run_name = str(run_name)

        self.paths['runs'][run_name] = {}
        self.paths['runs'][run_name]['area_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "area_layer.shp"
        self.paths['runs'][run_name]['grid_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "grid_layer.shp"
        self.paths['runs'][run_name]['road_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "roads_layer.shp"
        self.paths['runs'][run_name]['road_points_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "road_points_layer.shp"
        self.paths['runs'][run_name]['block_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "block_layer.shp"
        self.paths['runs'][run_name]['responder_shp_output'] = model_runs_dir + run_name + "/shp_files/" + "responder_layer.shp"
        self.paths['runs'][run_name]['model_result_shp_output'] = model_runs_dir + run_name + "/shp_files/selected_areas.shp"
        self.paths['runs'][run_name]['selected_points_shp_output'] = model_runs_dir + run_name + "/shp_files/selected_points.shp"
        self.paths['runs'][run_name]['csv_output'] = model_runs_dir + run_name + "/" + config['name'] + "_summary.csv"

    # TODO: Replace this with a PathHandler class when needed
    def _get_run_paths(self, run_name):
        return self.paths['runs'][run_name]
