import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS
import io
import base64
import re

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
    /* Dark Theme */
    .stApp {
        background-color: #0F1419;
        color: #E8E8E8;
    }
    h1, h2, h3, p, label { color: #E8E8E8 !important; }
    
    /* Line Container */
    .line-container {
        max-height: 400px;
        overflow-y: auto;
        background-color: #1A1E2A;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #2E3847;
    }
    
    /* Normal Line */
    .text-line {
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 6px;
        font-size: 14px;
        line-height: 1.6;
        color: #A8B0C0;
        background-color: #252D3D;
        border-left: 3px solid transparent;
    }
    
    /* Highlighted (Currently Reading) Line */
    .text-line.current {
        background-color: #4A90E2;
        color: white;
        font-weight: 600;
        border-left: 3px solid #2ECC71;
        box-shadow: 0 2px 8px rgba(74, 144, 226, 0.3);
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #4A90E2;
        color: white;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #2E5C8A;
    }
    
    /* PDF Viewer Iframe */
    .pdf-viewer {
        width: 100%;
        height: 500px;
        border: 1px solid #2E3847;
        border-radius: 8px;
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
def extract_lines_from_pdf(file_bytes):
    """Extracts text from PDF and splits into lines/sentences."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text = ""
        for page in doc:
            all_text += page.get_text() + "\n"
        
        # Split into sentences/lines (by period, newline, or fixed length)
        lines = re.split(r'(?<=[.!?])\s+|\n+', all_text)
        # Filter empty lines and strip whitespace
        lines = [line.strip() for line in lines if line.strip()]
        return lines
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return []

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

def render_lines_with_highlight(lines, current_idx):
    """Renders all lines with the current line highlighted."""
    html = '<div class="line-container">'
    for i, line in enumerate(lines):
        # Truncate long lines for display (keep full in title for tooltip)
        display_line = line[:150] + "..." if len(line) > 150 else line
        css_class = "text-line current" if i == current_idx else "text-line"
        html += f'<div class="{css_class}" title="{line}">{i+1}. {display_line}</div>'
    html += '</div>'
    return html

def main():
    st.markdown("<h1 style='text-align:center; color:#4A90E2;'>🎧 PDF Voice Reader</h1>", unsafe_allow_html=True)
    st.caption("Upload a PDF, navigate line-by-line, and listen with text-to-speech.")
    st.markdown("---")

    # --- Session State Initialization ---
    if 'lines' not in st.session_state:
        st.session_state.lines = []
    if 'current_line_index' not in st.session_state:
        st.session_state.current_line_index = 0
    if 'is_playing' not in st.session_state:
        st.session_state.is_playing = False
    if 'pdf_bytes' not in st.session_state:
        st.session_state.pdf_bytes = None

    # --- Sidebar: Voice Selection ---
    with st.sidebar:
        st.header("🎤 Voice")
        selected_voice = st.selectbox("Choose Voice", list(VOICE_MAP.keys()))
        voice_data = VOICE_MAP[selected_voice]

    # --- File Upload ---
    uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"], label_visibility="collapsed")

    if uploaded_file:
        # Store PDF bytes and extract lines (only on new upload)
        file_bytes = uploaded_file.read()
        if st.session_state.pdf_bytes != file_bytes:
            st.session_state.pdf_bytes = file_bytes
            st.session_state.lines = extract_lines_from_pdf(file_bytes)
            st.session_state.current_line_index = 0
            st.session_state.is_playing = False

        lines = st.session_state.lines
        current_idx = st.session_state.current_line_index
        total_lines = len(lines)

        if total_lines == 0:
            st.warning("No text could be extracted from this PDF.")
            return

        # --- Split Layout: Page Text | Controls ---
        col_pdf, col_controls = st.columns([1, 1], gap="large")

        with col_pdf:
            st.markdown("### 📖 Document Text")
            st.info(f"📄 **{uploaded_file.name}** • {len(lines)} sentences extracted")
            
            # Show current line prominently
            current_text = lines[current_idx] if current_idx < len(lines) else ""
            st.markdown(f"""
                <div style="background-color: #4A90E2; padding: 20px; border-radius: 10px; margin: 10px 0;">
                    <p style="color: white; font-size: 18px; font-weight: 600; margin: 0;">
                        📍 Line {current_idx + 1}: {current_text[:200]}{'...' if len(current_text) > 200 else ''}
                    </p>
                </div>
            """, unsafe_allow_html=True)

        with col_controls:
            st.markdown("### 🎧 Reading Controls")
            
            # Status
            st.info(f"📍 **Line {current_idx + 1} of {total_lines}**")
            
            # Navigation Buttons
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("⏮️ First"):
                    st.session_state.current_line_index = 0
                    st.rerun()
            with c2:
                if st.button("◀️ Prev"):
                    if current_idx > 0:
                        st.session_state.current_line_index -= 1
                        st.rerun()
            with c3:
                if st.button("▶️ Next"):
                    if current_idx < total_lines - 1:
                        st.session_state.current_line_index += 1
                        st.rerun()
            with c4:
                if st.button("⏭️ Last"):
                    st.session_state.current_line_index = total_lines - 1
                    st.rerun()
            
            # Line Slider
            new_idx = st.slider("Jump to Line", 1, total_lines, current_idx + 1) - 1
            if new_idx != current_idx:
                st.session_state.current_line_index = new_idx
                st.rerun()

            st.markdown("---")

            # Play Current Line
            if st.button("🔊 Play Current Line", use_container_width=True):
                current_text = lines[current_idx]
                audio = generate_audio(current_text, voice_data["lang"], voice_data["tld"])
                if audio:
                    st.audio(audio, format="audio/mp3")
                else:
                    st.warning("Could not generate audio for this line.")
            
            # Read FULL PDF
            st.markdown("---")
            st.markdown("### 📖 Read Full Document")
            
            if st.button("🎧 Generate Full Audio (All Pages)", type="primary", use_container_width=True):
                with st.spinner("⏳ Generating audio for entire PDF... This may take a few minutes for large documents."):
                    # Combine all lines into full text
                    full_text = " ".join(lines)
                    
                    # Show progress
                    st.info(f"Processing {len(full_text)} characters (~{len(full_text)//150} seconds of audio)")
                    
                    # Generate audio for full text
                    full_audio = generate_audio(full_text, voice_data["lang"], voice_data["tld"])
                    
                    if full_audio:
                        st.success("✅ Full audio generated successfully!")
                        st.audio(full_audio, format="audio/mp3")
                        
                        # Download button
                        st.download_button(
                            "📥 Download Full Audio (MP3)",
                            full_audio.getvalue(),
                            file_name="full_pdf_audio.mp3",
                            mime="audio/mp3",
                            use_container_width=True
                        )
                    else:
                        st.error("Could not generate audio. The PDF may be too large or contain no readable text.")
            
            st.caption("💡 Tip: Full audio generation may take 1-5 minutes for large PDFs.")
            
            st.markdown("---")
            
            # Highlighted Lines Display
            st.markdown("### 📝 Text (Current Line Highlighted)")
            lines_html = render_lines_with_highlight(lines, current_idx)
            st.markdown(lines_html, unsafe_allow_html=True)

    else:
        # No file uploaded - show instructions
        st.markdown("""
        <div style="background-color: #1A1E2A; padding: 30px; border-radius: 12px; text-align: center; border: 2px dashed #4A90E2;">
            <h3 style="color: #4A90E2;">📄 Upload a PDF to Start</h3>
            <p style="color: #A8B0C0;">
                1. Click "Browse files" or drag & drop a PDF.<br>
                2. Use the controls to navigate line-by-line.<br>
                3. Click "Play Current Line" to hear the text read aloud.
            </p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
