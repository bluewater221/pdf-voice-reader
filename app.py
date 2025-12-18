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

def extract_text_from_pdf(file):
    """Extracts text from a PDF file."""
    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = []
        for page in doc:
            text.append(page.get_text())
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return []

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

    with st.sidebar:
        st.header("📂 Upload & Settings")
        uploaded_file = st.file_uploader("Drop your PDF here", type=["pdf"])
        
        st.markdown("---")
        st.subheader("🎧 Voice Controls")
        speed = st.select_slider("Playback Speed", options=[0.5, 0.75, 1.0, 1.25, 1.5, 2.0], value=1.0)
        
        st.markdown("---")
        st.info("💡 **Tip:** Use the sidebar to control playback speed and navigate pages.")

    if uploaded_file:
        # Extract Text
        with st.spinner("📄 Extracting text from PDF..."):
            pages_text = extract_text_from_pdf(uploaded_file)
        
        if not pages_text:
            st.error("Could not extract text from this PDF.")
            return

        # Page Selection
        col1, col2 = st.columns([1, 3])
        with col1:
            page_number = st.number_input("Page", min_value=1, max_value=len(pages_text), value=1)
        with col2:
            st.markdown(f"**of {len(pages_text)} pages**")
            
        current_text = pages_text[page_number - 1]
        
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
                            file_name=f"pdf_audio_page_{page_number}.mp3",
                            mime="audio/mp3"
                        )
                    else:
                        st.warning("No text found on this page to read.")
                except Exception as e:
                    st.error(f"Error generating audio: {e}")

if __name__ == "__main__":
    main()
