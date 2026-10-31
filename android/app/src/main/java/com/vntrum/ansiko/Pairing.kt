package com.vntrum.ansiko

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

data class Pairing(val host: String, val port: Int, val token: String) {
    companion object {
        fun parse(raw: String): Pairing? {
            val uri = try {
                URI(raw.trim())
            } catch (e: Exception) {
                return null
            }
            if (uri.scheme != "ansiko" || uri.host != "pair") return null

            val values = try {
                uri.rawQuery
                    ?.split('&')
                    ?.filter { it.contains('=') }
                    ?.associate {
                        val index = it.indexOf('=')
                        decode(it.substring(0, index)) to decode(it.substring(index + 1))
                    }
            } catch (e: Exception) {
                null
            } ?: return null

            val host = values["host"]?.trim().orEmpty()
            val port = values["port"]?.toIntOrNull()
            val token = values["token"].orEmpty()
            if (host.isEmpty() || host.any { it.isWhitespace() }) return null
            if (host.contains("://") || host.contains('/')) return null
            if (port == null || port !in 1..65535 || token.isEmpty()) return null
            return Pairing(host, port, token)
        }

        private fun decode(value: String): String =
            URLDecoder.decode(value, StandardCharsets.UTF_8.name())
    }
}
