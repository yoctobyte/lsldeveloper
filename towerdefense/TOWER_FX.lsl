/****************************************************
 * Tower Effects Script
 *
 * This script handles particle and sound effects for tower actions.
 * It listens for linked messages from the TowerLogic script.
 *
 * Effect types (stringly typed):
 *  "EMPEFFECT"           - Play EMP effect
 *  "PROJECTILEEFFECT"    - Play projectile effect
 *  "PROJECTILEMISSEFFECT" - Play projectile miss effect (expects parameters)
 *  "IDLEEFFECT"          - Play idle effect
 ****************************************************/

// String constants for effect types.
string EMPEFFECT           = "EMPEFFECT";
string PROJECTILEEFFECT    = "PROJECTILEEFFECT";
string TESLAEFFECT         = "TESLAEFFECT";
string SNIPEREFFECT        = "SNIPEREFFECT";
string FOGEFFECT           = "FOGEFFECT";
string TOXICEFFECT         = "TOXICEFFECT";
string PROJECTILEMISSEFFECT = "PROJECTILEMISSEFFECT";
string IDLEEFFECT          = "IDLEEFFECT";

key EMP_SOUND = "236304ea-f071-7ae2-89c7-4b014ce26e17";
key TURRET_HIT_SOUND = "63fb7881-79ef-3848-6e28-a4870543e3f9";
key TURRET_MISS_SOUND = "5ed0b5dd-2961-45f8-4dd9-e098a152396c";

PlayEMPEffect() {
    llLinkParticleSystem(2, [
        PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
        PSYS_SRC_BURST_PART_COUNT, 1,
        PSYS_SRC_BURST_RATE, 0.12,
        PSYS_SRC_BURST_RADIUS, 0.025,
        PSYS_SRC_BURST_SPEED_MIN, 0.01,
        PSYS_SRC_BURST_SPEED_MAX, 0.02,
        PSYS_PART_START_COLOR, <1.0, 0.3, 0.5>,
        PSYS_PART_END_COLOR, <0.7, 0.8, 1.0>,
        PSYS_PART_START_SCALE, <0.5, 0.5, 0.0>,
        PSYS_PART_END_SCALE, <0.75, 0.35, 0.0>,
        PSYS_PART_MAX_AGE, 2.0,
        PSYS_SRC_MAX_AGE, 3.0,
        PSYS_SRC_ANGLE_BEGIN, 0.0,
        PSYS_SRC_ANGLE_END, 0.0,
        PSYS_PART_START_ALPHA, 0.0,
        PSYS_PART_END_ALPHA, 1.0,
        PSYS_SRC_TEXTURE, "a2656342-3158-a71d-f76f-92da4d5e5634"
    ]);
    llPlaySound(EMP_SOUND, 0.2);
}

PlayProjectileEffect(key targetId) {
    float travelTime = 1.0;
    llLinkParticleSystem(2, [
        PSYS_PART_FLAGS, PSYS_PART_TARGET_POS_MASK | PSYS_PART_EMISSIVE_MASK |
                         PSYS_PART_FOLLOW_VELOCITY_MASK | PSYS_PART_INTERP_COLOR_MASK |
                         PSYS_PART_INTERP_SCALE_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_DROP,
        PSYS_SRC_BURST_PART_COUNT, 1,
        PSYS_SRC_BURST_RATE, 1.0,
        PSYS_SRC_BURST_RADIUS, 1.0,
        PSYS_SRC_BURST_SPEED_MIN, 0.1,
        PSYS_SRC_BURST_SPEED_MAX, 1.0,
        PSYS_SRC_ACCEL, ZERO_VECTOR,
        PSYS_PART_START_COLOR, <1.0, 0.0, 0.0>,
        PSYS_PART_END_COLOR, <1.0, 1.0, 0.0>,
        PSYS_PART_START_SCALE, <0.1, 0.1, 0.0>,
        PSYS_PART_END_SCALE, <0.2, 0.2, 0.0>,
        PSYS_PART_MAX_AGE, travelTime,
        PSYS_SRC_MAX_AGE, 0.8,
        PSYS_SRC_ANGLE_BEGIN, 0.0,
        PSYS_SRC_ANGLE_END, 0.0,
        PSYS_SRC_TARGET_KEY, targetId,
        PSYS_SRC_TEXTURE, "f24cdf9f-b73d-d9bd-4e2f-ce732cbcc3de"
    ]);
    llPlaySound(TURRET_HIT_SOUND, 0.2);
}

PlayProjectileMissEffect(vector targetPos, float missDistance) {
    vector myPos = llGetPos();
    vector direction = targetPos - myPos;
    float travelTime = 1.0;
    float missAngle = llAtan2(direction.y, direction.x) + missDistance;
    vector missDirection = <llCos(missAngle) * llVecMag(direction), llSin(missAngle) * llVecMag(direction), direction.z>;
    vector missVelocity = missDirection / travelTime;
    llLinkParticleSystem(2, [
        PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_FOLLOW_VELOCITY_MASK |
                         PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_DROP,
        PSYS_SRC_BURST_PART_COUNT, 100,
        PSYS_SRC_BURST_RADIUS, 0.1,
        PSYS_SRC_BURST_RATE, 0.1,
        PSYS_SRC_BURST_SPEED_MIN, llVecMag(missVelocity),
        PSYS_SRC_BURST_SPEED_MAX, llVecMag(missVelocity),
        PSYS_SRC_ACCEL, direction,
        PSYS_PART_START_COLOR, <1.0, 0.0, 0.0>,
        PSYS_PART_END_COLOR, <1.0, 1.0, 0.0>,
        PSYS_PART_START_SCALE, <0.1, 0.1, 0.0>,
        PSYS_PART_END_SCALE, <0.2, 0.2, 0.0>,
        PSYS_PART_MAX_AGE, travelTime,
        PSYS_SRC_MAX_AGE, 3.0,
        PSYS_SRC_ANGLE_BEGIN, 0.0,
        PSYS_SRC_ANGLE_END, 0.0,
        PSYS_SRC_TEXTURE, "f24cdf9f-b73d-d9bd-4e2f-ce732cbcc3de"
    ]);
}

PlayTeslaEffect(key targetId) {
    // Flickering Lightning Beam
    llLinkParticleSystem(2, [
        PSYS_PART_FLAGS, PSYS_PART_TARGET_POS_MASK | PSYS_PART_EMISSIVE_MASK | PSYS_PART_RIBBON_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE,
        PSYS_SRC_BURST_PART_COUNT, 2,
        PSYS_SRC_BURST_RATE, 0.05,
        PSYS_PART_START_COLOR, <0.4, 0.7, 1.0>,
        PSYS_PART_START_SCALE, <0.2, 2.0, 0.0>,
        PSYS_PART_MAX_AGE, 0.2,
        PSYS_SRC_TARGET_KEY, targetId,
        PSYS_SRC_TEXTURE, "a2656342-3158-a71d-f76f-92da4d5e5634"
    ]);
}

PlaySniperEffect(key targetId) {
    // High-speed precision beam
    llLinkParticleSystem(2, [
        PSYS_PART_FLAGS, PSYS_PART_TARGET_POS_MASK | PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_DROP,
        PSYS_SRC_BURST_PART_COUNT, 1,
        PSYS_SRC_BURST_RATE, 1.0,
        PSYS_PART_START_COLOR, <1.0, 1.0, 1.0>,
        PSYS_PART_END_COLOR, <1.0, 0.0, 0.0>,
        PSYS_PART_START_SCALE, <0.05, 0.05, 0.0>,
        PSYS_PART_MAX_AGE, 0.1,
        PSYS_SRC_TARGET_KEY, targetId,
        PSYS_SRC_TEXTURE, "f24cdf9f-b73d-d9bd-4e2f-ce732cbcc3de"
    ]);
}

PlayFogEffect() {
    // Area of effect cloud
    llLinkParticleSystem(2, [
        PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
        PSYS_SRC_BURST_PART_COUNT, 10,
        PSYS_SRC_BURST_RATE, 0.5,
        PSYS_SRC_BURST_RADIUS, 1.5,
        PSYS_PART_START_COLOR, <0.8, 0.8, 0.8>,
        PSYS_PART_END_COLOR, <0.5, 0.5, 0.5>,
        PSYS_PART_START_SCALE, <1.0, 1.0, 0.0>,
        PSYS_PART_END_SCALE, <4.0, 4.0, 0.0>,
        PSYS_PART_MAX_AGE, 4.0,
        PSYS_PART_START_ALPHA, 0.3,
        PSYS_PART_END_ALPHA, 0.0
    ]);
}

PlayToxicEffect() {
    // Green corrosive spray
    llLinkParticleSystem(2, [
        PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK,
        PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE,
        PSYS_SRC_BURST_PART_COUNT, 5,
        PSYS_SRC_BURST_RATE, 0.1,
        PSYS_PART_START_COLOR, <0.2, 1.0, 0.2>,
        PSYS_PART_END_COLOR, <0.0, 0.4, 0.0>,
        PSYS_PART_START_SCALE, <0.1, 0.1, 0.0>,
        PSYS_PART_MAX_AGE, 1.5,
        PSYS_SRC_ANGLE_BEGIN, 0.1,
        PSYS_SRC_ANGLE_END, 0.1
    ]);
}

PlayIdleEffect() {
    // Optionally add idle animations or particle effects.
}

default {
    link_message(integer sender, integer num, string message, key id) {
         // Expect the message to be in the format "EFFECTNAME|parameter"
         list parts = llParseString2List(message, ["|"], []);
         string effectName = llList2String(parts, 0);
         if (effectName == EMPEFFECT) {
             PlayEMPEffect();
         } else if (effectName == PROJECTILEEFFECT) {
             PlayProjectileEffect(id);
         } else if (effectName == PROJECTILEMISSEFFECT) {
             if (llGetListLength(parts) >= 3) {
                vector targetPos = (vector) llList2String(parts, 1);
                float missDistance = (float) llList2String(parts, 2);
                PlayProjectileMissEffect(targetPos, missDistance);
             }
         } else if (effectName == TESLAEFFECT) {
             PlayTeslaEffect(id);
         } else if (effectName == SNIPEREFFECT) {
             PlaySniperEffect(id);
         } else if (effectName == FOGEFFECT) {
             PlayFogEffect();
         } else if (effectName == TOXICEFFECT) {
             PlayToxicEffect();
         } else if (effectName == IDLEEFFECT) {
             PlayIdleEffect();
         }
    }
}
