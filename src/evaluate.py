"""
Reliability evaluation for the Music Recommender.

Runs a fixed set of cases through the same guarded pipeline the app uses
(load_songs + safe_recommend), prints a pass/fail table with a pass rate,
and saves the report to assets/evaluation_results.txt.

Run with:
    python -m src.evaluate
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from src.guardrails import GuardrailError, check_recommendations, safe_recommend
from src.main import EVALUATION_PROFILES, setup_logging
from src.recommender import PROJECT_ROOT, load_songs, recommend_songs

DATA = "data/songs.csv"
RESULTS_FILE = PROJECT_ROOT / "assets" / "evaluation_results.txt"
POP = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}


def titles(result) -> list:
    """Return the song titles of a RecommendationResult, best first."""
    return [song["title"] for song, _, _ in result.recommendations]


def expect_error(action, error_type, must_contain: str):
    """Pass if action() raises error_type with a message containing must_contain."""
    try:
        action()
    except error_type as error:
        return must_contain in str(error), f"rejected: {error}"
    return False, "no error was raised"


# --- Normal cases ---------------------------------------------------------

def case_default_pop(songs):
    result = safe_recommend(POP, songs)
    passed = titles(result)[0] == "Sunrise City" and result.confidence == "High" and not result.warnings
    return passed, f"#1 {titles(result)[0]}, confidence {result.confidence}, {len(result.warnings)} warnings"


def case_deep_rock(songs):
    result = safe_recommend(EVALUATION_PROFILES["Deep Intense Rock"], songs)
    passed = titles(result)[0] == "Storm Runner" and result.confidence == "Medium"
    return passed, f"#1 {titles(result)[0]}, confidence {result.confidence}"


def case_chill_lofi(songs):
    result = safe_recommend(EVALUATION_PROFILES["Chill Lofi"], songs)
    top3_lofi = all(song["genre"] == "lofi" for song, _, _ in result.recommendations[:3])
    gap_warned = any("both 'lofi' and 'relaxed'" in w for w in result.warnings)
    return top3_lofi and gap_warned, f"top 3 all lofi: {top3_lofi}, genre/mood gap warned: {gap_warned}"


def case_scoring_unchanged(songs):
    for profile in list(EVALUATION_PROFILES.values()) + [POP]:
        guarded = safe_recommend(profile, songs).recommendations
        if guarded != recommend_songs(profile, songs, k=5):
            return False, f"guarded ranking differs for {profile}"
    return True, "5 profiles: guarded results identical to original recommend_songs()"


def case_reproducible(songs):
    runs = [titles(safe_recommend(POP, songs)) for _ in range(3)]
    return runs[0] == runs[1] == runs[2], "3 runs gave the same ranking" if runs[0] == runs[2] else "rankings differed"


# --- Edge cases -------------------------------------------------------------

def case_messy_input(songs):
    messy = {"genre": "  Hip Hop ", "mood": "CONFIDENT", "energy": "0.7", "likes_acoustic": "no"}
    result = safe_recommend(messy, songs)
    passed = result.profile["genre"] == "hip hop" and titles(result)[0] == "Concrete Verses"
    return passed, f"cleaned to genre='{result.profile['genre']}', #1 {titles(result)[0]}"


def case_unknown_genre(songs):
    result = safe_recommend(dict(POP, genre="hiphop", mood="confident"), songs)
    suggested = any("Did you mean 'hip hop'" in w for w in result.warnings)
    return suggested and len(result.recommendations) == 5, f"suggestion given: {suggested}, still {len(result.recommendations)} results"


def case_conflicting(songs):
    result = safe_recommend(EVALUATION_PROFILES["Conflicting (Peaceful Metal)"], songs)
    conflicts = sum("Conflicting preferences" in w for w in result.warnings)
    return conflicts == 2 and result.confidence == "Low", f"{conflicts} conflict warnings, confidence {result.confidence}"


def case_k_too_large(songs):
    result = safe_recommend(POP, songs, k=50)
    return len(result.recommendations) == len(songs) and bool(result.warnings), f"k=50 capped to {len(result.recommendations)} with warning"


# --- Invalid inputs ---------------------------------------------------------

def case_energy_too_high(songs):
    return expect_error(lambda: safe_recommend(dict(POP, energy=1.5), songs), GuardrailError, "between 0.0 and 1.0")


def case_energy_not_number(songs):
    return expect_error(lambda: safe_recommend(dict(POP, energy="loud"), songs), GuardrailError, "must be a number")


def case_bad_acoustic(songs):
    return expect_error(lambda: safe_recommend(dict(POP, likes_acoustic="maybe"), songs), GuardrailError, "yes or no")


def case_k_zero(songs):
    return expect_error(lambda: safe_recommend(POP, songs, k=0), GuardrailError, "at least 1")


def case_missing_field(songs):
    profile = {"genre": "pop", "energy": 0.8, "likes_acoustic": False}
    return expect_error(lambda: safe_recommend(profile, songs), GuardrailError, "missing: mood")


def case_empty_genre(songs):
    return expect_error(lambda: safe_recommend(dict(POP, genre="   "), songs), GuardrailError, "non-empty")


# --- Data and output checks -------------------------------------------------

def case_missing_file(songs):
    return expect_error(lambda: load_songs("data/does_not_exist.csv"), FileNotFoundError, "not found")


def case_bad_rows_skipped(songs):
    rows = [
        "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness",
        "1,Good Song,A,pop,happy,0.8,120,0.8,0.8,0.2",
        "2,Bad Energy,B,pop,happy,loud,120,0.8,0.8,0.2",
        "3,Out Of Range,C,pop,happy,1.9,120,0.8,0.8,0.2",
        "4,No Genre,D,,happy,0.5,120,0.8,0.8,0.2",
    ]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "messy.csv"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        loaded = load_songs(str(path))
    return [s["title"] for s in loaded] == ["Good Song"], f"loaded {len(loaded)} of 4 rows (3 bad rows skipped)"


def case_output_check_catches_bad_results(songs):
    song_a, song_b = songs[0], songs[1]
    bad = [(song_a, 1.0, "ok"), (song_b, 9.0, ""), (song_a, 2.0, "ok")]
    problems = check_recommendations(bad, expected_count=3)
    return len(problems) == 4, f"detected {len(problems)} problems (range, order, duplicate, missing explanation)"


CASES = [
    ("Normal", "Default pop profile ranks Sunrise City #1", case_default_pop),
    ("Normal", "Deep Intense Rock ranks Storm Runner #1", case_deep_rock),
    ("Normal", "Chill Lofi: top 3 lofi + genre/mood gap warning", case_chill_lofi),
    ("Normal", "Guardrails do not change original scoring", case_scoring_unchanged),
    ("Normal", "Same input gives same output (reproducible)", case_reproducible),
    ("Edge", "Messy input ('  Hip Hop ', 'CONFIDENT') cleaned", case_messy_input),
    ("Edge", "Unknown genre 'hiphop' warns + suggests", case_unknown_genre),
    ("Edge", "Conflicting prefs (Peaceful Metal) flagged", case_conflicting),
    ("Edge", "k larger than catalog is capped", case_k_too_large),
    ("Invalid", "Energy 1.5 is rejected", case_energy_too_high),
    ("Invalid", "Energy 'loud' is rejected", case_energy_not_number),
    ("Invalid", "Acoustic 'maybe' is rejected", case_bad_acoustic),
    ("Invalid", "k = 0 is rejected", case_k_zero),
    ("Invalid", "Missing 'mood' field is rejected", case_missing_field),
    ("Invalid", "Blank genre is rejected", case_empty_genre),
    ("Data", "Missing CSV file gives a clear error", case_missing_file),
    ("Data", "Malformed CSV rows are skipped, not fatal", case_bad_rows_skipped),
    ("Output", "Output check catches bad results", case_output_check_catches_bad_results),
]


def run_evaluation() -> list:
    """Run every case and return a list of report lines."""
    songs = load_songs(DATA)
    lines = [
        "Music Recommender - Reliability Evaluation",
        f"Run at: {datetime.now():%Y-%m-%d %H:%M:%S}  |  Catalog: {DATA} ({len(songs)} songs)",
        "",
        f"{'#':<3}{'Result':<7}{'Type':<9}{'Case':<50}Details",
        "-" * 120,
    ]
    passed_count = 0
    for number, (category, name, case) in enumerate(CASES, start=1):
        try:
            passed, detail = case(songs)
        except Exception as error:  # A crash counts as a failure, not the end of the run.
            passed, detail = False, f"crashed: {type(error).__name__}: {error}"
        passed_count += passed
        lines.append(f"{number:<3}{'PASS' if passed else 'FAIL':<7}{category:<9}{name:<50}{detail}")

    rate = 100 * passed_count / len(CASES)
    lines += ["-" * 120, f"Pass rate: {passed_count}/{len(CASES)} cases passed ({rate:.0f}%)"]
    return lines


def main() -> None:
    setup_logging(console_level=logging.CRITICAL)  # expected errors go to the log file only
    lines = run_evaluation()
    report = "\n".join(lines)
    print(report)
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    RESULTS_FILE.write_text(report + "\n", encoding="utf-8")
    print(f"\nSaved to {RESULTS_FILE.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
