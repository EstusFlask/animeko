# GitHub Actions Workflows

`build.yml` 和 `release.yml` 由 `src.main.kts` 生成而来。详情参考 <https://typesafegithub.github.io/github-workflows-kt/>。

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

## Fork 多平台 Release

`fork-release.yml` 直接维护，手动指定应用源码 `source_ref` 与版本标签 `release_tag`。
Android 与桌面构建使用附带 JCEF 的 JetBrains Runtime 21，满足仓库的 `jvm.toolchain.vendor=jetbrains` 要求。
发布分支的运行入口是已有的 `ios-livecontainer-release.yml`：选择发布分支，并填写非空的 `release_tag`，
调用该分支的多平台工作流；`release_tag` 留空时构建独立 iOS IPA。
Android 与桌面平台使用同一份固定 commit，已有标签必须指向该 commit；源码的基础版本必须与标签一致。
包含 Android 手机与 TV（arm64-v8a、armeabi-v7a、x86_64、universal）、Windows x64/ARM64、
macOS Intel/Apple Silicon、Linux x64，以及从 `ios_release_tag`（默认 `v4.9.1`）复用的已发布 iOS IPA。
各平台先上传 Actions artifacts，全部成功且资产齐全后统一写入 GitHub Release，并更新 LiveContainer 源。
资产包含桌面更新清单、AppImage zsync 与全平台 `SHA256SUMS`，不依赖 S3、自托管机器、Codex 或 App Store Connect。

Android 必需 repository secrets：`SIGNING_RELEASE_STOREFILE`（密钥文件的 base64）、
`SIGNING_RELEASE_STOREPASSWORD`、`SIGNING_RELEASE_KEYALIAS`、`SIGNING_RELEASE_KEYPASSWORD`。
弹弹play 功能需要 `DANDANPLAY_APP_ID` 与 `DANDANPLAY_APP_SECRET`。
密钥、密码与本地配置不属于仓库文件。

iOS 资产复用要求来源为正式 Release，且包含一个 IPA、`ios-release.json` 与 `SHA256SUMS`。
流程检查 IPA 校验和、ZIP 完整性、bundle ID、显示版本、构建号与文件大小。
`ios-provenance.json` 记录原 Release、源码 commit、下载地址与 IPA 校验和；Release 说明分别列出两份源码。
目标 Release 的 iOS 下载地址使用目标标签，IPA 内容与构建号保持来源版本。

## iOS 独立 Release 与 LiveContainer 源

`ios-livecontainer-release.yml` 直接维护，手动选择源分支或 commit（默认 `main`），通过上游 Gradle 任务构建 Release IPA，
发布 `Animeko <版本号>`，资产名为 `Animeko-<版本号>.ipa`，应用名称为 `Animeko`、bundle ID 为 `org.animeko.animeko`。
显示版本移除开发后缀，构建号单调递增。Release 同时包含 `ios-release.json` 元数据与 SHA256 校验。

LiveContainer 订阅地址固定为 `https://github.com/EstusFlask/animeko/releases/download/livecontainer-source/source.json`。
`livecontainer-source.yml` 在正式 Release 发布、编辑或删除时更新此资产，也支持手动运行。
`livecontainer-source` 自身是独立的预发布源资产，不参与应用版本列表，不标记为最新应用 Release。

手动发布时，先把 IPA 上传到草稿 Release，再点击发布；脚本可直接读取 IPA 的 Info.plist，无需自行编写源文件。
源只收录正式发布且包含一个 Animeko IPA 的 Release，并保留历史版本。通过构建工作流发布时会直接调用相同脚本，
因为 GITHUB_TOKEN 发出的 Release 事件不会触发其它工作流。将每次构建的旧源地址替换为上述固定地址后，后续无需重复添加源。
