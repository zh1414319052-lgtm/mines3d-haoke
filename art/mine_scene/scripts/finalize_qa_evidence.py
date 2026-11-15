"""Freeze documentation from measured final build/device evidence; never infer missing passes."""
from pathlib import Path
import hashlib, json, re, xml.etree.ElementTree as ET

ART=Path(__file__).resolve().parents[1]
ROOT=ART.parents[1]
REVIEW=ART/'review'
APK=ROOT/'app/build/outputs/apk/debug/app-debug.apk'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return p.read_text(encoding='utf-8-sig')

perf=read(REVIEW/'device-perf-final.log')
regression=json.loads(read(REVIEW/'device-final-regression.json'))
assert regression['passed'] and regression['apk_sha256']==regression['installed_sha256']==sha(APK)
assert 'PASS perf' in perf and 'FAIL ' not in perf, 'Final performance run has not passed'
pattern=r'elapsedMs=(\d+) rendered=(\d+) cadenceFps=([\d.]+) pssKb=(\d+) thermal=(-?\d+)'
final=re.search(r'PERF FINAL '+pattern,perf)
assert final and int(final[1])>=720000
samples=list(dict.fromkeys(re.findall(pattern,perf)))
tests=[ET.parse(p).getroot() for p in (ROOT/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
count=sum(int(t.attrib['tests']) for t in tests)
failures=sum(int(t.attrib['failures'])+int(t.attrib['errors']) for t in tests)
assert count==32 and failures==0
lint=read(ROOT/'app/build/reports/lint-results-debug.txt')
assert '0 errors, 40 warnings' in lint
for suite,file in [('flows','device-flows.log'),('levels','device-levels-final.log'),('options','device-options.log'),('lifecycle','device-lifecycle.log'),('persistence','device-persistence.log'),('showcase','device-showcase-final.log')]:
    data=read(REVIEW/file)
    assert 'PASS '+suite in data and 'FAIL ' not in data,file
audio=json.loads(read(REVIEW/'phone-audio-check-final.json'))
assert audio['samples_at_or_over_0dbfs']==0 and audio['first_half_second_normalized_correlation']>.98
pss=max(int(s[3]) for s in samples)
thermal=max(int(s[4]) for s in samples)
metrics={'passed':True,'device':'OnePlus PKG110 / Android 16 / Adreno 750',
 'board':'15x15x8, 540 mines, overview, continuous redraw and repeated orbit gestures',
 'elapsed_ms':int(final[1]),'rendered_frames':int(final[2]),'mean_draw_cadence_fps':float(final[3]),
 'sampled_peak_pss_kb':pss,'max_sampled_thermal_status':thermal,
 'method_limit':'GL draw callback cadence, not GPU timestamps or independently measured display presentation FPS.'}
verification={'edition':'1.7.1-qa.4','date':'2026-11-13','apk_sha256':sha(APK),'apk_bytes':APK.stat().st_size,
 'application_id':'cos.premy.mines.qa','version_code':18,'jvm_tests':count,'jvm_failures':failures,
 'test_suites':[{'name':t.attrib['name'],'tests':int(t.attrib['tests'])} for t in tests],
 'lint_errors':0,'lint_warnings':40,'performance':metrics,'audio_capture':audio,
 'test_revision_note':'Full flows passed before the final escape-2 seed and ignition-light refinement. Final level suite rechecks all three escape levels; final showcase/perf/options/lifecycle/persistence recheck the final APK. No core rule change followed the full flows run.',
 'untested':['Other phone models, low/mid-range GPUs and Android 4.4–15 hardware',
 'Physical speaker/headphone listening and acoustical measurements',
 'Independent GPU/presentation timing, battery drain and multi-hour endurance',
 'Full TalkBack board navigation, store release/signing/publication'],
 'original_blend_sha256':sha(ART/'Mines3D_DeepSector.blend'),
 'source_font_sha256':sha(ART/'fonts/NotoSansSC-VF.ttf')}
(REVIEW/'phase2-verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf8')
path=ART/'PHASE_2_HANDOFF.md';text=read(path)
start=text.index('用户已确认第一阶段');end=text.index('## 系统影响与进度')
text=text[:start]+f'用户已确认第一阶段样片并授权继续第二阶段。2026-11-13：沿用 Java / OpenGL ES 2 完成 QA.4 的场景、音效和五种新玩法。32 项 JVM 测试通过，Lint 0 错误 / 40 条警告；已在 PKG110 / Android 16 安装并验证。APK SHA-256：`{sha(APK)}`。\n\n'+text[end:]
start=text.index('| 项目 | 状态 |');end=text.index('## 先做同机位',start)
table=f'''| 项目 | 状态 | 实际证据 |
| --- | --- | --- |
| 同布局手机切片 | done | device-showcase-final.log：样片原布局、开安全格、插旗、选中踩雷及延迟结算；实际手机声画抽查。 |
| 材质、灯光与爆炸 | done | 原始几何/贴图/声音；36 个实时碎片、原体积烘焙图集、发光核心与邻近受光。phone-blast-sync-final.jpg。 |
| 五种玩法与共用规则 | done | device-flows.log、device-levels-final.log；三关撤离、三关无猜、三类断层、两次扫描、每日固定图；独立关卡数据复核。 |
| UI / 简中英文 / 设置 | done | device-options.log：真实设置开关、英文 Android Context、注入渲染故障后的同局平面兼容操作。 |
| 状态恢复 / 一次性声画 | done | device-lifecycle.log、device-persistence.log：后台计时、磁盘恢复、横竖屏重建、爆炸阶段恢复和结束后不重播。 |
| 真机与最大规模 | done | device-perf-final.log：{int(final[1])/1000:.1f} 秒，15×15×8 / 540 雷，绘制节奏 {float(final[3]):.2f}/秒；峰值 PSS {pss/1024:.1f} MiB，最高热状态 {thermal}。 |
| QA APK与对应源码 | done | 本地 APK 与完整对应源码 ZIP；打包脚本校验测试证据/哈希，保留 .blend、声音分轨、贴图、字体许可与导出脚本。 |

### 验收范围与限制

- 最终构建：32 项 JVM 测试、0 失败；Lint 0 错误、40 条警告（旧资源、View 工具构造器、无障碍、文本拼接等），未声称零警告。
- 完整模式回归先于最后的第二关种子与起爆发光微调；之后重跑三关撤离、最终声画、持续性能及设置/生命周期/恢复，验证改动路径。公开线索求解器测试验证三个无猜关卡；玩家误旗不作为推理真值。
- 最大棋盘已测内层/四角选格、真实双指缩放与平移、旋转、快速换层，棋盘数据保持一致。尺寸 15×15 使用简化倒角与缩放/平移查看；全局图不保证所有小数字同时可读。
- 性能是 GL 绘制调用节奏，非独立 GPU 帧时或屏幕呈现 FPS。压力测试强制持续刷新；正常静止局面按需绘制。热状态 2 表示中度，不代表无发热。
- 手机数字回采峰值 {audio['peak_dbfs']:.2f} dBFS，无满幅削波；原爆炸前半秒相关度 {audio['first_half_second_normalized_correlation']:.5f}。帧抽查声画起点处于约两帧范围。没有做实体扬声器/耳机听感或声学测量。
- 仅 PKG110 / Android 16 真机通过。中低端设备、Android 4.4–15 真机、独立 GPU 测量、电池续航、多小时耐久和完整 TalkBack 棋盘导航未验证。
- 本轮是本地 QA 调试签名交付，未执行商店上架、正式签名发行或网站发布。

'''
text=text[:start]+table+text[end:]
text=text.replace('快捷双击和长按必须与拖动、捏合可靠区分。','本版采用选格后按钮操作；可选的双击/长按快捷开格未启用。')
path.write_text(text,encoding='utf8')
(ART/'WORK_STATUS.md').write_text('''# 当前工作状态

第一阶段 Blender 样片已确认；第二阶段本地 Android QA.4 已完成场景、五种玩法及当前设备验证。

唯一需求与验收表为 PHASE_2_HANDOFF.md；机器可读证据为 review/phase2-verification.json。
源码上级目录交付 QA APK、对应源码 ZIP 与交付说明.md。保留现有 Java / GLES2 工程、原 .blend、音效分轨、贴图和字体许可。
已安装 PKG110 的 APK 与交付 APK 按 SHA-256 核对。32 项 JVM 测试、12 分钟最大棋盘压力测试及针对性真机流程通过。
未验证范围见唯一验收表；没有未保存的 Blender 编辑，不存在等待用户批准的第二阶段步骤。
''',encoding='utf8')
print(json.dumps(verification,ensure_ascii=False,indent=2))
