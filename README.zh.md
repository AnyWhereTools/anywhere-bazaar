# AnyWhere 扩展包集市

[English](README.md) · [AnyWhere](https://github.com/appdev/AnyWhere) · [生成的目录](catalog.json)

开发者在自己的公开 GitHub 仓库维护源码和 `manifest.json`，中央仓库每包保存一个 JSON 登记文件，自动生成静态目录。Finder 菜单、带面板的工具和工作流继续复用现有扩展包格式。

## 提交扩展包

1. 发布公开 GitHub 仓库，根目录包含 `manifest.json`、引用的资源、许可证和使用说明，并在 AnyWhere 中验证导入和各入口。参考[扩展包开发文档](https://github.com/appdev/AnyWhere/blob/main/docs/pack-spec.zh.md)和[完整示例](https://github.com/appdev/anywhere-tool-chain-demo)。
2. Fork 本仓库，新增 `registry/<id>.json`：

   ```json
   {
     "id": "appdev.tool-chain-demo",
     "repository": "https://github.com/appdev/anywhere-tool-chain-demo"
   }
   ```

3. 提交 PR，说明功能和权限用途。CI 检查登记文件并读取插件元数据；维护者核对仓库归属、许可证和代码后合并。CI 通过不等于审核通过。
4. 合并后工作流自动更新 `catalog.json`，不要手动修改生成文件。

ID 使用小写字母、数字及作为分隔符的点或短横线，最多 100 字符，必须全局唯一并与文件名一致。建议 `owner.package-name`。这是目录身份，不是 manifest 新字段，也不替换宿主本地 `packKey`。ID 应保持稳定；仓库改名或转移需更新登记并重新审核，不允许将旧 ID 改作无关插件。

地址仅接受 `https://github.com/owner/repo`，不带 `.git`、参数或分支路径；同一个仓库只登记一次。登记文件仅含 `id`、`repository`。标准 JSON 不支持注释：收录说明写在 PR，使用说明写在插件 README。名称、描述、作者、图标从 manifest 读取，类型从入口推导，避免重复维护。

## 更新与下架

日常更新直接提交插件仓库默认分支及其 manifest，不需要重复提交收录 PR。定时任务每小时运行一次，先取得默认分支 HEAD 的完整 Git 提交号，再按该提交读取 manifest 和文件列表、生成目录。GitHub 定时任务可能延迟，也可通过 **Actions → Catalog → Run workflow** 手动刷新。首版按 Git 提交更新，不依赖 Release 或语义版本号。

任意仓库不可访问、字段不合法或资源缺失时，整次刷新失败，保留上一份可用目录。修复后重跑；确需下架时，通过 PR 删除对应登记文件。下架只影响目录，不会删除用户已安装的插件。

首次登记由维护者审核；后续上游提交自动进入目录，不逐次人工审核。收录不代表安全背书，宿主仍需保留源码审阅和启用确认。

## 目录接口

客户端入口：[catalog.json](https://raw.githubusercontent.com/appdev/anywhere-bazaar/main/catalog.json)。结构示例：

```json
{
  "schemaVersion": 1,
  "packages": [
    {
      "id": "owner.example",
      "repository": "https://github.com/owner/example",
      "revision": "0123456789012345678901234567890123456789",
      "name": "Example",
      "description": null,
      "author": null,
      "icon": "shippingbox",
      "manifestSchemaVersion": 4,
      "types": ["tool", "workflow"]
    }
  ]
}
```

以上是格式示例，实际条目以生成文件为准。`types` 可以组合 `finder`（右键菜单）、`tool`（搜索或 UI 入口）、`workflow`（工作流）。作者和描述可为 null。`revision` 是 40 位 Git 提交号，不是 ZIP 哈希。条目按 ID 排序，输入未变时输出不变。

AnyWhere 的「插件市场」读取本目录，拒绝不支持的目录版本和重复身份/来源，按目录记录的完整 commit 安装，校验实际 checkout 和 manifest 后进入源码审阅，安装默认禁用。更新选择的版本会保留到差异审阅及安装完成。既有 HTTPS GitHub 安装按规范仓库地址匹配，不改变安装标识及用户数据；后续市场更新会保存注册身份。已绑定条目下架或迁移仓库时显示错误，不自动跟随仓库 HEAD。手动 Git/本地导入继续保留，GitHub topic 不再决定应用内上架；目录加载失败可重试。请使用包含 Bazaar 客户端接入的新版 AnyWhere。

## 本地校验与 CI

使用 Python 3.9+，无需额外依赖：

```sh
python3 -m unittest -v
python3 build_catalog.py
```

第二条命令需要连接 GitHub。可选设置只读 `GITHUB_TOKEN` 提高 API 限额；CI 使用 Actions 自动提供的令牌。令牌不会发送给 raw 文件地址。

校验包含严格 JSON、重复字段和仓库、公开且未归档的源仓库、manifest 版本 1–4、目录元数据类型、工具与工作流引用，以及声明脚本/UI 入口对应的普通文件。拒绝符号链接资源、越界路径、过大响应和被截断的文件树。未知 manifest 字段继续兼容。这些静态检查不替代宿主完整原生校验、权限控制、源码审阅或运行测试。

PR 校验使用只读权限，不执行插件文件、不构建插件项目。只有中央仓库经审核进入 `main` 的代码可发布；独立发布任务仅提交 `catalog.json`。生成器不跟随远程重定向、不检出插件代码，失败不会覆盖旧目录。中央仓库只提供元数据，不承担插件沙箱或下载服务器的职责。

本仓库使用 MIT 许可证；各扩展包保留各自许可证。
