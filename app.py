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

def text_to_speech(text, lang='en'):
    """Converts text to speech using gTTS."""
    if not text.strip():
        return None
    # gTTS defaults to female voice for 'en'
    tts = gTTS(text=text, lang=lang, slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

def main():
    st.set_page_config(
        page_title="PDF Voice Reader",
        page_icon="🎧",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # --- Custom CSS for Modern SaaS Look ---
    st.markdown("""
        <style>
        /* Global Font & Colors */
        .stApp {
            font-family: 'Inter', sans-serif;
        }
        
        /* Headers */
        h1, h2, h3 {
            color: #111827;
            font-weight: 700 !important;
        }
        
        /* Buttons */
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
            border: none;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            transition: all 0.2s;
        }
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        /* Custom Cards / Containers */
        .css-1r6slb0 { /* Streamlit container class approximation for card effect */
            background-color: white;
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid #E5E7EB;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        }
        
        /* Audio Player Styling in Markdown */
        audio {
            width: 100%;
            height: 40px;
            border-radius: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- Header Section ---
    col_header_1, col_header_2 = st.columns([1, 4])
    with col_header_1:
        st.title("🎧") # Just icon
    with col_header_2:
        st.title("PDF Voice Reader")
        st.caption("Turn any PDF into an instant audiobook. Perfect for students & professionals.")

    st.markdown("---")

    # --- Session State Init ---
    if 'pdf_total_pages' not in st.session_state:
        st.session_state.pdf_total_pages = 0

    # --- Main Content Area ---
    
    # 1. Main Controls & Input (Left Column)
    col_left, col_right = st.columns([1, 1], gap="large")
    
    with col_left:
        st.markdown("### 1. Upload Document")
        uploaded_file = st.file_uploader("Select a PDF file", type=["pdf"], label_visibility="collapsed")
        
        if not uploaded_file:
            # --- Empty State / Onboarding ---
            st.info("👋 **Welcome!** To get started:")
            st.markdown("""
            1. Upload a PDF file above.
            2. Select the pages you want to listen to.
            3. Click **Play** to generate audio.
            """)
            st.markdown("---")
            st.caption("🔒 Valid for text-based PDFs up to 200MB. Your files are processed securely in memory.")
        
        else:
            # File Info Card
            try:
                if st.session_state.pdf_total_pages == 0:
                     doc_temp = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                     st.session_state.pdf_total_pages = len(doc_temp)
                     uploaded_file.seek(0)

                st.success(f"✅ **{uploaded_file.name}** loaded successfully! ({st.session_state.pdf_total_pages} pages)")
                
                # Page Range Selection Card
                st.markdown("### 2. Select Range")
                with st.container():
                     c1, c2 = st.columns(2)
                     with c1:
                         start_page = st.number_input("Start Page", 1, st.session_state.pdf_total_pages, 1)
                     with c2:
                         end_page = st.number_input("End Page", 1, st.session_state.pdf_total_pages, st.session_state.pdf_total_pages)
                     
                     if start_page > end_page:
                         st.error("Start Page must be ≤ End Page")

            except Exception as e:
                st.error("Error loading PDF. Please ensure it is a valid file.")

    # 2. Playback & Output (Right Column)
    with col_right:
        if uploaded_file and st.session_state.pdf_total_pages > 0 and start_page <= end_page:
            st.markdown("### 3. Listen")
            
            # Processing Logic
            if 'start_page' not in locals(): start_page = 1
            if 'end_page' not in locals(): end_page = st.session_state.pdf_total_pages
            
            with st.spinner("Processing text..."):
                pages_text, _ = extract_text_from_pdf(uploaded_file, start_page, end_page)

            if pages_text:
                # Reader Interface
                tab1, tab2 = st.tabs(["🎧 Audio Player", "📄 Text Preview"])
                
                with tab1:
                    # Page Navigation for Reading
                    page_idx = st.slider(
                        "Current Page", 
                        0, 
                        len(pages_text)-1, 
                        0,
                        format=f"Page {start_page + '%d'}"
                    )
                    
                    current_text = pages_text[page_idx]
                    
                    # Generate Audio
                    if st.button("▶️ Generate & Play Audio", type="primary", use_container_width=True):
                         with st.spinner("Generating voice..."):
                            try:
                                audio_fp = text_to_speech(current_text)
                                if audio_fp:
                                    audio_bytes = audio_fp.read()
                                    b64 = base64.b64encode(audio_bytes).decode()
                                    
                                    # HTML5 Audio Player
                                    md_audio = f"""
                                        <audio controls autoplay>
                                        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                                        </audio>
                                    """
                                    st.markdown(md_audio, unsafe_allow_html=True)
                                    
                                    # Download
                                    st.download_button("📥 Download MP3", audio_bytes, f"page_{start_page+page_idx}.mp3", "audio/mp3", use_container_width=True)
                                else:
                                    st.warning("No readable text on this page.")
                            except Exception as e:
                                st.error(f"TTS Error: {e}")
                                
                with tab2:
                    st.text_area("Content", current_text, height=400)
            else:
                 st.warning("No text found in the selected range.")
                 
        else:
            # Right column empty state
            if not uploaded_file:
                 st.markdown(" ") # Spacer
                 st.image("https://cdn-icons-png.flaticon.com/512/337/337946.png", width=150, caption="Listen anywhere") # Placeholder icon

    # --- Sidebar: Settings ---
    with st.sidebar:
        st.header("⚙️ Settings")
        st.subheader("Voice Options")
        speed = st.select_slider("Speed multiplier", [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], 1.0)
        st.caption("Note: Speed adjustment is currently handled by the browser player controls.")
        
        st.divider()
        st.markdown("**About**")
        st.markdown("Built with Streamlit & gTTS.")

if __name__ == "__main__":
    main()
