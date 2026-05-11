/****************************************************
 * Tower Logic Script (Consolidated)
 *
 * This script handles tower behavior and game logic.
 * It supports tower type selection (when unselected) as well
 * as active behaviors (upgrading, selling, toggling, and attacking)
 * after selection.
 *
 * It communicates with the TowerEffects script (assumed on link 2)
 * by sending linked messages with stringly typed effect names.
 *
 * The dialog now includes detailed status information and only
 * shows tower types that the player can afford.
 *
 * The on-object label is set as: "TYPE [level]" followed by DPS for
 * offensive towers.
 ****************************************************/

// Constants
integer GAME_CHANNEL = -12345;
integer CHAT_CHANNEL = -10000;
integer GENERAL_BUILDING = 0; // Unselected
integer ENERGY_PLANT = 1;
integer DEFENSE_TOWER = 2;
integer BALLISTIC_TOWER = 3;
integer SNIPER_TOWER = 4;
integer FOG_TOWER = 5;
integer TOXIC_TOWER = 6;

// Tower names and their minimum cost (parallel lists; index 0 unused)
list TOWER_TYPES = ["Wall", "Energy plant", "Defense tower", "Ballistic", "Sniper", "Fog", "Toxic", "Tesla", "EMP"];
list TOWER_COSTS  = [10, 50, 50, 50, 75, 100, 200, 100, 150];

// Variables
integer debug_skip_rez = TRUE;
integer production = TRUE;
integer gTowerType = GENERAL_BUILDING;  // Initially unselected.
integer gLevel = 1;
integer gFunds;
integer gLifes;
integer gShield;
integer gEnergy;
integer gGameInProgress = FALSE;
key gOwner;

// (We no longer track active/inactive status)
 
// Default powers:
float gAttackPower = 10.0; // for offensive towers
float gShieldPower = 0.5;
float gEnergyPower = 2.0;

// Offensive towers parameters (only used for ballistic/sniper)
float gTurnSpeed = 5.0; // degrees per second
rotation gTargetDirection;
float gTargetAngle;
float gTurretInterval = 0.75; // seconds
float gTurretRange = 2.8;
 
// For sensor damage calculations
float gTurretMissChance = 0.95;

float gVolume = 0.2;
float gRezLevel;

// Effect names (Synchronized with TOWER_FX.lsl)
string TOUCH_FX      = "IDLEEFFECT";
string EMP_FX        = "EMPEFFECT";
string PROJ_FX       = "PROJECTILEEFFECT";
string PROJ_MISS_FX  = "PROJECTILEMISSEFFECT";
string TESLA_FX      = "TESLAEFFECT";
string SNIPER_FX     = "SNIPEREFFECT";
string FOG_FX        = "FOGEFFECT";
string TOXIC_FX      = "TOXICEFFECT";

// Host key (if applicable)
key GAMEHOST;

// --- Utility: Build a dynamic menu of affordable tower types ---
list BuildTowerMenu() {
    list menu = [];
    integer count = llGetListLength(TOWER_TYPES);
    integer i;
    // Start at index 1; index 0 is the placeholder.
    for (i = 1; i < count; ++i) {
        integer cost = llList2Integer(TOWER_COSTS, i);
        if (gFunds >= cost)
            menu += [llList2String(TOWER_TYPES, i)];
    }
    return menu;
}

// Functions for logic
BroadcastDamage(key targetId) {
    llRegionSay(GAME_CHANNEL + 2, "DMG = " + (string)(integer)gAttackPower + " " + (string)targetId);
}

BroadcastValueDelta(string name, integer value) {
    if (GAMEHOST)
        llRegionSayTo(GAMEHOST, GAME_CHANNEL+1, name + " Δ " + (string)value);
    else
        llRegionSay(GAME_CHANNEL+1, name + " Δ " + (string)value);
}

BroadcastValue(string name, integer value) {
    llRegionSay(GAME_CHANNEL+1, name + " = " + (string)value);
}

LevelUp() {
    gLevel++;
    // Update parameters
    gTurretRange *= 1.05;
    gTurretInterval *= 0.98;
    gTurnSpeed *= 1.0025;
    gTurretMissChance *= 0.95;
    gAttackPower *= llSqrt(2.0);
    gShieldPower *= 1.1;
    gEnergyPower *= llSqrt(2.0) + 1.0;    
}

UpgradeTower() {
    if (gFunds >= 500) {
        BroadcastValueDelta("fund", -500);
        gFunds -= 500;
        LevelUp();
        StopEMP();
        llWhisper(0, "tower upgraded to level " + (string)gLevel);
        DisplayHoverText();
    } else {
        llWhisper(0, "not enough funds to upgrade the tower.");
    }
}

SellTower() {
    integer refundAmount = (integer)(0.1 * (gLevel - 1) * 500);
    gFunds += refundAmount;
    BroadcastValueDelta("fund", refundAmount);
    BroadcastValueDelta("tower_sold", 1);
    if(TRUE) state SOLD;
}

Wall() {
    llSetText("WALL\nDurability: " + (string)gLevel, <0.5, 0.5, 0.5>, 1.0);
    // Walls do nothing but exist. 
    // Walkers check for walls in their path via LSD or Sensor.
}

Ballistic() {
    llRegionSay(GAME_CHANNEL + 1, "ENERGY - 1");
    llRegionSay(GAME_CHANNEL + 1, "KARMA - 1");
    list targets = ScanForWalkers();
}

ShowTowerDialog() {
    list menu = [];
    string dialogText = "Tower: " + llList2String(TOWER_TYPES, gTowerType) + "\n";
    dialogText += "Level: " + (string)gLevel + "\n";
    
    if (gTowerType == 0 && gLevel == 0) {
        // BLUEPRINT MODE: Choose a tower type
        dialogText = "CHOOSE BLUEPRINT:\nFunds: " + (string)gFunds + "\nEnergy: " + (string)gEnergy;
        menu = llList2List(TOWER_TYPES, 0, 5); // Show first 6 types (Dialog limit is 12)
        // Add a "Next" button if we have more types
        if (llGetListLength(TOWER_TYPES) > 6) menu += ["Next >>"];
    } else {
        // OPERATIONAL MODE
        integer upgradeCost = (integer)(llList2Integer(TOWER_COSTS, gTowerType) * llPow(2.2, gLevel));
        dialogText += "Next Upgrade: " + (string)upgradeCost + " Funds";
        menu = ["Upgrade", "Sell", "Status"];
    }
    
    llDialog(gOwner, dialogText, menu, CHAT_CHANNEL);
}

EnergyPlant() {
    // Production rate depends on level (Type specialization)
    // Level 1: Solar (5), Level 2: Coal (15), Level 3: Nuclear (50)
    integer rate = 5;
    if (gLevel == 2) rate = 15;
    if (gLevel >= 3) rate = 50;
    llRegionSay(GAME_CHANNEL+1, "ENERGY + " + (string)rate);
}

DefenseTower() {
    llRegionSay(GAME_CHANNEL+1, "life + " + (string)gLevel);
}

BallisticTower(key target) {
    SendEffect(PROJ_FX, "", target);
    llRegionSay(GAME_CHANNEL + 1, "ENERGY - 1");
    llRegionSay(GAME_CHANNEL + 1, "KARMA - 1");
}

SniperTower(key target) {
    SendEffect(SNIPER_FX, "", target);
    llRegionSay(GAME_CHANNEL + 1, "ENERGY - 5");
    llRegionSay(GAME_CHANNEL + 1, "KARMA - 1");
}

TeslaTower(key target) {
    SendEffect(TESLA_FX, "", target);
    llRegionSay(GAME_CHANNEL + 1, "ENERGY - 3");
    llRegionSay(GAME_CHANNEL + 1, "KARMA - 2");
}

FogTower() {
    SendEffect(FOG_FX, "", NULL_KEY);
    llRegionSay(GAME_CHANNEL + 1, "ENERGY - 2");
}

ToxicTower() {
    SendEffect(TOXIC_FX, "", NULL_KEY);
    llRegionSay(GAME_CHANNEL + 1, "ENERGY - 1");
}

// Send a linked message to the effects script (assumed on link 2)
// Format: "EffectName|parameter"
SendEffect(string effectName, string parameter, key target) {
    llMessageLinked(2, 0, effectName + "|" + parameter, target);
}

EMPAttack() {
    // For simplicity, offensive towers (ballistic/sniper) use sensor attack.
    // EMP towers are no longer in a separate group.
    llSensorRepeat("", NULL_KEY, SCRIPTED, 0.0, 0.0, 0.0); // placeholder
}

StopEMP() {
    llSensorRepeat("", NULL_KEY, 0, 0.0, 0.0, 0.0);
}

TurretAttack2() {
    gTargetAngle += gTurnSpeed * gTurretInterval * DEG_TO_RAD;
    if (gTargetAngle > 2*PI)
        gTargetAngle -= 2*PI;
    gTargetDirection = llEuler2Rot(<0.0, 0.0, gTargetAngle>);
    llSetRot(gTargetDirection);
    vector from = llGetPos();
    vector to = from + <gTurretRange, 0.0, 0.0> * gTargetDirection;
    list rayResults = llCastRay(from, to, [RC_MAX_HITS, 1, RC_REJECT_TYPES, RC_REJECT_AGENTS]);
    if (llList2Integer(rayResults, -1) > 0) {
        key targetId = llList2Key(rayResults, 0);
        if (~llSubStringIndex(llKey2Name(targetId), "walker")) {
            if (llFrand(1.0) >= gTurretMissChance) {
                BroadcastDamage(targetId);
                SendEffect(PROJ_FX, "", targetId);
            } else {
                vector targetPos = llList2Vector(rayResults, 1);
                string param = (string)targetPos + "|" + (string)0.9;
                SendEffect(PROJ_MISS_FX, param, NULL_KEY);
            }
        }
    }
}

TurretAttack() {
    gTargetAngle += gTurnSpeed * gTurretInterval * DEG_TO_RAD;
    if (gTargetAngle > 2*PI)
        gTargetAngle -= 2*PI;
    gTargetDirection = llEuler2Rot(<0.0, 0.0, gTargetAngle>);
    llSetRot(gTargetDirection);
    llSensor("", NULL_KEY, ACTIVE|PASSIVE|SCRIPTED, gTurretRange, PI/8.0);
}

AttackTower() {
    // For offensive towers (Ballistic and Sniper), sensor damage is used.
    TurretAttack2();
}

float z;
vector HoverColor() {    
    z += 0.01;
    return <llSin(z), llSin(2.7*z), llSin(8.2*z)>;
}

// Display hover text as "TYPE [level]" plus, for offensive towers, DPS.
DisplayHoverText() {
    string hoverText;
    if(gTowerType == GENERAL_BUILDING) {
        hoverText = "Type not selected";
        llSetText(hoverText, <1,0,0>, 1.0);
        return;
    }
    string typeStr = llList2String(TOWER_TYPES, gTowerType);
    hoverText = typeStr + " [" + (string)gLevel + "]";
    // For offensive towers (Ballistic and Sniper) compute DPS.
    if(gTowerType == BALLISTIC_TOWER || gTowerType == SNIPER_TOWER) {
         integer dps = (integer)(gAttackPower / gTurretInterval);
         hoverText += "\nDPS: " + (string)dps;
    }
    // Optionally add current funds.
    hoverText += "\nFunds: " + (string)gFunds;
    llSetText(hoverText, HoverColor(), 1.0);
}

// Consolidated state: handles both tower type selection and active behavior.
default {
    state_entry() {
        if (llGetObjectName() != "GAME_TOWER")
            state stop;
        llSetText("", ZERO_VECTOR, 0.0);
        if (!production)
            gFunds = 100000;
        CHAT_CHANNEL = -10000 - (integer)llFrand(2e9);
        if (llGetStartParameter())
            GAME_CHANNEL = llGetStartParameter();
        if(TRUE) state tower;
    }
    
    on_rez(integer sequence) {
        // 1. Fetch the Game Channel from LSD
        string chanStr = llLinksetDataRead("GAME_CHANNEL");
        if (chanStr != "") GAME_CHANNEL = (integer)chanStr;
        
        // 2. Fetch our intended Region Position for Sim-Wide support
        string posStr = llLinksetDataRead("REZZ_POS_" + (string)sequence);
        if (posStr != "") {
            llSetRegionPos((vector)posStr);
            llLinksetDataDelete("REZZ_POS_" + (string)sequence);
        }
        
        if(TRUE) state tower;
    }
}

state stop {
    state_entry() {}    
}

state tower {
    state_entry() {
        llListen(CHAT_CHANNEL, "", NULL_KEY, "");
        llListen(GAME_CHANNEL, "", NULL_KEY, "");
        llListen(GAME_CHANNEL+2, "", NULL_KEY, "");
        if (gTowerType == GENERAL_BUILDING) {
            llSetTimerEvent(10);
            string prompt = "Tower selection\nFunds: " + (string)gFunds + "\n" +
                            "Lives: " + (string)gLifes + "\n" +
                            "Shield: " + (string)gShield + "\n" +
                            "Energy: " + (string)gEnergy + "\n" +
                            "Level: " + (string)gLevel + "\n\nSelect type (cost: 50+)";
            llSetText(prompt, <1,0,0>, 1.0);
        } else {
            llSetTimerEvent(gTurretInterval);
            DisplayHoverText();
        }
    }
    
    touch_start(integer num_detected) {
        if (gTowerType == GENERAL_BUILDING) {
            gOwner = llDetectedKey(0);
            SendEffect(TOUCH_FX, "", llGetOwner());
            list menu = BuildTowerMenu(); // Only show affordable types.
            if(llGetListLength(menu) == 0) {
                llInstantMessage(gOwner, "not enough funds for any tower type.");
            } else {
                string selText = "Tower selection\nFunds: " + (string)gFunds + "\n" +
                                 "Lives: " + (string)gLifes + "\n" +
                                 "Shield: " + (string)gShield + "\n" +
                                 "Energy: " + (string)gEnergy + "\n" +
                                 "Level: " + (string)gLevel + "\n\nSelect type (cost: 50+)";
                llDialog(gOwner, selText, menu, CHAT_CHANNEL);
            }
        } else {
            gOwner = llDetectedKey(0);
            ShowTowerDialog();
            SendEffect(PROJ_FX, "", llGetOwner());
        }
    }
    
    listen(integer channel, string name, key id, string message) {
        if (channel == GAME_CHANNEL+2) {
            if (llToLower(message) == "td game stop")
                if(TRUE) state SOLD;
            if (llToLower(message) == "td game pause")
                ; // to-do: pause game.
        }
        if (channel == CHAT_CHANNEL) {
            if (gTowerType == GENERAL_BUILDING) {
                string cmd = llToLower(message);
                integer count = llGetListLength(TOWER_TYPES);
                integer i;
                for(i = 1; i < count; ++i) {
                    string typeStr = llToLower(llList2String(TOWER_TYPES, i));
                    integer cost = llList2Integer(TOWER_COSTS, i);
                    if (cmd == typeStr) {
                        if(gFunds >= cost) {
                            gFunds -= cost;
                            llRegionSay(GAME_CHANNEL + 1, "ENERGY - 25");
                            gTowerType = i; // Set selected type.
                            BroadcastValueDelta("fund", -cost);
                            // No active/inactive toggle now.
                            DisplayHoverText();
                        } else {
                            llInstantMessage(id, "not enough funds");
                        }
                        return;
                    }
                }
            } else {
                string cmd = llToLower(message);
                if (cmd == "upgrade") {
                    UpgradeTower();
                } else if (cmd == "sell") {
                    SellTower();
                } else if (cmd == "halt/continue") {
                    ; //ToggleTower();
                }
            }
        } else if (channel == GAME_CHANNEL) {
            gFunds = (integer)llJsonGetValue(message, ["funds"]);
            gLifes = (integer)llJsonGetValue(message, ["life"]);
            gShield = (integer)llJsonGetValue(message, ["shield"]);
            gEnergy = (integer)llJsonGetValue(message, ["energy"]);
        }
    }
    
    timer() {
        if (gTowerType == GENERAL_BUILDING) {
            llSetText("touch to select\na building type", <1,0,0>, 1.0);
        } else {
            // For simplicity, each tower type now acts on its own.
            if (gTowerType == ENERGY_PLANT) {
                EnergyPlant();
            } else if (gTowerType == DEFENSE_TOWER) {
                DefenseTower();
            } else if (gTowerType == BALLISTIC_TOWER || gTowerType == SNIPER_TOWER) {
                AttackTower();
            } else if (gTowerType == FOG_TOWER) {
                FogTower();
            } else if (gTowerType == TOXIC_TOWER) {
                ToxicTower();
            }
            DisplayHoverText();
        }
    }
    
    sensor(integer num_detected) {
        if (gTowerType == BALLISTIC_TOWER || gTowerType == SNIPER_TOWER) {
            integer i;
            for (i = 0; i < num_detected; i++) {
                key targetId = llDetectedKey(i);
                if (~llSubStringIndex(llDetectedName(i), "walker")) {
                    BroadcastDamage(targetId);
                    SendEffect(PROJ_FX, "", targetId);
                }
            }
        }
    }
}

state SOLD {
    state_entry() {
        StopEMP();
        llSetTimerEvent(0);
        llParticleSystem([]);
        if (production)
            if ((llGetObjectName() == "GAME_TOWER"))
                if (~llSubStringIndex(llGetObjectDesc(), (string)GAME_CHANNEL))
                    llDie();
    }
}
