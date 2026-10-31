package com.vntrum.ansiko

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingTest {
    @Test
    fun parsesPairingUrl() {
        val pairing = Pairing.parse(
            "ansiko://pair?host=192.168.1.50&port=8765&token=abc-123_XYZ",
        )
        assertEquals("192.168.1.50", pairing?.host)
        assertEquals(8765, pairing?.port)
        assertEquals("abc-123_XYZ", pairing?.token)
    }

    @Test
    fun decodesEscapedValues() {
        val pairing = Pairing.parse(
            "ansiko://pair?host=ansiko.local&port=8765&token=a%2Bb%20c",
        )
        assertEquals("a+b c", pairing?.token)
    }

    @Test
    fun rejectsOtherCodes() {
        assertNull(Pairing.parse("https://example.com/?host=1.2.3.4&port=8765"))
        assertNull(Pairing.parse("ansiko://pair?host=1.2.3.4&port=0&token=x"))
        assertNull(Pairing.parse("ansiko://pair?host=1.2.3.4&port=8765"))
        assertNull(Pairing.parse("not a pairing code"))
    }
}
