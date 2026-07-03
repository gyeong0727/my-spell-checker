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

# 똑똑한 최신 제미나이 모델 설정
model = genai.GenerativeModel('gemini-2.5-flash')

# [화면 설정]
st.set_page_config(page_title="제안서 통합 검수 시스템", page_icon="🛡️", layout="wide")

st.title("🛡️ 제안서 블라인드 및 오타 검수 시스템")
st.write("단순 오타 교정은 물론, 사본 제출 시 치명적인 **블라인드 위반 요소(텍스트 및 로고 이미지)**까지 완벽하게 적발합니다.")

uploaded_file = st.file_uploader("검수할 PDF 제안서 파일을 올려주세요", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 통합 검수 시작"):
        
        tab1, tab2 = st.tabs(["🚨 블라인드 위반 검증", "📊 맞춤법 & 문맥 교정"])
        
        with st.spinner('제미나이가 제안서를 열심히 스캔하고 있습니다. 잠시만 기다려주세요...'):
            try:
                # PDF 파일 읽기
                file_bytes = uploaded_file.read()
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                total_pages = len(doc)
                
                full_text = ""
                images_for_ai = []
                
                # [적발 대상 금지어 목록 설정]
                forbidden_words = ["(사)한국능률협회", "KMA", "능률협회", "한국능률협회", "한국능률협회 부산경남본부"]
                found_text_violations = []
                
                # 1. PDF 데이터 추출 및 이미지 변환
                for page_num in range(total_pages):
                    page = doc.load_page(page_num)
                    
                    page_text = page.get_text()
                    full_text += page_text + "\n"
                    
                    # 텍스트 검출 로직
                    for word in forbidden_words:
                        if word in page_text and f"'{word}'" not in str(found_text_violations):
                            found_text_violations.append(f"📄 제 {page_num+1}페이지: '{word}' 문구 발견 (텍스트)")
                    
                    # 이미지 스캔 가속화 (앞 3장, 뒤 2장) & 해상도 최적화(90)
                    if page_num < 3 or page_num >= (total_pages - 2):
                        pix = page.get_pixmap(dpi=90)
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
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
                    
                    st.info("🔍 제미나이가 표지 및 주요 페이지의 시각적 '로고/마크'를 분석 중입니다...")
                    
                    # [해결 1] 이미지 검사에서는 '텍스트'를 무시하도록 프롬프트 수정
                    vision_prompt = """당신은 입찰 제안서의 블라인드 규정 위반을 잡아내는 시각 분석 검수관입니다. 
첨부된 이미지에서 '한국능률협회' 또는 'KMA'의 '그림/도형 형태의 로고, 심볼, 마크, 배경 워터마크'가 존재하는지만 시각적으로 확인하세요.

[🚨 주의사항] 
1. 문서에 타이핑된 '일반 텍스트(글자)'는 절대 지적하지 마세요. 텍스트 중복 검출을 방지해야 합니다. 
2. 오직 '시각적인 이미지 로고'만 찾으세요. 발견되면 페이지와 내용을 보고하고, 로고 이미지가 없다면 '위반 없음'이라고 단호하게 답변해 주세요."""
                    
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
                    st.subheader("📊 오타 및 문맥 비문 교정 리포트")
                    
                    # [해결 2] 띄어쓰기 지적을 원천 차단하고 오타와 비문만 잡도록 프롬프트 수정
                    grammar_prompt = f"""당신은 제안서를 검수하는 엄격한 교정 전문가입니다. 
다음 텍스트에서 '실제로 존재하는' 명백한 오타(철자 틀림)와 문맥상 어색한 비문만 찾아내어 [기존 문장 -> 수정된 문장 (이유)] 형태로 리포트를 작성해 주세요.

[🚨 절대 엄수 사항 - 위반 시 감점]
1. 띄어쓰기 오류는 절대 지적하지 마세요. (띄어쓰기 관련 지적은 100% 무시할 것)
2. 오직 단어의 철자가 틀린 '오타'와 말이 안 되는 '비문'만 찾으세요.
3. '기존 문장'은 원본 텍스트에서 그대로 복사해야 하며, 억지로 오류를 지어내지 마세요. 수정할 오타가 없다면 '수정할 사항이 없습니다'라고만 하세요.

[제안서 내용]
{full_text[:40000]}"""
                    
                    grammar_response = model.generate_content(grammar_prompt)
                    
                    st.write(grammar_response.text)
                    st.success("✅ 맞춤법 및 문맥 검사 완료!")
                    
            except Exception as e:
                st.error(f"실행 중 오류가 발생했습니다: {e}")
