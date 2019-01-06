# This file builds a test config file and places it in the parent folder
import json


def generate_config():
    # Create config dict
    config = {
        "existing_coverage": True,
        "existing_coverage_path": "Results/TestBatch2/Model Runs/1/selected_areas.shp",
        "name": "Kerr_Pres_Run",
        "max_runtime": 90,
        "mode": "threshold",
        "map_path": "shp_files/local_area_boundary.shp",
        "block_path": "shp_files/block_outlines.shp",
        "road_path": "shp_files/public_streets.shp",
        "area_select_key": "MAPID",
        "settings": {
            "thresholds": [n for n in range(25, 100, 25)],
            "areas": ["KERR"],
            "response_time": [300],
            "responder_speed": [4.5, 10, 20],
            "responder_buffer": [180],
            "demand_map": ["Default"]
        }
    }

    config['batch_root'] = "Results/" + config['name'] + "/"

    with open("config.json", "w") as outfile:
        json.dump(config, outfile)

generate_config()