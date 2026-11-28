# GitHub Actions Workflows

`build.yml` 和 `release.yml` 由 `src.main.kts` 生成而来。详情参考 <https://typesafegithub.github.io/github-workflows-kt/>。

`Build` 对 `main`、`release/**`、`emby-fix2`、`codex/opensubtitles-local-subtitles` 和 `codex/ci-cd` 的代码推送自动运行，
也支持手动选择分支运行。Windows 的 x64、ARM64 产物由 `createReleaseDistributable` 生成，属于 Release 便携包；
Android 的普通分支检查产物为 Debug APK。打包、测试检查和产物验证是不同步骤，上传产物不代表整个工作流通过。

依赖准备步骤通过 `ci-helper/run-gradle-with-retry.py` 执行 Gradle。依赖仓库返回 HTTP 429 时等待 30、60 秒重试，
编译、测试和其他错误直接保留原退出码；工作流中各步骤的外层重试策略独立生效。
Android Gradle 插件通过插件解析规则直接使用同版本的 `com.android.tools.build:gradle` 实现包；
Android、AndroidX 和 Google 组件优先查询 Google Maven 仓库。
`CI=true` 时，主构建和 `build-logic` 的其余组件优先使用
[Google 托管的 Maven Central 镜像](https://docs.cloud.google.com/docs/buildpacks/java#google_cloud_hosted_maven_central_mirror)，其余仓库继续提供镜像中缺少的组件。

托管的 Ubuntu 构建与 Android 设备测试任务中，Gradle 与 Kotlin 编译器的最大堆合计为 7 GB，
最多使用两个 worker，为系统和原生编译工具保留内存。设备测试 APK 只包含模拟器使用的 ABI，应用打包任务覆盖全部发布 ABI。
Windows 便携包验证的数据、应用日志和进程输出保存在 `update-e2e/windows-verify-*`，
失败诊断随验证产物上传，原生输入断言和异常详情同时写入任务日志。
Windows 验证脚本自测为每个子进程提供 120 秒预算，覆盖托管 ARM64 runner 的启动延迟，
并校验成功与失败的退出码、标准输出、标准错误和应用诊断日志。

`pr-images.yml` 直接维护，拒绝 PR 在资源目录以外新增图片和视频，防止验证截图进入 git 历史。

`datasource-test-mcp.yml` 直接维护，构建自带 JBR 的 `tools/datasource-test-mcp` Windows 发行包，不依赖仓库环境即可运行，用法见该工具的 README。

`codex-agent.yml` 直接维护。新 issue 的分类器会读取组织级 `Priority` 字段的选项，校验模型输出后填写空缺的优先级，保留已有值。P0–P3 labels 已过时，不参与分类。

`OPENANI_BOT_TOKEN` 需要仓库 Issues 写权限和组织 Issue Fields 读权限（classic PAT 对应 `repo` 和 `read:org`）。机器人必须是组织成员，才能读取仅成员可见的 Priority 字段。
字段写入使用 [issue field values API](https://docs.github.com/en/rest/issues/issue-field-values#add-issue-field-values-to-an-issue)，不需要 Projects 权限。

在 PR 的 Reviewers 里请求 `openanibot` 会触发 `qa` job：Codex 以测试工程师的身份构建 PR、运行受影响模块的自动化测试、在 Android 模拟器和打包后的 macOS 桌面应用里按用户操作验证功能，然后把带截图的测试报告作为 PR review 提交（approve / request changes / comment）。它只评价行为，不评价代码写法，也不会推送任何内容。

- 只有仓库 write 权限以上的人发起的请求才会触发。bot 的 review 和普通 reviewer 的一样，maintainer 可以 dismiss。
- 判定以 runner 能做到的为限：PR 的核心声明在模拟器 / 桌面应用里实测通过、范围内没有缺陷就 approve。实体设备和遥控器、iOS / Windows / Linux、真人按键时序、压力测试等 runner 做不到的只列为未测试，不影响结论；只有核心声明本身无法在 runner 上验证（环境导致构建失败、功能只存在于缺失的平台、截图上传失败）才仅 comment。
- 每次请求都是对当前 head 的一次完整重测，使用全新的 Codex 会话，不复用 `iterate` 的对话；测试进行中收到新请求时取消旧测试，避免对过期 commit 出报告。
- PR 作者没有 write 权限时，测试固定在请求时刻的 commit，与 `iterate` job 的策略一致。
- GitHub 不允许把 PR 作者加为 reviewer，所以 openanibot 自己开的 PR 无法用这个方式测试。
- 想让 bot 重点测试某些场景，写在 PR 描述或普通评论里即可。评论里不要 @openanibot，那会触发 `iterate` job。
- 登录用的测试帐号来自仓库 secrets `ANI_TEST_ACCOUNT_EMAIL` 和 `ANI_TEST_ACCOUNT_OTP`：在 ani-api-server 的管理后台把某个帐号设为测试帐号（权限 `users.test-account`，固定 6 位验证码登录、不发邮件，验证码在用户详情的"绑定"分区查看），再把邮箱和验证码填进这两个 secret，两者都要设置。`implement`、`iterate`、`qa`、`respond` 四个 job 都把它们放进环境并写进 prompt。标记保存在服务端用户库里：生产服务器和用 `--server-db production` 启动的本地服务器都能用这个帐号。没有配置时 bot 无法登录生产服务器，需要登录的场景会报告为未测试。
- 生产库连接串来自 secret `ANI_SERVER_PROD_MONGODB_CONNECTION_STRING`：Mongo 用户 `ani-agent`（对 `ani-production` 读写、对 `animedb` 只读）经 Railway 的 TCP 代理连 mongo-1。四个 job 把它同时放进 `ANI_SERVER_PROD_MONGODB_CONNECTION_STRING` 和 `ANI_SERVER_PROD_ANIMEDB_CONNECTION_URL`，ani-api-server 的 animeko-server-local-test-server skill 用 `--server-db production --animedb production` 启动时自动读取，agent 就能在本地起一个连着生产数据的服务器用测试帐号登录。prompt 只告诉 agent 连接串在环境里，不写出内容。
- 本地库模式（skill 默认的 `--server-db local`）没有生产帐号：启动脚本会自动在本地库建一个测试帐号，邮箱和验证码写到服务端仓库的 `test-sandbox/local-test-account.json`，agent 用它登录。
- Codex 结束时没有提交 review，workflow 会在 PR 上留一条失败评论并标红；review 请求保持待处理，重新请求即可重试。

离线回归测试（执行 workflow 中的 shell，使用模拟 `gh`，不会修改 GitHub）：

```shell
uv run --with pyyaml python .github/workflows/test_issue_classification.py
uv run --with pyyaml python .github/workflows/test_qa_review.py
```

## iOS Release 与 LiveContainer 源

`main` 是默认分支，保存上游代码、功能修改及其测试，Workflow 与发行配置使用上游版本。
`codex/ci-cd` 基于 `main` 保存 fork 的 Runner、依赖准备、验证脚本和发行配置。
功能与上游 PR 从 `main` 或专用功能分支整理；构建分支通过合并 `main` 接收功能更新，CI 分支的发行提交不合回 `main`。

```shell
git switch codex/ci-cd
git merge main
git push origin codex/ci-cd
```

推送 `codex/ci-cd` 运行常规构建与 iOS Release IPA 构建，iOS 只上传产物，不发布 Release。
发布 iOS 时，在包含 CI 配置的提交上创建 `fork-ios/**` 标签并推送，例如：

```shell
git tag fork-ios/20261128-1 codex/ci-cd
git push origin refs/tags/fork-ios/20261128-1
```

`fork-ios/**` 标签构建成功后发布 Release，并更新 LiveContainer 源。
手工编辑、删除或发布 IPA Release 后，可在 CI 分支上推送唯一的 `fork-source/**` 标签来重建源。
自定义工作流同时保留 `workflow_dispatch`，其网页入口受默认分支上的工作流定义约束；推送与标签入口不依赖该入口。

`ios-livecontainer-release.yml` 直接维护，手动选择源分支或 commit（留空时使用运行工作流时选择的分支），通过上游 Gradle 任务构建 Release IPA，
发布 `Animeko <版本号>`，资产名为 `Animeko-<版本号>.ipa`，应用名称为 `Animeko`、bundle ID 为 `org.animeko.animeko`。
`publish_release=false` 时仅上传构建产物与诊断，不发布 Release 或更新 LiveContainer 源，适用于分支验证。
ONNX Runtime iOS 依赖由 `prepare_onnxruntime_ios.py` 准备：验证固定 SHA512 的 Microsoft NuGet 包，
提取设备与模拟器 XCFramework，并校验 Objective-C 源码提交与 NuGet 元数据一致。
源码从 ROCm 的 ONNX Runtime 仓库按固定上游提交读取。临时 CocoaPods spec 仓库同时供宿主 Podfile 和 Kotlin 合成项目使用，
其中归档通过 SHA256 校验；运行库版本与 `libs.versions.toml` 一致。仓库同时包含经过 SHA256 校验的 Sentry 8.49.2 官方 podspec，
满足宿主的 `~> 8.49.0` 约束。构建依赖规格仅从准备的仓库解析，Sentry 源码仍由 CocoaPods 从官方仓库下载，
依赖解析不访问公共 CDN。构建准备阶段运行离线回归测试、安装合成项目依赖并校验仓库配置。
显示版本移除开发后缀，构建号单调递增。Release 同时包含 `ios-release.json` 元数据与 SHA256 校验。

LiveContainer 订阅地址固定为 `https://github.com/EstusFlask/animeko/releases/download/livecontainer-source/source.json`。
`livecontainer-source.yml` 在推送 `fork-source/**` 标签时更新此资产，也支持手动运行。
`livecontainer-source` 自身是独立的预发布源资产，不参与应用版本列表，不标记为最新应用 Release。

手动发布时，先把 IPA 上传到草稿 Release，再点击发布；脚本可直接读取 IPA 的 Info.plist，无需自行编写源文件。
源只收录正式发布且包含一个 Animeko IPA 的 Release，并保留历史版本。通过构建工作流发布时会直接调用相同脚本，
因为 GITHUB_TOKEN 发出的 Release 事件不会触发其它工作流。将每次构建的旧源地址替换为上述固定地址后，后续无需重复添加源。
