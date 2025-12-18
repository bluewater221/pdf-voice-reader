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
    """Generate audio with caching and retry."""
    if not text or not text.strip():
        return None
    
    # Limit text length
    text = text[:5000]
    
    # Retry up to 3 times with delay
    for attempt in range(3):
        try:
            tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
            audio = io.BytesIO()
            tts.write_to_fp(audio)
            audio.seek(0)
            return audio.getvalue()  # Return bytes for caching
        except Exception as e:
            if "429" in str(e):
                if attempt < 2:
                    time.sleep(2)  # Wait 2 seconds before retry
                    continue
                else:
                    st.error("⏳ Too many requests. Please wait 30 seconds and try again.")
                    return None
            else:
                st.error(f"Audio Error: {e}")
                return None
    return None

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
                for f in files:
                    name = f.get('name', '')
                    with st.expander(f"📄 {name[:20]}"):
                        if st.button("📂 Load", key=f"l_{name}"):
                            data = cloud_download(name)
                            if data:
                                st.session_state.pdf = data
                                p, t = get_pdf_text(data)
                                st.session_state.pages = p
                                st.session_state.texts = t
                                st.session_state.page = 0
                                st.session_state.fname = name
                                st.rerun()
                        if st.button("🗑️ Delete", key=f"d_{name}"):
                            if cloud_delete(name):
                                st.success("Deleted!")
                                st.rerun()
            else:
                st.caption("No files saved")
        else:
            st.warning("Cloud not connected")

    # Upload
    file = st.file_uploader("📄 Upload PDF", type=["pdf"])
    
    if file:
        data = file.read()
        if st.session_state.pdf != data:
            st.session_state.pdf = data
            p, t = get_pdf_text(data)
            st.session_state.pages = p
            st.session_state.texts = t
            st.session_state.page = 0
            st.session_state.fname = file.name
        
        pages = st.session_state.pages
        texts = st.session_state.texts
        page = st.session_state.page
        
        if pages == 0:
            st.error("Cannot read PDF")
            return
        
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
        
        with col2:
            st.subheader("🎧 Controls")
            
            # Nav
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("⏮️"): st.session_state.page = 0; st.rerun()
            if c2.button("◀️") and page > 0: st.session_state.page -= 1; st.rerun()
            if c3.button("▶️") and page < pages-1: st.session_state.page += 1; st.rerun()
            if c4.button("⏭️"): st.session_state.page = pages-1; st.rerun()
            
            new_pg = st.slider("Page", 1, pages, page + 1) - 1
            if new_pg != page: st.session_state.page = new_pg; st.rerun()
            
            st.markdown("---")
            
            # Read
            if st.button("🔊 Read This Page", type="primary", use_container_width=True):
                text = texts[page] if page < len(texts) else ""
                if text.strip():
                    with st.spinner("Generating..."):
                        audio = make_audio(text, voice["lang"], voice["tld"])
                        if audio:
                            st.audio(audio, format="audio/mp3")
                else:
                    st.warning("No text on this page")
            
            st.markdown("---")
            
            # Range
            r1, r2 = st.columns(2)
            start = r1.number_input("From", 1, pages, 1)
            end = r2.number_input("To", 1, pages, pages)
            
            if start <= end:
                if st.button(f"🎧 Read {start}-{end}", use_container_width=True):
                    range_text = " ".join([texts[i] for i in range(start-1, end) if i < len(texts)])
                    if range_text.strip():
                        with st.spinner("Generating..."):
                            audio = make_audio(range_text, voice["lang"], voice["tld"])
                            if audio:
                                st.audio(audio, format="audio/mp3")
                                st.download_button("📥 Download", audio, "audio.mp3", "audio/mp3")
            
            st.markdown("---")
            st.subheader("📝 Text")
            st.text_area("", texts[page][:1500] if page < len(texts) else "", height=150, disabled=True)
    
    else:
        st.info("👆 Upload a PDF to start")

if __name__ == "__main__":
    main()
