/*
 * Copyright (C) 2026 OpenAni and contributors.
 * Use of this source code is governed by the GNU AGPLv3 license.
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

package me.him188.ani.app.videoplayer.subtitle

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.openani.mediamp.source.UriMediaData
import org.openani.mediamp.test.TestMediampPlayer

class ExternalSubtitleControllerTest {
    @Test
    fun `external captions follow seeks and delay and are cleared on media changes`() = runTest {
        val player = TestMediampPlayer(backgroundScope.coroutineContext)
        val controller = ExternalSubtitleController(player, backgroundScope)
        val first = UriMediaData("https://test/video.mp4")
        player.setMediaData(first)
        runCurrent()
        assertTrue(controller.select("test.srt", caption.encodeToByteArray(), first))
        player.injectPosition(1500)
        runCurrent()
        assertEquals("Hello", controller.text.value)
        controller.offsetMillis.value = 1000
        runCurrent()
        assertEquals("", controller.text.value)
        player.injectPosition(2500)
        runCurrent()
        assertEquals("Hello", controller.text.value)
        player.injectPosition(500)
        runCurrent()
        assertEquals("", controller.text.value)
        player.setMediaData(UriMediaData("https://test/next.mp4"))
        runCurrent()
        assertNull(controller.selected.value)
        assertEquals(0L, controller.offsetMillis.value)
        assertFalse(controller.select("stale.srt", caption.encodeToByteArray(), first))
        player.close()
    }

    @Test
    fun `ASS dialogue accepts custom field order commas and line breaks`() {
        val cues = parseExternalSubtitle(
            """[Script Info]
                |Title: Test
                |[Events]
                |Format: Layer, End, Start, Style, Name, MarginL, MarginR, MarginV, Effect, Text
                |Dialogue: 0,0:00:03.00,0:00:01.25,Default,,0,0,0,,{\i1}Hello, world\NSecond line
                |Comment: 0,0:00:03.00,0:00:01.25,Default,,0,0,0,,Ignored
                |Dialogue: 0,0:00:03.00,0:00:01.25,Default,,0,0,0,,{\p1}m 0 0 l 20 20
            """.trimMargin().encodeToByteArray(),
        )
        assertEquals(SubtitleCue(1250, 3000, "Hello, world\nSecond line"), cues.single())
    }

    @Test
    fun `UTF16 BOM subtitles are decoded`() {
        val bytes = byteArrayOf(0xFF.toByte(), 0xFE.toByte()) + caption.flatMap {
            listOf((it.code and 255).toByte(), (it.code shr 8).toByte())
        }.toByteArray()
        assertEquals("Hello", parseExternalSubtitle(bytes).single().text)
    }

    private val caption = "1\n00:00:01,000 --> 00:00:03,000\nHello"
}
