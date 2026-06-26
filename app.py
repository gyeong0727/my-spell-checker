import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image
import io

# =================================================================
# 🔑 [보안 업그레이드] 코드에서 진짜 키를 지우고, 스트림릿 금고에서 불러옵니다.
# =================================================================
try:
    MY_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=MY_API_KEY)
except Exception as e:
    st.error("🔑 스트림릿 설정(Secrets)에 'GEMINI_API_KEY'가 등록되지 않았습니다. 관리자 설정을 확인해 주세요.")
    st.stop()

# 최신 무료 모델 설정
model = genai.GenerativeModel('gemini-2.5-flash')

# [화면 설정]
st.set_page_config(page_title="제안서 통합 검수 시스템", page_icon="🛡️", layout="wide")

st.title("🛡️ 제안서 블라인드 및 오타 검수 시스템 (공유용 버전)")
st.write("단순 오타 교정은 물론, 블라인드 위반 요소(텍스트 및 로고 이미지)까지 완벽하게 적발합니다.")

uploaded_file = st.file_uploader("검수할 PDF 제안서 파일을 올려주세요", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 통합 검수 시작"):
        
        tab1, tab2 = st.tabs(["🚨 ... 블라인드 위반 검증", "📊 맞춤법 & 문맥 교정"])
        
        with st.spinner('제미나이가 제안서를 열심히 스캔하고 있습니다. 잠시만 기다려주세요...'):
            try:
                file_bytes = uploaded_file.read()
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                
                full_text = ""
                images_for_ai = []
                
                forbidden_words = ["(사)한국능률협회", "KMA", "능률협회", "한국능률협회"]
                found_text_violations = []
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    full_text += page_text + "\n"
                    
                    for word in forbidden_words:
                        if word in page_text and f"'{word}'" not in str(found_text_violations):
                            found_text_violations.append(f"📄 제 {page_num+1}페이지: '{word}' 문구 발견")
                    
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    images_for_ai.append(img)
                
                # --- 탭 1: 블라인드 검증 ---
                with tab1:
                    st.subheader("🕵️‍♂️ 블라인드 심사 규정 위반 검사")
                    if found_text_violations:
                        st.error("❌ 텍스트 감점 요인 적발!")
                        for v in found_text_violations:
                            st.write(v)
                    else:
                        st.success("✅ 텍스트 금지어 검사 통과 (금지 단어가 발견되지 않았습니다.)")
                    
                    st.divider()
                    st.info("🔍 제미나이가 제안서 내 포함된 심볼과 로고를 시각적으로 스캔하고 있습니다...")
                    
                    vision_prompt = "당신은 입찰 제안서의 블라인드 규정 위반을 잡아내는 엄격한 전문 검수관입니다. 첨부된 제안서 이미지들을 확인하고, '한국능률협회' 또는 'KMA'와 관련된 로고, 심볼, 마크, 배지, 혹은 배경 워터마크가 발견되면 몇 페이지에 어떤 형태로 있는지 보고해 주세요. 없다면 '위반 없음'이라고 단호하게 답변해 주세요."
                    
                    vision_contents = [vision_prompt] + images_for_ai[:10]
                    vision_response = model.generate_content(vision_contents)
                    vision_result = vision_response.text
                    
                    if "위반 없음" in vision_result or "발견되지 않았" in vision_result:
                        st.success("✅ 로고 이미지 검사 통과 (기관 로고 및 마크가 시각적으로 발견되지 않았습니다.)")
                    else:
                        st.warning("⚠️ 로고 이미지 분석 결과 확인 필요")
                    st.write(vision_result)
                
                # --- 탭 2: 맞춤법 교정 ---
                with tab2:
                    st.subheader("📊 오타 및 문맥 비문 교정 리포트")
                    grammar_prompt = f"당신은 정부 부처 및 대기업 교육 제안서를 검수하는 전문 교정 교열 전문가입니다. 다음 텍스트에서 오타, 맞춤법 오류, 문맥상 어색한 비문을 찾아내어 [기존 문장 -> 수정된 문장 (이유)] 형태로 깔끔하게 리포트를 작성해 주세요.\n\n[제안서 내용]\n{full_text[:40000]}"
                    grammar_response = model.generate_content(grammar_prompt)
                    st.write(grammar_response.text)
                    st.success("✅ 맞춤법 및 문맥 검사 완료!")
                    
            except Exception as e:
                st.error(f"실행 중 오류가 발생했습니다: {e}")