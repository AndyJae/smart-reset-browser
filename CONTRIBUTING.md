# Contributing to smart-reset-browser

## What contributions are welcome

- **New camera models** — the most valuable contribution
- Bug fixes for existing reset sequences
- Improved network discovery
- Documentation corrections

---

## Adding a camera model

### Panasonic

1. Copy `camera_plugins/panasonic/aw_ue80.py` as a starting point
2. Set `CAMERA_ID`, `DISPLAY_NAME`, and `PROTOCOL = "panasonic"`
3. Define `RESET_SEQUENCE` — ordered list of CGI commands
4. Define `UI_BUTTONS`, `UI_DROPDOWNS`, `UI_LAYOUT` for the controls panel
5. Add `CAMERA_ID_ALIASES` if the camera responds with multiple model strings
6. Test against real hardware — no emulator exists

### BirdDog

1. Copy `camera_plugins/birddog/p200.py` as a starting point
2. Same structure — REST/JSON instead of CGI; API port is 8080
3. Verify against the BirdDog REST API documentation for your model

---

## What you need to test

- Connect, Reset, and all feature toggles must work on real hardware
- Pull requests without hardware testing are accepted as **"untested"**
  and merged with a warning comment in the module header

---

## Pull request checklist

- [ ] One camera model per PR
- [ ] `DISPLAY_NAME` matches the official product name exactly
- [ ] No changes outside `camera_plugins/` unless discussed first in an issue
- [ ] Tested on real hardware — state this in the PR description

---

## Questions

Open an issue or contact [support@medien-support.com](mailto:support@medien-support.com).
