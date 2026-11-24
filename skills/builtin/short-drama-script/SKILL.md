---
name: short-drama-script
description: 写短剧：根据用户提供的素材写短剧剧本，包括台词、分集和钩子，注意节奏。
metadata:
  version: 1.0.0
  tags: [drama, script, creation]
allowed-tools:
  - read_skill_file
  - run_skill_script
---

# Short-drama script (creation from scratch)

Use this skill when the user brings an idea, a logline, a character sheet, or a
genre and asks for a **new** short-drama episode or series. If the user already
has a finished script and only wants the lines reworded, use
`short-drama-rewrite` instead.

## Steps

1. Confirm the four inputs. If any is missing, choose a sensible default and
   state it in one line: vertical 9:16, 60-90s per episode, 1 main hook per
   episode, target platform (douyin / kuaishou / reelshot).
2. Write the episode outline with `templates/episode-outline.md` as the section
   skeleton. One line per beat, 5-8 beats, each beat must change the situation.
3. Draft dialogue in Chinese, present tense, no camera directions in the spoken
   lines. Keep each line under 20 characters where possible; short drama is
   watched with sound off in the first 3 seconds, so the first line must carry
   the hook.
4. Enforce the beat budget: cold open <= 10s, first reversal before 35s, cliff
   hanger in the last 8s. Never resolve the main conflict inside one episode.
5. Run `scripts/check_scene_length.py` on the finished draft to verify per-scene
   length and hook placement. Fix every reported violation before answering.
6. Deliver: title, one-line logline, beat list, full script, and the "next
   episode hook" in one sentence.

## Rules

- No narration blocks. Everything that matters must be said or shown in action.
- Every scene needs a goal, an obstacle, and a turn.
- Do not write more than 3 named characters per episode.
