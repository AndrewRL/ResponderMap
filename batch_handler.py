import json
import itertools
import os
from model_core import ModelCore, LayerBuilder
from model_utils import MetadataHandler, ConfigReader, GraphBuilder


class BatchHandler:
    def __init__(self, batch_config_rdr, batch, logger=None):
        self.logger = logger
        self.batch_config = batch_config_rdr
        self.batch = batch
        self.metadata = MetadataHandler()
        self.demand_points = None

    def run(self, logger=None):
        # Run all of the models presented in the batch config
        self.metadata.add_config(self.batch_config)

        # Prepare the layer files for the batch
        print(self.batch_config.config)
        layers = LayerBuilder(self.batch_config)
        layers.make_all()
        print("Full layer table:")
        print(vars(layers.layers))

        if self.logger is not None:
            self.logger.info("Running {} models from batch: {}".format(len(self.batch), self.batch_config.config['name']))
            self.logger.info("Generating output dirs at {}".format(self.batch_config.config['batch_root']))
            self._create_dirs()
        for index, model_run_config in enumerate(self.batch):
            if self.logger is not None:
                self.logger.info("Running model {} of {} from batch: {}".format(index, len(self.batch),
                                                                                self.batch_config.config['name']))
            model_run = ModelCore(self.batch_config, model_run_config, logger=logger)
            print("Running model with the following settings and layers:")
            print(model_run_config)
            print(layers.get_run_layers(model_run_config))
            model_run.load_layers(layers.get_run_layers(model_run_config))
            model_run.model()
            model_results = model_run.results.metadata['results']
            if self.logger is not None:
                self.logger.info("Run complete. Status: {} | Coverage: FIX ME | Num. Responders: {}".format(model_results[0]['status'],
                                                                                           model_results[0]['n_responders']))
            self.metadata.metadata['results'].append(model_run.results.metadata)

        #self._save_metadata()
        self._save_batch_csv()

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
        print(test_scatter)
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

    def _save_run_files(self, model_run_results):
        # Create the directory structure, metadata, and shp files related to a model run
        pass

    def _save_batch_files(self):
        # Save CSV of batch information
        pass

'''
class ShapefileRenderer:


# Creates shapefiles for a model run (takes MetadataHandler)



        # Instantiate a ConfigReader with the path to the configuration file
        # Parse the json config file
        # Paths for input and output files
        # Batch definition
        # {
        max_runtime = 90,
        modes = [
            {
                mode_name = "threshold"
        test_values = [50, 75, 100]
        },
        {
            mode_name = "max_coverage"
        test_values = [20, 50, 100]
        }
        ],
        areas = [Kerrisdale, Kilarney],
        response_time = [3, 5, 7],
        responders = [
            {
                type = "Community Responder",
                       speed = 5,
                               buffer_time = 120,
                                             number = X
        },
        {
            type = "Staff Responder",
                   speed = 15,
                           buffer_time = 90,
                                         number = 5
        }
        ]
        }
        # Output the status of configuration
        # Prepare data files for model
        # Pass files to model engine
        # Preload shp files for areas (instead of recreating them for each model run)
        # Run each model based on the config
        # Output the results of each model run to the specified path, as well as a summary csv/xlsx file with information on all runs in each mode
        # Parent Dir
        # Batch Dir
        # Batch metadata file (contains all modelrun metadata plus batch config information)
        # Batch Summaries by mode
        # Model Run Dir
        # Model run metadata
        {
        status = "success", ("timeout")
        date = "2019-Nov-27",
        time = "12:00:00",
        runtime = 1200,
        user = "admin",
        config = {
            blah
        blah
        }
        responder_locs = [{
            area_id = 1,
                      loc = (x, y)
        }, ...]
        results = {
            coverage = 100,
                       num_responders = 53,
                                        responder_data = [
            {
                type = "Community Responder",
                       speed = 5,
                               number = 50
        },
        {
            type = "Staff Responder",
                   speed = 15,
                           number = 3
        }
        ]
        selected_areas = {
            {
                loc = (x, y),
                      responder_radius = 300,
                                         area_id = 1,
                                                   responder = {
            {
                type = "Community Responder",
                       speed = 5
        }
        }
        }
        }
        }
        }
        # SHP files

        # Make the results browsable and reviewable using an online GIS viewer 
        
'''
