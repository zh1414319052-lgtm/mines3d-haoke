"""Write the primary local delivery note after the APK/source archive are verified."""
from pathlib import Path
import hashlib,json,zipfile
ART=Path(__file__).resolve().parents[1];ROOT=ART.parents[1];DEST=ROOT.parent
v=json.loads((ART/'review/phase2-verification.json').read_text(encoding='utf8'))
p=json.loads((ART/'review/package-result.json').read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha(p['apk'])==p['apk_sha256']==v['apk_sha256']
assert sha(p['source_zip'])==p['source_zip_sha256']
with zipfile.ZipFile(p['source_zip']) as z:
    assert z.testzip() is None
    manifest=json.loads(z.read('源码/art/mine_scene/mobile/QA_MANIFEST.json'))
    for f in manifest['files']:
        data=z.read('源码/'+f['path'])
        assert hashlib.sha256(data).hexdigest()==f['sha256'],f['path']
perf=v['performance'];audio=v['audio_capture']
note=f'''# 三维扫雷 · 矿井 3D · Android QA.4

2026-11-13，本地 QA 交付。已在用户的 OnePlus PKG110 / Android 16 真机安装运行。

## 文件与安装

- 安装包：`{Path(p['apk']).name}`（{p['apk_bytes']:,} 字节，约 {p['apk_bytes']/1024/1024:.1f} MiB）。
- 对应源码：`{Path(p['source_zip']).name}`（{p['source_zip_bytes']:,} 字节，{p['source_files']} 个文件）；现有可编辑目录为 `源码`。
- 包名 `cos.premy.mines.qa`，versionCode 18，versionName `1.7.1-qa.4`，Android API 19 起，目标 API 36。沿用 QA 调试证书，可覆盖升级同签名 QA 包，与上游正式包并存。
- 在手机打开 APK 按系统安装提示完成。ColorOS 若出现安装校验，需在手机手动完成。当前这台手机已完成安装。

## 操作

1. 首页选择经典、矿井撤离、无猜解谜、断层矿井、有限扫描或每日同图。
2. 单击矿板选择，高亮后按底部「开格」或「插旗／取消旗帜」。单指拖动旋转，双指缩放和平移；「复位镜头」恢复斜俯视。
3. B1 为最高层，顶栏箭头换层。「全局视图」看层叠关系，「当前层视图」操作内层和边角。只有当前层参加选格，换层后旧选中作废。
4. 数字只统计同层上下左右和相邻层同坐标，最多六邻格。首次实际开格安全。除撤离外，正确标记全部地雷且无误标获胜；踩雷失败。
5. 撤离三关依次学习跨层、路线取舍和断层绕行；打开绿色入口到橙色出口的安全路线获胜。无猜三关有公开线索提示，先高亮相关格，再点提示查看解释。
6. 扫描每局两次，只拆分已开数字格的本层/跨层数量。每日同图按设备本地日期固定种子与起点，同日重试不换图，本地保存用时、误标、提示和最佳成绩。
7. 设置可关闭音效或减弱闪光与震屏。简中/英文随系统首选语言。切后台暂停计时和声音；首页「继续对局」可恢复检查点。

## 本轮已实际通过

- Gradle 构建、{v['jvm_tests']} 项 JVM 测试全部通过；Lint 0 错误、40 条警告，保留具体报告说明，不宣称零警告。
- 默认 5×5×2 开局、首格安全、开格、旗帜、误旗阻止胜利、胜负结算；最大 15×15×8 / 540 雷的六邻接与安全生成。
- 真机操作验证三关撤离、三关无猜（12/17/27 步公开推理）、三种断层、两次扫描/第三次拒绝、每日重试相同局面及记录。
- 内层和四角真实投影点选、快速换层、旋转、双指缩放/平移不改棋盘；公开求解不把玩家旗帜当真值。
- HOME 后计时暂停、磁盘检查点恢复棋盘/旗帜/层号/用时；横竖屏 Activity 重建保留棋盘与提示；爆炸后台冻结、恢复续播、结束后不再次起爆。
- 设置真实开关；英文 Android Context 中的实际局内控件；注入渲染失败后的平面兼容开格与扫描。
- 样片同布局可操作片段、矿灯和真实几何、起爆核心、局部闪光、36 个重力/碰撞碎片及原体积烘焙矿尘；实际手机数字回采爆炸峰值 {audio['peak_dbfs']:.2f} dBFS，无满幅削波，声画抽帧约两帧内对应。
- PKG110 / Adreno 750 最大棋盘持续压力测试 {perf['elapsed_ms']/1000:.1f} 秒，平均 GL 绘制节奏 {perf['mean_draw_cadence_fps']:.2f}/秒，采样峰值 PSS {perf['sampled_peak_pss_kb']/1024:.1f} MiB，最高 Android 热状态 {perf['max_sampled_thermal_status']}（中度）。测试强制持续绘制及旋转，正常静止时按需刷新。
- APK v1/v2 签名、16 KB 页对齐检查通过；手机安装文件和交付 APK 哈希相同。源码 ZIP 完整性及逐文件 SHA-256 校验通过。

完整模式回归在最后的撤离第二关种子/起爆光效微调之前完成；微调后重新验证三关撤离、最终声画、12 分钟性能、设置和恢复路径。证据随源码保存在 `art/mine_scene/review`。

## 未验证与边界

- 真机只测了 PKG110 / Android 16；中低端设备、其他 GPU 及 Android 4.4–15 真机未验证。
- 绘制节奏并非独立 GPU 帧时或屏幕呈现 FPS；未做电池续航、多小时耐久或实体扬声器/耳机听感测量。
- 手机端使用 GLES2 光照、有限实时碎片和原体积动画图集；保留样片资产与节奏，但不承诺与 Cycles 逐像素一致。
- 完整 TalkBack 棋盘导航未验证。3D 采用点选加按钮操作，可选双击/长按快捷操作未启用。
- 本次仅本地 QA，未进行正式证书发行、商店上架或网站发布。Debug 内有专用测试 runner，运行它会替换 QA「继续对局」记录。

## 源码、美术与许可

沿用 Mines3D 1.7.1 上游提交 `535b3e547585aca7c10443fd0ce0ea84961ea7c5`，保留 Přemysl Šťastný 与贡献者归属、GPL-3.0-only 许可证。源码含 Android 工程、Gradle wrapper、测试、原始 `Mines3D_DeepSector.blend`、贴图、独立声音和六条分轨、透明矿尘帧及生成/导出脚本。

本项目矿井美术与音效为程序原创生成，无第三方付费采样。Noto Sans / Noto Sans SC 使用 SIL OFL 1.1，允许商用，字体原件与许可保留。源码 ZIP 排除机器 SDK 路径、缓存、私有签名密钥和临时录屏。

构建：JDK 21、Android SDK 36、Gradle 8.13 / AGP 8.13.2；设置 `ANDROID_HOME`，从源码执行 `gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug`。Windows 中文路径若导致 JVM 测试类加载异常，可映射到确认未占用的 ASCII 盘符后执行。已包含运行时资产，重新编译 APK 无需重新渲染 Blender。

## SHA-256

- APK：`{p['apk_sha256'].upper()}`
- 源码 ZIP：`{p['source_zip_sha256'].upper()}`
- QA 签名证书：`A1519F2F24B603F1CD5AB4E76EC440C5275036A8DFCC439EB1AB868F35D0DDB2`
- 原 Blender 场景：`{v['original_blend_sha256'].upper()}`
'''
(DEST/'交付说明.md').write_text(note,encoding='utf8')
print('Verified APK, source ZIP and every manifest entry; wrote '+str(DEST/'交付说明.md'))
