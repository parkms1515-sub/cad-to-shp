import streamlit as st
import ezdxf
import io
import json
import streamlit.components.v1 as components
import shapefile # pip install pyshp 필수
import zipfile
import matplotlib.pyplot as plt
import os
import math # 거리 계산을 위해 추가
from pyproj import Transformer

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="CAD to SHP Web Plugin", layout="wide")

# --- 2. 세션 상태 초기화 ---
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'final_render_data' not in st.session_state:
    st.session_state.final_render_data = []
if 'converted_polygons' not in st.session_state:
    st.session_state.converted_polygons = []
if 'road_lines' not in st.session_state: # 3.2단계를 위한 세션 추가
    st.session_state.road_lines = []
if 'road_buffer_polygons' not in st.session_state:
    st.session_state.road_buffer_polygons = []
if 'pole_polygons' not in st.session_state:
    st.session_state.pole_polygons = []

# --- 3. 캔버스 렌더링 함수 (CAD 도면 확인용) ---
def render_dxf_canvas(entities_json):
    canvas_html = f"""
    <div style="border:1px solid #333; background:#ffffff; border-radius:10px; padding:0; position:relative; overflow:hidden; width:800px; height:500px;">
        <div style="position:absolute; top:10px; left:10px; background:rgba(255,255,255,0.9); padding:5px 10px; border-radius:20px; font-size:12px; z-index:10; border:1px solid #ccc; pointer-events:none;">
            🖱️ <b>휠</b>: 확대/축소 | 🖱️ <b>드래그</b>: 이동
        </div>
        <canvas id="dxfCanvas" width="800" height="500" style="cursor:grab; display:block;"></canvas>
    </div>
    <script>
        (function() {{
            const entities = {entities_json};
            const canvas = document.getElementById('dxfCanvas');
            const ctx = canvas.getContext('2d');
            
            let offset = {{ x: 0, y: 0 }};
            let zoom = 1.0;
            let isDragging = false;
            let lastMousePos = {{ x: 0, y: 0 }};

            if (!entities || entities.length === 0) return;

            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            entities.forEach(ent => {{
                ent.points.forEach(p => {{
                    if (p.x < minX) minX = p.x; if (p.y < minY) minY = p.y;
                    if (p.x > maxX) maxX = p.x; if (p.y > maxY) maxY = p.y;
                }});
            }});

            const worldW = maxX - minX;
            const worldH = maxY - minY;
            const centerX = (minX + maxX) / 2;
            const centerY = (minY + maxY) / 2;

            const padding = 40;
            const initialScale = Math.min(
                (canvas.width - padding) / (worldW || 1), 
                (canvas.height - padding) / (worldH || 1)
            );

            offset.x = canvas.width / 2;
            offset.y = canvas.height / 2;

            function draw() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.strokeStyle = "#f0f0f0";
                ctx.lineWidth = 0.5;
                for(let i=0; i<canvas.width; i+=50) {{ ctx.beginPath(); ctx.moveTo(i,0); ctx.lineTo(i,canvas.height); ctx.stroke(); }}
                for(let i=0; i<canvas.height; i+=50) {{ ctx.beginPath(); ctx.moveTo(0,i); ctx.lineTo(canvas.width,i); ctx.stroke(); }}

                ctx.save();
                ctx.translate(offset.x, offset.y);
                ctx.scale(zoom * initialScale, -zoom * initialScale);
                ctx.translate(-centerX, -centerY);

                entities.forEach(ent => {{
                    ctx.beginPath();
                    if (ent.type === "line") {{
                        ctx.strokeStyle = "#2c3e50";
                        ctx.lineWidth = 1 / (zoom * initialScale);
                        ent.points.forEach((p, i) => {{
                            if (i === 0) ctx.moveTo(p.x, p.y);
                            else ctx.lineTo(p.x, p.y);
                        }});
                        ctx.stroke();
                    }} else if (ent.type === "polygon") {{
                        ctx.strokeStyle = "#27ae60";
                        ctx.fillStyle = "rgba(39, 174, 96, 0.3)";
                        ctx.lineWidth = 2 / (zoom * initialScale);
                        ent.points.forEach((p, i) => {{
                            if (i === 0) ctx.moveTo(p.x, p.y);
                            else ctx.lineTo(p.x, p.y);
                        }});
                        ctx.closePath();
                        ctx.fill();
                        ctx.stroke();
                    }} else if (ent.type === "point") {{
                        const p = ent.points[0];
                        ctx.fillStyle = "#e74c3c";
                        ctx.beginPath();
                        ctx.arc(p.x, p.y, 4 / (zoom * initialScale), 0, Math.PI * 2);
                        ctx.fill();
                    }}
                }});
                ctx.restore();
            }}

            canvas.onmousedown = (e) => {{ isDragging = true; canvas.style.cursor = "grabbing"; lastMousePos = {{ x: e.clientX, y: e.clientY }}; }};
            window.onmouseup = () => {{ isDragging = false; canvas.style.cursor = "grab"; }};
            canvas.onmousemove = (e) => {{
                if (!isDragging) return;
                offset.x += (e.clientX - lastMousePos.x);
                offset.y += (e.clientY - lastMousePos.y);
                lastMousePos = {{ x: e.clientX, y: e.clientY }};
                draw();
            }};
            canvas.onwheel = (e) => {{
                e.preventDefault();
                const delta = -e.deltaY;
                const factor = Math.pow(1.1, delta / 200);
                zoom *= factor;
                draw();
            }};
            draw();
        }}).call(this);
    </script>
    """
    return components.html(canvas_html, height=550)

# --- 4. 상단 단계 표시 ---
steps = ["🏠 시작", "📂 DXF 로드", "🌐 좌표 설정", "🛠️ 편집"]
cols = st.columns(len(steps))
for i, step_name in enumerate(steps):
    if st.session_state.current_step == i:
        cols[i].markdown(f"**[{step_name}]**")
        cols[i].markdown("---")
    else:
        cols[i].write(step_name)

# --- 5. 단계별 콘텐츠 ---

# [단계 0: 시작]
if st.session_state.current_step == 0:
    st.subheader("📘 시스템 사용 매뉴얼")
    st.info("DXF 파일을 업로드하고 SHP로 변환하는 과정을 시작합니다.")
    if st.button("1단계: DXF 로드로 이동 ▶"):
        st.session_state.current_step = 1
        st.rerun()

# [단계 1: DXF 로드 및 캔버스]
elif st.session_state.current_step == 1:
    st.subheader("📂 1단계: DXF 파일 로드 및 도면층 확인")
    uploaded_file = st.file_uploader("DXF 파일을 업로드하세요.", type=['dxf'])
    
    if uploaded_file:
        try:
            file_bytes = uploaded_file.getvalue()
            raw_data = io.BytesIO(file_bytes)
            doc = None
            for enc in ['cp949', 'utf-8', 'latin1']:
                try:
                    raw_data.seek(0)
                    text_stream = io.TextIOWrapper(raw_data, encoding=enc, errors='ignore')
                    doc = ezdxf.read(text_stream)
                    break
                except: continue
            
            if doc:
                layers = sorted([layer.dxf.name for layer in doc.layers])
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    st.markdown("### 도면층 선택")
                    selected_layer = st.radio("시각화할 도면층 선택", layers)
                
                with col2:
                    msp = doc.modelspace()
                    entities = msp.query(f'*[layer=="{selected_layer}"]')
                    
                    render_data = []
                    line_count, point_count = 0, 0
                    
                    for e in entities:
                        try:
                            etype = e.dxftype()
                            if etype == 'LINE':
                                render_data.append({"type": "line", "points": [{"x": e.dxf.start.x, "y": e.dxf.start.y}, {"x": e.dxf.end.x, "y": e.dxf.end.y}]})
                                line_count += 1
                            elif etype in ['LWPOLYLINE', 'POLYLINE']:
                                pts = [{"x": p[0], "y": p[1]} for p in e.get_points()]
                                if pts:
                                    render_data.append({"type": "line", "points": pts})
                                    line_count += 1
                            elif etype == 'POINT':
                                render_data.append({"type": "point", "points": [{"x": e.dxf.location.x, "y": e.dxf.location.y}]})
                                point_count += 1
                        except: continue

                    if render_data:
                        st.session_state['final_render_data'] = render_data
                    
                    total = line_count + point_count
                    if total > 0:
                        st.markdown(f"### 미리보기: {selected_layer} (선:{line_count}, 점:{point_count})")
                        render_dxf_canvas(json.dumps(render_data))
                    else:
                        st.warning("⚠️ 해당 레이어에 데이터가 없습니다.")
            else: st.error("파일을 읽을 수 없습니다.")
        except Exception as e: st.error(f"❌ DXF 로드 실패: {e}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("◀ 이전 단계로"):
        st.session_state.current_step = 0
        st.rerun()
    if c2.button("2단계: 좌표 설정으로 이동 ▶"):
        if uploaded_file and st.session_state.final_render_data:
            st.session_state.current_step = 2
            st.rerun()
        else: st.warning("파일 로드 및 레이어 선택을 먼저 완료해주세요.")

# [단계 2: 좌표 설정]
elif st.session_state.current_step == 2:
    st.subheader("🌐 2단계: 좌표계 설정 및 확인")
    
    coord_options = {
        "EPSG:5186 (GRS80_중부원점_2010)": {"epsg": 5186, "wkt": 'PROJCS["KGD2002_Central_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",127.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5187 (GRS80_동부원점_2010)": {"epsg": 5187, "wkt": 'PROJCS["KGD2002_East_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",129.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5185 (GRS80_서부원점_2010)": {"epsg": 5185, "wkt": 'PROJCS["KGD2002_West_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",125.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5188 (GRS80_동해원점_2010)": {"epsg": 5188, "wkt": 'PROJCS["KGD2002_East_Sea_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",131.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5179 (GRS80_UTM-K)": {"epsg": 5179, "wkt": 'PROJCS["KGD2002_Unified_Coordinate_System",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",1000000.0],PARAMETER["False_Northing",2000000.0],PARAMETER["Central_Meridian",127.5],PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5174 (Bessel_중부원점)": {"epsg": 5174, "wkt": 'PROJCS["Korean_1985_Modified_Korea_Central_Belt",GEOGCS["GCS_Korean_Datum_1985",DATUM["D_Korean_Datum_1985",SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",500000.0],PARAMETER["Central_Meridian",127.002890277778],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:4326 (WGS84_위경도)": {"epsg": 4326, "wkt": 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'}
    }
    
    selected_coord_key = st.selectbox("도면의 원본 좌표계를 선택하세요.", options=list(coord_options.keys()))
    st.session_state.selected_epsg = coord_options[selected_coord_key]["epsg"]
    st.session_state.selected_wkt = coord_options[selected_coord_key]["wkt"]
    st.success(f"✅ 설정 완료: **{selected_coord_key}**")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("◀ 이전 단계로"):
        st.session_state.current_step = 1
        st.rerun()
    if c2.button("3단계: 배경 지도 오버레이 이동 ▶"):
        if st.session_state.get('final_render_data'):
            st.session_state.current_step = 3
            st.rerun()
        else: st.error("⚠️ 데이터가 없습니다.")

# [단계 3: 지도 오버레이 및 편집]
elif st.session_state.current_step == 3:
    st.subheader("🛠️ 3단계: 메뉴별 객체 변환 및 배경지도 오버레이")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "3.1 라인(폐합) 변환", "3.2 라인(도로) 변환", "3.3 포인트(전주) 변환", "3.4 포인트(측량) 변환", "5. 편집"
    ])

    # --- 3.1 탭: 라인 폐합 및 폴리곤 변환 ---
    with tab1:
        st.markdown("### 📐 3.1 폐합된 라인 -> 폴리곤(면) 변환")
        col_btn, col_down = st.columns([1.5, 2])

        if col_btn.button("🔍 폐합 라인 자동 검색 및 변환 (10m 허용)", key="btn_3_1_main"):
            polygons = []
            remaining_lines = []
            closed_count = 0
            tolerance = 10.0 

            for ent in st.session_state.get('final_render_data', []):
                if ent['type'] == 'line' and len(ent['points']) >= 3:
                    pts = ent['points']
                    p1, p2 = pts[0], pts[-1]
                    dist = math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)
                    
                    if dist <= tolerance:
                        closed_pts = list(pts)
                        # 시작점에 정확히 맞춤 (폐합 처리)
                        closed_pts[-1] = {"x": p1['x'], "y": p1['y']} 
                        polygons.append({"type": "polygon", "points": closed_pts, "layer": "Converted_Area"})
                        closed_count += 1
                        continue 
                remaining_lines.append(ent)
            
            st.session_state['converted_polygons'] = polygons
            st.session_state['road_lines'] = remaining_lines 
            st.success(f"✅ 분석 완료: {closed_count}개 폴리곤 변환 및 {len(remaining_lines)}개 라인 대기 중")
            st.rerun()

        # --- [복구된 다운로드 섹션] ---
        if st.session_state.get('converted_polygons'):
            st.divider()
            zip_buffer_poly = io.BytesIO()
            with zipfile.ZipFile(zip_buffer_poly, "w") as zf:
                shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
                
                # SHP 쓰기 (Polygon 타입)
                with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
                    w.field("LAYER", "C", "40")
                    for poly in st.session_state['converted_polygons']:
                        # pyshp 구조에 맞게 [[[x,y], [x,y]...]] 변환
                        w.poly([[[p['x'], p['y']] for p in poly['points']]]) 
                        w.record(poly['layer'])
                
                # 알집 구성
                zf.writestr("converted_area.shp", shp_io.getvalue())
                zf.writestr("converted_area.shx", shx_io.getvalue())
                zf.writestr("converted_area.dbf", dbf_io.getvalue())
                zf.writestr("converted_area.prj", st.session_state.get('selected_wkt', ''))
            
            st.download_button(
                label="📦 폐합 폴리곤 SHP(ZIP) 내려받기",
                data=zip_buffer_poly.getvalue(),
                file_name="converted_polygons.zip",
                mime="application/zip",
                key="poly_3_1_download"
            )
            
    # --- 3.2 탭: 도로 버퍼 변환 ---
    with tab2:
        st.markdown("### 🛣️ 3.2 라인(도로) 버퍼 변환")
        road_data = st.session_state.get('road_lines', [])
        
        if not road_data:
            st.info("ℹ️ 3.1단계에서 분류된 도로 후보 데이터가 없습니다.")
        else:
            col_input, col_info = st.columns([1, 2])
            with col_input:
                buffer_dist = st.number_input("버퍼 거리 입력 (m)", min_value=0.1, value=1.0, step=0.5)
            with col_info:
                st.write("")
                st.caption(f"💡 입력하신 {buffer_dist}m 간격으로 외곽선을 생성합니다.")

            if st.button("🛠️ 버퍼 적용 및 데이터 확정"):
                buffer_polygons = []
                for line in road_data:
                    pts = line['points']
                    if len(pts) < 2: continue
                    left_side, right_side = [], []
                    for i in range(len(pts)):
                        p1 = pts[i]
                        p2 = pts[i+1] if i < len(pts)-1 else pts[i]
                        p0 = pts[i-1] if i > 0 else pts[i]
                        
                        # 좌표 추출 (딕셔너리/리스트 대응)
                        c_x, c_y = (p1['x'], p1['y']) if isinstance(p1, dict) else (p1[0], p1[1])
                        n_x, n_y = (p2['x'], p2['y']) if isinstance(p2, dict) else (p2[0], p2[1])
                        p_x, p_y = (p0['x'], p0['y']) if isinstance(p0, dict) else (p0[0], p0[1])
                        
                        dx, dy = n_x - p_x, n_y - p_y
                        length = math.sqrt(dx**2 + dy**2)
                        if length == 0: continue
                        
                        nx, ny = -dy/length * buffer_dist, dx/length * buffer_dist
                        left_side.append([c_x + nx, c_y + ny])
                        right_side.insert(0, [c_x - nx, c_y - ny])
                    
                    poly_pts = left_side + right_side + [left_side[0]]
                    buffer_polygons.append({"points": poly_pts})
                
                st.session_state['road_buffer_polygons'] = buffer_polygons
                st.success(f"✅ {len(buffer_polygons)}개의 도로 객체 변환 완료!")
                st.rerun()

            # --- [복구된 다운로드 섹션] ---
            if st.session_state.get('road_buffer_polygons'):
                st.divider()
                zip_buffer_road = io.BytesIO()
                with zipfile.ZipFile(zip_buffer_road, "w") as zf:
                    shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
                    with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
                        w.field("LAYER", "C", "40")
                        w.field("BUF_DIST", "F", 10, 2)
                        for poly in st.session_state['road_buffer_polygons']:
                            w.poly([poly['points']])
                            w.record("Road_Buffer", buffer_dist)
                    
                    zf.writestr("road_buffer.shp", shp_io.getvalue())
                    zf.writestr("road_buffer.shx", shx_io.getvalue())
                    zf.writestr("road_buffer.dbf", dbf_io.getvalue())
                    zf.writestr("road_buffer.prj", st.session_state.get('selected_wkt', ''))
                
                st.download_button(
                    label="📦 변환된 도로 SHP(ZIP) 내려받기",
                    data=zip_buffer_road.getvalue(),
                    file_name="road_buffer_result.zip",
                    mime="application/zip",
                    key="road_buffer_download"
                )

    # --- 3.3 탭: 포인트(전주) 변환 ---
    with tab3:
        st.markdown("### 📍 3.3 포인트(전주) 변환")
        all_data = st.session_state.get('final_render_data', [])
        point_data = [ent for ent in all_data if ent['type'] == 'point']
        
        if not point_data:
            st.info("ℹ️ 현재 레이어에 포인트(점) 데이터가 없습니다.")
        else:
            pole_radius = st.number_input("전주 심볼 반경 (m)", min_value=0.1, value=0.5, step=0.1)
            if st.button("🔌 전주 객체 변환", key="btn_3_3_convert"):
                pole_polygons = []
                for p_ent in point_data:
                    center = p_ent['points'][0]
                    cx, cy = center['x'], center['y']
                    sides = 8 
                    poly_pts = []
                    for i in range(sides):
                        angle = math.radians(i * (360 / sides))
                        px = cx + pole_radius * math.cos(angle)
                        py = cy + pole_radius * math.sin(angle)
                        poly_pts.append([px, py])
                    poly_pts.append(poly_pts[0]) # 폐합
                    pole_polygons.append({"points": poly_pts, "center": [cx, cy]})
                
                st.session_state['pole_polygons'] = pole_polygons
                st.success(f"✅ {len(pole_polygons)}개의 전주 객체 변환 완료!")
                st.rerun()

            # --- [복구된 다운로드 섹션] ---
            if st.session_state.get('pole_polygons'):
                st.divider()
                zip_pole = io.BytesIO()
                with zipfile.ZipFile(zip_pole, "w") as zf:
                    shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
                    
                    # SHP 쓰기 (Polygon 타입)
                    with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
                        w.field("TYPE", "C", "20")
                        w.field("COORD_X", "F", 10, 3)
                        w.field("COORD_Y", "F", 10, 3)
                        for pole in st.session_state['pole_polygons']:
                            # 폴리곤 좌표 기록
                            w.poly([pole['points']])
                            # 속성 데이터 기록 (전주 타입, 중심 X, 중심 Y)
                            w.record("Utility_Pole", pole['center'][0], pole['center'][1])
                    
                    # ZIP 구성품 추가
                    zf.writestr("pole_symbol.shp", shp_io.getvalue())
                    zf.writestr("pole_symbol.shx", shx_io.getvalue())
                    zf.writestr("pole_symbol.dbf", dbf_io.getvalue())
                    zf.writestr("pole_symbol.prj", st.session_state.get('selected_wkt', ''))
                
                st.download_button(
                    label="📦 전주 SHP(ZIP) 내려받기",
                    data=zip_pole.getvalue(),
                    file_name="utility_pole_data.zip",
                    mime="application/zip",
                    key="pole_3_3_download"
                )

    # --- 3.4 탭: 포인트(측량) 단계별 변환 ---
    with tab4:
        st.markdown("### 📐 3.4 포인트(측량) 단계별 변환")
        survey_pts = [e for e in st.session_state.get('final_render_data', []) if e['type'] == 'point']
        if not survey_pts: 
            st.info("ℹ️ 변환할 포인트 데이터가 없습니다.")
        else:
            is_closed = st.checkbox("시점-종점 연결(폐합)", value=True)
            if st.button("🛣️ 1단계: 포인트 -> 라인 변환"):
                line_coords = [[p['points'][0]['x'], p['points'][0]['y']] for p in survey_pts]
                if is_closed and len(line_coords) > 2: 
                    line_coords.append(line_coords[0])
                st.session_state['survey_step_line'] = line_coords
                st.success("✅ 라인 생성 완료 (하단 지도 주황색 확인)")
                st.rerun()
            
            if 'survey_step_line' in st.session_state:
                if st.button("🟦 2단계: 라인 -> 폴리곤 변환"):
                    # 폴리곤 형태로 변환하여 세션 저장
                    st.session_state['survey_step_poly'] = [{"points": st.session_state['survey_step_line']}]
                    st.success("✅ 폴리곤 확정 완료 (하단 지도 보라색 확인)")
                    st.rerun()

            # --- [추가] 3단계: 다운로드 기능 ---
            if 'survey_step_poly' in st.session_state:
                st.divider()
                st.markdown("#### 3️⃣ 3단계: 결과물 내보내기")
                
                # 메모리 내 ZIP 파일 생성
                zip_survey_io = io.BytesIO()
                with zipfile.ZipFile(zip_survey_io, "w") as zf:
                    shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
                    
                    # SHP 쓰기 (Polygon 타입)
                    with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
                        w.field("NAME", "C", "40")
                        for poly in st.session_state['survey_step_poly']:
                            # pyshp는 [[[x,y], [x,y]...]] 형태의 리스트를 받음
                            w.poly([poly['points']])
                            w.record("Survey_Area")
                    
                    # 압축 파일 구성
                    zf.writestr("survey_area.shp", shp_io.getvalue())
                    zf.writestr("survey_area.shx", shx_io.getvalue())
                    zf.writestr("survey_area.dbf", dbf_io.getvalue())
                    # 좌표계 정보(WKT) 추가
                    zf.writestr("survey_area.prj", st.session_state.get('selected_wkt', ''))
                
                st.download_button(
                    label="📦 측량 폴리곤 SHP(ZIP) 내려받기",
                    data=zip_survey_io.getvalue(),
                    file_name="survey_polygon_result.zip",
                    mime="application/zip"
                )
                
    # --- 통합 배경 지도 (모든 데이터 한 곳에 표시) ---
    st.markdown("---")
    st.markdown("### 🌍 통합 실시간 배경 지도")
    
    src_epsg = st.session_state.get('selected_epsg', 5186)
    try:
        transformer = Transformer.from_crs(f"EPSG:{src_epsg}", "EPSG:4326", always_xy=True)
        viz_features = []

        # 1. 원본 라인/포인트 (파랑/빨강)
        for ent in st.session_state.get('final_render_data', []):
            if ent['type'] == 'line':
                viz_features.append({"type":"line", "coordinates":[list(transformer.transform(p['x'],p['y']))[::-1] for p in ent['points']], "color":"#007bff"})
            elif ent['type'] == 'point':
                lon, lat = transformer.transform(ent['points'][0]['x'], ent['points'][0]['y'])
                viz_features.append({"type":"point", "coordinates":[lat, lon], "color":"red"})

        # 2. 3.1 폐합 폴리곤 (초록)
        for poly in st.session_state.get('converted_polygons', []):
            viz_features.append({"type":"polygon", "coordinates":[list(transformer.transform(p['x'],p['y']))[::-1] for p in poly['points']], "color":"#28a745"})

        # 3. 3.2 도로 버퍼 (회색)
        for r_poly in st.session_state.get('road_buffer_polygons', []):
            viz_features.append({"type":"polygon", "coordinates":[list(transformer.transform(p[0],p[1]))[::-1] for p in r_poly['points']], "color":"#6c757d"})

        # 4. 3.4 측량 라인 (오렌지) & 폴리곤 (보라)
        if 'survey_step_line' in st.session_state:
            viz_features.append({"type":"line", "coordinates":[list(transformer.transform(p[0],p[1]))[::-1] for p in st.session_state['survey_step_line']], "color":"#fd7e14", "weight":5})
        if 'survey_step_poly' in st.session_state:
            for s_poly in st.session_state['survey_step_poly']:
                viz_features.append({"type":"polygon", "coordinates":[list(transformer.transform(p[0],p[1]))[::-1] for p in s_poly['points']], "color":"#6f42c1"})

        map_html = f"""
        <div style="border:1px solid #333; border-radius:10px; overflow:hidden;">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <div id="map" style="width: 100%; height: 600px;"></div>
            <script>
                (function() {{
                    const map = L.map('map').setView([36.5, 127.5], 7);
                    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
                    const features = {json.dumps(viz_features)};
                    const group = new L.featureGroup();
                    features.forEach(f => {{
                        let layer;
                        if (f.type === 'line') layer = L.polyline(f.coordinates, {{color: f.color, weight: f.weight || 3}});
                        else if (f.type === 'polygon') layer = L.polygon(f.coordinates, {{color: f.color, fillOpacity: 0.5}});
                        else if (f.type === 'point') layer = L.circleMarker(f.coordinates, {{radius: 5, color: f.color, fillOpacity: 0.8}});
                        if(layer) layer.addTo(group);
                    }});
                    group.addTo(map);
                    if (features.length > 0) map.fitBounds(group.getBounds());
                }})();
            </script>
        </div>
        """
        components.html(map_html, height=630)
    except Exception as e: st.error(f"지도 오류: {e}")

    st.markdown("---")
    if st.button("◀ 이전 단계로"):
        st.session_state.current_step = 2
        st.rerun()