import asyncio
import edge_tts
import re
import io

# --- Mock Text ---
SAMPLE_TEXT = """
Page 1
This is a sample text for testing.
1
Chapter 1
It should be read clearly.
"""

# --- Functions from app.py ---
def clean_text(text):
    lines = text.split('\n')
    cleaned_lines = []
    page_num_pattern = re.compile(r'^\s*(?:page\s*)?(\d+)(?:\s*of\s*\d+)?\s*[-]?\s*$', re.IGNORECASE)
    
    print(f"DEBUG: Processing {len(lines)} lines")
    
    for line in lines:
        stripped = line.strip()
        if not stripped: continue
        if page_num_pattern.match(stripped):
            print(f"Skipped Page Num: {stripped}")
            continue
        if len(stripped) < 4 and not stripped[0].isalnum(): 
            print(f"Skipped Artifact: {stripped}")
            continue
        
        cleaned_lines.append(line)
    
    result = '\n'.join(cleaned_lines)
    print(f"DEBUG: Cleaned Text:\n---\n{result}\n---")
    return result

async def _generate_audio(text, voice="en-US-JennyNeural"):
    print(f"DEBUG: Generating Audio for: {text[:20]}...")
    communicate = edge_tts.Communicate(text, voice)
    audio_data = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])
    val = audio_data.getvalue()
    print(f"DEBUG: Generated {len(val)} bytes")
    return val

def run_test():
    print("1. Testing Cleaner...")
    clean = clean_text(SAMPLE_TEXT)
    
    print("\n2. Testing TTS...")
    if clean.strip():
        try:
            audio = asyncio.run(_generate_audio(clean))
            print("SUCCESS: Audio verify OK")
        except Exception as e:
            print(f"FAIL: TTS Error: {e}")
    else:
        print("FAIL: Text is empty after cleaning")

if __name__ == "__main__":
    run_test()
