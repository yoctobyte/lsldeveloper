// Tower Logic Script

integer GAME_CHANNEL = -12345;
integer CHAT_CHANNEL = -10000;
integer GENERAL_BUILDING = 0;
integer ENERGY_PLANT = 1;
integer DEFENSE_TOWER = 2;
integer BALLISTIC_TOWER = 3;
integer SNIPER_TOWER = 4;
integer FOG_TOWER = 5;
integer TOXIC_TOWER = 6;
integer TESLA_TOWER = 7;
integer EMP_TOWER   = 8;

// Damage type bitflags — packed into every attack message so walkers apply affinity
integer DTYPE_BALLISTIC = 0x01;
integer DTYPE_LASER     = 0x02;
integer DTYPE_EMP       = 0x04;
integer DTYPE_POISON    = 0x08;
integer DTYPE_DIGITAL   = 0x10;
integer DTYPE_PIERCING  = 0x20;

// Damage type per tower index (index = tower type constant)
// GENERAL=0, PLANT=0, DEFENSE=0, BALLISTIC=1, SNIPER=LASER|PIERCING=34,
// FOG=POISON=8, TOXIC=POISON=8, TESLA=EMP=4, EMP=4
list TOWER_DTYPES = [0, 0, 0, 1, 34, 8, 8, 4, 4];

// Tower names and blueprint purchase cost (index = type constant)
list TOWER_TYPES = ["Wall", "Energy plant", "Defense tower", "Ballistic", "Sniper", "Fog", "Toxic", "Tesla", "EMP"];
list TOWER_COSTS = [10, 50, 50, 50, 75, 100, 200, 100, 150];

// Base stats per type — all scale mathematically per level.
// Attack types: base damage, range (m), fire interval (s).
// Energy plant: base output per tick (every BASE_INTERVAL seconds).
// Defense tower: base lives restored per tick (every BASE_INTERVAL seconds).
list BASE_DAMAGE   = [0.0, 0.0, 0.0, 10.0, 25.0,  4.0,  4.0, 18.0, 0.0];
list BASE_RANGE    = [0.0, 0.0, 0.0,  2.8,  4.0,  3.0,  2.5,  3.5, 5.0];
list BASE_INTERVAL = [0.0, 5.0,60.0, 0.75,  2.0,  3.0,  1.0,  1.5,10.0];
list ENERGY_COST   = [0,   0,   0,   1,     5,     2,    1,    3,   0  ];

// Upgrade cost formula: TOWER_COSTS[type] * UPGRADE_BASE^level
float UPGRADE_BASE = 1.8;

// Variables
integer production = TRUE;
integer gTowerType = GENERAL_BUILDING;
integer gLevel = 1;
integer gFunds;
integer gLifes;
integer gEnergy;
key gOwner;

float gAttackPower;
float gTurnSpeed = 5.0;
rotation gTargetDirection;
float gTargetAngle;
float gTurretInterval = 0.75;
float gTurretRange = 2.8;
float gTurretMissChance = 0.95;
float gTowerHealth = 1.0;   // 1.0 = full, 0.0 = destroyed; scales attack effectiveness
integer gPendingAoEDmg;     // set before llSensor() for AoE pass-through to sensor()
integer gPendingAoEDtype;   // dtype for the pending AoE pass
integer gDamageType;        // current tower damage type from TOWER_DTYPES

// Effect names (must match TOWER_FX.lsl)
string TOUCH_FX     = "IDLEEFFECT";
string PROJ_FX      = "PROJECTILEEFFECT";
string PROJ_MISS_FX = "PROJECTILEMISSEFFECT";
string TESLA_FX     = "TESLAEFFECT";
string SNIPER_FX    = "SNIPEREFFECT";
string FOG_FX       = "FOGEFFECT";
string TOXIC_FX     = "TOXICEFFECT";

// ---- Utility -------------------------------------------------------

list BuildTowerMenu() {
    list menu = [];
    integer i;
    for (i = 1; i < llGetListLength(TOWER_TYPES); ++i) {
        if (gFunds >= llList2Integer(TOWER_COSTS, i))
            menu += [llList2String(TOWER_TYPES, i)];
    }
    return menu;
}

// Broadcast a delta to the engine on GAME_CHANNEL+1.
// Use positive value for gains, negative for costs — engine handles both.
BroadcastDelta(string name, integer value) {
    llRegionSay(GAME_CHANNEL + 1, name + " + " + (string)value);
}

SendEffect(string effectName, string parameter, key target) {
    llMessageLinked(2, 0, effectName + "|" + parameter, target);
}

// ---- Stat formulae (call after gLevel or gTowerType changes) -------

RecalcStats() {
    float base    = llList2Float(BASE_DAMAGE,   gTowerType);
    float range   = llList2Float(BASE_RANGE,    gTowerType);
    float interval= llList2Float(BASE_INTERVAL, gTowerType);
    float lv      = (float)(gLevel - 1);

    // Damage: grows 50% per level
    gAttackPower = base * llPow(1.5, lv);

    // Range: +0.2 m per level (linear — keeps gameplay readable)
    gTurretRange = range + 0.2 * lv;

    // Fire/tick interval: shrinks 10% per level, floored at 0.2 s
    // Energy plants floor at 2 s; defence tower floors at 10 s
    gTurretInterval = interval * llPow(0.9, lv);
    if (gTowerType == ENERGY_PLANT)  gTurretInterval = llFmax(2.0,  gTurretInterval);
    else if (gTowerType == DEFENSE_TOWER) gTurretInterval = llFmax(10.0, gTurretInterval);
    else                             gTurretInterval = llFmax(0.2,  gTurretInterval);

    // Miss chance improves with level
    gTurretMissChance = llFmax(0.0, 0.95 * llPow(0.9, lv));
}

integer UpgradeCost() {
    return (integer)(llList2Integer(TOWER_COSTS, gTowerType) * llPow(UPGRADE_BASE, gLevel));
}

// ---- Tower actions -------------------------------------------------

UpgradeTower() {
    integer cost = UpgradeCost();
    if (gFunds >= cost) {
        BroadcastDelta("FUND", -cost);
        gFunds -= cost;
        gLevel++;
        RecalcStats();
        llSetTimerEvent(gTurretInterval);
        DisplayHoverText();
        llWhisper(0, "Upgraded to level " + (string)gLevel + ".");
    } else {
        llWhisper(0, "Need " + (string)cost + " funds (have " + (string)gFunds + ").");
    }
}

SellTower() {
    // Refund 10% of total upgrade investment
    integer invested = 0;
    integer i;
    for (i = 1; i < gLevel; ++i)
        invested += (integer)(llList2Integer(TOWER_COSTS, gTowerType) * llPow(UPGRADE_BASE, i));
    integer refund = invested / 10;
    BroadcastDelta("FUND", refund);
    state SOLD;
}

RepairTower() {
    float damage = 1.0 - gTowerHealth;
    if (damage < 0.01) { llWhisper(0, "Already at full health."); return; }
    integer cost = (integer)(damage * llList2Integer(TOWER_COSTS, gTowerType) * 10);
    if (gFunds >= cost) {
        BroadcastDelta("FUND", -cost);
        gFunds -= cost;
        gTowerHealth = 1.0;
        DisplayHoverText();
        llWhisper(0, "Repaired.");
    } else {
        llWhisper(0, "Need " + (string)cost + " funds to repair.");
    }
}

EnergyPlant() {
    // Output doubles every level (2.0^(level-1) growth, base 10/tick)
    integer output = (integer)(10.0 * llPow(2.0, (float)(gLevel - 1)));
    BroadcastDelta("ENERGY", output);
}

DefenseTower() {
    // Restores 1 life per level per tick
    BroadcastDelta("LIFE", gLevel);
}

// AoE: Fog and Toxic — broad slow-damage pulse via sensor
AoEPulse(string effectName, integer energyCost) {
    if (gTowerHealth <= 0.0 || gEnergy < energyCost) return;
    BroadcastDelta("ENERGY", -energyCost);
    gEnergy -= energyCost;
    SendEffect(effectName, "", NULL_KEY);
    gPendingAoEDmg   = (integer)(gAttackPower * gTowerHealth);
    gPendingAoEDtype = gDamageType;
    llSensor("GAME_WALKER", NULL_KEY, SCRIPTED | ACTIVE | PASSIVE, gTurretRange, PI);
}

// Raycast attack for single-target towers (Ballistic, Sniper, Tesla)
TurretAttack() {
    if (gTowerHealth <= 0.0) return;

    integer energyCost = llList2Integer(ENERGY_COST, gTowerType);
    if (gEnergy < energyCost) {
        llSetText("LOW ENERGY", <1.0, 0.5, 0.0>, 1.0);
        return;
    }

    gTargetAngle += gTurnSpeed * gTurretInterval * DEG_TO_RAD;
    if (gTargetAngle > TWO_PI) gTargetAngle -= TWO_PI;
    gTargetDirection = llEuler2Rot(<0.0, 0.0, gTargetAngle>);
    llSetRot(gTargetDirection);

    vector from = llGetPos();
    vector to   = from + <gTurretRange, 0.0, 0.0> * gTargetDirection;
    list ray = llCastRay(from, to, [RC_MAX_HITS, 1, RC_REJECT_TYPES, RC_REJECT_AGENTS]);

    if (llList2Integer(ray, -1) > 0) {
        key targetId = llList2Key(ray, 0);
        if (~llSubStringIndex(llKey2Name(targetId), "walker")) {
            BroadcastDelta("ENERGY", -energyCost);
            BroadcastDelta("KARMA", -1);
            gEnergy -= energyCost;

            // Combat wear: 0.2% health per shot
            gTowerHealth -= 0.002;
            if (gTowerHealth < 0.0) gTowerHealth = 0.0;

            integer effectiveDmg = (integer)(gAttackPower * gTowerHealth);

            if (llFrand(1.0) >= gTurretMissChance) {
                llRegionSay(GAME_CHANNEL + 2,
                    "DMG = " + (string)effectiveDmg + " " + (string)targetId + " " + (string)gDamageType);
                if (gTowerType == TESLA_TOWER)
                    llRegionSay(GAME_CHANNEL + 2, "SLOW = 0.3 3.0 " + (string)targetId);
                string fx = PROJ_FX;
                if (gTowerType == SNIPER_TOWER) fx = SNIPER_FX;
                else if (gTowerType == TESLA_TOWER) fx = TESLA_FX;
                SendEffect(fx, "", targetId);
            } else {
                SendEffect(PROJ_MISS_FX, (string)llList2Vector(ray, 1) + "|0.9", NULL_KEY);
            }
        }
    }
}

float z;
vector HoverColor() {
    z += 0.01;
    return <llSin(z), llSin(2.7*z), llSin(8.2*z)>;
}

DisplayHoverText() {
    if (gTowerType == GENERAL_BUILDING) {
        llSetText("touch to select type", <1,0,0>, 1.0);
        return;
    }
    if (gTowerHealth <= 0.0) {
        llSetText("DESTROYED\ntouch to repair", <0.6,0,0>, 1.0);
        return;
    }
    string t = llList2String(TOWER_TYPES, gTowerType) + " [" + (string)gLevel + "]";
    if (gTowerType == BALLISTIC_TOWER || gTowerType == SNIPER_TOWER || gTowerType == TESLA_TOWER) {
        t += "\nDPS: " + (string)(integer)(gAttackPower * gTowerHealth / gTurretInterval);
    } else if (gTowerType == ENERGY_PLANT) {
        t += "\nOutput: " + (string)(integer)(10.0 * llPow(2.0, (float)(gLevel-1))) + "/tick";
    }
    if (gTowerHealth < 0.99)
        t += "\nHP: " + (string)(integer)(gTowerHealth * 100.0) + "%";
    t += "\nFunds: " + (string)gFunds;
    llSetText(t, HoverColor(), 1.0);
}

ShowTowerDialog() {
    string txt = llList2String(TOWER_TYPES, gTowerType) +
                 " Lv" + (string)gLevel +
                 "\nHP: " + (string)(integer)(gTowerHealth * 100.0) + "%" +
                 "\nFunds: " + (string)gFunds +
                 "\nUpgrade: " + (string)UpgradeCost() + " funds";
    list menu = ["Upgrade", "Sell"];
    if (gTowerHealth < 0.99) {
        float dmg = 1.0 - gTowerHealth;
        integer rcost = (integer)(dmg * llList2Integer(TOWER_COSTS, gTowerType) * 10);
        txt += "\nRepair: " + (string)rcost + " funds";
        menu += ["Repair"];
    }
    llDialog(gOwner, txt, menu, CHAT_CHANNEL);
}

// ---- States --------------------------------------------------------

default {
    state_entry() {
        if (llGetObjectName() != "GAME_TOWER") state stop;
        llSetText("", ZERO_VECTOR, 0.0);
        if (!production) gFunds = 100000;
        CHAT_CHANNEL = -10000 - (integer)llFrand(2e9);
        // GAME_CHANNEL from LSD (most reliable) or start_param fallback
        string chanStr = llLinksetDataRead("GAME_CHANNEL");
        if (chanStr != "") GAME_CHANNEL = (integer)chanStr;
        else if (llGetStartParameter()) GAME_CHANNEL = llGetStartParameter();
        state tower;
    }

    on_rez(integer sequence) {
        string chanStr = llLinksetDataRead("GAME_CHANNEL");
        if (chanStr != "") GAME_CHANNEL = (integer)chanStr;
        string posStr = llLinksetDataRead("REZZ_POS_" + (string)sequence);
        if (posStr != "") {
            llSetRegionPos((vector)posStr);
            llLinksetDataDelete("REZZ_POS_" + (string)sequence);
        }
        state tower;
    }
}

state stop { state_entry() {} }

state tower {
    state_entry() {
        llListen(CHAT_CHANNEL, "", NULL_KEY, "");
        llListen(GAME_CHANNEL, "", NULL_KEY, "");
        llListen(GAME_CHANNEL + 2, "", NULL_KEY, "");
        if (gTowerType == GENERAL_BUILDING) {
            llSetTimerEvent(10);
            llSetText("touch to\nselect type", <1,0,0>, 1.0);
        } else {
            RecalcStats();
            llSetTimerEvent(gTurretInterval);
            DisplayHoverText();
        }
    }

    touch_start(integer num_detected) {
        gOwner = llDetectedKey(0);
        if (gTowerType == GENERAL_BUILDING) {
            list menu = BuildTowerMenu();
            if (llGetListLength(menu) == 0) {
                llInstantMessage(gOwner, "Not enough funds for any tower type.");
            } else {
                string txt = (string)["Select type\nFunds: ", gFunds,
                                      "  Energy: ", gEnergy];
                llDialog(gOwner, txt, menu, CHAT_CHANNEL);
            }
        } else {
            ShowTowerDialog();
        }
    }

    listen(integer channel, string name, key id, string message) {
        if (channel == GAME_CHANNEL + 2) {
            if (llToLower(message) == "td game stop") state SOLD;
            return;
        }
        if (channel == GAME_CHANNEL) {
            gFunds  = (integer)llJsonGetValue(message, ["funds"]);
            gLifes  = (integer)llJsonGetValue(message, ["life"]);
            gEnergy = (integer)llJsonGetValue(message, ["energy"]);
            return;
        }
        // CHAT_CHANNEL — dialog responses
        if (gTowerType == GENERAL_BUILDING) {
            string cmd = llToLower(message);
            integer i;
            for (i = 1; i < llGetListLength(TOWER_TYPES); ++i) {
                if (cmd == llToLower(llList2String(TOWER_TYPES, i))) {
                    integer cost = llList2Integer(TOWER_COSTS, i);
                    if (gFunds >= cost) {
                        BroadcastDelta("FUND", -cost);
                        BroadcastDelta("ENERGY", -25); // construction surge
                        gFunds -= cost;
                        gTowerType = i;
                        gDamageType = llList2Integer(TOWER_DTYPES, i);
                        gLevel = 1;
                        RecalcStats();
                        llSetTimerEvent(gTurretInterval);
                        DisplayHoverText();
                    } else {
                        llInstantMessage(id, "Not enough funds.");
                    }
                    return;
                }
            }
        } else {
            string cmd = llToLower(message);
            if      (cmd == "upgrade") UpgradeTower();
            else if (cmd == "sell")    SellTower();
            else if (cmd == "repair")  RepairTower();
        }
    }

    timer() {
        if (gTowerType == GENERAL_BUILDING) return;

        if (gTowerType == ENERGY_PLANT) {
            EnergyPlant();
        } else if (gTowerType == DEFENSE_TOWER) {
            DefenseTower();
        } else if (gTowerType == BALLISTIC_TOWER ||
                   gTowerType == SNIPER_TOWER    ||
                   gTowerType == TESLA_TOWER) {
            TurretAttack();
        } else if (gTowerType == FOG_TOWER) {
            AoEPulse(FOG_FX, llList2Integer(ENERGY_COST, FOG_TOWER));
        } else if (gTowerType == TOXIC_TOWER) {
            AoEPulse(TOXIC_FX, llList2Integer(ENERGY_COST, TOXIC_TOWER));
        }
        DisplayHoverText();
    }

    // Single-target sensor (used by TurretAttack for SL sensor sweep variant, not currently active)
    // AoE sensor response for Fog/Toxic
    sensor(integer n) {
        if (gPendingAoEDmg > 0) {
            integer i;
            for (i = 0; i < n; ++i) {
                if (~llSubStringIndex(llDetectedName(i), "walker")) {
                    key wkey = llDetectedKey(i);
                    if (gTowerType == TOXIC_TOWER)
                        llRegionSay(GAME_CHANNEL + 2,
                            "DOT = " + (string)gPendingAoEDmg + " 5 " + (string)wkey + " " + (string)gPendingAoEDtype);
                    else {
                        // Fog: slow movement + small instant hit
                        llRegionSay(GAME_CHANNEL + 2, "SLOW = 0.4 5.0 " + (string)wkey);
                        llRegionSay(GAME_CHANNEL + 2,
                            "DMG = " + (string)gPendingAoEDmg + " " + (string)wkey + " " + (string)gPendingAoEDtype);
                    }
                }
            }
            gPendingAoEDmg = 0;
        }
    }
}

state SOLD {
    state_entry() {
        llSetTimerEvent(0);
        llParticleSystem([]);
        if (production) llDie();
    }
}
