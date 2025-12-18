import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS
import io
import base64
from datetime import datetime
import uuid

# Try to import supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# --- Page Config ---
st.set_page_config(
    page_title="PDF Voice Reader",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Supabase Setup ---
SUPABASE_URL = "https://gkqjhfatsjormqthshri.supabase.co"
SUPABASE_KEY = "sb_publishable_KFJgk80J3P9If8PUo3UcSA_fDDQhW_4"

@st.cache_resource
def get_supabase_client():
    """Initialize Supabase client."""
    if SUPABASE_AVAILABLE:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except:
            return None
    return None

supabase = get_supabase_client()

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
</style>
""", unsafe_allow_html=True)

# --- Voice Configuration ---
VOICE_MAP = {
    "👩 Sarah (American)": {"tld": "com", "lang": "en"},
    "👩 Grace (British)": {"tld": "co.uk", "lang": "en"},
    "👩 Emma (American, Warm)": {"tld": "us", "lang": "en"},
    "👩 Zara (Canadian)": {"tld": "ca", "lang": "en"},
    "👩 Maya (Indian)": {"tld": "co.in", "lang": "en"},
    "👩 Lisa (Australian)": {"tld": "com.au", "lang": "en"},
    "👩 Sophia (South African)": {"tld": "co.za", "lang": "en"},
}

# --- Helper Functions ---
def get_pdf_data(file_bytes):
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = [page.get_text() for page in doc]
        return len(doc), pages_text
    except Exception as e:
        st.error(f"PDF Error: {e}")
        return 0, []

def render_page_as_image(file_bytes, page_num):
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        return pix.tobytes("png")
    except Exception as e:
        st.error(f"Render Error: {e}")
        return None

def generate_audio(text, lang='en', tld='com'):
    if not text or not text.strip():
        st.warning("No text to read on this page.")
        return None
    try:
        # Limit text to avoid gTTS timeout (max ~5000 chars at a time)
        text_to_read = text[:5000] if len(text) > 5000 else text
        tts = gTTS(text=text_to_read, lang=lang, tld=tld, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        st.error(f"Audio Error: {e}")
        return None

# --- Supabase Storage Functions ---
def upload_to_supabase(file_bytes, filename, bucket="pdfs"):
    """Upload file to Supabase Storage."""
    if not supabase:
        return None
    try:
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        result = supabase.storage.from_(bucket).upload(unique_name, file_bytes)
        public_url = supabase.storage.from_(bucket).get_public_url(unique_name)
        return {"name": unique_name, "url": public_url}
    except Exception as e:
        st.error(f"Upload error: {e}")
        return None

def list_files_from_supabase(bucket="pdfs"):
    """List all files from Supabase bucket."""
    if not supabase:
        return []
    try:
        files = supabase.storage.from_(bucket).list()
        return files if files else []
    except:
        return []

def delete_from_supabase(filename, bucket="pdfs"):
    """Delete file from Supabase Storage."""
    if not supabase:
        return False
    try:
        supabase.storage.from_(bucket).remove([filename])
        return True
    except:
        return False

def download_from_supabase(filename, bucket="pdfs"):
    """Download file from Supabase Storage."""
    if not supabase:
        return None
    try:
        data = supabase.storage.from_(bucket).download(filename)
        return data
    except:
        return None

def main():
    st.markdown("<h1 style='text-align:center; color:#4A90E2;'>🎧 PDF Voice Reader</h1>", unsafe_allow_html=True)
    
    # Show storage status
    if supabase:
        st.caption("☁️ Cloud storage connected (Supabase)")
    else:
        st.caption("💾 Using session storage (temporary)")

    # --- Session State ---
    if 'pdf_bytes' not in st.session_state:
        st.session_state.pdf_bytes = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'total_pages' not in st.session_state:
        st.session_state.total_pages = 0
    if 'pages_text' not in st.session_state:
        st.session_state.pages_text = []
    if 'current_filename' not in st.session_state:
        st.session_state.current_filename = ""

    # --- Sidebar ---
    with st.sidebar:
        st.header("🎤 Voice")
        selected_voice = st.selectbox("Choose Voice", list(VOICE_MAP.keys()))
        voice_data = VOICE_MAP[selected_voice]
        
        st.markdown("---")
        
        # --- Cloud Library ---
        st.header("☁️ Cloud Library")
        
        if supabase:
            files = list_files_from_supabase()
            if files:
                for f in files:
                    fname = f.get('name', 'Unknown')
                    with st.expander(f"📄 {fname[:25]}..."):
                        # Load button
                        if st.button(f"📂 Load", key=f"load_{fname}"):
                            data = download_from_supabase(fname)
                            if data:
                                st.session_state.pdf_bytes = data
                                total, texts = get_pdf_data(data)
                                st.session_state.total_pages = total
                                st.session_state.pages_text = texts
                                st.session_state.current_page = 0
                                st.session_state.current_filename = fname
                                st.rerun()
                        
                        # Delete button
                        if st.button(f"🗑️ Delete", key=f"del_{fname}"):
                            if delete_from_supabase(fname):
                                st.success("Deleted!")
                                st.rerun()
            else:
                st.caption("No files saved yet.")
        else:
            st.warning("Supabase not connected")

    # --- Main Content ---
    uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"])

    if uploaded_file:
        file_bytes = uploaded_file.read()
        
        if st.session_state.pdf_bytes != file_bytes:
            st.session_state.pdf_bytes = file_bytes
            total, texts = get_pdf_data(file_bytes)
            st.session_state.total_pages = total
            st.session_state.pages_text = texts
            st.session_state.current_page = 0
            st.session_state.current_filename = uploaded_file.name

        total_pages = st.session_state.total_pages
        pages_text = st.session_state.pages_text
        current_page = st.session_state.current_page

        if total_pages == 0:
            st.error("Could not read PDF.")
            return

        # File info + Save button
        col_info, col_save = st.columns([3, 1])
        with col_info:
            st.success(f"📄 **{st.session_state.current_filename}** • {total_pages} pages")
        with col_save:
            if supabase:
                if st.button("☁️ Save to Cloud"):
                    result = upload_to_supabase(st.session_state.pdf_bytes, st.session_state.current_filename)
                    if result:
                        st.success("✅ Saved!")

        # --- Layout ---
        col_pdf, col_ctrl = st.columns([1, 1], gap="large")

        with col_pdf:
            st.markdown(f"### 📖 Page {current_page + 1} / {total_pages}")
            img = render_page_as_image(st.session_state.pdf_bytes, current_page)
            if img:
                st.image(img, use_container_width=True)

        with col_ctrl:
            st.markdown("### 🎧 Controls")
            
            # Navigation
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("⏮️"): 
                st.session_state.current_page = 0
                st.rerun()
            if c2.button("◀️") and current_page > 0:
                st.session_state.current_page -= 1
                st.rerun()
            if c3.button("▶️") and current_page < total_pages - 1:
                st.session_state.current_page += 1
                st.rerun()
            if c4.button("⏭️"):
                st.session_state.current_page = total_pages - 1
                st.rerun()
            
            new_pg = st.slider("Page", 1, total_pages, current_page + 1) - 1
            if new_pg != current_page:
                st.session_state.current_page = new_pg
                st.rerun()

            st.markdown("---")
            
            # Read current page
            if st.button("🔊 Read This Page", type="primary", use_container_width=True):
                text = pages_text[current_page] if current_page < len(pages_text) else ""
                if text.strip():
                    with st.spinner("Generating..."):
                        audio = generate_audio(text, voice_data["lang"], voice_data["tld"])
                        if audio:
                            st.audio(audio, format="audio/mp3")
                            
                            # Save audio option
                            if supabase:
                                if st.button("☁️ Save Audio"):
                                    audio_name = f"audio_page_{current_page+1}.mp3"
                                    upload_to_supabase(audio.getvalue(), audio_name)

            st.markdown("---")
            
            # Custom range
            st.markdown("**📚 Custom Range:**")
            c_s, c_e = st.columns(2)
            start = c_s.number_input("From", 1, total_pages, 1)
            end = c_e.number_input("To", 1, total_pages, total_pages)
            
            if start <= end:
                if st.button(f"🎧 Read Pages {start}-{end}", use_container_width=True):
                    range_text = " ".join([pages_text[i] for i in range(start-1, end) if i < len(pages_text)])
                    if range_text:
                        with st.spinner("Generating..."):
                            audio = generate_audio(range_text, voice_data["lang"], voice_data["tld"])
                            if audio:
                                st.audio(audio, format="audio/mp3")
                                st.download_button("📥 Download", audio.getvalue(), f"pages_{start}_{end}.mp3", "audio/mp3")

            st.markdown("---")
            
            # Text preview
            st.markdown("### 📝 Text")
            text = pages_text[current_page] if current_page < len(pages_text) else ""
            st.text_area("Content", text[:2000], height=150, disabled=True)

    else:
        st.markdown("""
        <div style="background-color: #1A1E2A; padding: 30px; border-radius: 12px; text-align: center; border: 2px dashed #4A90E2;">
            <h3 style="color: #4A90E2;">📄 Upload a PDF to Start</h3>
            <p style="color: #A8B0C0;">Files are saved to cloud storage permanently.</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
