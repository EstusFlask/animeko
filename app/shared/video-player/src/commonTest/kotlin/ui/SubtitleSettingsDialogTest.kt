/*
 * Copyright (C) 2026 OpenAni and contributors.
 * Use of this source code is governed by the GNU AGPLv3 license.
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

package me.him188.ani.app.videoplayer.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.test.performTextReplacement
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import me.him188.ani.app.data.models.preference.SubtitleTextConversion
import me.him188.ani.app.ui.foundation.ProvideCompositionLocalsForPreview
import me.him188.ani.app.ui.framework.runAniComposeUiTest
import me.him188.ani.app.ui.lang.Lang
import me.him188.ani.app.ui.lang.subject_episode_close
import me.him188.ani.app.videoplayer.ui.progress.SubtitleSettingsDialog
import org.jetbrains.compose.resources.stringResource

class SubtitleSettingsDialogTest {
    @Test
    fun `subtitle conversion offers original simplified and traditional independently of size`() = runAniComposeUiTest {
        var target by mutableStateOf(SubtitleTextConversion.ORIGINAL)
        var scale by mutableFloatStateOf(1f)
        setContent {
            ProvideCompositionLocalsForPreview {
                SubtitleSettingsDialog(scale, { scale = it }, {}, target, { target = it })
            }
        }
        for (option in listOf(SubtitleTextConversion.TRADITIONAL, SubtitleTextConversion.SIMPLIFIED, SubtitleTextConversion.ORIGINAL)) {
            onNodeWithTag("SubtitleConversion-${option.name}").performClick().assertIsSelected()
            runOnIdle { assertEquals(option, target); assertEquals(1f, scale) }
        }
        onNodeWithTag("SubtitleFontSizeInput").assertTextContains("38")
    }

    @Test
    fun `subtitle size label contains one percent sign`() = runAniComposeUiTest {
        setContent {
            ProvideCompositionLocalsForPreview {
                SubtitleSettingsDialog(1f, {}, {})
            }
        }
        val label = onNodeWithTag("SubtitleSizeLabel").fetchSemanticsNode().config[SemanticsProperties.Text].single().text
        assertEquals(1, label.count { it == '%' })
    }

    @Test
    fun `subtitle font size can be typed directly and invalid input is not saved`() = runAniComposeUiTest {
        var scale by mutableFloatStateOf(1f)
        var close = ""
        setContent {
            ProvideCompositionLocalsForPreview {
                close = stringResource(Lang.subject_episode_close)
                SubtitleSettingsDialog(scale, { scale = it }, {})
            }
        }
        onNodeWithTag("SubtitleFontSizeInput").performTextReplacement("57")
        onNodeWithText(close).performClick()
        runOnIdle { assertEquals(1.5f, scale) }
        onNodeWithTag("SubtitleFontSizeInput").performTextReplacement("invalid")
        onNodeWithText(close).performClick()
        runOnIdle { assertEquals(1.5f, scale) }
    }

    @Test
    fun `subtitle size can increase reset and close with a visible multiline preview`() = runAniComposeUiTest {
        var scale by mutableFloatStateOf(1f)
        var visible by mutableStateOf(true)
        var close = ""
        setContent {
            ProvideCompositionLocalsForPreview {
                close = stringResource(Lang.subject_episode_close)
                if (visible) SubtitleSettingsDialog(scale, { scale = it }, { visible = false })
            }
        }
        onNodeWithTag("SubtitleFontScale").performSemanticsAction(SemanticsActions.SetProgress) { it(2f) }
        onNodeWithTag("SubtitleSizePreview").assertIsDisplayed()
        onNodeWithText(close).performClick()
        runOnIdle { assertEquals(2f, scale); visible = true }
        onNodeWithTag("ResetSubtitleSize").performClick()
        runOnIdle { assertEquals(1f, scale) }
        onNodeWithText(close).performClick()
        runOnIdle { assertFalse(visible) }
    }
}
