/****************************************************
 * Tano's Tower Defence - Game Engine Script Module
 *
 * This script implements the main game engine logic:
 *  - Rezzing towers and walkers.
 *  - Broadcasting live game data on the timer.
 *  - Handling touch and chat events.
 *  - Dynamically loading pinned scripts into rezzed objects
 *    via llRemoteLoadScriptPin (optional, for development).
 *
 * Data channels:
 *   GAME_CHANNEL     - Broadcast of live game data.
 *   GAME_CHANNEL+1   - Updates from towers/walkers.
 *
 * Remote Script Pinning:
 *   When enabled, the engine uses the rezzed object's name 
 *   (which should be either GAME_TOWER_OBJECT or GAME_WALKER_OBJECT)
 *   to determine which script(s) to load.
 *
 * New Feature:
 *   Pre-creation of valid tower grid positions. When the board is
 *   touched, the nearest available tower position is computed and
 *   presented to the user via a dialog (with a 'Stop' option).
 ****************************************************/

// ------------------ Constants & Globals ------------------
integer GAME_CHANNEL = -12345;
integer CHAT_CHANNEL = 56789;
integer WALKER_SPAWN_INTERVAL = 5;
integer WALKERS_PER_LEVEL = 20;
string GAME_WALKER_OBJECT = "GAME_WALKER";
string GAME_TOWER_OBJECT = "GAME_TOWER";
list TOWER_PIN_SCRIPTS = ["TOWER_SCRIPT","TOWER_FX"];
list WALKER_PIN_SCRIPTS = ["GAME_WALKER_SCRIPT"]; //, "GAME_WALKER_FX"];

// Board settings: these define the size of the board in local units.
vector gBoardScale = <1.0, 1.0, 1.0>;
rotation gBoardRotation;
vector gSpawnPosition = <0.5, 0.0, 0.0>;
vector gFinishPosition = <0.5, 1.0, 0.0>;

integer gDebugMode = FALSE;         // Debug mode flag
integer gDebugSkipRez = FALSE;      // Skip rezzing objects if TRUE

integer gLastRezTimestamp;
integer gGameWalkerCounter;
integer gLevelCompletedWalkers;     // Count of walkers either killed or arrived
integer gRezSequence = 0;
integer gLevel = 1;                 // Starting level
integer gFunds = 100;
integer gLives = 10;
integer gShield = 100;
integer gEnergy = 100;
integer gMaxEnergy = 500;
integer gKarma = 10000;             // New Alternate Resource
integer gGameInProgress = FALSE;

// Level themes and settings (populated from a notecard)
string gBackgroundTheme;
key gBackgroundTexture;
string gWalkerName;
string gBossWalkerName;
integer gWalkerHP;
integer gBossWalkerHP;
integer gWalkerCount;
integer gBossWalkerCount;
integer gWalkerFunds;
integer gBossWalkerFunds;
float gWalkerSpeed;
string gMusicTrack;
key gExplosionTexture;

// Score scaling constants:
integer MAX_LEVELS = 20;
integer MAX_FUNDS = 5000;
integer MAX_ENERGY = 1000;
vector gScoreVector = <0.0, 0.0, 0.0>;

// Touch and Grid settings:
vector gTouchPos;
float gIntendX;
float gIntendY;
integer gGridSizeX = 30;
integer gGridSizeY = 50;
integer gGridOptions = 0x52;  // Bit flags; low 4 bits = border

list gRezzedTowers;
list gOccupiedSquares;
integer gLevelTransitionCountdown = -1;

key gLevelsNotecard = "TD_GAME_LEVELS";
integer gNotecardLine = 0;    // current read position; advances past comments/blanks
key gNotecardQuery = NULL_KEY;

// Walker path waypoints in 0..100 scale — mirrors GAME_WALKER_SCRIPT MOTION list.
// Used once at game start to burn road squares into LSD via DrawRoadMap().
list MOTION_PATH_DATA = [
    1,1, 10,10, 30,20, 60,20, 70,10, 80,20, 60,30, 85,40,
    60,50, 50,50, 75,70, 35,80, 40,85, 65,80, 80,85, 90,90, 95,95
];

// Precomputed list is removed to save memory on 30x50 grids.
// Validity is now checked on-the-fly.

// ----------------- Remote Script Pinning Globals -----------------
integer gEnableScriptPinning = TRUE;  // Toggle remote script pinning (TRUE = enabled)
integer REMOTE_PIN = 7654312;         // Remote access pin (must match the setpin script)


// -------------------- Functions --------------------

// Draw the path into LSD to prevent building towers on it.
DrawRoadMap(list motion) {
    integer i;
    for (i = 0; i < llGetListLength(motion); i += 2) {
        integer x = llList2Integer(motion, i) / 3; // Approx scale to 30
        integer y = llList2Integer(motion, i + 1) / 2; // Approx scale to 50
        // Mark a 2x2 area around each path node as road
        integer dx;
        for (dx = -1; dx <= 1; ++dx) {
            integer dy;
            for (dy = -1; dy <= 1; ++dy) {
                llLinksetDataWrite("ROAD_" + (string)(x+dx) + "_" + (string)(y+dy), "1");
            }
        }
    }
}
// Helper to check if a grid coordinate is a valid tower position.
integer IsValidTowerPosition(integer x, integer y) {
    integer border = gGridOptions & 0xF;
    if (x < border || x >= gGridSizeX - border || y < border || y >= gGridSizeY - border)
        return FALSE;
    
    // Check parity conditions.
    integer isOddX = x % 2;
    integer isOddY = y % 2;
    if (((gGridOptions & 0x10) && !isOddX) ||
        ((gGridOptions & 0x20) && isOddX) ||
        ((gGridOptions & 0x40) && !isOddY) ||
        ((gGridOptions & 0x80) && isOddY) ||
        ((gGridOptions & 0x100) && ((x + y) % 2 == 0))) {
        return FALSE;
    }
    
    // CHECK ROAD MASK: No building on the road!
    if (llLinksetDataRead("ROAD_" + (string)x + "_" + (string)y) == "1") {
        return FALSE;
    }
    
    return TRUE;
}

// Given a touch grid coordinate (tx, ty), find the nearest valid tower position
// from the precomputed list.
vector FindNearestTowerPosition(float tx, float ty) {
    // scale from UV map to gridsize
    integer gridX = (integer)(tx * gGridSizeX);
    integer gridY = (integer)(ty * gGridSizeY);
    
    // Search in a small radius around the touch point for the nearest VALID position.
    // This is much faster and memory-efficient than storing all 1500 possibilities.
    integer bestX = -1;
    integer bestY = -1;
    float bestDist = 1e9;
    
    integer r;
    for (r = 0; r < 5; ++r) { // check up to 5 squares away
        integer x;
        for (x = gridX - r; x <= gridX + r; ++x) {
            integer y;
            for (y = gridY - r; y <= gridY + r; ++y) {
                if (IsValidTowerPosition(x, y)) {
                    float dx = (float)x - (tx * gGridSizeX);
                    float dy = (float)y - (ty * gGridSizeY);
                    float dist = dx*dx + dy*dy;
                    if (dist < bestDist) {
                        bestDist = dist;
                        bestX = x;
                        bestY = y;
                    }
                }
            }
        }
        if (bestX != -1) jump found;
    }
    
    @found;
    if (bestX == -1) return ZERO_VECTOR;
    
    return <(float)bestX / gGridSizeX, (float)bestY / gGridSizeY, 0.0>;
}

// Rez an object from inventory. The pos parameter is a relative coordinate (values 0..1)
// that is multiplied by gBoardScale, then converted to region coordinates using the root prim's position.
// Rez an object from inventory. 
// For Sim-Wide support, objects are rezzed at the board's position and 
// self-transport to their target via llSetRegionPos, using LSD to communicate the destination.
RezObject(string objName, vector relPos, rotation rot) {
    // 1. Calculate the final region coordinates.
    // relPos is 0..1 relative to board size.
    vector localPos = < (relPos.x - 0.5) * gBoardScale.x, (relPos.y - 0.5) * gBoardScale.y, relPos.z >;
    vector targetRegionPos = llGetPos() + (localPos * llGetRot());
    
    // 2. Prepare the sequence number for LSD communication.
    gRezSequence++;
    if (gRezSequence > 1000000) gRezSequence = 1; // Wrap around
    
    // 3. Write target position to LSD so the object can "self-transport" on rez.
    llLinksetDataWrite("REZZ_POS_" + (string)gRezSequence, (string)targetRegionPos);
    
    // 4. Rez the object at the BOARD's position (always within 10m range).
    if (llGetInventoryType(objName) != INVENTORY_OBJECT) {
         llOwnerSay("INVENTORY " + objName + " not found");
         return;
    }
    
    if (!gDebugSkipRez) {
         // Passing the sequence number as start_param
         llRezObject(objName, llGetPos() + <0,0,1>, ZERO_VECTOR, rot * llGetRot(), gRezSequence);
    }
}

// Rez a game walker. We pass a relative coordinate.
RezGameWalker() {
    // The walker should appear 1.0 unit above the board.
    vector spawnPos = <0.0, 0.0, 1.0>;
    rotation spawnRot = llGetRot();
    RezObject(GAME_WALKER_OBJECT, spawnPos, spawnRot);
}

// Rez a game tower.
RezGameTower() {
    // Use gIntendX and gIntendY (set via touch) as grid coordinates.
    // Convert these to relative coordinates (normalized over grid size).
    vector relPos = <gIntendX, gIntendY, 0.0>;
    
    if (gFunds >= 50 * gLevel) {
         gFunds -= 50 * gLevel;
         RezObject(GAME_TOWER_OBJECT, relPos, llGetRot());
         
         // Record wall position in LSD for walker interactions
         integer gx = (integer)(relPos.x * gGridSizeX);
         integer gy = (integer)(relPos.y * gGridSizeY);
         llLinksetDataWrite("WALL_" + (string)gx + "_" + (string)gy, "1");
    } else {
         llOwnerSay("Not enough funds to build a tower.");
    }
}

// Advance the notecard cursor to the next data line for the current level.
ReadNextLevelLine() {
    if (llGetInventoryType(gLevelsNotecard) == INVENTORY_NOTECARD)
        gNotecardQuery = llGetNotecardLine(gLevelsNotecard, gNotecardLine++);
}

ReadLevelData(integer level) {
    // level param kept for signature compat; actual read uses gNotecardLine cursor
    ReadNextLevelLine();
}

// Update the score vector based on level, time efficiency, and resource management.
UpdateScoreVector() {
    float normalizedLevel = (float)gLevel / (float)MAX_LEVELS;
    gScoreVector.x = normalizedLevel;

    integer timeTaken = llGetUnixTime() - gLastRezTimestamp;
    integer maxAllowableTime = WALKER_SPAWN_INTERVAL * WALKERS_PER_LEVEL;
    float normalizedTime = 1.0 - ((float)timeTaken / (float)maxAllowableTime);
    gScoreVector.y = normalizedTime;

    float normalizedFunds = (float)gFunds / (float)MAX_FUNDS;
    float normalizedEnergy = (float)gEnergy / (float)MAX_ENERGY;
    gScoreVector.z = (normalizedFunds + normalizedEnergy) / 2.0;
}

// Update the hover text on the game board.
UpdateHoverText() {
    string hoverText = (string)[
         "[R] Level: ", gLevel,
         "\n[G] Funds: ", gFunds,
         "\n[B] Lives: ", gLives
    ];
    llSetText(hoverText, gScoreVector, 1.0);
}

// Broadcast game data as a JSON string.
string BroadcastData() {
    string data = llList2Json(JSON_OBJECT, [
         "level", gLevel,
         "funds", gFunds,
         "life", gLives,
         "shield", gShield,
         "energy", gEnergy,
         "scale", gBoardScale,
         "rot", gBoardRotation,
         "spawn", gSpawnPosition
    ]);
    return data;
}

BuildingTowerProgress(integer percentage) {
    llSetText ((string)["Constructing Tower ",percentage,"%"], <255,128,64>, 1.0);
}

// -------------------- Event Handlers --------------------
default {
    state_entry() {
        gBoardScale=llGetScale();
         // Initialize channels and listeners.
          GAME_CHANNEL = (-10000 - (integer)llFrand(2e9)) & 0xFFFFF000;
          llLinksetDataWrite("GAME_CHANNEL", (string)GAME_CHANNEL);
          CHAT_CHANNEL = 10000 + (integer)llFrand(2e5);
         llListen(CHAT_CHANNEL, "", NULL_KEY, "");
         llListen(GAME_CHANNEL + 1, "", NULL_KEY, "");
         // Removed listener for GAME_CHANNEL+5.

         // Initial parameter setup removed precompute.
         
         // Write board parameters to Linkset Data for walkers/towers
         llLinksetDataWrite("BOARD_POS", (string)llGetPos());
         llLinksetDataWrite("BOARD_SCALE", (string)gBoardScale);
         llLinksetDataWrite("BOARD_ROT", (string)llGetRot());
         llLinksetDataWrite("SPAWN_POS", (string)gSpawnPosition);
         llLinksetDataWrite("FINISH_POS", (string)gFinishPosition);
         
         // Load default level data.
         ReadLevelData(0);
    }
    
    touch_start(integer num_detected) {
         integer i;
         for (i = 0; i < num_detected; ++i) {
              string text;
              list buttons;
              
              // Present context-sensitive menu
              if (!gGameInProgress) {
                   if (gLevel > 1) {
                       text = "Game paused — Level " + (string)gLevel +
                              "\nFunds: " + (string)gFunds + "  Lives: " + (string)gLives;
                       buttons = ["Resume", "Stop", "Help"];
                   } else {
                       text = "TT Tower Defence\n\nSelect an option:";
                       buttons = ["Start", "Help"];
                   }
              } else {
                   // Game is in progress: compute the touched grid coordinate.
                   vector touchPos = llDetectedTouchST(i);
                   // Calculate grid coordinates (integers) from the touch relative position.
                   //this so wrong..
                    //integer clickX = (integer)(touchPos.x * gGridSizeX);
                    //integer clickY = (integer)(touchPos.y * gGridSizeY);
                     // Find the nearest valid tower position.                     
                    //vector nearestPos = FindNearestTowerPosition(clickX, clickY);
                   vector nearestPos = FindNearestTowerPosition(touchPos.x, touchPos.y);
                   gIntendX = nearestPos.x;
                   gIntendY = nearestPos.y;
                   text = "Nearest tower pos: (" + (string)gIntendX + "," + (string)gIntendY + ")" +
                          "\nFunds: " + (string)gFunds + "  Lives: " + (string)gLives +
                          "\nEnergy: " + (string)gEnergy + "  Karma: " + (string)gKarma;
                   buttons = ["Place Tower", "Pause", "Stop"];
              }
              llDialog(llDetectedKey(i), text, buttons, CHAT_CHANNEL);
         }
    }
    
    listen(integer channel, string name, key id, string message) {
         // Menu dialog responses.
         if (channel == CHAT_CHANNEL) {
              if (message == "Start") {
                   gGameInProgress = TRUE;
                   gLastRezTimestamp = llGetUnixTime();
                   gLevel = 1;
                   gFunds = 100; gLives = 10; gShield = 100; gEnergy = 100; gKarma = 10000;
                   gLevelCompletedWalkers = 0; gGameWalkerCounter = 0;
                   gNotecardLine = 0; gLevelTransitionCountdown = -1;
                   llLinksetDataReset();
                   llLinksetDataWrite("GAME_CHANNEL", (string)GAME_CHANNEL);
                   llLinksetDataWrite("BOARD_POS",   (string)llGetPos());
                   llLinksetDataWrite("BOARD_SCALE", (string)gBoardScale);
                   llLinksetDataWrite("BOARD_ROT",   (string)llGetRot());
                   llLinksetDataWrite("SPAWN_POS",   (string)gSpawnPosition);
                   llLinksetDataWrite("FINISH_POS",  (string)gFinishPosition);
                   DrawRoadMap(MOTION_PATH_DATA);
                   llSetTimerEvent(1);
                   ReadLevelData(1);
                   llSay(0, "The game has started!");
                   llRegionSay(GAME_CHANNEL, "START");
              } else if (message == "Resume") {
                   gGameInProgress = TRUE;
                   gLastRezTimestamp = llGetUnixTime();
                   llSetTimerEvent(1);
                   llSay(0, "Game resumed.");
                   llRegionSay(GAME_CHANNEL, "START");
              } else if (message == "Help") {
                   if (llGetInventoryType("TD_HELP") == INVENTORY_NOTECARD)
                       llGiveInventory(llDetectedKey(0), "TD_HELP");
                   else
                       llInstantMessage(llDetectedKey(0), "No help card found.");
              } else if (message == "Pause") {
                   gGameInProgress = FALSE;
                   llSetTimerEvent(0);
                   llSay(0, "Game paused. Touch board to resume.");
              } else if (message == "Stop") {                   
                   if (gGameInProgress) {
                        //llSay(0, "Tower placement canceled.");
                        gGameInProgress = FALSE;
                        llSetTimerEvent(0);
                        llSay(0, "The game was forcefully stopped!");
                        llRegionSay (GAME_CHANNEL+2, "TD GAME STOP");
                        llSleep (1.0);
                        //llSay(0, "Resetting in 30 seconds.");
                        //llSleep(30.0);
                        llResetScript();
                   }
              } else if (message == "Place Tower") {
                   // Use the precomputed nearest grid coordinates.
                   RezGameTower();
              }
         }
         // Game data updates from towers and walkers.
         else if (channel == GAME_CHANNEL + 1) {
              list tokens = llParseString2List(llToUpper(message), [" "], []);
              string action = llList2String(tokens, 0);
              string operator = llList2String(tokens, 1);
              string value = llList2String(tokens, 2);
              integer isDelta = (operator == "Δ" || operator == "+" || operator == "-");
               if (operator == "-") value = "-" + value;
              if (!isDelta && operator != "=")
                   return;
              integer intValue = (integer)value;
              if (action == "LIFE") {
                   if (isDelta)
                        gLives += intValue;
                   else
                        gLives = intValue;
                   if (gLives <= 0) {
                        gLives = 0;
                        llSay(0, "GAME OVER! You reached level " + (string)gLevel + ". Final score: " +
                              (string)gFunds + " funds remaining.");
                        llRegionSay(GAME_CHANNEL + 2, "TD GAME STOP");
                        gGameInProgress = FALSE;
                        llSetTimerEvent(0);
                        gLevel = 0; // prevent Resume offer
                        llSleep(3.0);
                        llResetScript();
                   }
              } else if (action == "FUND") {
                   if (isDelta)
                        gFunds += intValue;
                   else
                        gFunds = intValue;
              } else if (action == "SHIELD") {
                   if (isDelta)
                        gShield += intValue;
                   else
                        gShield = intValue;
               } else if (action == "ENERGY") {
                    if (isDelta) {
                         gEnergy += intValue;
                         if (gEnergy > gMaxEnergy) gEnergy = gMaxEnergy;
                         if (gEnergy < 0) gEnergy = 0;
                    } else gEnergy = intValue;
                    llOwnerSay("Energy: " + (string)gEnergy + "/" + (string)gMaxEnergy);
               } else if (action == "KARMA") {
                    if (isDelta) gKarma += intValue;
                    else gKarma = intValue;
                    llOwnerSay("Karma: " + (string)gKarma);
               } else if (action == "WALKER_REMOVED") {
                    gLevelCompletedWalkers++;
                    llOwnerSay("Progress: " + (string)gLevelCompletedWalkers + "/" + (string)WALKERS_PER_LEVEL);
                    if (gLevelCompletedWalkers >= WALKERS_PER_LEVEL) {
                        llSay(0, "Level " + (string)gLevel + " complete! Next level in 10 seconds...");
                        gLevel++;
                        gLevelCompletedWalkers = 0;
                        gGameWalkerCounter = 0;
                        gLevelTransitionCountdown = 10;
                    }
               } else if (action == "WALL_DAMAGE") {
                    string coord = llList2String(tokens, 1);
                    llLinksetDataDelete("WALL_" + coord);
               }
         }
    }
    
    timer() {
         gFunds += 1;

         if (gLevelTransitionCountdown > 0) {
             gLevelTransitionCountdown--;
             if (gLevelTransitionCountdown == 0) {
                 gLevelTransitionCountdown = -1;
                 ReadLevelData(gLevel);
                 gLastRezTimestamp = llGetUnixTime();
             }
             UpdateHoverText();
             return;
         }

         integer currentTime = llGetUnixTime();
         if (currentTime - gLastRezTimestamp >= WALKER_SPAWN_INTERVAL && gGameWalkerCounter < WALKERS_PER_LEVEL) {
             llOwnerSay("Rezzing a walker");
             RezGameWalker();
             gGameWalkerCounter++;
             gLastRezTimestamp = currentTime;
         }
         
         // Broadcast game state every 3 seconds.
         if (llGetUnixTime() % 3 == 0) {
              llRegionSay(GAME_CHANNEL, BroadcastData());
              UpdateHoverText();
         }
         
         UpdateScoreVector();
    }
    
    // When an object is rezzed, retrieve its name to determine which scripts to load.
    object_rez(key id) {
         if (gEnableScriptPinning) {
              // Retrieve the object's name.
              string objName = llKey2Name(id);
              list pinScripts = [];
              if (objName == GAME_TOWER_OBJECT) {
                  pinScripts = TOWER_PIN_SCRIPTS;
                  BuildingTowerProgress (10);
              } else if (objName == GAME_WALKER_OBJECT) {
                  pinScripts = WALKER_PIN_SCRIPTS;
              } else {
                  llOwnerSay("Unknown object rezzed: " + objName);
              }
              integer count = llGetListLength(pinScripts);
              integer j;
              for (j = 0; j < count; ++j) {
                   string scriptName = llList2String(pinScripts, j);
                   llRemoteLoadScriptPin(id, scriptName, REMOTE_PIN, TRUE, GAME_CHANNEL);
                   if (objName == GAME_TOWER_OBJECT)                  
                        BuildingTowerProgress (10);
              }
         }
    }
    
    dataserver(key query_id, string data) {
        if (query_id != gNotecardQuery) return; // stale read
        if (data == EOF) {
            // Past the last defined level — scale up for endless play
            WALKERS_PER_LEVEL = llMin(50, llFloor(WALKERS_PER_LEVEL * 1.2));
            gWalkerHP = (integer)(gWalkerHP * 1.3);
            llLinksetDataWrite("WALKER_HP",    (string)gWalkerHP);
            llLinksetDataWrite("WALKER_SPEED", (string)gWalkerSpeed);
            llSay(0, "Endless! Level " + (string)gLevel +
                  ": " + (string)WALKERS_PER_LEVEL + " walkers, HP=" + (string)gWalkerHP);
            return;
        }
        // Skip blank lines and comments — read the next line
        string trimmed = llStringTrim(data, STRING_TRIM);
        if (trimmed == "" || llGetSubString(trimmed, 0, 0) == "#") {
            ReadNextLevelLine();
            return;
        }

        list params = llParseString2List(trimmed, [","], []);
        integer i;
        for (i = 0; i < llGetListLength(params); ++i) {
            list kv = llParseString2List(llList2String(params, i), ["="], []);
            string k = llStringTrim(llList2String(kv, 0), STRING_TRIM);
            string v = llStringTrim(llList2String(kv, 1), STRING_TRIM);
            if      (k == "theme") gBackgroundTheme = v;
            else if (k == "num")   { WALKERS_PER_LEVEL = (integer)v; gWalkerCount = (integer)v; }
            else if (k == "type")  gWalkerName = v;
            else if (k == "hp")    gWalkerHP = (integer)v;
            else if (k == "speed") gWalkerSpeed = (float)v;
        }
        llLinksetDataWrite("WALKER_HP",    (string)gWalkerHP);
        llLinksetDataWrite("WALKER_SPEED", (string)gWalkerSpeed);
        llSay(0, "Level " + (string)gLevel + ": " + (string)WALKERS_PER_LEVEL +
              " " + gWalkerName + " walkers, HP=" + (string)gWalkerHP +
              ", speed=" + (string)gWalkerSpeed);
    }
}
