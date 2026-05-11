// setpin script using llRemoteLoadScriptPin
// This script should be placed in the target object (tower or walker)
// so that it “opens” itself for a remote script update.

integer REMOTE_PIN = 7654312;    // Define your remote access pin
//integer READY_CHANNEL = -55555;       // Channel used to signal readiness

default
{
    state_entry()
    {
        // Set the remote script access pin so that the engine can later load a script remotely.
        llSetRemoteScriptAccessPin(REMOTE_PIN);
        //llOwnerSay("Remote script access pin set to: " + REMOTE_PIN);
    }
    
    on_rez(integer start_param)
    {
        // Store the rez parameter for future reference.
        // Here we use the object description, but you might choose another method.
        llSetObjectDesc("RezParam:" + (string)start_param);
        //llOwnerSay("Object rezzed with parameter: " + (string)start_param);
        
        // Wait 3 seconds to allow for any potential race conditions.
        //llSleep(3.0);
        
        // Notify the engine that this object is ready for a remote script load.
        // The message includes the object’s key so the engine knows which object to target.
        //llRegionSay(READY_CHANNEL, "READY:" + (string)llGetKey());
    }
}
