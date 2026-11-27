/*
 * Copyright (C) 2026 OpenAni and contributors.
 * Use of this source code is governed by the GNU AGPLv3 license.
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

package me.him188.ani.app.videoplayer.subtitle

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun ExternalSubtitleOverlay(controller: ExternalSubtitleController, modifier: Modifier = Modifier) {
    val text by controller.text.collectAsState()
    if (text.isEmpty()) return
    val safeArea = LocalSubtitleSafeArea.current
    val appearance = LocalSubtitleAppearance.current
    val density = LocalDensity.current
    BoxWithConstraints(modifier.fillMaxSize()) {
        // 与 mpv 的默认文本字幕一致，以播放器高度 720 时字号 38 为基准。
        // 字幕相对画面的大小由字幕设置决定，界面字体缩放不参与视频内排版。
        val fontSize = with(density) { (maxHeight * (38f / 720f) * appearance.effectiveFontScale).toSp() }
        val region = subtitleRegion(maxWidth.value.toDouble(), maxHeight.value.toDouble(), safeArea)
        Box(
            Modifier.offset(region.left.dp, region.top.dp).size(region.width.dp, region.height.dp).clipToBounds(),
            contentAlignment = Alignment.BottomCenter,
        ) {
            Text(
                text,
                Modifier.fillMaxWidth().testTag("ExternalSubtitleText"),
                color = Color.White,
                maxLines = 6,
                overflow = TextOverflow.Ellipsis,
                style = TextStyle(
                    fontSize = fontSize,
                    shadow = Shadow(Color.Black, blurRadius = 4f),
                    textAlign = TextAlign.Center,
                ),
            )
        }
    }
}
