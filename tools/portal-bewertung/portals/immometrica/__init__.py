"""Immometrica-Adapter: Marktstatistik fuer PLZ und Stadt (ETW + MFH).

Nutzt nodriver (Anti-Detection-Chrome via CDP) wegen reCAPTCHA-Schutz.
Login-State persistiert unter learned_selectors/immometrica_nodriver_userdata/.
"""

from portals.immometrica.portal import ImmometricaPortal, run_immometrica  # noqa

__all__ = ["ImmometricaPortal", "run_immometrica"]
