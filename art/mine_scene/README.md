# 三维扫雷 · 矿井场景 / 第一阶段

本目录保留 Blender 美术、踩雷特效、声音和有声视频的可编辑源文件。第一阶段样片已获用户确认；第二阶段已把场景导出至现有 Android GLES2 工程，进度和真实验收证据统一见 `PHASE_2_HANDOFF.md`。下面的渲染数据属于第一阶段样片。

## 已交付

- 完整视频：`D:\浩科软件优化\三维扫雷_Mines3D\三维扫雷_矿井爆炸_第一阶段样片.mp4`，24 秒、1080×1920、24 fps、H.264 / AAC，约 14 MB。
- 可编辑场景：`Mines3D_DeepSector.blend`。
- 贴图：`textures/`；独立音效与混音：`audio/`；六条对齐分轨：`audio/stems/`。
- 特效和场景源定义：`scripts/build_scene.py`、`fragment_trajectories.json`；声音及贴图生成源：`scripts/make_sources.py`。
- 接入尺寸、相机与坐标约定：`scene_contract.json`；后续范围与边界：`PHASE_2_HANDOFF.md`。

MP4 是实际 Blender 渲染后的样片，不是 Android 运行录屏。日常美术修改直接编辑 `.blend`；`build_scene.py` 用于从源定义重新生成场景。

## 打开与重现

- 用 Blender 5.2 打开 `Mines3D_DeepSector.blend`。文件打开在正常游戏机位的安全开格状态。
- 时间线为 1–576 帧，24 fps，共 24 秒；帧 337 对应音轨的 14.000 秒触雷。
- 集合按岩壁、支架、双层棋盘、灯光、选中框、碎块、尘土、相机和声音区分。各对象、材质节点、逐帧碎块轨迹、灯光和尘土动画均可编辑。
- 音频分轨已经放入 Blender 序列编辑器。渲染棋盘时关闭序列合成，成片由 `scripts/compose_movie.py` 叠加界面并混音编码。
- `.blend` 已打包实际使用的纹理、数字字体和六条声音分轨；独立贴图、字体许可、声音、字幕图板和生成脚本仍保留在相邻目录。
- 重生成贴图、音频和界面图板需要 Python 3.12 与 `requirements.txt` 所列依赖；场景脚本用 Blender 自带 Python 运行。视频合成需要 FFmpeg，`compose_movie.py` 可通过 `FFMPEG_BIN` 指定位置。

## 镜头与交互节奏

| 时间 | 内容 |
| --- | --- |
| 0–4.8 秒 | 斜俯视绕看双层矿井与层间灯光 |
| 4.8–6.1 秒 | 隐去上层棋盘及其框架，切到第 01 层 |
| 7 秒 | 选中安全格，描边确认 |
| 8 秒 | 开格，显示真实六邻接规则下的数字 2 |
| 10–10.4 秒 | 选格、插入立体暖色旗帜 |
| 13 秒 | 选中前侧右边的危险格 |
| 14 秒 | 同坐标闪光、碎片与声音同步起爆 |
| 14–20 秒 | 支架碰撞、落地回弹、浮尘扩散消散 |
| 20–24 秒 | 保持破损格与结算状态，矿洞尾音结束 |

## 尺度与后续接入

沿用现有 `BoardScene` 的 1.0 格距、0.91 格宽、1.5 层距；基准机位为方位角 36°、俯角 43°、垂直视场 40°。`scene_contract.json` 保存棋盘、雷位、示范开格位置与镜头；`fragment_trajectories.json` 保存每个碎块位置和碰撞事件。

美术矿板顶面为 0.431，已开格数字面为 0.123，选中框分别位于 0.45 / 0.15；原工程对应格顶为 0.39 / 0.095。接入时应在同一个棋盘几何抽象中同步修改可见网格和拾取边界，避免只换模型导致点选偏差。

Blender 采用 Z 向上；Android 原工程为 Y 向上。世界坐标按 Android `(x,y,z)` = Blender `(x,z,-y)` 转换；本场景制作行号 `j` 对应 Android 行号 `4-j`，所有雷位、开格、旗帜与提示必须一起翻转。爆点制作坐标 `[4,1,0]` 对应 Android 格 `[4,3,0]`，合同文件同时提供两套索引。Cycles 体积材质、路径追踪灯光、Blender 节点不会直接运行于现有 OpenGL ES 2 后端。第二阶段应将岩石与金属表面烘焙为纹理，碎片轨迹转为有限实例，尘土转换为透明图集，并在同一机位验证可读性和帧率。

## 音频与来源

- `audio/`：选格、开格、插旗、换层、起爆冲击、低频闷响、碎石、矿洞尾音等独立 WAV，以及 24 秒混音。
- `audio/stems/`：同起点、同长度的环境、交互、冲击、低频、碎石、回声六条分轨；格式为 48 kHz、24-bit PCM、双声道。
- 音效由 `scripts/make_sources.py` 使用合成振荡器、带通噪声、包络与延迟原创生成，没有使用第三方采样、录音或音乐。
- 岩石和金属贴图同样为本项目程序生成，无外部图库素材。
- 数字使用 Noto Sans Bold，中文界面使用 Noto Sans SC。两者采用 SIL Open Font License 1.1，允许商用；原许可随 `fonts/` 保留。来源：[Noto CJK](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE)、[Noto Fonts](https://github.com/notofonts/noto-fonts/blob/main/LICENSE)。

## 渲染与验证

最终设置为 Cycles / GTX 1070 Ti CUDA / 1080×1920 / 24 fps / 最大 256 采样 / 自适应阈值 0.005 / 高质量 OIDN / 0.35 帧运动模糊，保留 16-bit PNG 无损帧。静止画面按包含快门端点的完整状态散列复用像素，动态部分逐帧真实渲染，不使用补帧。

续渲脚本同时核对 `.blend`、渲染脚本和每个 PNG 的 SHA-256。编辑场景后会重新渲染，不把同名旧帧误当作新结果。`render_cache.json` 随每帧完成更新；`render_complete.json` 只有在全部画面与当前源文件一致时才标记完成。正常续渲直接运行 `scripts/render_movie.py`，无需执行历史迁移脚本。

最终 H.264 采用 x264 veryslow、film、CRF 10，AAC 320 kbps、48 kHz，BT.709、有限范围。以实际连续 120 帧爆炸段比较编码，film 的 VMAF 均值 97.552、1% 低值 96.986；完整结果保留在 `encode-bench.json`。

## 实际验收记录

| 项目 | 实际结果 |
| --- | --- |
| 成片规格与完整性 | 1080×1920，24 fps，576 帧，24.000 秒，AAC 48 kHz 双声道；完整解码通过。 |
| 成片画面 | 抽查 16 个解码帧，检查层叠与切层构图、选中和按钮状态、数字与旗帜、局部闪光及尘土消散后的受损格。 |
| 场景与资源 | 630 个对象；六条音轨已打包；25 格中心处于正常机位可见区域；示范安全格提示为 2。 |
| 碎片 | 检查到 7 次支架碰撞；10 个落在矿板上的碎片以旋转后的实际网格底部检查接触，间隙不超过 5.5 mm。 |
| 原始声音 | 六分轨能重建混音，均为有限数值，无削波；已进行手机频段的单声道数字模拟。 |
| 编码后声音与同步 | 起爆段 AAC 解码与原始 PCM 互相关的时间偏移为 0 ms，相关度 0.99169；最终积分响度 -18.54 LUFS，真峰值 -1.47 dBTP。 |
| 续渲恢复 | 再次运行命中全部 295 个缓存画面，无重渲；最终 MP4 哈希保持不变。 |

证据在 `review/video-verification.json`、`review/encoded-audio-verification.json`、`review/scene-verification.json`、`review/audio-verification.json` 和 `review/cache-verification.json`。

阶段一不能证明手机扬声器听感、安卓运行或帧率。第二阶段已另行在 PKG110 上验证操作、模式和恢复；实际通过与未验证项以 `PHASE_2_HANDOFF.md` 及项目交付说明为准。本样片仍不冒充手机录屏。

成片 SHA-256：`CC999A45506893C61BB37B7CE5D521D23D29CAEFAA0621A6D49DF663215204C2`。
