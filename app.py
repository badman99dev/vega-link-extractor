import os
import time
from flask import Flask, render_template, request, Response, stream_with_context
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

app = Flask(__name__)

BROWSERLESS_API_KEY = os.environ.get("BROWSERLESS_API_KEY", "YOUR_API_KEY_HERE_IF_TESTING_LOCALLY")

def generate_logs(vegamovies_url):
    driver = None
    start_time = time.time()

    def stream_log(message):
        elapsed_time = f"[{time.time() - start_time:.2f}s]"
        # Server-Sent Event format: data: <message>\n\n
        return f"data: {elapsed_time} {message}\n\n"

    try:
        yield stream_log("▶️ LOG STREAM INITIATED. Preparing scraper...")
        
        # --- Stage 1: Configuration ---
        yield stream_log("[CONFIG] Setting up Chrome options for remote browser.")
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080") # Set a window size

        b_options = {
            "browserless.apiKey": BROWSERLESS_API_KEY,
            "browserless.stealth": True,
            "browserless.timeout": 90000 # Timeout badha kar 90s kar diya hai
        }
        options.set_capability('goog:chromeOptions', {'args': [], **b_options})
        yield stream_log("[CONFIG] Chrome options configured successfully.")

        # --- Stage 2: Connection ---
        yield stream_log("🔄 [CONNECT] Attempting to establish a WebDriver session with Browserless.io...")
        driver = webdriver.Remote(
            command_executor="https://production-sfo.browserless.io/webdriver",
            options=options
        )
        yield stream_log(f"✅ [CONNECT] WebDriver session created successfully! Session ID: {driver.session_id}")

        # --- Stage 3: Navigation ---
        yield stream_log(f"🌐 [NAVIGATE] Loading the target URL: {vegamovies_url}")
        driver.get(vegamovies_url)
        yield stream_log(f"✅ [NAVIGATE] Page loaded. Current page title: '{driver.title}'")

        # --- Stage 4: Iframe Search and Switch ---
        yield stream_log("⏳ [IFRAME] Searching for the player iframe with selector '#IndStreamPlayer iframe'...")
        
        wait = WebDriverWait(driver, 60) # Increased wait time to 60 seconds
        iframe_selector = (By.CSS_SELECTOR, "#IndStreamPlayer iframe")
        
        iframe_element = wait.until(EC.presence_of_element_located(iframe_selector))
        yield stream_log("👍 [IFRAME] Found the iframe element. Now attempting to switch context...")
        
        driver.switch_to.frame(iframe_element)
        yield stream_log("✅ [IFRAME] Switched to player iframe context successfully.")

        # --- Stage 5: Video Element Search ---
        yield stream_log("🎬 [VIDEO] Searching for the <video> tag within the iframe...")
        video_element_selector = (By.TAG_NAME, "video")
        video_element = wait.until(EC.presence_of_element_located(video_element_selector))
        
        yield stream_log("👍 [VIDEO] Found the <video> element. Extracting the 'src' attribute...")
        direct_link = video_element.get_attribute("src")
        
        if direct_link:
            yield stream_log(f"✨ BINGO! Direct video link found: {direct_link[:50]}...") # Link ka preview dikhayenge
            yield f"data: --LINK--{direct_link}\n\n"
        else:
            yield stream_log("❌ [VIDEO] CRITICAL: <video> element found, but it has no 'src' attribute. The player might have loaded differently.")

        yield stream_log("🏁 SCRAPING PROCESS FINISHED SUCCESSFULLY.")

    except TimeoutException as e:
        error_message = f"❌ CRITICAL ERROR: Timeout! The process got stuck waiting for an element that never appeared. This is the most common error. It could mean the page structure has changed or the site is slow.\n\nPython Exception Details: {str(e).splitlines()[0]}"
        yield stream_log(error_message)
    except WebDriverException as e:
        error_details = str(e)
        if "session not created" in error_details.lower():
             error_message = f"❌ CRITICAL ERROR: WebDriver session could not be created. This almost always means your API Key is incorrect or your Browserless.io account has run out of usage credits.\n\nPython Exception Details: {error_details.splitlines()[0]}"
        else:
             error_message = f"❌ CRITICAL ERROR: A WebDriver error occurred. This could be a temporary network issue with Browserless.io or a code incompatibility.\n\nPython Exception Details: {error_details.splitlines()[0]}"
        yield stream_log(error_message)
    except Exception as e:
        error_message = f"❌ UNKNOWN ERROR: An unexpected error happened. This is likely a bug in the script.\n\nPython Exception Details: {str(e)}"
        yield stream_log(error_message)
    
    finally:
        if driver:
            yield stream_log("🚪 [CLEANUP] Closing browser session...")
            driver.quit()
            yield stream_log("✅ [CLEANUP] Session closed.")
        yield f"data: --END-OF-STREAM--\n\n"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream-logs')
def stream_logs():
    url = request.args.get('url')
    if not url:
        def error_stream():
            yield f"data: ❌ ERROR: URL parameter is missing in the request.\n\n"
            yield f"data: --END-OF-STREAM--\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream')

    return Response(stream_with_context(generate_logs(url)), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)
