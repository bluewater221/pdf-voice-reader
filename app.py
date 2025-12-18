import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS
import io
import uuid

# Supabase import
try:
    from supabase import create_client
    SUPABASE_OK = True
except:
    SUPABASE_OK = False

# --- Page Config ---
st.set_page_config(
    page_title="PDF Voice Reader",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Supabase ---
SUPABASE_URL = "https://gkqjhfatsjormqthshri.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdrcWpoZmF0c2pvcm1xdGhzaHJpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYwNDk4MDYsImV4cCI6MjA4MTYyNTgwNn0.z6Rn29XIRTicPxL99hc0i9TB2ur7Ek7EgNTyxQXH5xs"

@st.cache_resource
def get_supabase():
    if SUPABASE_OK:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except:
            return None
    return None

supabase = get_supabase()

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
    "👩 Mei (Chinese)": {"tld": "com", "lang": "zh-CN"},
}

# --- Helper Functions ---
def get_pdf_text(file_bytes):
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return len(doc), [page.get_text() for page in doc]
    except Exception as e:
        st.error(f"PDF Error: {e}")
        return 0, []

def get_page_image(file_bytes, page_num):
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pix = doc.load_page(page_num).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        return pix.tobytes("png")
    except:
        return None

import time

@st.cache_data(show_spinner=False)
def make_audio(text, lang, tld):
    """Generate audio. Returns (audio_bytes, status_code)."""
    if not text or not text.strip():
        return None, 400
    
    # Limit text length
    text = text[:5000]
    
    # Retry logic with exponential backoff
    max_retries = 3
    for attempt in range(max_retries):
        try:
            tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
            audio = io.BytesIO()
            tts.write_to_fp(audio)
            audio.seek(0)
            return audio.getvalue(), 200
        except Exception as e:
            if "429" in str(e):
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                else:
                    # Return 429 status so UI can handle cooldown
                    return None, 429
            else:
                st.error(f"Audio Error: {e}")
                return None, 500
    return None, 500

# --- Supabase Functions ---
def cloud_upload(data, name, bucket="pdfs"):
    if not supabase: return None
    try:
        fname = f"{uuid.uuid4().hex}_{name}"
        supabase.storage.from_(bucket).upload(fname, data)
        return fname
    except Exception as e:
        st.error(f"Upload Error: {e}")
        return None

def cloud_list(bucket="pdfs"):
    if not supabase: return []
    try:
        return supabase.storage.from_(bucket).list() or []
    except:
        return []

def cloud_download(name, bucket="pdfs"):
    if not supabase: 
        st.error("Supabase not connected")
        return None
    try:
        data = supabase.storage.from_(bucket).download(name)
        return data
    except Exception as e:
        st.error(f"Download Error: {e}")
        return None

def cloud_delete(name, bucket="pdfs"):
    if not supabase: return False
    try:
        supabase.storage.from_(bucket).remove([name])
        return True
    except:
        return False

# --- Main ---
def main():
    st.title("🎧 PDF Voice Reader")
    
    if supabase:
        st.caption("☁️ Cloud storage connected")
    
    # Session state
    if 'pdf' not in st.session_state: st.session_state.pdf = None
    if 'page' not in st.session_state: st.session_state.page = 0
    if 'pages' not in st.session_state: st.session_state.pages = 0
    if 'texts' not in st.session_state: st.session_state.texts = []
    if 'fname' not in st.session_state: st.session_state.fname = ""

    # Sidebar
    with st.sidebar:
        st.header("🎤 Voice")
        voice_name = st.selectbox("Select", list(VOICES.keys()))
        voice = VOICES[voice_name]
        
        st.markdown("---")
        st.header("☁️ Cloud Library")
        
        if supabase:
            files = cloud_list()
            if files:
                # Create a list of filenames
                file_names = [f.get('name') for f in files if f.get('name')]
                
                if file_names:
                    selected_file = st.selectbox("Select File", file_names)
                    
                    col_l, col_d = st.columns(2)
                    
                    if col_l.button("📂 Load", use_container_width=True):
                        with st.spinner("Downloading..."):
                            try:
                                data = cloud_download(selected_file)
                                
                                if data:
                                    try:
                                        st.session_state.pdf = data
                                        p, t = get_pdf_text(data)
                                        if p > 0:
                                            st.session_state.pages = p
                                            st.session_state.texts = t
                                            st.session_state.page = 0
                                            st.session_state.fname = selected_file
                                            st.success("Loaded!")
                                            time.sleep(0.5)
                                            st.rerun()
                                        else:
                                            st.error("Invalid PDF content")
                                    except Exception as ex:
                                        st.error(f"Error parsing PDF: {ex}")
                                else:
                                    st.error("Failed to download file")
                                        
                            except Exception as e:
                                st.error(f"Error: {e}")
                    
                    if col_d.button("🗑️ Delete", use_container_width=True):
                        if cloud_delete(selected_file):
                            st.success("Deleted!")
                            st.rerun()
                else:
                    st.caption("No files found")
            else:
                st.caption("Library is empty")
        else:
            st.warning("Cloud not connected")

    # Upload
    file = st.file_uploader("📄 Upload PDF", type=["pdf"])
    
    if file:
        data = file.read()
        # Only update if different file to avoid reset on rerun
        if st.session_state.pdf != data:
            st.session_state.pdf = data
            p, t = get_pdf_text(data)
            st.session_state.pages = p
            st.session_state.texts = t
            st.session_state.page = 0
            st.session_state.fname = file.name

    # Viewer (Checks Session State, not just Uploader)
    if st.session_state.pdf:
        # Initialize Audio State
        if 'audio_data' not in st.session_state:
            st.session_state.audio_data = None
            
        pages = st.session_state.pages
        texts = st.session_state.texts
        page = st.session_state.page
        
        if pages == 0:
            st.error("Cannot read PDF") 
            
        # Info + Save
        c1, c2 = st.columns([3, 1])
        c1.success(f"📄 {st.session_state.fname} - {pages} pages")
        if supabase and c2.button("☁️ Save"):
            if cloud_upload(st.session_state.pdf, st.session_state.fname):
                st.success("Saved!")
        
        # Layout
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"📖 Page {page + 1}/{pages}")
            img = get_page_image(st.session_state.pdf, page)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.warning("Cannot render page")
        
        with col2:
            st.subheader("🎧 Controls")
            
            # Nav
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("⏮️"): st.session_state.page = 0; st.session_state.audio_data = None; st.rerun()
            if c2.button("◀️") and page > 0: st.session_state.page -= 1; st.session_state.audio_data = None; st.rerun()
            if c3.button("▶️") and page < pages-1: st.session_state.page += 1; st.session_state.audio_data = None; st.rerun()
            if c4.button("⏭️"): st.session_state.page = pages-1; st.session_state.audio_data = None; st.rerun()
            
            new_pg = st.slider("Page", 1, pages, page + 1) - 1
            if new_pg != page: st.session_state.page = new_pg; st.session_state.audio_data = None; st.rerun()
            
            st.markdown("---")
            
            # TTS Cooldown Logic
            if 'tts_limit' not in st.session_state:
                st.session_state.tts_limit = 0
            
            remaining = int(st.session_state.tts_limit - time.time())
            is_cooldown = remaining > 0
            
            btn_text = f"⏳ Ready in {remaining}s" if is_cooldown else "🔊 Read This Page"
            
            if st.button(btn_text, disabled=is_cooldown, type="primary", use_container_width=True):
                text = texts[page] if page < len(texts) else ""
                if text.strip():
                    with st.spinner("Generating..."):
                        audio, status = make_audio(text, voice["lang"], voice["tld"])
                        
                        if audio:
                            st.session_state.audio_data = audio
                        elif status == 429:
                            st.session_state.tts_limit = time.time() + 20 # Reduced to 20s
                            st.rerun()
                else:
                    st.warning("No text on this page")
            
            st.markdown("---")
            
            # Range
            r1, r2 = st.columns(2)
            start = r1.number_input("From", 1, pages, 1)
            end = r2.number_input("To", 1, pages, pages)
            
            if start <= end:
                range_btn_text = f"⏳ Ready in {remaining}s" if is_cooldown else f"🎧 Read {start}-{end}"
                
                if st.button(range_btn_text, disabled=is_cooldown, use_container_width=True, key="range_read"):
                    range_text = " ".join([texts[i] for i in range(start-1, end) if i < len(texts)])
                    if range_text.strip():
                        with st.spinner("Generating..."):
                            audio, status = make_audio(range_text, voice["lang"], voice["tld"])
                            if audio:
                                st.session_state.audio_data = audio
                            elif status == 429:
                                st.session_state.tts_limit = time.time() + 20 # Reduced to 20s
                                st.rerun()

            # Persistent Audio Player
            if st.session_state.audio_data:
                st.success("✅ Ready to play!")
                st.audio(st.session_state.audio_data, format="audio/mp3")
                st.download_button("📥 Download MP3", st.session_state.audio_data, "audio.mp3", "audio/mp3")

            st.markdown("---")
            st.subheader("📝 Text")
            st.text_area("", texts[page][:1500] if page < len(texts) else "", height=150, disabled=True)
    
    else:
        st.info("👆 Upload a PDF to start (or load from cloud)")

if __name__ == "__main__":
    main()
