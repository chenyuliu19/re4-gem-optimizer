# 《生化危机4 重制版》宝物与宝石镶嵌优化工具

输入当前拥有的宝物与宝石数量，程序按真实游戏规则，用 **Google OR-Tools CP-SAT** 计算整份库存的 **全局最优镶嵌方案**，并明确给出：每件宝物该镶哪些宝石、售价多少、还剩哪些宝石。

**第一次使用请看 [Windows 零基础教程](BEGINNER_GUIDE.md)**：它分别讲解窗口版的下载、解压和双击运行，以及网页版从安装 Python 到打开浏览器的全部步骤。

- **想直接双击使用：**到 [GitHub Releases](https://github.com/chenyuliu19/re4-gem-optimizer/releases/latest) 的 **Assets** 下载 `RE4GemOptimizer-public.zip`，解压后双击其中的 `RE4GemOptimizer.exe`。发布包不附游戏图片，缺图时显示占位内容。
- **想使用网页版：**从仓库绿色 **Code → Download ZIP** 下载源码，按[零基础教程的网页版步骤](BEGINNER_GUIDE.md#二网页版在浏览器里运行)安装 Python 并运行。源码 ZIP **不包含 exe**。

两版共用优化规则，可同时安装，但库存不会自动同步。下面的内容主要用于了解项目结构与规则。

- 网页版：Python + Streamlit（中文网页，浏览器操作）
- 桌面版：Python + Tkinter（原生中文窗口，双击 exe 即可，无需 Python/浏览器）
- 求解：CP-SAT 整数规划，证明全局最优
- 规则、组合枚举、求解、界面分层独立，便于日后补充宝物数据或更换界面

---

## 目录结构

```
re4_gems/
  __init__.py          包信息
  gem_data.py          宝石数据（英文 ID + 中文名 + 颜色/形状/价格）
  treasure_data.py     宝物数据（基础价 + 圆形/矩形槽数）
  pricing.py           倍率与售价规则（整数倍率 10~20，金额放大 10 倍）
  combinations.py      组合枚举（六维宝石向量 + 缓存）
  solver.py            CP-SAT 全局优化求解器
  inventory.py         输入校验 + JSON 导入/导出 + 示例
  brute_force.py       暴力枚举交叉验证
app.py                 Streamlit 界面入口
web_images.py          网页版图片路径查找（纯路径查找，不依赖 Tkinter/Pillow）
desktop_app.py         桌面版入口（Tkinter，不依赖 Streamlit/app.py）
desktop/
  images.py            桌面版图片加载（按英文 ID 从 assets/ 读取，缺图显示占位）
RE4GemOptimizer.spec   PyInstaller 打包配置（--onedir --windowed）
build_desktop.py       Windows 桌面版构建脚本
requirements-desktop.txt  桌面版构建依赖
DESKTOP_README.txt     面向普通用户的「解压后双击 exe」说明
tests/
  test_optimizer.py    规则单元测试 + 8 大验收案例 + 交叉验证
  test_core_validation.py  输入校验与独立核验回归测试
  test_ui.py           网页版交互回归测试
  test_desktop.py      桌面版关键逻辑测试
requirements.txt       网页版依赖清单
README.md              项目说明与规则
BEGINNER_GUIDE.md      Windows 零基础安装运行教程（窗口版 + 网页版）
```

---

## 环境安装（Windows）

推荐 Python 3.12 64 位。首次安装请按 [零基础教程](BEGINNER_GUIDE.md) 操作；以下是已经熟悉 PowerShell 的用户所需的全部命令（在项目目录运行）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

这些命令不要求激活虚拟环境，也不需要更改 PowerShell 执行策略。

---

## 启动网页

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

启动后浏览器会自动打开（默认 http://localhost:8501），在页面中：

1. 左侧选择优化目标与求解时限。
2. 输入六种宝石的**库存**与**保留**数量、各宝物的**数量**（每行名称旁会显示对应缩略图）。
3. 点击「🚀 计算全局最优方案」。
4. 查看逐件镶嵌方案、倍率、售价、额外增值与宝石对账。

也可通过「加载示例」「导入/导出 JSON」「下载中文操作清单」完成批量操作。

### 网页版图片

网页版会在宝石 6 行与宝物 10 行的名称旁显示约 48 像素的缩略图，按英文 ID 查找文件名。公开源码不附图片；如果你有可使用的 PNG，请按[零基础教程的图片步骤](BEGINNER_GUIDE.md#三添加宝石和宝物图片可选)自行放置：

```
assets/gems/<gem_id>.png        如 assets/gems/ruby.png
assets/treasures/<treasure_id>.png  如 assets/treasures/flagon.png
```

查找顺序（优先用第一个存在的文件）：项目根目录 `assets/` → 本地构建目录 `dist/RE4GemOptimizer/assets/` → 本机备份 `assets_backup/`。从 GitHub 下载源码的用户通常只有第一个位置可用。缺图或图片损坏时，该行显示一个浅色占位块，页面与计算不受影响。图片查找由 `web_images.py` 完成，不依赖 Tkinter 或 Pillow。

---

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试覆盖：

| 编号 | 内容 |
| --- | --- |
| 规则单测 | 全部倍率条件、Ruby/Red Beryl 同色合并 |
| 案例1 | 皇冠五色 → 100000 / 2.0 |
| 案例2 | 皇冠高价值双色 → 108000 / 1.8 |
| 案例3 | 皇冠五颗红色 → 98800 / 1.9 |
| 案例4 | 颜色规则 [2,1,1]→1.3、[2,1,1,1]→1.6 |
| 案例5 | 全局分配 Flagon+灯 → 49800 |
| 案例6 | 边界（空/无宝石/仅宝石/保留/多件不同方案） |
| 案例7 | 随机小库存暴力枚举交叉验证 |
| 案例8 | 同款多件不同方案 |

---

## 核心规则说明

### 售价与倍率

```
最终售价 = (宝物基础价 + 已镶嵌宝石价之和) × 组合倍率
```

- 倍率按**实际镶嵌宝石的颜色**统计，取满足条件中的**最高倍率**，不叠加。
- 空槽不计入颜色；不要求填满全部槽位。
- 圆形宝石只能进圆形槽，矩形宝石只能进矩形槽。
- Ruby 与 Red Beryl 虽为不同宝石，但统计颜色时**同属红色**（六种宝石、五种颜色）。

倍率表（内部用整数 10~20 表示，金额放大 10 倍，全程无浮点金额）：

| 条件 | 倍率 |
| --- | --- |
| 无其他适用组合 | 1.0 |
| 至少 2 种颜色 | 1.1 |
| 某种颜色至少 2 颗 | 1.2 |
| 至少 3 种颜色 | 1.3 |
| 某种颜色至少 3 颗 | 1.4 |
| 两种不同颜色分别至少 2 颗 | 1.5 |
| 至少 4 种颜色 | 1.6 |
| 某种颜色至少 4 颗 | 1.7 |
| 两种不同颜色分别至少 3 颗和 2 颗 | 1.8 |
| 某种颜色至少 5 颗 | 1.9 |
| 至少 5 种颜色 | 2.0 |

### 优化目标

默认目标（**全部变现总收入最大化**）：

```
总收入 = Σ 宝物最终售价 + Σ 未镶嵌、未保留宝石的基础价单卖
```

备选目标（**仅最大化宝物售出价**）：剩余宝石全部保留，不计入收入。界面会明确提示两种目标结果不可混用。

> 注意：不能把“倍率最高”“单件售价最高”“先填满最贵的宝物”当作全局最优——宝石需在全部宝物之间**共同分配**。

---

## 数据说明

宝石（六种、五种颜色）：

| 英文 ID | 中文名 | 颜色 | 形状 | 单颗价(ptas) |
| --- | --- | --- | --- | --- |
| ruby | 红宝石 | 红 | 圆形 | 3000 |
| sapphire | 蓝宝石 | 蓝 | 圆形 | 4000 |
| yellow_diamond | 黄钻石 | 黄 | 圆形 | 7000 |
| emerald | 祖母绿 | 绿 | 矩形 | 5000 |
| alexandrite | 亚历山大石 | 紫 | 矩形 | 6000 |
| red_beryl | 红色线柱石 | 红 | 矩形 | 9000 |

宝物（基础价 / 圆形槽 / 矩形槽）：

| 英文 ID | 中文名 | 基础价 | 圆 | 矩 |
| --- | --- | --- | --- | --- |
| flagon | 酒壶 | 4000 | 2 | 0 |
| splendid_bangle | 华丽手镯 | 4000 | 0 | 2 |
| elegant_bangle | 典雅手镯 | 5000 | 2 | 0 |
| elegant_mask | 典雅面具 | 5000 | 3 | 0 |
| butterfly_lamp | 蝴蝶灯 | 6000 | 3 | 0 |
| chalice_of_atonement | 赎罪圣杯 | 7000 | 0 | 3 |
| extravagant_clock | 奢华座钟 | 9000 | 1 | 1 |
| golden_lynx | 黄金猞猁 | 15000 | 2 | 1 |
| ornate_necklace | 华丽项链 | 11000 | 2 | 2 |
| elegant_crown | 典雅皇冠 | 19000 | 2 | 3 |

如需补充宝物，只需在 `treasure_data.py` 的 `TREASURES` 列表中加入一条（英文 ID、中文名、基础价、圆/矩形槽数），算法与界面无需改动。

---

## Windows 桌面版

桌面版用 Tkinter 做原生中文窗口，**复用同一套 `re4_gems/` 价格规则与全局优化算法**，入口 `desktop_app.py` 不依赖 Streamlit 或 `app.py`。最终用户下载发布包、解压后双击 `RE4GemOptimizer.exe` 即可，无需安装 Python、无需命令行、无需浏览器。

### 面向最终用户

1. 到 [GitHub Releases](https://github.com/chenyuliu19/re4-gem-optimizer/releases/latest) 的 **Assets** 下载 `RE4GemOptimizer-public.zip`，右键 → **全部解压缩**，不要在压缩包预览窗口里双击。
2. 打开 `RE4GemOptimizer` 文件夹，保持 `RE4GemOptimizer.exe` 和 `_internal/` 在同一文件夹，双击 exe。
3. 在窗口左栏填宝石数量、选“出售剩余宝石”或“保留剩余宝石”；在右栏填宝物数量，点「生成镶嵌方案」。只有右栏宝物列表和下方结果区需要滚动。

详细步骤见[Windows 零基础教程](BEGINNER_GUIDE.md#一窗口版双击-exe-运行)、随包附带的 `使用说明.txt` 或项目根目录的 `DESKTOP_README.txt`。绿色 **Code → Download ZIP** 得到的是源码，没有 exe。

**关于图片**：公开发布包不附游戏图片，程序默认显示文字占位图。想显示真实图片，把自己可使用的 PNG 按英文名放进 exe 同级的 `assets/gems/` 和 `assets/treasures/` 目录（目录里各有一份 `放图片说明.txt`），重新打开程序即可，无需重新打包。缺图或图片损坏时自动回退占位图，程序照常可用。

> 网页版与桌面版使用相同的 PNG 文件名：桌面版读 exe 同级 `assets/`，网页版优先读项目根目录 `assets/`。如果两个版本分别下载到不同文件夹，请将自己的图片各复制一份；缺图不会影响计算。

### 面向开发者：构建

用 **Python 3.12 64 位**（Windows 10/11）：

```powershell
# 1. 安装构建依赖
py -3.12 -m pip install -r requirements-desktop.txt

# 2. 运行构建脚本（产出 dist/RE4GemOptimizer/ 与 dist/RE4GemOptimizer.zip）
py -3.12 build_desktop.py

# 若在受保护环境删除 dist/build 触发确认，可先手动删除再：
py -3.12 build_desktop.py --no-clean
```

`RE4GemOptimizer.spec` 使用 `--onedir --windowed`（无控制台窗口），产出的是**整个文件夹**而非单个 exe，交付时连同 `_internal/` 依赖目录一起分发。

### 面向开发者：测试

桌面版测试与算法测试都在 Python 3.12 环境运行（网页版 `test_ui.py` 依赖 Streamlit，需在装有 Streamlit 的环境跑）：

```powershell
py -3.12 -m pytest tests/test_optimizer.py tests/test_core_validation.py tests/test_desktop.py -q
```

桌面版打包后自检（验证 exe 内 ortools 动态库与求解链路）：

```powershell
.\dist\RE4GemOptimizer\RE4GemOptimizer.exe --smoke-test
# 成功时在同目录生成 smoke_test_result.txt，内容含 SMOKE_OK objective=49800
```

### 实际验证通过的依赖版本

| 组件 | 版本 |
| --- | --- |
| Python | 3.12.6（64 位） |
| PyInstaller | 6.22.3 |
| pyinstaller-hooks-contrib | 2026.8 |
| ortools | 9.15.6755 |
| Pillow | 11.1.0 |
| numpy | （随 ortools 依赖） |
| pandas | （随 ortools 依赖） |

> 注意：`ortools` 的 `cp_model` 模块硬依赖 `numpy` 与 `pandas`，打包时不要排除这两者，否则 exe 启动即报 `No module named 'numpy'/'pandas'`。

### 已知限制

- 交付包较大（约 68 MB 压缩包），因为完整打包了 OR-Tools 及其 numpy/pandas 运行时。
- 未在**完全没有 Python 的干净 Windows 虚拟机**上做独立安装验证；本次验证是在开发机（本身装有 Python 3.12）上启动打包后的 exe 完成，已确认：无控制台窗口、GUI 窗口正常显示、无图片（占位图）与有图片两种情况均不崩溃、示例「酒壶 1 + 蝴蝶灯 1 + 红宝石 2 + 黄钻石 3」正确得到 49,800 ptas。

---

## 免责声明

本工具基于公开整理的《生化危机4 重制版》镶嵌规则实现，仅供学习与游戏辅助；实际游戏行为请以游戏内为准。
