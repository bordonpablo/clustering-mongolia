import os
import yaml


def load_config(config_path, command_name):
    """Load a YAML config file and return the sub-dict for command_name.

    Args:
        config_path: path to the YAML file.
        command_name: top-level key to return (e.g. "process_data").

    Raises:
        FileNotFoundError: if config_path does not exist.
        KeyError: if command_name is not present in the file.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: '{config_path}'. "
            "Create one or point --config to an existing file."
        )

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if command_name not in config:
        raise KeyError(
            f"Command section '{command_name}' not found in config file: '{config_path}'. "
            f"Available sections: {list(config.keys())}"
        )

    return config[command_name]
