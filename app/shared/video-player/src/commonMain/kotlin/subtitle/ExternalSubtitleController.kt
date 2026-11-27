/*
 * Copyright (C) 2026 OpenAni and contributors.
 * Use of this source code is governed by the GNU AGPLv3 license.
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

package me.him188.ani.app.videoplayer.subtitle

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.openani.mediamp.MediampPlayer
import org.openani.mediamp.features.subtitleTracks
import org.openani.mediamp.source.MediaData

data class ExternalSubtitle(val name: String, val timeline: SubtitleCueTimeline, internal val media: MediaData)

/** 外挂文本字幕按媒体会话隔离，播放器的位置流同时驱动播放、暂停与 seek 后的对白。 */
class ExternalSubtitleController(private val player: MediampPlayer, scope: CoroutineScope) {
    private val _selected = MutableStateFlow<ExternalSubtitle?>(null)
    val selected = _selected.asStateFlow()
    val offsetMillis = MutableStateFlow(0L)
    private val _text = MutableStateFlow("")
    val text = _text.asStateFlow()

    init {
        scope.launch(player.mainDispatcher) {
            player.mediaData.collectLatest { current ->
                if (_selected.value?.media !== current) {
                    clear()
                }
            }
        }
        combine(player.currentPositionMillis, selected, offsetMillis, player.mediaData) { position, subtitle, offset, current ->
            if (current === subtitle?.media) subtitle?.timeline?.textAt(position - offset).orEmpty() else ""
        }.distinctUntilChanged().onEach { _text.value = it }
            .launchIn(CoroutineScope(scope.coroutineContext + player.mainDispatcher))
        scope.launch(player.mainDispatcher) {
            player.subtitleTracks?.selected?.collect { if (it != null) clear() }
        }
    }

    /** 只允许发起读取时的媒体安装字幕，异步导入完成时视频可能已被切换。 */
    suspend fun select(name: String, bytes: ByteArray, expectedMedia: MediaData): Boolean {
        if (player.mediaData.value !== expectedMedia) return false
        val cues = withContext(Dispatchers.Default) { parseExternalSubtitle(bytes) }
        require(cues.isNotEmpty()) { "No readable subtitle cues" }
        return withContext(player.mainDispatcher) {
            if (player.mediaData.value !== expectedMedia) return@withContext false
            player.subtitleTracks?.select(null)
            offsetMillis.value = 0
            _selected.value = ExternalSubtitle(name, SubtitleCueTimeline(cues), expectedMedia)
            true
        }
    }

    fun clear() {
        _selected.value = null
        offsetMillis.value = 0
        _text.value = ""
    }
}

/** UTF-8 或带 BOM 的 UTF-16；ASS/SSA 读取对白与时间，样式标签不进入文本层。 */
fun parseExternalSubtitle(bytes: ByteArray): List<SubtitleCue> {
    require(bytes.size <= 16 * 1024 * 1024) { "Subtitle file is too large" }
    val text = if (bytes.size >= 2 &&
        ((bytes[0] == 0xFF.toByte() && bytes[1] == 0xFE.toByte()) ||
                (bytes[0] == 0xFE.toByte() && bytes[1] == 0xFF.toByte()))
    ) {
        val littleEndian = bytes[0] == 0xFF.toByte()
        buildString {
            var index = 2
            while (index + 1 < bytes.size) {
                val a = bytes[index].toInt() and 255
                val b = bytes[index + 1].toInt() and 255
                append((if (littleEndian) a or (b shl 8) else (a shl 8) or b).toChar())
                index += 2
            }
        }
    } else bytes.decodeToString(throwOnInvalidSequence = true).removePrefix("\uFEFF")
    if (!text.contains("[Events]", ignoreCase = true)) return parseSubtitleCues(text)
    var inEvents = false
    var format = listOf("layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text")
    return text.lineSequence().mapNotNull { raw ->
        val line = raw.trim()
        if (line.startsWith('[')) inEvents = line.equals("[Events]", ignoreCase = true)
        if (!inEvents) return@mapNotNull null
        if (line.startsWith("Format:", ignoreCase = true)) {
            format = line.substringAfter(':').split(',').map { it.trim().lowercase() }
        }
        if (!line.startsWith("Dialogue:", ignoreCase = true)) return@mapNotNull null
        val parts = line.substringAfter(':').trimStart().split(',', limit = format.size)
        fun field(name: String) = parts.getOrNull(format.indexOf(name)) ?: ""
        if (Regex("""\\p[1-9]""").containsMatchIn(field("text"))) return@mapNotNull null
        val content = field("text").replace(Regex("\\{[^}]*}"), "")
            .replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
        parseSubtitleCues("${field("start")} --> ${field("end")}\n$content").firstOrNull()
    }.sortedBy { it.startMillis }.toList()
}
