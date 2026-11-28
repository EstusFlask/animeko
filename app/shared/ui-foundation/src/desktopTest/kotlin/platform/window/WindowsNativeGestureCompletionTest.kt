/*
 * Copyright (C) 2024-2026 OpenAni and contributors.
 *
 * 此源代码的使用受 GNU AFFERO GENERAL PUBLIC LICENSE version 3 许可证的约束, 可以在以下链接找到该许可证.
 * Use of this source code is governed by the GNU AGPLv3 license, which can be found at the following link.
 *
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

package me.him188.ani.app.platform.window

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.PointerEventType
import androidx.compose.ui.input.pointer.PointerType
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class WindowsNativeGestureCompletionTest {
    private val firstRelease = RecordedNativeEvent(
        PointerEventType.Release,
        listOf(
            RecordedNativePointer(1, PointerType.Touch, false, Offset.Zero),
            RecordedNativePointer(2, PointerType.Touch, true, Offset.Zero),
        ),
    )
    private val finalRelease = RecordedNativeEvent(
        PointerEventType.Release,
        listOf(RecordedNativePointer(2, PointerType.Touch, false, Offset.Zero)),
    )

    @Test
    fun `partial release does not complete a two contact gesture`() {
        assertFailsWith<WindowsNativeInputAssertionException> {
            awaitNativeGestureRelease(listOf(firstRelease), timeoutMillis = 40)
        }
    }

    @Test
    fun `gesture completes after the final contact release`() {
        assertSame(finalRelease, awaitNativeGestureRelease(listOf(firstRelease, finalRelease)))
    }
}
