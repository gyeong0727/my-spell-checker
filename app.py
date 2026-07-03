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

st.set_page_config(page_title="제안서 통합 검수 시스템", page_icon="🛡️", layout="wide")

# ✨ [문구 수정 완료] 타이틀 및 대기 시간 안내문 변경
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
                
                vision_prompt = """당신은 제안서의 블라인드 규정 위반을 잡아내는 예리한 시각 분석관입니다. 
첨부된 이미지들은 제안서의 각 페이지이며, 이미지 바로 앞에 '[N 페이지]'라는 꼬리표(텍스트)가 붙어 있습니다.

[🚨 핵심 지시사항]
1. '한국능률협회' 또는 'KMA'의 '그림/도형 형태의 로고나 마크'가 존재하는지 샅샅이 확인하세요.
2. 로고가 발견되면, 읽기 편하게 **반드시 한 줄에 하나씩 줄바꿈(- )**을 해서 명시하세요. 
   (예시)
   - ❌ 제 59페이지: 우측 하단 KMA 로고 발견
   - ❌ 제 73페이지: 좌측 상단 능률협회 마크 발견
3. 문서에 타이핑된 '일반 텍스트(글자)'는 절대 지적하지 마세요.
4. 시각적 로고가 없다면 억지로 찾지 말고 단호하게 '✅ 위반 없음'이라고 답변하세요."""
                
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
                        return model.generate_content(vision_payload).text

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

[🚨 출력 규칙 (가독성 최우선)]
1. 절대 표(Table) 형태로 그리지 마세요. 모바일이나 좁은 화면에서 가독성이 떨어집니다.
2. 반드시 각 오류마다 **한 줄씩 띄어서 항목별로 깔끔하게** 리스트 형태로 출력하세요.
   (양식 예시)
   - 📄 **[O 페이지]** 기존: ~ ➔ 수정: ~ (사유: ~)
3. 진짜 수정이 필요한 핵심 오타들만 모아서 최대 10개 이내로 요약 리포트 작성.
4. 오류가 없다면 '✅ 치명적인 오타 및 오류가 발견되지 않았습니다'라고만 출력.

[제안서 내용]
{full_text[:40000]}"""
                        return model.generate_content(grammar_prompt).text

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
