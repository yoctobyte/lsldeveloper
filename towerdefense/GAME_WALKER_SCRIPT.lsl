// Constants
string WALKER_NAME = "Annoying Ant Attacker";
integer TYPE_DUMMY=0;
integer TYPE_SPIRAL=1;
integer WALKER_TYPE = 1;

integer WALK_ON_REZ = FALSE;

integer GAME_CHANNEL = -12345;
integer WALKER_CHANNEL_HIT = -12348;

integer production = FALSE;

integer temporary = FALSE;

float gPathDuration;
integer gStartTimeStamp;

vector gScale=<3.0,3.0,0.0>;
rotation gBoardRot=ZERO_ROTATION;
//vector gSpawnPos=<0.5,0.0,0.0>;
//vector gFinishPos=<0.5,1.0,0.0>;
vector gSpawnPos=<0.01,0.01,0.0>;
vector gFinishPos=<0.99,0.99,0.0>;
string gPathData;

integer gLevel;

integer gRezLevel;

//time to define our motions.
//for now, let's assume all motions start on bottom row y=0, and end at top row y=1
//also, for simplicity, right now we assume start and finish are at x=0.5. not sure about this cause corners might work too.
//and ideally i would like that to be flexible. yet i also don't want to generate dynamic paths too much, that's all a to-do.
//now, by hardcoding the list we run into two problems. first, the rotations. we have to precalculate them. and cannot use llEuler2Rot 
//in a hardcoded list.
//so, instead, what about we make a list of only x,y coordinates. calculate the direction. calculate the time.
//we could either make the list in vector format, or just x,y pairs. x,y pairs we could multiply by 100 for further readability.
//alternatively instead of scaling to 100 we could scale to board sizex, sizey (ex. 30x50)
//so for maximum flex, what about we just define scale constants, so in the future can do as we see fit.

integer MOTION_LIST_TYPE = 0; // MOTION_LIST_TYPE_INTEGER PAIR or MOTION_LIST_TYPE_VECTOR
float MOTION_LIST_SCALE_X = 100.0; //divide the integers 
float MOTION_LIST_SCALE_Y = 100.0; 
//a custom list format

integer REZ_HAS_EXTENDED_PARAMS=0x800;

list MOTION = [
    1,1,
    10,10,
    30,20,
    60,20,
    70,10,
    80,20,
    60,30,
    85,40,
    60,50,
    50,50,
    75,70,
    35,80,
    40,85,
    65,80,
    80,85,
    90,90,
    95,95    
    ];
/*
list MOTION = [
    15,0, //spawn position
    15,2, //2 up
    0, 17, //15 diagonal left
    0,20, //3 up
    3,23, //3 diagonal right
    27,23, //24 to the right
    30,36, //3 diagonal right
    30, 39, //3 up
    27, 42, //3 diag left
    17, 42, //10 left
    12, 37, //5 diag down left
    3, 37, //left
    0, 41,
    1, 42,
    12, 42, 
    15, 45,
    20, 45,
    21, 46,
    20, 47,
    16, 48,
    15, 49,
    15, 50 //finish
];
*/

list MOTION_PATH;

/*
list MOTION_PATH = [
    // Zig-zag motion
    <0.2, 0, 0>, ZERO_ROTATION, 18.0,
    <0.4, 0.33, 0>, ZERO_ROTATION, 18.0,
    <0.6, 0.33, 0>, ZERO_ROTATION, 18.0,
    <0.8, 0.66, 0>, ZERO_ROTATION, 18.0,
    <1.0, 0.66, 0>, ZERO_ROTATION, 18.0,
    <0.8, 0.99, 0>, ZERO_ROTATION, 18.0,
    <0.6, 0.99, 0>, ZERO_ROTATION, 18.0,
    <0.4, 1.32, 0>, ZERO_ROTATION, 18.0,
    <0.2, 1.32, 0>, ZERO_ROTATION, 18.0,
    <0, 1.65, 0>, ZERO_ROTATION, 18.0,
    // Idle for 5 seconds
    <0, 1.65, 0>, ZERO_ROTATION, 5.0,
    // Return to starting position
    <0, 0, 0>, ZERO_ROTATION, 1.0
];
*/

// Variables
integer gWalkerLife = 100;
integer gWalkerShield = 10;
float gWalkerSpeed = 1.0; // 1.0 = baseline 60s path; loaded from LSD per level
vector gStartPosition;
integer gWalkerState = 0;
key gOwner;

// Functions
keyframeMotion(list path) {
    llSetKeyframedMotion(path, [
        KFM_MODE, KFM_FORWARD,
        KFM_DATA, KFM_TRANSLATION | KFM_ROTATION
    ]);
}

MoveToStartPosition() {
    llSetPos(gStartPosition);
    llSetRot(llEuler2Rot(<0, 0, 0> * DEG_TO_RAD));
}

float GetKeyframedMotionDuration(list path) {
    float duration = 0.0;
    integer i;
    for (i = 0; i < llGetListLength(path); i += 3) {
        duration += llList2Float(path, i + 2);
    }
    return duration;
}

list ScaleKeyframedMotionDuration(list path, float newDuration) {
    float currentDuration = GetKeyframedMotionDuration(path);
    integer i;
    for (i = 0; i < llGetListLength(path); i += 3) {
        float oldMotionDuration = llList2Float(path, i + 2);
        float newMotionDuration = oldMotionDuration * newDuration / currentDuration;
        if (newMotionDuration < 0.15)
            newMotionDuration = 0.15;
        path = llListReplaceList(path, [newMotionDuration], i + 2, i + 2);
    }

    return path;
}

list GenerateMotionPath(list motion) {
    list motionPath = [];
    integer i;
    vector lastPoint;
    lastPoint.x=gSpawnPos.x*gScale.x;
    lastPoint.y=gSpawnPos.y*gScale.y;
    rotation lastRot = ZERO_ROTATION;
    rotation myOwnRot = llEuler2Rot( DEG_TO_RAD*(vector)llGetObjectDesc());
    lastRot = myOwnRot;
    
    //rotation lastRot=llGetRot();
    for (i = 0; i < llGetListLength(motion); i += 2) {
        float x = llList2Float(motion, i) / MOTION_LIST_SCALE_X;
        float y = llList2Float(motion, i + 1) / MOTION_LIST_SCALE_Y;
        vector point = <x, y, 0.0>;

        if (i + 4 < llGetListLength(motion)) {
            float nextX = llList2Float(motion, i + 2) / MOTION_LIST_SCALE_X;
            float nextY = llList2Float(motion, i + 3) / MOTION_LIST_SCALE_Y;
            vector nextPoint = <nextX, nextY, 0.0>;

            //rotation rot = llRotBetween(<1.0, 0.0, 0.0>, nextPoint - point);

            vector scaledPoint; //= point*gScale + gSpawnPos;
            scaledPoint.x = point.x*gScale.x; //+ gSpawnPos.x;
            scaledPoint.y = point.y*gScale.y; //+ gSpawnPos.y;
            scaledPoint = scaledPoint * gBoardRot;

            //rotation rot = llRotBetween(point, nextPoint);            
            //rotation rot = llEuler2Rot (scaledPoint-lastPoint); //llRotBetween(point, nextPoint);            
            // Simplified and smoothed rotation logic.
            // We rotate over the entire segment duration instead of just 10%.
            rotation rot = myOwnRot * llRotBetween(<1.0, 0.0, 0.0>, scaledPoint - lastPoint);
            float segmentDuration = llVecDist(scaledPoint, lastPoint);
            
            // Single segment per point for maximum smoothness in KFM.
            motionPath += [(scaledPoint - lastPoint), rot / lastRot, segmentDuration];
            
            lastPoint = scaledPoint;
            lastRot = rot;
        } else {
            //vector scaledPoint = point * gScale + gSpawnPos;
            //motionPath += [scaledPoint];
        }
    }
    return motionPath;
}

list StringToPathData(string data) {
    return llParseString2List (data, [","], []);
}



SetHoverText() {
    float speedPerSecond = llVecMag(llGetVel());
    float timeLeft = gPathDuration - (llGetUnixTime() - gStartTimeStamp);
    string hoverText = (string)[ WALKER_NAME , "\n",
                       "Life: ", gWalkerLife, "  Shield", gWalkerShield,"\n",
                       "Speed: ", llRound(1000.0*speedPerSecond), " mm/s\n",
                       "Time left: ",llFloor(timeLeft), " s"];
    llSetText(hoverText, <0.8,0.5,0.9>, 1.0);
}

PlayExplosionEffect() {
    llParticleSystem([
        PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_TARGET_POS_MASK | PSYS_PART_FOLLOW_SRC_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
        PSYS_SRC_BURST_PART_COUNT, 1,
        PSYS_SRC_BURST_RATE, 8.0,
        PSYS_SRC_BURST_RADIUS, 0.075,
        PSYS_SRC_BURST_SPEED_MIN, 0.01,
        PSYS_SRC_BURST_SPEED_MAX, 0.02,
        PSYS_PART_START_COLOR, <1.0, 0.9, 1.0>,
        PSYS_PART_END_COLOR, <0.9, 1.0, 1.0>,
        PSYS_PART_START_SCALE, <0.5, 0.5, 0.0>,
        PSYS_PART_END_SCALE, <0.175, 0.135, 0.0>,
        PSYS_PART_MAX_AGE, 3.0,
        PSYS_SRC_MAX_AGE, 5.0,
        PSYS_SRC_ANGLE_BEGIN, 0.0,
        PSYS_SRC_ANGLE_END, 0.0,
        PSYS_PART_START_ALPHA, 0.0,
        PSYS_PART_END_ALPHA, 0.9,
        PSYS_SRC_TARGET_KEY, llGetKey(),        
        PSYS_SRC_TEXTURE, "d26eb61f-2bfc-3ccb-0bcf-22ea7b8dbd0d"        
    ]);

    //llPlaySound(EXPLOSION_SOUND, 1.0);
}

PlaySurvivedEffect() {
    //idk, a cloud?
    llParticleSystem([
        PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
        PSYS_SRC_BURST_PART_COUNT, 2,
        PSYS_SRC_BURST_RATE, 0.12,
        PSYS_SRC_BURST_RADIUS, 0.175,
        PSYS_SRC_BURST_SPEED_MIN, 0.01,
        PSYS_SRC_BURST_SPEED_MAX, 0.02,
        PSYS_PART_START_COLOR, <1.0, 0.9, 1.0>,
        PSYS_PART_END_COLOR, <0.9, 1.0, 1.0>,
        PSYS_PART_START_SCALE, <0.5, 0.5, 0.0>,
        PSYS_PART_END_SCALE, <0.175, 0.135, 0.0>,
        PSYS_PART_MAX_AGE, 5.0,
        PSYS_SRC_MAX_AGE, 1.5,
        PSYS_SRC_ANGLE_BEGIN, 0.0,
        PSYS_SRC_ANGLE_END, 0.0,
        PSYS_PART_START_ALPHA, 0.0,
        PSYS_PART_END_ALPHA, 1.0,
        PSYS_SRC_TEXTURE, "664886cd-3c22-399e-d434-d395b4dd67a3"        
    ]);

    //llPlaySound(EXPLOSION_SOUND, 1.0);
}


// States
default {
    state_entry() {
        llSetPrimitiveParams([PRIM_PHYSICS_SHAPE_TYPE, PRIM_PHYSICS_SHAPE_CONVEX]);
        if (!production) llOwnerSay((string)["Free mem: ", llGetFreeMemory()]);
        state initial;
    }
}

state initial {
    state_entry() {
        gStartPosition = llGetPos();
        gWalkerState = FALSE;
        state fetchParams;
    }

    touch_start(integer n) {
        if (!production) {
            PlayExplosionEffect();
            state active;
        }
    }

    on_rez(integer sequence) {
        llResetScript(); // re-enter default so llGetStartParameter() is used cleanly
    }
}

state fetchParams {
    state_entry() {
        // Self-transport and channel init using the rez start_param
        integer seq = llGetStartParameter();
        if (seq != 0) {
            string chanStr = llLinksetDataRead("GAME_CHANNEL");
            if (chanStr != "") GAME_CHANNEL = (integer)chanStr;
            string posStr = llLinksetDataRead("REZZ_POS_" + (string)seq);
            if (posStr != "") {
                llSetRegionPos((vector)posStr);
                llLinksetDataDelete("REZZ_POS_" + (string)seq);
            }
            gStartPosition = llGetPos();
        }

        // Board geometry
        string scaleStr = llLinksetDataRead("BOARD_SCALE");
        if (scaleStr != "") gScale = (vector)scaleStr;
        string rotStr = llLinksetDataRead("BOARD_ROT");
        if (rotStr != "") gBoardRot = (rotation)rotStr;
        string spawnStr = llLinksetDataRead("SPAWN_POS");
        if (spawnStr != "") gSpawnPos = (vector)spawnStr;
        string finishStr = llLinksetDataRead("FINISH_POS");
        if (finishStr != "") gFinishPos = (vector)finishStr;

        // Level-specific stats
        string hpStr = llLinksetDataRead("WALKER_HP");
        if (hpStr != "") gWalkerLife = (integer)hpStr;
        string speedStr = llLinksetDataRead("WALKER_SPEED");
        if (speedStr != "") gWalkerSpeed = (float)speedStr;

        llListen(GAME_CHANNEL, "", NULL_KEY, "START");
        llSetTimerEvent(30.0);
    }

    timer() {
        state active; // fallback if START never arrives
    }

    listen(integer channel, string name, key id, string message) {
        if (channel == GAME_CHANNEL && message == "START") {
            state active;
        }
    }

    on_rez(integer sequence) { llResetScript(); }
}

state active {
    state_entry() {
        //gBoardRot=llEuler2Rot(<0,0,-90*DEG_TO_RAD>);
        llListen(GAME_CHANNEL + 2, "", NULL_KEY, ""); //tower-to-walker channel
        //llListen(GAME_CHANNEL + 1, "", NULL_KEY, "");
        
        float targetDuration = 60.0 / gWalkerSpeed;
        MOTION_PATH = ScaleKeyframedMotionDuration(GenerateMotionPath(MOTION), targetDuration);
        gPathDuration = GetKeyframedMotionDuration(MOTION_PATH);
        gStartTimeStamp = llGetUnixTime();        
        //instead of a timer
        //llSetTimerEvent (GetKeyframedMotionDuration(MOTION_PATH)+1.0);
        //we set up a sensor misfire:
        llSensorRepeat ("NO-NAME", "12345678-1234-1234-1234-1234567890AB", AGENT, 0.1, 0.1, gPathDuration+2.5);        
        //set hover text
        llSetTimerEvent (1.5);
        if (temporary)
            llSetLinkPrimitiveParamsFast(LINK_THIS, [PRIM_TEMP_ON_REZ, TRUE]);
        keyframeMotion(MOTION_PATH);            
    }
    
    state_exit() {
        llSensorRepeat("", "", 0, 0.0, 0.0, 0.0);
    }
    
    listen(integer channel, string name, key id, string message) {
        if (channel == GAME_CHANNEL + 2) {
            if (llToLower(message) == "td game stop") {
                llDie();
                return;
            }
            if (llGetSubString(message, 0, 5) != "DMG = ") return;
            list tokens = llParseString2List(message, [" "], []);
            integer hitValue = (integer)llList2String(tokens, 2);
            key targetId = (key)llList2String(tokens, 3);
            if (targetId != llGetKey()) return;
            gWalkerLife -= hitValue;
            if (gWalkerLife <= 0) {
                MoveToStartPosition();
                gWalkerState = 2;
                state defeated;
            }
        }
    }
    
    no_sensor() {
        //when we hit the timer while alive, we arrived.
        llOwnerSay ("Motion completed!");
        state survived;
    }
    
    moving_end() {
        llOwnerSay ("Keyframed motion completed!");
        state survived;
    }
    
    timer() {  
        SetHoverText();             
        
        // --- Wall Blocking Logic ---
        vector pos = llGetPos();
        // Read board params from LSD to calculate our grid position
        vector bPos = (vector)llLinksetDataRead("BOARD_POS"); // Need to ensure engine writes this
        rotation bRot = (rotation)llLinksetDataRead("BOARD_ROT");
        vector bScale = (vector)llLinksetDataRead("BOARD_SCALE");
        
        // Convert region pos to local grid pos
        vector local = (pos - bPos) / bRot; // Standard inverse rotation
        integer gx = (integer)((local.x / bScale.x + 0.5) * 30); // 30 is gGridSizeX
        integer gy = (integer)((local.y / bScale.y + 0.5) * 50); // 50 is gGridSizeY
        
        if (llLinksetDataRead("WALL_" + (string)gx + "_" + (string)gy) == "1") {
            // WE HIT A WALL!
            llSetKeyframedMotion([], [KFM_COMMAND, KFM_CMD_PAUSE]);
            llSetText("SMASHING WALL!", <1,0,0>, 1.0);
            llRegionSay(GAME_CHANNEL + 1, "WALL_DAMAGE " + (string)gx + "_" + (string)gy);
            llSleep(2.0);
            llSetKeyframedMotion([], [KFM_COMMAND, KFM_CMD_PLAY]);
        }
    }

    on_rez(integer sequence) { llResetScript(); }
}

state defeated {
    state_entry() {
        llSetObjectName("DEAD_OBJECT");
        llSetKeyframedMotion([], []);
        PlayExplosionEffect();
        llSleep(2.5);
        state deactivate;
    }
    on_rez(integer sequence) { llResetScript(); }
}

state survived {
    state_entry() {
        llSetObjectName("COMPLETED_OBJECT");
        llSay(GAME_CHANNEL + 1, "LIFE - 1");
        PlaySurvivedEffect();
        llSetText("Survived!", <1,0,0>, 1.0);
        llSleep(10.0);
        state deactivate;
    }
    on_rez(integer sequence) { llResetScript(); }
}

state deactivate {
    state_entry() {
        llRegionSay(GAME_CHANNEL + 1, "WALKER_REMOVED");
        llSetKeyframedMotion([], []);
        llSetText("Destroying...", ZERO_VECTOR, 1.0);
        llSleep(3.0);
        llDie();
    }
    on_rez(integer sequence) { llResetScript(); }
}


