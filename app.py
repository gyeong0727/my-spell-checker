import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image
import io

# 🔑 비밀 금고에서 API 키 가져오기
try:
    MY_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=MY_API_KEY)
except Exception as e:
    st.error("🔑 설정 오류: .streamlit/secrets.toml 파일에 키가 없습니다.")
    st.stop()

model = genai.GenerativeModel('gemini-2.5-flash')

st.set_page_config(page_title="제안서 통합 검수 시스템", page_icon="🛡️", layout="wide")

st.title("🛡️ 제안서 블라인드 및 오타 검수 시스템")
st.write("단순 오타 교정은 물론, 사본 제출 시 치명적인 **블라인드 위반 요소(텍스트 및 전체 페이지 로고)**까지 완벽하게 적발합니다.")

uploaded_file = st.file_uploader("검수할 PDF 제안서 파일을 올려주세요", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 통합 검수 시작"):
        
        # [해결 1] 탭을 스피너 바깥으로 분리하여 UI를 안정화합니다.
        tab1, tab2 = st.tabs(["🚨 블라인드 위반 검증", "📊 맞춤법 & 문맥 교정"])
        
        try:
            # [해결 2] 1단계: PDF 압축 전용 스피너
            with st.spinner('📄 제안서 텍스트 추출 및 이미지를 초경량 압축하고 있습니다...'):
                file_bytes = uploaded_file.read()
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                total_pages = len(doc)
                
                full_text = ""
                images_for_ai = []
                
                forbidden_words = ["(사)한국능률협회", "KMA", "능률협회", "한국능률협회", "한국능률협회 부산경남본부"]
                found_text_violations = []
                
                for page_num in range(total_pages):
                    page = doc.load_page(page_num)
                    
                    page_text = page.get_text()
                    full_text += page_text + "\n"
                    
                    for word in forbidden_words:
                        if word in page_text and f"'{word}'" not in str(found_text_violations):
                            found_text_violations.append(f"📄 제 {page_num+1}페이지: '{word}' 문구 발견 (텍스트)")
                    
                    pix = page.get_pixmap(dpi=60)
                    img_data = pix.tobytes("png")
                    
                    img = Image.open(io.BytesIO(img_data)).convert("RGB")
                    img.thumbnail((800, 800)) 
                    images_for_ai.append(img)
            
            # ====================================================
            # 탭 1: 블라인드 위반 검증 로직
            # ====================================================
            with tab1:
                st.subheader("🕵️‍♂️ 블라인드 심사 규정 위반 검사")
                
                if found_text_violations:
                    st.error("❌ 텍스트 블라인드 위반 적발!")
                    for v in found_text_violations:
                        st.write(v)
                else:
                    st.success("✅ 텍스트 금지어 검사 통과 (위반 단어 없음)")
                
                st.divider()
                
                # [해결 3] 2단계: 탭 1(로고 검사) 전용 스피너
                with st.spinner(f"🔍 전체 {total_pages}페이지 구석구석 숨겨진 로고/마크를 시각적으로 분석 중입니다..."):
                    vision_prompt = """당신은 입찰 제안서의 블라인드 규정 위반을 잡아내는 시각 분석 검수관입니다. 
첨부된 전체 페이지 이미지 구석구석을 확인하여, '한국능률협회' 또는 'KMA'의 '그림/도형 형태의 로고, 심볼, 마크, 행사 현수막 이미지'가 존재하는지 시각적으로 찾아내세요.

[🚨 주의사항] 
1. 문서에 타이핑된 '일반 텍스트(글자)'는 절대 지적하지 마세요. 오직 '시각적인 이미지 마크나 현수막'만 찾으세요. 
2. 발견되면 몇 번째 이미지인지 보고하고, 시각적 로고가 전혀 없다면 '위반 없음'이라고 단호하게 답변해 주세요."""
                    
                    vision_contents = [vision_prompt] + images_for_ai 
                    vision_response = model.generate_content(vision_contents)
                    
                    vision_result = vision_response.text
                    
                    if "위반 없음" in vision_result or "발견되지 않았" in vision_result:
                        st.success("✅ 로고 이미지 검사 통과 (시각적 마크 발견되지 않음)")
                    else:
                        st.warning("⚠️ 이미지 형태의 로고 분석 결과 확인 필요")
                    
                    st.write(vision_result)
            
            # ====================================================
            # 탭 2: 맞춤법 및 문맥 교정 로직
            # ====================================================
            with tab2:
                st.subheader("📊 핵심 오타 및 비문 교정 리포트")
                
                # [해결 4] 3단계: 탭 2(맞춤법 검사) 전용 스피너
                with st.spinner("✍️ 치명적인 오타 및 비문을 찾아내고 있습니다... (약 10~15초 소요)"):
                    grammar_prompt = f"""당신은 공공기관 및 대기업 실무 제안서를 평가하는 최고위 심사위원입니다. 
다음 텍스트에서 '누가 보아도 의미가 왜곡될 정도로 치명적인 수준의 심각한 오타나 문법 파괴'만 찾아내어 작성해 주세요.

[🚨 제안서 특화 예외 규칙 - 아래 사항은 절대 지적 금지]
1. 제안서 특유의 강조형/슬로건 문구(예: "~를 세밀하게 실시, ~효과성 향상")는 문법적으로 다소 길거나 어색하더라도 절대 지적하지 마세요.
2. 개조식 문장(명사로 끝나는 문장)이나 불완전한 헤드라인은 오류가 아니므로 100% 무시하세요.
3. 띄어쓰기 오류는 무조건 무시하세요.
4. 오타는 명확하게 잡아주세요. 예를 들면 "사전진단"인데 "사적진단"으로 되어있는 것요.

[🚨 가독성 및 속도 향상을 위한 출력 규칙]
1. 결과는 반드시 가독성이 좋은 **마크다운 표(Table)** 형식으로만 정렬하여 출력하세요. 
   (양식: | 번호 | 기존 문장 | 수정된 문장 | 교정 사유 |)
2. 사소한 것은 다 넘어가고, 평가에 치명적인 '진짜 찐 오류'만 최대 5~7개 이내로 아주 짧게 요약해서 출력하세요. 
3. 치명적인 오류가 없다면 억지로 지어내지 말고, 단호하게 '✅ 치명적인 오타 및 오류가 발견되지 않았습니다'라고만 출력하세요.

[제안서 내용]
{full_text[:40000]}"""
                    
                    grammar_response = model.generate_content(grammar_prompt)
                    
                    st.write(grammar_response.text)
                    st.success("✅ 맞춤법 및 문맥 핵심 검사 완료!")
                    
        except Exception as e:
            st.error(f"실행 중 오류가 발생했습니다: {e}")
