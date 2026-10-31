package com.vntrum.ansiko

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Typeface
import android.util.TypedValue
import android.view.View
import com.termux.terminal.TerminalEmulator
import com.termux.terminal.TerminalOutput
import com.termux.terminal.TerminalSession
import com.termux.terminal.TerminalSessionClient
import com.termux.view.TerminalRenderer
import kotlin.math.max

/** Read-only terminal surface. Bytes arrive from the socket; the device sends nothing. */
class TerminalDisplayView(context: Context) : View(context) {

    var onGridChanged: ((cols: Int, rows: Int) -> Unit)? = null

    private val renderer = TerminalRenderer(
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 14f, resources.displayMetrics).toInt(),
        Typeface.MONOSPACE,
    )

    // TerminalEmulator only needs these callbacks for replies and side effects, which a
    // display-only client never performs.
    private val output = object : TerminalOutput() {
        override fun write(data: ByteArray, offset: Int, count: Int) {}
        override fun titleChanged(oldTitle: String, newTitle: String) {}
        override fun onCopyTextToClipboard(text: String) {}
        override fun onPasteTextFromClipboard() {}
        override fun onBell() {}
        override fun onColorsChanged() {}
    }

    private val client = object : TerminalSessionClient {
        override fun onTextChanged(changedSession: TerminalSession) {}
        override fun onTitleChanged(changedSession: TerminalSession) {}
        override fun onSessionFinished(finishedSession: TerminalSession) {}
        override fun onCopyTextToClipboard(session: TerminalSession, text: String) {}
        override fun onPasteTextFromClipboard(session: TerminalSession?) {}
        override fun onBell(session: TerminalSession) {}
        override fun onColorsChanged(session: TerminalSession) {}
        override fun onTerminalCursorStateChange(state: Boolean) {}
        override fun getTerminalCursorStyle(): Int? = null
        override fun logError(tag: String, message: String) {}
        override fun logWarn(tag: String, message: String) {}
        override fun logInfo(tag: String, message: String) {}
        override fun logDebug(tag: String, message: String) {}
        override fun logVerbose(tag: String, message: String) {}
        override fun logStackTraceWithMessage(tag: String, message: String, e: Exception) {}
        override fun logStackTrace(tag: String, e: Exception) {}
    }

    private var emulator = newEmulator(4, 2)

    init {
        setBackgroundColor(Color.BLACK)
        isFocusable = false
        isFocusableInTouchMode = false
    }

    fun feed(bytes: ByteArray) {
        if (bytes.isEmpty()) return
        emulator.append(bytes, bytes.size)
        invalidate()
    }

    /** A full reset replaces the emulator; TerminalEmulator.reset() keeps the screen contents. */
    fun reset() {
        emulator = newEmulator(emulator.mColumns, emulator.mRows)
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        if (w <= 0 || h <= 0) return

        val cols = max(4, (w / renderer.fontWidth).toInt())
        val rows = max(2, h / renderer.fontLineSpacing - 1)
        if (cols == emulator.mColumns && rows == emulator.mRows) return

        emulator.resize(cols, rows)
        invalidate()
        onGridChanged?.invoke(cols, rows)
    }

    override fun onDraw(canvas: Canvas) {
        canvas.drawColor(Color.BLACK)
        renderer.render(emulator, canvas, 0, -1, -1, -1, -1)
    }

    private fun newEmulator(cols: Int, rows: Int) =
        TerminalEmulator(output, cols, rows, 100, client)
}
