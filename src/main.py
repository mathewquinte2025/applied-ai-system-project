"""
Command line runner for the Music Recommender Simulation.

Runs the default example profile (detailed output), then the Phase 4
evaluation profiles and the weight experiment (compact output).
The scoring logic lives in recommender.py.
"""

from src.recommender import EXPERIMENT_WEIGHTS, load_songs, recommend_songs

# Phase 4 evaluation profiles. Note: the catalog has no lofi song labeled "relaxed"
# and no rock song labeled "angry"; these profiles are kept as specified on purpose.
EVALUATION_PROFILES = {
    "High-Energy Pop": {"genre": "pop", "mood": "happy", "energy": 0.9, "likes_acoustic": False},
    "Chill Lofi": {"genre": "lofi", "mood": "relaxed", "energy": 0.2, "likes_acoustic": True},
    "Deep Intense Rock": {"genre": "rock", "mood": "angry", "energy": 0.95, "likes_acoustic": False},
    # Edge case: conflicting preferences (loud genre, calm everything else).
    "Conflicting (Peaceful Metal)": {"genre": "metal", "mood": "peaceful", "energy": 0.1, "likes_acoustic": True},
}
EXPERIMENT_PROFILE = "Deep Intense Rock"


def describe_profile(user_prefs: dict) -> str:
    """Return a one-line summary of a user profile."""
    return (
        f"genre={user_prefs['genre']}, mood={user_prefs['mood']}, "
        f"energy={user_prefs['energy']}, likes_acoustic={user_prefs['likes_acoustic']}"
    )


def print_detailed(user_prefs: dict, songs: list) -> None:
    """Print the top 5 songs with every scoring reason."""
    recommendations = recommend_songs(user_prefs, songs, k=5)
    print(f"\nUser profile: {describe_profile(user_prefs)}")
    print("\nTop 5 recommendations:\n")
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"{rank}. {song['title']} by {song['artist']}")
        print(f"   Genre: {song['genre']} | Mood: {song['mood']}")
        print(f"   Score: {score:.3f} / 4.5")
        print("   Reasons:")
        for reason in explanation.split("; "):
            print(f"     - {reason}")
        print()


def print_compact(name: str, user_prefs: dict, songs: list) -> None:
    """Print the top 5 songs on one line each, plus the reasons for the #1 song."""
    recommendations = recommend_songs(user_prefs, songs, k=5)
    print(f"\n--- {name}: {describe_profile(user_prefs)} ---")
    for rank, (song, score, _) in enumerate(recommendations, start=1):
        label = f"{song['title']} ({song['genre']}, {song['mood']})"
        print(f"  {rank}. {label:<42} {score:.3f}")
    print("  Why #1:")
    for reason in recommendations[0][2].split("; "):
        print(f"     - {reason}")


def print_weight_experiment(name: str, user_prefs: dict, songs: list) -> None:
    """Print the top 5 under the original and experimental weights side by side."""
    original = recommend_songs(user_prefs, songs, k=5)
    experiment = recommend_songs(user_prefs, songs, k=5, weights=EXPERIMENT_WEIGHTS)
    print(f"\n=== Weight experiment ({name}) ===")
    print("Original: genre 2.0, mood 1.0, energy 1.0, acoustic 0.5 (max 4.5)")
    print("Experiment: genre 1.0, mood 1.0, energy 2.0, acoustic 0.5 (max 4.5)\n")
    print(f"  {'Rank':<5}{'Original':<30}{'Experiment':<30}")
    for rank, ((song_a, score_a, _), (song_b, score_b, _)) in enumerate(zip(original, experiment), start=1):
        left = f"{song_a['title']} ({score_a:.3f})"
        right = f"{song_b['title']} ({score_b:.3f})"
        print(f"  {rank:<5}{left:<30}{right:<30}")


def main() -> None:
    songs = load_songs("data/songs.csv")

    # Example taste profile (mirrors the UserProfile fields in recommender.py):
    #   genre          -> favorite_genre   (exact match, +2.0)
    #   mood           -> favorite_mood    (exact match, +1.0)
    #   energy         -> target_energy    (0.0-1.0, closeness scores up to +1.0)
    #   likes_acoustic -> likes_acoustic   (True/False, acoustic fit up to +0.5)
    user_prefs = {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.8,
        "likes_acoustic": False,
    }
    print_detailed(user_prefs, songs)

    print("\n=== Phase 4 evaluation profiles (top 5, original weights) ===")
    for name, profile in EVALUATION_PROFILES.items():
        print_compact(name, profile, songs)

    print_weight_experiment(EXPERIMENT_PROFILE, EVALUATION_PROFILES[EXPERIMENT_PROFILE], songs)


if __name__ == "__main__":
    main()
