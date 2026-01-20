import streamlit as st
import time
import re
import base64
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Try importing for local dev, handle failure for Cloud
try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

# 1. Page Configuration
st.set_page_config(
    page_title="Scribd to PDF",
    page_icon="📖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# 2. Custom CSS for UI Polish
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        font-weight: bold;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# 3. Sidebar (Instructions & Disclaimer)
with st.sidebar:
    st.header("📖 How to use")
    st.markdown("""
    1. Go to Scribd and open a document.
    2. Copy the URL (e.g., `www.scribd.com/document/...`).
    3. Paste it in the input field.
    4. Click **Convert to PDF**.
    """)
    
    st.divider()
    
    st.info("""
    **Note:** This tool lazily scrolls through the document to ensure images render before printing.
    """)
    st.caption("⚠️ For educational purposes only. Please respect copyright laws.")

# 4. Helper Functions
def convert_scribd_link(url):
    match = re.search(r'https://www\.scribd\.com/document/(\d+)/', url)
    if match:
        doc_id = match.group(1)
        return f'https://www.scribd.com/embeds/{doc_id}/content'
    return None

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Cloud vs Local Logic
    if os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
    else:
        if ChromeDriverManager:
            service = Service(ChromeDriverManager().install())
        else:
            st.error("❌ Driver not found. Please install webdriver-manager locally.")
            return None

    return webdriver.Chrome(service=service, options=chrome_options)

def generate_pdf(target_url, status_container):
    driver = setup_driver()
    if not driver:
        return None
    
    try:
        # Step 1: Load
        status_container.write("🌐 Launching browser...")
        driver.get(target_url)
        time.sleep(3)

        # Step 2: Scroll
        status_container.write("📜 Scrolling to render pages (this takes time)...")
        page_elements = driver.find_elements("css selector", "[class*='page']")
        
        # Simple progress bar inside the status container
        progress_bar = status_container.progress(0)
        total_pages = len(page_elements)
        
        for index, page in enumerate(page_elements):
            driver.execute_script("arguments[0].scrollIntoView();", page)
            time.sleep(0.4) # Optimized timing
            if total_pages > 0:
                progress_bar.progress(min((index + 1) / total_pages, 1.0))
        
        time.sleep(1) 
        
        # Step 3: Cleanup
        status_container.write("🧹 Removing banners and cookies...")
        cleanup_script = """
        // Remove standard toolbars
        document.querySelectorAll('.toolbar_top, .toolbar_bottom').forEach(el => el.remove());
        
        // Remove scroller styles
        var scrollers = document.getElementsByClassName("document_scroller");
        for (var i = 0; i < scrollers.length; i++) { scrollers[i].setAttribute('class', ''); }
        
        // Remove promos
        document.querySelectorAll('[class*="promo"]').forEach(el => el.remove());
        
        // Remove OneTrust/Cookie Banners
        var ids = ['onetrust-consent-sdk', 'onetrust-banner-sdk'];
        ids.forEach(id => {
            var el = document.getElementById(id);
            if(el) el.remove();
        });

        // Text content fallback removal
        document.querySelectorAll('div, footer').forEach(el => {
            if (el.textContent && el.textContent.includes('This website utilizes technologies such as cookies')) {
                el.remove();
            }
        });
        
        // CSS Injection
        var style = document.createElement('style');
        style.textContent = `
            @media print {
                @page { margin: 0; }
                body { background-color: white; }
                .toolbar_top, .toolbar_bottom, .promo_banner, #onetrust-consent-sdk { display: none !important; }
            }
        `;
        document.head.appendChild(style);
        """
        driver.execute_script(cleanup_script)
        
        # Step 4: Print
        status_container.write("🖨️ Generating PDF...")
        pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "preferCSSPageSize": True,
            "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0
        })
        
        return base64.b64decode(pdf_data['data'])

    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None
    finally:
        driver.quit()

# 5. Main UI Layout
st.title("📖 Scribd Downloader")
st.write("Convert Scribd documents to PDF for offline reading.")

url_input = st.text_input("Document URL", placeholder="Paste https://www.scribd.com/document/... here")

# Check if URL is entered before showing the button
if url_input:
    # Use columns to make the button not span the whole width if desired, 
    # but full width (via CSS above) looks good on mobile.
    if st.button("🚀 Convert to PDF", type="primary"):
        embed_url = convert_scribd_link(url_input)
        
        if embed_url:
            # The 'st.status' container is great for multi-step processes
            with st.status("Processing document...", expanded=True) as status:
                pdf_bytes = generate_pdf(embed_url, status)
                
                if pdf_bytes:
                    status.update(label="✅ Conversion Complete!", state="complete", expanded=False)
                    
                    # Success UI
                    st.balloons()
                    
                    # Extract ID for filename
                    doc_id = re.search(r'embeds/(\d+)/', embed_url).group(1)
                    file_name = f"scribd_doc_{doc_id}.pdf"
                    
                    st.success("Your document is ready!")
                    
                    col1, col2, col3 = st.columns([1,2,1])
                    with col2:
                        st.download_button(
                            label="⬇️ Download PDF",
                            data=pdf_bytes,
                            file_name=file_name,
                            mime="application/pdf",
                            type="primary"
                        )
        else:
            st.toast("Invalid URL format. Please check the link.", icon="⚠️")
else:
    st.info("Paste a URL above to get started.")
