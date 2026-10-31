package com.vntrum.ansiko

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConfigTest {

    @Test
    fun acceptsLanAddresses() {
        assertTrue(Config.isValid("192.168.1.50", 8080))
        assertTrue(Config.isValid("ansiko.local", 1))
        assertTrue(Config.isValid("phone", 65535))
    }

    @Test
    fun rejectsBrokenAddresses() {
        assertFalse(Config.isValid("", 8080))
        assertFalse(Config.isValid("192.168.1.50", null))
        assertFalse(Config.isValid("192.168.1.50", 0))
        assertFalse(Config.isValid("192.168.1.50", 65536))
        assertFalse(Config.isValid("192.168.1.50 8080", 8080))
        assertFalse(Config.isValid("192.168.1.50/path", 8080))
        assertFalse(Config.isValid("ws://192.168.1.50", 8080))
        assertFalse(Config.isValid("192.168.1.50:8080", 8080))
    }
}
