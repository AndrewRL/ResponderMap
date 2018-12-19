from qgis.core import *
import model_utils
import itertools
import math
from PyQt5.QtCore import QVariant


class BatchLayerHandler:
    # Builds the layers needed for a model based on batch input
    # Load and create layers for modeling
    def __init__(self, batch_config):
        self.config = batch_config
        self.layers = {}

    def make_all(self):

        self.make_area_layers()
        self.make_block_layers()
        self.make_road_layers()
        self.make_road_point_layers()
        self.make_responder_layers()

    def make_area_layers(self):
        # Iterate the areas in batch_config
        config = self.config.config
        self.layers['areas'] = {}
        for area in config['settings']['areas']:
            self.layers['areas'][area] = LayerBuilder()._make_area_layer({"area_source_path": config['map_path'],
                                                                          "area_select_key": config['area_select_key'],
                                                                          "area": area
                                                                          })
        return self

    def make_block_layers(self):
        config = self.config.config
        self.layers['blocks'] = {}
        for area in config['settings']['areas']:
            make_config = {
                "block_source_path": config['block_path'],
                "area_layer": self.layers['areas'][area].layer
            }
            self.layers['blocks'][area] = LayerBuilder()._make_block_layer(make_config)
        return self

    def make_road_layers(self):
        config = self.config.config
        self.layers['roads'] = {}
        for area in config['settings']['areas']:
            make_config = {
                "road_source_path": config['road_path'],
                "area_layer": self.layers['areas'][area].layer
            }
            self.layers['roads'][area] = LayerBuilder()._make_road_layer(make_config)
        return self

    def make_road_point_layers(self):
        config = self.config.config
        print(self.config)
        print(config)
        self.layers['road_points'] = {}
        for area in config['settings']['areas']:
            make_config = {
                "block_source_path": config['block_path'],
                "road_layer": self.layers['roads'][area].layer,
                "area_layer": self.layers['areas'][area].layer
            }
            self.layers['road_points'][area] = LayerBuilder()._make_road_point_layer(make_config)
        return self

    def make_responder_layers(self):
        self.layers['response_areas'] = {}
        config = self.config.config['settings']

        for area in config['areas']:
            service_area_combinations = list(
                itertools.product(*[config['response_time'], config['responder_speed'], config['responder_buffer']]))
            print(service_area_combinations)
            for response_time, responder_speed, responder_buffer in service_area_combinations:
                run_settings = {
                    'road_points_layer': self.layers['road_points'][area].layer,
                    'response_time': response_time,
                    'responder_speed': responder_speed,
                    'responder_buffer': responder_buffer,
                    'areas': area
                }

                response_area_layer = LayerBuilder()._make_responder_layer(run_settings)

                self.layers['response_areas'][model_utils._get_service_area_layer_key(run_settings)] = response_area_layer

        return self

    def get_run_layers(self, model_run_config):
        print("Run config: {}".format(model_run_config))
        layers = {}
        layers["area"] = self.layers['areas'][model_run_config['areas']]
        layers["blocks"] = self.layers['blocks'][model_run_config['areas']]
        layers["roads"] = self.layers['roads'][model_run_config['areas']]
        layers["road_points"] = self.layers['road_points'][model_run_config['areas']]
        layers["response_areas"] = \
            self.layers['response_areas'][model_utils._get_service_area_layer_key(model_run_config)]

        return layers
'''
    def save_layers_to_shp(self, model_run_config):
        
        output_paths = model_utils.get_output_paths(self.layers, self.config, model_run_config)
        
        for layer_type, layer in self.layers.items():
            layer.layer.write(output_paths[layer_type])
'''

class LayerBuilder:
    def __init__(self, logger=None):
        self.logger = logger
        pass

    def make(self, layer_type, make_config):
        layer_build_functions = {
            "area_layer": self._make_area_layer,
            "block_layer": self._make_block_layer,
            "road_layer": self._make_road_layer,
            "road_point_layer": self._make_road_layer
        }

        build_function = layer_build_functions[layer_type]

        return build_function(make_config)

    def _make_area_layer(self, make_config):
        if self.logger:
            self.logger.info("Creating area_layer from source: {}".format(make_config['area_source_path']))
        area_map = AreaSourceLayer().load("area_source_layer", make_config['area_source_path'])
        area_bounds = AreaLayer().copy(area_map)
        area_bounds.isolate_features([make_config['area_select_key']], [[make_config['area']]])
        return area_bounds

    def _make_block_layer(self, make_config):
        if self.logger:
            self.logger.info("Creating block_layer from source: {}".format(make_config['block_source_path']))

        block_map = BlockSourceLayer().load("block_source_layer", make_config['block_source_path'])
        blocks = BlockLayer().copy(block_map)
        blocks.isolate_intersecting_and_contained(make_config['area_layer'])
        blocks.set_attributes()
        return blocks

    def _make_road_layer(self, make_config):
        if self.logger:
            self.logger.info("Creating road_layer from source: {}".format(make_config['road_source_path']))
        road_map = RoadSourceLayer().load("road_source_layer", make_config['road_source_path'])
        roads = RoadLayer().copy(road_map)
        roads.isolate_contained(make_config['area_layer'])
        return roads

    def _make_road_point_layer(self, make_config):
        if self.logger:
            self.logger.info("Creating road_point_layer. RP Model: {}".format(make_config['rp_model']))

        return RoadPointLayer(layer=model_utils.create_road_points_layer(make_config['area_layer'],
                                                                         make_config['road_layer']))

    def _make_coverage_layer(self, make_config):
        pass

    def _make_responder_layer(self, make_config):
        if self.logger:
            self.logger.info("Creating responder layer. Speed: {} | Time: {} | Buffer: {}".format(
                make_config['speed'], make_config['target_time'], make_config['buffer']
            ))

        r_layer = QgsVectorLayer("Polygon", "sa_layer", "memory")
        r_layer = ResponderLayer(layer=r_layer)
        r_layer.layer.setCrs(make_config['road_points_layer'].crs())
        r_layer_prov = r_layer.layer.dataProvider()
        r_layer.layer.startEditing()
        r_layer_prov.addAttributes([QgsField("area_id", QVariant.Int), QgsField("from_point", QVariant.Int)])
        circles = []
        current_id = 0
        for point in make_config['road_points_layer'].getFeatures():
            ft = QgsFeature()
            radius = model_utils.calc_response_radius_km(make_config['response_time'],
                                                         make_config['responder_speed'],
                                                         make_config['responder_buffer'])
            ft.setGeometry(QgsGeometry.fromPointXY(point.geometry().asPoint()).buffer(radius, 10))
            ft.setAttributes([current_id, point["point_id"]])
            circles.append(ft)
            current_id += 1

        r_layer_prov.addFeatures(circles)
        r_layer.layer.commitChanges()

        print("Generated service area layer with {} service areas.".format(len(list(r_layer.layer.getFeatures()))))
        return r_layer


class Layer:
    # Holds the layer and layer name, allows loading, writing, copying
    def __init__(self, layer_type=None, layer=None):
        self.layer_type = layer_type
        self.layer = layer

    def load(self, layer_type, path):
        self.layer = QgsVectorLayer(path, layer_type, "ogr")
        return self

    def write(self, path):
        QgsVectorFileWriter.writeAsVectorFormat(self.layer, path, "System", self.layer.crs(),
                                                "ESRI Shapefile")

    def copy(self, source_layer):
        source_layer = source_layer.layer
        type_geom = QgsWkbTypes.displayString(int(QgsWkbTypes.flatType(int(source_layer.wkbType()))))
        crs_id = source_layer.crs().authid()
        out_layer = QgsVectorLayer(type_geom + "?crs=" + crs_id,
                                    self.layer_type,
                                   "memory")

        features = [feat for feat in source_layer.getFeatures()]

        out_layer_prov = out_layer.dataProvider()
        attr = source_layer.dataProvider().fields().toList()
        out_layer_prov.addAttributes(attr)
        out_layer.updateFields()
        out_layer_prov.addFeatures(features)
        self.layer = out_layer
        return self

    def make(self, layer_type, shape):
        # Create a scratch layer with feature shape "shape"
        pass

    def isolate_features(self, keys, values):
        filter_expression = ""
        count = 0
        num_keys = len(keys)
        for index, key in enumerate(keys):
            for value in values[index]:
                if isinstance(value, str):
                    filter_expression += '"{}"=\'{}\''.format(key, value)
                else:
                    filter_expression += '"{}"={}'.format(key, value)
                if count < num_keys-1:
                    filter_expression += "&&"
            count += 1
        print(filter_expression)
        self.layer.setSubsetString(filter_expression)

    def isolate_contained(self, area_layer):
        polygon = next(area_layer.getFeatures())
        self.layer.startEditing()
        for ft in self.layer.getFeatures():
            if not polygon.geometry().contains(ft.geometry()):
                self.layer.deleteFeature(ft.id())
        self.layer.commitChanges()
        return self

    def isolate_intersecting(self, area_layer):
        polygon = next(area_layer.getFeatures())
        self.layer.startEditing()
        for ft in self.layer.getFeatures():
            if not polygon.geometry().intersects(ft.geometry()):
                self.layer.deleteFeature(ft.id())
        self.layer.commitChanges()
        return self

    def isolate_intersecting_and_contained(self, area_layer):
        polygon = next(area_layer.getFeatures())
        self.layer.startEditing()
        for road in self.layer.getFeatures():
            if not polygon.geometry().intersects(road.geometry()) or not polygon.geometry().contains(road.geometry()):
                self.layer.deleteFeature(road.id())
        self.layer.commitChanges()
        return self


class AreaSourceLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("area_source_layer", layer)


class BlockSourceLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("block_source_layer", layer)


class RoadSourceLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("road_source_layer", layer)


class CoverageSourceLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("coverage_source_layer", layer)


class AreaLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("area_layer", layer)


class BlockLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("block_layer", layer)

    def set_attributes(self):
        provider = self.layer.dataProvider()
        provider.addAttributes([QgsField("point_id", QVariant.Int), QgsField("demand", QVariant.Int)])
        self.layer.startEditing()
        for index, ft in enumerate(self.layer.getFeatures()):
            self.layer.changeAttributeValue(ft.id(), provider.fieldNameIndex("point_id"), index)
            self.layer.changeAttributeValue(ft.id(), provider.fieldNameIndex("demand"), math.sqrt(ft.geometry().area()))
        self.layer.commitChanges()

class RoadLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("road_layer", layer)


class RoadPointLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("road_point_layer", layer)


class ResponderLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("responder_layer", layer)


class CoverageLayer(Layer):
    def __init__(self, layer=None):
        super().__init__("coverage_layer", layer)


def save_layers_as_shp(layers):
    for path, layer in layers:
        layer.layer.write(path)

