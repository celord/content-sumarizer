import importlib
import pkgutil
from .base_platform import BasePlatform

# Discover and load all platform plugins
def load_plugins():
    plugins = {}
    for _, name, _ in pkgutil.iter_modules(__path__):
        if name != 'base_platform':
            module = importlib.import_module(f'.{name}', package=__name__)
            for item_name in dir(module):
                item = getattr(module, item_name)
                if isinstance(item, type) and issubclass(item, BasePlatform) and item is not BasePlatform:
                    # Assuming the class name matches the platform name for the key
                    platform_name = name.lower()
                    plugins[platform_name] = item()
    return plugins

# Dictionary of available platform handlers
platform_plugins = load_plugins()
