RECLONE / RESET INSTRUCTIONS
===========================

为什么需要重新克隆
------------------
我们对 Git 历史执行了清理（移除大量示例/临时数据文件），这会改变仓库历史（rewrite）。为了避免本地与远程历史冲突，所有协作者应当重新克隆或重置他们的本地仓库。

推荐步骤（最安全，推荐）
--------------------------
1. 备份你本地未提交的改动（如果有）：
   - 保存补丁：
     git diff > mywork.patch
   - 或者把改动暂存到临时分支：
     git checkout -b local-work
     git add -A
     git commit -m "WIP: backup before reclone"

2. 删除本地仓库并重新克隆：
   - Windows / PowerShell:
     Remove-Item -Recurse -Force .git
     cd ..
     git clone git@github.com:yin1895/LANGCHAIN-RAG.git

   - 或者更简单地在父目录运行：
     rm -rf LANGCHAIN-RAG && git clone git@github.com:yin1895/LANGCHAIN-RAG.git

3. 如果你之前保存了补丁（mywork.patch），应用补丁：
   git apply mywork.patch

替代：在不重新克隆的情况下硬重置（高级用户）
------------------------------------------------
如果你非常熟悉 git 并且确认要在当前目录操作，你可以：

1. 丢弃未提交的更改（不可逆）：
   git reset --hard
   git clean -fdx

2. 从远程强制拉取（覆盖本地）：
   git fetch origin
   git checkout dev
   git reset --hard origin/dev

注意事项
--------
- 在执行上述任何命令之前，请务必备份你的本地工作（补丁或临时分支）。
- 如果你对历史重写或强制拉取有疑问，请联系仓库维护者以获得帮助。

联系人
------
仓库拥有者: yin1895
Issues 或邮件用于沟通：请在 GitHub 仓库中打开 issue 或通过项目中留的联系方式联系。
