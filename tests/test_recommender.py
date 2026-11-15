import pytest

from src.recommender import Song, UserProfile, Recommender, load_songs, recommend_songs, score_song

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


# --- Phase 3: functional API tests (load_songs, score_song, recommend_songs) ---

POP_USER = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}


def make_song(song_id, genre="pop", mood="happy", energy=0.8, acousticness=0.2):
    """Build a minimal song dictionary for scoring tests."""
    return {
        "id": song_id, "title": f"Song {song_id}", "artist": "Test Artist",
        "genre": genre, "mood": mood, "energy": energy, "tempo_bpm": 120.0,
        "valence": 0.5, "danceability": 0.5, "acousticness": acousticness,
    }


def test_load_songs_reads_all_18_songs_with_numeric_fields():
    songs = load_songs("data/songs.csv")
    assert len(songs) == 18
    assert len({song["id"] for song in songs}) == 18
    first = songs[0]
    assert first["title"] == "Sunrise City"
    assert isinstance(first["id"], int)
    for field in ["energy", "tempo_bpm", "valence", "danceability", "acousticness"]:
        assert isinstance(first[field], float)


def test_every_catalog_score_is_numeric_and_between_0_and_4_5():
    songs = load_songs("data/songs.csv")
    for prefs in [POP_USER, {"genre": "lofi", "mood": "chill", "energy": 0.4, "likes_acoustic": True}]:
        for song in songs:
            score, reasons = score_song(prefs, song)
            assert isinstance(score, float)
            assert 0.0 <= score <= 4.5
            assert len(reasons) == 4


def test_genre_match_adds_two_points():
    match, match_reasons = score_song(POP_USER, make_song(1, genre="pop"))
    miss, miss_reasons = score_song(POP_USER, make_song(2, genre="rock"))
    assert match - miss == pytest.approx(2.0)
    assert match_reasons[0].startswith("genre match")
    assert miss_reasons[0].startswith("genre mismatch")


def test_mood_match_adds_one_point():
    match, match_reasons = score_song(POP_USER, make_song(1, mood="happy"))
    miss, miss_reasons = score_song(POP_USER, make_song(2, mood="sad"))
    assert match - miss == pytest.approx(1.0)
    assert match_reasons[1].startswith("mood match")
    assert miss_reasons[1].startswith("mood mismatch")


def test_energy_rewards_closeness_not_loudness():
    exact, _ = score_song(POP_USER, make_song(1, energy=0.8))
    above, _ = score_song(POP_USER, make_song(2, energy=1.0))
    below, _ = score_song(POP_USER, make_song(3, energy=0.6))
    assert exact > above
    assert above == pytest.approx(below)  # 0.2 away in either direction scores the same
    assert exact - above == pytest.approx(0.2)


def test_acoustic_fit_depends_on_likes_acoustic():
    acoustic_song = make_song(1, acousticness=0.9)
    acoustic_fan = dict(POP_USER, likes_acoustic=True)
    with_pref, _ = score_song(acoustic_fan, acoustic_song)
    without_pref, _ = score_song(POP_USER, acoustic_song)
    assert with_pref - without_pref == pytest.approx(0.5 * 0.9 - 0.5 * 0.1)


def test_perfect_song_scores_maximum():
    score, _ = score_song(POP_USER, make_song(1, acousticness=0.0))
    assert score == pytest.approx(4.5)


def test_recommend_songs_returns_top_5_sorted_high_to_low():
    songs = load_songs("data/songs.csv")
    results = recommend_songs(POP_USER, songs, k=5)
    assert len(results) == 5
    scores = [score for _, score, _ in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0][0]["title"] == "Sunrise City"
    assert all(isinstance(explanation, str) and explanation for _, _, explanation in results)


def test_ties_break_by_energy_similarity_then_lower_id():
    # Song 2 and 3: same total (1.0), but song 3 has higher energy points.
    # Song 4 and 5: identical, so the lower id must come first.
    songs = [
        make_song(5, genre="x", mood="x", energy=0.5, acousticness=0.5),
        make_song(2, genre="x", mood="x", energy=0.6, acousticness=0.6),  # 0.8 + 0.2
        make_song(3, genre="x", mood="x", energy=0.8, acousticness=1.0),  # 1.0 + 0.0
        make_song(4, genre="x", mood="x", energy=0.5, acousticness=0.5),
    ]
    ranked_ids = [song["id"] for song, _, _ in recommend_songs(POP_USER, songs, k=4)]
    assert ranked_ids == [3, 2, 4, 5]


def test_recommend_songs_does_not_reorder_input():
    songs = load_songs("data/songs.csv")
    original_ids = [song["id"] for song in songs]
    recommend_songs(POP_USER, songs, k=5)
    assert [song["id"] for song in songs] == original_ids
