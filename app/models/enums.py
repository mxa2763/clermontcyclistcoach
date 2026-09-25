import enum


class Provider(str, enum.Enum):
    strava = "strava"
    intervals_icu = "intervals_icu"
    trainingpeaks = "trainingpeaks"  # schema only in Phase 1; no OAuth implemented
