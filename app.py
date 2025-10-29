import os
import time
from flask import Flask, render_template, request, Response, stream_with_context
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

app = Flask(__name__)

# Temporary test - Environment variable ko bypass kar rahe hain
BROWSERLESS_API_KEY = "2TKGVGBV4K04wYe3b36e7aaf2431193206e93a6c29fc9ce27"
def generate_logs(vegamovies_url):
    """
    Yeh ek generator function hai jo scraping process ke live logs ko stream karta hai.
    """
    driver = None
    try:
        # Har log message ko is format me bhejna zaroori hai SSE ke liye
        def stream_log(message):
            return f"data: {message}\n\n"

        yield stream_log("▶️ Process started...")
        yield stream_log("🔄 Connecting to headless browser via Browserless.io...")
        
        options = webdriver.ChromeOptions()
        options.set_capability(
            "browserless:options",
            {
                "apiKey": BROWSERLESS_API_KEY,
                "stealth": True,
                "timeout": 60000, # 60 seconds ka timeout
            },
        )
        
        driver = webdriver.Remote(
            command_executor="https://chrome.browserless.io/webdriver",
            options=options
        )
        yield stream_log("✅ Connection successful!")
        
        yield stream_log(f"🌐 Navigating to URL: {vegamovies_url}")
        driver.get(vegamovies_url)
        yield stream_log("✅ Page navigation complete.")

        yield stream_log("⏳ Waiting for the player iframe to become available...")
        
        wait = WebDriverWait(driver, 45) # Timeout badha diya 45 seconds tak
        iframe_selector = (By.CSS_SELECTOR, "#IndStreamPlayer iframe")
        
        wait.until(EC.frame_to_be_available_and_switch_to_it(iframe_selector))
        yield stream_log("✅ Switched to player iframe successfully.")

        yield stream_log("🎬 Searching for the main video element inside the iframe...")
        video_element_selector = (By.TAG_NAME, "video")
        video_element = wait.until(EC.presence_of_element_located(video_element_selector))
        
        direct_link = video_element.get_attribute("src")
        
        if direct_link:
            yield stream_log("✨ BINGO! Direct video link found!")
            # Link ko ek special format me bhejenge taaki JS use aasaani se pehchaan le
            yield f"data: --LINK--{direct_link}\n\n"
        else:
            yield stream_log("❌ Error: Video element found, but it has no 'src' link.")

        yield stream_log("🏁 Process finished.")

    except TimeoutException as e:
        error_message = f"❌ ERROR: Timeout! Element not found or page took too long to load. (Details: {str(e).splitlines()[0]})"
        yield stream_log(error_message)
    except WebDriverException as e:
        error_message = f"❌ ERROR: WebDriver issue. Could be a problem with Browserless.io connection. (Details: {str(e).splitlines()[0]})"
        yield stream_log(error_message)
    except Exception as e:
        error_message = f"❌ ERROR: An unexpected error occurred: {str(e)}"
        yield stream_log(error_message)
    
    finally:
        if driver:
            yield stream_log("🚪 Closing browser session...")
            driver.quit()
            yield stream_log("✅ Session closed.")
        # Special message to signal the end of the stream
        yield "data: --END-OF-STREAM--\n\n"


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream-logs')
def stream_logs():
    url = request.args.get('url')
    if not url:
        def error_stream():
            yield "data: ❌ ERROR: URL parameter is missing.\n\n"
            yield "data: --END-OF-STREAM--\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream')

    return Response(stream_with_context(generate_logs(url)), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)
