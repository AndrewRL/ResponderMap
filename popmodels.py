import pandas as pd
import numpy as np
import csv
import os
import sys
import random
from statistics import mean
from PyQt5.QtCore import QVariant

class Population:
    def __init__(self):
        self.subpopulations = {}
        self.members = []

    def add(self, name, subpopulation):
        self.subpopulations[name] = subpopulation
        self.members.extend(subpopulation.members)

    def remove(self, name):
        del(self.subpopulations[name])
        self._remove_members(name)

    def _remove_members(self, name):
        for member in self.members:
            if member.subpop == name:
                del(member)

    # TODO: Please...help...meeeeeee
    def summarize(self):
        counts = {field: {} for field in list(self.subpopulations.values())[0].fields}
        for pop in self.subpopulations.values():
            for field in counts.keys():
                attr_vals = pop.attr_counts()
                for val in attr_vals[field].keys():
                    if val in counts[field].keys():
                        counts[field][val] += attr_vals[field][val]
                    else:
                        counts[field][val] = attr_vals[field][val]
        return counts

    def write_shp_file(self, path):
        crs_id = 'EPSG:26917'
        outlayer = QgsVectorLayer('Point' + "?crs=" + crs_id,
                                    'population_layer',
                                    "memory")
        outlayer_prov = outlayer.dataProvider()
        outlayer.startEditing()
        outlayer_prov.addAttributes([QgsField('subpop', QVariant.String), QgsField('id', QVariant.Int)] +
                                    [QgsField('race', QVariant.String), QgsField('age', QVariant.String)])
        outlayer.updateFields()
        features = []
        for member in self.members:
            new_point = QgsFeature()
            new_point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(member.x, member.y)))
            new_point.setAttributes([member.subpop, member.id, member.attributes['race'], member.attributes['age']])
            features.append(new_point)
        outlayer_prov.addFeatures(features)
        outlayer.commitChanges()
        QgsVectorFileWriter.writeAsVectorFormat(outlayer, path, "System", outlayer.crs(),
                                                "ESRI Shapefile")


class SubPopulation:
    def __init__(self, person_generator):
        # TODO: Make members an efficient data structure
        self.members = []
        self.data = []
        self.generator = person_generator
        self.fields = person_generator.attributes.keys()

    def filter(self, on, values=list()):
        pass

    def generate(self, size):
        self.members.extend([self.generator.generate() for _ in range(size)])
        self.data = [person.to_list() for person in self.members]
        return self

    def summarize(self):
        pass

    def attr_counts(self):
        counts = {field: {} for field in self.fields}
        for person in self.members:
            for field in self.fields:
                attr_val = person.attributes[field]
                if attr_val in counts[field].keys():
                    counts[field][attr_val] += 1
                else:
                    counts[field][attr_val] = 1
        return counts


class PersonGenerator:
    def __init__(self, attributes, attr_order=list(), create_id=True):
        self.attributes = attributes
        self.attr_order = attr_order

    def generate(self):
        person = Person()
        if self.attr_order:
            for attr in self.attr_order:
                person.set_attr(attr, self.attributes[attr].generate(self))
        else:
            for attr in self.attributes.keys():
                person.set_attr(attr, self.attributes[attr].generate(self))
        return person


class AttributeGenerator:
    # Takes an attribute name and a function which returns a value for that attribute from the provided person generator
    def __init__(self, name, func):
        self.name = name
        self.func = func

    def generate(self, person_generator):
        return self.func()


class Person:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.subpop = ''
        self.id = np.random.randint(0, 1000000000)
        self.attributes = {}

    def set_loc(self, x, y):
        self.x = x
        self.y = y

    def set_attr(self, attr, value):
        self.attributes[attr] = value

    def to_list(self, header_row=False):
        output = []
        if header_row:
            output.append(self.attributes.keys())
        output.append(self.attributes.values())
        return output


class CensusData:
    def __init__(self, data=list()):
        self.fields = data[0] if data else []
        self.data = data[1:] if data else []
        self.blocks = [row[self.fields.index('id')] for row in self.data] if data else []
        self.by_block = self._create_block_data() if data else {}
        self.groups = {}
        print(f"Loaded census data:\nFields -> {len(self.fields)}\nBlocks -> {len(self.blocks)}\nData -> {len(self.data)}")

    def load_csv(self, path):
        self.fields, self.data = read_csv(path)
        self.blocks = [row[self.fields.index('id')] for row in self.data]
        # TODO: convert data to numeric except id
        new_data = []
        for row in self.data:
            new_row = []
            for field in self.fields:
                if field == 'id':
                    new_row.append(row[self.fields.index(field)])
                    continue
                new_row.append(float(row[self.fields.index(field)]))
            new_data.append(new_row)
        self.data = new_data
        #self.by_block = self._create_block_data()
        return self

    def from_blocks(self, data):
        pass

    def define_group(self, name, blocks=list(), cols=list()):
        self.groups[name] = self.filter(blocks=blocks, cols=cols)

    def filter(self, blocks=list(), cols=list()):
        # Return a new CensusData object
        if not cols:
            cols = self.fields

        if not blocks:
            blocks = self.blocks

        if 'id' not in cols:
            cols.insert(0, 'id')

        filtered_data = list()
        filtered_data.append(cols)

        for row in self.data:
            row_as_float = [row[self.fields.index('id')]] + [float(row[_]) for _ in range(len(row[1:]))]
            filtered_data.append([row_as_float[self.fields.index(field)] for field in cols])
        for row in filtered_data[1:]:
            if row[self.fields.index('id')] not in blocks:
                filtered_data.remove(row)
        return CensusData(filtered_data)

    def sum(self, cols=list()):
        if not cols:
            cols = self.fields.copy()
            cols.remove('id')
        return {col: sum([row[self.fields.index(col)] for row in self.data]) for col in cols}

    def average(self, cols=list()):
        # Average the values in the specified columns and return a key:value set
        return {col: mean([row[self.fields.index(col)] for row in self.data]) for col in cols}

    def _create_block_data(self):
        pass

    def _combine_block_data(self):
        # Merge by_block data to create self.fields and self.data
        pass


def read_csv(path, return_headers=True):
    content = []
    headers = None
    with open(path) as csv_file:
        reader = csv.reader(csv_file)
        if return_headers:
            headers = next(reader)
        for line in reader:
            content.append(line)
    return headers, content


def create_race_multinomial(race_probs, races):
    def race_multinomial(probs=race_probs, races=races):
        return races[np.random.multinomial(1, probs).tolist().index(1)]
    return race_multinomial


def create_age_multinomial(age_probs, ages):
    def age_multinomial(probs=age_probs, ages=ages):
        return ages[np.random.multinomial(1, probs).tolist().index(1)]
    return age_multinomial


# TODO: Generalize probability creation within CensusData
def generate_race_probs(census_data):
    if 'race' not in census_data.groups.keys():
        raise ValueError('The CensusData object must define a "race" group to generate race probabilities.')
    else:
        col_sums = census_data.groups['race'].sum().values()
        try:
            return [col_sum / sum(col_sums) for col_sum in col_sums]
        except ZeroDivisionError:
            return 0.0


def generate_age_probs(census_data):
    if 'age' not in census_data.groups.keys():
        raise ValueError('The CensusData object must define an "age" group to generate age probabilities.')
    else:
        col_sums = census_data.groups['age'].sum().values()
        try:
            return [col_sum / sum(col_sums) for col_sum in col_sums]
        except ZeroDivisionError:
            return 0.0


def random_point_in_block(block):
    # Load block shp file
    # TODO: Only load this layer once rather than once per point
    # Get the block whose attribute matches block

    bbox = block.geometry().boundingBox()
    attempts = 0
    while True:
        test_point = QgsPointXY(random.uniform(bbox.xMinimum(), bbox.xMaximum()), random.uniform(bbox.yMinimum(), bbox.yMaximum()))
        if block.geometry().contains(QgsGeometry.fromPointXY(test_point)):
                return [test_point.x(), test_point.y()]
        attempts += 1


if __name__ == "__main__":

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
    #ohio_census = CensusData().load_csv('Data/ohio_census_data.csv')
    headers, content = read_csv('Data/ohio_census_sample.csv')
    ohio_census = CensusData([headers] + content)

    block_path = "shp_files/ohio_census_blocks_nad83_17.shp"
    block_layer = QgsVectorLayer(block_path, 'block_layer', "ogr")
    print(f'Loaded block layer with {len(list(block_layer.getFeatures()))}')
    block_map = {polygon['BLOCKID10']: polygon for polygon in block_layer.getFeatures()}

    pop = Population()
    for block in ohio_census.blocks:
        block_data = ohio_census.filter(blocks=[block])
        block_data.define_group('race', cols=block_data.fields[4:10])
        block_data.define_group('age', cols=block_data.fields[10:])
        race_probs = generate_race_probs(block_data)
        races = block_data.groups['race'].fields[1:]
        race_generator = AttributeGenerator('race', create_race_multinomial(race_probs, races))
        age_probs = generate_age_probs(block_data)
        age_groups = block_data.groups['age'].fields[1:]
        age_generator = AttributeGenerator('age', create_age_multinomial(age_probs, age_groups))
        attrs = {
            'race': race_generator,
            'age': age_generator
        }
        pop_size = int(round(sum(block_data.groups['race'].sum().values()), 0))
        try:
            if pop_size > 0:
                subpop = SubPopulation(PersonGenerator(attrs)).generate(pop_size)
                try:
                    print(block)
                    block_polygon = block_map[block]
                except IndexError:
                    print(f"Could not find block polygon with ID {block}")

                for member in subpop.members:
                    member.set_loc(*random_point_in_block(block_polygon))
                    member.subpop = block
                pop.add(block, subpop)
            else:
                print(f"block {block} has pop of 0")
        except TypeError as e:
            print(e)
            print(block)
            print(block_data.data)

    pop.write_shp_file('/Users/andrewlaird/PycharmProjects/Van_Mapping_test/Data/pop_layer')
