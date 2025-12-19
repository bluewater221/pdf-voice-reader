import streamlit as st
import fitz  # PyMuPDF
import edge_tts
import asyncio
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

# --- Voices (Edge TTS voices) ---
VOICES = {
    "👩 Jenny (American)": "en-US-JennyNeural",
    "👩 Aria (American)": "en-US-AriaNeural",
    "👨 Guy (American)": "en-US-GuyNeural",
    "👩 Sonia (British)": "en-GB-SoniaNeural",
    "👩 Neerja (Indian)": "en-IN-NeerjaNeural",
    "👩 Natasha (Australian)": "en-AU-NatashaNeural",
    "👩 Xiaoxiao (Chinese)": "zh-CN-XiaoxiaoNeural",
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

async def _generate_audio(text, voice):
    """Async function to generate audio using edge-tts."""
    communicate = edge_tts.Communicate(text, voice)
    audio_data = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])
    audio_data.seek(0)
    return audio_data.getvalue()

def make_audio(text, voice):
    """Generate audio using Edge TTS. Returns (audio_bytes, status_code)."""
    if not text or not text.strip():
        return None, 400
    
    # Limit text length
    text = text[:5000]
    
    try:
        audio = asyncio.run(_generate_audio(text, voice))
        return audio, 200
    except Exception as e:
        st.error(f"TTS Error: {e}")
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
            # === PDF NAVIGATION SECTION ===
            st.subheader("📑 PDF Navigation")
            
            # Page slider
            if pages > 1:
                new_pg = st.slider("Go to page", 1, pages, page + 1, key="nav_slider") - 1
                if new_pg != page: 
                    st.session_state.page = new_pg
                    st.rerun()
            
            # Navigation buttons
            nav1, nav2, nav3, nav4 = st.columns(4)
            if nav1.button("⏪", help="First page", key="nav_first"): 
                st.session_state.page = 0; st.rerun()
            if nav2.button("◀️", help="Previous page", key="nav_prev") and page > 0: 
                st.session_state.page -= 1; st.rerun()
            if nav3.button("▶️", help="Next page", key="nav_next") and page < pages-1: 
                st.session_state.page += 1; st.rerun()
            if nav4.button("⏩", help="Last page", key="nav_last"): 
                st.session_state.page = pages-1; st.rerun()
            
            st.markdown("---")
            
            # === AUDIO SECTION ===
            st.subheader("🎧 Audio Reader")
            
            # Read This Page Button
            if st.button("🔊 Read This Page", type="primary", use_container_width=True):
                text = texts[page] if page < len(texts) else ""
                
                if len(text) > 5000:
                    st.warning(f"⚠️ Text is long ({len(text)} chars). Reading first 5000 chars.")
                
                if text.strip():
                    with st.spinner(f"📖 Generating audio for Page {page + 1}..."):
                        audio, status = make_audio(text, voice)
                        
                        if audio:
                            st.session_state.audio_data = audio
                            st.session_state.reading_page = page + 1
                            st.rerun()  # Rerun to show persistent player only
                        else:
                            st.error(f"❌ TTS failed")
                else:
                    st.warning("No text on this page")

            
            st.markdown("---")
            
            # Range Reading Section
            st.markdown("**📚 Read Multiple Pages**")
            r1, r2 = st.columns(2)
            start = r1.number_input("From page", 1, pages, 1, key="range_start")
            end = r2.number_input("To page", 1, pages, min(pages, 5), key="range_end")
            
            if start <= end:
                if st.button(f"🎧 Read Pages {start} to {end}", use_container_width=True, key="range_read"):
                    # Generate audio page by page with progress
                    all_audio = io.BytesIO()
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total_pages = end - start + 1
                    for i, pg in enumerate(range(start - 1, end)):
                        if pg < len(texts) and texts[pg].strip():
                            status_text.info(f"📖 Reading Page {pg + 1} of {start}-{end}...")
                            progress_bar.progress((i + 1) / total_pages)
                            
                            audio_chunk, status = make_audio(texts[pg], voice)
                            if audio_chunk:
                                all_audio.write(audio_chunk)
                    
                    all_audio.seek(0)
                    audio_data = all_audio.getvalue()
                    
                    if audio_data:
                        st.session_state.audio_data = audio_data
                        st.session_state.reading_page = f"{start}-{end}"
                        progress_bar.empty()
                        status_text.empty()
                        st.rerun()  # Rerun to show persistent player only
                    else:
                        status_text.error("❌ No audio generated")

            # === SINGLE AUDIO PLAYER (no duplicates) ===
            if 'audio_data' in st.session_state and st.session_state.audio_data:
                st.markdown("---")
                reading_info = st.session_state.get('reading_page', 'audio')
                st.success(f"🎧 Now Playing: Page {reading_info}")
                st.audio(st.session_state.audio_data, format="audio/mp3")
                st.download_button("📥 Download MP3", st.session_state.audio_data, "audio.mp3", "audio/mp3", key="dl_audio")

            st.markdown("---")
            st.subheader("📝 Text")
            st.text_area("", texts[page][:1500] if page < len(texts) else "", height=150, disabled=True)
    
    else:
        st.info("👆 Upload a PDF to start (or load from cloud)")

if __name__ == "__main__":
    main()
