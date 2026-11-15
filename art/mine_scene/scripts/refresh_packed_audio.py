"""Update packed soundtrack only; no geometry, animation or render settings change."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
assert bpy.app.background
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'),load_ui=False)
bpy.context.preferences.filepaths.save_version=0
seq=bpy.context.scene.sequence_editor
strips=seq.strips if hasattr(seq,'strips') else seq.sequences
for strip in strips:
    if strip.type!='SOUND':continue
    old=strip.sound;name=old.name
    new=bpy.data.sounds.load(str(ROOT/'audio/stems'/(strip.name+'.wav')),check_existing=False)
    strip.sound=new;new.pack()
    if old.users==0:bpy.data.sounds.remove(old)
    new.name=name
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'))
print('Refreshed six packed sound stems; visual scene unchanged.')
