# Tower Defense Subproject - Implementation Plan

## Current Status Analysis

The project consists of a main `GAME_ENGINE`, `GAME_WALKER`, and `GAME_TOWER`. However, there are several disconnects between the current implementation and the design specifications:

1.  **Protocol Mismatch**: 
    - `GAME_WALKER` attempts to fetch board parameters (Scale, Rotation, Path) via `GAME_CHANNEL+5` and `+6`.
    - `GAME_ENGINE` has explicitly removed the listener for these channels.
2.  **Grid Geometry**:
    - Design: 30x50 grid.
    - Implementation: 20x30 grid.
3.  **Resource Balancing**:
    - Design: 1 fund per second.
    - Implementation: 100 funds per second.
4.  **Initialization**:
    - `llRemoteLoadScriptPin` is being used for development-style script injection, but `GAME_WALKER` expects parameters on rez.

## Proposed Improvements

### 1. Modernize State Sharing with Linkset Data (LSD)
Instead of the `QUERY`/`RESPONSE` chat protocol for board parameters (Scale, Rotation, Path), the `GAME_ENGINE` will write these to Linkset Data.
- **Benefit**: Zero chat overhead for static board data. Scripts can read LSD instantly on rez.
- **Pattern**: `llLinksetDataWrite("BOARD_SCALE", (string)gBoardScale)`.

### 2. Standardize Communication Channels
We will align all scripts to the following channel map:
- `BASE_CHANNEL`: Communicated via `start_param` on rez.
- `BASE_CHANNEL + 0`: Engine Status Broadcast (JSON: funds, lives, etc.).
- `BASE_CHANNEL + 1`: Object to Engine Commands (`LIFE Δ -1`, `ENERGY + 10`).
- `BASE_CHANNEL + 2`: Engine/Tower to Walker Commands (`DMG = 10 <uuid>`).
- `BASE_CHANNEL + 3`: UI / Dialogs (randomized per session).

### 3. Engine Refinement
- Update grid to **30x50**.
- Fix the funds increment to **1 per tick**.
- Implement the `LEVELS` notecard parsing properly (it's currently partially implemented).
- Restore/Fix the walker spawning logic to ensure waves of 20 are handled.

### 4. Walker Logic Update
- Update `GAME_WALKER_SCRIPT` to read board parameters from LSD if available, or use a robust chat fallback.
- Ensure `llSetKeyframedMotion` correctly handles the 30x50 grid scaling.

### 5. Tower Specialization
- Ensure the `ENERGYPLANT`, `DEFENSETOWER`, and `ATTACKTOWER` states in `TOWER_SCRIPT` correctly send messages to the engine on `BASE_CHANNEL + 1`.

## Phase 1: Foundation (COMPLETED)
- **Engine Fixes**: Grid size (30x50), Funds (1/tick), LSD broadcast.
- **Walker Fixes**: LSD-based init, synchronized START signal.
- **Accounting**: Automated level advancement via walker removal tracking.

## Phase 2: Game Polish & Scaling (COMPLETED)
- **UI Design**: **NO HUD**. Dialog-only interaction.
- **Sim-Wide Deployment**: Self-transporting objects via `llSetRegionPos` and LSD.
- **Triad Economy**: Implemented Funds, Energy (Battery), and Karma resources.
- **Blueprint Flow**: Two-step building (Foundation -> Blueprint Selection).
- **Balanced Upgrades**: Exponential cost scaling (Base * 2.2^Level).
- **Road Masking**: Dynamic unbuildable zones burned into LSD from the path data.
- **Visual Suite**: Custom particles for Tesla, Sniper, Fog, and Toxic attacks.

## Phase 3: Content & Cartography (COMPLETED)
- **Map Design**: Regional paths designed (Snake, Spiral, Crossroads) in MAPS.txt.
- **Enemy Variety**: Ant, Scorpion, Fly, Drone, Tank, Boss defined in TD_GAME_LEVELS.txt.
- **Level Progression**: 15 levels with full difficulty arc + endless scaling after EOF.
- **Help Card**: TD_HELP.txt notecard delivered in-game via Help button.

## Phase 4: Bug Fixes & Compile Correctness (COMPLETED)
- Removed orphaned dead code from TD_GAME_ENGINE dataserver event.
- Fixed TOWER_FX: missing closing } on PlayProjectileMissEffect.
- Fixed TOWER_SCRIPT: declared TOUCH_FX; fixed BroadcastDamage to send
  "DMG = X <uuid>" on GAME_CHANNEL+2 (was wrong channel+format);
  fixed JSON key "lifes"→"life"; removed dead Ballistic() with undefined
  ScanForWalkers(); added energy+karma drain on each turret shot.
- Fixed GAME_WALKER_SCRIPT: rez race — state initial immediately went
  to active, skipping self-transport; restructured to use
  llGetStartParameter() in fetchParams; added on_rez llResetScript()
  to all persistent states; applied per-level HP/speed from LSD;
  speed now scales path duration; walkers handle "TD GAME STOP".
- Fixed TD_GAME_ENGINE: WALKERS_PER_LEVEL 2→20; DrawRoadMap called
  at game start; level-transition uses timer countdown instead of
  llSleep; game-over check on lives≤0; Pause/Resume flow; Stop works
  from both in-game and paused states; notecard cursor skips comments.

## Conceptual Ideas (Future)
- **Team Play**: The sim-wide scale invites collaborative or competitive team play.
  - *Cooperative*: Multiple players managing a large battlefield, sharing resources via LSD.
  - *Competitive*: Teams building defenses against waves sent by the opposing team.
- **Dynamic Pathing**: Walkers calculating paths based on tower density.
