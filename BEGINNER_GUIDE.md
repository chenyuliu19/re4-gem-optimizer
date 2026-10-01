# Windows 零基础教程：窗口版和网页版

这个工具有两种用法，可以任选一种，也可以两种都留在电脑上：

- **窗口版**：下载发布包、解压、双击 `RE4GemOptimizer.exe`。不需要安装 Python，也不需要浏览器。第一次使用建议从[窗口版步骤](#一窗口版双击-exe-运行)开始。
- **网页版**：下载项目源码、安装 Python，运行一条命令后在浏览器里使用。它还提供“保留指定数量的宝石”、库存 JSON 导入导出等功能。步骤见[网页版步骤](#二网页版在浏览器里运行)。网页在自己的电脑上运行，通常打开的是 `http://localhost:8501`。

两版使用同一套宝物、宝石和计算规则，但**库存不会自动同步**。两版都可以不放图片，缺图时会显示占位内容，不影响计算。下面所有操作适用于 Windows 10/11 64 位。

## 一、窗口版：双击 exe 运行

### 1. 下载正确的压缩包

1. 打开[本项目的 GitHub 发布页面](https://github.com/chenyuliu19/re4-gem-optimizer/releases/latest)，在 **Assets**（附件）里下载 `RE4GemOptimizer-public.zip`。
2. 不要把 GitHub 的 **Source code (zip)** 当成 exe 安装包。源码 ZIP 用于下面的网页版。
3. 在“下载”文件夹找到 `RE4GemOptimizer-public.zip`，右键选择 **全部解压缩**。**不要在压缩包预览窗口里双击 exe。**
4. 打开解压出的 `RE4GemOptimizer` 文件夹，确认其中有 `RE4GemOptimizer.exe`、`_internal` 文件夹和 `assets` 文件夹。请让它们保持在一起，不要只把 exe 单独移到桌面。

### 2. 打开并计算一次

1. 双击 `RE4GemOptimizer.exe`，等中文窗口打开。此版不用安装 Python，也不用打开 PowerShell。
2. 左边“宝石库存”设置你有多少颗宝石；每行可点 **− / +**，也可在中间直接输入非负整数。
3. 右边“宝物库存”设置你有多少件宝物。右栏宝物列表可用滚轮上下浏览；左栏的优化目标和生成按钮会留在原处。
4. 左边“优化目标”选择：**出售剩余宝石**会把未镶嵌的宝石按单卖价算进总收入；**保留剩余宝石**只优化宝物售价，余下宝石留着。
5. 点击左边的 **生成镶嵌方案**。下方“计算结果”会列出各件宝物的镶嵌方法、售价与剩余宝石；结果内容可独立滚动。修改数量或目标后，再点一次按钮计算新方案。

第一次可以试：酒壶 **1** 件、蝴蝶灯 **1** 件、红宝石 **2** 颗、黄钻石 **3** 颗，其余数量 **0**，目标保持“出售剩余宝石”。预期总收入是 **49,800 ptas**：酒壶镶 2 颗红宝石，蝴蝶灯镶 3 颗黄钻石。

已经镶在宝物上、并且愿意拆下来重新分配的宝石，也应计入库存；同一颗宝石只计一次。下次使用时，打开解压后的文件夹，再双击 exe 即可。关闭窗口就是退出程序。

## 二、网页版：在浏览器里运行

网页版**需要先安装 Python 3.12**。下面代码框中的命令每次复制一整行到 PowerShell，按回车执行；不需要先学会编程。

### 1. 下载项目源码

1. 打开[本项目的 GitHub 仓库页面](https://github.com/chenyuliu19/re4-gem-optimizer)，点绿色 **Code** → **Download ZIP**；也可直接[下载源码 ZIP](https://github.com/chenyuliu19/re4-gem-optimizer/archive/refs/heads/main.zip)。
2. 右键 ZIP → **全部解压缩**。打开解压后的文件夹，找到能同时看到 `app.py`、`requirements.txt` 的那一层；它就是后面所说的“项目文件夹”。
3. **这个源码 ZIP 不包含窗口版 exe。**如果你只想双击运行，请返回上面的[窗口版下载步骤](#1-下载正确的压缩包)。

### 2. 安装 Python

1. 打开 [Python 3.12.10 官方下载页](https://www.python.org/downloads/release/python-31210/)，在 **Files** 区域下载 **Windows installer (64-bit)**。
2. 双击安装程序。如果首页有 **Add python.exe to PATH** 或 **Add Python to PATH**，先勾选，再点 **Install Now**。
3. 安装后打开 PowerShell，输入：

```powershell
py -3.12 --version
```

看到 `Python 3.12.x` 就可以继续。如果提示找不到 `py`，先关闭 PowerShell、重新打开再试；若 `python --version` 显示 Python 3.12，也可以在下一步把 `py -3.12` 改成 `python`。

### 3. 在项目文件夹打开 PowerShell

1. 用文件资源管理器打开刚找到的项目文件夹，确认能看到 `app.py` 和 `requirements.txt`。
2. 点击文件资源管理器顶部地址栏，输入 `powershell`，按回车。这会打开一个已经处在当前文件夹的命令窗口。
3. 输入下列命令检查位置：

```powershell
Get-ChildItem app.py, requirements.txt
```

能看到两个文件名即可。如果提示找不到文件，返回文件资源管理器，进入真正包含这两个文件的文件夹再试。

### 4. 创建环境并安装依赖

在刚才的 PowerShell 里，依次执行：

```powershell
py -3.12 -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

第二条命令需要联网并可能花几分钟；请等到 `PS ...>` 提示符重新出现。这里直接调用 `.venv` 中的 Python，**不用运行 `Activate.ps1`，也不用改变 PowerShell 执行策略**。

### 5. 启动并使用网页版

仍在项目文件夹的 PowerShell 里运行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

第一次启动如果询问 Email，可以直接按回车跳过。浏览器通常会自动打开；否则把 PowerShell 中显示的 **Local URL** 复制到浏览器地址栏，通常是 [http://localhost:8501](http://localhost:8501)。**使用期间让 PowerShell 保持打开。**

1. 页面左侧选择“优化目标”和求解时限；初次使用保持默认即可。
2. 在“宝石库存”填拥有的数量；“保留”填本次不参与镶嵌、不出售的数量，不能大于对应库存。
3. 在“宝物库存”填宝物数量；可以沿用上面的 49,800 ptas 示例，所有“保留”填 0。
4. 点击 **🚀 计算全局最优方案**，在下方看逐件镶嵌方法和总收入。更改库存或目标后，需要再点一次计算。

网页版另有 **加载示例**、**清空**、库存 **JSON 导入/导出**，以及下载中文操作清单；这些功能不影响普通计算。下次使用时，不必重复安装，只需在项目文件夹打开 PowerShell，重新执行本步骤的启动命令。要退出，回到 PowerShell 按 `Ctrl+C`；只关浏览器标签页可能不会停止后台程序。

## 三、添加宝石和宝物图片（可选）

公开下载包**不附带游戏图片**。没有图片时，两版都会显示占位内容，输入和计算照常工作。如果你自己有可使用的 PNG 图片，可按下面的方法放置；放好后重新打开窗口版或刷新网页版。

- **窗口版**：放在解压后的 `RE4GemOptimizer\assets\gems\` 和 `RE4GemOptimizer\assets\treasures\`，与 exe 位于同一个 `RE4GemOptimizer` 文件夹下。发布包里有这两个目录；缺少时可自行新建。
- **网页版**：在能看到 `app.py` 的项目文件夹中新建 `assets\gems\` 和 `assets\treasures\`，把图片放进去。网页版也会依次尝试项目内的 `dist\RE4GemOptimizer\assets\` 和 `assets_backup\`，但**新手直接使用项目根目录的 `assets` 最清楚**。
- **两版都用**：若窗口版和网页版是分别下载、放在不同文件夹，需将自己的图片各复制一份到对应位置；两版不会自动共享另一个下载文件夹中的图片。

图片必须是 PNG，文件名与下列英文名**完全一致**；Windows 可能隐藏扩展名，请确认没有变成 `.png.png`：

宝石图片，放 `gems` 文件夹：

```text
ruby.png             红宝石
sapphire.png         蓝宝石
yellow_diamond.png   黄钻石
emerald.png          祖母绿
alexandrite.png      亚历山大石
red_beryl.png        红色线柱石
```

宝物图片，放 `treasures` 文件夹：

```text
flagon.png                 酒壶
splendid_bangle.png       华丽手镯
elegant_bangle.png        典雅手镯
elegant_mask.png          典雅面具
butterfly_lamp.png        蝴蝶灯
chalice_of_atonement.png  赎罪圣杯
extravagant_clock.png     奢华座钟
golden_lynx.png           黄金猞猁
ornate_necklace.png       华丽项链
elegant_crown.png         典雅皇冠
```

## 四、常见问题

**GitHub 下载后找不到 exe。** 你下载的可能是绿色 **Code** 按钮提供的源码 ZIP。窗口版请到 [Releases 的 Assets](https://github.com/chenyuliu19/re4-gem-optimizer/releases/latest) 下载 `RE4GemOptimizer-public.zip`，并解压。

**exe 双击后无法正常打开。** 确认已完整解压，exe 旁边仍有 `_internal` 文件夹；不要把 exe 单独复制出来运行。只从本项目的 GitHub 发布页下载，按照 Windows 显示的提示核对文件来源，不要关闭安全软件。

**图片不显示。** 先确认是 `.png`、文件名准确、放在本版本对应的 `gems` 或 `treasures` 文件夹里；然后重新打开窗口版或刷新网页。缺图不会影响计算。

**窗口版提示数量不正确。** 数量只能是非负整数（0、1、2……），不能输入负数、小数或文字。

**网页版提示 `py` 不是命令或找不到 Python 3.12。** 关闭 PowerShell 再打开，运行 `py -3.12 --version`；仍不行就检查 Python 3.12 是否已安装。若 `python --version` 显示 Python 3.12，可用 `python -m venv .venv` 代替创建环境的命令。

**网页版提示 `Activate.ps1 ... 禁止运行脚本`。** 本教程不需要激活环境。使用上面以 `.\.venv\Scripts\python.exe` 开头的命令即可，无需修改系统执行策略。

**网页版提示找不到 `requirements.txt` / `app.py`。** PowerShell 当前不在项目文件夹；重新按“在项目文件夹打开 PowerShell”的步骤操作。

**网页版提示 `No module named streamlit` 或 `No module named ortools`。** 在项目文件夹里重新执行安装依赖的命令，确保安装和启动都使用同一个 `.\.venv\Scripts\python.exe`。

**网页打不开或结果没更新。** 确认 PowerShell 仍在运行，复制其中实际显示的 **Local URL**；改动数量后再点一次“计算全局最优方案”。

**网络下载或安装超时。** 确认浏览器能联网，再重试下载或 `pip install` 命令；不需要下载所谓“缺失的 DLL”或关闭安全软件。

仍有问题时，可记录你执行的命令、Python 版本和 PowerShell 中最后几行报错，便于定位。
