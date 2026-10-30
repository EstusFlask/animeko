/*
 * Copyright (C) 2026 OpenAni and contributors.
 *
 * 此源代码的使用受 GNU AFFERO GENERAL PUBLIC LICENSE version 3 许可证的约束, 可以在以下链接找到该许可证.
 * Use of this source code is governed by the GNU AGPLv3 license, which can be found at the following link.
 *
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

package me.him188.ani.app.ui.settings.tabs.media.source

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.flow.flowOf
import me.him188.ani.app.ui.foundation.ProvideCompositionLocalsForPreview
import me.him188.ani.app.ui.framework.runAniComposeUiTest
import me.him188.ani.datasources.api.source.FactoryId
import me.him188.ani.datasources.api.source.MediaSourceConfig
import me.him188.ani.datasources.api.source.MediaSourceInfo
import me.him188.ani.datasources.api.source.parameter.buildMediaSourceParameters
import me.him188.ani.datasources.api.source.parameter.hasValue
import me.him188.ani.datasources.jellyfin.EmbyMediaSource
import me.him188.ani.datasources.webdav.WebDavMediaSource

class EditMediaSourceDialogTest {
    @Test
    fun `emby accepts a named server and username with an empty password`() = runAniComposeUiTest {
        val factory = EmbyMediaSource.Factory()
        val state = EditingMediaSource(
            editingMediaSourceId = "emby-instance",
            factoryId = factory.factoryId,
            info = factory.info,
            parameters = factory.parameters,
            persistedArguments = flowOf(MediaSourceConfig.Default),
            editMediaSourceMode = EditMediaSourceMode.Add(factory.factoryId),
            onSave = {},
            parentCoroutineContext = EmptyCoroutineContext,
        )
        try {
            setContent {
                ProvideCompositionLocalsForPreview { EditMediaSourceDialog(state, onDismissRequest = {}) }
            }
            onNodeWithTag(EditMediaSourceTestTags.argument("name")).performTextInput("Living room")
            onNodeWithTag(EditMediaSourceTestTags.argument("authMode")).performScrollTo().performClick()
            onNodeWithTag(EditMediaSourceTestTags.enumOption("authMode", EmbyMediaSource.AUTH_MODE_USERNAME_PASSWORD)).performClick()
            onNodeWithTag(EditMediaSourceTestTags.argument("username")).performScrollTo().performTextInput("test-user")
            onNodeWithTag(EditMediaSourceTestTags.argument("password"))
                .assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.Password))
            onNodeWithTag(EditMediaSourceTestTags.argument("apikey")).assertDoesNotExist()
            assertFalse(state.hasError)
            val config = state.createConfig()
            assertEquals("Living room", config.arguments["name"])
            assertEquals("test-user", config.arguments["username"])
            assertEquals("", config.arguments["password"])
        } finally {
            state.close()
        }
    }

    @Test
    fun `webdav configuration saves a named anonymous server`() = runAniComposeUiTest {
        val factory = WebDavMediaSource.Factory()
        val state = EditingMediaSource(
            editingMediaSourceId = "webdav-instance",
            factoryId = factory.factoryId,
            info = factory.info,
            parameters = factory.parameters,
            persistedArguments = flowOf(MediaSourceConfig.Default),
            editMediaSourceMode = EditMediaSourceMode.Add(factory.factoryId),
            onSave = {},
            parentCoroutineContext = EmptyCoroutineContext,
        )
        try {
            setContent {
                ProvideCompositionLocalsForPreview { EditMediaSourceDialog(state, onDismissRequest = {}) }
            }
            assertTrue(state.hasError)
            onNodeWithTag(EditMediaSourceTestTags.argument("name")).performTextInput("NAS")
            onNodeWithTag(EditMediaSourceTestTags.argument("baseUrl")).performTextInput("https://nas.test/dav/")
            assertFalse(state.hasError)
            assertEquals("https://nas.test/dav/", state.createConfig().arguments["baseUrl"])
        } finally {
            state.close()
        }
    }

    @Test
    fun `switching authentication mode shows only its credential fields`() = runAniComposeUiTest {
        val apiKeyMode = "apiKey"
        val passwordMode = "usernamePassword"
        val parameters = buildMediaSourceParameters {
            string("baseUrl", defaultProvider = { "http://localhost:8096" })
            val authMode = simpleEnum("authMode", apiKeyMode, passwordMode, default = apiKeyMode)
            string("userId", visibleWhen = authMode.hasValue(apiKeyMode))
            string("apikey", visibleWhen = authMode.hasValue(apiKeyMode))
            string("username", visibleWhen = authMode.hasValue(passwordMode))
            string("password", visibleWhen = authMode.hasValue(passwordMode))
        }
        val state = EditingMediaSource(
            editingMediaSourceId = "test",
            factoryId = FactoryId("test"),
            info = MediaSourceInfo(
                displayName = "Conditional source",
                description = "Test data source",
            ),
            parameters = parameters,
            persistedArguments = flowOf(MediaSourceConfig.Default),
            editMediaSourceMode = EditMediaSourceMode.Add(FactoryId("test")),
            onSave = {},
            parentCoroutineContext = EmptyCoroutineContext,
        )

        setContent {
            ProvideCompositionLocalsForPreview {
                EditMediaSourceDialog(state, onDismissRequest = {})
            }
        }

        onNodeWithTag(EditMediaSourceTestTags.argument("baseUrl")).assertExists()
        onNodeWithTag(EditMediaSourceTestTags.argument("authMode")).assertExists()
        onNodeWithTag(EditMediaSourceTestTags.argument("userId")).assertExists()
        onNodeWithTag(EditMediaSourceTestTags.argument("apikey")).assertExists()
        onNodeWithTag(EditMediaSourceTestTags.argument("username")).assertDoesNotExist()
        onNodeWithTag(EditMediaSourceTestTags.argument("password")).assertDoesNotExist()
        assertTrue(state.hasError)

        onNodeWithTag(EditMediaSourceTestTags.argument("userId")).performTextInput("test-user-id")
        onNodeWithTag(EditMediaSourceTestTags.argument("apikey")).performTextInput("test-api-key")
        assertFalse(state.hasError)

        onNodeWithTag(EditMediaSourceTestTags.argument("authMode")).performClick()
        onNodeWithTag(EditMediaSourceTestTags.enumOption("authMode", passwordMode)).performClick()

        onNodeWithTag(EditMediaSourceTestTags.argument("baseUrl")).assertExists()
        onNodeWithTag(EditMediaSourceTestTags.argument("authMode")).assertExists()
        onNodeWithTag(EditMediaSourceTestTags.argument("userId")).assertDoesNotExist()
        onNodeWithTag(EditMediaSourceTestTags.argument("apikey")).assertDoesNotExist()
        onNodeWithTag(EditMediaSourceTestTags.argument("username")).assertExists()
        onNodeWithTag(EditMediaSourceTestTags.argument("password")).assertExists()
        assertTrue(state.hasError)

        onNodeWithTag(EditMediaSourceTestTags.argument("username")).performTextInput("test-user")
        onNodeWithTag(EditMediaSourceTestTags.argument("password")).performTextInput("test-password")
        assertFalse(state.hasError)

        state.close()
    }
}
