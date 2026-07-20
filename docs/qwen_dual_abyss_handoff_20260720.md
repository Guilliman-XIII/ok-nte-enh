# Qwen Handoff: Dual-Team Abyss Finalization

## Read This First

This handoff records the newest runtime evidence and the immediate P0. Before changing combat behavior,
read these repository documents in this order:

1. `docs/research/abyss_live_research_decision.md` - evidence hierarchy, public guide source index,
   player-provided mechanics, and the decisions already derived from them.
2. `docs/combat_logic_deep_review.md`, sections 10 through 18 - the intended two-team design, the earlier
   failure modes, and why Planner ownership matters.
3. `docs/research/abyss_video_version_matrix.md` - which recording exercised which script revision. Never
   diagnose an old recording as a defect in a later revision without checking this matrix first.
4. `docs/abyss_live_test_runbook.md` - the live verification procedure and acceptance boundary.
5. `docs/research/source_guides/README.md` - local original guide subtitles and the matching local videos.

The user supplied additional Chinese guide subtitles, guide videos, and live recordings while this work
was developed. The original subtitles now live in `docs/research/source_guides/`; matching local videos
are in its ignored `videos/` directory. Their useful findings are also condensed into the first two
documents above.

## Game And Team Primer

NTE is a four-character real-time combat game. A good team alternates short off-field setup actions with
deliberate on-field damage windows, while grouping, elemental/reaction setup, ultimate state, cooldowns,
and survival all affect whether switching is useful. This repository automates visible UI and input only;
it does not read game memory. Consequently, every claimed mechanic must remain an observable hypothesis
until it is supported by source, Planner logs, or a version-bound recording.

The immediate product goal is reliable personal Abyss automation at a 1920x1080 windowed game client
(the user's display is 2K and recordings may be 60 FPS even when gameplay is 120 FPS). The intent is not
to imitate every high-skill manual technique. It is to produce a robust, repeatable route that combines
OKNTE's existing dodge/counter behavior with correct team rotations, and fails closed when the visible
roster is uncertain.

### Team 1: Baicang Speed Team

HUD/preset order: `Baicang -> Daphneel -> Sakiri -> Hania`.

- Baicang is the on-field main DPS. Keep her on field during grouped/enhanced windows. The current baseline
  is bounded normal attacks; the player's manual Shift-held AOE is a promising but unvalidated automation
  candidate, not an established requirement.
- Daphneel is a dark-element off-field/sub-DPS. Her E/Q sequence should be short and hand control back to
  Baicang. Baicang and Daphneel have the user's signature weapon R action; current evidence supports a
  conservative roughly-20-second policy, but visual readiness would be stronger if practical.
- Sakiri is the opening gather/control and damage-amplification setup. Her held E must be allowed to settle;
  an immediate switch can cancel the actual grouping result.
- Hania is the fast Q/E amplification/support step. She should not consume a long on-field window in the
  speed variant. A harder Abyss variant may later replace her with Fatiya for sustain, but that is not the
  current priority.

Current conceptual rotation: Sakiri gather/settle -> Hania Q/E -> Daphneel E/Q -> Baicang field window.

### Team 2: Chiz Yingxu Team

HUD/preset order: `Chiz -> Zero -> Jiuyuan -> Yi`.

- Chiz is the on-field main DPS. Her E is a three-use chain. Outside ultimate, the conservative baseline
  is two normal attacks then one E; inside ultimate, use the visible gold-gauge signal to avoid spending
  E at clearly poor value. The current yellow-versus-red gauge gate is only a conservative proxy, not a
  proven peak-timing detector.
- Jiuyuan is the grouping/quick-swap spirit setup. As with Sakiri, leave enough post-skill settle time for
  the gather to complete before switching away.
- Yi (the user's "wolf uncle") supplies the aspect/reaction part of the loop and should complete key Q/E
  setup without taking a long field window.
- Zero supplies cycle/sustain support and should also hand the field back quickly.

Current conceptual rotation: Jiuyuan gather/creation -> Yi and Zero setup/reaction/cycle -> Chiz sustained
field window. Do not collapse this into permanent support normal attacks merely because the next reaction
or cooldown has not been observed yet.

## Evidence Rules For Mechanics

- Treat player guides, subtitles, and online explanations as design candidates, not as proof that a specific
  screen state, color, sound, or input timing has occurred in this runtime.
- Treat a complete route as successful only when the current code revision's Planner logs and/or video show
  the intended action, switch, and return-to-main-DPS behavior.
- Preserve Planner reservation and route ownership. Character scripts should declare intents; ad hoc direct
  switching or input loops can reintroduce the races this branch removed.
- Prefer a safe, measurable baseline over a sophisticated mechanic that cannot be verified from UI. Upgrade
  the baseline only with focused tests plus a version-bound live recording.

## Current State

- Branch: `feat/baicang-combat`
- Runtime commit used by the newest continuous recording: `4eb6cc0b4797`
- Recording: `2026-07-20 22-13-50.mp4`, 1920x1080, 60 FPS, 467.5 seconds.
- Runtime configuration: automatic dual-team selection; saved four-member Baicang and Chiz presets.
- Current regression: `431 passed, 57 subtests passed, 1 warning` from the local ASCII runtime junction.

This is not a blank implementation. The remaining observed transition race is P0, but the next owner has
full authority to improve the entire two-team combat system, including character actions, route structure,
input timing, and Planner integration. Use the recording, logs, upstream source, and public mechanics as
evidence; do not treat the current route parameters as fixed design.

## What The New Recording Proves

At 22:14, the Baicang team was uniquely recognized and bound. Its opener fulfilled. A second Baicang
opener at 22:16 also fulfilled.

At 22:18:40, the upper-half roster disappeared. The bound Baicang task reported that the team UI was
unavailable and stopped old-team input. The old return request then spent about 1.07 seconds in `not in
team`; it did not send a character key to the lower team.

At 22:18:51, the intended handoff succeeded:

```text
detected handoff candidate: Chiz Yingxu team, waiting for stable confirmation
team handoff confirmed: Baicang speed team -> Chiz Yingxu team
automatic dual-team selection: Chiz Yingxu team
team binding: Chiz Yingxu team / Chiz -> Zero -> Jiuyuan -> Yi
```

The Chiz opener and subsequent strict routes fulfilled. The recording therefore proves that the stale
Baicang-to-Chiz slot misuse has been removed.

## P0 Remaining Defect

There is still an unacceptable initial-frame fallback during that same handoff:

1. At 22:18:48, the first lower-half frame recognizes Chiz, Zero, and Yi, but Jiuyuan is only `0.52`.
2. `load_chars()` sees no complete preset and falls back to generic character detection, as introduced by
   `4eb6cc0` to preserve ordinary non-abyss auto combat.
3. At 22:18:49, the temporary generic Chiz object sends `Q` before strict team binding is established.
4. At 22:18:51, the second stable frame binds the exact Chiz preset correctly.

This did not reuse a Baicang character or press a wrong lower-half slot. It is nevertheless a violation of
the strict abyss rule: a partially recognized known abyss roster must not receive generic combat input.

## Required Minimal Fix

Keep the existing behavior for a genuinely unknown new combat, but distinguish it from a partially
recognized saved abyss roster.

- If automatic dual-team mode sees a complete, unique four-member preset, use the existing exact bind path.
- If it sees a partial match to known saved abyss profiles during initial load, hold all character input and
  retry recognition for a short stabilization window. Do not create generic `BaseChar` objects or send Q/E.
- If no saved abyss profile is visible, preserve ordinary generic auto-combat behavior. This is required by
  `test_auto_mode_keeps_generic_detection_for_a_new_unmatched_battle`.
- Once a strict abyss binding exists, preserve the current fail-closed behavior: no generic fallback on any
  incomplete, ambiguous, or unmatched transition frame.

The useful implementation shape is a probe that returns both `VisibleTeamMatch | None` and how many HUD
slots confidently match any saved profile. The new partial-known case should be treated as `pending`, not
as generic. Do not use a fixed half-time or a scene classifier.

## Tests Required

Add focused tests beside `tests/TestTeamPresetGuard.py`:

1. Automatic initial load with three known saved profiles and one low-confidence slot must not call
   `_do_load_char`, reset the Planner to generic characters, or emit an input action.
2. A following complete unique frame must bind the expected preset in actual HUD slot order.
3. A new battle with zero saved-profile matches must still take the existing generic path.
4. Keep the current two-identical-frame handoff test and manual fail-closed test green.

Run from the ASCII runtime junction:

```powershell
cd <local ASCII runtime junction>
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m unittest tests.TestTeamPresetGuard
.\.venv\Scripts\python.exe -m ruff check src/combat/BaseCombatTask.py tests/TestTeamPresetGuard.py
```

## Scope And Evidence Discipline

The next owner may implement Baicang Shift-AOE, refine Chiz's gold-gauge E timing, alter strict routes,
or refactor Planner integration when the change is justified by source, logs, recording review, or new
research. The current bounded normal attacks and yellow/red gate are conservative baselines, not limits.

Keep the following observable guarantees unless a stronger replacement is implemented and tested:

- An old roster can never act on a new roster after an abyss handoff begins.
- A partial known abyss roster cannot receive generic combat input before a complete stable bind.
- A genuine unknown new combat can still use ordinary generic detection.
- Do not commit user `custom_chars/db.json`, logs, recordings, or personal paths.

After the P0 fix passes regression, one new continuous dual-team Abyss recording is still required for the
final Go/No-Go verdict.
