# This file builds a test config file and places it in the parent folder
import json
import random


def generate_config():
    # Create config dict
    columbus_areas = ['East Columbus', 'Harmon Road Corridor', 'Far South', 'Far West', 'North Central', 'Airport', 'Victorian Village', 'State of Ohio', 'South Side', 'Harrison West', 'West Scioto', 'Northwest', 'North Linden', 'Livingston Avenue Area', 'Southwest', 'Wolfe Park', 'Downtown', 'Fort Hayes', 'Rocky Fork-Blacklick', 'Franklinton', 'Near East', 'Northland', 'Fifth by Northwest', 'German Village', 'South East', 'Clintonville', 'Olentangy West', 'Brewery District', 'Mid East', 'Far East', 'Hayden Run', 'Far North', 'Italian Village', 'University District', 'South Linden', 'Dublin Road Corridor', 'Milo-Grogan', 'Greater Hilltop', 'Westland', 'Northeast', 'Far Northwest']
    cincinnati_areas = ['North Avondale - Paddock Hills', 'Avondale', 'Bond Hill', 'California', 'Camp Washington', 'Carthage', 'Clifton', 'College Hill', 'Columbia Tusculum', 'Corryville', 'CUF', 'Downtown', 'East End', 'East Price Hill', 'East Walnut Hills', 'East Westwood', 'English Woods', 'Evanston', 'Hartwell', 'Hyde Park', 'Kennedy Heights', 'Linwood', 'Lower Price Hill', 'Madisonville', 'Millvale', 'Mt. Adams', 'Mt. Airy', 'Mt. Auburn', 'Mt. Lookout', 'Mt. Washington', 'North Fairmount', 'Northside', 'Oakley', 'Over-the-Rhine', 'Pendleton', 'Pleasant Ridge', 'Queensgate', 'Riverside', 'Villages at Roll Hill', 'Roselawn', 'Sayler Park', 'Sedamsville', 'South Cumminsville', 'South Fairmount', 'Spring Grove Village', 'Walnut Hills', 'West End', 'West Price Hill', 'Westwood', 'Winton Hills']
    area_sample = random.sample(cincinnati_areas, 5)
    config = {
        "existing_coverage": False,
        "existing_coverage_path": None,
        "combine_areas": True,
        "name": "Cincinnati_Map",
        "max_runtime": 90,
        "mode": "threshold",
        "cache_data": True,
        "load_from_cache": True,
        "map_path": "shp_files/cincinnati_areas.shp",
        "block_path": "shp_files/ohio_census_blocks_nad83_17.shp",
        "road_path": "shp_files/cincinnati_streets.shp",
        "area_select_key": "SNA_NAME",
        "settings": {
            "thresholds": [80],
            "areas": cincinnati_areas,
            "response_time": [300],
            "responder_speed": [4.5, 15, 20, 35],
            "responder_buffer": [180],
            "demand_map": ["Default"]
        }
    }

    config['batch_root'] = "Results/" + config['name'] + "/"

    with open("config.json", "w") as outfile:
        json.dump(config, outfile)

generate_config()