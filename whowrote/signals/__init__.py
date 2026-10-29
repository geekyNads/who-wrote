from whowrote.signals import tier1_provenance, tier2_config, tier3_style, tier4_git
from whowrote.signals.base import Detector, RepoData, Signal

DETECTORS: list[Detector] = [
    *tier1_provenance.DETECTORS,
    *tier2_config.DETECTORS,
    *tier3_style.DETECTORS,
    *tier4_git.DETECTORS,
]


def collect(data: RepoData) -> list[Signal]:
    return [s for detect in DETECTORS for s in detect(data)]
