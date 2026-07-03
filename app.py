import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image
import io
import concurrent.futures
import time # 진행률 바를 위한 시간 모듈

# 🔑 비밀 금고에서 API 키 가져오기
try:
    MY_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=MY_API_KEY)
except Exception as e:
    st.error("🔑 설정 오류: .streamlit/secrets.toml 파일에 키가 없습니다.")
    st.stop()

# 똑똑한 최신 제미나이 모델 설정
model = genai.GenerativeModel('gemini-2.5-flash')

# ⚡ [가속 비기 1] AI의 답변 길이를 강제로 제한하여 타이핑 속도 2배 향상
fast_config = genai.types.GenerationConfig(max_output_tokens=500)

st.set_page_config(page_title="제안서 통합 검수 시스템", page_icon="🛡️", layout="wide")

st.title("🛡️ 제안서 블라인드 및 오타 검수 시스템 (초고속 엔진 🚀)")
st.write("단순 오타 교정은 물론, 사본 제출 시 치명적인 **블라인드 위반 요소**까지 완벽하게 적발합니다.")

uploaded_file = st.file_uploader("검수할 PDF 제안서 파일을 올려주세요", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 통합 검수 시작"):
        
        tab1, tab2 = st.tabs(["🚨 블라인드 위반 검증", "📊 맞춤법 & 문맥 교정"])
        
        try:
            # ⚡ [가속 비기 3] 답답함을 없애는 시각적 프로그레스 바 추가
            progress_text = "📄 PDF 데이터를 분해하고 있습니다..."
            my_bar = st.progress(0, text=progress_text)
            
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
                
                full_text += f"\n--- [ {page_num + 1} 페이지 ] ---\n" + page_text + "\n"
                
                for word in forbidden_words:
                    if word in page_text and f"'{word}'" not in str(found_text_violations):
                        found_text_violations.append(f"📄 제 {page_num+1}페이지: '{word}' 문구 발견 (텍스트)")
                
                # ⚡ [가속 비기 2] DPI 40, 크기 400으로 극한의 이미지 다이어트
                pix = page.get_pixmap(dpi=40)
                img_data = pix.tobytes("png")
                
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                img.thumbnail((400, 400)) 
                images_for_ai.append(img)
                
                # 진행률 바 업데이트 (사용자 안심 효과)
                my_bar.progress((page_num + 1) / total_pages, text=f"⚡ 초경량 압축 중... ({page_num + 1}/{total_pages}장)")
            
            my_bar.progress(100, text="✨ 압축 완료! AI 동시 스캔을 시작합니다.")
            time.sleep(0.5)
            my_bar.empty() # 진행률 바 숨기기
            
            with st.spinner("⚡ 제미나이가 '로고'와 '맞춤법'을 동시에 분석 중입니다... (곧 완료됩니다!)"):
                
                def run_vision_task():
                    vision_prompt = """당신은 입찰 제안서의 블라인드 규정 위반을 잡아내는 시각 분석 검수관입니다. 
첨부된 전체 페이지 이미지 구석구석을 확인하여, '한국능률협회' 또는 'KMA'의 '그림/도형 형태의 로고, 심볼, 마크, 행사 현수막 이미지'가 존재하는지 시각적으로 찾아내세요.
[🚨 주의사항] 
1. 문서에 타이핑된 '일반 텍스트(글자)'는 절대 지적하지 마세요. 
2. 발견되면 오류 페이지만 짧게 보고하고, 없다면 '위반 없음'이라고 단호하게 답변해 주세요."""
                    vision_contents = [vision_prompt] + images_for_ai 
                    # config 적용으로 답변을 짧고 빠르게 강제함
                    return model.generate_content(vision_contents, generation_config=fast_config).text

                def run_grammar_task():
                    grammar_prompt = f"""당신은 공공기관 실무 제안서를 평가하는 최고위 심사위원입니다. 
다음 텍스트에서 '누가 보아도 의미가 왜곡될 정도로 치명적인 수준의 심각한 오타나 문법 파괴'만 찾아내어 작성해 주세요.

[🚨 제안서 특화 예외 규칙 - 절대 지적 금지]
1. 제안서 특유의 강조형/슬로건 문구는 다소 길거나 어색하더라도 절대 지적 금지.
2. 개조식 문장(명사로 끝나는 문장) 무시.
3. 띄어쓰기 오류 무시.

[🚨 출력 규칙]
1. 반드시 **마크다운 표(Table)** 형식으로만 출력 (| 오류 페이지 | 기존 문장 | 수정된 문장 | 교정 사유 |).
2. 평가에 치명적인 '진짜 찐 오류'만 최대 5개 이내로 아주 짧게 요약.
3. 오류가 없다면 '✅ 치명적인 오타 및 오류가 발견되지 않았습니다'라고만 출력.

[제안서 내용 (각 페이지 번호가 표기되어 있음)]
{full_text[:40000]}"""
                    # config 적용으로 답변을 짧고 빠르게 강제함
                    return model.generate_content(grammar_prompt, generation_config=fast_config).text

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_vision = executor.submit(run_vision_task)
                    future_grammar = executor.submit(run_grammar_task)
                    
                    vision_result = future_vision.result()
                    grammar_result = future_grammar.result()
            
            # 3단계: 화면 출력
            with tab1:
                st.subheader("🕵️‍♂️ 블라인드 심사 규정 위반 검사")
                if found_text_violations:
                    st.error("❌ 텍스트 블라인드 위반 적발!")
                    for v in found_text_violations:
                        st.write(v)
                else:
                    st.success("✅ 텍스트 금지어 검사 통과 (위반 단어 없음)")
                st.divider()
                
                if "위반 없음" in vision_result or "발견되지 않았" in vision_result:
                    st.success("✅ 로고 이미지 검사 통과 (시각적 마크 발견되지 않음)")
                else:
                    st.warning("⚠️ 이미지 형태의 로고 분석 결과 확인 필요")
                st.write(vision_result)
            
            with tab2:
                st.subheader("📊 핵심 오타 및 비문 교정 리포트")
                st.write(grammar_result)
                st.success("✅ 맞춤법 및 문맥 핵심 검사 완료!")
                    
        except Exception as e:
            st.error(f"실행 중 오류가 발생했습니다: {e}")
