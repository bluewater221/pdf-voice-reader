import streamlit as st
import fitz  # PyMuPDF
import edge_tts
import asyncio
import io
import uuid
import re
import time

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
    try:
        doc = fitz.open(stream=file_bytes, filetype=ftype)
        # Get TOC: list of [lvl, title, page, dest]
        toc = doc.get_toc() 
        return len(doc), [page.get_text() for page in doc], toc
    except Exception as e:
        st.error(f"Doc Error: {e}")
        return 0, [], []

def get_page_image(file_bytes, page_num, ftype="pdf"):
    try:
        doc = fitz.open(stream=file_bytes, filetype=ftype)
        pix = doc.load_page(page_num).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        return pix.tobytes("png")
    except:
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

# --- Smart Text Cleaning ---
def clean_text(text):
    """
    Cleans text by removing:
    1. Page numbers (e.g., "14", "Page 14", "14 of 30")
    2. CID artifacts (often invisible or weird chars)
    3. Excessive whitespace
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    # Regex for common page number patterns
    # Matches: "1", " 1 ", "- 1 -", "Page 1", "1 of 20"
    page_num_pattern = re.compile(r'^\s*(?:page\s*)?(\d+)(?:\s*of\s*\d+)?\s*[-]?\s*$', re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
            
        # Skip page numbers
        if page_num_pattern.match(stripped):
            continue
            
        # Skip likely headers/footers (short uppercase lines might be titles, keep them, but skip purely numeric or weird symbols)
        if len(stripped) < 4 and not stripped[0].isalnum(): 
            continue
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

# --- Cloud Storage ---
def cloud_upload(file_bytes, filename, bucket="pdfs"):
    if not supabase: return None
    try:
        # Check if exists
        files = supabase.storage.from_(bucket).list()
        if any(f['name'] == filename for f in files):
            st.toast(f"Switched to existing: {filename}", icon="📂")
            return filename
            
        supabase.storage.from_(bucket).upload(filename, file_bytes)
        return filename
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

# --- Navigation Callbacks ---
def nav_page(delta):
    new_p = st.session_state.page + delta
    if 0 <= new_p < st.session_state.pages:
        st.session_state.page = new_p
        st.session_state.audio_data = None
        st.session_state.last_action = f"Navigated delta {delta}"
        # Force sync slider
        if 'nav_slider' in st.session_state: 
            del st.session_state.nav_slider

def set_page(p):
    st.session_state.page = p
    st.session_state.audio_data = None
    st.session_state.last_action = f"Set page to {p}"
    # Force sync slider
    if 'nav_slider' in st.session_state: 
        del st.session_state.nav_slider

def set_page_from_input():
    if 'nav_goto' in st.session_state:
        st.session_state.page = st.session_state.nav_goto - 1
        st.session_state.audio_data = None
        st.session_state.last_action = f"Jumped to {st.session_state.page + 1}"

# --- Main ---
def main():
    st.set_page_config(layout="wide") # Ensure layout is valid even if main calls it late
    st.title("🎧 PDF Voice Reader")
    st.caption("⚡ Version 3.1 - Mobile Optimized")
    
    # Debug Mode
    if st.sidebar.checkbox("🐞 Debug Mode"):
        st.sidebar.markdown("### State Inspector")
        st.sidebar.write(f"**Current Page:** {st.session_state.get('page')}")
        st.sidebar.write(f"**Total Pages:** {st.session_state.get('pages')}")
        st.sidebar.write(f"**Last Action:** {st.session_state.get('last_action', 'None')}")
    
    if supabase:
        st.caption("☁️ Cloud storage connected")
    
    # Session state
    if 'pdf' not in st.session_state: st.session_state.pdf = None
    if 'ftype' not in st.session_state: st.session_state.ftype = "pdf"
    if 'page' not in st.session_state: st.session_state.page = 0
    if 'pages' not in st.session_state: st.session_state.pages = 0
    if 'texts' not in st.session_state: st.session_state.texts = []
    if 'toc' not in st.session_state: st.session_state.toc = []
    if 'fname' not in st.session_state: st.session_state.fname = ""

    # Sidebar
    with st.sidebar:
        st.header("🎤 Voice")
        voice_name = st.selectbox("Select", list(VOICES.keys()))
        voice = VOICES[voice_name]
        
        st.checkbox("✨ Smart Cleaning", value=True, key="smart_clean", help="Removes headers & page numbers")
        
        # Chapter Navigation
        if st.session_state.get('toc'):
            st.markdown("---")
            st.header("📌 Chapters")
            # Create mapping for valid pages
            chapter_map = {f"{item[1]} (Pg {item[2]})": item[2]-1 for item in st.session_state.toc if item[2] > 0}
            if chapter_map:
                sel_chap = st.selectbox("Jump to", ["Select..."] + list(chapter_map.keys()))
                if sel_chap != "Select..." and chapter_map[sel_chap] != st.session_state.page:
                    st.session_state.page = chapter_map[sel_chap]
                    st.rerun()

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
                                        ftype = selected_file.split('.')[-1].lower() if '.' in selected_file else "pdf"
                                        st.session_state.pdf = data
                                        p, t, toc = get_pdf_text(data, ftype)
                                        st.session_state.ftype = ftype
                                        if p > 0:
                                            st.session_state.pages = p
                                            st.session_state.texts = t
                                            st.session_state.toc = toc
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
    file = st.file_uploader("📄 Upload Document", type=["pdf", "epub"])
    
    if file:
        data = file.read()
        # Only update if different file to avoid reset on rerun
        if st.session_state.pdf != data:
            ftype = file.name.split('.')[-1].lower() if '.' in file.name else "pdf"
            if ftype not in ["pdf", "epub"]: ftype = "pdf"
            
            st.session_state.pdf = data
            p, t, toc = get_pdf_text(data, ftype)
            st.session_state.pages = p
            st.session_state.texts = t
            st.session_state.toc = toc
            st.session_state.page = 0
            st.session_state.fname = file.name
            st.session_state.ftype = ftype

    # Viewer (Checks Session State, not just Uploader)
    if st.session_state.pdf:
        # Initialize Audio State
        if 'audio_data' not in st.session_state:
            st.session_state.audio_data = None
            
        pages = st.session_state.pages
        texts = st.session_state.texts
        page = st.session_state.page
        ftype = st.session_state.get('ftype', 'pdf')
        
        if pages == 0:
            st.error("Cannot read PDF") 
            
        # --- Top Audio Player (Sticky) ---
        if 'audio_data' in st.session_state and st.session_state.audio_data:
            reading_info = st.session_state.get('reading_page', 'audio')
            ac1, ac2 = st.columns([4, 1])
            ac1.success(f"🎧 Playing: Page {reading_info}")
            ac2.download_button("📥 MP3", st.session_state.audio_data, "audio.mp3", "audio/mp3", key="dl_audio_top")
            st.audio(st.session_state.audio_data, format="audio/mp3")
            st.markdown("---")

        # --- Top Controls (Mobile Friendly) ---
        c_nav, c_act = st.columns([2, 1])
        
        with c_nav:
            n1, n2, n3 = st.columns([1, 1.2, 1])
            n1.button("◀", on_click=nav_page, args=(-1,), disabled=(page<=0), use_container_width=True)
            n2.number_input("Pg", 1, pages, page+1, key="nav_goto", label_visibility="collapsed", on_change=set_page_from_input)
            n3.button("▶", on_click=nav_page, args=(1,), disabled=(page>=pages-1), use_container_width=True)

        with c_act:
             if st.button("🔊 Read Page", type="primary", use_container_width=True):
                 text = texts[page] if page < len(texts) else ""
                 if st.session_state.get('smart_clean', False): text = clean_text(text)
                 
                 if text.strip():
                     with st.spinner("Generating..."):
                         audio, status = make_audio(text, voice)
                         if audio:
                             st.session_state.audio_data = audio
                             st.session_state.reading_page = page + 1
                             st.rerun()
                         else:
                             st.error("TTS Failed")
                 else:
                     st.warning("No text")

        # --- Image Display ---
        st.caption(f"📄 Page {page + 1} of {pages}")
        img = get_page_image(st.session_state.pdf, page, ftype=ftype)
        if img:
            st.image(img, use_container_width=True)
        else:
            st.warning("Cannot render page")

        # --- Bottom / Advanced Tools ---
        with st.expander("📚 Advanced Tools (Save, Range Read, Text)"):
            c1, c2 = st.columns([3, 1])
            c1.caption(f"File: {st.session_state.fname}")
            if supabase and c2.button("☁️ Save to Cloud"):
                if cloud_upload(st.session_state.pdf, st.session_state.fname): st.success("Saved!")

            st.markdown("---")
            st.markdown("**Read Multiple Pages**")
            r1, r2 = st.columns(2)
            start = r1.number_input("Start", 1, pages, 1, key="r_start")
            end = r2.number_input("End", 1, pages, min(pages, 5), key="r_end")
            
            if start <= end and st.button("Start Range Read"):
                 all_audio = io.BytesIO()
                 prog = st.progress(0)
                 stat = st.empty()
                 total = end - start + 1
                 
                 for i, pg in enumerate(range(start - 1, end)):
                     if pg < len(texts):
                         stat.text(f"Reading page {pg+1}...")
                         prog.progress((i + 1) / total)
                         t_chunk = texts[pg]
                         if st.session_state.get('smart_clean', False): t_chunk = clean_text(t_chunk)
                         
                         try:
                             audio_chunk, s = make_audio(t_chunk, voice)
                             if audio_chunk: 
                                 all_audio.write(audio_chunk)
                                 time.sleep(0.1)
                             else:
                                 st.warning(f"Skipped {pg+1}")
                         except: pass
                 
                 res_audio = all_audio.getvalue()
                 if len(res_audio) > 100:
                     st.session_state.audio_data = res_audio
                     st.session_state.reading_page = f"{start}-{end}"
                     st.session_state.last_action = f"Generated Range {start}-{end}"
                     st.rerun()
                 else:
                     stat.error("Failed")

            st.markdown("---")
            st.text_area("Raw Text", texts[page][:1500] if page < len(texts) else "", height=150)
    
    else:
        st.info("👆 Upload a PDF to start (or load from cloud)")

if __name__ == "__main__":
    main()
