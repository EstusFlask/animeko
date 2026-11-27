/*
 * Copyright (C) 2024-2026 OpenAni and contributors.
 *
 * 此源代码的使用受 GNU AFFERO GENERAL PUBLIC LICENSE version 3 许可证的约束, 可以在以下链接找到该许可证.
 * Use of this source code is governed by the GNU AGPLv3 license, which can be found at the following link.
 *
 * https://github.com/open-ani/ani/blob/main/LICENSE
 */

@file:Suppress("INVISIBLE_MEMBER", "INVISIBLE_REFERENCE")

import org.gradle.testfixtures.ProjectBuilder
import org.jetbrains.kotlin.gradle.plugin.cocoapods.CocoapodsExtension
import org.jetbrains.kotlin.gradle.targets.native.tasks.PodGenTask
import org.jetbrains.kotlin.konan.target.Family
import kotlin.test.Test
import kotlin.test.assertEquals

class CocoaPodsRepositoryOrderTest {
    @Test
    fun `synthetic podfile resolves prepared pods before the public CDN`() {
        val project = ProjectBuilder.builder().build()
        val repository = "file:///prepared/onnxruntime-ios/specs.git"
        project.prioritizeCocoaPodsSpecRepository(repository)
        // Drive the pinned plugin's generator without an Apple toolchain.
        val task = project.tasks.register("podGenIos", PodGenTask::class.java).get().apply {
            family.set(Family.IOS)
            podName.set("application")
            platformSettings.set(CocoapodsExtension.PodspecPlatformSettings("ios", "16.0"))
            specRepos.set(CocoapodsExtension.SpecRepos().apply { url(repository) })
            pods.set(emptyList())
        }
        val podfile = task.podfile.get()
        podfile.parentFile.mkdirs()
        task.actions.forEach { it.execute(task) }

        val sources = podfile.readLines().filter { it.startsWith("source ") }
        assertEquals(
            listOf("source '$repository'", "source 'https://cdn.cocoapods.org'"),
            sources,
        )
    }
}
