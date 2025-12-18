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

# --- Voice Configuration (7 Female Voices) ---
VOICE_MAP = {
    "👩 Sarah (American, Neutral)": {"tld": "com", "lang": "en"},
    "👩 Grace (British, Professional)": {"tld": "co.uk", "lang": "en"},
    "👩 Emma (American, Warm)": {"tld": "us", "lang": "en"},
    "👩 Zara (Neutral, Modern)": {"tld": "ca", "lang": "en"},
    "👩 Maya (Indian, Clear)": {"tld": "co.in", "lang": "en"},
    "👩 Lisa (Australian, Friendly)": {"tld": "com.au", "lang": "en"},
    "👩 Sophia (South African)": {"tld": "co.za", "lang": "en"},
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

            # --- Audio Generation Options ---
            st.markdown("### 🎧 Generate Audio")
            
            # Option 1: Current Page
            if st.button("🔊 Read This Page", use_container_width=True):
                page_text = pages_text[current_page] if current_page < len(pages_text) else ""
                if page_text.strip():
                    with st.spinner("Generating audio..."):
                        audio = generate_audio(page_text, voice_data["lang"], voice_data["tld"])
                        if audio:
                            st.audio(audio, format="audio/mp3")
                            st.download_button("📥 Download", audio.getvalue(), f"page_{current_page+1}.mp3", "audio/mp3")
                else:
                    st.warning("No text on this page.")

            st.markdown("---")
            
            # Option 2: Custom Page Range
            st.markdown("**📚 Custom Page Range:**")
            col_start, col_end = st.columns(2)
            with col_start:
                start_page = st.number_input("From Page", 1, total_pages, 1)
            with col_end:
                end_page = st.number_input("To Page", 1, total_pages, total_pages)
            
            if start_page > end_page:
                st.error("Start page must be ≤ End page")
            else:
                if st.button(f"🎧 Read Pages {start_page} to {end_page}", type="primary", use_container_width=True):
                    # Extract text from selected range
                    range_text = " ".join([
                        pages_text[i] for i in range(start_page - 1, end_page) 
                        if i < len(pages_text) and pages_text[i].strip()
                    ])
                    
                    if range_text:
                        char_count = len(range_text)
                        st.info(f"📊 {char_count} characters • ~{char_count//150} seconds of audio")
                        
                        with st.spinner(f"Generating audio for pages {start_page}-{end_page}..."):
                            audio = generate_audio(range_text, voice_data["lang"], voice_data["tld"])
                            if audio:
                                st.audio(audio, format="audio/mp3")
                                st.download_button(
                                    "📥 Download MP3", 
                                    audio.getvalue(), 
                                    f"pages_{start_page}_to_{end_page}.mp3", 
                                    "audio/mp3",
                                    use_container_width=True
                                )
                    else:
                        st.error("No text found in selected page range.")

            st.markdown("---")
            
            # Show page text with highlighting
            st.markdown("### 📝 Currently Reading (Highlighted)")
            page_text = pages_text[current_page] if current_page < len(pages_text) else ""
            if page_text:
                # Display with yellow highlight styling
                st.markdown(f'''
                <div style="
                    background: linear-gradient(135deg, #4A90E2 0%, #2E5C8A 100%);
                    padding: 20px;
                    border-radius: 12px;
                    border-left: 5px solid #2ECC71;
                    margin: 10px 0;
                    box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
                ">
                    <p style="
                        color: white;
                        font-size: 16px;
                        line-height: 1.8;
                        margin: 0;
                        font-weight: 500;
                    ">
                        {page_text[:2000]}{'...' if len(page_text) > 2000 else ''}
                    </p>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.warning("No text on this page.")

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
