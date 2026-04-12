import importlib
import logging
import pkgutil


def load_camera_modules() -> dict:
    """Load all camera_types modules. Returns {camera_id: module} mapping."""
    camera_modules: dict = {}
    try:
        import camera_types

        for module_info in pkgutil.iter_modules(camera_types.__path__):
            if not module_info.name.startswith("camera_"):
                continue
            try:
                module = importlib.import_module(f"camera_types.{module_info.name}")
            except Exception as exc:
                logging.error(f"Skipping camera module '{module_info.name}': {exc}")
                continue
            camera_id = getattr(module, "CAMERA_ID", module_info.name)
            camera_modules[camera_id] = module
            aliases = getattr(module, "CAMERA_ID_ALIASES", [])
            if isinstance(aliases, (list, tuple, set)):
                for alias in aliases:
                    if isinstance(alias, str) and alias.strip():
                        camera_modules[alias.strip()] = module
    except ImportError:
        logging.error("Could not load camera_types package")
    return camera_modules


def resolve_camera_module(camera_id: str, camera_modules: dict):
    """Return the module for a given camera_id, or None if not found."""
    if not camera_id:
        return None
    return camera_modules.get(camera_id)
