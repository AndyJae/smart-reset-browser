"""
core/registry.py — Plugin-Registry für Kameramodule und Transport-Implementierungen.

Zwei getrennte Registries in einer Klasse:
  - Modulregistry:    CAMERA_ID → Kameramodul (inkl. CAMERA_ID_ALIASES)
  - Transportregistry: protocol-string → CameraProtocol-Instanz

Ersetzt langfristig camera_loader.py. Wird einmalig beim Startup befüllt
und als Singleton in app.state.registry abgelegt.

Verwendung:

    # Startup (app.py):
    registry = PluginRegistry()
    registry.load_package("camera_types", module_prefix="camera_")
    registry.register_transport("panasonic", PanasonicTransport())
    app.state.registry = registry

    # In Routen / Workern:
    module = registry.resolve_module("AW-UE160")       # → camera_aw_ue160
    transport = registry.resolve_transport("panasonic") # → PanasonicTransport
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.interfaces import CameraProtocol


logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Zentrale Registry für alle Kamera-Plugins und Transporte.

    Thread-Safety: Die Registry wird einmalig beim Startup befüllt und danach
    nur noch gelesen — keine Locks nötig.
    """

    def __init__(self) -> None:
        # camera_id (inkl. Aliases) → Modul
        self._modules: dict[str, ModuleType] = {}
        # protocol-string ("panasonic", "birddog") → Transport-Instanz
        self._transports: dict[str, "CameraProtocol"] = {}

    # -----------------------------------------------------------------------
    # Modulregistry
    # -----------------------------------------------------------------------

    def register_module(self, module: ModuleType) -> None:
        """
        Registriert ein Kameramodul anhand seiner CAMERA_ID und optionaler CAMERA_ID_ALIASES.

        Das Modul muss mindestens CAMERA_ID (str) definieren.
        Fehlt CAMERA_ID, wird das Modul übersprungen und ein Fehler geloggt.

        Bei Kollision (zwei Module mit gleicher ID) überschreibt das neue Modul
        das alte und ein Warning wird geloggt.
        """
        camera_id: str = getattr(module, "CAMERA_ID", "")
        if not camera_id or not isinstance(camera_id, str):
            logger.error(
                f"Module '{module.__name__}' has no valid CAMERA_ID — skipping."
            )
            return

        if camera_id in self._modules:
            pass  # plugins intentionally overwrite legacy camera_types/ entries

        self._modules[camera_id] = module
        logger.debug(f"Registered module: {camera_id} → {module.__name__}")

        aliases = getattr(module, "CAMERA_ID_ALIASES", [])
        if not isinstance(aliases, (list, tuple, set)):
            return
        for alias in aliases:
            if not isinstance(alias, str) or not alias.strip():
                continue
            alias = alias.strip()
            if alias in self._modules and self._modules[alias].__name__ != module.__name__:
                logger.warning(
                    f"Alias '{alias}' already registered by "
                    f"'{self._modules[alias].__name__}'. Overwriting."
                )
            self._modules[alias] = module
            logger.debug(f"Registered alias:  {alias} → {module.__name__}")

    def resolve_module(self, camera_id: str) -> ModuleType | None:
        """
        Gibt das Modul für eine erkannte Kamera-ID zurück, oder None.

        Suche ist exakt — Normalisierung (Groß-/Kleinschreibung) obliegt dem Aufrufer.
        """
        if not camera_id:
            return None
        return self._modules.get(camera_id)

    def all_modules(self) -> dict[str, ModuleType]:
        """Gibt eine Kopie der kompletten Modulregistry zurück (ID → Modul)."""
        return dict(self._modules)

    def registered_camera_ids(self) -> list[str]:
        """Alle registrierten CAMERA_IDs (ohne Aliases), sortiert."""
        ids = {
            getattr(m, "CAMERA_ID", "")
            for m in self._modules.values()
            if getattr(m, "CAMERA_ID", "")
        }
        return sorted(ids)

    # -----------------------------------------------------------------------
    # Transportregistry
    # -----------------------------------------------------------------------

    def register_transport(self, protocol: str, transport: "CameraProtocol") -> None:
        """
        Registriert eine CameraProtocol-Instanz für einen Protokoll-String.

        protocol muss dem PROTOCOL-Feld der zugehörigen Kameramodule entsprechen,
        z. B. "panasonic" oder "birddog".
        """
        if not protocol or not isinstance(protocol, str):
            logger.error("register_transport: protocol must be a non-empty string.")
            return
        if protocol in self._transports:
            logger.warning(
                f"Transport '{protocol}' already registered. Overwriting."
            )
        self._transports[protocol] = transport
        logger.debug(f"Registered transport: {protocol} → {type(transport).__name__}")

    def resolve_transport(self, protocol: str) -> "CameraProtocol | None":
        """
        Gibt die Transport-Instanz für einen Protokoll-String zurück, oder None.

        Fallback auf "panasonic" wenn protocol leer oder None ist — bestehende
        Kameramodule ohne PROTOCOL-Feld bleiben so kompatibel.
        """
        if not protocol:
            protocol = "panasonic"
        return self._transports.get(protocol)

    def resolve_transport_for_module(self, module: ModuleType) -> "CameraProtocol | None":
        """
        Löst den Transport für ein Kameramodul anhand seines PROTOCOL-Feldes auf.

        Fehlender PROTOCOL-Wert wird als "panasonic" interpretiert (Rückwärtskompatibilität).
        """
        protocol: str = getattr(module, "PROTOCOL", "panasonic") or "panasonic"
        transport = self.resolve_transport(protocol)
        if transport is None:
            logger.warning(
                f"No transport registered for protocol '{protocol}' "
                f"(module: {getattr(module, 'CAMERA_ID', module.__name__)})."
            )
        return transport

    def all_transports(self) -> dict[str, "CameraProtocol"]:
        """Gibt eine Kopie der Transportregistry zurück."""
        return dict(self._transports)

    # -----------------------------------------------------------------------
    # Bulk-Loader (ersetzt camera_loader.py)
    # -----------------------------------------------------------------------

    def load_package(
        self,
        package_name: str,
        module_prefix: str = "camera_",
        frozen_names: list[str] | None = None,
    ) -> int:
        """
        Lädt alle Kameramodule aus einem Python-Package und registriert sie.

        Unterstützt zwei Modi:
          - Development:   pkgutil.iter_modules() — erkennt Module dynamisch
          - PyInstaller:   frozen_names — explizite Namensliste (sys.frozen=True)

        Parameter:
            package_name    Name des Packages, z. B. "camera_types" oder
                            "camera_plugins.panasonic"
            module_prefix   Nur Module mit diesem Präfix werden geladen,
                            z. B. "camera_" oder "aw_"
            frozen_names    Explizite Modulliste für PyInstaller-Bundle,
                            z. B. ["camera_aw_ue160", "camera_aw_ue150"]
                            Wenn None und sys.frozen, wird ein Warning geloggt.

        Rückgabe: Anzahl erfolgreich registrierter Module (ohne Aliases).
        """
        try:
            package = importlib.import_module(package_name)
        except ImportError as exc:
            logger.error(f"Cannot import package '{package_name}': {exc}")
            return 0

        # Modulnamen bestimmen
        if getattr(sys, "frozen", False):
            if frozen_names is None:
                logger.warning(
                    f"Running frozen but no frozen_names provided for '{package_name}'. "
                    "Camera modules may not be loaded correctly."
                )
                names: list[str] = []
            else:
                names = [n for n in frozen_names if n.startswith(module_prefix)]
        else:
            names = [
                info.name
                for info in pkgutil.iter_modules(package.__path__)
                if info.name.startswith(module_prefix)
            ]

        loaded = 0
        before = len(self.registered_camera_ids())

        for name in names:
            full_name = f"{package_name}.{name}"
            try:
                module = importlib.import_module(full_name)
            except Exception as exc:
                logger.error(f"Failed to import '{full_name}': {exc}")
                continue
            self.register_module(module)
            loaded += 1

        after = len(self.registered_camera_ids())
        new_ids = after - before
        logger.info(
            f"Loaded {loaded} module file(s) from '{package_name}', "
            f"{new_ids} new CAMERA_ID(s) registered."
        )
        return loaded

    # -----------------------------------------------------------------------
    # Diagnostics
    # -----------------------------------------------------------------------

    def __repr__(self) -> str:
        ids = self.registered_camera_ids()
        protocols = sorted(self._transports.keys())
        return (
            f"<PluginRegistry "
            f"modules={ids} "
            f"transports={protocols}>"
        )
