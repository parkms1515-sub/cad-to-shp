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
import folium
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
    # JSON 데이터가 유효한지 확인하고, 문자열로 변환
    canvas_html = f"""
    <div id="container" style="border:2px solid #4A90E2; background:#ffffff; border-radius:10px; width:100%; height:500px; position:relative;">
        <canvas id="dxfCanvas" style="cursor:grab; width:100%; height:100%;"></canvas>
        <div style="position:absolute; top:10px; left:10px; background:rgba(255,255,255,0.8); padding:5px; border-radius:5px; font-size:12px; pointer-events:none;">
            🔍 휠: 확대/축소 | ✋ 드래그: 이동
        </div>
    </div>
    <script>
        (function() {{
            const entities = {entities_json};
            const canvas = document.getElementById('dxfCanvas');
            const ctx = canvas.getContext('2d');
            
            // 컨테이너 크기에 맞춰 해상도 설정
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;

            if (!entities || entities.length === 0) {{
                ctx.fillText("데이터가 없습니다.", 20, 20);
                return;
            }}

            // 1. 전체 바운딩 박스 계산
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

            // 2. 초기 스케일 및 오프셋 설정
            let zoom = 0.9 * Math.min(canvas.width / (worldW || 1), canvas.height / (worldH || 1));
            let offsetX = canvas.width / 2;
            let offsetY = canvas.height / 2;

            let isDragging = false;
            let lastMousePos = {{ x: 0, y: 0 }};

            function draw() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                ctx.save();
                // 화면 중앙으로 이동 후 스케일 조정 (Y축 반전)
                ctx.translate(offsetX, offsetY);
                ctx.scale(zoom, -zoom); 
                ctx.translate(-centerX, -centerY);

                entities.forEach(ent => {{
                    ctx.beginPath();
                    ctx.lineWidth = 1 / zoom; // 줌에 상관없이 일정한 선 굵기
                    
                    if (ent.type === "line") {{
                        ctx.strokeStyle = "#2c3e50";
                        ent.points.forEach((p, i) => {{
                            if (i === 0) ctx.moveTo(p.x, p.y);
                            else ctx.lineTo(p.x, p.y);
                        }});
                        ctx.stroke();
                    }} else if (ent.type === "point") {{
                        const p = ent.points[0];
                        ctx.fillStyle = "#e74c3c";
                        ctx.arc(p.x, p.y, 3 / zoom, 0, Math.PI * 2);
                        ctx.fill();
                    }}
                }});
                ctx.restore();
            }}

            // 이벤트 리스너
            canvas.onmousedown = (e) => {{ isDragging = true; lastMousePos = {{ x: e.clientX, y: e.clientY }}; }};
            window.onmouseup = () => {{ isDragging = false; }};
            canvas.onmousemove = (e) => {{
                if (!isDragging) return;
                offsetX += (e.clientX - lastMousePos.x);
                offsetY += (e.clientY - lastMousePos.y);
                lastMousePos = {{ x: e.clientX, y: e.clientY }};
                draw();
            }};
            canvas.onwheel = (e) => {{
                e.preventDefault();
                const scaleFactor = 1.1;
                if (e.deltaY < 0) zoom *= scaleFactor;
                else zoom /= scaleFactor;
                draw();
            }};

            draw();
        }})();
    </script>
    """
    return components.html(canvas_html, height=520)
# --- [추가] 사이드바 단계 표시 가이드 ---
with st.sidebar:
    st.markdown("## ⚙️ 작업 진행 단계")
    
    # 각 단계별 완료 여부 확인
    is_3_1_done = st.session_state.get('btn_3_1_downloaded', False)
    is_3_2_done = st.session_state.get('btn_3_2_done', False)
    
    # 3단계 통합 완료 체크 (3.1이나 3.2 중 하나라도 완료되면 완료로 간주)
    is_step_3_complete = is_3_1_done or is_3_2_done

    menu_3_text = "객체 변환 및 지도 확인"
    if is_step_3_complete:
        menu_3_text = f"~~{menu_3_text}~~ (종결)"

    steps = ["시작 화면", "도면 데이터 분석", "좌표계 설정", menu_3_text]
    
    for i, step_name in enumerate(steps):
        # 1. 완료된 경우 (3단계이면서 작업이 끝났거나, 현재 단계보다 이전인 경우)
        if (i == 3 and is_step_3_complete) or (st.session_state.current_step > i):
            display_name = step_name if "~~" in step_name else f"~~{step_name}~~"
            st.markdown(f"✅ {i}. {display_name}")
            
        # 2. 현재 진행 중인 경우
        elif st.session_state.current_step == i:
            st.markdown(f"#### 🔵 **{i}. {step_name}** (진행 중)")
            
        # 3. 아직 도달하지 않은 경우
        else:
            st.markdown(f"⚪ {i}. {step_name}")
    
# --- 5. 단계별 콘텐츠 ---
# --- [추가] 우측 상단 초기화 버튼 (오른쪽 정렬) ---
# 화면을 8:2 혹은 9:1 비율로 나누어 오른쪽 칸만 사용합니다.
top_col1, top_col2 = st.columns([9, 1])

with top_col2:
    # CSS를 사용하여 버튼을 오른쪽 끝으로 정렬
    st.markdown("""
        <style>
        .element-container:has(#reset_btn) {
            display: flex;
            justify-content: flex-end;
        }
        </style>
        """, unsafe_allow_html=True)
    
    if st.button("🔄 초기화", key="reset_btn", use_container_width=False):
        # 세션 초기화 로직
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.current_step = 0
        st.rerun()

st.write("---") # 버튼 아래 구분선 (선택 사항)
# [단계 0: 시작 화면 - 오류 수정 및 중앙 정렬 최적화]
if st.session_state.current_step == 0:
    # 1. 메인 타이틀 (HTML 중앙 정렬)
    st.markdown("<h1 style='text-align: center;'>🏗️ CAD to SHP Web Converter</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>v1.0 | 수치지형도 및 지적도 기반 GIS 데이터 변환 도구</p>", unsafe_allow_html=True)
    st.write(" ")

    # 2. 작업 전 주의 사항 (기존 디자인 유지)
    st.markdown("### ⚠️ 작업 전 파일 확인 사항")
    st.info("""
    **안정적인 변환을 위해 아래 조건을 반드시 확인해 주세요.**
    
    1.  **파일 버전**: 반드시 **DXF (2007 버전) 이하**의 파일로 변환하여 진행하세요.
    2.  **좌표 정보**: 캐드 파일은 **수치지형도 및 지적도**의 다운로드 받은 좌표 정보를 가지고 있어야 합니다.
    3.  **객체 구성**: **하나의 도면층(Layer)에는 하나의 유형**(라인 또는 포인트 중 하나) 객체로 가지고 있어야 합니다.
    """)
    
    # --- 주의 사항 하단 구분선 ---
    st.markdown("---")

    # 3. 작업 단계 안내 (중앙 정렬 및 텍스트 크기 최적화)
    # 양쪽 여백([0.5, 3, 0.5])을 주어 가운데 콘텐츠를 집중시킵니다.
    _, center_content, _ = st.columns([0.5, 3, 0.5])
    
    with center_content:
        st.markdown("<h4 style='text-align: center;'>⚙️ 작업 진행 단계</h4>", unsafe_allow_html=True)
        st.write(" ")
        step_col1, step_col2, step_col3 = st.columns(3)
        
        with step_col1:
            st.markdown("<div style='text-align: center;'><h3> 1️⃣</h3><b>DXF 분석</b><br><small>도면층별 객체 추출</small></div>", unsafe_allow_html=True)

        with step_col2:
            st.markdown("<div style='text-align: center;'><h3> 2️⃣</h3><b>좌표 등록</b><br><small>EPSG 좌표계 설정</small></div>", unsafe_allow_html=True)

        with step_col3:
            st.markdown("<div style='text-align: center;'><h3> 3️⃣</h3><b>SHP 추출</b><br><small>GIS 데이터 변환</small></div>", unsafe_allow_html=True)

    st.write(" ")
    st.write(" ")

    # 4. 시작 버튼 (중앙 정렬 버튼)
    _, btn_center, _ = st.columns([1, 2, 1])
    with btn_center:
        if st.button("🚀 위 조건을 확인했으며, 변환을 시작합니다", use_container_width=True, type="primary"):
            st.session_state.current_step = 1
            st.rerun()

# [단계 1: DXF 로드 및 기능 분할 레이아웃]
elif st.session_state.current_step == 1:
    # 1. 상단 헤더 (글자 크게)
    st.markdown("<h2 style='text-align: center;'>📂 1단계: 도면 데이터 분석</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>변환할 DXF 파일을 업로드하고 분석할 레이어를 선택하세요.</p>", unsafe_allow_html=True)
    st.write(" ")

    # --- [추가] 파일 업로드 전 하이라이트 안내 ---
    if 'file_uploaded' not in st.session_state:
        st.session_state['file_uploaded'] = False

    if not st.session_state['file_uploaded']:
        st.markdown("""
            <div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 5px solid #ffc107; margin-bottom: 10px;">
                <span style="color: #856404; font-weight: bold;">📢 먼저 캐드 파일(.dxf)을 입력해 주세요.</span>
            </div>
        """, unsafe_allow_html=True)

    # 2. 파일 업로드 영역
    uploaded_file = st.file_uploader("", type=['dxf'])
    st.markdown("---")

    if uploaded_file:
        st.session_state['file_uploaded'] = True # 업로드 상태 기록
        try:
            # --- [중요] doc 정의 및 파일 로드 로직 ---
            file_bytes = uploaded_file.getvalue()
            raw_data = io.BytesIO(file_bytes)
            doc = None
            
            # 인코딩 시도 (한글 깨짐 방지)
            for enc in ['cp949', 'utf-8', 'latin1']:
                try:
                    raw_data.seek(0)
                    text_stream = io.TextIOWrapper(raw_data, encoding=enc, errors='ignore')
                    doc = ezdxf.read(text_stream)
                    if doc: break
                except: continue

            if doc:
                layers = sorted([layer.dxf.name for layer in doc.layers])
                
                # --- 화면 분할 (좌측: 설정 및 유형 / 우측: 미리보기) ---
                col_sidebar, col_main = st.columns([1, 2.5], gap="large")

                # [좌측 영역: 도면 설정 및 유형 확인]
                with col_sidebar:
                    # --- 1-1. 도면 설정 영역 (생략 없이 유지) ---
                    st.subheader("📍 1-1. 도면 설정")
                    st.markdown("""
                        <div style="background-color: #e8f0fe; padding: 10px; border-radius: 5px; border: 1px solid #4285f4; margin-bottom: 5px;">
                            <span style="color: #1967d2; font-size: 0.85rem; font-weight: bold;">👉 분석할 도면층을 선택하세요</span>
                        </div>
                    """, unsafe_allow_html=True)

                    with st.container(border=True):
                        selected_layer = st.selectbox("레이어 선택", layers, label_visibility="collapsed")
                        st.caption("주의: 하나에 레이어에는 하나의 객체 유형만 권장합니다.")

                    st.markdown("<div style='margin-bottom: 40px;'></div>", unsafe_allow_html=True)

                    # --- 1-2. 유형 확인 영역 ---
                    st.subheader("🔍 1-2. 유형 확인")
                    st.markdown("<span style='color: #d32f2f; font-size: 0.8rem; font-weight: bold;'>* 필수: 객체 변환 방식을 하나 선택하세요.</span>", unsafe_allow_html=True)
                    
                    # 3단계에서 참조할 변수 초기화
                    st.session_state['selected_conversion'] = None

                    with st.container(border=True):
                        msp = doc.modelspace()
                        entities = msp.query(f'*[layer=="{selected_layer}"]')
                        
                        line_types = ['LINE', 'LWPOLYLINE', 'POLYLINE']
                        line_count = len([e for e in entities if e.dxftype() in line_types])
                        point_count = len([e for e in entities if e.dxftype() == 'POINT'])
                        
                        if line_count > 0 and point_count == 0:
                            st.success(f"📏 유형: 라인 ({line_count}개의 객체)")
                            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                            # 라디오 버튼을 사용하여 '하나만' 선택 강제
                            choice = st.radio(
                                "변환 방식 선택",
                                ["선택 안함", "ⓐ 영역을 폴리곤으로 변환", "ⓑ 라인을 버퍼 적용"],
                                index=0,
                                label_visibility="collapsed"
                            )
                            if choice != "선택 안함":
                                st.session_state['selected_conversion'] = choice

                        elif point_count > 0 and line_count == 0:
                            st.info(f"📍 유형: 포인트 ({point_count}개의 객체)")
                            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                            choice = st.radio(
                                "변환 방식 선택",
                                ["선택 안함", "ⓒ 포인트-라인-폴리곤 변환", "ⓓ 포인트를 폴리곤으로 선택"],
                                index=0,
                                label_visibility="collapsed"
                            )
                            if choice != "선택 안함":
                                st.session_state['selected_conversion'] = choice

                        elif line_count > 0 and point_count > 0:
                            st.warning(f"⚠️ 유형: 복합 ({line_count + point_count}개)")
                            st.error("❗ 하나의 유형으로 변환 후 다시 실행하세요.")
                            
                        else:
                            st.error("데이터가 존재하지 않습니다.")

                # [우측 영역: 도면층 미리보기 - 로직 최적화]
                with col_main:
                    st.subheader("🖼️ 1-3. 도면층 미리보기")
                    
                    with st.container(border=True):
                        render_data = []
                        # 현재 선택된 레이어의 엔티티 재추출
                        msp = doc.modelspace()
                        current_entities = msp.query(f'*[layer=="{selected_layer}"]')
                        
                        for e in current_entities:
                            try:
                                etype = e.dxftype()
                                pts = []
                                if etype == 'LINE':
                                    pts = [{"x": float(e.dxf.start.x), "y": float(e.dxf.start.y)}, 
                                        {"x": float(e.dxf.end.x), "y": float(e.dxf.end.y)}]
                                    render_data.append({"type": "line", "points": pts})
                                
                                elif etype in ['LWPOLYLINE', 'POLYLINE']:
                                    pts = [{"x": float(p[0]), "y": float(p[1])} for p in e.get_points()]
                                    render_data.append({"type": "line", "points": pts})
                                
                                elif etype == 'POINT':
                                    pts = [{"x": float(e.dxf.location.x), "y": float(e.dxf.location.y)}]
                                    render_data.append({"type": "point", "points": pts})
                            except Exception:
                                continue

                        if render_data:
                            # 세션 업데이트
                            st.session_state['final_render_data'] = render_data
                            
                            # 캔버스 렌더링
                            render_json = json.dumps(render_data)
                            render_dxf_canvas(render_json)
                            
                            st.markdown(f"<p style='text-align: center; font-size: 0.8rem; color: gray;'>현재 <b>{selected_layer}</b> 레이어 표시 중</p>", unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ 선택한 레이어에 시각화 가능한 데이터(Line, Polyline, Point)가 없습니다.")

            else:
                st.error("❌ DXF 파일을 읽을 수 없습니다. (2007 버전 이하 권장)")
        
        except Exception as e:
            st.error(f"❌ 파일 분석 중 오류 발생: {e}")
    else:
        st.session_state['file_uploaded'] = False

    # --- 하단 내비게이션 영역 ---
    st.write(" ")
    nav_c1, nav_c2 = st.columns([1, 1])
    with nav_c2:
        if st.button("다음 단계(좌표 설정) ▶", use_container_width=True, type="primary"):
            if not uploaded_file:
                st.warning("⚠️ 파일을 먼저 업로드하세요.")
            elif not st.session_state.get('selected_conversion'):
                st.warning("⚠️ 변환 방식(ⓐ~ⓓ) 중 하나를 반드시 선택해야 합니다.")
            else:
                # 선택된 값을 세션에 확실히 저장 후 이동
                st.session_state.current_step = 2
                st.rerun()

# [단계 2: 좌표 설정 - 9개 PRJ 데이터 및 요청 매핑 반영]
elif st.session_state.current_step == 2:
    st.markdown("<h2 style='text-align: center;'>🌐 2단계: 좌표계 설정 및 가이드</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>업로드된 9개의 PRJ 데이터와 매핑된 가이드를 제공합니다.</p>", unsafe_allow_html=True)
    st.write(" ")

    # 1. 이미지 분석 기반 지역 매핑 가이드 (9개 파일 기준)
    st.markdown("### 📍 지역별 좌표계 선택 가이드")
    guide_data = [
        {"구분": "서부원점 (West)", "해당 지역": "강화, 인천, 전남 섬 지역 등", "추천 EPSG": "5185 / 5173"},
        {"구분": "중부원점 (Central)", "해당 지역": "서울, 경기, 충청, 전라 지역", "추천 EPSG": "5186 / 5174"},
        {"구분": "동부원점 (East)", "해당 지역": "강원, 경상 지역", "추천 EPSG": "5187 / 5175"},
        {"구분": "제주원점 (Jeju)", "해당 지역": "제주도 및 인근 도서", "추천 EPSG": "5176"},
        {"구분": "동해원점 (East Sea)", "해당 지역": "울릉도, 독도", "추천 EPSG": "5188"},
        {"구분": "대한민국 전역", "해당 지역": "네이버/카카오 지도, 도로명주소", "추천 EPSG": "5179"},
    ]
    st.table(guide_data)
    
    st.write(" ")
    st.markdown("---")
    
    # 2. 좌표계 선택창 (9개 .prj 파일 실제 WKT 매핑)
    st.subheader("⚙️ 좌표계 최종 선택")
    
    # 업로드된 9개 파일의 실제 WKT 데이터 매핑
    coord_options = {
        "EPSG:5186 (GRS80 중부원점 2010)": {"epsg": 5186, "wkt": 'PROJCS["KGD2002_Central_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",127.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5174 (Bessel 중부원점)": {"epsg": 5174, "wkt": 'PROJCS["Korean_1985_Modified_Korea_Central_Belt",GEOGCS["GCS_Korean_Datum_1985",DATUM["D_Korean_Datum_1985",SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",500000.0],PARAMETER["Central_Meridian",127.002890277778],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5173 (Bessel 서부원점)": {"epsg": 5173, "wkt": 'PROJCS["Korean_1985_Modified_Korea_West_Belt",GEOGCS["GCS_Korean_Datum_1985",DATUM["D_Korean_Datum_1985",SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",500000.0],PARAMETER["Central_Meridian",125.002890277778],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5175 (Bessel 동부원점)": {"epsg": 5175, "wkt": 'PROJCS["Korean_1985_Modified_Korea_Central_Belt_Jeju",GEOGCS["GCS_Korean_Datum_1985",DATUM["D_Korean_Datum_1985",SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",550000.0],PARAMETER["Central_Meridian",127.002890277778],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5176 (Bessel 제주원점)": {"epsg": 5176, "wkt": 'PROJCS["Korean_1985_Modified_Korea_East_Belt",GEOGCS["GCS_Korean_Datum_1985",DATUM["D_Korean_Datum_1985",SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",500000.0],PARAMETER["Central_Meridian",129.002890277778],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5179 (GRS80 UTM-K 전역)": {"epsg": 5179, "wkt": 'PROJCS["KGD2002_Unified_Coordinate_System",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",1000000.0],PARAMETER["False_Northing",2000000.0],PARAMETER["Central_Meridian",127.5],PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5185 (GRS80 서부원점 2010)": {"epsg": 5185, "wkt": 'PROJCS["KGD2002_West_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",125.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5187 (GRS80 동부원점 2010)": {"epsg": 5187, "wkt": 'PROJCS["KGD2002_East_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",129.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'},
        "EPSG:5188 (GRS80 동해원점 2010)": {"epsg": 5188, "wkt": 'PROJCS["KGD2002_East_Sea_Belt_2010",GEOGCS["GCS_KGD2002",DATUM["D_Korea_Geodetic_Datum_2002",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",131.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]'}
    }
    
    with st.container(border=True):
        selected_coord_key = st.selectbox("가이드 표를 참고하여 좌표계를 선택하세요.", options=list(coord_options.keys()))
        # 세션 스테이트에 선택된 데이터 저장
        st.session_state.selected_epsg = coord_options[selected_coord_key]["epsg"]
        st.session_state.selected_wkt = coord_options[selected_coord_key]["wkt"]
        st.success(f"✅ 설정 완료: **{selected_coord_key}**")

    # 3. 하단 네비게이션
    st.write(" ")
    nav_c1, nav_c2 = st.columns([1, 1])
    with nav_c1:
        if st.button("◀ 이전 단계", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
    with nav_c2:
        if st.button("다음 단계 ▶", use_container_width=True, type="primary"):
            st.session_state.current_step = 3
            st.rerun()

# [단계 3: 지도 오버레이 및 편집]
# [단계 3: 지도 오버레이 및 편집]
elif st.session_state.current_step == 3:
    st.subheader("🛠️ 3단계: 메뉴별 객체 변환 및 배경지도 오버레이")
    
    # 1단계에서 저장한 선택 값 가져오기
    conversion_method = st.session_state.get('selected_conversion', None)

    # --- [필터링 로직] 선택된 유형에 맞는 메뉴 하나만 노출 ---
    
    # ⓐ 유형 선택 시 -> 3.1 라인(폐합) 변환만 활성화
    # ⓐ 유형 선택 시 -> 3.1 라인(폐합) 변환만 활성화
    if conversion_method == "ⓐ 영역을 폴리곤으로 변환":
        st.info("💡 1단계 선택: ⓐ 영역을 폴리곤으로 변환 (3.1 메뉴)")
        
        # --- 세션 상태 초기화 (버튼 색상 및 사이드바 알림용) ---
        if 'btn_3_1_converted' not in st.session_state:
            st.session_state.btn_3_1_converted = False
        if 'btn_3_1_downloaded' not in st.session_state:
            st.session_state.btn_3_1_downloaded = False

        # --- 작업 완료 시 사이드바 메시지 출력 ---
        if st.session_state.btn_3_1_downloaded:
            st.sidebar.success("✅ 3.1 작업 완료")
        # --------------------------------------------------

        st.markdown("### 📐 3.1 폐합된 라인 -> 폴리곤(면) 변환")
        
        # [1단계: 변환 실행 버튼]
        conv_btn_type = "secondary" if st.session_state.btn_3_1_converted else "primary"
        
        # 하단 다운로드 버튼과 크기를 맞추기 위해 3분할 컬럼의 중앙 배치
        _, col_conv, _ = st.columns([1, 1, 1])
        with col_conv:
            if st.button("🔍 폐합 라인 자동 검색 및 변환", key="btn_3_1_main", use_container_width=True, type=conv_btn_type):
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
                            closed_pts[-1] = {"x": p1['x'], "y": p1['y']} 
                            polygons.append({"type": "polygon", "points": closed_pts, "layer": "Converted_Area"})
                            closed_count += 1
                            continue 
                    remaining_lines.append(ent)
                
                st.session_state['converted_polygons'] = polygons
                st.session_state['road_lines'] = remaining_lines 
                st.session_state.btn_3_1_converted = True
                st.success(f"✅ 분석 완료: {closed_count}개 폴리곤 변환")
                st.rerun()

        # [2단계: 결과물 저장 섹션]
        if st.session_state.get('converted_polygons'):
            st.divider() 
            st.markdown("#### 📥 결과물 저장")
            
            # SHP 파일 생성 로직 (기존과 동일)
            zip_buffer_poly = io.BytesIO()
            with zipfile.ZipFile(zip_buffer_poly, "w") as zf:
                shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
                with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
                    w.field("LAYER", "C", "40")
                    for poly in st.session_state['converted_polygons']:
                        w.poly([[[p['x'], p['y']] for p in poly['points']]]) 
                        w.record(poly['layer'])
                
                zf.writestr("converted_area.shp", shp_io.getvalue())
                zf.writestr("converted_area.shx", shx_io.getvalue())
                zf.writestr("converted_area.dbf", dbf_io.getvalue())
                zf.writestr("converted_area.prj", st.session_state.get('selected_wkt', ''))
            
            # [다운로드 버튼] 색상 변경 및 중앙 배치
            dl_btn_type = "secondary" if st.session_state.btn_3_1_downloaded else "primary"
            _, col_dl, _ = st.columns([1, 1, 1]) 
            
            with col_dl:
                if st.download_button(
                    label="📦 폴리곤 SHP 내려받기",
                    data=zip_buffer_poly.getvalue(),
                    file_name="converted_polygons.zip",
                    mime="application/zip",
                    key="poly_3_1_download_trigger",
                    use_container_width=True,
                    type=dl_btn_type
                ):
                    st.session_state.btn_3_1_downloaded = True
                    st.rerun()
        # --- 3.1 내용 끝 ---

    # ⓑ 유형 선택 시 -> 3.2 라인(도로) 변환만 활성화
    elif conversion_method == "ⓑ 라인을 버퍼 적용":
        st.info("💡 1단계 선택: ⓑ 라인을 버퍼 적용 (3.2 메뉴)")
        
        if 'btn_3_2_converted' not in st.session_state: st.session_state.btn_3_2_converted = False
        if 'btn_3_2_done' not in st.session_state: st.session_state.btn_3_2_done = False

        st.markdown("### 🛣️ 3.2 라인(도로) 버퍼 변환")
        
        # 데이터 추출
        road_data = st.session_state.get('road_lines', [])
        if not road_data:
            road_data = [ent for ent in st.session_state.get('final_render_data', []) if ent['type'] == 'line']

        if not road_data:
            st.info("ℹ️ 변환할 라인 데이터가 없습니다.")
        else:
            # [Step 1] 거리 입력 및 적용 버튼 (화면 중앙)
            _, col_center, _ = st.columns([1, 1.2, 1])
            with col_center:
                buffer_dist = st.number_input("📏 버퍼 거리 입력 (m)", min_value=0.1, value=1.0, step=0.5)
                confirm_btn_type = "secondary" if st.session_state.btn_3_2_converted else "primary"
                
                if st.button("🛠️ 버퍼 적용 및 데이터 확정", key="btn_3_2_confirm", use_container_width=True, type=confirm_btn_type):
                    buffer_polygons = []
                    for line in road_data:
                        # ... (버퍼 계산 로직 생략: 기존과 동일) ...
                        pts = line['points']
                        if len(pts) < 2: continue
                        left_side, right_side = [], []
                        for i in range(len(pts)):
                            p1, p2, p0 = pts[i], pts[i+1] if i < len(pts)-1 else pts[i], pts[i-1] if i > 0 else pts[i]
                            c_x, c_y = (p1['x'], p1['y']) if isinstance(p1, dict) else (p1[0], p1[1])
                            n_x, n_y = (p2['x'], p2['y']) if isinstance(p2, dict) else (p2[0], p2[1])
                            p_x, p_y = (p0['x'], p0['y']) if isinstance(p0, dict) else (p0[0], p0[1])
                            dx, dy = n_x - p_x, n_y - p_y
                            length = math.sqrt(dx**2 + dy**2)
                            if length == 0: continue
                            nx, ny = -dy/length * buffer_dist, dx/length * buffer_dist
                            left_side.append([c_x + nx, c_y + ny]); right_side.insert(0, [c_x - nx, c_y - ny])
                        poly_pts = left_side + right_side + [left_side[0]]
                        buffer_polygons.append({"points": poly_pts})
                    
                    st.session_state['road_buffer_polygons'] = buffer_polygons
                    st.session_state.btn_3_2_converted = True
                    st.success(f"✅ {len(buffer_polygons)}개의 도로 객체 변환 완료!")
                    st.rerun()

            # [Step 2] 결과가 있을 때만 다운로드 버튼 표시
            if st.session_state.get('road_buffer_polygons'):
                st.divider()
                st.markdown("#### 📥 결과물 저장")
                
                # 파일 생성 (한 번만 수행)
                zip_buffer_road = io.BytesIO()
                with zipfile.ZipFile(zip_buffer_road, "w") as zf:
                    shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
                    with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
                        w.field("LAYER", "C", "40"); w.field("BUF_DIST", "F", 10, 2)
                        for poly in st.session_state['road_buffer_polygons']:
                            w.poly([poly['points']]); w.record("Road_Buffer", buffer_dist)
                    zf.writestr("road_buffer.shp", shp_io.getvalue())
                    zf.writestr("road_buffer.shx", shx_io.getvalue())
                    zf.writestr("road_buffer.dbf", dbf_io.getvalue())
                    zf.writestr("road_buffer.prj", st.session_state.get('selected_wkt', ''))

                # 다운로드 버튼 중앙 정렬
                _, col_dl, _ = st.columns([1, 1.2, 1])
                with col_dl:
                    dl_type = "secondary" if st.session_state.btn_3_2_done else "primary"
                    st.download_button(
                        label="📦 변환된 도로 SHP(ZIP) 내려받기",
                        data=zip_buffer_road.getvalue(),
                        file_name="road_buffer_result.zip",
                        mime="application/zip",
                        key="road_buffer_final_dl",
                        on_click=lambda: st.session_state.update({"btn_3_2_done": True}),
                        use_container_width=True,
                        type=dl_type
                    )
        # --- 3.2 내용 끝 ---

    # ⓓ 유형 선택 시 -> 3.3 포인트(전주) 변환만 활성화
    elif conversion_method == "ⓓ 포인트를 폴리곤으로 선택":
        st.info("💡 1단계 선택: ⓓ 포인트를 폴리곤으로 선택 (3.3 메뉴)")
        # --- 3.3 탭 내용 시작 (기존 소스 유지) ---
        st.markdown("### 📍 3.3 포인트(전주) 변환")
        all_data = st.session_state.get('final_render_data', [])
        point_data = [ent for ent in all_data if ent['type'] == 'point']
        
        if not point_data:
            st.info("ℹ️ 현재 레이어에 포인트(점) 데이터가 없습니다.")
        else:
            pole_radius = st.number_input("전주 심볼 반경 (m)", min_value=0.1, value=0.5, step=0.1)
            # ... 3.3단계 버튼 로직 부분 ...
            if st.button("🔌 전주 객체 변환", key="btn_3_3_convert"):
                pole_polygons = []
                for p_ent in point_data:
                    center = p_ent['points'][0]
                    cx, cy = center['x'], center['y']
                    
                    # 8각형 폴리곤 좌표 생성
                    sides = 8 
                    poly_pts = []
                    for i in range(sides):
                        angle = math.radians(i * (360 / sides))
                        px = cx + pole_radius * math.cos(angle)
                        py = cy + pole_radius * math.sin(angle)
                        poly_pts.append([px, py])
                    poly_pts.append(poly_pts[0]) # 닫힌 폴리곤
                    
                    # 1. 시각화를 위해 final_render_data 형식에 맞춰 추가 (이게 핵심!)
                    st.session_state.final_render_data.append({
                        'type': 'polygon',
                        'points': [{'x': p[0], 'y': p[1]} for p in poly_pts],
                        'properties': {'layer': 'Converted_Pole', 'color': 'red'} 
                    })
                    
                    # 2. SHP 다운로드를 위한 기존 데이터 저장
                    pole_polygons.append({"points": poly_pts, "center": [cx, cy]})

                st.session_state['pole_polygons'] = pole_polygons
                st.success(f"✅ {len(pole_polygons)}개의 전주 객체 변환 및 지도 반영 완료!")
                st.rerun()
        # --- 3.3 내용 끝 ---

    # ⓒ 유형 선택 시 -> 3.4 포인트(측량) 변환만 활성화
    # ⓒ 유형 선택 시 -> 3.4 포인트(측량) 변환만 활성화
    elif conversion_method == "ⓒ 포인트-라인-폴리곤 변환":
        st.info("💡 1단계 선택: ⓒ 포인트-라인-폴리곤 변환 (3.4 메뉴)")
        
        st.markdown("### 📐 3.4 포인트(측량) 단계별 변환")
        
        # 데이터 유무 확인
        survey_pts = [e for e in st.session_state.get('final_render_data', []) if e['type'] == 'point']
        
        if not survey_pts: 
            st.info("ℹ️ 변환할 포인트 데이터가 없습니다.")
        else:
            # 상태 변수 확인
            is_line_done = 'survey_step_line' in st.session_state
            is_poly_done = 'survey_step_poly' in st.session_state

            # --- 버튼 레이아웃 (가운데 정렬: 1:1.2:1 비율) ---
            _, col_center, _ = st.columns([1, 1.2, 1])

            with col_center:
                is_closed = st.checkbox("시점-종점 연결(폐합)", value=True)
                
                # [1단계 버튼] 실행 전(primary-붉은색조), 실행 후(secondary-회색조)
                line_btn_label = "✅ 1단계: 라인 변환 완료" if is_line_done else "🛣️ 1단계: 포인트 → 라인 변환"
                line_btn_type = "secondary" if is_line_done else "primary"
                
                if st.button(line_btn_label, key="btn_3_4_step1", use_container_width=True, type=line_btn_type):
                    line_coords = [[p['points'][0]['x'], p['points'][0]['y']] for p in survey_pts]
                    if is_closed and len(line_coords) > 2: 
                        line_coords.append(line_coords[0])
                    st.session_state['survey_step_line'] = line_coords
                    st.success("✅ 라인 생성 완료 (하단 지도 주황색 확인)")
                    st.rerun()

                st.write("") # 간격

                # [2단계 버튼] 1단계가 완료되었을 때만 강조(primary)
                poly_btn_label = "✅ 2단계: 폴리곤 확정 완료" if is_poly_done else "🟦 2단계: 라인 → 폴리곤 변환"
                poly_btn_type = "primary" if (is_line_done and not is_poly_done) else "secondary"
                
                if st.button(poly_btn_label, key="btn_3_4_step2", use_container_width=True, type=poly_btn_type):
                    if is_line_done:
                        st.session_state['survey_step_poly'] = [{"points": st.session_state['survey_step_line']}]
                        st.success("✅ 폴리곤 확정 완료 (하단 지도 보라색 확인)")
                        st.rerun()
                    else:
                        st.warning("먼저 1단계 라인 변환을 실행해 주세요.")

            # --- 3단계 결과물 내보내기 (폴리곤이 확정된 경우에만 표시) ---
            if is_poly_done:
                st.divider()
                st.markdown("<h4 style='text-align: center;'>📥 3단계: 결과물 내보내기</h4>", unsafe_allow_html=True)
                
                _, col_dl, _ = st.columns([1, 1.2, 1])
                with col_dl:
                    zip_survey_io = io.BytesIO()
                    with zipfile.ZipFile(zip_survey_io, "w") as zf:
                        shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
                        with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
                            w.field("NAME", "C", "40")
                            for poly in st.session_state['survey_step_poly']:
                                w.poly([poly['points']])
                                w.record("Survey_Area")
                        
                        zf.writestr("survey_area.shp", shp_io.getvalue())
                        zf.writestr("survey_area.shx", shx_io.getvalue())
                        zf.writestr("survey_area.dbf", dbf_io.getvalue())
                        zf.writestr("survey_area.prj", st.session_state.get('selected_wkt', ''))
                    
                    st.download_button(
                        label="📦 측량 폴리곤 SHP(ZIP) 내려받기",
                        data=zip_survey_io.getvalue(),
                        file_name="survey_polygon_result.zip",
                        mime="application/zip",
                        use_container_width=True,
                        type="primary" # 최종 버튼은 다시 강조
                    )
    
    # --- 5. 편집 및 공통 지도 미리보기 영역 (모든 유형 공통 노출) ---
    # --- [수정] 중복된 '5. 편집' 섹션 제거 및 지도 영역 통합 ---
    
    # --- [수정] 3단계 하단부: 저장 섹션 상단 이동 및 분할 지도 구성 ---
    st.write(" ")
    st.markdown("---")

    # 2. 🌍 지도 상단 컨트롤 바
    m_col1, m_col2 = st.columns([4, 1])
    with m_col1:
        st.markdown("### 🌍 통합 실시간 배경 지도")
    with m_col2:
        if 'split_view' not in st.session_state:
            st.session_state.split_view = False
        if st.button("🖥️ 화면 분할 모드", use_container_width=True, type="secondary"):
            st.session_state.split_view = not st.session_state.split_view
            st.rerun()

    # 3. 지도 데이터 및 변환 로직
    # --- [수정] 지도 데이터 및 변환 로직 섹션 ---
    src_epsg = st.session_state.get('selected_epsg', 5186)
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs(f"EPSG:{src_epsg}", "EPSG:4326", always_xy=True)
        viz_features = []

        # 1. [기본 데이터] 원본 라인/포인트
        for ent in st.session_state.get('final_render_data', []):
            if ent['type'] == 'line':
                viz_features.append({"type":"line", "coordinates":[list(transformer.transform(p['x'],p['y']))[::-1] for p in ent['points']], "color":"#007bff"})
            elif ent['type'] == 'point':
                lon, lat = transformer.transform(ent['points'][0]['x'], ent['points'][0]['y'])
                viz_features.append({"type":"point", "coordinates":[lat, lon], "color":"red"})

        # 2. [변환 데이터] 3.1, 3.2 폴리곤
        for poly_key, color in [('converted_polygons', '#28a745'), ('road_buffer_polygons', '#6c757d')]:
            for poly in st.session_state.get(poly_key, []):
                pts = poly['points']
                coords = [list(transformer.transform(p['x'],p['y']))[::-1] if isinstance(p, dict) else list(transformer.transform(p[0],p[1]))[::-1] for p in pts]
                viz_features.append({"type":"polygon", "coordinates":coords, "color":color})

        # 3. [추가] 3.4 단계: 포인트 -> 라인 변환 데이터 시각화 (주황색)
        if 'survey_step_line' in st.session_state:
            line_coords = st.session_state['survey_step_line']
            # line_coords는 [[x,y], [x,y]...] 형식임
            geo_line = [list(transformer.transform(pt[0], pt[1]))[::-1] for pt in line_coords]
            viz_features.append({"type":"line", "coordinates":geo_line, "color":"#ff7f0e"}) # 주황색

        # 4. [추가] 3.4 단계: 라인 -> 폴리곤 확정 데이터 시각화 (보라색)
        if 'survey_step_poly' in st.session_state:
            for poly in st.session_state['survey_step_poly']:
                pts = poly['points']
                geo_poly = [list(transformer.transform(pt[0], pt[1]))[::-1] for pt in pts]
                viz_features.append({"type":"polygon", "coordinates":geo_poly, "color":"#9467bd"}) # 보라색

    # ... 이후 렌더링 함수 호출 부분은 동일 ...
        # 4. 리플렛 지도 렌더링 함수 (좌측: 일반, 우측: 위성)
        def create_leaflet_js(map_id, is_satellite=False):
            if is_satellite:
                tile_layer = """
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                    maxZoom: 19,
                    attribution: 'Tiles &copy; Esri'
                }).addTo(map);
                L.tileLayer('https://stamen-tiles-{s}.a.ssl.fastly.net/toner-hybrid/{z}/{x}/{y}{r}.png', { opacity: 0.5 }).addTo(map);
                """
            else:
                tile_layer = "L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);"

            return f"""
            <div id="{map_id}" style="width: 100%; height: 550px; border-radius:10px; border:1px solid #ddd; box-shadow: 0 2px 5px rgba(0,0,0,0.1);"></div>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script>
                (function() {{
                    const map = L.map('{map_id}').setView([36.5, 127.5], 16); 
                    {tile_layer}
                    const features = {json.dumps(viz_features)};
                    const group = new L.featureGroup();
                    features.forEach(f => {{
                        let layer;
                        if (f.type === 'line') layer = L.polyline(f.coordinates, {{color: f.color, weight: 3, opacity: 0.9}});
                        else if (f.type === 'polygon') layer = L.polygon(f.coordinates, {{color: f.color, fillOpacity: 0.4, weight: 2}});
                        else if (f.type === 'point') layer = L.circleMarker(f.coordinates, {{radius: 6, color: f.color, fillOpacity: 0.9}});
                        if(layer) layer.addTo(group);
                    }});
                    group.addTo(map);
                    if (features.length > 0) map.fitBounds(group.getBounds(), {{padding: [30, 30]}});
                }})();
            </script>
            """

        # 5. 화면 분할 레이아웃 출력
        leaflet_head = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />'
        
        if st.session_state.split_view:
            col_left, col_right = st.columns(2)
            with col_left:
                st.caption("🛰️ 좌측: 일반 배경 지도 (OSM)")
                components.html(leaflet_head + create_leaflet_js("map_osm", False), height=570)
            with col_right:
                st.caption("🌍 우측: 고해상도 위성 영상 (Satellite)")
                components.html(leaflet_head + create_leaflet_js("map_sat", True), height=570)
        else:
            components.html(leaflet_head + create_leaflet_js("map_full", False), height=570)

    except Exception as e:
        st.error(f"지도 생성 오류: {e}")

    # 6. 하단 버튼 (이전 단계)
    st.write(" ")
    if st.button("◀ 이전 단계(좌표 설정)"):
        st.session_state.current_step = 2
        st.rerun()