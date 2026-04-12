from typing import Optional


class CameraSession:
    """Holds all runtime state for a single camera connection.

    Lives as a singleton in app.state.camera. No UI references.
    """

    def __init__(self):
        self.ip: str = ""
        self.port: str = "80"
        self.connected: bool = False
        self.camera_id: Optional[str] = None

        self.connect_in_progress: bool = False
        self.reset_in_progress: bool = False
        self.balance_in_progress: bool = False
        self.scan_in_progress: bool = False

        # Incremented on each successful connect; used to detect stale workers.
        self.session_id: int = 0

        # Incremented on disconnect/new balance start; used to cancel in-flight polls.
        self.balance_token: int = 0

        self.feature_states: dict[str, bool] = {
            "auto_focus": False,
            "auto_iris": False,
            "drs": False,
            "flare": False,
            "gamma": True,
            "knee": False,
            "matrix": False,
            "linear_matrix": False,
            "white_clip": False,
        }

        # Command maps populated after connect via _configure_advanced_controls.
        # Keys are dropdown labels, values are CGI command strings.
        self.c_temp_command_map: dict[str, str] = {}
        self.gamma_command_map: dict[str, str] = {}
        self.lmatrix_command_map: dict[str, str] = {}

        # Current dropdown selections (label strings).
        self.c_temp_selection: str = ""
        self.gamma_selection: str = ""
        self.lmatrix_selection: str = ""

        # Generic dropdown selections for plugin modules (key → selected label).
        self.dropdown_selections: dict[str, str] = {}

        # Cameras found during last UDP scan.
        self.discovered_cameras: list[dict] = []

    def reset_connection(self):
        """Clear all connection-specific state. Called on disconnect or failure."""
        self.connected = False
        self.camera_id = None
        self.connect_in_progress = False
        self.reset_in_progress = False
        self.balance_in_progress = False
        self.session_id = 0
        self.balance_token += 1
        self.c_temp_command_map = {}
        self.gamma_command_map = {}
        self.lmatrix_command_map = {}
        self.c_temp_selection = ""
        self.gamma_selection = ""
        self.lmatrix_selection = ""
        self.dropdown_selections = {}
