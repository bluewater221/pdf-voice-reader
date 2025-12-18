import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS
import io

# --- Page Config ---
st.set_page_config(
    page_title="PDF Voice Reader",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0F1419; color: #E8E8E8; }
    h1, h2, h3, p, label { color: #E8E8E8 !important; }
    .stButton > button { background-color: #4A90E2; color: white; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# --- Voices ---
VOICES = {
    "👩 Sarah (American)": {"tld": "com", "lang": "en"},
    "👩 Grace (British)": {"tld": "co.uk", "lang": "en"},
    "👩 Maya (Indian)": {"tld": "co.in", "lang": "en"},
    "👩 Lisa (Australian)": {"tld": "com.au", "lang": "en"},
}

# --- Functions ---
def get_pdf_text(file_bytes):
    """Extract text from all pages."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        texts = [page.get_text() for page in doc]
        return len(doc), texts
    except Exception as e:
        st.error(f"PDF Error: {e}")
        return 0, []

def get_page_image(file_bytes, page_num):
    """Render page as image."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        return pix.tobytes("png")
    except:
        return None

def make_audio(text, lang, tld):
    """Generate audio from text."""
    if not text or not text.strip():
        return None
    try:
        text = text[:5000]  # Limit length
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        audio = io.BytesIO()
        tts.write_to_fp(audio)
        audio.seek(0)
        return audio
    except Exception as e:
        st.error(f"Audio Error: {e}")
        return None

# --- Main App ---
def main():
    st.title("🎧 PDF Voice Reader")
    
    # Session state
    if 'pdf_bytes' not in st.session_state:
        st.session_state.pdf_bytes = None
    if 'page' not in st.session_state:
        st.session_state.page = 0
    if 'pages' not in st.session_state:
        st.session_state.pages = 0
    if 'texts' not in st.session_state:
        st.session_state.texts = []

    # Sidebar - Voice
    with st.sidebar:
        st.header("🎤 Voice")
        voice_name = st.selectbox("Select", list(VOICES.keys()))
        voice = VOICES[voice_name]

    # Upload
    file = st.file_uploader("📄 Upload PDF", type=["pdf"])
    
    if file:
        # Read file
        file_bytes = file.read()
        
        # Process if new file
        if st.session_state.pdf_bytes != file_bytes:
            st.session_state.pdf_bytes = file_bytes
            pages, texts = get_pdf_text(file_bytes)
            st.session_state.pages = pages
            st.session_state.texts = texts
            st.session_state.page = 0
        
        pages = st.session_state.pages
        texts = st.session_state.texts
        page = st.session_state.page
        
        if pages == 0:
            st.error("Could not read PDF")
            return
        
        st.success(f"📄 {file.name} - {pages} pages")
        
        # Layout
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"📖 Page {page + 1}/{pages}")
            img = get_page_image(st.session_state.pdf_bytes, page)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.warning("Cannot render page")
        
        with col2:
            st.subheader("🎧 Controls")
            
            # Navigation
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("⏮️"):
                st.session_state.page = 0
                st.rerun()
            if c2.button("◀️") and page > 0:
                st.session_state.page = page - 1
                st.rerun()
            if c3.button("▶️") and page < pages - 1:
                st.session_state.page = page + 1
                st.rerun()
            if c4.button("⏭️"):
                st.session_state.page = pages - 1
                st.rerun()
            
            # Slider
            new_page = st.slider("Page", 1, pages, page + 1) - 1
            if new_page != page:
                st.session_state.page = new_page
                st.rerun()
            
            st.markdown("---")
            
            # Read button
            if st.button("🔊 Read This Page", type="primary", use_container_width=True):
                text = texts[page] if page < len(texts) else ""
                if text.strip():
                    with st.spinner("Generating audio..."):
                        audio = make_audio(text, voice["lang"], voice["tld"])
                        if audio:
                            st.audio(audio, format="audio/mp3")
                else:
                    st.warning("No text on this page")
            
            st.markdown("---")
            
            # Custom range
            st.markdown("**Custom Range:**")
            r1, r2 = st.columns(2)
            start = r1.number_input("From", 1, pages, 1)
            end = r2.number_input("To", 1, pages, pages)
            
            if start <= end:
                if st.button(f"🎧 Read Pages {start}-{end}", use_container_width=True):
                    range_text = " ".join([texts[i] for i in range(start-1, end) if i < len(texts)])
                    if range_text.strip():
                        with st.spinner("Generating..."):
                            audio = make_audio(range_text, voice["lang"], voice["tld"])
                            if audio:
                                st.audio(audio, format="audio/mp3")
                                st.download_button("📥 Download", audio.getvalue(), "audio.mp3", "audio/mp3")
            
            st.markdown("---")
            
            # Text preview
            st.subheader("📝 Text")
            text = texts[page] if page < len(texts) else ""
            st.text_area("Content", text[:1500], height=150, disabled=True)
    
    else:
        st.info("👆 Upload a PDF to get started")

if __name__ == "__main__":
    main()
