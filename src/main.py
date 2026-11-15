"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from src.recommender import load_songs, recommend_songs


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

    recommendations = recommend_songs(user_prefs, songs, k=5)

    print(
        f"\nUser profile: genre={user_prefs['genre']}, mood={user_prefs['mood']}, "
        f"energy={user_prefs['energy']}, likes_acoustic={user_prefs['likes_acoustic']}"
    )
    print("\nTop 5 recommendations:\n")
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"{rank}. {song['title']} by {song['artist']}")
        print(f"   Genre: {song['genre']} | Mood: {song['mood']}")
        print(f"   Score: {score:.3f} / 4.5")
        print("   Reasons:")
        for reason in explanation.split("; "):
            print(f"     - {reason}")
        print()


if __name__ == "__main__":
    main()
