import streamlit as st
import fitz  # PyMuPDF
import edge_tts
import asyncio
import io
import re
import time
import sys

# Fix asyncio issues on Windows
if sys.platform == "win32":
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Supabase import
try:
    from supabase import create_client
    SUPABASE_OK = True
except ImportError:
    SUPABASE_OK = False

# --- Page Config ---
st.set_page_config(
    page_title="PDF Voice Reader",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Supabase (with graceful fallback) ---
def get_secret(key, default=""):
    """Safely get a secret, returning default if not found."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

@st.cache_resource
def get_supabase():
    """Initialize Supabase client with error handling."""
    if not SUPABASE_OK:
        return None
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.warning(f"Cloud storage unavailable: {e}")
        return None

supabase = get_supabase()

# --- CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid #262730;
        background-color: #262730;
        color: #FFFFFF;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        border-color: #4A90E2;
        color: #4A90E2;
        transform: translateY(-1px);
    }
    
    /* Primary Button (Read Page) */
    div[data-testid="stColumn"] > div > div > div > div > button[kind="primary"] {
        background: linear-gradient(90deg, #4A90E2 0%, #007ACC 100%);
        border: none;
        color: white;
    }
    
    /* Expander / Cards */
    .streamlit-expanderHeader {
        background-color: #1C1F26;
        border-radius: 8px;
    }
    
    .streamlit-expanderContent {
        background-color: #1C1F26;
        border-bottom-left-radius: 8px;
        border-bottom-right-radius: 8px;
    }

    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
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
def get_pdf_text(file_bytes, ftype="pdf"):
    """Extract text and TOC from PDF/EPUB."""
    try:
        doc = fitz.open(stream=file_bytes, filetype=ftype)
        toc = doc.get_toc()
        texts = [page.get_text() for page in doc]
        doc.close()
        return len(texts), texts, toc
    except Exception as e:
        st.error(f"Document Error: {e}")
        return 0, [], []

def get_page_image(file_bytes, page_num, ftype="pdf"):
    """Render a page as PNG image."""
    try:
        doc = fitz.open(stream=file_bytes, filetype=ftype)
        if page_num >= len(doc):
            doc.close()
            return None
        pix = doc.load_page(page_num).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception:
        return None

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
    """Generate audio using Edge TTS with proper error handling."""
    if not text or not text.strip():
        return None, 400
    
    # Limit text length to avoid timeout
    text = text[:5000]
    
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        audio = loop.run_until_complete(_generate_audio(text, voice))
        return audio, 200
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None, 500

# --- Smart Text Cleaning ---
def clean_text(text):
    """Clean text by removing page numbers, headers, footers, and artifacts."""
    if not text:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Regex for common page number patterns
    page_num_pattern = re.compile(r'^\s*(?:page\s*)?(\d+)(?:\s*of\s*\d+)?\s*[-]?\s*$', re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Skip page numbers
        if page_num_pattern.match(stripped):
            continue
        
        # Skip short non-alphanumeric lines (likely artifacts)
        if len(stripped) < 4 and stripped and not stripped[0].isalnum():
            continue
        
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

# --- Cloud Storage (with error handling) ---
def cloud_upload(file_bytes, filename, bucket="pdfs"):
    """Upload file to Supabase storage."""
    if not supabase:
        return None
    try:
        files = supabase.storage.from_(bucket).list()
        if any(f.get('name') == filename for f in (files or [])):
            st.toast(f"File exists: {filename}", icon="📂")
            return filename
        
        supabase.storage.from_(bucket).upload(filename, file_bytes)
        return filename
    except Exception as e:
        st.error(f"Upload Error: {e}")
        return None

def cloud_list(bucket="pdfs"):
    """List files in Supabase storage."""
    if not supabase:
        return []
    try:
        result = supabase.storage.from_(bucket).list()
        return result if result else []
    except Exception:
        return []

def cloud_download(name, bucket="pdfs"):
    """Download file from Supabase storage."""
    if not supabase:
        return None
    try:
        return supabase.storage.from_(bucket).download(name)
    except Exception as e:
        st.error(f"Download Error: {e}")
        return None

def cloud_delete(name, bucket="pdfs"):
    """Delete file from Supabase storage."""
    if not supabase:
        return False
    try:
        supabase.storage.from_(bucket).remove([name])
        return True
    except Exception:
        return False

# --- Navigation Callbacks ---
def nav_page(delta):
    """Navigate to next/previous page."""
    new_p = st.session_state.page + delta
    if 0 <= new_p < st.session_state.pages:
        st.session_state.page = new_p
        st.session_state.audio_data = None

def set_page_from_input():
    """Set page from number input."""
    if 'nav_goto' in st.session_state:
        new_page = st.session_state.nav_goto - 1
        if 0 <= new_page < st.session_state.pages:
            st.session_state.page = new_page
            st.session_state.audio_data = None

# --- Initialize Session State ---
def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        'pdf': None,
        'ftype': 'pdf',
        'page': 0,
        'pages': 0,
        'texts': [],
        'toc': [],
        'fname': '',
        'audio_data': None,
        'reading_page': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- Main Application ---
def main():
    st.title("🎧 PDF Voice Reader")
    st.caption("⚡ Version 4.0 - Improved Stability")
    
    # Show connection status
    if supabase:
        st.caption("☁️ Cloud storage connected")
    else:
        st.caption("📁 Local mode (cloud unavailable)")
    
    # Initialize session state
    init_session_state()
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("🎤 Voice Settings")
        voice_name = st.selectbox("Select Voice", list(VOICES.keys()))
        voice = VOICES[voice_name]
        
        smart_clean = st.checkbox("✨ Smart Cleaning", value=True, 
                                   help="Removes headers, footers & page numbers")
        
        # Chapter Navigation
        if st.session_state.toc:
            st.markdown("---")
            st.header("📌 Chapters")
            chapter_map = {
                f"{item[1][:30]}... (Pg {item[2]})" if len(item[1]) > 30 else f"{item[1]} (Pg {item[2]})": item[2] - 1
                for item in st.session_state.toc if item[2] > 0
            }
            if chapter_map:
                options = ["Select chapter..."] + list(chapter_map.keys())
                sel_chap = st.selectbox("Jump to Chapter", options)
                if sel_chap != "Select chapter..." and chapter_map.get(sel_chap, -1) != st.session_state.page:
                    st.session_state.page = chapter_map[sel_chap]
                    st.session_state.audio_data = None
                    st.rerun()
        
        # Cloud Library
        st.markdown("---")
        st.header("☁️ Cloud Library")
        
        if supabase:
            files = cloud_list()
            file_names = [f.get('name') for f in files if f.get('name')]
            
            if file_names:
                selected_file = st.selectbox("Select File", file_names)
                
                col_l, col_d = st.columns(2)
                
                if col_l.button("📂 Load", use_container_width=True):
                    with st.spinner("Downloading..."):
                        data = cloud_download(selected_file)
                        if data:
                            ftype = selected_file.split('.')[-1].lower() if '.' in selected_file else "pdf"
                            if ftype not in ["pdf", "epub"]:
                                ftype = "pdf"
                            
                            p, t, toc = get_pdf_text(data, ftype)
                            if p > 0:
                                st.session_state.pdf = data
                                st.session_state.ftype = ftype
                                st.session_state.pages = p
                                st.session_state.texts = t
                                st.session_state.toc = toc
                                st.session_state.page = 0
                                st.session_state.fname = selected_file
                                st.session_state.audio_data = None
                                st.success("Loaded!")
                                time.sleep(0.3)
                                st.rerun()
                            else:
                                st.error("Could not read document")
                        else:
                            st.error("Download failed")
                
                if col_d.button("🗑️ Delete", use_container_width=True):
                    if cloud_delete(selected_file):
                        st.success("Deleted!")
                        st.rerun()
            else:
                st.caption("No files in library")
        else:
            st.info("Cloud storage not configured")
    
    # --- Main Content ---
    # File Uploader
    file = st.file_uploader("📄 Upload PDF or EPUB", type=["pdf", "epub"])
    
    if file:
        data = file.read()
        # Only process if new file
        if st.session_state.pdf != data:
            ftype = file.name.split('.')[-1].lower() if '.' in file.name else "pdf"
            if ftype not in ["pdf", "epub"]:
                ftype = "pdf"
            
            p, t, toc = get_pdf_text(data, ftype)
            if p > 0:
                st.session_state.pdf = data
                st.session_state.ftype = ftype
                st.session_state.pages = p
                st.session_state.texts = t
                st.session_state.toc = toc
                st.session_state.page = 0
                st.session_state.fname = file.name
                st.session_state.audio_data = None
            else:
                st.error("Could not read the uploaded document")
    
    # --- Document Viewer ---
    if st.session_state.pdf and st.session_state.pages > 0:
        pages = st.session_state.pages
        texts = st.session_state.texts
        page = st.session_state.page
        ftype = st.session_state.ftype
        
        # --- Audio Player (if audio exists) ---
        if st.session_state.audio_data:
            reading_info = st.session_state.reading_page or "audio"
            
            ac1, ac2, ac3 = st.columns([3, 1, 1])
            ac1.success(f"🎧 Playing: Page {reading_info}")
            ac2.download_button("📥 MP3", st.session_state.audio_data, "audio.mp3", "audio/mp3", key="dl_audio")
            
            if supabase and ac3.button("☁️ Save MP3"):
                safe_fname = re.sub(r'[^\w\-_\.]', '_', st.session_state.fname)
                mp3_name = f"audio_{safe_fname}_{reading_info}.mp3"
                if cloud_upload(st.session_state.audio_data, mp3_name):
                    st.toast(f"Saved: {mp3_name}", icon="☁️")
            
            st.audio(st.session_state.audio_data, format="audio/mp3")
            st.markdown("---")
        
        # --- Navigation Controls ---
        c_nav, c_act = st.columns([2, 1])
        
        with c_nav:
            n1, n2, n3 = st.columns([1, 1.5, 1])
            n1.button("◀ Prev", on_click=nav_page, args=(-1,), disabled=(page <= 0), use_container_width=True)
            n2.number_input("Page", 1, pages, page + 1, key="nav_goto", label_visibility="collapsed", on_change=set_page_from_input)
            n3.button("Next ▶", on_click=nav_page, args=(1,), disabled=(page >= pages - 1), use_container_width=True)
        
        with c_act:
            if st.button("🔊 Read Page", type="primary", use_container_width=True):
                text = texts[page] if page < len(texts) else ""
                if smart_clean:
                    text = clean_text(text)
                
                if text.strip():
                    with st.spinner("Generating audio..."):
                        audio, status = make_audio(text, voice)
                        if audio:
                            st.session_state.audio_data = audio
                            st.session_state.reading_page = page + 1
                            st.rerun()
                        else:
                            st.error("Failed to generate audio. Please try again.")
                else:
                    st.warning("No readable text on this page")
        
        # --- Page Display ---
        st.caption(f"📄 Page {page + 1} of {pages} • {st.session_state.fname}")
        
        img = get_page_image(st.session_state.pdf, page, ftype=ftype)
        if img:
            st.image(img, use_container_width=True)
        else:
            st.warning("Could not render page image")
            # Show text fallback
            if page < len(texts) and texts[page].strip():
                st.text_area("Page Text", texts[page][:2000], height=300, disabled=True)
        
        # --- Advanced Tools ---
        with st.expander("📚 Advanced Tools"):
            # Save to Cloud
            c1, c2 = st.columns([3, 1])
            c1.caption(f"**File:** {st.session_state.fname}")
            if supabase and c2.button("☁️ Save to Cloud"):
                if cloud_upload(st.session_state.pdf, st.session_state.fname):
                    st.success("Saved to cloud!")
            
            st.markdown("---")
            
            # Range Read
            st.markdown("**📖 Read Multiple Pages**")
            r1, r2 = st.columns(2)
            start = r1.number_input("Start Page", 1, pages, 1, key="r_start")
            end = r2.number_input("End Page", 1, pages, min(pages, 5), key="r_end")
            
            if st.button("▶️ Generate Range Audio", disabled=(start > end)):
                if start <= end:
                    all_audio = io.BytesIO()
                    prog = st.progress(0)
                    status_text = st.empty()
                    total = end - start + 1
                    success_count = 0
                    
                    for i, pg in enumerate(range(start - 1, end)):
                        if pg < len(texts):
                            status_text.text(f"Processing page {pg + 1} of {end}...")
                            prog.progress((i + 1) / total)
                            
                            t_chunk = texts[pg]
                            if smart_clean:
                                t_chunk = clean_text(t_chunk)
                            
                            if t_chunk.strip():
                                try:
                                    audio_chunk, s = make_audio(t_chunk, voice)
                                    if audio_chunk:
                                        all_audio.write(audio_chunk)
                                        success_count += 1
                                except Exception:
                                    pass
                            
                            time.sleep(0.1)  # Rate limiting
                    
                    prog.empty()
                    status_text.empty()
                    
                    result = all_audio.getvalue()
                    if len(result) > 100:
                        st.session_state.audio_data = result
                        st.session_state.reading_page = f"{start}-{end}"
                        st.success(f"Generated audio for {success_count} pages!")
                        st.rerun()
                    else:
                        st.error("Could not generate audio for the selected range")
            
            st.markdown("---")
            
            # Raw Text View
            st.markdown("**📝 Raw Text**")
            current_text = texts[page][:2000] if page < len(texts) else ""
            st.text_area("Page Content", current_text, height=150, disabled=True)
    
    else:
        # Welcome Screen
        st.info("👆 Upload a PDF or EPUB to get started, or load one from the cloud library in the sidebar.")
        
        st.markdown("""
        ### Features
        - 📄 **PDF & EPUB Support** - Upload and view documents
        - 🔊 **Text-to-Speech** - Listen to any page with natural voices
        - 📚 **Range Reading** - Generate audio for multiple pages
        - ☁️ **Cloud Storage** - Save and access documents anywhere
        - 📌 **Chapter Navigation** - Jump to chapters via table of contents
        """)

if __name__ == "__main__":
    main()
