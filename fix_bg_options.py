"""탭3, 탭4의 BG_OPTIONS에서 지적도 항목 제거 스크립트"""
import re

path = r"c:\Users\kfca\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\dxftest\dxftest_dialog.py"

with open(path, encoding="utf-8") as f:
    content = f.read()

# 두 줄짜리 BG_OPTIONS를 한 줄 (배경, 위성, OSM) 으로 교체
old = (
    r'BG_OPTIONS = \[.*?vworld_cadastral.*?\n'
    r'.*?vworld_base.*?osm.*?\]'
)
new = 'BG_OPTIONS = [("브이월드 배경", "vworld_base"), ("브이월드 위성", "vworld_sat"), ("OSM", "osm")]'

result, n = re.subn(old, new, content, flags=re.DOTALL)
print(f"교체 횟수: {n}")

with open(path, "w", encoding="utf-8") as f:
    f.write(result)

print("완료")
