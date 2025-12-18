import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS
import io
import base64

# Page Config
st.set_page_config(
    page_title="PDF Voice Reader",
    page_icon="🗣️",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
# Custom CSS for styling
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #ff3333;
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    .stProgress > div > div > div > div {
        background-color: #ff4b4b;
    }
    div[data-testid="stExpander"] div[role="button"] p {
        font-size: 1.1rem;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Voice Configuration - WOMEN VOICES ONLY (Using gTTS TLDs) ---
VOICE_MAP = {
    "👩 Sarah (American, Neutral)": {"tld": "com", "lang": "en", "sample": "Hello, this is Sarah speaking."},
    "👩 Grace (British, Professional)": {"tld": "co.uk", "lang": "en", "sample": "Good morning, I am Grace."},
    "👩 Emma (American, Warm)": {"tld": "com", "lang": "en", "sample": "Hi there, it's Emma here."},
    "👩 Zara (Neutral, Modern)": {"tld": "com", "lang": "en", "sample": "Welcome, I'm Zara."},
    "👩 Maya (Indian, Clear)": {"tld": "co.in", "lang": "en", "sample": "Namaste, I'm Maya speaking."},
    "👩 Lisa (Australian, Friendly)": {"tld": "com.au", "lang": "en", "sample": "G'day, this is Lisa."},
    "👩 Sophia (American, Calm)": {"tld": "com", "lang": "en", "sample": "Hello, Sophia speaking here."},
}

def play_voice_sample(text, lang, tld):
    """Generates and plays a short voice sample."""
    try:
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        st.audio(fp, format="audio/mp3")
    except Exception as e:
        st.error(f"Sample Error: {e}")

def extract_text_from_pdf(file, start_page=1, end_page=None):
    """Extracts text from a PDF file within a specific range."""
    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        total_pages = len(doc)
        
        # Validate/Adjust range
        if end_page is None or end_page > total_pages:
            end_page = total_pages
        if start_page < 1:
            start_page = 1
            
        text = []
        # PyMuPDF is 0-indexed, UI is 1-indexed
        for i in range(start_page - 1, end_page):
            page = doc.load_page(i)
            text.append(page.get_text())
            
        return text, total_pages
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return [], 0

def text_to_speech(text, lang='en', tld='com'):
    """Converts text to speech using gTTS with accent support."""
    if not text.strip():
        return None
    tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

def main():
    st.markdown('<h1 style="color:#4A90E2;">PDF Voice Reader 🎧</h1>', unsafe_allow_html=True)
    st.caption("Turn any PDF into an instant audiobook with your preferred voice.")
    st.markdown("---")

    if 'pdf_total_pages' not in st.session_state:
        st.session_state.pdf_total_pages = 0

    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Settings")
        
        st.subheader("🎤 Voice Selection")
        selected_voice_name = st.selectbox(
            "Choose Speaker", 
            list(VOICE_MAP.keys()),
            index=0
        )
        voice_data = VOICE_MAP[selected_voice_name]
        
        # Audio Preview
        col_s1, col_s2 = st.columns([1, 2])
        with col_s1:
            if st.button("▶️ Test", help="Play sample"):
                play_voice_sample(voice_data["sample"], voice_data["lang"], voice_data["tld"])
        with col_s2:
            st.caption(f"Accent: {voice_data['tld']}")
            
        st.divider()
        st.subheader("⚡ Playback Speed")
        speed = st.select_slider("Multiplier", [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], 1.0)

    # --- Layout ---
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### 1. Upload & Range")
        uploaded_file = st.file_uploader("Select PDF", type=["pdf"], label_visibility="collapsed")
        
        if uploaded_file:
            try:
                if st.session_state.pdf_total_pages == 0:
                     doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                     st.session_state.pdf_total_pages = len(doc)
                     uploaded_file.seek(0)
                
                st.success(f"Loaded: {uploaded_file.name} ({st.session_state.pdf_total_pages} pages)")
                
                with st.container():
                     c1, c2 = st.columns(2)
                     start = c1.number_input("Start Page", 1, st.session_state.pdf_total_pages, 1)
                     end = c2.number_input("End Page", 1, st.session_state.pdf_total_pages, st.session_state.pdf_total_pages)
            except:
                st.error("Invalid PDF")
        else:
            st.info("Upload a PDF to begin.")
            st.markdown("""
            <div style="background-color: #1A1E2A; padding: 15px; border-radius: 8px; color: #A8B0C0;">
                <small>Supported: Text-based PDFs. Images excluded.</small>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.markdown("### 2. Player")
        
        if uploaded_file and st.session_state.pdf_total_pages > 0:
            if 'start' not in locals(): start = 1
            if 'end' not in locals(): end = st.session_state.pdf_total_pages
            
            if start <= end:
                 # Extraction
                 with st.spinner("Preparing text..."):
                     pages, _ = extract_text_from_pdf(uploaded_file, start, end)
                 
                 if pages:
                     # Navigation
                     curr_page = st.slider("Chapter Navigation", start, end, start)
                     raw_idx = curr_page - start
                     curr_text = pages[raw_idx]
                     
                     st.markdown("---")
                     
                     # Generate
                     if st.button("🔊 Generate Audio for Page", type="primary", use_container_width=True):
                         with st.spinner(f"Synthesizing voice ({selected_voice_name})..."):
                             audio_fp = text_to_speech(curr_text, voice_data["lang"], voice_data["tld"])
                             if audio_fp:
                                 b64 = base64.b64encode(audio_fp.read()).decode()
                                 st.markdown(f"""
                                     <div style="background-color: #1A1E2A; padding: 10px; border-radius: 8px; margin-top: 10px;">
                                         <audio controls autoplay style="width:100%;">
                                             <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                                         </audio>
                                     </div>
                                 """, unsafe_allow_html=True)
                             else:
                                 st.warning("No text extracted.")
                     
                     with st.expander("📄 View Text"):
                         st.text_area("Content", curr_text, height=200)

if __name__ == "__main__":
    main()
