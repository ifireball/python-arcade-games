from rich import print

from .asset_collection import AssetCollection
from .configuration import Configuration

INPUT_DIR = "resource_making/raw"
OUTPUT_DIR = "resources"
CONFIG_FILE = "asset_pipeline.toml"


def run_pipeline(work_path):
    configuration_path = work_path / CONFIG_FILE
    config = Configuration.from_toml(configuration_path)
    print(config)
    assets = AssetCollection.from_configuration(config, work_path / INPUT_DIR)
    print(assets)
    for tileset in assets.tilesets:
        tileset.save_to(work_path / OUTPUT_DIR)