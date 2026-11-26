import pytest

from src.guardrails import (
    GuardrailError,
    check_recommendations,
    confidence_label,
    safe_recommend,
    validate_profile,
)
from src.main import main
from src.recommender import load_songs, recommend_songs

POP_USER = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}
PEACEFUL_METAL = {"genre": "metal", "mood": "peaceful", "energy": 0.1, "likes_acoustic": True}
CSV_HEADER = "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness"


@pytest.fixture
def songs():
    return load_songs("data/songs.csv")


# --- Normal cases ---

def test_safe_recommend_matches_original_scoring(songs):
    for profile in [POP_USER, PEACEFUL_METAL, {"genre": "lofi", "mood": "relaxed", "energy": 0.2, "likes_acoustic": True}]:
        assert safe_recommend(profile, songs).recommendations == recommend_songs(profile, songs, k=5)


def test_strong_match_gets_high_confidence_and_no_warnings(songs):
    result = safe_recommend(POP_USER, songs)
    assert result.recommendations[0][0]["title"] == "Sunrise City"
    assert result.confidence == "High"
    assert result.warnings == []
    assert result.output_problems == []


def test_confidence_thresholds():
    assert confidence_label(4.0)[0] == "High"
    assert confidence_label(3.0)[0] == "Medium"
    assert confidence_label(2.0)[0] == "Low"


# --- Edge cases ---

def test_messy_input_is_cleaned(songs):
    messy = {"genre": "  Hip   Hop ", "mood": "CONFIDENT", "energy": "0.7", "likes_acoustic": "No"}
    profile, warnings = validate_profile(messy, songs)
    assert profile == {"genre": "hip hop", "mood": "confident", "energy": 0.7, "likes_acoustic": False}
    assert warnings == []


def test_unknown_genre_warns_with_suggestion(songs):
    _, warnings = validate_profile(dict(POP_USER, genre="hiphop"), songs)
    assert any("Did you mean 'hip hop'" in warning for warning in warnings)


def test_conflicting_preferences_are_flagged(songs):
    result = safe_recommend(PEACEFUL_METAL, songs)
    assert sum("Conflicting preferences" in w for w in result.warnings) == 2
    assert result.confidence == "Low"


def test_missing_genre_mood_combination_is_flagged(songs):
    _, warnings = validate_profile({"genre": "rock", "mood": "angry", "energy": 0.95, "likes_acoustic": False}, songs)
    assert any("both 'rock' and 'angry'" in warning for warning in warnings)


def test_k_larger_than_catalog_is_capped(songs):
    result = safe_recommend(POP_USER, songs, k=100)
    assert len(result.recommendations) == len(songs)
    assert any("only has 18 songs" in warning for warning in result.warnings)


# --- Invalid inputs ---

@pytest.mark.parametrize("changes, message", [
    ({"energy": 1.5}, "between 0.0 and 1.0"),
    ({"energy": -0.1}, "between 0.0 and 1.0"),
    ({"energy": "loud"}, "must be a number"),
    ({"energy": float("nan")}, "between 0.0 and 1.0"),
    ({"likes_acoustic": "maybe"}, "yes or no"),
    ({"genre": ""}, "non-empty"),
    ({"mood": None}, "non-empty"),
])
def test_invalid_profile_values_are_rejected(songs, changes, message):
    with pytest.raises(GuardrailError, match=message):
        safe_recommend(dict(POP_USER, **changes), songs)


def test_missing_field_is_rejected(songs):
    with pytest.raises(GuardrailError, match="missing: mood"):
        safe_recommend({"genre": "pop", "energy": 0.8, "likes_acoustic": False}, songs)


@pytest.mark.parametrize("k", [0, -3, "five"])
def test_invalid_k_is_rejected(songs, k):
    with pytest.raises(GuardrailError):
        safe_recommend(POP_USER, songs, k=k)


def test_empty_catalog_is_rejected():
    with pytest.raises(GuardrailError, match="empty"):
        safe_recommend(POP_USER, [])


# --- Data loading ---

def test_missing_csv_raises_clear_error():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_songs("data/does_not_exist.csv")


def test_bad_csv_rows_are_skipped(tmp_path):
    path = tmp_path / "songs.csv"
    path.write_text(
        CSV_HEADER + "\n"
        "1,Good Song,A,Pop ,Happy,0.8,120,0.8,0.8,0.2\n"
        "2,Bad Energy,B,pop,happy,loud,120,0.8,0.8,0.2\n"
        "3,Out Of Range,C,pop,happy,1.9,120,0.8,0.8,0.2\n",
        encoding="utf-8",
    )
    songs = load_songs(str(path))
    assert [song["title"] for song in songs] == ["Good Song"]
    assert songs[0]["genre"] == "pop" and songs[0]["mood"] == "happy"


def test_csv_missing_columns_raises_clear_error(tmp_path):
    path = tmp_path / "songs.csv"
    path.write_text("id,title\n1,Only Title\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_songs(str(path))


# --- Output checks ---

def test_output_check_passes_real_results(songs):
    assert check_recommendations(recommend_songs(POP_USER, songs, k=5), 5) == []


def test_output_check_catches_bad_results(songs):
    bad = [(songs[0], 1.0, "ok"), (songs[1], 9.0, ""), (songs[0], 2.0, "ok")]
    problems = check_recommendations(bad, expected_count=4)
    assert len(problems) == 5  # count, range, order, duplicate, missing explanation


# --- Command line ---

def test_cli_valid_input_succeeds(capsys):
    assert main(["--genre", "pop", "--mood", "happy", "--energy", "0.8", "--k", "2"]) == 0
    output = capsys.readouterr().out
    assert "1. Sunrise City" in output and "Confidence: High" in output


@pytest.mark.parametrize("args, message", [
    (["--genre", "pop", "--mood", "happy", "--energy", "1.7"], "Input error"),
    (["--genre", "pop", "--energy", "0.8"], "Please provide --mood"),
    (["--genre", "pop", "--mood", "happy", "--energy", "0.8", "--data", "nope.csv"], "Data error"),
])
def test_cli_invalid_input_fails_gracefully(capsys, args, message):
    assert main(args) == 1
    assert message in capsys.readouterr().out
