package com.vntrum.ansiko

import android.app.Activity
import android.app.AlertDialog
import android.content.SharedPreferences
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import org.json.JSONObject
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
    private var settingsDialog: AlertDialog? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        prefs = getSharedPreferences("ansiko", MODE_PRIVATE)

        display = TerminalDisplayView(this).apply {
            setOnLongClickListener {
                showSettings()
                true
            }
            onGridChanged = { c, r -> gridChanged(c, r) }
        }
        status = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 12f
            setPadding(dp(10), dp(4), dp(10), dp(4))
            setBackgroundColor(0xB3000000.toInt())
            visibility = View.GONE
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

        if (hasConfig()) display.post { maybeConnect() } else showSettings(firstRun = true)
    }

    override fun onStart() {
        super.onStart()
        started = true
        maybeConnect()
    }

    override fun onStop() {
        started = false
        attempt = 0
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
        if (!started || gaveUp || cols == 0 || socket != null || retry != null || !hasConfig()) return

        val host = prefs.getString(KEY_HOST, "")!!.trim()
        val port = prefs.getInt(KEY_PORT, 0)
        val request = try {
            Request.Builder().url("ws://$host:$port/ws/display").build()
        } catch (e: IllegalArgumentException) {
            gaveUp = true
            setStatus(getString(R.string.status_invalid))
            return
        }

        helloSent = false
        setStatus(getString(R.string.status_connecting))
        socket = http.newWebSocket(request, listener)
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
            showSettings(reason = getString(R.string.settings_token_rejected))
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
        if (type == "hello") message.put("token", prefs.getString(KEY_TOKEN, ""))
        webSocket.send(message.toString())
    }

    private fun setStatus(text: String) {
        status.text = text
        status.visibility = View.VISIBLE
    }

    private fun hideStatus() {
        status.visibility = View.GONE
    }

    private fun hasConfig(): Boolean {
        val host = prefs.getString(KEY_HOST, "")!!.trim()
        val port = prefs.getInt(KEY_PORT, 0)
        val token = prefs.getString(KEY_TOKEN, "")!!
        return host.isNotEmpty() && port in 1..65535 && token.isNotEmpty()
    }

    private fun showSettings(firstRun: Boolean = false, reason: String? = null) {
        if (settingsDialog?.isShowing == true) return

        val pad = dp(20)
        val form = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, 0, pad, 0)
        }
        val hostInput = EditText(this).apply {
            hint = getString(R.string.settings_host)
            setText(prefs.getString(KEY_HOST, ""))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            isSingleLine = true
        }
        val portInput = EditText(this).apply {
            hint = getString(R.string.settings_port)
            val port = prefs.getInt(KEY_PORT, 0)
            if (port != 0) setText(getString(R.string.settings_port_value, port))
            inputType = InputType.TYPE_CLASS_NUMBER
            isSingleLine = true
        }
        val tokenInput = EditText(this).apply {
            hint = getString(R.string.settings_token)
            setText(prefs.getString(KEY_TOKEN, ""))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            isSingleLine = true
        }
        form.addView(hostInput)
        form.addView(portInput)
        form.addView(tokenInput)

        val builder = AlertDialog.Builder(this)
            .setTitle(reason ?: getString(R.string.settings_title))
            .setView(form)
            .setPositiveButton(getString(R.string.settings_save), null)
        if (!firstRun) builder.setNegativeButton(android.R.string.cancel, null)

        val dialog = builder.create()
        dialog.setCancelable(!firstRun)
        dialog.setCanceledOnTouchOutside(false)
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val host = hostInput.text.toString().trim()
                val port = portInput.text.toString().toIntOrNull()
                val token = tokenInput.text.toString()
                val urlValid = host.isNotEmpty() && host.none { it.isWhitespace() } &&
                    port != null && port in 1..65535 &&
                    try {
                        Request.Builder().url("ws://$host:$port/ws/display").build()
                        true
                    } catch (e: IllegalArgumentException) {
                        false
                    }
                if (!urlValid || token.isEmpty()) {
                    Toast.makeText(this, R.string.settings_invalid, Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }

                prefs.edit()
                    .putString(KEY_HOST, host)
                    .putInt(KEY_PORT, port)
                    .putString(KEY_TOKEN, token)
                    .apply()
                settingsDialog = null
                dialog.dismiss()
                gaveUp = false
                attempt = 0
                closeSocket()
                maybeConnect()
            }
        }
        dialog.setOnDismissListener { settingsDialog = null }
        settingsDialog = dialog
        dialog.show()
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
        const val KEY_HOST = "host"
        const val KEY_PORT = "port"
        const val KEY_TOKEN = "token"
    }
}
