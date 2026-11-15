# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

Replace this paragraph with your own summary of what your version does.

---

## How The System Works

### How real-world recommenders work

Platforms like Spotify and YouTube collect two kinds of data and use it to predict what you'll want next:

- **Behavior data:** what users do, like plays, skips, likes, saves, playlist adds, replays, and watch or listen time. A skip is a weak "no." A replay or playlist add is a strong "yes."
- **Item data:** what the content is, like genre, mood, tempo, energy, artist, and release year.

Large platforms usually combine two main approaches:

| | Collaborative filtering | Content-based filtering |
|---|---|---|
| **Core idea** | "Users who liked what you liked also liked *this*." | "This song is *similar* to songs you like." |
| **Uses** | Other users' behavior (likes, skips, playlists, history) | The song's own attributes (genre, mood, energy, tempo) |
| **Strength** | Can find surprising picks across genres | Works without any other users and is easy to explain |
| **Weakness** | Needs lots of users. New songs with no plays get ignored (the "cold start" problem) | Tends to recommend more of the same (a "filter bubble") |

### Why this simulation uses content-based filtering

This project has a small song catalog (`data/songs.csv`) and **no data about other users**, so collaborative filtering isn't possible here. Content-based filtering only needs song attributes and one user's stated preferences. That makes it a good fit, and every recommendation is easy to explain.

### The user profile

The user profile is the system's picture of one listener's taste. Every song is compared against it. The fields match `UserProfile` in `src/recommender.py`, and the example dictionary in `src/main.py` uses the same fields:

| Field | Example | What it captures |
|---|---|---|
| `favorite_genre` (`genre`) | `"pop"` | The overall sound the listener prefers |
| `favorite_mood` (`mood`) | `"happy"` | The feeling they want right now |
| `target_energy` (`energy`) | `0.8` | How intense the music should be (0 = calm, 1 = intense) |
| `likes_acoustic` | `False` | Whether they prefer acoustic or electronic/produced sounds |

```python
user_prefs = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}
```

**Why these fields work together:** no single label decides the result. An intense-rock listener (`rock`, `intense`, `0.9`, not acoustic) and a chill-lofi listener (`lofi`, `chill`, `0.4`, acoustic) differ on all four fields. Even if a song matches one of them on a single label, energy closeness and acoustic fit pull it toward the right listener.

**Why it isn't too narrow:** the profile never *filters out* songs. Every song gets a score, and partial matches still earn points. A song that misses the genre but matches the mood and energy can still rank well, so the user always gets a full list of recommendations.

### Features used

**`Song`** (one row of `data/songs.csv`, 18 songs): `id`, `title`, `artist`, `genre`, `mood`, `energy` (0–1), `tempo_bpm`, `valence` (0–1, musical positivity), `danceability` (0–1), `acousticness` (0–1).

- **Used in the score:** `genre`, `mood`, `energy`, `acousticness`
- **Not scored (kept simple):** `tempo_bpm` largely overlaps with energy and uses a different scale (BPM). `valence` overlaps with mood. `danceability` has no matching profile field.

### Scoring Rule (one song)

```
score = genre_points + mood_points + energy_points + acoustic_points

genre_points    = 2.0 if song.genre == user.favorite_genre else 0.0
mood_points     = 1.0 if song.mood  == user.favorite_mood  else 0.0
energy_points   = 1 - abs(song.energy - user.target_energy)            # 0.0 to 1.0
acoustic_points = 0.5 * song.acousticness        if user.likes_acoustic  # 0.0 to 0.5
                  0.5 * (1 - song.acousticness)  otherwise
```

The maximum score is **4.5**.

1. **Genre match (+2.0):** genre is the strongest signal because it describes the overall sound of a song (instruments, style, production).
2. **Mood match (+1.0):** mood is a softer label that shows up across many genres, so it's worth half as much as genre.
3. **Energy similarity (0 to +1.0):** this rewards closeness to the target, not high energy. If the target is 0.80, a 0.82 song earns 0.98 and a 0.35 song earns 0.55.
4. **Acoustic fit (0 to +0.5):** this uses the `likes_acoustic` field that `UserProfile` already has. It separates acoustic songs (jazz, lofi, classical) from produced ones (EDM, pop). Its weight is kept low so it fine-tunes the ranking without overpowering genre or mood.
5. **Total:** all four parts are added together into one number.

### Worked example

User: `genre="pop"`, `mood="happy"`, `energy=0.8`, `likes_acoustic=False`

| Song | Genre | Mood | Energy | Acoustic | **Total** |
|---|---|---|---|---|---|
| Sunrise City (pop, happy, 0.82, ac 0.18) | 2.0 | 1.0 | 0.98 | 0.41 | **4.39** |
| Gym Hero (pop, intense, 0.93, ac 0.05) | 2.0 | 0.0 | 0.87 | 0.475 | **3.345** |
| Rooftop Lights (indie pop, happy, 0.76, ac 0.35) | 0.0 | 1.0 | 0.96 | 0.325 | **2.285** |
| Library Rain (lofi, chill, 0.35, ac 0.86) | 0.0 | 0.0 | 0.55 | 0.07 | **0.62** |

### Ranking Rule (whole catalog)

The Scoring Rule rates **one** song. The Ranking Rule puts the **whole list** in order:

1. Apply the Scoring Rule to every song in the catalog.
2. Sort the songs from highest to lowest total score.
3. **Ties:** if two songs have the same total, the one with the higher energy points ranks first. If they're still tied, the lower `id` ranks first, so results are always the same for the same input.
4. Return the top `k` songs (default `k = 5`), each with a short explanation of its points (for example, "genre match +2.0, mood match +1.0, energy +0.98").

```
songs.csv → [score each song] → [sort: score ↓, energy points ↓, id ↑] → top k recommendations
```

### Bias and limitations

- **Exact-match labels:** `"indie pop"` does not count as `"pop"`. In the example above, *Rooftop Lights* (indie pop, happy) scores below *Gym Hero* (pop, intense), even though it arguably matches the vibe better.
- **Genre dominance:** a genre match (2.0) usually outweighs mood plus energy. For an intense-rock user, the relaxed rock song *Slow Burn Sunday* (2.775) outranks the intense pop song *Gym Hero* (2.445).
- **Small, uneven catalog:** only 18 songs. Lofi has 3 songs and rock has 2, but most genres have just 1, so some users get much better top-5 lists than others.
- **One label per song:** each song has one genre and one mood. A song that is both "happy" and "chill" can only match one of them.
- **No behavior data:** the system can't learn from skips, replays, or other listeners, and it doesn't understand lyrics or language.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Recommendation Output

Actual output from running `python -m src.main` with the default example profile:

```
Loaded 18 songs from data/songs.csv

User profile: genre=pop, mood=happy, energy=0.8, likes_acoustic=False

Top 5 recommendations:

1. Sunrise City by Neon Echo
   Genre: pop | Mood: happy
   Score: 4.390 / 4.5
   Reasons:
     - genre match (pop): +2.0
     - mood match (happy): +1.0
     - energy similarity (0.82 vs. target 0.80): +0.980
     - acoustic fit (acousticness 0.18, prefers non-acoustic): +0.410

2. Gym Hero by Max Pulse
   Genre: pop | Mood: intense
   Score: 3.345 / 4.5
   Reasons:
     - genre match (pop): +2.0
     - mood mismatch (intense vs. happy): +0.0
     - energy similarity (0.93 vs. target 0.80): +0.870
     - acoustic fit (acousticness 0.05, prefers non-acoustic): +0.475

3. Rooftop Lights by Indigo Parade
   Genre: indie pop | Mood: happy
   Score: 2.285 / 4.5
   Reasons:
     - genre mismatch (indie pop vs. pop): +0.0
     - mood match (happy): +1.0
     - energy similarity (0.76 vs. target 0.80): +0.960
     - acoustic fit (acousticness 0.35, prefers non-acoustic): +0.325

4. Bassline Theory by Kilo Vector
   Genre: edm | Mood: euphoric
   Score: 1.395 / 4.5
   Reasons:
     - genre mismatch (edm vs. pop): +0.0
     - mood mismatch (euphoric vs. happy): +0.0
     - energy similarity (0.89 vs. target 0.80): +0.910
     - acoustic fit (acousticness 0.03, prefers non-acoustic): +0.485

5. Concrete Verses by Dre Malone
   Genre: hip hop | Mood: confident
   Score: 1.360 / 4.5
   Reasons:
     - genre mismatch (hip hop vs. pop): +0.0
     - mood mismatch (confident vs. happy): +0.0
     - energy similarity (0.72 vs. target 0.80): +0.920
     - acoustic fit (acousticness 0.12, prefers non-acoustic): +0.440
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or demo video link here -->

---

## Experiments You Tried

Use this section to document the experiments you ran. For example:

- What happened when you changed the weight on genre from 2.0 to 0.5
- What happened when you added tempo or valence to the score
- How did your system behave for different types of users

---

## Limitations and Risks

Summarize some limitations of your recommender.

Examples:

- It only works on a tiny catalog
- It does not understand lyrics or language
- It might over favor one genre or mood

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this



