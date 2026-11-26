import csv
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

# Scoring weights (see "How The System Works" in README.md). Maximum score = 4.5.
GENRE_WEIGHT = 2.0
MOOD_WEIGHT = 1.0
ENERGY_WEIGHT = 1.0
ACOUSTIC_WEIGHT = 0.5

DEFAULT_WEIGHTS = {
    "genre": GENRE_WEIGHT,
    "mood": MOOD_WEIGHT,
    "energy": ENERGY_WEIGHT,
    "acoustic": ACOUSTIC_WEIGHT,
}
# Phase 4 experiment only: genre halved, energy doubled. Never used unless passed in.
EXPERIMENT_WEIGHTS = {"genre": 1.0, "mood": 1.0, "energy": 2.0, "acoustic": 0.5}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NUMERIC_FIELDS = {
    "id": int,
    "energy": float,
    "tempo_bpm": float,
    "valence": float,
    "danceability": float,
    "acousticness": float,
}
TEXT_FIELDS = ("title", "artist", "genre", "mood")
REQUIRED_COLUMNS = set(NUMERIC_FIELDS) | set(TEXT_FIELDS)

logger = logging.getLogger(__name__)


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool


def profile_to_prefs(user: UserProfile) -> Dict:
    """Convert a UserProfile into the user_prefs dictionary used by score_song()."""
    return {
        "genre": user.favorite_genre,
        "mood": user.favorite_mood,
        "energy": user.target_energy,
        "likes_acoustic": user.likes_acoustic,
    }


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k Song objects for this user, using recommend_songs()."""
        songs_by_id = {song.id: song for song in self.songs}
        song_dicts = [asdict(song) for song in self.songs]
        results = recommend_songs(profile_to_prefs(user), song_dicts, k)
        return [songs_by_id[song_dict["id"]] for song_dict, _, _ in results]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a readable explanation of how this song was scored for this user."""
        score, reasons = score_song(profile_to_prefs(user), asdict(song))
        return f"Score {score:.3f}/4.5: " + "; ".join(reasons)


def clean_song_row(row: Dict) -> Dict:
    """Convert one CSV row into a song dictionary, or raise ValueError if it is unusable."""
    for field in TEXT_FIELDS:
        if not (row.get(field) or "").strip():
            raise ValueError(f"missing {field}")
    for field, convert in NUMERIC_FIELDS.items():
        row[field] = convert(row[field])
    for field in ("energy", "acousticness"):
        if not 0.0 <= row[field] <= 1.0:
            raise ValueError(f"{field} {row[field]} is outside 0.0-1.0")
    # Labels are compared exactly, so store them trimmed and lowercase.
    row["genre"] = " ".join(row["genre"].split()).lower()
    row["mood"] = " ".join(row["mood"].split()).lower()
    return row


def load_songs(csv_path: str) -> List[Dict]:
    """Load songs from a CSV file into dictionaries with numeric fields converted.

    Raises FileNotFoundError with a clear message if the file is missing, and
    ValueError if required columns are missing. Bad rows are skipped and logged.
    """
    path = Path(csv_path)
    if not path.exists():
        # Fall back to the project root so the program also works from other folders.
        path = PROJECT_ROOT / csv_path
    if not path.exists():
        logger.error("Song file not found: %s", csv_path)
        raise FileNotFoundError(f"Song file not found: '{csv_path}'. Check the path and try again.")

    songs = []
    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            logger.error("Song file %s is missing columns: %s", csv_path, sorted(missing_columns))
            raise ValueError(f"Song file '{csv_path}' is missing columns: {', '.join(sorted(missing_columns))}.")

        for line_number, row in enumerate(reader, start=2):  # line 1 is the header
            try:
                songs.append(clean_song_row(row))
            except (KeyError, TypeError, ValueError) as error:
                logger.warning("Skipping line %d of %s: %s", line_number, csv_path, error)

    logger.info("Loaded %d songs from %s", len(songs), csv_path)
    return songs


def energy_similarity(song_energy: float, target_energy: float) -> float:
    """Return 1.0 for an exact energy match, dropping toward 0.0 as energies differ."""
    return max(0.0, 1.0 - abs(song_energy - target_energy))


def score_song(user_prefs: Dict, song: Dict, weights: Dict = DEFAULT_WEIGHTS) -> Tuple[float, List[str]]:
    """Score one song against the user's preferences and explain each point."""
    reasons = []

    # 1. Genre: +2.0 for an exact match.
    if song["genre"] == user_prefs["genre"]:
        genre_points = weights["genre"]
        reasons.append(f"genre match ({song['genre']}): +{genre_points:.1f}")
    else:
        genre_points = 0.0
        reasons.append(f"genre mismatch ({song['genre']} vs. {user_prefs['genre']}): +0.0")

    # 2. Mood: +1.0 for an exact match.
    if song["mood"] == user_prefs["mood"]:
        mood_points = weights["mood"]
        reasons.append(f"mood match ({song['mood']}): +{mood_points:.1f}")
    else:
        mood_points = 0.0
        reasons.append(f"mood mismatch ({song['mood']} vs. {user_prefs['mood']}): +0.0")

    # 3. Energy: up to +1.0, rewarding closeness to the target (not just high energy).
    energy_points = weights["energy"] * energy_similarity(song["energy"], user_prefs["energy"])
    reasons.append(
        f"energy similarity ({song['energy']:.2f} vs. target {user_prefs['energy']:.2f}): "
        f"+{energy_points:.3f}"
    )

    # 4. Acoustic fit: up to +0.5, based on whether the user likes acoustic sounds.
    likes_acoustic = user_prefs.get("likes_acoustic", False)
    acoustic_fit = song["acousticness"] if likes_acoustic else 1.0 - song["acousticness"]
    acoustic_points = weights["acoustic"] * acoustic_fit
    preference = "prefers acoustic" if likes_acoustic else "prefers non-acoustic"
    reasons.append(
        f"acoustic fit (acousticness {song['acousticness']:.2f}, {preference}): "
        f"+{acoustic_points:.3f}"
    )

    # Round to remove tiny floating-point noise so equal scores compare as equal.
    total = round(genre_points + mood_points + energy_points + acoustic_points, 6)
    return total, reasons


def recommend_songs(
    user_prefs: Dict, songs: List[Dict], k: int = 5, weights: Dict = DEFAULT_WEIGHTS
) -> List[Tuple[Dict, float, str]]:
    """Score every song, rank them best-first, and return the top k as (song, score, explanation)."""
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song, weights)
        energy_points = energy_similarity(song["energy"], user_prefs["energy"])
        scored.append((song, score, energy_points, "; ".join(reasons)))

    # sorted() returns a new ranked list and leaves the caller's `songs` list untouched
    # (.sort() would reorder it in place). Sort key: score high->low, then energy
    # similarity high->low, then song id low->high, so ties always resolve the same way.
    ranked = sorted(scored, key=lambda item: (-item[1], -round(item[2], 6), item[0]["id"]))
    return [(song, score, explanation) for song, score, _, explanation in ranked[:k]]
