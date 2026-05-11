# Tower Defense: Asset Inventory

This document tracks the physical objects and scripts required for the simulation. All sub-objects must have a **Script Pin** configured to allow the Engine to deploy/update logic.

## 1. The Game Engine (Master Board)
The central hub for resources, levels, and rezzing.
*   **Scripts**:
    *   `TD_GAME_ENGINE.lsl`: The core logic, resource management, and wave controller.
*   **Inventory Assets**:
    *   `GAME_TOWER`: The base object for all defenses.
    *   `GAME_WALKER`: The base object for all enemies.
    *   `TD_GAME_LEVELS`: Notecard containing level data.

## 2. GAME_TOWER (Base Object)
A template prim (usually a small cube or turret base) placed in the Engine's inventory.
*   **Required Script**:
    *   `TD_GAME_PIN.lsl`: Set to a fixed PIN (e.g., `12345`) to allow `llRemoteLoadScriptPin` updates.
*   **Injected Scripts (Production)**:
    *   `TOWER_SCRIPT.lsl`: Handles targeting, energy consumption, and upgrades.
    *   `TOWER_FX.lsl`: Handles visual particles and sounds.

## 3. GAME_WALKER (Base Object)
A template prim (or invisible root for a mesh character) placed in the Engine's inventory.
*   **Required Script**:
    *   `TD_GAME_PIN.lsl`: Configured with the shared PIN.
*   **Injected Scripts (Production)**:
    *   `GAME_WALKER_SCRIPT.lsl`: Handles Keyframed Motion and health logic.

## 4. Visual & Audio Assets (UUIDs)
These are referenced in the scripts or the level notecard.

### Textures (Themes)
*   **Grasslands**: `8dcd0fbf-5800-47b7-4c4d-91b7e419b4f9`
*   **Desert**: `76239773-820d-838e-0453-625292419c8a`
*   **Tundra**: `403328ce-0e42-1e96-7c08-51838d780795`
*   **Volcanic**: `e1e86095-25e2-628d-128a-7889707d9b91`

### Particle Textures
*   **Laser/Beam**: `d26eb61f-2bfc-3ccb-0bcf-22ea7b8dbd0d`
*   **Explosion**: `664886cd-3c22-399e-d434-d395b4dd67a3`

## 5. Deployment Checklist
1. [ ] Set `llSetRemoteScriptAccessPin(12345)` on the Game Board.
2. [ ] Ensure `GAME_TOWER` and `GAME_WALKER` in inventory have `TD_GAME_PIN` inside them.
3. [ ] Configure `TD_GAME_LEVELS` with at least one valid theme row.
4. [ ] Set the Board's `gBoardScale` to match the physical prim size.
