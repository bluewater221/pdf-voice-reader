import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS
import io
import base64

# --- Page Config ---
st.set_page_config(
    page_title="PDF Voice Reader",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .stApp {
        background-color: #0F1419;
        color: #E8E8E8;
    }
    h1, h2, h3, p, label { color: #E8E8E8 !important; }
    
    .stButton > button {
        background-color: #4A90E2;
        color: white;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #2E5C8A;
    }
    
    .page-text-box {
        background-color: #1A1E2A;
        border: 1px solid #2E3847;
        border-radius: 8px;
        padding: 15px;
        max-height: 400px;
        overflow-y: auto;
        font-size: 14px;
        line-height: 1.8;
        color: #E8E8E8;
    }
</style>
""", unsafe_allow_html=True)

# --- Voice Configuration ---
VOICE_MAP = {
    "👩 Sarah (American)": {"tld": "com", "lang": "en"},
    "👩 Grace (British)": {"tld": "co.uk", "lang": "en"},
    "👩 Maya (Indian)": {"tld": "co.in", "lang": "en"},
    "👩 Lisa (Australian)": {"tld": "com.au", "lang": "en"},
}

# --- Helper Functions ---
def get_pdf_data(file_bytes):
    """Get PDF page count and extract text per page."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text())
        return len(doc), pages_text
    except:
        return 0, []

def render_page_as_image(file_bytes, page_num):
    """Renders a PDF page as an image (PNG bytes)."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = doc.load_page(page_num)
        # Render at 1.5x resolution for clarity
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        return pix.tobytes("png")
    except:
        return None

def generate_audio(text, lang='en', tld='com'):
    """Generates audio from text using gTTS."""
    if not text.strip():
        return None
    try:
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except:
        return None

def main():
    st.markdown("<h1 style='text-align:center; color:#4A90E2;'>🎧 PDF Voice Reader</h1>", unsafe_allow_html=True)
    st.caption("Upload a PDF, navigate page-by-page, and listen with text-to-speech.")
    st.markdown("---")

    # --- Session State ---
    if 'pdf_bytes' not in st.session_state:
        st.session_state.pdf_bytes = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'total_pages' not in st.session_state:
        st.session_state.total_pages = 0
    if 'pages_text' not in st.session_state:
        st.session_state.pages_text = []

    # --- Sidebar: Voice Selection ---
    with st.sidebar:
        st.header("🎤 Voice")
        selected_voice = st.selectbox("Choose Voice", list(VOICE_MAP.keys()))
        voice_data = VOICE_MAP[selected_voice]

    # --- File Upload ---
    uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"], label_visibility="collapsed")

    if uploaded_file:
        file_bytes = uploaded_file.read()
        
        # Only reprocess if new file
        if st.session_state.pdf_bytes != file_bytes:
            st.session_state.pdf_bytes = file_bytes
            total, texts = get_pdf_data(file_bytes)
            st.session_state.total_pages = total
            st.session_state.pages_text = texts
            st.session_state.current_page = 0

        total_pages = st.session_state.total_pages
        pages_text = st.session_state.pages_text
        current_page = st.session_state.current_page

        if total_pages == 0:
            st.error("Could not read this PDF.")
            return

        st.success(f"📄 **{uploaded_file.name}** • {total_pages} pages")

        # --- Split Layout: PDF Image | Controls ---
        col_pdf, col_controls = st.columns([1, 1], gap="large")

        with col_pdf:
            st.markdown(f"### 📖 Page {current_page + 1} of {total_pages}")
            
            # Render current page as image
            img_bytes = render_page_as_image(st.session_state.pdf_bytes, current_page)
            if img_bytes:
                st.image(img_bytes, use_container_width=True)
            else:
                st.warning("Could not render this page.")

        with col_controls:
            st.markdown("### 🎧 Controls")
            
            # Navigation
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("⏮️ First"):
                    st.session_state.current_page = 0
                    st.rerun()
            with c2:
                if st.button("◀️ Prev"):
                    if current_page > 0:
                        st.session_state.current_page -= 1
                        st.rerun()
            with c3:
                if st.button("▶️ Next"):
                    if current_page < total_pages - 1:
                        st.session_state.current_page += 1
                        st.rerun()
            with c4:
                if st.button("⏭️ Last"):
                    st.session_state.current_page = total_pages - 1
                    st.rerun()
            
            # Page Slider
            new_page = st.slider("Go to Page", 1, total_pages, current_page + 1) - 1
            if new_page != current_page:
                st.session_state.current_page = new_page
                st.rerun()

            st.markdown("---")

            # Play Current Page
            if st.button("🔊 Read This Page", type="primary", use_container_width=True):
                page_text = pages_text[current_page] if current_page < len(pages_text) else ""
                if page_text.strip():
                    with st.spinner("Generating audio..."):
                        audio = generate_audio(page_text, voice_data["lang"], voice_data["tld"])
                        if audio:
                            st.audio(audio, format="audio/mp3")
                else:
                    st.warning("No text on this page.")

            # Read Full PDF
            st.markdown("---")
            if st.button("🎧 Read Entire PDF", use_container_width=True):
                full_text = " ".join([t for t in pages_text if t.strip()])
                if full_text:
                    with st.spinner(f"Generating audio for {len(full_text)} characters..."):
                        audio = generate_audio(full_text, voice_data["lang"], voice_data["tld"])
                        if audio:
                            st.audio(audio, format="audio/mp3")
                            st.download_button("📥 Download MP3", audio.getvalue(), "full_audio.mp3", "audio/mp3")
                else:
                    st.error("No text found in PDF.")

            st.markdown("---")
            
            # Show page text
            st.markdown("### 📝 Page Text")
            page_text = pages_text[current_page] if current_page < len(pages_text) else ""
            st.markdown(f'<div class="page-text-box">{page_text[:3000] if page_text else "No text on this page."}</div>', unsafe_allow_html=True)

    else:
        st.markdown("""
        <div style="background-color: #1A1E2A; padding: 30px; border-radius: 12px; text-align: center; border: 2px dashed #4A90E2;">
            <h3 style="color: #4A90E2;">📄 Upload a PDF to Start</h3>
            <p style="color: #A8B0C0;">
                1. Click "Browse files" or drag & drop a PDF.<br>
                2. Navigate pages using the controls.<br>
                3. Click "Read This Page" or "Read Entire PDF".
            </p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
