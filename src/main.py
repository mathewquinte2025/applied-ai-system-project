"""
Command line runner for the Music Recommender Simulation.

With no arguments it runs the original demo: the default example profile
(detailed output), the Phase 4 evaluation profiles and the weight experiment.

With arguments it recommends songs for your own profile, for example:
    python -m src.main --genre pop --mood happy --energy 0.8 --acoustic no --k 5

Every recommendation goes through the guardrails in guardrails.py.
The scoring logic lives in recommender.py.
"""

import argparse
import logging
import sys

from src.guardrails import GuardrailError, safe_recommend
from src.recommender import EXPERIMENT_WEIGHTS, PROJECT_ROOT, load_songs, recommend_songs

DEFAULT_DATA = "data/songs.csv"
LOG_FILE = PROJECT_ROOT / "logs" / "recommender.log"

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


def setup_logging(console_level=logging.WARNING) -> None:
    """Log everything to logs/recommender.log; show only warnings and errors in the terminal."""
    handlers = []
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter("[log] %(levelname)s: %(message)s"))
    handlers.append(console)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        log_file = logging.FileHandler(LOG_FILE, encoding="utf-8")
        log_file.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handlers.append(log_file)
    except OSError:
        pass  # If the log file can't be created, keep running with terminal logging only.
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


def describe_profile(user_prefs: dict) -> str:
    """Return a one-line summary of a user profile."""
    return (
        f"genre={user_prefs['genre']}, mood={user_prefs['mood']}, "
        f"energy={user_prefs['energy']}, likes_acoustic={user_prefs['likes_acoustic']}"
    )


def print_reliability(result) -> None:
    """Print the confidence label and any guardrail warnings."""
    print(f"Confidence: {result.confidence} ({result.confidence_reason})")
    for warning in result.warnings:
        print(f"Warning: {warning}")


def print_detailed(user_prefs: dict, songs: list, k=5) -> None:
    """Print the top k songs with every scoring reason, plus confidence and warnings."""
    result = safe_recommend(user_prefs, songs, k)
    print(f"\nUser profile: {describe_profile(result.profile)}")
    print_reliability(result)
    print(f"\nTop {len(result.recommendations)} recommendations:\n")
    for rank, (song, score, explanation) in enumerate(result.recommendations, start=1):
        print(f"{rank}. {song['title']} by {song['artist']}")
        print(f"   Genre: {song['genre']} | Mood: {song['mood']}")
        print(f"   Score: {score:.3f} / 4.5")
        print("   Reasons:")
        for reason in explanation.split("; "):
            print(f"     - {reason}")
        print()


def print_compact(name: str, user_prefs: dict, songs: list) -> None:
    """Print the top 5 songs on one line each, the reasons for the #1 song, and confidence."""
    result = safe_recommend(user_prefs, songs, k=5)
    recommendations = result.recommendations
    print(f"\n--- {name}: {describe_profile(user_prefs)} ---")
    for rank, (song, score, _) in enumerate(recommendations, start=1):
        label = f"{song['title']} ({song['genre']}, {song['mood']})"
        print(f"  {rank}. {label:<42} {score:.3f}")
    print("  Why #1:")
    for reason in recommendations[0][2].split("; "):
        print(f"     - {reason}")
    print(f"  Confidence: {result.confidence}")
    for warning in result.warnings:
        print(f"  Warning: {warning}")


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


def run_demo(songs: list) -> None:
    """The original Module 3 demo: default profile, evaluation profiles, weight experiment."""
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


def build_parser() -> argparse.ArgumentParser:
    """Define the command line options."""
    parser = argparse.ArgumentParser(
        description="Rule-based music recommender with reliability guardrails. "
                    "Run with no options to see the original demo.",
    )
    parser.add_argument("--genre", help="favorite genre, e.g. pop, lofi, rock, 'hip hop'")
    parser.add_argument("--mood", help="favorite mood, e.g. happy, chill, intense")
    parser.add_argument("--energy", help="target energy from 0.0 (calm) to 1.0 (intense)")
    parser.add_argument("--acoustic", help="do you like acoustic music? yes or no (default: no)")
    parser.add_argument("--k", help="number of recommendations (default: 5)")
    parser.add_argument("--data", default=DEFAULT_DATA, help=f"song CSV file (default: {DEFAULT_DATA})")
    return parser


def main(argv=None) -> int:
    """Run the app. Returns 0 on success and 1 on a handled error."""
    setup_logging()
    args = build_parser().parse_args(argv)
    custom_options = [args.genre, args.mood, args.energy, args.acoustic, args.k]

    try:
        songs = load_songs(args.data)
        print(f"Loaded {len(songs)} songs from {args.data}")

        if all(option is None for option in custom_options):
            if not songs:
                raise GuardrailError("The song catalog is empty, so there is nothing to recommend.")
            run_demo(songs)
            return 0

        missing = [name for name in ("genre", "mood", "energy") if getattr(args, name) is None]
        if missing:
            raise GuardrailError(
                "Please provide " + ", ".join(f"--{name}" for name in missing)
                + " (or run with no options to see the demo)."
            )
        user_prefs = {
            "genre": args.genre,
            "mood": args.mood,
            "energy": args.energy,
            "likes_acoustic": "no" if args.acoustic is None else args.acoustic,
        }
        print_detailed(user_prefs, songs, k=5 if args.k is None else args.k)
        return 0

    except GuardrailError as error:
        logging.getLogger(__name__).info("Rejected input: %s", error)
        print(f"Input error: {error}")
    except (FileNotFoundError, ValueError) as error:
        print(f"Data error: {error}")
    except Exception:
        logging.getLogger(__name__).exception("Unexpected error")
        print(f"Unexpected error. Details were saved to {LOG_FILE}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
