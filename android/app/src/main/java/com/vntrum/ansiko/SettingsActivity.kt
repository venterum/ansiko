package com.vntrum.ansiko

import android.app.Activity
import android.content.Intent
import android.content.SharedPreferences
import android.os.Bundle
import android.text.Editable
import android.text.SpannableString
import android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
import android.text.TextWatcher
import android.text.style.ForegroundColorSpan
import android.view.View
import android.widget.CheckBox
import android.widget.EditText
import android.widget.TextView
import com.google.zxing.integration.android.IntentIntegrator

/** Full-screen settings, styled like the monospace terminal the phone displays. */
class SettingsActivity : Activity() {

    private lateinit var prefs: SharedPreferences
    private lateinit var host: EditText
    private lateinit var port: EditText
    private lateinit var token: EditText
    private lateinit var endpoint: TextView
    private lateinit var error: TextView
    private lateinit var brightnessValue: TextView
    private lateinit var drift: CheckBox
    private lateinit var dimNight: CheckBox
    private var brightness = Prefs.BRIGHTNESS_DEFAULT

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences(Prefs.NAME, MODE_PRIVATE)
        setContentView(R.layout.activity_settings)

        host = findViewById(R.id.host)
        port = findViewById(R.id.port)
        token = findViewById(R.id.token)
        endpoint = findViewById(R.id.endpoint)
        error = findViewById(R.id.error)
        brightnessValue = findViewById(R.id.brightness_value)
        drift = findViewById(R.id.drift)
        dimNight = findViewById(R.id.dim_night)

        val config = Config.load(prefs)
        host.setText(config.host)
        if (config.port != 0) port.setText(config.port.toString())
        token.setText(config.token)

        val connected = intent.getBooleanExtra(EXTRA_CONNECTED, false)
        val status = findViewById<TextView>(R.id.status)
        status.text = if (connected) {
            getString(R.string.settings_connected, intent.getStringExtra(EXTRA_GRID).orEmpty())
        } else {
            getString(R.string.settings_offline)
        }
        status.setTextColor(getColor(if (connected) R.color.accent else R.color.muted))

        val watcher = object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) = updateEndpoint()
        }
        host.addTextChangedListener(watcher)
        port.addTextChangedListener(watcher)
        updateEndpoint()

        drift.isChecked = prefs.getBoolean(Prefs.DRIFT, true)
        dimNight.isChecked = prefs.getBoolean(Prefs.DIM_NIGHT, true)
        paint(drift, R.string.settings_drift)
        paint(dimNight, R.string.settings_dim_night)
        drift.setOnClickListener { paint(drift, R.string.settings_drift) }
        dimNight.setOnClickListener { paint(dimNight, R.string.settings_dim_night) }

        brightness = prefs.getInt(Prefs.BRIGHTNESS, Prefs.BRIGHTNESS_DEFAULT)
        showBrightness()
        findViewById<View>(R.id.brightness_minus).setOnClickListener { stepBrightness(-STEP) }
        findViewById<View>(R.id.brightness_plus).setOnClickListener { stepBrightness(STEP) }

        findViewById<View>(R.id.scan).setOnClickListener { scan() }
        findViewById<View>(R.id.save).setOnClickListener { save() }
    }

    /** TUI checkbox: the box itself is a colored glyph, the label stays plain. */
    private fun paint(box: CheckBox, labelRes: Int) {
        val mark = if (box.isChecked) "[x] " else "[ ] "
        val text = SpannableString(mark + getString(labelRes))
        text.setSpan(
            ForegroundColorSpan(getColor(if (box.isChecked) R.color.accent else R.color.faint)),
            0,
            mark.length,
            SPAN_EXCLUSIVE_EXCLUSIVE,
        )
        box.text = text
    }

    private fun updateEndpoint() {
        val hostValue = host.text.toString().trim()
        val portValue = port.text.toString().toIntOrNull()
        endpoint.text = if (Config.isValid(hostValue, portValue)) {
            Config.url(hostValue, portValue!!)
        } else {
            getString(R.string.settings_endpoint_pending)
        }
    }

    private fun stepBrightness(delta: Int) {
        brightness = (brightness + delta).coerceIn(MIN, MAX)
        showBrightness()
    }

    private fun showBrightness() {
        brightnessValue.text = getString(R.string.settings_percent, brightness)
    }

    private fun save() {
        val hostValue = host.text.toString().trim()
        val portValue = port.text.toString().toIntOrNull()
        val tokenValue = token.text.toString()
        if (!Config.isValid(hostValue, portValue) || tokenValue.isEmpty()) {
            error.visibility = View.VISIBLE
            return
        }

        Config(hostValue, portValue!!, tokenValue).save(prefs)
        prefs.edit()
            .putBoolean(Prefs.DRIFT, drift.isChecked)
            .putBoolean(Prefs.DIM_NIGHT, dimNight.isChecked)
            .putInt(Prefs.BRIGHTNESS, brightness)
            .apply()
        setResult(RESULT_OK)
        finish()
    }

    private fun scan() {
        IntentIntegrator(this)
            .setDesiredBarcodeFormats(IntentIntegrator.QR_CODE)
            .setPrompt(getString(R.string.settings_scan_prompt))
            .setBeepEnabled(false)
            .setOrientationLocked(false)
            .initiateScan()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        val result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data)
        if (result == null) {
            super.onActivityResult(requestCode, resultCode, data)
            return
        }
        val contents = result.contents ?: return
        val pairing = Pairing.parse(contents)
        if (pairing == null) {
            error.text = getString(R.string.settings_pair_invalid)
            error.visibility = View.VISIBLE
            return
        }
        host.setText(pairing.host)
        port.setText(pairing.port.toString())
        token.setText(pairing.token)
    }

    companion object {
        const val EXTRA_CONNECTED = "connected"
        const val EXTRA_GRID = "grid"

        private const val STEP = 20
        private const val MIN = 20
        private const val MAX = 100
    }
}
