# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**VibeMatch 1.0**, a content-based music recommender built for a classroom simulation.

---

## 2. Goal / Task and Intended Use  

**Goal / task:** given one listener's stated taste (favorite genre, favorite mood, target energy level, and whether they like acoustic music), VibeMatch scores every song in a small catalog and returns the top 5 matches. Each match comes with a plain-language explanation of where its points came from. It's meant to show, in a way you can fully inspect, how a recommender turns data into a ranked list.

**Intended use**

- Classroom exploration of how content-based recommenders work.
- Experimenting with scoring weights and seeing how rankings change.
- Discussing bias, filter bubbles and the limits of label-based recommendations.

**Assumptions about the user:** the listener can describe their taste with one genre, one mood, one energy level and a yes/no acoustic preference, and that taste stays the same during a session.

**Not intended for**

- Real users or a production music service. The catalog has only 18 made-up songs.
- Claiming to understand a person's complete musical taste. It only knows four stated preferences and learns nothing from listening behavior.
- Making decisions about people, or judging which genres or artists are "better". Scores only measure how well a song's labels match one profile.

---

## 3. How the Model Works (Algorithm Summary)  

Every song gets points from four checks, and the points are added up. The maximum is **4.5**.

| Check | Points | How it works |
|---|---|---|
| Genre | +2.0 or 0 | Full points only if the song's genre exactly matches the favorite genre |
| Mood | +1.0 or 0 | Full points only if the song's mood exactly matches the favorite mood |
| Energy | 0 to +1.0 | `1 − |song energy − target energy|`, so closer is better, not just louder |
| Acoustic fit | 0 to +0.5 | `0.5 × acousticness` if the user likes acoustic music, otherwise `0.5 × (1 − acousticness)` |

Genre is weighted highest because it describes the overall sound of a song. Mood is a softer label that crosses genres. Acoustic fit has a small weight so it fine-tunes the order without taking over.

**Ranking:** every song in the catalog is scored and sorted from highest to lowest. Ties go to the song with the higher energy-similarity points, then to the lower song ID, so the same profile always gives the same list. The top 5 are returned with their reasons.

**Changes from the starter code:**
- Implemented CSV loading, scoring, ranking and explanations; the starter functions were placeholders.
- Added the acoustic-fit term using the starter's existing `likes_acoustic` field.
- Added deterministic tie-breaking.
- Added an optional weights setting so the Phase 4 experiment could run without replacing the default weights.

---

## 4. Data Used  

- **Catalog:** `data/songs.csv`, 18 songs. The starter provided 10. I added 8 made-up songs (IDs 11–18) to cover more genres, moods and energy levels. No songs were removed.
- **Columns:** `id`, `title`, `artist`, `genre`, `mood`, `energy` (0–1), `tempo_bpm`, `valence` (0–1), `danceability` (0–1), `acousticness` (0–1).
- **Used for scoring:** `genre`, `mood`, `energy` and `acousticness`.
- **Not used for scoring:** `tempo_bpm` overlaps with energy and uses a different scale. `valence` overlaps with mood. `danceability` has no matching user preference.
- **Genres (14):** lofi (3 songs); pop and rock (2 each); and one song each of ambient, blues, classical, country, edm, hip hop, indie pop, jazz, metal, r&b and synthwave.
- **Moods (13):** happy, chill, intense, relaxed, focused, moody, angry, romantic, nostalgic, euphoric, peaceful, confident and sad. Each song has exactly one.
- **What's missing:**
  - Lyrics, language, artist popularity and release year.
  - Any listening behavior (plays, skips, likes).
  - More than one song for most genres.
  - Some genre/mood combinations, for example no "relaxed" lofi and no "angry" rock.

---

## 5. Strengths  

- **It clearly separates different listening situations.** In Phase 4, the High-Energy Pop and Chill Lofi profiles shared no songs in their top 5. Energy and acoustic fit did most of that work.
- **Typical profiles get intuitive #1 picks.** Examples: *Sunrise City* for pop/happy, *Library Rain* for lofi, *Storm Runner* for rock.
- **The energy term rewards closeness.** Raising the pop target from 0.8 to 0.9 swapped the #5 song (*Concrete Verses*, 0.72) for a higher-energy one (*Storm Runner*, 0.91), as intended.
- **Every recommendation is explainable.** The output lists the exact points from each check, so you can always see why a song ranked where it did.
- **Results are repeatable.** The same profile always produces the same ranking, which makes testing and comparison easy.

---

## 6. Observed Behavior, Limitations and Bias

These come from the actual implementation (`src/recommender.py`) and the 18-song catalog (`data/songs.csv`), and were observed in the Phase 4 evaluation.

1. **Exact genre matching.** Genre is a yes/no string comparison, so `"indie pop"` gets 0 genre points from a `"pop"` user. *Rooftop Lights* (indie pop, happy) always ranks below *Gym Hero* (pop, intense) for pop/happy users, even though its mood and energy fit better.
2. **Genre label outweighs the actual sound.** The genre match (+2.0) is worth more than the largest possible energy and acoustic bonus combined (+1.5). For the Deep Intense Rock user, the calm rock song *Slow Burn Sunday* (energy 0.45) ranks #2, ahead of *Iron Horizon* (metal, angry, energy 0.97), which is much closer to what that listener asked for.
3. **Small, uneven catalog.** There are 18 songs. Lofi has 3, rock and pop have 2 each, and 11 genres have exactly 1. A metal fan can only ever get one metal song. Lofi fans get three genre matches, so their top-5 lists look much better than metal fans' lists. That's a bias toward the genres that happen to have more data.
4. **Mood labels are subjective and sparse.** Each song has one hand-picked mood. No lofi song is "relaxed" and no rock song is "angry", so the Chill Lofi and Deep Intense Rock users can never get a full genre + mood match. "Chill", "relaxed" and "peaceful" are treated as completely different words, even though people would call them similar.
5. **No learning from behavior.** The profile is fixed. The system never sees skips, replays or other listeners, so it can't notice that its guesses were wrong.

**Filter-bubble risk:** because genre dominates and the same profile always produces the same list, a user keeps seeing the same few songs from their favorite genre. Songs from other genres only appear in the leftover slots, and only if their energy happens to be close. In a real app, a user would rarely be shown anything outside their stated genre, and the system would never find out whether they'd like it.

---

## 7. Evaluation  

### 7.1 Evaluation process

1. Defined four user profiles: three typical listeners and one edge case with conflicting preferences.
2. Ran each through the real recommender (`python -m src.main`) using the original weights, and recorded the top 5.
3. For each profile, checked the #1 song's score breakdown, compared the list with what a person would expect, and noted surprises.
4. Ran one controlled weight experiment, changing only the weights, on the same profile and dataset.
5. Automated checks: 14 `pytest` tests cover loading, each scoring component, ranking, ties, and that the experiment weights don't change the default scoring.

**Dataset note:** the catalog has no lofi song labeled "relaxed" and no rock song labeled "angry". I kept the required profiles unchanged instead of editing the dataset to force matches. The gap is a realistic test of what happens when a user's mood doesn't exist in their genre.

### 7.2 Tested user profiles

| Profile | genre | mood | energy | likes_acoustic |
|---|---|---|---|---|
| High-Energy Pop | pop | happy | 0.9 | False |
| Chill Lofi | lofi | relaxed | 0.2 | True |
| Deep Intense Rock | rock | angry | 0.95 | False |
| Conflicting (Peaceful Metal) | metal | peaceful | 0.1 | True |

**Why the edge case is hard:** metal is the loudest, least acoustic genre in the catalog, but this user wants peaceful, very calm, acoustic music. Genre (+2.0) points to *Iron Horizon* (energy 0.97, acousticness 0.04). Mood, energy and acoustic fit (up to +2.5 together) point to quiet acoustic songs. Whichever side earns more points wins.

### 7.3 Results and observed behavior

Actual output, original weights (`python -m src.main`):

```
--- High-Energy Pop: genre=pop, mood=happy, energy=0.9, likes_acoustic=False ---
  1. Sunrise City (pop, happy)                  4.330
  2. Gym Hero (pop, intense)                    3.445
  3. Rooftop Lights (indie pop, happy)          2.185
  4. Bassline Theory (edm, euphoric)            1.475
  5. Storm Runner (rock, intense)               1.440

--- Chill Lofi: genre=lofi, mood=relaxed, energy=0.2, likes_acoustic=True ---
  1. Library Rain (lofi, chill)                 3.280
  2. Focus Flow (lofi, focused)                 3.190
  3. Midnight Coding (lofi, chill)              3.135
  4. Coffee Shop Stories (jazz, relaxed)        2.275
  5. Slow Burn Sunday (rock, relaxed)           2.025

--- Deep Intense Rock: genre=rock, mood=angry, energy=0.95, likes_acoustic=False ---
  1. Storm Runner (rock, intense)               3.410
  2. Slow Burn Sunday (rock, relaxed)           2.725
  3. Iron Horizon (metal, angry)                2.460
  4. Gym Hero (pop, intense)                    1.455
  5. Bassline Theory (edm, euphoric)            1.425

--- Conflicting (Peaceful Metal): genre=metal, mood=peaceful, energy=0.1, likes_acoustic=True ---
  1. Quiet Sonata No. 3 (classical, peaceful)   2.405
  2. Iron Horizon (metal, angry)                2.150
  3. Spacewalk Thoughts (ambient, chill)        1.280
  4. Library Rain (lofi, chill)                 1.180
  5. Coffee Shop Stories (jazz, relaxed)        1.175
```

**High-Energy Pop.** *Sunrise City* wins with 4.33: genre +2.0, mood +1.0, energy +0.92 (0.82 vs. 0.90) and acoustic +0.41. This matches intuition, and both pop songs take #1 and #2. Compared with the default profile (energy 0.8), the top 4 are the same. Only #5 changed: *Storm Runner* (energy 0.91) replaced *Concrete Verses* (0.72) because the target moved up. That shows the energy term reacts to the target as intended. *Rooftop Lights* at #3 is the expected exact-match casualty.

**Chill Lofi.** *Library Rain* wins with 3.28: genre +2.0, mood +0.0 (chill ≠ relaxed), energy +0.85 (0.35 vs. 0.20) and acoustic +0.43. All three lofi songs fill #1–#3 with no mood match at all, so genre is doing the work. *Focus Flow* (focused) slightly beats *Midnight Coding* (chill) because it's a bit more acoustic and calmer. A person might expect "chill" to count for a relaxed listener, but the system can't tell they're related. **Surprise:** *Slow Burn Sunday*, a rock song, reaches #5 for a lofi fan, purely because its mood label is "relaxed". Meanwhile *Quiet Sonata No. 3* (energy 0.18, acousticness 0.97), arguably a better fit, scores only 1.465 and misses the top 5.

**Deep Intense Rock.** The profile does favor rock. Both rock songs are #1 and #2, and *Storm Runner* wins with 3.41: genre +2.0, mood +0.0 (intense ≠ angry), energy +0.96 and acoustic +0.45. **Surprise:** *Slow Burn Sunday* (rock, relaxed, energy 0.45) ranks #2 even though it's calm. It earns only +0.50 for energy but the full +2.0 for genre. *Iron Horizon*, the only "angry" song and the closest in energy (0.97), comes third. A person would almost certainly rank *Iron Horizon* above a relaxed song.

**Conflicting (Peaceful Metal).** *Quiet Sonata No. 3* wins with 2.405: mood +1.0, energy +0.92 (0.18 vs. 0.10) and acoustic +0.485, with no genre match. The three "calm" signals together beat the single genre signal. *Iron Horizon* still reaches #2 (2.15) almost entirely from its +2.0 genre bonus, since it earns only +0.13 for energy and +0.02 for acoustic fit. The result is a strange mix: one classical piece, one aggressive metal track, then quiet ambient, lofi and jazz. The system doesn't recognize that the profile contradicts itself. It just adds the points up.

**Comparisons across profiles**

- **High-Energy Pop vs. Chill Lofi:** the lists don't share a single song. Pop's list is all energy 0.76 or higher and low acousticness. Lofi's list is all energy 0.45 or lower and acousticness 0.55 or higher. Energy and acoustic fit separate the two listening situations clearly.
- **Deep Intense Rock vs. High-Energy Pop:** they share *Gym Hero*, *Bassline Theory* and *Storm Runner*, because the high-energy songs fill the slots without a genre match for both users.
- **Genre vs. mood:** in three of the four profiles, a genre match alone (*Gym Hero* for pop, *Slow Burn Sunday* for rock, the lofi songs for Chill Lofi) beat a mood match plus close energy. That's working as designed, but it's sometimes the wrong call. The exception is Peaceful Metal, where mood, energy and acoustic fit all agreed and together outscored the genre match.

### 7.4 Weight experiment: halve genre, double energy

**Change:** genre 2.0 → **1.0**, energy 1.0 → **2.0**. Mood (1.0) and acoustic (0.5) are unchanged, and the maximum stays 4.5. It uses the same dataset, the same **Deep Intense Rock** profile and the same code. The experiment weights are passed in explicitly (`EXPERIMENT_WEIGHTS`), so the default scoring is never replaced.

```
=== Weight experiment (Deep Intense Rock) ===
Original: genre 2.0, mood 1.0, energy 1.0, acoustic 0.5 (max 4.5)
Experiment: genre 1.0, mood 1.0, energy 2.0, acoustic 0.5 (max 4.5)

  Rank Original                      Experiment
  1    Storm Runner (3.410)          Iron Horizon (3.440)
  2    Slow Burn Sunday (2.725)      Storm Runner (3.370)
  3    Iron Horizon (2.460)          Gym Hero (2.435)
  4    Gym Hero (1.455)              Bassline Theory (2.365)
  5    Bassline Theory (1.425)       Slow Burn Sunday (2.225)
```

| Song | Original | Experiment | Why it moved |
|---|---|---|---|
| Iron Horizon (metal, angry, 0.97) | #3 (2.460) | **#1** (3.440) | Energy is almost exact (0.98 × 2 = 1.96), so doubling energy adds ~1.0 |
| Storm Runner (rock, intense, 0.91) | #1 (3.410) | #2 (3.370) | Lost 1.0 of genre, gained 0.96 of energy |
| Slow Burn Sunday (rock, relaxed, 0.45) | #2 (2.725) | **#5** (2.225) | Lost 1.0 of genre and gained only 0.50 of energy |
| Gym Hero, Bassline Theory | #4, #5 | #3, #4 | High energy now counts more than the leftover genre bonus |

**Verdict: better for this profile, but with a tradeoff.** For an intense, angry rock fan, the experiment's list is more sensible. The only angry, highest-energy song rises to #1, and the calm rock song drops to #5. But the change also makes genre matter much less everywhere. From the same comparison run on the other profiles:
- High-Energy Pop's order was unchanged.
- In Chill Lofi, the jazz song *Coffee Shop Stories* rose from #4 to #2.
- For the Peaceful Metal user, *Iron Horizon* (the catalog's only metal song) dropped out of the top 5 entirely.

The experiment trades one bias (genre labels dominate) for another (energy dominates). The original weights were kept as the default.

---

## 8. Future Work  

1. **Partial genre and mood matching.** Give partial credit for related labels: `"indie pop"` → `"pop"` (for example +1.0 instead of 0), or `"chill"` ≈ `"relaxed"` ≈ `"peaceful"`. This fixes the most common surprise from Phase 4, where *Rooftop Lights* always lost to *Gym Hero*.
2. **A bigger, more balanced catalog with multiple mood tags.** Several songs per genre would give metal or classical fans as many good options as lofi fans. Letting a song have more than one mood ("happy" *and* "chill") would reduce exact-match misses.
3. **Diversity and learning from behavior.** Limit how many top-5 slots one genre can take, to push back against the filter bubble. Later, adjust a user's profile based on skips and replays instead of keeping it fixed.

---

## 9. Personal Reflection  

**Biggest concept.** A recommender doesn't "understand" music. It turns labels and numbers into a score, and the weights decide whose preferences win. Changing just two weights in Phase 4 moved *Iron Horizon* from #3 to #1 and *Slow Burn Sunday* from #2 to #5 for the same user and the same songs. The "right" answer depends on choices a person made, not on the data alone.

**How AI assistance was used.** I worked with an AI coding assistant (Claude Code) through the project's five phases. I gave it each phase's instructions, and it inspected the project files, then:
- researched and wrote up the design;
- expanded the dataset;
- implemented and tested the recommender;
- ran the evaluation profiles and the weight experiment;
- drafted documentation from the actual program output.

I reviewed its work between phases and decided when to commit.

**Why results needed checking.** The AI's output wasn't automatically correct. While drafting the evaluation, an early version claimed that "in every profile" a genre match alone beat a mood match. Checking that against the real output showed it was false for the Peaceful Metal profile, so it was corrected. A starter import problem in `src/main.py` was also caught before the program could run. Tests (14 passing) and real terminal output, rather than predicted results, were what made the documentation trustworthy.

**What was surprising.**
- A calm rock song (*Slow Burn Sunday*, energy 0.45) ranked #2 for a user who wanted intense, angry rock, purely because of its genre label.
- The same song showed up for a lofi fan just because its mood was "relaxed".
- Simple, reasonable-looking weights can still produce recommendations a person would immediately call wrong.

**What could be added next.** Partial genre matching and a larger catalog would make the biggest difference (see Future Work).

> **[TO COMPLETE — your own words]:** Add 1–3 sentences on your personal experience. For example: what you found hardest or most interesting, whether working with the AI assistant met your expectations, or how this changed the way you see apps like Spotify or YouTube. This can't be filled in from the project files.
