import streamlit as st
import time
import re
import base64
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
# We wrap the import to prevent errors if running locally without the manager installed
try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

# Page Config
st.set_page_config(page_title="Scribd Downloader", page_icon="📄")

st.title("📄 Scribd Document Downloader")
st.markdown("""
This app converts a Scribd document URL into a downloadable PDF.
*Note: This tool is for educational purposes only.*
""")

# Input URL
url = st.text_input("Enter Scribd Document URL", placeholder="https://www.scribd.com/document/123456789/Example-Document")

def convert_scribd_link(url):
    """Converts a standard Scribd URL to the embed/content URL."""
    match = re.search(r'https://www\.scribd\.com/document/(\d+)/', url)
    if match:
        doc_id = match.group(1)
        return f'https://www.scribd.com/embeds/{doc_id}/content'
    return None

def setup_driver():
    """Configures the Chrome WebDriver for headless execution."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # ---------------------------------------------------------
    # FIX FOR STREAMLIT CLOUD
    # ---------------------------------------------------------
    # Check if we are running on Streamlit Cloud (Debian) by looking for the binary
    if os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
    else:
        # Fallback for local development (Windows/Mac)
        if ChromeDriverManager:
            service = Service(ChromeDriverManager().install())
        else:
            st.error("Webdriver Manager not found and not on Linux. Please install it.")
            return None

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def generate_pdf(target_url):
    driver = setup_driver()
    if not driver:
        return None
        
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    try:
        # 1. Load Page
        status_text.info("Launching browser and loading document...")
        driver.get(target_url)
        time.sleep(3) # Wait for initial load

        # 2. Scroll to load all pages (Lazy Loading)
        status_text.info("Scrolling through document to load all pages...")
        page_elements = driver.find_elements("css selector", "[class*='page']")
        total_pages = len(page_elements)
        
        for index, page in enumerate(page_elements):
            driver.execute_script("arguments[0].scrollIntoView();", page)
            time.sleep(0.5) # Slight delay to let images render
            
            # Update progress
            if total_pages > 0:
                progress = min((index + 1) / total_pages, 1.0)
                progress_bar.progress(progress)
        
        time.sleep(2) # Final wait after scrolling
        
        # 3. Clean up DOM (Remove toolbars and promo banners)
        status_text.info("Cleaning up page elements...")
        # 3. Clean up DOM (Remove toolbars, promo banners, and cookie footers)
        status_text.info("Cleaning up page elements...")
        
        cleanup_script = """
        // 1. Remove standard Scribd toolbars
        var toolbarTop = document.querySelector('.toolbar_top');
        if (toolbarTop) toolbarTop.remove();

        var toolbarBottom = document.querySelector('.toolbar_bottom');
        if (toolbarBottom) toolbarBottom.remove();
        
        // 2. Remove document scroller wrappers to simplify structure
        var scrollers = document.getElementsByClassName("document_scroller");
        for (var i = 0; i < scrollers.length; i++) {
            scrollers[i].setAttribute('class', '');
        }
        
        // 3. Remove "Read free for 30 days" promos
        var promos = document.querySelectorAll('[class*="promo"]');
        promos.forEach(el => el.remove());
        
        // 4. REMOVE COOKIE/PRIVACY BANNER (The yellow footer)
        // Try common OneTrust IDs
        var otHost = document.getElementById('onetrust-consent-sdk');
        if (otHost) otHost.remove();
        
        var otBanner = document.getElementById('onetrust-banner-sdk');
        if (otBanner) otBanner.remove();

        // 5. Fallback: Find and remove any container with the specific cookie text
        var allDivs = document.querySelectorAll('div, footer, section');
        allDivs.forEach(el => {
            if (el.textContent.includes('This website utilizes technologies such as cookies')) {
                el.style.display = 'none';
                el.remove();
            }
        });

        // 6. Inject CSS for clean printing
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
        driver.execute_script(cleanup_script)
        
        # 4. Generate PDF via CDP
        status_text.info("Generating PDF file...")
        
        pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "preferCSSPageSize": True,
            "marginTop": 0,
            "marginBottom": 0,
            "marginLeft": 0,
            "marginRight": 0
        })
        
        return base64.b64decode(pdf_data['data'])

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None
    finally:
        driver.quit()
        status_text.empty()
        progress_bar.empty()

# Main App Logic
if st.button("Download PDF"):
    if not url:
        st.warning("Please enter a valid URL.")
    else:
        embed_url = convert_scribd_link(url)
        
        if embed_url:
            with st.spinner("Processing... This may take a minute depending on document length."):
                pdf_bytes = generate_pdf(embed_url)
                
                if pdf_bytes:
                    st.success("PDF generated successfully!")
                    
                    # Create a valid filename
                    doc_id = re.search(r'embeds/(\d+)/', embed_url).group(1)
                    file_name = f"scribd_doc_{doc_id}.pdf"
                    
                    st.download_button(
                        label="⬇️ Save PDF",
                        data=pdf_bytes,
                        file_name=file_name,
                        mime="application/pdf"
                    )
        else:
            st.error("Invalid Scribd URL. It should look like: https://www.scribd.com/document/12345/Name")
