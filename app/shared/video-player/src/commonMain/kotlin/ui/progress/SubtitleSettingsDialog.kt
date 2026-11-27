/*
 * Copyright (C) 2026 OpenAni and contributors.
 * Use of this source code is governed by the GNU AGPLv3 license.
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

package me.him188.ani.app.videoplayer.ui.progress

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt
import me.him188.ani.app.data.models.preference.SubtitleTextConversion
import me.him188.ani.app.domain.player.SubtitleTextConverter
import me.him188.ani.app.ui.lang.Lang
import me.him188.ani.app.ui.lang.subject_episode_close
import me.him188.ani.app.ui.lang.video_player_subtitle_conversion
import me.him188.ani.app.ui.lang.video_player_subtitle_conversion_description
import me.him188.ani.app.ui.lang.video_player_subtitle_font_size
import me.him188.ani.app.ui.lang.video_player_subtitle_font_size_hint
import me.him188.ani.app.ui.lang.video_player_subtitle_font_size_input
import me.him188.ani.app.ui.lang.video_player_subtitle_original
import me.him188.ani.app.ui.lang.video_player_subtitle_preview
import me.him188.ani.app.ui.lang.video_player_subtitle_reset
import me.him188.ani.app.ui.lang.video_player_subtitle_settings
import me.him188.ani.app.ui.lang.video_player_subtitle_simplified
import me.him188.ani.app.ui.lang.video_player_subtitle_traditional
import me.him188.ani.app.videoplayer.subtitle.SubtitleAppearance
import org.jetbrains.compose.resources.stringResource

@Composable
fun SubtitleSettingsDialog(
    fontScale: Float,
    onFontScaleChange: (Float) -> Unit,
    onDismissRequest: () -> Unit,
    textConversion: SubtitleTextConversion = SubtitleTextConversion.ORIGINAL,
    onTextConversionChange: (SubtitleTextConversion) -> Unit = {},
) {
    var scale by remember(fontScale) { mutableFloatStateOf(SubtitleAppearance(fontScale).effectiveFontScale) }
    var input by remember(fontScale) { mutableStateOf(formatSubtitleFontSize(SubtitleAppearance(fontScale).fontSize)) }
    val size = input.toFloatOrNull()
    val validSize = size != null && size.isFinite() && size in SubtitleAppearance.MinFontSize..SubtitleAppearance.MaxFontSize
    val converter = remember { SubtitleTextConverter() }
    val originalPreview = stringResource(Lang.video_player_subtitle_preview)
    val preview by produceState(originalPreview, originalPreview, textConversion) {
        value = converter.convert(originalPreview, textConversion)
    }
    AlertDialog(
        onDismissRequest = onDismissRequest,
        title = { Text(stringResource(Lang.video_player_subtitle_settings)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(Lang.video_player_subtitle_font_size, "${(scale * 100).roundToInt()}%"), Modifier.testTag("SubtitleSizeLabel"))
                OutlinedTextField(
                    value = input,
                    onValueChange = { value ->
                        input = value
                        value.toFloatOrNull()?.takeIf {
                            it.isFinite() && it in SubtitleAppearance.MinFontSize..SubtitleAppearance.MaxFontSize
                        }?.let { scale = it / SubtitleAppearance.DefaultFontSize }
                    },
                    label = { Text(stringResource(Lang.video_player_subtitle_font_size_input)) },
                    supportingText = { Text(stringResource(Lang.video_player_subtitle_font_size_hint)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    isError = !validSize,
                    modifier = Modifier.fillMaxWidth().testTag("SubtitleFontSizeInput"),
                )
                Slider(
                    value = scale,
                    onValueChange = {
                        scale = (it * 100).roundToInt() / 100f
                        input = formatSubtitleFontSize(scale * SubtitleAppearance.DefaultFontSize)
                    },
                    onValueChangeFinished = { onFontScaleChange(scale) },
                    valueRange = SubtitleAppearance.MinFontSize / SubtitleAppearance.DefaultFontSize..SubtitleAppearance.MaxFontSize / SubtitleAppearance.DefaultFontSize,
                    modifier = Modifier.testTag("SubtitleFontScale"),
                )
                Text(stringResource(Lang.video_player_subtitle_conversion))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (option in SubtitleTextConversion.entries) {
                        FilterChip(
                            selected = option == textConversion,
                            onClick = { onTextConversionChange(option) },
                            label = { Text(stringResource(when (option) {
                                SubtitleTextConversion.ORIGINAL -> Lang.video_player_subtitle_original
                                SubtitleTextConversion.SIMPLIFIED -> Lang.video_player_subtitle_simplified
                                SubtitleTextConversion.TRADITIONAL -> Lang.video_player_subtitle_traditional
                            })) },
                            modifier = Modifier.testTag("SubtitleConversion-${option.name}"),
                        )
                    }
                }
                Text(stringResource(Lang.video_player_subtitle_conversion_description), style = MaterialTheme.typography.bodySmall)
                Text(
                    preview,
                    modifier = Modifier.fillMaxWidth().clipToBounds().background(Color.Black)
                        .padding(horizontal = 16.dp, vertical = 20.dp).testTag("SubtitleSizePreview"),
                    color = Color.White,
                    fontSize = (22 * scale).sp,
                    lineHeight = (28 * scale).sp,
                    textAlign = TextAlign.Center,
                    maxLines = 4,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onFontScaleChange(scale); onDismissRequest() }, enabled = validSize) {
                Text(stringResource(Lang.subject_episode_close))
            }
        },
        dismissButton = {
            TextButton(onClick = { scale = 1f; input = "38"; onFontScaleChange(1f) }, modifier = Modifier.testTag("ResetSubtitleSize")) {
                Text(stringResource(Lang.video_player_subtitle_reset))
            }
        },
    )
}

private fun formatSubtitleFontSize(value: Float): String =
    if (value == value.toInt().toFloat()) value.toInt().toString() else ((value * 10).roundToInt() / 10f).toString()
