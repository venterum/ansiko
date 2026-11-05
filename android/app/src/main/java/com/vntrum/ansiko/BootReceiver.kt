package com.vntrum.ansiko

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Bring the display back after a reboot on a dedicated wall phone. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val prefs = context.getSharedPreferences(Prefs.NAME, Context.MODE_PRIVATE)
        if (!Config.load(prefs).isComplete()) return
        val launch = Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        try {
            context.startActivity(launch)
        } catch (_: Exception) {
            // Android 10+ may block background activity launches; see docs/release.md.
        }
    }
}
