# 零基础上手：在 Windows 电脑运行宝石优化工具

本教程适合从未使用过 Python 或命令行的玩家。按顺序操作即可；代码框中的命令每次复制**一整行**，粘贴到 PowerShell 后按回车。第一次安装需要联网，之后在本机运行。工具会在浏览器里打开，但地址是你自己电脑上的 `localhost`，不需要把游戏账号交给它。

你需要一台 **Windows 10/11 64 位电脑**、可联网的浏览器，以及几分钟完成安装。下文统一使用 Python 3.12 的 64 位版本。

## 第 1 步：把项目下载到电脑

1. 打开[本项目的 GitHub 仓库页面](https://github.com/chenyuliu19/re4-gem-optimizer)。
2. 点击页面上的绿色 **Code** 按钮，再点 **Download ZIP**。也可以直接点[下载项目 ZIP](https://github.com/chenyuliu19/re4-gem-optimizer/archive/refs/heads/main.zip)。
3. 在“下载”文件夹找到 ZIP，右键选择 **全部解压缩**。不要直接在 ZIP 压缩包里运行程序。
4. 打开解压后的文件夹，找到同时包含 `app.py` 和 `requirements.txt` 的那一层。后面说的“项目文件夹”就是这一层。

已经会用 Git 的读者也可以用下面的命令下载，然后打开新生成的 `re4-gem-optimizer` 文件夹继续；**第一次使用建议走 ZIP 路线**，不需要额外安装 Git。

```powershell
git clone https://github.com/chenyuliu19/re4-gem-optimizer.git
```

只从本项目的 GitHub 页面获取项目文件；Python 从下面给出的官方网站下载。安装时不必关闭杀毒软件或修改系统安全设置。

## 第 2 步：安装 Python

1. 打开 [Python 3.12.10 官方下载页](https://www.python.org/downloads/release/python-31210/)，找到 **Files** 区域，下载 **Windows installer (64-bit)**。不要选 32-bit、ARM64 或 embeddable package。
2. 双击下载的安装程序。若首页出现 **Add python.exe to PATH** 或 **Add Python to PATH**，先勾选，再点 **Install Now**。
3. 安装完成后，关闭安装程序。如果 PowerShell 此时已经打开，请先关闭，稍后重新打开。

电脑上已经装有 Python 3.12 的读者可以先跳到下一步。打开 PowerShell 后，用下面的命令检查；看到 `Python 3.12.x` 就可以继续：

```powershell
py -3.12 --version
```

如果提示找不到 `py`，但安装时已勾选 PATH，可以试 `python --version`；只要显示的是 Python 3.12，就在第 4 步把第一条命令中的 `py -3.12` 改成 `python`。

## 第 3 步：在正确的文件夹打开 PowerShell

1. 用文件资源管理器打开第 1 步找到的项目文件夹，确认眼前能看到 `app.py` 和 `requirements.txt`。解压后的文件夹可能套了两层同名目录，以看到这两个文件的那一层为准。
2. 点击文件资源管理器顶部的**地址栏**，输入 `powershell`，按回车。会出现一个蓝色或黑色窗口，且已经进入当前文件夹。
3. 如果你是从“开始”菜单打开 PowerShell，也可以先复制文件资源管理器地址栏中的**完整文件夹路径**，再用 `cd` 进入。下面只展示格式，请把引号里的示例路径换成你复制的真实路径：

```powershell
cd "C:\Users\你的用户名\Downloads\re4-gem-optimizer-main"
```

4. 在 PowerShell 窗口运行：

```powershell
Get-ChildItem app.py, requirements.txt
```

看到这两个文件名说明位置正确。如果提示“找不到路径”，回到文件资源管理器，进入真正包含这两个文件的文件夹，再重复本步。

## 第 4 步：创建专用的 Python 环境

在**刚才打开的 PowerShell 窗口**运行：

```powershell
py -3.12 -m venv .venv
```

成功后，项目文件夹里会多一个 `.venv` 文件夹。这是本项目自己的 Python 环境，不会把依赖混进其他项目。用下面的命令确认：

```powershell
.\.venv\Scripts\python.exe --version
```

应显示 `Python 3.12.x`。后续命令都直接使用 `.venv` 里的 Python，**无需运行 `Activate.ps1`，也无需更改 PowerShell 执行策略**。

## 第 5 步：安装依赖

仍在同一个 PowerShell 窗口运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

安装 Streamlit、OR-Tools 等依赖可能要几分钟。请等命令执行完、再次出现 `PS ...>` 提示符；不要在下载到一半时关闭窗口。末尾若出现 `Successfully installed ...`，即可继续。安装过程中看到普通的版本升级提示，不影响使用。

## 第 6 步：启动工具

运行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

第一次启动如果询问是否填写 Email，可直接按回车跳过。浏览器通常会自动打开；如果没有，就在浏览器地址栏输入 [http://localhost:8501](http://localhost:8501)。若 PowerShell 显示了另一个 `Local URL`，以窗口里显示的地址为准。**运行期间请保持 PowerShell 窗口开着**。

## 第 7 步：跟着做一次示例

1. 左侧“优化目标”保持默认的**全部变现总收入最大化**。
2. 在“宝物库存”填：**酒壶 1 件、蝴蝶灯 1 件**，其余宝物为 0。
3. 在“宝石库存”填：**红宝石 2 颗、黄钻石 3 颗**，其余宝石为 0；所有“保留”数量为 0。
4. 点击 **🚀 计算全局最优方案**。

预期总收入为 **49,800 ptas**：酒壶镶 2 颗红宝石，售价 12,000；蝴蝶灯镶 3 颗黄钻石，售价 37,800。展开结果卡片可查看每件宝物的槽位、倍率和剩余宝石。换成自己的库存后，重新点击计算。

“库存”填你手头的总数；“保留”填你想留给以后、不让本次计算使用或出售的数量，不能大于库存。已经装在宝物上、且你愿意拆下来重新分配的宝石，也应算进库存，但每颗只算一次。

## 下次使用、停止与卸载

- **下次使用：**打开项目文件夹，在地址栏输入 `powershell`，只执行第 6 步的启动命令。依赖已经安装，不必重复第 4、5 步。
- **停止：**回到运行程序的 PowerShell 窗口，按 `Ctrl+C`，然后关闭窗口。只关浏览器标签页，后台程序可能仍在运行。
- **删除工具：**先停止程序，再通过文件资源管理器删除整个项目文件夹即可。若只想重装项目依赖，删除其中的 `.venv` 文件夹，然后重新做第 4、5 步。Python 本身可在 Windows“设置 → 应用 → 已安装的应用”中单独卸载；除非不再使用任何 Python 程序，否则无需卸载。

## 常见问题

**`py` 不是命令或找不到 Python 3.12。** 关闭旧 PowerShell、重新打开，运行 `py -3.12 --version`。如果仍不行，重新运行官方安装程序并确认安装 Python 3.12；如 `python --version` 显示 Python 3.12，可在第 4 步使用 `python -m venv .venv`。如果 `python` 打开 Microsoft Store，请使用 `py -3.12`，或检查 Python 是否真正安装完成。

**出现 `Activate.ps1 ... 禁止运行脚本`。** 本教程不需要激活环境；直接复制第 5、6 步以 `.\.venv\Scripts\python.exe` 开头的命令即可，不需要修改执行策略。

**提示找不到 `requirements.txt` 或 `app.py`。** 当前 PowerShell 没有处在项目文件夹。按第 3 步重新打开，确认 `Get-ChildItem app.py, requirements.txt` 能列出两个文件。

**`No module named streamlit` 或 `No module named ortools`。** 依赖没有装进当前项目环境。回到项目文件夹，重新执行第 5 步；确保安装和启动命令都以同一个 `.\.venv\Scripts\python.exe` 开头。

**安装依赖时报网络连接或超时错误。** 确认浏览器能正常上网，然后重新执行第 5 步。不要从陌生网站下载所谓“缺失的 DLL”或关闭安全软件。

**浏览器打不开 `localhost:8501`。** 先确认启动命令所在的 PowerShell 窗口还开着，且没有红色报错；查看其 `Local URL`，复制实际地址到浏览器。如果 8501 端口被占用，Streamlit 可能自动改用另一个端口。

**页面输入之后结果没有变化。** 修改库存后，要再次点击“计算全局最优方案”；看到“需要重新计算”提示时，旧结果尚未更新。

仍有问题时，请保存 PowerShell 窗口里**最后几行报错文字**、你执行的命令及 Python 版本，以便定位。不要公开包含个人路径以外敏感信息的完整日志。
