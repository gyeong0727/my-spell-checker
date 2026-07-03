import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image
import io
import concurrent.futures
import time

try:
    MY_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=MY_API_KEY)
except Exception as e:
    st.error("🔑 설정 오류: .streamlit/secrets.toml 파일에 키가 없습니다.")
    st.stop()

model = genai.GenerativeModel('gemini-2.5-flash')

# ✨ [핵심 차단 장치 1] AI의 상상력을 0%로 고정하여 헛것(환각)을 보는 현상 원천 차단
strict_config = genai.types.GenerationConfig(temperature=0.0)

st.set_page_config(page_title="제안서 통합 검수 시스템", page_icon="🛡️", layout="wide")

st.title("🛡️ KMA 제안 블라인드 및 오타 검수 시스템 🚀")
st.write("30초 이내에 검수가 완료되지만, 제안서 용량과 인터넷 환경에 따라 검수시간이 늘어날 수 있습니다.")

uploaded_file = st.file_uploader("검수할 PDF 제안서 파일을 올려주세요", type=["pdf", "ppt", "pptx"])

if uploaded_file is not None:
    
    if uploaded_file.name.lower().endswith(('.ppt', '.pptx')):
        st.toast("🚨 PPT 파일은 검수할 수 없습니다! PDF로 변환해 주세요.", icon="❌")
        st.error("🚨 **파일 형식 오류:** PPT 파일은 바로 검수할 수 없습니다.\n\n파워포인트에서 **[다른 이름으로 저장] ➔ [PDF]**로 변환하신 후 다시 올려주세요!")
    
    else:
        if st.button("🚀 통합 검수 시작"):
            
            tab1, tab2 = st.tabs(["🚨 블라인드 위반 검증", "📊 맞춤법 & 문맥 교정"])
            
            try:
                my_bar = st.progress(0, text="📄 PDF 데이터를 분해하고 있습니다...")
                
                file_bytes = uploaded_file.read()
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                total_pages = len(doc)
                
                full_text = ""
                vision_payload = [] 
                
                # ✨ [핵심 차단 장치 2] 로고 발견 시 '색상'과 '모양'을 의무적으로 묘사하게 하여 텍스트 오인 방지
                vision_prompt = """당신은 제안서의 블라인드 규정 위반을 잡아내는 '매우 깐깐하고 보수적인' 시각 분석관입니다. 
첨부된 이미지들은 제안서의 각 페이지이며, 이미지 바로 앞에 '[N 페이지]'라는 꼬리표가 붙어 있습니다.

[🚨 허위 신고(과잉 탐지) 원천 차단 특별 규칙 - 반드시 지키세요]
1. 오직 '한국능률협회' 또는 'KMA'의 **명백한 그림/도형 형태의 공식 로고나 마크**만 찾으세요.
2. 문서 본문, 표, 다이어그램, 그래프 안에 단순히 타이핑된 '글자(텍스트)'는 로고가 아닙니다. 절대 지적하지 마세요.
3. [가장 중요] 로고를 발견했다고 판단한 경우, 허위 신고를 막기 위해 **반드시 해당 로고의 '색상'과 '도형의 생김새'를 구체적으로 묘사**해야 합니다.
   - 올바른 예: - ❌ 제 3페이지: 우측 하단에 파란색 선과 구체 모양으로 이루어진 KMA 마크 발견
   - 잘못된 예(기각): - ❌ 제 5페이지: KMA 로고 발견 (색상과 도형 묘사가 불가능하므로 단순 글자로 간주하여 무효 처리)
4. 색상과 도형의 생김새를 명확히 설명할 수 없다면, 그것은 로고가 아니므로 단호하게 무시하세요.
5. 확실한 시각적 로고가 단 하나도 없다면 '✅ 위반 없음'이라고 답변하세요."""
                
                vision_payload.append(vision_prompt)
                
                forbidden_words = ["(사)한국능률협회", "KMA", "능률협회", "한국능률협회", "한국능률협회 부산경남본부"]
                found_text_violations = []
                
                for page_num in range(total_pages):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    
                    full_text += f"\n--- [ {page_num + 1} 페이지 ] ---\n" + page_text + "\n"
                    
                    for word in forbidden_words:
                        if word in page_text:
                            v_msg = f"📄 제 {page_num+1}페이지: '{word}' 문구 발견"
                            if v_msg not in found_text_violations:
                                found_text_violations.append(v_msg)
                    
                    pix = page.get_pixmap(dpi=40)
                    img_data = pix.tobytes("png")
                    
                    img = Image.open(io.BytesIO(img_data)).convert("RGB")
                    img.thumbnail((300, 300)) 
                    
                    vision_payload.append(f"[{page_num + 1} 페이지]")
                    vision_payload.append(img)
                    
                    my_bar.progress((page_num + 1) / total_pages, text=f"⚡ 초경량 압축 중... ({page_num + 1}/{total_pages}장)")
                
                my_bar.progress(100, text="✨ 압축 완료! AI 동시 스캔을 시작합니다.")
                time.sleep(0.5)
                my_bar.empty()
                
                with st.spinner("⚡ 제미나이가 '로고(초정밀 스캔)'와 '맞춤법'을 동시에 분석 중입니다..."):
                    
                    def run_vision_task():
                        # ✨ 생성 옵션(generation_config)에 strict_config(temperature 0.0)를 적용합니다.
                        return model.generate_content(vision_payload, generation_config=strict_config).text

                    def run_grammar_task():
                    grammar_prompt = f"""당신은 공공기관 실무 제안서를 검수하는 꼼꼼한 최고위 심사위원입니다. 
다음 텍스트에서 '문맥에 맞지 않는 치명적인 단어 오타(예: 사전설문 -> 사적설문)'와 '의미가 왜곡되는 비문'을 예리하게 찾아내어 작성해 주세요.

[🚨 제안서 특화 예외 규칙 - 절대 지적 금지]
1. 제안서 특유의 강조형/슬로건 문구는 다소 길거나 어색하더라도 절대 지적 금지.
2. 개조식 문장(명사로 끝나는 문장) 무시.
3. 띄어쓰기 오류는 100% 무시.

[🎯 집중 검출 대상 (이런 오타를 찾으세요)]
1. 철자 기입 실수로 문맥이 완전히 어색해진 단어 (예: 사전설문 -> 사적설문, 결재 -> 결제 등)
2. 기업명, 기관명, 고유명사 등의 오탈자

[🚨 출력 규칙]
1. 반드시 **마크다운 표(Table)** 형식으로만 출력 (| 오류 페이지 | 기존 문장 | 수정된 문장 | 교정 사유 |).
2. 진짜 수정이 필요한 핵심 오타들만 모아서 최대 10개 이내로 요약 리포트 작성.
3. 오류가 없다면 '✅ 치명적인 오타 및 오류가 발견되지 않았습니다'라고만 출력.

[제안서 내용]
{full_text[:40000]}"""
                        # 텍스트 검수도 깐깐하게 하도록 옵션 적용
                        return model.generate_content(grammar_prompt, generation_config=strict_config).text

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future_vision = executor.submit(run_vision_task)
                        future_grammar = executor.submit(run_grammar_task)
                        
                        vision_result = future_vision.result()
                        grammar_result = future_grammar.result()
                
                with tab1:
                    st.subheader("🕵️‍♂️ 블라인드 심사 규정 위반 검사")
                    if found_text_violations:
                        st.error("❌ 텍스트 블라인드 위반 적발!")
                        for v in found_text_violations:
                            st.markdown(f"- **{v}**")
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
