import json
import itertools
import os
from layers import *
from model_core import ModelCore
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
        layers = BatchLayerHandler(self.batch_config)
        layers.make_all()
        print("Full layer table:")
        print(layers.layers)

        if self.logger is not None:
            self.logger.info("Running {} models from batch: {}".format(len(self.batch), self.batch_config.config['name']))
            self.logger.info("Generating output dirs at {}".format(self.batch_config.config['batch_root']))
            # TODO: Update create dirs to throw error if dirs exist unless config flag overwrite=True
            self._create_dirs()
        for index, model_run_config in enumerate(self.batch):
            if self.logger is not None:
                self.logger.info("Running model {} of {} from batch: {}".format(index, len(self.batch),
                                                                                self.batch_config.config['name']))
            model_run = ModelCore(self.batch_config, model_run_config, logger=logger)
            print("Running model with the following settings and layers:")
            print(model_run_config)
            for layer in layers.get_run_layers(model_run_config).values():
                print("{} --> {} features".format(layer.layer_type, len(list(layer.layer.getFeatures()))))
            model_run.load_layers(layers.get_run_layers(model_run_config))
            model_run.model()
            model_results = model_run.results.metadata['results']
            if self.logger is not None:
                self.logger.info("Run complete. Status: {} | Coverage: FIX ME | Num. Responders: {}".format(model_results[0]['status'],
                                                                                           model_results[0]['n_responders']))
            self.metadata.metadata['results'].append(model_run.results.metadata)

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

    def _save_run_files(self, model_run_results):
        # Create the directory structure, metadata, and shp files related to a model run
        pass

    def _save_batch_files(self):
        # Save CSV of batch information
        pass
