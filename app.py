import streamlit as st
from google import genai
from google.genai import types
from fpdf import FPDF
import fitz  # PyMuPDF
import tempfile
import os
import re

st.set_page_config(page_title="Strict PDF Extractor", layout="centered")
st.title("📄 100% PDF-Only Answer App")
st.write("તમે અપલોડ કરેલી PDF માંથી જ બેઠેબેઠા જવાબો અને પેજ નંબર મેળવો.")

search_mode = st.radio(
    "તમારે જવાબ કેવી રીતે શોધવા છે?",
    [
        "૧. Strict PDF Copy Mode (PDF માંથી બેઠેબેઠો જવાબ + Page No.)",
        "૨. Non-AI Keyword Search (API Key વગર સીધા પેરેગ્રાફ શોધો)"
    ]
)

api_key = ""
if "Strict PDF Copy Mode" in search_mode:
    api_key = st.text_input("તમારી Gemini API Key અહીં નાખો:", type="password")

unit_pdf = st.file_uploader("૧. આખા યુનિટની PDF અપલોડ કરો", type=["pdf"])

st.subheader("૨. તમારા પ્રશ્નો આપો")
question_mode = st.radio("પ્રશ્નો કેવી રીતે આપવા છે?", ["લખીને આપવા છે", "પ્રશ્નોની PDF અપલોડ કરવી છે"])

questions_text = ""
questions_pdf = None

if question_mode == "લખીને આપવા છે":
    questions_text = st.text_area("તમારા પ્રશ્નો અહીં લખો (એક નીચે એક):", height=150)
else:
    questions_pdf = st.file_uploader("પ્રશ્નોની PDF અપલોડ કરો", type=["pdf"])

def create_answer_pdf(content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=11)
    for line in content.split('\n'):
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 7, txt=clean_line)
    return bytes(pdf.output())

def extract_without_ai(unit_bytes, q_list):
    doc = fitz.open(stream=unit_bytes, filetype="pdf")
    stop_words = {"what", "is", "are", "the", "of", "in", "and", "to", "explain", "define", "write", "note", "on", "short", "describe", "discuss", "how", "why", "with", "for", "a", "an"}
    
    output_report = []
    for idx, q in enumerate(q_list, 1):
        if not q.strip():
            continue
        words = [w.lower() for w in re.findall(r'\w+', q) if w.lower() not in stop_words and len(w) > 2]
        output_report.append(f"Q{idx}: {q.strip()}")
        
        matches = []
        for page_num in range(len(doc)):
            blocks = doc[page_num].get_text("blocks")
            for b in blocks:
                block_text = b[4].strip()
                if len(block_text) < 30:
                    continue
                score = sum(1 for w in words if w in block_text.lower())
                if score > 0:
                    matches.append((score, page_num + 1, block_text))
        
        matches.sort(key=lambda x: x[0], reverse=True)
        if matches:
            output_report.append("Answer (Extracted directly from PDF):")
            for score, p_no, text in matches[:3]:
                clean_blk = " ".join(text.splitlines())
                output_report.append(f"[Page {p_no}]: {clean_blk}\n")
        else:
            output_report.append("Answer: Not found in PDF.\n")
        output_report.append("-" * 50)
    return "\n".join(output_report)

if st.button("PDF માંથી જવાબ શોધીને નવી PDF બનાવો 🚀"):
    if not unit_pdf:
        st.error("કૃપા કરીને પહેલા યુનિટની PDF અપલોડ કરો!")
    elif question_mode == "લખીને આપવા છે" and not questions_text.strip():
        st.error("કૃપા કરીને પ્રશ્નો લખો!")
    elif question_mode == "પ્રશ્નોની PDF અપલોડ કરવી છે" and not questions_pdf:
        st.error("કૃપા કરીને પ્રશ્નોની PDF અપલોડ કરો!")
    else:
        unit_bytes = unit_pdf.read()
        
        if "Non-AI Keyword Search" in search_mode:
            with st.spinner("PDF ના પેજમાંથી સીધા પેરેગ્રાફ શોધાઈ રહ્યા છે..."):
                if question_mode == "લખીને આપવા છે":
                    q_list = questions_text.strip().split('\n')
                else:
                    q_doc = fitz.open(stream=questions_pdf.read(), filetype="pdf")
                    full_q_text = "\n".join([page.get_text() for page in q_doc])
                    q_list = [line for line in full_q_text.split('\n') if '?' in line or len(line.strip()) > 10]
                
                final_answers = extract_without_ai(unit_bytes, q_list)
                st.success("✅ PDF માંથી પેરેગ્રાફ મળી ગયા છે!")
                with st.expander("જવાબો અહીં વાંચો"):
                    st.text(final_answers)
                
                pdf_bytes = create_answer_pdf(final_answers)
                st.download_button("📥 જવાબોની PDF ડાઉનલોડ કરો", data=pdf_bytes, file_name="Direct_PDF_Answers.pdf", mime="application/pdf")

        else:
            if not api_key:
                st.error("કૃપા કરીને Gemini API Key નાખો!")
            else:
                with st.spinner("PDF માંથી બેઠેબેઠા જવાબો શોધાઈ રહ્યા છે..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_unit:
                            tmp_unit.write(unit_bytes)
                            tmp_unit_path = tmp_unit.name
                        
                        uploaded_unit = client.files.upload(file=tmp_unit_path)
                        
                        strict_instruction = (
                            "STRICT RULES:\n"
                            "1. You are a strict PDF text extractor, NOT a general AI assistant.\n"
                            "2. Answer the questions using ONLY the exact sentences, definitions, formulas, and points written inside the uploaded Unit PDF.\n"
                            "3. DO NOT use any outside knowledge or your own words. Keep the exact wording from the PDF.\n"
                            "4. Mention the exact Page Number from the Unit PDF for every answer (e.g., [PDF Page: 4]).\n"
                            "5. If any answer is NOT present in the uploaded PDF, strictly write: 'Not found in the uploaded PDF'."
                        )
                        
                        prompt_contents = [uploaded_unit, strict_instruction]
                        
                        if question_mode == "લખીને આપવા છે":
                            prompt_contents.append(f"Extract exact answers from the PDF for these questions:\n{questions_text}")
                        else:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_q:
                                tmp_q.write(questions_pdf.read())
                                tmp_q_path = tmp_q.name
                            uploaded_q = client.files.upload(file=tmp_q_path)
                            prompt_contents.append(uploaded_q)
                            prompt_contents.append("Extract exact verbatim answers from the first Unit PDF for all questions in the second PDF.")

                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt_contents,
                            config=types.GenerateContentConfig(temperature=0.0)
                        )
                        
                        final_answers = response.text
                        st.success("✅ PDF માંથી બેઠેબેઠા જવાબો તૈયાર થઈ ગયા છે!")
                        
                        with st.expander("જવાબો અહીં વાંચો (Preview)"):
                            st.markdown(final_answers)
                        
                        pdf_bytes = create_answer_pdf(final_answers)
                        st.download_button(
                            label="📥 જવાબોની PDF ડાઉનલોડ કરો",
                            data=pdf_bytes,
                            file_name="Strict_PDF_Answers.pdf",
                            mime="application/pdf"
                        )
                        
                        os.remove(tmp_unit_path)
                        if questions_pdf:
                            os.remove(tmp_q_path)
                    except Exception as e:
                        st.error(f"ભૂલ આવી: {e}")
