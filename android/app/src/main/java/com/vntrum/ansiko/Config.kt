package com.vntrum.ansiko

import android.content.SharedPreferences
import okhttp3.Request

/** Keys shared by the display screen and the settings screen. */
object Prefs {
    const val NAME = "ansiko"
    const val HOST = "host"
    const val PORT = "port"
    const val TOKEN = "token"

    /** Burn-in guard: slowly drift the whole grid, on by default. */
    const val DRIFT = "drift"

    /** Dim the panel between [NIGHT_START] and [NIGHT_END]. */
    const val DIM_NIGHT = "dim_night"

    /** Panel brightness in percent while dimmed. */
    const val BRIGHTNESS = "brightness"

    /** Optional screen pinning for a dedicated wall display. */
    const val KIOSK = "kiosk"

    const val NIGHT_START = 22
    const val NIGHT_END = 8
    const val BRIGHTNESS_DEFAULT = 40
}

/** Server address and token the phone connects to. */
data class Config(val host: String, val port: Int, val token: String) {

    val url: String get() = url(host, port)

    fun isComplete(): Boolean = token.isNotEmpty() && isValid(host, port)

    fun save(prefs: SharedPreferences) {
        prefs.edit()
            .putString(Prefs.HOST, host)
            .putInt(Prefs.PORT, port)
            .putString(Prefs.TOKEN, token)
            .apply()
    }

    companion object {
        fun load(prefs: SharedPreferences) = Config(
            prefs.getString(Prefs.HOST, "")!!.trim(),
            prefs.getInt(Prefs.PORT, 0),
            prefs.getString(Prefs.TOKEN, "")!!,
        )

        fun url(host: String, port: Int) = "ws://$host:$port/ws/display"

        /** Address the WebSocket client can actually open. */
        fun isValid(host: String, port: Int?): Boolean {
            // shortcut: no IPv6 literals, add bracket-aware parsing if a phone ever needs one
            if (host.isEmpty() || host.any { it.isWhitespace() }) return false
            if (host.contains('/') || host.contains(':')) return false
            if (port == null || port !in 1..65535) return false
            return try {
                Request.Builder().url(url(host, port)).build()
                true
            } catch (e: IllegalArgumentException) {
                false
            }
        }
    }
}
