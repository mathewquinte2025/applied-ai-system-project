"""
Reliability and guardrail layer for the Music Recommender.

Every recommendation made by the app goes through safe_recommend(), which:
  1. checks and cleans the user's profile BEFORE scoring (input guardrails),
  2. calls the original rule-based recommend_songs() (scoring is unchanged),
  3. checks the results AFTER scoring (output guardrails),
  4. adds a confidence label and plain-language warnings.

Problems the user can fix (bad energy, unknown field, bad k) raise GuardrailError
with a clear message instead of crashing with a traceback.
"""

import logging
import math
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Dict, List, Tuple

from src.recommender import DEFAULT_WEIGHTS, recommend_songs

logger = logging.getLogger(__name__)

MAX_SCORE = 4.5
REQUIRED_FIELDS = ("genre", "mood", "energy", "likes_acoustic")
TRUE_WORDS = {"yes", "y", "true", "1"}
FALSE_WORDS = {"no", "n", "false", "0"}

# Confidence thresholds, based on the top song's score out of 4.5.
# High   (>= 3.5): the #1 song matches genre AND mood with close energy.
# Medium (>= 2.5): usually a genre match without a mood match.
# Low    (< 2.5): no song matched the favorite genre, so results are weaker guesses.
HIGH_CONFIDENCE = 3.5
MEDIUM_CONFIDENCE = 2.5

# Thresholds for spotting conflicting preferences.
ENERGY_CONFLICT_GAP = 0.5     # target energy this far from the genre's average energy
LOW_ACOUSTIC = 0.3            # genre's average acousticness below this = "not acoustic"
HIGH_ACOUSTIC = 0.7           # genre's average acousticness above this = "acoustic"


class GuardrailError(ValueError):
    """Raised when a profile or request cannot be used safely. The message is user-friendly."""


@dataclass
class RecommendationResult:
    """Everything the app shows the user for one request."""
    profile: Dict
    recommendations: List[Tuple[Dict, float, str]]
    confidence: str
    confidence_reason: str
    warnings: List[str] = field(default_factory=list)
    output_problems: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Input guardrails
# ---------------------------------------------------------------------------

def clean_label(value, field_name: str) -> str:
    """Trim spaces, collapse repeated spaces and lowercase a genre or mood label."""
    if not isinstance(value, str) or not value.strip():
        raise GuardrailError(f"'{field_name}' must be a non-empty word, for example 'pop'.")
    return " ".join(value.split()).lower()


def parse_energy(value) -> float:
    """Convert energy to a number between 0.0 and 1.0, or raise GuardrailError."""
    try:
        energy = float(value)
    except (TypeError, ValueError):
        raise GuardrailError(f"Energy must be a number between 0.0 and 1.0 (got '{value}').")
    if math.isnan(energy) or not 0.0 <= energy <= 1.0:
        raise GuardrailError(f"Energy must be between 0.0 and 1.0 (got {value}).")
    return energy


def parse_bool(value) -> bool:
    """Accept True/False or words like yes/no/true/false/y/n/1/0."""
    if isinstance(value, bool):
        return value
    word = str(value).strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise GuardrailError(f"Acoustic preference must be yes or no (got '{value}').")


def parse_k(value, catalog_size: int) -> Tuple[int, List[str]]:
    """Check the number of recommendations. Too many is capped with a warning."""
    try:
        k = int(str(value).strip())
    except (TypeError, ValueError):
        raise GuardrailError(f"Number of recommendations must be a whole number (got '{value}').")
    if k < 1:
        raise GuardrailError(f"Number of recommendations must be at least 1 (got {k}).")
    if k > catalog_size:
        return catalog_size, [
            f"You asked for {k} recommendations but the catalog only has "
            f"{catalog_size} songs, so showing all {catalog_size}."
        ]
    return k, []


def unknown_label_warning(label: str, known: List[str], field_name: str) -> str:
    """Build a warning for a genre or mood that is not in the catalog, with a suggestion."""
    message = f"The {field_name} '{label}' is not in the catalog, so no song can earn {field_name} points."
    suggestion = get_close_matches(label, known, n=1, cutoff=0.6)
    if suggestion:
        message += f" Did you mean '{suggestion[0]}'?"
    return message


def validate_profile(user_prefs: Dict, songs: List[Dict]) -> Tuple[Dict, List[str]]:
    """Return a cleaned copy of the profile plus a list of warnings.

    Raises GuardrailError if a required field is missing or has an invalid value.
    """
    if not isinstance(user_prefs, dict):
        raise GuardrailError("The user profile must be a dictionary.")
    missing = [name for name in REQUIRED_FIELDS if name not in user_prefs]
    if missing:
        raise GuardrailError(f"The user profile is missing: {', '.join(missing)}.")

    profile = {
        "genre": clean_label(user_prefs["genre"], "genre"),
        "mood": clean_label(user_prefs["mood"], "mood"),
        "energy": parse_energy(user_prefs["energy"]),
        "likes_acoustic": parse_bool(user_prefs["likes_acoustic"]),
    }

    warnings = []
    known_genres = sorted({song["genre"] for song in songs})
    known_moods = sorted({song["mood"] for song in songs})
    if profile["genre"] not in known_genres:
        warnings.append(unknown_label_warning(profile["genre"], known_genres, "genre"))
    if profile["mood"] not in known_moods:
        warnings.append(unknown_label_warning(profile["mood"], known_moods, "mood"))
    warnings.extend(find_conflicts(profile, songs))
    return profile, warnings


def find_conflicts(profile: Dict, songs: List[Dict]) -> List[str]:
    """Warn when the requested genre does not fit the other preferences in this catalog."""
    genre_songs = [song for song in songs if song["genre"] == profile["genre"]]
    if not genre_songs:
        return []  # Unknown genre is already reported.

    warnings = []
    genre, mood = profile["genre"], profile["mood"]
    if not any(song["mood"] == mood for song in genre_songs):
        if any(song["mood"] == mood for song in songs):
            warnings.append(
                f"No song in the catalog is both '{genre}' and '{mood}', so the top "
                f"results can match your genre or your mood, but not both."
            )

    avg_energy = sum(song["energy"] for song in genre_songs) / len(genre_songs)
    if abs(avg_energy - profile["energy"]) >= ENERGY_CONFLICT_GAP:
        warnings.append(
            f"Conflicting preferences: '{genre}' songs here average energy {avg_energy:.2f}, "
            f"but your target is {profile['energy']:.2f}. Expect a mix of {genre} songs "
            f"and songs from other genres that match your energy."
        )

    avg_acoustic = sum(song["acousticness"] for song in genre_songs) / len(genre_songs)
    if profile["likes_acoustic"] and avg_acoustic < LOW_ACOUSTIC:
        warnings.append(
            f"Conflicting preferences: you prefer acoustic music, but '{genre}' songs here "
            f"are not acoustic (average acousticness {avg_acoustic:.2f})."
        )
    elif not profile["likes_acoustic"] and avg_acoustic > HIGH_ACOUSTIC:
        warnings.append(
            f"Conflicting preferences: you prefer non-acoustic music, but '{genre}' songs "
            f"here are mostly acoustic (average acousticness {avg_acoustic:.2f})."
        )
    return warnings


# ---------------------------------------------------------------------------
# Output guardrails
# ---------------------------------------------------------------------------

def check_recommendations(recommendations: List[Tuple[Dict, float, str]], expected_count: int) -> List[str]:
    """Return a list of problems with the results (an empty list means everything passed)."""
    problems = []
    if len(recommendations) != expected_count:
        problems.append(f"Expected {expected_count} results but got {len(recommendations)}.")

    scores = [score for _, score, _ in recommendations]
    if any(not 0.0 <= score <= MAX_SCORE for score in scores):
        problems.append(f"A score is outside the valid range 0 to {MAX_SCORE}.")
    if scores != sorted(scores, reverse=True):
        problems.append("Results are not sorted from highest to lowest score.")

    ids = [song["id"] for song, _, _ in recommendations]
    if len(ids) != len(set(ids)):
        problems.append("The same song appears more than once.")
    if any(not explanation for _, _, explanation in recommendations):
        problems.append("A recommendation is missing its explanation.")
    return problems


def confidence_label(top_score: float) -> Tuple[str, str]:
    """Turn the #1 song's score into a High / Medium / Low label with a short reason."""
    if top_score >= HIGH_CONFIDENCE:
        return "High", f"top song scored {top_score:.2f}/{MAX_SCORE}: strong match on genre, mood and energy"
    if top_score >= MEDIUM_CONFIDENCE:
        return "Medium", f"top song scored {top_score:.2f}/{MAX_SCORE}: partial match (usually genre but not mood)"
    return "Low", f"top song scored {top_score:.2f}/{MAX_SCORE}: no song closely matches this profile"


# ---------------------------------------------------------------------------
# The guarded recommendation pipeline used by the app
# ---------------------------------------------------------------------------

def safe_recommend(user_prefs: Dict, songs: List[Dict], k=5, weights: Dict = DEFAULT_WEIGHTS) -> RecommendationResult:
    """Validate the input, run the original recommender, then check the output."""
    if not songs:
        raise GuardrailError("The song catalog is empty, so there is nothing to recommend.")

    profile, warnings = validate_profile(user_prefs, songs)
    k, k_warnings = parse_k(k, len(songs))
    warnings.extend(k_warnings)

    recommendations = recommend_songs(profile, songs, k, weights)

    problems = check_recommendations(recommendations, k)
    if problems:
        logger.error("Output check failed: %s", "; ".join(problems))
        warnings.append("Output check failed, so these results may be unreliable.")
        confidence, reason = "Low", "the output check found problems"
    else:
        confidence, reason = confidence_label(recommendations[0][1])

    logger.info(
        "Recommended %d songs for %s | confidence=%s | top=%s | warnings=%d",
        len(recommendations), profile, confidence, recommendations[0][0]["title"], len(warnings),
    )
    for warning in warnings:
        logger.info("Guardrail warning: %s", warning)

    return RecommendationResult(profile, recommendations, confidence, reason, warnings, problems)
