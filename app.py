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
    st.title("🗣️ PDF Voice Reader")
    st.markdown("### Turn your PDFs into Audiobooks instantly!")

    # Initialize session state for page range if not exists
    if 'pdf_total_pages' not in st.session_state:
        st.session_state.pdf_total_pages = 0

    with st.sidebar:
        st.header("📂 Upload & Settings")
        uploaded_file = st.file_uploader("Drop your PDF here", type=["pdf"])
        
        if uploaded_file:
            # Quick open to get page count for sliders (inefficient but needed for UI before processing)
            # A better way is to process once, but we need the range BEFORE processing for the requirement "Skip processing unselected pages"
            # So we check total pages first
            try:
                doc_temp = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                st.session_state.pdf_total_pages = len(doc_temp)
                uploaded_file.seek(0) # Reset pointer
            except:
                pass

        if st.session_state.pdf_total_pages > 0:
            st.markdown("---")
            st.subheader("📑 Page Range Selection")
            col_start, col_end = st.columns(2)
            with col_start:
                start_page = st.number_input("Start Page", min_value=1, max_value=st.session_state.pdf_total_pages, value=1)
            with col_end:
                end_page = st.number_input("End Page", min_value=1, max_value=st.session_state.pdf_total_pages, value=st.session_state.pdf_total_pages)

            if start_page > end_page:
                st.error("Start page must be less than or equal to End page.")
            else:
                st.success(f"Selected: Pages {start_page} to {end_page}")

        st.markdown("---")
        st.subheader("🎧 Voice Controls")
        speed = st.select_slider("Playback Speed", options=[0.5, 0.75, 1.0, 1.25, 1.5, 2.0], value=1.0)
        
        st.markdown("---")
        st.info("💡 **Tip:** Use the sidebar to control playback speed and navigate pages.")

    if uploaded_file and st.session_state.pdf_total_pages > 0:
        if start_page <= end_page:
            # Extract Text
            with st.spinner(f"📄 Extracting text from pages {start_page}-{end_page}..."):
                pages_text, _ = extract_text_from_pdf(uploaded_file, start_page, end_page)
            
            if not pages_text:
                st.error("Could not extract text from this PDF.")
                return

            # Page Selection (Relative to the selected range)
            # The 'pages_text' list index 0 corresponds to 'start_page'
            st.markdown(f"---")
            
            # Helper to map slider index to actual page number
            # Slider range: 0 to len(pages_text)-1
            selected_index = st.slider("Select Page to Read", 0, len(pages_text) - 1, 0, format=f"Page %d (Original: {start_page + '%d'})")
            
            # Display intuitive page numbers
            current_display_page = start_page + selected_index
            st.markdown(f"### 📄 Page {current_display_page} (of {st.session_state.pdf_total_pages})")
                
            current_text = pages_text[selected_index]
            
            # Display Text
            with st.expander("📝 View Page Text", expanded=True):
                st.text_area("Content", current_text, height=300, label_visibility="collapsed")

            # Generate Audio
            if st.button("🔊 Play / Generate Audio", key="generate"):
                with st.spinner("🎧 Generating Audio..."):
                    try:
                        audio_fp = text_to_speech(current_text)
                        if audio_fp:
                            audio_bytes = audio_fp.read()
                            audio_base64 = base64.b64encode(audio_bytes).decode()
                            
                            # Custom Audio Player with Speed Control and Skip Buttons
                            audio_html = f"""
                                <div style="background-color: #262730; padding: 20px; border-radius: 10px; margin-top: 20px;">
                                    <audio id="audio-player" controls autoplay style="width: 100%;">
                                        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                                    </audio>
                                    <div style="display: flex; justify-content: center; gap: 10px; margin-top: 10px;">
                                        <button onclick="document.getElementById('audio-player').currentTime -= 10" style="padding: 5px 10px; border-radius: 5px; border: none; background: #ff4b4b; color: white; cursor: pointer;">⏪ -10s</button>
                                        <button onclick="document.getElementById('audio-player').currentTime += 10" style="padding: 5px 10px; border-radius: 5px; border: none; background: #ff4b4b; color: white; cursor: pointer;">+10s ⏩</button>
                                    </div>
                                    <script>
                                        var audio = document.getElementById('audio-player');
                                        audio.playbackRate = {speed};
                                    </script>
                                </div>
                            """
                            st.markdown(audio_html, unsafe_allow_html=True)
                            
                            # Download Button
                            st.download_button(
                                label="📥 Download MP3",
                                data=audio_bytes,
                                file_name=f"pdf_audio_page_{current_display_page}.mp3",
                                mime="audio/mp3"
                            )
                        else:
                            st.warning("No text found on this page to read.")
                    except Exception as e:
                        st.error(f"Error generating audio: {e}")

if __name__ == "__main__":
    main()
