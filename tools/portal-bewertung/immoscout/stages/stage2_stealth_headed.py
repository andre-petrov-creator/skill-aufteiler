"""Stage 2: same as Stage 1 but headed — defeats outerHeight detection."""
from .stage1_stealth_headless import Stage1StealthHeadless


class Stage2StealthHeaded(Stage1StealthHeadless):
    name = "stage2_stealth_headed"
    headless = False
