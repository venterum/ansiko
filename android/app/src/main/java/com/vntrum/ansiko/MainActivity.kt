package com.vntrum.ansiko

import android.app.Activity
import android.content.Intent
import android.content.SharedPreferences
import android.graphics.Color
import android.graphics.Typeface
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.TextView
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import org.json.JSONObject
import java.util.Calendar
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

class MainActivity : Activity() {

    private val http = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build()
    private val handler = Handler(Looper.getMainLooper())

    private lateinit var prefs: SharedPreferences
    private lateinit var display: TerminalDisplayView
    private lateinit var status: TextView

    private var socket: WebSocket? = null
    private var helloSent = false
    private var started = false
    private var cols = 0
    private var rows = 0
    private var attempt = 0
    private var gaveUp = false
    private var retry: Runnable? = null
    private var activeConfig: Config? = null

    // Burn-in guard: the panel runs 24/7, so the whole grid drifts around a small ring.
    private val driftPath = listOf(0 to 0, 1 to -1, 2 to 0, 1 to 1, 0 to 1, -1 to 1, -2 to 0, -1 to -1)
    private var driftStep = 0
    private var kioskRequested = false
    private val panelTick = object : Runnable {
        override fun run() {
            // Check the clock every minute, not only when the activity resumes:
            // a wall display may stay in the foreground across 22:00 and 08:00.
            applyBrightness()
            if (prefs.getBoolean(Prefs.DRIFT, true)) {
                driftStep = (driftStep + 1) % driftPath.size
                val (x, y) = driftPath[driftStep]
                display.animate()
                    .translationX(dp(x).toFloat())
                    .translationY(dp(y).toFloat())
                    .setDuration(DRIFT_ANIM)
                    .start()
            }
            handler.postDelayed(this, DRIFT_PERIOD)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        applyLockScreenBehavior()
        prefs = getSharedPreferences(Prefs.NAME, MODE_PRIVATE)

        display = TerminalDisplayView(this).apply {
            setOnLongClickListener {
                openSettings()
                true
            }
            onGridChanged = { c, r -> gridChanged(c, r) }
        }
        status = TextView(this).apply {
            typeface = Typeface.MONOSPACE
            setTextColor(Color.parseColor("#ECECE4"))
            textSize = 12f
            setPadding(dp(10), dp(4), dp(10), dp(4))
            setBackgroundColor(0xB30B0D0C.toInt())
            visibility = View.INVISIBLE
        }

        val root = FrameLayout(this)
        root.setBackgroundColor(Color.BLACK)
        root.addView(display, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        val statusParams = FrameLayout.LayoutParams(
            WRAP_CONTENT,
            WRAP_CONTENT,
            Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL,
        )
        statusParams.bottomMargin = dp(16)
        root.addView(status, statusParams)
        setContentView(root)
        hideSystemUi()

        val config = Config.load(prefs)
        if (config.isComplete()) {
            display.post { maybeConnect() }
        } else {
            setStatus(
                getString(
                    if (config.host.isNotEmpty() || config.token.isNotEmpty()) {
                        R.string.status_invalid
                    } else {
                        R.string.status_no_config
                    },
                ),
            )
            display.post { openSettings() }
        }
    }

    override fun onStart() {
        super.onStart()
        started = true
        handler.removeCallbacks(panelTick)
        handler.post(panelTick)
        maybeConnect()
    }

    override fun onResume() {
        super.onResume()
        applyBrightness()
        applyKioskMode()
        // The settings screen may have changed the address or the token. Also
        // retry after a rejected token: the server may have been fixed without
        // changing anything on the phone.
        if (Config.load(prefs) != activeConfig || gaveUp) {
            gaveUp = false
            attempt = 0
            closeSocket()
            maybeConnect()
        }
    }

    override fun onStop() {
        started = false
        attempt = 0
        handler.removeCallbacks(panelTick)
        closeSocket()
        super.onStop()
    }

    override fun onDestroy() {
        closeSocket()
        handler.removeCallbacksAndMessages(null)
        http.dispatcher.executorService.shutdown()
        super.onDestroy()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemUi()
    }

    private fun gridChanged(newCols: Int, newRows: Int) {
        if (newCols == cols && newRows == rows) return
        cols = newCols
        rows = newRows
        if (helloSent) sendSize("resize") else maybeConnect()
    }

    private fun maybeConnect() {
        if (!started || gaveUp || cols == 0 || socket != null || retry != null) return
        val config = Config.load(prefs)
        if (!config.isComplete()) return

        helloSent = false
        activeConfig = config
        setStatus(getString(R.string.status_connecting))
        socket = http.newWebSocket(Request.Builder().url(config.url).build(), listener)
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            handler.post {
                if (socket !== webSocket) {
                    webSocket.close(1000, null)
                    return@post
                }
                helloSent = true
                attempt = 0
                sendSize("hello")
                hideStatus()
            }
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            handler.post {
                if (socket === webSocket && helloSent) display.feed(bytes.toByteArray())
            }
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            handler.post {
                if (socket !== webSocket || !helloSent) return@post
                val type = try {
                    JSONObject(text).optString("type")
                } catch (e: Exception) {
                    ""
                }
                if (type == "reset") display.reset()
            }
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            webSocket.close(code, null)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            handler.post { socketGone(webSocket, code) }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            handler.post { socketGone(webSocket, 0) }
        }
    }

    private fun socketGone(webSocket: WebSocket, code: Int) {
        if (socket !== webSocket) return
        socket = null
        helloSent = false

        if (code == 4401) {
            gaveUp = true
            setStatus(getString(R.string.status_rejected))
            openSettings()
        } else if (started) {
            scheduleRetry()
        }
    }

    private fun scheduleRetry() {
        if (retry != null || !started || gaveUp) return
        val delay = minOf(30_000L, 1000L shl minOf(attempt, 5))
        attempt++
        setStatus(getString(R.string.status_offline, delay / 1000))
        val runnable = Runnable {
            retry = null
            maybeConnect()
        }
        retry = runnable
        handler.postDelayed(runnable, delay)
    }

    private fun closeSocket() {
        retry?.let { handler.removeCallbacks(it) }
        retry = null
        socket?.close(1000, null)
        socket = null
        helloSent = false
    }

    private fun sendSize(type: String) {
        val webSocket = socket ?: return
        val message = JSONObject()
            .put("type", type)
            .put("cols", cols)
            .put("rows", rows)
        if (type == "hello") message.put("token", prefs.getString(Prefs.TOKEN, ""))
        webSocket.send(message.toString())
    }

    @Suppress("DEPRECATION")
    private fun applyLockScreenBehavior() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                    WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD,
            )
        }
    }

    /** Optional screen pinning: keeps accidental swipes from leaving the display. */
    private fun applyKioskMode() {
        val wanted = prefs.getBoolean(Prefs.KIOSK, false)
        if (wanted == kioskRequested) return
        try {
            if (wanted) startLockTask() else stopLockTask()
        } catch (_: Exception) {
            // Screen pinning can be declined or already be in the requested state.
        }
        kioskRequested = wanted
    }

    /** A panel left at full brightness overnight is what burns an OLED in. */
    private fun applyBrightness() {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val night = hour >= Prefs.NIGHT_START || hour < Prefs.NIGHT_END
        val dimmed = night && prefs.getBoolean(Prefs.DIM_NIGHT, true)
        val attributes = window.attributes
        attributes.screenBrightness = if (dimmed) {
            prefs.getInt(Prefs.BRIGHTNESS, Prefs.BRIGHTNESS_DEFAULT) / 100f
        } else {
            WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE
        }
        window.attributes = attributes
    }

    private fun openSettings() {
        startActivity(
            Intent(this, SettingsActivity::class.java)
                .putExtra(SettingsActivity.EXTRA_CONNECTED, socket != null && helloSent)
                .putExtra(SettingsActivity.EXTRA_GRID, "$cols×$rows"),
        )
    }

    private fun setStatus(text: String) {
        status.text = text
        status.visibility = View.VISIBLE
    }

    private fun hideStatus() {
        status.visibility = View.INVISIBLE
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).roundToInt()

    @Suppress("DEPRECATION")
    private fun hideSystemUi() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.apply {
                hide(WindowInsets.Type.systemBars())
                systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            window.decorView.systemUiVisibility =
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        }
    }

    private companion object {
        const val DRIFT_PERIOD = 60_000L
        const val DRIFT_ANIM = 1500L
    }
}
